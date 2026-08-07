from loguru import logger
"""
Data Loader Module

This module provides functionality for loading and managing data.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, List
from functools import lru_cache
import time
from concurrent.futures import ThreadPoolExecutor
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logger

@dataclass
class DataValidationResult:
    """数据验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

class DataLoadError(Exception):
    """数据加载错误"""
    pass

class DataSourceValidator:
    """数据源验证器 - 预防重复字符串生成"""
    
    @staticmethod
    def validate_and_clean_data(df: pd.DataFrame, context: str = "") -> pd.DataFrame:
        """验证和清理数据源数据"""
        logger.info(f"{context}开始数据源验证...")
        
        # 增强的重复字符串检测 - 更严格的检查
        repeat_strings = DataSourceValidator._detect_repeat_strings(df)
        if repeat_strings:
            logger.warning(f"{context}检测到重复字符串: {repeat_strings}")
            df = DataSourceValidator._clean_repeat_strings(df, context)
            
            # 再次验证确保清理成功
            remaining_strings = DataSourceValidator._detect_repeat_strings(df)
            if remaining_strings:
                logger.error(f"{context}重复字符串清理失败，仍存在: {remaining_strings}")
                # 强制转换为数值类型
                df = DataSourceValidator._force_numeric_conversion(df, context)
        
        # 验证数据格式
        df = DataSourceValidator._validate_data_format(df, context)
        
        # 数据去重
        df = DataSourceValidator._remove_duplicates(df, context)
        
        # 额外的字符串安全检查 - 特别针对'000158'等问题
        df = DataSourceValidator._check_specific_problematic_strings(df, context)
        
        return df
    
    @staticmethod
    def _detect_repeat_strings(df: pd.DataFrame) -> List[str]:
        """检测重复字符串"""
        repeat_strings = []
        for col in df.columns:
            if df[col].dtype == 'object':
                for value in df[col].unique():
                    str_val = str(value)
                    if len(str_val) > 10 and DataSourceValidator._is_repeat_pattern(str_val):
                        repeat_strings.append(str_val)
        return repeat_strings
    
    @staticmethod
    def _is_repeat_pattern(value: str) -> bool:
        """检查是否为重复模式"""
        for i in range(1, min(len(value), 20)):
            unit = value[:i]
            if len(value) % len(unit) == 0:
                repeated = unit * (len(value) // len(unit))
                if value == repeated:
                    return True
        return False
    
    @staticmethod
    def _clean_repeat_strings(df: pd.DataFrame, context: str) -> pd.DataFrame:
        """清理重复字符串"""
        cleaned_df = df.copy()
        cleaned_count = 0
        
        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == 'object':
                repeat_mask = cleaned_df[col].astype(str).apply(
                    lambda x: DataSourceValidator._is_repeat_pattern(x) if len(str(x)) > 10 else False
                )
                if repeat_mask.any():
                    cleaned_count += repeat_mask.sum()
                    cleaned_df.loc[repeat_mask, col] = np.nan
                    logger.warning(f"{context}列{col}清理了{repeat_mask.sum()}个重复字符串")
        
        logger.info(f"{context}数据源验证完成: 共清理{cleaned_count}个重复字符串")
        return cleaned_df
    
    @staticmethod
    def _validate_data_format(df: pd.DataFrame, context: str) -> pd.DataFrame:
        """验证数据格式"""
        # 确保数值列为正确类型
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if col in df.columns:
                if df[col].dtype == 'object':
                    # 尝试转换为数值
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    logger.debug(f"{context}列{col}已转换为数值类型")
        
        return df
    
    @staticmethod
    def _remove_duplicates(df: pd.DataFrame, context: str) -> pd.DataFrame:
        """去除重复数据"""
        original_count = len(df)
        df = df.drop_duplicates()
        removed_count = original_count - len(df)
        
        if removed_count > 0:
            logger.info(f"{context}去除了{removed_count}个重复行")
        
        return df
    
    @staticmethod
    def _check_specific_problematic_strings(df: pd.DataFrame, context: str) -> pd.DataFrame:
        """检查并修复已知的特定问题字符串（如'000158'等）"""
        try:
            cleaned_df = df.copy()
            problem_strings = ['000158', '000001', '000002', '600000', '600036', '000858', '000725']
            
            # 检查所有字符串列
            for col in cleaned_df.columns:
                if cleaned_df[col].dtype == 'object':
                    # 检查是否包含已知问题字符串的重复模式
                    for problem_str in problem_strings:
                        # 构建重复模式
                        repeat_patterns = [problem_str * i for i in range(2, 11)]  # 2倍到10倍重复
                        
                        # 检查并修复这些模式
                        for pattern in repeat_patterns:
                            mask = cleaned_df[col].astype(str) == pattern
                            if mask.any():
                                cleaned_df.loc[mask, col] = np.nan
                                logger.warning(f"{context}列{col}检测并修复了重复字符串: {problem_str}*{len(pattern)//len(problem_str)}")
            
            return cleaned_df
            
        except Exception as e:
            logger.error(f"{context}检查问题字符串失败: {str(e)}")
            return df
    
    @staticmethod
    def _force_numeric_conversion(df: pd.DataFrame, context: str) -> pd.DataFrame:
        """强制将数据转换为数值类型，处理无法转换的值"""
        try:
            cleaned_df = df.copy()
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
            
            for col in numeric_columns:
                if col in cleaned_df.columns:
                    # 尝试直接转换为数值
                    cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')
                    logger.debug(f"{context}列{col}已强制转换为数值类型")
            
            return cleaned_df
            
        except Exception as e:
            logger.error(f"{context}强制数值转换失败: {str(e)}")
            return df

def _get_data_cache():
    """获取数据缓存实例（延迟加载）"""
    try:
        from core.services.unified_cache_provider import get_unified_cache_provider
        provider = get_unified_cache_provider()
        return provider.get_cache_service()
    except ImportError:
        return None

data_cache = _get_data_cache()

def retry_on_failure(max_retries: int = 3, delay_seconds: int = 1):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"函数 {func.__name__} 执行失败: {str(e)}")
                        raise
                    logger.warning(
                        f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败，将重试")
                    time.sleep(delay_seconds * (attempt + 1))
            return None
        return wrapper
    return decorator

@retry_on_failure(max_retries=3)
def fetch_fundamental_data(stock, use_cache: bool = True) -> pd.DataFrame:
    """
    获取基本面数据

    参数:
        stock: 股票对象
        use_cache: 是否使用缓存

    返回:
        DataFrame: 包含基本面数据的DataFrame
    """
    try:
        cache_key = f"fundamental_{stock.code}"
        if use_cache and data_cache:
            cached_data = data_cache.get(cache_key, namespace="data_loader")
            if cached_data is not None:
                return cached_data

        # DEPRECATED: 不再注入模拟基本面数据（模拟数据会干扰真实场景）。
        # 改调真实 akshare 数据源；真实数据不可用时由下方校验显式报错。
        df = fetch_fundamental_data_akshare(stock.code, use_cache=False)
        if df.empty:
            raise DataLoadError(f"真实基本面数据源不可用（akshare 无返回），请检查数据源配置: {stock.code}")

        # 列名兼容：akshare 返回 net_profit，验证器需要 net_income
        if 'net_profit' in df.columns and 'net_income' not in df.columns:
            df['net_income'] = df['net_profit']
        
        # 使用数据源验证器预防重复字符串
        df = DataSourceValidator.validate_and_clean_data(df, "基本面数据")

        # 验证数据
        validation = validate_fundamental_data(df)
        if not validation.is_valid:
            raise DataLoadError(f"基本面数据验证失败: {validation.errors}")

        df = handle_outliers(df)

        if use_cache and data_cache:
            from datetime import timedelta
            data_cache.set(cache_key, df, namespace="data_loader", ttl=timedelta(minutes=30))

        return df

    except Exception as e:
        logger.error(f"获取基本面数据失败: {str(e)}")
        raise DataLoadError(f"获取基本面数据失败: {str(e)}")

def validate_fundamental_data(df: pd.DataFrame) -> DataValidationResult:
    """验证基本面数据"""
    errors = []
    warnings = []

    # 检查必需的列
    required_columns = ['revenue', 'net_income', 'assets', 'liabilities']
    missing_columns = [
        col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"缺少必需的列: {', '.join(missing_columns)}")

    # 检查数据类型
    for col in df.columns:
        if not np.issubdtype(df[col].dtype, np.number):
            errors.append(f"列 {col} 不是数值类型")

    # 检查空值
    null_cols = df.columns[df.isnull().any()].tolist()
    if null_cols:
        warnings.append(f"以下列包含空值: {', '.join(null_cols)}")

    # 检查负值
    for col in ['revenue', 'assets']:
        if (df[col] < 0).any():
            errors.append(f"列 {col} 包含负值")

    return DataValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )

