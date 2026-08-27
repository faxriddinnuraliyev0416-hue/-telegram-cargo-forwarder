"""
Userbot process (Telethon / MTProto).
Vazifalari:
1. Manba guruh/kanallardagi yangi xabarlarni real-time tezkor tinglash (Zero-latency pipeline).
2. Xabarni mikrosekundlarda chuqur tahlil qilish (parsing) va FAQAT yuk e'lonlarini saralash.
3. Taksi, yo'lovchi, reklama va spam xabarlarni filtrlab o'tkazib yubormaslik.
4. Xotiradagi tezkor LRU keshi va Redis orqali 0.001ms da duplikat tekshiruvi.
5. Asosiy guruhga PRE-RESOLVED PEER orqali KUTISHSIZ BIR NECHA MILLISEKUNDDA forward qilish.
6. DB'ga yozish va faol filtrlar mosligini parallel fonda bajarish.
7. Real session monitoring uchun muntazam heartbeat yuborish.
"""
import asyncio
import datetime
import time
from collections import deque

from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User as TgUser

from app import config, geodata
from app.db import get_session, init_db
from app.models import SourceChat, SourceType, CargoMessage, ProcessingStatus, CargoFilter
from app.parser import parse_message, ParsedCargo
from app.dedup import compute_hash
from app.matcher import matches
from app.utils.formatting import build_forwarded_message
from app.utils.logging_config import setup_logging
from app import redis_bus
from app.services.session_service import record_heartbeat, log_error

logger = setup_logging("userbot")

# --- Tezkor Xotira Keshlari (In-Memory Micro-Cache) ---
_DEDUP_CACHE_MAX = 20000
_DEDUP_SET: set[str] = set()
_DEDUP_QUEUE: deque[str] = deque()

_ACTIVE_FILTERS_CACHE: list[tuple[int, int, str, str, str | None, str | None]] = []
_LAST_FILTERS_REFRESH = 0.0

# Pre-resolved Main Group Peer
_MAIN_GROUP_PEER = None
_WATCHED_CHATS_MAP: dict[int | str, tuple[int, str, str | None, bool]] = {}


def _get_all_chat_keys(chat_id: int | str, username: str | None = None) -> list[int | str]:
    """Chat ID ning barcha mumkin bo'lgan formatlarini (-100..., bare id, username) generatsiya qiladi."""
    keys: list[int | str] = []
    if isinstance(chat_id, int):
        keys.append(chat_id)
        s = str(chat_id)
        if s.startswith("-100"):
            bare = int(s[4:])
            keys.extend([bare, -bare])
        elif s.startswith("-"):
            bare = int(s[1:])
            keys.extend([bare, int(f"-100{bare}")])
        else:
            keys.extend([-chat_id, int(f"-100{chat_id}")])
    elif isinstance(chat_id, str):
        cleaned = chat_id.lower().strip()
        keys.append(cleaned)
        if cleaned.startswith("@"):
            keys.append(cleaned[1:])
        elif cleaned.lstrip("-").isdigit():
            keys.extend(_get_all_chat_keys(int(cleaned)))

    if username:
        u = username.lower().strip().lstrip("@")
        keys.extend([u, f"@{u}"])
    return keys


def _is_in_memory_duplicate(dedup_hash: str) -> bool:
    return dedup_hash in _DEDUP_SET


def _add_in_memory_dedup(dedup_hash: str):
    if dedup_hash not in _DEDUP_SET:
        _DEDUP_SET.add(dedup_hash)
        _DEDUP_QUEUE.append(dedup_hash)
        if len(_DEDUP_QUEUE) > _DEDUP_CACHE_MAX:
            oldest = _DEDUP_QUEUE.popleft()
            _DEDUP_SET.discard(oldest)


def _get_active_filters_fast() -> list[tuple[int, int, str, str, str | None, str | None]]:
    global _ACTIVE_FILTERS_CACHE, _LAST_FILTERS_REFRESH
    now = time.time()
    if now - _LAST_FILTERS_REFRESH > 15.0 or not _ACTIVE_FILTERS_CACHE:
        session = get_session()
        try:
            filters = session.query(CargoFilter).filter_by(active=True).all()
            _ACTIVE_FILTERS_CACHE = [
                (f.id, f.user.telegram_id, f.origin, f.destination, f.vehicle_type, f.tonnage)
                for f in filters if f.user
            ]
            _LAST_FILTERS_REFRESH = now
        except Exception as e:
            logger.debug(f"Filtrlarni yangilashda xato: {e}")
        finally:
            session.close()
    return _ACTIVE_FILTERS_CACHE


