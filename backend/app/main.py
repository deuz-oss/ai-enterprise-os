from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.bootstrap import ensure_admin_user
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.storage import ensure_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.app_env != "test":
        Base.metadata.create_all(bind=engine)
        ensure_storage()
        with SessionLocal() as db:
            ensure_admin_user(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.project_name, version="0.2.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.modules.auth.router import router as auth_router
    from app.modules.clients.router import router as clients_router
    from app.modules.dashboard.router import router as dashboard_router
    from app.modules.files import router as files_router
    from app.modules.hrd.router import router as hrd_router
    from app.modules.presales.router import router as presales_router
    from app.modules.recruitment.router import router as recruitment_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(presales_router, prefix="/api/v1")
    app.include_router(clients_router, prefix="/api/v1")
    app.include_router(recruitment_router, prefix="/api/v1")
    app.include_router(hrd_router, prefix="/api/v1")
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
