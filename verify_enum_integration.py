"""
综合枚举集成验证脚本

验证所有枚举定义的正确性、完整性和系统集成情况
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_enums_import():
    """测试枚举导入"""
    print("=" * 60)
    print("1. 测试枚举导入")
    print("=" * 60)
    
    try:
        from core.enums import (
            HealthStatus,
            PluginLifecycle,
            PluginStatus,
            ComponentState,
            ComponentType
        )
        print("✅ 所有枚举导入成功")
        return True
    except Exception as e:
        print(f"❌ 枚举导入失败: {e}")
        return False

def test_enum_values():
    """测试枚举值"""
    print("\n" + "=" * 60)
    print("2. 测试枚举值")
    print("=" * 60)
    
    try:
        from core.enums import (
            HealthStatus,
            PluginLifecycle,
            PluginStatus,
            ComponentState,
            ComponentType
        )
        
        print(f"✅ HealthStatus: {len(list(HealthStatus))}个状态")
        print(f"✅ PluginLifecycle: {len(list(PluginLifecycle))}个状态")
        print(f"✅ PluginStatus: {len(list(PluginStatus))}个状态")
        print(f"✅ ComponentState: {len(list(ComponentState))}个状态")
        print(f"✅ ComponentType: {len(list(ComponentType))}个类型")
        return True
    except Exception as e:
        print(f"❌ 枚举值测试失败: {e}")
        return False

def test_enum_methods():
    """测试枚举方法"""
    print("\n" + "=" * 60)
    print("3. 测试枚举方法")
    print("=" * 60)
    
    try:
        from core.enums import (
            HealthStatus,
            PluginLifecycle,
            PluginStatus,
            ComponentState,
            ComponentType
        )
        
        # 测试HealthStatus方法
        assert HealthStatus.HEALTHY.is_healthy() == True
        assert HealthStatus.DEGRADED.needs_attention() == True
        assert HealthStatus.FAILED.is_operational() == False
        print("✅ HealthStatus方法测试通过")
        
        # 测试PluginLifecycle方法
        assert PluginLifecycle.LOADED.is_loaded() == True
        assert PluginLifecycle.ACTIVE.is_active() == True
        assert PluginLifecycle.FAILED.is_error() == True
        assert PluginLifecycle.LOADED.can_transition_to(PluginLifecycle.ACTIVATED) == True
        print("✅ PluginLifecycle方法测试通过")
        
        # 测试PluginStatus方法
        assert PluginStatus.ENABLED.is_enabled() == True
        assert PluginStatus.DISABLED.is_disabled() == True
        assert PluginStatus.RUNNING.is_operational() == True
        assert PluginStatus.ERROR.is_error() == True
        print("✅ PluginStatus方法测试通过")
        
        # 测试ComponentState方法
        assert ComponentState.REGISTERED.is_registered() == True
        assert ComponentState.ACTIVE.is_active() == True
        assert ComponentState.ERROR.is_error() == True
        print("✅ ComponentState方法测试通过")
        
        # 测试ComponentType方法
        assert ComponentType.WINDOW.is_window() == True
        assert ComponentType.DIALOG.is_dialog() == True
        assert ComponentType.WIDGET.is_widget() == True
        assert ComponentType.TAB.is_container() == True
        print("✅ ComponentType方法测试通过")
        
        return True
    except Exception as e:
        print(f"❌ 枚举方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_module_integration():
    """测试模块集成"""
    print("\n" + "=" * 60)
    print("4. 测试模块集成")
    print("=" * 60)
    
    results = []
    
    # 测试core模块
    try:
        from core.enums import PluginLifecycle, PluginStatus
        from core.plugin_types import PluginType
        print("✅ core模块集成成功")
        results.append(True)
    except Exception as e:
        print(f"❌ core模块集成失败: {e}")
        results.append(False)
    
    # 测试db模块
    try:
        import db.models.plugin_models
        print("✅ db模块集成成功")
        results.append(True)
    except Exception as e:
        print(f"❌ db模块集成失败: {e}")
        results.append(False)
    
    # 测试plugins模块
    try:
        import plugins.plugin_interface
        print("✅ plugins模块集成成功")
        results.append(True)
    except Exception as e:
        print(f"❌ plugins模块集成失败: {e}")
        results.append(False)
    
    return all(results)

def test_ui_integration():
    """测试UI集成"""
    print("\n" + "=" * 60)
    print("5. 测试UI集成")
    print("=" * 60)
    
    results = []
    
    # 测试gui模块
    try:
        from gui.registry.component_registry import ComponentState, ComponentType
        from gui.coordinators.modern_ui_coordinator import ComponentState as UIComponentState
        print("✅ gui模块集成成功")
        results.append(True)
    except Exception as e:
        print(f"❌ gui模块集成失败: {e}")
        results.append(False)
    
    return all(results)

def test_enum_consistency():
    """测试枚举一致性"""
    print("\n" + "=" * 60)
    print("6. 测试枚举一致性")
    print("=" * 60)
    
    try:
        from core.enums import (
            HealthStatus,
            PluginLifecycle,
            PluginStatus,
            ComponentState,
            ComponentType
        )
        
        # 检查枚举值的字符串表示
        assert HealthStatus.HEALTHY.value == "healthy"
        assert PluginLifecycle.LOADED.value == "loaded"
        assert PluginStatus.ENABLED.value == "enabled"
        assert ComponentState.ACTIVE.value == "active"
        assert ComponentType.WIDGET.value == "widget"
        print("✅ 枚举值字符串表示一致")
        
        # 检查枚举的__str__方法
        assert str(HealthStatus.HEALTHY) == "healthy"
        assert str(PluginLifecycle.LOADED) == "loaded"
        assert str(PluginStatus.ENABLED) == "enabled"
        assert str(ComponentState.ACTIVE) == "active"
        assert str(ComponentType.WIDGET) == "widget"
        print("✅ 枚举__str__方法一致")
        
        return True
    except Exception as e:
        print(f"❌ 枚举一致性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("枚举集成验证测试")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(test_enums_import())
    results.append(test_enum_values())
    results.append(test_enum_methods())
    results.append(test_module_integration())
    results.append(test_ui_integration())
    results.append(test_enum_consistency())
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(results)
    failed_tests = total_tests - passed_tests
    
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {failed_tests}")
    
    if all(results):
        print("\n✅ 所有测试通过！枚举集成验证成功。")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
