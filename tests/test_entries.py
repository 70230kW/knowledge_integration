def test_create_get_update_delete_manual_entry(authed_client):
    res = authed_client.post(
        "/api/entries",
        json={
            "title": "テストマニュアル",
            "body": "本文です",
            "type": "manual",
            "tags": ["タグA", "タグB"],
        },
    )
    assert res.status_code == 201
    entry = res.json()
    entry_id = entry["id"]
    assert entry["title"] == "テストマニュアル"
    assert entry["body"] == "本文です"
    assert sorted(entry["tags"]) == ["タグA", "タグB"]

    res = authed_client.get(f"/api/entries/{entry_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "テストマニュアル"

    res = authed_client.put(
        f"/api/entries/{entry_id}",
        json={"title": "更新後タイトル", "body": "更新後本文", "type": "manual", "tags": ["タグC"]},
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["title"] == "更新後タイトル"
    assert updated["tags"] == ["タグC"]

    res = authed_client.delete(f"/api/entries/{entry_id}")
    assert res.status_code == 204

    res = authed_client.get(f"/api/entries/{entry_id}")
    assert res.status_code == 404

    res = authed_client.delete(f"/api/entries/{entry_id}")
    assert res.status_code == 404


def test_credential_entry_body_roundtrip(authed_client):
    res = authed_client.post(
        "/api/entries",
        json={
            "title": "秘密の認証情報",
            "body": "user: admin\npassword: hunter2",
            "type": "credential",
            "tags": [],
        },
    )
    assert res.status_code == 201
    entry_id = res.json()["id"]

    res = authed_client.get(f"/api/entries/{entry_id}")
    assert res.status_code == 200
    assert res.json()["body"] == "user: admin\npassword: hunter2"


def test_list_filter_by_type_and_tag(authed_client):
    authed_client.post(
        "/api/entries",
        json={"title": "マニュアル1", "body": "", "type": "manual", "tags": ["共通タグ"]},
    )
    authed_client.post(
        "/api/entries",
        json={"title": "認証情報1", "body": "x", "type": "credential", "tags": ["共通タグ"]},
    )

    res = authed_client.get("/api/entries", params={"type": "manual"})
    assert res.status_code == 200
    titles = [e["title"] for e in res.json()]
    assert titles == ["マニュアル1"]

    res = authed_client.get("/api/entries", params={"tag": "共通タグ"})
    assert res.status_code == 200
    assert len(res.json()) == 2

    res = authed_client.get("/api/entries", params={"type": "invalid"})
    assert res.status_code == 422


def test_links_between_entries(authed_client):
    id_a = authed_client.post(
        "/api/entries", json={"title": "A", "body": "", "type": "manual", "tags": []}
    ).json()["id"]
    id_b = authed_client.post(
        "/api/entries", json={"title": "B", "body": "", "type": "manual", "tags": []}
    ).json()["id"]

    res = authed_client.post(f"/api/entries/{id_a}/links", json={"target_id": id_b})
    assert res.status_code == 201
    linked_ids = [e["id"] for e in res.json()["linked_entries"]]
    assert linked_ids == [id_b]

    # 逆方向からも見える
    res = authed_client.get(f"/api/entries/{id_b}")
    assert [e["id"] for e in res.json()["linked_entries"]] == [id_a]

    # 自己リンクは拒否
    res = authed_client.post(f"/api/entries/{id_a}/links", json={"target_id": id_a})
    assert res.status_code == 422

    res = authed_client.delete(f"/api/entries/{id_a}/links/{id_b}")
    assert res.status_code == 200
    assert res.json()["linked_entries"] == []
