"""
测试完整的 MemoryDrivenAgent
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.session import get_db
from src.core.agent.memory_driven_agent import MemoryDrivenAgent
from src.skills.initialize import initialize_all_tools


async def test_agent():
    """测试完整的 agent"""
    print("=" * 60)
    print("测试完整的 MemoryDrivenAgent")
    print("=" * 60)

    # 初始化工具
    initialize_all_tools()

    async for db in get_db():
        agent = MemoryDrivenAgent(
            db=db,
            use_reasoner=False,
            fixed_skill_id="supervision"
        )

        print("✓ Agent 创建成功\n")

        # 第一次调用
        print("第 1 次调用...")
        try:
            result = await agent.process_message(
                user_message="你好",
                session_id=None
            )
            print(f"✓ 第 1 次成功: {result.get('text', '')[:50]}...\n")
        except Exception as e:
            print(f"❌ 第 1 次失败: {e}\n")
            import traceback
            traceback.print_exc()
            break

        # 第二次调用
        print("第 2 次调用...")
        try:
            result = await agent.process_message(
                user_message="再见",
                session_id=None
            )
            print(f"✓ 第 2 次成功: {result.get('text', '')[:50]}...\n")
        except Exception as e:
            print(f"❌ 第 2 次失败: {e}\n")
            import traceback
            traceback.print_exc()

        break


if __name__ == "__main__":
    asyncio.run(test_agent())
