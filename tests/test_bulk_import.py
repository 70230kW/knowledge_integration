import sqlite3


def test_bulk_create_credential_entries(authed_client):
    res = authed_client.post(
        "/api/entries/bulk",
        json={
            "type": "credential",
            "items": [
                {"title": "サービスA", "body": "user: a\npassword: pa", "tags": ["仕事"]},
                {"title": "サービスB", "body": "user: b\npassword: pb", "tags": ["仕事", "個人"]},
            ],
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["created_count"] == 2
    assert len(body["ids"]) == 2

    res = authed_client.get("/api/entries")
    assert res.status_code == 200
    titles = {e["title"] for e in res.json()}
    assert titles == {"サービスA", "サービスB"}

    res = authed_client.get("/api/tags")
    tag_names = {t["name"] for t in res.json()}
    assert tag_names == {"仕事", "個人"}


def test_bulk_create_manual_entries(authed_client):
    res = authed_client.post(
        "/api/entries/bulk",
        json={
            "type": "manual",
            "items": [{"title": "手順1", "body": "本文1", "tags": []}],
        },
    )
    assert res.status_code == 201
    entry_id = res.json()["ids"][0]

    res = authed_client.get(f"/api/entries/{entry_id}")
    assert res.status_code == 200
    assert res.json()["type"] == "manual"
    assert res.json()["body"] == "本文1"


def test_bulk_create_rejects_empty_items(authed_client):
    res = authed_client.post("/api/entries/bulk", json={"type": "credential", "items": []})
    assert res.status_code == 422


def test_bulk_create_rejects_blank_title(authed_client):
    res = authed_client.post(
        "/api/entries/bulk",
        json={"type": "manual", "items": [{"title": "", "body": "本文", "tags": []}]},
    )
    assert res.status_code == 422


def test_bulk_create_requires_auth(client):
    res = client.post(
        "/api/entries/bulk",
        json={"type": "manual", "items": [{"title": "x", "body": "", "tags": []}]},
    )
    assert res.status_code == 401


def test_bulk_created_credential_body_is_encrypted_on_disk(app_ctx):
    client = app_ctx.client
    client.post("/api/auth/setup", json={"password": "testpassword123"})

    plaintext = "user: admin\npassword: hunter2"
    res = client.post(
        "/api/entries/bulk",
        json={"type": "credential", "items": [{"title": "秘密", "body": plaintext, "tags": []}]},
    )
    entry_id = res.json()["ids"][0]

    conn = sqlite3.connect(app_ctx.db_path)
    try:
        row = conn.execute("SELECT body FROM entries WHERE id = ?", (entry_id,)).fetchone()
    finally:
        conn.close()

    assert plaintext not in row[0]
    assert row[0].startswith("gAAAAA")
