from telegram import Update
from telegram.ext import ContextTypes

from app.db import get_session
from app.models import User
from app.bot.handlers.filter_wizard import get_main_menu_keyboard, filter_start


def _get_or_create_user(tg_user) -> User:
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=tg_user.id).first()
        if not user:
            user = User(telegram_id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name)
            session.add(user)
            session.commit()
        return user
    finally:
        session.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _get_or_create_user(update.effective_user)

    args = context.args
    if args and args[0] == "filtr":
        # deep-link orqali kelgan bo'lsa, to'g'ridan-to'g'ri filtr wizard'ini boshlaymiz
        return await filter_start(update, context)

    user_id = update.effective_user.id if update.effective_user else None

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "Bu bot orqali sizga mos yuk e'lonlari kelishi bilan avtomatik xabar beriladi.\n\n"
        "📌 Asosiy buyruqlar:\n"
        "/filtr — yangi filtr yaratish\n"
        "/myfilters — filtrlaringizni ko'rish/boshqarish\n"
        "/admin — boshqaruv paneli (faqat adminlar uchun)\n"
        "\nPastdagi menyu orqali qulay boshqaring 👇",
        reply_markup=get_main_menu_keyboard(user_id),
    )

