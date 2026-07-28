import sqlite3

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status

from app import repository as repo
from app.deps import get_db, require_auth
from app.schemas import (
    BulkImportRequest,
    BulkImportResult,
    EntryIn,
    EntryListItem,
    EntryOut,
    LinkIn,
    SuggestionItem,
    SuggestionRequest,
)

router = APIRouter(prefix="/api/entries", tags=["entries"])


@router.get("", response_model=list[EntryListItem])
def list_or_search_entries(
    q: str | None = None,
    type: str | None = None,
    tag: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
    _fernet: Fernet = Depends(require_auth),
) -> list[EntryListItem]:
    if type is not None and type not in ("manual", "credential"):
        raise HTTPException(status_code=422, detail="typeはmanualまたはcredentialを指定してください。")
    if q:
        return repo.search_entries(conn, q, type_filter=type)
    return repo.list_entries(conn, type_filter=type, tag_filter=tag)


@router.post("", response_model=EntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    entry: EntryIn,
    conn: sqlite3.Connection = Depends(get_db),
    fernet: Fernet = Depends(require_auth),
) -> EntryOut:
    entry_id = repo.create_entry(conn, entry, fernet)
    return repo.get_entry(conn, entry_id, fernet)


@router.get("/{entry_id}", response_model=EntryOut)
def get_entry(
    entry_id: int,
    conn: sqlite3.Connection = Depends(get_db),
    fernet: Fernet = Depends(require_auth),
) -> EntryOut:
    result = repo.get_entry(conn, entry_id, fernet)
    if result is None:
        raise HTTPException(status_code=404, detail="エントリが見つかりません。")
    return result


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(
    entry_id: int,
    entry: EntryIn,
    conn: sqlite3.Connection = Depends(get_db),
    fernet: Fernet = Depends(require_auth),
) -> EntryOut:
    updated = repo.update_entry(conn, entry_id, entry, fernet)
    if not updated:
        raise HTTPException(status_code=404, detail="エントリが見つかりません。")
    return repo.get_entry(conn, entry_id, fernet)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    conn: sqlite3.Connection = Depends(get_db),
    _fernet: Fernet = Depends(require_auth),
) -> None:
    deleted = repo.delete_entry(conn, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="エントリが見つかりません。")


@router.post("/bulk", response_model=BulkImportResult, status_code=status.HTTP_201_CREATED)
def bulk_create_entries(
    payload: BulkImportRequest,
    conn: sqlite3.Connection = Depends(get_db),
    fernet: Fernet = Depends(require_auth),
) -> BulkImportResult:
    ids = repo.bulk_create_entries(conn, payload.type, payload.items, fernet)
    return BulkImportResult(created_count=len(ids), ids=ids)


@router.post("/suggestions", response_model=list[SuggestionItem])
def suggest(
    req: SuggestionRequest,
    conn: sqlite3.Connection = Depends(get_db),
    _fernet: Fernet = Depends(require_auth),
) -> list[SuggestionItem]:
    return repo.suggest_related(conn, req)


@router.post("/{entry_id}/links", status_code=status.HTTP_201_CREATED)
def create_link(
    entry_id: int,
    payload: LinkIn,
    conn: sqlite3.Connection = Depends(get_db),
    fernet: Fernet = Depends(require_auth),
) -> EntryOut:
    try:
        repo.add_link(conn, entry_id, payload.target_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    result = repo.get_entry(conn, entry_id, fernet)
    if result is None:
        raise HTTPException(status_code=404, detail="エントリが見つかりません。")
    return result


@router.delete("/{entry_id}/links/{target_id}")
def delete_link(
    entry_id: int,
    target_id: int,
    conn: sqlite3.Connection = Depends(get_db),
    fernet: Fernet = Depends(require_auth),
) -> EntryOut:
    repo.remove_link(conn, entry_id, target_id)
    result = repo.get_entry(conn, entry_id, fernet)
    if result is None:
        raise HTTPException(status_code=404, detail="エントリが見つかりません。")
    return result
