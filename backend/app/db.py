# app/db.py
import sqlite3
import secrets
import time
from contextlib import contextmanager
from app.config import (
    DB_PATH, START_MONEY, START_DEV, START_LIFE, START_ANOMALY, CITY_NAMES
)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_session() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            join_code     TEXT    NOT NULL UNIQUE,
            admin_token   TEXT    NOT NULL UNIQUE,
            status        TEXT    NOT NULL DEFAULT 'lobby',
            rounds_total  INTEGER NOT NULL DEFAULT 6,
            current_round INTEGER NOT NULL DEFAULT 0,
            anomaly       INTEGER NOT NULL DEFAULT 5,
            created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS players (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    INTEGER NOT NULL,
            name          TEXT    NOT NULL,
            planet        TEXT    NOT NULL,
            token         TEXT    NOT NULL UNIQUE,
            money         INTEGER NOT NULL DEFAULT 1000,
            missiles      INTEGER NOT NULL DEFAULT 0,
            tech_meteor   INTEGER NOT NULL DEFAULT 0,
            order_ready   INTEGER NOT NULL DEFAULT 0,
            is_alive      INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS cities (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id     INTEGER NOT NULL,
            name          TEXT    NOT NULL,
            development   INTEGER NOT NULL DEFAULT 60,
            life_level    INTEGER NOT NULL DEFAULT 55,
            has_shield    INTEGER NOT NULL DEFAULT 0,
            is_destroyed  INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id     INTEGER NOT NULL,
            round         INTEGER NOT NULL,
            action_type   TEXT    NOT NULL,
            target_id     INTEGER,
            cost          INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS talk_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL,
            from_player_id  INTEGER NOT NULL,
            to_player_id    INTEGER NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'pending',
            created_at      REAL    NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (from_player_id) REFERENCES players(id),
            FOREIGN KEY (to_player_id) REFERENCES players(id)
        );
        """)
    migrate()


# ---------- Миграция ----------

def migrate():
    """Добавляет новые колонки в существующие таблицы, если их нет."""
    with db_session() as conn:
        cols_players = {r["name"] for r in conn.execute("PRAGMA table_info(players)").fetchall()}
        for col, ddl in [
            ("pending_tech", "INTEGER NOT NULL DEFAULT 0"),
            ("pending_missiles", "INTEGER NOT NULL DEFAULT 0"),
            ("pending_sanctions", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if col not in cols_players:
                conn.execute(f"ALTER TABLE players ADD COLUMN {col} {ddl}")

        cols_sessions = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        for col, ddl in [
            ("finished_reason", "TEXT"),
            ("winner_planet", "TEXT"),
            ("winners", "TEXT"),
        ]:
            if col not in cols_sessions:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {ddl}")


# ---------- Pending → Active ----------

def apply_pending(session_id: int):
    with db_session() as conn:
        conn.execute("""
            UPDATE players
            SET tech_meteor = 1, pending_tech = 0
            WHERE session_id = ? AND pending_tech = 1
        """, (session_id,))
        conn.execute("""
            UPDATE players
            SET missiles = missiles + pending_missiles, pending_missiles = 0
            WHERE session_id = ? AND pending_missiles > 0
        """, (session_id,))


# ---------- Sessions ----------

def gen_code(n: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(n))


def gen_token() -> str:
    return secrets.token_urlsafe(32)


def create_session(rounds_total: int) -> dict:
    with db_session() as conn:
        while True:
            code = gen_code()
            exists = conn.execute(
                "SELECT 1 FROM sessions WHERE join_code = ?", (code,)
            ).fetchone()
            if not exists:
                break
        token = gen_token()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sessions (join_code, admin_token, rounds_total, anomaly)
            VALUES (?, ?, ?, ?)
        """, (code, token, rounds_total, START_ANOMALY))
        sid = cur.lastrowid
        return {"id": sid, "join_code": code, "admin_token": token}


