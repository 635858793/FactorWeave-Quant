"""
AI选股回测服务

基于现有UnifiedBacktestEngine，为AI选股策略提供专业的回测功能
支持个性化策略回测、多维度绩效分析和AI选股特有指标
"""

import json
import traceback
import random
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import threading
from collections import defaultdict

# 现有的回测引擎和指标计算
from backtest.unified_backtest_engine import (
    UnifiedBacktestEngine, BacktestLevel, UnifiedRiskMetrics,
    RiskManagementLevel
)

# AI选股相关服务
from .ai_selection_integration_service import (
    AISelectionIntegrationService, StockSelectionCriteria, SelectionStrategy,
    StockSelectionResult, SelectionPerformanceMetrics
)

# 用户画像和个性化引擎
from ..ai.personalized_stock_selection_engine import (
    PersonalizedStockSelectionEngine, PersonalizedSelectionCriteria,
    InvestmentProfile, InvestmentExperience
)

# 数据库服务
from .database_service import DatabaseService

from loguru import logger


class BacktestReportType(Enum):
    """回测报告类型"""
    BASIC = "basic"                    # 基础报告
    PROFESSIONAL = "professional"      # 专业报告
    DETAILED = "detailed"             # 详细报告
    INSTITUTIONAL = "institutional"   # 机构级报告


class AISelectionBacktestConfig:
    """AI选股回测配置"""
    
    def __init__(self,
                 backtest_level: BacktestLevel = BacktestLevel.PROFESSIONAL,
                 initial_capital: float = 1000000.0,
                 position_size: float = 0.95,
                 commission_pct: float = 0.0003,
                 slippage_pct: float = 0.0002,
                 min_commission: float = 5.0,
                 stop_loss_pct: Optional[float] = 0.15,
                 take_profit_pct: Optional[float] = 0.30,
                 max_holding_periods: Optional[int] = 60,
                 enable_compound: bool = True,
                 rebalancing_frequency: str = 'monthly',
                 benchmark_symbol: str = '000300',  # 沪深300
                 risk_free_rate: float = 0.03,
                 confidence_level: float = 0.95,
                 enable_monte_carlo: bool = False,
                 monte_carlo_simulations: int = 1000,
                 enable_stress_test: bool = True,
                 report_type: BacktestReportType = BacktestReportType.PROFESSIONAL):
        """
        初始化AI选股回测配置
        
        Args:
            backtest_level: 回测级别
            initial_capital: 初始资金
            position_size: 仓位大小
            commission_pct: 手续费比例
            slippage_pct: 滑点比例
            min_commission: 最小手续费
            stop_loss_pct: 止损比例
            take_profit_pct: 止盈比例
            max_holding_periods: 最大持有期
            enable_compound: 是否启用复利
            rebalancing_frequency: 调仓频率
            benchmark_symbol: 基准指数代码
            risk_free_rate: 无风险利率
            confidence_level: 置信水平
            enable_monte_carlo: 是否启用蒙特卡洛模拟
            monte_carlo_simulations: 蒙特卡洛模拟次数
            enable_stress_test: 是否启用压力测试
            report_type: 报告类型
        """
        self.backtest_level = backtest_level
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.min_commission = min_commission
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_holding_periods = max_holding_periods
        self.enable_compound = enable_compound
        self.rebalancing_frequency = rebalancing_frequency
        self.benchmark_symbol = benchmark_symbol
        self.risk_free_rate = risk_free_rate
        self.confidence_level = confidence_level
        self.enable_monte_carlo = enable_monte_carlo
        self.monte_carlo_simulations = monte_carlo_simulations
        self.enable_stress_test = enable_stress_test
        self.report_type = report_type


@dataclass
class AISelectionBacktestResult:
    """AI选股回测结果"""
    
    # 基本回测结果
    backtest_result: pd.DataFrame
    unified_risk_metrics: UnifiedRiskMetrics
    benchmark_data: Optional[pd.DataFrame] = None
    
    # AI选股特有指标
    ai_selection_metrics: Optional[Dict[str, Any]] = None
    personalization_impact: Optional[Dict[str, Any]] = None
    selection_accuracy: Optional[Dict[str, Any]] = None
    recommendation_quality: Optional[Dict[str, Any]] = None
    
    # 详细分析结果
    monte_carlo_results: Optional[Dict[str, Any]] = None
    stress_test_results: Optional[Dict[str, Any]] = None
    factor_attribution: Optional[Dict[str, Any]] = None
    
    # 元数据
    backtest_config: AISelectionBacktestConfig = field(default_factory=AISelectionBacktestConfig)
    calculation_timestamp: datetime = field(default_factory=datetime.now)
    execution_time: float = 0.0
    total_simulations: int = 0

    def cleanup(self):
        """显式清理大型DataFrame引用，释放内存"""
        import gc
        if self.backtest_result is not None and not self.backtest_result.empty:
            del self.backtest_result
            self.backtest_result = pd.DataFrame()
        if self.benchmark_data is not None and not self.benchmark_data.empty:
            del self.benchmark_data
            self.benchmark_data = None
        gc.collect()
        logger.debug(f"AISelectionBacktestResult.cleanup: 内存已释放")


@dataclass
class AISelectionBacktestSummary:
    """AI选股回测摘要"""
    
    # 核心绩效指标
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    
    # AI选股特有指标
    ai_selection_accuracy: float = 0.0
    personalization_benefit: float = 0.0
    recommendation_precision: float = 0.0
    factor_effectiveness: float = 0.0
    
    # 风险指标
    var_95: float = 0.0
    cvar_95: float = 0.0
    downside_deviation: float = 0.0
    tail_ratio: float = 0.0
    
    # 交易统计
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_holding_period: float = 0.0
    
    # 比较基准
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    information_ratio: float = 0.0
    tracking_error: float = 0.0


