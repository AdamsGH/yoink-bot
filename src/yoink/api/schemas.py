"""Pydantic v2 request/response schemas for the Yoink API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from yoink.storage.models import UserRole


# Auth

class TelegramIdRequest(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str


# User

class UserResponse(BaseModel):
    id: int
    username: str | None
    first_name: str | None
    role: UserRole
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


class UserUpdateRequest(BaseModel):
    role: UserRole | None = None
    ban_until: datetime | None = None


# Settings

class SettingsResponse(BaseModel):
    user_id: int
    language: str
    quality: str
    codec: str
    container: str
    proxy_enabled: bool
    proxy_url: str | None
    keyboard: str
    subs_enabled: bool
    subs_auto: bool
    subs_always_ask: bool
    subs_lang: str
    split_size: int
    nsfw_blur: bool
    mediainfo: bool
    send_as_file: bool
    theme: str
    args_json: dict


class SettingsUpdateRequest(BaseModel):
    language: str | None = None
    quality: str | None = None
    codec: str | None = None
    container: str | None = None
    proxy_enabled: bool | None = None
    proxy_url: str | None = None
    keyboard: str | None = None
    subs_enabled: bool | None = None
    subs_auto: bool | None = None
    subs_always_ask: bool | None = None
    subs_lang: str | None = None
    split_size: int | None = None
    nsfw_blur: bool | None = None
    mediainfo: bool | None = None
    send_as_file: bool | None = None
    theme: str | None = None
    args_json: dict | None = None


# Downloads

class DownloadLogResponse(BaseModel):
    id: int
    user_id: int
    url: str
    domain: str | None
    title: str | None
    quality: str | None
    file_size: int | None
    duration: float | None
    status: str
    error_msg: str | None
    group_id: int | None
    group_title: str | None
    thread_id: int | None
    message_id: int | None
    clip_start: int | None
    clip_end: int | None
    created_at: datetime


class DownloadListResponse(BaseModel):
    items: list[DownloadLogResponse]
    total: int


# Cookies

class CookieResponse(BaseModel):
    id: int
    user_id: int
    domain: str
    is_valid: bool
    created_at: datetime
    updated_at: datetime


class CookieListResponse(BaseModel):
    items: list[CookieResponse]


class CookieUploadRequest(BaseModel):
    user_id: int
    domain: str
    content: str  # Netscape format


# Groups

class GroupResponse(BaseModel):
    id: int
    title: str | None
    enabled: bool
    auto_grant_role: UserRole
    allow_pm: bool
    nsfw_allowed: bool
    created_at: datetime


class GroupListResponse(BaseModel):
    items: list[GroupResponse]
    total: int


class GroupCreateRequest(BaseModel):
    id: int  # Telegram chat_id
    title: str | None = None
    enabled: bool = False
    auto_grant_role: UserRole = UserRole.user
    allow_pm: bool = True
    nsfw_allowed: bool = False


class GroupUpdateRequest(BaseModel):
    title: str | None = None
    enabled: bool | None = None
    auto_grant_role: UserRole | None = None
    allow_pm: bool | None = None
    nsfw_allowed: bool | None = None


# NSFW

class NsfwDomainResponse(BaseModel):
    id: int
    domain: str
    note: str | None
    created_at: datetime


class NsfwDomainListResponse(BaseModel):
    items: list[NsfwDomainResponse]
    total: int


class NsfwDomainCreateRequest(BaseModel):
    domain: str
    note: str | None = None


class NsfwKeywordResponse(BaseModel):
    id: int
    keyword: str
    note: str | None
    created_at: datetime


class NsfwKeywordListResponse(BaseModel):
    items: list[NsfwKeywordResponse]
    total: int


class NsfwKeywordCreateRequest(BaseModel):
    keyword: str
    note: str | None = None


class NsfwCheckRequest(BaseModel):
    url: str
    title: str = ""
    description: str = ""
    tags: list[str] = []


class NsfwCheckResponse(BaseModel):
    is_nsfw: bool
    reason: str


class ThreadPolicyResponse(BaseModel):
    id: int
    group_id: int
    thread_id: int | None
    name: str | None
    enabled: bool


class ThreadPolicyRequest(BaseModel):
    thread_id: int | None = None
    name: str | None = None
    enabled: bool = True


class UserGroupPolicyResponse(BaseModel):
    user_id: int
    group_id: int
    role_override: UserRole | None
    allow_pm_override: bool | None


class UserGroupPolicyRequest(BaseModel):
    role_override: UserRole | None = None
    allow_pm_override: bool | None = None


# Stats

class EventResponse(BaseModel):
    id: int
    user_id: int | None
    event_type: str
    url_domain: str | None
    file_size: int | None
    duration_sec: float | None
    processing_ms: int | None
    created_at: datetime


class StatsOverview(BaseModel):
    total_downloads: int
    downloads_today: int
    cache_hits_today: int
    errors_today: int
    top_domains: list[dict]  # [{"domain": str, "count": int}]
    downloads_by_day: list[dict]  # [{"date": str, "count": int}] last 30 days


class RetryResponse(BaseModel):
    url: str
    queued: bool
