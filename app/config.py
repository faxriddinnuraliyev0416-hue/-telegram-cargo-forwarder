"""
Markazlashgan konfiguratsiya. Barcha maxfiy ma'lumotlar faqat .env orqali o'qiladi,
hech qanday token/parol source code ichida yozilmagan.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default=None):
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return int(val)


def _get_list(name: str) -> list[str]:
    val = os.getenv(name, "")
    return [item.strip() for item in val.split(",") if item.strip()]


def _get_int_list(name: str) -> list[int]:
    return [int(x) for x in _get_list(name)]


# --- Telethon (userbot) ---
API_ID = _get_int("API_ID")
API_HASH = os.getenv("API_HASH", "").strip()
TELETHON_SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "sessions/userbot_session").strip()
TELETHON_STRING_SESSION = os.getenv("TELETHON_STRING_SESSION", "").strip()

# --- Bot API ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip()

# --- Guruhlar ---
MAIN_GROUP_ID = _get_int("MAIN_GROUP_ID")
SOURCE_CHATS = _get_list("SOURCE_CHATS")

# --- Adminlar ---
ADMIN_IDS = set(_get_int_list("ADMIN_IDS"))

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://cargo_user:cargo_pass@localhost:5432/cargo_db")

# --- Redis ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_MATCH_CHANNEL = "cargo:new_matches"
REDIS_DEDUP_PREFIX = "cargo:dedup:"

# --- Boshqalar ---
MESSAGE_RETENTION_DAYS = _get_int("MESSAGE_RETENTION_DAYS", 30)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")


def _validate_required(values: list[tuple[str, object]]):
    missing = []
    for name, val in values:
        if not val:
            missing.append(name)
    if missing:
        raise RuntimeError(f".env faylida quyidagi qiymatlar to'ldirilmagan: {', '.join(missing)}")


def validate_userbot():
    """Telethon userbot uchun majburiy sozlamalarni tekshiradi."""
    _validate_required([
        ("API_ID", API_ID),
        ("API_HASH", API_HASH),
        ("MAIN_GROUP_ID", MAIN_GROUP_ID),
        ("SOURCE_CHATS", SOURCE_CHATS),
    ])


def validate_bot():
    """Bot API processi uchun majburiy sozlamalarni tekshiradi."""
    _validate_required([
        ("BOT_TOKEN", BOT_TOKEN),
        ("BOT_USERNAME", BOT_USERNAME),
        ("MAIN_GROUP_ID", MAIN_GROUP_ID),
    ])


def validate():
    """Orqaga moslik uchun userbot tekshiruvini chaqiradi."""
    validate_userbot()
