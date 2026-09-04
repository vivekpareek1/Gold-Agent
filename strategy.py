"""
Confluence-based intraday strategy for XAU/USD.

Logic (applied on the most recently CLOSED candle to avoid repainting):
  Trend filter:   EMA9 / EMA21 / EMA50 stack direction
  Momentum:       RSI in a "healthy trend" band (not overbought/oversold extreme)
  Confirmation:   MACD line vs signal line, and histogram direction
  Entry trigger:  price pulled back near EMA21 (within ~0.6x ATR) then closed
                  back in the trend direction

Every signal carries a human-readable `reasoning` string that explains
exactly which conditions fired -- this is what the dashboard shows per trade.
"""
import config


def generate_signal(df_with_indicators):
    df = df_with_indicators
    if len(df) < config.EMA_SLOW + 5:
        return _wait("Not enough candle history yet to evaluate the strategy.", df.index[-1] if len(df) else None)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    uptrend = last["ema_fast"] > last["ema_mid"] > last["ema_slow"]
    downtrend = last["ema_fast"] < last["ema_mid"] < last["ema_slow"]

    rsi_ok_long = config.RSI_LOWER <= last["rsi"] <= config.RSI_UPPER
    rsi_ok_short = (100 - config.RSI_UPPER) <= last["rsi"] <= (100 - config.RSI_LOWER)

    macd_bullish = last["macd"] > last["macd_signal"] and last["macd_hist"] > prev["macd_hist"]
    macd_bearish = last["macd"] < last["macd_signal"] and last["macd_hist"] < prev["macd_hist"]

    distance_to_ema_mid = abs(last["close"] - last["ema_mid"])
    near_ema_mid = distance_to_ema_mid <= 0.6 * last["atr"]

    reasons = []
    score = 0

    if uptrend:
        reasons.append("EMA9>EMA21>EMA50 (uptrend stack)")
        score += 30
    if downtrend:
        reasons.append("EMA9<EMA21<EMA50 (downtrend stack)")
        score += 30

    if uptrend and rsi_ok_long:
        reasons.append(f"RSI {last['rsi']:.1f} in healthy long zone ({config.RSI_LOWER}-{config.RSI_UPPER})")
        score += 20
    if downtrend and rsi_ok_short:
        reasons.append(f"RSI {last['rsi']:.1f} in healthy short zone")
        score += 20

    if uptrend and macd_bullish:
        reasons.append("MACD above signal line and histogram rising")
        score += 25
    if downtrend and macd_bearish:
        reasons.append("MACD below signal line and histogram falling")
        score += 25

    if near_ema_mid:
        reasons.append("Price within 0.6x ATR of EMA21 (pullback entry zone)")
        score += 25

    long_setup = uptrend and rsi_ok_long and macd_bullish and near_ema_mid
    short_setup = downtrend and rsi_ok_short and macd_bearish and near_ema_mid

    if long_setup:
        entry = float(last["close"])
        sl = entry - config.ATR_SL_MULTIPLIER * float(last["atr"])
        tp = entry + config.REWARD_RISK_RATIO * (entry - sl)
        reasoning = "BUY signal. " + "; ".join(reasons) + \
            f". Entry {entry:.2f}, SL {sl:.2f} ({config.ATR_SL_MULTIPLIER}x ATR), " \
            f"TP {tp:.2f} ({config.REWARD_RISK_RATIO}:1 R:R)."
        return {
            "signal": "BUY", "reasoning": reasoning, "entry": entry, "sl": sl, "tp": tp,
            "confidence": min(score, 100), "timestamp": df.index[-1],
        }

    if short_setup:
        entry = float(last["close"])
        sl = entry + config.ATR_SL_MULTIPLIER * float(last["atr"])
        tp = entry - config.REWARD_RISK_RATIO * (sl - entry)
        reasoning = "SELL signal. " + "; ".join(reasons) + \
            f". Entry {entry:.2f}, SL {sl:.2f} ({config.ATR_SL_MULTIPLIER}x ATR), " \
            f"TP {tp:.2f} ({config.REWARD_RISK_RATIO}:1 R:R)."
        return {
            "signal": "SELL", "reasoning": reasoning, "entry": entry, "sl": sl, "tp": tp,
            "confidence": min(score, 100), "timestamp": df.index[-1],
        }

    why_not = reasons if reasons else ["No trend/momentum/MACD/pullback alignment."]
    reasoning = "WAIT. Partial or no confluence: " + "; ".join(why_not) + "."
    return _wait(reasoning, df.index[-1], score=score)


def _wait(reasoning, timestamp, score=0):
    return {
        "signal": "WAIT", "reasoning": reasoning, "entry": None, "sl": None, "tp": None,
        "confidence": score, "timestamp": timestamp,
    }
