"""Async SQLAlchemy engine and session factory.

The default ``sqlite+aiosqlite`` URL is resolved relative to the backend root
so that running from a different working directory does not scatter database
files around the filesystem.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import BACKEND_ROOT, Settings, get_settings


def normalize_database_url(settings: Settings) -> str:
    """Resolve relative SQLite paths against the backend root directory."""
    url = settings.database_url
    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix):
        raw_path = url[len(prefix):]
        if not raw_path.startswith("/") and not raw_path.startswith(":memory:"):
            resolved = (BACKEND_ROOT / raw_path).resolve()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{resolved.as_posix()}"
        if not raw_path.startswith(":memory:"):
            Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
    elif url.startswith("sqlite:///"):  # allow sync-driver spelling too
        raw_path = url[len("sqlite:///"):]
        if not raw_path.startswith("/") and not raw_path.startswith(":memory:"):
            resolved = (BACKEND_ROOT / raw_path).resolve()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{resolved.as_posix()}"
    return url


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    """Build the async engine with sensible pooling defaults."""
    settings = settings or get_settings()
    url = normalize_database_url(settings)
    kwargs: dict[str, object] = {"echo": False, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["pool_pre_ping"] = False
        # aiosqlite does not support NullPool kwargs the same way; default pool is fine
    engine: AsyncEngine = create_async_engine(url, **kwargs)  # type: ignore[arg-type]
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the session factory bound to ``engine``."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


def resolve_clone_root(clone_root: str) -> Path:
    """Resolve the (possibly relative) clone root against CWD or backend root."""
    path = Path(clone_root)
    if not path.is_absolute():
        path = (Path(os.getcwd()) / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
