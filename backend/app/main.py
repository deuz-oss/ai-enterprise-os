from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.bootstrap import run_bootstrap
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import require_any_licensed_app, require_licensed_app, require_roles
from app.core.storage import ensure_storage
from app.core.tenancy import TenantContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.app_env != "test":
        if settings.app_env == "production":
            # Skema dikelola Alembic (dijalankan entrypoint container).
            # create_all TIDAK dipanggil agar tidak mendahului migrasi.
            ensure_storage()
            with SessionLocal() as db:
                run_bootstrap(db)
        else:
            Base.metadata.create_all(bind=engine)
            ensure_storage()
            with SessionLocal() as db:
                run_bootstrap(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.project_name, version="0.2.0", lifespan=lifespan)

    # Konteks tenant harus terpasang sebelum dependency/endpoint dieksekusi.
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.modules.accounting.router import router as accounting_router
    from app.modules.accounting.transactions_router import router as accounting_tx_router
    from app.modules.ai.router import (
        finance_router as ai_finance_router,
    )
    from app.modules.ai.router import (
        hr_router as ai_hr_router,
    )
    from app.modules.ai.router import (
        recruitment_router as ai_recruitment_router,
    )
    from app.modules.apps.router import router as apps_router
    from app.modules.attendance.router import router as attendance_router
    from app.modules.audit.router import router as audit_router
    from app.modules.auth.router import router as auth_router
    from app.modules.bpjs.router import router as bpjs_router
    from app.modules.chat.router import ai_router as chat_ai_router
    from app.modules.chat.router import router as chat_router
    from app.modules.chat.router import ws_router as chat_ws_router
    from app.modules.clients.router import router as clients_router
    from app.modules.dashboard.router import router as dashboard_router
    from app.modules.esign.router import router as esign_router
    from app.modules.esign.router import webhook_router as esign_webhook_router
    from app.modules.ess.router import router as ess_router
    from app.modules.files import router as files_router
    from app.modules.finance.router import pr_router as payment_request_router
    from app.modules.finance.router import router as finance_router
    from app.modules.hrd.router import router as hrd_router
    from app.modules.notifications.router import router as notifications_router
    from app.modules.pages import router as pages_router
    from app.modules.payroll.router import public_router as payroll_public_router
    from app.modules.payroll.router import router as payroll_router
    from app.modules.platform.router import router as platform_router
    from app.modules.presales.router import router as presales_router
    from app.modules.rates.router import router as rates_router
    from app.modules.recruitment.router import router as recruitment_router
    from app.modules.talentpool.router import branding_admin_router as talentpool_branding_router
    from app.modules.talentpool.router import router as talentpool_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(platform_router, prefix="/api/v1")
    # Guard lisensi Fase 7: endpoint aplikasi tanpa lisensi tenant → 403.
    app.include_router(
        presales_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("sales_crm"))],
    )
    app.include_router(
        clients_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("sales_crm"))],
    )
    app.include_router(
        recruitment_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("recruitment"))],
    )
    app.include_router(
        talentpool_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("recruitment"))],
    )
    app.include_router(
        talentpool_branding_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("recruitment"))],
    )
    app.include_router(
        ai_recruitment_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("ai_addon"))],
    )
    app.include_router(
        ai_hr_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("ai_addon"))],
    )
    app.include_router(
        ai_finance_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("ai_addon"))],
    )
    app.include_router(
        hrd_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("people_ops"))],
    )
    app.include_router(
        ess_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("people_ops"))],
    )
    app.include_router(
        notifications_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("people_ops"))],
    )
    app.include_router(
        esign_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("people_ops"))],
    )
    app.include_router(esign_webhook_router, prefix="/api/v1")  # webhook: tanpa guard lisensi
    app.include_router(
        payroll_router,
        prefix="/api/v1",
        dependencies=[
            # people_ops cukup untuk run internal (Workforce Cloud); run proyek
            # tetap disaring lebih ketat oleh _assert_run_license di service layer.
            Depends(require_any_licensed_app("people_ops", "payroll")),
            Depends(require_roles("operations", "management", "hr")),
        ],
    )
    # Link approval klien ber-token: publik, dikontrol token + kedaluwarsa (ADR/PRD Fase 9).
    app.include_router(payroll_public_router, prefix="/api/v1")
    app.include_router(
        bpjs_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("people_ops"))],
    )
    app.include_router(
        finance_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("finance"))],
    )
    # Payment Request lintas bundle finance (PRD v2.0) — guard finance.
    app.include_router(
        payment_request_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("finance"))],
    )
    app.include_router(
        accounting_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("accounting"))],
    )
    app.include_router(
        accounting_tx_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("accounting"))],
    )
    app.include_router(apps_router, prefix="/api/v1")
    app.include_router(rates_router, prefix="/api/v1")
    # Chat Workspace (Fase 11): gratis di semua paket — tanpa guard lisensi.
    app.include_router(chat_router, prefix="/api/v1")
    # Page tree ala Notion (Fase 7 polish): gratis untuk staf internal.
    app.include_router(pages_router, prefix="/api/v1")
    # Fase 12: fitur AI kolaborasi ter-guard lisensi ai_addon (chat dasar tetap gratis).
    app.include_router(
        chat_ai_router,
        prefix="/api/v1",
        dependencies=[Depends(require_licensed_app("ai_addon"))],
    )
    app.include_router(chat_ws_router, prefix="/api/v1")
    # Absensi harian: bagian dari people_ops (PRD v2.0) — guard bundle.
    app.include_router(
        attendance_router,
        prefix="/api/v1",
        dependencies=[
            Depends(require_licensed_app("people_ops")),
            Depends(require_roles("operations", "hr", "management")),
        ],
    )
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(files_router, prefix="/api/v1")

    @app.get("/health/live")
    def health_live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready():
        return {"status": "ok"}

    return app


app = create_app()
