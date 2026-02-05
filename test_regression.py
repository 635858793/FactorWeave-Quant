"""
回归测试脚本

测试修复后的功能：
1. MainWindowCoordinator 初始化
2. panel_padding 配置
3. MiddlePanel 多屏功能
"""

import sys
import traceback
from loguru import logger

def test_main_window_coordinator_initialization():
    """测试 MainWindowCoordinator 初始化"""
    print("\n" + "="*60)
    print("测试 1: MainWindowCoordinator 初始化")
    print("="*60)
    
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import get_service_container
        from core.events import get_event_bus
        
        print("✓ 导入成功")
        
        service_container = get_service_container()
        event_bus = get_event_bus()
        print("✓ 服务容器和事件总线获取成功")
        
        print("正在创建 MainWindowCoordinator 实例...")
        coordinator = MainWindowCoordinator(
            service_container=service_container,
            event_bus=event_bus,
            parent=None
        )
        print("✓ MainWindowCoordinator 实例创建成功")
        
        # 验证关键属性
        print("正在验证关键属性...")
        assert hasattr(coordinator, '_main_window'), "缺少 _main_window 属性"
        print("✓ _main_window 属性存在")
        
        assert hasattr(coordinator, '_layout_config'), "缺少 _layout_config 属性"
        print("✓ _layout_config 属性存在")
        
        assert hasattr(coordinator, '_panels'), "缺少 _panels 属性"
        print("✓ _panels 属性存在")
        
        assert hasattr(coordinator, '_current_symbol'), "缺少 _current_symbol 属性"
        print("✓ _current_symbol 属性存在")
        
        assert hasattr(coordinator, '_current_asset_data'), "缺少 _current_asset_data 属性"
        print("✓ _current_asset_data 属性存在")
        
        print("\n✓ 测试 1 通过: MainWindowCoordinator 初始化成功")
        return True
        
    except AssertionError as e:
        print(f"\n✗ 测试 1 失败（断言错误）: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ 测试 1 失败（异常）: {e}")
        traceback.print_exc()
        return False


def test_panel_padding_config():
    """测试 panel_padding 配置"""
    print("\n" + "="*60)
    print("测试 2: panel_padding 配置")
    print("="*60)
    
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import get_service_container
        from core.events import get_event_bus
        
        coordinator = MainWindowCoordinator(
            service_container=get_service_container(),
            event_bus=get_event_bus(),
            parent=None
        )
        
        # 验证 panel_padding 配置
        assert 'panel_padding' in coordinator._layout_config, "缺少 panel_padding 配置"
        print(f"✓ panel_padding 配置存在: {coordinator._layout_config['panel_padding']}")
        
        assert coordinator._layout_config['panel_padding'] == 5, "panel_padding 值不正确"
        print(f"✓ panel_padding 值正确: {coordinator._layout_config['panel_padding']}")
        
        # 验证其他布局配置
        assert 'left_panel_width' in coordinator._layout_config, "缺少 left_panel_width 配置"
        print(f"✓ left_panel_width: {coordinator._layout_config['left_panel_width']}")
        
        assert 'right_panel_width' in coordinator._layout_config, "缺少 right_panel_width 配置"
        print(f"✓ right_panel_width: {coordinator._layout_config['right_panel_width']}")
        
        assert 'bottom_panel_height' in coordinator._layout_config, "缺少 bottom_panel_height 配置"
        print(f"✓ bottom_panel_height: {coordinator._layout_config['bottom_panel_height']}")
        
        print("\n✓ 测试 2 通过: panel_padding 配置正确")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 2 失败: {e}")
        traceback.print_exc()
        return False


