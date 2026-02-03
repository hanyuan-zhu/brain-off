"""
多轮对话测试脚本 - 直接测试 agent
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.session import AsyncSessionLocal
from src.core.agent.memory_driven_agent import MemoryDrivenAgent


async def test_scenario_1():
    """场景 1: 自我介绍和记忆测试"""
    print("\n" + "=" * 60)
    print("【场景 1】自我介绍和记忆测试")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        agent = MemoryDrivenAgent(db, use_reasoner=False)

        conversations = [
            "你好，我叫小明，是一名软件工程师",
            "我喜欢用 Python 和 JavaScript 编程",
            "我刚才说我叫什么名字？",
            "我喜欢用什么编程语言？"
        ]

        session_id = None
        for i, msg in enumerate(conversations, 1):
            print(f"\n第 {i} 轮:")
            print(f"👤 用户: {msg}")

            try:
                result = await agent.process_message(
                    user_message=msg,
                    session_id=session_id
                )

                if result["success"]:
                    session_id = result["session_id"]
                    print(f"🤖 助手: {result['text']}")
                else:
                    print(f"❌ 错误: {result.get('error', 'Unknown')}")
                    break
            except Exception as e:
                print(f"❌ 异常: {e}")
                import traceback
                traceback.print_exc()
                break


async def test_scenario_2():
    """场景 2: 任务管理多轮对话"""
    print("\n" + "=" * 60)
    print("【场景 2】任务管理多轮对话")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        agent = MemoryDrivenAgent(db, use_reasoner=False)

        conversations = [
            "帮我创建一个任务：学习 Python 异步编程",
            "把这个任务设置为高优先级",
            "再创建一个任务：写本周工作周报",
            "列出我所有的任务"
        ]

        session_id = None
        for i, msg in enumerate(conversations, 1):
            print(f"\n第 {i} 轮:")
            print(f"👤 用户: {msg}")

            try:
                result = await agent.process_message(
                    user_message=msg,
                    session_id=session_id
                )

                if result["success"]:
                    session_id = result["session_id"]
                    print(f"🤖 助手: {result['text']}")
                else:
                    print(f"❌ 错误: {result.get('error', 'Unknown')}")
                    break
            except Exception as e:
                print(f"❌ 异常: {e}")
                import traceback
                traceback.print_exc()
                break


async def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("🧪 开始多轮对话测试")
    print("=" * 60)

    try:
        await test_scenario_1()
        await test_scenario_2()

        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
