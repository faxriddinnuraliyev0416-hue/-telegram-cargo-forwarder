FROM python:3.11-slim

WORKDIR /app

# Sistema kutubxonalari (psycopg2 uchun)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Telethon session fayli saqlanadigan joy (volume orqali persist qilinadi)
RUN mkdir -p /app/sessions

CMD ["python", "-m", "app.bot.main"]
