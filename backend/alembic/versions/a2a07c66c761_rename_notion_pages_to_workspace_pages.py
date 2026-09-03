"""Rename notion_pages -> workspace_pages (hapus jejak nama produk pihak
ketiga dari skema; halaman ini murni page-tree internal, bukan Notion).

Revision ID: a2a07c66c761
Revises: 6e62b0510adb
Create Date: 2026-09-04
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a2a07c66c761"
down_revision = "6e62b0510adb"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.rename_table("notion_pages", "workspace_pages")
    if _is_pg():
        # Rename index/constraint fisik juga -- SQLite (dipakai test migrasi)
        # tidak mendukung ALTER INDEX/CONSTRAINT RENAME, tapi nama itu tidak
        # dites di sana (test_migrations.py cuma bandingkan nama tabel+kolom).
        op.execute("ALTER INDEX notion_pages_pkey RENAME TO workspace_pages_pkey")
        op.execute("ALTER INDEX ix_notion_pages_tenant_id RENAME TO ix_workspace_pages_tenant_id")
        op.execute("ALTER INDEX ix_notion_pages_parent_id RENAME TO ix_workspace_pages_parent_id")
        op.execute(
            "ALTER TABLE workspace_pages RENAME CONSTRAINT "
            "notion_pages_tenant_id_fkey TO workspace_pages_tenant_id_fkey"
        )
        op.execute(
            "ALTER TABLE workspace_pages RENAME CONSTRAINT "
            "notion_pages_created_by_id_fkey TO workspace_pages_created_by_id_fkey"
        )
        op.execute(
            "ALTER TABLE workspace_pages RENAME CONSTRAINT "
            "notion_pages_parent_id_fkey TO workspace_pages_parent_id_fkey"
        )


def downgrade() -> None:
    op.rename_table("workspace_pages", "notion_pages")
    if _is_pg():
        op.execute("ALTER INDEX workspace_pages_pkey RENAME TO notion_pages_pkey")
        op.execute("ALTER INDEX ix_workspace_pages_tenant_id RENAME TO ix_notion_pages_tenant_id")
        op.execute("ALTER INDEX ix_workspace_pages_parent_id RENAME TO ix_notion_pages_parent_id")
        op.execute(
            "ALTER TABLE notion_pages RENAME CONSTRAINT "
            "workspace_pages_tenant_id_fkey TO notion_pages_tenant_id_fkey"
        )
        op.execute(
            "ALTER TABLE notion_pages RENAME CONSTRAINT "
            "workspace_pages_created_by_id_fkey TO notion_pages_created_by_id_fkey"
        )
        op.execute(
            "ALTER TABLE notion_pages RENAME CONSTRAINT "
            "workspace_pages_parent_id_fkey TO notion_pages_parent_id_fkey"
        )
