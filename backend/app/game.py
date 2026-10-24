# app/game.py
import time
from app import summary
from app import db
from app.config import (
    ROUND_DURATION_SEC, MIN_PLAYERS, MAX_MISSILES_PER_ROUND,
    COST_DEV, COST_SHIELD, COST_TECH, COST_MISSILES,
    DEV_GAIN, ANOMALY_ON_TECH, ANOMALY_ON_BUY, ANOMALY_ON_SEND,
    ANOMALY_ON_DROP, ANOMALY_LIMIT, SANCTION_PENALTY, SANCTION_PENALTY_MAX,
)

# session_id -> timestamp конца раунда
_round_deadlines: dict[int, float] = {}

# пауза
_paused_at: dict[int, float] = {}
_paused_remaining: dict[int, float] = {}


# ===========================================================================
#  СТАРТ ИГРЫ И РАУНДЫ
# ===========================================================================

def start_game(session_id: int):
    s = db.get_session(session_id)
    if not s or s["status"] != "lobby":
        raise ValueError("Игра не в лобби")
    players = db.get_players(session_id)
    if len(players) < MIN_PLAYERS:
        raise ValueError(f"Нужно минимум {MIN_PLAYERS} игроков")

    db.set_session_status(session_id, "active")
    db.set_session_round(session_id, 1)
    _begin_round(session_id)
    return {"ok": True, "round": 1}


def _begin_round(session_id: int):
    db.apply_pending(session_id)
    _round_deadlines[session_id] = time.time() + ROUND_DURATION_SEC
    with db.db_session() as conn:
        conn.execute("UPDATE players SET order_ready = 0 WHERE session_id = ?",
                     (session_id,))


def get_round_deadline(session_id: int) -> float | None:
    return _round_deadlines.get(session_id)


def clear_round_deadline(session_id: int):
    _round_deadlines.pop(session_id, None)


def pause_round(session_id: int) -> dict:
    s = db.get_session(session_id)
    if not s or s["status"] != "active":
        raise ValueError("Игра не активна")
    if session_id in _paused_at:
        return {"ok": True, "already_paused": True}
    deadline = _round_deadlines.get(session_id)
    if deadline is None:
        raise ValueError("Раунд не запущен")
    remaining = max(0.0, deadline - time.time())
    _paused_remaining[session_id] = remaining
    _paused_at[session_id] = time.time()
    _round_deadlines.pop(session_id, None)
    return {"ok": True, "remaining": int(remaining)}


def resume_round(session_id: int) -> dict:
    s = db.get_session(session_id)
    if not s or s["status"] != "active":
        raise ValueError("Игра не активна")
    if session_id not in _paused_at:
        return {"ok": True, "not_paused": True}
    remaining = _paused_remaining.pop(session_id, ROUND_DURATION_SEC)
    _paused_at.pop(session_id, None)
    _round_deadlines[session_id] = time.time() + remaining
    return {"ok": True, "remaining": int(remaining)}


def is_paused(session_id: int) -> bool:
    return session_id in _paused_at


# ===========================================================================
#  СОСТОЯНИЕ
# ===========================================================================

