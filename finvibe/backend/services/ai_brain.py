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

# Stock universe — well-known liquid tickers from global markets
STOCK_UNIVERSE = [
    # US Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "INTC", "CRM",
    "NFLX", "ORCL", "ADBE", "PYPL", "SQ", "SHOP", "UBER", "ABNB", "SNAP", "COIN",
    # US Finance
    "JPM", "BAC", "GS", "MS", "V", "MA", "AXP", "BRK-B", "C", "WFC",
    # US Healthcare
    "JNJ", "PFE", "UNH", "ABBV", "MRK", "LLY", "TMO", "ABT", "AMGN", "GILD",
    # US Energy & Industrial
    "XOM", "CVX", "COP", "NEE", "BA", "CAT", "GE", "HON", "UPS", "RTX",
    # US Consumer
    "WMT", "KO", "PEP", "MCD", "NKE", "SBUX", "DIS", "HD", "LOW", "TGT",
    # India
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "BHARTIARTL.NS", "SBIN.NS", "WIPRO.NS",
    # Europe
    "ASML", "SAP", "NVO", "AZN", "SHEL", "NESN.SW", "MC.PA", "SIE.DE",
    # Asia
    "TSM", "BABA", "9988.HK", "005930.KS", "7203.T",
]

YAHOO_SCREENER_IDS = [
    "day_gainers",
    "most_actives",
    "undervalued_growth_stocks",
    "growth_technology_stocks",
]


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


def get_dynamic_stock_universe(target_size: int = 220) -> list[str]:
    """
    Build a dynamic stock universe from Yahoo Finance screeners.
    Falls back to static STOCK_UNIVERSE on failure.
    """
    symbols: list[str] = []
    for scr_id in YAHOO_SCREENER_IDS:
        fetched = _fetch_screener_symbols(scr_id, count=100)
        for symbol in fetched:
            if symbol not in symbols:
                symbols.append(symbol)
        if len(symbols) >= target_size:
            break

    # Keep known global static names too, but prioritize dynamic list first.
    for symbol in STOCK_UNIVERSE:
        if symbol not in symbols:
            symbols.append(symbol)

    if not symbols:
        return STOCK_UNIVERSE[:]

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


def _llm_json(prompt: str, max_tokens: int = 2000, retries: int = 3) -> dict:
    """Call Gemini and parse JSON response with robust extraction, retry, and 429 backoff."""
    last_error = ""
    for attempt in range(retries):
        try:
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
            logger.info(f"[Brain LLM] attempt={attempt+1} raw_length={len(raw or '')}")
            logger.debug(f"[Brain LLM] raw response: {(raw or '')[:500]}")

            if not raw or not raw.strip():
                last_error = "Empty response from LLM"
                logger.warning(f"[Brain LLM] Empty response on attempt {attempt+1}")
                continue

            parsed = _extract_json(raw)
            if parsed is not None:
                logger.info(f"[Brain LLM] JSON parsed OK, keys={list(parsed.keys())}")
                return parsed

            last_error = f"Could not parse JSON from: {raw[:200]}"
            logger.warning(f"[Brain LLM] JSON parse failed attempt {attempt+1}: {raw[:300]}")

        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.error(f"[Brain LLM] Exception attempt {attempt+1}: {last_error}")

            # ── Handle 429 rate-limit: short wait and retry ──
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower():
                wait_sec = RATELIMIT_BASE_WAIT * (attempt + 1)
                retry_match = re.search(r"retry in ([\d.]+)s", err_str, re.IGNORECASE)
                if retry_match:
                    wait_sec = float(retry_match.group(1)) + 1
                logger.warning(f"[Brain LLM] Rate limited! Sleeping {wait_sec:.0f}s before retry...")
                time.sleep(wait_sec)
                continue

            logger.debug(traceback.format_exc())

    logger.error(f"[Brain LLM] All {retries} attempts failed: {last_error}")
    return {"error": last_error}


def _ensure_portfolio() -> dict:
    """Ensure the finvibe-agent shadow portfolio exists, return it."""
    p = get_portfolio(AGENT_USER, PORTFOLIO_TYPE)
    if not p:
        p = create_portfolio(AGENT_USER, PORTFOLIO_TYPE, settings.shadow_portfolio_cash)
    return p


# ────────────────────── STEP 1: SCAN — Discover candidates ─────────────────

def scan_market() -> list[dict]:
    """
    Ask Gemini to pick the most promising stocks to analyze right now.
    Uses the full stock universe + current market context.
    Returns a list of tickers with brief reasons.
    Falls back to random diverse selection if LLM fails.
    """
    portfolio = _ensure_portfolio()
    current_holdings = [h.get("ticker") for h in portfolio.get("holdings", [])]
    cash = portfolio.get("cash_balance", 0)
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
Mix sectors and geographies. Include some of my current holdings if I have any.

