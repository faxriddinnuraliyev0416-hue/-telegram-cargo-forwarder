"""
Xabarlarni professional va qulay formatda shakllantirish:
- Google Maps orqali shahar va marshrut havolalari
- Telefon raqamlarini to'g'ri 'tel:' va nusxalanadigan 'code' ko'rinishida chiqarish
- Mashina turi, tonnaj, narx va tovar tavsifini ko'rgazmali ajratish
"""
import html
from app import geodata

TELEGRAM_TEXT_LIMIT = 4096


def truncate_escaped_text(text: str, max_length: int) -> str:
    """HTML-escape qilingan matn Telegram limitidan oshmasligini ta'minlaydi."""
    if max_length <= 0:
        return ""
    text = text or ""
    escaped = html.escape(text)
    if len(escaped) <= max_length:
        return escaped

    suffix = "…"
    low, high = 0, len(text)
    available = max_length - len(suffix)
    while low < high:
        middle = (low + high + 1) // 2
        if len(html.escape(text[:middle])) <= available:
            low = middle
        else:
            high = middle - 1
    return f"{html.escape(text[:low])}{suffix}"


def build_source_line(title: str, username: str | None) -> str:
    safe_title = html.escape(title or "Noma'lum manba")
    if username:
        return f'📡 <b>Manba:</b> <a href="https://t.me/{username}">{safe_title}</a>'
    return f"📡 <b>Manba:</b> {safe_title}"


def build_sender_line(name: str | None, username: str | None, user_id: int | None) -> str:
    display_name = html.escape(name or "Yuboruvchi")
    if username:
        return f'👤 <b>Yuboruvchi:</b> <a href="https://t.me/{username}">@{username}</a>'
    if user_id:
        return f'👤 <b>Yuboruvchi:</b> <a href="tg://user?id={user_id}">{display_name}</a>'
    return f"👤 <b>Yuboruvchi:</b> {display_name}"


def format_phone_lines(phones) -> str:
    """Telefon raqamlarini bosiladigan (tel:) va nusxalash oson (code) ko'rinishda chiqaradi."""
    if not phones:
        return ""
    lines = []
    for p in phones:
        # p obyekti PhoneNumberInfo yoki str bo'lishi mumkin
        if hasattr(p, "formatted"):
            lines.append(f'📞 <a href="{p.tel_link}">{html.escape(p.formatted)}</a> <code>{p.digits}</code>')
        elif isinstance(p, str):
            clean_digits = p.replace(" ", "").replace("-", "")
            lines.append(f'📞 <a href="tel:{clean_digits}">{html.escape(p)}</a> <code>{clean_digits}</code>')
    return "\n".join(lines)


