"""
统一的工具初始化模块

在应用启动时初始化所有已注册的skill工具
"""
from src.skills.todo.setup import initialize_todo_tools
from src.skills.cost.setup import initialize_cost_tools


def initialize_all_tools():
    """初始化所有skill的工具"""
    print("🔧 初始化工具...")

    # 初始化 Todo Skill
    initialize_todo_tools()
    print("  ✅ Todo Skill 工具已加载")

    # 初始化 Cost Skill
    try:
        initialize_cost_tools()
        print("  ✅ Cost Skill 工具已加载")
    except Exception as e:
        print(f"  ⚠️  Cost Skill 加载失败: {e}")

    print("✅ 工具初始化完成\n")
