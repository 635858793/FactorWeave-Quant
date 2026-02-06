"""
简化的回归测试脚本

测试修复后的功能：
1. MainWindowCoordinator 初始化
2. panel_padding 配置
3. MiddlePanel 没有 get_stock_list 方法
"""

import sys
import traceback

def test_simple_import():
    """测试简单的导入"""
    print("\n" + "="*60)
    print("测试 1: 简单导入")
    print("="*60)
    
    try:
        print("正在导入 MainWindowCoordinator...")
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        print("✓ MainWindowCoordinator 导入成功")
        
        print("正在导入服务容器和事件总线...")
        from core.containers import get_service_container
        from core.events import get_event_bus
        print("✓ 服务容器和事件总线导入成功")
        
        print("\n✓ 测试 1 通过: 简单导入成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 1 失败: {e}")
        traceback.print_exc()
        return False


def test_coordinator_creation():
    """测试创建协调器实例"""
    print("\n" + "="*60)
    print("测试 2: 创建协调器实例")
    print("="*60)
    
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import get_service_container
        from core.events import get_event_bus
        
        print("正在获取服务容器...")
        service_container = get_service_container()
        print("✓ 服务容器获取成功")
        
        print("正在获取事件总线...")
        event_bus = get_event_bus()
        print("✓ 事件总线获取成功")
        
        print("正在创建 MainWindowCoordinator 实例...")
        coordinator = MainWindowCoordinator(
            service_container=service_container,
            event_bus=event_bus,
            parent=None
        )
        print("✓ MainWindowCoordinator 实例创建成功")
        
        print("\n✓ 测试 2 通过: 创建协调器实例成功")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试 2 失败: {e}")
        traceback.print_exc()
        return False


def test_layout_config():
    """测试布局配置"""
    print("\n" + "="*60)
    print("测试 3: 布局配置")
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
        
        print("正在验证 _layout_config 属性...")
        assert hasattr(coordinator, '_layout_config'), "缺少 _layout_config 属性"
        print("✓ _layout_config 属性存在")
        
        print("正在验证 panel_padding 配置...")
        assert 'panel_padding' in coordinator._layout_config, "缺少 panel_padding 配置"
        print(f"✓ panel_padding 配置存在: {coordinator._layout_config['panel_padding']}")
        
        print("正在验证 panel_padding 值...")
        assert coordinator._layout_config['panel_padding'] == 5, "panel_padding 值不正确"
        print(f"✓ panel_padding 值正确: {coordinator._layout_config['panel_padding']}")
        
        print("\n✓ 测试 3 通过: 布局配置正确")
        return True
        
    except AssertionError as e:
        print(f"\n✗ 测试 3 失败（断言错误）: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ 测试 3 失败（异常）: {e}")
        traceback.print_exc()
        return False


def test_no_get_stock_list():
    """测试没有 get_stock_list 方法"""
    print("\n" + "="*60)
    print("测试 4: 没有 get_stock_list 方法")
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
        
        print("正在检查 coordinator 是否有 get_stock_list 方法...")
        has_get_stock_list = hasattr(coordinator, 'get_stock_list')
        print(f"  coordinator.get_stock_list 存在: {has_get_stock_list}")
        
        print("正在验证 coordinator 没有 get_stock_list 方法...")
        assert not has_get_stock_list, "coordinator 不应该有 get_stock_list 方法"
        print("✓ coordinator 确实没有 get_stock_list 方法")
        
        print("正在验证 hasattr 返回 False...")
        result = hasattr(coordinator, 'get_stock_list')
        print(f"✓ hasattr(coordinator, 'get_stock_list') 返回: {result}")
        
        assert result == False, "hasattr 应该返回 False"
        print("✓ hasattr 返回 False，死代码不会执行")
        
        print("\n✓ 测试 4 通过: 没有 get_stock_list 方法验证成功")
        return True
        
    except AssertionError as e:
        print(f"\n✗ 测试 4 失败（断言错误）: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ 测试 4 失败（异常）: {e}")
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有回归测试"""
    print("\n" + "="*60)
    print("开始简化回归测试")
    print("="*60)
    
    tests = [
        ("简单导入", test_simple_import),
        ("创建协调器实例", test_coordinator_creation),
        ("布局配置", test_layout_config),
        ("没有 get_stock_list 方法", test_no_get_stock_list),
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
