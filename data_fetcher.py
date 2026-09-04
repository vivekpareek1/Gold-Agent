"""
Thin wrapper around the Twelve Data REST API.
Handles fetching OHLC candle history for XAU/USD.
"""
import requests
import pandas as pd
import config


class DataFetchError(Exception):
    pass


def get_candles(symbol: str = None, interval: str = None, outputsize: int = 200) -> pd.DataFrame:
    """
    Fetch recent OHLC candles from Twelve Data.
    Returns a DataFrame sorted oldest -> newest, indexed by datetime, with
    columns: open, high, low, close, volume (volume may be 0 for FX/metals).
    """
    symbol = symbol or config.SYMBOL
    interval = interval or config.INTERVAL

    if not config.TWELVE_DATA_API_KEY:
        raise DataFetchError("TWELVE_DATA_API_KEY is not set in the environment.")

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": config.TWELVE_DATA_API_KEY,
        "order": "ASC",
    }
    resp = requests.get(f"{config.TWELVE_DATA_BASE_URL}/time_series", params=params, timeout=15)
    data = resp.json()

    if "status" in data and data["status"] == "error":
        raise DataFetchError(f"Twelve Data error: {data.get('message', 'unknown error')}")

    if "values" not in data:
        raise DataFetchError(f"Unexpected response from Twelve Data: {data}")

    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    if "volume" in df.columns:
        df["volume"] = df["volume"].astype(float)
    else:
        df["volume"] = 0.0
    df = df.set_index("datetime")
    return df[["open", "high", "low", "close", "volume"]]


def get_latest_price(symbol: str = None) -> float:
    """Fetch the latest real-time price for the symbol."""
    symbol = symbol or config.SYMBOL
    if not config.TWELVE_DATA_API_KEY:
        raise DataFetchError("TWELVE_DATA_API_KEY is not set in the environment.")

    params = {"symbol": symbol, "apikey": config.TWELVE_DATA_API_KEY}
    resp = requests.get(f"{config.TWELVE_DATA_BASE_URL}/price", params=params, timeout=15)
    data = resp.json()
    if "price" not in data:
        raise DataFetchError(f"Unexpected response from Twelve Data /price: {data}")
    return float(data["price"])
