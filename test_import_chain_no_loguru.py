#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入链（不使用loguru）
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_import_chain_no_loguru():
    """测试导入链（不使用loguru）"""
    print("=" * 80)
    print("测试导入链（不使用loguru）")
    print("=" * 80)

    try:
        print("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        print("✓ Qt模块导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 导入gui.widgets.performance.workers...")
        import gui.widgets.performance.workers
        print("✓ gui.widgets.performance.workers导入成功")

        print("4. 访问AsyncDataSignals...")
        from gui.widgets.performance.workers import AsyncDataSignals
        print("✓ AsyncDataSignals类导入成功")

        print("5. 创建AsyncDataSignals实例...")
        signals = AsyncDataSignals()
        print(f"✓ AsyncDataSignals实例创建成功: {type(signals).__name__}")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_import_chain_no_loguru()
    print(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)