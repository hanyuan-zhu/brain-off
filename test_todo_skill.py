"""
测试 todo skill 的多轮对话功能
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.database.session import get_db
from src.core.agent.memory_driven_agent import MemoryDrivenAgent


async def test_todo_skill():
    """测试 todo skill 的完整多轮对话"""

    print("=" * 60)
    print("开始测试 todo skill 多轮对话功能")
    print("=" * 60)

    async for db in get_db():
        # 创建使用固定 todo skill 的 agent
        agent = MemoryDrivenAgent(db, use_reasoner=False, fixed_skill_id="todo")

        # 测试场景
        test_messages = [
            "添加一个任务：学习 Python",
            "再添加一个任务：写项目文档",
            "查看所有任务",
            "把学习 Python 这个任务标记为完成",
            "再查看一下所有任务"
        ]

        session_id = None

        for i, message in enumerate(test_messages, 1):
            print(f"\n{'=' * 60}")
            print(f"第 {i} 轮对话")
            print(f"{'=' * 60}")
            print(f"用户: {message}")
            print()

            try:
                response = await agent.process_message(
                    message,
                    session_id=session_id
                )

                if not session_id:
                    session_id = response["session_id"]

                if response["success"]:
                    print(f"助手: {response['text']}")
                    print(f"\n[元数据]")
                    print(f"  - Skill ID: {response['metadata']['skill_id']}")
                    print(f"  - 迭代次数: {response['iterations']}")
                    print(f"  - 工具调用: {len(response['metadata']['tool_calls'])}")
                else:
                    print(f"❌ 错误: {response['error']}")
                    break

                await db.commit()

            except Exception as e:
                print(f"❌ 处理消息时出错: {str(e)}")
                import traceback
                traceback.print_exc()
                break

        print(f"\n{'=' * 60}")
        print("测试完成")
        print(f"{'=' * 60}")

        break


if __name__ == "__main__":
    asyncio.run(test_todo_skill())
