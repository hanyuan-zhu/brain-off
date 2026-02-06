#!/usr/bin/env python3
"""
Kimi Agent 工具定义

为 Kimi 2.5 Agent 提供 CAD 分析工具，让其能够：
1. 获取 CAD 全局概览（元数据 + 全图缩略图）
2. 检查指定区域（高清图 + 实体数据）
3. 提取 CAD 结构化数据（图层、实体、尺寸等）
4. 文件操作和格式转换
"""

from typing import Dict, Any, List, Optional
import json


# ============================================================
# 工具函数定义
# ============================================================

def get_cad_metadata(file_path: str) -> Dict[str, Any]:
    """
    获取 CAD 文件的全局概览信息

    【全局视图】鸟瞰整张图纸，了解整体布局和基本信息

    Args:
        file_path: CAD 文件路径

    Returns:
        - 视觉：整张图纸的缩略图
        - 数据：边界范围、图层列表、实体统计、文件信息
    """
    try:
        import os
        import ezdxf
        from pathlib import Path
        from ezdxf.bbox import extents

        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}"
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

        # 获取边界信息
        try:
            bbox = extents(msp)
            bounds = {
                "min_x": round(bbox.extmin.x, 2),
                "max_x": round(bbox.extmax.x, 2),
                "min_y": round(bbox.extmin.y, 2),
                "max_y": round(bbox.extmax.y, 2),
                "width": round(bbox.size.x, 2),
                "height": round(bbox.size.y, 2),
                "width_m": round(bbox.size.x / 1000, 2),
                "height_m": round(bbox.size.y / 1000, 2)
            }
        except:
            bounds = None

        # 获取文件元数据
        filename = Path(file_path).name
        file_size = os.path.getsize(file_path)

        result = {
            "success": True,
            "data": {
                "filename": filename,
                "file_path": file_path,
                "metadata": {
                    "dxf_version": doc.dxfversion,
                    "file_size": file_size,
                    "units": str(doc.units)
                },
                "bounds": bounds,
                "layers": layers_info,
                "entity_count": len(list(msp)),
                "layer_count": len(layers_info)
            }
        }

        # 生成全局缩略图
        if bounds:
            from .cad_renderer import render_drawing_region

            thumbnail_result = render_drawing_region(
                file_path,
                bbox={
                    "x": bounds["min_x"],
                    "y": bounds["min_y"],
                    "width": bounds["width"],
                    "height": bounds["height"]
                },
                output_size=(800, 800),
                color_mode="by_layer"
            )

            if thumbnail_result["success"]:
                result["data"]["thumbnail"] = thumbnail_result["image_path"]

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"获取元数据失败: {str(e)}"
        }


