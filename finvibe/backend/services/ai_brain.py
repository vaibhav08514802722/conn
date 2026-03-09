"""
AI Brain — Autonomous stock trading engine for the $1M shadow portfolio.

The brain performs a full investment cycle:
1. SCAN   — discover trending / top-performing stocks globally
2. ANALYZE — deep-analyze each candidate with Gemini LLM
3. REVIEW  — check existing holdings: hold, buy more, or sell
4. EXECUTE — place virtual trades and update the shadow portfolio in MongoDB
5. LOG     — record every decision with rationale for full transparency

Designed to behave like a real human fund manager.
"""
import json
import re
import random
import time
import uuid
import traceback
import requests
from datetime import datetime, timezone
from typing import Optional

from backend.config import settings
from backend.deps import get_llm_client, get_market_sentiments_col, get_active_model
from backend.services.market_service import get_stock_price, get_latest_news
from backend.services.portfolio_service import (
    get_portfolio,
    create_portfolio,
    update_holdings,
    record_trade,
    get_trade_logs,
)

import logging
logger = logging.getLogger("ai_brain")
logger.setLevel(logging.DEBUG)

# ────────────────────── Constants ───────────────────────────────────────────

AGENT_USER = "finvibe-agent"
PORTFOLIO_TYPE = "shadow"
MAX_POSITION_PCT = 0.12          # max 12% of capital in one stock
MIN_TRADE_VALUE = 500            # minimum trade amount
MAX_SCAN_CANDIDATES = 12         # Groq allows 30 req/min — plenty of headroom
MAX_HOLDINGS = 20                # max simultaneous positions
RATELIMIT_BASE_WAIT = 3          # seconds to wait on 429 before retry (Groq is fast)

# Stock universe — well-known liquid tickers (India-heavy + global)
STOCK_UNIVERSE = [
    # ── India — Nifty 50 + Nifty Next 50 + popular mid-caps ──
    # Large-cap IT
    "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "LTI.NS",
    "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "LTTS.NS",
    # Large-cap Banking & Finance
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "INDUSINDBK.NS", "BANDHANBNK.NS",
    "PNB.NS", "BANKBARODA.NS", "IDFCFIRSTB.NS", "SBILIFE.NS", "HDFCLIFE.NS",
    "ICICIPRULI.NS", "MUTHOOTFIN.NS",
    # Large-cap Conglomerate / Energy / Industrial
    "RELIANCE.NS", "ADANIENT.NS", "ADANIPORTS.NS", "ADANIGREEN.NS",
    "ADANIPOWER.NS", "LT.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS",
    "COALINDIA.NS", "BPCL.NS", "IOC.NS", "GAIL.NS", "TATAPOWER.NS",
    # FMCG & Consumer
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS",
    "MARICO.NS", "GODREJCP.NS", "COLPAL.NS", "TATACONSUM.NS", "VBL.NS",
    # Auto & EV
    "TATAMOTORS.NS", "MARUTI.NS", "M&M.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "ASHOKLEY.NS", "TVSMOTOR.NS",
    # Pharma & Healthcare
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "BIOCON.NS", "AUROPHARMA.NS", "LUPIN.NS", "TORNTPHARM.NS",
    # Telecom & Media
    "BHARTIARTL.NS", "IDEA.NS",
    # Metals & Cement
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS",
    "ULTRACEMCO.NS", "SHREECEM.NS", "AMBUJACEM.NS", "GRASIM.NS",
    # Mid-cap growth (popular on Groww/Zerodha)
    "IRCTC.NS", "ZOMATO.NS", "PAYTM.NS", "POLICYBZR.NS", "NYKAA.NS",
    "DELHIVERY.NS", "DIXON.NS", "TRENT.NS", "PIIND.NS", "ASTRAL.NS",
    "DEEPAKNTR.NS", "ATUL.NS", "NAVINFLUOR.NS", "HAPPSTMNDS.NS",
    "ROUTE.NS", "LICI.NS", "JIOFIN.NS", "CAMS.NS",
    # Defence & PSU
    "HAL.NS", "BEL.NS", "BHEL.NS", "IRFC.NS", "RVNL.NS",
    "COCHINSHIP.NS", "MAZAGON.NS",
    # India BSE (some stocks only on BSE)
    "RELIANCE.BO", "TCS.BO", "HDFCBANK.BO", "INFY.BO",

    # ── US — Top 30 most liquid ──
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD",
    "NFLX", "CRM", "ORCL", "ADBE", "PYPL", "UBER", "COIN",
    "JPM", "GS", "V", "MA", "BRK-B",
    "JNJ", "UNH", "LLY", "PFE", "MRK",
    "XOM", "BA", "CAT",
    "WMT", "KO",

    # ── Europe & Asia ──
    "ASML", "SAP", "NVO", "AZN", "SHEL",
    "TSM", "BABA", "9988.HK", "005930.KS", "7203.T",
]

YAHOO_SCREENER_IDS = [
    "day_gainers",
    "most_actives",
    "undervalued_growth_stocks",
    "growth_technology_stocks",
]

# ── Financial Modeling Prep (FMP) — global stock API ──
FMP_BASE = "https://financialmodelingprep.com/stable"


def _fmp_key() -> str:
    """Get FMP API key from settings (empty string if not set)."""
    return getattr(settings, "fmp_api_key", "") or ""


