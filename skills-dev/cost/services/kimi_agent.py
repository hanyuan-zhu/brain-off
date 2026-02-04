#!/usr/bin/env python3
"""
Kimi Agent - CAD 图纸分析 Agent

让 Kimi 2.5 作为 Agent 主动调用工具：
1. 先用 ezdxf 提取结构化数据作为上下文
2. 自己决定要渲染哪些区域
3. 结合结构化数据和视觉分析得出结论
"""

import os
import json
import base64
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入工具函数
from services.kimi_agent_tools import (
    get_cad_metadata,
    get_cad_regions,
    render_cad_region,
    extract_cad_entities,
    list_files,
    read_file,
    write_file,
    append_to_file,
    convert_dwg_to_dxf,
    KIMI_AGENT_TOOLS
)

# 初始化 Kimi 客户端
client = OpenAI(
    api_key=os.getenv("VISION_MODEL_API_KEY"),
    base_url=os.getenv("VISION_MODEL_BASE_URL")
)

MODEL_NAME = os.getenv("VISION_MODEL_NAME", "kimi-k2.5")


# ============================================================
# 工具调用处理
# ============================================================

def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """执行工具调用"""
    try:
        if tool_name == "get_cad_metadata":
            return get_cad_metadata(**arguments)

        elif tool_name == "get_cad_regions":
            return get_cad_regions(**arguments)

        elif tool_name == "render_cad_region":
            return render_cad_region(**arguments)

        elif tool_name == "extract_cad_entities":
            return extract_cad_entities(**arguments)

        elif tool_name == "list_files":
            return list_files(**arguments)

        elif tool_name == "read_file":
            return read_file(**arguments)

        elif tool_name == "write_file":
            return write_file(**arguments)

        elif tool_name == "append_to_file":
            return append_to_file(**arguments)

        elif tool_name == "convert_dwg_to_dxf":
            return convert_dwg_to_dxf(**arguments)

        else:
            return {
                "success": False,
                "error": f"未知工具: {tool_name}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"工具执行失败: {str(e)}"
        }


def encode_image_to_base64(image_path: str) -> str:
    """将图片编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


# ============================================================
# Kimi Agent 核心函数
# ============================================================

def run_kimi_agent(
    file_path: str,
    task: str,
    max_iterations: int = 10
) -> Dict[str, Any]:
    """
    运行 Kimi Agent 分析 CAD 文件

    Args:
        file_path: CAD 文件路径
        task: 分析任务描述
        max_iterations: 最大迭代次数

    Returns:
        分析结果
    """
    try:
        # 初始化对话历史
        messages = [
            {
                "role": "system",
                "content": """你是一个专业的建筑工程图纸分析助手。你可以使用以下工具来分析CAD图纸：

1. get_cad_metadata - 获取CAD文件元数据（图层、实体统计等）
2. get_cad_regions - 识别图纸中的关键区域
3. render_cad_region - 渲染指定区域为图片
4. extract_cad_entities - 提取实体的结构化数据

分析策略：
1. 先调用 get_cad_metadata 了解图纸基本信息
2. 调用 get_cad_regions 识别关键区域
3. 根据需要调用 render_cad_region 渲染感兴趣的区域
4. 结合结构化数据和视觉分析给出结论

请主动思考需要"看"哪些区域，然后调用工具获取信息。"""
            },
            {
                "role": "user",
                "content": f"请分析这个CAD文件：{file_path}\n\n任务：{task}"
            }
        ]

        # Agent 主循环
        iteration = 0
        tool_calls_history = []
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"迭代 {iteration}/{max_iterations}")
            print(f"{'='*60}")
            
            # 调用 Kimi API
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=KIMI_AGENT_TOOLS,
                temperature=1
            )
            
            assistant_message = response.choices[0].message
            messages.append(assistant_message)
            
            # 检查是否有工具调用
            if not assistant_message.tool_calls:
                # 没有工具调用，Agent 完成分析
                print("\n✅ Agent 完成分析")
                return {
                    "success": True,
                    "data": {
                        "analysis": assistant_message.content,
                        "tool_calls_history": tool_calls_history,
                        "iterations": iteration
                    }
                }
            
            # 处理工具调用
            print(f"\n🔧 Agent 调用了 {len(assistant_message.tool_calls)} 个工具")
            
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                print(f"\n工具: {tool_name}")
                print(f"参数: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
                
                # 执行工具
                result = execute_tool_call(tool_name, arguments)
                
                # 记录工具调用
                tool_calls_history.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result
                })
                
                # 如果是渲染工具，需要将图片编码为 base64
                if tool_name == "render_cad_region" and result.get("success"):
                    image_path = result["data"]["image_path"]
                    image_base64 = encode_image_to_base64(image_path)
                    
                    # 添加图片到消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "success": True,
                            "image_base64": image_base64,
                            "image_path": image_path,
                            "scale": result["data"]["scale"]
                        }, ensure_ascii=False)
                    })
                    
                    print(f"✅ 渲染成功: {image_path}")
                else:
                    # 其他工具直接返回结果
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                    
                    if result.get("success"):
                        print(f"✅ 执行成功")
                    else:
                        print(f"❌ 执行失败: {result.get('error')}")
        
        # 达到最大迭代次数
        print(f"\n⚠️ 达到最大迭代次数 {max_iterations}")
        return {
            "success": False,
            "error": "达到最大迭代次数",
            "data": {
                "tool_calls_history": tool_calls_history,
                "iterations": iteration
            }
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Agent 运行失败: {str(e)}"
        }
