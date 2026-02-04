#!/usr/bin/env python3
"""
测试 CAD 解析功能

测试 load_cad_file, extract_cad_entities, calculate_cad_measurements 三个函数
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from tools import load_cad_file, extract_cad_entities, calculate_cad_measurements


def test_load_cad_file(file_path: str):
    """测试加载 CAD 文件"""
    print("=" * 60)
    print("测试 1: 加载 CAD 文件")
    print("=" * 60)

    result = load_cad_file(file_path)

    if result["success"]:
        print("✅ 加载成功！")
        data = result["data"]
        print(f"\n文件信息:")
        print(f"  文件名: {data['filename']}")
        print(f"  DXF版本: {data['metadata']['dxf_version']}")
        print(f"  文件大小: {data['metadata']['file_size']} 字节")
        print(f"  实体总数: {data['entity_count']}")
        print(f"  图层数量: {data['layer_count']}")

        print(f"\n图层详情:")
        for layer_name, layer_info in data['layers'].items():
            print(f"  - {layer_name}: {layer_info['entity_count']} 个实体")
            for entity_type, count in layer_info['entity_types'].items():
                print(f"    · {entity_type}: {count}")

        return data['file_id']
    else:
        print(f"❌ 加载失败: {result['error']}")
        return None


def test_extract_entities(file_id: str):
    """测试提取实体"""
    print("\n" + "=" * 60)
    print("测试 2: 提取所有实体")
    print("=" * 60)

    result = extract_cad_entities(file_id)

    if result["success"]:
        print("✅ 提取成功！")
        data = result["data"]
        print(f"\n提取到 {data['total_count']} 个实体")

        # 统计实体类型
        type_counts = {}
        for entity in data['entities']:
            entity_type = entity['type']
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

        print("\n实体类型统计:")
        for entity_type, count in type_counts.items():
            print(f"  - {entity_type}: {count}")

        return data['entities']
    else:
        print(f"❌ 提取失败: {result['error']}")
        return None


def test_calculate_measurements(entities: list):
    """测试计算工程量"""
    print("\n" + "=" * 60)
    print("测试 3: 计算工程量")
    print("=" * 60)

    # 测试不同的计算类型
    calculation_types = ['count', 'length', 'area']

    for calc_type in calculation_types:
        print(f"\n计算类型: {calc_type}")
        result = calculate_cad_measurements(entities, calc_type)

        if result["success"]:
            data = result["data"]
            print(f"  ✅ 总计: {data['total']} {data['unit']}")
            print(f"  计算了 {data['calculated_count']}/{data['entity_count']} 个实体")
        else:
            print(f"  ❌ 计算失败: {result['error']}")


def test_filter_entities(file_id: str):
    """测试过滤特定类型的实体"""
    print("\n" + "=" * 60)
    print("测试 4: 过滤特定实体类型")
    print("=" * 60)

    # 测试只提取 LINE 实体
    print("\n提取 LINE 实体:")
    result = extract_cad_entities(file_id, entity_types=['LINE'])

    if result["success"]:
        data = result["data"]
        print(f"  ✅ 提取到 {data['total_count']} 个 LINE 实体")

        # 计算线段总长度
        calc_result = calculate_cad_measurements(data['entities'], 'length')
        if calc_result["success"]:
            calc_data = calc_result["data"]
            print(f"  总长度: {calc_data['total']} {calc_data['unit']}")
    else:
        print(f"  ❌ 提取失败: {result['error']}")


def main():
    """主函数"""
    print("🔧 CAD 解析功能测试\n")

    if len(sys.argv) < 2:
        print("用法: python test_cad_parsing.py <DXF文件路径>")
        print("\n示例:")
        print("  python test_cad_parsing.py sample.dxf")
        return

    file_path = sys.argv[1]

    # 测试 1: 加载文件
    file_id = test_load_cad_file(file_path)
    if not file_id:
        return

    # 测试 2: 提取实体
    entities = test_extract_entities(file_id)
    if not entities:
        return

    # 测试 3: 计算工程量
    test_calculate_measurements(entities)

    # 测试 4: 过滤实体
    test_filter_entities(file_id)

    print("\n" + "=" * 60)
    print("✅ 所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
