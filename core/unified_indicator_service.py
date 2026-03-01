from loguru import logger
#!/usr/bin/env python3
"""
统一指标服务
整合技术指标和形态识别功能，使用 factorweave_system.sqlite 作为唯一数据源
支持指标计算、形态识别、参数管理等全部功能
"""

import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd
import importlib
import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from functools import lru_cache
from datetime import datetime
from threading import Lock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Loguru日志已在全局配置，无需额外设置
# logger 已在文件开头导入
# Loguru不需要setLevel
# Loguru自动处理所有日志配置

# 统一数据库路径
UNIFIED_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'factorweave_system.sqlite')

# 尝试导入TA-Lib
try:
    talib = importlib.import_module('talib')
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib 未安装或无法导入，将使用自定义实现")


def _worker_calculate_indicator(args: Tuple) -> pd.DataFrame:
    """
    进程池工作函数 - 用于多进程计算指标
    
    Args:
        args: (indicator_name, df_pickle, params, db_path)
    
    Returns:
        pd.DataFrame: 计算结果
    """
    import pickle
    import pandas as pd
    
    indicator_name, df_bytes, params, db_path = args
    
    try:
        df = pickle.loads(df_bytes)
        
        service = UnifiedIndicatorService(db_path)
        result = service.calculate_indicator(indicator_name, df, params)
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None


def _worker_batch_calculate(args: Tuple) -> pd.DataFrame:
    """
    进程池工作函数 - 用于多进程批量计算
    
    Args:
        args: (indicators, df_pickle, db_path)
    
    Returns:
        pd.DataFrame: 计算结果
    """
    import pickle
    
    indicators, df_bytes, db_path = args
    
    try:
        df = pickle.loads(df_bytes)
        
        service = UnifiedIndicatorService(db_path)
        result = service.batch_calculate_indicators(indicators, df)
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None


