"""Guard konfigurasi produksi (audit 2026-11-11 Top-20 #6): nilai bawaan yang
tertulis di repo tidak boleh lolos ke produksi."""

import pytest
from app.core import bootstrap
from app.core.config import DEFAULT_SECRET_KEY, Settings
from pydantic import ValidationError

STRONG_KEY = "k" * 64


@pytest.mark.parametrize(
    "secret", [DEFAULT_SECRET_KEY, "change-me-generate-a-random-64-char-hex", "", "pendek"]
)
def test_produksi_menolak_secret_key_lemah(secret):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(app_env="production", secret_key=secret)


def test_produksi_menerima_secret_key_kuat():
    assert Settings(app_env="production", secret_key=STRONG_KEY).secret_key == STRONG_KEY


def test_dev_dan_test_tetap_boleh_nilai_bawaan():
    assert Settings(app_env="dev", secret_key=DEFAULT_SECRET_KEY).secret_key == DEFAULT_SECRET_KEY


def _settings(**overrides):
    base = {"app_env": "production", "secret_key": STRONG_KEY, "admin_email": "boot@example.com"}
    return Settings(**{**base, **overrides})


@pytest.mark.parametrize("password", ["admin1234", "change-me-strong-password", "", "pendek"])
def test_bootstrap_produksi_menolak_password_admin_lemah(client, monkeypatch, password):
    monkeypatch.setattr(bootstrap, "get_settings", lambda: _settings(admin_password=password))
    db = client.testing_session()
    try:
        with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
            bootstrap.run_bootstrap(db)
    finally:
        db.close()


def test_bootstrap_produksi_tidak_mengganggu_admin_yang_sudah_ada(client, monkeypatch):
    db = client.testing_session()
    try:
        monkeypatch.setattr(
            bootstrap, "get_settings", lambda: _settings(admin_password="kata-sandi-kuat-1")
        )
        bootstrap.run_bootstrap(db)
        # Start berikutnya dengan env kosong: admin sudah ada, tidak boleh gagal.
        monkeypatch.setattr(bootstrap, "get_settings", lambda: _settings(admin_password=""))
        bootstrap.run_bootstrap(db)
    finally:
        db.close()
