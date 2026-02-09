"""
JIT系统初始化模块
在系统启动时自动加载配置并初始化JIT系统
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def initialize_jit_system():
    """初始化JIT系统
    
    在系统启动时自动执行以下操作：
    1. 加载JIT配置文件
    2. 根据配置启用/禁用JIT优化
    3. 自动发现并注册JIT函数
    4. 导入AutoJIT函数到JIT优化器
    """
    try:
        logger.info("=" * 60)
        logger.info("开始初始化JIT系统")
        logger.info("=" * 60)
        
        # 1. 加载JIT配置
        try:
            from backtest.jit_config_manager import jit_config_manager
            
            config_loaded = jit_config_manager.load_config()
            if config_loaded:
                logger.info("JIT配置文件加载成功")
                
                # 获取全局配置
                global_config = jit_config_manager.get_global_config()
                jit_enabled = global_config.get('enabled', True)
                
                logger.info(f"JIT优化配置: {'启用' if jit_enabled else '禁用'}")
                logger.info(f"缓存配置: {'启用' if global_config.get('cache_enabled', True) else '禁用'}")
                logger.info(f"快速数学运算: {'启用' if global_config.get('fastmath_enabled', True) else '禁用'}")
                logger.info(f"并行计算: {'启用' if global_config.get('parallel_enabled', False) else '禁用'}")
            else:
                logger.warning("JIT配置文件加载失败，使用默认配置")
        except Exception as e:
            logger.warning(f"加载JIT配置失败: {e}")
        
        # 2. 初始化AutoJIT系统
        try:
            from backtest.auto_jit_decorator import (
                auto_jit_instance,
                enable_auto_jit,
                disable_auto_jit,
                is_auto_jit_enabled
            )
            
            # 根据配置设置AutoJIT状态
            autojit_enabled = True  # 默认启用
            try:
                autojit_enabled = jit_config_manager.is_jit_enabled()
            except:
                pass
            
            if autojit_enabled:
                enable_auto_jit()
                logger.info("AutoJIT系统已启用")
            else:
                disable_auto_jit()
                logger.info("AutoJIT系统已禁用")
            
            # 获取AutoJIT摘要
            summary = auto_jit_instance.get_summary()
            logger.info(f"AutoJIT系统摘要: {summary}")
            
        except Exception as e:
            logger.warning(f"初始化AutoJIT系统失败: {e}")
        
        # 3. 初始化JIT优化器
        try:
            from backtest.jit_optimizer import jit_optimizer
            
            # 根据配置设置JIT优化器状态
            jit_optimizer_enabled = True  # 默认启用
            try:
                jit_optimizer_enabled = jit_config_manager.is_jit_enabled()
            except:
                pass
            
            if jit_optimizer_enabled:
                jit_optimizer.enable()
                logger.info("JIT优化器已启用")
            else:
                jit_optimizer.disable()
                logger.info("JIT优化器已禁用")
            
            # 获取JIT优化器统计
            stats = jit_optimizer.get_stats()
            logger.info(f"JIT优化器统计: 编译函数数={stats['compile_count']}, 编译时间={stats['compile_time']:.2f}s")
            
        except Exception as e:
            logger.warning(f"初始化JIT优化器失败: {e}")
        
        # 4. 自动发现并注册函数
        try:
            if jit_config_manager.is_auto_discovery_enabled():
                logger.info("开始自动发现JIT函数...")
                
                auto_discovery_modules = jit_config_manager.get_auto_discovery_modules()
                
                for module_config in auto_discovery_modules:
                    if module_config.get('enabled', False):
                        module_name = module_config.get('name')
                        pattern = module_config.get('pattern', 'calculate_')
                        description = module_config.get('description', module_name)
                        
                        try:
                            registered = jit_optimizer.auto_discover_and_register(module_name, pattern)
                            if registered:
                                logger.info(f"自动发现模块 {description} ({module_name}): 注册了 {len(registered)} 个函数")
                        except Exception as e:
                            logger.warning(f"自动发现模块 {module_name} 失败: {e}")
            else:
                logger.info("自动发现功能已禁用")
            
        except Exception as e:
            logger.warning(f"自动发现JIT函数失败: {e}")
        
        # 5. 导入AutoJIT函数到JIT优化器
        try:
            imported_count = jit_optimizer.import_from_auto_jit()
            if imported_count > 0:
                logger.info(f"从AutoJIT系统导入了 {imported_count} 个函数到JIT优化器")
        except Exception as e:
            logger.warning(f"导入AutoJIT函数到JIT优化器失败: {e}")
        
        # 6. 显示最终状态
        logger.info("=" * 60)
        logger.info("JIT系统初始化完成")
        logger.info("=" * 60)
        
        # 显示JIT使用情况
        try:
            jit_usage = jit_optimizer.get_jit_usage()
            logger.info(f"JIT函数总数: {len(jit_usage['functions'])}")
            logger.info(f"JIT函数列表: {list(jit_usage['function_names'].values())}")
        except Exception as e:
            logger.warning(f"获取JIT使用情况失败: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"JIT系统初始化失败: {e}")
        return False


def get_jit_system_status():
    """获取JIT系统状态
    
    Returns:
        Dict[str, Any]: JIT系统状态信息
    """
    status = {
        'autojit_enabled': False,
        'jit_optimizer_enabled': False,
        'autojit_functions': 0,
        'jit_optimizer_functions': 0,
        'config_loaded': False
    }
    
    try:
        # AutoJIT状态
        from backtest.auto_jit_decorator import is_auto_jit_enabled, get_auto_jit_summary
        status['autojit_enabled'] = is_auto_jit_enabled()
        summary = get_auto_jit_summary()
        status['autojit_functions'] = summary.get('total_functions', 0)
    except:
        pass
    
    try:
        # JIT优化器状态
        from backtest.jit_optimizer import jit_optimizer
        status['jit_optimizer_enabled'] = jit_optimizer.is_enabled()
        stats = jit_optimizer.get_stats()
        status['jit_optimizer_functions'] = stats.get('compile_count', 0)
    except:
        pass
    
    try:
        # 配置状态
        from backtest.jit_config_manager import jit_config_manager
        status['config_loaded'] = jit_config_manager.load_config()
    except:
        pass
    
    return status


# 自动初始化（当模块被导入时）
if __name__ != "__main__":
    initialize_jit_system()