def handle_outliers(df: pd.DataFrame, method: str = 'zscore', threshold: float = 3.0) -> pd.DataFrame:
    """
    处理异常值

    参数:
        df: 输入数据
        method: 异常值检测方法 ('zscore' 或 'iqr')
        threshold: 异常值阈值
    """
    df_clean = df.copy()

    for col in df.select_dtypes(include=[np.number]).columns:
        if method == 'zscore':
            # Z-score方法
            z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
            mask = z_scores > threshold
        else:
            # IQR方法
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            mask = (df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))

        if mask.any():
            logger.warning(f"列 {col} 发现 {mask.sum()} 个异常值")
            # 使用中位数替换异常值
            df_clean.loc[mask, col] = df[col].median()

    return df_clean

@retry_on_failure(max_retries=3)
def fetch_macroeconomic_data(use_cache: bool = True) -> pd.DataFrame:
    """获取宏观经济数据"""
    try:
        cache_key = "macroeconomic"
        if use_cache and data_cache:
            cached_data = data_cache.get(cache_key, namespace="data_loader")
            if cached_data is not None:
                return cached_data

        # DEPRECATED: 已移除模拟宏观经济数据注入（模拟数据会干扰真实场景）。
        # 请接入真实宏观经济数据源（如 akshare 宏观接口）后恢复本函数。
        raise NotImplementedError(
            "已移除模拟宏观经济数据，请接入真实宏观经济数据源（如 akshare 宏观接口）"
        )
        
        df = DataSourceValidator.validate_and_clean_data(df, "宏观经济数据")

        validation = validate_macroeconomic_data(df)
        if not validation.is_valid:
            raise DataLoadError(f"宏观经济数据验证失败: {validation.errors}")

        df = handle_outliers(df)

        if use_cache and data_cache:
            from datetime import timedelta
            data_cache.set(cache_key, df, namespace="data_loader", ttl=timedelta(minutes=30))

        return df

    except Exception as e:
        logger.error(f"获取宏观经济数据失败: {str(e)}")
        raise DataLoadError(f"获取宏观经济数据失败: {str(e)}")

