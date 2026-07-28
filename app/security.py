import base64
import os
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import SALT_PATH, SESSION_TTL_SECONDS, VERIFY_TOKEN_PATH

_KDF_ITERATIONS = 390_000
_VERIFY_PLAINTEXT = b"knowledge-integration-verify"


class InvalidMasterPassword(Exception):
    pass


def is_initialized() -> bool:
    return VERIFY_TOKEN_PATH.exists() and SALT_PATH.exists()


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def setup_master_password(password: str) -> Fernet:
    """初回起動時にマスターパスワードを登録し、Fernetインスタンスを返す。"""
    if is_initialized():
        raise RuntimeError("master password is already initialized")
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    fernet = Fernet(key)
    token = fernet.encrypt(_VERIFY_PLAINTEXT)

    SALT_PATH.write_bytes(salt)
    VERIFY_TOKEN_PATH.write_bytes(token)
    return fernet


def verify_master_password(password: str) -> Fernet:
    """マスターパスワードを検証し、正しければFernetインスタンスを返す。"""
    if not is_initialized():
        raise RuntimeError("master password is not initialized yet")

    salt = SALT_PATH.read_bytes()
    key = _derive_key(password, salt)
    fernet = Fernet(key)
    token = VERIFY_TOKEN_PATH.read_bytes()
    try:
        plaintext = fernet.decrypt(token)
    except InvalidToken:
        raise InvalidMasterPassword("incorrect master password")
    if plaintext != _VERIFY_PLAINTEXT:
        raise InvalidMasterPassword("incorrect master password")
    return fernet


class SessionStore:
    """認証済みセッションごとのFernetキーをメモリ上にのみ保持するストア。

    Fernetキー（復号鍵）はディスクにもクッキーにも書き出さない。
    """

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS):
        self._sessions: dict[str, tuple[Fernet, float]] = {}
        self._ttl = ttl_seconds

    def create(self, fernet: Fernet) -> str:
        session_id = secrets.token_urlsafe(32)
        self._sessions[session_id] = (fernet, time.monotonic() + self._ttl)
        return session_id

    def get(self, session_id: str | None) -> Fernet | None:
        if not session_id:
            return None
        entry = self._sessions.get(session_id)
        if entry is None:
            return None
        fernet, expires_at = entry
        if time.monotonic() > expires_at:
            self._sessions.pop(session_id, None)
            return None
        return fernet

    def delete(self, session_id: str | None) -> None:
        if session_id:
            self._sessions.pop(session_id, None)


session_store = SessionStore()
