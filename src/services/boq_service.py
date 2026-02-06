"""
清单编辑工具 - BOQ (Bill of Quantities) 管理

提供清单项目的CRUD操作和计算功能
"""

from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from src.infrastructure.database.connection import get_session
from models import BOQItem, AnalysisPlan


def create_boq_item(
    plan_id: str,
    name: str,
    unit: str,
    quantity: float,
    code: Optional[str] = None,
    unit_price: Optional[float] = None,
    parent_id: Optional[str] = None,
    source: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建清单项目

    Args:
        plan_id: 计划ID
        name: 项目名称
        unit: 计量单位（如：m²、m³、m）
        quantity: 工程量
        code: 项目编码（可选）
        unit_price: 单价（可选）
        parent_id: 父项目ID（用于子清单）
        source: 来源信息（CAD实体、计算规则等）
        metadata: 附加信息

    Returns:
        Dict包含：
        - success: bool
        - data: {item_id, code, name, quantity, total_price}
        - error: str
    """
    try:
        session = get_session()

        # 验证计划存在
        plan = session.query(AnalysisPlan).filter_by(id=uuid.UUID(plan_id)).first()
        if not plan:
            return {
                "success": False,
                "error": f"计划不存在: {plan_id}"
            }

        # 计算合价
        total_price = None
        if unit_price is not None:
            total_price = quantity * unit_price

        # 创建清单项
        item = BOQItem(
            plan_id=uuid.UUID(plan_id),
            parent_id=uuid.UUID(parent_id) if parent_id else None,
            code=code,
            name=name,
            unit=unit,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            source=source,
            metadata=metadata
        )

        session.add(item)
        session.commit()

        return {
            "success": True,
            "data": {
                "item_id": str(item.id),
                "code": item.code,
                "name": item.name,
                "unit": item.unit,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"创建清单项失败: {str(e)}"
        }


def update_boq_item(
    item_id: str,
    **kwargs
) -> Dict[str, Any]:
    """
    更新清单项目

    Args:
        item_id: 清单项ID
        **kwargs: 要更新的字段（name, unit, quantity, unit_price, code等）

    Returns:
        Dict包含：
        - success: bool
        - data: {item_id, updated_fields}
        - error: str
    """
    try:
        session = get_session()
        item = session.query(BOQItem).filter_by(id=uuid.UUID(item_id)).first()

        if not item:
            return {
                "success": False,
                "error": f"清单项不存在: {item_id}"
            }

        # 更新字段
        allowed_fields = ['name', 'code', 'unit', 'quantity', 'unit_price', 'metadata', 'source']
        updated_fields = {}

        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(item, key, value)
                updated_fields[key] = value

        # 重新计算合价
        if 'quantity' in updated_fields or 'unit_price' in updated_fields:
            if item.quantity is not None and item.unit_price is not None:
                item.total_price = item.quantity * item.unit_price
                updated_fields['total_price'] = item.total_price

        item.updated_at = datetime.utcnow()
        session.commit()

        return {
            "success": True,
            "data": {
                "item_id": str(item.id),
                "updated_fields": updated_fields
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"更新清单项失败: {str(e)}"
        }


def query_boq(
    plan_id: str,
    parent_id: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询清单项目

    Args:
        plan_id: 计划ID
        parent_id: 父项目ID（查询子清单）
        category: 分类过滤

    Returns:
        Dict包含：
        - success: bool
        - data: {items: [清单项列表], total_count: int}
        - error: str
    """
    try:
        session = get_session()

        query = session.query(BOQItem).filter_by(plan_id=uuid.UUID(plan_id))

        if parent_id:
            query = query.filter_by(parent_id=uuid.UUID(parent_id))
        else:
            # 默认只查询顶层项目
            query = query.filter_by(parent_id=None)

        items = query.all()

        return {
            "success": True,
            "data": {
                "items": [item.to_dict() for item in items],
                "total_count": len(items)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"查询清单失败: {str(e)}"
        }


def calculate_boq_total(plan_id: str) -> Dict[str, Any]:
    """
    计算清单总价

    Args:
        plan_id: 计划ID

    Returns:
        Dict包含：
        - success: bool
        - data: {total_price, item_count, summary_by_category}
        - error: str
    """
    try:
        session = get_session()
        items = session.query(BOQItem).filter_by(plan_id=uuid.UUID(plan_id)).all()

        total_price = 0.0
        item_count = len(items)

        for item in items:
            if item.total_price:
                total_price += item.total_price

        return {
            "success": True,
            "data": {
                "total_price": round(total_price, 2),
                "item_count": item_count,
                "currency": "CNY"
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"计算总价失败: {str(e)}"
        }


# 清单工具定义
BOQ_TOOL_DEFINITIONS = [
    {
        "name": "create_boq_item",
        "description": "创建工程量清单项目",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string", "description": "计划ID"},
                "name": {"type": "string", "description": "项目名称"},
                "unit": {"type": "string", "description": "计量单位"},
                "quantity": {"type": "number", "description": "工程量"},
                "code": {"type": "string", "description": "项目编码（可选）"},
                "unit_price": {"type": "number", "description": "单价（可选）"},
                "parent_id": {"type": "string", "description": "父项目ID（可选）"}
            },
            "required": ["plan_id", "name", "unit", "quantity"]
        }
    },
    {
        "name": "update_boq_item",
        "description": "更新清单项目信息",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "清单项ID"},
                "name": {"type": "string", "description": "项目名称"},
                "quantity": {"type": "number", "description": "工程量"},
                "unit_price": {"type": "number", "description": "单价"}
            },
            "required": ["item_id"]
        }
    },
    {
        "name": "query_boq",
        "description": "查询清单项目列表",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string", "description": "计划ID"},
                "parent_id": {"type": "string", "description": "父项目ID（可选）"}
            },
            "required": ["plan_id"]
        }
    },
    {
        "name": "calculate_boq_total",
        "description": "计算清单总价",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string", "description": "计划ID"}
            },
            "required": ["plan_id"]
        }
    }
]


