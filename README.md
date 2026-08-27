# Telegram Yuk E'lonlari Forwarder + Filtr Tizimi

Bu tizim sizning 5-6 ta manba Telegram guruh/kanalingizdagi yangi yuk
e'lonlarini kuzatib, ularni sizning asosiy guruhingizga (manba/yuboruvchi
ko'rsatkichi bilan) forward qiladi, va foydalanuvchilar o'z filtriga mos
kelgan yuk kelishi bilan shaxsiy xabar (DM) oladi.

## Arxitektura

| Komponent | Vazifasi |
|---|---|
| **userbot** (Telethon, MTProto) | Sizning shaxsiy Telegram akkountingiz nomidan manba guruhlarni tinglaydi, parsing/dedup qiladi, asosiy guruhga forward qiladi |
| **bot** (Bot API) | Foydalanuvchilar bilan muloqot (filtr forma, /myfilters), admin buyruqlari, real-time DM yuborish |
| **PostgreSQL** | Barcha xabarlar, foydalanuvchilar, filtrlar shu yerda saqlanadi |
| **Redis** | Tezkor dedup keshi + userbot va bot orasida real-time signal almashish (pub/sub) |

Ikkita alohida process (userbot va bot) ishlatilishining sababi: manba
guruhlarni "oddiy a'zo" sifatida tinglash faqat shaxsiy akkount (Telethon)
orqali mumkin, foydalanuvchilarga xabar yuborish/forma esa Bot API orqali
qulayroq va xavfsizroq.

---

## 1-QADAM: Kerakli ma'lumotlarni tayyorlash

### 1.1 — Bot yaratish (@BotFather)

Sizda hali bot yo'q, shuning uchun:

1. Telegram'da **@BotFather** ga o'ting.
2. `/newbot` buyrug'ini yuboring.
3. Botga nom bering (masalan: `Yuk Filtr Bot`).
4. Botga username bering — `bot` bilan tugashi shart (masalan: `yukfiltr_bot`).
5. BotFather sizga **BOT_TOKEN** beradi (masalan `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`).
   Buni `.env` faylidagi `BOT_TOKEN` ga qo'ying.
6. Bot username'ini (masalan `yukfiltr_bot`, `@` belgisisiz) `.env` dagi `BOT_USERNAME` ga qo'ying.
7. **Botni asosiy guruhingizga admin sifatida qo'shing** (kamida "xabar yuborish" va
   "pin qilish" huquqlari bilan) — chunki bot guruhda "🔎 Filtr" tugmasini pin qiladi.

> ⚠️ BOT_TOKEN'ni hech kimga, hech qanday chatga (shu jumladan menga ham) yubormang.

### 1.2 — API_ID va API_HASH

Sizda bular allaqachon bor ekan — ularni to'g'ridan-to'g'ri `.env` fayliga
quyidagicha joylashtiring:

```
API_ID=sizning_api_id_raqamingiz
API_HASH=sizning_api_hash_qatoringiz
```

