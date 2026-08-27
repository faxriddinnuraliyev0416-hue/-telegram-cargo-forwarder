"""Asosiy guruh uchun avtomatik moderatsiya."""
import datetime
import re
from collections import defaultdict

from telegram import ChatPermissions, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from app import config
from app.utils.logging_config import setup_logging

logger = setup_logging("moderation")

# So'zning bir qismi emas, aynan haqorat/18+ ibora bo'lganda ishlaydi.
_BANNED_TEXT = re.compile(
    r"(?:\b(?:fuck|f+u+c+k+|shit|bitch|asshole|idiot|porn|porno|"
    r"sex|sexy|nudes?|onlyfans|ahmoq|tentak|haromi|fahsh)\b|"
    r"(?:бляд|бля|сука|пизд|хуй|еба))",
    re.IGNORECASE,
)
_ADULT_URL = re.compile(
    r"(?:pornhub|xvideos|xnxx|redtube|youporn|onlyfans|xhamster|"
    r"chaturbate|stripchat|cam4)\.",
    re.IGNORECASE,
)

_strikes: dict[int, int] = defaultdict(int)
_MUTE_AFTER_STRIKES = 3
_MUTE_DURATION = datetime.timedelta(hours=24)


def _content(message) -> str:
    """Matn, caption va yashirilgan URL'larni bitta satrga yig'adi."""
    parts = [message.text or "", message.caption or ""]
    for entity in (message.entities or ()) + (message.caption_entities or ()):
        if entity.url:
            parts.append(entity.url)
    return "\n".join(parts)


def _violation_reason(message) -> str | None:
    content = _content(message)
    if _ADULT_URL.search(content):
        return "18+ havola"
    if _BANNED_TEXT.search(content):
        return "haqoratli yoki 18+ matn"
    return None


async def moderate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Faqat MAIN_GROUP_ID ichidagi qoidabuzar xabarlarni o'chiradi."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or chat.id != config.MAIN_GROUP_ID or not user:
        return
    if user.id in config.ADMIN_IDS or user.is_bot:
        return

    reason = _violation_reason(message)
    if not reason:
        return

    try:
        await message.delete()
    except (BadRequest, Forbidden) as exc:
        logger.warning("Qoidabuzar xabarni o'chirib bo'lmadi: %s", exc)
        return

    _strikes[user.id] += 1
    strikes = _strikes[user.id]
    notice = (
        f"{user.mention_html()} xabari o'chirildi: <b>{reason}</b>. "
        "Guruhda haqorat va 18+ kontent taqiqlangan."
    )
    try:
        if strikes >= _MUTE_AFTER_STRIKES:
            until = datetime.datetime.now(datetime.timezone.utc) + _MUTE_DURATION
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            _strikes[user.id] = 0
            notice += " Takroriy qoidabuzarlik uchun 24 soatga yozish cheklovi qo'yildi."
        await context.bot.send_message(chat.id, notice, parse_mode="HTML")
    except (BadRequest, Forbidden) as exc:
        # O'chirish ishlagan bo'lsa, admin huquqi cheklov uchun yetarli bo'lmasligi mumkin.
        logger.warning("Moderatsiya ogohlantirishi/cheklovi yuborilmadi: %s", exc)

