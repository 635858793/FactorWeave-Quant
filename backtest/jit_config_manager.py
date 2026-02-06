"""
JIT配置管理器
用于加载和管理JIT配置文件
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class JITConfigManager:
    """JIT配置管理器
    
    负责加载和管理JIT配置文件
    支持热更新配置
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为config/jit_config.yaml
        """
        if config_path is None:
            config_path = "config/jit_config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._last_modified = 0
        
        # 加载配置
        self.load_config()
    
    def load_config(self) -> bool:
        """加载配置文件
        
        Returns:
            bool: 是否成功加载
        """
        try:
            if not self.config_path.exists():
                logger.warning(f"配置文件不存在: {self.config_path}")
                self._config = self._get_default_config()
                return False
            
            # 检查文件是否被修改
            current_modified = self.config_path.stat().st_mtime
            if current_modified == self._last_modified:
                return True
            
            # 加载配置
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            
            self._last_modified = current_modified
            logger.info(f"已加载JIT配置文件: {self.config_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()
            return False
    
    def reload_config(self) -> bool:
        """重新加载配置文件
        
        Returns:
            bool: 是否成功重新加载
        """
        logger.info("重新加载JIT配置...")
        return self.load_config()
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置
        
        Returns:
            Dict[str, Any]: 完整的配置字典
        """
        return self._config.copy()
    
    def get_global_config(self) -> Dict[str, Any]:
        """获取全局配置
        
        Returns:
            Dict[str, Any]: 全局配置字典
        """
        return self._config.get('global', {})
    
    def get_functions_config(self) -> List[Dict[str, Any]]:
        """获取函数配置列表
        
        Returns:
            List[Dict[str, Any]]: 函数配置列表
        """
        return self._config.get('functions', [])
    
    def get_function_config(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定函数的配置
        
        Args:
            name: 函数名称
        
        Returns:
            Optional[Dict[str, Any]]: 函数配置，如果不存在则返回None
        """
        functions = self.get_functions_config()
        for func_config in functions:
            if func_config.get('name') == name:
                return func_config
        return None
    
    def get_enabled_functions(self) -> List[Dict[str, Any]]:
        """获取启用的函数配置列表
        
        Returns:
            List[Dict[str, Any]]: 启用的函数配置列表
        """
        functions = self.get_functions_config()
        return [func for func in functions if func.get('enabled', False)]
    
    def get_auto_discovery_config(self) -> Dict[str, Any]:
        """获取自动发现配置
        
        Returns:
            Dict[str, Any]: 自动发现配置字典
        """
        return self._config.get('auto_discovery', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """获取性能监控配置
        
        Returns:
            Dict[str, Any]: 性能监控配置字典
        """
        return self._config.get('monitoring', {})
    
    def get_cache_management_config(self) -> Dict[str, Any]:
        """获取缓存管理配置
        
        Returns:
            Dict[str, Any]: 缓存管理配置字典
        """
        return self._config.get('cache_management', {})
    
    def is_jit_enabled(self) -> bool:
        """检查JIT是否启用
        
        Returns:
            bool: JIT是否启用
        """
        global_config = self.get_global_config()
        return global_config.get('enabled', True)
    
    def is_cache_enabled(self) -> bool:
        """检查缓存是否启用
        
        Returns:
            bool: 缓存是否启用
        """
        global_config = self.get_global_config()
        return global_config.get('cache_enabled', True)
    
    def is_fastmath_enabled(self) -> bool:
        """检查快速数学运算是否启用
        
        Returns:
            bool: 快速数学运算是否启用
        """
        global_config = self.get_global_config()
        return global_config.get('fastmath_enabled', True)
    
    def is_parallel_enabled(self) -> bool:
        """检查并行计算是否启用
        
        Returns:
            bool: 并行计算是否启用
        """
        global_config = self.get_global_config()
        return global_config.get('parallel_enabled', False)
    
    def get_cache_dir(self) -> str:
        """获取缓存目录
        
        Returns:
            str: 缓存目录路径
        """
        global_config = self.get_global_config()
        return global_config.get('cache_dir', 'cache/numba')
    
    def is_auto_discovery_enabled(self) -> bool:
        """检查自动发现是否启用
        
        Returns:
            bool: 自动发现是否启用
        """
        auto_discovery_config = self.get_auto_discovery_config()
        return auto_discovery_config.get('enabled', True)
    
    def get_auto_discovery_modules(self) -> List[Dict[str, Any]]:
        """获取自动发现模块列表
        
        Returns:
            List[Dict[str, Any]]: 自动发现模块列表
        """
        auto_discovery_config = self.get_auto_discovery_config()
        return auto_discovery_config.get('modules', [])
    
    def is_monitoring_enabled(self) -> bool:
        """检查性能监控是否启用
        
        Returns:
            bool: 性能监控是否启用
        """
        monitoring_config = self.get_monitoring_config()
        return monitoring_config.get('enabled', True)
    
    def get_stats_interval(self) -> int:
        """获取性能统计间隔
        
        Returns:
            int: 统计间隔（秒）
        """
        monitoring_config = self.get_monitoring_config()
        return monitoring_config.get('stats_interval', 60)
    
    def is_detailed_logging_enabled(self) -> bool:
        """检查详细日志是否启用
        
        Returns:
            bool: 详细日志是否启用
        """
        monitoring_config = self.get_monitoring_config()
        return monitoring_config.get('detailed_logging', False)
    
    def get_performance_warning_threshold(self) -> float:
        """获取性能警告阈值
        
        Returns:
            float: 性能警告阈值（秒）
        """
        monitoring_config = self.get_monitoring_config()
        return monitoring_config.get('performance_warning_threshold', 1.0)
    
    def is_auto_cleanup_enabled(self) -> bool:
        """检查自动清理缓存是否启用
        
        Returns:
            bool: 自动清理缓存是否启用
        """
        cache_config = self.get_cache_management_config()
        return cache_config.get('auto_cleanup', False)
    
    def get_cleanup_interval(self) -> int:
        """获取缓存清理间隔
        
        Returns:
            int: 清理间隔（天）
        """
        cache_config = self.get_cache_management_config()
        return cache_config.get('cleanup_interval', 7)
    
    def get_max_cache_size(self) -> int:
        """获取最大缓存大小
        
        Returns:
            int: 最大缓存大小（MB）
        """
        cache_config = self.get_cache_management_config()
        return cache_config.get('max_cache_size', 1024)
    
    def is_compress_cache_enabled(self) -> bool:
        """检查缓存压缩是否启用
        
        Returns:
            bool: 缓存压缩是否启用
        """
        cache_config = self.get_cache_management_config()
        return cache_config.get('compress_cache', False)
    
    def update_function_config(self, name: str, updates: Dict[str, Any]) -> bool:
        """更新函数配置
        
        Args:
            name: 函数名称
            updates: 要更新的配置项
        
        Returns:
            bool: 是否成功更新
        """
        try:
            functions = self.get_functions_config()
            
            # 查找并更新函数配置
            for func_config in functions:
                if func_config.get('name') == name:
                    func_config.update(updates)
                    self._config['functions'] = functions
                    
                    # 保存配置
                    self._save_config()
                    return True
            
            logger.warning(f"未找到函数配置: {name}")
            return False
            
        except Exception as e:
            logger.error(f"更新函数配置失败: {e}")
            return False
    
    def _save_config(self) -> bool:
        """保存配置到文件
        
        Returns:
            bool: 是否成功保存
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
            
            self._last_modified = self.config_path.stat().st_mtime
            logger.info(f"已保存JIT配置文件: {self.config_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置
        
        Returns:
            Dict[str, Any]: 默认配置字典
        """
        return {
            'global': {
                'enabled': True,
                'cache_enabled': True,
                'fastmath_enabled': True,
                'parallel_enabled': False,
                'cache_dir': 'cache/numba'
            },
            'functions': [],
            'auto_discovery': {
                'enabled': True,
                'modules': []
            },
            'monitoring': {
                'enabled': True,
                'stats_interval': 60,
                'detailed_logging': False,
                'performance_warning_threshold': 1.0
            },
            'cache_management': {
                'auto_cleanup': False,
                'cleanup_interval': 7,
                'max_cache_size': 1024,
                'compress_cache': False
            }
        }


# 全局配置管理器实例
jit_config_manager = JITConfigManager()
