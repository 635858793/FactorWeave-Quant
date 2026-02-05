#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试matplotlib导入（逐步测试）
"""

import sys
import traceback

def test_matplotlib_step_by_step():
    """测试matplotlib导入（逐步测试）"""
    print("=" * 80)
    print("测试matplotlib导入（逐步测试）")
    print("=" * 80)

    try:
        print("1. 导入matplotlib...")
        import matplotlib
        print("✓ matplotlib导入成功")

        print("2. 设置matplotlib后端...")
        matplotlib.use('Agg')
        print("✓ matplotlib后端设置成功")

        print("3. 导入matplotlib.pyplot...")
        import matplotlib.pyplot as plt
        print("✓ matplotlib.pyplot导入成功")

        print("4. 导入Figure...")
        from matplotlib.figure import Figure
        print("✓ Figure导入成功")

        print("5. 导入numpy...")
        import numpy as np
        print("✓ numpy导入成功")

        print("6. 导入matplotlib.backends...")
        import matplotlib.backends
        print("✓ matplotlib.backends导入成功")

        print("7. 导入matplotlib.backends.backend_qt5agg...")
        import matplotlib.backends.backend_qt5agg
        print("✓ matplotlib.backends.backend_qt5agg导入成功")

        print("8. 导入FigureCanvasQTAgg...")
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        print("✓ FigureCanvasQTAgg导入成功")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_matplotlib_step_by_step()
    sys.exit(0 if success else 1)