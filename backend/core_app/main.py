from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core_app.api.adaptix_ai_router import router as adaptix_ai_router
from core_app.api.ai_shell_router import router as ai_shell_router
from core_app.api.auth_router import router as auth_router
from core_app.api.founder_ai_router import router as founder_ai_router
from core_app.api.health_router import router as health_router
from core_app.api.system_health_router import router as system_health_router
from core_app.config import settings
from core_app.database import init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup: Initialize database
    init_database()
    yield
    # Shutdown: Cleanup if needed (currently none)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)
origins = settings.get_cors_origins_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(ai_shell_router)
app.include_router(founder_ai_router)
app.include_router(system_health_router)
app.include_router(adaptix_ai_router)
