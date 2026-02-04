"""
测试 Cost Skill 集成

验证 cost skill 的工具注册和基本功能
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.session import get_db
from src.core.agent.memory_driven_agent import MemoryDrivenAgent
from src.skills.initialize import initialize_all_tools


async def test_cost_skill():
    """测试 cost skill 基本功能"""

    print("=" * 60)
    print("Cost Skill 集成测试")
    print("=" * 60)
    print()

    # 1. 初始化工具
    print("📋 步骤 1: 初始化工具")
    print("-" * 60)
    initialize_all_tools()
    print()

    # 2. 创建 agent（固定使用 cost skill）
    print("📋 步骤 2: 创建 Agent（固定 cost skill）")
    print("-" * 60)
    async for db in get_db():
        agent = MemoryDrivenAgent(db, use_reasoner=False, fixed_skill_id="cost")
        print("✅ Agent 创建成功")
        print()

        # 3. 测试工具可用性
        print("📋 步骤 3: 检查 Cost Skill 工具")
        print("-" * 60)
        from src.core.skills.tool_registry import get_tool_registry
        registry = get_tool_registry()

        cost_tools = [
            "get_cad_metadata",
            "get_cad_regions",
            "render_cad_region",
            "extract_cad_entities",
            "convert_dwg_to_dxf",
            "list_files",
            "read_file",
            "write_file",
            "append_to_file"
        ]

        for tool_name in cost_tools:
            if tool_name in registry.tools:
                print(f"  ✅ {tool_name}")
            else:
                print(f"  ❌ {tool_name} - 未注册")
        print()

        # 4. 测试简单对话
        print("📋 步骤 4: 测试简单对话")
        print("-" * 60)
        test_message = "你好，我想分析一个CAD图纸"
        print(f"用户: {test_message}")
        print()

        print("助手: ", end="", flush=True)

        # 定义回调函数来处理流式输出
        def stream_callback(chunk):
            if chunk.get("type") == "content":
                print(chunk.get("content", ""), end="", flush=True)

        result = await agent.process_message(
            test_message,
            stream_callback=stream_callback
        )
        print("\n")

        print("=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
        break


if __name__ == "__main__":
    asyncio.run(test_cost_skill())