def build_forwarded_message(
    source_title: str,
    source_username: str | None,
    sender_name: str | None,
    sender_username: str | None,
    sender_id: int | None,
    original_text: str,
    origin: str | None = None,
    destination: str | None = None,
    vehicle_types: list[str] | None = None,
    tonnage: str | None = None,
    volume: str | None = None,
    cargo_type: str | None = None,
    price: str | None = None,
    phones: list | None = None,
) -> str:
    """Asosiy guruhga forward qilinadigan chiroyli, to'liq yuk kartochkasi."""
    parts = ["🚚 <b>YUK E'LONI</b>", "━━━━━━━━━━━━━━━━━━━━"]

    # 1. Lokatsiya va Marshrut (Google Maps)
    if origin and destination:
        orig_map_url = geodata.google_maps_search_url(origin)
        dest_map_url = geodata.google_maps_search_url(destination)
        route_map_url = geodata.google_maps_route_url(origin, destination)

        parts.append(
            f'📍 <b>Qayerdan:</b> <a href="{orig_map_url}">{html.escape(origin)}</a>\n'
            f'🏁 <b>Qayerga:</b> <a href="{dest_map_url}">{html.escape(destination)}</a>'
        )
        if route_map_url:
            parts.append(f'🗺 <a href="{route_map_url}">Marshrutni xaritada ochish (Google Maps) ↗️</a>')
        parts.append("━━━━━━━━━━━━━━━━━━━━")
    elif origin:
        orig_map_url = geodata.google_maps_search_url(origin)
        parts.append(f'📍 <b>Qayerdan:</b> <a href="{orig_map_url}">{html.escape(origin)}</a>')
        parts.append("━━━━━━━━━━━━━━━━━━━━")

    # 2. Yuk ma'lumotlari
    details = []
    if cargo_type:
        details.append(f"📦 <b>Yuk turi:</b> {html.escape(cargo_type)}")
    if tonnage:
        details.append(f"⚖️ <b>Og'irligi:</b> {html.escape(tonnage)}")
    if volume:
        details.append(f"📐 <b>Hajmi:</b> {html.escape(volume)}")
    if vehicle_types:
        vehicles_str = ", ".join(vehicle_types).title()
        details.append(f"🚛 <b>Transport:</b> {html.escape(vehicles_str)}")
    if price:
        details.append(f"💰 <b>Narxi / To'lov:</b> {html.escape(price)}")

    if details:
        parts.extend(details)
        parts.append("━━━━━━━━━━━━━━━━━━━━")

    # 3. Aloqa va Manba
    phone_text = format_phone_lines(phones)
    if phone_text:
        parts.append(phone_text)

    sender_line = build_sender_line(sender_name, sender_username, sender_id)
    source_line = build_source_line(source_title, source_username)
    parts.append(sender_line)
    parts.append(source_line)
    parts.append("━━━━━━━━━━━━━━━━━━━━")

    # 4. Original matn
    header = "\n".join(parts)
    body_max_len = TELEGRAM_TEXT_LIMIT - len(header) - 30
    if body_max_len > 100:
        escaped_body = truncate_escaped_text(original_text or "", body_max_len)
        return f"{header}\n📝 <i>Asl e'lon:</i>\n{escaped_body}"

    return header


def build_dm_match_message(
    origin: str | None,
    destination: str | None,
    vehicle_types: list[str] | None,
    tonnage: str | None,
    volume: str | None,
    cargo_type: str | None,
    price: str | None,
    phones: list | None,
    source_title: str,
    source_username: str | None,
    sender_name: str | None,
    sender_username: str | None,
    sender_id: int | None,
    original_text: str,
) -> str:
    """Foydalanuvchiga shaxsiy xabar (DM notification) uchun moslik xabari."""
    parts = ["🚨 <b>FILTRINGIZGA MOS YUK TOPILDI!</b>", "━━━━━━━━━━━━━━━━━━━━"]

    if origin and destination:
        orig_map_url = geodata.google_maps_search_url(origin)
        dest_map_url = geodata.google_maps_search_url(destination)
        route_map_url = geodata.google_maps_route_url(origin, destination)
        parts.append(
            f'📍 <b>Yo\'nalish:</b> <a href="{orig_map_url}">{html.escape(origin)}</a> ➔ <a href="{dest_map_url}">{html.escape(destination)}</a>'
        )
        if route_map_url:
            parts.append(f'🗺 <a href="{route_map_url}">Marshrut xaritasi ↗️</a>')
        parts.append("━━━━━━━━━━━━━━━━━━━━")

    details = []
    if cargo_type:
        details.append(f"📦 <b>Yuk turi:</b> {html.escape(cargo_type)}")
    if tonnage:
        details.append(f"⚖️ <b>Tonnaj:</b> {html.escape(tonnage)}")
    if volume:
        details.append(f"📐 <b>Hajm:</b> {html.escape(volume)}")
    if vehicle_types:
        details.append(f"🚛 <b>Mashina:</b> {html.escape(', '.join(vehicle_types).title())}")
    if price:
        details.append(f"💰 <b>Narx:</b> {html.escape(price)}")

    if details:
        parts.extend(details)
        parts.append("━━━━━━━━━━━━━━━━━━━━")

    phone_text = format_phone_lines(phones)
    if phone_text:
        parts.append(phone_text)

    parts.append(build_sender_line(sender_name, sender_username, sender_id))
    parts.append(build_source_line(source_title, source_username))
    parts.append("━━━━━━━━━━━━━━━━━━━━")

    header = "\n".join(parts)
    body_max_len = TELEGRAM_TEXT_LIMIT - len(header) - 30
    if body_max_len > 100:
        escaped_body = truncate_escaped_text(original_text or "", body_max_len)
        return f"{header}\n📝 <i>Original matn:</i>\n{escaped_body}"

    return header

