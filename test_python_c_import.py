#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用Python -c直接测试async_workers导入
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_python_c_import():
    """使用python -c直接测试async_workers导入"""
    print("=" * 80)
    print("使用python -c直接测试async_workers导入")
    print("=" * 80)

    try:
        print("1. 导入PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        print("✓ PyQt5.QtWidgets导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 使用exec直接导入async_workers模块...")
        code = """
import sys
sys.path.insert(0, r'd:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui')
import gui.widgets.performance.workers.async_workers
print("async_workers模块导入成功")
"""
        exec(code)
        print("✓ async_workers模块导入成功")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_python_c_import()
    print(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)