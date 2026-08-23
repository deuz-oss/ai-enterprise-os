from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Root proyek (folder yang dibuka di VS Code). Semua path relatif
# (.env, data/, dll.) dihitung dari sini agar konsisten terlepas dari
# direktori kerja saat menjalankan uvicorn.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", REPO_ROOT / ".env"), extra="ignore"
    )

    project_name: str = "AI Enterprise OS"
    app_env: str = "dev"
    secret_key: str = "dev-secret-key-change-me"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    admin_email: str = "admin@example.com"
    admin_password: str = "admin1234"

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

    @field_validator(
        "database_url", "storage_endpoint", "storage_access_key", "storage_secret_key",
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
        return bool(
            self.storage_endpoint and self.storage_access_key and self.storage_secret_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