def _fetch_fmp_gainers_losers() -> list[str]:
    """Fetch today's top gainers, losers, and most-active from FMP /stable/ API."""
    key = _fmp_key()
    if not key:
        return []
    symbols: list[str] = []
    # Correct /stable/ endpoint names (verified working on free tier)
    for endpoint in ["biggest-gainers", "biggest-losers", "most-actives"]:
        try:
            resp = requests.get(
                f"{FMP_BASE}/{endpoint}",
                params={"apikey": key},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    for item in data[:30]:
                        sym = (item.get("symbol") or "").strip().upper()
                        if sym and sym not in symbols:
                            symbols.append(sym)
            else:
                logger.warning(f"[FMP] {endpoint} HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"[FMP] {endpoint} error: {e}")
    logger.info(f"[FMP] Movers fetched: {len(symbols)} symbols")
    return symbols


def _fetch_fmp_screener(
    market_cap_min: int = 1_000_000_000,
    volume_min: int = 500_000,
    limit: int = 50,
    sector: str = "",
    exchange: str = "",
    country: str = "",
) -> list[str]:
    """
    FMP Company Screener via /stable/company-screener.
    Requires PAID plan (free tier returns 402). Kept as fallback for paid users.
    """
    key = _fmp_key()
    if not key:
        return []
    try:
        params: dict = {
            "apikey": key,
            "marketCapMoreThan": market_cap_min,
            "volumeMoreThan": volume_min,
            "limit": limit,
            "isActivelyTrading": "true",
        }
        if sector:
            params["sector"] = sector
        if exchange:
            params["exchange"] = exchange
        if country:
            params["country"] = country

        resp = requests.get(f"{FMP_BASE}/company-screener", params=params, timeout=20)
        if resp.status_code in (402, 403):
            # Paid-only endpoint — silent skip on free tier
            return []
        if resp.status_code != 200:
            logger.warning(f"[FMP Screener] HTTP {resp.status_code}")
            return []
        data = resp.json()
        symbols = []
        for item in data:
            sym = (item.get("symbol") or "").strip().upper()
            if sym and sym not in symbols:
                symbols.append(sym)
        return symbols
    except Exception as e:
        logger.warning(f"[FMP Screener] error: {e}")
        return []


def _fetch_fmp_exchange_stocks(exchange: str = "NSE", limit: int = 80) -> list[str]:
    """
    Search for stocks on a specific exchange via FMP /stable/search-symbol (FREE tier).
    Uses search queries for popular Indian/global companies.
    Returns Yahoo-format tickers (.NS for NSE, .BO for BSE).
    """
    key = _fmp_key()
    if not key:
        return []

    suffix_map = {"NSE": ".NS", "BSE": ".BO", "NASDAQ": "", "NYSE": "", "LSE": ".L", "HKSE": ".HK"}
    suffix = suffix_map.get(exchange, "")

    # Search queries designed to discover stocks on the target exchange
    search_queries = {
        "NSE": ["Reliance", "Tata", "Infosys", "HDFC", "ICICI", "Wipro", "Bajaj",
                "Maruti", "Adani", "Bharti", "SBI", "Kotak", "HUL", "ITC",
                "Sun Pharma", "Axis", "Titan", "Nestle", "Power Grid", "NTPC"],
        "BSE": ["Reliance", "Tata", "Infosys", "HDFC", "ICICI", "Wipro", "Bajaj",
                "Adani", "Coal India", "Zomato"],
        "NASDAQ": ["Apple", "Microsoft", "Google", "Amazon", "Tesla", "NVIDIA",
                   "Meta", "Netflix", "AMD", "Intel"],
        "NYSE": ["JPMorgan", "Goldman", "Visa", "Johnson", "Procter", "Walmart",
                 "Disney", "Coca", "Boeing", "Pfizer"],
    }
    queries = search_queries.get(exchange, ["Apple", "Google", "Tesla"])

    symbols: list[str] = []
    for query in queries:
        if len(symbols) >= limit:
            break
        try:
            resp = requests.get(
                f"{FMP_BASE}/search-symbol",
                params={"query": query, "apikey": key, "limit": 10, "exchange": exchange},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not isinstance(data, list):
                continue
            for item in data:
                item_exchange = (item.get("exchange") or "").upper()
                if item_exchange != exchange.upper():
                    continue
                sym = (item.get("symbol") or "").strip().upper()
                if not sym:
                    continue
                # FMP already returns suffixed symbols like RELIANCE.NS
                if sym not in symbols:
                    symbols.append(sym)
        except Exception as e:
            logger.debug(f"[FMP Search] {exchange}/{query} error: {e}")

    logger.info(f"[FMP Search] {exchange}: {len(symbols)} stocks found via search")
    return symbols[:limit]


def _fetch_nse_top_stocks() -> list[str]:
    """
    Fetch top NSE India stocks from public NSE API.
    Returns Yahoo-format tickers (.NS suffix).
    """
    symbols: list[str] = []
    # Primary: NSE equity list (publicly accessible JSON)
    nse_urls = [
        "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050",
        "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20NEXT%2050",
        "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20MIDCAP%2050",
        "https://www.nseindia.com/api/live-analysis-variations?index=gainers",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    session = requests.Session()
    # NSE requires a cookie — hit homepage first
    try:
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
    except Exception:
        pass

    for url in nse_urls:
        try:
            resp = session.get(url, headers=headers, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            stocks = data.get("data", [])
            for stock in stocks:
                sym = (stock.get("symbol") or "").strip().upper()
                if sym and sym != "NIFTY 50" and sym != "NIFTY NEXT 50":
                    yf_sym = f"{sym}.NS"
                    if yf_sym not in symbols:
                        symbols.append(yf_sym)
        except Exception as e:
            logger.debug(f"[NSE] {url} error: {e}")
    logger.info(f"[NSE] Fetched {len(symbols)} Indian stocks")
    return symbols


# ────────────────────── Helpers ─────────────────────────────────────────────

def _get_ticker_vibe(ticker: str) -> dict:
    try:
        doc = get_market_sentiments_col().find_one(
            {"ticker": ticker.upper()},
            {"_id": 0},
            sort=[("analyzed_at", -1)],
        )
        return doc or {}
    except Exception:
        return {}


def _derive_vibe_from_price(price_data: dict) -> dict:
    """Fallback vibe inference from daily movement when no stored sentiment exists."""
    change = float(price_data.get("change_pct", 0) or 0)
    if change >= 2:
        return {"vibe_label": "bullish", "anxiety_score": 3.0, "sentiment_score": 0.6}
    if change >= 0.5:
        return {"vibe_label": "cautious bullish", "anxiety_score": 4.5, "sentiment_score": 0.25}
    if change <= -2:
        return {"vibe_label": "panic", "anxiety_score": 8.4, "sentiment_score": -0.65}
    if change <= -0.5:
        return {"vibe_label": "bearish", "anxiety_score": 6.7, "sentiment_score": -0.3}
    return {"vibe_label": "neutral", "anxiety_score": 5.0, "sentiment_score": 0.0}


def _fetch_screener_symbols(scr_id: str, count: int = 100) -> list[str]:
    """Fetch symbols from Yahoo Finance predefined screener."""
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved"
        params = {
            "scrIds": scr_id,
            "count": count,
            "formatted": "false",
        }
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code != 200:
            logger.warning(f"[Brain Universe] screener={scr_id} http={resp.status_code}")
            return []

        payload = resp.json()
        quotes = (
            payload.get("finance", {})
            .get("result", [{}])[0]
            .get("quotes", [])
        )
        symbols = []
        for quote in quotes:
            symbol = (quote.get("symbol") or "").strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
        return symbols
    except Exception as e:
        logger.warning(f"[Brain Universe] screener={scr_id} error={e}")
        return []


def get_dynamic_stock_universe(target_size: int = 300) -> list[str]:
    """
    Build a dynamic stock universe from multiple live APIs.
    Priority order (India-first):
      1. NSE India direct API (Nifty 50/100/Midcap + gainers)
      2. FMP stock list — NSE + BSE (FREE tier, no 403)
      3. FMP real-time movers (gainers/losers/actives — FREE tier)
      4. Yahoo Finance screeners (backup)
      5. Static STOCK_UNIVERSE (guaranteed fallback)
    """
    symbols: list[str] = []

    def _add(new_syms: list[str]):
        for s in new_syms:
            if s and s not in symbols:
                symbols.append(s)

    # ── 1. NSE India direct ──
    _add(_fetch_nse_top_stocks())
    logger.info(f"[Brain Universe] After NSE India: {len(symbols)} symbols")

    # ── 2. FMP search — Indian exchanges (FREE tier, uses /search-symbol) ──
    _add(_fetch_fmp_exchange_stocks("NSE", limit=80))
    _add(_fetch_fmp_exchange_stocks("BSE", limit=40))
    logger.info(f"[Brain Universe] After FMP India search: {len(symbols)} symbols")

    # ── 3. FMP real-time movers (FREE tier) ──
    _add(_fetch_fmp_gainers_losers())
    logger.info(f"[Brain Universe] After FMP movers: {len(symbols)} symbols")

    # ── 4. Yahoo screeners (backup) ──
    for scr_id in YAHOO_SCREENER_IDS:
        fetched = _fetch_screener_symbols(scr_id, count=50)
        _add(fetched)
        if len(symbols) >= target_size:
            break
    logger.info(f"[Brain Universe] After Yahoo screeners: {len(symbols)} symbols")

    # ── 5. Static fallback (always include core list) ──
    _add(STOCK_UNIVERSE)

    if not symbols:
        return STOCK_UNIVERSE[:]

    logger.info(f"[Brain Universe] Final universe: {len(symbols)} symbols")
    return symbols[:target_size]


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response text using multiple strategies."""
    if not text:
        return None

    cleaned = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first { ... } block via bracket matching
    first_brace = cleaned.find("{")
    if first_brace != -1:
        depth = 0
        for i in range(first_brace, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[first_brace : i + 1])
                except json.JSONDecodeError:
                    break

    # Strategy 4: Find first [ ... ] block (array response)
    first_bracket = cleaned.find("[")
    if first_bracket != -1:
        depth = 0
        for i in range(first_bracket, len(cleaned)):
            if cleaned[i] == "[":
                depth += 1
            elif cleaned[i] == "]":
                depth -= 1
            if depth == 0:
                try:
                    arr = json.loads(cleaned[first_bracket : i + 1])
                    return {"items": arr}  # wrap array in dict
                except json.JSONDecodeError:
                    break

    return None


def _llm_json(prompt: str, max_tokens: int = 2000) -> dict:
    """
    Call LLM and parse JSON response.
    Fail-fast on all errors EXCEPT 429 rate-limit:
      - On 429, parse the suggested wait time and retry ONCE after waiting.
      - All other errors return immediately.
    """
    def _do_call():
        client = get_llm_client()
        resp = client.chat.completions.create(
            model=get_active_model(),
            messages=[
                {"role": "system", "content": "You are a JSON-only responder. Always respond with valid JSON, no markdown, no explanation, no extra text."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
            max_tokens=max_tokens,
        )
        raw = resp.choices[0].message.content
        logger.info(f"[Brain LLM] raw_length={len(raw or '')}")
        logger.debug(f"[Brain LLM] raw response: {(raw or '')[:500]}")

        if not raw or not raw.strip():
            logger.error("[Brain LLM] Empty response from LLM")
            return {"error": "Empty response from LLM"}

        parsed = _extract_json(raw)
        if parsed is not None:
            logger.info(f"[Brain LLM] JSON parsed OK, keys={list(parsed.keys())}")
            return parsed

        logger.error(f"[Brain LLM] Could not parse JSON: {raw[:300]}")
        return {"error": f"Could not parse JSON from: {raw[:200]}"}

    # ── First attempt ──
    try:
        return _do_call()
    except Exception as e:
        err_str = str(e).lower()
        # Check for 429 rate-limit (Groq / OpenAI style errors)
        is_rate_limit = "429" in err_str or "rate_limit" in err_str or "rate limit" in err_str
        if not is_rate_limit:
            logger.error(f"[Brain LLM] ✘ Request failed: {type(e).__name__}: {e}")
            logger.debug(traceback.format_exc())
            return {"error": f"{type(e).__name__}: {e}"}

        # ── 429 detected — parse wait time and retry once ──
        wait_match = re.search(r"try again in (\d+\.?\d*)\s*s", str(e), re.IGNORECASE)
        wait_sec = float(wait_match.group(1)) + 1.5 if wait_match else 8.0
        logger.warning(f"[Brain LLM] ⏳ Rate-limited (429) — waiting {wait_sec:.1f}s then retrying once...")
        time.sleep(wait_sec)

    # ── Second (final) attempt after 429 wait ──
    try:
        return _do_call()
    except Exception as e2:
        logger.error(f"[Brain LLM] ✘ Retry also failed: {type(e2).__name__}: {e2}")
        logger.debug(traceback.format_exc())
        return {"error": f"{type(e2).__name__}: {e2}"}


def _ensure_portfolio() -> dict:
    """Ensure the finvibe-agent shadow portfolio exists, return it."""
    logger.info("[Brain] Loading shadow portfolio from MongoDB...")
    p = get_portfolio(AGENT_USER, PORTFOLIO_TYPE)
    if not p:
        logger.info(f"[Brain] No portfolio found — creating new one with ${settings.shadow_portfolio_cash:,.0f}")
        p = create_portfolio(AGENT_USER, PORTFOLIO_TYPE, settings.shadow_portfolio_cash)
    else:
        logger.info(f"[Brain] Portfolio loaded: {len(p.get('holdings', []))} holdings, ${p.get('cash_balance', 0):,.2f} cash")
    return p


# ────────────────────── STEP 1: SCAN — Discover candidates ─────────────────

def scan_market() -> list[dict]:
    """
    Ask LLM to pick the most promising stocks to analyze right now.
    Uses the full stock universe + current market context.
    Returns a list of tickers with brief reasons.
    Falls back to random diverse selection if LLM fails.
    """
    logger.info("═" * 70)
    logger.info("  STEP 1 / 4  ─  SCAN MARKET  (Discovering candidates)")
    logger.info("═" * 70)
    portfolio = _ensure_portfolio()
    current_holdings = [h.get("ticker") for h in portfolio.get("holdings", [])]
    cash = portfolio.get("cash_balance", 0)
    logger.info(f"[SCAN] Building dynamic stock universe from live APIs...")
    universe = get_dynamic_stock_universe()

    logger.info(
        f"[Brain SCAN] Universe built with {len(universe)} symbols from screeners"
    )

    prompt = f"""You are an expert autonomous fund manager with ${cash:,.0f} available cash.

Current holdings: {current_holdings if current_holdings else 'None (empty portfolio)'}

Below is the universe of stocks you can choose from (from live market screener APIs):
{', '.join(universe)}

Pick exactly {MAX_SCAN_CANDIDATES} tickers that are most promising to ANALYZE right now.
Consider: recent market trends, sector rotation, momentum, value opportunities, diversification.
IMPORTANT: At least 6-8 of the 12 picks should be INDIAN stocks (.NS or .BO suffix).
Focus heavily on Indian markets (NSE/BSE) — Nifty, mid-caps, emerging sectors.
Also include 3-4 strong global picks for diversification.
Include some of my current holdings if I have any.

Respond ONLY with this JSON (no comments, no markdown, nothing else):
{{
  "candidates": [
    {{"ticker": "AAPL", "reason": "Strong momentum post earnings"}},
    {{"ticker": "NVDA", "reason": "AI demand driving growth"}},
    {{"ticker": "RELIANCE.NS", "reason": "Indian market strength"}}
  ]
}}

Return exactly {MAX_SCAN_CANDIDATES} items in the candidates array. Every ticker MUST be from the universe above."""

    logger.info(f"[SCAN] Sending {len(universe)} tickers to LLM — asking for top {MAX_SCAN_CANDIDATES} picks...")
    result = _llm_json(prompt, max_tokens=2000)

    candidates = result.get("candidates", [])

    if candidates:
        logger.info(f"[SCAN] LLM returned {len(candidates)} candidates")
        # Validate tickers are from the universe
        valid = []
        for c in candidates:
            t = c.get("ticker", "").upper().strip()
            if t in universe:
                c["ticker"] = t
                valid.append(c)
                logger.info(f"[SCAN]   ✔ {t}: {c.get('reason', '')}")
            else:
                logger.warning(f"[SCAN]   ✘ {t} not in universe — skipping")
        if valid:
            logger.info(f"[SCAN] ✅ Final scan result: {len(valid)} validated candidates")
            return valid[:MAX_SCAN_CANDIDATES]

    # ── FALLBACK: Deterministic diverse selection ──
    logger.warning(f"[SCAN] ⚠ LLM scan failed or empty — using fallback selection")
    fallback_tickers = _fallback_scan(current_holdings, universe)
    logger.info(f"[SCAN] Fallback selected: {[c['ticker'] for c in fallback_tickers]}")
    return fallback_tickers


def _fallback_scan(current_holdings: list[str], universe: list[str]) -> list[dict]:
    """Deterministic fallback: pick a diverse set of stocks if LLM scan fails."""
    if not universe:
        universe = STOCK_UNIVERSE

    # Sector buckets for diversity
    buckets = [
        universe[0:15],
        universe[15:30],
        universe[30:45],
        universe[45:60],
        universe[60:75],
        universe[75:90],
        universe[90:105],
        universe[105:120],
        universe[120:150],
    ]
    picks = []
    # Include current holdings first
    for h in current_holdings:
        if h in universe:
            picks.append({"ticker": h, "reason": "Existing holding — review needed"})
    # Then pick 1-2 from each sector bucket
    for bucket in buckets:
        available = [t for t in bucket if t not in [p["ticker"] for p in picks]]
        if available:
            chosen = random.sample(available, min(2, len(available)))
            for t in chosen:
                picks.append({"ticker": t, "reason": "Diversified sector pick (fallback)"})
        if len(picks) >= MAX_SCAN_CANDIDATES:
            break
    return picks[:MAX_SCAN_CANDIDATES]


# ────────────────────── STEP 2: ANALYZE — Deep analysis ────────────────────

def analyze_candidate(ticker: str) -> dict:
    """
    Deep-analyze a single stock: price data + news + vibe + LLM verdict.
    Returns full analysis dict with action recommendation.
    """
    logger.info(f"[ANALYZE] ── Analyzing {ticker} ──")
    logger.info(f"[ANALYZE] {ticker}: Fetching live price from yfinance...")
    price_data = get_stock_price(ticker)
    if price_data.get("error"):
        logger.warning(f"[ANALYZE] {ticker}: ✘ Price fetch failed: {price_data['error']}")
        return {"ticker": ticker, "error": price_data["error"], "action": "SKIP"}

    logger.info(f"[ANALYZE] {ticker}: Fetching latest news...")
    news = get_latest_news(ticker, max_articles=3)
    logger.info(f"[ANALYZE] {ticker}: Looking up market vibe/sentiment...")
    vibe = _get_ticker_vibe(ticker) or _derive_vibe_from_price(price_data)
    price = price_data.get("current_price", 0)
    change = price_data.get("change_pct", 0)
    high = price_data.get("high", 0)
    low = price_data.get("low", 0)
    volume = price_data.get("volume", 0)
    history = price_data.get("history_5d", [])
    prices_str = ", ".join([f"{h['date']}: ${h['close']}" for h in history[-5:]]) if history else "N/A"
    logger.info(f"[ANALYZE] {ticker}: Price=${price}, Change={change:+.1f}%, Vol={volume:,}, Vibe={vibe.get('vibe_label', '?')}, News={len(news)} articles")

    news_text = "\n".join([f"- {a['title']}" for a in news[:3]]) if news else "No recent news"
    vibe_label = vibe.get("vibe_label", "unknown")
    anxiety = vibe.get("anxiety_score", 5)
    sentiment = vibe.get("sentiment_score", 0)

    prompt = f"""You are an autonomous fund manager analyzing {ticker} for potential trade.

MARKET DATA:
- Current Price: ${price} ({'+' if change >= 0 else ''}{change}% today)
- Day Range: ${low} - ${high}
- Volume: {volume:,}
- 5-Day Prices: {prices_str}
- Market Vibe: {vibe_label} (anxiety: {anxiety}/10, sentiment: {sentiment})

RECENT NEWS:
{news_text}

Analyze this stock as a potential investment. Consider:
1. Price trend direction and momentum
2. Volume patterns (accumulation vs distribution)
3. News sentiment and catalysts
4. Risk level and volatility
5. Entry point quality

Respond ONLY with valid JSON (no markdown, no explanations). Use this exact schema:
{{
  "ticker": "{ticker}",
  "action": "BUY",
  "conviction": 0.75,
  "analysis": "Your 2-3 sentence analysis here",
  "target_price": 150.00,
  "risk_level": "MEDIUM",
  "suggested_allocation_pct": 0.05,
  "timeframe": "MEDIUM"
}}

action must be one of: STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL, SKIP
risk_level must be one of: LOW, MEDIUM, HIGH
timeframe must be one of: SHORT, MEDIUM, LONG
conviction must be between 0.0 and 1.0
suggested_allocation_pct must be between 0.01 and 0.12"""

    logger.info(f"[ANALYZE] {ticker}: Sending data to LLM for verdict...")

    result = _llm_json(prompt)
    if result.get("error"):
        logger.warning(f"[ANALYZE] {ticker}: ✘ LLM failed: {result['error']}")
        return {"ticker": ticker, "action": "SKIP", "error": result["error"]}

    result["current_price"] = price
    result["change_pct"] = change
    result["volume"] = volume
    result["vibe_label"] = vibe_label
    result["anxiety"] = anxiety
    action = result.get('action', 'SKIP')
    conviction = result.get('conviction', 0)
    logger.info(f"[ANALYZE] {ticker}: ✅ Verdict={action}, Conviction={conviction}, Target=${result.get('target_price', '?')}, Risk={result.get('risk_level', '?')}")
    return result


# ────────────────────── STEP 3: REVIEW — Check existing holdings ───────────

def review_holdings(portfolio: dict) -> list[dict]:
    """
    Review ALL current holdings in a SINGLE LLM call (saves rate limit quota).
    Returns list of decisions per holding.
    """
    logger.info("═" * 70)
    logger.info("  STEP 3 / 4  ─  REVIEW HOLDINGS  (Hold / Buy More / Trim / Sell)")
    logger.info("═" * 70)
    holdings = portfolio.get("holdings", [])
    if not holdings:
        logger.info("[REVIEW] No existing holdings to review — skipping")
        return []

    logger.info(f"[REVIEW] Reviewing {len(holdings)} current positions...")

    # ── Build summary of all holdings for one batched LLM call ──
    holding_summaries = []
    price_map = {}  # ticker -> current_price for later
    for h in holdings:
        ticker = h.get("ticker", "")
        shares = h.get("shares", 0)
        avg_cost = h.get("avg_cost", 0)
        price_data = get_stock_price(ticker)
        current_price = price_data.get("current_price", avg_cost)
        pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
        vibe = _get_ticker_vibe(ticker) or _derive_vibe_from_price(price_data)
        news = get_latest_news(ticker, 1)
        headline = news[0]["title"] if news else "No news"

        price_map[ticker] = {
            "current_price": current_price,
            "shares": shares,
            "avg_cost": avg_cost,
            "pnl_pct": round(pnl_pct, 2),
        }

        summary_line = (
            f"{ticker}: {shares:.2f} shares @ ${avg_cost:.2f}, "
            f"now ${current_price:.2f} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}% P&L), "
            f"today {'+' if price_data.get('change_pct', 0) >= 0 else ''}{price_data.get('change_pct', 0):.1f}%, "
            f"vibe: {vibe.get('vibe_label', 'unknown')}, news: {headline}"
        )
        logger.info(f"[REVIEW]   {summary_line}")
        holding_summaries.append(summary_line)

    positions_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(holding_summaries))

    prompt = f"""You are an autonomous fund manager reviewing your current portfolio positions.

CURRENT POSITIONS:
{positions_text}

For EACH position, decide:
- HOLD: keep as-is
- BUY_MORE: increase position (momentum continuing)
- TRIM: sell some (take profits / reduce risk) — include trim_pct (0.0-1.0)
- SELL_ALL: exit completely

Respond ONLY with valid JSON array (no markdown). Example:
{{
  "decisions": [
    {{"ticker": "AAPL", "decision": "HOLD", "reason": "Strong momentum", "confidence": 0.8, "trim_pct": 0.0}},
    {{"ticker": "TSLA", "decision": "TRIM", "reason": "Take partial profits", "confidence": 0.7, "trim_pct": 0.3}}
  ]
}}

Return exactly {len(holdings)} decisions, one per position. decision must be HOLD, BUY_MORE, TRIM, or SELL_ALL."""

    logger.info(f"[REVIEW] Sending all {len(holdings)} holdings to LLM for batch review...")
    result = _llm_json(prompt, max_tokens=1500)

    raw_decisions = result.get("decisions", [])
    if not raw_decisions and not result.get("error"):
        # Maybe the LLM returned a flat list
        raw_decisions = result.get("items", [])  # from array wrapper

    # Enrich each decision with price data
    decisions = []
    for d in raw_decisions:
        ticker = d.get("ticker", "")
        info = price_map.get(ticker, {})
        d["current_price"] = info.get("current_price", 0)
        d["shares"] = info.get("shares", 0)
        d["avg_cost"] = info.get("avg_cost", 0)
        d["pnl_pct"] = info.get("pnl_pct", 0)
        decisions.append(d)

    # If LLM failed, default all to HOLD (safe)
    if not decisions:
        logger.warning("[REVIEW] ⚠ LLM review failed — defaulting ALL to HOLD (safe mode)")
        for ticker, info in price_map.items():
            decisions.append({
                "ticker": ticker,
                "decision": "HOLD",
                "reason": "Review unavailable — defaulting to hold",
                "confidence": 0.5,
                "trim_pct": 0.0,
                **info,
            })
    else:
        for d in decisions:
            logger.info(f"[REVIEW]   {d.get('ticker')}: {d.get('decision')} — {d.get('reason', '')[:80]}")

    logger.info(f"[REVIEW] ✅ Review complete: {len(decisions)} decisions")
    return decisions


# ────────────────────── STEP 4: EXECUTE — Place trades ─────────────────────

def execute_trades(
    buy_candidates: list[dict],
    hold_decisions: list[dict],
    portfolio: dict,
) -> list[dict]:
    """
    Execute trades based on AI analysis:
    - Sell holdings marked SELL_ALL or TRIM
    - Buy new stocks rated BUY or STRONG_BUY
    - Buy more of existing holdings rated BUY_MORE
    Returns list of executed trade records.
    """
    logger.info("═" * 70)
    logger.info("  STEP 4 / 4  ─  EXECUTE TRADES  (Selling → Buying → Persist)")
    logger.info("═" * 70)
    holdings = portfolio.get("holdings", [])
    cash = portfolio.get("cash_balance", settings.shadow_portfolio_cash)
    initial_capital = settings.shadow_portfolio_cash
    executed = []
    logger.info(f"[EXECUTE] Starting cash: ${cash:,.2f} | Holdings: {len(holdings)} | Initial capital: ${initial_capital:,.0f}")

    # ── SELL / TRIM existing holdings first (frees up cash) ──
    logger.info("[EXECUTE] ── Phase A: Processing SELLS and TRIMS ──")
    sell_count = 0
    for d in hold_decisions:
        ticker = d.get("ticker", "")
        decision = d.get("decision", "HOLD")

        if decision == "SELL_ALL":
            # Find and remove holding
            for h in holdings:
                if h.get("ticker") == ticker:
                    logger.info(f"[EXECUTE] 🔴 SELL_ALL {ticker}: {h['shares']:.2f} shares")
                    sell_count += 1
                    sell_value = h["shares"] * d.get("current_price", h.get("current_price", h["avg_cost"]))
                    trade_id = f"brain-{uuid.uuid4().hex[:8]}"
                    record_trade(
                        trade_id=trade_id,
                        ticker=ticker,
                        action="SELL",
                        shares=h["shares"],
                        price=d.get("current_price", h.get("current_price", h["avg_cost"])),
                        rationale={
                            "signal": "SELL_ALL",
                            "prediction": d.get("reason", "AI decided to exit"),
                            "confidence": d.get("confidence", 0.5),
                            "source": "ai_brain",
                        },
                    )
                    cash += sell_value
                    executed.append({
                        "trade_id": trade_id,
                        "action": "SELL",
                        "ticker": ticker,
                        "shares": round(h["shares"], 2),
                        "price": round(d.get("current_price", h["avg_cost"]), 2),
                        "value": round(sell_value, 2),
                        "reason": d.get("reason", ""),
                    })
                    break
            holdings = [h for h in holdings if h.get("ticker") != ticker]

        elif decision == "TRIM":
            trim_pct = d.get("trim_pct", 0.5)
            for h in holdings:
                if h.get("ticker") == ticker:
                    sell_shares = h["shares"] * trim_pct
                    sell_price = d.get("current_price", h.get("current_price", h["avg_cost"]))
                    sell_value = sell_shares * sell_price
                    if sell_value < MIN_TRADE_VALUE:
                        logger.info(f"[EXECUTE] ⏭ TRIM {ticker}: sell value ${sell_value:.0f} < min ${MIN_TRADE_VALUE} — skipping")
                        break
                    logger.info(f"[EXECUTE] 🟡 TRIM {ticker}: selling {trim_pct*100:.0f}% ({sell_shares:.2f} shares @ ${sell_price:.2f} = ${sell_value:.2f})")
                    sell_count += 1

                    trade_id = f"brain-{uuid.uuid4().hex[:8]}"
                    record_trade(
                        trade_id=trade_id,
                        ticker=ticker,
                        action="SELL",
                        shares=sell_shares,
                        price=sell_price,
                        rationale={
                            "signal": "TRIM",
                            "prediction": d.get("reason", "AI trimming position"),
                            "confidence": d.get("confidence", 0.5),
                            "trim_pct": trim_pct,
                            "source": "ai_brain",
                        },
                    )
                    cash += sell_value
                    h["shares"] -= sell_shares
                    executed.append({
                        "trade_id": trade_id,
                        "action": "TRIM",
                        "ticker": ticker,
                        "shares": round(sell_shares, 2),
                        "price": round(sell_price, 2),
                        "value": round(sell_value, 2),
                        "reason": d.get("reason", ""),
                    })
                    break
            # Remove holdings with zero/negative shares
            holdings = [h for h in holdings if h.get("shares", 0) > 0.01]

    logger.info(f"[EXECUTE] Phase A done: {sell_count} sells/trims executed, cash now ${cash:,.2f}")

    # ── BUY MORE for existing holdings ──
    logger.info("[EXECUTE] ── Phase B: Processing BUY_MORE for existing holdings ──")
    buymore_count = 0
    for d in hold_decisions:
        if d.get("decision") != "BUY_MORE":
            continue
        ticker = d.get("ticker", "")
        price = d.get("current_price", 0)
        if price <= 0 or cash < MIN_TRADE_VALUE:
            logger.info(f"[EXECUTE] ⏭ BUY_MORE {ticker}: insufficient cash or zero price — skipping")
            continue

        # Allocate up to 3% more
        buy_value = min(initial_capital * 0.03, cash * 0.3, cash - MIN_TRADE_VALUE)
        if buy_value < MIN_TRADE_VALUE:
            logger.info(f"[EXECUTE] ⏭ BUY_MORE {ticker}: allocation ${buy_value:.0f} < min ${MIN_TRADE_VALUE} — skipping")
            continue
        buy_shares = buy_value / price
        logger.info(f"[EXECUTE] 🟢 BUY_MORE {ticker}: {buy_shares:.2f} shares @ ${price:.2f} = ${buy_value:.2f}")
        buymore_count += 1

        trade_id = f"brain-{uuid.uuid4().hex[:8]}"
        record_trade(
            trade_id=trade_id,
            ticker=ticker,
            action="BUY",
            shares=buy_shares,
            price=price,
            rationale={
                "signal": "BUY_MORE",
                "prediction": d.get("reason", "AI increasing position"),
                "confidence": d.get("confidence", 0.5),
                "source": "ai_brain",
            },
        )
        cash -= buy_value
        # Update holding
        for h in holdings:
            if h.get("ticker") == ticker:
                old_total = h["shares"] * h["avg_cost"]
                h["shares"] += buy_shares
                h["avg_cost"] = (old_total + buy_value) / h["shares"]
                h["current_price"] = price
                break
        executed.append({
            "trade_id": trade_id,
            "action": "BUY_MORE",
            "ticker": ticker,
            "shares": round(buy_shares, 2),
            "price": round(price, 2),
            "value": round(buy_value, 2),
            "reason": d.get("reason", ""),
        })

    logger.info(f"[EXECUTE] Phase B done: {buymore_count} buy-more trades, cash now ${cash:,.2f}")

    # ── BUY new stocks ──
    logger.info("[EXECUTE] ── Phase C: Buying NEW stocks (highest conviction first) ──")
    # Sort by conviction, take strongest signals
    strong_buys = [
        c for c in buy_candidates
        if c.get("action") in ("BUY", "STRONG_BUY")
        and c.get("conviction", 0) >= 0.5
        and not c.get("error")
    ]
    strong_buys.sort(key=lambda x: x.get("conviction", 0), reverse=True)
    logger.info(f"[EXECUTE] {len(strong_buys)} candidates qualify (BUY/STRONG_BUY, conviction ≥ 0.5)")

    existing_tickers = {h.get("ticker") for h in holdings}
    new_buy_count = 0

    for candidate in strong_buys:
        ticker = candidate.get("ticker", "")
        if ticker in existing_tickers:
            continue  # Already handled in BUY_MORE
        if len(holdings) >= MAX_HOLDINGS:
            logger.info(f"[EXECUTE] ⏹ Max holdings ({MAX_HOLDINGS}) reached — stopping new buys")
            break
        if cash < MIN_TRADE_VALUE:
            logger.info(f"[EXECUTE] ⏹ Cash ${cash:.0f} < min trade ${MIN_TRADE_VALUE} — stopping new buys")
            break

        price = candidate.get("current_price", 0)
        if price <= 0:
            continue

        # Size the position
        alloc = min(
            candidate.get("suggested_allocation_pct", 0.05),
            MAX_POSITION_PCT,
        )
        buy_value = min(initial_capital * alloc, cash * 0.4, cash - 1000)
        if buy_value < MIN_TRADE_VALUE:
            logger.info(f"[EXECUTE] ⏭ BUY {ticker}: allocation ${buy_value:.0f} too small — skipping")
            continue
        buy_shares = buy_value / price
        logger.info(f"[EXECUTE] 🟢 BUY {ticker}: {buy_shares:.2f} shares @ ${price:.2f} = ${buy_value:.2f} (conviction={candidate.get('conviction', 0)})")
        new_buy_count += 1

        trade_id = f"brain-{uuid.uuid4().hex[:8]}"
        record_trade(
            trade_id=trade_id,
            ticker=ticker,
            action="BUY",
            shares=buy_shares,
            price=price,
            rationale={
                "signal": candidate.get("action", "BUY"),
                "prediction": candidate.get("analysis", ""),
                "target_price": candidate.get("target_price", 0),
                "risk_level": candidate.get("risk_level", "MEDIUM"),
                "conviction": candidate.get("conviction", 0),
                "timeframe": candidate.get("timeframe", "MEDIUM"),
                "source": "ai_brain",
            },
        )
        cash -= buy_value
        holdings.append({
            "ticker": ticker,
            "shares": buy_shares,
            "avg_cost": price,
            "current_price": price,
        })
        existing_tickers.add(ticker)
        executed.append({
            "trade_id": trade_id,
            "action": "BUY",
            "ticker": ticker,
            "shares": round(buy_shares, 2),
            "price": round(price, 2),
            "value": round(buy_value, 2),
            "reason": candidate.get("analysis", ""),
            "conviction": candidate.get("conviction", 0),
            "risk_level": candidate.get("risk_level", "MEDIUM"),
        })

    logger.info(f"[EXECUTE] Phase C done: {new_buy_count} new buys")

    # ── Persist updated portfolio ──
    logger.info(f"[EXECUTE] Persisting portfolio to MongoDB: {len(holdings)} holdings, ${cash:,.2f} cash")
    update_holdings(AGENT_USER, PORTFOLIO_TYPE, holdings, cash)

    logger.info(f"[EXECUTE] ✅ Execution complete: {len(executed)} total trades ({sell_count} sells, {buymore_count} buy-more, {new_buy_count} new buys)")
    return executed


# ────────────────────── MAIN ENTRY: Run full brain cycle ───────────────────

def run_brain_cycle() -> dict:
    """
    Execute one full autonomous investment cycle:
    SCAN → ANALYZE → REVIEW → EXECUTE

    Returns a complete activity log.
    """
    started_at = datetime.now(timezone.utc)
    log = {
        "cycle_id": f"cycle-{uuid.uuid4().hex[:8]}",
        "started_at": started_at.isoformat(),
        "status": "running",
        "scan": [],
        "analyses": [],
        "hold_decisions": [],
        "trades": [],
        "summary": "",
        "error": None,
    }

    try:
        logger.info("╔" + "═" * 68 + "╗")
        logger.info("║" + "  AI BRAIN CYCLE STARTED".center(68) + "║")
        logger.info("║" + f"  Cycle ID: {log['cycle_id']}".center(68) + "║")
        logger.info("╚" + "═" * 68 + "╝")

        portfolio = _ensure_portfolio()

        # ── STEP 1: SCAN ──
        candidates = scan_market()
        log["scan"] = candidates

        # Brief cooldown between steps to respect rate limits
        time.sleep(3)

        # ── STEP 2: ANALYZE each candidate ──
        logger.info("═" * 70)
        logger.info("  STEP 2 / 4  ─  ANALYZE CANDIDATES  (Deep-diving each stock)")
        logger.info("═" * 70)
        existing_tickers = {h.get("ticker") for h in portfolio.get("holdings", [])}
        analyses = []
        for i, c in enumerate(candidates):
            ticker = c.get("ticker", "")
            if not ticker:
                continue
            logger.info(f"[ANALYZE] ━━━ [{i+1}/{len(candidates)}] {ticker} ━━━")
            analysis = analyze_candidate(ticker)
            analyses.append(analysis)
            # Pause between LLM calls to stay within rate limits (6000 TPM on some models)
            if i < len(candidates) - 1:
                time.sleep(5)
        log["analyses"] = analyses
        buy_count = sum(1 for a in analyses if a.get("action") in ("BUY", "STRONG_BUY"))
        hold_count = sum(1 for a in analyses if a.get("action") == "HOLD")
        skip_count = sum(1 for a in analyses if a.get("action") in ("SKIP", "SELL", "STRONG_SELL"))
        logger.info(f"[ANALYZE] ✅ Analysis complete: {len(analyses)} stocks → {buy_count} BUY, {hold_count} HOLD, {skip_count} SKIP/SELL")

        # Brief cooldown before review step
        time.sleep(3)

        # ── STEP 3: REVIEW existing holdings ──
        hold_decisions = review_holdings(portfolio)
        log["hold_decisions"] = hold_decisions

        # ── STEP 4: EXECUTE trades ──
        # Pass only new candidates (not already held) for potential buys,
        # but also include existing-held candidates whose analysis says BUY/STRONG_BUY
        new_candidates = [a for a in analyses if a.get("ticker") not in existing_tickers]
        trades = execute_trades(new_candidates, hold_decisions, portfolio)
        log["trades"] = trades

        # ── Generate summary ──
        buys = [t for t in trades if t["action"] in ("BUY", "BUY_MORE")]
        sells = [t for t in trades if t["action"] in ("SELL", "TRIM")]
        holds = [d for d in hold_decisions if d.get("decision") == "HOLD"]
        buy_str = ", ".join([f"{t['ticker']}" for t in buys]) or "none"
        sell_str = ", ".join([f"{t['ticker']}" for t in sells]) or "none"

        log["summary"] = (
            f"Scanned {len(candidates)} stocks, analyzed {len(analyses)}. "
            f"Executed {len(trades)} trades: {len(buys)} buys ({buy_str}), {len(sells)} sells ({sell_str}). "
            f"Holding {len(holds)} positions unchanged."
        )

        log["status"] = "completed"

        logger.info("╔" + "═" * 68 + "╗")
        logger.info("║" + "  AI BRAIN CYCLE COMPLETED ✅".center(68) + "║")
        logger.info("╚" + "═" * 68 + "╝")
        logger.info(f"[SUMMARY] {log['summary']}")

    except Exception as e:
        log["status"] = "error"
        log["error"] = str(e)
        logger.error("╔" + "═" * 68 + "╗")
        logger.error("║" + "  AI BRAIN CYCLE FAILED ❌".center(68) + "║")
        logger.error("╚" + "═" * 68 + "╝")
        logger.error(f"[ERROR] {e}")
        logger.debug(traceback.format_exc())

    log["completed_at"] = datetime.now(timezone.utc).isoformat()
    log["duration_sec"] = round(
        (datetime.now(timezone.utc) - started_at).total_seconds(), 1
    )

    # Persist the cycle log
    try:
        from backend.deps import get_db
        get_db()["ai_brain_logs"].insert_one({
            **log,
            "_id_log": log["cycle_id"],
        })
    except Exception:
        pass

    return log


def get_brain_history(limit: int = 10) -> list[dict]:
    """Get recent AI brain cycle logs."""
    try:
        from backend.deps import get_db
        docs = list(
            get_db()["ai_brain_logs"]
            .find({}, {"_id": 0})
            .sort("started_at", -1)
            .limit(limit)
        )
        return docs
    except Exception:
        return []


def get_brain_stats() -> dict:
    """Get brain performance stats."""
    portfolio = _ensure_portfolio()
    holdings = portfolio.get("holdings", [])
    cash = portfolio.get("cash_balance", settings.shadow_portfolio_cash)
    total_value = portfolio.get("total_value", cash)
    pnl = total_value - settings.shadow_portfolio_cash
    pnl_pct = (pnl / settings.shadow_portfolio_cash) * 100

    # Count total trades by brain
    try:
        from backend.deps import get_db
        brain_trades = get_db()["trade_logs"].count_documents(
            {"rationale.source": "ai_brain"}
        )
        brain_cycles = get_db()["ai_brain_logs"].count_documents({})
    except Exception:
        brain_trades = 0
        brain_cycles = 0

    return {
        "holdings_count": len(holdings),
        "cash_balance": round(cash, 2),
        "total_value": round(total_value, 2),
        "total_pnl": round(pnl, 2),
        "total_pnl_pct": round(pnl_pct, 2),
        "brain_trades": brain_trades,
        "brain_cycles": brain_cycles,
    }