class IndicatorProcessPool:
    """指标计算进程池管理器"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, max_workers: int = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, max_workers: int = None):
        if self._initialized:
            return
            
        self._max_workers = max_workers or multiprocessing.cpu_count()
        self._process_pool = None
        self._thread_pool = None
        self._initialized = True
        self._db_path = UNIFIED_DB_PATH
        
        logger.info(f"指标进程池初始化: max_workers={self._max_workers}")
    
    def _ensure_pools(self):
        """确保进程池和线程池已创建"""
        if self._process_pool is None:
            self._process_pool = ProcessPoolExecutor(max_workers=self._max_workers)
        if self._thread_pool is None:
            self._thread_pool = ThreadPoolExecutor(max_workers=self._max_workers * 2)
    
    def calculate_parallel(self, indicators: List[Tuple[str, Dict]], df: pd.DataFrame, use_multiprocess: bool = True) -> pd.DataFrame:
        """
        并行计算多个指标
        
        Args:
            indicators: 指标列表 [(名称, 参数), ...]
            df: 输入数据
            use_multiprocess: 是否使用多进程（False则使用多线程）
        
        Returns:
            pd.DataFrame: 合并后的结果
        """
        import pickle
        
        self._ensure_pools()
        
        df_bytes = pickle.dumps(df)
        
        tasks = []
        for indicator_name, params in indicators:
            tasks.append((indicator_name, df_bytes, params or {}, self._db_path))
        
        if use_multiprocess:
            futures = [self._process_pool.submit(_worker_calculate_indicator, task) for task in tasks]
        else:
            futures = [self._thread_pool.submit(_worker_calculate_indicator, task) for task in tasks]
        
        result_df = df.copy()
        for future in futures:
            try:
                result = future.result(timeout=30)
                if result is not None:
                    for col in result.columns:
                        if col not in result_df.columns:
                            result_df[col] = result[col]
            except Exception as e:
                logger.warning(f"并行计算任务失败: {e}")
        
        return result_df
    
    async def calculate_async(self, indicator_name: str, df: pd.DataFrame, params: Dict = None) -> pd.DataFrame:
        """
        异步计算单个指标
        
        Args:
            indicator_name: 指标名称
            df: 输入数据
            params: 参数
        
        Returns:
            pd.DataFrame: 计算结果
        """
        import pickle
        
        self._ensure_pools()
        
        df_bytes = pickle.dumps(df)
        task = (indicator_name, df_bytes, params or {}, self._db_path)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._thread_pool,
            _worker_calculate_indicator,
            task
        )
        
        return result
    
    async def batch_calculate_async(self, indicators: List[Tuple[str, Dict]], df: pd.DataFrame) -> pd.DataFrame:
        """
        异步批量计算指标
        
        Args:
            indicators: 指标列表
            df: 输入数据
        
        Returns:
            pd.DataFrame: 计算结果
        """
        import pickle
        
        self._ensure_pools()
        
        df_bytes = pickle.dumps(df)
        task = (indicators, df_bytes, self._db_path)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._process_pool,
            _worker_batch_calculate,
            task
        )
        
        return result
    
    def shutdown(self):
        """关闭进程池"""
        if self._process_pool:
            self._process_pool.shutdown(wait=True)
            self._process_pool = None
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None
        logger.info("指标进程池已关闭")


class UnifiedIndicatorService:
    """统一指标服务类 - 支持技术指标和形态识别（插件化版本）"""

    def __init__(self, db_path: str = UNIFIED_DB_PATH):
        """
        初始化统一指标服务

        参数:
            db_path: 统一数据库文件路径
        """
        self.db_path = db_path
        self.conn = None
        self._custom_functions = {}  # 存储自定义函数缓存
        self._indicators_cache = {}  # 指标元数据缓存
        self._patterns_cache = {}   # 形态元数据缓存

        # 插件化支持
        self._indicator_plugins = {}  # 指标插件字典 {plugin_id: plugin_adapter}
        self._plugin_priorities = {}  # 插件优先级 {plugin_id: priority}
        self._calculation_cache = {}  # 计算结果缓存
        self._cache_enabled = True

        # 高级功能支持
        self._backend_selection_strategy = "priority"  # 后端选择策略: priority, performance, accuracy, availability
        self._performance_monitor = {}  # 性能监控 {plugin_id: {avg_time, success_rate, etc.}}
        self._consistency_checker_enabled = False  # 结果一致性检查
        self._async_calculation_enabled = False  # 异步计算支持
        self._max_cache_size = 1000  # 最大缓存条目数
        self._cache_ttl_seconds = 3600  # 缓存生存时间（秒）
        
        # 多进程支持
        self._process_pool: Optional[IndicatorProcessPool] = None
        self._multiprocess_enabled = False

        self._init_connection()

    def _init_connection(self):
        """初始化数据库连接"""
        try:
            # 确保数据库目录存在
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # 使用字典式访问
            logger.info(f" 连接到统一数据库: {self.db_path}")
            
            # 确保数据库表结构存在
            self._create_tables()
        except Exception as e:
            logger.error(f" 数据库连接失败: {str(e)}")
            raise
    
    def _create_tables(self):
        """创建必要的数据库表（如果不存在）"""
        try:
            cursor = self.conn.cursor()
            
            # 创建指标分类表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT,
                parent_id INTEGER,
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (parent_id) REFERENCES indicator_categories (id)
            )
            ''')
            
            # 创建指标表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                formula TEXT,
                output_names TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version TEXT DEFAULT '1.0.0',
                is_builtin BOOLEAN DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES indicator_categories (id)
            )
            ''')
            
            # 创建指标参数表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                param_type TEXT NOT NULL,
                default_value TEXT NOT NULL,
                min_value TEXT,
                max_value TEXT,
                step_value TEXT,
                choices TEXT,
                is_required INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (indicator_id) REFERENCES indicator (id) ON DELETE CASCADE,
                UNIQUE (indicator_id, name)
            )
            ''')
            
            # 创建指标实现表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator_implementations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_id INTEGER NOT NULL,
                engine TEXT NOT NULL,
                function_name TEXT NOT NULL,
                implementation_code TEXT,
                is_default BOOLEAN DEFAULT 0,
                priority INTEGER DEFAULT 50,
                performance_score REAL DEFAULT 1.0,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (indicator_id) REFERENCES indicator (id) ON DELETE CASCADE,
                UNIQUE (indicator_id, engine)
            )
            ''')
            
            # 创建形态类型表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pattern_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                english_name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                description TEXT,
                min_periods INTEGER DEFAULT 5,
                max_periods INTEGER DEFAULT 20,
                confidence_threshold REAL DEFAULT 0.7,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                algorithm_code TEXT,
                parameters TEXT,
                success_rate REAL DEFAULT 0.7,
                risk_level TEXT DEFAULT 'medium'
            )
            ''')
            
            # 创建趋势预警配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trend_alert_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT NOT NULL,
                config_value TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            self.conn.commit()
            logger.info("数据库表结构初始化完成")
        except Exception as e:
            logger.error(f"创建数据库表失败: {str(e)}")
            # 不抛出异常，允许系统继续运行

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __del__(self):
        """析构函数"""
        self.close()

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()

    # ==================== 插件管理方法 ====================

    def register_indicator_plugin(self, plugin_id: str, plugin_adapter, priority: int = 50) -> bool:
        """
        注册指标插件

        Args:
            plugin_id: 插件唯一标识
            plugin_adapter: 插件适配器实例
            priority: 优先级（数字越小优先级越高）

        Returns:
            bool: 注册是否成功
        """
        try:
            # 验证插件接口
            from .indicator_extensions import validate_indicator_plugin_interface

            if not hasattr(plugin_adapter, 'plugin'):
                logger.error(f"插件适配器无效: {plugin_id}")
                return False

            if not validate_indicator_plugin_interface(plugin_adapter.plugin):
                logger.error(f"指标插件接口验证失败: {plugin_id}")
                return False

            # 注册插件
            self._indicator_plugins[plugin_id] = plugin_adapter
            self._plugin_priorities[plugin_id] = priority

            logger.info(f" 指标插件注册成功: {plugin_id} (优先级: {priority})")
            return True

        except Exception as e:
            logger.error(f" 注册指标插件失败 {plugin_id}: {e}")
            return False

    def unregister_indicator_plugin(self, plugin_id: str) -> bool:
        """
        注销指标插件

        Args:
            plugin_id: 插件唯一标识

        Returns:
            bool: 注销是否成功
        """
        try:
            if plugin_id in self._indicator_plugins:
                # 清理插件缓存
                plugin_adapter = self._indicator_plugins[plugin_id]
                if hasattr(plugin_adapter, 'clear_cache'):
                    plugin_adapter.clear_cache()

                # 移除插件
                del self._indicator_plugins[plugin_id]
                del self._plugin_priorities[plugin_id]

                # 清理相关计算缓存
                self._clear_plugin_cache(plugin_id)

                logger.info(f" 指标插件注销成功: {plugin_id}")
                return True
            else:
                logger.warning(f"指标插件不存在: {plugin_id}")
                return False

        except Exception as e:
            logger.error(f" 注销指标插件失败 {plugin_id}: {e}")
            return False

    def get_registered_plugins(self) -> List[str]:
        """获取已注册的插件列表"""
        return list(self._indicator_plugins.keys())

    def get_plugin_priorities(self) -> Dict[str, int]:
        """获取插件优先级配置"""
        return self._plugin_priorities.copy()

    def set_plugin_priority(self, plugin_id: str, priority: int) -> bool:
        """
        设置插件优先级

        Args:
            plugin_id: 插件标识
            priority: 新优先级

        Returns:
            bool: 设置是否成功
        """
        if plugin_id in self._indicator_plugins:
            self._plugin_priorities[plugin_id] = priority
            logger.info(f"插件优先级已更新: {plugin_id} -> {priority}")
            return True
        else:
            logger.error(f"插件不存在: {plugin_id}")
            return False

    def _get_sorted_plugins(self) -> List[Tuple[str, Any]]:
        """获取按优先级排序的插件列表"""
        return sorted(
            [(plugin_id, adapter) for plugin_id, adapter in self._indicator_plugins.items()],
            key=lambda x: self._plugin_priorities.get(x[0], 999)
        )

    def _clear_plugin_cache(self, plugin_id: str) -> None:
        """清理指定插件的缓存"""
        keys_to_remove = [key for key in self._calculation_cache.keys() if key.startswith(f"{plugin_id}:")]
        for key in keys_to_remove:
            del self._calculation_cache[key]

    def clear_all_cache(self) -> None:
        """清理所有缓存"""
        self._calculation_cache.clear()
        self._indicators_cache.clear()
        self._patterns_cache.clear()

        # 清理插件缓存
        for plugin_adapter in self._indicator_plugins.values():
            if hasattr(plugin_adapter, 'clear_cache'):
                plugin_adapter.clear_cache()

        logger.info("所有指标缓存已清理")

    def enable_cache(self, enabled: bool = True) -> None:
        """启用或禁用缓存"""
        self._cache_enabled = enabled
        logger.info(f"指标缓存已{'启用' if enabled else '禁用'}")

    def _generate_cache_key(self, indicator_name: str, parameters: Dict[str, Any],
                            data_hash: str, plugin_id: str = None) -> str:
        """生成缓存键"""
        import hashlib

        # 创建参数字符串
        param_str = json.dumps(parameters, sort_keys=True)

        # 生成缓存键
        key_parts = [indicator_name, param_str, data_hash]
        if plugin_id:
            key_parts.insert(0, plugin_id)

        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_data_hash(self, data: pd.DataFrame) -> str:
        """获取数据哈希值"""
        import hashlib

        # 使用数据的形状和部分内容生成哈希
        shape_str = str(data.shape)
        if not data.empty:
            # 使用首尾几行数据生成哈希
            sample_data = pd.concat([data.head(3), data.tail(3)])
            content_str = str(sample_data.values.tobytes())
        else:
            content_str = "empty"

        hash_string = f"{shape_str}|{content_str}"
        return hashlib.md5(hash_string.encode()).hexdigest()[:16]

    # ==================== 基础查询方法 ====================

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """获取所有分类"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, name, display_name, description, parent_id, sort_order
                FROM indicator_categories 
                WHERE is_active = 1 
                ORDER BY sort_order, id
            ''')

            categories = []
            for row in cursor.fetchall():
                categories.append({
                    'id': row['id'],
                    'name': row['name'],
                    'display_name': row['display_name'],
                    'description': row['description'],
                    'parent_id': row['parent_id'],
                    'sort_order': row['sort_order']
                })

            return categories
        except Exception as e:
            logger.error(f"获取分类失败: {str(e)}")
            return []

    def get_category_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取分类"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, name, display_name, description, parent_id, sort_order
                FROM indicator_categories 
                WHERE name = ? AND is_active = 1
            ''', (name,))

            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'display_name': row['display_name'],
                    'description': row['description'],
                    'parent_id': row['parent_id'],
                    'sort_order': row['sort_order']
                }
            return None
        except Exception as e:
            logger.error(f"获取分类失败: {str(e)}")
            return None

    # ==================== 技术指标相关方法 ====================

    @lru_cache(maxsize=128)
    def get_indicator(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指标定义 - 支持英文名和中文显示名查找"""
        if name in self._indicators_cache:
            return self._indicators_cache[name]

        try:
            cursor = self.conn.cursor()
            # 支持通过英文名或中文显示名查找
            cursor.execute('''
                SELECT i.*, c.name as category_name, c.display_name as category_display_name
                FROM indicator i
                LEFT JOIN indicator_categories c ON i.category_id = c.id
                WHERE (i.name = ? OR i.display_name = ?) AND i.is_active = 1
            ''', (name, name))

            row = cursor.fetchone()
            if not row:
                return None

            # 获取参数
            cursor.execute('''
                SELECT name, description, param_type, default_value, min_value, 
                       max_value, step_value, choices, is_required, sort_order
                FROM indicator_parameters 
                WHERE indicator_id = ? 
                ORDER BY sort_order, id
            ''', (row['id'],))

            parameters = []
            for param_row in cursor.fetchall():
                param = {
                    'name': param_row['name'],
                    'description': param_row['description'],
                    'type': param_row['param_type'],
                    'default_value': json.loads(param_row['default_value']),
                    'is_required': bool(param_row['is_required']),
                    'sort_order': param_row['sort_order']
                }

                # 可选字段
                for field in ['min_value', 'max_value', 'step_value', 'choices']:
                    if param_row[field]:
                        param[field] = json.loads(param_row[field])

                parameters.append(param)

            # 获取实现
            cursor.execute('''
                SELECT engine, function_name, implementation_code, is_default, 
                       priority, performance_score, is_active
                FROM indicator_implementations 
                WHERE indicator_id = ? AND is_active = 1
                ORDER BY priority DESC, is_default DESC
            ''', (row['id'],))

            implementations = []
            for impl_row in cursor.fetchall():
                implementations.append({
                    'engine': impl_row['engine'],
                    'function_name': impl_row['function_name'],
                    'code': impl_row['implementation_code'],
                    'is_default': bool(impl_row['is_default']),
                    'priority': impl_row['priority'],
                    'performance_score': impl_row['performance_score']
                })

            indicator = {
                'id': row['id'],
                'name': row['name'],
                'display_name': row['display_name'],
                'category_id': row['category_id'],
                'category_name': row['category_name'],
                'category_display_name': row['category_display_name'],
                'description': row['description'],
                'formula': row['formula'],
                'output_names': json.loads(row['output_names']) if row['output_names'] else [],
                'version': row['version'],
                'is_builtin': bool(row['is_builtin']),
                'parameters': parameters,
                'implementations': implementations,
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }

            # 缓存结果
            self._indicators_cache[name] = indicator
            return indicator

        except Exception as e:
            logger.error(f"获取指标 {name} 失败: {str(e)}")
            return None

    def get_all_indicators(self) -> List[Dict[str, Any]]:
        """获取所有指标定义"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT name FROM indicator 
                WHERE is_active = 1 
                ORDER BY name
            ''')

            indicators = []
            for row in cursor.fetchall():
                indicator = self.get_indicator(row['name'])
                if indicator:
                    indicators.append(indicator)

            return indicators
        except Exception as e:
            logger.error(f"获取所有指标失败: {str(e)}")
            return []

    def get_indicators_by_category(self, category_name: str) -> List[Dict[str, Any]]:
        """获取指定分类的所有指标"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT i.name
                FROM indicator i
                LEFT JOIN indicator_categories c ON i.category_id = c.id
                WHERE c.name = ? AND i.is_active = 1
                ORDER BY i.name
            ''', (category_name,))

            indicators = []
            for row in cursor.fetchall():
                indicator = self.get_indicator(row['name'])
                if indicator:
                    indicators.append(indicator)

            return indicators
        except Exception as e:
            logger.error(f"获取分类 {category_name} 的指标失败: {str(e)}")
            return []

    def get_indicator_default_params(self, name: str) -> Dict[str, Any]:
        """获取指标默认参数"""
        indicator = self.get_indicator(name)
        if not indicator:
            return {}

        return {
            param['name']: param['default_value']
            for param in indicator['parameters']
        }

    # ==================== 形态识别相关方法 ====================

    def get_pattern(self, name: str) -> Optional[Dict[str, Any]]:
        """获取形态定义 - 支持中文名称和英文名称查询"""
        if name in self._patterns_cache:
            return self._patterns_cache[name]

        try:
            cursor = self.conn.cursor()
            # 同时支持中文名称和英文名称查询
            cursor.execute('''
                SELECT p.*, c.name as category_name, c.display_name as category_display_name
                FROM pattern_types p
                LEFT JOIN indicator_categories c ON p.category_id = c.id
                WHERE (p.name = ? OR p.english_name = ?) AND p.is_active = 1
            ''', (name, name))

            row = cursor.fetchone()
            if not row:
                return None

            pattern = {
                'id': row['id'],
                'name': row['name'],
                'english_name': row['english_name'],
                'category': row['category'],
                'category_id': row['category_id'],
                'category_name': row['category_name'],
                'category_display_name': row['category_display_name'],
                'signal_type': row['signal_type'],
                'description': row['description'],
                'min_periods': row['min_periods'],
                'max_periods': row['max_periods'],
                'confidence_threshold': row['confidence_threshold'],
                'algorithm_code': row['algorithm_code'],
                'parameters': json.loads(row['parameters']) if row['parameters'] else {},
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }

            # 缓存结果
            self._patterns_cache[name] = pattern
            return pattern

        except Exception as e:
            logger.error(f"获取形态 {name} 失败: {str(e)}")
            return None

    def get_all_patterns(self) -> List[Dict[str, Any]]:
        """获取所有形态定义"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT english_name FROM pattern_types 
                WHERE is_active = 1 
                ORDER BY english_name
            ''')

            patterns = []
            for row in cursor.fetchall():
                pattern = self.get_pattern(row['english_name'])
                if pattern:
                    patterns.append(pattern)

            return patterns
        except Exception as e:
            logger.error(f"获取所有形态失败: {str(e)}")
            return []

    def get_patterns_by_category(self, category: str) -> List[Dict[str, Any]]:
        """获取指定分类的所有形态"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT english_name FROM pattern_types 
                WHERE category = ? AND is_active = 1
                ORDER BY english_name
            ''', (category,))

            patterns = []
            for row in cursor.fetchall():
                pattern = self.get_pattern(row['english_name'])
                if pattern:
                    patterns.append(pattern)

            return patterns
        except Exception as e:
            logger.error(f"获取分类 {category} 的形态失败: {str(e)}")
            return []

    # ==================== 指标计算方法 ====================

    def _get_best_implementation(self, indicator: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取最佳实现"""
        implementations = indicator.get('implementations', [])
        if not implementations:
            return None

        # 按优先级和默认标志排序，选择最佳实现
        best_impl = None

        # 1. 首先查找默认实现
        for impl in implementations:
            if impl.get('is_default', False):
                best_impl = impl
                break

        # 2. 如果没有默认实现，根据引擎优先级选择
        if not best_impl:
            # TA-Lib > custom > pandas
            engine_priority = {'talib': 3, 'custom': 2, 'pandas': 1}

            implementations_sorted = sorted(
                implementations,
                key=lambda x: (x.get('priority', 0), engine_priority.get(x['engine'], 0)),
                reverse=True
            )

            # 如果TA-Lib可用，优先选择TA-Lib实现
            if TALIB_AVAILABLE:
                for impl in implementations_sorted:
                    if impl['engine'] == 'talib':
                        best_impl = impl
                        break

            # 否则选择优先级最高的实现
            if not best_impl and implementations_sorted:
                best_impl = implementations_sorted[0]

        return best_impl

    def _compile_custom_function(self, code: str, function_name: str) -> Optional[Callable]:
        """编译自定义函数"""
        cache_key = f"{function_name}_{hash(code)}"

        if cache_key in self._custom_functions:
            return self._custom_functions[cache_key]

        try:
            namespace = {'np': np, 'pd': pd}
            exec(code, namespace)

            if function_name not in namespace:
                logger.error(f"函数 {function_name} 未在代码中定义")
                return None

            func = namespace[function_name]
            self._custom_functions[cache_key] = func
            return func

        except Exception as e:
            logger.error(f"编译自定义函数 {function_name} 失败: {str(e)}")
            return None

    def calculate_indicator(self, name: str, df: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        计算指标（技术指标或形态指标）- 插件化版本

        参数:
            name: 指标名称
            df: 输入DataFrame，包含OHLCV数据
            params: 计算参数，如果为None则使用默认参数

        返回:
            DataFrame: 添加了指标列的DataFrame
        """
        if params is None:
            params = {}

        # 1. 首先尝试使用插件计算
        plugin_result = self._calculate_indicator_with_plugins(name, df, params)
        if plugin_result is not None:
            return plugin_result

        # 2. 回退到传统方法：技术指标
        indicator = self.get_indicator(name)
        if indicator:
            return self._calculate_technical_indicator(name, df, params, indicator)

        # 3. 回退到传统方法：形态指标
        pattern = self.get_pattern(name)
        if pattern:
            return self._calculate_pattern_indicator(name, df, params, pattern)

        logger.error(f"指标或形态 {name} 不存在")
        return df.copy()

    def _calculate_indicator_with_plugins(self, name: str, df: pd.DataFrame, params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        使用插件计算指标

        Args:
            name: 指标名称
            df: 输入数据
            params: 参数

        Returns:
            Optional[pd.DataFrame]: 计算结果或None
        """
        if not self._indicator_plugins:
            return None

        try:
            # 检查缓存
            if self._cache_enabled:
                data_hash = self._get_data_hash(df)
                cache_key = self._generate_cache_key(name, params, data_hash)
                if cache_key in self._calculation_cache:
                    logger.debug(f"指标缓存命中: {name}")
                    return self._calculation_cache[cache_key]

            # 按优先级尝试插件
            for plugin_id, plugin_adapter in self._get_sorted_plugins():
                try:
                    # 检查插件是否支持该指标
                    supported_indicators = plugin_adapter.get_supported_indicators()
                    if name not in supported_indicators:
                        continue

                    logger.debug(f"使用插件计算指标: {plugin_id}.{name}")

                    # 转换数据格式
                    from .indicator_extensions import StandardKlineData, IndicatorCalculationContext

                    kline_data = StandardKlineData.from_dataframe(df)
                    context = IndicatorCalculationContext(
                        symbol="unknown",
                        timeframe="D",
                        cache_enabled=self._cache_enabled
                    )

                    # 计算指标
                    result = plugin_adapter.calculate_indicator(name, kline_data, params, context)

                    if result and not result.data.empty:
                        # 合并结果到原始DataFrame
                        result_df = df.copy()
                        for col in result.data.columns:
                            result_df[col] = result.data[col]

                        # 缓存结果
                        if self._cache_enabled:
                            self._calculation_cache[cache_key] = result_df

                        logger.info(f" 插件指标计算成功: {plugin_id}.{name}")
                        return result_df

                except Exception as e:
                    logger.warning(f"插件指标计算失败 {plugin_id}.{name}: {e}")
                    continue

            # 所有插件都失败
            logger.debug(f"所有插件都无法计算指标: {name}")
            return None

        except Exception as e:
            logger.error(f"插件指标计算异常 {name}: {e}")
            return None

    def batch_calculate_indicators(self, indicators: List[Tuple[str, Dict[str, Any]]], df: pd.DataFrame) -> pd.DataFrame:
        """
        批量计算指标 - 优化版本，减少数据复制

        Args:
            indicators: 指标列表 [(指标名称, 参数), ...]
            df: 输入数据

        Returns:
            pd.DataFrame: 包含所有指标的结果
        """
        result_df = df.copy()

        try:
            if not TALIB_AVAILABLE:
                for indicator_name, params in indicators:
                    try:
                        indicator_result = self.calculate_indicator(indicator_name, result_df, params)
                        if indicator_result is not None:
                            for col in indicator_result.columns:
                                if col not in df.columns:
                                    result_df[col] = indicator_result[col]
                    except Exception as e:
                        logger.error(f"计算指标失败 {indicator_name}: {e}")
                return result_df

            for indicator_name, params in indicators:
                params = params or {}
                
                indicator = self.get_indicator(indicator_name)
                if not indicator:
                    continue
                
                impl = self._get_best_implementation(indicator)
                if not impl:
                    continue
                
                try:
                    if impl['engine'] == 'talib':
                        result_df = self._calculate_talib_indicator(indicator_name, result_df, impl, params, indicator)
                    else:
                        indicator_result = self.calculate_indicator(indicator_name, result_df, params)
                        if indicator_result is not None:
                            for col in indicator_result.columns:
                                if col not in result_df.columns:
                                    result_df[col] = indicator_result[col]
                except Exception as e:
                    logger.warning(f"批量计算指标 {indicator_name} 失败: {e}")
                    continue

            return result_df

        except Exception as e:
            logger.error(f"批量计算指标失败: {e}")
            return result_df

        except Exception as e:
            logger.error(f"批量计算指标失败: {e}")
            return result_df

    def _batch_calculate_with_plugins(self, indicators: List[Tuple[str, Dict[str, Any]]], df: pd.DataFrame) -> Dict[str, Any]:
        """
        使用插件批量计算指标

        Args:
            indicators: 指标列表
            df: 输入数据

        Returns:
            Dict[str, Any]: 插件计算结果
        """
        plugin_results = {}

        try:
            # 按插件分组指标
            plugin_indicators = {}
            for indicator_name, params in indicators:
                for plugin_id, plugin_adapter in self._get_sorted_plugins():
                    supported_indicators = plugin_adapter.get_supported_indicators()
                    if indicator_name in supported_indicators:
                        if plugin_id not in plugin_indicators:
                            plugin_indicators[plugin_id] = []
                        plugin_indicators[plugin_id].append((indicator_name, params))
                        break

            # 对每个插件进行批量计算
            for plugin_id, plugin_indicator_list in plugin_indicators.items():
                try:
                    plugin_adapter = self._indicator_plugins[plugin_id]

                    # 转换数据格式
                    from .indicator_extensions import StandardKlineData, IndicatorCalculationContext

                    kline_data = StandardKlineData.from_dataframe(df)
                    context = IndicatorCalculationContext(
                        symbol="unknown",
                        timeframe="D",
                        cache_enabled=self._cache_enabled
                    )

                    # 批量计算
                    batch_results = plugin_adapter.batch_calculate_indicators(
                        plugin_indicator_list, kline_data, context
                    )

                    # 合并结果
                    plugin_results.update(batch_results)

                    logger.info(f" 插件批量计算完成: {plugin_id} ({len(plugin_indicator_list)} 个指标)")

                except Exception as e:
                    logger.error(f"插件批量计算失败 {plugin_id}: {e}")

            return plugin_results

        except Exception as e:
            logger.error(f"插件批量计算异常: {e}")
            return {}

    def _calculate_technical_indicator(self, name: str, df: pd.DataFrame, params: Optional[Dict[str, Any]], indicator: Dict[str, Any]) -> pd.DataFrame:
        """计算技术指标"""
        # 获取参数
        if params is None:
            params = self.get_indicator_default_params(name)
        else:
            # 合并默认参数
            default_params = self.get_indicator_default_params(name)
            for key, value in default_params.items():
                if key not in params:
                    params[key] = value

        # 获取最佳实现
        impl = self._get_best_implementation(indicator)
        if not impl:
            logger.error(f"指标 {name} 没有可用的实现")
            return df.copy()

        try:
            result = df.copy()

            if impl['engine'] == 'talib':
                # TA-Lib实现
                result = self._calculate_talib_indicator(name, result, impl, params, indicator)
            elif impl['engine'] in ['custom', 'pandas']:
                # 自定义实现
                result = self._calculate_custom_indicator(name, result, impl, params, indicator)
            else:
                logger.error(f"不支持的实现引擎: {impl['engine']}")

            return result

        except Exception as e:
            logger.error(f"计算指标 {name} 时发生错误: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return df.copy()

    def _calculate_pattern_indicator(self, name: str, df: pd.DataFrame, params: Optional[Dict[str, Any]], pattern: Dict[str, Any]) -> pd.DataFrame:
        """计算形态指标"""
        try:
            from analysis.pattern_recognition import EnhancedPatternRecognizer

            result = df.copy()

            # 使用 EnhancedPatternRecognizer 进行识别
            recognizer = EnhancedPatternRecognizer()

            # 获取置信度阈值
            confidence_threshold = params.get('置信度阈值', pattern.get('confidence_threshold', 0.7))

            # 识别特定形态
            pattern_results = recognizer.identify_patterns(df,
                                                           confidence_threshold=confidence_threshold,
                                                           pattern_types=[pattern['english_name']])

            # 创建一个信号Series
            signal = pd.Series(0, index=df.index)

            for presult in pattern_results:
                # 根据信号类型设置值
                signal_type = presult.signal_type.value if hasattr(presult, 'signal_type') else 'neutral'
                if signal_type == 'buy':
                    signal.iloc[presult.index] = 1
                elif signal_type == 'sell':
                    signal.iloc[presult.index] = -1

            result[name] = signal
            return result

        except Exception as e:
            logger.error(f"计算形态 {name} 时发生错误: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return df.copy()

    def _execute_pattern_algorithm(self, name: str, df: pd.DataFrame, params: Dict[str, Any], pattern: Dict[str, Any]) -> Union[pd.Series, Dict[str, pd.Series]]:
        """执行形态识别算法"""
        try:
            # 获取算法代码
            algorithm_code = pattern.get('algorithm_code', '')

            if algorithm_code:
                # 执行自定义算法
                return self._execute_custom_pattern_algorithm(name, df, params, algorithm_code)
            else:
                # 使用内置形态识别
                return self._execute_builtin_pattern_algorithm(name, df, params, pattern)

        except Exception as e:
            logger.error(f"执行形态算法 {name} 失败: {str(e)}")
            # 返回默认的空信号
            return pd.Series(0, index=df.index)

    def _execute_custom_pattern_algorithm(self, name: str, df: pd.DataFrame, params: Dict[str, Any], algorithm_code: str) -> Union[pd.Series, Dict[str, pd.Series]]:
        """执行自定义形态算法"""
        try:
            # 创建执行环境
            namespace = {
                'np': np,
                'pd': pd,
                'df': df,
                'params': params,
                'name': name
            }

            # 执行算法代码
            exec(algorithm_code, namespace)

            # 获取结果 - 约定算法代码应该设置result变量
            if 'result' in namespace:
                return namespace['result']
            else:
                logger.warning(f"形态算法 {name} 没有返回result变量")
                return pd.Series(0, index=df.index)

        except Exception as e:
            logger.error(f"执行自定义形态算法 {name} 失败: {str(e)}")
            return pd.Series(0, index=df.index)

    def _execute_builtin_pattern_algorithm(self, name: str, df: pd.DataFrame, params: Dict[str, Any], pattern: Dict[str, Any]) -> Union[pd.Series, Dict[str, pd.Series]]:
        """执行内置形态算法"""
        try:
            # 这里可以添加内置的形态识别算法
            # 目前返回简单的模拟结果

            confidence_threshold = params.get('置信度阈值', 0.7)
            min_periods = params.get('最小周期', 5)
            max_periods = params.get('最大周期', 20)

            # 创建简单的形态信号
            # 这里是一个示例实现，实际应该根据具体形态实现相应算法
            signal = pd.Series(0, index=df.index)

            # 模拟一些形态信号（基于价格变化）
            if len(df) >= min_periods:
                price_change = df['close'].pct_change(periods=min_periods)

                # 根据形态类型生成不同的信号
                if '锤头' in name or '十字星' in name:
                    # 反转形态
                    signal.loc[price_change > 0.02] = 1  # 买入信号
                    signal.loc[price_change < -0.02] = -1  # 卖出信号
                elif '吞没' in name or '包容' in name:
                    # 包容形态
                    signal.loc[price_change > 0.03] = 1
                    signal.loc[price_change < -0.03] = -1
                else:
                    # 默认处理
                    signal.loc[price_change > 0.025] = 1
                    signal.loc[price_change < -0.025] = -1

            return signal

        except Exception as e:
            logger.error(f"执行内置形态算法 {name} 失败: {str(e)}")
            return pd.Series(0, index=df.index)

    def _calculate_talib_indicator(self, name: str, df: pd.DataFrame, impl: Dict, params: Dict, indicator: Dict) -> pd.DataFrame:
        """使用TA-Lib计算指标"""
        if not TALIB_AVAILABLE:
            logger.error(f"TA-Lib 未安装，无法计算指标 {name}")
            return df

        try:
            function_name = impl['function_name']

            # 修复STOCH指标参数
            if function_name == 'STOCH':
                params = fix_stoch_parameters(params)

            talib_func = getattr(talib, function_name)

            # 准备输入数据
            inputs = self._prepare_talib_inputs(df, function_name, params)

            # 调用TA-Lib函数
            # 将参数分为数据参数和设置参数
            data_params = {}
            config_params = {}

            for key, value in inputs.items():
                if key in ['close', 'open', 'high', 'low', 'volume']:
                    data_params[key] = value
                else:
                    config_params[key] = value

            # 根据函数特性调用
            if data_params and len(data_params) == 1 and 'close' in data_params:
                # 单一数据列函数
                talib_result = talib_func(data_params['close'], **config_params)
            elif len(data_params) == 3 and all(k in data_params for k in ['high', 'low', 'close']):
                # 三数据列函数
                talib_result = talib_func(data_params['high'], data_params['low'], data_params['close'], **config_params)
            elif len(data_params) == 2 and all(k in data_params for k in ['close', 'volume']):
                # 双数据列函数
                talib_result = talib_func(data_params['close'], data_params['volume'], **config_params)
            else:
                # 通用调用
                talib_result = talib_func(**inputs)

            # 处理返回结果
            output_names = indicator.get('output_names', [])

            if isinstance(talib_result, tuple):
                # 多个输出
                for i, output_name in enumerate(output_names):
                    if i < len(talib_result):
                        df[output_name] = pd.Series(talib_result[i], index=df.index)
            else:
                # 单个输出
                if output_names:
                    df[output_names[0]] = pd.Series(talib_result, index=df.index)
                else:
                    df[name] = pd.Series(talib_result, index=df.index)

            return df

        except Exception as e:
            logger.error(f"TA-Lib计算指标 {name} 失败: {str(e)}")
            return df

    def _prepare_talib_inputs(self, df: pd.DataFrame, function_name: str, params: Dict) -> Dict:
        """准备TA-Lib函数的输入参数"""
        inputs = {}

        # 根据函数名确定需要的输入列，确保数据类型为float64
        if function_name in ['MA', 'SMA', 'EMA', 'RSI', 'ROC', 'MOM', 'TRIX']:
            inputs['close'] = df['close'].astype(np.float64).values
        elif function_name in ['WILLR']:
            inputs['high'] = df['high'].astype(np.float64).values
            inputs['low'] = df['low'].astype(np.float64).values
            inputs['close'] = df['close'].astype(np.float64).values
        elif function_name in ['MACD']:
            inputs['close'] = df['close'].astype(np.float64).values
        elif function_name in ['BBANDS', 'BOLL']:
            inputs['close'] = df['close'].astype(np.float64).values
        elif function_name in ['STOCH', 'STOCHF']:
            inputs['high'] = df['high'].astype(np.float64).values
            inputs['low'] = df['low'].astype(np.float64).values
            inputs['close'] = df['close'].astype(np.float64).values
        elif function_name in ['ATR', 'CCI']:
            inputs['high'] = df['high'].astype(np.float64).values
            inputs['low'] = df['low'].astype(np.float64).values
            inputs['close'] = df['close'].astype(np.float64).values
        elif function_name in ['OBV']:
            inputs['close'] = df['close'].astype(np.float64).values
            inputs['volume'] = df['volume'].astype(np.float64).values
        elif function_name in ['ADX']:
            inputs['high'] = df['high'].astype(np.float64).values
            inputs['low'] = df['low'].astype(np.float64).values
            inputs['close'] = df['close'].astype(np.float64).values
        elif function_name in ['SAR']:
            inputs['high'] = df['high'].astype(np.float64).values
            inputs['low'] = df['low'].astype(np.float64).values
        elif function_name in ['MFI']:
            inputs['high'] = df['high'].astype(np.float64).values
            inputs['low'] = df['low'].astype(np.float64).values
            inputs['close'] = df['close'].astype(np.float64).values
            inputs['volume'] = df['volume'].astype(np.float64).values
        elif function_name in ['ADOSC']:
            inputs['high'] = df['high'].astype(np.float64).values
            inputs['low'] = df['low'].astype(np.float64).values
            inputs['close'] = df['close'].astype(np.float64).values
            inputs['volume'] = df['volume'].astype(np.float64).values
        else:
            # 默认使用close
            inputs['close'] = df['close'].astype(np.float64).values

        # 定义每个指标支持的参数
        supported_params = {
            'MA': ['timeperiod'],
            'SMA': ['timeperiod'],
            'EMA': ['timeperiod'],
            'RSI': ['timeperiod'],
            'ROC': ['timeperiod'],
            'MOM': ['timeperiod'],
            'TRIX': ['timeperiod'],
            'WILLR': ['timeperiod'],
            'ATR': ['timeperiod'],
            'CCI': ['timeperiod'],
            'ADX': ['timeperiod'],
            'MACD': ['fastperiod', 'slowperiod', 'signalperiod'],
            'BBANDS': ['timeperiod', 'nbdevup', 'nbdevdn'],
            'BOLL': ['timeperiod', 'nbdevup', 'nbdevdn'],
            'STOCH': ['fastk_period', 'slowk_period', 'slowk_matype', 'slowd_period', 'slowd_matype'],
            'OBV': [],  # OBV不需要参数
            'SAR': ['acceleration', 'maximum'],
            'MFI': ['timeperiod'],
            'ADOSC': ['fastperiod', 'slowperiod']
        }

        # 只添加支持的参数
        allowed_params = supported_params.get(function_name, ['timeperiod'])  # 默认支持timeperiod
        for key, value in params.items():
            if key not in inputs and key in allowed_params:  # 避免覆盖数据列，并且只添加支持的参数
                inputs[key] = value

        return inputs

    def _calculate_custom_indicator(self, name: str, df: pd.DataFrame, impl: Dict, params: Dict, indicator: Dict) -> pd.DataFrame:
        """使用自定义实现计算指标"""
        try:
            if impl['engine'] == 'custom' and impl.get('code'):
                # 编译并执行自定义代码
                func = self._compile_custom_function(impl['code'], impl['function_name'])
                if not func:
                    return df
            else:
                # 导入预定义的函数
                try:
                    module_parts = impl['function_name'].split('.')
                    if len(module_parts) > 1:
                        module_path = '.'.join(module_parts[:-1])
                        func_name = module_parts[-1]
                        module = importlib.import_module(module_path)
                        func = getattr(module, func_name)
                    else:
                        # 尝试从全局命名空间获取
                        func = globals().get(impl['function_name'])
                        if not func:
                            logger.error(f"找不到函数: {impl['function_name']}")
                            return df
                except Exception as e:
                    logger.error(f"导入函数 {impl['function_name']} 失败: {str(e)}")
                    return df

            # 准备函数参数
            import inspect
            sig = inspect.signature(func)
            call_args = {}

            for param_name in sig.parameters:
                if param_name == 'df':
                    call_args['df'] = df
                elif param_name in ['close', 'open', 'high', 'low', 'volume']:
                    if param_name in df.columns:
                        call_args[param_name] = df[param_name]
                elif param_name in params:
                    call_args[param_name] = params[param_name]

            # 调用函数
            custom_result = func(**call_args)

            # 处理返回结果
            output_names = indicator.get('output_names', [])

            if isinstance(custom_result, pd.DataFrame):
                # 返回DataFrame，合并结果
                for output_name in output_names:
                    if output_name in custom_result.columns:
                        df[output_name] = custom_result[output_name]
            elif isinstance(custom_result, tuple):
                # 返回多个Series
                for i, output_name in enumerate(output_names):
                    if i < len(custom_result):
                        df[output_name] = custom_result[i]
            elif isinstance(custom_result, pd.Series):
                # 返回单个Series
                if output_names:
                    df[output_names[0]] = custom_result
                else:
                    df[name] = custom_result

            return df

        except Exception as e:
            logger.error(f"自定义计算指标 {name} 失败: {str(e)}")
            return df

    # ==================== 统一查询方法 ====================

    def get_all_indicators_and_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有指标和形态，按分类组织"""
        try:
            categories = self.get_all_categories()
            result = {}

            for category in categories:
                category_name = category['name']
                category_display_name = category['display_name']

                # 初始化分类
                result[category_display_name] = {
                    'category_info': category,
                    'indicators': [],
                    'patterns': []
                }

                # 获取指标
                if category_name != 'pattern':
                    indicators = self.get_indicators_by_category(category_name)
                    result[category_display_name]['indicators'] = indicators

                # 获取形态（只有形态类）
                if category_name == 'pattern':
                    patterns = self.get_all_patterns()
                    result[category_display_name]['patterns'] = patterns

            return result

        except Exception as e:
            logger.error(f"获取所有指标和形态失败: {str(e)}")
            return {}

    def search_indicators_and_patterns(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """搜索指标和形态"""
        query = query.lower()
        result = {'indicators': [], 'patterns': []}

        try:
            # 搜索指标
            indicators = self.get_all_indicators()
            for indicator in indicators:
                if (query in indicator['name'].lower() or
                    query in indicator['display_name'].lower() or
                        query in indicator['description'].lower()):
                    result['indicators'].append(indicator)

            # 搜索形态
            patterns = self.get_all_patterns()
            for pattern in patterns:
                if (query in pattern['english_name'].lower() or
                    query in pattern['name'].lower() or
                        query in pattern['description'].lower()):
                    result['patterns'].append(pattern)

            return result

        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return result

    def enable_multiprocess(self, enabled: bool = True, max_workers: int = None) -> None:
        """
        启用或禁用多进程计算
        
        Args:
            enabled: 是否启用
            max_workers: 最大进程数，默认为CPU核心数
        """
        self._multiprocess_enabled = enabled
        
        if enabled:
            if self._process_pool is None:
                self._process_pool = IndicatorProcessPool(max_workers=max_workers)
            logger.info(f"多进程计算已启用，进程数: {self._process_pool._max_workers}")
        else:
            if self._process_pool:
                self._process_pool.shutdown()
                self._process_pool = None
            logger.info("多进程计算已禁用")

    def calculate_parallel(self, indicators: List[Tuple[str, Dict]], df: pd.DataFrame, use_multiprocess: bool = None) -> pd.DataFrame:
        """
        并行计算多个指标 - 智能选择最优执行方式
        
        智能选择策略：
        - 小数据量(< 10000行): 使用同步计算（TA-Lib已经足够快）
        - 大数据量(>= 10000行) + 显式启用多进程: 使用进程池
        - 异步模式启用: 使用线程池
        
        Args:
            indicators: 指标列表 [(名称, 参数), ...]
            df: 输入数据
            use_multiprocess: 是否使用多进程（None则自动选择）
        
        Returns:
            pd.DataFrame: 计算结果
        """
        data_size = len(df)
        indicator_count = len(indicators)
        
        if use_multiprocess is None:
            if data_size < 10000:
                use_multiprocess = False
            else:
                use_multiprocess = self._multiprocess_enabled
        
        if use_multiprocess and self._process_pool and data_size >= 10000:
            return self._process_pool.calculate_parallel(indicators, df, use_multiprocess=True)
        elif self._async_calculation_enabled and self._process_pool:
            return self._process_pool.calculate_parallel(indicators, df, use_multiprocess=False)
        else:
            return self.batch_calculate_indicators(indicators, df)

    async def calculate_indicator_async(self, name: str, df: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        异步计算单个指标
        
        Args:
            name: 指标名称
            df: 输入数据
            params: 参数
        
        Returns:
            pd.DataFrame: 计算结果
        """
        if self._process_pool is None:
            self._process_pool = IndicatorProcessPool()
        
        return await self._process_pool.calculate_async(name, df, params)

    async def batch_calculate_async(self, indicators: List[Tuple[str, Dict]], df: pd.DataFrame) -> pd.DataFrame:
        """
        异步批量计算指标
        
        Args:
            indicators: 指标列表
            df: 输入数据
        
        Returns:
            pd.DataFrame: 计算结果
        """
        if self._process_pool is None:
            self._process_pool = IndicatorProcessPool()
        
        return await self._process_pool.batch_calculate_async(indicators, df)


# ==================== 全局实例和便捷函数 ====================

# 创建全局实例
_unified_service = None


def get_unified_service() -> UnifiedIndicatorService:
    """获取全局统一服务实例"""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedIndicatorService()
    return _unified_service


def calculate_indicator(name: str, df: pd.DataFrame, params: Dict[str, Any] = None) -> pd.DataFrame:
    """便捷函数：计算指标"""
    service = get_unified_service()
    return service.calculate_indicator(name, df, params)


def get_indicator_metadata(name: str) -> Optional[Dict[str, Any]]:
    """便捷函数：获取指标元数据"""
    service = get_unified_service()
    return service.get_indicator(name)


def get_all_indicators_metadata() -> List[Dict[str, Any]]:
    """便捷函数：获取所有指标元数据"""
    service = get_unified_service()
    return service.get_all_indicators()


def get_indicators_by_category(category_name: str) -> List[Dict[str, Any]]:
    """便捷函数：获取分类指标"""
    service = get_unified_service()
    return service.get_indicators_by_category(category_name)


def get_all_categories() -> List[Dict[str, Any]]:
    """便捷函数：获取所有分类"""
    service = get_unified_service()
    return service.get_all_categories()


# ==================== 向后兼容性支持 ====================

# 指标别名映射
INDICATOR_ALIASES = {
    'SMA': 'MA',
    'BOLL': 'BBANDS',
    '移动平均线': 'MA',
    '指数移动平均': 'EMA',
    '随机指标': 'KDJ',  # 中文名映射到KDJ
    '布林带': 'BBANDS',
    'MACD指标': 'MACD',
    '相对强弱指标': 'RSI'
    # 注意：移除了 'STOCH': 'KDJ' 映射，因为STOCH和KDJ是不同的指标
}


def resolve_indicator_alias(name: str) -> str:
    """解析指标别名"""
    return INDICATOR_ALIASES.get(name, name)


def fix_stoch_parameters(params: Dict) -> Dict:
    """修复STOCH指标参数，将timeperiod转换为正确的参数"""
    if not params:
        return {}

    fixed_params = params.copy()

    # 如果有timeperiod参数，将其转换为STOCH的正确参数
    if 'timeperiod' in fixed_params:
        timeperiod = fixed_params.pop('timeperiod', 14)
        # 设置STOCH的默认参数
        if 'fastk_period' not in fixed_params:
            fixed_params['fastk_period'] = max(5, timeperiod // 3)
        if 'slowk_period' not in fixed_params:
            fixed_params['slowk_period'] = 3
        if 'slowd_period' not in fixed_params:
            fixed_params['slowd_period'] = 3
        if 'slowk_matype' not in fixed_params:
            fixed_params['slowk_matype'] = 0
        if 'slowd_matype' not in fixed_params:
            fixed_params['slowd_matype'] = 0

    return fixed_params


class UnifiedIndicatorServiceEnhanced(UnifiedIndicatorService):
    """增强版统一指标服务 - 添加高级功能"""

    def __init__(self, db_path: str = UNIFIED_DB_PATH):
        super().__init__(db_path)

        # 高级功能支持
        self._backend_selection_strategy = "priority"  # 后端选择策略: priority, performance, accuracy, availability
        self._performance_monitor = {}  # 性能监控 {plugin_id: {avg_time, success_rate, etc.}}
        self._consistency_checker_enabled = False  # 结果一致性检查
        self._async_calculation_enabled = False  # 异步计算支持
        self._max_cache_size = 1000  # 最大缓存条目数
        self._cache_ttl_seconds = 3600  # 缓存生存时间（秒）

    def set_backend_selection_strategy(self, strategy: str) -> bool:
        """
        设置后端选择策略

        Args:
            strategy: 策略类型 - priority, performance, accuracy, availability

        Returns:
            bool: 设置是否成功
        """
        valid_strategies = ["priority", "performance", "accuracy", "availability"]
        if strategy in valid_strategies:
            self._backend_selection_strategy = strategy
            logger.info(f"后端选择策略已更新为: {strategy}")
            return True
        else:
            logger.error(f"无效的后端选择策略: {strategy}，有效选项: {valid_strategies}")
            return False

    def get_backend_selection_strategy(self) -> str:
        """获取当前后端选择策略"""
        return self._backend_selection_strategy

    def enable_consistency_checker(self, enabled: bool = True) -> None:
        """启用或禁用结果一致性检查"""
        self._consistency_checker_enabled = enabled
        logger.info(f"结果一致性检查已{'启用' if enabled else '禁用'}")

    def enable_async_calculation(self, enabled: bool = True) -> None:
        """启用或禁用异步计算"""
        self._async_calculation_enabled = enabled
        logger.info(f"异步计算已{'启用' if enabled else '禁用'}")

    def enable_multiprocess(self, enabled: bool = True, max_workers: int = None) -> None:
        """
        启用或禁用多进程计算
        
        Args:
            enabled: 是否启用
            max_workers: 最大进程数，默认为CPU核心数
        """
        self._multiprocess_enabled = enabled
        
        if enabled:
            if self._process_pool is None:
                self._process_pool = IndicatorProcessPool(max_workers=max_workers)
            logger.info(f"多进程计算已启用，进程数: {self._process_pool._max_workers}")
        else:
            if self._process_pool:
                self._process_pool.shutdown()
                self._process_pool = None
            logger.info("多进程计算已禁用")

    def calculate_parallel(self, indicators: List[Tuple[str, Dict]], df: pd.DataFrame, use_multiprocess: bool = None) -> pd.DataFrame:
        """
        并行计算多个指标
        
        Args:
            indicators: 指标列表 [(名称, 参数), ...]
            df: 输入数据
            use_multiprocess: 是否使用多进程（None则自动选择）
        
        Returns:
            pd.DataFrame: 计算结果
        """
        if use_multiprocess is None:
            use_multiprocess = self._multiprocess_enabled
        
        if use_multiprocess and self._process_pool:
            return self._process_pool.calculate_parallel(indicators, df, use_multiprocess=True)
        elif self._async_calculation_enabled and self._process_pool:
            return self._process_pool.calculate_parallel(indicators, df, use_multiprocess=False)
        else:
            return self.batch_calculate_indicators(indicators, df)

    async def calculate_indicator_async(self, name: str, df: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        异步计算单个指标
        
        Args:
            name: 指标名称
            df: 输入数据
            params: 参数
        
        Returns:
            pd.DataFrame: 计算结果
        """
        if self._process_pool is None:
            self._process_pool = IndicatorProcessPool()
        
        return await self._process_pool.calculate_async(name, df, params)

    async def batch_calculate_async(self, indicators: List[Tuple[str, Dict]], df: pd.DataFrame) -> pd.DataFrame:
        """
        异步批量计算指标
        
        Args:
            indicators: 指标列表
            df: 输入数据
        
        Returns:
            pd.DataFrame: 计算结果
        """
        if self._process_pool is None:
            self._process_pool = IndicatorProcessPool()
        
        return await self._process_pool.batch_calculate_async(indicators, df)

    def set_cache_config(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        """
        设置缓存配置

        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存生存时间（秒）
        """
        self._max_cache_size = max_size
        self._cache_ttl_seconds = ttl_seconds

        # 清理超出大小限制的缓存
        if len(self._calculation_cache) > max_size:
            # 保留最近使用的缓存项
            cache_items = list(self._calculation_cache.items())
            self._calculation_cache = dict(cache_items[-max_size:])

        logger.info(f"缓存配置已更新: 最大条目数={max_size}, TTL={ttl_seconds}秒")

    def get_performance_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        获取插件性能统计信息

        Returns:
            Dict: 插件性能统计 {plugin_id: {avg_time, success_rate, total_calls, etc.}}
        """
        return self._performance_monitor.copy()

    def _update_performance_monitor(self, plugin_id: str, calculation_time_ms: float, success: bool) -> None:
        """
        更新性能监控数据

        Args:
            plugin_id: 插件ID
            calculation_time_ms: 计算时间（毫秒）
            success: 是否成功
        """
        if plugin_id not in self._performance_monitor:
            self._performance_monitor[plugin_id] = {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_time_ms': 0.0,
                'avg_time_ms': 0.0,
                'success_rate': 0.0,
                'last_update': datetime.now()
            }

        stats = self._performance_monitor[plugin_id]
        stats['total_calls'] += 1
        stats['total_time_ms'] += calculation_time_ms

        if success:
            stats['successful_calls'] += 1
        else:
            stats['failed_calls'] += 1

        # 更新平均值
        stats['avg_time_ms'] = stats['total_time_ms'] / stats['total_calls']
        stats['success_rate'] = (stats['successful_calls'] / stats['total_calls']) * 100
        stats['last_update'] = datetime.now()

    def calculate_indicator_enhanced(self, name: str, df: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        增强版指标计算，包含性能监控和一致性检查

        Args:
            name: 指标名称
            df: 输入数据
            params: 参数

        Returns:
            Tuple[pd.DataFrame, Dict[str, Any]]: (结果数据, 元数据)
        """
        if params is None:
            params = {}

        metadata = {
            "indicator_name": name,
            "backend_strategy": self._backend_selection_strategy,
            "calculation_start_time": datetime.now(),
            "selected_plugin": None,
            "calculation_time_ms": 0.0,
            "consistency_report": None,
            "performance_stats": None
        }

        start_time = datetime.now()

        try:
            # 1. 选择最优插件
            optimal_plugin = self._select_optimal_plugin(name)

            if optimal_plugin:
                plugin_id, plugin_adapter = optimal_plugin
                metadata["selected_plugin"] = plugin_id

                # 2. 使用选定插件计算
                try:
                    from .indicator_extensions import StandardKlineData, IndicatorCalculationContext

                    kline_data = StandardKlineData.from_dataframe(df)
                    context = IndicatorCalculationContext(
                        symbol="enhanced_calc",
                        timeframe="D",
                        cache_enabled=self._cache_enabled
                    )

                    plugin_start_time = datetime.now()
                    result = plugin_adapter.calculate_indicator(name, kline_data, params, context)
                    plugin_calculation_time = (datetime.now() - plugin_start_time).total_seconds() * 1000

                    if result and not result.data.empty:
                        # 合并结果到原始DataFrame
                        result_df = df.copy()
                        for col in result.data.columns:
                            result_df[col] = result.data[col]

                        # 更新性能监控
                        self._update_performance_monitor(plugin_id, plugin_calculation_time, True)

                        # 一致性检查
                        if self._consistency_checker_enabled:
                            metadata["consistency_report"] = self._check_result_consistency(name, df, params, result_df)

                        metadata["calculation_time_ms"] = plugin_calculation_time
                        metadata["performance_stats"] = self._performance_monitor.get(plugin_id, {})

                        return result_df, metadata

                    else:
                        # 插件计算失败，更新性能监控
                        self._update_performance_monitor(plugin_id, plugin_calculation_time, False)

                except Exception as e:
                    logger.error(f"插件计算失败 {plugin_id}.{name}: {e}")
                    self._update_performance_monitor(plugin_id, 0, False)

            # 3. 回退到传统方法
            result_df = self.calculate_indicator(name, df, params)
            metadata["selected_plugin"] = "traditional"
            metadata["calculation_time_ms"] = (datetime.now() - start_time).total_seconds() * 1000

            return result_df, metadata

        except Exception as e:
            logger.error(f"增强指标计算失败 {name}: {e}")
            metadata["error"] = str(e)
            metadata["calculation_time_ms"] = (datetime.now() - start_time).total_seconds() * 1000
            return df.copy(), metadata

    def _select_optimal_plugin(self, indicator_name: str) -> Optional[Tuple[str, Any]]:
        """
        根据策略选择最优插件

        Args:
            indicator_name: 指标名称

        Returns:
            Optional[Tuple[str, Any]]: (plugin_id, plugin_adapter) 或 None
        """
        available_plugins = []

        # 找到支持该指标的所有插件
        for plugin_id, plugin_adapter in self._indicator_plugins.items():
            try:
                supported_indicators = plugin_adapter.get_supported_indicators()
                if indicator_name in supported_indicators:
                    available_plugins.append((plugin_id, plugin_adapter))
            except Exception as e:
                logger.warning(f"检查插件支持时出错 {plugin_id}: {e}")
                continue

        if not available_plugins:
            return None

        # 根据策略选择插件
        if self._backend_selection_strategy == "priority":
            # 按优先级排序
            return min(available_plugins, key=lambda x: self._plugin_priorities.get(x[0], 999))

        elif self._backend_selection_strategy == "performance":
            # 按性能排序（平均计算时间）
            def get_performance_score(plugin_tuple):
                plugin_id = plugin_tuple[0]
                if plugin_id in self._performance_monitor:
                    return self._performance_monitor[plugin_id]['avg_time_ms']
                return float('inf')  # 未知性能的插件排在最后

            return min(available_plugins, key=get_performance_score)

        elif self._backend_selection_strategy == "accuracy":
            # 按成功率排序
            def get_accuracy_score(plugin_tuple):
                plugin_id = plugin_tuple[0]
                if plugin_id in self._performance_monitor:
                    return -self._performance_monitor[plugin_id]['success_rate']  # 负数，因为要最大化成功率
                return 0  # 未知准确性的插件排在中间

            return min(available_plugins, key=get_accuracy_score)

        elif self._backend_selection_strategy == "availability":
            # 选择最近成功使用的插件
            def get_availability_score(plugin_tuple):
                plugin_id = plugin_tuple[0]
                if plugin_id in self._performance_monitor:
                    last_update = self._performance_monitor[plugin_id]['last_update']
                    return -(last_update.timestamp())  # 负数，因为要最大化时间戳
                return float('inf')

            return min(available_plugins, key=get_availability_score)

        else:
            # 默认按优先级
            return min(available_plugins, key=lambda x: self._plugin_priorities.get(x[0], 999))

    def _check_result_consistency(self, indicator_name: str, df: pd.DataFrame, params: Dict[str, Any],
                                  primary_result: pd.DataFrame) -> Dict[str, Any]:
        """
        检查结果一致性（使用多个后端计算同一指标并比较结果）

        Args:
            indicator_name: 指标名称
            df: 输入数据
            params: 参数
            primary_result: 主要结果

        Returns:
            Dict: 一致性检查报告
        """
        if not self._consistency_checker_enabled:
            return {"enabled": False}

        consistency_report = {
            "enabled": True,
            "primary_backend": None,
            "comparison_results": [],
            "consistency_score": 0.0,
            "warnings": []
        }

        try:
            # 获取所有支持该指标的插件
            available_plugins = []
            for plugin_id, plugin_adapter in self._indicator_plugins.items():
                try:
                    supported_indicators = plugin_adapter.get_supported_indicators()
                    if indicator_name in supported_indicators:
                        available_plugins.append((plugin_id, plugin_adapter))
                except:
                    continue

            if len(available_plugins) < 2:
                consistency_report["warnings"].append("可用插件数量不足，无法进行一致性检查")
                return consistency_report

            # 使用其他插件计算相同指标
            comparison_results = []
            for plugin_id, plugin_adapter in available_plugins:
                try:
                    # 转换数据格式并计算
                    from .indicator_extensions import StandardKlineData, IndicatorCalculationContext

                    kline_data = StandardKlineData.from_dataframe(df)
                    context = IndicatorCalculationContext(
                        symbol="consistency_check",
                        timeframe="D",
                        cache_enabled=False  # 不使用缓存以确保重新计算
                    )

                    result = plugin_adapter.calculate_indicator(indicator_name, kline_data, params, context)

                    if result and not result.data.empty:
                        comparison_results.append({
                            "plugin_id": plugin_id,
                            "backend": result.metadata.get('backend', 'Unknown'),
                            "data": result.data,
                            "calculation_time_ms": result.metadata.get('calculation_time_ms', 0)
                        })

                except Exception as e:
                    consistency_report["warnings"].append(f"插件 {plugin_id} 计算失败: {e}")
                    continue

            # 计算一致性分数
            if len(comparison_results) >= 2:
                consistency_scores = []

                for i, result1 in enumerate(comparison_results):
                    for j, result2 in enumerate(comparison_results[i+1:], i+1):
                        try:
                            # 比较数值结果（忽略NaN值）
                            data1 = result1["data"].select_dtypes(include=[np.number])
                            data2 = result2["data"].select_dtypes(include=[np.number])

                            if data1.shape == data2.shape:
                                # 计算相关系数
                                correlation = data1.corrwith(data2, axis=0).mean()
                                if not np.isnan(correlation):
                                    consistency_scores.append(correlation)

                        except Exception as e:
                            consistency_report["warnings"].append(f"比较 {result1['plugin_id']} 和 {result2['plugin_id']} 时出错: {e}")

                if consistency_scores:
                    consistency_report["consistency_score"] = np.mean(consistency_scores)

            consistency_report["comparison_results"] = comparison_results

        except Exception as e:
            consistency_report["warnings"].append(f"一致性检查异常: {e}")

        return consistency_report

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            Dict: 缓存统计信息
        """
        return {
            "cache_enabled": self._cache_enabled,
            "current_cache_size": len(self._calculation_cache),
            "max_cache_size": self._max_cache_size,
            "cache_ttl_seconds": self._cache_ttl_seconds,
            "cache_keys": list(self._calculation_cache.keys())[:10]  # 只显示前10个键
        }

    def preload_indicators(self, indicators: List[str], sample_data: pd.DataFrame) -> Dict[str, bool]:
        """
        预加载指标（预热）

        Args:
            indicators: 指标名称列表
            sample_data: 样本数据

        Returns:
            Dict[str, bool]: 预加载结果 {indicator_name: success}
        """
        preload_results = {}

        logger.info(f"开始预加载 {len(indicators)} 个指标...")

        for indicator_name in indicators:
            try:
                # 使用默认参数计算指标
                result = self.calculate_indicator(indicator_name, sample_data, {})
                preload_results[indicator_name] = not result.empty

                if preload_results[indicator_name]:
                    logger.debug(f" 指标预加载成功: {indicator_name}")
                else:
                    logger.warning(f" 指标预加载返回空结果: {indicator_name}")

            except Exception as e:
                preload_results[indicator_name] = False
                logger.error(f" 指标预加载失败 {indicator_name}: {e}")

        successful_count = sum(preload_results.values())
        logger.info(f"预加载完成: {successful_count}/{len(indicators)} 个指标成功")

        return preload_results


if __name__ == '__main__':
    # 测试统一服务
    logger.info("测试统一指标服务...")

    try:
        service = UnifiedIndicatorService()

        # 测试获取分类
        categories = service.get_all_categories()
        logger.info(f" 共有 {len(categories)} 个分类")

        # 测试获取指标
        indicators = service.get_all_indicators()
        logger.info(f" 共有 {len(indicators)} 个指标")

        # 测试获取形态
        patterns = service.get_all_patterns()
        logger.info(f" 共有 {len(patterns)} 个形态")

        service.close()
        logger.info("统一指标服务测试通过")

    except Exception as e:
        logger.info(f" 测试失败: {str(e)}")
        import traceback
        logger.info(traceback.format_exc())
