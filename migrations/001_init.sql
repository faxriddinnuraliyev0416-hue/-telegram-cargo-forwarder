-- Bu fayl faqat ma'lumot va hujjatlashtirish uchun — haqiqiy jadvallar
-- `scripts/init_db.py` orqali SQLAlchemy modellaridan avtomatik yaratiladi.

CREATE TABLE IF NOT EXISTS source_chats (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    username VARCHAR(255),
    invite_link VARCHAR(255),
    type VARCHAR(20) DEFAULT 'group',
    active BOOLEAN DEFAULT TRUE,
    message_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id);

CREATE TABLE IF NOT EXISTS cargo_filters (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    origin VARCHAR(255) NOT NULL,
    destination VARCHAR(255) NOT NULL,
    vehicle_type VARCHAR(255),
    tonnage VARCHAR(100),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cargo_messages (
    id SERIAL PRIMARY KEY,
    source_chat_id INTEGER NOT NULL REFERENCES source_chats(id),
    source_message_id BIGINT NOT NULL,
    original_sender_id BIGINT,
    original_sender_username VARCHAR(255),
    original_sender_name VARCHAR(255),
    original_text TEXT NOT NULL,
    message_date TIMESTAMP,
    parsed_origin VARCHAR(255),
    parsed_destination VARCHAR(255),
    parsed_cargo_type VARCHAR(255),
    parsed_vehicle_type VARCHAR(255),
    parsed_tonnage VARCHAR(100),
    parsed_phone VARCHAR(255),
    is_cargo BOOLEAN DEFAULT TRUE,
    rejection_reason VARCHAR(255),
    status VARCHAR(20) DEFAULT 'parsed',
    dedup_hash VARCHAR(64) NOT NULL,
    forwarded_to_main_group BOOLEAN DEFAULT FALSE,
    main_group_message_id BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (source_chat_id, source_message_id)
);
CREATE INDEX IF NOT EXISTS ix_dedup_hash ON cargo_messages (dedup_hash);

CREATE TABLE IF NOT EXISTS custom_cities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    region VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS custom_vehicles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    synonyms TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS custom_tonnages (
    id SERIAL PRIMARY KEY,
    label VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS userbot_session_status (
    id SERIAL PRIMARY KEY,
    session_name VARCHAR(255) UNIQUE DEFAULT 'userbot_session',
    is_online BOOLEAN DEFAULT FALSE,
    last_ping_at TIMESTAMP,
    connected_chats_count INTEGER DEFAULT 0,
    total_processed INTEGER DEFAULT 0,
    total_forwarded INTEGER DEFAULT 0,
    total_duplicates INTEGER DEFAULT 0,
    total_ignored INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS error_logs (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
