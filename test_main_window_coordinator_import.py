#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试MainWindowCoordinator导入
"""

import sys
import traceback

def test_main_window_coordinator_import():
    """测试MainWindowCoordinator导入"""
    print("=" * 80)
    print("测试MainWindowCoordinator导入")
    print("=" * 80)

    try:
        print("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        print("✓ Qt模块导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 导入服务容器和事件总线...")
        from core.containers.service_container import get_service_container
        from core.events import get_event_bus
        service_container = get_service_container()
        event_bus = get_event_bus()
        print("✓ 服务容器和事件总线导入成功")

        print("4. 导入MainWindowCoordinator...")
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        print("✓ MainWindowCoordinator导入成功")

        print("5. 创建MainWindowCoordinator实例...")
        coordinator = MainWindowCoordinator(
            service_container=service_container,
            event_bus=event_bus
        )
        print("✓ MainWindowCoordinator实例创建成功")

        print("6. 初始化MainWindowCoordinator...")
        coordinator.initialize()
        print("✓ MainWindowCoordinator初始化成功")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_main_window_coordinator_import()
    sys.exit(0 if success else 1)