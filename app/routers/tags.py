import sqlite3

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends

from app import repository as repo
from app.deps import get_db, require_auth
from app.schemas import TagOut

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(
    conn: sqlite3.Connection = Depends(get_db),
    _fernet: Fernet = Depends(require_auth),
) -> list[TagOut]:
    return repo.list_tags(conn)
