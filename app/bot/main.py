"""
Bot process (python-telegram-bot / Bot API).

Vazifalari:
1. Foydalanuvchilar bilan muloqot: /start, /filtr (forma), /myfilters.
2. Admin buyruqlari: /stats, /sources, /users, /activefilters, /errors.
3. Asosiy guruhda "🔎 Filtr" tugmasini o'z ichiga olgan xabarni pin qilish
   (deep-link orqali shaxsiy chatga yo'naltiradi).
4. Redis "new_matches" kanalini tinglab, userbot process aniqlagan har bir
   moslikni FAKAT shu (bot) orqali foydalanuvchiga real-time DM qiladi.
"""
import asyncio
import html
import json
import logging

import redis.asyncio as aioredis
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from app import config
from app.db import get_session, init_db
from app.models import CargoMessage, ErrorLog
from app.utils.logging_config import setup_logging
from app.utils.formatting import TELEGRAM_TEXT_LIMIT, truncate_escaped_text, build_dm_match_message
from app.bot.handlers.start import start
from app.bot.handlers.filter_wizard import (
    get_filter_conversation_handler, my_filters, filter_callback,
)
from app.bot.handlers.admin import get_admin_handlers
from app.bot.handlers.moderation import moderate_message

logger = setup_logging("bot")


async def _pin_filter_button(application: Application):
    """Filtr tugmasi pinlanganini tekshiradi va faqat kerak bo'lsa yaratadi."""
    try:
        chat = await application.bot.get_chat(config.MAIN_GROUP_ID)
        pinned = chat.pinned_message
        if pinned and pinned.text and "filtr yarat" in pinned.text.lower():
            logger.info("Filtr tugmasi asosiy guruhda allaqachon pinlangan.")
            return

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔎 Filtr yaratish", url=f"https://t.me/{config.BOT_USERNAME}?start=filtr")
        ]])
        msg = await application.bot.send_message(
            chat_id=config.MAIN_GROUP_ID,
            text="Sizga mos yuk e'lonlari kelishi bilan xabar olish uchun filtr yarating 👇",
            reply_markup=keyboard,
        )
        await application.bot.pin_chat_message(chat_id=config.MAIN_GROUP_ID, message_id=msg.message_id,
                                                 disable_notification=True)
        logger.info("Filtr tugmasi asosiy guruhda pin qilindi.")
    except Exception as e:
        logger.warning(f"Filtr tugmasini pin qilishda xato (qo'lda pin qilish mumkin): {e}")


async def _send_match_notification(application: Application, user_telegram_id: int, cargo_message_id: int):
    session = get_session()
    try:
        cm = session.query(CargoMessage).filter_by(id=cargo_message_id).first()
        if not cm:
            return

        source_title = cm.source_chat.title if cm.source_chat else "Telegram guruh"
        source_username = cm.source_chat.username if cm.source_chat else None
        vehicle_types = [v.strip() for v in (cm.parsed_vehicle_type or "").split(",") if v.strip()]
        phones = [cm.parsed_phone] if cm.parsed_phone else []

        text = build_dm_match_message(
            origin=cm.parsed_origin,
            destination=cm.parsed_destination,
            vehicle_types=vehicle_types,
            tonnage=cm.parsed_tonnage,
            volume=None,
            cargo_type=cm.parsed_cargo_type,
            price=None,
            phones=phones,
            source_title=source_title,
            source_username=source_username,
            sender_name=cm.original_sender_name,
            sender_username=cm.original_sender_username,
            sender_id=cm.original_sender_id,
            original_text=cm.original_text,
        )

        try:
            await application.bot.send_message(
                chat_id=user_telegram_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Forbidden:
            logger.info(f"Foydalanuvchi {user_telegram_id} botni bloklagan, DM yuborilmadi.")
    finally:
        session.close()


async def _redis_listener(application: Application):
    """Userbot process'dan kelayotgan 'yangi moslik' signallarini tinglaydi
    va DARHOL foydalanuvchiga DM yuboradi (real-time talabi shu orqali bajariladi)."""
    r = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(config.REDIS_MATCH_CHANNEL)
    logger.info("Redis 'new_matches' kanali tinglanmoqda...")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            # Barcha mos foydalanuvchilarga parallel va bir vaqtning o'zida yuborish
            asyncio.create_task(
                _send_match_notification(application, data["user_telegram_id"], data["cargo_message_id"])
            )
        except Exception as e:
            logger.exception(f"Match xabarini qabul qilishda xato: {e}")


_redis_task = None


async def post_init(application: Application):
    global _redis_task
    init_db()
    await _pin_filter_button(application)
    # Redis tinglovchisini fon vazifasi sifatida ishga tushiramiz
    _redis_task = asyncio.create_task(_redis_listener(application))


async def post_shutdown(application: Application):
    global _redis_task
    if _redis_task and not _redis_task.done():
        _redis_task.cancel()
        try:
            await _redis_task
        except asyncio.CancelledError:
            pass


def main():
    config.validate_bot()

    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(get_filter_conversation_handler())
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myfilters", my_filters))
    application.add_handler(CallbackQueryHandler(filter_callback, pattern=r"^filter:"))

    for handler in get_admin_handlers():
        application.add_handler(handler)

    # Guruhdagi oddiy va tahrirlangan xabarlarni avtomatik moderatsiya qilish.
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, moderate_message), group=1)
    application.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & ~filters.COMMAND, moderate_message), group=1)

    logger.info("Bot ishga tushdi.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
