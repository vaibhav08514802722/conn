# FinVibe In-Depth Study Guide

## What FinVibe Is
FinVibe is an agentic AI portfolio platform that combines:
- a LangGraph multi-node decision pipeline
- an autonomous AI Brain that runs full scan/analyze/review/execute cycles
- a user portfolio assistant with ticker-level predictions
- a RAG investment chatbot with citations and memory
- persistence and learning loops (MongoDB + Qdrant + Mem0 + evaluator)

It is designed for paper-trading and investment education, not brokerage execution.

---

## High-Level Architecture

```text
Frontend (Next.js)                                    External Data/AI
  - Landing/Login/Signup                                - Groq LLM API
  - Dashboard                                            - yfinance
  - My Portfolio                                         - FMP stable APIs
  - AI Portfolio                                         - NewsAPI (optional)
  - AI Chat (RAG)                                        - Vapi (optional)
          |
          v
FastAPI Backend
  - Routes: auth, agent, market, portfolio, user_portfolio, ai_brain, webhook
  - Graph: researcher -> vibe_analyst -> strategist -> executor/alerter -> reflector
  - Services: ai_brain, rag_chat, memory, vector, market, auth, vapi, audio
  - Jobs: evaluator + scheduler
          |
          v
Data Layer
  - MongoDB: users, portfolios, trade_logs, market_sentiments, alerts, ai_brain_logs, webhooks
  - Qdrant: market_research + reflection_memory
  - Mem0: episodic user memory (with optional Neo4j graph store)
```

---

## Recommended Study Order

### Phase 1: Runtime Boot and Configuration
1. backend/config.py
2. backend/deps.py
3. backend/main.py

### Phase 2: Graph Contracts and Control Flow
4. backend/schemas/agent_state.py
5. backend/graph/builder.py
6. backend/graph/edges.py

### Phase 3: Core Graph Nodes
7. backend/graph/nodes/researcher.py
8. backend/graph/nodes/vibe_analyst.py
9. backend/graph/nodes/strategist.py
10. backend/graph/nodes/executor.py
11. backend/graph/nodes/reflector.py
12. backend/graph/nodes/alerter.py

### Phase 4: Autonomous AI Brain Engine
13. backend/services/ai_brain.py
14. backend/routes/ai_brain.py

### Phase 5: User Portfolio + Auth + API Surface
15. backend/services/auth_service.py
16. backend/routes/auth.py
17. backend/routes/user_portfolio.py
18. backend/routes/agent.py
19. backend/routes/market.py
20. backend/routes/portfolio.py
21. backend/routes/webhook.py

### Phase 6: Memory/RAG/Vector Layer
22. backend/services/vector_service.py
23. backend/services/memory_service.py
24. backend/services/rag_chat_service.py

### Phase 7: Evaluation and Learning Loops
25. backend/jobs/evaluator.py
26. backend/jobs/scheduler.py
27. frontend/components/ReflectionFeed.tsx (consumer)

