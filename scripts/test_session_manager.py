"""
测试 session manager 的行为
"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.agent.state import get_session_manager


def test_session_manager():
    """测试 session manager"""
    print("\n" + "=" * 60)
    print("【测试 Session Manager】")
    print("=" * 60)

    manager = get_session_manager()

    # 创建第一个 session
    print("\n1. 创建第一个 session")
    state1 = manager.create_session()
    session_id = state1.session_id
    print(f"   Session ID: {session_id}")
    print(f"   Session ID 类型: {type(session_id)}")

    # 添加消息
    state1.add_message("user", "你好")
    state1.add_message("assistant", "你好！")
    print(f"   添加 2 条消息")
    print(f"   对话历史长度: {len(state1.conversation_history)}")

    # 尝试用 UUID 获取 session
    print(f"\n2. 用 UUID 获取 session")
    retrieved_state = manager.get_session(session_id)
    if retrieved_state:
        print(f"   ✅ 成功获取 session")
        print(f"   对话历史长度: {len(retrieved_state.conversation_history)}")
    else:
        print(f"   ❌ 无法获取 session")

    # 尝试用字符串获取 session
    print(f"\n3. 用字符串获取 session")
    session_id_str = str(session_id)
    print(f"   Session ID 字符串: {session_id_str}")
    retrieved_state2 = manager.get_session(session_id_str)
    if retrieved_state2:
        print(f"   ✅ 成功获取 session")
    else:
        print(f"   ❌ 无法获取 session (需要 UUID 类型)")

    # 尝试转换后获取
    print(f"\n4. 转换为 UUID 后获取 session")
    try:
        session_id_uuid = UUID(session_id_str)
        retrieved_state3 = manager.get_session(session_id_uuid)
        if retrieved_state3:
            print(f"   ✅ 成功获取 session")
            print(f"   对话历史长度: {len(retrieved_state3.conversation_history)}")
        else:
            print(f"   ❌ 无法获取 session")
    except Exception as e:
        print(f"   ❌ 转换失败: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_session_manager()
