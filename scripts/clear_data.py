"""
清空数据库数据 - 保留表结构，删除所有数据
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from src.config import settings


async def clear_all_data():
    """清空所有表的数据，但保留表结构"""
    engine = create_async_engine(settings.database_url, echo=True)

    async with engine.begin() as conn:
        print("\n开始清空数据...")

        # 按照依赖顺序删除数据（先删除有外键的表）
        tables = [
            "task_tags",        # 任务-标签关联表
            "conversations",    # 对话历史
            "tasks",            # 任务表
            "tags",             # 标签表
        ]

        for table in tables:
            await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            print(f"  ✓ 清空表: {table}")

        print("\n✓ 所有数据已清空")
        print("✓ 表结构保留完整")

    await engine.dispose()
    print("\n数据库已准备就绪，可以开始测试！\n")


if __name__ == "__main__":
    asyncio.run(clear_all_data())
