"""
定额知识检索服务

支持三种搜索方式：
1. 向量语义搜索（主要）
2. 关键词全文搜索（辅助）
3. 精确编码查询（快速）

数据来源：
- 爬虫采集：定额站、造价网站
- 增量更新：搜索结果自动入库
- 人工补充：用户反馈和修正
"""

from typing import Dict, Any, List, Optional
import os
from sqlalchemy import text
from src.infrastructure.database.connection import get_session


def search_quota_standard(
    query: str,
    search_type: str = "semantic",
    category: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    搜索定额标准

    Args:
        query: 搜索关键词或描述（如："240mm厚砖墙砌筑"）
        search_type: 搜索类型
            - semantic: 向量语义搜索（推荐）
            - keyword: 关键词全文搜索
            - code: 精确编码查询
        category: 分类过滤（土建/安装/装饰等）
        region: 地区过滤（全国/北京/上海等）
        limit: 返回结果数量

    Returns:
        Dict包含：
        - success: bool
        - data: {
            results: [{
                code, name, unit, base_price,
                work_content, measurement_rules,
                similarity_score
            }],
            total: int
          }
        - error: str
    """
    try:
        session = get_session()

        if search_type == "code":
            # 精确编码查询
            sql = """
                SELECT * FROM cost_quota_standards
                WHERE code = :query
            """
            result = session.execute(text(sql), {"query": query}).fetchone()

            if result:
                return {
                    "success": True,
                    "data": {
                        "results": [dict(result._mapping)],
                        "total": 1
                    }
                }
            else:
                return {
                    "success": True,
                    "data": {"results": [], "total": 0}
                }

        elif search_type == "keyword":
            # 全文搜索
            sql = """
                SELECT *,
                       ts_rank(to_tsvector('chinese', name || ' ' || work_content),
                               plainto_tsquery('chinese', :query)) as rank
                FROM cost_quota_standards
                WHERE to_tsvector('chinese', name || ' ' || work_content) @@
                      plainto_tsquery('chinese', :query)
            """

            if category:
                sql += " AND category = :category"
            if region:
                sql += " AND region = :region"

            sql += " ORDER BY rank DESC LIMIT :limit"

            params = {"query": query, "limit": limit}
            if category:
                params["category"] = category
            if region:
                params["region"] = region

            results = session.execute(text(sql), params).fetchall()

            return {
                "success": True,
                "data": {
                    "results": [dict(r._mapping) for r in results],
                    "total": len(results)
                }
            }

        elif search_type == "semantic":
            # 向量语义搜索
            # TODO: 需要先生成query的embedding
            # 这里返回提示信息
            return {
                "success": False,
                "error": "向量搜索需要先配置embedding服务（将在后续实现）"
            }

        else:
            return {
                "success": False,
                "error": f"不支持的搜索类型: {search_type}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"搜索定额失败: {str(e)}"
        }


def add_quota_to_database(
    code: str,
    name: str,
    category: str,
    unit: str,
    work_content: str,
    measurement_rules: str,
    base_price: Optional[float] = None,
    labor_cost: Optional[float] = None,
    material_cost: Optional[float] = None,
    machine_cost: Optional[float] = None,
    region: str = "全国",
    source: str = "manual",
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    添加定额数据到数据库（用于爬虫或手动补充）

    Args:
        code: 定额编码
        name: 项目名称
        category: 分类
        unit: 单位
        work_content: 工作内容
        measurement_rules: 计量规则
        base_price: 基价
        labor_cost: 人工费
        material_cost: 材料费
        machine_cost: 机械费
        region: 地区
        source: 来源
        metadata: 其他元数据

    Returns:
        Dict包含：
        - success: bool
        - data: {quota_id: str}
        - error: str
    """
    try:
        # TODO: 实现数据插入
        # 1. 生成embedding
        # 2. 插入数据库
        # 3. 返回ID

        return {
            "success": False,
            "error": "添加定额功能尚未实现"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"添加定额失败: {str(e)}"
        }


def update_quota_from_search(
    search_result: str,
    source_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    从搜索结果中提取并更新定额数据库

    Args:
        search_result: 搜索结果文本（可能包含定额信息）
        source_url: 来源URL

    Returns:
        Dict包含：
        - success: bool
        - data: {added_count: int, updated_count: int}
        - error: str
    """
    try:
        # TODO: 实现智能提取和更新
        # 1. 使用LLM解析搜索结果
        # 2. 提取结构化定额信息
        # 3. 检查是否已存在
        # 4. 插入或更新

        return {
            "success": False,
            "error": "自动更新功能尚未实现"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"更新失败: {str(e)}"
        }


# 定额工具定义
QUOTA_TOOL_DEFINITIONS = [
    {
        "name": "search_quota_standard",
        "description": "搜索工程定额标准，支持语义搜索、关键词搜索和编码查询",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索内容：可以是定额编码、项目名称或工作描述"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["semantic", "keyword", "code"],
                    "description": "搜索类型：semantic(语义)、keyword(关键词)、code(编码)"
                },
                "category": {
                    "type": "string",
                    "description": "分类过滤：土建、安装、装饰等"
                },
                "region": {
                    "type": "string",
                    "description": "地区过滤：全国、北京、上海等"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量，默认10"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_quota_to_database",
        "description": "添加新的定额数据到数据库（用于补充定额库）",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "定额编码"},
                "name": {"type": "string", "description": "项目名称"},
                "category": {"type": "string", "description": "分类"},
                "unit": {"type": "string", "description": "单位"},
                "work_content": {"type": "string", "description": "工作内容"},
                "measurement_rules": {"type": "string", "description": "计量规则"},
                "base_price": {"type": "number", "description": "基价"},
                "region": {"type": "string", "description": "地区"}
            },
            "required": ["code", "name", "category", "unit", "work_content", "measurement_rules"]
        }
    },
    {
        "name": "update_quota_from_search",
        "description": "从网络搜索结果中自动提取并更新定额数据库",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_result": {
                    "type": "string",
                    "description": "搜索结果文本"
                },
                "source_url": {
                    "type": "string",
                    "description": "来源URL"
                }
            },
            "required": ["search_result"]
        }
    }
]
