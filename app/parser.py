"""
Yuk e'lonlari matnidan struktura ma'lumot ajratib olish (parsing),
telefon raqamlarini to'liq aniqlash va formatlash,
hamda FAQAT yuk haqidagi xabarlarni saralash (Cargo vs Taxi/Spam classifier).
"""
import re
from dataclasses import dataclass, field
from app import geodata
from app.db import get_session

# Mashina/kuzov turlari (baza)
BASE_VEHICLE_KEYWORDS: dict[str, list[str]] = {
    "fura": ["fura", "фура", "tent", "тент", "tentlik", "tentovka", "shaland", "шаланда", "tir", "тир", "yevrofura", "еврофура"],
    "isuzu": ["isuzu", "изузу", "исузу", "isuzi", "isuzu npr", "isuzu nmr"],
    "kamaz": ["kamaz", "камаз", "man", "ман", "howo", "хово", "shacman", "шакман", "volvo", "вольво", "scania", "скания", "daf", "даф", "mercedes", "mersedes"],
    "gazel": ["gazel", "газель", "gazell", "gazelka", "gazel next", "sprinter", "спринтер", "ford", "форд"],
    "kiya": ["kiya", "кия", "kia", "hyundai", "хюндай", "hunday", "porter", "портер", "bongo", "бонго", "chaqqon"],
    "labo": ["labo", "лабо", "damas", "дамас"],
    "refrijerator": ["refrijerator", "рефрижератор", "refrigorator", "рефригоратор", "refrigirator", "refrigator", "ref", "реф", "muzlatgich", "reefer", "holodilnik", "холодильник", "termos", "термос"],
    "bortovoy": ["bortovoy", "бортовой", "bort", "борт", "ochiq", "otkritiy", "открытый", "ploshadka", "площадка"],
    "manipulyator": ["manipulyator", "манипулятор", "kran", "кран", "avtokran", "автокран"],
    "samosval": ["samosval", "самосвал"],
    "konteynerovoz": ["konteynerovoz", "контейнеровоз", "konteyner", "контейнер"],
    "avtovoz": ["avtovoz", "автовоз"],
    "tsisterna": ["tsisterna", "цистерна", "bochka", "бочка", "vodovoz"],
}

# Telefon raqamlarini topish regexi
# +998XXXXXXXXX, 998XXXXXXXXX, (90) 123-45-67, 90 123 45 67, 901234567, +7XXXXXXXXXX
_PHONE_REGEX = re.compile(
    r"(?:\+?998[\s.-]?)?\(?(?:20|33|50|55|77|88|90|91|93|94|95|97|98|99)\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}"
    r"|(?:\+?7[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2})"
    r"|(?:\b998\d{9}\b)"
    r"|(?:\b[0-9]{9}\b)"
)

# Tonnaj / Og'irlik regexi
_TONNAGE_RE = re.compile(
    r"(\d{1,3}(?:\s*[-–—]\s*\d{1,3})?(?:[.,]\d+)?)\s*(?:tonna|tona|тонна|тона|тн|tn|t\b|тонн|т\b)",
    re.IGNORECASE,
)
_KG_RE = re.compile(
    r"(\d{1,5}(?:\s*[-–—]\s*\d{1,5})?)\s*(?:kg|кг|kilogram|килограмм)",
    re.IGNORECASE,
)
_VOLUME_RE = re.compile(
    r"(\d{1,4}(?:\s*[-–—]\s*\d{1,4})?)\s*(?:kub|куб|m3|м3|m\^3|metr kub)",
    re.IGNORECASE,
)

# Narx / To'lov regexi
_PRICE_RE = re.compile(
    r"(\d{1,3}(?:[.,\s]\d{3})*|\d+)\s*(?:so['`]?m|сум|sum|dollor|dollar|usd|\$|ming|mln|mlrd)\b",
    re.IGNORECASE,
)

# Taksi / Yo'lovchi / Reklama / Spam so'zlari (Rad etish uchun)
_NON_CARGO_NEGATIVE_KEYWORDS = [
    "odam", "kishi", "passajir", "пассажир", "yolovchi", "йуловчи", "yo'lovchi", "pitak", "пятак",
    "nexia", "нексия", "cobalt", "кобальт", "gentra", "джентра", "jentra", "matiz", "матиз", "spark", "спарк",
    "monza", "онликс", "onix", "taksi", "такси", "taxi", "bilet", "билет", "joy bor", "жой бор",
    "kartaga pul", "kartadan", "kripto", "крипто", "usdt", "dollar almashtirish", "обмен валюты",
    "uy sotiladi", "kvartira", "ijara", "ishga taklif", "vakansiya", "reklama",
]

