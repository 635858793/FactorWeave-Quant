#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
指标数据库模型
定义了指标系统的数据库表结构
"""

import os
import json
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, field, asdict
from core.database.unified_sqlite_access import UnifiedSQLiteAccess

@dataclass
class IndicatorParameter:
    """指标参数模型"""
    name: str
    description: str
    type: str
    default_value: Any
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    choices: Optional[List[Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndicatorParameter':
        """从字典创建参数对象"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class IndicatorImplementation:
    """指标实现模型"""
    engine: str  # 'talib', 'pandas', 'custom'
    function_name: str
    code: Optional[str] = None  # 自定义实现的代码
    is_default: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndicatorImplementation':
        """从字典创建实现对象"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class Indicator:
    """指标模型"""
    id: int
    name: str  # 指标英文名，如 'MACD'
    display_name: str  # 指标显示名，如 '指数平滑异同移动平均线'
    category_id: int  # 分类ID
    description: str  # 指标描述
    formula: Optional[str] = None  # 计算公式
    parameters: List[IndicatorParameter] = field(default_factory=list)
    implementations: List[IndicatorImplementation] = field(
        default_factory=list)
    output_names: List[str] = field(default_factory=list)  # 输出结果的名称列表
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: str = '1.0.0'
    is_builtin: bool = True  # 是否为内置指标

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['parameters'] = [p.to_dict() for p in self.parameters]
        result['implementations'] = [i.to_dict() for i in self.implementations]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Indicator':
        """从字典创建指标对象"""
        params = [IndicatorParameter.from_dict(
            p) for p in data.pop('parameters', [])]
        impls = [IndicatorImplementation.from_dict(
            i) for i in data.pop('implementations', [])]
        indicator = cls(**{k: v for k, v in data.items()
                        if k in cls.__annotations__})
        indicator.parameters = params
        indicator.implementations = impls
        return indicator

@dataclass
class IndicatorCategory:
    """指标分类模型"""
    id: int
    name: str  # 分类英文名
    display_name: str  # 分类显示名
    description: Optional[str] = None
    parent_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndicatorCategory':
        """从字典创建分类对象"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

