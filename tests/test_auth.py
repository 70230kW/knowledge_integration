def test_initial_status_not_initialized(client):
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    assert res.json() == {"initialized": False, "authenticated": False}


def test_setup_rejects_short_password(client):
    res = client.post("/api/auth/setup", json={"password": "short"})
    assert res.status_code == 422


def test_setup_login_logout_flow(client):
    res = client.post("/api/auth/setup", json={"password": "testpassword123"})
    assert res.status_code == 200
    assert res.json() == {"initialized": True, "authenticated": True}

    # 2回目のsetupは拒否される
    res = client.post("/api/auth/setup", json={"password": "testpassword123"})
    assert res.status_code == 409

    res = client.post("/api/auth/logout")
    assert res.status_code == 200

    res = client.get("/api/auth/status")
    assert res.json() == {"initialized": True, "authenticated": False}

    res = client.post("/api/auth/login", json={"password": "wrong-password"})
    assert res.status_code == 401

    res = client.post("/api/auth/login", json={"password": "testpassword123"})
    assert res.status_code == 200
    assert res.json()["authenticated"] is True


def test_entries_endpoints_require_auth(client):
    res = client.get("/api/entries")
    assert res.status_code == 401

    res = client.post(
        "/api/entries",
        json={"title": "t", "body": "b", "type": "manual", "tags": []},
    )
    assert res.status_code == 401
