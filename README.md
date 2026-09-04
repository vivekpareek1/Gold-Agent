# Gold Intraday Trading Agent (rule-based, free)

Autonomous XAU/USD intraday paper-trading agent. Fixed-rule confluence
strategy -- NOT LLM-based (reverted from an LLM/Gemini approach after
repeated billing/quota problems on the free tier). Zero ongoing API cost.

## Strategy
15-min confluence: EMA9/21/50 trend stack + RSI(14) momentum band +
MACD confirmation + pullback-to-EMA21 entry trigger. ATR(14)-based
stop loss (1.5x ATR), take profit at 2:1 reward:risk.

## Risk
- Paper account: $10,000 | Risk per trade: 1% ($100)
- Max 1 open trade | Daily loss limit: 3% | Pause after 3 consecutive losses

## Files
- `config.py` — all parameters
- `data_fetcher.py` — Twelve Data API client
- `indicators.py` — EMA/RSI/MACD/ATR
- `strategy.py` — fixed-rule signal generation + reasoning text per trade
- `risk_manager.py` — position sizing + risk gates
- `db.py` — Postgres access (schema `gold_agent` on the shared free DB)
- `live_check.py` — checked every 15 min via GitHub Actions -> /run-check
- `backtest.py` — free, instant, run via /run-backtest or locally
- `dashboard/` — public Flask dashboard with trade log + reasoning per trade,
  plus protected `/run-check` and `/run-backtest` admin endpoints

## Environment variables (set on Render)
- `TWELVE_DATA_API_KEY`
- `DATABASE_URL` (shared free Postgres, schema `gold_agent`)
- `DB_SCHEMA` (defaults to `gold_agent`)
- `RUN_TOKEN` (shared secret protecting the admin endpoints)
- `PYTHON_VERSION=3.11.9` (pin -- pandas has no prebuilt wheels for newer Python)

## Scheduling
Render free tier has no cron job support, so a GitHub Actions workflow
(`.github/workflows/schedule.yml`) calls `/run-check?token=...` every 15
minutes on weekdays (best-effort timing, GitHub's scheduler can lag a few
minutes under load).

## Running the backtest
Visit `/run-backtest?token=...` once (runs in background, ~seconds since
it's rule-based, watch the Backtest tab), or locally:
```
pip install -r requirements.txt
export TWELVE_DATA_API_KEY=...
export DATABASE_URL=...
python backtest.py
```