def player_state(player: dict) -> dict:
    s = db.get_session(player["session_id"])
    cities = db.get_cities(player["id"])
    orders_raw = db.get_orders(player["id"], s["current_round"])
    orders = [_enrich_order(o, s["id"]) for o in orders_raw]
    players = db.get_players(player["session_id"])
    others = [
        {"id": p["id"], "name": p["name"], "planet": p["planet"],
         "is_alive": bool(p["is_alive"])}
        for p in players if p["id"] != player["id"]
    ]
    sanctions_against_me = []
    with db.db_session() as conn:
        rows = conn.execute("""
            SELECT o.round, pf.planet AS from_planet
            FROM orders o
            JOIN players pf ON pf.id = o.player_id
            WHERE o.action_type = 'sanction'
              AND o.target_id = ?
              AND o.round = ?
        """, (player["id"], s["current_round"])).fetchall()
        for r in rows:
            sanctions_against_me.append({
                "from_planet": r["from_planet"],
                "round": r["round"],
            })
    return {
        "session": {
            "id": s["id"],
            "status": s["status"],
            "current_round": s["current_round"],
            "rounds_total": s["rounds_total"],
            "anomaly": s["anomaly"],
            "deadline": get_round_deadline(s["id"]),
            "paused": is_paused(s["id"]),
            # ---- ИЗМЕНЕНИЕ: last_summary и при finished ----
            "last_summary": {
                "round": s["current_round"],
                "html_url": f"/api/summary/{s['id']}/{s['current_round']}.html",
            } if s["status"] in ("discussion", "finished") else None,
            # ---- конец изменения ----
            "finished_reason": s.get("finished_reason"),
            "winner_planet": s.get("winner_planet"),
        },
        "player": {
            "id": player["id"],
            "name": player["name"],
            "planet": player["planet"],
            "money": player["money"],
            "missiles": player["missiles"],
            "tech_meteor": bool(player["tech_meteor"]),
            "pending_tech": bool(player["pending_tech"]),
            "pending_missiles": player["pending_missiles"],
            "pending_sanctions": player["pending_sanctions"],
            "order_ready": bool(player["order_ready"]),
            "is_alive": bool(player["is_alive"]),
        },
        "cities": cities,
        "orders": orders,
        "other_players": others,
        "sanctions_against_me": sanctions_against_me,
    }


def _enrich_order(o: dict, session_id: int) -> dict:
    """Добавляет target_name в order для отображения на фронте."""
    o = dict(o)
    o["target_name"] = None
    t = o["action_type"]
    if t == "dev" or t == "shield":
        c = db.get_city(o["target_id"])
        if c:
            o["target_name"] = c["name"]
    elif t == "meteor_city":
        c = db.get_city(o["target_id"])
        if c:
            owner = db.get_player(c["player_id"])
            o["target_name"] = f"{c['name']} ({owner['planet']})" if owner else c["name"]
    elif t == "sanction":
        p = db.get_player(o["target_id"])
        if p:
            o["target_name"] = p["planet"]
    return o


def public_state(session_id: int, viewer_player_id: int | None = None,
                 show_all_shields: bool = False,
                 include_winner: bool = False) -> dict:
    import json as _json
    s = db.get_session(session_id)
    players = db.get_players(session_id)
    ready_count = sum(1 for p in players if p["order_ready"])

    winners = []
    if include_winner and s["status"] == "finished":
        raw = s.get("winners")
        if raw:
            try:
                winners = _json.loads(raw)
            except Exception:
                winners = []
        if not winners and s.get("winner_planet"):
            winners = [s["winner_planet"]]

    return {
        "id": s["id"],
        "status": s["status"],
        "current_round": s["current_round"],
        "rounds_total": s["rounds_total"],
        "anomaly": s["anomaly"],
        "deadline": get_round_deadline(s["id"]),
        "paused": is_paused(s["id"]),
        "ready_count": ready_count,
        "players_count": len(players),
        # ---- ИЗМЕНЕНИЕ: last_summary и при finished ----
        "last_summary": {
            "round": s["current_round"],
            "html_url": f"/api/summary/{s['id']}/{s['current_round']}.html",
        } if s["status"] in ("discussion", "finished") else None,
        # ---- конец изменения ----
        "finished_reason": s.get("finished_reason") if include_winner else None,
        "winner_planet": (s.get("winner_planet") if include_winner else None),
        "winners": winners if include_winner else [],
        "players": [
            {"id": p["id"], "name": p["name"], "planet": p["planet"],
             "is_alive": bool(p["is_alive"]), "order_ready": bool(p["order_ready"]),
             "money": p["money"], "missiles": p["missiles"],
             "tech_meteor": bool(p["tech_meteor"]),
             "pending_tech": bool(p["pending_tech"]),
             "pending_missiles": p["pending_missiles"],
             "cities": [
                 {"id": c["id"], "name": c["name"],
                  "development": c["development"],
                  "life_level": c["life_level"],
                  "has_shield": bool(c["has_shield"])
                    if (show_all_shields or p["id"] == viewer_player_id)
                    else False,
                  "is_destroyed": bool(c["is_destroyed"])}
                 for c in db.get_cities(p["id"])
             ]}
            for p in players
        ],
    }


