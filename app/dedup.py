"""
Duplicate detection.

Foydalanuvchi javobi (6-savol): "matn bir hil bo'lganida duplikat deb
hisoblansin" — ya'ni original xabar matni deyarli bir xil bo'lsa, bu
duplicate hisoblanadi (turli manbalardan kelgan bo'lsa ham).

Matn solishtirishdan oldin bo'sh joy/registr farqlari, telefon raqamlar va
tinish belgilaridagi arzimas farqlar ta'sir qilmasligi uchun matn
normalizatsiya qilinadi, keyin SHA-256 xesh hisoblanadi.
"""
import hashlib
import re

_PHONE_RE = re.compile(r"[\+]?\d[\d\s().-]{6,}\d")
_WS_RE = re.compile(r"\s+")


def normalize_for_dedup(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    # telefon raqamlarni olib tashlaymiz — chunki bir xil e'lon ba'zan turli
    # raqam formatida qayta yuborilishi mumkin, lekin matn mazmuni bir xil
    t = _PHONE_RE.sub(" ", t)
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = _WS_RE.sub(" ", t).strip()
    return t


def compute_hash(text: str) -> str:
    normalized = normalize_for_dedup(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