def test_middle_panel_no_get_stock_list():
    """测试 MiddlePanel 没有 get_stock_list 方法"""
    print("\n" + "="*60)
    print("测试 3: MiddlePanel 没有 get_stock_list 方法")
    print("="*60)
    
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import get_service_container
        from core.events import get_event_bus
        
        coordinator = MainWindowCoordinator(
            service_container=get_service_container(),
            event_bus=get_event_bus(),
            parent=None
        )
        
        # 验证 coordinator 没有 get_stock_list 方法
        has_get_stock_list = hasattr(coordinator, 'get_stock_list')
        print(f"  coordinator.get_stock_list 存在: {has_get_stock_list}")
        
        assert not has_get_stock_list, "coordinator 不应该有 get_stock_list 方法"
        print("✓ coordinator 确实没有 get_stock_list 方法")
        
        # 验证 hasattr 返回 False
        result = hasattr(coordinator, 'get_stock_list')
        print(f"✓ hasattr(coordinator, 'get_stock_list') 返回: {result}")
        
        assert result == False, "hasattr 应该返回 False"
        print("✓ hasattr 返回 False，死代码不会执行")
        
        print("\n✓ 测试 3 通过: MiddlePanel 死代码验证成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 3 失败: {e}")
        traceback.print_exc()
        return False


def test_coordinator_initialization_with_parent():
    """测试带 parent 参数的初始化"""
    print("\n" + "="*60)
    print("测试 4: 带 parent 参数的初始化")
    print("="*60)
    
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import get_service_container
        from core.events import get_event_bus
        from PyQt5.QtWidgets import QWidget
        
        parent_widget = QWidget()
        print("✓ 创建了 parent_widget")
        
        coordinator = MainWindowCoordinator(
            service_container=get_service_container(),
            event_bus=get_event_bus(),
            parent=parent_widget
        )
        print("✓ MainWindowCoordinator 实例创建成功（带 parent 参数）")
        
        assert coordinator._main_window.parent() == parent_widget, "parent 设置不正确"
        print("✓ parent 设置正确")
        
        print("\n✓ 测试 4 通过: 带 parent 参数的初始化成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 4 失败: {e}")
        traceback.print_exc()
        return False


def test_backward_compatibility_properties():
    """测试向后兼容属性"""
    print("\n" + "="*60)
    print("测试 5: 向后兼容属性")
    print("="*60)
    
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import get_service_container
        from core.events import get_event_bus
        
        coordinator = MainWindowCoordinator(
            service_container=get_service_container(),
            event_bus=get_event_bus(),
            parent=None
        )
        
        # 测试 _current_stock_code 属性
        coordinator._current_stock_code = "600000"
        print(f"✓ 设置 _current_stock_code: {coordinator._current_stock_code}")
        assert coordinator._current_stock_code == "600000", "_current_stock_code 设置失败"
        assert coordinator._current_symbol == "600000", "_current_symbol 未同步"
        print("✓ _current_stock_code 和 _current_symbol 同步正确")
        
        # 测试 _current_stock_data 属性
        test_data = {"test": "data"}
        coordinator._current_stock_data = test_data
        print(f"✓ 设置 _current_stock_data: {coordinator._current_stock_data}")
        assert coordinator._current_stock_data == test_data, "_current_stock_data 设置失败"
        assert coordinator._current_asset_data == test_data, "_current_asset_data 未同步"
        print("✓ _current_stock_data 和 _current_asset_data 同步正确")
        
        print("\n✓ 测试 5 通过: 向后兼容属性工作正常")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 5 失败: {e}")
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有回归测试"""
    print("\n" + "="*60)
    print("开始回归测试")
    print("="*60)
    
    tests = [
        ("MainWindowCoordinator 初始化", test_main_window_coordinator_initialization),
        ("panel_padding 配置", test_panel_padding_config),
        ("MiddlePanel 没有 get_stock_list 方法", test_middle_panel_no_get_stock_list),
        ("带 parent 参数的初始化", test_coordinator_initialization_with_parent),
        ("向后兼容属性", test_backward_compatibility_properties),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ 测试 '{test_name}' 发生异常: {e}")
            traceback.print_exc()
            results.append((test_name, False))
    
    print("\n" + "="*60)
    print("回归测试结果汇总")
    print("="*60)
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-"*60)
    print(f"总计: {len(results)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print("-"*60)
    
    if failed == 0:
        print("\n✓✓✓ 所有回归测试通过 ✓✓✓")
        return True
    else:
        print(f"\n✗✗✗ 有 {failed} 个测试失败 ✗✗✗")
        return False


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 回归测试发生严重错误: {e}")
        traceback.print_exc()
        sys.exit(1)
