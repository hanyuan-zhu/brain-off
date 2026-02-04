#!/bin/bash
# 代码清理脚本
# 生成时间: 2026-02-04
#
# 使用方法:
#   1. 查看要删除的文件: bash cleanup_commands.sh --dry-run
#   2. 执行删除: bash cleanup_commands.sh --execute
#   3. 只删除特定类别: bash cleanup_commands.sh --execute --category services

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 工作目录
WORK_DIR="/Users/zhuhanyuan/Documents/chatbot/skills-dev/cost"

# 解析参数
DRY_RUN=true
CATEGORY="all"

while [[ $# -gt 0 ]]; do
  case $1 in
    --execute)
      DRY_RUN=false
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --category)
      CATEGORY="$2"
      shift 2
      ;;
    *)
      echo "未知参数: $1"
      exit 1
      ;;
  esac
done

echo "=========================================="
echo "代码清理脚本"
echo "=========================================="
echo ""

if [ "$DRY_RUN" = true ]; then
  echo -e "${YELLOW}模式: 预览模式 (不会实际删除文件)${NC}"
else
  echo -e "${RED}模式: 执行模式 (将实际删除文件)${NC}"
  echo -e "${RED}警告: 此操作不可逆！${NC}"
  echo ""
  read -p "确认继续? (输入 yes 继续): " confirm
  if [ "$confirm" != "yes" ]; then
    echo "已取消"
    exit 0
  fi
fi

echo ""
echo "类别: $CATEGORY"
echo ""

# 删除函数
delete_file() {
  local file=$1
  local reason=$2

  if [ -f "$WORK_DIR/$file" ]; then
    if [ "$DRY_RUN" = true ]; then
      echo -e "${YELLOW}[预览]${NC} 将删除: $file ($reason)"
    else
      rm "$WORK_DIR/$file"
      echo -e "${GREEN}[已删除]${NC} $file ($reason)"
    fi
  else
    echo -e "${RED}[不存在]${NC} $file"
  fi
}

delete_dir() {
  local dir=$1
  local reason=$2

  if [ -d "$WORK_DIR/$dir" ]; then
    if [ "$DRY_RUN" = true ]; then
      echo -e "${YELLOW}[预览]${NC} 将删除目录: $dir ($reason)"
    else
      rm -rf "$WORK_DIR/$dir"
      echo -e "${GREEN}[已删除]${NC} 目录: $dir ($reason)"
    fi
  else
    echo -e "${RED}[不存在]${NC} 目录: $dir"
  fi
}

# ============================================================
# 1. services/ 目录清理
# ============================================================

if [ "$CATEGORY" = "all" ] || [ "$CATEGORY" = "services" ]; then
  echo "----------------------------------------"
  echo "1. 清理 services/ 目录"
  echo "----------------------------------------"

  delete_file "services/example_service.py" "示例代码"
  delete_file "services/rendering_service_v2.py" "与 rendering_service.py 重复"
  delete_file "services/dxf_service.py" "与 tools.py 功能重复"
  delete_file "services/plan_service.py" "旧数据库架构"
  delete_file "services/strategy_service.py" "已被 Kimi Agent 替代"

  echo ""
fi

# ============================================================
# 2. 根目录测试文件清理
# ============================================================

if [ "$CATEGORY" = "all" ] || [ "$CATEGORY" = "tests" ]; then
  echo "----------------------------------------"
  echo "2. 清理根目录测试文件"
  echo "----------------------------------------"

  delete_file "test_cad_simple.py" "过时测试"
  delete_file "test_small_file.py" "临时测试"
  delete_file "test_auto_convert.py" "实验测试"
  delete_file "test_glaili.py" "临时测试"

  echo ""
fi

# ============================================================
# 3. 分析脚本清理
# ============================================================

if [ "$CATEGORY" = "all" ] || [ "$CATEGORY" = "scripts" ]; then
  echo "----------------------------------------"
  echo "3. 清理临时分析脚本"
  echo "----------------------------------------"

  delete_file "analyze_details.py" "临时分析脚本"
  delete_file "analyze_for_boq.py" "临时分析脚本"
  delete_file "boq_assessment_report.py" "临时报告脚本"

  echo ""
fi

# ============================================================
# 4. 临时文件清理
# ============================================================

if [ "$CATEGORY" = "all" ] || [ "$CATEGORY" = "temp" ]; then
  echo "----------------------------------------"
  echo "4. 清理临时文件"
  echo "----------------------------------------"

  delete_file "test_output_auto.dxf" "临时 DXF 文件"
  delete_file "test_small_file.dxf" "临时 DXF 文件"
  delete_file "test_output_miconv.dxf" "临时 DXF 文件"

  echo ""
fi

# ============================================================
# 5. repositories/ 目录清理
# ============================================================

if [ "$CATEGORY" = "all" ] || [ "$CATEGORY" = "repositories" ]; then
  echo "----------------------------------------"
  echo "5. 清理 repositories/ 目录"
  echo "----------------------------------------"

  delete_dir "repositories" "整个目录都是示例代码"

  echo ""
fi

# ============================================================
# 6. tests/ 目录清理
# ============================================================

if [ "$CATEGORY" = "all" ] || [ "$CATEGORY" = "tests-dir" ]; then
  echo "----------------------------------------"
  echo "6. 清理 tests/ 目录"
  echo "----------------------------------------"

  delete_file "tests/test_integration.py" "依赖不存在的框架"
  delete_file "tests/test_tools.py" "测试不存在的函数"

  echo ""
fi

# ============================================================
# 7. 其他调试文件清理
# ============================================================

if [ "$CATEGORY" = "all" ] || [ "$CATEGORY" = "debug" ]; then
  echo "----------------------------------------"
  echo "7. 清理调试文件"
  echo "----------------------------------------"

  delete_file "debug_miconv_elements.py" "调试脚本"
  delete_file "dwg_convert_helper.py" "临时辅助脚本"

  # 清理所有 test_conversion_*.py 文件
  for file in test_conversion_*.py; do
    if [ -f "$WORK_DIR/$file" ]; then
      delete_file "$file" "临时转换测试"
    fi
  done

  echo ""
fi

# ============================================================
# 统计
# ============================================================

echo "=========================================="
echo "清理完成"
echo "=========================================="

if [ "$DRY_RUN" = true ]; then
  echo ""
  echo -e "${YELLOW}这是预览模式，没有实际删除任何文件${NC}"
  echo ""
  echo "要执行删除，请运行:"
  echo "  bash cleanup_commands.sh --execute"
  echo ""
  echo "或者只删除特定类别:"
  echo "  bash cleanup_commands.sh --execute --category services"
  echo "  bash cleanup_commands.sh --execute --category tests"
  echo "  bash cleanup_commands.sh --execute --category scripts"
  echo "  bash cleanup_commands.sh --execute --category temp"
  echo "  bash cleanup_commands.sh --execute --category repositories"
  echo "  bash cleanup_commands.sh --execute --category debug"
else
  echo ""
  echo -e "${GREEN}文件已删除${NC}"
  echo ""
  echo "建议下一步:"
  echo "  1. 运行测试确保核心功能正常"
  echo "  2. 提交更改: git add -A && git commit -m 'chore: cleanup unused code'"
fi

echo ""
