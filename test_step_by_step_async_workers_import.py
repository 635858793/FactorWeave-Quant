#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐步测试async_workers导入
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_step_by_step_async_workers_import():
    """逐步测试async_workers导入"""
    print("=" * 80)
    print("逐步测试async_workers导入")
    print("=" * 80)

    try:
        print("1. 导入PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        print("✓ PyQt5.QtWidgets导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 导入async_workers模块（不导入任何类）...")
        import gui.widgets.performance.workers.async_workers as async_workers_module
        print("✓ async_workers模块导入成功")

        print("4. 访问AsyncDataSignals类...")
        signals_class = async_workers_module.AsyncDataSignals
        print(f"✓ AsyncDataSignals类访问成功: {signals_class.__name__}")

        print("5. 创建AsyncDataSignals实例...")
        signals = signals_class()
        print(f"✓ AsyncDataSignals实例创建成功: {type(signals).__name__}")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_step_by_step_async_workers_import()
    print(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)