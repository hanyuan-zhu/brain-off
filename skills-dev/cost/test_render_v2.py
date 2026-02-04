#!/usr/bin/env python3
"""
测试 CAD 渲染功能 - 改进版

渲染实际有内容的区域
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.cad_renderer import render_drawing_region
from services.rendering_service import get_drawing_bounds


def test_render_v2():
    """测试渲染功能 - 使用智能区域识别"""
    print("🎨 测试 CAD 渲染功能 v2\n")

    file_path = "temp_workspace/input/甲类仓库建施.dxf"

    # 步骤 1: 获取图纸边界和关键区域
    print("步骤 1: 获取图纸边界和关键区域...")
    bounds_result = get_drawing_bounds(file_path, grid_size=1000)

    if not bounds_result["success"]:
        print(f"❌ 失败: {bounds_result['error']}")
        return

    print(f"✅ 图纸范围: {bounds_result['bounds']['width']:.0f} × {bounds_result['bounds']['height']:.0f} mm")
    print(f"   识别到 {len(bounds_result['regions'])} 个区域")

    # 步骤 2: 渲染第一个关键区域
    if bounds_result['regions']:
        region = bounds_result['regions'][0]
        print(f"\n步骤 2: 渲染第一个区域...")
        print(f"  区域名称: {region['name']}")
        print(f"  位置: ({region['bbox']['x']:.0f}, {region['bbox']['y']:.0f})")
        print(f"  尺寸: {region['bbox']['width']:.0f} × {region['bbox']['height']:.0f} mm")
        print(f"  实体数: {region['entity_count']}")

        result = render_drawing_region(
            file_path,
            bbox=region['bbox'],
            output_size=(2048, 2048)
        )

        if result["success"]:
            print(f"\n✅ 渲染成功！")
            print(f"  图片路径: {result['image_path']}")
            print(f"  缩放比例: {result['scale']:.6f} 像素/mm")
            print(f"  输出尺寸: {result['output_size']}")
        else:
            print(f"❌ 渲染失败: {result['error']}")
    else:
        print("❌ 没有识别到关键区域")


if __name__ == "__main__":
    test_render_v2()
