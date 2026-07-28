import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_MODULE_NAMES = [
    "app.config",
    "app.database",
    "app.security",
    "app.repository",
    "app.deps",
    "app.routers.auth",
    "app.routers.entries",
    "app.routers.tags",
    "app.main",
]


@dataclass
class AppContext:
    client: TestClient
    db_path: Path
    security: object
    repository: object


@pytest.fixture()
def app_ctx(tmp_path, monkeypatch):
    # 各テストごとにDATA_DIRを切り替え、DB/暗号化キー/セッションストアが
    # 前後のテストと絶対に共有されないようにモジュールをreloadする。
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")

    modules = {}
    for name in _MODULE_NAMES:
        if name in sys.modules:
            modules[name] = importlib.reload(sys.modules[name])
        else:
            modules[name] = importlib.import_module(name)

    main = modules["app.main"]
    with TestClient(main.app) as client:
        yield AppContext(
            client=client,
            db_path=modules["app.config"].DB_PATH,
            security=modules["app.security"],
            repository=modules["app.repository"],
        )


@pytest.fixture()
def client(app_ctx):
    return app_ctx.client


@pytest.fixture()
def authed_client(client):
    res = client.post("/api/auth/setup", json={"password": "testpassword123"})
    assert res.status_code == 200
    return client
