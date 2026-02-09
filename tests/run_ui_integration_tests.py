#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI 集成回归测试运行脚本

使用方法：
    python run_ui_integration_tests.py [选项]

选项：
    --verbose, -v          详细输出模式
    --pattern, -p PATTERN  只运行匹配模式的测试
    --report-dir DIR         指定报告输出目录
    --no-gui               跳过 GUI 测试
    --help, -h             显示帮助信息

示例：
    python run_ui_integration_tests.py
    python run_ui_integration_tests.py --verbose
    python run_ui_integration_tests.py --pattern test_ui_
    python run_ui_integration_tests.py --no-gui
"""

import sys
import os
import argparse
import unittest
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="UI 集成回归测试运行脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python run_ui_integration_tests.py
  python run_ui_integration_tests.py --verbose
  python run_ui_integration_tests.py --pattern test_ui_
  python run_ui_integration_tests.py --no-gui
        """
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出模式"
    )

    parser.add_argument(
        "-p", "--pattern",
        type=str,
        default=None,
        help="只运行匹配模式的测试"
    )

    parser.add_argument(
        "--report-dir",
        type=str,
        default="test_reports",
        help="指定报告输出目录"
    )

    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="跳过 GUI 测试"
    )

    return parser.parse_args()


def run_tests(args):
    """运行测试"""
    logger.info("=" * 80)
    logger.info("UI 集成回归测试")
    logger.info("=" * 80)

    # 导入测试模块
    try:
        from test_ui_integration_regression import TestUIIntegration
    except ImportError:
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from test_ui_integration_regression import TestUIIntegration
        except ImportError as e:
            logger.error(f"无法导入测试模块: {e}")
            logger.error(f"请确保在项目根目录运行测试")
            return False

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 加载测试用例
    if args.pattern:
        logger.info(f"只运行匹配模式 '{args.pattern}' 的测试")
        suite.addTests(loader.loadTestsFromName(f"test_ui_integration_regression.{args.pattern}"))
    else:
        suite.addTests(loader.loadTestsFromTestCase(TestUIIntegration))

    # 如果指定了 --no-gui，过滤掉 GUI 测试
    if args.no_gui:
        logger.info("跳过 GUI 测试")
        filtered_suite = unittest.TestSuite()
        
        def filter_tests(test_suite):
            """递归过滤测试套件"""
            for test in test_suite:
                if isinstance(test, unittest.TestSuite):
                    filter_tests(test)
                else:
                    test_name = str(test)
                    if "gui" not in test_name.lower() and "dialog" not in test_name.lower():
                        filtered_suite.addTest(test)
        
        filter_tests(suite)
        suite = filtered_suite

    # 设置详细程度
    verbosity = 2 if args.verbose else 1

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    # 输出测试摘要
    logger.info("=" * 80)
    logger.info("测试摘要")
    logger.info("=" * 80)
    logger.info(f"总测试数: {result.testsRun}")
    logger.info(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    logger.info(f"失败: {len(result.failures)}")
    logger.info(f"错误: {len(result.errors)}")
    logger.info(f"跳过: {len(result.skipped)}")

    # 输出失败和错误的详细信息
    if result.failures:
        logger.info("\n失败的测试:")
        for test, traceback in result.failures:
            logger.info(f"  - {test}")
            if args.verbose:
                logger.info(f"\n{traceback}")

    if result.errors:
        logger.info("\n错误的测试:")
        for test, traceback in result.errors:
            logger.info(f"  - {test}")
            if args.verbose:
                logger.info(f"\n{traceback}")

    # 检查报告目录
    report_dir = Path(args.report_dir)
    if report_dir.exists():
        logger.info(f"\n测试报告已保存到: {report_dir}")
        report_files = list(report_dir.glob("ui_integration_test_report_*.txt"))
        if report_files:
            latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"最新报告: {latest_report}")

    return result.wasSuccessful()


def main():
    """主函数"""
    args = parse_arguments()

    try:
        success = run_tests(args)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"运行测试时发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
