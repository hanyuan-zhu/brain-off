"""
详细调试测试 - 查看实际传递给 LLM 的内容
"""
import asyncio
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.session import AsyncSessionLocal
from src.core.agent.memory_driven_agent import MemoryDrivenAgent


async def test_with_debug():
    """测试并打印详细信息"""
    print("\n" + "=" * 60)
    print("【详细调试测试】")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        agent = MemoryDrivenAgent(db, use_reasoner=False)

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
            print(f"👤 用户: {msg}")

            try:
                result = await agent.process_message(
                    user_message=msg,
                    session_id=session_id
                )

                if result["success"]:
                    session_id = result["session_id"]
                    print(f"🤖 助手: {result['text']}")

                    # 打印上下文信息
                    if "metadata" in result:
                        metadata = result["metadata"]
                        print(f"\n📊 元数据:")
                        print(f"  - Skill ID: {metadata.get('skill_id', 'None')}")
                        print(f"  - 工具调用次数: {len(metadata.get('tool_calls', []))}")

                        # 打印对话历史长度
                        if "context_content" in metadata:
                            context = metadata["context_content"]
                            print(f"  - 对话历史条数: {len(context.get('conversation_history', []))}")
                            print(f"  - 线上记忆条数: {len(context.get('online_memories', []))}")
                            print(f"  - 总消息数: {context.get('total_messages', 0)}")

                            # 打印对话历史内容
                            if context.get('conversation_history'):
                                print(f"\n  📝 对话历史:")
                                for j, hist_msg in enumerate(context['conversation_history'], 1):
                                    print(f"    {j}. [{hist_msg['role']}] {hist_msg['content']}")
                else:
                    print(f"❌ 错误: {result.get('error', 'Unknown')}")
                    break
            except Exception as e:
                print(f"❌ 异常: {e}")
                import traceback
                traceback.print_exc()
                break


async def main():
    try:
        await test_with_debug()
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