def validate_macroeconomic_data(df: pd.DataFrame) -> DataValidationResult:
    """验证宏观经济数据"""
    errors = []
    warnings = []

    # 检查必需的列
    required_columns = ['gdp_growth', 'inflation',
                        'unemployment', 'interest_rate']
    missing_columns = [
        col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"缺少必需的列: {', '.join(missing_columns)}")

    # 检查数据类型
    for col in df.columns:
        if not np.issubdtype(df[col].dtype, np.number):
            errors.append(f"列 {col} 不是数值类型")

    # 检查数据范围
    if 'inflation' in df.columns and ((df['inflation'] < -10) | (df['inflation'] > 30)).any():
        warnings.append("通货膨胀率超出正常范围")

    if 'unemployment' in df.columns and ((df['unemployment'] < 0) | (df['unemployment'] > 50)).any():
        warnings.append("失业率超出正常范围")

    return DataValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )

def integrate_multiple_data_sources(df_kdata: pd.DataFrame,
                                    fundamental_data: pd.DataFrame,
                                    macroeconomic_data: pd.DataFrame,
                                    sentiment_data: Optional[pd.DataFrame] = None,
                                    chunk_size: int = 1000) -> pd.DataFrame:
    """
    整合多源数据

    参数:
        df_kdata: K线数据
        fundamental_data: 基本面数据
        macroeconomic_data: 宏观经济数据
        sentiment_data: 市场情绪数据
        chunk_size: 数据分块大小
    """
    try:
        # 验证输入数据
        if df_kdata.empty:
            raise ValueError("K线数据为空")

        # 确保索引为日期类型
        if not isinstance(df_kdata.index, pd.DatetimeIndex):
            if 'date' in df_kdata.columns:
                df_kdata = df_kdata.set_index('date')
            else:
                raise ValueError("K线数据缺少日期索引")
        
        # 使用数据源验证器对K线数据进行验证和清理
        df_kdata = DataSourceValidator.validate_and_clean_data(df_kdata, "K线数据整合")

        # 使用线程池处理数据对齐
        with ThreadPoolExecutor() as executor:
            # 提交数据对齐任务
            fundamental_future = executor.submit(
                align_and_process_data, fundamental_data, 'Q', 'ffill')
            macro_future = executor.submit(
                align_and_process_data, macroeconomic_data, 'M', 'ffill')
            sentiment_future = executor.submit(
                align_and_process_data, sentiment_data, 'D', 'ffill')

            # 获取结果
            aligned_fundamental = fundamental_future.result()
            aligned_macro = macro_future.result()
            aligned_sentiment = sentiment_future.result()

        # 分块处理数据合并
        result_chunks = []
        for i in range(0, len(df_kdata), chunk_size):
            chunk = df_kdata.iloc[i:i+chunk_size].copy()

            # 合并基本面数据
            if aligned_fundamental is not None:
                # 使用数据源验证器验证和清理基本面数据
                aligned_fundamental = DataSourceValidator.validate_and_clean_data(aligned_fundamental, "基本面数据整合")
                chunk = merge_chunk_data(chunk, aligned_fundamental, 'fund_')

            # 合并宏观数据
            if aligned_macro is not None:
                # 使用数据源验证器验证和清理宏观数据
                aligned_macro = DataSourceValidator.validate_and_clean_data(aligned_macro, "宏观数据整合")
                chunk = merge_chunk_data(chunk, aligned_macro, 'macro_')

            # 合并情绪数据
            if aligned_sentiment is not None:
                # 使用数据源验证器验证和清理情绪数据
                aligned_sentiment = DataSourceValidator.validate_and_clean_data(aligned_sentiment, "情绪数据整合")
                chunk = merge_chunk_data(chunk, aligned_sentiment, 'sent_')

            result_chunks.append(chunk)

        # 合并所有分块
        result_df = pd.concat(result_chunks)

        # 处理缺失值
        result_df = handle_missing_data(result_df)

        return result_df

    except Exception as e:
        logger.error(f"整合数据失败: {str(e)}")
        raise DataLoadError(f"整合数据失败: {str(e)}")

