#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试matplotlib导入
"""

import sys

def test_matplotlib_import():
    """测试matplotlib导入"""
    print("=" * 80)
    print("测试matplotlib导入")
    print("=" * 80)

    try:
        print("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        print("✓ Qt模块导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 导入matplotlib...")
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        import numpy as np
        print("✓ matplotlib导入成功")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_matplotlib_import()
    sys.exit(0 if success else 1)