# ===========================================================================
#  ПРИКАЗЫ
# ===========================================================================

def _reserve_money(player_id: int, amount: int) -> dict:
    p = db.get_player(player_id)
    if p["money"] < amount:
        raise ValueError(f"Не хватает денег (нужно {amount}, у тебя {p['money']})")
    with db.db_session() as conn:
        conn.execute("UPDATE players SET money = money - ? WHERE id = ?",
                     (amount, player_id))
    return db.get_player(player_id)


def add_order(player_id: int, action: str, target_id: int | None = None) -> dict:
    player = db.get_player(player_id)
    s = db.get_session(player["session_id"])
    if s["status"] != "active":
        raise ValueError("Игра не активна")
    if player["order_ready"]:
        raise ValueError("Ты уже отправил приказ")
    rnd = s["current_round"]
    orders = db.get_orders(player_id, rnd)

    if action == "dev":
        if not target_id:
            raise ValueError("Не указан город")
        cities = db.get_cities(player_id)
        city = next((c for c in cities if c["id"] == target_id), None)
        if not city or city["is_destroyed"]:
            raise ValueError("Город недоступен")
        if any(o["action_type"] == "dev" and o["target_id"] == target_id for o in orders):
            raise ValueError("На этот город уже заказано развитие")
        _reserve_money(player_id, COST_DEV)
        db.add_order(player_id, rnd, "dev", target_id, COST_DEV)

    elif action == "shield":
        if s["current_round"] < 2:
            raise ValueError("Щиты доступны со 2 раунда")
        if not target_id:
            raise ValueError("Не указан город")
        cities = db.get_cities(player_id)
        city = next((c for c in cities if c["id"] == target_id), None)
        if not city or city["is_destroyed"]:
            raise ValueError("Город недоступен")
        if city["has_shield"]:
            raise ValueError("На городе уже есть щит")
        if any(o["action_type"] == "shield" and o["target_id"] == target_id for o in orders):
            raise ValueError("Щит на этот город уже заказан")
        _reserve_money(player_id, COST_SHIELD)
        db.add_order(player_id, rnd, "shield", target_id, COST_SHIELD)

    elif action == "tech":
        if player["tech_meteor"]:
            raise ValueError("Технология уже изучена")
        if player["pending_tech"]:
            raise ValueError("Технология уже заказана ранее (активируется в след. раунде)")
        if any(o["action_type"] == "tech" for o in orders):
            raise ValueError("Технология уже заказана")
        _reserve_money(player_id, COST_TECH)
        db.add_order(player_id, rnd, "tech", None, COST_TECH)

    elif action == "buy_missile":
        if not player["tech_meteor"]:
            raise ValueError("Сначала нужна технология метеоритов")
        bought = sum(1 for o in orders if o["action_type"] == "buy_missile")
        if bought >= MAX_MISSILES_PER_ROUND:
            raise ValueError(f"Не более {MAX_MISSILES_PER_ROUND} метеоритов за раунд")
        price = COST_MISSILES[bought]
        _reserve_money(player_id, price)
        db.add_order(player_id, rnd, "buy_missile", None, price)

    elif action == "meteor_city":
        if not player["tech_meteor"]:
            raise ValueError("Нужна технология")
        if not target_id:
            raise ValueError("Не указан город-цель")
        if any(o["action_type"] == "meteor_city" and o["target_id"] == target_id
               for o in orders):
            raise ValueError("В этот город уже летит твой метеорит")
        used = sum(1 for o in orders if o["action_type"] in ("meteor_city", "meteor_anomaly"))
        if used >= player["missiles"]:
            raise ValueError("Нет свободных метеоритов")
        db.add_order(player_id, rnd, "meteor_city", target_id, 0)

    elif action == "meteor_anomaly":
        if not player["tech_meteor"]:
            raise ValueError("Нужна технология")
        if any(o["action_type"] == "meteor_anomaly" for o in orders):
            raise ValueError("Ты уже отправил метеорит в аномалию в этом раунде")
        used = sum(1 for o in orders if o["action_type"] in ("meteor_city", "meteor_anomaly"))
        if used >= player["missiles"]:
            raise ValueError("Нет свободных метеоритов")
        db.add_order(player_id, rnd, "meteor_anomaly", None, 0)

    elif action == "sanction":
        if not target_id:
            raise ValueError("Не указана планета-цель")
        target = db.get_player(target_id)
        if not target or target["session_id"] != player["session_id"]:
            raise ValueError("Цель не найдена")
        if any(o["action_type"] == "sanction" and o["target_id"] == target_id
               for o in orders):
            raise ValueError("Санкции против этой планеты уже заказаны")
        db.add_order(player_id, rnd, "sanction", target_id, 0)

    else:
        raise ValueError("Неизвестное действие")

    return {"ok": True, "state": player_state(db.get_player(player_id))}