(Agar kelajakda kerak bo'lsa: bular **my.telegram.org** saytiga o'z telefon
raqamingiz bilan kirib, "API development tools" bo'limidan olinadi.)

### 1.3 — Guruh ID'lar

- **MAIN_GROUP_ID** — asosiy guruhingizning ID'si. Buni topish uchun eng oson
  yo'l: guruhga istalgan xabarni forward qiling **@userinfobot** ga. ID odatda
  `-100` bilan boshlanadi (masalan `-1001234567890`).
- **SOURCE_CHATS** — 5-6 ta manba guruh/kanal. Ular hammasi **ochiq
  (public)** ekan — shuning uchun ularni oddiy `@username` ko'rinishida
  `.env` ga vergul bilan ajratib yozasiz:
  ```
  SOURCE_CHATS=@manba1,@manba2,@manba3,@manba4,@manba5
  ```

### 1.4 — Admin ID'lar

4-5 ta admin bo'ladi. Har birining Telegram ID'sini bilish uchun
**@userinfobot** ga yozing, u sizga ID'ingizni qaytaradi. Barcha ID'larni
vergul bilan `.env` dagi `ADMIN_IDS` ga yozing:

```
ADMIN_IDS=111111111,222222222,333333333,444444444,555555555
```

---

## 2-QADAM: Serverni tayyorlash

Tavsiya: **Hetzner CX22** yoki **DigitalOcean Basic Droplet** (2 vCPU / 4GB RAM
yetarli), Ubuntu 22.04, Docker o'rnatilgan.

```bash
# Docker va Docker Compose o'rnatish (Ubuntu)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# terminaldan chiqib qayta kiring, keyin tekshiring:
docker --version
docker compose version
```

---

## 3-QADAM: Loyihani serverga joylashtirish

```bash
# loyiha papkasini serverga ko'chiring (scp/git orqali), so'ng:
cd telegram-cargo-forwarder

cp .env.example .env
nano .env   # barcha qiymatlarni to'ldiring (1-qadamdagi ma'lumotlar)
```

---

## 4-QADAM: Birinchi marta ishga tushirish (Telethon login)

**MUHIM**: userbot birinchi marta ishga tushganda Telegram sizning telefon
raqamingiz va tasdiqlash kodini so'raydi. Bu **faqat bir marta**, interaktiv
rejimda amalga oshiriladi — keyin session fayl saqlanib qoladi va qayta
so'ramaydi.

```bash
# avval infratuzilmani (DB, Redis) va jadvallarni tayyorlaymiz
docker compose up -d postgres redis
docker compose run --rm init-db

# endi userbot'ni INTERAKTIV rejimda ishga tushiramiz (login uchun)
docker compose run --rm userbot python -m app.userbot
```

Terminalda sizdan so'raladi:
1. **Telefon raqam** — xalqaro formatda (masalan `+998901234567`).
2. **Tasdiqlash kodi** — Telegram ilovangizga keladi. Uni shu yerga kiriting.
3. Agar 2FA (ikki bosqichli parol) yoqilgan bo'lsa — parolni ham so'raydi.

> 🔒 Bu kod/parolni HECH KIMGA (shu jumladan botlarga, "qo'llab-quvvatlash"
> deb yozganlarga ham) yubormang. Faqat shu terminalga kiritasiz.

Login muvaffaqiyatli bo'lgach, `./sessions/` papkasida session fayl paydo
bo'ladi va konsolda "Userbot muvaffaqiyatli ulandi" degan xabar chiqadi.
`Ctrl+C` bilan to'xtatib, endi doimiy (background) rejimda ishga tushiring:

```bash
docker compose up -d
```

Shu buyruq **postgres, redis, userbot, bot** — barcha xizmatlarni fon
rejimida ishga tushiradi. Endi session fayl saqlangani uchun qayta login
so'ramaydi.

---

## 5-QADAM: Tekshirish

1. Botingizga Telegram'da `/start` yozing — salomlashish xabari kelishi kerak.
2. Asosiy guruhingizda "🔎 Filtr yaratish" tugmali pin qilingan xabar
   paydo bo'lishi kerak.
3. `/filtr` orqali bot bilan shaxsiy chatda filtr yarating (masalan
   Toshkent → Samarqand).
4. Manba guruhlardan biriga mos yuk e'loni kelishini kuting (yoki test
   uchun o'zingiz manba guruhga sinov xabar yozing) — bir necha soniyada
   asosiy guruhga forward bo'lishi va filtringizga mos kelsa DM kelishi kerak.
5. Admin sifatida `/stats`, `/sources`, `/users`, `/activefilters`, `/errors`
   buyruqlarini sinab ko'ring.

---

## Kundalik boshqaruv

### Loglarni ko'rish
```bash
docker compose logs -f userbot     # userbot loglarini kuzatish
docker compose logs -f bot         # bot loglarini kuzatish
docker compose logs -f             # barcha xizmatlar
```

### Qayta ishga tushirish (restart)
```bash
docker compose restart userbot bot
```

### To'liq to'xtatish / qayta ko'tarish
```bash
docker compose down     # to'xtatish (ma'lumotlar volume'da saqlanib qoladi)
docker compose up -d    # qayta ishga tushirish
```

### Yangilash (kod o'zgargandan keyin)
```bash
git pull   # yoki yangi kodni serverga yuklang
docker compose build
docker compose up -d
```

### Backup (PostgreSQL)
```bash
# Qo'lda backup olish
docker compose exec postgres pg_dump -U cargo_user cargo_db > backup_$(date +%Y%m%d).sql

# Kunlik avtomatik backup uchun cron (masalan har kuni soat 03:00 da):
# crontab -e ga qo'shing:
0 3 * * * cd /path/to/telegram-cargo-forwarder && docker compose exec -T postgres pg_dump -U cargo_user cargo_db > /path/to/backups/backup_$(date +\%Y\%m\%d).sql
```

### Backup'dan tiklash
```bash
cat backup_20260101.sql | docker compose exec -T postgres psql -U cargo_user cargo_db
```

### Eski xabarlarni tozalash (30 kundan eski)
Bu avtomatik emas — cron orqali kuniga bir marta ishga tushirish tavsiya etiladi:
```bash
# crontab -e ga qo'shing (har kuni soat 04:00 da):
0 4 * * * cd /path/to/telegram-cargo-forwarder && docker compose run --rm bot python -m scripts.cleanup_old_messages
```

---

## Muhim texnik eslatmalar

- **Original xabarlar hech qachon o'chirilmaydi/yashirilmaydi** — tizim faqat
  o'qiydi va nusxa (forward) yuboradi, manba guruhga hech qanday yozish
  huquqisiz ishlaydi.
- **Faqat ochiq (public) manba guruhlar** ishlatilgani uchun "📍 Manba" va
  "👤 Yuboruvchi" qatorlarida haqiqiy, ishlaydigan linklar chiqadi. Agar
  kelajakda yopiq guruh qo'shsangiz, tizim avtomatik ravishda o'sha guruh
  uchun linksiz, faqat nom ko'rinishida ko'rsatadi (noto'g'ri link hech
  qachon yaratilmaydi).
- **Parsing 100% aniq emas** — turli formatdagi xabarlar sababli ba'zi
  maydonlar (ayniqsa erkin matnli e'lonlarda) aniqlanmasligi mumkin. Bunday
  holda tizim hech narsani o'ylab topmaydi, faqat original matnni saqlaydi
  va forward qiladi; shunchaki avtomatik filtr moslashtirishga
  qo'shilmaydi. Vaqt o'tishi bilan `app/parser.py` va `app/geodata.py`
  fayllariga yangi kalit so'z/shahar nomlari qo'shib, aniqlikni oshirish mumkin.
- **Duplicate detection** original matn asosida ishlaydi (deyarli bir xil
  matn = duplicate), telefon raqamlardagi farqlarga e'tibor bermaydi.
- **Ma'lumotlar 30 kun saqlanadi** (`.env` dagi `MESSAGE_RETENTION_DAYS`
  orqali o'zgartirilishi mumkin), tozalash cron orqali qo'lda sozlanadi
  (yuqoriga qarang).
- Barcha maxfiy ma'lumotlar (`BOT_TOKEN`, `API_ID`, `API_HASH`, DB parol)
  faqat `.env` faylida — source code ichida yo'q. `.env` faylni hech qachon
  git repository'ga qo'shmang (`.gitignore`ga kiritilgan bo'lishi kerak).

---

## 6-QADAM: Yangi Imkoniyatlar va Boshqaruv

### 6.1 — Interaktiv Admin Panel
Adminlar uchun qulay inline va reply tugmali boshqaruv paneli yaratilgan:
- Telegramda `/admin` buyrug'ini yuboring yoki menyudagi `⚙️ Admin Panel` tugmasini bosing.
- **📡 Kanallar va Guruhlar:** Yangi manba kanallarni bot orqali kiritish, o'chirish yoki vaqtincha to'xtatish.
- **🏙 Shaharlar va Tumanlar:** Dinamik tarzda yangi shahar/tumanlarni qo'shish va chiqarish (geodata avtomatik yangilanadi).
- **🚛 Mashina Rusumlari:** Yangi transport rusumlarini sinonimlari bilan kiritish va boshqarish.
- **⚖️ Yuk Hajmlari / Tonnaj:** Yangi yuk hajmlari (tonna, m³, kg) kiritish.
- **⚡️ Real Session Monitoring:** Userbot ulanish holati (Online/Offline), oxirgi ping vaqti, tinglanayotgan chatlar soni, qayta ishlangan yuklar va rad etilgan taksi/spamlar sonini jonli ko'rish.
- **📊 Umumiy Statistika:** Jami xabarlar, faol filtrlar va foydalanuvchilar soni.
- **🐞 Xatolar Jurnali:** Tizim xatolarini real-time ko'rish va tozalash.
- **🧹 Keshni Tozalash:** Xotira va Redis keshini bitta tugma bilan yangilash.

### 6.2 — Yuk Xabarlarini Saralash (Cargo Filter)
Tizim sun'iy intellekt va ko'p bosqichli tahlil orqali **FAQAT YUK E'LONLARINI** o'tkazadi:
- **Taksi va yo'lovchi e'lonlari** (odam olamiz, 4 kishi, pitak, nexia, cobalt, gentra, bilet va h.k.) avtomatik rad etiladi.
- **Spam, reklama va chat xabarlari** (valyuta, karta, ishga taklif, uy va h.k.) filtrlanadi.
- Forward qilinadigan har bir yuk xabari quyidagi formatda shakllanadi:
  - 📍 **Qayerdan** va 🏁 **Qayerga** Google Maps qidiruv havolasi
  - 🗺 **Google Maps marshrut (Directions)** havolasi
  - 📦 **Yuk turi**, ⚖️ **Og'irligi/Tonnaji**, 🚛 **Transport turi**, 💰 **Narxi**
  - 📞 **Aloqa:** To'g'ri `tel:` va nusxalash oson `<code>` formatidagi telefon raqamlari
  - 👤 **Yuboruvchi** va 📡 **Manba** havolasi

### 6.3 — 32 ta Xabar va Aloqa Testlarini Ishga Tushirish
Barcha 32 ta real xabarlar, telefon formatlari, Google Maps havolalari va filtr matching testlarini tekshirish uchun:
```bash
python -m scripts.run_tests
```
yoki
```bash
python -m unittest tests/test_cargo_suite.py
```

---

## Loyiha tuzilishi

```
telegram-cargo-forwarder/
├── app/
│   ├── config.py              # .env dan barcha sozlamalarni o'qiydi
│   ├── db.py                  # SQLAlchemy engine, session_scope
│   ├── models.py              # DB jadvallari (User, CargoFilter, SourceChat, CustomCity, CustomVehicle, CustomTonnage, UserbotSessionStatus, CargoMessage, ErrorLog)
│   ├── geodata.py             # O'zbekiston viloyat/shahar lug'ati + Google Maps integratsiyasi
│   ├── parser.py              # Yuk xabarlarini saralash (Classifier), telefon va yo'nalish parsing
│   ├── dedup.py               # Duplicate aniqlash
│   ├── matcher.py             # Filtr bilan moslashtirish
│   ├── redis_bus.py           # Redis pub/sub + dedup kesh
│   ├── userbot.py             # Telethon process (manba tinglash + heartbeat)
│   ├── services/
│   │   └── session_service.py # Real session monitoring va xatolar jurnali
│   ├── utils/
│   │   ├── formatting.py      # Google Maps va telefonli chiroyli yuk kartochkasi
│   │   └── logging_config.py  # Logging sozlamalari
│   └── bot/
│       ├── main.py            # Bot API process + DM bildirishnomalar
│       └── handlers/
│           ├── start.py       # /start + Asosiy menyu
│           ├── filter_wizard.py # Filtr forma + boshqarish
│           ├── admin.py       # Interaktiv Admin Panel (Tugmali)
│           └── moderation.py  # Guruh moderatsiyasi
├── tests/
│   └── test_cargo_suite.py    # 32 ta real xabar va aloqa testlari to'plami
├── scripts/
│   ├── init_db.py             # DB jadval yaratish
│   ├── cleanup_old_messages.py # Eski ma'lumot tozalash
│   └── run_tests.py           # 32 ta test sinovlarini ishga tushiruvchi
├── migrations/
│   └── 001_init.sql           # SQL sxema
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```
