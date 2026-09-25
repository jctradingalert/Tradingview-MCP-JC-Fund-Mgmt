import datetime

import config
import fmp_client
from darvas import to_weekly


def _weekly_return(weekly_bars: list[dict], lookback_weeks: int = 1) -> float | None:
    if len(weekly_bars) < lookback_weeks + 1:
        return None
    latest = weekly_bars[-1]["close"]
    prior = weekly_bars[-1 - lookback_weeks]["close"]
    return 100 * (latest / prior - 1)


def rank_sectors(lookback_weeks: int = 1) -> list[dict]:
    """Rank the 11 SPDR sector ETFs by weekly return relative to SPY. Highest relative strength first."""
    from_date = (datetime.date.today() - datetime.timedelta(weeks=lookback_weeks + 4)).isoformat()
    to_date = datetime.date.today().isoformat()

    spy_bars = to_weekly(fmp_client.get_historical_daily(config.BENCHMARK, from_date, to_date))
    spy_return = _weekly_return(spy_bars, lookback_weeks)

    ranked = []
    for sector_name, etf in config.SECTOR_ETFS.items():
        bars = to_weekly(fmp_client.get_historical_daily(etf, from_date, to_date))
        etf_return = _weekly_return(bars, lookback_weeks)
        if etf_return is None or spy_return is None:
            continue
        ranked.append({
            "sector": sector_name,
            "etf": etf,
            "weekly_return_pct": round(etf_return, 2),
            "relative_strength_pct": round(etf_return - spy_return, 2),
        })
    ranked.sort(key=lambda r: r["relative_strength_pct"], reverse=True)
    return ranked


def top_performing_sectors(top_n: int = config.TOP_N_SECTORS) -> list[dict]:
    return rank_sectors()[:top_n]