def merge_chunk_data(chunk: pd.DataFrame, data: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """合并数据块"""
    # 只保留chunk日期范围内的数据
    filtered_data = data.loc[data.index.isin(chunk.index)]

    # 添加前缀并合并
    filtered_data = filtered_data.add_prefix(prefix)
    return chunk.join(filtered_data, how='left')

def handle_missing_data(df: pd.DataFrame) -> pd.DataFrame:
    """处理缺失值"""
    # 记录缺失值情况
    missing_stats = df.isnull().sum()
    if missing_stats.any():
        logger.warning("发现缺失值:\n" + str(missing_stats[missing_stats > 0]))

    # 对不同类型的列使用不同的填充方法
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns

    # 对数值列使用前向填充和线性插值
    df[numeric_cols] = df[numeric_cols].fillna(method='ffill')
    df[numeric_cols] = df[numeric_cols].interpolate(method='linear')

    # 对分类列使用前向填充
    df[categorical_cols] = df[categorical_cols].fillna(method='ffill')

    # 最后的缺失值用0填充
    df = df.fillna(0)

    return df

@lru_cache(maxsize=100)
def load_stock_data(file_path: str) -> pd.DataFrame:
    """
    加载股票数据（使用缓存）

    参数:
        file_path: 数据文件路径
    """
    try:
        df = pd.read_csv(file_path, parse_dates=['date'], index_col='date')

        # 验证数据
        validation = validate_stock_data(df)
        if not validation.is_valid:
            raise DataLoadError(f"股票数据验证失败: {validation.errors}")

        # 处理异常值
        df = handle_outliers(df)

        return df

    except Exception as e:
        logger.error(f"加载股票数据失败: {str(e)}")
        raise DataLoadError(f"加载股票数据失败: {str(e)}")

def validate_stock_data(df: pd.DataFrame) -> DataValidationResult:
    """验证股票数据"""
    errors = []
    warnings = []

    # 检查必需的列
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    missing_columns = [
        col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"缺少必需的列: {', '.join(missing_columns)}")

    # 检查数据类型
    for col in required_columns:
        if col in df.columns and not np.issubdtype(df[col].dtype, np.number):
            errors.append(f"列 {col} 不是数值类型")

    # 检查数据有效性
    if 'close' in df.columns:
        if (df['close'] <= 0).any():
            errors.append("收盘价包含无效值")

    if 'volume' in df.columns:
        if (df['volume'] < 0).any():
            errors.append("成交量包含负值")

    # 检查OHLC关系
    if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        if (df['high'] < df['low']).any():
            errors.append("最高价小于最低价")
        if ((df['high'] < df['open']) | (df['high'] < df['close'])).any():
            errors.append("最高价小于开盘价或收盘价")
        if ((df['low'] > df['open']) | (df['low'] > df['close'])).any():
            errors.append("最低价大于开盘价或收盘价")

    return DataValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )

def create_simulated_fundamental_data():
    """
    创建模拟的基本面数据

    返回:
        DataFrame: 包含模拟基本面数据的DataFrame
    """
    # 创建日期范围
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='Q')

    # 创建基本财务指标
    np.random.seed(42)  # 固定随机种子以确保可重复性

    # 模拟财务数据
    data = {
        # 收入逐渐增长
        'revenue': np.random.normal(1000, 200, len(dates)) * (1 + np.arange(len(dates)) * 0.05),
        # 净利润逐渐增长
        'net_income': np.random.normal(100, 30, len(dates)) * (1 + np.arange(len(dates)) * 0.03),
        # 资产逐渐增长
        'assets': np.random.normal(5000, 500, len(dates)) * (1 + np.arange(len(dates)) * 0.02),
        # 负债逐渐增长
        'liabilities': np.random.normal(2000, 300, len(dates)) * (1 + np.arange(len(dates)) * 0.01),
        # 经营现金流
        'operating_cash_flow': np.random.normal(120, 40, len(dates)) * (1 + np.arange(len(dates)) * 0.04),
    }

    # 创建DataFrame
    df = pd.DataFrame(data, index=dates)

    # 计算衍生指标
    df['equity'] = df['assets'] - df['liabilities']  # 权益
    df['roe'] = df['net_income'] / df['equity']  # 净资产收益率
    df['profit_margin'] = df['net_income'] / df['revenue']  # 利润率
    df['asset_turnover'] = df['revenue'] / df['assets']  # 资产周转率
    df['debt_to_equity'] = df['liabilities'] / df['equity']  # 负债权益比

    return df