def remove_order(player_id: int, order_id: int) -> dict:
    player = db.get_player(player_id)
    s = db.get_session(player["session_id"])
    if s["status"] != "active" or player["order_ready"]:
        raise ValueError("Недоступно")
    rnd = s["current_round"]
    with db.db_session() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ? AND player_id = ? AND round = ?",
            (order_id, player_id, rnd)
        ).fetchone()
        if not row:
            raise ValueError("Заказ не найден")
        refund = row["cost"]
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        if refund:
            conn.execute("UPDATE players SET money = money + ? WHERE id = ?",
                         (refund, player_id))
    return {"ok": True, "refund": refund}


def clear_orders(player_id: int) -> dict:
    player = db.get_player(player_id)
    s = db.get_session(player["session_id"])
    if s["status"] != "active" or player["order_ready"]:
        raise ValueError("Недоступно")
    rnd = s["current_round"]
    orders = db.get_orders(player_id, rnd)
    refund = sum(o["cost"] for o in orders)
    if refund:
        with db.db_session() as conn:
            conn.execute("UPDATE players SET money = money + ? WHERE id = ?",
                         (refund, player_id))
    with db.db_session() as conn:
        conn.execute("DELETE FROM orders WHERE player_id = ? AND round = ?",
                     (player_id, rnd))
    return {"ok": True, "refund": refund}


def set_ready(player_id: int) -> dict:
    player = db.get_player(player_id)
    s = db.get_session(player["session_id"])
    if s["status"] != "active":
        raise ValueError("Игра не активна")
    if player["order_ready"]:
        return {"ok": True, "already": True}
    rnd = s["current_round"]
    orders = db.get_orders(player_id, rnd)
    if not orders:
        raise ValueError("Корзина пуста")
    with db.db_session() as conn:
        conn.execute("UPDATE players SET order_ready = 1 WHERE id = ?", (player_id,))
    
    # ✅ Убираем автозавершение раунда — раунд завершается только по таймеру или вручную админом
    # players = db.get_players(s["id"])
    # if all(p["order_ready"] for p in players):
    #     _finish_round(s["id"])
    
    return {"ok": True}


# ===========================================================================
#  ПЕРЕВОДЫ
# ===========================================================================

