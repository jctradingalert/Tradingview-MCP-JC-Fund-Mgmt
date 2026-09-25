import requests

import config


class FMPError(RuntimeError):
    pass


def get_historical_daily(symbol: str, from_date: str, to_date: str) -> list[dict]:
    """Ascending list of {date, open, high, low, close, volume} for one symbol."""
    if not config.FMP_API_KEY:
        raise FMPError("FMP_API_KEY is not set")
    resp = requests.get(
        f"{config.FMP_BASE_URL}/historical-price-eod/full",
        params={"symbol": symbol, "from": from_date, "to": to_date, "apikey": config.FMP_API_KEY},
        timeout=30,
    )
    if resp.status_code != 200:
        raise FMPError(f"FMP request failed for {symbol}: {resp.status_code} {resp.text[:200]}")
    bars = resp.json()
    if not isinstance(bars, list):
        raise FMPError(f"Unexpected FMP response for {symbol}: {bars}")
    bars.sort(key=lambda b: b["date"])
    return bars
