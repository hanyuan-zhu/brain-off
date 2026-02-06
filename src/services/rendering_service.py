#!/usr/bin/env python3
"""
CAD 渲染服务 - 基于坐标的渐进式渲染

提供三个核心功能：
1. get_drawing_bounds() - 获取图纸边界和关键区域
2. render_drawing_region() - 渲染指定坐标区域
3. render_drawing_overview() - 渲染全图概览
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import math


def get_drawing_bounds(
    file_path: str,
    layers: Optional[List[str]] = None,
    grid_size: int = 1000
) -> Dict[str, Any]:
    """
    获取图纸边界和关键区域

    Args:
        file_path: DXF 文件路径
        layers: 可选的图层过滤
        grid_size: 网格大小（mm），用于区域识别

    Returns:
        Dict 包含：
        - success: bool
        - bounds: 图纸边界 {min_x, min_y, max_x, max_y, width, height}
        - regions: 关键区域列表
        - error: str (如果失败)
    """
    try:
        import ezdxf

        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}"
            }

        # 读取 DXF 文件
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        # 计算图纸边界
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')

        # 存储所有实体的位置信息
        entity_positions = []

        for entity in msp:
            # 图层过滤
            if layers and entity.dxf.layer not in layers:
                continue

            # 获取实体的边界框
            try:
                bbox = _get_entity_bbox(entity)
                if bbox:
                    min_x = min(min_x, bbox['min_x'])
                    min_y = min(min_y, bbox['min_y'])
                    max_x = max(max_x, bbox['max_x'])
                    max_y = max(max_y, bbox['max_y'])

                    # 记录实体位置（用于区域识别）
                    entity_positions.append({
                        'center_x': (bbox['min_x'] + bbox['max_x']) / 2,
                        'center_y': (bbox['min_y'] + bbox['max_y']) / 2,
                        'layer': entity.dxf.layer,
                        'type': entity.dxftype()
                    })
            except:
                continue

        # 如果没有找到任何实体
        if min_x == float('inf'):
            return {
                "success": False,
                "error": "图纸中没有找到有效实体"
            }

        # 计算图纸尺寸
        width = max_x - min_x
        height = max_y - min_y

        bounds = {
            "min_x": round(min_x, 2),
            "min_y": round(min_y, 2),
            "max_x": round(max_x, 2),
            "max_y": round(max_y, 2),
            "width": round(width, 2),
            "height": round(height, 2)
        }

        # 识别关键区域
        regions = _identify_key_regions(
            entity_positions,
            bounds,
            grid_size
        )

        return {
            "success": True,
            "bounds": bounds,
            "regions": regions,
            "total_entities": len(entity_positions)
        }

    except ImportError:
        return {
            "success": False,
            "error": "需要安装 ezdxf 库。请运行: pip install ezdxf"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取图纸边界失败: {str(e)}"
        }


def _get_entity_bbox(entity) -> Optional[Dict[str, float]]:
    """
    获取实体的边界框

    Returns:
        {min_x, min_y, max_x, max_y} 或 None
    """
    entity_type = entity.dxftype()

    try:
        if entity_type == "LINE":
            return {
                'min_x': min(entity.dxf.start.x, entity.dxf.end.x),
                'min_y': min(entity.dxf.start.y, entity.dxf.end.y),
                'max_x': max(entity.dxf.start.x, entity.dxf.end.x),
                'max_y': max(entity.dxf.start.y, entity.dxf.end.y)
            }

        elif entity_type == "CIRCLE":
            cx, cy, r = entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius
            return {
                'min_x': cx - r,
                'min_y': cy - r,
                'max_x': cx + r,
                'max_y': cy + r
            }

        elif entity_type == "ARC":
            cx, cy, r = entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius
            return {
                'min_x': cx - r,
                'min_y': cy - r,
                'max_x': cx + r,
                'max_y': cy + r
            }

        elif entity_type in ["LWPOLYLINE", "POLYLINE"]:
            if entity_type == "LWPOLYLINE":
                points = list(entity.get_points())
            else:
                points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]

            if not points:
                return None

            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            return {
                'min_x': min(xs),
                'min_y': min(ys),
                'max_x': max(xs),
                'max_y': max(ys)
            }

        elif entity_type in ["TEXT", "MTEXT"]:
            x = entity.dxf.insert.x
            y = entity.dxf.insert.y
            # 文字边界框估算（简化处理）
            height = entity.dxf.height if entity_type == "TEXT" else entity.dxf.char_height
            width = height * 10  # 粗略估算
            return {
                'min_x': x,
                'min_y': y,
                'max_x': x + width,
                'max_y': y + height
            }

        elif entity_type == "INSERT":
            x = entity.dxf.insert.x
            y = entity.dxf.insert.y
            # 块引用边界框估算
            return {
                'min_x': x - 100,
                'min_y': y - 100,
                'max_x': x + 100,
                'max_y': y + 100
            }

    except:
        pass

    return None


def _create_full_region(entity_positions: List[Dict], bounds: Dict[str, float]) -> Dict[str, Any]:
    """创建全图区域（作为后备方案）"""
    return {
        "name": "全图区域",
        "bbox": {
            "x": bounds["min_x"],
            "y": bounds["min_y"],
            "width": bounds["width"],
            "height": bounds["height"]
        },
        "entity_count": len(entity_positions),
        "density": len(entity_positions) / (bounds["width"] * bounds["height"]) if bounds["width"] * bounds["height"] > 0 else 0,
        "layers": list(set(e['layer'] for e in entity_positions)),
        "grid_count": 1
    }


def _identify_key_regions(
    entity_positions: List[Dict],
    bounds: Dict[str, float],
    grid_size: int
) -> List[Dict[str, Any]]:
    """
    识别图纸中的关键区域

    使用网格密度分析识别实体集中的区域
    """
    if not entity_positions:
        return []

    # 步骤 1: 将实体分配到网格
    grid_map = {}  # {(grid_x, grid_y): {"entities": [...], "layers": set()}}

    for entity in entity_positions:
        grid_x = int(entity['center_x'] // grid_size)
        grid_y = int(entity['center_y'] // grid_size)
        grid_key = (grid_x, grid_y)

        if grid_key not in grid_map:
            grid_map[grid_key] = {"entities": [], "layers": set()}

        grid_map[grid_key]["entities"].append(entity)
        grid_map[grid_key]["layers"].add(entity['layer'])

    # 步骤 2: 计算密度阈值（使用中位数）
    entity_counts = [len(g["entities"]) for g in grid_map.values()]
    entity_counts.sort()

    if len(entity_counts) == 0:
        return []

    # 使用 75 分位数作为高密度阈值
    percentile_75_idx = int(len(entity_counts) * 0.75)
    density_threshold = entity_counts[percentile_75_idx] if percentile_75_idx < len(entity_counts) else entity_counts[-1]

    # 至少要有 3 个实体才算高密度
    density_threshold = max(density_threshold, 3)

    # 步骤 3: 筛选高密度网格
    high_density_grids = {
        k: v for k, v in grid_map.items()
        if len(v["entities"]) >= density_threshold
    }

    if not high_density_grids:
        # 如果没有高密度区域，返回全图
        return [_create_full_region(entity_positions, bounds)]

    # 步骤 4: 聚类相邻网格
    from services.region_utils import cluster_grids
    regions = cluster_grids(high_density_grids, grid_size)

    # 步骤 5: 按密度排序
    regions.sort(key=lambda r: r['density'], reverse=True)

    return regions if regions else [_create_full_region(entity_positions, bounds)]


# 工具定义
RENDERING_TOOL_DEFINITIONS = [
    {
        "name": "get_drawing_bounds",
        "description": "获取 CAD 图纸的边界和关键区域，用于了解图纸布局和规划渲染策略",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "DXF 文件的完整路径"
                },
                "layers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选的图层过滤列表"
                },
                "grid_size": {
                    "type": "integer",
                    "description": "网格大小（mm），用于区域识别，默认 1000"
                }
            },
            "required": ["file_path"]
        }
    }
]
