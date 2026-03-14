from loguru import logger
"""
形态管理器模块
负责管理K线形态的配置和识别
"""

import sqlite3
import os
import json
import threading
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from analysis.pattern_recognition import PatternRecognizer
from analysis.pattern_base import (
    BasePatternRecognizer, PatternConfig, PatternResult,
    PatternAlgorithmFactory, SignalType
)


class _CachedConnection:
    """数据库连接包装类，支持with语句并管理连接锁"""
    
    def __init__(self, connection, lock: threading.Lock):
        self._connection = connection
        self._lock = lock
    
    def __enter__(self):
        self._lock.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()
        return False
    
    def cursor(self):
        return self._connection.cursor()
    
    def commit(self):
        return self._connection.commit()
    
    def close(self):
        return self._connection.close()


class PatternManager:
    """形态管理器 - 增强版，支持数据库算法和统一接口"""
    
    _instance: Optional['PatternManager'] = None
    _lock = threading.Lock()
    _connection_lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> 'PatternManager':
        """获取单例实例"""
        return cls(db_path)
    
    @classmethod
    def reset_instance(cls):
        """重置单例实例（仅用于测试）"""
        with cls._lock:
            cls._instance = None

    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return
            
        if db_path is None:
            self.db_path = os.path.join(os.path.dirname(
                __file__), '..', 'data', 'factorweave_system.sqlite')
        else:
            self.db_path = db_path

        self.pattern_recognizer = PatternRecognizer()
        self._patterns_cache: Optional[List[PatternConfig]] = None
        self._pattern_by_name_cache: Dict[str, PatternConfig] = {}
        self._pattern_by_type_cache: Dict[str, PatternConfig] = {}
        self._effectiveness_cache: Dict[str, Tuple[List[Dict], float]] = {}
        self._cache_lock = threading.Lock()
        self._db_connection = None
        self._connection_acquired_time = 0
        self._connection_timeout = 60.0
        self._ensure_database_schema()
        self._initialized = True

    def _get_db_connection(self):
        """获取数据库连接（带连接缓存，复用连接提升性能）"""
        current_time = time.time()
        
        with self._connection_lock:
            if self._db_connection is not None:
                if current_time - self._connection_acquired_time < self._connection_timeout:
                    return _CachedConnection(self._db_connection, self._connection_lock)
                else:
                    try:
                        self._db_connection.close()
                    except:
                        pass
            
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._db_connection = conn
            self._connection_acquired_time = current_time
            return _CachedConnection(conn, self._connection_lock)

    def _release_connection(self):
        """释放数据库连接（仅在实际需要使用with语句时才调用）"""
        pass

    def _ensure_database_schema(self):
        """确保数据库表结构正确"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # 检查并添加新字段
                try:
                    cursor.execute(
                        'ALTER TABLE pattern_types ADD COLUMN algorithm_code TEXT')
                except sqlite3.OperationalError:
                    pass

                try:
                    cursor.execute(
                        'ALTER TABLE pattern_types ADD COLUMN parameters TEXT')
                except sqlite3.OperationalError:
                    pass

                try:
                    cursor.execute(
                        'ALTER TABLE pattern_types ADD COLUMN success_rate REAL DEFAULT 0.7')
                except sqlite3.OperationalError:
                    pass

                try:
                    cursor.execute(
                        'ALTER TABLE pattern_types ADD COLUMN risk_level TEXT DEFAULT "medium"')
                except sqlite3.OperationalError:
                    pass

                # 创建形态历史表（用于效果统计）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pattern_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pattern_type TEXT NOT NULL,
                        stock_code TEXT NOT NULL,
                        signal_type TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        trigger_date TEXT NOT NULL,
                        trigger_price REAL NOT NULL,
                        result_date TEXT,
                        result_price REAL,
                        return_rate REAL,
                        is_successful INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_pattern_history_type_date 
                    ON pattern_history(pattern_type, trigger_date)
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_pattern_history_date 
                    ON pattern_history(trigger_date)
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_pattern_history_stock 
                    ON pattern_history(stock_code)
                ''')

                # 创建通达信形态导入表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tdx_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        formula TEXT NOT NULL,
                        description TEXT,
                        category TEXT,
                        signal_type TEXT,
                        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
        except sqlite3.Error as e:
            logger.info(f"数据库 schema 检查失败: {e}")

    def get_pattern_configs(self, category: Optional[str] = None, signal_type: Optional[str] = None,
                            active_only: bool = True) -> List[PatternConfig]:
        """
        获取形态配置列表

        Args:
            category: 形态类别筛选
            signal_type: 信号类型筛选 
            active_only: 是否只返回激活的形态

        Returns:
            形态配置列表
        """
        import time
        logger.info("[DEBUG] PatternManager.get_pattern_configs 开始...")
        
        with self._cache_lock:
            logger.info(f"[DEBUG] _patterns_cache 是 None? {self._patterns_cache is None}")
            if self._patterns_cache is None:
                logger.info("[DEBUG] 调用 _load_all_patterns_from_db()...")
                start = time.time()
                self._load_all_patterns_from_db()
                logger.info(f"[DEBUG] _load_all_patterns_from_db() 完成，耗时: {time.time() - start:.2f}秒")

            logger.info(f"[DEBUG] 缓存中有 {len(self._patterns_cache) if self._patterns_cache else 0} 条")

            filtered_patterns = self._patterns_cache
            if filtered_patterns is None:
                return []

            if active_only:
                filtered_patterns = [p for p in filtered_patterns if p.is_active]

            if category:
                filtered_patterns = [
                    p for p in filtered_patterns if p.category == category]

            if signal_type:
                filtered_patterns = [
                    p for p in filtered_patterns if p.signal_type.value == signal_type]

            return filtered_patterns

    def _load_all_patterns_from_db(self):
        """从数据库加载所有形态并缓存（注意：此方法由get_pattern_configs调用，已持有锁）"""
        import time
        try:
            logger.info("[DEBUG] 开始连接数据库...")
            start = time.time()
            with self._get_db_connection() as conn:
                logger.info(f"[DEBUG] 数据库连接完成，耗时: {time.time() - start:.2f}秒")
                
                cursor = conn.cursor()
                logger.info("[DEBUG] 执行SQL查询...")
                start = time.time()
                cursor.execute("SELECT * FROM pattern_types ORDER BY category, name")
                rows = cursor.fetchall()
                logger.info(f"[DEBUG] SQL查询完成，耗时: {time.time() - start:.2f}秒，返回 {len(rows)} 条")

                patterns = []
                logger.info(f"[_load_all_patterns_from_db] 从数据库加载了 {len(rows)} 条形态配置。")

                for row in rows:
                    try:
                        raw_category = row[3]
                        parameters_raw = row[13] if len(row) > 13 and row[13] else '{}'
                        if isinstance(parameters_raw, str):
                            parameters = json.loads(parameters_raw)
                        elif isinstance(parameters_raw, (int, float)):
                            parameters = json.loads(str(parameters_raw)) if str(parameters_raw).strip() else {}
                        else:
                            parameters = parameters_raw if isinstance(parameters_raw, dict) else {}

                        signal_enum = SignalType.from_string(row[4])

                        patterns.append(PatternConfig(
                            id=row[0],
                            name=row[1],
                            english_name=row[2],
                            category=raw_category,
                            signal_type=signal_enum,
                            description=row[5],
                            min_periods=row[6],
                            max_periods=row[7],
                            confidence_threshold=row[8],
                            algorithm_code=row[12] if len(row) > 12 else "",
                            parameters=parameters,
                            is_active=bool(row[9]),
                            success_rate=row[15] if len(row) > 15 and row[15] is not None and row[15] > 0 else None,
                            risk_level=row[16] if len(row) > 16 and row[16] is not None else 'medium'
                        ))
                    except Exception as e:
                        logger.warning(f"解析形态配置失败: {e}")
                        continue
            self._patterns_cache = patterns
            logger.info(f"[_load_all_patterns_from_db] 成功解析并缓存了 {len(patterns)} 条形态配置。")
        except sqlite3.Error as e:
            logger.info(f"从数据库加载形态配置失败: {e}")
            self._patterns_cache = []

    def get_pattern_by_name(self, name: str) -> Optional[PatternConfig]:
        """
        根据名称获取形态配置

        Args:
            name: 形态名称（中文或英文）

        Returns:
            形态配置或None
        """
        if name in self._pattern_by_name_cache:
            return self._pattern_by_name_cache[name]
            
        if self._patterns_cache is None:
            self._load_all_patterns_from_db()

        if self._patterns_cache:
            for config in self._patterns_cache:
                if config.name == name or config.english_name == name:
                    self._pattern_by_name_cache[name] = config
                    return config
        return None

    def get_pattern_config(self, pattern_type: str) -> Optional[PatternConfig]:
        """
        根据形态类型获取单个形态的配置。

        Args:
            pattern_type: 形态的英文名或中文名。

        Returns:
            如果找到，则返回PatternConfig对象，否则返回None。
        """
        if pattern_type in self._pattern_by_type_cache:
            return self._pattern_by_type_cache[pattern_type]
            
        with self._cache_lock:
            if self._patterns_cache is None:
                self._load_all_patterns_from_db()

            normalized_type = pattern_type.strip().lower().replace('_', ' ')

            for config in self._patterns_cache:
                if config.english_name and config.english_name.lower().replace('_', ' ') == normalized_type:
                    self._pattern_by_type_cache[pattern_type] = config
                    return config
                if config.name.lower() == normalized_type:
                    self._pattern_by_type_cache[pattern_type] = config
                    return config

            self._pattern_by_type_cache[pattern_type] = None
            return None

    def get_patterns_by_category(self, category: str) -> List[PatternConfig]:
        """
        根据形态类别获取形态配置列表

        Args:
            category: 形态类别字符串

        Returns:
            形态配置列表
        """
        with self._cache_lock:
            if self._patterns_cache is None:
                self._load_all_patterns_from_db()

            return [
                config for config in self._patterns_cache
                if config.category == category
            ]

    def get_categories(self) -> List[str]:
        """获取所有形态类别"""
        with self._cache_lock:
            if self._patterns_cache is None:
                self._load_all_patterns_from_db()

            if self._patterns_cache:
                return sorted(list(set(p.category for p in self._patterns_cache if p.is_active)))
            return []

    def get_signal_types(self) -> List[str]:
        """获取所有信号类型"""
        with self._cache_lock:
            if self._patterns_cache is None:
                self._load_all_patterns_from_db()

            if self._patterns_cache:
                return sorted(list(set(p.signal_type.value for p in self._patterns_cache if p.is_active)))
            return []

    def add_pattern_config(self, name: str, english_name: str, category: str,
                           signal_type: str, description: str,
                           algorithm_code: str = "", parameters: Dict = None,
                           **kwargs) -> Optional[int]:
        """
        添加新的形态配置

        Args:
            name: 中文名称
            english_name: 英文名称
            category: 形态类别
            signal_type: 信号类型
            description: 描述
            algorithm_code: 算法代码
            parameters: 参数字典
            **kwargs: 其他参数

        Returns:
            新增记录的ID，失败返回None
        """
        try:
            with self._get_db_connection() as conn:
                min_periods = kwargs.get('min_periods', 5)
                max_periods = kwargs.get('max_periods', 60)
                confidence_threshold = kwargs.get('confidence_threshold', 0.5)
                is_active = kwargs.get('is_active', True)

                parameters_json = json.dumps(parameters or {})

                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO pattern_types 
                    (name, english_name, category, signal_type, description, 
                     min_periods, max_periods, confidence_threshold, is_active,
                     algorithm_code, parameters)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, english_name, category, signal_type, description,
                      min_periods, max_periods, confidence_threshold, is_active,
                      algorithm_code, parameters_json))

                pattern_id = cursor.lastrowid
                conn.commit()

                # 清除缓存
                self.invalidate_cache()

                return pattern_id
        except sqlite3.Error as e:
            logger.info(f"添加形态配置失败: {e}")
            return None

    def update_pattern_config(self, pattern_id: int, **kwargs) -> bool:
        """
        更新形态配置

        Args:
            pattern_id: 形态ID
            **kwargs: 要更新的字段

        Returns:
            是否成功
        """
        try:
            with self._get_db_connection() as conn:
                # 构建更新语句
                update_fields = []
                values = []

                for field, value in kwargs.items():
                    if field == 'parameters' and isinstance(value, dict):
                        value = json.dumps(value)
                    update_fields.append(f"{field} = ?")
                    values.append(value)

                if not update_fields:
                    return False

                values.append(pattern_id)
                query = f"UPDATE pattern_types SET {', '.join(update_fields)} WHERE id = ?"

                cursor = conn.cursor()
                cursor.execute(query, values)
                conn.commit()

                # 清除缓存
                self.invalidate_cache()

                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.info(f"更新形态配置失败: {e}")
            return False

    def delete_pattern_config(self, pattern_id: int) -> bool:
        """
        删除形态配置

        Args:
            pattern_id: 形态ID

        Returns:
            是否成功
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM pattern_types WHERE id = ?", (pattern_id,))
                conn.commit()

                # 清除缓存
                self.invalidate_cache()

                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.info(f"删除形态配置失败: {e}")
            return False

    def import_tdx_formula(self, name: str, formula: str) -> bool:
        """导入通达信公式

        Args:
            name: 形态名称
            formula: 通达信公式代码

        Returns:
            是否导入成功
        """
        try:
            # 转换通达信公式为Python代码
            python_code = self._convert_tdx_formula(formula)

            if not python_code:
                return False

            # 创建新的形态配置
            config = PatternConfig(
                id=0,  # 将由数据库自动分配
                name=name,
                english_name=name.lower().replace(' ', '_'),
                category=PatternCategory.COMPLEX,
                signal_type=SignalType.NEUTRAL,
                description=f"通达信导入的形态: {name}",
                min_periods=1,
                max_periods=100,
                confidence_threshold=0.5,
                algorithm_code=python_code,
                parameters={},
                is_active=True
            )

            # 保存到数据库
            return self._save_pattern_config(config)

        except Exception as e:
            logger.info(f"导入通达信公式失败: {e}")
            return False

    def _save_pattern_config(self, config: PatternConfig) -> bool:
        """保存形态配置到数据库"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO pattern_types (
                        name, english_name, category, signal_type, description,
                        min_periods, max_periods, confidence_threshold,
                        algorithm_code, parameters, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    config.name,
                    config.english_name,
                    config.category.value,
                    config.signal_type.value,
                    config.description,
                    config.min_periods,
                    config.max_periods,
                    config.confidence_threshold,
                    config.algorithm_code,
                    json.dumps(config.parameters),
                    config.is_active
                ))
            # 清除缓存
            self.invalidate_cache()
            return True

        except sqlite3.Error as e:
            logger.info(f"保存形态配置失败: {e}")
            return False

    def _convert_tdx_formula(self, formula: str) -> str:
        """
        转换通达信公式为Python代码

        Args:
            formula: 通达信公式

        Returns:
            Python算法代码
        """
        # 这是一个简化的转换器，实际应用中需要更复杂的解析
        # 通达信常用函数映射
        tdx_mappings = {
            'C': "k['close']",
            'O': "k['open']",
            'H': "k['high']",
            'L': "k['low']",
            'V': "k['volume']",
            'REF(': 'kdata.iloc[i-',
            'MA(': 'kdata.rolling(',
            'AND': 'and',
            'OR': 'or',
            'NOT': 'not',
        }

        # 基础转换
        python_code = formula
        for tdx_func, py_func in tdx_mappings.items():
            python_code = python_code.replace(tdx_func, py_func)

        # 生成完整的算法代码模板
        algorithm_template = f'''
# 通达信公式转换: {formula}
for i in range(len(kdata)):
    k = kdata.iloc[i]
    
    try:
        # 转换后的条件判断
        condition = {python_code}
        
        if condition:
            confidence = 0.6  # 默认置信度
            datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
            
            result = create_result(
                pattern_type='tdx_pattern',
                signal_type=SignalType.NEUTRAL,
                confidence=confidence,
                index=i,
                price=k['close'],
                datetime_val=datetime_val,
                extra_data={{'original_formula': '{formula}'}}
            )
            results.append(result)
    except Exception as e:
        # 忽略单个K线的计算错误
        continue
'''

        return algorithm_template

    def get_pattern_statistics(self, kdata, pattern_name: str = None) -> Dict:
        """
        获取形态统计信息

        Args:
            kdata: K线数据
            pattern_name: 特定形态名称，None表示所有形态

        Returns:
            统计信息字典
        """
        if self._patterns_cache is None:
            self._load_all_patterns_from_db()

        try:
            # 识别形态
            if pattern_name:
                patterns = self.identify_all_patterns(kdata, [pattern_name])
            else:
                patterns = self.identify_all_patterns(kdata)

            if not patterns:
                return {
                    'total_patterns': 0,
                    'by_category': {},
                    'by_signal': {},
                    'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0}
                }

            # 统计分析
            stats = {
                'total_patterns': len(patterns),
                'by_category': {},
                'by_signal': {},
                'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0}
            }

            for pattern in patterns:
                # 按类别统计
                category = pattern.get('pattern_category', '未分类')
                stats['by_category'][category] = stats['by_category'].get(
                    category, 0) + 1

                # 按信号统计
                signal = pattern.get('signal', 'neutral')
                signal_cn = {'buy': '买入', 'sell': '卖出',
                             'neutral': '中性'}.get(signal, signal)
                stats['by_signal'][signal_cn] = stats['by_signal'].get(
                    signal_cn, 0) + 1

                # 按置信度统计
                confidence = pattern.get('confidence', 0)
                if confidence >= 0.8:
                    stats['confidence_distribution']['high'] += 1
                elif confidence >= 0.5:
                    stats['confidence_distribution']['medium'] += 1
                else:
                    stats['confidence_distribution']['low'] += 1

            return stats

        except Exception as e:
            logger.info(f"获取形态统计失败: {e}")
            return {
                'total_patterns': 0,
                'by_category': {},
                'by_signal': {},
                'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0}
            }

    def get_pattern_effectiveness(self, pattern_type: str, days: int = 30) -> Dict:
        """
        获取形态有效性统计

        Args:
            pattern_type: 形态类型
            days: 统计天数

        Returns:
            有效性统计
        """
        cache_key = f"{pattern_type}_{days}"
        if cache_key in self._effectiveness_cache:
            cached_data, cached_time = self._effectiveness_cache[cache_key]
            if time.time() - cached_time < 300:
                return cached_data
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_count,
                        AVG(return_rate) as avg_return,
                        COUNT(CASE WHEN is_successful = 1 THEN 1 END) as success_count,
                        AVG(confidence) as avg_confidence
                    FROM pattern_history 
                    WHERE pattern_type = ? 
                    AND trigger_date >= date('now', '-{} days')
                '''.format(days), (pattern_type,))

                row = cursor.fetchone()
                if row and row[0] > 0:
                    result = {
                        'total_signals': row[0],
                        'success_rate': (row[2] / row[0]) * 100 if row[0] > 0 else 0,
                        'average_return': row[1] or 0,
                        'average_confidence': row[3] or 0
                    }
                else:
                    result = {
                        'total_signals': 0,
                        'success_rate': 0,
                        'average_return': 0,
                        'average_confidence': 0
                    }
                
                self._effectiveness_cache[cache_key] = (result, time.time())
                return result

        except sqlite3.Error as e:
            logger.info(f"获取形态有效性失败: {e}")
            return {
                'total_signals': 0,
                'success_rate': 0,
                'average_return': 0,
                'average_confidence': 0
            }

    def record_pattern_result(self, pattern_type: str, stock_code: str,
                              signal_type: str, confidence: float,
                              trigger_date: str, trigger_price: float,
                              result_date: str = None, result_price: float = None,
                              max_total_records: int = 10000) -> bool:
        """
        记录形态识别结果（用于效果统计）

        Args:
            pattern_type: 形态类型
            stock_code: 股票代码
            signal_type: 信号类型
            confidence: 置信度
            trigger_date: 触发日期
            trigger_price: 触发价格
            result_date: 结果日期
            result_price: 结果价格
            max_total_records: 最大总记录数，默认10000

        Returns:
            是否成功
        """
        try:
            with self._get_db_connection() as conn:
                # 计算收益率和成功标志
                return_rate = None
                is_successful = None

                if result_price is not None and trigger_price > 0:
                    return_rate = (result_price - trigger_price) / \
                        trigger_price * 100

                    if signal_type == 'buy':
                        is_successful = 1 if return_rate > 0 else 0
                    elif signal_type == 'sell':
                        is_successful = 1 if return_rate < 0 else 0
                    else:
                        is_successful = 1 if abs(
                            return_rate) < 2 else 0

                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM pattern_history')
                total_count = cursor.fetchone()[0]

                if total_count >= max_total_records:
                    excess = total_count - max_total_records + 1
                    cursor.execute('''
                        DELETE FROM pattern_history
                        WHERE id IN (
                            SELECT id FROM pattern_history
                            ORDER BY trigger_date ASC, created_at ASC
                            LIMIT ?
                        )
                    ''', (excess,))
                    logger.info(f"已达到最大记录数{max_total_records}，删除{excess}条最旧记录")

                cursor.execute('''
                    INSERT INTO pattern_history 
                    (pattern_type, stock_code, signal_type, confidence, 
                     trigger_date, trigger_price, result_date, result_price, 
                     return_rate, is_successful)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (pattern_type, stock_code, signal_type, confidence,
                      trigger_date, trigger_price, result_date, result_price,
                      return_rate, is_successful))
                return True
        except sqlite3.Error as e:
            logger.info(f"记录形态结果失败: {e}")
            return False

    def get_recommended_patterns(self, top_n: int = 10) -> List[Dict]:
        """
        获取推荐形态（基于历史效果）

        Args:
            top_n: 返回前N个推荐形态

        Returns:
            推荐形态列表
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        pattern_type,
                        COUNT(*) as total_count,
                        AVG(return_rate) as avg_return,
                        COUNT(CASE WHEN is_successful = 1 THEN 1 END) * 1.0 / COUNT(*) as success_rate,
                        AVG(confidence) as avg_confidence
                    FROM pattern_history 
                    WHERE trigger_date >= date('now', '-90 days')
                    GROUP BY pattern_type
                    HAVING total_count >= 5
                    ORDER BY success_rate DESC, avg_return DESC
                    LIMIT ?
                ''', (top_n,))

                recommendations = []
                for row in cursor.fetchall():
                    recommendations.append({
                        'pattern_type': row[0],
                        'total_signals': row[1],
                        'average_return': round(row[2] or 0, 2),
                        'success_rate': round(row[3] * 100, 2),
                        'average_confidence': round(row[4] or 0, 3),
                        'recommendation_score': round((row[3] * 0.6 + (row[2] or 0) * 0.004 + (row[4] or 0) * 0.4), 3)
                    })

                return recommendations
        except sqlite3.Error as e:
            logger.info(f"获取推荐形态失败: {e}")
            return []

    def cleanup_old_records(self, days: int = 90, min_samples: int = 20, max_delete: int = 1000) -> Dict:
        """
        清理过期的形态历史记录（智能清理）

        Args:
            days: 保留天数，默认90天
            min_samples: 每种形态最低保留样本数，默认20条
            max_delete: 每次最多删除条数，避免长事务，默认1000

        Returns:
            清理结果统计
        """
        result = {
            'total_deleted': 0,
            'by_pattern': {},
            'error': None
        }

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT pattern_type, COUNT(*) as count
                    FROM pattern_history
                    GROUP BY pattern_type
                ''')
                pattern_counts = {row[0]: row[1] for row in cursor.fetchall()}

                for pattern_type, total_count in pattern_counts.items():
                    if total_count <= min_samples:
                        continue

                    to_delete = min(total_count - min_samples, max_delete)

                    cursor.execute('''
                        DELETE FROM pattern_history
                        WHERE id IN (
                            SELECT id FROM pattern_history
                            WHERE pattern_type = ?
                            AND trigger_date < date('now', '-' || ? || ' days')
                            ORDER BY trigger_date ASC
                            LIMIT ?
                        )
                    ''', (pattern_type, days, to_delete))

                    deleted = cursor.rowcount
                    result['total_deleted'] += deleted
                    result['by_pattern'][pattern_type] = deleted

                conn.commit()
                logger.info(f"历史数据清理完成: 删除{result['total_deleted']}条记录")

        except sqlite3.Error as e:
            result['error'] = str(e)
            logger.error(f"清理历史记录失败: {e}")

        return result

    def get_training_data_summary(self) -> Dict:
        """
        获取训练数据摘要（用于AI训练数据管理）

        Returns:
            训练数据统计信息
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM pattern_history')
                total_records = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT pattern_type, COUNT(*) as count
                    FROM pattern_history
                    GROUP BY pattern_type
                    ORDER BY count DESC
                ''')
                pattern_distribution = [{'pattern': row[0], 'count': row[1]} for row in cursor.fetchall()]

                cursor.execute('SELECT AVG(confidence) FROM pattern_history')
                avg_confidence = cursor.fetchone()[0] or 0

                cursor.execute('''
                    SELECT signal_type, COUNT(*) as count
                    FROM pattern_history
                    GROUP BY signal_type
                ''')
                signal_distribution = {row[0]: row[1] for row in cursor.fetchall()}

                return {
                    'total_records': total_records,
                    'pattern_distribution': pattern_distribution,
                    'average_confidence': round(avg_confidence, 3),
                    'signal_distribution': signal_distribution,
                    'valid_for_training': sum(1 for p in pattern_distribution if p['count'] >= 30)
                }

        except sqlite3.Error as e:
            logger.error(f"获取训练数据摘要失败: {e}")
            return {
                'total_records': 0,
                'pattern_distribution': [],
                'average_confidence': 0,
                'signal_distribution': {},
                'valid_for_training': 0
            }

    def get_pattern_effectiveness_trend(self, pattern_type: str, months: int = 6) -> List[Dict]:
        """
        获取形态效果趋势（用于形态优化建议）

        Args:
            pattern_type: 形态类型
            months: 追溯月份数，默认6个月

        Returns:
            月度统计数据列表
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        strftime('%Y-%m', trigger_date) as month,
                        COUNT(*) as total_count,
                        COUNT(CASE WHEN is_successful = 1 THEN 1 END) as success_count,
                        AVG(return_rate) as avg_return,
                        AVG(confidence) as avg_confidence
                    FROM pattern_history
                    WHERE pattern_type = ?
                    AND trigger_date >= date('now', '-' || ? || ' months')
                    GROUP BY month
                    ORDER BY month ASC
                ''', (pattern_type, months))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'month': row[0],
                        'total_count': row[1],
                        'success_count': row[2],
                        'success_rate': round(row[2] / row[1] * 100, 2) if row[1] > 0 else 0,
                        'avg_return': round(row[3] or 0, 2),
                        'avg_confidence': round(row[4] or 0, 3)
                    })

                return results

        except sqlite3.Error as e:
            logger.error(f"获取形态效果趋势失败: {e}")
            return []

    def get_all_patterns(self, active_only: bool = True) -> List[PatternConfig]:
        """
        获取所有形态配置（兼容优化系统接口）

        Args:
            active_only: 是否只返回激活的形态

        Returns:
            形态配置列表
        """
        return self.get_pattern_configs(active_only=active_only)

    def invalidate_cache(self):
        """使缓存失效"""
        with self._cache_lock:
            self._patterns_cache = None
