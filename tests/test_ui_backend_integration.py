"""
UI与后端连接测试脚本
测试AutoJIT和JIT系统与UI的正确连接
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import numpy as np
from loguru import logger


def test_auto_jit_system():
    """测试AutoJIT系统"""
    logger.info("=" * 60)
    logger.info("测试AutoJIT系统")
    logger.info("=" * 60)
    
    try:
        from backtest.auto_jit_decorator import (
            auto_jit,
            get_auto_jit_summary,
            get_auto_jit_functions,
            get_auto_jit_stats,
            enable_auto_jit,
            disable_auto_jit,
            is_auto_jit_enabled
        )
        
        # 创建测试函数
        @auto_jit(name="test_autojit", description="AutoJIT测试函数", category="test")
        def test_function(x: float, y: float) -> float:
            total = 0.0
            for i in range(100):
                total += x * y
            return total
        
        # 测试函数
        result = test_function(2.0, 3.0)
        assert result == 600.0, "AutoJIT函数结果不正确"
        logger.info(f"✓ AutoJIT函数测试通过: {result}")
        
        # 测试状态切换
        assert is_auto_jit_enabled() == True, "AutoJIT应该默认启用"
        logger.info("✓ AutoJIT状态检查通过")
        
        disable_auto_jit()
        assert is_auto_jit_enabled() == False, "AutoJIT应该被禁用"
        logger.info("✓ AutoJIT禁用功能通过")
        
        enable_auto_jit()
        assert is_auto_jit_enabled() == True, "AutoJIT应该被启用"
        logger.info("✓ AutoJIT启用功能通过")
        
        # 测试统计信息
        summary = get_auto_jit_summary()
        logger.info(f"✓ AutoJIT摘要: {summary}")
        
        functions = get_auto_jit_functions()
        logger.info(f"✓ AutoJIT函数数量: {len(functions)}")
        
        stats = get_auto_jit_stats()
        logger.info(f"✓ AutoJIT统计: {len(stats)} 个函数有统计")
        
        return True
        
    except Exception as e:
        logger.error(f"AutoJIT系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_jit_optimizer():
    """测试JIT优化器"""
    logger.info("\n" + "=" * 60)
    logger.info("测试JIT优化器")
    logger.info("=" * 60)
    
    try:
        from backtest.jit_optimizer import jit_optimizer
        
        # 测试状态
        assert jit_optimizer.is_enabled() == True, "JIT优化器应该默认启用"
        logger.info("✓ JIT优化器状态检查通过")
        
        # 测试统计
        stats = jit_optimizer.get_stats()
        logger.info(f"✓ JIT优化器统计: {stats}")
        
        cache_stats = jit_optimizer.get_cache_stats()
        logger.info(f"✓ JIT缓存统计: {cache_stats}")
        
        efficiency = jit_optimizer.get_execution_efficiency()
        logger.info(f"✓ JIT执行效率: {efficiency:.2f}%")
        
        jit_usage = jit_optimizer.get_jit_usage()
        logger.info(f"✓ JIT使用情况: {len(jit_usage['functions'])} 个函数")
        
        # 测试状态切换
        jit_optimizer.disable()
        assert jit_optimizer.is_enabled() == False, "JIT优化器应该被禁用"
        logger.info("✓ JIT优化器禁用功能通过")
        
        jit_optimizer.enable()
        assert jit_optimizer.is_enabled() == True, "JIT优化器应该被启用"
        logger.info("✓ JIT优化器启用功能通过")
        
        return True
        
    except Exception as e:
        logger.error(f"JIT优化器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_jit_integration():
    """测试AutoJIT与JIT优化器的集成"""
    logger.info("\n" + "=" * 60)
    logger.info("测试AutoJIT与JIT优化器的集成")
    logger.info("=" * 60)
    
    try:
        from backtest.jit_optimizer import jit_optimizer
        from backtest.auto_jit_decorator import (
            auto_jit,
            get_auto_jit_summary
        )
        
        # 创建测试函数
        @auto_jit(name="integration_test", description="集成测试函数", category="integration")
        def integration_test(x: float) -> float:
            total = 0.0
            for i in range(100):
                total += x
            return total
        
        # 调用函数触发编译
        result = integration_test(2.0)
        assert result == 200.0, "集成测试函数结果不正确"
        logger.info(f"✓ 集成测试函数执行通过: {result}")
        
        # 导入AutoJIT函数到JIT优化器
        imported_count = jit_optimizer.import_from_auto_jit()
        logger.info(f"✓ 从AutoJIT导入了 {imported_count} 个函数")
        
        # 验证函数已导入
        jit_usage = jit_optimizer.get_jit_usage()
        assert 'integration_test' in jit_usage['functions'], "集成测试函数应该被导入"
        logger.info("✓ 集成测试函数已导入到JIT优化器")
        
        return True
        
    except Exception as e:
        logger.error(f"AutoJIT与JIT优化器集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_manager():
    """测试配置管理器"""
    logger.info("\n" + "=" * 60)
    logger.info("测试配置管理器")
    logger.info("=" * 60)
    
    try:
        from backtest.jit_config_manager import jit_config_manager
        
        # 测试配置加载
        loaded = jit_config_manager.load_config()
        logger.info(f"✓ 配置文件加载: {'成功' if loaded else '失败'}")
        
        # 测试全局配置
        global_config = jit_config_manager.get_global_config()
        logger.info(f"✓ 全局配置: {global_config}")
        
        # 测试函数配置
        functions = jit_config_manager.get_enabled_functions()
        logger.info(f"✓ 启用的函数数量: {len(functions)}")
        
        # 测试自动发现配置
        auto_discovery = jit_config_manager.get_auto_discovery_config()
        logger.info(f"✓ 自动发现配置: {auto_discovery}")
        
        # 测试监控配置
        monitoring = jit_config_manager.get_monitoring_config()
        logger.info(f"✓ 监控配置: {monitoring}")
        
        return True
        
    except Exception as e:
        logger.error(f"配置管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_integration():
    """测试UI集成"""
    logger.info("\n" + "=" * 60)
    logger.info("测试UI集成")
    logger.info("=" * 60)
    
    try:
        # 测试UI导入的函数
        from gui.widgets.performance.tabs.algorithm_optimization_tab import (
            get_auto_jit_summary,
            get_auto_jit_functions,
            get_auto_jit_stats,
            enable_auto_jit,
            disable_auto_jit,
            is_auto_jit_enabled
        )
        
        # 测试函数调用
        summary = get_auto_jit_summary()
        logger.info(f"✓ UI获取AutoJIT摘要: {summary}")
        
        functions = get_auto_jit_functions()
        logger.info(f"✓ UI获取AutoJIT函数: {len(functions)} 个")
        
        stats = get_auto_jit_stats()
        logger.info(f"✓ UI获取AutoJIT统计: {len(stats)} 个函数")
        
        # 测试状态控制
        enabled = is_auto_jit_enabled()
        logger.info(f"✓ UI状态检查通过: AutoJIT {'启用' if enabled else '禁用'}")
        
        disable_auto_jit()
        enabled = is_auto_jit_enabled()
        assert enabled == False, "AutoJIT应该被禁用"
        logger.info("✓ UI禁用AutoJIT通过")
        
        enable_auto_jit()
        enabled = is_auto_jit_enabled()
        assert enabled == True, "AutoJIT应该被启用"
        logger.info("✓ UI启用AutoJIT通过")
        
        return True
        
    except Exception as e:
        logger.error(f"UI集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_system_initializer():
    """测试系统初始化器"""
    logger.info("\n" + "=" * 60)
    logger.info("测试系统初始化器")
    logger.info("=" * 60)
    
    try:
        from backtest.jit_system_initializer import (
            initialize_jit_system,
            get_jit_system_status
        )
        
        # 测试系统初始化
        initialized = initialize_jit_system()
        logger.info(f"✓ JIT系统初始化: {'成功' if initialized else '失败'}")
        
        # 测试系统状态
        status = get_jit_system_status()
        logger.info(f"✓ JIT系统状态: {status}")
        
        return True
        
    except Exception as e:
        logger.error(f"系统初始化器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("开始UI与后端连接测试")
    logger.info("=" * 60)
    
    results = {}
    
    # 测试AutoJIT系统
    results['auto_jit'] = test_auto_jit_system()
    
    # 测试JIT优化器
    results['jit_optimizer'] = test_jit_optimizer()
    
    # 测试AutoJIT与JIT优化器的集成
    results['integration'] = test_auto_jit_integration()
    
    # 测试配置管理器
    results['config_manager'] = test_config_manager()
    
    # 测试UI集成
    results['ui_integration'] = test_ui_integration()
    
    # 测试系统初始化器
    results['system_initializer'] = test_system_initializer()
    
    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("所有测试通过！")
    else:
        logger.error("部分测试失败！")
    logger.info("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
