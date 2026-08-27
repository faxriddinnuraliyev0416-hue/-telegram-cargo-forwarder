"""
Interaktiv Admin Panel (Tugmali boshqaruv tizimi).
Funksiyalari:
1. 📡 Manba kanallarni qo'shish, o'chirish, faol/nofaol qilish.
2. 🏙 Shaharlar va tumanlarni kiritish va chiqarish (dinamik geodata).
3. 🚛 Mashina rusumlarini kiritish va chiqarish.
4. ⚖️ Yuk hajmi va tonnajlarini kiritish va chiqarish.
5. ⚡️ Real Session Monitoring paneli (Userbot holati, oxirgi ping, statistika).
6. 📊 Umumiy statistika va xatolar jurnali.
"""
from functools import wraps
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, filters,
)

from app import config, geodata
from app.db import get_session
from app.models import (
    User, CargoFilter, SourceChat, CargoMessage, ErrorLog,
    CustomCity, CustomVehicle, CustomTonnage, ProcessingStatus, SourceType,
)
from app.services.session_service import get_session_status

# ConversationHandler holatlari
ADMIN_ADD_CHANNEL, ADMIN_ADD_CITY, ADMIN_ADD_VEHICLE, ADMIN_ADD_TONNAGE = range(4)

ADMIN_REPLY_BUTTON = "⚙️ Admin Panel"


def is_admin_user(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshiradi."""
    if user_id in config.ADMIN_IDS:
        return True
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        return bool(user and user.is_admin)
    finally:
        session.close()


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not is_admin_user(user.id):
            if update.callback_query:
                await update.callback_query.answer("⛔️ Bu bo'lim faqat adminlar uchun!", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔️ Bu buyruq faqat adminlar uchun.")
            return
        return await func(update, context)
    return wrapper


def _admin_main_keyboard() -> InlineKeyboardMarkup:
    """Asosiy admin paneli inline menyusi."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📡 Kanallar va Guruhlar", callback_data="admin:channels"),
            InlineKeyboardButton("🏙 Shaharlar va Tumanlar", callback_data="admin:cities"),
        ],
        [
            InlineKeyboardButton("🚛 Mashina Rusumlari", callback_data="admin:vehicles"),
            InlineKeyboardButton("⚖️ Yuk Hajmlari / Tonnaj", callback_data="admin:tonnages"),
        ],
        [
            InlineKeyboardButton("⚡️ Real Session Monitoring", callback_data="admin:session"),
            InlineKeyboardButton("📊 Umumiy Statistika", callback_data="admin:stats"),
        ],
        [
            InlineKeyboardButton("🐞 Xatolar Jurnali", callback_data="admin:errors"),
            InlineKeyboardButton("🧹 Keshni Tozalash", callback_data="admin:clear_cache"),
        ],
        [
            InlineKeyboardButton("❌ Panelni yopish", callback_data="admin:close"),
        ],
    ])