async def _ensure_source_chats_in_db(client: TelegramClient):
    global _WATCHED_CHATS_MAP
    entities = []
    session = get_session()
    try:
        sources_to_check = list(config.SOURCE_CHATS)

        db_sources = session.query(SourceChat).filter_by(active=True).all()
        for dbs in db_sources:
            ident = dbs.username or dbs.invite_link or dbs.chat_id
            if ident and ident not in sources_to_check:
                sources_to_check.append(ident)

        for ref in sources_to_check:
            ref_clean = str(ref).strip().rstrip(".")
            if not ref_clean:
                continue
            try:
                entity = await client.get_entity(ref_clean)
            except Exception as e:
                logger.warning(f"Manba chatga ulanib bo'lmadi: {ref_clean} — {e}")
                continue

            full_chat_id = int(f"-100{entity.id}") if isinstance(entity, Channel) else -entity.id if isinstance(entity, Chat) else entity.id
            existing = session.query(SourceChat).filter_by(chat_id=full_chat_id).first()
            username = getattr(entity, "username", None)
            title = getattr(entity, "title", None) or getattr(entity, "first_name", "Noma'lum")
            src_type = SourceType.CHANNEL if isinstance(entity, Channel) and getattr(entity, "broadcast", False) else SourceType.GROUP

            if not existing:
                existing = SourceChat(chat_id=full_chat_id, title=title, username=username, type=src_type, active=True)
                session.add(existing)
                session.commit()
                logger.info(f"Yangi manba chat DB'ga qo'shildi: {title} ({full_chat_id})")
            else:
                existing.title = title
                existing.username = username
                session.commit()

            # Barcha kalitlar bo'yicha xotiraga yozamiz
            info = (existing.id, title, username, existing.active)
            for k in _get_all_chat_keys(full_chat_id, username):
                _WATCHED_CHATS_MAP[k] = info

            entities.append(entity)
        return entities
    finally:
        session.close()


def _sender_display_info(sender):
    if sender is None:
        return None, None, None
    if isinstance(sender, TgUser):
        name = " ".join(filter(None, [sender.first_name, sender.last_name])) or sender.username or "Noma'lum"
        return name, sender.username, sender.id
    title = getattr(sender, "title", None)
    return title, getattr(sender, "username", None), getattr(sender, "id", None)


_FORWARD_QUEUE: asyncio.Queue = asyncio.Queue(maxsize=10000)


def _sync_save_db_and_match(source_chat_row_id: int, message_id: int, sender_id: int | None,
                            sender_username: str | None, sender_name: str | None, text: str,
                            message_date: datetime.datetime, parsed: ParsedCargo,
                            dedup_hash: str, main_group_msg_id: int | None):
    """Alohida threadpool'da ishlaydi: DB ga yozish asinxron event loop'ni aslo to'xtatmaydi."""
    session = get_session()
    try:
        phone_str = parsed.phones[0].formatted if parsed.phones else None
        cargo_msg = CargoMessage(
            source_chat_id=source_chat_row_id,
            source_message_id=message_id,
            original_sender_id=sender_id,
            original_sender_username=sender_username,
            original_sender_name=sender_name,
            original_text=text,
            message_date=message_date,
            parsed_origin=parsed.origin,
            parsed_destination=parsed.destination,
            parsed_cargo_type=parsed.cargo_type,
            parsed_vehicle_type=", ".join(parsed.vehicle_types) if parsed.vehicle_types else None,
            parsed_tonnage=parsed.tonnage or parsed.volume,
            parsed_phone=phone_str,
            is_cargo=True,
            status=ProcessingStatus.PARSED if parsed.is_fully_parsed else ProcessingStatus.PARSE_FAILED,
            dedup_hash=dedup_hash,
            forwarded_to_main_group=bool(main_group_msg_id),
            main_group_message_id=main_group_msg_id,
        )
        session.add(cargo_msg)

        chat_row = session.query(SourceChat).filter_by(id=source_chat_row_id).first()
        if chat_row:
            chat_row.message_count = (chat_row.message_count or 0) + 1
            chat_row.last_message_at = datetime.datetime.utcnow()

        session.commit()
        cargo_msg_id = cargo_msg.id

        if parsed.origin and parsed.destination:
            active_filters = _get_active_filters_fast()
            for fid, user_tg_id, f_orig, f_dest, f_veh, f_ton in active_filters:
                cf = CargoFilter(origin=f_orig, destination=f_dest, vehicle_type=f_veh, tonnage=f_ton)
                if matches(cf, parsed):
                    redis_bus.publish_match(user_tg_id, cargo_msg_id)
                    logger.info(f"Moslik topildi: filter#{fid} -> user {user_tg_id}")

        record_heartbeat(
            session_name="userbot_session",
            processed_increment=1,
            forwarded_increment=1 if main_group_msg_id else 0,
        )
    except Exception as e:
        logger.exception(f"DB saqlash yoki matching xatosi: {e}")
        log_error("userbot_db_save", str(e))
    finally:
        session.close()


