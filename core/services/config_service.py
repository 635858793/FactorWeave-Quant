from loguru import logger
"""
配置服务模块

负责应用配置的管理、持久化和同步。
集成了原ConfigManager、PluginConfigManager等的所有功能。
"""

import json
import os
import sqlite3
import yaml
import threading
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from datetime import datetime
from .base_service import BaseService

# PyQt5相关导入
try:
    from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
    PYQT5_AVAILABLE = True

    # 创建信号持有者类
    class ConfigSignals(QObject):
        """配置服务的信号类"""
        config_changed = pyqtSignal(str, object)
        theme_changed = pyqtSignal(str)

except ImportError:
    PYQT5_AVAILABLE = False
    # 创建模拟的QObject和pyqtSignal

    class QObject:
        def __init__(self):
            pass

    def pyqtSignal(*args, **kwargs):
        return lambda: None

    # 模拟的信号类
    class ConfigSignals(QObject):
        pass

# 导入配置类型
try:
    from utils.config_types import (
        ThemeConfig, ChartConfig, TradingConfig, DataConfig,
        UIConfig, LoggingConfig
    )
    from utils.theme_types import Theme
    from utils.theme_utils import load_theme_json_with_comments
except ImportError as e:
    logger.warning(f"配置类型导入失败: {e}")
    # 创建基本的配置类型
    ThemeConfig = dict
    ChartConfig = dict
    TradingConfig = dict
    DataConfig = dict
    UIConfig = dict
    LoggingConfig = dict
    Theme = dict

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'factorweave_system.sqlite')


