# app/models.py
from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    rounds_total: int = Field(default=6, ge=1, le=20)


class CreateSessionResponse(BaseModel):
    session_id: int
    join_code: str
    admin_token: str


class JoinRequest(BaseModel):
    join_code: str
    name: str = Field(min_length=1, max_length=64)


class JoinResponse(BaseModel):
    player_id: int
    planet: str
    player_token: str
    session_id: int


class PlayerPublic(BaseModel):
    id: int
    name: str
    planet: str
    is_alive: bool
    order_ready: bool = False


class SessionPublic(BaseModel):
    id: int
    status: str
    current_round: int
    rounds_total: int
    anomaly: int
    paused: bool = False
    deadline: float | None = None
    last_summary: dict | None = None
    players: list[PlayerPublic]


class OrderRequest(BaseModel):
    action: str
    target_id: int | None = None


class PayRequest(BaseModel):
    to_player_id: int
    amount: int


class TalkRequest(BaseModel):
    to_player_id: int