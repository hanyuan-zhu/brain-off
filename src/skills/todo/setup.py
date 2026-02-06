"""
Todo Skill 工具初始化
"""
import json
from pathlib import Path

from src.core.skills.tool_registry import get_tool_registry
from src.skills.todo.tools import (
    database_operation_tool,
    DATABASE_OPERATION_SCHEMA,
    DATABASE_OPERATION_VISUALIZATION
)
from src.skills.todo.search_tools import (
    search_tool,
    SEARCH_SCHEMA,
    SEARCH_VISUALIZATION
)


def _load_todo_visualizations():
    """从 skills/todo/config.json 读取可视化模板。"""
    config_path = Path(__file__).resolve().parents[3] / "skills" / "todo" / "config.json"
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        visualizations = data.get("visualizations")
        return visualizations if isinstance(visualizations, dict) else {}
    except Exception:
        return {}


def initialize_todo_tools():
    """初始化 Todo Skill 的工具"""
    registry = get_tool_registry()
    config_visualizations = _load_todo_visualizations()

    # 注册任务管理工具
    registry.register_tool(
        name="database_operation",
        schema=DATABASE_OPERATION_SCHEMA,
        function=database_operation_tool,
        visualization=config_visualizations.get("database_operation", DATABASE_OPERATION_VISUALIZATION),
    )

    # 注册搜索工具
    registry.register_tool(
        name="search",
        schema=SEARCH_SCHEMA,
        function=search_tool,
        visualization=config_visualizations.get("search", SEARCH_VISUALIZATION),
    )

    return registry