def get_session(session_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None


def get_session_by_code(code: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE join_code = ?", (code,)).fetchone()
        return dict(row) if row else None


def get_session_by_admin_token(token: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE admin_token = ?", (token,)).fetchone()
        return dict(row) if row else None


def set_session_status(session_id: int, status: str):
    with db_session() as conn:
        conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))


def set_session_round(session_id: int, rnd: int):
    with db_session() as conn:
        conn.execute("UPDATE sessions SET current_round = ? WHERE id = ?", (rnd, session_id))


def update_anomaly(session_id: int, delta: int):
    with db_session() as conn:
        conn.execute("""
            UPDATE sessions
            SET anomaly = MAX(0, MIN(100, anomaly + ?))
            WHERE id = ?
        """, (delta, session_id))


# ---------- Players ----------

def get_players(session_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM players WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_player_by_token(token: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM players WHERE token = ?", (token,)).fetchone()
        return dict(row) if row else None


def get_player(player_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
        return dict(row) if row else None

def get_city(city_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM cities WHERE id = ?", (city_id,)).fetchone()
        return dict(row) if row else None


def get_taken_planets(session_id: int) -> set[str]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT planet FROM players WHERE session_id = ?", (session_id,)
        ).fetchall()
        return {r["planet"] for r in rows}


def add_player(session_id: int, name: str, planet: str) -> dict:
    token = gen_token()
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO players (session_id, name, planet, token, money)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, name, planet, token, START_MONEY))
        pid = cur.lastrowid
        for city_name in CITY_NAMES.get(planet, ["Город1", "Город2", "Город3", "Город4"]):
            cur.execute("""
                INSERT INTO cities (player_id, name, development, life_level)
                VALUES (?, ?, ?, ?)
            """, (pid, city_name, START_DEV, START_LIFE))
    return {"id": pid, "token": token, "planet": planet}


# ---------- Cities ----------

def get_cities(player_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM cities WHERE player_id = ? ORDER BY id", (player_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- Orders ----------

def add_order(player_id: int, round_num: int, action_type: str,
              target_id: int | None, cost: int) -> int:
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO orders (player_id, round, action_type, target_id, cost)
            VALUES (?, ?, ?, ?, ?)
        """, (player_id, round_num, action_type, target_id, cost))
        return cur.lastrowid


def get_orders(player_id: int, round_num: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE player_id = ? AND round = ? ORDER BY id",
            (player_id, round_num)
        ).fetchall()
        return [dict(r) for r in rows]


def clear_orders(player_id: int, round_num: int):
    with db_session() as conn:
        conn.execute("DELETE FROM orders WHERE player_id = ? AND round = ?",
                     (player_id, round_num))


# ---------- Talk requests ----------

def create_talk_request(session_id: int, from_id: int, to_id: int) -> dict:
    with db_session() as conn:
        existing = conn.execute("""
            SELECT * FROM talk_requests
            WHERE session_id = ? AND status IN ('pending','accepted','arrived')
              AND ((from_player_id = ? AND to_player_id = ?) OR
                   (from_player_id = ? AND to_player_id = ?))
        """, (session_id, from_id, to_id, to_id, from_id)).fetchone()
        if existing:
            raise ValueError("Между вами уже есть активный запрос")
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO talk_requests (session_id, from_player_id, to_player_id, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        """, (session_id, from_id, to_id, time.time()))
        rid = cur.lastrowid
        row = conn.execute("SELECT * FROM talk_requests WHERE id = ?", (rid,)).fetchone()
        return dict(row)


def get_talk_request(rid: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM talk_requests WHERE id = ?", (rid,)).fetchone()
        return dict(row) if row else None


def get_talk_requests_for_player(player_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute("""
            SELECT tr.*,
                   pf.planet AS from_planet, pt.planet AS to_planet
            FROM talk_requests tr
            JOIN players pf ON pf.id = tr.from_player_id
            JOIN players pt ON pt.id = tr.to_player_id
            WHERE (tr.from_player_id = ? OR tr.to_player_id = ?)
              AND tr.status IN ('pending','accepted','arrived')
            ORDER BY tr.created_at
        """, (player_id, player_id)).fetchall()
        return [dict(r) for r in rows]


def get_talk_requests_for_session(session_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute("""
            SELECT tr.*,
                   pf.planet AS from_planet, pt.planet AS to_planet
            FROM talk_requests tr
            JOIN players pf ON pf.id = tr.from_player_id
            JOIN players pt ON pt.id = tr.to_player_id
            WHERE tr.session_id = ?
            ORDER BY tr.created_at
        """, (session_id,)).fetchall()
        return [dict(r) for r in rows]


def set_talk_status(rid: int, status: str):
    with db_session() as conn:
        conn.execute("UPDATE talk_requests SET status = ? WHERE id = ?", (status, rid))


def get_receiving_talk(player_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("""
            SELECT * FROM talk_requests
            WHERE to_player_id = ? AND status IN ('accepted','arrived')
            LIMIT 1
        """, (player_id,)).fetchone()
        return dict(row) if row else None


def expire_old_talk_requests(timeout_sec: int = 60):
    with db_session() as conn:
        conn.execute("""
            UPDATE talk_requests
            SET status = 'expired'
            WHERE status = 'pending' AND (? - created_at) > ?
        """, (time.time(), timeout_sec))