def transfer(from_id: int, to_id: int, amount: int) -> dict:
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    src = db.get_player(from_id)
    dst = db.get_player(to_id)
    if not src or not dst or src["session_id"] != dst["session_id"]:
        raise ValueError("Игрок не найден")
    if src["money"] < amount:
        raise ValueError("Не хватает денег")
    with db.db_session() as conn:
        conn.execute("UPDATE players SET money = money - ? WHERE id = ?",
                     (amount, from_id))
        conn.execute("UPDATE players SET money = money + ? WHERE id = ?",
                     (amount, to_id))
    return {"ok": True, "amount": amount, "to_planet": dst["planet"]}


# ===========================================================================
#  ПЕРЕГОВОРЫ
# ===========================================================================

def request_talk(from_id: int, to_id: int) -> dict:
    src = db.get_player(from_id)
    dst = db.get_player(to_id)
    if not src or not dst or src["session_id"] != dst["session_id"]:
        raise ValueError("Игрок не найден")
    if from_id == to_id:
        raise ValueError("Нельзя отправить запрос самому себе")
    req = db.create_talk_request(src["session_id"], from_id, to_id)
    return {
        "ok": True,
        "request_id": req["id"],
        "from_planet": src["planet"],
        "to_planet": dst["planet"],
    }


def respond_talk(player_id: int, request_id: int, accept: bool) -> dict:
    req = db.get_talk_request(request_id)
    if not req or req["to_player_id"] != player_id:
        raise ValueError("Запрос не найден")
    if req["status"] != "pending":
        raise ValueError("Запрос уже обработан")

    if accept:
        busy = db.get_receiving_talk(player_id)
        if busy:
            raise ValueError("Ты уже занят другим дипломатом")
        db.set_talk_status(request_id, "accepted")
        player = db.get_player(player_id)
        src = db.get_player(req["from_player_id"])
        return {
            "ok": True,
            "action": "accepted",
            "admin_hint": (f"Планета {src['planet']} отправила дипломата "
                           f"к планете {player['planet']}. Сопроводи дипломата."),
        }
    else:
        db.set_talk_status(request_id, "rejected")
        return {"ok": True, "action": "rejected"}


def mark_diplomat_arrived(session_id: int, request_id: int) -> dict:
    req = db.get_talk_request(request_id)
    if not req:
        raise ValueError("Запрос не найден")
    if req["session_id"] != session_id:
        raise ValueError("Запрос из другой сессии")
    if req["status"] != "accepted":
        raise ValueError("Запрос не в статусе 'accepted'")
    db.set_talk_status(request_id, "arrived")
    return {"ok": True}


def finish_talk(player_id: int, request_id: int) -> dict:
    req = db.get_talk_request(request_id)
    if not req or req["to_player_id"] != player_id:
        raise ValueError("Запрос не найден")
    if req["status"] != "arrived":
        raise ValueError("Переговоры ещё не начались")
    db.set_talk_status(request_id, "finished")
    player = db.get_player(player_id)
    src = db.get_player(req["from_player_id"])
    return {
        "ok": True,
        "admin_hint": (f"Планета {player['planet']} завершила переговоры. "
                       f"Сопроводи дипломата обратно на {src['planet']}."),
    }


def get_my_talks(player_id: int) -> dict:
    rows = db.get_talk_requests_for_player(player_id)
    incoming = []
    outgoing = []
    now = time.time()
    for r in rows:
        item = {
            "id": r["id"],
            "status": r["status"],
            "from_planet": r["from_planet"],
            "to_planet": r["to_planet"],
            "created_at": r["created_at"],
            "ttl_left": max(0, int(60 - (now - r["created_at"])))
                        if r["status"] == "pending" else 0,
        }
        if r["to_player_id"] == player_id:
            incoming.append(item)
        if r["from_player_id"] == player_id:
            outgoing.append(item)
    busy = db.get_receiving_talk(player_id)
    return {
        "incoming": incoming,
        "outgoing": outgoing,
        "busy_with": busy["id"] if busy else None,
    }


# ===========================================================================
#  ОБРАБОТКА КОНЦА РАУНДА
# ===========================================================================

