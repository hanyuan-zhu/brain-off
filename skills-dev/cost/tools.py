"""
工程造价 Skill 工具实现

整合所有工具函数，供LLM调用
"""

from typing import Dict, Any, List, Optional

# 导入所有服务模块
from services.vision_service import (
    convert_cad_to_image,
    analyze_drawing_visual,
    extract_drawing_annotations,
    VISION_TOOL_DEFINITIONS
)

from services.quota_service import (
    search_quota_standard,
    add_quota_to_database,
    update_quota_from_search,
    QUOTA_TOOL_DEFINITIONS
)

from services.plan_service import (
    create_analysis_plan,
    update_plan_progress,
    get_plan_context,
    add_plan_note,
    PLAN_TOOL_DEFINITIONS
)

from services.boq_service import (
    create_boq_item,
    update_boq_item,
    query_boq,
    calculate_boq_total,
    BOQ_TOOL_DEFINITIONS
)

from services.export_service import (
    export_boq_to_excel,
    EXPORT_TOOL_DEFINITIONS
)

from services.dwg_converter import (
    convert_dwg_to_dxf,
    CONVERTER_TOOL_DEFINITIONS
)


# ============================================
# CAD 数据工具（基础实现）
# ============================================

def load_cad_file(file_path: str) -> Dict[str, Any]:
    """
    加载并解析CAD文件

    Args:
        file_path: CAD文件路径（支持DXF/DWG）

    Returns:
        Dict包含：
        - success: bool
        - data: {file_id, filename, metadata, layers, entity_count}
        - error: str (如果失败)
    """
    try:
        import os
        from pathlib import Path

        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}"
            }

        # 检查文件扩展名
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in ['.dxf', '.dwg']:
            return {
                "success": False,
                "error": f"不支持的文件格式: {file_ext}，仅支持 .dxf 和 .dwg"
            }

        # 如果是 DWG 文件，提示需要转换
        if file_ext == '.dwg':
            return {
                "success": False,
                "error": "DWG 文件需要先转换为 DXF 格式。请使用 convert_dwg_to_dxf 工具进行自动转换，或手动使用 ODA File Converter。",
                "suggestion": "可以调用 convert_dwg_to_dxf 工具自动转换此文件"
            }

        # 使用 ezdxf 读取 DXF 文件
        try:
            import ezdxf
        except ImportError:
            return {
                "success": False,
                "error": "需要安装 ezdxf 库。请运行: pip install ezdxf"
            }

        # 读取 DXF 文件
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        # 提取图层信息
        layers_info = {}
        for entity in msp:
            layer_name = entity.dxf.layer
            if layer_name not in layers_info:
                layers_info[layer_name] = {
                    "entity_count": 0,
                    "entity_types": {}
                }
            layers_info[layer_name]["entity_count"] += 1

            entity_type = entity.dxftype()
            if entity_type not in layers_info[layer_name]["entity_types"]:
                layers_info[layer_name]["entity_types"][entity_type] = 0
            layers_info[layer_name]["entity_types"][entity_type] += 1

        # 获取文件元数据
        filename = Path(file_path).name
        file_size = os.path.getsize(file_path)

        # 获取单位信息
        try:
            units = str(doc.units)
        except:
            units = "Unknown"

        return {
            "success": True,
            "data": {
                "file_id": file_path,  # 使用文件路径作为临时ID
                "filename": filename,
                "file_path": file_path,
                "metadata": {
                    "dxf_version": doc.dxfversion,
                    "file_size": file_size,
                    "units": units
                },
                "layers": layers_info,
                "entity_count": len(list(msp)),
                "layer_count": len(layers_info)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"加载CAD文件失败: {str(e)}"
        }


def extract_cad_entities(
    file_id: str,
    entity_types: Optional[List[str]] = None,
    layers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    从CAD文件提取特定实体

    Args:
        file_id: CAD文件ID（文件路径）
        entity_types: 实体类型列表（如：['LINE', 'CIRCLE', 'TEXT']）
        layers: 图层过滤列表

    Returns:
        Dict包含：
        - success: bool
        - data: {entities: [{type, layer, properties, coordinates}]}
        - error: str
    """
    try:
        import os

        # file_id 实际上是文件路径
        file_path = file_id

        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}"
            }

        try:
            import ezdxf
        except ImportError:
            return {
                "success": False,
                "error": "需要安装 ezdxf 库。请运行: pip install ezdxf"
            }

        # 读取 DXF 文件
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        entities = []

        for entity in msp:
            entity_type = entity.dxftype()
            entity_layer = entity.dxf.layer

            # 过滤实体类型
            if entity_types and entity_type not in entity_types:
                continue

            # 过滤图层
            if layers and entity_layer not in layers:
                continue

            # 提取实体数据
            entity_data = {
                "type": entity_type,
                "layer": entity_layer,
                "handle": entity.dxf.handle,
                "properties": {},
                "coordinates": {}
            }

            # 根据实体类型提取几何信息
            if entity_type == "LINE":
                entity_data["coordinates"] = {
                    "start": (entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z),
                    "end": (entity.dxf.end.x, entity.dxf.end.y, entity.dxf.end.z)
                }
                entity_data["properties"]["length"] = entity.dxf.start.distance(entity.dxf.end)

            elif entity_type == "CIRCLE":
                entity_data["coordinates"] = {
                    "center": (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z),
                    "radius": entity.dxf.radius
                }
                entity_data["properties"]["area"] = 3.14159 * entity.dxf.radius ** 2
                entity_data["properties"]["circumference"] = 2 * 3.14159 * entity.dxf.radius

            elif entity_type == "ARC":
                entity_data["coordinates"] = {
                    "center": (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z),
                    "radius": entity.dxf.radius,
                    "start_angle": entity.dxf.start_angle,
                    "end_angle": entity.dxf.end_angle
                }

            elif entity_type == "LWPOLYLINE":
                points = [(p[0], p[1]) for p in entity.get_points()]
                entity_data["coordinates"]["points"] = points
                entity_data["properties"]["is_closed"] = entity.closed

            elif entity_type == "POLYLINE":
                points = [(v.dxf.location.x, v.dxf.location.y, v.dxf.location.z)
                         for v in entity.vertices]
                entity_data["coordinates"]["points"] = points
                entity_data["properties"]["is_closed"] = entity.is_closed

            elif entity_type == "TEXT":
                entity_data["coordinates"]["insert"] = (
                    entity.dxf.insert.x,
                    entity.dxf.insert.y,
                    entity.dxf.insert.z
                )
                entity_data["properties"]["text"] = entity.dxf.text
                entity_data["properties"]["height"] = entity.dxf.height

            elif entity_type == "MTEXT":
                entity_data["coordinates"]["insert"] = (
                    entity.dxf.insert.x,
                    entity.dxf.insert.y,
                    entity.dxf.insert.z
                )
                entity_data["properties"]["text"] = entity.text
                entity_data["properties"]["char_height"] = entity.dxf.char_height

            entities.append(entity_data)

        return {
            "success": True,
            "data": {
                "entities": entities,
                "total_count": len(entities)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"提取实体失败: {str(e)}"
        }


def calculate_cad_measurements(
    entities: List[Dict[str, Any]],
    calculation_type: str
) -> Dict[str, Any]:
    """
    计算CAD实体的工程量

    Args:
        entities: 实体列表（从extract_cad_entities获取）
        calculation_type: 计算类型（length/area/volume/count）

    Returns:
        Dict包含：
        - success: bool
        - data: {total, unit, details: [{entity_id, value}]}
        - error: str
    """
    try:
        import math

        if calculation_type not in ['length', 'area', 'volume', 'count']:
            return {
                "success": False,
                "error": f"不支持的计算类型: {calculation_type}。支持的类型: length, area, volume, count"
            }

        total = 0
        details = []

        for entity in entities:
            entity_type = entity.get("type")
            entity_handle = entity.get("handle", "unknown")
            value = 0

            # 计数类型
            if calculation_type == "count":
                value = 1
                total += 1
                details.append({
                    "entity_id": entity_handle,
                    "entity_type": entity_type,
                    "value": value
                })
                continue

            # 长度计算
            if calculation_type == "length":
                if entity_type == "LINE":
                    value = entity.get("properties", {}).get("length", 0)

                elif entity_type == "CIRCLE":
                    value = entity.get("properties", {}).get("circumference", 0)

                elif entity_type == "ARC":
                    coords = entity.get("coordinates", {})
                    radius = coords.get("radius", 0)
                    start_angle = coords.get("start_angle", 0)
                    end_angle = coords.get("end_angle", 0)
                    angle_diff = abs(end_angle - start_angle)
                    value = radius * math.radians(angle_diff)

                elif entity_type in ["LWPOLYLINE", "POLYLINE"]:
                    points = entity.get("coordinates", {}).get("points", [])
                    for i in range(len(points) - 1):
                        p1 = points[i]
                        p2 = points[i + 1]
                        dx = p2[0] - p1[0]
                        dy = p2[1] - p1[1]
                        value += math.sqrt(dx**2 + dy**2)

                    # 如果是闭合的，加上最后一段
                    if entity.get("properties", {}).get("is_closed") and len(points) > 2:
                        p1 = points[-1]
                        p2 = points[0]
                        dx = p2[0] - p1[0]
                        dy = p2[1] - p1[1]
                        value += math.sqrt(dx**2 + dy**2)

            # 面积计算
            elif calculation_type == "area":
                if entity_type == "CIRCLE":
                    value = entity.get("properties", {}).get("area", 0)

                elif entity_type in ["LWPOLYLINE", "POLYLINE"]:
                    # 使用鞋带公式计算多边形面积
                    points = entity.get("coordinates", {}).get("points", [])
                    if len(points) >= 3:
                        area = 0
                        for i in range(len(points)):
                            j = (i + 1) % len(points)
                            area += points[i][0] * points[j][1]
                            area -= points[j][0] * points[i][1]
                        value = abs(area) / 2

            if value > 0:
                total += value
                details.append({
                    "entity_id": entity_handle,
                    "entity_type": entity_type,
                    "value": round(value, 4)
                })

        # 确定单位
        unit_map = {
            "length": "m",
            "area": "m²",
            "volume": "m³",
            "count": "个"
        }

        return {
            "success": True,
            "data": {
                "total": round(total, 4),
                "unit": unit_map.get(calculation_type, ""),
                "calculation_type": calculation_type,
                "entity_count": len(entities),
                "calculated_count": len(details),
                "details": details
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"计算失败: {str(e)}"
        }


# ============================================
# 通用网络搜索工具
# ============================================

def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    通用网络搜索（用于查询定额、规范等）

    Args:
        query: 搜索关键词
        max_results: 最大结果数

    Returns:
        Dict包含：
        - success: bool
        - data: {results: [{title, url, snippet}]}
        - error: str
    """
    try:
        # TODO: 实现网络搜索（可使用 requests + BeautifulSoup）
        return {
            "success": False,
            "error": "网络搜索功能需要实现"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"搜索失败: {str(e)}"
        }


# ============================================
# 工具注册信息（供 LLM 调用）
# ============================================

CAD_TOOL_DEFINITIONS = [
    {
        "name": "load_cad_file",
        "description": "加载并解析CAD文件（DXF/DWG格式），提取基本信息和元数据",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "CAD文件的完整路径"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "extract_cad_entities",
        "description": "从CAD文件中提取特定类型的实体（如墙体、门窗等）",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "CAD文件ID（从load_cad_file获取）"
                },
                "entity_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要提取的实体类型列表，如：['LINE', 'CIRCLE', 'TEXT']"
                },
                "layers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "图层过滤列表（可选）"
                }
            },
            "required": ["file_id"]
        }
    },
    {
        "name": "calculate_cad_measurements",
        "description": "计算CAD实体的工程量（长度、面积、体积等）",
        "input_schema": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "description": "实体列表（从extract_cad_entities获取）"
                },
                "calculation_type": {
                    "type": "string",
                    "enum": ["length", "area", "volume", "count"],
                    "description": "计算类型"
                }
            },
            "required": ["entities", "calculation_type"]
        }
    }
]

WEB_TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "通用网络搜索，用于查询定额标准、施工规范等信息",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数，默认5"
                }
            },
            "required": ["query"]
        }
    }
]

# 整合所有工具定义
TOOL_DEFINITIONS = (
    CAD_TOOL_DEFINITIONS +
    CONVERTER_TOOL_DEFINITIONS +
    VISION_TOOL_DEFINITIONS +
    PLAN_TOOL_DEFINITIONS +
    BOQ_TOOL_DEFINITIONS +
    QUOTA_TOOL_DEFINITIONS +
    EXPORT_TOOL_DEFINITIONS +
    WEB_TOOL_DEFINITIONS
)
