#!/usr/bin/env python3
"""
测试 CAD 渲染服务 - get_drawing_bounds()
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from services.rendering_service import get_drawing_bounds


def test_get_drawing_bounds():
    """测试获取图纸边界功能"""
    print("🔍 测试 get_drawing_bounds()\n")

    file_path = "temp_workspace/input/甲类仓库建施.dxf"

    print("=" * 60)
    print("测试：获取图纸边界和关键区域")
    print("=" * 60)

    result = get_drawing_bounds(file_path)

    if result["success"]:
        print("✅ 成功！\n")

        bounds = result["bounds"]
        print("图纸边界:")
        print(f"  X 范围: {bounds['min_x']:.2f} ~ {bounds['max_x']:.2f} mm")
        print(f"  Y 范围: {bounds['min_y']:.2f} ~ {bounds['max_y']:.2f} mm")
        print(f"  尺寸: {bounds['width']:.2f} × {bounds['height']:.2f} mm")
        print(f"  总实体数: {result['total_entities']}")

        print(f"\n识别到 {len(result['regions'])} 个区域:")
        for i, region in enumerate(result['regions'][:5], 1):  # 只显示前5个
            print(f"\n区域 {i}: {region['name']}")
            bbox = region['bbox']
            print(f"  位置: ({bbox['x']:.0f}, {bbox['y']:.0f})")
            print(f"  尺寸: {bbox['width']:.0f} × {bbox['height']:.0f} mm")
            print(f"  实体数: {region['entity_count']}")
            print(f"  密度: {region['density']:.6f}")
            print(f"  网格数: {region['grid_count']}")

        if len(result['regions']) > 5:
            print(f"\n... 还有 {len(result['regions']) - 5} 个区域")

    else:
        print(f"❌ 失败: {result['error']}")


if __name__ == "__main__":
    test_get_drawing_bounds()
