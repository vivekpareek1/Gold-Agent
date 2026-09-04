"""
High-impact US economic event calendar for gold (XAU/USD).

Free, zero-API-key approach: FOMC meeting dates, CPI release dates, and
Nonfarm Payrolls (Employment Situation) dates are all published MONTHS in
advance by the Federal Reserve and Bureau of Labor Statistics themselves --
these are the events that move gold the most, and they don't need Forex
Factory or any scraper to know about.

Trade-off (stated plainly): this covers only the 3 biggest recurring US
releases, not every minor economic print Forex Factory lists. That's a
deliberate choice -- those three account for the large majority of gold's
news-driven volatility, and this list has zero ongoing cost or breakage risk.

MAINTENANCE: dates were sourced from federalreserve.gov and bls.gov in
September 2026. FOMC dates are set a year ahead and rarely change. CPI/NFP
dates for a few months (mid-2026 onward at time of writing) were extrapolated
from the BLS's usual "second week" / "first Friday" pattern where the
official calendar wasn't yet published -- re-verify at bls.gov/schedule
periodically, especially near government-shutdown risk periods (BLS has
skipped/delayed releases before, e.g. Oct 2025).
"""
from datetime import datetime, timedelta, timezone

FOMC_EVENTS_UTC = [
    "2026-01-28 19:00", "2026-03-18 18:00", "2026-04-29 18:00", "2026-06-17 18:00",
    "2026-07-29 18:00", "2026-09-16 18:00", "2026-10-28 18:00", "2026-12-09 19:00",
]

CPI_EVENTS_UTC = [
    "2026-01-13 13:30", "2026-02-11 13:30", "2026-03-11 12:30", "2026-04-14 12:30",
    "2026-05-12 12:30", "2026-06-10 12:30", "2026-07-14 12:30", "2026-08-12 12:30",
    "2026-09-11 12:30", "2026-10-13 12:30", "2026-11-12 13:30", "2026-12-10 13:30",
]

NFP_EVENTS_UTC = [
    "2026-01-09 13:30", "2026-02-11 13:30", "2026-03-06 13:30", "2026-04-03 12:30",
    "2026-05-08 12:30", "2026-06-05 12:30", "2026-07-03 12:30", "2026-08-07 12:30",
    "2026-09-04 12:30", "2026-10-02 12:30", "2026-11-06 13:30", "2026-12-04 13:30",
]

_ALL_EVENTS = (
    [(t, "FOMC rate decision") for t in FOMC_EVENTS_UTC]
    + [(t, "CPI release") for t in CPI_EVENTS_UTC]
    + [(t, "Nonfarm Payrolls") for t in NFP_EVENTS_UTC]
)


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def check_event_window(now_utc: datetime, buffer_minutes: int = 45):
    """
    Returns (in_window: bool, description: str or None).
    in_window is True if `now_utc` falls within `buffer_minutes` before OR
    after any listed high-impact event -- gold often whipsaws violently in
    this window and a mechanical confluence strategy has no way to judge
    a news reaction, so the safest move is to sit it out.
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    buffer = timedelta(minutes=buffer_minutes)
    for ts, label in _ALL_EVENTS:
        event_time = _parse(ts)
        if event_time - buffer <= now_utc <= event_time + buffer:
            return True, f"{label} at {event_time.strftime('%Y-%m-%d %H:%M UTC')}"
    return False, None
