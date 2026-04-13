"""Database setup and session management."""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core_app.config import settings

# Create declarative base for models
Base = declarative_base()

# Database engine
engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def init_database() -> None:
    """Initialize database engine and session factory."""
    global engine, SessionLocal

    if not settings.database_url:
        # Allow running without database in development with explicit opt-in
        if settings.is_development():
            print(
                "WARNING: No database configured. Running in development mode "
                "without persistence. Set ADAPTIX_AI_DATABASE_URL to enable database."
            )
            return
        raise ValueError(
            "Database URL must be configured. Set ADAPTIX_AI_DATABASE_URL environment variable."
        )

    engine = create_engine(
        str(settings.database_url),
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,  # Verify connections before using
    )

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI routes to get database session.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    if SessionLocal is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() during application startup."
        )

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database session outside FastAPI routes.

    Usage:
        with get_db_context() as db:
            result = db.query(Model).all()
    """
    if SessionLocal is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() during application startup."
        )

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_health() -> tuple[bool, str]:
    """
    Check database connectivity and health.

    Returns:
        Tuple of (is_healthy, status_message)
    """
    if engine is None:
        return False, "database_not_configured"

    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True, "connected"
    except Exception as e:
        return False, f"connection_failed: {type(e).__name__}"
