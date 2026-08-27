import datetime
import enum

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, Integer,
    String, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from app.db import Base


def utcnow():
    return datetime.datetime.utcnow()


class ProcessingStatus(str, enum.Enum):
    PARSED = "parsed"                # to'liq yoki qisman parse qilindi
    PARSE_FAILED = "parse_failed"    # yuk e'loni, lekin to'liq parse qilinmadi
    DUPLICATE = "duplicate"          # boshqa manbadan avval kelgan xabar bilan bir xil
    IGNORED = "ignored"              # yuk haqida emas (taksi, odam, spam, reklama va h.k.)


class SourceType(str, enum.Enum):
    GROUP = "group"
    CHANNEL = "channel"


class SourceChat(Base):
    """Yuk e'lonlari kuzatilayotgan manba guruh/kanallar."""
    __tablename__ = "source_chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True)  # public bo'lsa username (@ belgisisiz)
    invite_link = Column(String(255), nullable=True)
    type = Column(Enum(SourceType), default=SourceType.GROUP)
    active = Column(Boolean, default=True)
    message_count = Column(Integer, default=0)
    last_message_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    messages = relationship("CargoMessage", back_populates="source_chat")


class User(Base):
    """Botdan foydalanuvchi bo'lgan (kamida bitta /start yozgan) shaxslar."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    filters = relationship("CargoFilter", back_populates="user", cascade="all, delete-orphan")


class CargoFilter(Base):
    """Foydalanuvchining faol yuk qidiruv filtri."""
    __tablename__ = "cargo_filters"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    origin = Column(String(255), nullable=False)          # Yuk qayerdan
    destination = Column(String(255), nullable=False)     # Yuk qayerga
    vehicle_type = Column(String(255), nullable=True)     # Mashina turi/rusumi
    tonnage = Column(String(100), nullable=True)           # Yuk hajmi/tonnasi (matn, masalan "20 tonna")

    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="filters")


class CargoMessage(Base):
    """Manba guruhlardan kelgan, qayta ishlangan har bir xabar."""
    __tablename__ = "cargo_messages"
    __table_args__ = (
        UniqueConstraint("source_chat_id", "source_message_id", name="uq_source_message"),
        Index("ix_dedup_hash", "dedup_hash"),
    )

    id = Column(Integer, primary_key=True)

    source_chat_id = Column(Integer, ForeignKey("source_chats.id"), nullable=False)
    source_message_id = Column(BigInteger, nullable=False)

    original_sender_id = Column(BigInteger, nullable=True)
    original_sender_username = Column(String(255), nullable=True)
    original_sender_name = Column(String(255), nullable=True)

    original_text = Column(Text, nullable=False)
    message_date = Column(DateTime, nullable=True)

    # Parsing natijalari
    parsed_origin = Column(String(255), nullable=True)
    parsed_destination = Column(String(255), nullable=True)
    parsed_cargo_type = Column(String(255), nullable=True)
    parsed_vehicle_type = Column(String(255), nullable=True)
    parsed_tonnage = Column(String(100), nullable=True)
    parsed_phone = Column(String(255), nullable=True)

    is_cargo = Column(Boolean, default=True)
    rejection_reason = Column(String(255), nullable=True)

    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PARSED)
    dedup_hash = Column(String(64), nullable=False)

    forwarded_to_main_group = Column(Boolean, default=False)
    main_group_message_id = Column(BigInteger, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    source_chat = relationship("SourceChat", back_populates="messages")


class CustomCity(Base):
    """Admin panel orqali qo'shilgan yoki tahrirlangan shahar/tumanlar."""
    __tablename__ = "custom_cities"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    region = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class CustomVehicle(Base):
    """Admin panel orqali qo'shilgan mashina rusumlari."""
    __tablename__ = "custom_vehicles"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    synonyms = Column(Text, nullable=True)  # Vergul bilan ajratilgan sinonimlar
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class CustomTonnage(Base):
    """Admin panel orqali qo'shilgan yuk hajmlari/tonnajlar."""
    __tablename__ = "custom_tonnages"

    id = Column(Integer, primary_key=True)
    label = Column(String(100), unique=True, nullable=False)  # Masalan "20 - 24 tonna", "1 - 3 tonna", "Kub / m3"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class UserbotSessionStatus(Base):
    """Real session monitoring va status ma'lumotlari."""
    __tablename__ = "userbot_session_status"

    id = Column(Integer, primary_key=True)
    session_name = Column(String(255), unique=True, default="userbot_session")
    is_online = Column(Boolean, default=False)
    last_ping_at = Column(DateTime, nullable=True)
    connected_chats_count = Column(Integer, default=0)
    total_processed = Column(Integer, default=0)
    total_forwarded = Column(Integer, default=0)
    total_duplicates = Column(Integer, default=0)
    total_ignored = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ErrorLog(Base):
    """Admin panelida ko'rish uchun xatoliklar jurnali."""
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True)
    source = Column(String(100), nullable=False)   # "userbot", "bot", "parser"
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)

