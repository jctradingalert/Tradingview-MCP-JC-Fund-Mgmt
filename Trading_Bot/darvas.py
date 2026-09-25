import datetime
from dataclasses import dataclass

import config


def to_weekly(daily_bars: list[dict]) -> list[dict]:
    """daily_bars: ascending [{date: 'YYYY-MM-DD', open, high, low, close}, ...]."""
    weeks: dict[tuple, list[dict]] = {}
    for b in daily_bars:
        d = datetime.date.fromisoformat(b["date"])
        iso = d.isocalendar()
        weeks.setdefault((iso[0], iso[1]), []).append({**b, "date": d})
    out = []
    for key in sorted(weeks.keys()):
        wd = sorted(weeks[key], key=lambda x: x["date"])
        out.append({
            "start": wd[0]["date"],
            "end": wd[-1]["date"],
            "open": wd[0]["open"],
            "high": max(x["high"] for x in wd),
            "low": min(x["low"] for x in wd),
            "close": wd[-1]["close"],
        })
    return out


def ema_series(values: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    out = [0.0] * len(values)
    ema = values[0]
    out[0] = ema
    for i in range(1, len(values)):
        ema = values[i] * k + ema * (1 - k)
        out[i] = ema
    return out


@dataclass
class WeeklySignal:
    week_start: str
    week_end: str
    close: float
    top: float
    bottom: float
    stop: float
    trigger: float
    breakout_raw: bool
    stop_review: bool
    raised_stop: float | None


def compute_weekly_signals(weekly_bars: list[dict]) -> list[WeeklySignal]:
    """One WeeklySignal per week, starting once enough history exists for the box + MACD warm-up."""
    closes = [w["close"] for w in weekly_bars]
    if len(closes) < config.BOX_WEEKS + 10:
        return []
    ema20 = ema_series(closes, 20)
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    macd = [a - b for a, b in zip(ema12, ema26)]
    signal_line = ema_series(macd, 9)

    out = []
    n = len(weekly_bars)
    for w in range(config.BOX_WEEKS, n):
        box = weekly_bars[w - config.BOX_WEEKS:w]
        top = max(b["high"] for b in box)
        bottom = min(b["low"] for b in box)
        height = top - bottom
        top_touches = sum(1 for b in box if b["high"] >= top * (1 - config.TOUCH_TOLERANCE_PCT / 100))
        bottom_touches = sum(1 for b in box if b["low"] <= bottom * (1 + config.TOUCH_TOLERANCE_PCT / 100))
        box_ok = bottom > 0 and height > 0 and top_touches >= config.MIN_TOUCHES and bottom_touches >= config.MIN_TOUCHES

        cur = weekly_bars[w]
        prev_close = weekly_bars[w - 1]["close"] if w >= 1 else None
        gain = 100 * (cur["close"] / prev_close - 1) if prev_close else None
        upper_wick = (100 * (cur["high"] - max(cur["open"], cur["close"])) / (cur["high"] - cur["low"])
                      if cur["high"] != cur["low"] else None)
        stop = bottom + height / 3
        trigger = cur["close"] + config.ENTRY_TICKS * config.MINTICK
        risk = 100 * (trigger - stop) / trigger if trigger > 0 else None
        highest_close_prev9 = max((b["close"] for b in weekly_bars[max(0, w - 9):w]), default=None) if w >= 9 else None

        breakout = bool(
            box_ok and highest_close_prev9 is not None
            and cur["close"] > ema20[w] and macd[w] > signal_line[w]
            and cur["close"] > top and cur["close"] > highest_close_prev9
            and gain is not None and config.MIN_RISE_PCT < gain < config.MAX_RISE_PCT
            and upper_wick is not None and upper_wick <= config.MAX_UPPER_WICK_PCT
            and risk is not None and 0 < risk < config.MAX_STOP_RISK_PCT
        )
        stop_review = w >= 1 and macd[w - 1] >= signal_line[w - 1] and macd[w] < signal_line[w]
        raised_stop = (cur["low"] - config.STOP_TICKS * config.MINTICK) if stop_review else None

        out.append(WeeklySignal(
            week_start=cur["start"].isoformat(), week_end=cur["end"].isoformat(), close=cur["close"],
            top=top, bottom=bottom, stop=stop, trigger=trigger,
            breakout_raw=breakout, stop_review=stop_review, raised_stop=raised_stop,
        ))
    return out


def spy_trend_up_asof(spy_weekly_bars: list[dict], asof_week_end: str) -> bool | None:
    """SPY weekly EMA10 > EMA20 as of the completed SPY week ending on/just before asof_week_end."""
    closes = [w["close"] for w in spy_weekly_bars if w["end"].isoformat() <= asof_week_end]
    if len(closes) < 20:
        return None
    ema10 = ema_series(closes, 10)
    ema20 = ema_series(closes, 20)
    return ema10[-1] > ema20[-1]


def check_daily_followthrough(active_top: float, active_trigger: float, day: dict) -> dict:
    """day: {open, high, low, close} for one confirmed daily bar."""
    false_breakout = day["close"] <= active_top
    trigger_touched = day["high"] >= active_trigger and day["low"] <= active_trigger and day["close"] > active_top
    open_above = day["open"] >= active_trigger and day["close"] > active_top
    return {
        "false_breakout": false_breakout,
        "entry_review": (trigger_touched or open_above) and not false_breakout,
    }
