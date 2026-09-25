import csv
import datetime
import io
import json
import os

import requests

import config


def _load_cache() -> list[dict] | None:
    if not os.path.exists(config.SP500_CACHE_PATH):
        return None
    with open(config.SP500_CACHE_PATH) as f:
        cached = json.load(f)
    fetched_at = datetime.date.fromisoformat(cached["fetched_at"])
    if (datetime.date.today() - fetched_at).days > config.SP500_CACHE_MAX_AGE_DAYS:
        return None
    return cached["constituents"]


def _save_cache(constituents: list[dict]) -> None:
    os.makedirs(os.path.dirname(config.SP500_CACHE_PATH), exist_ok=True)
    with open(config.SP500_CACHE_PATH, "w") as f:
        json.dump({"fetched_at": datetime.date.today().isoformat(), "constituents": constituents}, f)


def get_sp500_constituents() -> list[dict]:
    """[{symbol, sector}] — sector is the GICS sector name used as a key into config.SECTOR_ETFS."""
    cached = _load_cache()
    if cached is not None:
        return cached
    resp = requests.get(config.SP500_SOURCE_URL, timeout=30)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    constituents = [{"symbol": row["Symbol"].replace(".", "-"), "sector": row["GICS Sector"]} for row in reader]
    if not constituents:
        raise RuntimeError("S&P 500 constituent fetch returned no rows")
    _save_cache(constituents)
    return constituents


def get_universe(top_sectors: list[str]) -> list[dict]:
    """Stocks in the given GICS sectors, plus every sector ETF (so ETFs are always scanned too)."""
    constituents = get_sp500_constituents()
    symbols = [c for c in constituents if c["sector"] in top_sectors]
    for sector_name, etf in config.SECTOR_ETFS.items():
        symbols.append({"symbol": etf, "sector": sector_name})
    seen = set()
    deduped = []
    for s in symbols:
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            deduped.append(s)
    return deduped
