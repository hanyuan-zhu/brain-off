"""
完整的 CLI 对话测试脚本

测试场景：
1. 简单问候
2. 创建任务
3. 多轮对话（上下文保持）
4. 搜索任务
5. 更新任务
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.session import get_db
from src.core.agent.memory_driven_agent import MemoryDrivenAgent
from src.skills.todo.setup import initialize_todo_tools


class ConversationTester:
    """对话测试器"""

    def __init__(self):
        self.agent = None
        self.session_id = None
        self.test_results = []

    async def setup(self):
        """初始化"""
        print("🔧 初始化工具...")
        initialize_todo_tools()
        print("✅ 工具初始化完成\n")

        print("🤖 创建 Agent...")
        async for db in get_db():
            self.agent = MemoryDrivenAgent(db, use_reasoner=False)
            print("✅ Agent 创建完成\n")
            break

    async def test_conversation(self, test_name: str, user_message: str, expected_skill: str = None):
        """测试单轮对话"""
        print(f"\n{'='*60}")
        print(f"📝 测试: {test_name}")
        print(f"{'='*60}")
        print(f"👤 用户: {user_message}\n")

        result = await self.agent.process_message(
            user_message,
            session_id=self.session_id
        )

        if not self.session_id:
            self.session_id = result.get('session_id')

        # 记录结果
        test_result = {
            "test_name": test_name,
            "user_message": user_message,
            "success": result.get('success'),
            "skill_id": result.get('metadata', {}).get('skill_id', ''),
            "tool_calls": len(result.get('metadata', {}).get('tool_calls', [])),
            "iterations": result.get('iterations', 0),
            "response": result.get('text', 'N/A')
        }

        self.test_results.append(test_result)

        # 打印结果
        print(f"🤖 助手: {result.get('text', 'N/A')}\n")
        print(f"📊 元数据:")
        print(f"   - Skill: {test_result['skill_id'] or '(无)'}")
        print(f"   - 工具调用: {test_result['tool_calls']} 次")
        print(f"   - 迭代次数: {test_result['iterations']}")
        print(f"   - 成功: {'✅' if test_result['success'] else '❌'}")

        # 验证预期
        if expected_skill is not None:
            if test_result['skill_id'] == expected_skill:
                print(f"   - 预期验证: ✅ (期望 '{expected_skill}')")
            else:
                print(f"   - 预期验证: ❌ (期望 '{expected_skill}', 实际 '{test_result['skill_id']}')")

        return result

    def print_summary(self):
        """打印测试总结"""
        print(f"\n\n{'='*60}")
        print("📊 测试总结")
        print(f"{'='*60}\n")

        total = len(self.test_results)
        success = sum(1 for r in self.test_results if r['success'])

        print(f"总测试数: {total}")
        print(f"成功: {success}")
        print(f"失败: {total - success}")
        print(f"成功率: {success/total*100:.1f}%\n")

        print("详细结果:")
        for i, result in enumerate(self.test_results, 1):
            status = "✅" if result['success'] else "❌"
            print(f"{i}. {status} {result['test_name']}")
            print(f"   Skill: {result['skill_id'] or '(无)'}, 工具: {result['tool_calls']}次")


async def main():
    """主测试流程"""
    tester = ConversationTester()
    await tester.setup()

    print("\n" + "="*60)
    print("🧪 开始多轮对话测试")
    print("="*60)

    # === 对话场景 1: 自我介绍和记忆测试 ===
    print("\n\n【场景 1】自我介绍和记忆测试")
    await tester.test_conversation(
        "自我介绍",
        "你好，我叫小明，是一名软件工程师",
        expected_skill=""
    )

    await tester.test_conversation(
        "补充信息",
        "我喜欢用 Python 和 JavaScript 编程",
        expected_skill=""
    )

    await tester.test_conversation(
        "测试记忆召回",
        "我刚才说我叫什么名字？",
        expected_skill=""
    )

    await tester.test_conversation(
        "测试记忆召回2",
        "我喜欢用什么编程语言？",
        expected_skill=""
    )

    # === 对话场景 2: 任务管理多轮对话 ===
    print("\n\n【场景 2】任务管理多轮对话")
    await tester.test_conversation(
        "创建任务1",
        "帮我创建一个任务：学习 Python 异步编程",
        expected_skill="todo"
    )

    await tester.test_conversation(
        "引用上文修改",
        "把这个任务设置为高优先级",
        expected_skill="todo"
    )

    await tester.test_conversation(
        "创建任务2",
        "再创建一个任务：写本周工作周报，明天下午3点截止",
        expected_skill="todo"
    )

    await tester.test_conversation(
        "创建任务3",
        "还要创建一个任务：准备团队分享PPT",
        expected_skill="todo"
    )

    await tester.test_conversation(
        "搜索任务",
        "帮我找一下关于学习的任务",
        expected_skill="todo"
    )

    await tester.test_conversation(
        "列出所有任务",
        "列出我所有的任务",
        expected_skill="todo"
    )

    # 打印总结
    tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