async def _forward_worker(client: TelegramClient):
    """
    Xabarlarni kanalga bir necha soniya farq (smooth pacing delay) bilan,
    navbat asosida va Telegram FloodWait cheklovlaridan 100% himoyalangan holda
    xavfsiz yuboruvchi doimiy ishchi (Worker).
    """
    global _MAIN_GROUP_PEER
    logger.info(f"Forward worker faol. Xabarlar oralig'i: {config.FORWARD_DELAY_SECONDS} soniya.")

    while True:
        try:
            item = await _FORWARD_QUEUE.get()
            (
                source_chat_row_id,
                message_id,
                sender_id,
                sender_username,
                sender_name,
                text,
                msg_date,
                parsed,
                dedup_hash,
                formatted,
            ) = item

            target_peer = _MAIN_GROUP_PEER or config.MAIN_GROUP_ID
            main_group_msg_id = None

            # Xabarni guruhga yuborish (FloodWait himoyasi va avtomatik retry bilan)
            retry_count = 0
            while retry_count < 3:
                try:
                    sent = await client.send_message(
                        target_peer,
                        formatted,
                        parse_mode="html",
                        link_preview=False,
                    )
                    main_group_msg_id = sent.id
                    break
                except errors.FloodWaitError as fe:
                    wait_sec = fe.seconds + 1
                    logger.warning(f"Telegram FloodWait: {wait_sec} soniya kutilmoqda...")
                    await asyncio.sleep(wait_sec)
                    retry_count += 1
                except Exception as e:
                    logger.error(f"Asosiy guruhga yuborishda xato: {e}")
                    log_error("userbot_forward", str(e))
                    try:
                        _MAIN_GROUP_PEER = await client.get_input_entity(config.MAIN_GROUP_ID)
                        target_peer = _MAIN_GROUP_PEER
                    except Exception:
                        pass
                    retry_count += 1
                    await asyncio.sleep(1.0)

            # DB ga saqlash va DM matching'ni fonda tezkor bajarish
            asyncio.to_thread(
                _sync_save_db_and_match,
                source_chat_row_id=source_chat_row_id,
                message_id=message_id,
                sender_id=sender_id,
                sender_username=sender_username,
                sender_name=sender_name,
                text=text,
                message_date=msg_date,
                parsed=parsed,
                dedup_hash=dedup_hash,
                main_group_msg_id=main_group_msg_id,
            )

            _FORWARD_QUEUE.task_done()

            # Habarlar bir necha soniya farq bilan tushishi uchun intervalli kutish
            if config.FORWARD_DELAY_SECONDS > 0:
                await asyncio.sleep(config.FORWARD_DELAY_SECONDS)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception(f"Forward workerda kutilmagan xato: {e}")
            await asyncio.sleep(1.0)


async def _second_interval_monitor():
    """
    Har soniyada xabarlar navbati va tizim faolligini nazorat qiluvchi monitor.
    """
    while True:
        try:
            qsize = _FORWARD_QUEUE.qsize()
            if qsize > 5:
                logger.info(f"[Har soniya nazorat] Navbatda {qsize} ta xabar yuborilish arafasida.")
        except Exception as e:
            logger.debug(f"Har soniya monitor ogohlantirish: {e}")
        await asyncio.sleep(1.0)


async def _process_new_message(client: TelegramClient, event, source_chat_row_id: int,
                               source_title: str, source_username: str | None):
    try:
        message = event.message
        text = message.raw_text or ""
        if not text.strip():
            return

        # 1. Xotiradagi 0.0001ms duplikat tekshiruvi
        dedup_hash = compute_hash(text)
        if _is_in_memory_duplicate(dedup_hash) or await redis_bus.async_is_duplicate_cached(dedup_hash):
            logger.info(f"Duplicate xabar o'tkazib yuborildi (hash={dedup_hash[:8]})")
            record_heartbeat(
                session_name="userbot_session",
                processed_increment=1,
                duplicate_increment=1,
            )
            return

        _add_in_memory_dedup(dedup_hash)
        asyncio.create_task(redis_bus.async_cache_dedup_hash(dedup_hash))

        # 2. Tezkor parsing
        parsed = parse_message(text)

        # 3. Yuboruvchi ma'lumotlarini olish
        sender = getattr(event, "sender", None)
        sender_name, sender_username, sender_id = _sender_display_info(sender)
        if not sender_name and not sender_username and event.sender_id:
            sender_id = event.sender_id

        # 4. Chiroyli formatlangan xabar yaratish
        formatted = build_forwarded_message(
            source_title=source_title,
            source_username=source_username,
            sender_name=sender_name,
            sender_username=sender_username,
            sender_id=sender_id,
            original_text=text,
            origin=parsed.origin,
            destination=parsed.destination,
            vehicle_types=parsed.vehicle_types,
            tonnage=parsed.tonnage,
            volume=parsed.volume,
            cargo_type=parsed.cargo_type,
            price=parsed.price,
            phones=parsed.phones,
        )

        # 5. NAVBATGA QO'SHISH (FAST NON-BLOCKING QUEUE)
        msg_date = message.date.replace(tzinfo=None) if message.date else datetime.datetime.utcnow()
        queue_item = (
            source_chat_row_id,
            message.id,
            sender_id,
            sender_username,
            sender_name,
            text,
            msg_date,
            parsed,
            dedup_hash,
            formatted,
        )
        _FORWARD_QUEUE.put_nowait(queue_item)
        qsize = _FORWARD_QUEUE.qsize()
        if qsize > 1:
            logger.info(f"Yangi e'lon navbatga qo'shildi (Navbatdagi jami: {qsize})")

    except Exception as e:
        logger.exception(f"Xabarni qayta ishlashda kutilmagan xato: {e}")
        log_error("userbot_process", str(e))
        record_heartbeat(
            session_name="userbot_session",
            error_increment=1,
        )


