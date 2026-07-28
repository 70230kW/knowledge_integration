from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR
from app.database import init_db
from app.routers import auth, entries, tags


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ナレッジ集約アプリ", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(entries.router)
app.include_router(tags.router)

app.mount("/", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="static")
