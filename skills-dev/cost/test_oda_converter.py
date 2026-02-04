#!/usr/bin/env python3
"""
测试 ODA File Converter 集成
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.oda_converter import ODAConverter, convert_dwg_to_dxf


def test_installation():
    """测试 ODA File Converter 是否已安装"""
    print("="*60)
    print("检查 ODA File Converter 安装状态")
    print("="*60)

    converter = ODAConverter()

    if converter.is_available():
        print(f"✓ ODA File Converter 已安装")
        print(f"  路径: {converter.oda_path}")
        return True
    else:
        print("✗ ODA File Converter 未安装")
        print("\n请按照以下步骤安装:")
        print("1. 访问: https://www.opendesign.com/guestfiles/oda_file_converter")
        print("2. 下载 macOS 版本")
        print("3. 安装到 /Applications 目录")
        print("4. 重新运行此测试")
        return False


def test_conversion(dwg_file: str = None):
    """测试转换功能"""
    if dwg_file is None:
        print("\n跳过转换测试（未提供 DWG 文件）")
        print("使用方法: python test_oda_converter.py <dwg_file_path>")
        return

    if not os.path.exists(dwg_file):
        print(f"\n✗ 文件不存在: {dwg_file}")
        return

    print("\n" + "="*60)
    print("测试 DWG 到 DXF 转换")
    print("="*60)
    print(f"输入文件: {dwg_file}")

    result = convert_dwg_to_dxf(dwg_file)

    if result["success"]:
        print("✓ 转换成功")
        print(f"  输出文件: {result['data']['output_path']}")
        print(f"  文件大小: {result['data']['file_size'] / 1024:.2f} KB")
    else:
        print(f"✗ 转换失败: {result['error']}")


def main():
    print("ODA File Converter 测试工具\n")

    # 测试安装
    installed = test_installation()

    # 如果已安装且提供了文件路径，测试转换
    if installed and len(sys.argv) > 1:
        test_conversion(sys.argv[1])

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
