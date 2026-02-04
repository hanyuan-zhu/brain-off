"""
视觉理解工具 - 支持OpenAI SDK兼容接口

用于CAD图纸的多模态分析，支持：
- Kimi 2.5 Vision
- GPT-4 Vision
- 其他OpenAI兼容的视觉模型
"""

from typing import Dict, Any, Optional
import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def get_vision_client():
    """获取视觉模型客户端"""
    base_url = os.getenv("VISION_MODEL_BASE_URL", "https://api.moonshot.cn/v1")
    api_key = os.getenv("VISION_MODEL_API_KEY")

    if not api_key:
        raise ValueError("未配置VISION_MODEL_API_KEY环境变量")

    return OpenAI(base_url=base_url, api_key=api_key)


def convert_cad_to_image(
    file_path: str,
    output_format: str = "png",
    layers: Optional[list] = None,
    render_mode: str = "regions"
) -> Dict[str, Any]:
    """
    将CAD文件转换为图片

    Args:
        file_path: CAD文件路径
        output_format: 输出格式（png/jpg/pdf）
        layers: 要显示的图层列表（可选）
        render_mode: 渲染模式 - "regions"(多个高密度区域) 或 "overview"(全图概览)

    Returns:
        Dict包含：
        - success: bool
        - data: {image_paths: [str], regions: [...], image_count: int}
        - error: str
    """
    try:
        from services.rendering_service import get_drawing_bounds
        from services.cad_renderer import render_drawing_region

        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}"
            }

        # 步骤 1: 获取图纸边界和关键区域
        bounds_result = get_drawing_bounds(file_path, layers=layers, grid_size=1000)

        if not bounds_result["success"]:
            return {
                "success": False,
                "error": f"获取图纸边界失败: {bounds_result['error']}"
            }

        image_paths = []
        regions_info = []

        if render_mode == "overview":
            # 渲染全图概览
            full_region = {
                "x": bounds_result["bounds"]["min_x"],
                "y": bounds_result["bounds"]["min_y"],
                "width": bounds_result["bounds"]["width"],
                "height": bounds_result["bounds"]["height"]
            }

            result = render_drawing_region(
                file_path,
                bbox=full_region,
                output_size=(2048, 2048),
                layers=layers
            )

            if result["success"]:
                image_paths.append(result["image_path"])
                regions_info.append({
                    "name": "全图概览",
                    "bbox": full_region,
                    "image_path": result["image_path"]
                })

        else:  # render_mode == "regions"
            # 渲染前5个高密度区域
            regions = bounds_result["regions"][:5]

            for i, region in enumerate(regions, 1):
                result = render_drawing_region(
                    file_path,
                    bbox=region["bbox"],
                    output_size=(2048, 2048),
                    layers=layers
                )

                if result["success"]:
                    image_paths.append(result["image_path"])
                    regions_info.append({
                        "name": region["name"],
                        "bbox": region["bbox"],
                        "entity_count": region["entity_count"],
                        "image_path": result["image_path"]
                    })

        return {
            "success": True,
            "data": {
                "image_paths": image_paths,
                "regions": regions_info,
                "image_count": len(image_paths),
                "bounds": bounds_result["bounds"]
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"转换失败: {str(e)}"
        }


def analyze_drawing_visual(
    image_path: str,
    analysis_goal: str,
    detail_level: str = "medium"
) -> Dict[str, Any]:
    """
    使用多模态模型分析图纸视觉内容

    Args:
        image_path: 图片路径
        analysis_goal: 分析目标（如："识别所有文字标注"、"找出门窗符号"）
        detail_level: 详细程度（low/medium/high）

    Returns:
        Dict包含：
        - success: bool
        - data: {analysis_text: str, structured_data: dict}
        - error: str
    """
    try:
        if not os.path.exists(image_path):
            return {
                "success": False,
                "error": f"图片文件不存在: {image_path}"
            }

        # 读取图片并转为base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 获取模型配置
        model_name = os.getenv("VISION_MODEL_NAME", "moonshot-v1-vision")
        client = get_vision_client()

        # 构建提示词
        prompt = f"""你是一个专业的工程图纸分析助手。

分析目标：{analysis_goal}

请仔细观察图纸，提供详细的分析结果。如果是识别文字，请列出所有可见的文字内容及其位置。如果是识别符号，请描述符号的类型、位置和含义。

详细程度：{detail_level}
"""

        # 调用视觉模型
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            temperature=1,  # Kimi 2.5 要求 temperature=1
        )

        analysis_text = response.choices[0].message.content

        return {
            "success": True,
            "data": {
                "analysis_text": analysis_text,
                "model_used": model_name,
                "image_path": image_path
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"视觉分析失败: {str(e)}"
        }


def extract_drawing_annotations(image_path: str) -> Dict[str, Any]:
    """
    提取图纸中的标注和说明文字

    Args:
        image_path: 图片路径

    Returns:
        Dict包含：
        - success: bool
        - data: {annotations: [{text, type, location}]}
        - error: str
    """
    try:
        # 使用analyze_drawing_visual的特化版本
        result = analyze_drawing_visual(
            image_path=image_path,
            analysis_goal="提取图纸中所有的文字标注、尺寸标注和说明文字。请按类别整理：1)尺寸标注 2)材料说明 3)其他文字",
            detail_level="high"
        )

        if not result["success"]:
            return result

        return {
            "success": True,
            "data": {
                "annotations": result["data"]["analysis_text"],
                "image_path": image_path
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"提取标注失败: {str(e)}"
        }


# 视觉工具定义
VISION_TOOL_DEFINITIONS = [
    {
        "name": "convert_cad_to_image",
        "description": "将CAD文件转换为图片格式，便于视觉分析",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "CAD文件ID"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["png", "jpg", "pdf"],
                    "description": "输出格式，默认png"
                },
                "layers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要显示的图层列表（可选）"
                }
            },
            "required": ["file_id"]
        }
    },
    {
        "name": "analyze_drawing_visual",
        "description": "使用多模态AI模型分析图纸视觉内容，识别文字、符号、图例等",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "图片文件路径"
                },
                "analysis_goal": {
                    "type": "string",
                    "description": "分析目标，如：'识别所有门窗符号'、'提取房间名称'"
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "分析详细程度，默认medium"
                }
            },
            "required": ["image_path", "analysis_goal"]
        }
    },
    {
        "name": "extract_drawing_annotations",
        "description": "专门提取图纸中的标注文字和说明",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "图片文件路径"
                }
            },
            "required": ["image_path"]
        }
    }
]
