from utils.imports import np, pd
from loguru import logger

try:
    from core.performance import calc_full_metrics
except ImportError:
    calc_full_metrics = None

# 日志系统已迁移到Loguru
# 直接使用 logger.info(), logger.error() 等方法

def calculate_atr(df, period=14):
    """
    计算ATR (Average True Range)

    参数:
        df (DataFrame): 包含'high', 'low', 'close'列的DataFrame
        period (int): ATR计算周期

    返回:
        Series: ATR值
    """
    # 使用全局logger

    # 使用统一的数据预处理
    try:
        from utils.data_preprocessing import kdata_preprocess
        df = kdata_preprocess(df, context="ATR计算")
    except ImportError:
        logger.warning("无法导入统一的数据预处理模块")

    if df is None or df.empty:
        logger.warning("ATR计算: 输入数据无效")
        return pd.Series(dtype=float)

    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def calculate_drawdown(equity_curve):
    """
    计算回撤 - 保留简单版本用于快速计算

    参数:
        equity_curve (array-like): 资金曲线数据

    返回:
        array: 回撤序列
        float: 最大回撤值
    """
    # 使用全局logger
    logger.info(f"开始计算回撤，数据点数={len(equity_curve)}")

    # 转换为numpy数组
    equity = np.array(equity_curve)

    # 计算累计最大值
    running_max = np.maximum.accumulate(equity)

    # 计算回撤
    drawdown = (equity - running_max) / running_max

    # 最大回撤
    max_drawdown = np.min(drawdown)

    logger.info(f"回撤计算完成，最大回撤={max_drawdown:.4f}")
    return drawdown, max_drawdown

def calculate_sharpe_ratio(returns, risk_free_rate=0.0, periods_per_year=252):
    """
    计算夏普比率 - 保留简单版本用于快速计算

    参数:
        returns (array-like): 收益率序列
        risk_free_rate (float): 无风险利率
        periods_per_year (int): 每年的周期数 (日=252, 周=52, 月=12)

    返回:
        float: 年化夏普比率
    """
    # 使用全局logger
    logger.info(f"开始计算夏普比率，收益率序列长度={len(returns)}")

    returns = np.array(returns)
    excess_returns = returns - risk_free_rate

    if len(excess_returns) == 0 or np.std(excess_returns) == 0:
        logger.warning("夏普比率计算失败，收益率序列为空或标准差为0")
        return 0

    sharpe = np.mean(excess_returns) / np.std(excess_returns)
    annual_sharpe = sharpe * np.sqrt(periods_per_year)

    logger.info(f"夏普比率计算完成，年化夏普比率={annual_sharpe:.4f}")
    return annual_sharpe

def calc_full_metrics(returns_df):
    """计算完整的性能指标

    Args:
        returns_df: DataFrame, 必须包含 'daily_return' 列

    Returns:
        dict: 完整的性能指标字典
    """
    logger.info("calc_full_metrics: 开始计算完整性能指标")

    try:
        if 'daily_return' in returns_df.columns:
            returns = returns_df['daily_return'].dropna().values
        elif 'returns' in returns_df.columns:
            returns = returns_df['returns'].dropna().values
        else:
            logger.warning("calc_full_metrics: 未找到 daily_return 或 returns 列")
            return {}
        if len(returns) == 0:
            logger.warning("calc_full_metrics: 收益率序列为空")
            return {}

        cumulative = np.cumprod(1 + returns)
        total_return = cumulative[-1] - 1
        n_periods = len(returns)
        annualized_return = (1 + total_return) ** (252 / max(n_periods, 1)) - 1

        annualized_volatility = np.std(returns) * np.sqrt(252)
        sharpe_ratio = (annualized_return - 0.0) / annualized_volatility if annualized_volatility > 0 else 0

        running_max = np.maximum.accumulate(cumulative)
        drawdown_series = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown_series)

        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

        winning_days = np.sum(returns > 0)
        total_days = len(returns)
        win_rate = winning_days / total_days if total_days > 0 else 0

        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        avg_win = np.mean(positive_returns) if len(positive_returns) > 0 else 0
        avg_loss = np.mean(negative_returns) if len(negative_returns) > 0 else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        sortino_ratio = annualized_return / (np.sqrt(np.mean(negative_returns ** 2)) * np.sqrt(252)) if len(negative_returns) > 0 else 0

        metrics = {
            'total_return': float(total_return),
            'annualized_return': float(annualized_return),
            'annualized_volatility': float(annualized_volatility),
            'sharpe_ratio': float(sharpe_ratio),
            'sortino_ratio': float(sortino_ratio),
            'max_drawdown': float(max_drawdown),
            'calmar_ratio': float(calmar_ratio),
            'win_rate': float(win_rate),
            'profit_factor': float(profit_factor),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'total_periods': total_days,
        }

        logger.info(f"calc_full_metrics: 计算完成, 总收益率={total_return:.4f}, 夏普比率={sharpe_ratio:.4f}")
        return metrics

    except Exception as e:
        logger.error(f"calc_full_metrics 计算失败: {e}")
        return {}


