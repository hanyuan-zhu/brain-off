"""
Supervision Skill 工具初始化

将 skills-dev/supervision 的工具注册到主系统的 ToolRegistry
"""
import sys
import os
from pathlib import Path

from src.core.skills.tool_registry import get_tool_registry

# 导入工具函数（从共享服务目录）
from src.services.kimi_agent_tools import (
    get_cad_metadata,
    inspect_region,
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
        print("\n⚠️  [Supervision Skill] 缺少必需的环境变量：")
        for var in missing_vars:
            print(var)
        print("\n请在 .env 文件中配置这些变量")
        return False

    return True


def initialize_supervision_tools():
    """初始化 Supervision Skill 的 8 个工具"""
    # 检查环境变量
    if not check_environment_variables():
        print("⚠️  [Supervision Skill] 环境变量未配置，部分功能可能无法使用")

    registry = get_tool_registry()

    # 工具函数映射
    tool_functions = {
        "get_cad_metadata": get_cad_metadata,
        "inspect_region": inspect_region,
        "extract_cad_entities": extract_cad_entities,
        "convert_dwg_to_dxf": convert_dwg_to_dxf,
        "list_files": list_files,
        "read_file": read_file,
        "write_file": write_file,
        "append_to_file": append_to_file
    }

    # 工具可视化模板
    tool_visualizations = {
        "list_files": {
            "calling": "查看文件",
            "success": "✓ 找到文件",
            "error": "✗ 查看文件失败"
        },
        "read_file": {
            "calling": "读取文件",
            "success": "✓ 文件已读取",
            "error": "✗ 读取失败"
        },
        "write_file": {
            "calling": "写入文件",
            "success": "✓ 文件已保存",
            "error": "✗ 写入失败"
        },
        "append_to_file": {
            "calling": "记录工作日志",
            "success": "✓ 日志已记录",
            "error": "✗ 记录失败"
        },
        "get_cad_metadata": {
            "calling": "读取图纸信息",
            "success": "✓ 图纸信息已获取",
            "error": "✗ 读取失败"
        },
        "inspect_region": {
            "calling": "检查图纸区域",
            "success": "✓ 已检查区域（图片+数据）",
            "error": "✗ 检查失败"
        },
        "extract_cad_entities": {
            "calling": "提取实体数据",
            "success": "✓ 已提取实体数据",
            "error": "✗ 提取失败"
        },
        "convert_dwg_to_dxf": {
            "calling": "转换DWG文件",
            "success": "✓ 已转换为DXF",
            "error": "✗ 转换失败"
        }
    }

    # 注册所有工具
    for tool_def in KIMI_AGENT_TOOLS:
        tool_name = tool_def["function"]["name"]
        if tool_name in tool_functions:
            registry.register_tool(
                name=tool_name,
                schema=_convert_to_openai_schema(tool_def),
                function=tool_functions[tool_name],
                visualization=tool_visualizations.get(tool_name)
            )

    print(f"[Supervision Skill] 已注册 {len(tool_functions)} 个工具")
    return registry


def _convert_to_openai_schema(tool_def: dict) -> dict:
    """
    KIMI_AGENT_TOOLS 已经是 OpenAI 格式，直接返回
    """
    return tool_def
