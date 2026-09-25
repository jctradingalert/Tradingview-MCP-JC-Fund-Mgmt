import os
import sqlite3
from contextlib import contextmanager

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS eligible_watchlist (
    symbol TEXT PRIMARY KEY,
    sector TEXT,
    box_top REAL,
    box_bottom REAL,
    box_stop REAL,
    box_trigger REAL,
    confirmed_week TEXT,
    updated_at TEXT
)
"""


def _use_postgres() -> bool:
    return bool(config.DATABASE_URL)


@contextmanager
def _connection():
    if _use_postgres():
        import psycopg2
        conn = psycopg2.connect(config.DATABASE_URL)
        try:
            yield conn, "%s"
        finally:
            conn.close()
    else:
        os.makedirs(os.path.dirname(config.SQLITE_PATH), exist_ok=True)
        conn = sqlite3.connect(config.SQLITE_PATH)
        try:
            yield conn, "?"
        finally:
            conn.close()


def init_db() -> None:
    with _connection() as (conn, _):
        cur = conn.cursor()
        cur.execute(_SCHEMA)
        conn.commit()


def upsert_eligible(symbol: str, sector: str, top: float, bottom: float, stop: float,
                     trigger: float, confirmed_week: str, updated_at: str) -> None:
    with _connection() as (conn, ph):
        cur = conn.cursor()
        if _use_postgres():
            cur.execute(
                f"""INSERT INTO eligible_watchlist
                    (symbol, sector, box_top, box_bottom, box_stop, box_trigger, confirmed_week, updated_at)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    ON CONFLICT (symbol) DO UPDATE SET
                    sector=EXCLUDED.sector, box_top=EXCLUDED.box_top, box_bottom=EXCLUDED.box_bottom,
                    box_stop=EXCLUDED.box_stop, box_trigger=EXCLUDED.box_trigger,
                    confirmed_week=EXCLUDED.confirmed_week, updated_at=EXCLUDED.updated_at""",
                (symbol, sector, top, bottom, stop, trigger, confirmed_week, updated_at),
            )
        else:
            cur.execute(
                f"""INSERT OR REPLACE INTO eligible_watchlist
                    (symbol, sector, box_top, box_bottom, box_stop, box_trigger, confirmed_week, updated_at)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
                (symbol, sector, top, bottom, stop, trigger, confirmed_week, updated_at),
            )
        conn.commit()


def remove_eligible(symbol: str) -> None:
    with _connection() as (conn, ph):
        cur = conn.cursor()
        cur.execute(f"DELETE FROM eligible_watchlist WHERE symbol = {ph}", (symbol,))
        conn.commit()


def list_eligible() -> list[dict]:
    with _connection() as (conn, _):
        cur = conn.cursor()
        cur.execute("SELECT symbol, sector, box_top, box_bottom, box_stop, box_trigger, confirmed_week, updated_at "
                    "FROM eligible_watchlist")
        rows = cur.fetchall()
    return [
        {
            "symbol": r[0], "sector": r[1], "top": r[2], "bottom": r[3],
            "stop": r[4], "trigger": r[5], "confirmed_week": r[6], "updated_at": r[7],
        }
        for r in rows
    ]
