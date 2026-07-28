import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "knowledge.db"
SALT_PATH = DATA_DIR / "salt.bin"
VERIFY_TOKEN_PATH = DATA_DIR / "verify.token"

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "")
SESSION_COOKIE_NAME = "ki_session"
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60 * 12)))
