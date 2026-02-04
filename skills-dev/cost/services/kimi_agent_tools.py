#!/usr/bin/env python3
"""
Kimi Agent 工具定义

为 Kimi 2.5 Agent 提供 CAD 分析工具，让其能够：
1. 提取 CAD 结构化数据（图层、实体、尺寸等）
2. 识别关键区域
3. 按需渲染特定区域
4. 结合结构化数据和视觉分析
"""

from typing import Dict, Any, List, Optional
import json


# ============================================================
# 工具函数定义
# ============================================================

def get_cad_metadata(file_path: str) -> Dict[str, Any]:
    """
    获取 CAD 文件的元数据和基本信息

    Args:
        file_path: CAD 文件路径

    Returns:
        包含图层、实体统计、边界等信息
    """
    try:
        import os
        import ezdxf
        from pathlib import Path

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

        # 获取文件元数据
        filename = Path(file_path).name
        file_size = os.path.getsize(file_path)

        return {
            "success": True,
            "data": {
                "filename": filename,
                "file_path": file_path,
                "metadata": {
                    "dxf_version": doc.dxfversion,
                    "file_size": file_size,
                    "units": str(doc.units)
                },
                "layers": layers_info,
                "entity_count": len(list(msp)),
                "layer_count": len(layers_info)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"获取元数据失败: {str(e)}"
        }


def get_cad_regions(file_path: str, grid_size: int = 1000) -> Dict[str, Any]:
    """
    识别 CAD 图纸中的关键区域

    Args:
        file_path: CAD 文件路径
        grid_size: 网格大小（mm）

    Returns:
        包含识别到的高密度区域列表
    """
    try:
        from services.rendering_service import get_drawing_bounds

        result = get_drawing_bounds(file_path, grid_size=grid_size)

        if result["success"]:
            return {
                "success": True,
                "data": {
                    "bounds": result["bounds"],
                    "regions": result["regions"][:10],  # 返回前10个区域
                    "total_regions": len(result["regions"])
                }
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"识别区域失败: {str(e)}"
        }


def render_cad_region(
    file_path: str,
    x: float,
    y: float,
    width: float,
    height: float,
    output_size: int = 2048
) -> Dict[str, Any]:
    """
    渲染指定坐标区域为图片

    Args:
        file_path: CAD 文件路径
        x: 区域左下角 X 坐标
        y: 区域左下角 Y 坐标
        width: 区域宽度（mm）
        height: 区域高度（mm）
        output_size: 输出图片最大尺寸（像素）

    Returns:
        包含图片路径和渲染信息
    """
    try:
        from services.cad_renderer import render_drawing_region

        bbox = {"x": x, "y": y, "width": width, "height": height}

        result = render_drawing_region(
            file_path,
            bbox=bbox,
            output_size=(output_size, output_size)
        )

        if result["success"]:
            return {
                "success": True,
                "data": {
                    "image_path": result["image_path"],
                    "output_size": result["output_size"],
                    "scale": result["scale"]
                }
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"渲染失败: {str(e)}"
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

        for entity in msp:
            # 过滤实体类型
            if entity_types and entity.dxftype() not in entity_types:
                continue

            # 过滤图层
            if layers and entity.dxf.layer not in layers:
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


def list_files(working_folder: str) -> Dict[str, Any]:
    """
    列出 working folder 中的所有文件

    Args:
        working_folder: 工作文件夹路径

    Returns:
        文件列表
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
        for item in folder_path.iterdir():
            if item.is_file():
                files.append({
                    "name": item.name,
                    "size": item.stat().st_size,
                    "modified": item.stat().st_mtime
                })

        return {
            "success": True,
            "data": {
                "folder": str(folder_path),
                "files": files,
                "count": len(files)
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


def convert_dwg_to_dxf(dwg_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    将 DWG 文件转换为 DXF 格式

    Args:
        dwg_path: DWG 文件路径
        output_path: 输出 DXF 文件路径（可选，默认与 DWG 同名同目录）

    Returns:
        转换结果
    """
    try:
        from services.oda_converter import ODAConverter

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
            "description": "获取CAD文件的元数据，包括图层列表、实体统计、文件信息等。这是分析CAD文件的第一步。",
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
            "name": "get_cad_regions",
            "description": "识别CAD图纸中的关键区域（高密度区域）。返回区域列表，每个区域包含位置、尺寸、实体数等信息。用于决定要渲染哪些区域。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "CAD文件路径"
                    },
                    "grid_size": {
                        "type": "integer",
                        "description": "网格大小（mm），默认1000",
                        "default": 1000
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "render_cad_region",
            "description": "渲染指定坐标区域为PNG图片。用于将CAD矢量图转换为图片以便视觉分析。",
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
                        "description": "输出图片最大尺寸（像素），默认2048",
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
            "description": "列出工作文件夹中的所有文件。用于查看当前有哪些文件可用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "working_folder": {
                        "type": "string",
                        "description": "工作文件夹路径"
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
            "description": "将 DWG 文件转换为 DXF 格式。DWG 文件无法直接读取，必须先转换为 DXF 才能分析。",
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
                    }
                },
                "required": ["dwg_path"]
            }
        }
    }
]
