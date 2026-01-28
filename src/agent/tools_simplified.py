"""
Simplified agent tools - from 6 tools to 3 core tools.

Design Philosophy (inspired by Vercel's approach):
- Trust the model to handle complex reasoning
- Reduce tool count for better performance
- Let the agent decide what to do, not pre-define every step
"""
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.task_repository import TaskRepository
from src.repositories.tag_repository import TagRepository
from src.services.embedding_service import get_embedding_service
from src.services.search_service import SearchService


# ============================================================================
# TOOL 1: database_operation - Unified database operations
# ============================================================================

# Visualization templates for database_operation tool
DATABASE_OPERATION_VISUALIZATION = {
    "create_task": {
        "calling": "【创建任务卡：\"{title}\"】",
        "success": "【✓ 任务已创建】",
        "error": "【✗ 创建失败：{error}】"
    },
    "update_task": {
        "calling": "【更新任务】",
        "success": "【✓ 已更新：\"{title}\"】",
        "error": "【✗ 更新失败：{error}】"
    },
    "delete_task": {
        "calling": "【删除任务】",
        "success": "【✓ 已删除：\"{title}\"】",
        "error": "【✗ 删除失败：{error}】"
    }
}

DATABASE_OPERATION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "database_operation",
        "description": """统一的数据库操作工具。支持任务的创建、更新、删除等操作。

使用场景：
- 捕获想法：创建 status=brainstorm 的任务
- 创建任务：创建 status=inbox 的任务
- 更新任务：修改任务状态、优先级、标签等
- 删除任务：软删除任务
- 管理标签：创建或获取标签""",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create_task", "update_task", "delete_task"],
                    "description": "操作类型"
                },
                "task_data": {
                    "type": "object",
                    "description": "任务数据（用于 create_task 和 update_task）",
                    "properties": {
                        "task_id": {"type": "string", "description": "任务 ID（更新时必需）"},
                        "title": {"type": "string", "description": "任务标题"},
                        "description": {"type": "string", "description": "任务描述"},
                        "status": {
                            "type": "string",
                            "enum": ["brainstorm", "inbox", "active", "waiting", "someday", "completed", "archived"],
                            "description": "任务状态"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["urgent", "high", "medium", "low", "none"],
                            "description": "优先级"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "标签列表"
                        },
                        "energy_level": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "所需精力"
                        },
                        "estimated_duration": {
                            "type": "integer",
                            "description": "预计耗时（分钟）"
                        }
                    }
                }
            },
            "required": ["operation"]
        }
    }
}