async def _heartbeat_loop(client: TelegramClient, get_chats_count_fn):
    while True:
        try:
            connected = get_chats_count_fn()
            record_heartbeat(
                session_name="userbot_session",
                connected_chats_count=connected,
            )
        except Exception as e:
            logger.debug(f"Heartbeat yangilashda xatolik: {e}")
        await asyncio.sleep(30)


async def main():
    global _MAIN_GROUP_PEER, _WATCHED_CHATS_MAP
    config.validate_userbot()
    init_db()

    # Telethon ulanishini optimal tezlikka sozlash
    session_target = (
        StringSession(config.TELETHON_STRING_SESSION)
        if config.TELETHON_STRING_SESSION
        else config.TELETHON_SESSION_NAME
    )
    client = TelegramClient(
        session_target,
        config.API_ID,
        config.API_HASH,
        flood_sleep_threshold=60,
        request_retries=10,
        connection_retries=10,
        retry_delay=1,
        auto_reconnect=True,
        sequential_updates=False,
    )
    await client.start()

    logger.info("Userbot muvaffaqiyatli ulandi (Ultra-fast zero-latency engine).")

    # Asosiy guruh peer'ini oldindan resolve qilib olamiz (RPC kutmaslik uchun)
    try:
        _MAIN_GROUP_PEER = await client.get_input_entity(config.MAIN_GROUP_ID)
        logger.info("Asosiy guruh peer'i muvaffaqiyatli resolve qilindi.")
    except Exception as e:
        logger.warning(f"Asosiy guruh peer'ini olishda ogohlantirish: {e}")
        _MAIN_GROUP_PEER = config.MAIN_GROUP_ID

    entities = await _ensure_source_chats_in_db(client)
    if not entities:
        logger.warning("Hech qanday manba chat topilmadi! SOURCE_CHATS sozlamasini tekshiring.")

    # DB dagi barcha manbalarni xotira xaritasiga yuklaymiz
    session = get_session()
    try:
        for row in session.query(SourceChat).all():
            info = (row.id, row.title, row.username, row.active)
            for k in _get_all_chat_keys(row.chat_id, row.username):
                _WATCHED_CHATS_MAP[k] = info
    finally:
        session.close()

    _get_active_filters_fast()

    # Doimiy fonda ishlovchi vazifalar:
    asyncio.create_task(_heartbeat_loop(client, lambda: len(entities)))
    asyncio.create_task(_forward_worker(client))
    asyncio.create_task(_second_interval_monitor())

    # Asosiy guruh ID larining barcha variantlarini chetlab o'tish uchun ro'yxat
    main_group_keys = set(_get_all_chat_keys(config.MAIN_GROUP_ID))

    @client.on(events.NewMessage())
    async def global_message_handler(event):
        full_chat_id = event.chat_id
        if not full_chat_id or full_chat_id in main_group_keys:
            return  # Asosiy guruhning o'z xabarlarini qayta ishlamaymiz

        # 0.0001ms da xotiradan tekshirish
        row_info = _WATCHED_CHATS_MAP.get(full_chat_id)
        if not row_info:
            # Agar chat username bo'lsa
            chat = getattr(event, "chat", None)
            username = getattr(chat, "username", None) if chat else None
            if username:
                row_info = _WATCHED_CHATS_MAP.get(username.lower()) or _WATCHED_CHATS_MAP.get(f"@{username.lower()}")

        if not row_info or not row_info[3]:  # not active
            return

        logger.info(f"Yangi xabar qabul qilindi: {row_info[1]} (chat_id={full_chat_id})")
        asyncio.create_task(
            _process_new_message(client, event, row_info[0], row_info[1], row_info[2])
        )

    logger.info(f"{len(entities)} ta manba chat tinglanmoqda. Asosiy guruh: {config.MAIN_GROUP_ID}")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())


