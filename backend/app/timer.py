# app/timer.py
import threading
import time
from app import db
from app.game import get_round_deadline, clear_round_deadline, _finish_round


def _loop():
    while True:
        try:
            now = time.time()
            # Завершение раундов по таймеру
            with db.db_session() as conn:
                rows = conn.execute(
                    "SELECT id, status FROM sessions WHERE status = 'active'"
                ).fetchall()
            for row in rows:
                deadline = get_round_deadline(row["id"])
                if deadline and now >= deadline:
                    clear_round_deadline(row["id"])
                    _finish_round(row["id"])
                    from app.ws import notify_sync
                    notify_sync(row["id"], "round_finished")

            # Очистка старых запросов на переговоры
            db.expire_old_talk_requests(60)
        except Exception:
            import traceback
            traceback.print_exc()
        time.sleep(2)


def start_timer():
    t = threading.Thread(target=_loop, daemon=True)
    t.start()