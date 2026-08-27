"""
Redis orqali:
1. Tezkor dedup keshi (DB'ga qo'shimcha, tezroq tekshirish uchun) — 30 kunlik TTL.
2. "new_matches" pub/sub kanali — userbot yangi mos xabarni topganda, bot
   process'iga darhol (real-time) xabar beradi, u esa foydalanuvchiga DM yuboradi.
"""
import json
import redis
import redis.asyncio as aioredis
from app import config

_redis_client = None
_async_redis_client = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
    return _redis_client


def get_async_redis() -> aioredis.Redis:
    global _async_redis_client
    if _async_redis_client is None:
        _async_redis_client = aioredis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
    return _async_redis_client


def is_duplicate_cached(dedup_hash: str) -> bool:
    try:
        r = get_redis()
        return r.exists(f"{config.REDIS_DEDUP_PREFIX}{dedup_hash}") == 1
    except Exception:
        return False


def cache_dedup_hash(dedup_hash: str):
    try:
        r = get_redis()
        ttl_seconds = config.MESSAGE_RETENTION_DAYS * 24 * 3600
        r.set(f"{config.REDIS_DEDUP_PREFIX}{dedup_hash}", "1", ex=ttl_seconds)
    except Exception:
        pass


async def async_is_duplicate_cached(dedup_hash: str) -> bool:
    try:
        r = get_async_redis()
        return bool(await r.exists(f"{config.REDIS_DEDUP_PREFIX}{dedup_hash}"))
    except Exception:
        return False


async def async_cache_dedup_hash(dedup_hash: str):
    try:
        r = get_async_redis()
        ttl_seconds = config.MESSAGE_RETENTION_DAYS * 24 * 3600
        await r.set(f"{config.REDIS_DEDUP_PREFIX}{dedup_hash}", "1", ex=ttl_seconds)
    except Exception:
        pass


async def async_publish_match(user_telegram_id: int, cargo_message_id: int):
    try:
        r = get_async_redis()
        payload = json.dumps({"user_telegram_id": user_telegram_id, "cargo_message_id": cargo_message_id})
        await r.publish(config.REDIS_MATCH_CHANNEL, payload)
    except Exception:
        pass


def publish_match(user_telegram_id: int, cargo_message_id: int):
    try:
        r = get_redis()
        payload = json.dumps({"user_telegram_id": user_telegram_id, "cargo_message_id": cargo_message_id})
        r.publish(config.REDIS_MATCH_CHANNEL, payload)
    except Exception:
        pass
