"""Uygulama ayarları.

Tüm gizli değerler ortam değişkenlerinden gelir; depoda yalnızca `.env.example` bulunur.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    DEMO = "demo"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    api_title: str = "DOU-Synapse API"
    api_version: str = "0.1.0"

    # --- Veritabanı ---------------------------------------------------------
    # API bağlantısı `dou_app` rolüyle kurulmalıdır: bu rol tabloların sahibi değildir ve
    # BYPASSRLS taşımaz, dolayısıyla RLS politikaları gerçekten uygulanır.
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://dou_app@localhost:5432/dou_synapse"),
    )
    # Worker, chunks tablosuna yazabilmek için RLS'i atlayan ayrı bir rolle bağlanır.
    worker_database_url: PostgresDsn | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_echo: bool = False

    # --- Kimlik doğrulama ---------------------------------------------------
    # Supabase JWT'lerini doğrulamak için proje JWT secret'ı (HS256).
    supabase_jwt_secret: str | None = None
    jwt_audience: str = "authenticated"
    jwt_algorithms: list[str] = ["HS256"]

    # Çevrimdışı demo ve yerel geliştirme için kimlik doğrulama bypass'ı.
    # Üretimde açılması ayarların yüklenmesini engeller (aşağıdaki doğrulayıcı).
    dev_auth_enabled: bool = False

    # --- CORS ---------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Yükleme sınırları --------------------------------------------------
    max_upload_bytes: int = 20 * 1024 * 1024
    allowed_upload_extensions: set[str] = {
        ".pdf",
        ".pptx",
        ".md",
        ".txt",
        ".py",
        ".java",
        ".js",
        ".ts",
        ".c",
        ".h",
        ".cpp",
    }

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @model_validator(mode="after")
    def _check_auth_configuration(self) -> Settings:
        if self.dev_auth_enabled and self.is_production:
            raise ValueError(
                "DEV_AUTH_ENABLED üretim ortamında açılamaz. "
                "Bu bayrak yalnızca yerel geliştirme ve çevrimdışı demo içindir."
            )
        if not self.dev_auth_enabled and not self.supabase_jwt_secret:
            raise ValueError("SUPABASE_JWT_SECRET tanımlı olmalı ya da DEV_AUTH_ENABLED açılmalı.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
