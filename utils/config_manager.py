"""
Configuration Manager Module

This module provides classes for managing application configuration settings.
现在作为ConfigService的适配器，保持向后兼容性。
"""

import os
import json
import yaml
import time
import threading
from utils.theme_utils import load_theme_json_with_comments
from typing import Any, Dict, Optional, Union
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
from datetime import datetime
from .theme_types import Theme
from .config_types import (
    ThemeConfig,
    ChartConfig,
    TradingConfig,
    DataConfig,
    UIConfig,
    LoggingConfig
)
import traceback
from core.database.unified_sqlite_access import UnifiedSQLiteAccess
from loguru import logger

DB_PATH = os.path.join(os.path.dirname(
    os.path.dirname(__file__)), 'data', 'factorweave_system.sqlite')

class ConfigManager(QObject):
    """
    配置管理器适配器

    为了保持向后兼容性，这个类现在作为ConfigService的适配器。
    所有新的功能都应该直接使用ConfigService。
    """

    def __init__(self, config_service=None):
        super().__init__()
        self._config_service = config_service
        self._container_checked = False

    def _ensure_config_service(self):
        """确保ConfigService可用，延迟导入避免循环依赖"""
        if self._config_service is None and not self._container_checked:
            self._container_checked = True
            try:
                from core.containers import get_service_container
                from core.services.config_service import ConfigService
                container = get_service_container()
                if container:
                    self._config_service = container.resolve(ConfigService)
                    if self._config_service:
                        logger.info("ConfigManager成功获取ConfigService")
                        return
            except Exception as e:
                logger.debug(f"无法获取ConfigService，使用SQLite备用模式: {e}")
            self._init_sqlite_fallback()

    def _init_sqlite_fallback(self):
        """初始化SQLite备用模式"""
        try:
            self.db = UnifiedSQLiteAccess.get_instance(DB_PATH)
            self._ensure_table()
            logger.info("ConfigManager使用SQLite备用模式")
        except Exception as e:
            logger.error(f"SQLite备用模式初始化失败: {e}")
            self.db = None

    def _ensure_table(self):
        """确保配置表存在"""
        if self.db:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)''')

    def get(self, key: str, default=None):
        """获取配置值"""
        if self._config_service is None:
            self._ensure_config_service()
        if self._config_service:
            return self._config_service.get(key, default)
        elif self.db:
            # SQLite备用模式
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM config WHERE key=?', (key,))
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row[0])
                    except Exception:
                        return row[0]
                return default
        else:
            return default

    def set(self, key: str, value):
        """设置配置值"""
        if self._config_service is None:
            self._ensure_config_service()
        if self._config_service:
            return self._config_service.set(key, value)
        elif self.db:
            # SQLite备用模式
            value_str = json.dumps(value, ensure_ascii=False)
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'REPLACE INTO config (key, value) VALUES (?, ?)', (key, value_str))
            return True
        else:
            return False

    def get_all(self):
        """获取所有配置"""
        if self._config_service is None:
            self._ensure_config_service()
        if self._config_service:
            return self._config_service.get_all()
        elif self.db:
            # SQLite备用模式
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, value FROM config')
                rows = cursor.fetchall()
                result = {}
                for k, v in rows:
                    try:
                        result[k] = json.loads(v)
                    except Exception:
                        result[k] = v
                return result
        else:
            return {}

    def delete(self, key: str) -> bool:
        """删除配置项"""
        if self._config_service is None:
            self._ensure_config_service()
        if self._config_service:
            return self._config_service.delete(key) if hasattr(self._config_service, 'delete') else False
        elif self.db:
            # SQLite备用模式
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM config WHERE key=?', (key,))
                return cursor.rowcount > 0
        else:
            return False

    def validate(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """验证配置"""
        if self._config_service:
            return self._config_service.validate(config)
        else:
            return True

    # 兼容性方法别名
    def set_config(self, key: str, value):
        """设置配置值（兼容性方法）"""
        return self.set(key, value)

    def get_config(self, key: str, default=None):
        """获取配置值（兼容性方法）"""
        return self.get(key, default)

    def delete_config(self, key: str) -> bool:
        """删除配置项（兼容性方法）"""
        return self.delete(key)

    @property
    def trading(self):
        """交易配置"""
        return self.get('trading', {})

    @property
    def data(self):
        """数据配置"""
        return self.get('data', {})

    @property
    def theme(self):
        """主题配置"""
        return self.get('theme', {})

    @property
    def chart(self):
        """图表配置"""
        return self.get('chart', {})

    @property
    def logging(self):
        """日志配置"""
        return self.get('logging', {})

    @property
    def ui(self):
        """UI配置"""
        return self.get('ui', {})

    def cleanup(self):
        """清理资源"""
        if self._config_service and hasattr(self._config_service, 'cleanup'):
            self._config_service.cleanup()
        # UnifiedSQLiteAccess 使用单例模式，连接由上下文管理器自动管理，无需手动关闭

    def save(self) -> bool:
        """持久化保存所有配置（set() 已即时持久化，此方法作为显式确认点）"""
        if self._config_service is None:
            self._ensure_config_service()
        if self._config_service:
            if hasattr(self._config_service, 'save'):
                self._config_service.save()
                return True
            else:
                logger.debug("ConfigService 无 save 方法，跳过")
                return True
        elif hasattr(self, '_config') and self.db:
            for key, value in self._config.items():
                self.set(key, value)
            logger.info("ConfigManager: 配置已保存到SQLite")
            return True
        elif self.db:
            logger.debug("ConfigManager: SQLite模式下每次set自动持久化，无需显式save")
            return True
        else:
            logger.warning("ConfigManager.save: 无可用存储后端")
            return False

# 为了兼容性，保留原有的函数接口


def get_config_manager():
    """获取配置管理器实例"""
    try:
        from core.containers import get_service_container
        from core.services.config_service import ConfigService
        container = get_service_container()
        if container:
            config_service = container.resolve(ConfigService)
            return ConfigManager(config_service)
    except Exception as e:
        logger.warning(f"获取ConfigService失败，使用备用模式: {e}")

    return ConfigManager()

# 兼容性别名


def create_config_manager():
    """创建配置管理器（兼容性函数）"""
    return get_config_manager()
