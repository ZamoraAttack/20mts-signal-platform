# 20 MTS — Signal Detection & Research Platform

A research platform that translates a manually-traded options strategy into software — detecting leader/follower divergence setups between a market index and an individual stock in real time, logging every signal with full outcome tracking, and providing analytics to evaluate whether the strategy actually works before ever risking capital on it.

## Why this exists

The strategy ("20 Minute Trading Strategy") was originally traded by eye on 1-second charts: watch a leader instrument and a correlated stock, look for a moment where they desynchronize, and trade the reconnection. The goal of this platform is **not** to invent a better strategy — it's to faithfully encode the exact rules a human follows, run them tirelessly against live or historical data, and produce the outcome data needed to evaluate the strategy objectively instead of by gut feel. Filters and thresholds are deliberately *not* invented beyond what the strategy defines — the philosophy is "record and bucket everything, let the evidence decide," not assume a threshold upfront.

## The strategy

Four sequential conditions must fire in order for a signal:

| # | Condition | Rule |
|---|---|---|
| 1 | **Synchronization** | Leader/stock 1s-return correlation ≥ 0.70 over a trailing 5-minute window (background regime filter) |
| 2 | **Joint decline** | Both instruments down ≥ 0.05% over 12s and trading below their 25s EMA |
| 3 | **Divergence** | Leader shows 3+ consecutive upticks (or a positive 5s return) while the stock stays flat/negative |
| 4 | **Reconnection** | Stock shows 2+ consecutive upticks, or trades above its price from 10s ago — this is the entry trigger |

A signal expires if reconnection hasn't happened within 120 seconds of divergence starting (a "red herring"). Every signal — fired or expired — is logged with its full outcome, not just the winners.

## Architecture

```
                    ┌─────────────────────────────┐
 Live/Replay Feed ─►│      Signal State Machine     │  IDLE → MONITORING → JOINT_DECLINE
 (Schwab / CSV /    │  (ring buffers, EMA, tick     │       → DIVERGENCE → SIGNAL_FIRED
  simulated)        │   direction tracking)         │            or SIGNAL_EXPIRED
                    └─────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                            ▼
            PostgreSQL (every tick,        WebSocket broadcast
            every signal, every            (live chart + state
            outcome persisted)             updates to frontend)
                    │
                    ▼
      Outcome Tracker (watches 20 min post-signal,
      auto-populates peak/trough/gain %, never
      touches the human "was this a good trade?" call)
                    │
                    ▼
      Analytics (win rate by stock / by day / by
      time-of-day / by divergence-duration bucket)
```

- **Signal engine** is pure logic with no I/O — fully unit-testable in isolation from any data source.
- **Three interchangeable data feeds** behind one interface: a simulated correlated random-walk feed (dev/testing), a historical CSV replay feed (backtesting), and a real Schwab market-data feed (live) — the state machine and everything downstream never knows which one it's connected to.
- **Outcome tracking is automatic but classification stays human**: the tracker auto-computes objective numbers (max gain, time-to-peak, drawdown), but whether a signal was a "good trade" is always a human judgment call, never inferred.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy (async), asyncpg, WebSockets |
| Database | PostgreSQL |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, `lightweight-charts` |
| Market data | Schwab API (live), Databento (historical backtesting), synthetic generator (dev) |
| Testing | pytest / pytest-asyncio — 100+ backend tests |

## Backtesting / replay

Any session the engine has ever processed — live, simulated, or replayed — is exported back into the same CSV shape the replay feed reads, so every run becomes a reusable backtest. A synthetic data generator (`backend/scripts/generate_sample_replay.py`) produces a correlated leader/stock CSV with realistic price action for anyone running the project without a paid market-data subscription:

```bash
python scripts/generate_sample_replay.py --date 2025-03-17 --minutes 30
```

(Real historical data for this project's own development came from [Databento](https://databento.com); those CSVs are excluded from this repo since redistributing licensed market data isn't something we have rights to do — the generator above produces an equivalent synthetic dataset instead.)

## Running it

```bash
# Database (local dev via Docker)
docker compose up -d db

# Backend
cd backend
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` — the frontend proxies `/api` and `/ws` to the backend. Defaults to a simulated data feed, so it runs out of the box with no market-data credentials at all.

## Status

Backend: 100+ tests passing. Validated end-to-end against real historical data (not just synthetic) — the engine reproduces the same divergence/reconnection signals deterministically across repeated runs. Live Schwab market-data integration is built and scaffolded, pending Schwab developer API approval; the platform runs fully today against simulated or replayed historical data.
