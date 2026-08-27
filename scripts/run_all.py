"""
Yagona process orqali Bot va Userbotni parallel ishga tushirish skripti.
Render yoki bitta server/workerda barcha xizmatlarni birgalikda yurgazish uchun ishlatiladi.
"""
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - Telegram Cargo Forwarder is active.")

    def log_message(self, format, *args):
        pass  # Health-check pinglarini logga chiqarmaslik


def start_health_server():
    port = int(os.getenv("PORT", 10000))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        print(f"[HealthCheck] Port {port} da tekshiruv serveri faol.")
        server.serve_forever()
    except Exception as e:
        print(f"[HealthCheck] Server xatosi: {e}")


def start_keep_alive_pinger():
    """
    Render Free Web Service 15 daqiqada uxlab qolishini oldini olish uchun
    har 5-7 daqiqada tashqi URL'ga avtomatik HTTP GET so'rov yuboruvchi doimiy pinger.
    """
    import urllib.request

    url = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-cargo-forwarder.onrender.com").strip()
    interval = int(os.getenv("KEEP_ALIVE_INTERVAL_MINUTES", "6")) * 60
    if not url:
        return

    print(f"[AntiSleep-KeepAlive] O'z-o'zini uyg'otib turuvchi pinger faollashtirildi (har {interval//60} daqiqada -> {url})")
    time.sleep(45)  # Server to'liq ko'tarilishini kutish

    while True:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CargoBot-KeepAlive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[AntiSleep-KeepAlive] {current_time} — Ping yuborildi (HTTP 200 OK). Server 100% uyg'oq.")
        except Exception as e:
            print(f"[AntiSleep-KeepAlive] Ping ogohlantirish: {e}")
        time.sleep(interval)


def main():
    print("==================================================")
    print("  Telegram Cargo Forwarder — Xizmatlar ishga tushirilmoqda...")
    print("==================================================")

    # 0. Render Web Service uchun healthcheck serverini va KeepAlive pingerini fonda ishga tushirish
    h_thread = threading.Thread(target=start_health_server, daemon=True)
    h_thread.start()

    pinger_thread = threading.Thread(target=start_keep_alive_pinger, daemon=True)
    pinger_thread.start()

    # 1. DB initsializatsiyasi
    print("[1/3] Baza jadvallari tekshirilmoqda...")
    try:
        subprocess.run([sys.executable, "-m", "scripts.init_db"], check=True)
    except Exception as e:
        print(f"Baza initsializatsiyasida ogohlantirish: {e}")

    # 2. Jarayonlarni doimiy nazorat ostida (Auto-Restart Supervisor) ishga tushirish
    env = dict(os.environ, PYTHONUNBUFFERED="1")

    def run_supervised(module_name: str):
        while True:
            try:
                print(f"[{module_name}] Ishga tushirilmoqda (python -m {module_name})...")
                p = subprocess.Popen([sys.executable, "-m", module_name], env=env)
                p.wait()
                print(f"[{module_name}] To'xtadi (kod: {p.returncode}). 3 soniyada avtomatik qayta boshlanadi...")
            except Exception as exc:
                print(f"[{module_name}] Xatolik yuz berdi: {exc}")
            time.sleep(3)

    t_bot = threading.Thread(target=run_supervised, args=("app.bot.main",), daemon=True)
    t_userbot = threading.Thread(target=run_supervised, args=("app.userbot",), daemon=True)

    t_bot.start()
    t_userbot.start()

    print("Barcha xizmatlar (Bot, Userbot, HealthServer, KeepAlive) to'liq ishga tushirildi.")

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nTo'xtatish signali qabul qilindi.")

if __name__ == "__main__":
    main()
