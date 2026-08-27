"""
Telethon String Session generator skripti.
Render yoki boshqa bulutli hostinglarga faylsiz (string session) orqali deploy qilish uchun ishlatiladi.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from app import config

async def main():
    print("=" * 60)
    print("Telethon String Session Generator")
    print("=" * 60)
    api_id = config.API_ID or int(input("API_ID ni kiriting: ").strip())
    api_hash = config.API_HASH or input("API_HASH ni kiriting: ").strip()

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_str = client.session.save()
        print("\n" + "=" * 60)
        print("Sizning TELETHON_STRING_SESSION qimmatingiz:")
        print("=" * 60)
        print(session_str)
        print("=" * 60)
        print("Buni Render'dagi Environment Variables bo'limiga TELETHON_STRING_SESSION nomi bilan kiriting.\n")

if __name__ == "__main__":
    asyncio.run(main())
