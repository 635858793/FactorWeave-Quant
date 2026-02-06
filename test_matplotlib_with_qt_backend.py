#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试matplotlib导入（使用Qt后端）
"""

import sys
import traceback

def test_matplotlib_with_qt_backend():
    """测试matplotlib导入（使用Qt后端）"""
    print("=" * 80)
    print("测试matplotlib导入（使用Qt后端）")
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
        print("✓ matplotlib导入成功")

        print("4. 设置matplotlib后端为Agg...")
        matplotlib.use('Agg')
        print("✓ matplotlib后端设置成功")

        print("5. 导入matplotlib.pyplot...")
        import matplotlib.pyplot as plt
        print("✓ matplotlib.pyplot导入成功")

        print("6. 导入Figure...")
        from matplotlib.figure import Figure
        print("✓ Figure导入成功")

        print("7. 导入numpy...")
        import numpy as np
        print("✓ numpy导入成功")

        print("8. 创建一个简单的图表...")
        fig, ax = plt.subplots()
        x = np.linspace(0, 10, 100)
        ax.plot(x, np.sin(x))
        print("✓ 图表创建成功")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_matplotlib_with_qt_backend()
    sys.exit(0 if success else 1)