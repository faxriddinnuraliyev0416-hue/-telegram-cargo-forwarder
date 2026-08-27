import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app import config

logger = logging.getLogger("app.db")

db_url = config.DATABASE_URL
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url and db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
if not db_url or "sqlite" in db_url:
    engine = create_engine(db_url or "sqlite:///cargo.db", connect_args={"check_same_thread": False} if "sqlite" in (db_url or "") else {}, future=True)
else:
    try:
        engine = create_engine(db_url, pool_pre_ping=True, future=True)
    except Exception as exc:
        logger.warning(f"Asosiy DATABASE_URL ga ulanib bo'lmadi ({exc}), sqlite:///cargo.db ga o'tilmoqda")
        engine = create_engine("sqlite:///cargo.db", connect_args={"check_same_thread": False}, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_session():
    """Yangi DB sessiyasini qaytaradi. Har doim `session.close()` qilinishi lozim."""
    return SessionLocal()


@contextmanager
def session_scope():
    """Context manager yordamida xavfsiz sessiya boshqaruvi:
    with session_scope() as session:
        session.query(...)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Barcha jadvallarni va yangi qo'shilgan ustunlarni yaratadi (Auto-migration)."""
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Mavjud PostgreSQL/SQLite jadvallariga yangi ustunlarni avtomatik qo'shish
    from sqlalchemy import text
    migration_sqls = [
        "ALTER TABLE source_chats ADD COLUMN IF NOT EXISTS invite_link VARCHAR(255);",
        "ALTER TABLE source_chats ADD COLUMN IF NOT EXISTS message_count INTEGER DEFAULT 0;",
        "ALTER TABLE source_chats ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMP;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE cargo_messages ADD COLUMN IF NOT EXISTS parsed_phone VARCHAR(255);",
        "ALTER TABLE cargo_messages ADD COLUMN IF NOT EXISTS is_cargo BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE cargo_messages ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(255);",
    ]

    with engine.connect() as conn:
        for sql in migration_sqls:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                logger.debug(f"Migratsiya ogohlantirish: {e}")