def _finish_round(session_id: int):
    s = db.get_session(session_id)
    if not s or s["status"] != "active":
        return
    rnd = s["current_round"]
    players = db.get_players(session_id)
    all_orders = []
    for p in players:
        for o in db.get_orders(p["id"], rnd):
            all_orders.append((p["id"], o))

    with db.db_session() as conn:
        for p in players:
            cities = db.get_cities(p["id"])
            income = sum(c["life_level"] for c in cities if not c["is_destroyed"])
            n_san = p["pending_sanctions"]
            penalty = min(n_san * SANCTION_PENALTY, SANCTION_PENALTY_MAX)
            income = int(income * (1 - penalty))
            conn.execute("UPDATE players SET money = money + ? WHERE id = ?",
                         (income, p["id"]))
        conn.execute("UPDATE players SET pending_sanctions = 0 WHERE session_id = ?",
                     (session_id,))

    sanctions_this_round: dict[int, int] = {}
    for pid, o in all_orders:
        if o["action_type"] == "sanction":
            t = o["target_id"]
            sanctions_this_round[t] = sanctions_this_round.get(t, 0) + 1
    with db.db_session() as conn:
        for target_id, count in sanctions_this_round.items():
            conn.execute(
                "UPDATE players SET pending_sanctions = pending_sanctions + ? WHERE id = ?",
                (count, target_id)
            )

    with db.db_session() as conn:
        for pid, o in all_orders:
            if o["action_type"] == "dev":
                conn.execute(
                    "UPDATE cities SET development = development + ? WHERE id = ?",
                    (DEV_GAIN, o["target_id"])
                )
            elif o["action_type"] == "shield":
                conn.execute("UPDATE cities SET has_shield = 1 WHERE id = ?",
                             (o["target_id"],))

    with db.db_session() as conn:
        for pid, o in all_orders:
            if o["action_type"] == "tech":
                conn.execute("UPDATE players SET pending_tech = 1 WHERE id = ?", (pid,))
                conn.execute(
                    "UPDATE sessions SET anomaly = MAX(0, MIN(100, anomaly + ?)) WHERE id = ?",
                    (ANOMALY_ON_TECH, session_id)
                )
            elif o["action_type"] == "buy_missile":
                conn.execute(
                    "UPDATE players SET pending_missiles = pending_missiles + 1 WHERE id = ?",
                    (pid,)
                )
                conn.execute(
                    "UPDATE sessions SET anomaly = MAX(0, MIN(100, anomaly + ?)) WHERE id = ?",
                    (ANOMALY_ON_BUY, session_id)
                )

    missiles_to_city: dict[int, int] = {}
    for pid, o in all_orders:
        if o["action_type"] == "meteor_city":
            missiles_to_city[o["target_id"]] = missiles_to_city.get(o["target_id"], 0) + 1

    with db.db_session() as conn:
        for city_id, count in missiles_to_city.items():
            row = conn.execute("SELECT * FROM cities WHERE id = ?", (city_id,)).fetchone()
            if not row or row["is_destroyed"]:
                continue
            if count >= 2:
                conn.execute("""
                    UPDATE cities SET development = 0, life_level = 0,
                                      has_shield = 0, is_destroyed = 1
                    WHERE id = ?
                """, (city_id,))
            elif count == 1:
                if row["has_shield"]:
                    conn.execute("UPDATE cities SET has_shield = 0 WHERE id = ?",
                                 (city_id,))
                else:
                    conn.execute("""
                        UPDATE cities SET development = 0, life_level = 0,
                                          has_shield = 0, is_destroyed = 1
                        WHERE id = ?
                    """, (city_id,))
            conn.execute(
                "UPDATE sessions SET anomaly = MAX(0, MIN(100, anomaly + ?)) WHERE id = ?",
                (ANOMALY_ON_SEND * count, session_id)
            )

    dropped = 0
    for pid, o in all_orders:
        if o["action_type"] == "meteor_anomaly":
            dropped += 1
    if dropped:
        with db.db_session() as conn:
            conn.execute(
                "UPDATE sessions SET anomaly = MAX(0, MIN(100, anomaly + ?)) WHERE id = ?",
                (ANOMALY_ON_DROP * dropped + ANOMALY_ON_SEND * dropped, session_id)
            )

    with db.db_session() as conn:
        for p in players:
            used = sum(
                1 for pid, o in all_orders
                if pid == p["id"] and o["action_type"] in ("meteor_city", "meteor_anomaly")
            )
            if used:
                conn.execute(
                    "UPDATE players SET missiles = MAX(0, missiles - ?) WHERE id = ?",
                    (used, p["id"])
                )

    s = db.get_session(session_id)
    anomaly = s["anomaly"]
    with db.db_session() as conn:
        for p in players:
            for c in db.get_cities(p["id"]):
                if c["is_destroyed"]:
                    continue
                new_life = max(0, c["development"] - anomaly)
                conn.execute("UPDATE cities SET life_level = ? WHERE id = ?",
                             (new_life, c["id"]))

    with db.db_session() as conn:
        for p in players:
            cities = db.get_cities(p["id"])
            if cities and all(c["is_destroyed"] for c in cities):
                conn.execute("UPDATE players SET is_alive = 0 WHERE id = ?", (p["id"],))

    clear_round_deadline(session_id)
    _paused_at.pop(session_id, None)
    _paused_remaining.pop(session_id, None)

    # Закрываем все незавершённые переговоры этого раунда
    with db.db_session() as conn:
        conn.execute("""
            UPDATE talk_requests
            SET status = 'finished'
            WHERE session_id = ? AND status IN ('pending','accepted','arrived')
        """, (session_id,))

    s = db.get_session(session_id)

    # ---- ИЗМЕНЕНИЕ: генерируем сводку ДО проверки на конец игры ----
    try:
        summary.generate_both(session_id, s["current_round"])
    except Exception:
        import traceback
        traceback.print_exc()
    # ---- конец изменения ----

    if s["anomaly"] >= ANOMALY_LIMIT:
        _end_game(session_id, reason="anomaly")
        return
    if s["current_round"] >= s["rounds_total"]:
        _end_game(session_id, reason="rounds")
        return

    # --- Переход в фазу обсуждения ---
    db.set_session_status(session_id, "discussion")


