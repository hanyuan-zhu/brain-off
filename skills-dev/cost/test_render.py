#!/usr/bin/env python3
"""
测试 CAD 渲染功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.cad_renderer import render_drawing_region
from services.rendering_service import get_drawing_bounds


def test_render():
    """测试渲染功能"""
    print("🎨 测试 CAD 渲染功能\n")

    file_path = "temp_workspace/input/甲类仓库建施.dxf"

    # 步骤 1: 获取图纸边界
    print("步骤 1: 获取图纸边界...")
    bounds_result = get_drawing_bounds(file_path)

    if not bounds_result["success"]:
        print(f"❌ 失败: {bounds_result['error']}")
        return

    print(f"✅ 图纸范围: {bounds_result['bounds']['width']:.0f} × {bounds_result['bounds']['height']:.0f} mm")

    # 步骤 2: 渲染一个小区域测试
    print("\n步骤 2: 渲染测试区域...")

    # 选择一个 10000×10000 mm 的区域
    test_bbox = {
        "x": 0,
        "y": 0,
        "width": 10000,
        "height": 10000
    }

    result = render_drawing_region(
        file_path,
        bbox=test_bbox,
        output_size=(1024, 1024)  # 先用小尺寸测试
    )

    if result["success"]:
        print(f"✅ 渲染成功！")
        print(f"  图片路径: {result['image_path']}")
        print(f"  缩放比例: {result['scale']:.6f} 像素/mm")
        print(f"  输出尺寸: {result['output_size']}")
    else:
        print(f"❌ 渲染失败: {result['error']}")


if __name__ == "__main__":
    test_render()
