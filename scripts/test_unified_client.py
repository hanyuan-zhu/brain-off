"""
使用 agent 实际代码结构的测试
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.llm.unified_client import UnifiedLLMClient


async def test_unified_client():
    """测试 UnifiedLLMClient"""
    print("=" * 60)
    print("测试 UnifiedLLMClient")
    print("=" * 60)

    # 创建客户端（和 agent 一样的方式）
    client = UnifiedLLMClient(provider="moonshot", model_name=None)

    print(f"✓ 客户端创建成功")
    print(f"  Provider: {client.provider}")
    print(f"  Model: {client.model}")
    print()

    # 第一次调用
    print("第 1 次调用...")
    response = await client.chat_completion(
        messages=[{"role": "user", "content": "你好"}],
        tools=[{
            "type": "function",
            "function": {
                "name": "test",
                "description": "测试",
                "parameters": {"type": "object", "properties": {}}
            }
        }]
    )
    print(f"✓ 第 1 次成功: {response.choices[0].message.content[:50]}...")
    print()

    # 第二次调用
    print("第 2 次调用...")
    response = await client.chat_completion(
        messages=[{"role": "user", "content": "再见"}],
        tools=[{
            "type": "function",
            "function": {
                "name": "test",
                "description": "测试",
                "parameters": {"type": "object", "properties": {}}
            }
        }]
    )
    print(f"✓ 第 2 次成功: {response.choices[0].message.content[:50]}...")


if __name__ == "__main__":
    asyncio.run(test_unified_client())