def calculate_performance_metrics(trades=None, equity_curve=None, returns_df=None):
    """
    计算交易系统性能指标 - 统一接口

    参数:
        trades (list, optional): 交易记录列表（旧版本兼容）
        equity_curve (array-like, optional): 资金曲线数据（旧版本兼容）
        returns_df (DataFrame, optional): 包含收益数据的DataFrame（推荐使用）

    返回:
        dict: 包含各种性能指标的字典
    """
    # 使用全局logger
    logger.info("开始计算性能指标")

    try:
        # 使用统一的性能指标计算模块
        # 性能指标计算已整合到 core.performance 模块中

        if returns_df is not None:
            logger.info("使用统一模块计算性能指标（DataFrame输入）")
            result = calc_full_metrics(returns_df)
            logger.info("统一模块性能指标计算完成")
            return result
        elif equity_curve is not None:
            logger.info("使用统一模块计算性能指标（资金曲线输入）")
            # 转换为DataFrame格式
            equity_curve = np.array(equity_curve)
            returns = np.diff(equity_curve) / equity_curve[:-1]
            returns_df = pd.DataFrame({
                'daily_return': returns
            })
            result = calc_full_metrics(returns_df)
            logger.info("统一模块性能指标计算完成")
            return result
        elif trades is not None:
            logger.info("从交易记录计算性能指标")
            # 从交易记录构建收益序列
            returns_df = _build_returns_from_trades(trades)
            result = calc_full_metrics(returns_df)
            logger.info("统一模块性能指标计算完成")
            return result
        else:
            raise ValueError("需要提供returns_df、equity_curve或trades参数")

    except ImportError:
        logger.warning("统一性能指标模块不可用，使用简化版本")
        # 如果统一模块不可用，使用简化版本
        return _calculate_simple_performance_metrics_fallback(trades, equity_curve)
    except Exception as e:
        logger.error(f"性能指标计算失败: {e}")
        return _calculate_simple_performance_metrics_fallback(trades, equity_curve)

def _build_returns_from_trades(trades):
    """从交易记录构建收益序列"""
    # 使用全局logger

    if not trades:
        logger.warning("交易记录为空")
        return pd.DataFrame({'daily_return': []})

    # 构建简单的日收益序列
    returns = []
    for trade in trades:
        # 假设每笔交易的收益率
        trade_return = trade.profit / \
            trade.entry_price if hasattr(
                trade, 'entry_price') and trade.entry_price > 0 else 0
        returns.append(trade_return)

    return pd.DataFrame({'daily_return': returns})

