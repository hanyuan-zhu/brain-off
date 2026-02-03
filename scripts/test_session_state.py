"""
深度调试 - 打印传递给 LLM 的实际 messages
"""
import asyncio
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.session import AsyncSessionLocal
from src.core.agent.memory_driven_agent import MemoryDrivenAgent
from src.core.agent.state import get_session_manager


async def test_messages_content():
    """测试并打印传递给 LLM 的 messages"""
    print("\n" + "=" * 60)
    print("【深度调试 - Messages 内容】")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        agent = MemoryDrivenAgent(db, use_reasoner=False)
        session_manager = get_session_manager()

        conversations = [
            "你好，我叫小明",
            "我喜欢吃苹果",
            "我刚才说我叫什么名字？"
        ]

        session_id = None
        for i, msg in enumerate(conversations, 1):
            print(f"\n{'='*60}")
            print(f"第 {i} 轮对话")
            print(f"{'='*60}")
            print(f"👤 用户输入: {msg}")

            # 处理消息
            result = await agent.process_message(
                user_message=msg,
                session_id=session_id
            )

            if result["success"]:
                session_id = result["session_id"]
                print(f"🤖 助手回复: {result['text']}")

                # 获取 session state 并打印对话历史
                from uuid import UUID
                state = session_manager.get_session(UUID(session_id))
                if state:
                    print(f"\n📝 Session 中的对话历史 ({len(state.conversation_history)} 条):")
                    for j, hist_msg in enumerate(state.conversation_history, 1):
                        content_preview = hist_msg.content[:50] + "..." if len(hist_msg.content) > 50 else hist_msg.content
                        print(f"  {j}. [{hist_msg.role}] {content_preview}")
                else:
                    print(f"\n⚠️ 无法获取 session state")
            else:
                print(f"❌ 错误: {result.get('error', 'Unknown')}")
                break


async def main():
    try:
        await test_messages_content()
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