def start_next_round(session_id: int) -> dict:
    s = db.get_session(session_id)
    if not s or s["status"] != "discussion":
        raise ValueError("Сейчас не фаза обсуждения")
    next_round = s["current_round"] + 1
    if next_round > s["rounds_total"]:
        raise ValueError("Раунды закончились")
    db.set_session_status(session_id, "active")
    db.set_session_round(session_id, next_round)
    _begin_round(session_id)
    return {"ok": True, "round": next_round}


def _end_game(session_id: int, reason: str):
    import json as _json
    db.set_session_status(session_id, "finished")
    players = db.get_players(session_id)

    winners: list[str] = []
    winner_planet = None

    if reason == "rounds":
        scores = []
        for p in players:
            cities = db.get_cities(p["id"])
            if not cities:
                avg = 0.0
            else:
                avg = sum(c["life_level"] for c in cities) / len(cities)
            scores.append((p["planet"], avg))

        if scores:
            best = max(s for _, s in scores)
            winners = [name for name, s in scores if abs(s - best) < 1e-9]
            winner_planet = winners[0] if len(winners) == 1 else None

    with db.db_session() as conn:
        conn.execute("""
            UPDATE sessions
            SET finished_reason = ?, winner_planet = ?, winners = ?
            WHERE id = ?
        """, (
            reason,
            winner_planet,
            _json.dumps(winners, ensure_ascii=False),
            session_id,
        ))


def end_round_manually(session_id: int):
    _finish_round(session_id)