@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel bosh menyusini chiqaradi."""
    text = (
        "🛠 <b>Boshqaruv Paneli (Admin Panel)</b>\n"
        "Xush kelibsiz, Haydarbek! Barcha operatsiyalarni quyidagi tugmalar orqali boshqarishingiz mumkin:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=_admin_main_keyboard())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=_admin_main_keyboard())


# ============================================================
# 1. KANALLAR VA GURUHLAR BOSHQARUVI
# ============================================================

async def _show_channels_menu(target, is_callback=True):
    session = get_session()
    try:
        channels = session.query(SourceChat).all()
        lines = [f"📡 <b>Kuzatilayotgan manba kanallar ({len(channels)} ta):</b>\n"]
        for c in channels:
            status = "🟢 Faol" if c.active else "⚪️ To'xtatilgan"
            uname = f"@{c.username}" if c.username else (c.invite_link or f"id:{c.chat_id}")
            lines.append(f"• <b>{c.title}</b> ({uname})\n  Holati: {status} | Xabarlar: {c.message_count}")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Yangi kanal qo'shish", callback_data="admin:add_channel_start")],
            [
                InlineKeyboardButton("🔄 Faollikni o'zgartirish", callback_data="admin:toggle_channel_list"),
                InlineKeyboardButton("🗑 Kanalni o'chirish", callback_data="admin:delete_channel_list"),
            ],
            [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")],
        ])

        msg_text = "\n".join(lines) if channels else "📡 Hozircha hech qanday kanal ulanmagan."
        if is_callback:
            await target.edit_message_text(msg_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await target.reply_text(msg_text, parse_mode="HTML", reply_markup=keyboard)
    finally:
        session.close()


@admin_only
async def channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _show_channels_menu(query)


async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kanal qo'shish so'rovini boshlaydi."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text(
            "➕ <b>Yangi manba kanal qo'shish:</b>\n\n"
            "Kanal username (@yuk_markazi), havolasi (https://t.me/...) yoki Chat ID sini yuboring:\n\n"
            "<i>Bekor qilish uchun /cancel deb yozing.</i>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "➕ <b>Yangi manba kanal username yoki havolasini yuboring:</b>",
            parse_mode="HTML",
        )
    return ADMIN_ADD_CHANNEL


async def add_channel_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/cancel") or text == "❌ Bekor qilish":
        await update.message.reply_text("Kanal qo'shish bekor qilindi.", reply_markup=_admin_main_keyboard())
        return ConversationHandler.END

    # Username yoki linkdan tozalash
    clean_username = text.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "").strip()
    title = clean_username.title()

    session = get_session()
    try:
        # Chat ID dummy yoki link sifatida
        chat_id_val = hash(clean_username) % (10**12)  # Vaqtinchalik unikal identifikator
        existing = session.query(SourceChat).filter(
            (SourceChat.username == clean_username) | (SourceChat.title == title)
        ).first()

        if existing:
            await update.message.reply_text(f"⚠️ Bu kanal allaqachon mavjud: {existing.title}")
        else:
            new_chat = SourceChat(
                chat_id=-1000000000000 + abs(chat_id_val),
                title=title,
                username=clean_username if not clean_username.startswith("+") else None,
                invite_link=text if clean_username.startswith("+") else None,
                type=SourceType.CHANNEL,
                active=True,
            )
            session.add(new_chat)
            session.commit()
            await update.message.reply_text(f"✅ <b>Kanal muvaffaqiyatli qo'shildi:</b> {title}", parse_mode="HTML")
    except Exception as e:
        session.rollback()
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {e}")
    finally:
        session.close()

    await _show_channels_menu(update.message, is_callback=False)
    return ConversationHandler.END


# ============================================================
# 2. SHAHARLAR VA TUMANLAR BOSHQARUVI
# ============================================================

async def _show_cities_menu(target, is_callback=True):
    session = get_session()
    try:
        custom_cities = session.query(CustomCity).filter_by(is_active=True).all()
        lines = [
            "🏙 <b>Shaharlar va Hududlar boshqaruvi:</b>\n",
            f"Standart viloyatlar: <b>14 ta</b> (200+ tumanlar)",
            f"Qo'shimcha kiritilgan shaharlar: <b>{len(custom_cities)} ta</b>\n",
        ]
        if custom_cities:
            lines.append("<b>Qo'shimcha shaharlar:</b>")
            for cc in custom_cities:
                lines.append(f"• {cc.name} ({cc.region})")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Yangi shahar kiritish", callback_data="admin:add_city_start")],
            [InlineKeyboardButton("🗑 Shaharni chiqarish (o'chirish)", callback_data="admin:delete_city_list")],
            [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")],
        ])

        msg_text = "\n".join(lines)
        if is_callback:
            await target.edit_message_text(msg_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await target.reply_text(msg_text, parse_mode="HTML", reply_markup=keyboard)
    finally:
        session.close()


@admin_only
async def cities_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _show_cities_menu(query)


async def add_city_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text(
            "➕ <b>Yangi shahar yoki tuman kiritish:</b>\n\n"
            "Format: <code>Shahar nomi, Viloyati</code>\n"
            "Masalan: <code>Angren, Toshkent</code> yoki <code>Zomin, Jizzax</code>\n\n"
            "<i>Bekor qilish uchun /cancel deb yozing.</i>",
            parse_mode="HTML",
        )
    return ADMIN_ADD_CITY


async def add_city_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/cancel"):
        await update.message.reply_text("Bekor qilindi.")
        return ConversationHandler.END

    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) < 2:
        await update.message.reply_text("⚠️ Noto'g'ri format. Iltimos: <code>Shahar, Viloyat</code> ko'rinishida yuboring.")
        return ADMIN_ADD_CITY

    city_name, region_name = parts[0], parts[1]
    session = get_session()
    try:
        existing = session.query(CustomCity).filter_by(name=city_name).first()
        if existing:
            existing.region = region_name
            existing.is_active = True
        else:
            new_c = CustomCity(name=city_name, region=region_name, is_active=True)
            session.add(new_c)
        session.commit()
        geodata.reload_geodata()
        await update.message.reply_text(f"✅ <b>Shahar muvaffaqiyatli saqlandi:</b> {city_name} ➔ {region_name}", parse_mode="HTML")
    finally:
        session.close()

    await _show_cities_menu(update.message, is_callback=False)
    return ConversationHandler.END


# ============================================================
# 3. MASHINA RUSUMLARI BOSHQARUVI
# ============================================================

async def _show_vehicles_menu(target, is_callback=True):
    session = get_session()
    try:
        custom_vehicles = session.query(CustomVehicle).filter_by(is_active=True).all()
        lines = [
            "🚛 <b>Mashina Rusumlari boshqaruvi:</b>\n",
            "Baza rusumlari: Fura, Isuzu, Kamaz, MAN, Gazel, Kiya, Labo, Damas, Refrijerator, Bortovoy, Manipulyator, Samosval, Konteynerovoz, Avtovoz",
            f"Qo'shimcha rusumlar: <b>{len(custom_vehicles)} ta</b>\n",
        ]
        if custom_vehicles:
            for cv in custom_vehicles:
                lines.append(f"• <b>{cv.name}</b> (sinonimlar: {cv.synonyms or 'yoq'})")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Yangi rusum kiritish", callback_data="admin:add_vehicle_start")],
            [InlineKeyboardButton("🗑 Rusumni chiqarish (o'chirish)", callback_data="admin:delete_vehicle_list")],
            [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")],
        ])

        msg_text = "\n".join(lines)
        if is_callback:
            await target.edit_message_text(msg_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await target.reply_text(msg_text, parse_mode="HTML", reply_markup=keyboard)
    finally:
        session.close()


@admin_only
async def vehicles_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _show_vehicles_menu(query)


async def add_vehicle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text(
            "➕ <b>Yangi mashina rusumini kiritish:</b>\n\n"
            "Format: <code>Rusum nomi, sinonim1, sinonim2</code>\n"
            "Masalan: <code>Chaqqon, chaqqon, shaqqon, labo katta</code>\n\n"
            "<i>Bekor qilish uchun /cancel deb yozing.</i>",
            parse_mode="HTML",
        )
    return ADMIN_ADD_VEHICLE


async def add_vehicle_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/cancel"):
        await update.message.reply_text("Bekor qilindi.")
        return ConversationHandler.END

    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        await update.message.reply_text("⚠️ Rusum nomini kiriting.")
        return ADMIN_ADD_VEHICLE

    v_name = parts[0]
    synonyms_str = ", ".join(parts[1:]) if len(parts) > 1 else v_name

    session = get_session()
    try:
        existing = session.query(CustomVehicle).filter_by(name=v_name).first()
        if existing:
            existing.synonyms = synonyms_str
            existing.is_active = True
        else:
            new_v = CustomVehicle(name=v_name, synonyms=synonyms_str, is_active=True)
            session.add(new_v)
        session.commit()
        await update.message.reply_text(f"✅ <b>Mashina rusumi saqlandi:</b> {v_name}", parse_mode="HTML")
    finally:
        session.close()

    await _show_vehicles_menu(update.message, is_callback=False)
    return ConversationHandler.END


# ============================================================
# 4. YUK HAJMI VA TONNAJ BOSHQARUVI
# ============================================================

async def _show_tonnages_menu(target, is_callback=True):
    session = get_session()
    try:
        custom_tonnages = session.query(CustomTonnage).filter_by(is_active=True).all()
        lines = [
            "⚖️ <b>Yuk Hajmi va Tonnaj boshqaruvi:</b>\n",
            "Baza variantlari: 1-3 tonna, 5 tonna, 10 tonna, 20-24 tonna, Kub/m³",
            f"Qo'shimcha tonnajlar: <b>{len(custom_tonnages)} ta</b>\n",
        ]
        if custom_tonnages:
            for ct in custom_tonnages:
                lines.append(f"• {ct.label}")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Yangi hajm/tonnaj kiritish", callback_data="admin:add_tonnage_start")],
            [InlineKeyboardButton("🗑 Tonnajni chiqarish (o'chirish)", callback_data="admin:delete_tonnage_list")],
            [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")],
        ])

        msg_text = "\n".join(lines)
        if is_callback:
            await target.edit_message_text(msg_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await target.reply_text(msg_text, parse_mode="HTML", reply_markup=keyboard)
    finally:
        session.close()


@admin_only
async def tonnages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _show_tonnages_menu(query)


async def add_tonnage_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text(
            "➕ <b>Yangi yuk hajmi yoki tonnaj kiritish:</b>\n\n"
            "Masalan: <code>30 - 35 tonna (Katta yuk)</code> yoki <code>50 m³ (Kub)</code>\n\n"
            "<i>Bekor qilish uchun /cancel deb yozing.</i>",
            parse_mode="HTML",
        )
    return ADMIN_ADD_TONNAGE


async def add_tonnage_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/cancel"):
        await update.message.reply_text("Bekor qilindi.")
        return ConversationHandler.END

    session = get_session()
    try:
        existing = session.query(CustomTonnage).filter_by(label=text).first()
        if existing:
            existing.is_active = True
        else:
            new_t = CustomTonnage(label=text, is_active=True)
            session.add(new_t)
        session.commit()
        await update.message.reply_text(f"✅ <b>Tonnaj saqlandi:</b> {text}", parse_mode="HTML")
    finally:
        session.close()

    await _show_tonnages_menu(update.message, is_callback=False)
    return ConversationHandler.END


# ============================================================
# 5. REAL SESSION MONITORING PANEL
# ============================================================

@admin_only
async def session_monitoring_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    status = get_session_status()

    text = (
        "⚡️ <b>REAL SESSION MONITORING PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔌 <b>Userbot Holati:</b> {status['status_badge']}\n"
        f"🕒 <b>Oxirgi Ping:</b> {status['last_ping']}\n"
        f"📡 <b>Ulangan Chatlar:</b> {status['connected_chats']} ta\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 <b>Jami kelgan xabarlar:</b> {status['total_processed']}\n"
        f"🚚 <b>Forward qilingan yuklar:</b> {status['total_forwarded']}\n"
        f"🚫 <b>O'tkazib yuborilgan (taksi/spam):</b> {status['total_ignored']}\n"
        f"🔁 <b>Duplikatlar:</b> {status['total_duplicates']}\n"
        f"⚠️ <b>Qayd etilgan xatolar:</b> {status['error_count']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Holat har 30 soniyada avtomatik sinxronlanadi.</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Yangilash", callback_data="admin:session_refresh")],
        [InlineKeyboardButton("🧹 Keshni Tozalash", callback_data="admin:clear_cache")],
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")],
    ])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


# ============================================================
# 6. STATISTIKA VA XATOLIKLAR JURNALI
# ============================================================

@admin_only
async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    session = get_session()
    try:
        total_messages = session.query(CargoMessage).count()
        parsed = session.query(CargoMessage).filter_by(status=ProcessingStatus.PARSED).count()
        failed = session.query(CargoMessage).filter_by(status=ProcessingStatus.PARSE_FAILED).count()
        duplicates = session.query(CargoMessage).filter_by(status=ProcessingStatus.DUPLICATE).count()
        ignored = session.query(CargoMessage).filter_by(status=ProcessingStatus.IGNORED).count()
        users_count = session.query(User).count()
        active_filters = session.query(CargoFilter).filter_by(active=True).count()
        sources_count = session.query(SourceChat).filter_by(active=True).count()

        text = (
            "📊 <b>Batafsil Tizim Statistikasi:</b>\n\n"
            f"📥 Jami xabarlar: <b>{total_messages}</b>\n"
            f"✅ Yuk sifatida parse qilingan: <b>{parsed}</b>\n"
            f"🚫 Rad etilgan (taksi/spam): <b>{ignored}</b>\n"
            f"⚠️ Parse qilinmagan: <b>{failed}</b>\n"
            f"🔁 Duplikat: <b>{duplicates}</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{users_count}</b>\n"
            f"🔎 Faol yuk filtrlari: <b>{active_filters}</b>\n"
            f"📡 Faol kuzatuv kanallari: <b>{sources_count}</b>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin:stats")],
            [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")],
        ])

        if query:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    finally:
        session.close()


@admin_only
async def errors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    session = get_session()
    try:
        rows = session.query(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(10).all()
        if not rows:
            text = "🐞 <b>Xatolar Jurnali:</b>\n\nHozircha tizimda hech qanday xatolik qayd etilmagan. 🎉"
        else:
            lines = [f"🐞 <b>Oxirgi {len(rows)} ta xatolik:</b>\n"]
            for e in rows:
                lines.append(f"• <code>[{e.created_at:%d.%m %H:%M}]</code> <b>{e.source}:</b> {e.message[:120]}")
            text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Xatolarni tozalash", callback_data="admin:clear_errors_do")],
            [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")],
        ])

        if query:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    finally:
        session.close()


@admin_only
async def clear_errors_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session = get_session()
    try:
        session.query(ErrorLog).delete()
        session.commit()
    finally:
        session.close()
    await query.edit_message_text(
        "✅ <b>Barcha xatoliklar jurnali tozalandi.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")]]),
    )


@admin_only
async def clear_cache_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Kesh tozalanmoqda...", show_alert=False)
    geodata.reload_geodata()
    await query.edit_message_text(
        "✅ <b>Kesh va xotira muvaffaqiyatli tozalandi va yangilandi!</b>\n\n"
        "Shahar va mashina nomlari qayta yuklandi.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Asosiy menyu", callback_data="admin:main")]]),
    )


# ============================================================
# 7. ROUTER VA HANDLERLARNI YIG'ISH
# ============================================================

@admin_only
async def admin_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "admin:main":
        return await admin_panel(update, context)
    elif data == "admin:channels":
        return await channels_menu(update, context)
    elif data == "admin:cities":
        return await cities_menu(update, context)
    elif data == "admin:vehicles":
        return await vehicles_menu(update, context)
    elif data == "admin:tonnages":
        return await tonnages_menu(update, context)
    elif data in ("admin:session", "admin:session_refresh"):
        return await session_monitoring_menu(update, context)
    elif data == "admin:stats":
        return await stats_menu(update, context)
    elif data == "admin:errors":
        return await errors_menu(update, context)
    elif data == "admin:clear_errors_do":
        return await clear_errors_action(update, context)
    elif data == "admin:clear_cache":
        return await clear_cache_action(update, context)
    elif data == "admin:close":
        await query.answer()
        return await query.message.delete()


def get_admin_handlers():
    """Botga ulanadigan barcha admin handlerlarini qaytaradi."""
    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_channel_start, pattern=r"^admin:add_channel_start$"),
            CallbackQueryHandler(add_city_start, pattern=r"^admin:add_city_start$"),
            CallbackQueryHandler(add_vehicle_start, pattern=r"^admin:add_vehicle_start$"),
            CallbackQueryHandler(add_tonnage_start, pattern=r"^admin:add_tonnage_start$"),
        ],
        states={
            ADMIN_ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_save)],
            ADMIN_ADD_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_city_save)],
            ADMIN_ADD_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_vehicle_save)],
            ADMIN_ADD_TONNAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tonnage_save)],
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: u.message.reply_text("Bekor qilindi.")),
        ],
    )

    return [
        CommandHandler("admin", admin_panel),
        CommandHandler("stats", stats_menu),
        CommandHandler("errors", errors_menu),
        MessageHandler(filters.Regex(r"^⚙️ Admin Panel$"), admin_panel),
        admin_conv,
        CallbackQueryHandler(admin_callback_router, pattern=r"^admin:"),
    ]

