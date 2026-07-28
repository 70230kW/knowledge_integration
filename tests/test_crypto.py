import sqlite3

import pytest


def test_credential_body_is_encrypted_on_disk(app_ctx):
    client = app_ctx.client
    client.post("/api/auth/setup", json={"password": "testpassword123"})

    plaintext = "user: admin\npassword: hunter2"
    res = client.post(
        "/api/entries",
        json={"title": "秘密", "body": plaintext, "type": "credential", "tags": []},
    )
    entry_id = res.json()["id"]

    conn = sqlite3.connect(app_ctx.db_path)
    try:
        row = conn.execute("SELECT body FROM entries WHERE id = ?", (entry_id,)).fetchone()
    finally:
        conn.close()

    stored_body = row[0]
    assert plaintext not in stored_body
    assert stored_body.startswith("gAAAAA")  # Fernetトークンの先頭バイト列


def test_manual_body_is_stored_as_plaintext(app_ctx):
    client = app_ctx.client
    client.post("/api/auth/setup", json={"password": "testpassword123"})

    plaintext = "平文の手順メモ"
    res = client.post(
        "/api/entries",
        json={"title": "メモ", "body": plaintext, "type": "manual", "tags": []},
    )
    entry_id = res.json()["id"]

    conn = sqlite3.connect(app_ctx.db_path)
    try:
        row = conn.execute("SELECT body FROM entries WHERE id = ?", (entry_id,)).fetchone()
    finally:
        conn.close()

    assert row[0] == plaintext


def test_verify_master_password_rejects_wrong_password(app_ctx):
    security = app_ctx.security
    security.setup_master_password("correct-password-123")

    with pytest.raises(security.InvalidMasterPassword):
        security.verify_master_password("wrong-password")

    fernet = security.verify_master_password("correct-password-123")
    token = fernet.encrypt(b"hello")
    assert fernet.decrypt(token) == b"hello"


def test_session_store_ttl_and_lookup(app_ctx):
    security = app_ctx.security
    fernet = security.setup_master_password("correct-password-123")
    store = security.SessionStore(ttl_seconds=0)
    session_id = store.create(fernet)
    # ttl=0なので即座に期限切れ扱いになる
    assert store.get(session_id) is None

    store2 = security.SessionStore(ttl_seconds=60)
    session_id2 = store2.create(fernet)
    assert store2.get(session_id2) is fernet
    store2.delete(session_id2)
    assert store2.get(session_id2) is None
