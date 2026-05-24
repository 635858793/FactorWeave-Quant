"""
Core configuration module that re-exports the unified ConfigManager
"""

from loguru import logger
from typing import Dict, Any, Optional
import os
import json
from datetime import datetime
from utils import (
    Theme,
    ConfigManager,
    ThemeConfig,
    TradingConfig,
    DataConfig,
    LoggingConfig
)

__all__ = [
    'ConfigManager',
    'ThemeConfig',
    'TradingConfig',
    'DataConfig',
    'LoggingConfig',
    'Theme',
    'config_manager',
    'lazy_config_manager',
    'get_config_manager',
    'validate_config',
    'migrate_config',
    'backup_config',
    'restore_config'
]

def validate_config(config: Dict[str, Any]) -> bool:
    """验证配置是否有效

    Args:
        config: 配置字典

    Returns:
        配置是否有效
    """
    try:
        # 验证版本信息
        if 'version' not in config:
            logger.error("配置缺少版本信息")
            return False

        # 验证必需的配置部分
        required_sections = {
            'theme': ThemeConfig,
            'trading': TradingConfig,
            'data': DataConfig
            # 移除复杂的logging配置验证，Loguru由代码直接管理
        }

        for section, config_class in required_sections.items():
            if section not in config:
                logger.error(f"缺少必需的配置部分: {section}")
                return False

            try:
                # 尝试创建配置对象来验证数据
                config_class(**config[section])
            except Exception as e:
                logger.error(f"配置部分 {section} 验证失败: {str(e)}")
                return False

        # 验证交易配置
        if 'trading' in config:
            trading_config = config['trading']
            if trading_config.get('commission_rate', 0) < 0:
                logger.error("佣金率不能为负数")
                return False
            if trading_config.get('initial_cash', 0) <= 0:
                logger.error("初始资金必须大于0")
                return False
            if not 0 <= trading_config.get('position_ratio', 0) <= 1:
                logger.error("仓位比例必须在0到1之间")
                return False

        return True

    except Exception as e:
        logger.error(f"配置验证失败: {str(e)}")
        return False

def migrate_config(config: Dict[str, Any], current_version: str) -> Dict[str, Any]:
    """迁移配置到最新版本

    Args:
        config: 当前配置
        current_version: 当前配置版本

    Returns:
        迁移后的配置
    """
    try:
        # 如果没有版本信息，假定为最早的版本
        if 'version' not in config:
            config['version'] = '1.0.0'

        # 根据版本执行迁移
        if config['version'] == '1.0.0':
            config['version'] = '1.1.0'
            logger.info("配置已迁移到版本 1.1.0")

        if config['version'] == '1.1.0':
            # 迁移到 1.2.0
            if 'ui' not in config:
                config['ui'] = {'theme': 'default', 'language': 'zh_CN'}
            # 移除logging配置，由Loguru直接管理
            # if 'logging' not in config:
            #     config['logging'] = LoggingConfig().to_dict()
            # 更新交易配置
            if 'trading' in config:
                trading = config['trading']
                if 'stop_loss' not in trading:
                    trading['stop_loss'] = 0.05
                if 'trailing_stop' not in trading:
                    trading['trailing_stop'] = 0.1
                if 'time_stop' not in trading:
                    trading['time_stop'] = 5
            config['version'] = '1.2.0'
            logger.info("配置已迁移到版本 1.2.0")

        if config['version'] == '1.2.0':
            # 迁移到 1.3.0
            if 'performance' in config:
                perf = config['performance']
                if 'track_time' not in perf:
                    perf['track_time'] = True
                if 'track_memory' not in perf:
                    perf['track_memory'] = True
                if 'track_cpu' not in perf:
                    perf['track_cpu'] = True
                if 'track_exceptions' not in perf:
                    perf['track_exceptions'] = True
            config['version'] = '1.3.0'
            logger.info("配置已迁移到版本 1.3.0")

        return config

    except Exception as e:
        logger.error(f"配置迁移失败: {str(e)}")
        return config

def backup_config(config_manager: ConfigManager, backup_dir: str = "backups") -> Optional[str]:
    """备份当前配置

    Args:
        config_manager: 配置管理器实例
        backup_dir: 备份目录

    Returns:
        备份文件路径，如果备份失败则返回 None
    """
    try:
        # 确保备份目录存在
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # 创建备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(
            backup_dir, f"config_backup_{timestamp}.json")

        # 保存当前配置
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(config_manager.get_all(), f,
                      indent=2, ensure_ascii=False)

        logger.info(f"配置已备份到: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"配置备份失败: {str(e)}")
        return None

def restore_config(config_manager: ConfigManager, backup_path: str) -> bool:
    """从备份恢复配置

    Args:
        config_manager: 配置管理器实例
        backup_path: 备份文件路径

    Returns:
        是否恢复成功
    """
    try:
        # 读取备份文件
        with open(backup_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 验证配置
        if not validate_config(config):
            logger.error("备份配置验证失败")
            return False

        # 迁移配置到最新版本
        config = migrate_config(config, config.get('version', '1.0.0'))

        # 更新配置：通过 set() 逐项持久化
        for key, value in config.items():
            config_manager.set(key, value)

        logger.info(f"配置已从备份恢复: {backup_path}")
        return True

    except Exception as e:
        logger.error(f"恢复配置失败: {str(e)}")
        return False

# 创建全局配置管理器实例
config_manager = ConfigManager()

_config_initialized = False
_config_initialization_lock = None

def _ensure_config_initialized():
    """确保配置已初始化，延迟执行避免循环依赖"""
    global _config_initialized, _config_initialization_lock
    if _config_initialized:
        return
    
    import threading
    if _config_initialization_lock is None:
        _config_initialization_lock = threading.Lock()
    
    with _config_initialization_lock:
        if _config_initialized:
            return
        
        # 验证和迁移配置
        if not validate_config(config_manager.get_all()):
            logger.warning("配置验证失败，使用默认配置")
            default_config = {
                'version': '1.3.0',
                'theme': ThemeConfig().to_dict(),
                'trading': TradingConfig().to_dict(),
                'data': DataConfig().to_dict(),
                'ui': {'theme': 'default', 'language': 'zh_CN'}
            }
            for key, value in default_config.items():
                config_manager.set(key, value)
        else:
            migrated_config = migrate_config(
                config_manager.get_all(), config_manager.get('version', '1.0.0'))
            for key, value in migrated_config.items():
                config_manager.set(key, value)
        
        _config_initialized = True


def get_config_manager():
    """获取配置管理器，确保已初始化"""
    _ensure_config_initialized()
    return config_manager


class LazyConfigManager:
    """懒加载配置管理器代理"""
    
    def __getattr__(self, name):
        _ensure_config_initialized()
        return getattr(config_manager, name)


# 使用懒加载代理替代全局config_manager
lazy_config_manager = LazyConfigManager()
