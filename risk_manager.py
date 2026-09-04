"""
Position sizing and risk-gate checks for the paper trading account.
"""
import config


def position_size(entry: float, sl: float, account_size: float = None, risk_pct: float = None) -> float:
    """
    Risk-based position sizing.
    Returns size in troy ounces of gold (XAU/USD is quoted per ounce).
    risk_amount = account_size * risk_pct
    size = risk_amount / abs(entry - sl)
    """
    account_size = account_size or config.ACCOUNT_SIZE
    risk_pct = risk_pct if risk_pct is not None else config.RISK_PCT
    distance = abs(entry - sl)
    if distance <= 0:
        return 0.0
    risk_amount = account_size * risk_pct
    size_oz = risk_amount / distance
    return round(size_oz, 4)


def can_open_new_trade(open_trades_count: int, todays_realized_pnl: float,
                        consecutive_losses: int, account_size: float = None) -> tuple[bool, str]:
    """
    Risk gate checked before opening any new trade.
    Returns (allowed: bool, reason: str)
    """
    account_size = account_size or config.ACCOUNT_SIZE

    if open_trades_count >= config.MAX_OPEN_TRADES:
        return False, f"Max open trades ({config.MAX_OPEN_TRADES}) already reached."

    daily_loss_limit = -abs(account_size * config.DAILY_LOSS_LIMIT_PCT)
    if todays_realized_pnl <= daily_loss_limit:
        return False, (f"Daily loss limit hit: realized P&L {todays_realized_pnl:.2f} "
                        f"<= limit {daily_loss_limit:.2f}. No new trades today.")

    if consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
        return False, (f"{consecutive_losses} consecutive losses reached "
                        f"(limit {config.MAX_CONSECUTIVE_LOSSES}). Pausing new entries.")

    return True, "OK"
