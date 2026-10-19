# app/ws.py
import asyncio
import json
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.active: dict[int, list[WebSocket]] = {}
        self.lock = asyncio.Lock()
        self._main_loop: asyncio.AbstractEventLoop | None = None

    def set_main_loop(self, loop):
        self._main_loop = loop

    async def connect(self, session_id: int, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.active.setdefault(session_id, []).append(ws)

    async def disconnect(self, session_id: int, ws: WebSocket):
        async with self.lock:
            lst = self.active.get(session_id, [])
            if ws in lst:
                lst.remove(ws)
            if not lst:
                self.active.pop(session_id, None)

    async def broadcast(self, session_id: int, event: dict):
        async with self.lock:
            conns = list(self.active.get(session_id, []))
        payload = json.dumps(event, ensure_ascii=False)
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                pass


manager = WSManager()


def notify_sync(session_id: int, event_type: str, data: dict | None = None):
    """
    Синхронная функция, вызывается из эндпоинтов (в т.ч. sync def).
    Отправляет событие в главный event loop через run_coroutine_threadsafe.
    """
    loop = manager._main_loop
    if loop is None:
        return
    event = {"type": event_type, "session_id": session_id, "data": data or {}}
    try:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast(session_id, event), loop
        )
    except Exception:
        pass