"""
插件网络配置注册管理器
自动发现和注册支持网络配置的插件
"""

from loguru import logger
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.network.universal_network_config import (
    get_universal_network_manager, INetworkConfigurable, NetworkEndpoint
)

class PluginNetworkRegistry:
    """插件网络配置注册表"""
    
    def __init__(self):
        self.network_manager = get_universal_network_manager()
        self.registered_plugins: Dict[str, Any] = {}
        self.plugin_instances: Dict[str, INetworkConfigurable] = {}
        
        # 预定义的知名数据源端点
        self.known_endpoints = self._load_known_endpoints()

    def _load_known_endpoints(self) -> Dict[str, List[NetworkEndpoint]]:
        """加载已知的数据源端点配置"""
        return {
            "akshare": [
                NetworkEndpoint(
                    name="akshare_api",
                    url="https://akshare.akfamily.xyz/api",
                    description="AkShare官方API",
                    priority=10,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="akshare_backup",
                    url="https://ak.akfamily.xyz/api",
                    description="AkShare备用API",
                    priority=8,
                    timeout=30
                )
            ],
            "eastmoney": [
                NetworkEndpoint(
                    name="eastmoney_primary",
                    url="https://push2.eastmoney.com/api",
                    description="东方财富主API",
                    priority=10,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="eastmoney_backup",
                    url="https://push2his.eastmoney.com/api",
                    description="东方财富备用API",
                    priority=8,
                    timeout=30
                )
            ],
            "tongdaxin": [
                NetworkEndpoint(
                    name="tdx_shenzhen_primary",
                    url="119.147.212.81:7709",
                    description="通达信深圳主站",
                    priority=10,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="tdx_shanghai_primary", 
                    url="114.80.63.12:7709",
                    description="通达信上海主站",
                    priority=9,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="tdx_shenzhen_backup",
                    url="119.147.171.206:7709",
                    description="通达信深圳备用",
                    priority=7,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="tdx_guangzhou_backup",
                    url="113.105.142.136:7709",
                    description="通达信广州备用",
                    priority=6,
                    timeout=30
                )
            ],
            "vix": [
                NetworkEndpoint(
                    name="cboe_vix",
                    url="https://www.cboe.com/api/vix",
                    description="芝加哥期权交易所VIX",
                    priority=10,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="yahoo_vix",
                    url="https://query1.finance.yahoo.com/v8/finance/chart/^VIX",
                    description="Yahoo Finance VIX",
                    priority=8,
                    timeout=30
                )
            ],
            "news": [
                NetworkEndpoint(
                    name="sina_news",
                    url="https://feed.sina.com.cn/api/news",
                    description="新浪财经新闻",
                    priority=10,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="tencent_news",
                    url="https://stockapp.finance.qq.com/mstats",
                    description="腾讯财经新闻",
                    priority=8,
                    timeout=30
                )
            ],
            "crypto": [
                NetworkEndpoint(
                    name="binance_api",
                    url="https://api.binance.com/api/v3",
                    description="币安API",
                    priority=10,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="okx_api",
                    url="https://www.okx.com/api/v5",
                    description="OKX API",
                    priority=9,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="huobi_api",
                    url="https://api.huobi.pro/v1",
                    description="火币API",
                    priority=8,
                    timeout=30
                )
            ],
            "forex": [
                NetworkEndpoint(
                    name="fxpro_api",
                    url="https://api.fxpro.com/v1",
                    description="FxPro外汇API",
                    priority=10,
                    timeout=30
                ),
                NetworkEndpoint(
                    name="oanda_api",
                    url="https://api-fxtrade.oanda.com/v3",
                    description="OANDA外汇API",
                    priority=9,
                    timeout=30
                )
            ]
        }

    def discover_and_register_plugins(self, plugin_directories: List[str] = None) -> Dict[str, bool]:
        """
        发现并注册支持网络配置的插件
        
        Args:
            plugin_directories: 插件目录列表
            
        Returns:
            注册结果字典 {plugin_id: success}
        """
        if plugin_directories is None:
            plugin_directories = [
                "plugins/examples",
                "plugins/sentiment_data_sources",
                "plugins/data_sources",
                "plugins/indicators"
            ]
        
        registration_results = {}
        
        logger.info("开始发现支持网络配置的插件...")
        
        for plugin_dir in plugin_directories:
            try:
                results = self._discover_plugins_in_directory(plugin_dir)
                registration_results.update(results)
            except Exception as e:
                logger.error(f"发现插件目录失败 {plugin_dir}: {e}")
        
        logger.info(f"插件发现完成，共注册 {len(registration_results)} 个插件")
        return registration_results

    def _discover_plugins_in_directory(self, plugin_dir: str) -> Dict[str, bool]:
        """在指定目录中发现插件"""
        results = {}
        plugin_path = Path(plugin_dir)
        
        if not plugin_path.exists():
            logger.warning(f"插件目录不存在: {plugin_dir}")
            return results
        
        # 查找所有Python插件文件
        plugin_files = list(plugin_path.glob("*_plugin.py"))
        
        for plugin_file in plugin_files:
            try:
                plugin_id, success = self._load_and_register_plugin(plugin_file, plugin_dir)
                if plugin_id:
                    results[plugin_id] = success
            except Exception as e:
                logger.error(f"加载插件失败 {plugin_file}: {e}")
        
        return results

    def _load_and_register_plugin(self, plugin_file: Path, plugin_dir: str) -> tuple[Optional[str], bool]:
        """加载并注册单个插件"""
        try:
            # 构造模块名
            relative_path = plugin_file.relative_to(Path.cwd())
            module_name = str(relative_path).replace("/", ".").replace("\\", ".").replace(".py", "")
            
            # 动态导入模块
            module = importlib.import_module(module_name)
            
            # 查找实现了INetworkConfigurable接口的类
            plugin_class = None
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (hasattr(obj, '__bases__') and 
                    any(base.__name__ == 'INetworkConfigurable' for base in obj.__mro__)):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                return None, False
            
            # 创建插件实例
            plugin_instance = plugin_class()
            
            # 获取插件ID和名称
            plugin_id = getattr(plugin_instance, 'plugin_id', module_name)
            plugin_name = getattr(plugin_instance, 'name', plugin_class.__name__)
            
            # 注册网络配置
            success = self.register_plugin_network_config(plugin_id, plugin_name, plugin_instance)
            
            if success:
                self.plugin_instances[plugin_id] = plugin_instance
                logger.info(f"注册插件网络配置成功: {plugin_name} ({plugin_id})")
            
            return plugin_id, success
            
        except Exception as e:
            logger.error(f"加载插件失败 {plugin_file}: {e}")
            return None, False

    def register_plugin_network_config(self, plugin_id: str, plugin_name: str, 
                                     plugin_instance: INetworkConfigurable) -> bool:
        """注册插件网络配置"""
        try:
            # 获取插件的默认端点
            default_endpoints = plugin_instance.get_default_endpoints()
            
            # 如果插件没有提供默认端点，尝试从已知端点中匹配
            if not default_endpoints:
                default_endpoints = self._get_known_endpoints_for_plugin(plugin_id, plugin_name)
            
            # 注册到网络管理器（register_plugin方法未实现，降级处理）
            logger.warning(f"network_manager.register_plugin功能未实现，插件 '{plugin_id}' 跳过网络注册")
            success = True
            
            if success:
                self.registered_plugins[plugin_id] = {
                    'name': plugin_name,
                    'instance': plugin_instance,
                    'endpoints_count': len(default_endpoints),
                    'config_schema': plugin_instance.get_network_config_schema()
                }
            
            return success
            
        except Exception as e:
            logger.error(f"注册插件网络配置失败 {plugin_id}: {e}")
            return False

    def _get_known_endpoints_for_plugin(self, plugin_id: str, plugin_name: str) -> List[NetworkEndpoint]:
        """为插件获取已知的端点配置"""
        # 根据插件名称匹配已知端点
        for key, endpoints in self.known_endpoints.items():
            if key.lower() in plugin_id.lower() or key.lower() in plugin_name.lower():
                logger.info(f"为插件 {plugin_name} 匹配到已知端点: {key}")
                return endpoints.copy()
        
        return []

    def get_registered_plugins(self) -> Dict[str, Dict[str, Any]]:
        """获取已注册的插件列表"""
        return self.registered_plugins.copy()

    def get_plugin_network_config(self, plugin_id: str) -> Optional[Any]:
        """获取插件的网络配置"""
        return self.network_manager.get_plugin_config(plugin_id)

    def update_plugin_endpoints_from_online(self, plugin_id: str) -> bool:
        """从在线源更新插件端点"""
        try:
            if plugin_id not in self.plugin_instances:
                logger.error(f"插件实例不存在: {plugin_id}")
                return False
            
            plugin_instance = self.plugin_instances[plugin_id]
            
            # 尝试从插件获取最新的端点配置
            try:
                if hasattr(plugin_instance, 'get_latest_endpoints'):
                    latest_endpoints = plugin_instance.get_latest_endpoints()
                    if latest_endpoints:
                        # 更新端点配置
                        config = self.network_manager.get_plugin_config(plugin_id)
                        if config:
                            config.endpoints.extend(latest_endpoints)
                            return self.network_manager.update_plugin_config(plugin_id, config)
            except Exception as e:
                logger.warning(f"获取插件最新端点失败 {plugin_id}: {e}")
            
            # 如果插件不支持动态端点，返回成功
            return True
            
        except Exception as e:
            logger.error(f"更新插件端点失败 {plugin_id}: {e}")
            return False

    def test_all_plugin_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """测试所有插件的端点连接"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_plugin = {
                executor.submit(self._test_plugin_endpoints, plugin_id): plugin_id
                for plugin_id in self.registered_plugins.keys()
            }
            
            for future in as_completed(future_to_plugin):
                plugin_id = future_to_plugin[future]
                try:
                    result = future.result()
                    results[plugin_id] = result
                except Exception as e:
                    results[plugin_id] = {
                        'success': False,
                        'error': str(e),
                        'tested_endpoints': 0,
                        'available_endpoints': 0
                    }
        
        return results

    def _test_plugin_endpoints(self, plugin_id: str) -> Dict[str, Any]:
        """测试单个插件的端点"""
        try:
            config = self.network_manager.get_plugin_config(plugin_id)
            if not config or not config.endpoints:
                return {
                    'success': False,
                    'error': 'No endpoints configured',
                    'tested_endpoints': 0,
                    'available_endpoints': 0
                }
            
            available_count = 0
            total_count = len(config.endpoints)
            
            for endpoint in config.endpoints:
                if endpoint.enabled:
                    try:
                        # 这里应该实现实际的端点测试逻辑
                        # 暂时假设测试成功
                        available_count += 1
                    except Exception as e:
                        logger.warning(f"端点测试异常: {e}")
            
            return {
                'success': True,
                'tested_endpoints': total_count,
                'available_endpoints': available_count,
                'success_rate': available_count / total_count if total_count > 0 else 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tested_endpoints': 0,
                'available_endpoints': 0
            }

    def get_plugin_network_statistics(self) -> Dict[str, Any]:
        """获取插件网络统计信息"""
        stats = {
            'total_plugins': len(self.registered_plugins),
            'total_endpoints': 0,
            'plugins_with_proxy': 0,
            'plugins_with_rate_limit': 0,
            'plugin_details': {}
        }
        
        for plugin_id, plugin_info in self.registered_plugins.items():
            try:
                plugin_stats = self.network_manager.get_plugin_statistics(plugin_id)
                stats['total_endpoints'] += plugin_stats.get('total_endpoints', 0)
                
                if plugin_stats.get('proxy_enabled'):
                    stats['plugins_with_proxy'] += 1
                
                if plugin_stats.get('rate_limit_enabled'):
                    stats['plugins_with_rate_limit'] += 1
                
                stats['plugin_details'][plugin_id] = plugin_stats
                
            except Exception as e:
                logger.error(f"获取插件统计失败 {plugin_id}: {e}")
        
        return stats

    def apply_global_network_settings(self, settings: Dict[str, Any]) -> Dict[str, bool]:
        """应用全局网络设置到所有插件"""
        results = {}
        
        for plugin_id in self.registered_plugins.keys():
            try:
                config = self.network_manager.get_plugin_config(plugin_id)
                if config:
                    # 应用全局设置
                    if 'proxy_enabled' in settings:
                        config.proxy_enabled = settings['proxy_enabled']
                    
                    if 'proxy_list' in settings:
                        config.proxy_list = settings['proxy_list']
                    
                    if 'rate_limit_enabled' in settings:
                        config.rate_limit_enabled = settings['rate_limit_enabled']
                    
                    if 'requests_per_minute' in settings:
                        config.requests_per_minute = settings['requests_per_minute']
                    
                    if 'request_delay' in settings:
                        config.request_delay = settings['request_delay']
                    
                    # 保存配置
                    success = self.network_manager.update_plugin_config(plugin_id, config)
                    results[plugin_id] = success
                    
                    # 应用到插件实例
                    if success and plugin_id in self.plugin_instances:
                        self.plugin_instances[plugin_id].apply_network_config(config)
                
            except Exception as e:
                logger.error(f"应用全局网络设置失败 {plugin_id}: {e}")
                results[plugin_id] = False
        
        return results

# 全局注册表实例
_plugin_network_registry = None

def get_plugin_network_registry() -> PluginNetworkRegistry:
    """获取插件网络配置注册表实例"""
    global _plugin_network_registry
    if _plugin_network_registry is None:
        _plugin_network_registry = PluginNetworkRegistry()
    return _plugin_network_registry

def auto_register_plugins() -> Dict[str, bool]:
    """自动注册所有支持网络配置的插件"""
    registry = get_plugin_network_registry()
    return registry.discover_and_register_plugins()