# Yuk e'loni tasdiqlovchi so'zlar
_CARGO_POSITIVE_KEYWORDS = [
    "yuk", "юк", "gruz", "груз", "tonna", "тонна", "tn", "тн", "fura", "фура", "tent", "тент",
    "isuzu", "исузу", "kamaz", "камаз", "man", "ман", "gazel", "газель", "labo", "лабо", "damas", "дамас",
    "ref", "реф", "refrijerator", "bortovoy", "manipulyator", "samosval", "konteyner", "kiya", "kia", "porter",
    "sement", "семент", "gips", "un", "ун", "meva", "мева", "sabzavot", "kartoshka", "piyoz",
    "pomidor", "tarvuz", "qovun", "gilos", "olma", "yogoch", "yog'och", "taxta", "temir",
    "armatura", "truba", "mebel", "texnika", "uskuna", "stanok", "qop", "palet", "paletta",
    "karobka", "doplata", "stavka", "dispetcher", "perevozka", "yuklash", "tushirish", "moshina", "мошина",
    "mashina", "машина", "yuk bor", "юк бор", "gruz bor", "груз есть", "mashina kerak", "машина керак",
    "fura kerak", "фура керак", "bor", "бор", "kerak", "керак", "kk", "кк",
]


@dataclass
class PhoneNumberInfo:
    raw: str
    digits: str          # Masalan: +998901234567
    formatted: str       # Masalan: +998 90 123 45 67
    tel_link: str        # Masalan: tel:+998901234567


@dataclass
class ParsedCargo:
    origin: str | None = None
    destination: str | None = None
    cargo_type: str | None = None
    vehicle_types: list[str] = field(default_factory=list)
    tonnage: str | None = None
    volume: str | None = None
    price: str | None = None
    phones: list[PhoneNumberInfo] = field(default_factory=list)
    primary_phone: str | None = None
    is_cargo: bool = True
    rejection_reason: str | None = None
    is_fully_parsed: bool = False
    google_origin_url: str | None = None
    google_dest_url: str | None = None
    google_route_url: str | None = None


def _format_uzbek_phone(digits: str) -> tuple[str, str, str]:
    """Raqamni standart +998 XX XXX XX XX formatiga keltiradi."""
    d = re.sub(r"\D", "", digits)
    if d.startswith("998") and len(d) == 12:
        clean = f"+{d}"
    elif len(d) == 9:
        clean = f"+998{d}"
    elif d.startswith("7") and len(d) == 11:
        # Rossiya/Qozog'iston
        clean = f"+{d}"
        formatted = f"+{d[0]} ({d[1:4]}) {d[4:7]}-{d[7:9]}-{d[9:11]}"
        return clean, formatted, f"tel:{clean}"
    else:
        clean = f"+{d}" if not digits.startswith("+") else digits
        return clean, digits, f"tel:{clean}"

    # O'zbekiston formati: +998 90 123 45 67
    cc = clean[1:4]     # 998
    code = clean[4:6]   # 90
    p1 = clean[6:9]     # 123
    p2 = clean[9:11]    # 45
    p3 = clean[11:13]   # 67
    formatted = f"+{cc} {code} {p1} {p2} {p3}"
    return clean, formatted, f"tel:{clean}"


def extract_phone_numbers(text: str) -> list[PhoneNumberInfo]:
    """Matndan barcha telefon raqamlarini to'g'ri formatda ajratib oladi."""
    if not text:
        return []

    found = []
    seen_digits = set()

    for match in _PHONE_REGEX.finditer(text):
        raw_val = match.group(0).strip()
        digits = re.sub(r"[^\d+]", "", raw_val)
        pure_digits = re.sub(r"\D", "", digits)

        if len(pure_digits) < 9 or len(pure_digits) > 13:
            continue

        clean, formatted, tel_link = _format_uzbek_phone(digits)
        if clean not in seen_digits:
            seen_digits.add(clean)
            found.append(PhoneNumberInfo(
                raw=raw_val,
                digits=clean,
                formatted=formatted,
                tel_link=tel_link,
            ))

    return found


