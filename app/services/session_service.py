"""
Userbot va Bot sessiyalarini monitoring qilish, real-time status,
heartbeat va xatoliklar jurnali servisi.
"""
import datetime
from app.db import get_session
from app.models import UserbotSessionStatus, ErrorLog


def record_heartbeat(
    session_name: str = "userbot_session",
    connected_chats_count: int = 0,
    processed_increment: int = 0,
    forwarded_increment: int = 0,
    duplicate_increment: int = 0,
    ignored_increment: int = 0,
    error_increment: int = 0,
):
    """Userbot muntazam (masalan har 30 soniyada) ushbu funksiyani chaqirib yurak urishi (heartbeat) yuboradi."""
    session = get_session()
    try:
        status_row = session.query(UserbotSessionStatus).filter_by(session_name=session_name).first()
        now = datetime.datetime.utcnow()
        if not status_row:
            status_row = UserbotSessionStatus(
                session_name=session_name,
                is_online=True,
                last_ping_at=now,
                connected_chats_count=connected_chats_count,
                total_processed=processed_increment,
                total_forwarded=forwarded_increment,
                total_duplicates=duplicate_increment,
                total_ignored=ignored_increment,
                error_count=error_increment,
            )
            session.add(status_row)
        else:
            status_row.is_online = True
            status_row.last_ping_at = now
            status_row.connected_chats_count = connected_chats_count
            status_row.total_processed += processed_increment
            status_row.total_forwarded += forwarded_increment
            status_row.total_duplicates += duplicate_increment
            status_row.total_ignored += ignored_increment
            status_row.error_count += error_increment

        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_session_status(session_name: str = "userbot_session") -> dict:
    """Admin panelida real session holatini ko'rsatish uchun ma'lumotlarni qaytaradi."""
    session = get_session()
    try:
        row = session.query(UserbotSessionStatus).filter_by(session_name=session_name).first()
        if not row:
            return {
                "is_online": False,
                "status_badge": "⚪️ Nofaol (Oflayn)",
                "last_ping": "Hali ulanmagan",
                "connected_chats": 0,
                "total_processed": 0,
                "total_forwarded": 0,
                "total_duplicates": 0,
                "total_ignored": 0,
                "error_count": 0,
            }

        now = datetime.datetime.utcnow()
        # Agar oxirgi ping 90 soniyadan eski bo'lsa -> Oflayn
        is_online = bool(row.last_ping_at and (now - row.last_ping_at).total_seconds() < 90)
        status_badge = "🟢 ONLINE (Faol)" if is_online else "🔴 OFFLINE (To'xtagan)"

        last_ping_str = row.last_ping_at.strftime("%Y-%m-%d %H:%M:%S UTC") if row.last_ping_at else "Noma'lum"

        return {
            "is_online": is_online,
            "status_badge": status_badge,
            "last_ping": last_ping_str,
            "connected_chats": row.connected_chats_count,
            "total_processed": row.total_processed,
            "total_forwarded": row.total_forwarded,
            "total_duplicates": row.total_duplicates,
            "total_ignored": row.total_ignored,
            "error_count": row.error_count,
        }
    finally:
        session.close()


def log_error(source: str, message: str):
    """Xatolikni error_logs jadvaliga xavfsiz yozadi."""
    session = get_session()
    try:
        err = ErrorLog(source=source, message=str(message)[:2000])
        session.add(err)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()

