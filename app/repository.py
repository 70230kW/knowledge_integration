import re
import sqlite3
from datetime import datetime, timezone

from cryptography.fernet import Fernet

from app.schemas import EntryIn, EntryListItem, EntryOut, LinkedEntryOut, SuggestionItem, SuggestionRequest, TagOut

_TAG_SEP = ""
_KEYWORD_SPLIT_RE = re.compile(
    r"[\s、。,.!?！？「」『』:：;；()（）\[\]【】/\\・\-—~〜\"'`\n\t]+"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _fts_delete(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute("DELETE FROM entries_fts WHERE rowid = ?", (entry_id,))


def _fts_upsert(conn: sqlite3.Connection, entry_id: int, title: str, body_for_index: str, tags_text: str) -> None:
    _fts_delete(conn, entry_id)
    conn.execute(
        "INSERT INTO entries_fts(rowid, title, body, tags_text) VALUES (?, ?, ?, ?)",
        (entry_id, title, body_for_index, tags_text),
    )


def _get_or_create_tag_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO tags(name) VALUES (?)", (name,))
    return cur.lastrowid


def _cleanup_orphan_tags(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM entry_tags)"
    )


def _normalize_tags(tags: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for raw in tags:
        name = raw.strip()
        if not name:
            continue
        key = name.lower()
        seen.setdefault(key, name)
    return list(seen.values())


def _set_entry_tags(conn: sqlite3.Connection, entry_id: int, tag_names: list[str]) -> list[str]:
    normalized = _normalize_tags(tag_names)
    conn.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
    for name in normalized:
        tag_id = _get_or_create_tag_id(conn, name)
        conn.execute(
            "INSERT OR IGNORE INTO entry_tags(entry_id, tag_id) VALUES (?, ?)",
            (entry_id, tag_id),
        )
    _cleanup_orphan_tags(conn)
    return normalized


def _get_entry_tags(conn: sqlite3.Connection, entry_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT t.name FROM tags t
        JOIN entry_tags et ON et.tag_id = t.id
        WHERE et.entry_id = ?
        ORDER BY t.name
        """,
        (entry_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def _encrypt_body(fernet: Fernet, entry_type: str, body: str) -> str:
    if entry_type == "credential":
        return fernet.encrypt(body.encode("utf-8")).decode("ascii")
    return body


def _decrypt_body(fernet: Fernet, entry_type: str, stored_body: str) -> str:
    if entry_type == "credential":
        return fernet.decrypt(stored_body.encode("ascii")).decode("utf-8")
    return stored_body


def _body_for_index(entry_type: str, plaintext_body: str) -> str:
    # credentialの本文は暗号文しか持たないため、平文が漏れないようFTS索引には入れない
    return plaintext_body if entry_type == "manual" else ""


def create_entry(conn: sqlite3.Connection, entry: EntryIn, fernet: Fernet) -> int:
    now = _now_iso()
    stored_body = _encrypt_body(fernet, entry.type, entry.body)
    cur = conn.execute(
        "INSERT INTO entries(title, body, type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (entry.title, stored_body, entry.type, now, now),
    )
    entry_id = cur.lastrowid
    tag_names = _set_entry_tags(conn, entry_id, entry.tags)
    _fts_upsert(conn, entry_id, entry.title, _body_for_index(entry.type, entry.body), " ".join(tag_names))
    return entry_id


def update_entry(conn: sqlite3.Connection, entry_id: int, entry: EntryIn, fernet: Fernet) -> bool:
    existing = conn.execute("SELECT id FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not existing:
        return False
    now = _now_iso()
    stored_body = _encrypt_body(fernet, entry.type, entry.body)
    conn.execute(
        "UPDATE entries SET title = ?, body = ?, type = ?, updated_at = ? WHERE id = ?",
        (entry.title, stored_body, entry.type, now, entry_id),
    )
    tag_names = _set_entry_tags(conn, entry_id, entry.tags)
    _fts_upsert(conn, entry_id, entry.title, _body_for_index(entry.type, entry.body), " ".join(tag_names))
    return True


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    cur = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    _fts_delete(conn, entry_id)
    _cleanup_orphan_tags(conn)
    return cur.rowcount > 0


def get_linked_entries(conn: sqlite3.Connection, entry_id: int) -> list[LinkedEntryOut]:
    rows = conn.execute(
        """
        SELECT e.id, e.title, e.type FROM entry_links el
        JOIN entries e ON e.id = (
            CASE WHEN el.entry_id_a = :eid THEN el.entry_id_b ELSE el.entry_id_a END
        )
        WHERE el.entry_id_a = :eid OR el.entry_id_b = :eid
        ORDER BY e.title
        """,
        {"eid": entry_id},
    ).fetchall()
    return [LinkedEntryOut(id=r["id"], title=r["title"], type=r["type"]) for r in rows]


def get_entry(conn: sqlite3.Connection, entry_id: int, fernet: Fernet) -> EntryOut | None:
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        return None
    body = _decrypt_body(fernet, row["type"], row["body"])
    tags = _get_entry_tags(conn, entry_id)
    linked = get_linked_entries(conn, entry_id)
    return EntryOut(
        id=row["id"],
        title=row["title"],
        body=body,
        type=row["type"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        tags=tags,
        linked_entries=linked,
    )


def _row_to_list_item(row: sqlite3.Row, snippet: str | None = None) -> EntryListItem:
    tags_csv = row["tags_csv"] or ""
    tags = [t for t in tags_csv.split(_TAG_SEP) if t]
    return EntryListItem(
        id=row["id"],
        title=row["title"],
        type=row["type"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        tags=tags,
        snippet=snippet,
    )


def list_entries(
    conn: sqlite3.Connection, type_filter: str | None = None, tag_filter: str | None = None
) -> list[EntryListItem]:
    conditions = []
    params: list = []
    if type_filter:
        conditions.append("e.type = ?")
        params.append(type_filter)
    if tag_filter:
        conditions.append(
            "e.id IN (SELECT et.entry_id FROM entry_tags et JOIN tags t ON t.id = et.tag_id WHERE t.name = ?)"
        )
        params.append(tag_filter)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT e.id, e.title, e.type, e.created_at, e.updated_at,
               GROUP_CONCAT(t.name, '{_TAG_SEP}') AS tags_csv
        FROM entries e
        LEFT JOIN entry_tags et ON et.entry_id = e.id
        LEFT JOIN tags t ON t.id = et.tag_id
        {where_clause}
        GROUP BY e.id
        ORDER BY e.updated_at DESC
    """
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_list_item(r) for r in rows]


def _escape_fts_phrase(term: str) -> str:
    return term.replace('"', '""')


def search_entries(
    conn: sqlite3.Connection, query: str, type_filter: str | None = None
) -> list[EntryListItem]:
    query = query.strip()
    if not query:
        return list_entries(conn, type_filter=type_filter)

    terms = [t for t in re.split(r"\s+", query) if t]
    if not terms:
        return list_entries(conn, type_filter=type_filter)

    if all(len(t) >= 3 for t in terms):
        return _search_entries_fts(conn, terms, type_filter)
    return _search_entries_like(conn, terms, type_filter)


def _search_entries_fts(
    conn: sqlite3.Connection, terms: list[str], type_filter: str | None
) -> list[EntryListItem]:
    match_expr = " AND ".join(f'"{_escape_fts_phrase(t)}"' for t in terms)
    type_clause = "AND e.type = ?" if type_filter else ""
    params: list = [match_expr]
    if type_filter:
        params.append(type_filter)
    sql = f"""
        SELECT e.id, e.title, e.type, e.created_at, e.updated_at,
               (
                   SELECT GROUP_CONCAT(t.name, '{_TAG_SEP}') FROM entry_tags et
                   JOIN tags t ON t.id = et.tag_id WHERE et.entry_id = e.id
               ) AS tags_csv,
               snippet(entries_fts, 1, '[[', ']]', '…', 12) AS body_snippet,
               snippet(entries_fts, 0, '[[', ']]', '', 8) AS title_snippet
        FROM entries_fts
        JOIN entries e ON e.id = entries_fts.rowid
        WHERE entries_fts MATCH ?
        {type_clause}
        ORDER BY bm25(entries_fts)
    """
    rows = conn.execute(sql, params).fetchall()
    results = []
    for r in rows:
        snippet = r["body_snippet"] if "[[" in (r["body_snippet"] or "") else r["title_snippet"]
        results.append(_row_to_list_item(r, snippet=snippet or None))
    return results


def _naive_snippet(text: str, terms: list[str], width: int = 60) -> str | None:
    if not text:
        return None
    lower = text.lower()
    for term in terms:
        idx = lower.find(term.lower())
        if idx >= 0:
            start = max(0, idx - width // 2)
            end = min(len(text), idx + len(term) + width // 2)
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(text) else ""
            return prefix + text[start:end] + suffix
    return None


def _search_entries_like(
    conn: sqlite3.Connection, terms: list[str], type_filter: str | None
) -> list[EntryListItem]:
    having_clauses = []
    params: list = []
    for term in terms:
        pattern = f"%{term}%"
        having_clauses.append(
            "(e.title LIKE ? OR IFNULL(tags_csv, '') LIKE ? OR (e.type = 'manual' AND e.body LIKE ?))"
        )
        params.extend([pattern, pattern, pattern])

    where_clause = ""
    if type_filter:
        where_clause = "WHERE e.type = ?"

    sql = f"""
        SELECT e.id, e.title, e.type, e.created_at, e.updated_at, e.body,
               GROUP_CONCAT(t.name, '{_TAG_SEP}') AS tags_csv
        FROM entries e
        LEFT JOIN entry_tags et ON et.entry_id = e.id
        LEFT JOIN tags t ON t.id = et.tag_id
        {where_clause}
        GROUP BY e.id
        HAVING {' AND '.join(having_clauses)}
        ORDER BY e.updated_at DESC
    """
    query_params = ([type_filter] if type_filter else []) + params
    rows = conn.execute(sql, query_params).fetchall()
    results = []
    for r in rows:
        source_text = r["title"] + " " + (r["tags_csv"] or "").replace(_TAG_SEP, " ")
        if r["type"] == "manual":
            source_text += " " + r["body"]
        snippet = _naive_snippet(source_text, terms)
        results.append(_row_to_list_item(r, snippet=snippet))
    return results


def list_tags(conn: sqlite3.Connection) -> list[TagOut]:
    rows = conn.execute(
        """
        SELECT t.id, t.name, COUNT(et.entry_id) AS cnt
        FROM tags t
        LEFT JOIN entry_tags et ON et.tag_id = t.id
        GROUP BY t.id
        ORDER BY cnt DESC, t.name ASC
        """
    ).fetchall()
    return [TagOut(id=r["id"], name=r["name"], count=r["cnt"]) for r in rows]


def add_link(conn: sqlite3.Connection, entry_id_a: int, entry_id_b: int) -> None:
    if entry_id_a == entry_id_b:
        raise ValueError("同じエントリ同士はリンクできません")
    rows = conn.execute(
        "SELECT id FROM entries WHERE id IN (?, ?)", (entry_id_a, entry_id_b)
    ).fetchall()
    if len(rows) != 2:
        raise ValueError("指定されたエントリが見つかりません")
    a, b = sorted((entry_id_a, entry_id_b))
    conn.execute(
        "INSERT OR IGNORE INTO entry_links(entry_id_a, entry_id_b, created_at) VALUES (?, ?, ?)",
        (a, b, _now_iso()),
    )


def remove_link(conn: sqlite3.Connection, entry_id_a: int, entry_id_b: int) -> bool:
    a, b = sorted((entry_id_a, entry_id_b))
    cur = conn.execute(
        "DELETE FROM entry_links WHERE entry_id_a = ? AND entry_id_b = ?", (a, b)
    )
    return cur.rowcount > 0


def _extract_keywords(text: str, limit: int = 20) -> list[str]:
    tokens = _KEYWORD_SPLIT_RE.split(text)
    seen: dict[str, str] = {}
    for tok in tokens:
        tok = tok.strip()
        if len(tok) < 2:
            continue
        key = tok.lower()
        seen.setdefault(key, tok)
        if len(seen) >= limit:
            break
    return list(seen.values())


def suggest_related(conn: sqlite3.Connection, req: SuggestionRequest) -> list[SuggestionItem]:
    draft_tags = {t.strip().lower(): t.strip() for t in req.tags if t.strip()}
    keywords = _extract_keywords(f"{req.title} {req.body}")

    already_linked_ids: set[int] = set()
    if req.exclude_id is not None:
        already_linked_ids = {l.id for l in get_linked_entries(conn, req.exclude_id)}

    rows = conn.execute(
        """
        SELECT e.id, e.title, e.type, e.body,
               GROUP_CONCAT(t.name, '{sep}') AS tags_csv
        FROM entries e
        LEFT JOIN entry_tags et ON et.entry_id = e.id
        LEFT JOIN tags t ON t.id = et.tag_id
        GROUP BY e.id
        """.format(sep=_TAG_SEP)
    ).fetchall()

    candidates: list[SuggestionItem] = []
    for row in rows:
        if req.exclude_id is not None and row["id"] == req.exclude_id:
            continue
        if row["id"] in already_linked_ids:
            continue
        candidate_tags = [t for t in (row["tags_csv"] or "").split(_TAG_SEP) if t]
        candidate_tag_keys = {t.lower() for t in candidate_tags}
        matched_tags = [orig for key, orig in draft_tags.items() if key in candidate_tag_keys]

        searchable = row["title"] + " " + " ".join(candidate_tags)
        if row["type"] == "manual":
            searchable += " " + row["body"]
        searchable_lower = searchable.lower()
        matched_keywords = [kw for kw in keywords if kw.lower() in searchable_lower]

        score = len(matched_tags) * 3 + len(matched_keywords) * 1.0
        if score <= 0:
            continue
        candidates.append(
            SuggestionItem(
                id=row["id"],
                title=row["title"],
                type=row["type"],
                matched_tags=matched_tags,
                matched_keywords=matched_keywords,
                score=score,
            )
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:5]
