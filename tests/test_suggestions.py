def test_suggestions_match_by_tag_and_keyword(authed_client):
    manual_id = authed_client.post(
        "/api/entries",
        json={
            "title": "Wi-Fiルーター設定マニュアル",
            "body": "ルーターの初期設定手順。SSIDとパスワードの設定方法を記載。",
            "type": "manual",
            "tags": ["ネットワーク", "ルーター"],
        },
    ).json()["id"]

    res = authed_client.post(
        "/api/entries/suggestions",
        json={
            "title": "自宅Wi-FiのID/Pass",
            "body": "SSIDとパスワードを控えておく",
            "tags": ["ネットワーク"],
            "exclude_id": None,
        },
    )
    assert res.status_code == 200
    suggestions = res.json()
    assert len(suggestions) == 1
    assert suggestions[0]["id"] == manual_id
    assert "ネットワーク" in suggestions[0]["matched_tags"]
    assert suggestions[0]["score"] > 0


def test_suggestions_exclude_self_and_no_overlap_returns_empty(authed_client):
    entry_id = authed_client.post(
        "/api/entries",
        json={"title": "何かのタイトル", "body": "本文", "type": "manual", "tags": ["タグX"]},
    ).json()["id"]

    res = authed_client.post(
        "/api/entries/suggestions",
        json={"title": "何かのタイトル", "body": "本文", "tags": ["タグX"], "exclude_id": entry_id},
    )
    assert res.status_code == 200
    assert res.json() == []

    res = authed_client.post(
        "/api/entries/suggestions",
        json={"title": "全く関係ない単語列", "body": "無関係", "tags": [], "exclude_id": None},
    )
    assert res.status_code == 200
    assert res.json() == []


def test_suggestions_exclude_already_linked_entries(authed_client):
    id_a = authed_client.post(
        "/api/entries",
        json={"title": "エントリA", "body": "共通キーワード", "type": "manual", "tags": ["共通タグ"]},
    ).json()["id"]
    id_b = authed_client.post(
        "/api/entries",
        json={"title": "エントリB", "body": "共通キーワード", "type": "manual", "tags": ["共通タグ"]},
    ).json()["id"]

    authed_client.post(f"/api/entries/{id_a}/links", json={"target_id": id_b})

    res = authed_client.post(
        "/api/entries/suggestions",
        json={"title": "エントリA", "body": "共通キーワード", "tags": ["共通タグ"], "exclude_id": id_a},
    )
    assert res.status_code == 200
    # 既にリンク済みのidBは提案から除外される
    assert res.json() == []
