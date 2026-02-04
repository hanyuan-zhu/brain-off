"""
Cost Skill 工具初始化

将 skills-dev/cost 的 Kimi Agent 工具注册到主系统的 ToolRegistry
"""
import sys
import os
from pathlib import Path

# 添加 skills-dev/cost 到 Python 路径
# __file__ 是 src/skills/cost/setup.py
# parent.parent.parent 是项目根目录
project_root = Path(__file__).parent.parent.parent.parent
cost_skill_path = project_root / "skills-dev" / "cost"
sys.path.insert(0, str(cost_skill_path))

from src.core.skills.tool_registry import get_tool_registry

# 导入 Kimi Agent 工具函数
from services.kimi_agent_tools import (
    get_cad_metadata,
    get_cad_regions,
    render_cad_region,
    extract_cad_entities,
    convert_dwg_to_dxf,
    list_files,
    read_file,
    write_file,
    append_to_file,
    KIMI_AGENT_TOOLS
)


def check_environment_variables():
    """检查必需的环境变量"""
    required_vars = {
        "VISION_MODEL_API_KEY": "Kimi/Vision模型API密钥",
        "VISION_MODEL_BASE_URL": "Vision模型API地址"
    }

    missing_vars = []
    for var_name, description in required_vars.items():
        if not os.getenv(var_name):
            missing_vars.append(f"  - {var_name}: {description}")

    if missing_vars:
        print("\n⚠️  [Cost Skill] 缺少必需的环境变量：")
        for var in missing_vars:
            print(var)
        print("\n请在 .env 文件中配置这些变量")
        print("示例：")
        print("  VISION_MODEL_API_KEY=your_kimi_api_key")
        print("  VISION_MODEL_BASE_URL=https://api.moonshot.cn/v1\n")
        return False

    return True


def initialize_cost_tools():
    """初始化 Cost Skill 的 9 个 Kimi Agent 工具"""
    # 检查环境变量
    if not check_environment_variables():
        print("⚠️  [Cost Skill] 环境变量未配置，部分功能可能无法使用")

    registry = get_tool_registry()

    # 工具函数映射
    tool_functions = {
        "get_cad_metadata": get_cad_metadata,
        "get_cad_regions": get_cad_regions,
        "render_cad_region": render_cad_region,
        "extract_cad_entities": extract_cad_entities,
        "convert_dwg_to_dxf": convert_dwg_to_dxf,
        "list_files": list_files,
        "read_file": read_file,
        "write_file": write_file,
        "append_to_file": append_to_file
    }

    # 注册所有工具
    for tool_def in KIMI_AGENT_TOOLS:
        tool_name = tool_def["function"]["name"]
        if tool_name in tool_functions:
            registry.register_tool(
                name=tool_name,
                schema=_convert_to_openai_schema(tool_def),
                function=tool_functions[tool_name],
                visualization=None
            )

    print(f"[Cost Skill] 已注册 {len(tool_functions)} 个工具")
    return registry


def _convert_to_openai_schema(tool_def: dict) -> dict:
    """
    KIMI_AGENT_TOOLS 已经是 OpenAI 格式，直接返回

    格式:
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "...",
            "parameters": {...}
        }
    }
    """
    return tool_def