class ConfigService(BaseService):
    """
    统一配置服务

    功能：
    1. 应用配置的管理、持久化和同步
    2. 支持JSON文件和SQLite数据库存储
    3. 支持PyQt5信号通知配置变更
    4. 支持插件配置管理
    5. 支持主题配置管理
    6. 支持交易、数据、UI等各类配置
    """

    def __init__(self, config_file: str = None, use_sqlite: bool = True, **kwargs):
        """
        初始化配置服务

        Args:
            config_file: 配置文件路径
            use_sqlite: 是否使用SQLite存储
            **kwargs: 其他参数
        """
        # 先初始化BaseService
        super().__init__(**kwargs)

        # 如果PyQt5可用，创建ConfigSignals实例用于信号
        self._qt_object = None
        if PYQT5_AVAILABLE:
            self._qt_object = ConfigSignals()

        self._config_file = config_file or 'config/app_config.json'
        self._use_sqlite = use_sqlite
        self._config_data = {}
        self._default_config = {}
        self._config_watchers = {}

        # SQLite相关
        self._db_path = DB_PATH
        self._db_lock = threading.Lock()

        # 初始化配置存储
        self._initialize_storage()

        # 加载默认配置
        self._load_default_config()

        # 加载现有配置
        self._load_config()

        logger.info(f"ConfigService初始化完成 - 文件: {self._config_file}, SQLite: {self._use_sqlite}")

    def emit_config_changed(self, key: str, value: Any):
        """发射配置变更信号"""
        if self._qt_object and hasattr(self._qt_object, 'config_changed'):
            self._qt_object.config_changed.emit(key, value)

    def emit_theme_changed(self, theme_name: str):
        """发射主题变更信号"""
        if self._qt_object and hasattr(self._qt_object, 'theme_changed'):
            self._qt_object.theme_changed.emit(theme_name)

    def connect_config_changed(self, slot):
        """连接配置变更信号"""
        if self._qt_object and hasattr(self._qt_object, 'config_changed'):
            self._qt_object.config_changed.connect(slot)

    def connect_theme_changed(self, slot):
        """连接主题变更信号"""
        if self._qt_object and hasattr(self._qt_object, 'theme_changed'):
            self._qt_object.theme_changed.connect(slot)

    def _initialize_storage(self):
        """初始化配置存储"""
        try:
            if self._use_sqlite:
                self._init_sqlite()

            # 确保配置目录存在
            config_path = Path(self._config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)

        except Exception as e:
            logger.error(f"初始化配置存储失败: {e}")

    def _load_default_config(self):
        """加载默认配置"""
        try:
            self._setup_default_config()
        except Exception as e:
            logger.error(f"加载默认配置失败: {e}")

    def _load_config(self):
        """加载配置"""
        try:
            if self._use_sqlite:
                self._load_config_from_sqlite()
            else:
                self._load_config_from_file()
        except Exception as e:
            logger.error(f"加载配置失败: {e}")

    def _init_sqlite(self):
        """初始化SQLite数据库"""
        try:
            # 确保数据库目录存在
            db_dir = os.path.dirname(self._db_path)
            os.makedirs(db_dir, exist_ok=True)

            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()

                # 创建配置表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS app_config (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        type TEXT DEFAULT 'str',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.commit()
                logger.info("SQLite配置数据库初始化成功")

        except Exception as e:
            logger.error(f"SQLite数据库初始化失败: {e}")
            raise

    def _setup_default_config(self):
        """设置默认配置"""
        self._default_config = {
            'app': {
                'name': 'FactorWeave-Quant',
                'version': '2.0.0',
                'debug': False,
                'auto_save': True,
                'save_interval': 300
            },
            'ui': {
                'theme': 'default',
                'font_family': 'Microsoft YaHei',
                'font_size': 10,
                'window_opacity': 1.0,
                'auto_start': False
            },
            'data': {
                'update_interval': 2000,
                'cache_enabled': True,
                'cache_size': 1000,
                'data_sources': ['eastmoney', 'tushare']
            },
            'trading': {
                'commission_rate': 0.0003,
                'min_commission': 5.0,
                'slippage': 0.0001,
                'interface_type': 'simulation'
            },
            'risk': {
                'max_daily_loss': 0.05,
                'max_single_trade': 0.1,
                'max_positions': 10,
                'stop_loss_enabled': True
            },
            'logging': {
                'level': 'INFO',
                'max_files': 10,
                'file_size': '10MB'
            }
        }

    def _load_config_from_file(self):
        """从文件加载配置"""
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    self._config_data = json.load(f)
                logger.info(f"从文件加载配置成功: {self._config_file}")
            else:
                self._config_data = self._default_config.copy()
                self._save_config_to_file()
                logger.info("使用默认配置并保存到文件")
        except Exception as e:
            logger.error(f"从文件加载配置失败: {e}")
            self._config_data = self._default_config.copy()

    def _load_config_from_sqlite(self):
        """从SQLite加载配置"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, value, type FROM app_config')
                rows = cursor.fetchall()

                self._config_data = self._default_config.copy()

                for key, value, value_type in rows:
                    try:
                        if value_type == 'json':
                            parsed_value = json.loads(value)
                        elif value_type == 'int':
                            parsed_value = int(value)
                        elif value_type == 'float':
                            parsed_value = float(value)
                        elif value_type == 'bool':
                            parsed_value = value.lower() == 'true'
                        else:
                            parsed_value = value

                        # 设置嵌套配置
                        keys = key.split('.')
                        current = self._config_data
                        for k in keys[:-1]:
                            if k not in current:
                                current[k] = {}
                            current = current[k]
                        current[keys[-1]] = parsed_value

                    except Exception as e:
                        logger.warning(f"解析配置项失败 {key}: {e}")

                logger.info("从SQLite加载配置成功")

        except Exception as e:
            logger.error(f"从SQLite加载配置失败: {e}")
            self._config_data = self._default_config.copy()

    def _save_config_to_file(self):
        """保存配置到文件"""
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, ensure_ascii=False, indent=2)
            logger.info(f"配置保存到文件成功: {self._config_file}")
        except Exception as e:
            logger.error(f"保存配置到文件失败: {e}")
            raise

    def _merge_config(self, target: Dict, source: Dict):
        """合并配置"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value

    def cleanup(self):
        """清理资源"""
        try:
            # 保存配置
            self._save_config()

            # 关闭数据库连接
            if self._db_conn:
                self._db_conn.close()

            logger.info("配置服务资源清理完成")

        except Exception as e:
            logger.error(f"配置服务清理失败: {e}")

    # 向后兼容性方法
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（向后兼容性方法）

        Args:
            key: 配置键，支持点分隔的嵌套键如 'ui.theme'
            default: 默认值

        Returns:
            配置值
        """
        try:
            # 分割键路径
            keys = key.split('.')
            value = self._config_data

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value

        except Exception as e:
            logger.error(f"获取配置失败 '{key}': {e}")
            return default

    def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置（向后兼容性方法）

        Returns:
            所有配置的字典
        """
        try:
            return self._config_data.copy()
        except Exception as e:
            logger.error(f"获取所有配置失败: {e}")
            return {}

    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """
        设置配置值（向后兼容性方法）

        Args:
            key: 配置键
            value: 配置值
            save: 是否立即保存

        Returns:
            是否成功设置
        """
        try:
            with self._db_lock:
                keys = key.split('.')
                config = self._config_data

                for k in keys[:-1]:
                    if k not in config:
                        config[k] = {}
                    config = config[k]

                old_value = config.get(keys[-1])
                config[keys[-1]] = value

            if save:
                if self._use_sqlite:
                    self._save_config_to_sqlite(key, value)
                else:
                    self._save_config_to_file()

            # 发送变更信号
            if old_value != value:
                self.emit_config_changed(key, value)

                # 特殊处理主题变更
                if key == 'ui.theme':
                    self.emit_theme_changed(str(value))

            return True

        except Exception as e:
            logger.error(f"设置配置失败 '{key}': {e}")
            return False

    def _save_config_to_sqlite(self, key: str, value: Any):
        """保存单个配置到SQLite"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()

                # 确定值类型
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, ensure_ascii=False)
                    value_type = 'json'
                elif isinstance(value, bool):
                    value_str = str(value).lower()
                    value_type = 'bool'
                elif isinstance(value, int):
                    value_str = str(value)
                    value_type = 'int'
                elif isinstance(value, float):
                    value_str = str(value)
                    value_type = 'float'
                else:
                    value_str = str(value)
                    value_type = 'str'

                cursor.execute('''
                    INSERT OR REPLACE INTO app_config (key, value, type, updated_at) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (key, value_str, value_type))

                conn.commit()

        except Exception as e:
            logger.error(f"保存配置到SQLite失败 '{key}': {e}")

    def _save_config(self):
        """保存所有配置"""
        try:
            if self._use_sqlite:
                # 保存所有配置到SQLite
                self._save_all_config_to_sqlite()
            else:
                # 保存到文件
                self._save_config_to_file()
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def _save_all_config_to_sqlite(self):
        """保存所有配置到SQLite"""
        try:
            def flatten_dict(d, parent_key='', sep='.'):
                """扁平化字典"""
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    else:
                        items.append((new_key, v))
                return dict(items)

            flat_config = flatten_dict(self._config_data)

            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()

                for key, value in flat_config.items():
                    # 确定值类型
                    if isinstance(value, (dict, list)):
                        value_str = json.dumps(value, ensure_ascii=False)
                        value_type = 'json'
                    elif isinstance(value, bool):
                        value_str = str(value).lower()
                        value_type = 'bool'
                    elif isinstance(value, int):
                        value_str = str(value)
                        value_type = 'int'
                    elif isinstance(value, float):
                        value_str = str(value)
                        value_type = 'float'
                    else:
                        value_str = str(value)
                        value_type = 'str'

                    cursor.execute('''
                        INSERT OR REPLACE INTO app_config (key, value, type, updated_at) 
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (key, value_str, value_type))

                conn.commit()

        except Exception as e:
            logger.error(f"保存所有配置到SQLite失败: {e}")