def create_simulated_macroeconomic_data():
    """
    创建模拟的宏观经济数据

    返回:
        DataFrame: 包含模拟宏观经济数据的DataFrame
    """
    # 创建日期范围 - 每月数据
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='M')

    # 设置随机种子以确保可重复性
    np.random.seed(42)

    # 基础趋势 - 模拟经济周期
    t = np.arange(len(dates))
    cycle1 = 0.2 * np.sin(2 * np.pi * t / 24)  # 2年周期
    cycle2 = 0.1 * np.sin(2 * np.pi * t / 12)  # 1年周期
    trend = 0.02 * t / len(t)  # 微弱的长期上升趋势

    # 生成不同经济指标
    gdp_growth = 2.0 + trend * 3 + cycle1 + \
        np.random.normal(0, 0.3, len(dates))
    inflation = 2.5 + cycle2 * 2 + np.random.normal(0, 0.2, len(dates))
    unemployment = 5.0 - trend + cycle1 * 0.5 + \
        np.random.normal(0, 0.1, len(dates))
    interest_rate = 1.5 + cycle1 * 0.8 + cycle2 + \
        np.random.normal(0, 0.05, len(dates))
    consumer_confidence = 100 + cycle1 * 10 + \
        cycle2 * 5 + np.random.normal(0, 2, len(dates))

    # 调整合理范围
    unemployment = np.clip(unemployment, 3, 10)
    interest_rate = np.clip(interest_rate, 0, 5)
    inflation = np.clip(inflation, -1, 7)

    # 组织数据为DataFrame
    data = {
        'gdp_growth': gdp_growth,
        'inflation': inflation,
        'unemployment': unemployment,
        'interest_rate': interest_rate,
        'consumer_confidence': consumer_confidence,
    }

    df = pd.DataFrame(data, index=dates)

    # 添加一些衍生指标
    df['real_interest_rate'] = df['interest_rate'] - df['inflation']
    df['economic_health'] = df['gdp_growth'] - df['unemployment'] * 0.5

    return df

def align_and_process_data(kdata, freq='D', method='ffill'):
    """对数据进行对齐处理"""
    if kdata.empty:
        return None

    # 获取K线数据的时间范围
    start_date = kdata.index.min()
    end_date = kdata.index.max()

    # 创建完整的日期范围
    date_range = pd.date_range(start=start_date, end=end_date, freq=freq)

    # 重新索引数据并填充缺失值
    reindexed_data = kdata.reindex(date_range, method=method)

    # 将数据重采样到日频率
    if freq != 'D':
        reindexed_data = reindexed_data.resample('D').asfreq()
        reindexed_data = reindexed_data.fillna(method=method)

    return reindexed_data

@retry_on_failure(max_retries=3)
def fetch_fundamental_data_akshare(stock_code: str, use_cache: bool = True) -> pd.DataFrame:
    """
    获取真实财务数据，自动适配akshare接口，并标准化字段。
    返回DataFrame，字段名为：revenue、net_profit、roe、assets、liabilities、profit_margin、debt_to_equity、operating_cash_flow、equity、revenue_yoy。
    """
    try:
        import akshare as ak
        # 优先用stock_financial_abstract
        if hasattr(ak, 'stock_financial_abstract'):
            df = ak.stock_financial_abstract(symbol=stock_code)
            if df is not None and not df.empty:
                # 字段映射
                mapping = {
                    '营业总收入': 'revenue',
                    '净利润': 'net_profit',
                    '净资产收益率ROE': 'roe',
                    '资产总计': 'assets',
                    '负债合计': 'liabilities',
                    '销售净利率': 'profit_margin',
                    '资产负债率': 'debt_to_equity',
                    '经营活动产生的现金流量净额': 'operating_cash_flow',
                    '归属于母公司股东权益合计': 'equity',
                    '营业总收入同比增长': 'revenue_yoy',
                }
                # 取最新一行
                row = df.iloc[0]
                result = {}
                for k, v in mapping.items():
                    result[v] = row.get(k, 0)
                return pd.DataFrame([result])
        # 其次用stock_financial_analysis_indicator
        elif hasattr(ak, 'stock_financial_analysis_indicator'):
            df = ak.stock_financial_analysis_indicator(symbol=stock_code)
            if df is not None and not df.empty:
                # 这里字段名需根据实际接口调整
                row = df.iloc[0]
                result = {k: row.get(k, 0) for k in df.columns}
                return pd.DataFrame([result])
        else:
            raise ImportError("当前akshare版本不支持主流A股财报接口，请升级akshare >= 1.11.0")
    except Exception as e:
        logger.info(f"akshare获取财务数据失败: {str(e)}")
        return pd.DataFrame()

