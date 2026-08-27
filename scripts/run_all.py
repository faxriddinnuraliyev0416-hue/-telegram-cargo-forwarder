"""
Yagona process orqali Bot va Userbotni parallel ishga tushirish skripti.
Render yoki bitta server/workerda barcha xizmatlarni birgalikda yurgazish uchun ishlatiladi.
"""
import os
import signal
import subprocess
import sys
import time

def main():
    print("==================================================")
    print("  Telegram Cargo Forwarder — Xizmatlar ishga tushirilmoqda...")
    print("==================================================")

    # 1. DB initsializatsiyasi
    print("[1/3] Baza jadvallari tekshirilmoqda...")
    try:
        subprocess.run([sys.executable, "-m", "scripts.init_db"], check=True)
    except Exception as e:
        print(f"Baza initsializatsiyasida ogohlantirish: {e}")

    # 2. Jarayonlarni ishga tushirish
    print("[2/3] Bot processi ishga tushirilmoqda...")
    p_bot = subprocess.Popen([sys.executable, "-m", "app.bot.main"])

    print("[3/3] Userbot processi ishga tushirilmoqda...")
    p_userbot = subprocess.Popen([sys.executable, "-m", "app.userbot"])

    def shutdown_all(*args):
        print("\nTo'xtatish signali qabul qilindi. Jarayonlar yakunlanmoqda...")
        p_bot.terminate()
        p_userbot.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_all)
    signal.signal(signal.SIGTERM, shutdown_all)

    print("Barcha xizmatlar muvaffaqiyatli ishga tushirildi.")

    try:
        while True:
            if p_bot.poll() is not None:
                print("Bot processi to'xtadi! Userbot ham to'xtatilmoqda...")
                p_userbot.terminate()
                sys.exit(1)
            if p_userbot.poll() is not None:
                print("Userbot processi to'xtadi! Bot ham to'xtatilmoqda...")
                p_bot.terminate()
                sys.exit(1)
            time.sleep(2)
    except KeyboardInterrupt:
        shutdown_all()

if __name__ == "__main__":
    main()
