import datetime
import time

import fmp_client
import notify
import state_store
from darvas import check_daily_followthrough

REQUEST_PAUSE_SECONDS = 0.25


def run() -> None:
    """Assumes this runs every trading day after the close; checks only the latest daily bar
    against each watchlist symbol's box levels. A missed run means that day's action is skipped."""
    state_store.init_db()
    watchlist = state_store.list_eligible()
    if not watchlist:
        print("Watchlist is empty, nothing to check today.")
        return

    today = datetime.date.today()
    from_date = (today - datetime.timedelta(days=10)).isoformat()
    to_date = today.isoformat()

    entry_reviews, false_breakouts, errors = [], [], []
    for w in watchlist:
        symbol = w["symbol"]
        try:
            bars = fmp_client.get_historical_daily(symbol, from_date, to_date)
            if not bars:
                continue
            latest_day = bars[-1]
            result = check_daily_followthrough(w["top"], w["trigger"], latest_day)
            if result["false_breakout"]:
                state_store.remove_eligible(symbol)
                false_breakouts.append({"symbol": symbol, "sector": w["sector"], "close": latest_day["close"],
                                         "top": w["top"], "date": latest_day["date"]})
            elif result["entry_review"]:
                entry_reviews.append({"symbol": symbol, "sector": w["sector"], "close": latest_day["close"],
                                       "trigger": w["trigger"], "stop": w["stop"], "date": latest_day["date"]})
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
        time.sleep(REQUEST_PAUSE_SECONDS)

    _email_summary(entry_reviews, false_breakouts, errors)


def _email_summary(entry_reviews, false_breakouts, errors) -> None:
    if not entry_reviews and not false_breakouts and not errors:
        print("No daily follow-through events today; skipping email.")
        return

    entry_rows = "".join(
        f"<tr><td>{e['symbol']}</td><td>{e['sector']}</td><td>{e['date']}</td><td>{e['close']:.2f}</td>"
        f"<td>{e['trigger']:.2f}</td><td>{e['stop']:.2f}</td></tr>"
        for e in entry_reviews
    ) or "<tr><td colspan='6'>None today</td></tr>"
    false_rows = "".join(
        f"<tr><td>{f['symbol']}</td><td>{f['sector']}</td><td>{f['date']}</td>"
        f"<td>{f['close']:.2f}</td><td>{f['top']:.2f}</td></tr>"
        for f in false_breakouts
    ) or "<tr><td colspan='5'>None today</td></tr>"
    error_block = f"<p>{len(errors)} symbols failed to fetch: {', '.join(errors[:20])}</p>" if errors else ""

    html = f"""
    <h2>Daily Darvas Follow-Through — {datetime.date.today().isoformat()}</h2>
    <h3>Entry Level Review (still eligible, price touched the buffered trigger today)</h3>
    <table border="1" cellpadding="4"><tr><th>Symbol</th><th>Sector</th><th>Date</th><th>Close</th>
    <th>Trigger</th><th>Stop</th></tr>{entry_rows}</table>
    <h3>False Breakouts today (removed from watchlist)</h3>
    <table border="1" cellpadding="4"><tr><th>Symbol</th><th>Sector</th><th>Date</th>
    <th>Close</th><th>Box Top</th></tr>{false_rows}</table>
    {error_block}
    <p>This is a scan result, not a trade recommendation or an executed order.</p>
    """
    notify.send_email(f"Daily Darvas Entry Review — {datetime.date.today().isoformat()}", html)


if __name__ == "__main__":
    run()
