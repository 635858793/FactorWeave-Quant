"""
应用初始化模块
在应用启动时自动初始化所有必要的组件和配置
"""

from loguru import logger
import asyncio
from typing import Dict, Any, List
from pathlib import Path

from core.network.plugin_auto_register import initialize_plugin_network_configs, get_plugin_auto_register

class AppInitializer:
    """应用初始化器"""
    
    def __init__(self):
        self.initialization_results: Dict[str, Any] = {}
        self.initialized = False

    def initialize_all(self) -> Dict[str, Any]:
        """初始化所有组件"""
        logger.info("开始应用初始化...")

        # 1. 初始化网络配置
        network_results = self._initialize_network_configs()
        self.initialization_results['network_config'] = network_results

        # 2. 初始化数据库
        database_results = self._initialize_databases()
        self.initialization_results['database'] = database_results

        # 3. 初始化其他组件
        other_results = self._initialize_other_components()
        self.initialization_results['other_components'] = other_results

        self.initialized = True

        self._log_initialization_summary()

        return self.initialization_results

    def _initialize_network_configs(self) -> Dict[str, Any]:
        """初始化网络配置"""
        logger.info("初始化插件网络配置...")
        
        try:
            # 自动注册所有支持网络配置的插件
            registration_results = initialize_plugin_network_configs()
            
            # 获取注册统计
            auto_register = get_plugin_auto_register()
            registration_status = auto_register.get_registration_status()
            plugins_info = auto_register.get_registered_plugins_info()
            
            network_results = {
                'status': 'success',
                'registration_results': registration_results,
                'registration_status': registration_status,
                'plugins_info': plugins_info,
                'total_plugins': len(registration_results),
                'successful_plugins': sum(1 for success in registration_results.values() if success),
                'failed_plugins': sum(1 for success in registration_results.values() if not success)
            }
            
            logger.info(f"网络配置初始化完成: {network_results['successful_plugins']}/{network_results['total_plugins']} 插件成功")
            
            return network_results
            
        except Exception as e:
            logger.error(f"网络配置初始化失败: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'total_plugins': 0,
                'successful_plugins': 0,
                'failed_plugins': 0
            }

    def _initialize_databases(self) -> Dict[str, Any]:
        """初始化数据库"""
        logger.info("初始化数据库...")
        
        try:
            # 确保配置目录存在
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            # 确保网络配置目录存在
            network_config_dir = config_dir / "network"
            network_config_dir.mkdir(exist_ok=True)
            
            # 确保数据库目录存在
            db_dir = Path("database")
            db_dir.mkdir(exist_ok=True)
            
            database_results = {
                'status': 'success',
                'config_dir_created': config_dir.exists(),
                'network_config_dir_created': network_config_dir.exists(),
                'database_dir_created': db_dir.exists()
            }
            
            logger.info("数据库初始化完成")
            return database_results
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }

    def _initialize_other_components(self) -> Dict[str, Any]:
        """初始化其他组件并验证其可用性"""
        logger.info("初始化其他组件...")

        components_initialized = []
        components_failed = []
        components_status = {}

        # 1. 日志系统检测
        try:
            logger.debug("日志系统自检")
            components_initialized.append('logging')
            components_status['logging'] = True
        except Exception as e:
            logger.warning(f"日志系统初始化失败: {e}")
            components_failed.append('logging')
            components_status['logging'] = False

        # 2. 配置管理检测
        try:
            from utils.config_manager import ConfigManager
            cfg = ConfigManager()
            test_val = cfg.get('app.name', None)
            components_initialized.append('config_management')
            components_status['config_management'] = True
            logger.debug(f"配置管理已就绪, app.name={test_val}")
        except Exception as e:
            logger.warning(f"配置管理检测失败: {e}")
            components_failed.append('config_management')
            components_status['config_management'] = False

        # 3. 事件总线检测
        try:
            from core.events.event_bus import EventBus, get_event_bus
            bus = get_event_bus()
            stats = bus.get_stats()
            logger.debug(f"事件总线自检通过: handlers={len(bus)}, stats={stats}")
            components_initialized.append('event_bus')
            components_status['event_bus'] = True
        except Exception as e:
            logger.warning(f"事件总线检测失败: {e}")
            components_failed.append('event_bus')
            components_status['event_bus'] = False

        # 4. 数据库连接检测
        try:
            from core.database.unified_sqlite_access import UnifiedSQLiteAccess
            db = UnifiedSQLiteAccess.get_instance()
            if db is not None:
                components_initialized.append('database')
                components_status['database'] = True
            else:
                components_failed.append('database')
                components_status['database'] = False
        except Exception as e:
            logger.warning(f"数据库连接检测失败: {e}")
            components_failed.append('database')
            components_status['database'] = False

        # 5. 插件系统检测
        try:
            from core.plugin_manager import PluginManager
            pm = PluginManager()
            if pm is not None:
                components_initialized.append('plugin_system')
                components_status['plugin_system'] = True
            else:
                components_failed.append('plugin_system')
                components_status['plugin_system'] = False
        except Exception as e:
            logger.warning(f"插件系统检测失败: {e}")
            components_failed.append('plugin_system')
            components_status['plugin_system'] = False

        # 6. 指标服务检测
        try:
            from core.metrics.app_metrics_service import get_app_metrics_service
            svc = get_app_metrics_service()
            if svc is not None and svc.is_enabled():
                components_initialized.append('metrics_service')
                components_status['metrics_service'] = True
            else:
                components_failed.append('metrics_service')
                components_status['metrics_service'] = False
        except Exception as e:
            logger.warning(f"指标服务检测失败: {e}")
            components_failed.append('metrics_service')
            components_status['metrics_service'] = False

        other_results = {
            'status': 'success' if len(components_failed) == 0 else 'partial',
            'components': components_initialized,
            'components_failed': components_failed,
            'components_status': components_status,
            'summary': f'{len(components_initialized)}/{len(components_initialized) + len(components_failed)} 组件可用'
        }

        if components_failed:
            logger.warning(f"部分组件初始化失败: {components_failed}")
        else:
            logger.info(f"所有组件初始化完成: {components_initialized}")

        return other_results

    def _log_initialization_summary(self):
        """记录初始化摘要"""
        try:
            logger.info("=== 应用初始化摘要 ===")
            
            # 网络配置摘要
            network_config = self.initialization_results.get('network_config', {})
            if network_config.get('status') == 'success':
                logger.info(f"✓ 网络配置: {network_config['successful_plugins']}/{network_config['total_plugins']} 插件成功注册")
                
                # 显示注册的插件列表
                for plugin_info in network_config.get('plugins_info', []):
                    plugin_name = plugin_info['plugin_name']
                    endpoints_count = plugin_info['endpoints_count']
                    logger.info(f"  - {plugin_name}: {endpoints_count} 个端点")
            else:
                logger.error(f"✗ 网络配置初始化失败: {network_config.get('error', '未知错误')}")
            
            # 数据库摘要
            database = self.initialization_results.get('database', {})
            if database.get('status') == 'success':
                logger.info("✓ 数据库: 初始化成功")
            else:
                logger.error(f"✗ 数据库初始化失败: {database.get('error', '未知错误')}")
            
            # 其他组件摘要
            other = self.initialization_results.get('other_components', {})
            if other.get('status') == 'success':
                components = ', '.join(other.get('components', []))
                logger.info(f"✓ 其他组件: {components}")
            else:
                logger.error(f"✗ 其他组件初始化失败: {other.get('error', '未知错误')}")
            
            logger.info("=== 初始化完成 ===")
            
        except Exception as e:
            logger.error(f"记录初始化摘要失败: {e}")

    def get_initialization_status(self) -> Dict[str, Any]:
        """获取初始化状态"""
        return {
            'initialized': self.initialized,
            'results': self.initialization_results.copy() if self.initialization_results else {}
        }

    def reinitialize_network_configs(self) -> Dict[str, Any]:
        """重新初始化网络配置"""
        logger.info("重新初始化网络配置...")
        
        try:
            network_results = self._initialize_network_configs()
            self.initialization_results['network_config'] = network_results
            
            logger.info("网络配置重新初始化完成")
            return network_results
            
        except Exception as e:
            logger.error(f"重新初始化网络配置失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }

# 全局初始化器实例
_app_initializer = None

def get_app_initializer() -> AppInitializer:
    """获取应用初始化器实例"""
    global _app_initializer
    if _app_initializer is None:
        _app_initializer = AppInitializer()
    return _app_initializer

def initialize_application() -> Dict[str, Any]:
    """初始化应用"""
    initializer = get_app_initializer()
    return initializer.initialize_all()

def get_app_status() -> Dict[str, Any]:
    """获取应用状态"""
    initializer = get_app_initializer()
    return initializer.get_initialization_status()

def startup_initialization():
    """
    启动时的初始化

    .. deprecated::
        此函数未被项目任何代码调用，属于死代码。
        如需应用启动初始化，请直接调用 initialize_application()。
        计划在后续版本中移除此函数。
    """
    import warnings
    warnings.warn(
        "startup_initialization() is deprecated. Use initialize_application() instead.",
        DeprecationWarning,
        stacklevel=2
    )

    logger.info("开始应用启动初始化...")

    try:
        results = initialize_application()

        if results.get('error'):
            logger.error(f"应用初始化包含错误: {results['error']}")
        else:
            logger.info("应用启动初始化成功完成")

        return results

    except Exception as e:
        logger.error(f"应用启动初始化失败: {e}")
        return {'error': str(e)}
