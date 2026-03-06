from loguru import logger
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
指标计算服务（统一版）
基于统一数据库的指标计算服务，提供完整的指标计算功能
"""

import atexit
from core.unified_indicator_service import (
    UnifiedIndicatorService,
    get_unified_service,
    TALIB_AVAILABLE
)
import os
import sys
import json
import traceback
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union, Tuple
from functools import lru_cache

# Loguru日志已在全局配置，无需额外设置
# logger = logger  # 已在文件开头导入
# Loguru自动处理所有日志配置

# 统一数据库文件路径
UNIFIED_DB_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'factorweave_system.sqlite')


class IndicatorService:
    """指标计算服务类（统一版 - 使用统一数据库）"""

    def __init__(self, db_path: str = UNIFIED_DB_PATH):
        """
        初始化指标计算服务

        参数:
            db_path: 统一数据库文件路径（保留用于兼容性，实际使用全局单例）
        """
        self.db_path = db_path
        # 使用统一指标服务（全局单例，不需要传递db_path）
        try:
            self.unified_service = get_unified_service()
            logger.info(f"✓ 统一指标服务初始化成功")
        except Exception as e:
            logger.error(f"✗ 统一指标服务初始化失败: {e}")
            logger.error(traceback.format_exc())
            self.unified_service = None
        self._custom_functions = {}  # 存储自定义函数

    def close(self):
        """关闭数据库连接（线程本地实例不需要关闭）"""
        pass

    def __del__(self):
        """析构函数"""
        pass

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()

    @lru_cache(maxsize=128)
    def get_indicator(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取指标定义

        参数:
            name: 指标名称

        返回:
            Dict: 指标对象，如果不存在则返回None
        """
        return self.unified_service.get_indicator(name)

    def get_all_indicators(self) -> List[Dict[str, Any]]:
        """
        获取所有指标定义

        返回:
            List[Dict]: 指标对象列表
        """
        return self.unified_service.get_all_indicators()

    def get_indicators_by_category(self, category_name: str) -> List[Dict[str, Any]]:
        """
        获取指定分类的所有指标

        参数:
            category_name: 分类名称

        返回:
            List[Dict]: 指标对象列表
        """
        return self.unified_service.get_indicators_by_category(category_name)

    def calculate_indicator(self, name: str, data: pd.DataFrame, **params) -> Union[pd.DataFrame, pd.Series, Dict[str, Any]]:
        """
        计算指标

        参数:
            name: 指标名称
            data: K线数据
            **params: 指标参数

        返回:
            计算结果
        """
        if self.unified_service is None:
            logger.error(f"✗ 统一指标服务未初始化，无法计算指标: {name}")
            raise RuntimeError("统一指标服务未初始化")
        return self.unified_service.calculate_indicator(name, data, params if params else {})

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """获取所有分类"""
        return self.unified_service.get_all_categories()

    def get_patterns_by_category(self, category_name: str) -> List[Dict[str, Any]]:
        """获取指定分类的所有形态"""
        return self.unified_service.get_patterns_by_category(category_name)

    def calculate_pattern(self, name: str, data: pd.DataFrame, **params) -> Union[pd.DataFrame, pd.Series, Dict[str, Any]]:
        """计算形态识别"""
        return self.unified_service.calculate_pattern(name, data, **params)

    def batch_calculate_indicators(self, indicators: List[str], data: pd.DataFrame, params_dict: Optional[Dict[str, Dict]] = None) -> pd.DataFrame:
        """批量计算指标"""
        indicator_tuples = []
        params_dict = params_dict or {}
        for indicator in indicators:
            params = params_dict.get(indicator, {})
            indicator_tuples.append((indicator, params))
        return self.unified_service.batch_calculate_indicators(indicator_tuples, data)

    def get_indicator_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指标元数据（兼容性方法）"""
        return self.get_indicator(name)

    def get_all_indicators_metadata(self) -> List[Dict[str, Any]]:
        """获取所有指标元数据（兼容性方法）"""
        return self.get_all_indicators()

    def get_indicator_categories(self) -> List[Dict[str, Any]]:
        """获取指标分类（兼容性方法）"""
        return self.get_all_categories()


# 全局服务实例
_global_service = None


def get_indicator_service() -> IndicatorService:
    """获取全局指标服务实例"""
    global _global_service
    if _global_service is None:
        _global_service = IndicatorService()
    return _global_service

# 兼容性函数导出


def calculate_indicator(name: str, data: pd.DataFrame, **params) -> Union[pd.DataFrame, pd.Series, Dict[str, Any]]:
    """计算指标（兼容性函数）"""
    service = get_indicator_service()
    return service.calculate_indicator(name, data, **params)


def get_indicator_metadata(name: str) -> Optional[Dict[str, Any]]:
    """获取指标元数据（兼容性函数）"""
    service = get_indicator_service()
    return service.get_indicator_metadata(name)


def get_all_indicators_metadata() -> List[Dict[str, Any]]:
    """获取所有指标元数据（兼容性函数）"""
    service = get_indicator_service()
    return service.get_all_indicators_metadata()


def get_indicator_categories() -> List[Dict[str, Any]]:
    """获取指标分类（兼容性函数）"""
    service = get_indicator_service()
    return service.get_indicator_categories()


def get_indicators_by_category(category_name: str) -> List[Dict[str, Any]]:
    """获取指定分类的指标（兼容性函数）"""
    service = get_indicator_service()
    return service.get_indicators_by_category(category_name)


# 导入指标别名和解析函数
try:
    from core.unified_indicator_service import INDICATOR_ALIASES, resolve_indicator_alias
except ImportError:
    logger.warning("无法导入指标别名，使用空字典")
    INDICATOR_ALIASES = {}

    def resolve_indicator_alias(name: str) -> str:
        """解析指标别名"""
        return INDICATOR_ALIASES.get(name.upper(), name)

# 批量计算函数


def batch_calculate_indicators(indicators: List[str], data: pd.DataFrame, params_dict: Optional[Dict[str, Dict]] = None) -> pd.DataFrame:
    """批量计算指标（兼容性函数）"""
    service = get_indicator_service()
    return service.batch_calculate_indicators(indicators, data, params_dict)

# 形态识别函数


def calculate_pattern(name: str, data: pd.DataFrame, **params) -> Union[pd.DataFrame, pd.Series, Dict[str, Any]]:
    """计算形态识别（兼容性函数）"""
    service = get_indicator_service()
    return service.calculate_pattern(name, data, **params)


def get_patterns_by_category(category_name: str) -> List[Dict[str, Any]]:
    """获取指定分类的形态（兼容性函数）"""
    service = get_indicator_service()
    return service.get_patterns_by_category(category_name)

# 清理函数


def cleanup_indicator_service():
    """清理指标服务资源"""
    global _global_service
    if _global_service:
        _global_service.close()
        _global_service = None


# 模块清理
atexit.register(cleanup_indicator_service)

# 兼容性别名
get_indicator = get_indicator_metadata
get_all_indicators = get_all_indicators_metadata
get_categories = get_indicator_categories

# 导出所有公共接口
__all__ = [
    'IndicatorService',
    'get_indicator_service',
    'calculate_indicator',
    'get_indicator_metadata',
    'get_all_indicators_metadata',
    'get_indicator_categories',
    'get_indicators_by_category',
    'batch_calculate_indicators',
    'calculate_pattern',
    'get_patterns_by_category',
    'INDICATOR_ALIASES',
    'resolve_indicator_alias',
    'TALIB_AVAILABLE',
    'cleanup_indicator_service',
    # 兼容性别名
    'get_indicator',
    'get_all_indicators',
    'get_categories',
]


def get_talib_category():
    """
    获取TA-Lib指标分类

    Returns:
        Dict: 指标分类字典
    """
    try:
        # TA-Lib指标分类
        categories = {
            'Overlap Studies': [
                'BBANDS', 'DEMA', 'EMA', 'HT_TRENDLINE', 'KAMA', 'MA', 'MAMA',
                'MAVP', 'MIDPOINT', 'MIDPRICE', 'SAR', 'SAREXT', 'SMA', 'T3',
                'TEMA', 'TRIMA', 'WMA'
            ],
            'Momentum Indicators': [
                'ADX', 'ADXR', 'APO', 'AROON', 'AROONOSC', 'BOP', 'CCI', 'CMO',
                'DX', 'MACD', 'MACDEXT', 'MACDFIX', 'MFI', 'MINUS_DI', 'MINUS_DM',
                'MOM', 'PLUS_DI', 'PLUS_DM', 'PPO', 'ROC', 'ROCP', 'ROCR',
                'ROCR100', 'RSI', 'STOCH', 'STOCHF', 'STOCHRSI', 'TRIX',
                'ULTOSC', 'WILLR'
            ],
            'Volume Indicators': [
                'AD', 'ADOSC', 'OBV'
            ],
            'Volatility Indicators': [
                'ATR', 'NATR', 'TRANGE'
            ],
            'Price Transform': [
                'AVGPRICE', 'MEDPRICE', 'TYPPRICE', 'WCLPRICE'
            ],
            'Cycle Indicators': [
                'HT_DCPERIOD', 'HT_DCPHASE', 'HT_PHASOR', 'HT_SINE', 'HT_TRENDMODE'
            ],
            'Pattern Recognition': [
                'CDL2CROWS', 'CDL3BLACKCROWS', 'CDL3INSIDE', 'CDL3LINESTRIKE',
                'CDL3OUTSIDE', 'CDL3STARSINSOUTH', 'CDL3WHITESOLDIERS',
                'CDLABANDONEDBABY', 'CDLADVANCEBLOCK', 'CDLBELTHOLD',
                'CDLBREAKAWAY', 'CDLCLOSINGMARUBOZU', 'CDLCONCEALBABYSWALL',
                'CDLCOUNTERATTACK', 'CDLDARKCLOUDCOVER', 'CDLDOJI',
                'CDLDOJISTAR', 'CDLDRAGONFLYDOJI', 'CDLENGULFING',
                'CDLEVENINGDOJISTAR', 'CDLEVENINGSTAR', 'CDLGAPSIDESIDEWHITE',
                'CDLGRAVESTONEDOJI', 'CDLHAMMER', 'CDLHANGINGMAN',
                'CDLHARAMI', 'CDLHARAMICROSS', 'CDLHIGHWAVE', 'CDLHIKKAKE',
                'CDLHIKKAKEMOD', 'CDLHOMINGPIGEON', 'CDLIDENTICAL3CROWS',
                'CDLINNECK', 'CDLINVERTEDHAMMER', 'CDLKICKING',
                'CDLKICKINGBYLENGTH', 'CDLLADDERBOTTOM', 'CDLLONGLEGGEDDOJI',
                'CDLLONGLINE', 'CDLMARUBOZU', 'CDLMATCHINGLOW',
                'CDLMATHOLD', 'CDLMORNINGDOJISTAR', 'CDLMORNINGSTAR',
                'CDLONNECK', 'CDLPIERCING', 'CDLRICKSHAWMAN', 'CDLRISEFALL3METHODS',
                'CDLSEPARATINGLINES', 'CDLSHOOTINGSTAR', 'CDLSHORTLINE',
                'CDLSPINNINGTOP', 'CDLSTALLEDPATTERN', 'CDLSTICKSANDWICH',
                'CDLTAKURI', 'CDLTASUKIGAP', 'CDLTHRUSTING', 'CDLTRISTAR',
                'CDLUNIQUE3RIVER', 'CDLUPSIDEGAP2CROWS', 'CDLXSIDEGAP3METHODS'
            ],
            'Statistic Functions': [
                'BETA', 'CORREL', 'LINEARREG', 'LINEARREG_ANGLE',
                'LINEARREG_INTERCEPT', 'LINEARREG_SLOPE', 'STDDEV', 'TSF', 'VAR'
            ]
        }

        logger.info(f"获取TA-Lib指标分类成功，共{len(categories)}个分类")
        return categories

    except Exception as e:
        logger.error(f"获取TA-Lib指标分类失败: {e}")
        return {}


def get_indicator_categories():
    """
    获取所有指标分类（包括TA-Lib和自定义）

    Returns:
        Dict: 完整的指标分类字典
    """
    try:
        categories = get_talib_category()

        # 添加自定义指标分类
        categories.update({
            'Custom Indicators': [
                'CUSTOM_MA', 'CUSTOM_MACD', 'CUSTOM_RSI', 'CUSTOM_KDJ'
            ],
            'FactorWeave-Quant Indicators': [
                'HKU_MA', 'HKU_MACD', 'HKU_RSI', 'HKU_KDJ', 'HKU_BOLL'
            ]
        })

        return categories

    except Exception as e:
        logger.error(f"获取指标分类失败: {e}")
        return {}


# 向后兼容性函数
get_all_indicators = get_indicator_categories
