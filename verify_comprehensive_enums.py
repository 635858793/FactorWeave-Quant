"""
全面枚举验证脚本

检查所有枚举定义、重复枚举、遗漏替换和验证使用情况
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_all_enums_import():
    """测试所有枚举导入"""
    print("=" * 60)
    print("1. 测试所有枚举导入")
    print("=" * 60)
    
    try:
        # 核心枚举
        from core.enums import (
            HealthStatus,
            PluginLifecycle,
            PluginStatus,
            ComponentState,
            ComponentType
        )
        print("✅ core.enums导入成功")
        
        # 插件类型枚举
        from core.plugin_types import (
            PluginType,
            PluginCategory,
            AssetType,
            DataType,
            PluginPriority
        )
        print("✅ core.plugin_types导入成功")
        
        # 接口枚举
        from core.interfaces.data_source import ConnectionStatus
        from core.interfaces.cache import CacheLevel
        from core.interfaces.circuit_breaker import CircuitBreakerState
        print("✅ core.interfaces枚举导入成功")
        
        return True
    except Exception as e:
        print(f"❌ 枚举导入失败: {e}")
        import traceback
        traceback.print_exc()
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
        from core.plugin_types import (
            PluginType,
            PluginCategory,
            AssetType,
            DataType
        )
        
        print(f"✅ HealthStatus: {len(list(HealthStatus))}个状态")
        print(f"✅ PluginLifecycle: {len(list(PluginLifecycle))}个状态")
        print(f"✅ PluginStatus: {len(list(PluginStatus))}个状态")
        print(f"✅ ComponentState: {len(list(ComponentState))}个状态")
        print(f"✅ ComponentType: {len(list(ComponentType))}个类型")
        print(f"✅ PluginType: {len(list(PluginType))}个类型")
        print(f"✅ PluginCategory: {len(list(PluginCategory))}个分类")
        print(f"✅ AssetType: {len(list(AssetType))}个资产类型")
        print(f"✅ DataType: {len(list(DataType))}个数据类型")
        
        return True
    except Exception as e:
        print(f"❌ 枚举值测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_no_duplicate_enums():
    """测试没有重复的枚举定义"""
    print("\n" + "=" * 60)
    print("3. 测试没有重复的枚举定义")
    print("=" * 60)
    
    try:
        # 检查PluginType是否只有一个定义
        from core.plugin_types import PluginType as CorePluginType
        from core.interfaces.plugin import PluginType as InterfacePluginType
        
        # 应该是同一个对象
        assert CorePluginType is InterfacePluginType, "PluginType定义重复"
        print("✅ PluginType没有重复定义")
        
        # 检查PluginCategory是否只有一个定义
        from core.plugin_types import PluginCategory as CorePluginCategory
        from plugins.plugin_interface import PluginCategory as PluginsPluginCategory
        
        # 应该是同一个对象
        assert CorePluginCategory is PluginsPluginCategory, "PluginCategory定义重复"
        print("✅ PluginCategory没有重复定义")
        
        return True
    except Exception as e:
        print(f"❌ 重复枚举测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_plugin_state_renamed():
    """测试PluginState已重命名为PluginLifecycle"""
    print("\n" + "=" * 60)
    print("4. 测试PluginState已重命名为PluginLifecycle")
    print("=" * 60)
    
    try:
        from core.enums import PluginLifecycle
        
        # 检查PluginLifecycle存在
        assert hasattr(PluginLifecycle, 'LOADED'), "PluginLifecycle.LOADED不存在"
        assert hasattr(PluginLifecycle, 'ACTIVE'), "PluginLifecycle.ACTIVE不存在"
        assert hasattr(PluginLifecycle, 'FAILED'), "PluginLifecycle.FAILED不存在"
        print("✅ PluginLifecycle存在且包含必要的状态")
        
        # 检查PluginState不存在
        try:
            from core.enums import PluginState
            print("❌ PluginState仍然存在，应该已被重命名为PluginLifecycle")
            return False
        except ImportError:
            print("✅ PluginState已成功重命名为PluginLifecycle")
            return True
            
    except Exception as e:
        print(f"❌ PluginState重命名测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_module_imports():
    """测试模块导入"""
    print("\n" + "=" * 60)
    print("5. 测试模块导入")
    print("=" * 60)
    
    results = []
    
    # 测试核心模块
    try:
        import core.enums
        import core.plugin_types
        import core.plugin_manager
        import core.interfaces.plugin
        import core.interfaces.data_source
        import core.interfaces.cache
        import core.interfaces.circuit_breaker
        print("✅ 核心模块导入成功")
        results.append(True)
    except Exception as e:
        print(f"❌ 核心模块导入失败: {e}")
        results.append(False)
    
    # 测试数据库模块
    try:
        import db.models.plugin_models
        print("✅ 数据库模块导入成功")
        results.append(True)
    except Exception as e:
        print(f"❌ 数据库模块导入失败: {e}")
        results.append(False)
    
    # 测试插件模块
    try:
        import plugins.plugin_interface
        print("✅ 插件模块导入成功")
        results.append(True)
    except Exception as e:
        print(f"❌ 插件模块导入失败: {e}")
        results.append(False)
    
    return all(results)

def test_enum_methods():
    """测试枚举方法"""
    print("\n" + "=" * 60)
    print("6. 测试枚举方法")
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

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("全面枚举验证测试")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(test_all_enums_import())
    results.append(test_enum_values())
    results.append(test_no_duplicate_enums())
    results.append(test_plugin_state_renamed())
    results.append(test_module_imports())
    results.append(test_enum_methods())
    
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
        print("\n✅ 所有测试通过！枚举验证成功。")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
