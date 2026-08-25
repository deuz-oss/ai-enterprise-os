from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Root proyek (folder yang dibuka di VS Code). Semua path relatif
# (.env, data/, dll.) dihitung dari sini agar konsisten terlepas dari
# direktori kerja saat menjalankan uvicorn.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", REPO_ROOT / ".env"), extra="ignore")

    project_name: str = "AI Enterprise OS"
    app_env: str = "dev"
    secret_key: str = "dev-secret-key-change-me"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    admin_email: str = "admin@example.com"
    admin_password: str = "admin1234"

    # Akun pengelola SaaS (tanpa tenant) — dibuat otomatis saat start.
    platform_admin_email: str = "platform@example.com"
    platform_admin_password: str | None = None

    # Rate limit login (sliding window per proses, kunci IP|email)
    login_rate_limit_max: int = 5
    login_rate_limit_window_sec: int = 300
    # Token reset password (satu kali pakai, dikirim via admin secara out-of-band)
    password_reset_ttl_min: int = 30
    # Rate limit endpoint reset password (per IP)
    reset_rate_limit_max: int = 10

    # Folder untuk semua data lokal (database SQLite & dokumen upload),
    # relatif terhadap root proyek.
    data_dir: str = "./data"

    # None/"" => mode lokal: SQLite di <data_dir>/aeos.db dan file di <data_dir>/uploads.
    # Saat Docker Compose, env dioverride ke PostgreSQL + MinIO.
    database_url: str | None = None
    storage_endpoint: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_bucket: str = "documents"

    # Layanan LLM dengan API kompatibel OpenAI (OpenAI, vLLM, Ollama /v1, dll).
    # AI_BASE_URL kosong => seluruh fitur AI nonaktif (endpoint memberi 503).
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str = "gpt-4o-mini"
    ai_embedding_model: str = "text-embedding-3-small"

    # Integrasi tanda tangan elektronik. Nilai ESIGN_PROVIDER:
    # "" (nonaktif) | "sandbox" (simulasi lokal) | "privy" (PrivyID produksi)
    esign_provider: str = ""
    privy_api_url: str | None = None
    privy_merchant_key: str | None = None
    privy_username: str | None = None
    privy_password: str | None = None
    # Rahasia bersama untuk verifikasi header webhook dari penyedia TTE.
    esign_webhook_secret: str | None = None

    # Email notifikasi (mis. keputusan cuti). SMTP_HOST kosong => nonaktif.
    # Kirim berjalan fire-and-forget di thread terpisah, best-effort.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    @field_validator(
        "database_url",
        "storage_endpoint",
        "storage_access_key",
        "storage_secret_key",
        "ai_base_url",
        "ai_api_key",
        "privy_api_url",
        "privy_merchant_key",
        "privy_username",
        "privy_password",
        "esign_webhook_secret",
        "platform_admin_password",
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "smtp_from",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v):
        """Env var kosong (mis. DATABASE_URL=) diperlakukan sebagai tidak disetel."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_root(self) -> Path:
        path = Path(self.data_dir)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.data_root / 'aeos.db'}"

    @property
    def uploads_root(self) -> Path:
        return self.data_root / "uploads"

    @property
    def storage_configured(self) -> bool:
        return bool(self.storage_endpoint and self.storage_access_key and self.storage_secret_key)

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_base_url)

    @property
    def esign_configured(self) -> bool:
        return self.esign_provider in ("sandbox", "privy")

    @property
    def email_enabled(self) -> bool:
        """Notifikasi email aktif bila SMTP_HOST diisi."""
        return bool(self.smtp_host)


@lru_cache
def get_settings() -> Settings:
    return Settings()