async def database_operation_tool(
    db: AsyncSession,
    operation: str,
    task_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute unified database operations.

    Args:
        db: Database session
        operation: Operation type
        task_data: Task data for create/update operations

    Returns:
        Operation result
    """
    task_repo = TaskRepository(db)
    tag_repo = TagRepository(db)
    embedding_service = get_embedding_service()

    try:
        if operation == "create_task":
            if not task_data or "title" not in task_data:
                return {"error": "title is required for create_task"}

            # Generate embedding
            content = f"{task_data['title']}\n{task_data.get('description', '')}"
            embedding = await embedding_service.generate(content)

            # Create task
            task = await task_repo.create(
                title=task_data["title"],
                description=task_data.get("description"),
                status=task_data.get("status", "brainstorm"),
                priority=task_data.get("priority"),
                energy_level=task_data.get("energy_level"),
                estimated_duration=task_data.get("estimated_duration"),
                embedding=embedding
            )

            # Add tags if provided
            if task_data.get("tags"):
                for tag_name in task_data["tags"]:
                    tag = await tag_repo.get_or_create(tag_name)
                    await task_repo.add_tag(task.id, tag.id)

            return {
                "task_id": str(task.id),
                "title": task.title,
                "status": task.status,
                "created_at": task.created_at.isoformat()
            }

        elif operation == "update_task":
            if not task_data or "task_id" not in task_data:
                return {"error": "task_id is required for update_task"}

            task_id = UUID(task_data["task_id"])
            task = await task_repo.get_by_id(task_id)

            if not task:
                return {"error": f"Task {task_id} not found"}

            # Update fields
            update_data = {}
            for field in ["title", "description", "status", "priority", "energy_level", "estimated_duration"]:
                if field in task_data:
                    update_data[field] = task_data[field]

            # Regenerate embedding if title/description changed
            if "title" in update_data or "description" in update_data:
                content = f"{update_data.get('title', task.title)}\n{update_data.get('description', task.description or '')}"
                update_data["embedding"] = await embedding_service.generate(content)

            updated_task = await task_repo.update(task_id, **update_data)

            # Update tags if provided
            if "tags" in task_data:
                # Remove existing tags
                await task_repo.remove_all_tags(task_id)
                # Add new tags
                for tag_name in task_data["tags"]:
                    tag = await tag_repo.get_or_create(tag_name)
                    await task_repo.add_tag(task_id, tag.id)

            return {
                "task_id": str(updated_task.id),
                "title": updated_task.title,
                "status": updated_task.status,
                "updated_at": updated_task.updated_at.isoformat()
            }

        elif operation == "delete_task":
            if not task_data or "task_id" not in task_data:
                return {"error": "task_id is required for delete_task"}

            task_id = UUID(task_data["task_id"])

            # Get task info before deleting (for visualization)
            task = await task_repo.get_by_id(task_id)
            if not task:
                return {"error": f"Task {task_id} not found"}

            task_title = task.title
            await task_repo.soft_delete(task_id)

            return {
                "task_id": str(task_id),
                "title": task_title,
                "deleted": True
            }

        else:
            return {"error": f"Unknown operation: {operation}"}

    except Exception as e:
        return {"error": f"Operation failed: {str(e)}"}


# ============================================================================
# TOOL 2: search - Semantic search (will be upgraded to Sub-Agent later)
# ============================================================================

# Visualization templates for search tool
SEARCH_VISUALIZATION = {
    "calling": "【正在搜索 \"{query}\"】",
    "success": "【找到 {count} 个结果】",
    "error": "【✗ 搜索失败：{error}】"
}

SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search",
        "description": """语义搜索工具。使用向量相似度搜索任务或对话历史。

使用场景：
- 搜索任务："帮我找关于学习的任务"
- 搜索想法："搜索 brainstorm 状态的任务"
- 搜索对话："我之前说过什么关于健身的？"
- 清理重复："找出重复的任务"

注意：未来会升级为 Sub-Agent，支持更智能的检索策略。""",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["tasks", "conversations", "both"],
                    "description": "搜索类型",
                    "default": "tasks"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量",
                    "default": 10
                },
                "status_filter": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "按状态过滤（仅用于任务搜索）"
                },
                "priority_filter": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "按优先级过滤（仅用于任务搜索）"
                }
            },
            "required": ["query"]
        }
    }
}


async def search_tool(
    db: AsyncSession,
    query: str,
    search_type: str = "tasks",
    limit: int = 10,
    status_filter: Optional[List[str]] = None,
    priority_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Execute semantic search.

    Args:
        db: Database session
        query: Search query
        search_type: Type of search (tasks, conversations, both)
        limit: Maximum number of results
        status_filter: Filter by task status
        priority_filter: Filter by task priority

    Returns:
        Search results
    """
    search_service = SearchService(db)

    try:
        results = {}

        if search_type in ["tasks", "both"]:
            tasks = await search_service.search_tasks_semantic(
                query=query,
                limit=limit,
                status_filter=status_filter,
                priority_filter=priority_filter
            )

            results["tasks"] = [
                {
                    "id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "created_at": task.created_at.isoformat()
                }
                for task in tasks
            ]

        if search_type in ["conversations", "both"]:
            # TODO: Implement conversation search when embedding is added
            results["conversations"] = []

        return {
            "query": query,
            "search_type": search_type,
            "results": results,
            "count": len(results.get("tasks", [])) + len(results.get("conversations", []))
        }

    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


# ============================================================================
# Tool Registry
# ============================================================================

CORE_TOOLS = {
    "database_operation": {
        "schema": DATABASE_OPERATION_SCHEMA,
        "function": database_operation_tool,
        "visualization": DATABASE_OPERATION_VISUALIZATION
    },
    "search": {
        "schema": SEARCH_SCHEMA,
        "function": search_tool,
        "visualization": SEARCH_VISUALIZATION
    }
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Get all tool schemas for LLM function calling."""
    return [tool["schema"] for tool in CORE_TOOLS.values()]


def format_tool_visualization(
    tool_name: str,
    arguments: Dict[str, Any],
    stage: str = "calling"
) -> str:
    """
    Format tool call visualization text.

    Args:
        tool_name: Name of the tool
        arguments: Tool arguments
        stage: Visualization stage (calling, success, error)

    Returns:
        Formatted visualization text
    """
    if tool_name not in CORE_TOOLS:
        return f"[调用工具: {tool_name}]"

    visualization = CORE_TOOLS[tool_name].get("visualization")
    if not visualization:
        return f"[调用工具: {tool_name}]"

    # For database_operation, get operation-specific template
    if tool_name == "database_operation":
        operation = arguments.get("operation", "")
        op_viz = visualization.get(operation, {})
        template = op_viz.get(stage, "")

        if not template:
            return f"[{operation}]"

        # Extract data for formatting
        task_data = arguments.get("task_data", {})
        tag_data = arguments.get("tag_data", {})

        # For update_task, prefer title from result data (after update)
        # Otherwise fall back to task_data
        title = arguments.get("title", task_data.get("title", ""))

        # Format template with available data
        try:
            return template.format(
                title=title,
                name=tag_data.get("name", ""),
                error=arguments.get("error", "")
            )
        except KeyError:
            return template

    # For search tool
    elif tool_name == "search":
        template = visualization.get(stage, "")
        if not template:
            return "[搜索]"

        try:
            return template.format(
                query=arguments.get("query", ""),
                count=arguments.get("count", 0),
                error=arguments.get("error", "")
            )
        except KeyError:
            return template

    return f"[调用工具: {tool_name}]"


async def execute_tool(
    tool_name: str,
    db: AsyncSession,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute a tool by name.

    Args:
        tool_name: Name of the tool to execute
        db: Database session
        **kwargs: Tool parameters

    Returns:
        Tool execution result
    """
    if tool_name not in CORE_TOOLS:
        return {"error": f"Unknown tool: {tool_name}"}

    tool_function = CORE_TOOLS[tool_name]["function"]
    try:
        result = await tool_function(db, **kwargs)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
