#!/usr/bin/env python3
"""
测试视觉 AI 分析 - 完整工作流

测试流程：
1. CAD 文件 → 渲染图片
2. 图片 → Kimi 2.5 视觉分析
3. 提取结构化数据
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.vision_service import (
    convert_cad_to_image,
    analyze_drawing_visual,
    extract_drawing_annotations
)


def test_vision_analysis():
    """测试完整的视觉 AI 分析流程"""
    print("🔬 测试视觉 AI 分析\n")

    file_path = "temp_workspace/input/甲类仓库建施.dxf"

    # 步骤 1: CAD 转图片
    print("=" * 60)
    print("步骤 1: CAD 转图片")
    print("=" * 60)

    convert_result = convert_cad_to_image(
        file_path=file_path,
        render_mode="regions"  # 渲染高密度区域
    )

    if not convert_result["success"]:
        print(f"❌ 转换失败: {convert_result['error']}")
        return

    print(f"✅ 成功生成 {convert_result['data']['image_count']} 张图片\n")

    for i, region in enumerate(convert_result['data']['regions'], 1):
        print(f"区域 {i}: {region['name']}")
        print(f"  图片: {region['image_path']}")
        print(f"  实体数: {region.get('entity_count', 'N/A')}\n")

    # 步骤 2: 选择第一张图片进行视觉分析
    if convert_result['data']['image_paths']:
        first_image = convert_result['data']['image_paths'][0]

        print("=" * 60)
        print("步骤 2: 视觉 AI 分析")
        print("=" * 60)
        print(f"分析图片: {first_image}\n")

        # 测试 1: 整体分析
        print("测试 1: 整体分析...")
        analysis_result = analyze_drawing_visual(
            image_path=first_image,
            analysis_goal="这是一张建筑施工图。请识别：1) 图纸类型 2) 主要建筑构件（墙体、柱子、门窗等）3) 可见的尺寸标注",
            detail_level="medium"
        )

        if analysis_result["success"]:
            print("✅ 分析成功！\n")
            print("分析结果：")
            print("-" * 60)
            print(analysis_result['data']['analysis_text'])
            print("-" * 60)
        else:
            print(f"❌ 分析失败: {analysis_result['error']}")

        # 测试 2: 提取标注
        print("\n测试 2: 提取标注...")
        annotation_result = extract_drawing_annotations(first_image)

        if annotation_result["success"]:
            print("✅ 提取成功！\n")
            print("标注内容：")
            print("-" * 60)
            print(annotation_result['data']['annotations'])
            print("-" * 60)
        else:
            print(f"❌ 提取失败: {annotation_result['error']}")


if __name__ == "__main__":
    test_vision_analysis()
