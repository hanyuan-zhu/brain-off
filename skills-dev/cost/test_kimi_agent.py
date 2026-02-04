#!/usr/bin/env python3
"""
测试 Kimi Agent - CAD 图纸分析

测试 Kimi Agent 主动调用工具分析 CAD 文件
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.kimi_agent import run_kimi_agent


def test_kimi_agent():
    """测试 Kimi Agent 分析 CAD 文件"""
    print("🤖 测试 Kimi Agent - CAD 图纸分析\n")

    file_path = "temp_workspace/input/甲类仓库建施.dxf"

    # 测试任务
    task = """
请分析这张建筑施工图，完成以下任务：

1. 了解图纸的基本信息（图层、实体数量等）
2. 识别图纸中的关键区域
3. 选择1-2个最重要的区域进行渲染和视觉分析
4. 提取可见的尺寸标注和文字说明
5. 总结图纸的主要内容和建筑构件

请主动思考需要"看"哪些区域，然后调用工具获取信息。
"""

    print("任务描述：")
    print("-" * 60)
    print(task)
    print("-" * 60)

    # 运行 Agent
    result = run_kimi_agent(
        file_path=file_path,
        task=task,
        max_iterations=10
    )

    if result["success"]:
        print("\n" + "=" * 60)
        print("✅ Agent 分析完成")
        print("=" * 60)
        print("\n分析结果：")
        print("-" * 60)
        print(result["data"]["analysis"])
        print("-" * 60)
        print(f"\n总迭代次数: {result['data']['iterations']}")
        print(f"工具调用次数: {len(result['data']['tool_calls_history'])}")
    else:
        print(f"\n❌ Agent 运行失败: {result['error']}")


if __name__ == "__main__":
    test_kimi_agent()
