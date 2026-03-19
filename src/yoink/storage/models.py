"""SQLAlchemy ORM models."""
from __future__ import annotations
import enum
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, Index,
    Integer, String, Text, UniqueConstraint, ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    moderator = "moderator"
    user = "user"
    restricted = "restricted"
    banned = "banned"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user_id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user, nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    quality: Mapped[str] = mapped_column(String(32), default="best", nullable=False)
    codec: Mapped[str] = mapped_column(String(16), default="avc1", nullable=False)
    container: Mapped[str] = mapped_column(String(8), default="mp4", nullable=False)
    proxy_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proxy_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    keyboard: Mapped[str] = mapped_column(String(8), default="2x3", nullable=False)
    subs_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subs_auto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subs_always_ask: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subs_lang: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    split_size: Mapped[int] = mapped_column(BigInteger, default=2043000000, nullable=False)
    nsfw_blur: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mediainfo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    send_as_file: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    theme: Mapped[str] = mapped_column(String(32), default="macchiato", nullable=False)
    args_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ban_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    cookies: Mapped[list[Cookie]] = relationship(back_populates="user", cascade="all, delete-orphan")
    downloads: Mapped[list[DownloadLog]] = relationship(back_populates="user", cascade="all, delete-orphan")
    group_policies: Mapped[list[UserGroupPolicy]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Cookie(Base):
    __tablename__ = "cookies"
    __table_args__ = (UniqueConstraint("user_id", "domain"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="cookies")


class DownloadLog(Base):
    __tablename__ = "download_log"
    __table_args__ = (Index("idx_download_log_user", "user_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(253))
    title: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[str | None] = mapped_column(String(32))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    duration: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="ok", nullable=False)
    error_msg: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[int | None] = mapped_column(BigInteger)
    thread_id: Mapped[int | None] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    clip_start: Mapped[int | None] = mapped_column(Integer)
    clip_end: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="downloads")


class FileCache(Base):
    __tablename__ = "file_cache"
    __table_args__ = (Index("idx_file_cache_expires", "expires_at"),)
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RateLimit(Base):
    __tablename__ = "rate_limits"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    window: Mapped[str] = mapped_column(String(16), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NsfwDomain(Base):
    """Known adult/NSFW domains. Checked before downloading."""
    __tablename__ = "nsfw_domains"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(253), unique=True, nullable=False)
    note: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class NsfwKeyword(Base):
    """Keywords used for NSFW detection in URL path and media metadata."""
    __tablename__ = "nsfw_keywords"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    note: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram chat_id
    title: Mapped[str | None] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_grant_role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user, nullable=False)
    allow_pm: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    nsfw_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    thread_policies: Mapped[list[ThreadPolicy]] = relationship(back_populates="group", cascade="all, delete-orphan")
    user_policies: Mapped[list[UserGroupPolicy]] = relationship(back_populates="group", cascade="all, delete-orphan")


class ThreadPolicy(Base):
    __tablename__ = "thread_policies"
    __table_args__ = (UniqueConstraint("group_id", "thread_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    thread_id: Mapped[int | None] = mapped_column(BigInteger)  # NULL = main chat
    name: Mapped[str | None] = mapped_column(String(256))  # human-readable topic name
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped[Group] = relationship(back_populates="thread_policies")


class UserGroupPolicy(Base):
    __tablename__ = "user_group_policies"
    __table_args__ = (UniqueConstraint("user_id", "group_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    role_override: Mapped[UserRole | None] = mapped_column(Enum(UserRole))
    allow_pm_override: Mapped[bool | None] = mapped_column(Boolean)

    user: Mapped[User] = relationship(back_populates="group_policies")
    group: Mapped[Group] = relationship(back_populates="user_policies")


class BotSetting(Base):
    """Global bot settings editable via Admin UI. Single-row key-value store."""
    __tablename__ = "bot_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Event(Base):
    """Append-only analytics events table."""
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_user_created", "user_id", "created_at"),
        Index("idx_events_type_created", "event_type", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    group_id: Mapped[int | None] = mapped_column(BigInteger)
    thread_id: Mapped[int | None] = mapped_column(BigInteger)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    url_domain: Mapped[str | None] = mapped_column(String(253))
    format: Mapped[str | None] = mapped_column(String(32))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    duration_sec: Mapped[float | None] = mapped_column(Float)
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
