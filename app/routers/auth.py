from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.config import SESSION_COOKIE_NAME, SESSION_TTL_SECONDS
from app.schemas import AuthStatus, PasswordIn
from app.security import (
    InvalidMasterPassword,
    is_initialized,
    session_store,
    setup_master_password,
    verify_master_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )


@router.get("/status", response_model=AuthStatus)
def get_status(
    ki_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> AuthStatus:
    return AuthStatus(
        initialized=is_initialized(),
        authenticated=session_store.get(ki_session) is not None,
    )


@router.post("/setup", response_model=AuthStatus)
def setup(payload: PasswordIn, response: Response) -> AuthStatus:
    if is_initialized():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="マスターパスワードは既に設定されています。ログインしてください。",
        )
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="マスターパスワードは8文字以上にしてください。",
        )
    fernet = setup_master_password(payload.password)
    session_id = session_store.create(fernet)
    _set_session_cookie(response, session_id)
    return AuthStatus(initialized=True, authenticated=True)


@router.post("/login", response_model=AuthStatus)
def login(payload: PasswordIn, response: Response) -> AuthStatus:
    if not is_initialized():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="マスターパスワードが未設定です。先に初期設定を行ってください。",
        )
    try:
        fernet = verify_master_password(payload.password)
    except InvalidMasterPassword:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="マスターパスワードが正しくありません。",
        )
    session_id = session_store.create(fernet)
    _set_session_cookie(response, session_id)
    return AuthStatus(initialized=True, authenticated=True)


@router.post("/logout")
def logout(
    response: Response,
    ki_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
    session_store.delete(ki_session)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}
