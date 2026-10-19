# app/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app import db

_bearer = HTTPBearer(auto_error=False)


def get_player_from_header(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if not creds:
        raise HTTPException(401, "Missing token")
    player = db.get_player_by_token(creds.credentials)
    if not player:
        raise HTTPException(401, "Invalid token")
    return player


def get_admin_session_from_header(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if not creds:
        raise HTTPException(401, "Missing token")
    session = db.get_session_by_admin_token(creds.credentials)
    if not session:
        raise HTTPException(401, "Invalid admin token")
    return session