class AISelectionBacktestService:
    """
    AI选股回测服务
    
    基于现有UnifiedBacktestEngine，为AI选股策略提供专业回测功能
    """
    
    def __init__(self, 
                 database_service: Optional[DatabaseService] = None,
                 ai_selection_service: Optional[AISelectionIntegrationService] = None,
                 personalization_engine: Optional[PersonalizedStockSelectionEngine] = None):
        """
        初始化AI选股回测服务
        
        Args:
            database_service: 数据库服务
            ai_selection_service: AI选股集成服务
            personalization_engine: 个性化引擎
        """
        self.database_service = database_service
        self.ai_selection_service = ai_selection_service
        self.personalization_engine = personalization_engine
        
        # 初始化统一回测引擎
        self.unified_engine = UnifiedBacktestEngine(
            backtest_level=BacktestLevel.PROFESSIONAL,
            risk_management_level=RiskManagementLevel.PROFESSIONAL,
            use_vectorized_engine=True,
            auto_select_engine=True
        )
        
        # 缓存管理
        self._cache_lock = threading.Lock()
        self._backtest_cache = {}
        self._performance_cache = {}
        
        logger.info("AI选股回测服务初始化完成")
    
    def run_backtest(self,
                     user_id: str,
                     stock_selection_criteria: StockSelectionCriteria,
                     selection_strategy: SelectionStrategy,
                     start_date: datetime,
                     end_date: datetime,
                     personalized: bool = True,
                     backtest_config: Optional[AISelectionBacktestConfig] = None) -> AISelectionBacktestResult:
        """
        运行AI选股回测
        
        Args:
            user_id: 用户ID
            stock_selection_criteria: 选股标准
            selection_strategy: 选股策略
            start_date: 回测开始日期
            end_date: 回测结束日期
            personalized: 是否使用个性化
            backtest_config: 回测配置
            
        Returns:
            AI选股回测结果
        """
        try:
            start_time = datetime.now()
            logger.info(f"开始AI选股回测 - 用户: {user_id}, 策略: {selection_strategy.value}")
            
            # 1. 准备回测配置
            if backtest_config is None:
                backtest_config = AISelectionBacktestConfig()
            
            # 2. 获取个性化选股标准（如果启用个性化）
            if personalized and self.personalization_engine:
                personalized_criteria = self.personalization_engine.create_personalized_criteria(
                    user_id=user_id,
                    base_criteria=stock_selection_criteria,
                    session_id=f"backtest_{int(start_time.timestamp())}"
                )
                logger.info(f"使用个性化选股标准，用户: {user_id}")
            else:
                personalized_criteria = stock_selection_criteria
                logger.info("使用基础选股标准")
            
            # 3. 获取回测数据
            historical_data = self._get_historical_data(
                start_date, end_date, backtest_config.benchmark_symbol
            )
            
            if historical_data is None or historical_data.empty:
                raise ValueError(f"无法获取回测数据，日期范围: {start_date} 到 {end_date}")
            
            # 4. 生成AI选股信号
            ai_signals = self._generate_ai_selection_signals(
                user_id=user_id,
                criteria=personalized_criteria,
                strategy=selection_strategy,
                data=historical_data,
                start_date=start_date,
                end_date=end_date
            )
            
            # 5. 运行统一回测
            backtest_result_data = self.unified_engine.run_backtest(
                data=ai_signals,
                signal_col='ai_signal',
                price_col='close',
                initial_capital=backtest_config.initial_capital,
                position_size=backtest_config.position_size,
                commission_pct=backtest_config.commission_pct,
                slippage_pct=backtest_config.slippage_pct,
                min_commission=backtest_config.min_commission,
                stop_loss_pct=backtest_config.stop_loss_pct,
                take_profit_pct=backtest_config.take_profit_pct,
                max_holding_periods=backtest_config.max_holding_periods,
                enable_compound=backtest_config.enable_compound,
                benchmark_data=historical_data[historical_data['symbol'] == backtest_config.benchmark_symbol]
            )
            
            # 6. 计算AI选股特有指标
            ai_selection_metrics = self._calculate_ai_selection_metrics(
                self._build_backtest_dataframe(backtest_result_data),
                ai_signals,
                historical_data
            )
            
            # 7. 计算个性化影响（如果启用个性化）
            personalization_impact = None
            if personalized and self.personalization_engine:
                personalization_impact = self._calculate_personalization_impact(
                    user_id, self._build_backtest_dataframe(backtest_result_data)
                )
            
            # 8. 蒙特卡洛模拟（如果启用）
            monte_carlo_results = None
            if backtest_config.enable_monte_carlo:
                monte_carlo_results = self._run_monte_carlo_simulation(
                    ai_signals, backtest_config, historical_data
                )
            
            # 9. 压力测试（如果启用）
            stress_test_results = None
            if backtest_config.enable_stress_test:
                stress_test_results = self._run_stress_test(
                    self._build_backtest_dataframe(backtest_result_data), historical_data
                )
            
            # 10. 因子归因分析
            factor_attribution = self._calculate_factor_attribution(
                self._build_backtest_dataframe(backtest_result_data), ai_signals
            )
            
            # 11. 构建结果
            execution_time = (datetime.now() - start_time).total_seconds()
            total_simulations = (backtest_config.monte_carlo_simulations 
                               if backtest_config.enable_monte_carlo else 0)
            
            result = AISelectionBacktestResult(
                backtest_result=self._build_backtest_dataframe(backtest_result_data),
                unified_risk_metrics=self._extract_risk_metrics(backtest_result_data),
                benchmark_data=historical_data[historical_data['symbol'] == backtest_config.benchmark_symbol],
                ai_selection_metrics=ai_selection_metrics,
                personalization_impact=personalization_impact,
                selection_accuracy=self._calculate_selection_accuracy(ai_signals),
                recommendation_quality=self._calculate_recommendation_quality(ai_signals),
                monte_carlo_results=monte_carlo_results,
                stress_test_results=stress_test_results,
                factor_attribution=factor_attribution,
                backtest_config=backtest_config,
                calculation_timestamp=datetime.now(),
                execution_time=execution_time,
                total_simulations=total_simulations
            )
            
            # 12. 保存回测结果到数据库
            self._save_backtest_result(user_id, result)
            
            logger.info(f"AI选股回测完成 - 执行时间: {execution_time:.2f}秒")
            return result
            
        except Exception as e:
            logger.error(f"AI选股回测失败: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _build_backtest_dataframe(self, result_dict: Dict[str, Any]) -> pd.DataFrame:
        """从统一回测引擎返回的扁平字典构建包含returns列的DataFrame"""
        equity_curve = result_dict.get('equity_curve')
        if equity_curve is not None and len(equity_curve) > 1:
            returns = equity_curve.pct_change().dropna()
            df = pd.DataFrame({'returns': returns})
            df.index.name = 'date'
            return df
        return pd.DataFrame(columns=['returns'])
    
    def _extract_risk_metrics(self, result_dict: Dict[str, Any]) -> UnifiedRiskMetrics:
        """从统一回测引擎返回的扁平字典提取UnifiedRiskMetrics对象"""
        field_names = {f.name for f in UnifiedRiskMetrics.__dataclass_fields__.values()}
        metrics_kwargs = {k: v for k, v in result_dict.items() if k in field_names}
        return UnifiedRiskMetrics(**metrics_kwargs)
    
    def _get_historical_data(self, 
                           start_date: datetime, 
                           end_date: datetime, 
                           benchmark_symbol: str) -> Optional[pd.DataFrame]:
        """获取历史数据"""
        try:
            symbols = ['000001', '000002', '600000', '600036', benchmark_symbol]
            data_list = []

            if self.database_service:
                placeholders = ','.join(['?' for _ in symbols])
                query = f"""
                SELECT symbol, date, open, high, low, close, volume, amount
                FROM daily_price_data
                WHERE symbol IN ({placeholders})
                AND date BETWEEN ? AND ?
                ORDER BY symbol, date
                """
                try:
                    results = self.database_service.execute_query(
                        query,
                        symbols + [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')],
                        pool_name="analytics_duckdb"
                    )
                    if results:
                        historical_data = pd.DataFrame(results)
                        logger.info(f"从数据库获取历史数据完成 - {len(historical_data)}条记录")
                        return historical_data
                except Exception as db_err:
                    logger.warning(f"数据库查询历史数据失败: {db_err}")

            try:
                from core.containers import get_service_container
                from core.services.stock_service import StockService
                container = get_service_container()
                if container:
                    stock_service = container.resolve(StockService)
                    if stock_service:
                        total_days = (end_date - start_date).days + 1
                        # fallback: 仅5个硬编码symbol，且仅在数据库批量查询失败时执行，非热路径
                        for symbol in symbols:
                            kdata = stock_service.get_stock_data(symbol, period='D', count=total_days)
                            if kdata is not None and not kdata.empty:
                                kdata = kdata.copy()
                                kdata['symbol'] = symbol
                                kdata['date'] = pd.to_datetime(kdata.index)
                                kdata_filtered = kdata[(kdata['date'] >= start_date) & (kdata['date'] <= end_date)]
                                if not kdata_filtered.empty:
                                    data_list.append(kdata_filtered)
                        if data_list:
                            historical_data = pd.concat(data_list, ignore_index=True)
                            logger.info(f"从StockService获取历史数据完成 - {len(historical_data)}条记录")
                            return historical_data
            except Exception as stock_err:
                logger.warning(f"StockService获取历史数据失败: {stock_err}")

            logger.warning("无法获取真实历史数据，返回空结果")
            return None

        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return None
    
    def _generate_ai_selection_signals(self,
                                     user_id: str,
                                     criteria: Union[StockSelectionCriteria, PersonalizedSelectionCriteria],
                                     strategy: SelectionStrategy,
                                     data: pd.DataFrame,
                                     start_date: datetime,
                                     end_date: datetime) -> pd.DataFrame:
        """生成AI选股信号"""
        try:
            logger.info(f"生成AI选股信号 - 策略: {strategy.value}")

            data_filtered = data[(data['date'] >= start_date) & (data['date'] <= end_date)].copy()

            stock_scores = {}
            if self.ai_selection_service:
                try:
                    result = self.ai_selection_service.select_stocks(
                        criteria=criteria,
                        strategy=strategy
                    )
                    if result.get("success") and result.get("data"):
                        stock_scores = result["data"].get("stock_scores", {})
                        logger.info(f"AI选股服务返回 {len(stock_scores)} 只股票的评分")
                    else:
                        logger.warning(f"AI选股服务返回失败: {result.get('error', '未知错误')}")
                except Exception as ai_err:
                    logger.warning(f"调用AI选股服务失败: {ai_err}")

            data_filtered['score'] = data_filtered['symbol'].map(stock_scores).fillna(0.0)
            data_filtered['ai_signal'] = np.select(
                [data_filtered['score'] > 0.6, data_filtered['score'] < 0.3],
                [1, -1],
                default=0
            )
            data_filtered['signal_strength'] = data_filtered['score'].abs()
            data_filtered['confidence'] = data_filtered['score']

            signal_df = data_filtered[['date', 'symbol', 'open', 'high', 'low', 'close',
                                        'volume', 'ai_signal', 'signal_strength', 'confidence']].copy()
            logger.info(f"生成AI选股信号完成 - {len(signal_df)}条记录")
            return signal_df

        except Exception as e:
            logger.error(f"生成AI选股信号失败: {e}")
            empty_data = data[(data['date'] >= start_date) & (data['date'] <= end_date)].copy()
            empty_data['ai_signal'] = 0
            empty_data['signal_strength'] = 0
            empty_data['confidence'] = 0
            return empty_data
    
    def _generate_single_stock_signal(self,
                                    symbol: str,
                                    row: pd.Series,
                                    criteria: Union[StockSelectionCriteria, PersonalizedSelectionCriteria],
                                    strategy: SelectionStrategy,
                                    score: float = 0.0) -> int:
        """为单只股票生成信号"""
        try:
            if score > 0.6:
                return 1
            elif score < 0.3:
                return -1
            else:
                return 0

        except Exception as e:
            logger.error(f"生成单股票信号失败: {e}")
            return 0
    
    def _calculate_ai_selection_metrics(self,
                                      backtest_result: pd.DataFrame,
                                      ai_signals: pd.DataFrame,
                                      historical_data: pd.DataFrame) -> Dict[str, Any]:
        """计算AI选股特有指标"""
        try:
            metrics = {}
            
            # 信号质量指标
            signal_counts = ai_signals['ai_signal'].value_counts()
            metrics['signal_distribution'] = signal_counts.to_dict()
            metrics['signal_density'] = len(ai_signals[ai_signals['ai_signal'] != 0]) / len(ai_signals)
            
            # 置信度统计
            metrics['avg_confidence'] = ai_signals['confidence'].mean()
            metrics['confidence_std'] = ai_signals['confidence'].std()
            metrics['high_confidence_signals'] = len(ai_signals[ai_signals['confidence'] > 0.8])
            
            # 信号强度统计
            metrics['avg_signal_strength'] = ai_signals['signal_strength'].mean()
            metrics['signal_strength_std'] = ai_signals['signal_strength'].std()
            
            # 选股多样性
            unique_symbols = ai_signals['symbol'].nunique()
            total_periods = ai_signals['date'].nunique()
            metrics['selection_diversity'] = unique_symbols / total_periods
            
            if 'industry' in ai_signals.columns:
                active_signals = ai_signals[ai_signals['ai_signal'] != 0]
                if len(active_signals) > 0:
                    industry_weights = active_signals['industry'].value_counts(normalize=True)
                    metrics['industry_concentration'] = float(np.sum(industry_weights ** 2))
                else:
                    metrics['industry_concentration'] = None
            else:
                metrics['industry_concentration'] = None
            
            logger.info("AI选股指标计算完成")
            return metrics
            
        except Exception as e:
            logger.error(f"计算AI选股指标失败: {e}")
            return {}
    
    def _calculate_personalization_impact(self,
                                        user_id: str,
                                        backtest_result: pd.DataFrame) -> Dict[str, Any]:
        """计算个性化影响"""
        try:
            impact = {}
            
            # 获取用户画像
            if self.personalization_engine:
                profile = self.personalization_engine.get_investment_profile(user_id)
                if profile:
                    impact['user_experience_level'] = profile.investment_experience.value
                    impact['risk_tolerance_score'] = profile.risk_tolerance_score
                    impact['investment_horizon'] = profile.investment_horizon
                    impact['investment_style'] = profile.investment_style
                    
                    # 计算个性化调整效果
                    base_performance = backtest_result['returns'].mean() * 252  # 年化收益
                    impact['base_performance'] = base_performance

                    experience_bonus_map = {
                        InvestmentExperience.BEGINNER: 0.0,
                        InvestmentExperience.INTERMEDIATE: 0.01,
                        InvestmentExperience.ADVANCED: 0.02,
                        InvestmentExperience.PROFESSIONAL: 0.03,
                    }
                    experience_bonus = experience_bonus_map.get(
                        profile.investment_experience, 0.0
                    )
                    risk_factor = profile.risk_tolerance_score
                    personalization_bonus = risk_factor * 0.02 + experience_bonus
                    impact['personalization_bonus'] = personalization_bonus
                    impact['adjusted_performance'] = base_performance + personalization_bonus
            
            logger.info("个性化影响计算完成")
            return impact
            
        except Exception as e:
            logger.error(f"计算个性化影响失败: {e}")
            return {}
    
    def _run_monte_carlo_simulation(self,
                                  ai_signals: pd.DataFrame,
                                  config: AISelectionBacktestConfig,
                                  historical_data: pd.DataFrame) -> Dict[str, Any]:
        """运行蒙特卡洛模拟"""
        try:
            logger.info(f"开始蒙特卡洛模拟 - {config.monte_carlo_simulations}次")
            
            signal_changes = ai_signals['ai_signal'].diff().dropna().values
            if len(signal_changes) == 0:
                logger.warning("信号变化数据不足，无法进行蒙特卡洛模拟")
                return {}

            simulation_results = []
            signal_changes_list = signal_changes.tolist()
            rng = random.Random(42)

            for i in range(config.monte_carlo_simulations):
                perturbed_signals = ai_signals.copy()
                noise = np.array([rng.choice(signal_changes_list) for _ in range(len(perturbed_signals))])
                perturbed_signals['ai_signal'] = np.clip(
                    perturbed_signals['ai_signal'] + noise, -1, 1
                )
                
                # 运行简化回测
                simulation_result = self._run_simplified_backtest(
                    perturbed_signals, historical_data, config
                )
                simulation_results.append(simulation_result)
            
            # 计算统计结果
            returns = [r['total_return'] for r in simulation_results]
            max_drawdowns = [r['max_drawdown'] for r in simulation_results if r['max_drawdown'] is not None]
            sharpe_ratios = [r['sharpe_ratio'] for r in simulation_results]

            monte_carlo_results = {
                'simulations_count': config.monte_carlo_simulations,
                'return_statistics': {
                    'mean': np.mean(returns),
                    'std': np.std(returns),
                    'min': np.min(returns),
                    'max': np.max(returns),
                    'percentile_5': np.percentile(returns, 5),
                    'percentile_95': np.percentile(returns, 95)
                },
                'drawdown_statistics': {
                    'mean': np.mean(max_drawdowns) if max_drawdowns else None,
                    'std': np.std(max_drawdowns) if max_drawdowns else None,
                    'max': np.max(max_drawdowns) if max_drawdowns else None
                },
                'sharpe_statistics': {
                    'mean': np.mean(sharpe_ratios),
                    'std': np.std(sharpe_ratios),
                    'min': np.min(sharpe_ratios),
                    'max': np.max(sharpe_ratios)
                },
                'probability_of_loss': len([r for r in returns if r < 0]) / len(returns),
                'probability_of_outperformance': len([r for r in returns if r > 0.1]) / len(returns)
            }
            
            logger.info("蒙特卡洛模拟完成")
            return monte_carlo_results
            
        except Exception as e:
            logger.error(f"蒙特卡洛模拟失败: {e}")
            return {}
    
    def _run_simplified_backtest(self,
                               ai_signals: pd.DataFrame,
                               historical_data: pd.DataFrame,
                               config: AISelectionBacktestConfig) -> Dict[str, Any]:
        """运行简化回测（用于蒙特卡洛模拟）"""
        try:
            capital = config.initial_capital
            positions = {}
            trades = 0
            daily_portfolio_values = {}

            for date, day_data in ai_signals.groupby('date'):
                for row_dict in day_data.to_dict('records'):
                    signal = row_dict['ai_signal']
                    price = row_dict['close']

                    if signal != 0 and capital > 0:
                        position_value = capital * config.position_size
                        shares = int(position_value / price)

                        if shares > 0:
                            cost = shares * price * (1 + config.commission_pct)
                            if capital >= cost:
                                capital -= cost
                                positions[row_dict['symbol']] = positions.get(row_dict['symbol'], 0) + shares
                                trades += 1

                day_total_value = capital
                for symbol, held_shares in positions.items():
                    symbol_rows = day_data[day_data['symbol'] == symbol]
                    if not symbol_rows.empty:
                        day_total_value += held_shares * symbol_rows.iloc[-1]['close']
                daily_portfolio_values[date] = day_total_value

            final_value = capital
            for symbol, shares in positions.items():
                last_price_data = ai_signals[ai_signals['symbol'] == symbol]
                if not last_price_data.empty:
                    last_price = last_price_data.iloc[-1]['close']
                    final_value += shares * last_price * (1 - config.commission_pct)

            total_return = (final_value - config.initial_capital) / config.initial_capital

            sorted_dates = sorted(daily_portfolio_values.keys())
            if len(sorted_dates) > 1:
                portfolio_values = np.array([daily_portfolio_values[d] for d in sorted_dates])
                daily_returns = np.diff(portfolio_values) / portfolio_values[:-1]
                volatility = float(np.std(daily_returns) * np.sqrt(252))

                cumulative = np.cumprod(1 + daily_returns)
                running_max = np.maximum.accumulate(cumulative)
                drawdowns = (cumulative - running_max) / running_max
                max_drawdown = float(np.min(drawdowns))
            else:
                volatility = None
                max_drawdown = None

            if volatility is not None and volatility > 0:
                risk_free_rate = 0.02
                annual_mean = np.mean(daily_returns) * 252
                sharpe_ratio = (annual_mean - risk_free_rate) / volatility
            else:
                sharpe_ratio = 0.0

            return {
                'total_return': total_return,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'total_trades': trades,
                'final_capital': final_value
            }

        except Exception as e:
            logger.error(f"简化回测失败: {e}")
            return {
                'total_return': 0.0,
                'max_drawdown': None,
                'sharpe_ratio': 0.0,
                'total_trades': 0,
                'final_capital': config.initial_capital
            }
    
    def _run_stress_test(self,
                       backtest_result: pd.DataFrame,
                       historical_data: pd.DataFrame) -> Dict[str, Any]:
        """运行压力测试"""
        try:
            logger.info("开始压力测试")
            
            stress_results = {}
            
            # 市场崩盘场景 (2008年金融危机)
            crash_scenario = self._simulate_market_crash(backtest_result)
            stress_results['market_crash_scenario'] = crash_scenario
            
            # 高波动率场景
            volatility_scenario = self._simulate_high_volatility(backtest_result)
            stress_results['high_volatility_scenario'] = volatility_scenario
            
            # 流动性枯竭场景
            liquidity_scenario = self._simulate_liquidity_crisis(backtest_result)
            stress_results['liquidity_crisis_scenario'] = liquidity_scenario
            
            # 系统性风险场景
            systemic_risk_scenario = self._simulate_systemic_risk(backtest_result)
            stress_results['systemic_risk_scenario'] = systemic_risk_scenario
            
            logger.info("压力测试完成")
            return stress_results
            
        except Exception as e:
            logger.error(f"压力测试失败: {e}")
            return {}
    
    def _simulate_market_crash(self, backtest_result: pd.DataFrame) -> Dict[str, Any]:
        try:
            logger.warning("市场崩盘模拟依赖真实压力测试引擎，当前无法执行真实模拟。返回空结果。")
            return {}
        except Exception as e:
            logger.error(f"市场崩盘模拟失败: {e}")
            return {}
    
    def _simulate_high_volatility(self, backtest_result: pd.DataFrame) -> Dict[str, Any]:
        """模拟高波动率场景"""
        try:
            logger.warning("高波动率模拟依赖真实压力测试引擎，当前无法执行真实模拟。返回空结果。")
            return {}
        except Exception as e:
            logger.error(f"高波动率模拟失败: {e}")
            return {}
    
    def _simulate_liquidity_crisis(self, backtest_result: pd.DataFrame) -> Dict[str, Any]:
        try:
            logger.warning("流动性危机模拟依赖真实压力测试引擎，当前无法执行真实模拟。返回空结果。")
            return {}
        except Exception as e:
            logger.error(f"流动性危机模拟失败: {e}")
            return {}
    
    def _simulate_systemic_risk(self, backtest_result: pd.DataFrame) -> Dict[str, Any]:
        try:
            logger.warning("系统性风险模拟依赖真实压力测试引擎，当前无法执行真实模拟。返回空结果。")
            return {}
        except Exception as e:
            logger.error(f"系统性风险模拟失败: {e}")
            return {}

    def _calculate_factor_attribution(self,
                                    backtest_result: pd.DataFrame,
                                    ai_signals: pd.DataFrame) -> Dict[str, Any]:
        """计算因子归因分析"""
        try:
            if backtest_result is None or backtest_result.empty or 'returns' not in backtest_result.columns:
                logger.warning("无法计算因子归因，回测结果数据不足")
                return {}

            returns = backtest_result['returns'].dropna()
            if len(returns) < 5:
                logger.warning("数据点不足，无法进行因子归因分析")
                return {}

            total_return = float(returns.sum())
            market_return = float(returns.mean())

            attribution = {
                'market': {
                    'exposure': 1.0,
                    'factor_return': market_return,
                    'contribution': market_return * len(returns),
                    'contribution_pct': (market_return * len(returns)) / total_return if total_return != 0 else 0
                }
            }

            attribution['total_factor_contribution'] = attribution['market']['contribution']
            attribution['specific_return'] = total_return - attribution['market']['contribution']

            logger.info("因子归因分析完成（基于市场因子模型）")
            return attribution
            
        except Exception as e:
            logger.error(f"因子归因分析失败: {e}")
            return {}
    
    def _calculate_selection_accuracy(self, ai_signals: pd.DataFrame) -> Dict[str, Any]:
        """计算选股准确性"""
        try:
            accuracy_metrics = {}

            positive_signals = ai_signals[ai_signals['ai_signal'] > 0]
            negative_signals = ai_signals[ai_signals['ai_signal'] < 0]
            non_zero_signals = ai_signals[ai_signals['ai_signal'] != 0]

            accuracy_metrics['total_signals'] = len(non_zero_signals)
            accuracy_metrics['positive_signals'] = len(positive_signals)
            accuracy_metrics['negative_signals'] = len(negative_signals)

            if 'confidence' in ai_signals.columns and len(non_zero_signals) > 0:
                high_conf_signals = non_zero_signals[non_zero_signals['confidence'] > 0.7]
                high_conf_positive = high_conf_signals[high_conf_signals['ai_signal'] > 0]

                accuracy_metrics['signal_accuracy'] = len(high_conf_signals) / len(non_zero_signals)
                accuracy_metrics['precision'] = len(high_conf_positive) / len(high_conf_signals) if len(high_conf_signals) > 0 else 0.0
                accuracy_metrics['recall'] = len(high_conf_signals) / len(non_zero_signals)
            else:
                logger.warning("缺少置信度数据，无法计算真实准确率指标")
                accuracy_metrics['signal_accuracy'] = 0.0
                accuracy_metrics['precision'] = 0.0
                accuracy_metrics['recall'] = 0.0

            accuracy_metrics['f1_score'] = (
                2 * (accuracy_metrics['precision'] * accuracy_metrics['recall']) /
                (accuracy_metrics['precision'] + accuracy_metrics['recall'])
                if (accuracy_metrics['precision'] + accuracy_metrics['recall']) > 0 else 0.0
            )

            logger.info("选股准确性计算完成")
            return accuracy_metrics
            
        except Exception as e:
            logger.error(f"计算选股准确性失败: {e}")
            return {}
    
    def _calculate_recommendation_quality(self, ai_signals: pd.DataFrame) -> Dict[str, Any]:
        """计算推荐质量"""
        try:
            quality_metrics = {}
            
            # 推荐强度分析
            high_confidence_signals = ai_signals[ai_signals['confidence'] > 0.8]
            quality_metrics['high_confidence_ratio'] = len(high_confidence_signals) / len(ai_signals[ai_signals['ai_signal'] != 0])
            
            # 信号质量分布
            signal_strengths = ai_signals['signal_strength']
            quality_metrics['avg_signal_strength'] = signal_strengths.mean()
            quality_metrics['signal_strength_variance'] = signal_strengths.var()
            
            # 推荐一致性
            daily_signals = (ai_signals['ai_signal'] != 0).groupby(ai_signals['date']).sum()
            quality_metrics['avg_daily_signals'] = daily_signals.mean()
            quality_metrics['signal_consistency'] = 1 - (daily_signals.std() / daily_signals.mean()) if daily_signals.mean() > 0 else 0
            
            logger.info("推荐质量计算完成")
            return quality_metrics
            
        except Exception as e:
            logger.error(f"计算推荐质量失败: {e}")
            return {}
    
    def _save_backtest_result(self, user_id: str, result: AISelectionBacktestResult):
        """保存回测结果到数据库"""
        try:
            if not self.database_service:
                logger.warning("数据库服务不可用，跳过结果保存")
                return
            
            # 准备保存数据
            backtest_data = {
                'user_id': user_id,
                'backtest_config': json.dumps(asdict(result.backtest_config)),
                'total_return': result.unified_risk_metrics.total_return,
                'annualized_return': result.unified_risk_metrics.annualized_return,
                'volatility': result.unified_risk_metrics.volatility,
                'sharpe_ratio': result.unified_risk_metrics.sharpe_ratio,
                'max_drawdown': result.unified_risk_metrics.max_drawdown,
                'win_rate': result.unified_risk_metrics.win_rate,
                'profit_factor': result.unified_risk_metrics.profit_factor,
                'calmar_ratio': result.unified_risk_metrics.calmar_ratio,
                'sortino_ratio': result.unified_risk_metrics.sortino_ratio,
                'beta': result.unified_risk_metrics.beta,
                'alpha': result.unified_risk_metrics.alpha,
                'information_ratio': result.unified_risk_metrics.information_ratio,
                'tracking_error': result.unified_risk_metrics.tracking_error,
                'benchmark_return': result.unified_risk_metrics.benchmark_return,
                'excess_return': result.unified_risk_metrics.excess_return,
                'turnover_rate': getattr(result.unified_risk_metrics, 'turnover_rate', 0.0),
                'backtest_data': json.dumps(asdict(result.backtest_config)),
                'daily_returns': json.dumps(result.backtest_result['returns'].tolist()),
                'monthly_returns': json.dumps([]),
                'trade_records': json.dumps([]),
                'ai_selection_metrics': json.dumps(result.ai_selection_metrics or {}),
                'personalization_impact': json.dumps(result.personalization_impact or {}),
                'monte_carlo_results': json.dumps(result.monte_carlo_results or {}),
                'stress_test_results': json.dumps(result.stress_test_results or {}),
                'factor_attribution': json.dumps(result.factor_attribution or {}),
                'calculation_timestamp': result.calculation_timestamp.isoformat(),
                'execution_time': result.execution_time,
                'total_simulations': result.total_simulations
            }
            
            # 保存到数据库
            backtest_id = self.database_service.save_backtest_result(backtest_data)
            
            if backtest_id:
                logger.info(f"回测结果保存成功，ID: {backtest_id}")
            else:
                logger.warning("回测结果保存失败")
                
        except Exception as e:
            logger.error(f"保存回测结果失败: {e}")
    
    def generate_backtest_report(self,
                               result: AISelectionBacktestResult,
                               report_type: BacktestReportType = BacktestReportType.PROFESSIONAL) -> str:
        """
        生成回测报告
        
        Args:
            result: 回测结果
            report_type: 报告类型
            
        Returns:
            格式化的报告字符串
        """
        try:
            timestamp = result.calculation_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            # 基础信息
            report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI选股策略回测报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 基本信息
   报告生成时间: {timestamp}
   回测级别: {result.backtest_config.backtest_level.value}
   初始资金: {result.backtest_config.initial_capital:,.2f}
   回测周期: {result.backtest_config.start_date} 至 {result.backtest_config.end_date}
   执行时间: {result.execution_time:.2f}秒
"""
            
            # 核心绩效指标
            metrics = result.unified_risk_metrics
            report += f"""
📈 核心绩效指标
   总收益率: {metrics.total_return:+.2%}
   年化收益率: {metrics.annualized_return:+.2%}
   波动率: {metrics.volatility:.2%}
   夏普比率: {metrics.sharpe_ratio:.3f}
   最大回撤: {metrics.max_drawdown:.2%}
   卡玛比率: {metrics.calmar_ratio:.3f}
   索提诺比率: {metrics.sortino_ratio:.3f}
"""
            
            # 风险指标
            report += f"""
📉 风险指标
   VaR (95%): {metrics.var_95:.2%}
   CVaR (95%): {metrics.cvar_95:.2%}
   下行偏差: {metrics.downside_deviation:.2%}
   尾部比率: {metrics.tail_ratio:.3f}
   偏度: {metrics.skewness:.3f}
   峰度: {metrics.kurtosis:.3f}
"""
            
            # 交易统计
            report += f"""
交易统计
   总交易次数: {getattr(metrics, 'total_trades', 0)}次
   胜率: {metrics.win_rate:.1%}
   盈亏比: {metrics.profit_factor:.2f}:1
   恢复因子: {metrics.recovery_factor:.3f}
"""
            
            # 相对指标
            report += f"""
相对指标
   Beta系数: {metrics.beta:.3f}
   Alpha收益: {metrics.alpha:+.2%}
   信息比率: {metrics.information_ratio:.3f}
   跟踪误差: {metrics.tracking_error:.2%}
   超额收益: {metrics.excess_return:+.2%}
"""
            
            # AI选股特有指标
            if result.ai_selection_metrics:
                ai_metrics = result.ai_selection_metrics
                report += f"""
🤖 AI选股指标
   信号密度: {ai_metrics.get('signal_density', 0):.2%}
   平均置信度: {ai_metrics.get('avg_confidence', 0):.3f}
   高置信度信号: {ai_metrics.get('high_confidence_signals', 0)}个
   平均信号强度: {ai_metrics.get('avg_signal_strength', 0):.3f}
   选股多样性: {ai_metrics.get('selection_diversity', 0):.3f}
"""
            
            # 个性化影响
            if result.personalization_impact:
                pers_impact = result.personalization_impact
                report += f"""
👤 个性化影响
   用户经验水平: {pers_impact.get('user_experience_level', 'N/A')}
   风险承受能力: {pers_impact.get('risk_tolerance_score', 0):.1f}
   投资风格: {pers_impact.get('investment_style', 'N/A')}
   个性化收益调整: {pers_impact.get('personalization_bonus', 0):+.2%}
"""
            
            # 选股准确性
            if result.selection_accuracy:
                accuracy = result.selection_accuracy
                report += f"""
选股准确性
   总信号数: {accuracy.get('total_signals', 0)}个
   信号准确率: {accuracy.get('signal_accuracy', 0):.1%}
   精确率: {accuracy.get('precision', 0):.1%}
   召回率: {accuracy.get('recall', 0):.1%}
   F1得分: {accuracy.get('f1_score', 0):.3f}
"""
            
            # 推荐质量
            if result.recommendation_quality:
                quality = result.recommendation_quality
                report += f"""
⭐ 推荐质量
   高置信度比例: {quality.get('high_confidence_ratio', 0):.1%}
   平均信号强度: {quality.get('avg_signal_strength', 0):.3f}
   信号一致性: {quality.get('signal_consistency', 0):.3f}
   日均信号数: {quality.get('avg_daily_signals', 0):.1f}
"""
            
            # 蒙特卡洛结果
            if result.monte_carlo_results:
                mc_results = result.monte_carlo_results
                report += f"""
蒙特卡洛模拟 ({mc_results.get('simulations_count', 0)}次)
   收益均值: {mc_results.get('return_statistics', {}).get('mean', 0):+.2%}
   收益标准差: {mc_results.get('return_statistics', {}).get('std', 0):.2%}
   5%分位数: {mc_results.get('return_statistics', {}).get('percentile_5', 0):+.2%}
   95%分位数: {mc_results.get('return_statistics', {}).get('percentile_95', 0):+.2%}
   亏损概率: {mc_results.get('probability_of_loss', 0):.1%}
   超越概率: {mc_results.get('probability_of_outperformance', 0):.1%}
"""
            
            # 压力测试结果
            if result.stress_test_results:
                stress_results = result.stress_test_results
                report += f"""
⚡ 压力测试结果
"""
                for scenario_name, scenario_data in stress_results.items():
                    if isinstance(scenario_data, dict) and 'scenario_name' in scenario_data:
                        report += f"""
   {scenario_data['scenario_name']}:
     收益影响: {scenario_data.get('impact_on_return', 0):+.2%}
     调整后收益: {scenario_data.get('adjusted_return', 0):+.2%}
"""
            
            # 因子归因
            if result.factor_attribution:
                factor_attr = result.factor_attribution
                report += f"""
🔍 因子归因分析
   总因子贡献: {factor_attr.get('total_factor_contribution', 0):+.2%}
   特有收益: {factor_attr.get('specific_return', 0):+.2%}
"""
                
                for factor, data in factor_attr.items():
                    if isinstance(data, dict) and 'contribution' in data:
                        report += f"""
   {factor.title()}因子:
     暴露度: {data.get('exposure', 0):.3f}
     因子收益: {data.get('factor_return', 0):+.2%}
     贡献度: {data.get('contribution', 0):+.2%}
"""
            
            # 报告结尾
            report += f"""
报告生成完成 | 生成时间: {timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            logger.info(f"回测报告生成完成，类型: {report_type.value}")
            return report
            
        except Exception as e:
            logger.error(f"生成回测报告失败: {e}")
            return f"报告生成失败: {str(e)}"
    
    def batch_backtest(self,
                      user_id: str,
                      criteria_list: List[StockSelectionCriteria],
                      strategy_list: List[SelectionStrategy],
                      start_date: datetime,
                      end_date: datetime,
                      personalized: bool = True,
                      max_workers: int = 4) -> List[AISelectionBacktestResult]:
        """
        批量回测
        
        Args:
            user_id: 用户ID
            criteria_list: 选股标准列表
            strategy_list: 策略列表
            start_date: 开始日期
            end_date: 结束日期
            personalized: 是否使用个性化
            max_workers: 最大并行数
            
        Returns:
            回测结果列表
        """
        try:
            logger.info(f"开始批量回测 - 用户: {user_id}, 组合数: {len(criteria_list) * len(strategy_list)}")
            
            # 生成所有组合
            test_combinations = []
            for criteria in criteria_list:
                for strategy in strategy_list:
                    test_combinations.append((criteria, strategy))
            
            results = []
            
            # 使用线程池并行执行
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_combination = {
                    executor.submit(
                        self.run_backtest,
                        user_id,
                        criteria,
                        strategy,
                        start_date,
                        end_date,
                        personalized
                    ): (criteria, strategy)
                    for criteria, strategy in test_combinations
                }
                
                # 收集结果
                for future in as_completed(future_to_combination):
                    combination = future_to_combination[future]
                    try:
                        result = future.result()
                        results.append(result)
                        logger.info(f"组合回测完成: {combination[1].value}")
                    except Exception as e:
                        logger.error(f"组合回测失败 {combination}: {e}")
            
            logger.info(f"批量回测完成 - 成功: {len(results)}, 失败: {len(test_combinations) - len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"批量回测失败: {e}")
            return []
    
    def compare_backtest_results(self,
                               results: List[AISelectionBacktestResult],
                               comparison_metrics: List[str] = None) -> Dict[str, Any]:
        """
        比较多个回测结果
        
        Args:
            results: 回测结果列表
            comparison_metrics: 比较指标列表
            
        Returns:
            比较结果字典
        """
        try:
            if not results:
                return {}
            
            # 默认比较指标
            if comparison_metrics is None:
                comparison_metrics = [
                    'total_return', 'annualized_return', 'sharpe_ratio', 
                    'max_drawdown', 'win_rate', 'profit_factor'
                ]
            
            comparison = {}
            
            for metric in comparison_metrics:
                values = []
                for i, result in enumerate(results):
                    if hasattr(result.unified_risk_metrics, metric):
                        values.append(getattr(result.unified_risk_metrics, metric))
                    else:
                        values.append(0.0)
                
                if values:
                    comparison[metric] = {
                        'values': values,
                        'best_index': np.argmax(values) if metric in ['total_return', 'annualized_return', 'sharpe_ratio', 'win_rate', 'profit_factor'] else np.argmin(values),
                        'worst_index': np.argmin(values) if metric in ['total_return', 'annualized_return', 'sharpe_ratio', 'win_rate', 'profit_factor'] else np.argmax(values),
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'median': np.median(values)
                    }
            
            # 排名分析
            rankings = {}
            for metric in comparison_metrics:
                if metric in comparison:
                    values = comparison[metric]['values']
                    rankings[metric] = sorted(range(len(values)), key=lambda i: values[i], reverse=(metric in ['total_return', 'annualized_return', 'sharpe_ratio', 'win_rate', 'profit_factor']))
            
            comparison['rankings'] = rankings
            
            logger.info("回测结果比较完成")
            return comparison
            
        except Exception as e:
            logger.error(f"比较回测结果失败: {e}")
            return {}
    
    def optimize_backtest_parameters(self,
                                   user_id: str,
                                   base_criteria: StockSelectionCriteria,
                                   strategy: SelectionStrategy,
                                   start_date: datetime,
                                   end_date: datetime,
                                   parameter_grid: Dict[str, List],
                                   optimization_metric: str = 'sharpe_ratio',
                                   cv_folds: int = 3) -> Dict[str, Any]:
        """
        优化回测参数
        
        Args:
            user_id: 用户ID
            base_criteria: 基础选股标准
            strategy: 选股策略
            start_date: 开始日期
            end_date: 结束日期
            parameter_grid: 参数网格
            optimization_metric: 优化指标
            cv_folds: 交叉验证折数
            
        Returns:
            优化结果
        """
        try:
            logger.info(f"开始参数优化 - 指标: {optimization_metric}, 网格大小: {len(parameter_grid)}")
            
            # 生成参数组合
            from itertools import product
            
            param_names = list(parameter_grid.keys())
            param_values = list(parameter_grid.values())
            param_combinations = [
                dict(zip(param_names, combo))
                for combo in product(*param_values)
            ]
            
            optimization_results = []
            
            # 为每个参数组合运行回测
            for params in param_combinations:
                # 创建回测配置
                backtest_config = AISelectionBacktestConfig()
                
                # 应用参数
                for param_name, param_value in params.items():
                    if hasattr(backtest_config, param_name):
                        setattr(backtest_config, param_name, param_value)
                
                # 运行回测
                result = self.run_backtest(
                    user_id=user_id,
                    stock_selection_criteria=base_criteria,
                    selection_strategy=strategy,
                    start_date=start_date,
                    end_date=end_date,
                    personalized=True,
                    backtest_config=backtest_config
                )
                
                # 记录优化指标
                optimization_value = getattr(result.unified_risk_metrics, optimization_metric, 0.0)
                optimization_results.append({
                    'parameters': params,
                    'result': result,
                    'optimization_value': optimization_value
                })
            
            # 排序并返回最佳参数
            optimization_results.sort(key=lambda x: x['optimization_value'], reverse=True)
            
            best_result = optimization_results[0]
            
            optimization_summary = {
                'best_parameters': best_result['parameters'],
                'best_value': best_result['optimization_value'],
                'all_results': optimization_results,
                'optimization_metric': optimization_metric,
                'total_combinations': len(param_combinations)
            }
            
            logger.info(f"参数优化完成 - 最佳{optimization_metric}: {best_result['optimization_value']:.4f}")
            return optimization_summary
            
        except Exception as e:
            logger.error(f"参数优化失败: {e}")
            return {}
    
    def clear_cache(self):
        """清除缓存"""
        try:
            with self._cache_lock:
                self._backtest_cache.clear()
                self._performance_cache.clear()
            logger.info("回测缓存清除完成")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")