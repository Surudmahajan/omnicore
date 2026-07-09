"""
OmniCore — Database Layer
SQLAlchemy engine, session management, and database initialization.
SQLite by default; schema is PostgreSQL-compatible for easy migration.
"""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.pool import StaticPool

from config import settings


class Base(DeclarativeBase):
    pass


def _get_engine():
    """Create SQLAlchemy engine with environment-appropriate settings."""
    db_url = settings.database_url

    if db_url.startswith("sqlite"):
        # Ensure the data directory exists for SQLite
        db_path = settings.DATABASE_PATH
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.DEBUG,
        )

        # Enable WAL mode and foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        return engine

    # PostgreSQL / other databases
    return create_engine(db_url, echo=settings.DEBUG, pool_pre_ping=True)


engine = _get_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for use outside of FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Create all tables and seed initial data.
    Called once at application startup.
    """
    import models  # noqa: F401 — import triggers table registration
    Base.metadata.create_all(bind=engine)
