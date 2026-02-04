"""
Todo 任务管理工具
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from src.infrastructure.database.models import Task


async def create_todo(db: AsyncSession, title: str, description: str = "") -> Dict[str, Any]:
    """
    创建新的待办任务

    Args:
        db: 数据库会话
        title: 任务标题
        description: 任务描述（可选）

    Returns:
        创建结果
    """
    try:
        task = Task(
            title=title,
            description=description,
            status="todo"
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        return {
            "success": True,
            "message": f"✓ 任务已创建: {title}",
            "data": {
                "id": str(task.id),
                "title": task.title,
                "description": task.description
            }
        }
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": f"创建任务失败: {str(e)}"
        }


async def list_todos(db: AsyncSession, show_completed: bool = False) -> Dict[str, Any]:
    """
    列出所有待办任务

    Args:
        db: 数据库会话
        show_completed: 是否显示已完成的任务

    Returns:
        任务列表
    """
    try:
        query = select(Task)
        if not show_completed:
            query = query.where(Task.status != "done")

        result = await db.execute(query.order_by(Task.created_at.desc()))
        tasks = result.scalars().all()

        if not tasks:
            return {
                "success": True,
                "message": "暂无任务",
                "data": {"todos": []}
            }

        task_list = []
        for task in tasks:
            status = "✓" if task.status == "done" else "○"
            task_list.append({
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "status_icon": status
            })

        return {
            "success": True,
            "message": f"找到 {len(tasks)} 个任务",
            "data": {"todos": task_list}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取任务列表失败: {str(e)}"
        }


async def update_todo(db: AsyncSession, todo_id: str, completed: bool = True) -> Dict[str, Any]:
    """
    更新任务状态

    Args:
        db: 数据库会话
        todo_id: 任务 ID (UUID 字符串)
        completed: 是否完成

    Returns:
        更新结果
    """
    try:
        from uuid import UUID
        task_uuid = UUID(todo_id)
        result = await db.execute(select(Task).where(Task.id == task_uuid))
        task = result.scalar_one_or_none()

        if not task:
            return {
                "success": False,
                "error": f"任务 ID {todo_id} 不存在"
            }

        task.status = "done" if completed else "todo"
        await db.commit()

        status = "已完成" if completed else "未完成"
        return {
            "success": True,
            "message": f"✓ 任务已标记为{status}: {task.title}",
            "data": {
                "id": str(task.id),
                "title": task.title,
                "status": task.status
            }
        }
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": f"更新任务失败: {str(e)}"
        }


async def delete_todo(db: AsyncSession, todo_id: str) -> Dict[str, Any]:
    """
    删除任务

    Args:
        db: 数据库会话
        todo_id: 任务 ID (UUID 字符串)

    Returns:
        删除结果
    """
    try:
        from uuid import UUID
        task_uuid = UUID(todo_id)
        result = await db.execute(select(Task).where(Task.id == task_uuid))
        task = result.scalar_one_or_none()

        if not task:
            return {
                "success": False,
                "error": f"任务 ID {todo_id} 不存在"
            }

        title = task.title
        await db.execute(delete(Task).where(Task.id == task_uuid))
        await db.commit()

        return {
            "success": True,
            "message": f"✓ 任务已删除: {title}",
            "data": {"id": todo_id}
        }
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": f"删除任务失败: {str(e)}"
        }

