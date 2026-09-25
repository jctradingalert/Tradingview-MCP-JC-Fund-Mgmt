import datetime

import config
import fmp_client
from darvas import to_weekly


def _compound_return(daily_rows: list[dict], trading_days: int = 5) -> float | None:
    """Compounds the trailing `trading_days` of averageChange% into one weekly-equivalent return."""
    recent = daily_rows[-trading_days:]
    if len(recent) < trading_days:
        return None
    factor = 1.0
    for r in recent:
        factor *= 1 + r["averageChange"] / 100
    return 100 * (factor - 1)


def _spy_weekly_return() -> float | None:
    from_date = (datetime.date.today() - datetime.timedelta(weeks=3)).isoformat()
    to_date = datetime.date.today().isoformat()
    spy_bars = to_weekly(fmp_client.get_historical_daily(config.BENCHMARK, from_date, to_date))
    if len(spy_bars) < 2:
        return None
    return 100 * (spy_bars[-1]["close"] / spy_bars[-2]["close"] - 1)


def rank_sectors() -> list[dict]:
    """Rank GICS sectors by trailing ~1-week performance relative to SPY, using FMP's
    sector-performance data (not per-ETF OHLC, which this FMP plan doesn't allow)."""
    from_date = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    to_date = datetime.date.today().isoformat()

    spy_return = _spy_weekly_return()

    ranked = []
    for gics_name, fmp_name in config.SECTORS.items():
        rows = fmp_client.get_historical_sector_performance(fmp_name, from_date, to_date)
        sector_return = _compound_return(rows)
        if sector_return is None or spy_return is None:
            continue
        ranked.append({
            "sector": gics_name,
            "weekly_return_pct": round(sector_return, 2),
            "relative_strength_pct": round(sector_return - spy_return, 2),
        })
    ranked.sort(key=lambda r: r["relative_strength_pct"], reverse=True)
    return ranked


def top_performing_sectors(top_n: int = config.TOP_N_SECTORS) -> list[dict]:
    return rank_sectors()[:top_n]
