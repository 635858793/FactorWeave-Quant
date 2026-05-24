from loguru import logger
"""
专业级回测数据验证器模块
确保回测数据质量和参数合理性，对标行业专业软件标准
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import warnings
# 纯Loguru架构，移除旧的日志导入

class BacktestValidationLevel(Enum):
    """回测验证级别枚举"""
    BASIC = "basic"              # 基础验证
    STANDARD = "standard"        # 标准验证
    STRICT = "strict"            # 严格验证
    PROFESSIONAL = "professional"  # 专业级验证

class BacktestDataQuality(Enum):
    """回测数据质量等级"""
    EXCELLENT = "excellent"      # 优秀 (95-100%)
    GOOD = "good"               # 良好 (85-94%)
    FAIR = "fair"               # 一般 (70-84%)
    POOR = "poor"               # 较差 (<70%)

@dataclass
class BacktestValidationResult:
    """回测验证结果数据类"""
    is_valid: bool
    quality_score: float  # 0-100分
    quality_level: BacktestDataQuality
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    metrics: Dict[str, Any]
    validation_time: datetime

class ProfessionalBacktestValidator:
    """
    专业级回测验证器
    对标行业专业软件标准，提供全面的回测质量控制
    """

    def __init__(self,
                 validation_level: BacktestValidationLevel = BacktestValidationLevel.PROFESSIONAL):
        """
        初始化专业级回测验证器

        Args:
            # log_manager: 已迁移到Loguru日志系统
            validation_level: 验证级别
        """
        # 纯Loguru架构，移除log_manager依赖
        self.validation_level = validation_level
        self.validation_rules = self._initialize_validation_rules()

    def _initialize_validation_rules(self) -> Dict[str, Dict]:
        """初始化验证规则"""
        return {
            "data_requirements": {
                "required_columns": ["open", "high", "low", "close", "volume"],
                "optional_columns": ["amount", "datetime", "date"],
                "min_records": 252,  # 至少一年数据
                "max_missing_ratio": 0.05,  # 最大缺失比例5%
                "price_consistency_tolerance": 0.001,  # 价格一致性容忍度
            },
            "signal_requirements": {
                "valid_signal_values": [-1, 0, 1],  # 有效信号值
                "min_signal_frequency": 0.01,  # 最小信号频率1%
                "max_signal_frequency": 0.5,   # 最大信号频率50%
                "signal_change_tolerance": 0.8,  # 信号变化容忍度
            },
            "parameter_requirements": {
                "initial_capital": {"min": 10000, "max": 100000000},
                "position_size": {"min": 0.01, "max": 1.0},
                "commission_pct": {"min": 0.0001, "max": 0.01},
                "slippage_pct": {"min": 0.0001, "max": 0.01},
                "stop_loss_pct": {"min": 0.01, "max": 0.5},
                "take_profit_pct": {"min": 0.01, "max": 1.0},
            },
            "performance_requirements": {
                "min_trades": 10,  # 最少交易次数
                "max_drawdown_threshold": 0.5,  # 最大回撤阈值50%
                "min_sharpe_threshold": -2.0,   # 最小夏普比率阈值
                "max_volatility_threshold": 1.0,  # 最大波动率阈值100%
            }
        }

    def validate_backtest_data(self, data: pd.DataFrame, signal_col: str = 'signal',
                               stock_code: str = None) -> BacktestValidationResult:
        """
        验证回测数据

        Args:
            data: 回测数据DataFrame
            signal_col: 信号列名
            stock_code: 股票代码

        Returns:
            BacktestValidationResult: 验证结果
        """
        start_time = datetime.now()
        errors = []
        warnings = []
        suggestions = []
        metrics = {}

        try:
            # 1. 数据结构验证
            structure_score = self._validate_data_structure(
                data, errors, warnings)
            metrics["structure_score"] = structure_score

            # 2. 数据质量验证
            quality_score = self._validate_data_quality(data, errors, warnings)
            metrics["quality_score"] = quality_score

            # 3. 信号验证
            signal_score = self._validate_signals(
                data, signal_col, errors, warnings)
            metrics["signal_score"] = signal_score

            # 4. 时间序列验证
            timeseries_score = self._validate_timeseries(
                data, errors, warnings)
            metrics["timeseries_score"] = timeseries_score

            # 5. 市场数据合理性验证
            market_score = self._validate_market_data(
                data, stock_code, errors, warnings)
            metrics["market_score"] = market_score

            # 计算总体质量分数
            quality_score = np.mean([
                structure_score, quality_score, signal_score,
                timeseries_score, market_score
            ])

            # 确定质量等级
            quality_level = self._determine_quality_level(quality_score)

            # 生成改进建议
            suggestions = self._generate_suggestions(metrics, errors, warnings)

            # 记录验证结果
            logger.info(
                f"回测数据验证完成 - 股票: {stock_code}, 质量分数: {quality_score:.2f}, "
                f"等级: {quality_level.value}, 错误: {len(errors)}, 警告: {len(warnings)}"
            )

            return BacktestValidationResult(
                is_valid=len(errors) == 0,
                quality_score=quality_score,
                quality_level=quality_level,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                metrics=metrics,
                validation_time=start_time
            )

        except Exception as e:
            logger.error(f"回测数据验证异常: {str(e)}")
            return BacktestValidationResult(
                is_valid=False,
                quality_score=0.0,
                quality_level=BacktestDataQuality.POOR,
                errors=[f"验证过程异常: {str(e)}"],
                warnings=[],
                suggestions=["请检查数据格式和完整性"],
                metrics={},
                validation_time=start_time
            )

    def validate_backtest_parameters(self, params: Dict[str, Any]) -> BacktestValidationResult:
        """
        验证回测参数

        Args:
            params: 回测参数字典

        Returns:
            BacktestValidationResult: 验证结果
        """
        start_time = datetime.now()
        errors = []
        warnings = []
        suggestions = []
        metrics = {}

        try:
            rules = self.validation_rules["parameter_requirements"]

            # 验证各个参数
            for param_name, param_value in params.items():
                if param_name in rules:
                    param_rules = rules[param_name]

                    # 检查范围
                    if "min" in param_rules and param_value < param_rules["min"]:
                        errors.append(
                            f"参数 {param_name} 值 {param_value} 小于最小值 {param_rules['min']}")

                    if "max" in param_rules and param_value > param_rules["max"]:
                        errors.append(
                            f"参数 {param_name} 值 {param_value} 大于最大值 {param_rules['max']}")

            # 参数组合合理性检查
            if "stop_loss_pct" in params and "take_profit_pct" in params:
                if params["stop_loss_pct"] >= params["take_profit_pct"]:
                    warnings.append("止损比例不应大于等于止盈比例")

            if "commission_pct" in params and "slippage_pct" in params:
                total_cost = params["commission_pct"] + params["slippage_pct"]
                if total_cost > 0.02:  # 总成本超过2%
                    warnings.append(f"总交易成本过高: {total_cost:.3%}")

            # 计算参数合理性得分
            param_score = 100.0 - len(errors) * 20 - len(warnings) * 5
            param_score = max(0, param_score)

            quality_level = self._determine_quality_level(param_score)

            return BacktestValidationResult(
                is_valid=len(errors) == 0,
                quality_score=param_score,
                quality_level=quality_level,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                metrics={"parameter_score": param_score},
                validation_time=start_time
            )

        except Exception as e:
            logger.error(f"回测参数验证异常: {str(e)}")
            return BacktestValidationResult(
                is_valid=False,
                quality_score=0.0,
                quality_level=BacktestDataQuality.POOR,
                errors=[f"验证过程异常: {str(e)}"],
                warnings=[],
                suggestions=["请检查参数格式和类型"],
                metrics={},
                validation_time=start_time
            )

    def _validate_data_structure(self, data: pd.DataFrame,
                                 errors: List[str], warnings: List[str]) -> float:
        """验证数据结构"""
        if data is None or data.empty:
            errors.append("数据为空")
            return 0.0

        rules = self.validation_rules["data_requirements"]
        required_columns = rules["required_columns"]

        # 检查必需列
        missing_columns = [
            col for col in required_columns if col not in data.columns]
        if missing_columns:
            errors.append(f"缺少必需列: {missing_columns}")
            return 0.0

        # 检查数据长度
        min_records = rules["min_records"]
        if len(data) < min_records:
            warnings.append(f"数据长度不足，建议至少 {min_records} 条记录，当前 {len(data)} 条")

        # 检查数据类型
        score = 100.0
        for col in required_columns:
            if col in data.columns:
                if not pd.api.types.is_numeric_dtype(data[col]):
                    warnings.append(f"列 {col} 应为数值类型")
                    score -= 10

        return max(0, score)

    def _validate_data_quality(self, data: pd.DataFrame,
                               errors: List[str], warnings: List[str]) -> float:
        """验证数据质量"""
        if data.empty:
            return 0.0

        rules = self.validation_rules["data_requirements"]
        score = 100.0

        # 检查缺失值
        total_cells = data.size
        missing_cells = data.isnull().sum().sum()
        missing_ratio = missing_cells / total_cells

        if missing_ratio > rules["max_missing_ratio"]:
            errors.append(f"数据缺失比例过高: {missing_ratio:.2%}")
            score -= 30
        elif missing_ratio > 0:
            warnings.append(f"存在缺失数据: {missing_ratio:.2%}")
            score -= 10

        # 检查异常值
        price_columns = ["open", "high", "low", "close"]
        for col in price_columns:
            if col in data.columns:
                # 检查负价格
                negative_count = (data[col] <= 0).sum()
                if negative_count > 0:
                    errors.append(f"发现 {negative_count} 个非正价格在列 {col}")
                    score -= 20

                # 检查异常波动
                if len(data) > 1:
                    returns = data[col].pct_change().dropna()
                    extreme_returns = (abs(returns) > 0.5).sum()  # 50%以上变动
                    if extreme_returns > 0:
                        warnings.append(
                            f"发现 {extreme_returns} 个异常价格波动在列 {col}")
                        score -= 5

        return max(0, score)

    def _validate_signals(self, data: pd.DataFrame, signal_col: str,
                          errors: List[str], warnings: List[str]) -> float:
        """验证交易信号"""
        if signal_col not in data.columns:
            errors.append(f"缺少信号列: {signal_col}")
            return 0.0

        rules = self.validation_rules["signal_requirements"]
        score = 100.0

        signals = data[signal_col]

        # 检查信号值的有效性
        valid_values = rules["valid_signal_values"]
        invalid_signals = ~signals.isin(valid_values + [np.nan])
        if invalid_signals.any():
            invalid_count = invalid_signals.sum()
            errors.append(f"发现 {invalid_count} 个无效信号值")
            score -= 30

        # 检查信号频率
        non_zero_signals = (signals != 0).sum()
        signal_frequency = non_zero_signals / len(signals)

        if signal_frequency < rules["min_signal_frequency"]:
            warnings.append(f"信号频率过低: {signal_frequency:.2%}")
            score -= 15
        elif signal_frequency > rules["max_signal_frequency"]:
            warnings.append(f"信号频率过高: {signal_frequency:.2%}")
            score -= 10

        # 检查信号连续性
        signal_changes = (signals.diff() != 0).sum()
        change_frequency = signal_changes / len(signals)

        if change_frequency > rules["signal_change_tolerance"]:
            warnings.append(f"信号变化过于频繁: {change_frequency:.2%}")
            score -= 10

        return max(0, score)

    def _validate_timeseries(self, data: pd.DataFrame,
                             errors: List[str], warnings: List[str]) -> float:
        """验证时间序列数据"""
        score = 100.0

        # 检查时间索引
        if not isinstance(data.index, pd.DatetimeIndex):
            if 'datetime' in data.columns:
                try:
                    time_series = pd.to_datetime(data['datetime'])
                except Exception:
                    errors.append("无法解析时间列")
                    return 0.0
            else:
                warnings.append("未找到时间列")
                return 80.0
        else:
            time_series = data.index

        # 检查时间顺序
        if not time_series.is_monotonic_increasing:
            errors.append("时间序列不是递增的")
            score -= 30

        # 检查重复时间
        duplicates = time_series.duplicated().sum()
        if duplicates > 0:
            errors.append(f"发现 {duplicates} 个重复时间点")
            score -= 20

        # 检查时间间隔
        if len(time_series) > 1:
            time_diffs = time_series.diff().dropna()

            # 检查是否有异常的时间间隔
            median_diff = time_diffs.median()
            outlier_diffs = (time_diffs > median_diff * 3).sum()

            if outlier_diffs > 0:
                warnings.append(f"发现 {outlier_diffs} 个异常时间间隔")
                score -= 10

        return max(0, score)

    def _validate_market_data(self, data: pd.DataFrame, stock_code: str,
                              errors: List[str], warnings: List[str]) -> float:
        """验证市场数据合理性"""
        score = 100.0

        # OHLC关系验证
        if all(col in data.columns for col in ["open", "high", "low", "close"]):
            # High应该是最高价
            invalid_high = (
                data["high"] < data[["open", "close"]].max(axis=1)).sum()
            if invalid_high > 0:
                errors.append(f"发现 {invalid_high} 条记录的最高价不正确")
                score -= 20

            # Low应该是最低价
            invalid_low = (
                data["low"] > data[["open", "close"]].min(axis=1)).sum()
            if invalid_low > 0:
                errors.append(f"发现 {invalid_low} 条记录的最低价不正确")
                score -= 20

        # 成交量验证
        if "volume" in data.columns:
            # 检查负成交量
            negative_volume = (data["volume"] < 0).sum()
            if negative_volume > 0:
                errors.append(f"发现 {negative_volume} 条负成交量记录")
                score -= 15

            # 检查异常成交量
            if len(data) > 20:
                volume_ma = data["volume"].rolling(20).mean()
                extreme_volume = (data["volume"] > volume_ma * 10).sum()
                if extreme_volume > 0:
                    warnings.append(f"发现 {extreme_volume} 个异常成交量")
                    score -= 5

        # 停牌检测：连续日价格不变且成交量为0
        if all(col in data.columns for col in ["open", "high", "low", "close", "volume"]):
            price_unchanged = (
                (data["open"] == data["close"]) &
                (data["high"] == data["low"]) &
                (data["open"] == data["high"])
            )
            zero_volume = (data["volume"] == 0)
            suspension_mask = price_unchanged & zero_volume
            suspension_count = suspension_mask.sum()
            if suspension_count > 0:
                suspension_pct = suspension_count / len(data)
                if suspension_pct > 0.05:
                    errors.append(f"发现 {suspension_count} 个疑似停牌日（{suspension_pct:.1%}），可能影响回测准确性")
                    score -= 15
                else:
                    warnings.append(f"发现 {suspension_count} 个疑似停牌日（{suspension_pct:.1%}）")

        # 涨跌停边界检测
        if "close" in data.columns and len(data) > 1:
            daily_change = data["close"].pct_change().dropna()
            if len(daily_change) > 0:
                limit_up = (daily_change >= 0.098)
                limit_down = (daily_change <= -0.098)
                limit_up_count = limit_up.sum()
                limit_down_count = limit_down.sum()
                limit_total = limit_up_count + limit_down_count
                if limit_total > 0:
                    limit_pct = limit_total / len(daily_change)
                    if limit_pct > 0.10:
                        warnings.append(
                            f"发现 {limit_total} 个涨跌停日（涨停{limit_up_count}跌停{limit_down_count}，{limit_pct:.1%}），"
                            f"可能影响交易执行"
                        )
                        score -= 10

        # 交易量为0边界检测
        if "volume" in data.columns:
            zero_vol_count = (data["volume"] == 0).sum()
            if zero_vol_count > 0:
                zero_vol_pct = zero_vol_count / len(data)
                if zero_vol_pct > 0.05:
                    warnings.append(
                        f"发现 {zero_vol_count} 个交易量为0的日期（{zero_vol_pct:.1%}），无法正常交易"
                    )
                    score -= 10
                else:
                    warnings.append(f"发现 {zero_vol_count} 个交易量为0的日期")

        return max(0, score)

    def _determine_quality_level(self, score: float) -> BacktestDataQuality:
        """确定数据质量等级"""
        if score >= 95:
            return BacktestDataQuality.EXCELLENT
        elif score >= 85:
            return BacktestDataQuality.GOOD
        elif score >= 70:
            return BacktestDataQuality.FAIR
        else:
            return BacktestDataQuality.POOR

    def _generate_suggestions(self, metrics: Dict[str, Any],
                              errors: List[str], warnings: List[str]) -> List[str]:
        """生成改进建议"""
        suggestions = []

        # 基于分数生成建议
        if metrics.get("structure_score", 100) < 90:
            suggestions.append("建议检查数据结构和必需列")

        if metrics.get("quality_score", 100) < 90:
            suggestions.append("建议进行数据清洗，处理缺失值和异常值")

        if metrics.get("signal_score", 100) < 90:
            suggestions.append("建议优化交易信号的生成逻辑")

        if metrics.get("timeseries_score", 100) < 90:
            suggestions.append("建议检查时间序列的连续性和准确性")

        if metrics.get("market_score", 100) < 90:
            suggestions.append("建议验证市场数据的OHLC关系和成交量")

        # 基于错误和警告生成建议
        if len(errors) > 0:
            suggestions.append("存在严重数据问题，建议重新获取或清洗数据")

        if len(warnings) > 5:
            suggestions.append("数据质量问题较多，建议进行全面的数据质量检查")

        return suggestions

    def validate_backtest_results(self, results: pd.DataFrame,
                                  trades: List[Dict]) -> BacktestValidationResult:
        """
        验证回测结果

        Args:
            results: 回测结果DataFrame
            trades: 交易记录列表

        Returns:
            BacktestValidationResult: 验证结果
        """
        start_time = datetime.now()
        errors = []
        warnings = []
        suggestions = []
        metrics = {}

        try:
            rules = self.validation_rules["performance_requirements"]

            # 验证交易次数
            trade_count = len(trades)
            if trade_count < rules["min_trades"]:
                warnings.append(
                    f"交易次数过少: {trade_count}, 建议至少 {rules['min_trades']} 次")

            # 验证回测结果的合理性
            if 'equity' in results.columns:
                equity_series = results['equity']

                # 计算最大回撤
                running_max = equity_series.cummax()
                drawdown = (equity_series - running_max) / running_max
                max_drawdown = abs(drawdown.min())

                if max_drawdown > rules["max_drawdown_threshold"]:
                    warnings.append(f"最大回撤过大: {max_drawdown:.2%}")

                # 计算收益率波动
                if len(equity_series) > 1:
                    returns = equity_series.pct_change().dropna()
                    volatility = returns.std() * np.sqrt(252)  # 年化波动率

                    if volatility > rules["max_volatility_threshold"]:
                        warnings.append(f"波动率过高: {volatility:.2%}")

            # 计算结果质量得分
            result_score = 100.0 - len(errors) * 25 - len(warnings) * 10
            result_score = max(0, result_score)

            quality_level = self._determine_quality_level(result_score)

            return BacktestValidationResult(
                is_valid=len(errors) == 0,
                quality_score=result_score,
                quality_level=quality_level,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                metrics={"result_score": result_score,
                         "trade_count": trade_count},
                validation_time=start_time
            )

        except Exception as e:
            logger.error(f"回测结果验证异常: {str(e)}")
            return BacktestValidationResult(
                is_valid=False,
                quality_score=0.0,
                quality_level=BacktestDataQuality.POOR,
                errors=[f"验证过程异常: {str(e)}"],
                warnings=[],
                suggestions=["请检查回测结果格式"],
                metrics={},
                validation_time=start_time
            )

# 便捷函数

def create_backtest_validator(validation_level: BacktestValidationLevel = BacktestValidationLevel.PROFESSIONAL) -> ProfessionalBacktestValidator:
    """
    创建回测验证器实例

    Args:
        validation_level: 验证级别

    Returns:
        ProfessionalBacktestValidator: 回测验证器实例
    """
    return ProfessionalBacktestValidator(validation_level=validation_level)

def validate_backtest_data(data: pd.DataFrame, signal_col: str = 'signal',
                           stock_code: str = None) -> BacktestValidationResult:
    """
    快速验证回测数据

    Args:
        data: 回测数据
        signal_col: 信号列名
        stock_code: 股票代码

    Returns:
        BacktestValidationResult: 验证结果
    """
    validator = create_backtest_validator()
    return validator.validate_backtest_data(data, signal_col, stock_code)

def validate_backtest_parameters(params: Dict[str, Any]) -> BacktestValidationResult:
    """
    快速验证回测参数

    Args:
        params: 回测参数字典

    Returns:
        BacktestValidationResult: 验证结果
    """
    validator = create_backtest_validator()
    return validator.validate_backtest_parameters(params)
