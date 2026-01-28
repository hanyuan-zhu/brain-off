"""
Script to initialize the database and create initial migration.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import init_db


async def main():
    """Initialize database with pgvector extension and create tables."""
    print("Initializing database...")
    try:
        await init_db()
        print("✓ Database initialized successfully!")
        print("✓ pgvector extension created")
        print("✓ All tables created")
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