def classify_cargo(text: str, origin: str | None, destination: str | None,
                   vehicle_types: list[str], tonnage: str | None) -> tuple[bool, str | None]:
    """
    Xabar FAQAT yuk haqida ekanligini qat'iy tekshiradi.
    Taksi, yo'lovchi, reklama va boshqa spam xabarlarni rad etadi.
    """
    norm_text = geodata.normalize(text)

    # 1. Taksi / yo'lovchi so'zlari tekshiruvi (Negative check)
    for kw in _NON_CARGO_NEGATIVE_KEYWORDS:
        norm_kw = geodata.normalize(kw)
        if re.search(rf"\b{re.escape(norm_kw)}\b", norm_text):
            # Istisno: agar xabarda katta tonnaj yoki og'ir yuk mashinasi aniq bo'lsa
            if tonnage or any(v in ("fura", "kamaz", "isuzu", "refrijerator", "samosval") for v in vehicle_types):
                # Lekin agar "4 kishi", "odam olamiz", "pitak" aniq taksi bo'lsa
                if any(re.search(rf"\b{re.escape(p)}\b", norm_text) for p in ("kishi", "odam", "pitak", "taksi", "taxi", "bilet")):
                    return False, f"Taksi/Yo'lovchi e'loni ({kw})"
                continue
            return False, f"Taksi/Yo'lovchi yoki Spam e'loni ({kw})"

    # 2. Xabar juda qisqa yoki bema'ni bo'lsa
    if len(text.strip()) < 10:
        return False, "Matn juda qisqa"

    # 3. Ijobiy yuk signallari (Positive cargo check)
    has_cargo_keyword = any(re.search(rf"\b{re.escape(geodata.normalize(kw))}\b", norm_text) for kw in _CARGO_POSITIVE_KEYWORDS)
    has_route = bool(origin and destination)
    has_vehicle = bool(vehicle_types)
    has_tonnage = bool(tonnage)
    has_phone = bool(extract_phone_numbers(text))

    if has_cargo_keyword:
        return True, None

    if has_route and (has_vehicle or has_tonnage or has_phone):
        return True, None

    if has_vehicle and (has_tonnage or has_phone or origin or destination):
        return True, None

    if has_tonnage and (has_route or has_phone or origin or destination):
        return True, None

    if has_route:
        return True, None

    return False, "Yuk haqida ma'lumot topilmadi"


import time

_VEHICLE_KEYWORDS_CACHE: dict[str, list[str]] = dict(BASE_VEHICLE_KEYWORDS)
_LAST_VEHICLE_REFRESH = 0.0


def _get_active_vehicle_keywords() -> dict[str, list[str]]:
    """Baza va DB'dagi mashina rusumlarini xotirada keshlab birlashtiradi."""
    global _VEHICLE_KEYWORDS_CACHE, _LAST_VEHICLE_REFRESH
    now = time.time()
    if now - _LAST_VEHICLE_REFRESH > 30.0:
        combined = dict(BASE_VEHICLE_KEYWORDS)
        try:
            session = get_session()
            try:
                from app.models import CustomVehicle
                rows = session.query(CustomVehicle).filter_by(is_active=True).all()
                for r in rows:
                    key = r.name.lower().strip()
                    syns = [s.strip() for s in (r.synonyms or "").split(",") if s.strip()]
                    syns.append(key)
                    combined[key] = syns
                _VEHICLE_KEYWORDS_CACHE = combined
                _LAST_VEHICLE_REFRESH = now
            finally:
                session.close()
        except Exception:
            pass
    return _VEHICLE_KEYWORDS_CACHE


def _extract_locations(norm_text: str) -> tuple[str | None, str | None]:
    """Yo'nalishlarni (origin, destination) ishonchli ajratib oladi."""
    # 1-urinish: Ajratgich belgilar (-, ->, ➔, =>, /, dan ... ga)
    dash_match = re.search(
        r"\b([a-z0-9]+(?:dan)?)\s*(?:[-–—➔→>]|\bto\b|\bga\b|\/)\s*([a-z0-9]+(?:ga|gacha)?)\b",
        norm_text
    )
    if dash_match:
        w1, w2 = dash_match.group(1), dash_match.group(2)
        r1, r2 = geodata.region_of(w1), geodata.region_of(w2)
        if r1 and r2 and (r1 != r2 or w1 != w2):
            return geodata.canonical_city_name(w1), geodata.canonical_city_name(w2)

    # 2-urinish: 'X dan Y ga' qolipi
    from_to_match = re.search(
        r"\b([a-z0-9]+)\s*dan\b.*?\b([a-z0-9]+)\s*(?:ga|gacha|bozoriga|markaziga|tomon)\b",
        norm_text
    )
    if from_to_match:
        w1, w2 = from_to_match.group(1), from_to_match.group(2)
        r1, r2 = geodata.region_of(w1), geodata.region_of(w2)
        if r1 and r2:
            return geodata.canonical_city_name(w1), geodata.canonical_city_name(w2)

    # 3-urinish: So'zma-so'z skan qilish (barcha shahar tokenlarini tartib bilan yig'ish)
    tokens = norm_text.split()
    found_locations: list[tuple[str, str]] = []
    for token in tokens:
        reg = geodata.region_of(token)
        if reg:
            canon = geodata.canonical_city_name(token)
            if not found_locations or found_locations[-1][0] != canon:
                found_locations.append((canon, reg))

    if len(found_locations) >= 2:
        return found_locations[0][0], found_locations[1][0]
    elif len(found_locations) == 1:
        return found_locations[0][0], None

    return None, None


