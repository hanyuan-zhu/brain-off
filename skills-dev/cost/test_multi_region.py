#!/usr/bin/env python3
"""
测试多区域渲染 - 演示坐标式渐进渲染
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.cad_renderer import render_drawing_region
from services.rendering_service import get_drawing_bounds


def test_multi_region_rendering():
    """测试渲染多个高密度区域"""
    print("🎨 测试多区域渲染\n")

    file_path = "temp_workspace/input/甲类仓库建施.dxf"

    # 步骤 1: 获取所有区域
    print("步骤 1: 识别关键区域...")
    bounds_result = get_drawing_bounds(file_path, grid_size=1000)

    if not bounds_result["success"]:
        print(f"❌ 失败: {bounds_result['error']}")
        return

    regions = bounds_result["regions"]
    print(f"✅ 识别到 {len(regions)} 个区域\n")

    # 步骤 2: 渲染前 5 个高密度区域
    print("步骤 2: 渲染前 5 个高密度区域...\n")

    for i, region in enumerate(regions[:5], 1):
        print(f"区域 {i}: {region['name']}")
        print(f"  位置: ({region['bbox']['x']:.0f}, {region['bbox']['y']:.0f})")
        print(f"  尺寸: {region['bbox']['width']:.0f} × {region['bbox']['height']:.0f} mm")
        print(f"  实体数: {region['entity_count']}")

        result = render_drawing_region(
            file_path,
            bbox=region['bbox'],
            output_size=(2048, 2048)
        )

        if result["success"]:
            print(f"  ✅ 渲染成功: {result['image_path']}")
            print(f"     输出尺寸: {result['output_size']}")
            print(f"     缩放比例: {result['scale']:.6f} 像素/mm\n")
        else:
            print(f"  ❌ 渲染失败: {result['error']}\n")

    print(f"完成！共渲染 5 个区域")


if __name__ == "__main__":
    test_multi_region_rendering()
