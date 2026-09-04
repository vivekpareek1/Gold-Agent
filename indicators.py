"""
Technical indicator calculations: EMA, RSI, MACD, ATR.
Pure pandas/numpy implementations, no external TA library dependency
(keeps the Render deploy lightweight).
"""
import pandas as pd
import numpy as np


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def add_all_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Adds all indicator columns needed by the strategy to a copy of df."""
    out = df.copy()
    out["ema_fast"] = ema(out["close"], cfg.EMA_FAST)
    out["ema_mid"] = ema(out["close"], cfg.EMA_MID)
    out["ema_slow"] = ema(out["close"], cfg.EMA_SLOW)
    out["rsi"] = rsi(out["close"], cfg.RSI_PERIOD)
    macd_line, signal_line, hist = macd(out["close"], cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
    out["macd"] = macd_line
    out["macd_signal"] = signal_line
    out["macd_hist"] = hist
    out["atr"] = atr(out, cfg.ATR_PERIOD)
    return out
