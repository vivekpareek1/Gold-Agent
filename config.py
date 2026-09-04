"""
Configuration for the Gold Intraday Trading Agent.
All values are read from environment variables (set on Render as
service env vars / secrets). Nothing here is hardcoded to a secret value.
"""
import os

# --- Data source ---
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"
SYMBOL = os.environ.get("SYMBOL", "XAU/USD")
INTERVAL = os.environ.get("INTERVAL", "15min")  # 15-minute candles

# --- Database (reused free Postgres instance, isolated schema) ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_SCHEMA = os.environ.get("DB_SCHEMA", "gold_agent")

# --- Account / risk parameters ---
ACCOUNT_SIZE = float(os.environ.get("ACCOUNT_SIZE", "10000"))
RISK_PCT = float(os.environ.get("RISK_PCT", "0.01"))  # 1% per trade
MAX_OPEN_TRADES = int(os.environ.get("MAX_OPEN_TRADES", "1"))
DAILY_LOSS_LIMIT_PCT = float(os.environ.get("DAILY_LOSS_LIMIT_PCT", "0.03"))  # 3% of account/day
MAX_CONSECUTIVE_LOSSES = int(os.environ.get("MAX_CONSECUTIVE_LOSSES", "3"))

# --- Strategy parameters ---
EMA_FAST = 9
EMA_MID = 21
EMA_SLOW = 50
RSI_PERIOD = 14
RSI_LOWER = 40
RSI_UPPER = 70
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5
REWARD_RISK_RATIO = 2.0  # TP = 2x the SL distance
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# --- Trading session (XAUUSD trades ~23h/day, Sun 22:00 UTC - Fri 22:00 UTC) ---
# We restrict to weekdays only; hours left open since XAUUSD is near-continuous.
TRADING_DAYS = {0, 1, 2, 3, 4}  # Mon-Fri (datetime.weekday())

# Mode tag used when writing rows to the trades table
MODE_LIVE = "live"
MODE_BACKTEST = "backtest"

# --- LLM-based decision making (replaces rule-only strategy.py) ---
# Using Google Gemini (free tier: gemini-2.5-flash, no card, ~1500 req/day)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
LLM_MAX_TOKENS = 1200

# Pre-filter thresholds (cheap, free, deterministic) -- only call the LLM
# when there's at least partial trend+momentum alignment, to avoid paying
# for a decision on candles with obviously nothing going on.
PREFILTER_RSI_LOWER = 35
PREFILTER_RSI_UPPER = 75

# Safety clamp: reject any LLM-proposed SL that implies more than this many
# ATRs of risk (guards against a bad/hallucinated price level).
MAX_SL_ATR_MULTIPLE = 4.0

# Backtest cost/time guard -- hard stop if pre-filter is looser than expected
MAX_BACKTEST_LLM_CALLS = 800

# --- Admin trigger endpoints (called by the external GitHub Actions scheduler
# since Render's free tier has no cron job support) ---
RUN_TOKEN = os.environ.get("RUN_TOKEN", "")


# --- Position sizing safety limits (added after a live anomaly: a near-zero
# ATR candle produced a 0.41-point SL distance, which the naive risk_amount/
# distance formula blew up into a 243oz / ~97x-leverage position) ---
MIN_SL_DISTANCE_PCT = 0.0015  # SL must be at least 0.15% of entry price away, else reject the trade
MAX_POSITION_VALUE_MULTIPLE = 8.0  # hard cap: notional position value <= 8x account size
