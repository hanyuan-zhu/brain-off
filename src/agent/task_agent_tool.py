"""
Task Agent Tool - 将 ReActAgent 包装为 Main Agent 的工具
"""
from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession


# Tool Schema
TASK_AGENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "todos",
        "description": "管理 todos",
        "parameters": {
            "type": "object",
            "properties": {
                "user_request": {
                    "type": "string",
                    "description": "用户对 todos 的操作请求"
                }
            },
            "required": ["user_request"]
        }
    }
}


# 可视化模板
TASK_AGENT_VISUALIZATION = {
    "calling": "【切换到任务管理模式】\n",
    "success": "\n【任务管理完成】",
    "error": "\n【任务管理失败：{error}】"
}


def format_task_agent_visualization(stage: str, error: str = "") -> str:
    """格式化可视化文本"""
    template = TASK_AGENT_VISUALIZATION.get(stage, "")
    try:
        return template.format(error=error)
    except KeyError:
        return template


async def task_agent_tool(
    db: AsyncSession,
    user_request: str,
    session_id: Optional[UUID] = None,
    stream_callback=None,
    use_reasoner: bool = True
) -> Dict[str, Any]:
    """
    Task Agent Tool - 将 ReActAgent 包装为工具

    关键设计：
    1. 创建独立的 ReActAgent 实例
    2. 透传 stream_callback（保持流式输出）
    3. 透传 session_id（保持会话连续性）
    4. 返回结构化结果

    Args:
        db: 数据库会话
        user_request: 用户的任务管理请求
        session_id: 会话 ID（用于保持上下文）
        stream_callback: 流式输出回调
        use_reasoner: 是否使用 reasoner 模式

    Returns:
        执行结果
    """
    from src.agent.react_agent import ReActAgent

    # 创建 Task Agent 实例
    task_agent = ReActAgent(db, use_reasoner=use_reasoner)

    # 调用 Task Agent 处理请求
    # 关键：透传 stream_callback 和 session_id
    result = await task_agent.process_message(
        user_message=user_request,
        session_id=session_id,
        stream_callback=stream_callback  # 透传流式回调
    )

    # 返回结构化结果
    return {
        "success": result["success"],
        "response": result["text"],
        "tool_type": "skill",  # 标记为 Skill 类型（直接回复用户的 Sub-agent）
        "iterations": result.get("iterations", 0),
        "error": result.get("error")
    }