def generate_quality_report(df: pd.DataFrame, context: str = "数据质量") -> Dict[str, Any]:
    """
    生成数据质量报告，统计缺失、异常、分布、评分等，便于导出和UI展示。
    参数：
        df: 输入DataFrame
        context: 场景说明
    返回：
        dict: 结构化报告
    """
    report = {
        'context': context,
        'shape': df.shape,
        'columns': list(df.columns),
        'missing_fields': {},
        'empty_ratio': {},
        'anomaly_stats': {},
        'type_errors': {},
        'price_relation_errors': [],
        'logic_errors': [],
        'preprocess_fixes': [],
        'field_distributions': {},
        'quality_score': 100,
        'warnings': [],
        'errors': []
    }
    # 缺失字段统计
    required_cols = ['open', 'high', 'low',
                     'close', 'volume', 'datetime', 'code']
    for col in required_cols:
        if col not in df.columns:
            report['missing_fields'][col] = '缺失'
            report['quality_score'] -= 10
    # 空值分布
    for col in df.columns:
        null_count = df[col].isnull().sum()
        ratio = null_count / len(df) if len(df) > 0 else 0
        if null_count > 0:
            report['empty_ratio'][col] = {
                'count': int(null_count), 'ratio': float(ratio)}
            report['quality_score'] -= min(5, int(ratio*100))
    # 异常值统计
    for col in df.select_dtypes(include=[np.number]).columns:
        negatives = (df[col] < 0).sum()
        extreme = ((df[col] > df[col].mean() + 5*df[col].std())
                   | (df[col] < df[col].mean() - 5*df[col].std())).sum()
        if negatives > 0 or extreme > 0:
            report['anomaly_stats'][col] = {
                'negatives': int(negatives), 'extreme': int(extreme)}
            report['quality_score'] -= min(5, negatives+extreme)
    # 类型检查
    for col in df.columns:
        if col in required_cols and col in df.columns:
            if col in ['open', 'high', 'low', 'close', 'volume']:
                if not np.issubdtype(df[col].dtype, np.number):
                    report['type_errors'][col] = str(df[col].dtype)
                    report['quality_score'] -= 5
            if col == 'datetime':
                try:
                    pd.to_datetime(df['datetime'])
                except Exception:
                    report['type_errors'][col] = '非日期格式'
                    report['quality_score'] -= 5
    # 价格关系异常
    if all(c in df.columns for c in ['high', 'low']):
        if (df['high'] < df['low']).any():
            report['price_relation_errors'].append('high < low')
            report['quality_score'] -= 5
    if all(c in df.columns for c in ['high', 'open', 'close']):
        if ((df['high'] < df['open']) | (df['high'] < df['close'])).any():
            report['price_relation_errors'].append('high < open/close')
            report['quality_score'] -= 5
    if all(c in df.columns for c in ['low', 'open', 'close']):
        if ((df['low'] > df['open']) | (df['low'] > df['close'])).any():
            report['price_relation_errors'].append('low > open/close')
            report['quality_score'] -= 5
    # 业务逻辑异常（如财务负值、比率超常）
    for col in ['pe', 'pb', 'roe']:
        if col in df.columns:
            if (df[col] < 0).any():
                report['logic_errors'].append(f'{col} 存在负值')
                report['quality_score'] -= 2
    # 字段分布统计
    for col in ['close', 'volume', 'pe', 'pb']:
        if col in df.columns:
            desc = df[col].describe().to_dict()
            report['field_distributions'][col] = desc
    # 评分归一化
    report['quality_score'] = max(0, min(100, report['quality_score']))
    # 预处理修正记录（留空，后续补充）
    return report
