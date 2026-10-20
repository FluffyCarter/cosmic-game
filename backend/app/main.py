# app/main.py
import asyncio

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import db, game, ws
from app.config import (
    CORS_ORIGINS, MAX_SESSIONS, MAX_PLAYERS, PLANETS,
)
from app.models import (
    CreateSessionRequest, CreateSessionResponse,
    JoinRequest, JoinResponse,
    SessionPublic, PlayerPublic,
    OrderRequest, PayRequest, TalkRequest,
)
from app.auth import (
    get_player_from_header, get_admin_session_from_header,
)
from app.timer import start_timer

app = FastAPI(title="Cosmic Domination API")

from fastapi.staticfiles import StaticFiles
from app.config import STATIC_DIR
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    db.init_db()
    start_timer()
    ws.manager.set_main_loop(asyncio.get_running_loop())


@app.get("/api/health")
def health():
    return {"ok": True}


# ===========================================================================
#  АДМИН
# ===========================================================================

@app.post("/api/sessions", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest):
    with db.db_session() as conn:
        open_count = conn.execute(
            "SELECT COUNT(*) AS c FROM sessions WHERE status != 'finished'"
        ).fetchone()["c"]
    if open_count >= MAX_SESSIONS:
        raise HTTPException(400, f"Уже открыто {MAX_SESSIONS} сессий")
    s = db.create_session(req.rounds_total)
    return CreateSessionResponse(
        session_id=s["id"],
        join_code=s["join_code"],
        admin_token=s["admin_token"],
    )


@app.get("/api/admin/session", response_model=SessionPublic)
def admin_session(session: dict = Depends(get_admin_session_from_header)):
    players = db.get_players(session["id"])
    pub = game.public_state(session["id"], show_all_shields=True)
    return SessionPublic(
        id=session["id"],
        status=session["status"],
        current_round=session["current_round"],
        rounds_total=session["rounds_total"],
        anomaly=session["anomaly"],
        paused=game.is_paused(session["id"]),
        deadline=pub["deadline"],
        last_summary=game.public_state(session["id"], show_all_shields=True).get("last_summary"),
        players=[
            PlayerPublic(
                id=p["id"], name=p["name"], planet=p["planet"],
                is_alive=bool(p["is_alive"]),
                order_ready=bool(p["order_ready"]),
            )
            for p in players
        ],
    )


