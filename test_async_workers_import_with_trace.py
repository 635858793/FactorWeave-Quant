#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试async_workers导入时卡住的问题
"""

import sys
from pathlib import Path
import traceback

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_async_workers_import_with_trace():
    """测试async_workers导入时卡住的问题"""
    print("=" * 80)
    print("测试async_workers导入时卡住的问题")
    print("=" * 80)

    try:
        print("1. 导入PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        print("✓ PyQt5.QtWidgets导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 导入async_workers模块...")
        import gui.widgets.performance.workers.async_workers
        print("✓ async_workers模块导入成功")

        print("4. 访问AsyncDataSignals类...")
        from gui.widgets.performance.workers.async_workers import AsyncDataSignals
        print("✓ AsyncDataSignals类导入成功")

        print("5. 创建AsyncDataSignals实例...")
        signals = AsyncDataSignals()
        print(f"✓ AsyncDataSignals实例创建成功: {type(signals).__name__}")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_async_workers_import_with_trace()
    print(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)