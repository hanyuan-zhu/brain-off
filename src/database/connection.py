"""
Database connection and engine setup.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from src.config import settings


# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,  # Disable SQL logging for cleaner chat output
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


async def init_db():
    """Initialize database - create all tables."""
    from src.database.models import Base

    async with engine.begin() as conn:
        # Create pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()
