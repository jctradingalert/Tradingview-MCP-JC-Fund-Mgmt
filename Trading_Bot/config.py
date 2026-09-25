import os

FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
FMP_BASE_URL = "https://financialmodelingprep.com/stable"

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "jctradingalert@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USER)
EMAIL_TO = os.environ.get("EMAIL_TO", "jctradingalert@gmail.com")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "data", "state.db"))

SP500_CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "sp500_constituents.json")
SP500_CACHE_MAX_AGE_DAYS = 30
SP500_SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"

# GICS sector name (as used by the S&P 500 constituent CSV) -> FMP's own sector
# taxonomy (as used by the historical-sector-performance endpoint). Sector ETF
# tickers (XLK, XLF, ...) are NOT used here: FMP's plan in use returns 402 for
# historical OHLC on sector ETFs, so ETFs are not scanned as Darvas candidates
# and sector strength is ranked from FMP's own sector-performance data instead.
SECTORS = {
    "Information Technology": "Technology",
    "Health Care": "Healthcare",
    "Financials": "Financial Services",
    "Consumer Discretionary": "Consumer Cyclical",
    "Consumer Staples": "Consumer Defensive",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Materials": "Basic Materials",
    "Real Estate": "Real Estate",
    "Utilities": "Utilities",
    "Communication Services": "Communication Services",
}
BENCHMARK = "SPY"
TOP_N_SECTORS = int(os.environ.get("TOP_N_SECTORS", "3"))

# Darvas Weekly Breakout and Daily Follow-Through parameters (mirrors the TradingView Pine script)
BOX_WEEKS = 6
TOUCH_TOLERANCE_PCT = 2.0
MIN_TOUCHES = 2
MAX_STOP_RISK_PCT = 20.0
MIN_RISE_PCT = 5.0
MAX_RISE_PCT = 20.0
MAX_UPPER_WICK_PCT = 50.0
ENTRY_TICKS = 1
STOP_TICKS = 1
MINTICK = 0.01  # approximation of syminfo.mintick for US equities/ETFs priced above $1

PRICE_HISTORY_YEARS = 3  # lookback pulled per symbol, enough for 26-week MACD warm-up