Respond ONLY with this JSON (no comments, no markdown, nothing else):
{{
  "candidates": [
    {{"ticker": "AAPL", "reason": "Strong momentum post earnings"}},
    {{"ticker": "NVDA", "reason": "AI demand driving growth"}},
    {{"ticker": "RELIANCE.NS", "reason": "Indian market strength"}}
  ]
}}

Return exactly {MAX_SCAN_CANDIDATES} items in the candidates array. Every ticker MUST be from the universe above."""

    logger.info(f"[Brain SCAN] Requesting {MAX_SCAN_CANDIDATES} candidates from LLM...")
    result = _llm_json(prompt, max_tokens=2000)

    candidates = result.get("candidates", [])

    if candidates:
        logger.info(f"[Brain SCAN] LLM returned {len(candidates)} candidates: {[c.get('ticker') for c in candidates]}")
        # Validate tickers are from the universe
        valid = []
        for c in candidates:
            t = c.get("ticker", "").upper().strip()
            if t in universe:
                c["ticker"] = t
                valid.append(c)
            else:
                logger.warning(f"[Brain SCAN] Unknown ticker '{t}', skipping")
        if valid:
            return valid[:MAX_SCAN_CANDIDATES]

    # ── FALLBACK: Deterministic diverse selection ──
    logger.warning(f"[Brain SCAN] LLM scan failed or empty (result={result}). Using fallback selection.")
    fallback_tickers = _fallback_scan(current_holdings, universe)
    logger.info(f"[Brain SCAN] Fallback selected: {[c['ticker'] for c in fallback_tickers]}")
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
    price_data = get_stock_price(ticker)
    if price_data.get("error"):
        logger.warning(f"[Brain ANALYZE] {ticker}: price fetch failed: {price_data['error']}")
        return {"ticker": ticker, "error": price_data["error"], "action": "SKIP"}

    news = get_latest_news(ticker, max_articles=3)
    vibe = _get_ticker_vibe(ticker) or _derive_vibe_from_price(price_data)
    price = price_data.get("current_price", 0)
    change = price_data.get("change_pct", 0)
    high = price_data.get("high", 0)
    low = price_data.get("low", 0)
    volume = price_data.get("volume", 0)
    history = price_data.get("history_5d", [])
    prices_str = ", ".join([f"{h['date']}: ${h['close']}" for h in history[-5:]]) if history else "N/A"

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

    logger.info(f"[Brain ANALYZE] {ticker}: price=${price}, change={change}%, vibe={vibe_label}")

    result = _llm_json(prompt)
    if result.get("error"):
        logger.warning(f"[Brain ANALYZE] {ticker}: LLM failed: {result['error']}")
        return {"ticker": ticker, "action": "SKIP", "error": result["error"]}

    result["current_price"] = price
    result["change_pct"] = change
    result["volume"] = volume
    result["vibe_label"] = vibe_label
    result["anxiety"] = anxiety
    return result


# ────────────────────── STEP 3: REVIEW — Check existing holdings ───────────

def review_holdings(portfolio: dict) -> list[dict]:
    """
    Review ALL current holdings in a SINGLE LLM call (saves rate limit quota).
    Returns list of decisions per holding.
    """
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return []

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

        holding_summaries.append(
            f"{ticker}: {shares:.2f} shares @ ${avg_cost:.2f}, "
            f"now ${current_price:.2f} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}% P&L), "
            f"today {'+' if price_data.get('change_pct', 0) >= 0 else ''}{price_data.get('change_pct', 0):.1f}%, "
            f"vibe: {vibe.get('vibe_label', 'unknown')}, news: {headline}"
        )

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

    logger.info(f"[Brain REVIEW] Reviewing {len(holdings)} holdings in one batched call...")
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
        logger.warning("[Brain REVIEW] LLM review failed, defaulting all to HOLD")
        for ticker, info in price_map.items():
            decisions.append({
                "ticker": ticker,
                "decision": "HOLD",
                "reason": "Review unavailable — defaulting to hold",
                "confidence": 0.5,
                "trim_pct": 0.0,
                **info,
            })

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
    holdings = portfolio.get("holdings", [])
    cash = portfolio.get("cash_balance", settings.shadow_portfolio_cash)
    initial_capital = settings.shadow_portfolio_cash
    executed = []

    # ── SELL / TRIM existing holdings first (frees up cash) ──
    for d in hold_decisions:
        ticker = d.get("ticker", "")
        decision = d.get("decision", "HOLD")

        if decision == "SELL_ALL":
            # Find and remove holding
            for h in holdings:
                if h.get("ticker") == ticker:
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
                        break

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

    # ── BUY MORE for existing holdings ──
    for d in hold_decisions:
        if d.get("decision") != "BUY_MORE":
            continue
        ticker = d.get("ticker", "")
        price = d.get("current_price", 0)
        if price <= 0 or cash < MIN_TRADE_VALUE:
            continue

        # Allocate up to 3% more
        buy_value = min(initial_capital * 0.03, cash * 0.3, cash - MIN_TRADE_VALUE)
        if buy_value < MIN_TRADE_VALUE:
            continue
        buy_shares = buy_value / price

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

    # ── BUY new stocks ──
    # Sort by conviction, take strongest signals
    strong_buys = [
        c for c in buy_candidates
        if c.get("action") in ("BUY", "STRONG_BUY")
        and c.get("conviction", 0) >= 0.5
        and not c.get("error")
    ]
    strong_buys.sort(key=lambda x: x.get("conviction", 0), reverse=True)

    existing_tickers = {h.get("ticker") for h in holdings}

    for candidate in strong_buys:
        ticker = candidate.get("ticker", "")
        if ticker in existing_tickers:
            continue  # Already handled in BUY_MORE
        if len(holdings) >= MAX_HOLDINGS:
            break
        if cash < MIN_TRADE_VALUE:
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
            continue
        buy_shares = buy_value / price

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

    # ── Persist updated portfolio ──
    update_holdings(AGENT_USER, PORTFOLIO_TYPE, holdings, cash)

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
        portfolio = _ensure_portfolio()
        logger.info(f"[Brain CYCLE] Portfolio loaded: {len(portfolio.get('holdings', []))} holdings, ${portfolio.get('cash_balance', 0):,.0f} cash")

        # ── STEP 1: SCAN ──
        logger.info("[Brain CYCLE] Step 1/4: SCANNING market...")
        candidates = scan_market()
        log["scan"] = candidates
        logger.info(f"[Brain CYCLE] Scan complete: {len(candidates)} candidates")

        # ── STEP 2: ANALYZE each candidate ──
        logger.info(f"[Brain CYCLE] Step 2/4: ANALYZING {len(candidates)} candidates...")
        existing_tickers = {h.get("ticker") for h in portfolio.get("holdings", [])}
        analyses = []
        for i, c in enumerate(candidates):
            ticker = c.get("ticker", "")
            if not ticker:
                continue
            logger.info(f"[Brain CYCLE]   Analyzing [{i+1}/{len(candidates)}] {ticker}...")
            analysis = analyze_candidate(ticker)
            analyses.append(analysis)
            action = analysis.get("action", "SKIP")
            logger.info(f"[Brain CYCLE]   {ticker} → {action} (conviction={analysis.get('conviction', 0)})")
            # Brief pause between requests
            if i < len(candidates) - 1:
                time.sleep(0.5)
        log["analyses"] = analyses
        logger.info(f"[Brain CYCLE] Analysis complete: {len(analyses)} analyzed")

        # ── STEP 3: REVIEW existing holdings ──
        logger.info(f"[Brain CYCLE] Step 3/4: REVIEWING {len(portfolio.get('holdings', []))} holdings...")
        hold_decisions = review_holdings(portfolio)
        log["hold_decisions"] = hold_decisions
        for d in hold_decisions:
            logger.info(f"[Brain CYCLE]   {d.get('ticker')}: {d.get('decision')} ({d.get('reason', '')[:60]})")

        # ── STEP 4: EXECUTE trades ──
        logger.info("[Brain CYCLE] Step 4/4: EXECUTING trades...")
        # Pass only new candidates (not already held) for potential buys,
        # but also include existing-held candidates whose analysis says BUY/STRONG_BUY
        new_candidates = [a for a in analyses if a.get("ticker") not in existing_tickers]
        trades = execute_trades(new_candidates, hold_decisions, portfolio)
        log["trades"] = trades
        for t in trades:
            logger.info(f"[Brain CYCLE]   TRADE: {t['action']} {t.get('shares', 0)} {t['ticker']} @ ${t.get('price', 0):.2f}")

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
        logger.info(f"[Brain CYCLE] ✅ Cycle complete: {log['summary']}")

    except Exception as e:
        log["status"] = "error"
        log["error"] = str(e)
        logger.error(f"[Brain CYCLE] ❌ Cycle failed: {e}")
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
