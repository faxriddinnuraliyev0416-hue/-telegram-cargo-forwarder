"""
Database'ni ishga tayyorlash skripti.
Ishga tushirish: python -m scripts.init_db
Bu barcha jadvallarni (agar mavjud bo'lmasa) yaratadi.
"""
from app.db import init_db

if __name__ == "__main__":
    init_db()
    print("[SUCCESS] Database jadvallari tayyor.")

