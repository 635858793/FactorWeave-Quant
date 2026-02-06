#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试async_workers导入时是否有循环导入
"""

import sys
from pathlib import Path
import traceback

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_circular_import():
    """测试async_workers导入时是否有循环导入"""
    print("=" * 80)
    print("测试async_workers导入时是否有循环导入")
    print("=" * 80)

    try:
        print("1. 导入PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        print("✓ PyQt5.QtWidgets导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 导入async_workers模块（使用importlib）...")
        import importlib
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "async_workers",
            "gui/widgets/performance/workers/async_workers.py"
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["async_workers"] = module
            spec.loader.exec_module(module)
            print("✓ async_workers模块导入成功")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_circular_import()
    print(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)