from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    # Only log SQL in local dev — production logs would leak query data and are very noisy.
    echo=settings.debug and settings.environment == "local",
    # Conservative pool size: each container runs multiple gunicorn/celery
    # worker processes, each with its own pool. Use Supabase's pgbouncer
    # connection pooler (port 6543, transaction mode) in production to stay
    # under the project's max connection limit.
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    # Supabase (and most managed Postgres hosts) require TLS. asyncpg needs
    # ssl=True explicitly — it does not auto-upgrade plain connections.
    connect_args={"ssl": True} if settings.environment != "local" else {},
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
