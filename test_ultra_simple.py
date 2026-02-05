"""
超简单的回归测试脚本

测试修复后的功能：
1. MainWindowCoordinator 导入
2. panel_padding 配置
3. 没有 get_stock_list 方法
"""

import sys
import traceback

def test_import():
    """测试导入"""
    print("\n测试 1: 导入 MainWindowCoordinator")
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        print("✓ 导入成功")
        return True
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        traceback.print_exc()
        return False

def test_creation():
    """测试创建实例"""
    print("\n测试 2: 创建实例")
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import get_service_container
        from core.events import get_event_bus
        
        service_container = get_service_container()
        event_bus = get_event_bus()
        
        coordinator = MainWindowCoordinator(
            service_container=service_container,
            event_bus=event_bus,
            parent=None
        )
        print("✓ 实例创建成功")
        return coordinator
    except Exception as e:
        print(f"✗ 实例创建失败: {e}")
        traceback.print_exc()
        return None

def test_panel_padding(coordinator):
    """测试 panel_padding"""
    print("\n测试 3: panel_padding 配置")
    try:
        assert hasattr(coordinator, '_layout_config')
        assert 'panel_padding' in coordinator._layout_config
        assert coordinator._layout_config['panel_padding'] == 5
        print(f"✓ panel_padding: {coordinator._layout_config['panel_padding']}")
        return True
    except Exception as e:
        print(f"✗ panel_padding 验证失败: {e}")
        traceback.print_exc()
        return False

def test_no_get_stock_list(coordinator):
    """测试没有 get_stock_list"""
    print("\n测试 4: 没有 get_stock_list 方法")
    try:
        has_get_stock_list = hasattr(coordinator, 'get_stock_list')
        assert not has_get_stock_list
        print("✓ 没有 get_stock_list 方法")
        return True
    except Exception as e:
        print(f"✗ get_stock_list 验证失败: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*60)
    print("开始超简单回归测试")
    print("="*60)
    
    # 测试 1: 导入
    if not test_import():
        sys.exit(1)
    
    # 测试 2: 创建实例
    coordinator = test_creation()
    if coordinator is None:
        sys.exit(1)
    
    # 测试 3: panel_padding
    if not test_panel_padding(coordinator):
        sys.exit(1)
    
    # 测试 4: 没有 get_stock_list
    if not test_no_get_stock_list(coordinator):
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✓✓✓ 所有测试通过 ✓✓✓")
    print("="*60)
