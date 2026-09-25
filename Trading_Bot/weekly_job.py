import datetime
import time

import config
import fmp_client
import notify
import sector_scan
import state_store
from darvas import compute_weekly_signals, spy_trend_up_asof, to_weekly
from universe import get_universe

REQUEST_PAUSE_SECONDS = 0.25


def _price_history_dates() -> tuple[str, str]:
    today = datetime.date.today()
    return (today - datetime.timedelta(days=365 * config.PRICE_HISTORY_YEARS)).isoformat(), today.isoformat()


def run() -> None:
    state_store.init_db()
    from_date, to_date = _price_history_dates()

    top_sectors = sector_scan.top_performing_sectors()
    top_sector_names = [s["sector"] for s in top_sectors]
    print(f"Top {len(top_sectors)} sectors: {top_sector_names}")

    spy_weekly = to_weekly(fmp_client.get_historical_daily(config.BENCHMARK, from_date, to_date))

    universe = get_universe(top_sector_names)
    print(f"Universe size: {len(universe)} symbols")

    newly_confirmed = []
    errors = []
    for entry in universe:
        symbol, sector = entry["symbol"], entry["sector"]
        try:
            daily_bars = fmp_client.get_historical_daily(symbol, from_date, to_date)
            weekly_bars = to_weekly(daily_bars)
            signals = compute_weekly_signals(weekly_bars)
            if not signals:
                continue
            latest = signals[-1]
            if not latest.breakout_raw:
                continue
            if not spy_trend_up_asof(spy_weekly, latest.week_start):
                continue
            state_store.upsert_eligible(
                symbol=symbol, sector=sector, top=latest.top, bottom=latest.bottom,
                stop=latest.stop, trigger=latest.trigger, confirmed_week=latest.week_start,
                updated_at=datetime.datetime.utcnow().isoformat(),
            )
            newly_confirmed.append({"symbol": symbol, "sector": sector, **latest.__dict__})
        except Exception as exc:  # keep scanning the rest of the universe on a single-symbol failure
            errors.append(f"{symbol}: {exc}")
        time.sleep(REQUEST_PAUSE_SECONDS)

    watchlist = state_store.list_eligible()
    _email_summary(top_sectors, newly_confirmed, watchlist, errors)


def _email_summary(top_sectors, newly_confirmed, watchlist, errors) -> None:
    rows = "".join(
        f"<tr><td>{s['sector']}</td><td>{s['weekly_return_pct']}%</td>"
        f"<td>{s['relative_strength_pct']}%</td></tr>"
        for s in top_sectors
    )
    confirmed_rows = "".join(
        f"<tr><td>{c['symbol']}</td><td>{c['sector']}</td><td>{c['close']:.2f}</td>"
        f"<td>{c['top']:.2f}</td><td>{c['bottom']:.2f}</td><td>{c['stop']:.2f}</td><td>{c['trigger']:.2f}</td></tr>"
        for c in newly_confirmed
    ) or "<tr><td colspan='7'>None this week</td></tr>"
    watchlist_rows = "".join(
        f"<tr><td>{w['symbol']}</td><td>{w['sector']}</td><td>{w['top']:.2f}</td>"
        f"<td>{w['trigger']:.2f}</td><td>{w['stop']:.2f}</td><td>{w['confirmed_week']}</td></tr>"
        for w in watchlist
    ) or "<tr><td colspan='6'>Empty</td></tr>"
    error_block = f"<p>{len(errors)} symbols failed to fetch: {', '.join(errors[:20])}</p>" if errors else ""

    html = f"""
    <h2>Weekly Sector &amp; Darvas Breakout Scan — {datetime.date.today().isoformat()}</h2>
    <h3>Top performing sectors (weekly relative strength vs SPY)</h3>
    <table border="1" cellpadding="4"><tr><th>Sector</th><th>Weekly Return</th><th>Rel. Strength</th></tr>
    {rows}</table>
    <h3>Newly confirmed weekly breakouts</h3>
    <table border="1" cellpadding="4"><tr><th>Symbol</th><th>Sector</th><th>Close</th><th>Top</th>
    <th>Bottom</th><th>Stop</th><th>Trigger</th></tr>{confirmed_rows}</table>
    <h3>Full eligible watchlist (carried forward, checked daily)</h3>
    <table border="1" cellpadding="4"><tr><th>Symbol</th><th>Sector</th><th>Top</th><th>Trigger</th>
    <th>Stop</th><th>Confirmed Week</th></tr>{watchlist_rows}</table>
    {error_block}
    <p>This is a scan result, not a trade recommendation or an executed order.</p>
    """
    notify.send_email(f"Weekly Darvas Sector Scan — {datetime.date.today().isoformat()}", html)


if __name__ == "__main__":
    run()