@app.post("/api/admin/start")
def admin_start(session: dict = Depends(get_admin_session_from_header)):
    try:
        r = game.start_game(session["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(session["id"], "game_started")
    return r


@app.post("/api/admin/end-round")
def admin_end_round(session: dict = Depends(get_admin_session_from_header)):
    game.end_round_manually(session["id"])
    ws.notify_sync(session["id"], "round_finished")
    return {"ok": True}

@app.post("/api/admin/pause")
def admin_pause(session: dict = Depends(get_admin_session_from_header)):
    try:
        r = game.pause_round(session["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(session["id"], "round_paused")
    return r


@app.post("/api/admin/resume")
def admin_resume(session: dict = Depends(get_admin_session_from_header)):
    try:
        r = game.resume_round(session["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(session["id"], "round_resumed")
    return r


# ===========================================================================
#  ИГРОК
# ===========================================================================

@app.post("/api/sessions/join", response_model=JoinResponse)
def join_session(req: JoinRequest):
    session = db.get_session_by_code(req.join_code)
    if not session:
        raise HTTPException(404, "Комната с таким кодом не найдена")
    if session["status"] != "lobby":
        raise HTTPException(400, "Игра уже началась")

    players = db.get_players(session["id"])
    if len(players) >= MAX_PLAYERS:
        raise HTTPException(400, "В комнате уже максимум игроков")

    taken = db.get_taken_planets(session["id"])
    free = [p for p in PLANETS if p not in taken]
    if not free:
        raise HTTPException(400, "Свободных планет нет")
    planet = free[0]

    player = db.add_player(session["id"], req.name, planet)
    ws.notify_sync(session["id"], "player_joined",
                   {"player_id": player["id"], "planet": planet})
    return JoinResponse(
        player_id=player["id"],
        planet=player["planet"],
        player_token=player["token"],
        session_id=session["id"],
    )


@app.get("/api/me")
def me(player: dict = Depends(get_player_from_header)):
    cities = db.get_cities(player["id"])
    return {
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
        "cities": cities,
    }


@app.post("/api/admin/next-round")
def admin_next_round(session: dict = Depends(get_admin_session_from_header)):
    try:
        r = game.start_next_round(session["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(session["id"], "round_started", {"round": r["round"]})
    return r

@app.get("/api/session/state")
def player_state_endpoint(player: dict = Depends(get_player_from_header)):
    return game.player_state(player)


@app.get("/api/session/public")
def session_public(session_id: int, token: str | None = None):
    viewer_id = None
    if token:
        p = db.get_player_by_token(token)
        if p:
            viewer_id = p["id"]
    return game.public_state(session_id, viewer_player_id=viewer_id)

@app.post("/api/order")
def add_order_endpoint(req: OrderRequest,
                       player: dict = Depends(get_player_from_header)):
    try:
        r = game.add_order(player["id"], req.action, req.target_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "order_added",
                   {"player_id": player["id"]})
    return r


@app.delete("/api/order/{order_id}")
def remove_order_endpoint(order_id: int,
                          player: dict = Depends(get_player_from_header)):
    try:
        r = game.remove_order(player["id"], order_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "order_removed",
                   {"player_id": player["id"]})
    return r


@app.delete("/api/order")
def clear_orders_endpoint(player: dict = Depends(get_player_from_header)):
    try:
        r = game.clear_orders(player["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "orders_cleared",
                   {"player_id": player["id"]})
    return r

@app.get("/api/admin/public")
def admin_public(session: dict = Depends(get_admin_session_from_header)):
    return game.public_state(
        session["id"],
        show_all_shields=True,
        include_winner=True,
    )

@app.get("/api/admin/public")
def admin_public(session: dict = Depends(get_admin_session_from_header)):
    return game.public_state(session["id"], show_all_shields=True)

@app.post("/api/ready")
def ready_endpoint(player: dict = Depends(get_player_from_header)):
    try:
        r = game.set_ready(player["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "player_ready",
                   {"player_id": player["id"]})
    return r


@app.post("/api/pay")
def pay_endpoint(req: PayRequest, player: dict = Depends(get_player_from_header)):
    try:
        r = game.transfer(player["id"], req.to_player_id, req.amount)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "money_transferred",
                   {"from": player["id"], "to": req.to_player_id,
                    "amount": req.amount})
    return r


# ===========================================================================
#  ПЕРЕГОВОРЫ
# ===========================================================================

@app.post("/api/talk")
def talk_endpoint(req: TalkRequest, player: dict = Depends(get_player_from_header)):
    try:
        r = game.request_talk(player["id"], req.to_player_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "talk_requested", {
        "request_id": r["request_id"],
        "from_planet": r["from_planet"],
        "to_planet": r["to_planet"],
    })
    return r


@app.get("/api/talk/my")
def my_talks(player: dict = Depends(get_player_from_header)):
    return game.get_my_talks(player["id"])


@app.post("/api/talk/{request_id}/accept")
def talk_accept(request_id: int, player: dict = Depends(get_player_from_header)):
    try:
        r = game.respond_talk(player["id"], request_id, accept=True)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "talk_accepted", {
        "request_id": request_id,
        "admin_hint": r["admin_hint"],
    })
    return r


@app.post("/api/talk/{request_id}/reject")
def talk_reject(request_id: int, player: dict = Depends(get_player_from_header)):
    try:
        r = game.respond_talk(player["id"], request_id, accept=False)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "talk_rejected", {"request_id": request_id})
    return r


@app.post("/api/talk/{request_id}/arrived")
def talk_arrived(request_id: int,
                 session: dict = Depends(get_admin_session_from_header)):
    try:
        r = game.mark_diplomat_arrived(session["id"], request_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(session["id"], "talk_arrived", {"request_id": request_id})
    return r


@app.post("/api/talk/{request_id}/finish")
def talk_finish(request_id: int, player: dict = Depends(get_player_from_header)):
    try:
        r = game.finish_talk(player["id"], request_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ws.notify_sync(player["session_id"], "talk_finished", {
        "request_id": request_id,
        "admin_hint": r["admin_hint"],
    })
    return r


from fastapi.responses import HTMLResponse
from app import summary as summary_module


@app.get("/api/summary/{session_id}/{round_num}.html", response_class=HTMLResponse)
def get_summary_html(session_id: int, round_num: int):
    try:
        html = summary_module.generate_html_string(session_id, round_num)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return HTMLResponse(content=html)


# ===========================================================================
#  ОЧИСТКА БД (только для супер-админа)
# ===========================================================================

import os
from fastapi.security import HTTPAuthorizationCredentials
from app.auth import _bearer
from app.config import SECRET_KEY


@app.post("/api/admin/reset-db")
def admin_reset_db(
    confirm: str,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """
    Удаляет все игровые данные. Требует:
    - confirm=yes-i-want-to-wipe-everything
    - Bearer <SECRET_KEY> в заголовке Authorization
    """
    if confirm != "yes-i-want-to-wipe-everything":
        raise HTTPException(400, "Передай confirm=yes-i-want-to-wipe-everything")

    if not creds or creds.credentials != SECRET_KEY:
        raise HTTPException(403, "Только супер-админ")

    with db.db_session() as conn:
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM cities")
        conn.execute("DELETE FROM talk_requests")
        conn.execute("DELETE FROM players")
        conn.execute("DELETE FROM sessions")

    return {
        "ok": True,
        "message": "БД очищена. Все сессии, игроки, приказы удалены.",
    }


# ===========================================================================
#  WEBSOCKET
# ===========================================================================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: int):
    await ws.manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws.manager.disconnect(session_id, websocket)
    except Exception:
        await ws.manager.disconnect(session_id, websocket)
