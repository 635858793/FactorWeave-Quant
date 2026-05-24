#!/bin/bash
# 自动化验证测试运行脚本
# 用法: bash scripts/run_validation.sh [选项]
# 
# 选项:
#   all          - 运行所有测试（默认）
#   imports      - 仅运行导入验证测试
#   database     - 仅运行数据库连接测试
#   coordinator  - 仅运行协调器初始化测试
#   dialog       - 仅运行对话框创建测试
#   order        - 仅运行订单执行器测试
#   report       - 生成测试报告
#   help         - 显示帮助信息

set -e

# 设置项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 设置日志目录
LOG_DIR="$PROJECT_ROOT/logs/validation"
mkdir -p "$LOG_DIR"

# 设置测试文件路径
TEST_FILE="$PROJECT_ROOT/tests/test_validation_suite.py"

# 检查测试文件是否存在
if [ ! -f "$TEST_FILE" ]; then
    echo "[错误] 测试文件不存在: $TEST_FILE"
    exit 1
fi

# 解析命令行参数
TEST_MARK=""
case "${1:-all}" in
    all)
        TEST_MARK=""
        ;;
    imports)
        TEST_MARK="-m imports"
        ;;
    database)
        TEST_MARK="-m database"
        ;;
    coordinator)
        TEST_MARK="-m coordinator"
        ;;
    dialog)
        TEST_MARK="-m dialog"
        ;;
    order)
        TEST_MARK="-m order"
        ;;
    report)
        TEST_MARK="-m report"
        ;;
    help)
        show_help
        exit 0
        ;;
    *)
        echo "[错误] 未知选项: $1"
        show_help
        exit 1
        ;;
esac

# 生成时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 设置报告文件
REPORT_FILE="$LOG_DIR/report_${TIMESTAMP}.html"
LOG_FILE="$LOG_DIR/run_${TIMESTAMP}.log"

echo "============================================"
echo "FactorWeave-Quant 自动化验证测试"
echo "============================================"
echo "运行时间: $TIMESTAMP"
echo "测试模式: ${1:-all}"
echo "测试文件: $TEST_FILE"
echo "报告文件: $REPORT_FILE"
echo "日志文件: $LOG_FILE"
echo "============================================"
echo ""

# 激活conda环境（如果需要）
# source ~/miniconda3/etc/profile.d/conda.sh
# conda activate hikyuu

# 运行pytest测试
if [ -z "$TEST_MARK" ]; then
    pytest "$TEST_FILE" \
        -v \
        --tb=short \
        --log-cli-level=INFO \
        --html="$REPORT_FILE" \
        --self-contained-html \
        2>&1 | tee "$LOG_FILE"
else
    pytest "$TEST_FILE" \
        $TEST_MARK \
        -v \
        --tb=short \
        --log-cli-level=INFO \
        --html="$REPORT_FILE" \
        --self-contained-html \
        2>&1 | tee "$LOG_FILE"
fi

# 检查测试结果
EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "============================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "测试状态: 全部通过 ✅"
    echo "报告文件: $REPORT_FILE"
    echo "日志文件: $LOG_FILE"
else
    echo "测试状态: 部分测试失败 ❌ (退出码: $EXIT_CODE)"
    echo "报告文件: $REPORT_FILE"
    echo "日志文件: $LOG_FILE"
fi
echo "============================================"

exit $EXIT_CODE

show_help() {
    echo ""
    echo "用法: bash scripts/run_validation.sh [选项]"
    echo ""
    echo "选项:"
    echo "  all          - 运行所有测试（默认）"
    echo "  imports      - 仅运行导入验证测试"
    echo "  database     - 仅运行数据库连接测试"
    echo "  coordinator  - 仅运行协调器初始化测试"
    echo "  dialog       - 仅运行对话框创建测试"
    echo "  order        - 仅运行订单执行器测试"
    echo "  report       - 生成测试报告"
    echo "  help         - 显示帮助信息"
    echo ""
    echo "示例:"
    echo "  bash scripts/run_validation.sh          # 运行所有测试"
    echo "  bash scripts/run_validation.sh imports  # 仅运行导入测试"
    echo "  bash scripts/run_validation.sh database # 仅运行数据库测试"
}
