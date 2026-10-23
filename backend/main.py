from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.auth_routes import router as auth_router
from backend.api.developer_routes import router as developer_router
from backend.api.knowledge_routes import router as knowledge_router
from backend.api.routes import router as app_router
from backend.api.ticket_routes import router as ticket_router
from backend.errors import register_error_handlers
from core.config import get_settings

settings = get_settings()
settings.data_root.mkdir(parents=True, exist_ok=True)
settings.uploads_root.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    import logging

    from backend.services.cms import get_cms
    from databases.mongo.memory import get_memory
    from databases.psql.base import close_database, init_database

    log = logging.getLogger(__name__)
    db_info = await init_database()
    get_cms()
    get_memory()
    try:
        from databases.psql.base import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            from backend.services import accounts as accounts_svc

            await accounts_svc.ensure_default_group(session)
            await accounts_svc.ensure_bootstrap_developer(session)
            await session.commit()
    except Exception as exc:
        log.warning("ساخت گروه/دولوپر پیش‌فرض ناموفق: %s", exc)

    async def _warm_stack() -> None:
        def _warm() -> dict:
            from core.chunking import split_into_chunks
            from core.embedding import get_embedding_model

            chunks = split_into_chunks(
                "گرم‌کردن چانکر و امبدر برای دایان. این متن تست است.",
                chunk_size=80,
                overlap=10,
            )
            emb = get_embedding_model()
            vec = emb.embed_query("warm up dayan embedding")
            return {"chunks": len(chunks), "dim": len(vec)}

        try:
            info = await asyncio.to_thread(_warm)
            log.info("embedder/chunking آماده: %s", info)
            app.state.embed_warm = info
        except Exception as exc:
            log.warning("گرم‌کردن امبدر/چانک ناموفق: %s", exc)
            app.state.embed_warm = {"ok": False, "error": str(exc)[:160]}

        try:
            from backend.services.temporal_client import temporal_ping

            app.state.temporal = await temporal_ping()
        except Exception as exc:
            app.state.temporal = {"ok": False, "error": str(exc)[:120]}

    asyncio.create_task(_warm_stack())
    app.state.db_info = db_info
    yield
    await close_database()


app = FastAPI(
    title="دایان — API",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS فقط برای دامنه‌های واقعی فرانت — هرگز *
_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

register_error_handlers(app)
app.include_router(auth_router, prefix="/api")
app.include_router(app_router, prefix="/api")
app.include_router(ticket_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(developer_router, prefix="/api")
app.mount("/files", StaticFiles(directory=str(settings.uploads_root)), name="files")


@app.middleware("http")
async def attach_request_meta(request: Request, call_next):
    """آی‌پی را برای rate limit و audit در state نگه می‌داریم."""
    forwarded = request.headers.get("x-forwarded-for", "")
    request.state.client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "")
    )
    return await call_next(request)
