def _create(client, title, body, type_="manual", tags=None):
    res = client.post(
        "/api/entries",
        json={"title": title, "body": body, "type": type_, "tags": tags or []},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_search_matches_title_and_body(authed_client):
    _create(authed_client, "Wi-Fiルーター設定マニュアル", "SSIDとパスワードの設定方法を記載")
    _create(authed_client, "無関係なメモ", "特に関係のない内容です")

    res = authed_client.get("/api/entries", params={"q": "SSID"})
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 1
    assert results[0]["title"] == "Wi-Fiルーター設定マニュアル"
    assert "SSID" in results[0]["snippet"]


def test_search_excludes_credential_body(authed_client):
    _create(authed_client, "認証情報", "SSID: home\npassword: hunter2", type_="credential")

    res = authed_client.get("/api/entries", params={"q": "hunter2"})
    assert res.status_code == 200
    assert res.json() == []


def test_search_short_query_uses_like_fallback(authed_client):
    _create(authed_client, "テスト", "本文", tags=["ネ"])

    res = authed_client.get("/api/entries", params={"q": "ネ"})
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_search_respects_type_filter(authed_client):
    _create(authed_client, "共通キーワードマニュアル", "きょうつうキーワードです")
    _create(authed_client, "共通キーワード認証", "きょうつうキーワードです", type_="credential")

    res = authed_client.get("/api/entries", params={"q": "共通キーワード", "type": "manual"})
    assert res.status_code == 200
    titles = [e["title"] for e in res.json()]
    assert titles == ["共通キーワードマニュアル"]
