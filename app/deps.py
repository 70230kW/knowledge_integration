from collections.abc import Generator

from cryptography.fernet import Fernet
from fastapi import Cookie, HTTPException, status

from app.config import SESSION_COOKIE_NAME
from app.database import get_connection
from app.security import session_store


def get_db() -> Generator:
    with get_connection() as conn:
        yield conn


def require_auth(
    ki_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> Fernet:
    fernet = session_store.get(ki_session)
    if fernet is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です。マスターパスワードでログインしてください。",
        )
    return fernet