### Phase 8: Frontend App Flow
28. frontend/lib/api.ts
29. frontend/lib/auth.tsx
30. frontend/app/dashboard/page.tsx
31. frontend/app/dashboard/my-portfolio/page.tsx
32. frontend/app/dashboard/ai-portfolio/page.tsx
33. frontend/app/dashboard/chat/page.tsx
34. frontend/components/* (PortfolioChart, VibeGauge, TradeLogTable, Navbar)

---

## Phase 1: Foundation Layer (Detailed)

### 1) backend/config.py
Centralized settings with pydantic-settings, read from .env.

Important fields:
- LLM:
  - groq_api_key, groq_base_url, groq_model
  - gemini_api_key/base/model as fallback
- Storage:
  - mongo_uri, mongo_db_name
  - qdrant_url, qdrant_api_key, collection names
  - neo_uri/username/password (optional graph memory)
- Runtime:
  - allowed_origins (comma-separated CORS)
- Integrations:
  - fmp_api_key, news_api_key, vapi_api_key
- Strategy defaults:
  - shadow_portfolio_cash, anxiety_threshold

Why this matters:
- No module hardcodes infra coordinates.
- Local -> cloud migration is done by env updates.

### 2) backend/deps.py
Lazy singleton factory for expensive/shared dependencies.

What it lazily provides:
- LLM client (OpenAI SDK style, Groq first, Gemini fallback)
- MongoClient + db + collections
- Qdrant client (local or cloud with api_key)
- HuggingFace embeddings (384-dim)
- Mem0 instance (vector store + optional Neo4j graph)

Key behavior:
- `ensure_qdrant_collections()` auto-creates:
  - market_research
  - reflection_memory
- `get_vector_store()` dynamically passes qdrant api key when cloud is used.

Why lazy-init is important:
- Importing modules does not require all infra to be up.
- Startup is resilient in partial environments.

### 3) backend/main.py
FastAPI entrypoint and lifecycle hooks.

Startup sequence:
1. Initialize app metadata.
2. Parse CORS origins from allowed_origins.
3. Register routers.
4. On startup:
   - ensure Qdrant collections
   - start APScheduler evaluator (every 4h)
5. On shutdown:
   - stop scheduler

Primary health endpoint:
- GET / returns app status + scheduler status.

---

## Phase 2: Graph Contract + Routing

### 4) backend/schemas/agent_state.py
Defines the LangGraph shared state contract from start to finish.

Key state buckets:
- Input: user_id, tickers
- Research output: market_data, news_articles
- Sentiment output: vibe_scores
- Strategy output: trade_decisions, should_alert, alert_reason, memories, snapshot
- Execution output: execution_results
- Alert output: alert_sent
- Conversation plumbing: messages

This file is your truth source for what each node must read/write.

### 5) backend/graph/builder.py
Builds and compiles graph topology:
- START -> researcher -> vibe_analyst -> strategist
- Strategist routes conditionally:
  - executor path when trade_decisions exist
  - alerter path when should_alert=true and no trades
  - end otherwise
- executor -> reflector -> END
- alerter -> END

Provides:
- compile_graph_simple() for one-shot runs
- compile_graph_with_checkpointer() using MongoDBSaver

### 6) backend/graph/edges.py
Contains routing function:
- route_after_strategy(state): executor | alerter | __end__

Small file, huge importance because it determines operational path.

---

## Phase 3: Graph Nodes Deep Dive

### 7) Researcher Node
File: backend/graph/nodes/researcher.py

Responsibilities:
- fetches price data per ticker via market_service.get_stock_price()
- fetches up to 3 news items per ticker
- attaches related_ticker on each article
- emits summary message into state.messages

Output:
- market_data dict
- flattened news_articles list

### 8) Vibe Analyst Node
File: backend/graph/nodes/vibe_analyst.py

Responsibilities:
- builds context from price + 5-day trend + news snippets
- calls LLM in JSON mode to get per-ticker:
  - sentiment_score (-1..1)
  - anxiety_score (0..10)
  - vibe_label
  - key_driver
- persists sentiment docs to MongoDB market_sentiments
- fallback mode: neutral/anxiety=5 when LLM fails

Important robustness detail:
- news summary/title fields are null-safe to avoid crash in missing-news scenarios.

### 9) Strategist Node
File: backend/graph/nodes/strategist.py

Responsibilities:
- loads shadow portfolio snapshot from MongoDB
- retrieves reflection memory from Qdrant
- retrieves user memory from Mem0
- asks LLM for trade plan JSON
- enforces anxiety override:
  - if max anxiety >= threshold, should_alert=true even if LLM omitted

Output:
- trade_decisions
- should_alert + alert_reason
- portfolio snapshot and retrieved memory snippets

Key concept:
- This node is where current market + historical memory + preferences are merged.

### 10) Executor Node
File: backend/graph/nodes/executor.py

Responsibilities:
- validates trades against strict rules:
  - cash availability
  - max single trade 5%
  - minimum 10% cash reserve
  - max single position 10%
  - cannot sell more shares than owned
- executes BUY/SELL into in-memory snapshot
- writes trade logs
- persists updated portfolio

Output:
- execution_results with statuses EXECUTED/REJECTED/FAILED

### 11) Reflector Node
File: backend/graph/nodes/reflector.py

Responsibilities:
- converts executed trades into textual lessons
- stores lessons in reflection_memory Qdrant collection
- stores conversation summary into Mem0 for user context continuity

Why it matters:
- forms the self-improvement memory loop consumed by Strategist later.

### 12) Alerter Node
File: backend/graph/nodes/alerter.py

Responsibilities:
- runs only when should_alert=true
- computes affected tickers and estimated impact
- generates action suggestions
- stores alerts in MongoDB
- optionally triggers Vapi voice call

Output:
- alert_sent flag and user-facing alert summary message

---

## Phase 4: Autonomous AI Brain (Most Critical Module)

### 13) backend/services/ai_brain.py
This is a standalone autonomous engine separate from the graph pipeline, focused on fully autonomous portfolio operation.

Core cycle:
1. SCAN
2. ANALYZE
3. REVIEW
4. EXECUTE
5. LOG

#### SCAN
- Builds dynamic stock universe (India-first):
  - NSE APIs
  - FMP search-symbol (NSE/BSE)
  - FMP biggest-gainers/losers/most-actives
  - Yahoo screeners
  - static fallback universe
- LLM picks exactly MAX_SCAN_CANDIDATES (12)
- fallback diversity sampler if LLM fails

#### ANALYZE
Per ticker:
- gets live price + 5d history + news + vibe
- asks LLM for structured verdict:
  - action, conviction, analysis, target, risk, timeframe, allocation
- handles parse and errors safely

#### REVIEW
- batches all existing holdings into one LLM call (rate-limit efficient)
- returns HOLD/BUY_MORE/TRIM/SELL_ALL with reasons and confidence
- safe fallback = HOLD all

#### EXECUTE
Three phases:
- Phase A: SELL/TRIM first to free cash
- Phase B: BUY_MORE for existing positions
- Phase C: BUY new high-conviction candidates
Then persists updated holdings and logs every trade.

#### LLM Reliability and Rate Limiting
`_llm_json()`:
- parse strategy: direct json -> fenced json -> bracket matching
- fail-fast for non-429 errors
- special 429 logic:
  - parse retry wait from provider message
  - sleep
  - retry once

#### Metrics and history
- get_brain_history(): reads ai_brain_logs
- get_brain_stats(): holdings, pnl, cycle count, trade count

### 14) backend/routes/ai_brain.py
Exposes brain operations:
- POST /api/brain/run
- GET /api/brain/history
- GET /api/brain/stats
- POST /api/brain/scan
- POST /api/brain/analyze/{ticker}

---

## Phase 5: API Surface and User Flows

### Authentication
Files:
- backend/services/auth_service.py
- backend/routes/auth.py

Current auth model:
- custom HMAC-SHA256 password hashing helper
- custom JWT-like token (HS256 format)
- signup/login/me endpoints

Important note:
- service currently uses hardcoded secret and simple hash flow suitable for prototype/hackathon, not production-grade auth hardening.

### Agent API
File: backend/routes/agent.py

Key endpoints:
- POST /api/agent/analyze
- GET /api/agent/stream (SSE node updates)
- POST /api/agent/chat
- POST /api/agent/chat/seed
- GET /api/agent/portfolio
- GET /api/agent/trades
- GET /api/agent/alerts
- GET /api/agent/reflections

SSE behavior:
- streams node-by-node updates from graph.stream(..., stream_mode="updates")
- emits done/error final events

### User Portfolio API
File: backend/routes/user_portfolio.py

Main capabilities:
- token-authenticated personal portfolio CRUD
- live price refresh
- AI prediction per holding and bulk
- global stock search
- AI-managed shadow portfolio views and trade history

Prediction normalization:
- coerces model output into stable schema:
  - signal (BUY/HOLD/SELL)
  - target_price, target_pct
  - horizon_days (1..30)
  - confidence (0..1)
- computes missing target_pct/target_price as needed

### Market and Portfolio APIs
Files:
- backend/routes/market.py
- backend/routes/portfolio.py

Provide:
- quote/news/vibe aggregation
- manual evaluation trigger
- portfolio trade history and value history retrieval

### Webhook API
File: backend/routes/webhook.py

Purpose:
- stores all Vapi callback events
- updates alert call outcome when calls complete

---

## Phase 6: RAG, Vector Search, and Memory

### Vector Service
File: backend/services/vector_service.py

Collections:
- market_research: educational/investment context
- reflection_memory: post-trade lessons

Operations:
- search_reflection_memory(query, k)
- store_reflection_lesson(lesson, metadata)
- search_market_research(query, k)
- store_market_documents(documents)

### Memory Service
File: backend/services/memory_service.py

Wrapper around Mem0:
- add_user_memory(user_id, messages)
- search_user_memory(user_id, query)

### RAG Chat Service
File: backend/services/rag_chat_service.py

Flow:
1. Ensure seeded corpus (if sparse)
2. Search user memory for personalized context
3. Search Qdrant market_research for relevant chunks
4. Build grounded prompt + memory block
5. Request structured JSON response from LLM
6. Construct citations and return action_bias/timeframe/risk/followups
7. Write Q/A back to Mem0

Seed corpus includes:
- diversification, position sizing, valuation multiples, earnings quality
- macro regimes, momentum risk, behavioral biases, hold/sell framework
- ETF vs single stock, AI/tech DD

---

## Phase 7: Continuous Learning Jobs

### Evaluator
File: backend/jobs/evaluator.py

Purpose:
- checks pending trades whose horizon_days have elapsed
- computes actual_pct versus execution price
- marks success/failure
- generates detailed lesson text
- writes outcome to trade_logs
- stores lesson in reflection_memory

Failure taxonomy examples:
- major_loss
- minor_loss
- underperformance
- premature_exit
- wrong_direction

### Scheduler
File: backend/jobs/scheduler.py

- APScheduler background scheduler
- evaluator job every 4 hours
- startup and shutdown hooks in FastAPI main

---

## Phase 8: Frontend Deep Walkthrough

### app/layout and providers
Files:
- frontend/app/layout.tsx
- frontend/components/ClientProviders.tsx

- wraps entire app with AuthProvider and Navbar
- sets metadata and global styles

### Auth context
File: frontend/lib/auth.tsx

- keeps `user` + `token` in React state
- persists both in localStorage
- exposes login/signup/logout methods

### Typed API client
File: frontend/lib/api.ts

- centralized fetchJSON wrapper with API_URL base
- type-rich contracts for:
  - graph analysis
  - RAG chat
  - user portfolio
  - AI portfolio
  - AI brain cycles
  - market/vibe/trade/reflection feeds

### Dashboard pages
- frontend/app/dashboard/page.tsx
  - one-click graph analysis and summary cards
  - embeds chart/vibe/trades/reflections widgets

- frontend/app/dashboard/my-portfolio/page.tsx
  - authenticated user portfolio
  - add/search/remove holdings
  - refresh live prices + AI predictions
  - polling mode

- frontend/app/dashboard/ai-portfolio/page.tsx
  - AI shadow portfolio PnL and holdings
  - run brain cycle button
  - shows brain history + stats + execution outcomes

- frontend/app/dashboard/chat/page.tsx
  - RAG Q&A interface
  - optional seed action
  - citation toggles, follow-up chips, confidence badges

### Shared widgets
- PortfolioChart: value curve from shadow history
- VibeGauge: aggregate anxiety + per-ticker vibe chips
- TradeLogTable: latest trades and outcomes
- ReflectionFeed: lesson history from /api/agent/reflections

---

## Request/Response Cheat Sheet

### Analyze pipeline
POST /api/agent/analyze

Input:
```json
{
  "tickers": ["AAPL", "TSLA", "NVDA"],
  "user_id": "demo_user"
}
```

Output highlights:
- market_data
- vibe_scores
- trade_decisions
- execution_results
- alert_sent / alert_reason

### RAG chat
POST /api/agent/chat

Input:
```json
{
  "question": "How should I size NVDA in a medium-risk portfolio?",
  "user_id": "demo_user",
  "top_k": 6
}
```

Output highlights:
- answer
- citations[]
- confidence
- action_bias
- risk_notes[]

### Brain run
POST /api/brain/run

Output:
- cycle log with scan, analyses, hold_decisions, trades, summary, duration

---

## End-to-End Trace (One Typical User Journey)

### Scenario A: User runs dashboard analyze
1. UI sends ticker list to /api/agent/analyze.
2. Graph executes nodes in sequence.
3. Researcher fetches price/news.
4. Vibe analyst scores sentiment+anxiety and persists market_sentiments.
5. Strategist combines portfolio + reflection + user memory and decides trades.
6. Executor validates and writes portfolio + trade logs.
7. Reflector stores lessons + conversation memory.
8. Response returns full payload rendered in dashboard cards/tables.

### Scenario B: User asks AI Chat question
1. UI sends question to /api/agent/chat.
2. Service ensures corpus seeded.
3. Retrieves context from market_research and memory from Mem0.
4. LLM returns JSON answer.
5. Service attaches citations from retrieved chunks.
6. UI renders answer/risk/followups/source cards.

### Scenario C: Brain autonomous run
1. User triggers /api/brain/run.
2. Service scans universe (India-first).
3. Analyzes each candidate with throttled LLM calls.
4. Reviews current holdings in a batched LLM call.
5. Executes sell/trim/buy_more/buy-new in order.
6. Persists cycle log and trade logs.

---

## Data Model Snapshot (Mongo + Qdrant)

MongoDB collections commonly used:
- users
- portfolios
- user_portfolios
- trade_logs
- market_sentiments
- alerts
- ai_brain_logs
- vapi_webhooks

Qdrant collections:
- market_research (RAG knowledge)
- reflection_memory (post-trade lessons)

---

## Local Setup and Boot Sequence

### 1) Infrastructure
`docker-compose up -d`

Starts:
- MongoDB on 27017
- Qdrant on 6333
- Neo4j on 7474/7687

### 2) Backend
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.seed_portfolio
python -m backend.main
```

### 3) Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4) Optional env
Use `.env.example` as template for:
- GROQ_API_KEY
- MONGO_URI
- QDRANT_URL / QDRANT_API_KEY
- FMP_API_KEY
- ALLOWED_ORIGINS

---

## Production/Deployment Learning Notes

- Backend start command (Render):
  - gunicorn backend.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120
- Frontend API base from NEXT_PUBLIC_API_URL
- CORS originates from ALLOWED_ORIGINS
- Qdrant cloud auth via qdrant_api_key is already supported

---

## Debugging Playbook

### Graph analyze returns error
Check:
1. backend logs for node where failure occurred
2. /docs endpoint test for /api/market/quote and /api/agent/analyze
3. qdrant collections created on startup

### RAG chat gives weak answers
Check:
1. POST /api/agent/chat/seed executed
2. market_research collection has vectors
3. top_k not too low
4. API key and model availability

### No reflections shown
Check:
1. trades executed successfully
2. reflector wrote lessons to reflection_memory
3. /api/agent/reflections returns count > 0

### 429 rate-limit behavior
- ai_brain has one retry with dynamic wait parsing
- candidate analysis includes inter-call sleep
- if limits continue, switch to higher TPM model and/or reduce candidate count

---

## Common Design Patterns Used

1. Lazy dependency factories
2. Typed state for agent graph
3. LLM JSON schema prompting + robust parsing
4. Fallback-safe pipeline behavior
5. Persistent memory loop:
   - decision -> trade -> evaluate -> lesson -> retrieval
6. UI typed API client for end-to-end contract consistency

---

## Suggested Learning Exercises

### Beginner
1. Change anxiety threshold and observe alert behavior.
2. Add one new ticker to static universe and run one brain cycle.
3. Seed portfolio and verify chart updates.

### Intermediate
1. Add a new strategist risk rule (for example sector cap).
2. Extend RAG schema to include portfolio-allocation percentages.
3. Add a market endpoint for top movers consumed by frontend.

### Advanced
1. Add confidence calibration from evaluator outcomes.
2. Add multi-user AI Brain cycles (one shadow portfolio per user).
3. Add backtesting mode by injecting historical prices instead of live yfinance.

---

## Security and Hardening Notes (Important)

Current codebase is strong for prototyping/hackathon velocity, but before production hardening consider:
- replacing custom password hashing/JWT with mature auth libs (bcrypt + PyJWT/jose)
- moving static secrets to env-only
- adding stricter input validation and rate limiting per endpoint
- adding audit logs and role-based access boundaries

---

## One-Page Mental Model

FinVibe is two intelligence loops sharing the same data layer:

1) Graph loop (interactive, per user request)
- fast pipeline for analyzing selected tickers with explainable outputs

2) Brain loop (autonomous, cycle-based)
- continuously discovers, analyzes, and rebalances virtual portfolio

Both loops improve over time through evaluator/reflection memory and can be inspected from API + dashboard surfaces.

---

## Quick Reference: Most Important Files

Backend core:
- backend/main.py
- backend/config.py
- backend/deps.py
- backend/services/ai_brain.py
- backend/graph/builder.py
- backend/graph/nodes/*.py
- backend/routes/agent.py
- backend/routes/user_portfolio.py
- backend/jobs/evaluator.py
- backend/services/rag_chat_service.py

Frontend core:
- frontend/lib/api.ts
- frontend/lib/auth.tsx
- frontend/app/dashboard/page.tsx
- frontend/app/dashboard/my-portfolio/page.tsx
- frontend/app/dashboard/ai-portfolio/page.tsx
- frontend/app/dashboard/chat/page.tsx

Infra/scripts:
- docker-compose.yml
- scripts/seed_portfolio.py
- .env.example

---

If you study in the phase order above and trace one request through backend -> DB -> frontend, you will understand both architecture and behavior quickly and deeply.
