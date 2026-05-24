from loguru import logger
"""
数据计算工具函数库

提供常用的金融计算函数，包括：
- 基础金融计算（涨跌幅、振幅、换手率等）
- 技术指标计算（MA、RSI、MACD、KDJ等）
- 财务比率计算
- 数据标准化和归一化
- 向量化计算优化

作者: FactorWeave-Quant团队
版本: 1.0
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import warnings

# 抑制pandas性能警告
warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)

def calculate_change_pct(current: Union[float, pd.Series],
                         previous: Union[float, pd.Series]) -> Union[float, pd.Series]:
    """
    计算涨跌幅

    Args:
        current: 当前值
        previous: 前一期值

    Returns:
        涨跌幅（小数形式，如0.05表示5%）
    """
    try:
        if isinstance(current, pd.Series) or isinstance(previous, pd.Series):
            # 向量化计算
            result = (current - previous) / previous
            return result.fillna(0.0)
        else:
            # 标量计算
            if previous == 0 or pd.isna(previous) or pd.isna(current):
                return 0.0
            return (current - previous) / previous
    except Exception as e:
        logger.error(f"计算涨跌幅失败: {e}")
        return 0.0 if not isinstance(current, pd.Series) else pd.Series([0.0] * len(current))

def calculate_amplitude(high: Union[float, pd.Series],
                        low: Union[float, pd.Series],
                        prev_close: Union[float, pd.Series]) -> Union[float, pd.Series]:
    """
    计算振幅

    Args:
        high: 最高价
        low: 最低价
        prev_close: 前收盘价

    Returns:
        振幅（小数形式）
    """
    try:
        if isinstance(high, pd.Series) or isinstance(low, pd.Series) or isinstance(prev_close, pd.Series):
            # 向量化计算
            result = (high - low) / prev_close
            return result.fillna(0.0)
        else:
            # 标量计算
            if prev_close == 0 or pd.isna(prev_close):
                return 0.0
            return (high - low) / prev_close
    except Exception as e:
        logger.error(f"计算振幅失败: {e}")
        return 0.0 if not isinstance(high, pd.Series) else pd.Series([0.0] * len(high))

def calculate_turnover_rate(volume: Union[int, pd.Series],
                            total_shares: Union[int, pd.Series]) -> Union[float, pd.Series]:
    """
    计算换手率

    Args:
        volume: 成交量
        total_shares: 总股本

    Returns:
        换手率（小数形式）
    """
    try:
        if isinstance(volume, pd.Series) or isinstance(total_shares, pd.Series):
            # 向量化计算
            result = volume / total_shares
            return result.fillna(0.0)
        else:
            # 标量计算
            if total_shares == 0 or pd.isna(total_shares) or pd.isna(volume):
                return 0.0
            return volume / total_shares
    except Exception as e:
        logger.error(f"计算换手率失败: {e}")
        return 0.0 if not isinstance(volume, pd.Series) else pd.Series([0.0] * len(volume))

def calculate_vwap(high: pd.Series, low: pd.Series, close: pd.Series,
                   volume: pd.Series) -> pd.Series:
    """
    计算成交量加权平均价格(VWAP)

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        volume: 成交量序列

    Returns:
        VWAP序列
    """
    try:
        # 典型价格
        typical_price = (high + low + close) / 3

        # 累计成交量加权价格
        cumulative_volume_price = (typical_price * volume).cumsum()
        cumulative_volume = volume.cumsum()

        # VWAP
        vwap = cumulative_volume_price / cumulative_volume
        return vwap.fillna(method='ffill')
    except Exception as e:
        logger.error(f"计算VWAP失败: {e}")
        return pd.Series([0.0] * len(close), index=close.index)

def calculate_moving_average(data: pd.Series, window: int,
                             method: str = 'simple') -> pd.Series:
    """
    计算移动平均线

    Args:
        data: 数据序列
        window: 窗口期
        method: 计算方法 ('simple', 'exponential', 'weighted')

    Returns:
        移动平均线序列
    """
    try:
        if method == 'simple':
            return data.rolling(window=window).mean()
        elif method == 'exponential':
            return data.ewm(span=window).mean()
        elif method == 'weighted':
            weights = np.arange(1, window + 1)
            return data.rolling(window=window).apply(
                lambda x: np.average(x, weights=weights), raw=True
            )
        else:
            raise ValueError(f"不支持的移动平均方法: {method}")
    except Exception as e:
        logger.error(f"计算移动平均线失败: {e}")
        return pd.Series([np.nan] * len(data), index=data.index)

def calculate_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """
    计算相对强弱指标(RSI)

    Args:
        close: 收盘价序列
        window: 计算窗口期

    Returns:
        RSI序列
    """
    try:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)  # 默认中性值
    except Exception as e:
        logger.error(f"计算RSI失败: {e}")
        return pd.Series([50.0] * len(close), index=close.index)

def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26,
                   signal: int = 9) -> Dict[str, pd.Series]:
    """
    计算MACD指标

    Args:
        close: 收盘价序列
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期

    Returns:
        包含DIF、DEA、MACD的字典
    """
    try:
        ema_fast = close.ewm(span=fast).mean()
        ema_slow = close.ewm(span=slow).mean()

        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal).mean()
        macd = (dif - dea) * 2

        return {
            'DIF': dif,
            'DEA': dea,
            'MACD': macd
        }
    except Exception as e:
        logger.error(f"计算MACD失败: {e}")
        return {
            'DIF': pd.Series([0.0] * len(close), index=close.index),
            'DEA': pd.Series([0.0] * len(close), index=close.index),
            'MACD': pd.Series([0.0] * len(close), index=close.index)
        }

def calculate_kdj(high: pd.Series, low: pd.Series, close: pd.Series,
                  window: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> Dict[str, pd.Series]:
    """
    计算KDJ指标

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        window: 计算窗口期
        k_smooth: K值平滑周期
        d_smooth: D值平滑周期

    Returns:
        包含K、D、J的字典
    """
    try:
        lowest_low = low.rolling(window=window).min()
        highest_high = high.rolling(window=window).max()

        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        rsv = rsv.fillna(50.0)

        k = rsv.ewm(alpha=1/k_smooth).mean()
        d = k.ewm(alpha=1/d_smooth).mean()
        j = 3 * k - 2 * d

        return {
            'K': k,
            'D': d,
            'J': j
        }
    except Exception as e:
        logger.error(f"计算KDJ失败: {e}")
        return {
            'K': pd.Series([50.0] * len(close), index=close.index),
            'D': pd.Series([50.0] * len(close), index=close.index),
            'J': pd.Series([50.0] * len(close), index=close.index)
        }

def calculate_bollinger_bands(close: pd.Series, window: int = 20,
                              std_dev: float = 2.0) -> Dict[str, pd.Series]:
    """
    计算布林带

    Args:
        close: 收盘价序列
        window: 移动平均窗口期
        std_dev: 标准差倍数

    Returns:
        包含上轨、中轨、下轨的字典
    """
    try:
        middle = close.rolling(window=window).mean()
        std = close.rolling(window=window).std(ddof=0)

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
    except Exception as e:
        logger.error(f"计算布林带失败: {e}")
        return {
            'upper': pd.Series([np.nan] * len(close), index=close.index),
            'middle': pd.Series([np.nan] * len(close), index=close.index),
            'lower': pd.Series([np.nan] * len(close), index=close.index)
        }

def calculate_technical_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """
    批量计算技术指标

    Args:
        data: 包含OHLCV的DataFrame

    Returns:
        添加了技术指标的DataFrame
    """
    try:
        result = data.copy()

        # 基础验证
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            logger.warning(f"缺少必需列: {missing_columns}")
            return result

        # 移动平均线
        for window in [5, 10, 20, 60]:
            result[f'MA{window}'] = calculate_moving_average(data['close'], window)

        # RSI
        result['RSI'] = calculate_rsi(data['close'])

        # MACD
        macd_data = calculate_macd(data['close'])
        result['MACD_DIF'] = macd_data['DIF']
        result['MACD_DEA'] = macd_data['DEA']
        result['MACD'] = macd_data['MACD']

        # KDJ
        kdj_data = calculate_kdj(data['high'], data['low'], data['close'])
        result['KDJ_K'] = kdj_data['K']
        result['KDJ_D'] = kdj_data['D']
        result['KDJ_J'] = kdj_data['J']

        # 布林带
        bb_data = calculate_bollinger_bands(data['close'])
        result['BB_UPPER'] = bb_data['upper']
        result['BB_MIDDLE'] = bb_data['middle']
        result['BB_LOWER'] = bb_data['lower']

        # VWAP
        result['VWAP'] = calculate_vwap(data['high'], data['low'], data['close'], data['volume'])

        # 基础计算指标
        if len(data) > 1:
            result['CHANGE_PCT'] = calculate_change_pct(data['close'], data['close'].shift(1))
            result['AMPLITUDE'] = calculate_amplitude(data['high'], data['low'], data['close'].shift(1))

        logger.info(f"成功计算 {len(result.columns) - len(data.columns)} 个技术指标")
        return result

    except Exception as e:
        logger.error(f"批量计算技术指标失败: {e}")
        return data

def calculate_financial_ratios(financial_data: Dict[str, Union[float, Decimal]]) -> Dict[str, float]:
    """
    计算财务比率

    Args:
        financial_data: 财务数据字典

    Returns:
        财务比率字典
    """
    try:
        ratios = {}

        # 转换为float以便计算，跳过非数值字段
        data = {}
        for k, v in financial_data.items():
            if isinstance(v, str) and not v.replace('.', '').replace('-', '').isdigit():
                # 跳过字符串字段（如symbol, report_date等）
                continue
            try:
                data[k] = float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                # 跳过无法转换为数值的字段
                continue

        # 盈利能力比率
        if data.get('net_profit', 0) != 0 and data.get('shareholders_equity', 0) != 0:
            ratios['roe'] = data['net_profit'] / data['shareholders_equity']

        if data.get('net_profit', 0) != 0 and data.get('total_assets', 0) != 0:
            ratios['roa'] = data['net_profit'] / data['total_assets']

        if data.get('gross_profit', 0) != 0 and data.get('operating_revenue', 0) != 0:
            ratios['gross_profit_margin'] = data['gross_profit'] / data['operating_revenue']

        if data.get('net_profit', 0) != 0 and data.get('operating_revenue', 0) != 0:
            ratios['net_profit_margin'] = data['net_profit'] / data['operating_revenue']

        # 偿债能力比率
        if data.get('current_assets', 0) != 0 and data.get('current_liabilities', 0) != 0:
            ratios['current_ratio'] = data['current_assets'] / data['current_liabilities']

        if data.get('total_liabilities', 0) != 0 and data.get('total_assets', 0) != 0:
            ratios['debt_to_assets'] = data['total_liabilities'] / data['total_assets']

        if data.get('total_liabilities', 0) != 0 and data.get('shareholders_equity', 0) != 0:
            ratios['debt_to_equity'] = data['total_liabilities'] / data['shareholders_equity']

        # 营运能力比率
        if data.get('operating_revenue', 0) != 0 and data.get('total_assets', 0) != 0:
            ratios['asset_turnover'] = data['operating_revenue'] / data['total_assets']

        return ratios

    except Exception as e:
        logger.error(f"计算财务比率失败: {e}")
        return {}

def normalize_financial_data(data: pd.DataFrame, method: str = 'zscore',
                             columns: Optional[List[str]] = None) -> pd.DataFrame:
    """
    财务数据标准化

    Args:
        data: 财务数据DataFrame
        method: 标准化方法 ('zscore', 'minmax', 'robust')
        columns: 要标准化的列名列表，None表示所有数值列

    Returns:
        标准化后的DataFrame
    """
    try:
        result = data.copy()

        # 确定要标准化的列
        if columns is None:
            numeric_columns = result.select_dtypes(include=[np.number]).columns.tolist()
        else:
            numeric_columns = [col for col in columns if col in result.columns]

        if not numeric_columns:
            logger.warning("没有找到需要标准化的数值列")
            return result

        for col in numeric_columns:
            if method == 'zscore':
                # Z-score标准化
                mean_val = result[col].mean()
                std_val = result[col].std()
                if std_val != 0:
                    result[f'{col}_normalized'] = (result[col] - mean_val) / std_val
                else:
                    result[f'{col}_normalized'] = 0.0

            elif method == 'minmax':
                # Min-Max标准化
                min_val = result[col].min()
                max_val = result[col].max()
                if max_val != min_val:
                    result[f'{col}_normalized'] = (result[col] - min_val) / (max_val - min_val)
                else:
                    result[f'{col}_normalized'] = 0.0

            elif method == 'robust':
                # 鲁棒标准化（使用中位数和四分位距）
                median_val = result[col].median()
                q75 = result[col].quantile(0.75)
                q25 = result[col].quantile(0.25)
                iqr = q75 - q25
                if iqr != 0:
                    result[f'{col}_normalized'] = (result[col] - median_val) / iqr
                else:
                    result[f'{col}_normalized'] = 0.0
            else:
                raise ValueError(f"不支持的标准化方法: {method}")

        logger.info(f"成功标准化 {len(numeric_columns)} 个数值列")
        return result

    except Exception as e:
        logger.error(f"财务数据标准化失败: {e}")
        return data

def calculate_correlation_matrix(data: pd.DataFrame,
                                 method: str = 'pearson') -> pd.DataFrame:
    """
    计算相关性矩阵

    Args:
        data: 数据DataFrame
        method: 相关性计算方法 ('pearson', 'spearman', 'kendall')

    Returns:
        相关性矩阵
    """
    try:
        numeric_data = data.select_dtypes(include=[np.number])
        if numeric_data.empty:
            logger.warning("没有找到数值列用于计算相关性")
            return pd.DataFrame()

        correlation_matrix = numeric_data.corr(method=method)
        return correlation_matrix

    except Exception as e:
        logger.error(f"计算相关性矩阵失败: {e}")
        return pd.DataFrame()

def calculate_volatility(returns: pd.Series, window: int = 20,
                         annualize: bool = True) -> pd.Series:
    """
    计算波动率

    Args:
        returns: 收益率序列
        window: 计算窗口期
        annualize: 是否年化

    Returns:
        波动率序列
    """
    try:
        volatility = returns.rolling(window=window).std()

        if annualize:
            # 假设252个交易日
            volatility = volatility * np.sqrt(252)

        return volatility.fillna(0.0)

    except Exception as e:
        logger.error(f"计算波动率失败: {e}")
        return pd.Series([0.0] * len(returns), index=returns.index)

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.03,
                           window: int = 252) -> pd.Series:
    """
    计算夏普比率

    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率（年化）
        window: 计算窗口期

    Returns:
        夏普比率序列
    """
    try:
        # 计算超额收益
        daily_rf_rate = risk_free_rate / 252  # 转换为日收益率
        excess_returns = returns - daily_rf_rate

        # 计算滚动夏普比率
        rolling_mean = excess_returns.rolling(window=window).mean()
        rolling_std = excess_returns.rolling(window=window).std()

        sharpe_ratio = (rolling_mean / rolling_std) * np.sqrt(252)  # 年化
        return sharpe_ratio.fillna(0.0)

    except Exception as e:
        logger.error(f"计算夏普比率失败: {e}")
        return pd.Series([0.0] * len(returns), index=returns.index)

def calculate_max_drawdown(cumulative_returns: pd.Series) -> Dict[str, float]:
    """
    计算最大回撤

    Args:
        cumulative_returns: 累计收益率序列

    Returns:
        包含最大回撤、回撤开始和结束时间的字典
    """
    try:
        # 计算累计最高点
        rolling_max = cumulative_returns.expanding().max()

        # 计算回撤
        drawdown = (cumulative_returns - rolling_max) / rolling_max

        # 找到最大回撤
        max_drawdown = drawdown.min()
        max_drawdown_idx = drawdown.idxmin()

        # 找到回撤开始时间（最大回撤点之前的最高点）
        peak_idx = rolling_max.loc[:max_drawdown_idx].idxmax()

        return {
            'max_drawdown': max_drawdown,
            'peak_date': peak_idx,
            'trough_date': max_drawdown_idx,
            'recovery_date': None  # 需要额外计算
        }

    except Exception as e:
        logger.error(f"计算最大回撤失败: {e}")
        return {
            'max_drawdown': 0.0,
            'peak_date': None,
            'trough_date': None,
            'recovery_date': None
        }

def validate_data_quality(data: pd.DataFrame,
                          required_columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    验证数据质量

    Args:
        data: 待验证的数据
        required_columns: 必需的列名列表

    Returns:
        数据质量报告
    """
    try:
        report = {
            'total_rows': len(data),
            'total_columns': len(data.columns),
            'missing_data': {},
            'duplicate_rows': 0,
            'data_types': {},
            'quality_score': 0.0,
            'issues': []
        }

        # 检查缺失数据
        for col in data.columns:
            missing_count = data[col].isnull().sum()
            missing_pct = missing_count / len(data) * 100
            report['missing_data'][col] = {
                'count': missing_count,
                'percentage': missing_pct
            }

            if missing_pct > 50:
                report['issues'].append(f"列 '{col}' 缺失数据超过50%")

        # 检查重复行
        report['duplicate_rows'] = data.duplicated().sum()
        if report['duplicate_rows'] > 0:
            report['issues'].append(f"发现 {report['duplicate_rows']} 行重复数据")

        # 检查数据类型
        for col in data.columns:
            report['data_types'][col] = str(data[col].dtype)

        # 检查必需列
        if required_columns:
            missing_columns = set(required_columns) - set(data.columns)
            if missing_columns:
                report['issues'].append(f"缺少必需列: {list(missing_columns)}")

        # 计算质量评分
        total_cells = len(data) * len(data.columns)
        missing_cells = sum(info['count'] for info in report['missing_data'].values())
        completeness_score = 1 - (missing_cells / total_cells) if total_cells > 0 else 0

        duplicate_penalty = min(report['duplicate_rows'] / len(data), 0.2) if len(data) > 0 else 0
        required_columns_penalty = len(missing_columns) * 0.1 if required_columns else 0

        report['quality_score'] = max(0, completeness_score - duplicate_penalty - required_columns_penalty)

        return report

    except Exception as e:
        logger.error(f"数据质量验证失败: {e}")
        return {
            'total_rows': 0,
            'total_columns': 0,
            'missing_data': {},
            'duplicate_rows': 0,
            'data_types': {},
            'quality_score': 0.0,
            'issues': [f"验证过程出错: {str(e)}"]
        }