def _calculate_simple_performance_metrics_fallback(trades, equity_curve):
    """简化版性能指标计算 - 作为后备方案"""
    # 使用全局logger
    logger.info("使用后备方案计算性能指标")

    if equity_curve is None and not trades:
        logger.warning("后备方案计算失败，无有效数据")
        return {}

    # 如果有资金曲线，优先使用
    if equity_curve is not None:
        equity_curve = np.array(equity_curve)
        returns = np.diff(equity_curve) / equity_curve[:-1]

        # 计算基本指标
        total_return = (equity_curve[-1] / equity_curve[0]) - 1
        annual_return = (1 + total_return) ** (252 / len(returns)) - 1
        _, max_drawdown = calculate_drawdown(equity_curve)
        sharpe_ratio = calculate_sharpe_ratio(returns)

        metrics = {
            'total_return': total_return,
            'annualized_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
        }
    else:
        # 从交易记录计算基本指标
        metrics = {}

    # 如果有交易记录，添加交易统计
    if trades:
        logger.info(f"计算交易统计，交易记录数={len(trades)}")

        winning_trades = sum(1 for trade in trades if trade.profit > 0)
        losing_trades = sum(1 for trade in trades if trade.profit < 0)
        total_trades = len(trades)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # 计算盈亏比
        profits = [trade.profit for trade in trades if trade.profit > 0]
        losses = [abs(trade.profit) for trade in trades if trade.profit < 0]
        profit_factor = sum(profits) / \
            sum(losses) if sum(losses) > 0 else float('inf')

        # 添加交易统计
        metrics.update({
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
        })

    logger.info("后备方案性能指标计算完成")
    return metrics

def get_optimal_position_size(capital, risk_per_trade, entry_price, stop_loss):
    """
    计算最优仓位大小（基于固定风险）

    参数:
        capital (float): 可用资金
        risk_per_trade (float): 每笔交易的风险比例
        entry_price (float): 入场价格
        stop_loss (float): 止损价格

    返回:
        int: 计算得到的仓位大小（股数）
    """
    # 使用全局logger
    logger.info(f"计算最优仓位大小，资金={capital}, 风险比例={risk_per_trade}")

    # 计算每股风险
    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share <= 0:
        logger.warning("仓位计算失败，止损价格无效")
        return 0

    # 计算风险金额
    risk_amount = capital * risk_per_trade

    # 计算可买入数量
    position_size = risk_amount / risk_per_share

    # 向下取整到100的倍数
    position_size = (int(position_size) // 100) * 100

    result = position_size if position_size >= 100 else 0
    logger.info(f"最优仓位计算完成，建议仓位={result}股")
    return result

def _kdata_preprocess(df, context="分析"):
    """K线数据预处理：检查并修正所有关键字段，统一处理datetime字段"""
    # 使用全局logger
    logger.info(f"开始{context}数据预处理")

    if not isinstance(df, pd.DataFrame):
        logger.info(f"{context}数据不是DataFrame格式，直接返回")
        return df

    # 检查datetime是否在索引中或列中
    has_datetime = False
    datetime_in_index = False

    # 检查datetime是否在索引中
    if isinstance(df.index, pd.DatetimeIndex) or (hasattr(df.index, 'name') and df.index.name == 'datetime'):
        has_datetime = True
        datetime_in_index = True
    # 检查datetime是否在列中
    elif 'datetime' in df.columns:
        has_datetime = True
        datetime_in_index = False

    # 如果没有datetime信息，创建一个简单的日期索引
    if not has_datetime:
        df = df.copy()
        df.index = pd.date_range(start='2020-01-01', periods=len(df), freq='D')
        datetime_in_index = True
        logger.info(f"{context}数据缺少时间信息，已自动创建日期索引")

    # 如果datetime在列中，将其设为索引
    if has_datetime and not datetime_in_index:
        df = df.copy()
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        logger.info(f"{context}数据已将datetime列设为索引")

    # 检查必需的列
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    missing_columns = [
        col for col in required_columns if col not in df.columns]

    if missing_columns:
        logger.warning(f"{context}缺少必需的列: {missing_columns}")
        # 尝试修复缺失的列
        for col in missing_columns:
            if col == 'volume' and 'vol' in df.columns:
                df['volume'] = df['vol']
                logger.info(f"{context}已将vol列重命名为volume")
            elif col in ['open', 'high', 'low'] and 'close' in df.columns:
                # 如果只有close价格，用close填充其他价格
                df[col] = df['close']
                logger.info(f"{context}已用close价格填充{col}列")

    # 检查数据类型
    numeric_columns = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 删除包含NaN的行
    original_len = len(df)
    df = df.dropna()
    if len(df) < original_len:
        logger.info(f"{context}已删除{original_len - len(df)}行包含NaN的数据")

    if df.empty:
        logger.warning(f"{context}数据预处理后为空")
        return None

    logger.info(f"{context}数据预处理完成，最终数据{len(df)}行")
    return df
