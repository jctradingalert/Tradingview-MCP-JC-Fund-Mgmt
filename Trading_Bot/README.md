# Darvas Weekly Sector Scanner

Replicates the TradingView "Darvas Weekly Breakout and Daily Follow-Through"
Pine script (box construction, MACD/EMA filters, SPY market-trend gate, daily
false-breakout and entry-review checks) as a standalone scanner over the S&P
500 plus the 11 SPDR sector ETFs, since TradingView's own Pine Screener has no
API and can't be run on a schedule unattended.

It is a **scanner and email alerter only** — it never places trades. Every
email ends with a reminder of that; treat its output as a shortlist to review
yourself.

## What runs when

1. **`weekly_job.py`** (run once a week, e.g. Sunday evening)
   - Ranks the 11 sector ETFs by weekly return relative to SPY, takes the top
     `TOP_N_SECTORS` (default 3).
   - Builds the scan universe: S&P 500 constituents in those sectors, plus all
     11 sector ETFs (always included as candidates in their own right).
   - Runs the weekly Darvas breakout test (6-week box, touch counts, MACD,
     20-EMA, gain/wick/risk filters, SPY trend gate) on each symbol.
   - Symbols with a confirmed breakout are saved to the `eligible_watchlist`
     table for the daily job to track.
   - Emails a summary: top sectors, newly confirmed breakouts, and the full
     running watchlist.

2. **`daily_job.py`** (run every trading day after the close)
   - Pulls the latest daily bar for every symbol currently on the watchlist.
   - Flags **Entry Level Review** (price touched the buffered breakout
     trigger today) or **False Breakout** (closed back at/below box
     resistance — removed from the watchlist).
   - Emails only when there's something to report.

This mirrors the original Pine script's split: the box/breakout/MACD logic
only changes once a week, the false-breakout/entry-review checks change daily.

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in:
   - `FMP_API_KEY` — your Financial Modeling Prep key. Only the
     `historical-price-eod/full` (`stable`) endpoint is used, which works on
     FMP's lower tiers — this project does **not** use FMP's `indexes` or
     `directory` endpoints (they require a Premium+ plan). The S&P 500
     constituent list instead comes from the public
     [datasets/s-and-p-500-companies](https://github.com/datasets/s-and-p-500-companies)
     CSV, cached locally for 30 days in `data/sp500_constituents.json`.
   - `SMTP_USER` / `SMTP_PASS` — sends from `jctradingalert@gmail.com` via
     Gmail SMTP. `SMTP_PASS` must be a 16-character
     [Gmail App Password](https://myaccount.google.com/apppasswords) (requires
     2FA enabled on the account), not its regular login password.
   - `EMAIL_TO` — defaults to `jctradingalert@gmail.com` (self-send to a
     dedicated alerts inbox). Change it if you'd rather alerts land in a
     different inbox.
   - `DATABASE_URL` — leave blank for local testing (falls back to a SQLite
     file). **Required in production on Railway** — see below.

3. Test locally:
   ```bash
   python weekly_job.py
   python daily_job.py
   ```

## Deploying on Railway

Railway cron jobs run in a fresh, ephemeral container each time — nothing
written to the local filesystem survives between runs. The watchlist that
`weekly_job.py` builds and `daily_job.py` reads must therefore live outside
the container:

1. Add Railway's **Postgres** plugin to this project. It injects
   `DATABASE_URL` automatically — copy that value into this service's env
   vars (or reference it directly if Railway lets you share it across
   services).
2. Create two Railway services from this `Trading_Bot/` directory (or one
   service with two Cron Job schedules, if your plan supports that):
   - **Weekly scan**: cron schedule `0 22 * * 0` (Sunday 10pm UTC ≈ Sunday
     evening ET), start command `python weekly_job.py`.
   - **Daily follow-through**: cron schedule `15 21 * * 1-5` (9:15pm UTC ≈
     shortly after the 4pm ET close on weekdays), start command
     `python daily_job.py`.
3. Set the same env vars from `.env.example` on both services.

## Known simplifications vs. the live Pine script

- `daily_job.py` only checks the **most recent** daily bar per symbol. It
  assumes the job runs every trading day without gaps — if a run is missed,
  that day's false-breakout/entry-review event is skipped rather than
  replayed.
- Tick size is approximated as `$0.01` for all symbols (`config.MINTICK`),
  matching the Pine script's `syminfo.mintick` closely enough for US equities
  and ETFs priced above $1.
- The S&P 500 constituent list is a public GitHub CSV, refreshed at most
  every 30 days — it will lag official index changes by up to that long.
- Sector ETF selection uses the standard 11 SPDR sector ETFs, mapped from
  each stock's GICS sector in that CSV.
