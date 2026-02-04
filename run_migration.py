"""
执行数据库迁移
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from src.infrastructure.database.session import get_db


async def run_migration():
    """执行数据库迁移"""

    migration_sql = text("""
    ALTER TABLE skills
    ADD COLUMN IF NOT EXISTS model_config JSONB;
    """)

    print("开始执行数据库迁移...")

    async for db in get_db():
        try:
            await db.execute(migration_sql)
            await db.commit()
            print("✓ 迁移成功：已添加 model_config 列到 skills 表")
        except Exception as e:
            print(f"✗ 迁移失败: {str(e)}")
            await db.rollback()
        break


if __name__ == "__main__":
    asyncio.run(run_migration())
