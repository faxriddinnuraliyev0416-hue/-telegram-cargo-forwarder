"""
"🔎 Filtr" — foydalanuvchi shaxsiy chatida qulay tugmalar orqali filtr yaratadi,
o'zgartiradi, o'chiradi yoki vaqtincha yoqib/o'chiradi.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from app.db import get_session
from app.models import User, CargoFilter
from app import geodata

logger = logging.getLogger("bot.filter")

ORIGIN, DESTINATION, VEHICLE, TONNAGE = range(4)

from app import config

def get_main_menu_keyboard(user_id: int | None = None) -> ReplyKeyboardMarkup:
    """Foydalanuvchi va admin uchun mos asosiy menyu tugmalarini qaytaradi."""
    buttons = [["🔎 Filtr yaratish"]]
    if user_id and (user_id in config.ADMIN_IDS):
        buttons.append(["⚙️ Admin Panel"])
    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [["🔎 Filtr yaratish"]],
    resize_keyboard=True,
    one_time_keyboard=False,
    is_persistent=True,
)

REGION_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Toshkent", "Samarqand", "Farg'ona"],
        ["Andijon", "Namangan", "Buxoro"],
        ["Qashqadaryo", "Surxondaryo", "Xorazm"],
        ["Navoiy", "Jizzax", "Sirdaryo"],
        ["Qoraqalpog'iston", "Vodiy", "Istalgan viloyat"],
        ["❌ Bekor qilish"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

VEHICLE_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Fura / Tent", "Isuzu"],
        ["Gazel / Kiya", "Kamaz"],
        ["Refrijerator", "Labo / Damas"],
        ["Istalgan mashina", "❌ Bekor qilish"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

TONNAGE_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["1 - 3 tonna", "5 tonna"],
        ["10 tonna", "20 - 24 tonna"],
        ["Istalgan tonnaj", "❌ Bekor qilish"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def _get_or_create_user(tg_user) -> User:
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=tg_user.id).first()
        if not user:
            user = User(telegram_id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user
    finally:
        session.close()


async def filter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yangi filtr yaratish wizard'ini boshlaydi."""
    chat = update.effective_chat
    if chat.type != "private":
        bot_username = context.bot.username
        await update.message.reply_text(
            "🔎 <b>Filtr yaratish uchun shaxsiy chatga o'ting:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔎 Filtr yaratish", url=f"https://t.me/{bot_username}?start=filtr")
            ]]),
        )
        return ConversationHandler.END

    _get_or_create_user(update.effective_user)
    await update.message.reply_text(
        "🔎 <b>Yangi yuk filtri yaratish</b>\n\n"
        "1️⃣ <b>Yuk qayerdan yuklanadi?</b>\n"
        "Quyidagi tugmalardan birini tanlang yoki aniq shahar/tuman nomini yozing (masalan: <i>Denov</i>, <i>Kattaqo'rg'on</i>, <i>Toshkent</i>):",
        parse_mode="HTML",
        reply_markup=REGION_KEYBOARD,
    )
    return ORIGIN


async def filter_origin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Bekor qilish":
        return await filter_cancel(update, context)

    origin_name = "Istalgan" if text in ("Istalgan viloyat", "Istalgan", "Barchasi") else geodata.canonical_city_name(text) or text
    context.user_data["new_filter_origin"] = origin_name

    await update.message.reply_text(
        f"✅ <b>Qayerdan:</b> {origin_name}\n\n"
        "2️⃣ <b>Yuk qayerga yetkaziladi?</b>\n"
        "Tugmalardan tanlang yoki shahar nomini yozing:",
        parse_mode="HTML",
        reply_markup=REGION_KEYBOARD,
    )
    return DESTINATION


async def filter_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Bekor qilish":
        return await filter_cancel(update, context)

    dest_name = "Istalgan" if text in ("Istalgan viloyat", "Istalgan", "Barchasi") else geodata.canonical_city_name(text) or text
    context.user_data["new_filter_destination"] = dest_name

    await update.message.reply_text(
        f"✅ <b>Qayerga:</b> {dest_name}\n\n"
        "3️⃣ <b>Mashina turi/rusumi qanday bo'lsin?</b>\n"
        "Tugmalardan tanlang yoki yozing:",
        parse_mode="HTML",
        reply_markup=VEHICLE_KEYBOARD,
    )
    return VEHICLE


async def filter_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Bekor qilish":
        return await filter_cancel(update, context)

    vehicle = None if text in ("Istalgan mashina", "Istalgan", "shart emas", "-", "yo'q", "yoq") else text
    context.user_data["new_filter_vehicle"] = vehicle

    await update.message.reply_text(
        f"✅ <b>Mashina turi:</b> {vehicle or 'Istalgan'}\n\n"
        "4️⃣ <b>Yuk hajmi / tonnasi qancha bo'lsin?</b>\n"
        "Tugmalardan tanlang yoki yozing:",
        parse_mode="HTML",
        reply_markup=TONNAGE_KEYBOARD,
    )
    return TONNAGE


