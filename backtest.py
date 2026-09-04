"""
Backtest the rule-based strategy against historical XAU/USD candles.
Free, instant, deterministic -- no API calls, no cost.
Run manually: python backtest.py
"""
import config
import data_fetcher
import indicators
import strategy
import risk_manager
import db

MODE = config.MODE_BACKTEST


def run_backtest(outputsize=5000):
    db.init_db()

    print(f"Fetching up to {outputsize} historical {config.INTERVAL} candles for {config.SYMBOL}...")
    df = data_fetcher.get_candles(outputsize=outputsize)
    df_ind = indicators.add_all_indicators(df, config)
    print(f"Got {len(df_ind)} candles: {df_ind.index[0]} to {df_ind.index[-1]}")

    min_bars = config.EMA_SLOW + 5
    open_trade = None
    closed_trades = []
    consecutive_losses = 0
    daily_pnl = {}

    for i in range(min_bars, len(df_ind)):
        window = df_ind.iloc[: i + 1]
        bar = window.iloc[-1]
        today = bar.name.date()
        daily_pnl.setdefault(today, 0.0)

        if open_trade:
            direction = open_trade["direction"]
            hit_tp = (direction == "BUY" and bar["high"] >= open_trade["tp"]) or \
                     (direction == "SELL" and bar["low"] <= open_trade["tp"])
            hit_sl = (direction == "BUY" and bar["low"] <= open_trade["sl"]) or \
                     (direction == "SELL" and bar["high"] >= open_trade["sl"])
            if hit_sl:
                exit_price = open_trade["sl"]
                pnl = (exit_price - open_trade["entry"]) * open_trade["size"] if direction == "BUY" \
                    else (open_trade["entry"] - exit_price) * open_trade["size"]
                status = "CLOSED_SL"
            elif hit_tp:
                exit_price = open_trade["tp"]
                pnl = (exit_price - open_trade["entry"]) * open_trade["size"] if direction == "BUY" \
                    else (open_trade["entry"] - exit_price) * open_trade["size"]
                status = "CLOSED_TP"
            else:
                pnl = None

            if pnl is not None:
                open_trade["exit_time"] = bar.name
                open_trade["exit_price"] = exit_price
                open_trade["status"] = status
                open_trade["pnl"] = pnl
                closed_trades.append(open_trade)
                daily_pnl[today] += pnl
                consecutive_losses = consecutive_losses + 1 if pnl < 0 else 0
                open_trade = None
            else:
                continue

        allowed, _ = risk_manager.can_open_new_trade(
            open_trades_count=0, todays_realized_pnl=daily_pnl[today], consecutive_losses=consecutive_losses,
        )
        if not allowed:
            continue

        signal = strategy.generate_signal(window)
        if signal["signal"] in ("BUY", "SELL"):
            size = risk_manager.position_size(signal["entry"], signal["sl"])
            if size > 0:
                open_trade = {
                    "direction": signal["signal"], "entry": signal["entry"], "sl": signal["sl"],
                    "tp": signal["tp"], "size": size, "entry_time": bar.name,
                    "confidence": signal["confidence"], "reasoning": signal["reasoning"],
                }

    for t in closed_trades:
        trade_id = db.insert_trade(
            mode=MODE, direction=t["direction"], entry_time=t["entry_time"],
            entry_price=t["entry"], sl=t["sl"], tp=t["tp"], size_oz=t["size"],
            confidence=t["confidence"], reasoning=t["reasoning"],
        )
        db.close_trade(trade_id, t["exit_time"], t["exit_price"], t["status"], t["pnl"])

    wins = [t for t in closed_trades if t["pnl"] > 0]
    losses = [t for t in closed_trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in closed_trades)
    win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    print("\n--- BACKTEST SUMMARY ---")
    print(f"Total trades: {len(closed_trades)}")
    print(f"Win rate: {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
    print(f"Total P&L: ${total_pnl:.2f} on ${config.ACCOUNT_SIZE:.0f} ({total_pnl/config.ACCOUNT_SIZE*100:.2f}%)")
    print(f"Profit factor: {profit_factor:.2f}")
    return closed_trades


if __name__ == "__main__":
    run_backtest()