def extract_cad_entities(
    file_path: str,
    entity_types: Optional[List[str]] = None,
    layers: Optional[List[str]] = None,
    bbox: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    提取 CAD 实体数据

    Args:
        file_path: CAD 文件路径
        entity_types: 实体类型列表（如 ["LINE", "CIRCLE", "TEXT"]）
        layers: 图层列表
        bbox: 边界框（可选，用于只提取特定区域的实体）

    Returns:
        包含实体列表和统计信息
    """
    try:
        import ezdxf

        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        entities = []
        entity_count = {}

        # 辅助函数：检查点是否在 bbox 内
        def is_in_bbox(x, y, bbox):
            if not bbox:
                return True
            return (bbox['x'] <= x <= bbox['x'] + bbox['width'] and
                    bbox['y'] <= y <= bbox['y'] + bbox['height'])

        for entity in msp:
            # 过滤实体类型
            if entity_types and entity.dxftype() not in entity_types:
                continue

            # 过滤图层
            if layers and entity.dxf.layer not in layers:
                continue

            # 过滤 bbox（检查实体是否在指定区域内）
            if bbox:
                in_region = False
                try:
                    if entity.dxftype() == "LINE":
                        # 线段：起点或终点在区域内
                        if (is_in_bbox(entity.dxf.start.x, entity.dxf.start.y, bbox) or
                            is_in_bbox(entity.dxf.end.x, entity.dxf.end.y, bbox)):
                            in_region = True
                    elif entity.dxftype() == "CIRCLE":
                        # 圆：圆心在区域内
                        if is_in_bbox(entity.dxf.center.x, entity.dxf.center.y, bbox):
                            in_region = True
                    elif entity.dxftype() == "TEXT":
                        # 文字：插入点在区域内
                        if is_in_bbox(entity.dxf.insert.x, entity.dxf.insert.y, bbox):
                            in_region = True
                    elif hasattr(entity.dxf, 'start'):
                        # 其他有起点的实体
                        if is_in_bbox(entity.dxf.start.x, entity.dxf.start.y, bbox):
                            in_region = True
                    elif hasattr(entity.dxf, 'center'):
                        # 其他有中心点的实体
                        if is_in_bbox(entity.dxf.center.x, entity.dxf.center.y, bbox):
                            in_region = True
                    elif hasattr(entity.dxf, 'insert'):
                        # 其他有插入点的实体
                        if is_in_bbox(entity.dxf.insert.x, entity.dxf.insert.y, bbox):
                            in_region = True
                except:
                    pass

                if not in_region:
                    continue

            # 提取实体信息
            entity_info = {
                "type": entity.dxftype(),
                "layer": entity.dxf.layer,
                "color": entity.dxf.color
            }

            # 提取几何信息
            if entity.dxftype() == "LINE":
                entity_info["start"] = [entity.dxf.start.x, entity.dxf.start.y]
                entity_info["end"] = [entity.dxf.end.x, entity.dxf.end.y]

            elif entity.dxftype() == "CIRCLE":
                entity_info["center"] = [entity.dxf.center.x, entity.dxf.center.y]
                entity_info["radius"] = entity.dxf.radius

            elif entity.dxftype() == "TEXT":
                entity_info["text"] = entity.dxf.text
                entity_info["position"] = [entity.dxf.insert.x, entity.dxf.insert.y]
                entity_info["height"] = entity.dxf.height

            entities.append(entity_info)

            # 统计
            entity_type = entity.dxftype()
            entity_count[entity_type] = entity_count.get(entity_type, 0) + 1

        return {
            "success": True,
            "data": {
                "entities": entities[:100],  # 只返回前100个
                "total_count": len(entities),
                "entity_count": entity_count
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"提取实体失败: {str(e)}"
        }


def inspect_region(
    file_path: str,
    x: float,
    y: float,
    width: float,
    height: float,
    output_size: int = 2048
) -> Dict[str, Any]:
    """
    检查指定区域 - 一次调用同时获取图片和数据

    【核心工具】查看图纸的某个区域时使用此工具，一次性获取：
    - 视觉：该区域的高清放大图
    - 数据：该区域内的实体统计、图层分布、关键信息

    Args:
        file_path: CAD 文件路径
        x: 区域左下角 X 坐标（mm）
        y: 区域左下角 Y 坐标（mm）
        width: 区域宽度（mm）
        height: 区域高度（mm）
        output_size: 输出图片尺寸（默认 2048px）

    Returns:
        {
            "success": True,
            "data": {
                "image_path": "渲染图片路径",
                "image_base64": "base64编码的图片（供AI查看）",
                "region_info": {
                    "bbox": {"x": ..., "y": ..., "width": ..., "height": ...},
                    "area_m2": 区域面积（平方米）
                },
                "entity_summary": {
                    "total_count": 总实体数,
                    "by_type": {"LINE": 数量, "TEXT": 数量, ...},
                    "by_layer": {"WALL": 数量, "DIM": 数量, ...}
                },
                "key_content": {
                    "texts": [文字内容列表],
                    "dimensions": [尺寸标注列表]
                }
            }
        }
    """
    try:
        from .cad_renderer import render_drawing_region
        import ezdxf
        import base64

        bbox = {"x": x, "y": y, "width": width, "height": height}

        # 1. 渲染图片
        render_result = render_drawing_region(
            file_path,
            bbox=bbox,
            output_size=(output_size, output_size)
        )

        if not render_result["success"]:
            return {
                "success": False,
                "error": f"渲染失败: {render_result['error']}"
            }

        image_path = render_result["image_path"]

        # 2. 编码图片为 base64（让 AI 能看到）
        try:
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            image_base64 = None

        # 3. 提取区域内的实体数据
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        entities_by_type = {}
        entities_by_layer = {}
        texts = []
        dimensions = []

        def is_in_bbox(px, py):
            return (x <= px <= x + width and y <= py <= y + height)

        for entity in msp:
            # 检查实体是否在区域内
            in_region = False
            entity_point = None

            try:
                if entity.dxftype() == "LINE":
                    if (is_in_bbox(entity.dxf.start.x, entity.dxf.start.y) or
                        is_in_bbox(entity.dxf.end.x, entity.dxf.end.y)):
                        in_region = True
                elif entity.dxftype() == "TEXT":
                    if is_in_bbox(entity.dxf.insert.x, entity.dxf.insert.y):
                        in_region = True
                        texts.append({
                            "text": entity.dxf.text,
                            "position": [entity.dxf.insert.x, entity.dxf.insert.y],
                            "height": entity.dxf.height,
                            "layer": entity.dxf.layer
                        })
                elif entity.dxftype() == "MTEXT":
                    if is_in_bbox(entity.dxf.insert.x, entity.dxf.insert.y):
                        in_region = True
                        texts.append({
                            "text": entity.text,
                            "position": [entity.dxf.insert.x, entity.dxf.insert.y],
                            "layer": entity.dxf.layer
                        })
                elif hasattr(entity.dxf, 'center'):
                    if is_in_bbox(entity.dxf.center.x, entity.dxf.center.y):
                        in_region = True
                elif hasattr(entity.dxf, 'start'):
                    if is_in_bbox(entity.dxf.start.x, entity.dxf.start.y):
                        in_region = True
                elif hasattr(entity.dxf, 'insert'):
                    if is_in_bbox(entity.dxf.insert.x, entity.dxf.insert.y):
                        in_region = True
            except:
                pass

            if not in_region:
                continue

            # 统计实体类型
            entity_type = entity.dxftype()
            entities_by_type[entity_type] = entities_by_type.get(entity_type, 0) + 1

            # 统计图层
            layer = entity.dxf.layer
            entities_by_layer[layer] = entities_by_layer.get(layer, 0) + 1

        # 计算区域面积
        area_m2 = round((width * height) / 1000000, 2)

        return {
            "success": True,
            "data": {
                "image_path": image_path,
                "image_base64": image_base64,
                "region_info": {
                    "bbox": bbox,
                    "area_m2": area_m2,
                    "scale": render_result.get("scale")
                },
                "entity_summary": {
                    "total_count": sum(entities_by_type.values()),
                    "by_type": entities_by_type,
                    "by_layer": entities_by_layer
                },
                "key_content": {
                    "texts": texts[:50],  # 最多返回 50 个文字
                    "text_count": len(texts)
                }
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"检查区域失败: {str(e)}"
        }


def list_files(working_folder: str, recursive: bool = False) -> Dict[str, Any]:
    """
    列出 working folder 中的所有文件和文件夹

    Args:
        working_folder: 工作文件夹路径
        recursive: 是否递归列出子文件夹中的文件

    Returns:
        文件和文件夹列表
    """
    try:
        import os
        from pathlib import Path

        folder_path = Path(working_folder)

        if not folder_path.exists():
            return {
                "success": False,
                "error": f"文件夹不存在: {working_folder}"
            }

        if not folder_path.is_dir():
            return {
                "success": False,
                "error": f"路径不是文件夹: {working_folder}"
            }

        files = []
        directories = []

        if recursive:
            # 递归列出所有文件
            for item in folder_path.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(folder_path)
                    files.append({
                        "name": item.name,
                        "path": str(relative_path),
                        "size": item.stat().st_size,
                        "modified": item.stat().st_mtime
                    })
        else:
            # 只列出当前目录
            for item in folder_path.iterdir():
                if item.is_file():
                    files.append({
                        "name": item.name,
                        "type": "file",
                        "size": item.stat().st_size,
                        "modified": item.stat().st_mtime
                    })
                elif item.is_dir():
                    directories.append({
                        "name": item.name,
                        "type": "directory",
                        "modified": item.stat().st_mtime
                    })

        return {
            "success": True,
            "data": {
                "folder": str(folder_path),
                "files": files,
                "directories": directories,
                "file_count": len(files),
                "directory_count": len(directories)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"列出文件失败: {str(e)}"
        }


def read_file(working_folder: str, filename: str) -> Dict[str, Any]:
    """
    读取文件内容

    Args:
        working_folder: 工作文件夹路径
        filename: 文件名

    Returns:
        文件内容
    """
    try:
        from pathlib import Path

        file_path = Path(working_folder) / filename

        if not file_path.exists():
            return {
                "success": False,
                "error": f"文件不存在: {filename}"
            }

        content = file_path.read_text(encoding='utf-8')

        return {
            "success": True,
            "data": {
                "filename": filename,
                "content": content,
                "size": len(content)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"读取文件失败: {str(e)}"
        }


def write_file(working_folder: str, filename: str, content: str) -> Dict[str, Any]:
    """
    写入文件（覆盖模式，不存在则创建）

    Args:
        working_folder: 工作文件夹路径
        filename: 文件名
        content: 文件内容

    Returns:
        操作结果
    """
    try:
        from pathlib import Path

        folder_path = Path(working_folder)
        folder_path.mkdir(parents=True, exist_ok=True)

        file_path = folder_path / filename
        file_path.write_text(content, encoding='utf-8')

        return {
            "success": True,
            "data": {
                "filename": filename,
                "path": str(file_path),
                "size": len(content)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"写入文件失败: {str(e)}"
        }


def append_to_file(working_folder: str, filename: str, content: str) -> Dict[str, Any]:
    """
    追加内容到文件末尾

    Args:
        working_folder: 工作文件夹路径
        filename: 文件名
        content: 要追加的内容

    Returns:
        操作结果
    """
    try:
        from pathlib import Path

        folder_path = Path(working_folder)
        folder_path.mkdir(parents=True, exist_ok=True)

        file_path = folder_path / filename

        # 追加模式
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)

        return {
            "success": True,
            "data": {
                "filename": filename,
                "path": str(file_path),
                "appended_size": len(content)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"追加文件失败: {str(e)}"
        }


def convert_dwg_to_dxf(dwg_path: str, output_path: Optional[str] = None, delete_original: bool = True) -> Dict[str, Any]:
    """
    将 DWG 文件转换为 DXF 格式

    Args:
        dwg_path: DWG 文件路径
        output_path: 输出 DXF 文件路径（可选，默认与 DWG 同名同目录）
        delete_original: 转换成功后是否删除原始 DWG 文件（默认 True）

    Returns:
        转换结果
    """
    try:
        import os
        from .oda_converter import ODAConverter

        converter = ODAConverter()

        if not converter.is_available():
            return {
                "success": False,
                "error": "ODA File Converter 未安装。请从 https://www.opendesign.com/guestfiles/oda_file_converter 下载安装"
            }

        result = converter.convert_dwg_to_dxf(
            dwg_path=dwg_path,
            output_path=output_path
        )

        # 转换成功后删除原始文件
        if result.get("success") and delete_original:
            try:
                os.remove(dwg_path)
                result["deleted_original"] = True
                result["message"] = f"转换成功，已删除原始文件: {dwg_path}"
            except Exception as e:
                result["deleted_original"] = False
                result["warning"] = f"转换成功但删除原始文件失败: {str(e)}"

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"DWG 转换失败: {str(e)}"
        }


# ============================================================
# 工具定义 Schema（供 Kimi Agent 使用）
# ============================================================

KIMI_AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_cad_metadata",
            "description": "获取CAD文件的全局概览信息。返回：1) 全图缩略图（800x800px）2) 图纸边界和尺寸 3) 图层列表和实体统计 4) 文件元数据。这是分析CAD文件的第一步，先看全局再看局部。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "CAD文件路径"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_region",
            "description": "检查指定区域的详细信息。一次性返回：1) 高清放大图（2048px）2) 区域内的实体统计 3) 图层分布 4) 文字内容。用于查看局部细节（如房间布局、尺寸标注等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "CAD文件路径"
                    },
                    "x": {
                        "type": "number",
                        "description": "区域左下角X坐标（mm）"
                    },
                    "y": {
                        "type": "number",
                        "description": "区域左下角Y坐标（mm）"
                    },
                    "width": {
                        "type": "number",
                        "description": "区域宽度（mm）"
                    },
                    "height": {
                        "type": "number",
                        "description": "区域高度（mm）"
                    },
                    "output_size": {
                        "type": "integer",
                        "description": "输出图片尺寸（像素），默认2048",
                        "default": 2048
                    }
                },
                "required": ["file_path", "x", "y", "width", "height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_cad_entities",
            "description": "提取CAD实体的结构化数据，包括线条、圆、文字等。可以按类型、图层过滤。用于获取几何信息和文字标注。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "CAD文件路径"
                    },
                    "entity_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "实体类型列表，如 ['LINE', 'CIRCLE', 'TEXT']"
                    },
                    "layers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "图层列表"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出工作文件夹中的所有文件和子文件夹。用于查看当前有哪些文件和目录可用。支持递归列出所有子目录中的文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "working_folder": {
                        "type": "string",
                        "description": "工作文件夹路径"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "是否递归列出所有子文件夹中的文件，默认 false",
                        "default": False
                    }
                },
                "required": ["working_folder"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容。用于查看已有文件的内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "working_folder": {
                        "type": "string",
                        "description": "工作文件夹路径"
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名"
                    }
                },
                "required": ["working_folder", "filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入文件内容（覆盖模式）。如果文件不存在则创建，存在则完全覆盖。用于创建新文件或重写整个文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "working_folder": {
                        "type": "string",
                        "description": "工作文件夹路径"
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名"
                    },
                    "content": {
                        "type": "string",
                        "description": "文件内容"
                    }
                },
                "required": ["working_folder", "filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_file",
            "description": "追加内容到文件末尾。用于增量添加内容，如日志记录。如果文件不存在则创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "working_folder": {
                        "type": "string",
                        "description": "工作文件夹路径"
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名"
                    },
                    "content": {
                        "type": "string",
                        "description": "要追加的内容"
                    }
                },
                "required": ["working_folder", "filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "convert_dwg_to_dxf",
            "description": "将 DWG 文件转换为 DXF 格式。DWG 文件无法直接读取，必须先转换为 DXF 才能分析。转换成功后会自动删除原始 DWG 文件以节省空间。",
            "parameters": {
                "type": "object",
                "properties": {
                    "dwg_path": {
                        "type": "string",
                        "description": "DWG 文件路径"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出 DXF 文件路径（可选，默认与 DWG 同名同目录）"
                    },
                    "delete_original": {
                        "type": "boolean",
                        "description": "转换成功后是否删除原始 DWG 文件（默认 true）"
                    }
                },
                "required": ["dwg_path"]
            }
        }
    }
]