class IndicatorDatabase:
    """指标数据库操作类"""

    def __init__(self, db_path: str):
        """
        初始化数据库连接

        参数:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.db = UnifiedSQLiteAccess.get_instance(db_path)
        self._init_db()

    def _init_db(self):
        """初始化数据库连接和表结构"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # 创建表
        self._create_tables()

    def _create_tables(self):
        """创建数据库表"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 创建指标分类表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES indicator_categories (id)
            )
            ''')

            # 创建指标表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicators (
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
                type TEXT NOT NULL,
                default_value TEXT NOT NULL,
                min_value TEXT,
                max_value TEXT,
                step TEXT,
                choices TEXT,
                FOREIGN KEY (indicator_id) REFERENCES indicators (id) ON DELETE CASCADE,
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
                code TEXT,
                is_default BOOLEAN DEFAULT 0,
                FOREIGN KEY (indicator_id) REFERENCES indicators (id) ON DELETE CASCADE,
                UNIQUE (indicator_id, engine)
            )
            ''')

    def close(self):
        """关闭数据库连接（UnifiedSQLiteAccess 使用单例，无需手动关闭）"""
        pass

    def __del__(self):
        """析构函数，确保数据库连接被关闭"""
        self.close()

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()

    # 指标分类相关方法

    def add_category(self, category: IndicatorCategory) -> int:
        """
        添加指标分类

        参数:
            category: 指标分类对象

        返回:
            int: 新增分类的ID
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO indicator_categories (name, display_name, description, parent_id)
                VALUES (?, ?, ?, ?)
                ''',
                (category.name, category.display_name,
                 category.description, category.parent_id)
            )
            # Auto-committed by UnifiedSQLiteAccess
            return cursor.lastrowid

    def get_category(self, category_id: int) -> Optional[IndicatorCategory]:
        """
        获取指标分类

        参数:
            category_id: 分类ID

        返回:
            IndicatorCategory: 指标分类对象，如果不存在则返回None
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM indicator_categories WHERE id = ?', (category_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return IndicatorCategory(
                id=row['id'],
                name=row['name'],
                display_name=row['display_name'],
                description=row['description'],
                parent_id=row['parent_id']
            )

    def get_category_by_name(self, name: str) -> Optional[IndicatorCategory]:
        """
        根据名称获取指标分类

        参数:
            name: 分类名称

        返回:
            IndicatorCategory: 指标分类对象，如果不存在则返回None
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM indicator_categories WHERE name = ?', (name,))
            row = cursor.fetchone()
            if not row:
                return None
            return IndicatorCategory(
                id=row['id'],
                name=row['name'],
                display_name=row['display_name'],
                description=row['description'],
                parent_id=row['parent_id']
            )

    def get_all_categories(self) -> List[IndicatorCategory]:
        """
        获取所有指标分类

        返回:
            List[IndicatorCategory]: 指标分类对象列表
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM indicator_categories')
            rows = cursor.fetchall()
            return [
                IndicatorCategory(
                    id=row['id'],
                    name=row['name'],
                    display_name=row['display_name'],
                    description=row['description'],
                    parent_id=row['parent_id']
                )
                for row in rows
            ]

    # 指标相关方法

    def add_indicator(self, indicator: Indicator) -> int:
        """
        添加指标

        参数:
            indicator: 指标对象

        返回:
            int: 新增指标的ID
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 插入指标基本信息
            cursor.execute(
                '''
                INSERT INTO indicators 
                (name, display_name, category_id, description, formula, output_names, version, is_builtin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    indicator.name,
                    indicator.display_name,
                    indicator.category_id,
                    indicator.description,
                    indicator.formula,
                    json.dumps(indicator.output_names),
                    indicator.version,
                    indicator.is_builtin
                )
            )
            indicator_id = cursor.lastrowid

            # 插入参数
            for param in indicator.parameters:
                cursor.execute(
                    '''
                    INSERT INTO indicator_parameters
                    (indicator_id, name, description, type, default_value, min_value, max_value, step, choices)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        indicator_id,
                        param.name,
                        param.description,
                        param.type,
                        json.dumps(param.default_value),
                        json.dumps(
                            param.min_value) if param.min_value is not None else None,
                        json.dumps(
                            param.max_value) if param.max_value is not None else None,
                        json.dumps(param.step) if param.step is not None else None,
                        json.dumps(
                            param.choices) if param.choices is not None else None
                    )
                )

            # 插入实现
            for impl in indicator.implementations:
                cursor.execute(
                    '''
                    INSERT INTO indicator_implementations
                    (indicator_id, engine, function_name, code, is_default)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        indicator_id,
                        impl.engine,
                        impl.function_name,
                        impl.code,
                        impl.is_default
                    )
                )

            # Auto-committed by UnifiedSQLiteAccess
            return indicator_id

    def get_indicator(self, indicator_id: int) -> Optional[Indicator]:
        """
        获取指标

        参数:
            indicator_id: 指标ID

        返回:
            Indicator: 指标对象，如果不存在则返回None
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 获取指标基本信息
            cursor.execute('SELECT * FROM indicators WHERE id = ?',
                           (indicator_id,))
            row = cursor.fetchone()
            if not row:
                return None

            # 获取参数
            cursor.execute(
                'SELECT * FROM indicator_parameters WHERE indicator_id = ?', (indicator_id,))
            param_rows = cursor.fetchall()
            parameters = []
            for param_row in param_rows:
                parameters.append(IndicatorParameter(
                    name=param_row['name'],
                    description=param_row['description'],
                    type=param_row['type'],
                    default_value=json.loads(param_row['default_value']),
                    min_value=json.loads(
                        param_row['min_value']) if param_row['min_value'] else None,
                    max_value=json.loads(
                        param_row['max_value']) if param_row['max_value'] else None,
                    step=json.loads(param_row['step']
                                    ) if param_row['step'] else None,
                    choices=json.loads(
                        param_row['choices']) if param_row['choices'] else None
                ))

            # 获取实现
            cursor.execute(
                'SELECT * FROM indicator_implementations WHERE indicator_id = ?', (indicator_id,))
            impl_rows = cursor.fetchall()
            implementations = []
            for impl_row in impl_rows:
                implementations.append(IndicatorImplementation(
                    engine=impl_row['engine'],
                    function_name=impl_row['function_name'],
                    code=impl_row['code'],
                    is_default=bool(impl_row['is_default'])
                ))

            return Indicator(
                id=row['id'],
                name=row['name'],
                display_name=row['display_name'],
                category_id=row['category_id'],
                description=row['description'],
                formula=row['formula'],
                parameters=parameters,
                implementations=implementations,
                output_names=json.loads(row['output_names']),
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                version=row['version'],
                is_builtin=bool(row['is_builtin'])
            )

    def get_indicator_by_name(self, name: str) -> Optional[Indicator]:
        """
        根据名称获取指标

        参数:
            name: 指标名称

        返回:
            Indicator: 指标对象，如果不存在则返回None
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM indicators WHERE name = ?', (name,))
            row = cursor.fetchone()
            if not row:
                return None
            return self.get_indicator(row['id'])

    def _batch_get_indicators(self, indicator_ids: List[int]) -> List[Indicator]:
        """
        批量获取指标（避免N+1查询）

        参数:
            indicator_ids: 指标ID列表

        返回:
            List[Indicator]: 指标对象列表
        """
        if not indicator_ids:
            return []

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            placeholders = ','.join(['?'] * len(indicator_ids))

            cursor.execute(
                f'SELECT * FROM indicators WHERE id IN ({placeholders})',
                indicator_ids
            )
            indicator_rows = {row['id']: row for row in cursor.fetchall()}

            cursor.execute(
                f'SELECT * FROM indicator_parameters WHERE indicator_id IN ({placeholders})',
                indicator_ids
            )
            param_rows = cursor.fetchall()

            cursor.execute(
                f'SELECT * FROM indicator_implementations WHERE indicator_id IN ({placeholders})',
                indicator_ids
            )
            impl_rows = cursor.fetchall()

        params_by_indicator = {}
        for pr in param_rows:
            params_by_indicator.setdefault(pr['indicator_id'], []).append(pr)

        impls_by_indicator = {}
        for ir in impl_rows:
            impls_by_indicator.setdefault(ir['indicator_id'], []).append(ir)

        indicators = []
        for indicator_id in indicator_ids:
            row = indicator_rows.get(indicator_id)
            if not row:
                continue

            parameters = []
            for param_row in params_by_indicator.get(indicator_id, []):
                parameters.append(IndicatorParameter(
                    name=param_row['name'],
                    description=param_row['description'],
                    type=param_row['type'],
                    default_value=json.loads(param_row['default_value']),
                    min_value=json.loads(param_row['min_value']) if param_row['min_value'] else None,
                    max_value=json.loads(param_row['max_value']) if param_row['max_value'] else None,
                    step=json.loads(param_row['step']) if param_row['step'] else None,
                    choices=json.loads(param_row['choices']) if param_row['choices'] else None
                ))

            implementations = []
            for impl_row in impls_by_indicator.get(indicator_id, []):
                implementations.append(IndicatorImplementation(
                    engine=impl_row['engine'],
                    function_name=impl_row['function_name'],
                    code=impl_row['code'],
                    is_default=bool(impl_row['is_default'])
                ))

            indicators.append(Indicator(
                id=row['id'],
                name=row['name'],
                display_name=row['display_name'],
                category_id=row['category_id'],
                description=row['description'],
                formula=row['formula'],
                parameters=parameters,
                implementations=implementations,
                output_names=json.loads(row['output_names']),
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                version=row['version'],
                is_builtin=bool(row['is_builtin'])
            ))

        return indicators

    def get_all_indicators(self) -> List[Indicator]:
        """
        获取所有指标

        返回:
            List[Indicator]: 指标对象列表
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM indicators')
            rows = cursor.fetchall()
            indicator_ids = [row['id'] for row in rows]
            return self._batch_get_indicators(indicator_ids)

    def get_indicators_by_category(self, category_id: int) -> List[Indicator]:
        """
        获取指定分类的所有指标

        参数:
            category_id: 分类ID

        返回:
            List[Indicator]: 指标对象列表
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM indicators WHERE category_id = ?', (category_id,))
            rows = cursor.fetchall()
            indicator_ids = [row['id'] for row in rows]
            return self._batch_get_indicators(indicator_ids)

    def update_indicator(self, indicator: Indicator) -> bool:
        """
        更新指标

        参数:
            indicator: 指标对象

        返回:
            bool: 是否更新成功
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 更新指标基本信息
            cursor.execute(
                '''
                UPDATE indicators 
                SET display_name = ?, category_id = ?, description = ?, formula = ?, 
                    output_names = ?, updated_at = CURRENT_TIMESTAMP, version = ?, is_builtin = ?
                WHERE id = ?
                ''',
                (
                    indicator.display_name,
                    indicator.category_id,
                    indicator.description,
                    indicator.formula,
                    json.dumps(indicator.output_names),
                    indicator.version,
                    indicator.is_builtin,
                    indicator.id
                )
            )

            if cursor.rowcount == 0:
                return False

            # 删除旧参数
            cursor.execute(
                'DELETE FROM indicator_parameters WHERE indicator_id = ?', (indicator.id,))

            # 插入新参数
            for param in indicator.parameters:
                cursor.execute(
                    '''
                    INSERT INTO indicator_parameters
                    (indicator_id, name, description, type, default_value, min_value, max_value, step, choices)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        indicator.id,
                        param.name,
                        param.description,
                        param.type,
                        json.dumps(param.default_value),
                        json.dumps(
                            param.min_value) if param.min_value is not None else None,
                        json.dumps(
                            param.max_value) if param.max_value is not None else None,
                        json.dumps(param.step) if param.step is not None else None,
                        json.dumps(
                            param.choices) if param.choices is not None else None
                    )
                )

            # 删除旧实现
            cursor.execute(
                'DELETE FROM indicator_implementations WHERE indicator_id = ?', (indicator.id,))

            # 插入新实现
            for impl in indicator.implementations:
                cursor.execute(
                    '''
                    INSERT INTO indicator_implementations
                    (indicator_id, engine, function_name, code, is_default)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        indicator.id,
                        impl.engine,
                        impl.function_name,
                        impl.code,
                        impl.is_default
                    )
                )

            # Auto-committed by UnifiedSQLiteAccess
            return True

    def delete_indicator(self, indicator_id: int) -> bool:
        """
        删除指标

        参数:
            indicator_id: 指标ID

        返回:
            bool: 是否删除成功
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM indicators WHERE id = ?', (indicator_id,))
            success = cursor.rowcount > 0
            # Auto-committed by UnifiedSQLiteAccess
            return success
