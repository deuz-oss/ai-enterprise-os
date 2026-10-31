"""Fase 28 lanjutan (rencana §13 kasus 49): backfill revisi 4b32d019ebc2 --
langganan lama jadi bulanan, period_fee = monthly_fee, current_period_end =
akhir siklus terbuka."""

from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _cfg(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_backfill_langganan_lama(tmp_path):
    url = "sqlite:///" + (tmp_path / "bf.db").as_posix()
    command.upgrade(_cfg(url), "57b5ffb1923e")
    engine = create_engine(url)
    tenant, sub, cycle = uuid4().hex, uuid4().hex, uuid4().hex
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, status, billing_mode) "
                    "VALUES (:id, 'T', 'bf-t', 'aktif', 'commercial')"
                ),
                {"id": tenant},
            )
            conn.execute(
                text(
                    "INSERT INTO tenant_subscriptions (id, tenant_id, tier, monthly_fee, "
                    "included_budget, cycle_start_day, auto_renew, status) VALUES "
                    "(:id, :t, 'tier2', 2000000, 2000000, 1, 1, 'aktif')"
                ),
                {"id": sub, "t": tenant},
            )
            conn.execute(
                text(
                    "INSERT INTO tenant_budget_cycles (id, tenant_id, subscription_id, "
                    "period_start, period_end, included_budget, consumed) VALUES "
                    "(:id, :t, :s, '2026-10-01', '2026-10-31', 2000000, 0)"
                ),
                {"id": cycle, "t": tenant, "s": sub},
            )
        command.upgrade(_cfg(url), "head")
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT billing_period, period_fee, discount_percent, current_period_end, "
                    "renewal_attempt_count FROM tenant_subscriptions WHERE id = :id"
                ),
                {"id": sub},
            ).one()
        assert row[0] == "monthly"
        assert float(row[1]) == 2_000_000
        assert float(row[2]) == 0
        assert str(row[3]) == "2026-10-31"
        assert row[4] == 0
    finally:
        engine.dispose()