def _extract_vehicle_types(norm_text: str) -> list[str]:
    """Matndan talab qilinadigan transport turlarini aniqlaydi."""
    vehicle_keywords = _get_active_vehicle_keywords()
    found = []
    for canonical, synonyms in vehicle_keywords.items():
        for syn in synonyms:
            syn_norm = geodata.normalize(syn)
            if not syn_norm:
                continue
            # Faqat to'liq so'z sifatida tekshirish (\b...\b)
            if re.search(rf"\b{re.escape(syn_norm)}\b", norm_text):
                if canonical not in found:
                    found.append(canonical)
                break
    return found


def _extract_tonnage(original_text: str) -> str | None:
    """Tonnaj yoki og'irlikni ajratadi."""
    m_ton = _TONNAGE_RE.search(original_text)
    if m_ton:
        val = m_ton.group(1).replace(" ", "")
        return f"{val} tonna"

    m_kg = _KG_RE.search(original_text)
    if m_kg:
        val = m_kg.group(1).replace(" ", "")
        return f"{val} kg"

    return None


def _extract_volume(original_text: str) -> str | None:
    """Yuk hajmini (kub/m3) ajratadi."""
    m_vol = _VOLUME_RE.search(original_text)
    if m_vol:
        val = m_vol.group(1).replace(" ", "")
        return f"{val} m³"
    return None


def _extract_price(original_text: str) -> str | None:
    """Narx yoki stavkani ajratadi."""
    m_price = _PRICE_RE.search(original_text)
    if m_price:
        return m_price.group(0).strip()
    norm = geodata.normalize(original_text)
    if "kelishiladi" in norm or "kelishamiz" in norm:
        return "Kelishilgan narxda"
    if "naqd" in norm:
        return "Naqd to'lov"
    return None


def _extract_cargo_type(norm_text: str, origin: str | None, destination: str | None) -> str | None:
    """Yuk tavsifini (tovar/mahsulot nomini) aniqlaydi."""
    known_cargo_commodities = [
        "sement", "gips", "un", "meva", "sabzavot", "kartoshka", "piyoz", "pomidor",
        "tarvuz", "qovun", "gilos", "olma", "uzum", "shaftoli", "yogoch", "taxta",
        "temir", "armatura", "truba", "mebel", "texnika", "uskuna", "stanok", "qop",
        "palet", "karobka", "osh tuzi", "shakar", "paxta", "mato", "kiyim", "stroy material",
        "qurilish mollari", "plastik", "shisha", "kabellar", "metall", "kochir", "penoplast",
    ]
    for comm in known_cargo_commodities:
        if comm in norm_text:
            return comm.title()

    tokens = norm_text.split()
    known_city_tokens = set(geodata.all_known_city_tokens())
    marker_words = {
        "dan", "ga", "bozoriga", "bozori", "bor", "kerak", "keladigan",
        "olib", "ketadi", "ketadigan", "yol", "yoli", "tonna", "tona", "yuk", "gruz",
        "ta", "mashina", "moahna", "kk", "som", "sum", "dollor", "naqd", "karta", "kub", "m3",
    }
    candidates = [
        w for w in tokens
        if w not in known_city_tokens and not geodata.region_of(w) and w not in marker_words
        and not w.isdigit() and len(w) >= 3
    ]
    return candidates[0].title() if candidates else None


def parse_message(text: str) -> ParsedCargo:
    """Asosiy parsing va tasniflash funksiyasi."""
    if not text or not text.strip():
        return ParsedCargo(is_cargo=False, rejection_reason="Bo'sh matn")

    norm_text = geodata.normalize(text)

    origin, destination = _extract_locations(norm_text)
    vehicle_types = _extract_vehicle_types(norm_text)
    tonnage = _extract_tonnage(text)
    volume = _extract_volume(text)
    price = _extract_price(text)
    phones = extract_phone_numbers(text)
    primary_phone = phones[0].formatted if phones else None
    cargo_type = _extract_cargo_type(norm_text, origin, destination)

    is_cargo, reason = classify_cargo(text, origin, destination, vehicle_types, tonnage)
    fully_parsed = bool(is_cargo and origin and destination)

    # Google Maps URL manzillari
    google_origin_url = geodata.google_maps_search_url(origin) if origin else None
    google_dest_url = geodata.google_maps_search_url(destination) if destination else None
    google_route_url = geodata.google_maps_route_url(origin, destination) if (origin and destination) else None

    return ParsedCargo(
        origin=origin,
        destination=destination,
        cargo_type=cargo_type,
        vehicle_types=vehicle_types,
        tonnage=tonnage,
        volume=volume,
        price=price,
        phones=phones,
        primary_phone=primary_phone,
        is_cargo=is_cargo,
        rejection_reason=reason,
        is_fully_parsed=fully_parsed,
        google_origin_url=google_origin_url,
        google_dest_url=google_dest_url,
        google_route_url=google_route_url,
    )