async def filter_tonnage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Bekor qilish":
        return await filter_cancel(update, context)

    tonnage = None if text in ("Istalgan tonnaj", "Istalgan", "shart emas", "-", "yo'q", "yoq") else text

    tg_user = update.effective_user
    user = _get_or_create_user(tg_user)

    origin = context.user_data.pop("new_filter_origin", "Istalgan")
    destination = context.user_data.pop("new_filter_destination", "Istalgan")
    vehicle = context.user_data.pop("new_filter_vehicle", None)

    session = get_session()
    try:
        cf = CargoFilter(
            user_id=user.id,
            origin=origin,
            destination=destination,
            vehicle_type=vehicle,
            tonnage=tonnage,
            active=True,
        )
        session.add(cf)
        session.commit()
        filter_id = cf.id
    finally:
        session.close()

    summary_text = (
        "🎉 <b>Filtr muvaffaqiyatli saqlandi!</b>\n\n"
        f"📍 <b>Yo'nalish:</b> {origin} ➔ {destination}\n"
        f"🚛 <b>Mashina:</b> {vehicle or 'Istalgan'}\n"
        f"⚖️ <b>Tonna:</b> {tonnage or 'Istalgan'}\n\n"
        "⚡️ <i>Endi ushbu yo'nalish bo'yicha yangi yuk e'loni chiqishi bilan sizga DARHOL shaxsiy xabar keladi.</i>\n\n"
        "Filtrlaringizni ko'rish yoki o'chirish uchun /myfilters buyrug'ini yuboring."
    )

    await update.message.reply_text(
        summary_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(tg_user.id if tg_user else None),
    )
    return ConversationHandler.END


async def filter_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    uid = update.effective_user.id if update.effective_user else None
    await update.message.reply_text(
        "❌ Filtr yaratish bekor qilindi.",
        reply_markup=get_main_menu_keyboard(uid),
    )
    return ConversationHandler.END


def get_filter_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("filtr", filter_start),
            CommandHandler("start", filter_start, filters=filters.Regex(r"filtr")),
            MessageHandler(filters.Regex(r"^🔎 Filtr yaratish$"), filter_start),
            CallbackQueryHandler(filter_start_callback, pattern=r"^new_filter$"),
        ],
        states={
            ORIGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_origin)],
            DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_destination)],
            VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_vehicle)],
            TONNAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_tonnage)],
        },
        fallbacks=[
            CommandHandler("cancel", filter_cancel),
            MessageHandler(filters.Regex(r"^❌ Bekor qilish$"), filter_cancel),
        ],
    )


async def filter_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🔎 <b>Yangi yuk filtri yaratish</b>\n\n"
        "1️⃣ <b>Yuk qayerdan yuklanadi?</b>\n"
        "Quyidagi tugmalardan birini tanlang yoki aniq shahar/tuman nomini yozing:",
        parse_mode="HTML",
        reply_markup=REGION_KEYBOARD,
    )
    return ORIGIN


def _filter_keyboard(cf: CargoFilter) -> InlineKeyboardMarkup:
    toggle_text = "⏸ To'xtatish" if cf.active else "▶️ Faollashtirish"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_text, callback_data=f"filter:toggle:{cf.id}")],
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"filter:delete:{cf.id}")],
    ])


async def my_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=tg_user.id).first()
        cargo_filters = user.filters if user else []
        if not cargo_filters:
            await update.message.reply_text(
                "📋 <b>Sizda hali saqlangan filtrlar yo'q.</b>\n\n"
                "Yangi filtr qo'shish uchun /filtr buyrug'ini yuboring.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ Yangi filtr yaratish", callback_data="new_filter")
                ]]),
            )
            return

        await update.message.reply_text(
            f"📋 <b>Sizning filtrlaringiz ({len(cargo_filters)} ta):</b>",
            parse_mode="HTML",
        )
        for cf in cargo_filters:
            status = "🟢 Faol (xabarlar keladi)" if cf.active else "⚪️ To'xtatilgan"
            text = (
                f"<b>{status}</b>\n"
                f"📍 <b>Yo'nalish:</b> {cf.origin} ➔ {cf.destination}\n"
                f"🚛 <b>Mashina:</b> {cf.vehicle_type or 'Istalgan'}\n"
                f"⚖️ <b>Tonna:</b> {cf.tonnage or 'Istalgan'}"
            )
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=_filter_keyboard(cf))
    finally:
        session.close()


async def filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "new_filter":
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return
    _, action, filter_id = parts
    filter_id = int(filter_id)

    session = get_session()
    try:
        cf = session.query(CargoFilter).filter_by(id=filter_id).first()
        if not cf or cf.user.telegram_id != update.effective_user.id:
            await query.edit_message_text("Filtr topilmadi yoki sizga tegishli emas.")
            return

        if action == "toggle":
            cf.active = not cf.active
            session.commit()
            status = "🟢 Faol (xabarlar keladi)" if cf.active else "⚪️ To'xtatilgan"
            text = (
                f"<b>{status}</b>\n"
                f"📍 <b>Yo'nalish:</b> {cf.origin} ➔ {cf.destination}\n"
                f"🚛 <b>Mashina:</b> {cf.vehicle_type or 'Istalgan'}\n"
                f"⚖️ <b>Tonna:</b> {cf.tonnage or 'Istalgan'}"
            )
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=_filter_keyboard(cf))
        elif action == "delete":
            desc = f"{cf.origin} ➔ {cf.destination}"
            session.delete(cf)
            session.commit()
            await query.edit_message_text(f"🗑 <b>Filtr o'chirildi:</b> {desc}", parse_mode="HTML")
    finally:
        session.close()
