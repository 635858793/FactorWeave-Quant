"""
插件网络配置自动注册器
在应用启动时自动注册所有支持网络配置的插件
"""

from loguru import logger
import asyncio
from typing import Dict, Any, List
from pathlib import Path

from core.network.plugin_network_registry import get_plugin_network_registry, auto_register_plugins

class PluginAutoRegister:
    """插件自动注册器"""
    
    def __init__(self):
        self.registry = get_plugin_network_registry()
        self.registration_results: Dict[str, bool] = {}
        self.initialized = False

    def register_all_plugins(self) -> Dict[str, bool]:
        """注册所有支持网络配置的插件"""
        try:
            logger.info("开始自动注册插件网络配置...")
            
            # 执行自动注册
            self.registration_results = auto_register_plugins()
            
            # 记录注册结果
            success_count = sum(1 for success in self.registration_results.values() if success)
            total_count = len(self.registration_results)
            
            logger.info(f"插件网络配置注册完成: {success_count}/{total_count} 成功")
            
            # 显示详细结果
            for plugin_id, success in self.registration_results.items():
                if success:
                    logger.info(f"✓ {plugin_id}: 注册成功")
                else:
                    logger.warning(f"✗ {plugin_id}: 注册失败")
            
            self.initialized = True
            return self.registration_results
            
        except Exception as e:
            logger.error(f"自动注册插件失败: {e}")
            return {}

    async def register_all_plugins_async(self) -> Dict[str, bool]:
        """异步注册所有插件"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.register_all_plugins)

    def get_registration_status(self) -> Dict[str, Any]:
        """获取注册状态信息"""
        if not self.initialized:
            return {
                'status': 'not_initialized',
                'total_plugins': 0,
                'successful_registrations': 0,
                'failed_registrations': 0,
                'details': {}
            }
        
        successful = sum(1 for success in self.registration_results.values() if success)
        failed = len(self.registration_results) - successful
        
        return {
            'status': 'initialized',
            'total_plugins': len(self.registration_results),
            'successful_registrations': successful,
            'failed_registrations': failed,
            'success_rate': successful / len(self.registration_results) if self.registration_results else 0,
            'details': self.registration_results.copy()
        }

    def get_registered_plugins_info(self) -> List[Dict[str, Any]]:
        """获取已注册插件的详细信息"""
        registered_plugins = self.registry.get_registered_plugins()
        plugins_info = []
        
        for plugin_id, plugin_data in registered_plugins.items():
            try:
                # 获取网络统计
                stats = self.registry.network_manager.get_plugin_statistics(plugin_id)
                
                plugin_info = {
                    'plugin_id': plugin_id,
                    'plugin_name': plugin_data['name'],
                    'endpoints_count': plugin_data['endpoints_count'],
                    'total_requests': stats.get('total_requests', 0),
                    'success_rate': stats.get('success_rate', 0),
                    'proxy_enabled': stats.get('proxy_enabled', False),
                    'rate_limit_enabled': stats.get('rate_limit_enabled', True),
                    'avg_response_time': stats.get('avg_response_time', 0),
                    'enabled_endpoints': stats.get('enabled_endpoints', 0),
                    'total_endpoints': stats.get('total_endpoints', 0)
                }
                plugins_info.append(plugin_info)
                
            except Exception as e:
                logger.error(f"获取插件信息失败 {plugin_id}: {e}")
        
        return plugins_info

    def refresh_plugin_endpoints(self, plugin_id: str = None) -> Dict[str, bool]:
        """刷新插件端点配置"""
        try:
            if plugin_id:
                # 刷新指定插件
                success = self.registry.update_plugin_endpoints_from_online(plugin_id)
                return {plugin_id: success}
            else:
                # 刷新所有插件
                results = {}
                registered_plugins = self.registry.get_registered_plugins()
                
                for pid in registered_plugins.keys():
                    success = self.registry.update_plugin_endpoints_from_online(pid)
                    results[pid] = success
                
                return results
                
        except Exception as e:
            logger.error(f"刷新插件端点失败: {e}")
            return {}

    def apply_global_network_settings(self, settings: Dict[str, Any]) -> Dict[str, bool]:
        """应用全局网络设置"""
        try:
            logger.info("应用全局网络设置...")
            results = self.registry.apply_global_network_settings(settings)
            
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            logger.info(f"全局设置应用完成: {success_count}/{total_count} 成功")
            return results
            
        except Exception as e:
            logger.error(f"应用全局网络设置失败: {e}")
            return {}

    def test_all_plugin_connections(self) -> Dict[str, Dict[str, Any]]:
        """测试所有插件的网络连接"""
        try:
            logger.info("开始测试所有插件网络连接...")
            results = self.registry.test_all_plugin_endpoints()
            
            # 统计测试结果
            total_plugins = len(results)
            successful_plugins = sum(1 for result in results.values() if result.get('success', False))
            
            logger.info(f"网络连接测试完成: {successful_plugins}/{total_plugins} 插件连接正常")
            
            return results
            
        except Exception as e:
            logger.error(f"测试插件网络连接失败: {e}")
            return {}

    def get_plugin_network_summary(self) -> Dict[str, Any]:
        """获取插件网络配置摘要"""
        try:
            stats = self.registry.get_plugin_network_statistics()
            registration_status = self.get_registration_status()
            
            summary = {
                'registration': registration_status,
                'network_stats': stats,
                'recommendations': self._generate_recommendations(stats, registration_status)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"获取插件网络摘要失败: {e}")
            return {}

    def _generate_recommendations(self, stats: Dict[str, Any], 
                                registration_status: Dict[str, Any]) -> List[str]:
        """生成网络配置建议"""
        recommendations = []
        
        try:
            # 检查注册状态
            if registration_status['failed_registrations'] > 0:
                recommendations.append(
                    f"发现 {registration_status['failed_registrations']} 个插件注册失败，建议检查插件配置"
                )
            
            # 检查代理使用
            if stats['plugins_with_proxy'] == 0 and stats['total_plugins'] > 0:
                recommendations.append("建议为需要频繁请求的插件配置代理，避免IP被封")
            
            # 检查频率限制
            if stats['plugins_with_rate_limit'] < stats['total_plugins']:
                recommendations.append("建议为所有插件启用频率限制，避免请求过于频繁")
            
            # 检查端点数量
            avg_endpoints = stats['total_endpoints'] / max(stats['total_plugins'], 1)
            if avg_endpoints < 2:
                recommendations.append("建议为插件配置多个备用端点，提高可用性")
            
            if not recommendations:
                recommendations.append("网络配置良好，无需特别调整")
            
        except Exception as e:
            logger.error(f"生成建议失败: {e}")
            recommendations.append("无法生成配置建议")
        
        return recommendations

# 全局自动注册器实例
_plugin_auto_register = None

def get_plugin_auto_register() -> PluginAutoRegister:
    """获取插件自动注册器实例"""
    global _plugin_auto_register
    if _plugin_auto_register is None:
        _plugin_auto_register = PluginAutoRegister()
    return _plugin_auto_register

def initialize_plugin_network_configs() -> Dict[str, bool]:
    """初始化所有插件的网络配置"""
    auto_register = get_plugin_auto_register()
    return auto_register.register_all_plugins()

async def initialize_plugin_network_configs_async() -> Dict[str, bool]:
    """异步初始化所有插件的网络配置"""
    auto_register = get_plugin_auto_register()
    return await auto_register.register_all_plugins_async()

def get_network_config_summary() -> Dict[str, Any]:
    """获取网络配置摘要信息"""
    auto_register = get_plugin_auto_register()
    return auto_register.get_plugin_network_summary()
