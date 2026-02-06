#!/usr/bin/env python3
"""
CAD 渲染器 - 使用 matplotlib 渲染 DXF 文件

提供基于坐标的渐进式渲染功能
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import LineCollection
import numpy as np


# 图层颜色映射（白底配色方案）
LAYER_COLOR_MAP = {
    "WALL": "#CC0000",      # 深红色 - 墙体
    "S_WALL": "#CC0000",    # 深红色 - 墙体
    "COLUMN": "#FF6600",    # 橙色 - 柱子
    "WINDOW": "#0099CC",    # 深青色 - 门窗
    "E_WINDOW": "#0099CC",  # 深青色 - 门窗
    "DIM": "#0000CC",       # 深蓝色 - 标注
    "PUB_DIM": "#0000CC",   # 深蓝色 - 标注
    "TEXT": "#008800",      # 深绿色 - 文字
    "PUB_TEXT": "#008800",  # 深绿色 - 文字
    "AXIS": "#CC8800",      # 深黄色 - 轴线
    "STAIR": "#CC00CC",     # 深紫色 - 楼梯
    "E_STAIR": "#CC00CC",   # 深紫色 - 楼梯
}

DEFAULT_COLOR = "#000000"  # 黑色 - 默认（白底上可见）


def get_layer_color(layer_name: str) -> str:
    """获取图层颜色"""
    layer_upper = layer_name.upper()

    # 精确匹配
    if layer_upper in LAYER_COLOR_MAP:
        return LAYER_COLOR_MAP[layer_upper]

    # 模糊匹配
    for key, color in LAYER_COLOR_MAP.items():
        if key in layer_upper:
            return color

    return DEFAULT_COLOR


def render_drawing_region(
    file_path: str,
    bbox: Dict[str, float],
    output_size: Tuple[int, int] = (2048, 2048),
    layers: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    color_mode: str = "by_layer",
    maintain_aspect_ratio: bool = True
) -> Dict[str, Any]:
    """
    渲染指定坐标区域为 PNG 图片

    Args:
        file_path: DXF 文件路径
        bbox: 边界框 {"x": 1000, "y": 2000, "width": 5000, "height": 3000}
        output_size: 输出尺寸（像素），作为最大尺寸
        layers: 要渲染的图层列表
        output_path: 输出文件路径（可选）
        color_mode: "by_layer" 或 "monochrome"
        maintain_aspect_ratio: 是否保持宽高比（默认 True）

    Returns:
        {"success": True, "image_path": "...", "scale": 0.4096, ...}
    """
    try:
        import ezdxf
        import gc  # 用于垃圾回收

        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}

        # 读取 DXF
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        # 生成输出路径（统一输出到 workspace/rendered/）
        if not output_path:
            output_dir = Path("workspace/rendered")
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"region_{int(bbox['x'])}_{int(bbox['y'])}_{int(bbox['width'])}_{int(bbox['height'])}.png"
            output_path = str(output_dir / filename)

        # 计算实际输出尺寸（保持宽高比）
        if maintain_aspect_ratio:
            aspect_ratio = bbox['width'] / bbox['height']
            max_width, max_height = output_size

            if aspect_ratio > 1:  # 宽图
                actual_width = max_width
                actual_height = int(max_width / aspect_ratio)
            else:  # 高图
                actual_height = max_height
                actual_width = int(max_height * aspect_ratio)
        else:
            actual_width, actual_height = output_size

        # 创建图形（白底）
        fig, ax = plt.subplots(figsize=(actual_width/100, actual_height/100), dpi=100)
        fig.patch.set_facecolor('white')  # 设置图形背景为白色
        ax.set_facecolor('white')  # 设置坐标轴背景为白色
        ax.set_xlim(bbox['x'], bbox['x'] + bbox['width'])
        ax.set_ylim(bbox['y'], bbox['y'] + bbox['height'])
        ax.set_aspect('equal')
        ax.axis('off')

        # 渲染实体
        _render_entities(ax, msp, bbox, layers, color_mode)

        # 保存（白底）
        plt.tight_layout(pad=0)
        plt.savefig(output_path, dpi=100, bbox_inches='tight', pad_inches=0, facecolor='white')

        # 显式清理内存
        plt.close(fig)  # 关闭特定 figure
        plt.close('all')  # 确保关闭所有 figure
        gc.collect()  # 强制垃圾回收

        # 计算缩放比例
        scale = actual_width / bbox['width']

        return {
            "success": True,
            "image_path": output_path,
            "actual_bbox": bbox,
            "scale": round(scale, 6),
            "output_size": [actual_width, actual_height]
        }

    except ImportError:
        return {"success": False, "error": "需要安装 ezdxf 和 matplotlib"}
    except Exception as e:
        # 异常时也要清理内存
        try:
            plt.close('all')
            import gc
            gc.collect()
        except:
            pass
        return {"success": False, "error": f"渲染失败: {str(e)}"}


def _render_entities(ax, msp, bbox, layers, color_mode):
    """渲染实体到 matplotlib axes"""
    x_min = bbox['x']
    x_max = bbox['x'] + bbox['width']
    y_min = bbox['y']
    y_max = bbox['y'] + bbox['height']
    
    for entity in msp:
        # 图层过滤
        if layers and entity.dxf.layer not in layers:
            continue
        
        # 获取颜色
        if color_mode == "by_layer":
            color = get_layer_color(entity.dxf.layer)
        else:
            color = DEFAULT_COLOR
        
        entity_type = entity.dxftype()
        
        try:
            # 渲染不同类型的实体
            if entity_type == "LINE":
                _render_line(ax, entity, x_min, x_max, y_min, y_max, color)
            elif entity_type == "CIRCLE":
                _render_circle(ax, entity, x_min, x_max, y_min, y_max, color)
            elif entity_type == "ARC":
                _render_arc(ax, entity, x_min, x_max, y_min, y_max, color)
            elif entity_type == "LWPOLYLINE":
                _render_lwpolyline(ax, entity, x_min, x_max, y_min, y_max, color)
            elif entity_type == "POLYLINE":
                _render_polyline(ax, entity, x_min, x_max, y_min, y_max, color)
        except:
            pass  # 忽略渲染错误


def _is_in_bbox(x, y, x_min, x_max, y_min, y_max, margin=0):
    """检查点是否在边界框内（带边距）"""
    return (x_min - margin <= x <= x_max + margin and 
            y_min - margin <= y <= y_max + margin)


def _render_line(ax, entity, x_min, x_max, y_min, y_max, color):
    """渲染线段"""
    x1, y1 = entity.dxf.start.x, entity.dxf.start.y
    x2, y2 = entity.dxf.end.x, entity.dxf.end.y
    
    # 检查是否在视图范围内
    if (_is_in_bbox(x1, y1, x_min, x_max, y_min, y_max, margin=1000) or
        _is_in_bbox(x2, y2, x_min, x_max, y_min, y_max, margin=1000)):
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=0.5)


def _render_circle(ax, entity, x_min, x_max, y_min, y_max, color):
    """渲染圆"""
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    
    if _is_in_bbox(cx, cy, x_min, x_max, y_min, y_max, margin=r):
        circle = patches.Circle((cx, cy), r, fill=False, edgecolor=color, linewidth=0.5)
        ax.add_patch(circle)


def _render_arc(ax, entity, x_min, x_max, y_min, y_max, color):
    """渲染圆弧"""
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    start_angle = entity.dxf.start_angle
    end_angle = entity.dxf.end_angle
    
    if _is_in_bbox(cx, cy, x_min, x_max, y_min, y_max, margin=r):
        arc = patches.Arc((cx, cy), 2*r, 2*r, angle=0, 
                         theta1=start_angle, theta2=end_angle,
                         edgecolor=color, linewidth=0.5)
        ax.add_patch(arc)


def _render_lwpolyline(ax, entity, x_min, x_max, y_min, y_max, color):
    """渲染轻量多段线"""
    points = list(entity.get_points())
    if not points:
        return
    
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    
    # 检查是否有点在视图范围内
    in_view = any(_is_in_bbox(x, y, x_min, x_max, y_min, y_max, margin=1000) 
                  for x, y in zip(xs, ys))
    
    if in_view:
        if entity.closed and len(points) > 2:
            xs.append(xs[0])
            ys.append(ys[0])
        ax.plot(xs, ys, color=color, linewidth=0.5)


def _render_polyline(ax, entity, x_min, x_max, y_min, y_max, color):
    """渲染多段线"""
    points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    if not points:
        return
    
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    
    in_view = any(_is_in_bbox(x, y, x_min, x_max, y_min, y_max, margin=1000) 
                  for x, y in zip(xs, ys))
    
    if in_view:
        if entity.is_closed and len(points) > 2:
            xs.append(xs[0])
            ys.append(ys[0])
        ax.plot(xs, ys, color=color, linewidth=0.5)
