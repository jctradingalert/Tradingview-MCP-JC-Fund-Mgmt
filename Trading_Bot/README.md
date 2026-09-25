# Darvas Weekly Sector Scanner

Replicates the TradingView "Darvas Weekly Breakout and Daily Follow-Through"
Pine script (box construction, MACD/EMA filters, SPY market-trend gate, daily
false-breakout and entry-review checks) as a standalone scanner over the S&P
500, since TradingView's own Pine Screener has no API and can't be run on a
schedule unattended.

**Stocks only, not ETFs.** Sector ETFs (XLK, XLF, ...) are used only to rank
which sectors are performing (via FMP's sector-performance data), not as
direct Darvas scan candidates — this FMP plan returns `402` on historical
OHLC requests for sector ETFs (confirmed for XLK and XLF), so their own price
history isn't fetchable here. Some individual stocks are also gated the same
way on a per-symbol basis (e.g. `ACN` returns the same 402, while `AAPL`,
`MSFT`, `AMD` etc. work fine) — `weekly_job.py` catches this per symbol and
logs it in the run's error list rather than failing the whole scan.

It is a **scanner and email alerter only** — it never places trades. Every
email ends with a reminder of that; treat its output as a shortlist to review
yourself.

## What runs when

1. **`weekly_job.py`** (run once a week, e.g. Sunday evening)
   - Ranks the 11 GICS sectors by trailing weekly performance relative to SPY,
     using FMP's `historical-sector-performance` endpoint, and takes the top
     `TOP_N_SECTORS` (default 3).
   - Builds the scan universe: S&P 500 constituents in those sectors.
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
   - `FMP_API_KEY` — your Financial Modeling Prep key. Only two `stable`
     endpoints are used: `historical-price-eod/full` (per-stock OHLC) and
     `historical-sector-performance` (sector ranking) — both work on FMP's
     lower tiers. This project does **not** use FMP's `indexes` or `directory`
     endpoints (they require a Premium+ plan) — the S&P 500 constituent list
     instead comes from the public
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
the container, in the shared Postgres database.

**Already provisioned** (in the "Tradingview MCP JC Fund Mgmt" Railway
project, alongside the unrelated existing MCP service — untouched by any of
this):
- A **Postgres** service, providing `DATABASE_URL`.
- **`trading-bot-weekly`** and **`trading-bot-daily`** services, each with
  `FMP_API_KEY`, `SMTP_*`, `EMAIL_*`, `TOP_N_SECTORS`, and `DATABASE_URL`
  (referencing `${{Postgres.DATABASE_URL}}`) already set.
- Code deployed to both via `railway up Trading_Bot --path-as-root -s <service>`
  (not GitHub-integrated — redeploying after a code change means re-running
  that command, it won't happen automatically on `git push`).

**Still required — dashboard-only, the CLI cannot set these two fields:**
for each of `trading-bot-weekly` and `trading-bot-daily`, in Railway's
dashboard under Settings:
- **Weekly scan**: Cron Schedule `0 22 * * 0` (Sunday 10pm UTC ≈ Sunday
  evening ET).
- **Daily follow-through**: Cron Schedule `15 21 * * 1-5` (9:15pm UTC ≈
  shortly after the 4pm ET close on weekdays).

**Important — do not redeploy via `railway up` until Cron Schedule is set.**
The start command is already baked into each deploy via `railpack.json`
(Railpack's own config file — `railway.json`'s `deploy.startCommand` and
`deploy.cronSchedule` were tried first and silently did **not** take effect
through a CLI `up` deploy, confirmed by testing), but without a Cron Schedule
set on the service itself, a fresh deploy **runs the job immediately** instead
of waiting for the schedule. That's exactly what happened during initial
setup — `trading-bot-weekly` executed on deploy, hit an FMP `402` on the old
ETF-based sector ranking, and crash-looped until Railway's retry cap stopped
it (no email was sent, minimal API usage — this is what led to dropping ETFs
as scan candidates, see above). Set the Cron Schedule first, *then* deploy.

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
- A subset of individual symbols return `402` from FMP regardless of
  ETF/stock status (e.g. `ACN`) — these are skipped and reported in the run's
  error list rather than scanned, so the universe scanned each week is
  whatever your FMP plan actually allows, not literally every constituent.
