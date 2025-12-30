from loguru import logger
#!/usr/bin/env python3
"""
策略数据库管理器

提供策略的数据库存储、查询、修改、导入和删除功能
使用系统统一组件，避免硬编码
"""

import sqlite3
import json
import pickle
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import threading
from contextlib import contextmanager

# 使用系统统一组件
from core.adapters import get_config, get_data_validator
from .base_strategy import BaseStrategy, StrategySignal, StrategyParameter

class StrategyDatabaseManager:
    """策略数据库管理器"""

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库路径，如果为None则使用配置文件中的路径
        """
        self.logger = logger.bind(module=__name__)
        self.config = get_config()
        self.validator = get_data_validator()

        # 从配置获取数据库路径，避免硬编码
        if db_path is None:
            db_path = self.config.get('strategy_database', {}).get(
                'path', 'data/factorweave_system.sqlite')

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 线程锁确保数据库操作安全
        self._lock = threading.RLock()

        # 初始化数据库
        self._init_database()

        self.logger.info(f"策略数据库管理器初始化完成: {self.db_path}")

    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 策略基本信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    strategy_type TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '1.0.0',
                    author TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT DEFAULT '{}',
                    class_path TEXT NOT NULL
                )
            ''')

            # 策略参数表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_parameters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id INTEGER NOT NULL,
                    param_name TEXT NOT NULL,
                    param_value TEXT NOT NULL,
                    param_type TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    min_value TEXT DEFAULT NULL,
                    max_value TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE,
                    UNIQUE(strategy_id, param_name)
                )
            ''')

            # 策略执行历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id INTEGER NOT NULL,
                    execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_hash TEXT NOT NULL,
                    signals_count INTEGER DEFAULT 0,
                    execution_duration REAL DEFAULT 0.0,
                    success BOOLEAN DEFAULT 1,
                    error_message TEXT DEFAULT NULL,
                    performance_metrics TEXT DEFAULT '{}',
                    FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE
                )
            ''')

            # 策略信号表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id INTEGER NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    signal_type TEXT NOT NULL,
                    price REAL NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT DEFAULT '',
                    stop_loss REAL DEFAULT NULL,
                    take_profit REAL DEFAULT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (execution_id) REFERENCES strategy_executions (id) ON DELETE CASCADE
                )
            ''')

            # 创建索引提高查询性能
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies (name)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_strategies_type ON strategies (strategy_type)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_strategies_category ON strategies (category)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_executions_strategy ON strategy_executions (strategy_id)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_signals_execution ON strategy_signals (execution_id)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON strategy_signals (timestamp)')

            conn.commit()

    @contextmanager
    def _get_connection(self, auto_commit=True):
        """获取数据库连接的上下文管理器
        
        Args:
            auto_commit: 是否自动提交事务
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                if auto_commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()
                
    @contextmanager
    def transaction(self):
        """事务上下文管理器，用于执行多个相关的数据库操作"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"事务执行失败，已回滚: {e}")
                raise
            finally:
                conn.close()

    def register_strategy(self, strategy_class: type, metadata: Dict[str, Any]) -> int:
        """
        注册策略到数据库

        Args:
            strategy_class: 策略类
            metadata: 策略元数据

        Returns:
            策略ID
        """
        try:
            # 验证策略类
            if not issubclass(strategy_class, BaseStrategy):
                raise ValueError(f"策略类必须继承自BaseStrategy: {strategy_class}")

            # 提取策略信息
            strategy_name = metadata.get('name', strategy_class.__name__)
            class_path = f"{strategy_class.__module__}.{strategy_class.__name__}"

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 检查策略是否已存在
                cursor.execute(
                    'SELECT id FROM strategies WHERE name = ?', (strategy_name,))
                existing = cursor.fetchone()

                if existing:
                    # 更新现有策略
                    strategy_id = existing['id']
                    cursor.execute('''
                        UPDATE strategies SET
                            strategy_type = ?, version = ?, author = ?, description = ?,
                            category = ?, updated_at = CURRENT_TIMESTAMP, metadata = ?, class_path = ?
                        WHERE id = ?
                    ''', (
                        metadata.get('strategy_type', 'CUSTOM'),
                        metadata.get('version', '1.0.0'),
                        metadata.get('author', ''),
                        metadata.get('description', ''),
                        metadata.get('category', ''),
                        json.dumps(metadata),
                        class_path,
                        strategy_id
                    ))
                    self.logger.info(
                        f"更新策略: {strategy_name} (ID: {strategy_id})")
                else:
                    # 插入新策略
                    cursor.execute('''
                        INSERT INTO strategies (name, strategy_type, version, author, description, category, metadata, class_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        strategy_name,
                        metadata.get('strategy_type', 'CUSTOM'),
                        metadata.get('version', '1.0.0'),
                        metadata.get('author', ''),
                        metadata.get('description', ''),
                        metadata.get('category', ''),
                        json.dumps(metadata),
                        class_path
                    ))
                    strategy_id = cursor.lastrowid
                    self.logger.info(
                        f"注册新策略: {strategy_name} (ID: {strategy_id})")

                return strategy_id

        except Exception as e:
            self.logger.error(f"注册策略失败 {strategy_class}: {e}")
            raise

    def get_strategy_info(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        获取策略信息

        Args:
            strategy_name: 策略名称

        Returns:
            策略信息字典
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT * FROM strategies WHERE name = ? AND is_active = 1', (strategy_name,))
                row = cursor.fetchone()

                if row:
                    strategy_info = dict(row)
                    strategy_info['metadata'] = json.loads(
                        strategy_info['metadata'])

                    # 获取参数信息
                    cursor.execute('''
                        SELECT param_name, param_value, param_type, description, min_value, max_value
                        FROM strategy_parameters WHERE strategy_id = ?
                    ''', (strategy_info['id'],))

                    parameters = {}
                    for param_row in cursor.fetchall():
                        param_dict = dict(param_row)
                        param_name = param_dict['param_name']
                        parameters[param_name] = {
                            'value': self._deserialize_value(param_dict['param_value'], param_dict['param_type']),
                            'type': param_dict['param_type'],
                            'description': param_dict['description'],
                            'min_value': self._deserialize_value(param_dict['min_value'], param_dict['param_type']) if param_dict['min_value'] else None,
                            'max_value': self._deserialize_value(param_dict['max_value'], param_dict['param_type']) if param_dict['max_value'] else None
                        }

                    strategy_info['parameters'] = parameters
                    return strategy_info

                return None

        except Exception as e:
            self.logger.error(f"获取策略信息失败 {strategy_name}: {e}")
            return None

    def list_strategies(self, category: Optional[str] = None, strategy_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出策略

        Args:
            category: 策略分类过滤
            strategy_type: 策略类型过滤

        Returns:
            策略信息列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = 'SELECT * FROM strategies WHERE is_active = 1'
                params = []

                if category:
                    query += ' AND category = ?'
                    params.append(category)

                if strategy_type:
                    query += ' AND strategy_type = ?'
                    params.append(strategy_type)

                query += ' ORDER BY name'

                cursor.execute(query, params)
                strategies = []

                for row in cursor.fetchall():
                    strategy_info = dict(row)
                    strategy_info['metadata'] = json.loads(
                        strategy_info['metadata'])
                    strategies.append(strategy_info)

                return strategies

        except Exception as e:
            self.logger.error(f"列出策略失败: {e}")
            return []

    def save_strategy_parameters(self, strategy_name: str, parameters: Dict[str, StrategyParameter]):
        """
        保存策略参数

        Args:
            strategy_name: 策略名称
            parameters: 参数字典
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 获取策略ID
                cursor.execute(
                    'SELECT id FROM strategies WHERE name = ?', (strategy_name,))
                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"策略不存在: {strategy_name}")

                strategy_id = row['id']

                # 删除现有参数
                cursor.execute(
                    'DELETE FROM strategy_parameters WHERE strategy_id = ?', (strategy_id,))

                # 插入新参数
                for param_name, param in parameters.items():
                    cursor.execute('''
                        INSERT INTO strategy_parameters 
                        (strategy_id, param_name, param_value, param_type, description, min_value, max_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        strategy_id,
                        param_name,
                        self._serialize_value(param.value),
                        param.param_type.__name__,
                        param.description,
                        self._serialize_value(
                            param.min_value) if param.min_value is not None else None,
                        self._serialize_value(
                            param.max_value) if param.max_value is not None else None
                    ))

                conn.commit()
                self.logger.info(
                    f"保存策略参数: {strategy_name} ({len(parameters)}个参数)")

        except Exception as e:
            self.logger.error(f"保存策略参数失败 {strategy_name}: {e}")
            raise

    def save_execution_result(self, strategy_name: str, data_hash: str, signals: List[StrategySignal],
                              execution_time: float, success: bool, error_message: Optional[str] = None,
                              performance_metrics: Optional[Dict[str, Any]] = None) -> int:
        """
        保存策略执行结果

        Args:
            strategy_name: 策略名称
            data_hash: 数据哈希
            signals: 生成的信号列表
            execution_time: 执行时间
            success: 是否成功
            error_message: 错误信息
            performance_metrics: 性能指标

        Returns:
            执行记录ID
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 获取策略ID
                cursor.execute(
                    'SELECT id FROM strategies WHERE name = ?', (strategy_name,))
                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"策略不存在: {strategy_name}")

                strategy_id = row['id']

                # 插入执行记录
                cursor.execute('''
                    INSERT INTO strategy_executions 
                    (strategy_id, data_hash, signals_count, execution_duration, success, error_message, performance_metrics)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    strategy_id,
                    data_hash,
                    len(signals),
                    execution_time,
                    success,
                    error_message,
                    json.dumps(performance_metrics or {})
                ))

                execution_id = cursor.lastrowid

                # 插入信号记录
                if signals:
                    signal_data = []
                    for signal in signals:
                        signal_data.append((
                            execution_id,
                            signal.timestamp.isoformat(),
                            signal.signal_type.value,
                            signal.price,
                            signal.confidence,
                            signal.reason,
                            signal.stop_loss,
                            signal.take_profit,
                            json.dumps(signal.metadata if hasattr(
                                signal, 'metadata') else {})
                        ))

                    cursor.executemany('''
                        INSERT INTO strategy_signals 
                        (execution_id, timestamp, signal_type, price, confidence, reason, stop_loss, take_profit, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', signal_data)

                conn.commit()
                self.logger.info(
                    f"保存执行结果: {strategy_name} (执行ID: {execution_id}, 信号数: {len(signals)})")
                return execution_id

        except Exception as e:
            self.logger.error(f"保存执行结果失败 {strategy_name}: {e}")
            raise

    def delete_strategy(self, strategy_name: str) -> bool:
        """
        删除策略（软删除）

        Args:
            strategy_name: 策略名称

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    'UPDATE strategies SET is_active = 0 WHERE name = ?', (strategy_name,))

                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.info(f"删除策略: {strategy_name}")
                    return True
                else:
                    self.logger.warning(f"策略不存在: {strategy_name}")
                    return False

        except Exception as e:
            self.logger.error(f"删除策略失败 {strategy_name}: {e}")
            return False

    def import_strategies(self, strategies_data: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        批量导入策略

        Args:
            strategies_data: 策略数据列表

        Returns:
            (成功数量, 失败数量)
        """
        success_count = 0
        failure_count = 0

        for strategy_data in strategies_data:
            try:
                # 验证数据格式
                if not self.validator.validate_strategy_data(strategy_data):
                    self.logger.warning(
                        f"策略数据格式无效: {strategy_data.get('name', 'Unknown')}")
                    failure_count += 1
                    continue

                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # 插入或更新策略
                    cursor.execute('''
                        INSERT OR REPLACE INTO strategies 
                        (name, strategy_type, version, author, description, category, metadata, class_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        strategy_data['name'],
                        strategy_data.get('strategy_type', 'CUSTOM'),
                        strategy_data.get('version', '1.0.0'),
                        strategy_data.get('author', ''),
                        strategy_data.get('description', ''),
                        strategy_data.get('category', ''),
                        json.dumps(strategy_data.get('metadata', {})),
                        strategy_data.get('class_path', '')
                    ))

                    conn.commit()
                    success_count += 1

            except Exception as e:
                self.logger.error(
                    f"导入策略失败 {strategy_data.get('name', 'Unknown')}: {e}")
                failure_count += 1

        self.logger.info(f"策略导入完成: 成功 {success_count}, 失败 {failure_count}")
        return success_count, failure_count

    def export_strategies(self, strategy_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        导出策略数据

        Args:
            strategy_names: 要导出的策略名称列表，如果为None则导出所有策略

        Returns:
            策略数据列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if strategy_names:
                    # 导出指定策略
                    placeholders = ','.join(['?' for _ in strategy_names])
                    cursor.execute(f'''
                        SELECT * FROM strategies WHERE name IN ({placeholders})
                    ''', strategy_names)
                else:
                    # 导出所有策略
                    cursor.execute(
                        'SELECT * FROM strategies WHERE is_active = 1')

                strategies = cursor.fetchall()
                exported_data = []

                for strategy in strategies:
                    strategy_data = dict(strategy)

                    # 获取参数
                    cursor.execute('''
                        SELECT param_name, param_value, param_type, description, min_value, max_value
                        FROM strategy_parameters WHERE strategy_id = ?
                    ''', (strategy['id'],))
                    parameters = cursor.fetchall()

                    strategy_data['parameters'] = {
                        param['param_name']: {
                            'value': self._deserialize_value(param['param_value'], param['param_type']),
                            'type': param['param_type'],
                            'description': param['description'],
                            'min_value': self._deserialize_value(param['min_value'], param['param_type']) if param['min_value'] else None,
                            'max_value': self._deserialize_value(param['max_value'], param['param_type']) if param['max_value'] else None
                        }
                        for param in parameters
                    }

                    # 解析元数据
                    try:
                        strategy_data['metadata'] = json.loads(
                            strategy_data['metadata'])
                    except (json.JSONDecodeError, TypeError):
                        strategy_data['metadata'] = {}

                    exported_data.append(strategy_data)

                self.logger.info(f"成功导出 {len(exported_data)} 个策略")
                return exported_data

        except Exception as e:
            self.logger.error(f"导出策略失败: {e}")
            return []

    def export_strategy(self, strategy_name: str, output_path: Optional[str] = None) -> bool:
        """
        导出单个策略到文件

        Args:
            strategy_name: 策略名称
            output_path: 输出文件路径，如果为None则返回数据

        Returns:
            是否导出成功
        """
        try:
            # 导出策略数据
            strategy_data = self.export_strategies([strategy_name])
            if not strategy_data:
                self.logger.error(f"策略不存在或导出失败: {strategy_name}")
                return False

            strategy_info = strategy_data[0]

            if output_path:
                # 保存到文件
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(strategy_info, f, ensure_ascii=False,
                              indent=2, default=str)

                self.logger.info(f"策略已导出到文件: {output_path}")

            return True

        except Exception as e:
            self.logger.error(f"导出策略失败 {strategy_name}: {e}")
            return False

    def get_execution_history(self, strategy_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取策略执行历史

        Args:
            strategy_name: 策略名称
            limit: 返回记录数限制

        Returns:
            执行历史列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT e.*, s.name as strategy_name
                    FROM strategy_executions e
                    JOIN strategies s ON e.strategy_id = s.id
                    WHERE s.name = ? AND s.is_active = 1
                    ORDER BY e.execution_time DESC
                    LIMIT ?
                ''', (strategy_name, limit))

                executions = []
                for row in cursor.fetchall():
                    execution = dict(row)
                    execution['performance_metrics'] = json.loads(
                        execution['performance_metrics'])
                    executions.append(execution)

                return executions

        except Exception as e:
            self.logger.error(f"获取执行历史失败 {strategy_name}: {e}")
            return []

    def cleanup_old_data(self, days: int = 30):
        """
        清理旧数据

        Args:
            days: 保留天数
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 删除旧的执行记录和信号
                cursor.execute('''
                    DELETE FROM strategy_executions 
                    WHERE execution_time < datetime('now', '-{} days')
                '''.format(days))

                deleted_count = cursor.rowcount
                conn.commit()

                self.logger.info(f"清理旧数据完成: 删除 {deleted_count} 条执行记录")

        except Exception as e:
            self.logger.error(f"清理旧数据失败: {e}")

    def _serialize_value(self, value: Any) -> str:
        """序列化值"""
        if value is None:
            return ''
        return json.dumps(value)

    def _deserialize_value(self, value_str: str, param_type: str) -> Any:
        """反序列化值"""
        if not value_str:
            return None

        try:
            value = json.loads(value_str)

            # 类型转换
            if param_type == 'int':
                return int(value)
            elif param_type == 'float':
                return float(value)
            elif param_type == 'bool':
                return bool(value)
            elif param_type == 'str':
                return str(value)
            else:
                return value

        except (json.JSONDecodeError, ValueError, TypeError):
            return value_str

    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                stats = {}

                # 策略统计
                cursor.execute(
                    'SELECT COUNT(*) as count FROM strategies WHERE is_active = 1')
                stats['active_strategies'] = cursor.fetchone()['count']

                cursor.execute(
                    'SELECT COUNT(*) as count FROM strategies WHERE is_active = 0')
                stats['deleted_strategies'] = cursor.fetchone()['count']

                # 执行统计
                cursor.execute(
                    'SELECT COUNT(*) as count FROM strategy_executions')
                stats['total_executions'] = cursor.fetchone()['count']

                cursor.execute(
                    'SELECT COUNT(*) as count FROM strategy_executions WHERE success = 1')
                stats['successful_executions'] = cursor.fetchone()['count']

                # 信号统计
                cursor.execute(
                    'SELECT COUNT(*) as count FROM strategy_signals')
                stats['total_signals'] = cursor.fetchone()['count']

                # 数据库大小
                cursor.execute(
                    "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                stats['database_size_bytes'] = cursor.fetchone()['size']

                return stats

        except Exception as e:
            self.logger.error(f"获取数据库统计失败: {e}")
            return {}

# 全局单例实例
_strategy_db_manager = None
_db_lock = threading.Lock()

def get_strategy_database_manager() -> StrategyDatabaseManager:
    """获取策略数据库管理器单例"""
    global _strategy_db_manager

    if _strategy_db_manager is None:
        with _db_lock:
            if _strategy_db_manager is None:
                _strategy_db_manager = StrategyDatabaseManager()

    return _strategy_db_manager

def initialize_strategy_database(db_path: Optional[str] = None) -> StrategyDatabaseManager:
    """初始化策略数据库管理器"""
    global _strategy_db_manager

    with _db_lock:
        _strategy_db_manager = StrategyDatabaseManager(db_path)

    return _strategy_db_manager
