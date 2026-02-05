#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试system_monitor_tab导入
"""

import sys
import traceback

def test_system_monitor_tab_import():
    """测试system_monitor_tab导入"""
    print("=" * 80)
    print("测试system_monitor_tab导入")
    print("=" * 80)

    try:
        print("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        print("✓ Qt模块导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 导入metric_card...")
        from gui.widgets.performance.components.metric_card import ModernMetricCard
        print("✓ metric_card导入成功")

        print("4. 导入performance_chart...")
        from gui.widgets.performance.components.performance_chart import ModernPerformanceChart
        print("✓ performance_chart导入成功")

        print("5. 导入enhanced_risk_monitor...")
        from core.risk_monitoring.enhanced_risk_monitor import get_enhanced_risk_monitor
        print("✓ enhanced_risk_monitor导入成功")

        print("6. 导入system_monitor_tab...")
        from gui.widgets.performance.tabs.system_monitor_tab import ModernSystemMonitorTab
        print("✓ system_monitor_tab导入成功")

        print("7. 创建ModernSystemMonitorTab实例...")
        tab = ModernSystemMonitorTab()
        print("✓ ModernSystemMonitorTab实例创建成功")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_system_monitor_tab_import()
    sys.exit(0 if success else 1)