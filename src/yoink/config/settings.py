from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str
    owner_id: int
    api_id: int | None = None
    api_hash: str | None = None
    telegram_base_url: str = "https://api.telegram.org/bot"
    log_channel: int | None = None
    log_exception_channel: int | None = None
    required_channel: str | None = None

    # Allowed groups (empty = private only)
    allowed_groups: list[int] = []

    # Proxy
    proxy_1_url: str | None = None
    proxy_2_url: str | None = None
    proxy_strategy: str = "round_robin"
    proxy_domains: list[str] = []
    proxy_2_domains: list[str] = []

    # YouTube
    youtube_pot_enabled: bool = True
    youtube_pot_url: str = "http://localhost:4416"
    youtube_cookie_urls: list[str] = []
    youtube_cookie_strategy: str = "round_robin"

    # Per-service cookies
    instagram_cookie_url: str | None = None
    tiktok_cookie_url: str | None = None
    facebook_cookie_url: str | None = None
    twitter_cookie_url: str | None = None

    # Browser profile for automatic cookie extraction (yt-dlp cookiesfrombrowser)
    # Format: /path/to/profile   - the directory containing Default/Cookies
    browser_profile_path: str | None = None
    # Domains to pull from browser profile when no DB cookie is found.
    # Empty list = use for all domains where DB has no cookie.
    browser_cookie_domains: list[str] = []


    # Limits
    max_file_size_gb: float = 2.0
    download_timeout: int = 1200
    max_playlist_count: int = 50
    rate_limit_per_minute: int = 5
    rate_limit_per_hour: int = 30
    rate_limit_per_day: int = 100

    # Database
    database_url: str = "postgresql+asyncpg://yoink:yoink@localhost:5432/yoink"
    database_echo: bool = False

    # API
    api_port: int = 8000
    api_secret_key: str = "change-me-in-production"
    api_token_expire_minutes: int = 1440  # 24h
    debug: bool = False

    # Default language
    default_language: str = "en"

    @field_validator("proxy_strategy", "youtube_cookie_strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        if v not in ("round_robin", "random"):
            raise ValueError("strategy must be 'round_robin' or 'random'")
        return v

    @model_validator(mode="after")
    def validate_log_channels(self) -> "Settings":
        if self.log_exception_channel is None:
            self.log_exception_channel = self.log_channel
        return self

    @property
    def max_file_size_bytes(self) -> int:
        return int(self.max_file_size_gb * 1024 ** 3)

    def browser_cookies_available(self) -> bool:
        """True if a browser profile is configured."""
        return bool(self.browser_profile_path)


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
