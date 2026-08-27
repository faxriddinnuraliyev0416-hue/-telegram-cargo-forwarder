"""
30 kundan (yoki .env'dagi MESSAGE_RETENTION_DAYS) eski xabarlarni DB'dan tozalaydi.
Cron orqali kuniga bir marta ishga tushirish tavsiya etiladi (README'ga qarang).

Ishga tushirish: python -m scripts.cleanup_old_messages
"""
import datetime
from app import config
from app.db import get_session
from app.models import CargoMessage, ErrorLog

if __name__ == "__main__":
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=config.MESSAGE_RETENTION_DAYS)
    session = get_session()
    try:
        deleted_messages = session.query(CargoMessage).filter(CargoMessage.created_at < cutoff).delete()
        deleted_errors = session.query(ErrorLog).filter(ErrorLog.created_at < cutoff).delete()
        session.commit()
        print(f"✅ Tozalandi: {deleted_messages} ta xabar, {deleted_errors} ta error log ({config.MESSAGE_RETENTION_DAYS} kundan eski).")
    finally:
        session.close()
