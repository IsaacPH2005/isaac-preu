from collections.abc import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Motor asíncrono para la API (FastAPI)
async_engine = create_async_engine(settings.async_database_url, pool_pre_ping=True, pool_size=10)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

# Motor síncrono para el worker (Celery)
sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True, pool_size=5)
SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
