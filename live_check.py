"""
Entry point run on a schedule (Render cron job, every 15 minutes on weekdays).

Each run:
  1. If there's an open live trade -> check whether price has hit SL or TP,
     close it and log the result if so.
  2. If there's no open trade -> fetch latest candles, run the strategy,
     and if it fires BUY/SELL (and passes the risk gate), open a new
     paper trade and log it with full reasoning.

This is intentionally simple and stateless between runs -- all state
(open trade, today's P&L, consecutive losses) is read fresh from Postgres
on every run, so it doesn't matter if the cron job restarts.
"""
import datetime
import config
import data_fetcher
import indicators
import strategy
import risk_manager
import db

MODE = config.MODE_LIVE


def check_and_manage_open_trade():
    open_trade = db.get_open_trade(MODE)
    if not open_trade:
        return False  # no open trade

    current_price = data_fetcher.get_latest_price()
    direction = open_trade["direction"]
    entry = open_trade["entry_price"]
    sl = open_trade["sl"]
    tp = open_trade["tp"]
    size = open_trade["size_oz"]

    hit_tp = (direction == "BUY" and current_price >= tp) or (direction == "SELL" and current_price <= tp)
    hit_sl = (direction == "BUY" and current_price <= sl) or (direction == "SELL" and current_price >= sl)

    if hit_tp or hit_sl:
        exit_price = tp if hit_tp else sl
        status = "CLOSED_TP" if hit_tp else "CLOSED_SL"
        pnl = (exit_price - entry) * size if direction == "BUY" else (entry - exit_price) * size
        db.close_trade(open_trade["id"], datetime.datetime.utcnow(), exit_price, status, pnl)
        print(f"[{datetime.datetime.utcnow()}] Closed trade #{open_trade['id']} "
              f"{status} at {exit_price:.2f}, P&L {pnl:.2f}")
        return True

    print(f"[{datetime.datetime.utcnow()}] Trade #{open_trade['id']} still open "
          f"(price {current_price:.2f}, SL {sl:.2f}, TP {tp:.2f})")
    return True  # trade still open, don't look for a new one this run


def try_open_new_trade():
    open_count = db.get_open_trades_count(MODE)
    todays_pnl = db.get_todays_realized_pnl(MODE)
    consecutive_losses = db.get_consecutive_losses(MODE)

    allowed, reason = risk_manager.can_open_new_trade(open_count, todays_pnl, consecutive_losses)
    if not allowed:
        print(f"[{datetime.datetime.utcnow()}] Risk gate blocked new trade: {reason}")
        return

    df = data_fetcher.get_candles(outputsize=150)
    df_ind = indicators.add_all_indicators(df, config)
    signal = strategy.generate_signal(df_ind)

    print(f"[{datetime.datetime.utcnow()}] Signal: {signal['signal']} | {signal['reasoning']}")

    if signal["signal"] in ("BUY", "SELL"):
        size = risk_manager.position_size(signal["entry"], signal["sl"])
        if size <= 0:
            print("Position size computed as 0 -- skipping trade.")
            return
        trade_id = db.insert_trade(
            mode=MODE,
            direction=signal["signal"],
            entry_time=datetime.datetime.utcnow(),
            entry_price=signal["entry"],
            sl=signal["sl"],
            tp=signal["tp"],
            size_oz=size,
            confidence=signal["confidence"],
            reasoning=signal["reasoning"],
        )
        print(f"Opened trade #{trade_id}: {signal['signal']} {size} oz @ {signal['entry']:.2f}")


def main():
    now = datetime.datetime.utcnow()
    if now.weekday() not in config.TRADING_DAYS:
        print(f"[{now}] Weekend -- market closed, skipping run.")
        return

    db.init_db()
    had_open = check_and_manage_open_trade()
    if not had_open:
        try_open_new_trade()


if __name__ == "__main__":
    main()
