from loguru import logger
"""
实时回测监控和报告系统
提供实时性能监控、动态报告生成、风险预警等功能
对标Bloomberg Terminal、Wind、聚宽等专业平台
"""

import numpy as np
import pandas as pd
import asyncio
import threading
import queue
import time
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import psutil
import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.animation import FuncAnimation
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from backtest.unified_backtest_engine import UnifiedRiskMetrics, BacktestLevel

class MonitoringLevel(Enum):
    """监控级别"""
    BASIC = "basic"              # 基础监控
    STANDARD = "standard"        # 标准监控
    ADVANCED = "advanced"        # 高级监控
    REAL_TIME = "real_time"      # 实时监控

class AlertLevel(Enum):
    """预警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class RealTimeMetrics:
    """实时指标数据类"""
    timestamp: datetime
    current_return: float
    cumulative_return: float
    current_drawdown: float
    max_drawdown: float
    sharpe_ratio: float
    volatility: float
    var_95: float
    position_count: int
    trade_count: int
    win_rate: float
    profit_factor: float

    # 性能指标
    execution_time: float
    memory_usage: float
    cpu_usage: float

@dataclass
class AlertMessage:
    """预警消息数据类"""
    timestamp: datetime
    level: AlertLevel
    category: str
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    recommendation: str

class RealTimeBacktestMonitor:
    """
    实时回测监控器
    提供实时性能监控、动态图表更新、风险预警等功能
    """

    def __init__(self,
                 monitoring_level: MonitoringLevel = MonitoringLevel.REAL_TIME,
                 update_interval: float = 1.0):
        """
        初始化实时监控器

        Args:
            monitoring_level: 监控级别
            update_interval: 更新间隔（秒）
            # log_manager: 已迁移到Loguru日志系统
        """
        self.monitoring_level = monitoring_level
        self.update_interval = update_interval
        # 纯Loguru架构，移除log_manager依赖

        # 数据存储
        self.metrics_history: List[RealTimeMetrics] = []
        self.alerts_history: List[AlertMessage] = []
        self.data_queue = queue.Queue()

        # 监控状态
        self.is_monitoring = False
        self.monitor_thread = None

        # 预警阈值
        self.alert_thresholds = self._initialize_alert_thresholds()

        # 数据库连接
        self.db_path = Path("data/backtest_monitor.sqlite")
        self._initialize_database()

        # 图表配置
        self.chart_config = self._initialize_chart_config()

    def _initialize_alert_thresholds(self) -> Dict[str, Dict]:
        """初始化预警阈值"""
        return {
            "max_drawdown": {
                "warning": 0.10,    # 10%回撤预警
                "critical": 0.20,   # 20%回撤严重预警
                "emergency": 0.30   # 30%回撤紧急预警
            },
            "sharpe_ratio": {
                "warning": 0.5,     # Sharpe比率低于0.5预警
                "critical": 0.0,    # Sharpe比率为负严重预警
                "emergency": -1.0   # Sharpe比率低于-1紧急预警
            },
            "var_95": {
                "warning": -0.03,   # 日VaR超过3%预警
                "critical": -0.05,  # 日VaR超过5%严重预警
                "emergency": -0.10  # 日VaR超过10%紧急预警
            },
            "volatility": {
                "warning": 0.25,    # 年化波动率超过25%预警
                "critical": 0.40,   # 年化波动率超过40%严重预警
                "emergency": 0.60   # 年化波动率超过60%紧急预警
            },
            "win_rate": {
                "warning": 0.30,    # 胜率低于30%预警
                "critical": 0.20,   # 胜率低于20%严重预警
                "emergency": 0.10   # 胜率低于10%紧急预警
            }
        }

    def _initialize_database(self):
        """初始化数据库"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as conn:
                # 创建指标历史表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS metrics_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        current_return REAL,
                        cumulative_return REAL,
                        current_drawdown REAL,
                        max_drawdown REAL,
                        sharpe_ratio REAL,
                        volatility REAL,
                        var_95 REAL,
                        position_count INTEGER,
                        trade_count INTEGER,
                        win_rate REAL,
                        profit_factor REAL,
                        execution_time REAL,
                        memory_usage REAL,
                        cpu_usage REAL
                    )
                """)

                # 创建预警历史表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS alerts_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        level TEXT NOT NULL,
                        category TEXT NOT NULL,
                        message TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        current_value REAL,
                        threshold_value REAL,
                        recommendation TEXT
                    )
                """)

                conn.commit()

        except Exception as e:
            logger.error(f"初始化数据库失败: {e}")

    def _initialize_chart_config(self) -> Dict[str, Any]:
        """初始化图表配置"""
        return {
            "theme": "plotly_dark",
            "color_palette": px.colors.qualitative.Set3,
            "figure_size": (1200, 800),
            "update_interval": 1000,  # 毫秒
            "max_points": 1000,       # 最大显示点数
            "chart_types": {
                "performance": ["cumulative_return", "drawdown"],
                "risk": ["sharpe_ratio", "volatility", "var_95"],
                "trading": ["win_rate", "profit_factor", "trade_count"],
                "system": ["execution_time", "memory_usage", "cpu_usage"]
            }
        }

    def start_monitoring(self, backtest_engine: Any, data: pd.DataFrame, **kwargs):
        """
        开始实时监控

        Args:
            backtest_engine: 回测引擎
            data: 回测数据
            **kwargs: 回测参数
        """
        try:
            if self.is_monitoring:
                logger.warning("监控已在运行中")
                return

            # 如果有旧的线程还在运行，先停止它
            if self.monitor_thread and self.monitor_thread.is_alive():
                logger.info("停止旧的监控线程")
                self.stop_monitoring()

            self.is_monitoring = True
            self.metrics_history.clear()
            self.alerts_history.clear()

            logger.info(
                f"开始实时监控 - 级别: {self.monitoring_level.value}")

            # 启动监控线程
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(backtest_engine, data),
                kwargs=kwargs,
                daemon=False,  # 改为非守护线程，确保可以正确停止
                name=f"BacktestMonitor-{threading.get_ident()}"
            )
            self.monitor_thread.start()

            logger.info(f"实时监控已启动 - 线程ID: {self.monitor_thread.ident}")

        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            self.is_monitoring = False

    def stop_monitoring(self):
        """停止监控"""
        try:
            logger.info("正在停止监控...")
            self.is_monitoring = False

            # 安全检查：确保 monitor_thread 不为 None
            if self.monitor_thread is None:
                logger.info("监控线程对象为 None，无需停止")
                return

            # 保存线程引用，避免竞态条件
            thread_to_stop = self.monitor_thread
            self.monitor_thread = None

            # 检查线程是否存活
            try:
                if not thread_to_stop.is_alive():
                    logger.info(f"监控线程已结束 - 线程ID: {thread_to_stop.ident}")
                    return
            except (AttributeError, Exception) as e:
                logger.warning(f"检查线程状态失败: {e}")
                return

            logger.info(f"等待监控线程结束 - 线程ID: {thread_to_stop.ident}")

            # 检查是否是当前线程
            current_thread = threading.current_thread()
            if thread_to_stop is current_thread:
                logger.info("当前线程为监控线程，跳过 join 操作")
            else:
                # 等待线程结束
                thread_to_stop.join(timeout=10.0)

                # 再次检查线程状态
                try:
                    if thread_to_stop.is_alive():
                        logger.warning(f"监控线程未能在10秒内结束 - 线程ID: {thread_to_stop.ident}")
                    else:
                        logger.info("监控线程已正常结束")
                except (AttributeError, Exception) as e:
                    logger.warning(f"检查线程状态失败: {e}")

            logger.info("监控已停止")

        except Exception as e:
            logger.error(f"停止监控失败: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop_monitoring()

    def get_latest_metrics(self) -> Optional[RealTimeMetrics]:
        """获取最新的监控指标"""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None

    def get_data_queue(self) -> queue.Queue:
        """获取数据队列，用于实时数据获取"""
        return self.data_queue

    def _monitor_loop(self, backtest_engine: Any, data: pd.DataFrame, **kwargs):
        """监控循环"""
        thread_name = threading.current_thread().name
        logger.info(f"监控循环开始 - 线程: {thread_name}")

        try:
            chunk_size = max(100, len(data) // 100)  # 动态调整块大小
            processed_rows = 0

            while self.is_monitoring and processed_rows < len(data):
                # 检查停止信号（更频繁的检查）
                if not self.is_monitoring:
                    logger.info(f"收到停止信号，退出监控循环 - 线程: {thread_name}")
                    break

                start_time = time.time()

                # 处理数据块
                end_row = min(processed_rows + chunk_size, len(data))
                chunk_data = data.iloc[:end_row].copy()

                # 过滤掉 run_backtest 不支持的参数
                filtered_kwargs = {
                    k: v for k, v in kwargs.items()
                    if k in ['signal_col', 'price_col', 'initial_capital', 'position_size',
                             'commission_pct', 'slippage_pct', 'min_commission', 'stop_loss_pct',
                             'take_profit_pct', 'max_holding_periods', 'enable_compound', 'benchmark_data']
                    # 不包含 progress_callback，因为监控器有自己的进度逻辑，避免与引擎内部回调冲突
                }

                # 运行回测
                result = backtest_engine.run_backtest(
                    chunk_data, **filtered_kwargs)

                # 调用进度回调
                progress_callback = kwargs.get('progress_callback')
                if progress_callback and callable(progress_callback):
                    try:
                        progress_callback(processed_rows, len(data), result)
                    except Exception as e:
                        logger.warning(f"进度回调失败: {e}")

                # 再次检查停止信号
                if not self.is_monitoring:
                    logger.info(f"收到停止信号，退出监控循环 - 线程: {thread_name}")
                    break

                # 计算实时指标
                metrics = self._calculate_real_time_metrics(result, start_time)

                # 检查预警
                alerts = self._check_alerts(metrics)

                # 存储数据
                self._store_metrics(metrics)
                self._store_alerts(alerts)

                # 更新历史记录
                self.metrics_history.append(metrics)
                self.alerts_history.extend(alerts)

                # 限制历史记录长度
                if len(self.metrics_history) > self.chart_config["max_points"]:
                    self.metrics_history = self.metrics_history[-self.chart_config["max_points"]:]

                # 发送数据到队列（用于实时图表更新）
                try:
                    self.data_queue.put({
                        'type': 'metrics',
                        'data': metrics,
                        'progress': processed_rows / len(data)
                    }, timeout=1.0)  # 添加超时避免阻塞

                    if alerts:
                        self.data_queue.put({
                            'type': 'alerts',
                            'data': alerts
                        }, timeout=1.0)
                except queue.Full:
                    logger.warning("数据队列已满，跳过本次数据推送")

                processed_rows = end_row

                # 短暂休眠，给其他线程机会，同时允许更快响应停止信号
                time.sleep(0.01)

                # 控制更新频率
                elapsed = time.time() - start_time
                if elapsed < self.update_interval:
                    time.sleep(self.update_interval - elapsed)

        except Exception as e:
            logger.error(f"监控循环异常: {e}")
        finally:
            self.is_monitoring = False

    def _calculate_real_time_metrics(self, backtest_result: Any, start_time: float) -> RealTimeMetrics:
        """计算实时指标"""
        try:
            # 处理不同的结果格式
            if isinstance(backtest_result, pd.DataFrame):
                # 如果是DataFrame格式（直接返回）
                result_df = backtest_result
                
                # 计算累计收益
                if 'returns' in result_df.columns:
                    cumulative_series = (1 + result_df['returns']).cumprod()
                    cumulative_return = cumulative_series.iloc[-1] - 1 if len(cumulative_series) > 0 else 0
                else:
                    cumulative_return = 0.0
                
                # 计算当前回撤
                current_drawdown = 0.0
                if 'returns' in result_df.columns and len(result_df) > 0:
                    cumulative_series = (1 + result_df['returns']).cumprod()
                    running_max = cumulative_series.cummax()
                    current_drawdown = (
                        (cumulative_series.iloc[-1] - running_max.iloc[-1]) / running_max.iloc[-1]) if running_max.iloc[-1] != 0 else 0
                
                # 从DataFrame计算其他指标
                if 'position' in result_df.columns:
                    position_count = int((result_df['position'] != 0).sum())
                else:
                    position_count = 0
                
                # 获取最新的单期收益
                if 'returns' in result_df.columns and len(result_df) > 0:
                    latest_return = result_df['returns'].iloc[-1]
                else:
                    latest_return = 0.0
                
                # 创建默认的风险指标
                from backtest.unified_backtest_engine import UnifiedRiskMetrics
                risk_metrics = UnifiedRiskMetrics(
                    total_return=cumulative_return,
                    max_drawdown=abs(current_drawdown),
                    annualized_return=cumulative_return * 12 if len(result_df) >= 12 else cumulative_return,
                    sharpe_ratio=0.0, sortino_ratio=0.0, volatility=0.0,
                    var_95=0.0, win_rate=0.0, profit_factor=0.0
                )
                trade_stats = {'total_trades': 0}
                
            elif isinstance(backtest_result, dict):
                # 如果是字典格式
                result_df = backtest_result.get('backtest_result', pd.DataFrame())
                risk_metrics = backtest_result.get('risk_metrics', None)
                trade_stats = backtest_result.get('trade_statistics', {'total_trades': 0})
                
                # 确保我们有所有必要的数据
                if risk_metrics is None:
                    from backtest.unified_backtest_engine import UnifiedRiskMetrics
                    risk_metrics = UnifiedRiskMetrics()
                
                # 计算累计收益
                if 'returns' in result_df.columns and len(result_df) > 0:
                    cumulative_series = (1 + result_df['returns']).cumprod()
                    cumulative_return = cumulative_series.iloc[-1] - 1
                else:
                    cumulative_return = risk_metrics.total_return
                
                # 计算当前回撤
                current_drawdown = risk_metrics.current_drawdown if hasattr(risk_metrics, 'current_drawdown') else 0.0
                
                # 获取最新的单期收益
                if 'returns' in result_df.columns and len(result_df) > 0:
                    latest_return = result_df['returns'].iloc[-1]
                else:
                    latest_return = 0.0
                
                # 仓位计数
                if 'position' in result_df.columns:
                    position_count = int((result_df['position'] != 0).sum())
                else:
                    position_count = 0
                    
            else:
                # 默认情况，创建空DataFrame
                result_df = pd.DataFrame()
                from backtest.unified_backtest_engine import UnifiedRiskMetrics
                risk_metrics = UnifiedRiskMetrics()
                trade_stats = {'total_trades': 0}
                cumulative_return = 0.0
                current_drawdown = 0.0
                latest_return = 0.0
                position_count = 0

            # 性能指标
            execution_time = time.time() - start_time
            memory_usage = self._get_memory_usage()
            cpu_usage = self._get_cpu_usage()

            return RealTimeMetrics(
                timestamp=datetime.now(),
                current_return=latest_return,
                cumulative_return=cumulative_return,
                current_drawdown=current_drawdown,
                max_drawdown=risk_metrics.max_drawdown,
                sharpe_ratio=risk_metrics.sharpe_ratio,
                volatility=risk_metrics.volatility,
                var_95=risk_metrics.var_95,
                position_count=position_count,
                trade_count=trade_stats.get('total_trades', 0),
                win_rate=risk_metrics.win_rate,
                profit_factor=risk_metrics.profit_factor,
                execution_time=execution_time,
                memory_usage=memory_usage,
                cpu_usage=cpu_usage
            )

        except Exception as e:
            logger.error(f"计算实时指标失败: {e}")
            return RealTimeMetrics(
                timestamp=datetime.now(),
                current_return=0, cumulative_return=0, current_drawdown=0,
                max_drawdown=0, sharpe_ratio=0, volatility=0, var_95=0,
                position_count=0, trade_count=0, win_rate=0, profit_factor=0,
                execution_time=0, memory_usage=0, cpu_usage=0
            )

    def _get_memory_usage(self) -> float:
        """获取内存使用率"""
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0

    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception:
            return 0.0

    def _check_alerts(self, metrics: RealTimeMetrics) -> List[AlertMessage]:
        """检查预警条件"""
        alerts = []

        try:
            # 检查最大回撤
            alerts.extend(self._check_metric_alert(
                "max_drawdown", metrics.max_drawdown, "风险管理",
                "最大回撤超过阈值", lambda cv, th: cv > th
            ))

            # 检查Sharpe比率
            alerts.extend(self._check_metric_alert(
                "sharpe_ratio", metrics.sharpe_ratio, "收益质量",
                "Sharpe比率低于阈值", lambda cv, th: cv < th
            ))

            # 检查VaR
            alerts.extend(self._check_metric_alert(
                "var_95", metrics.var_95, "风险管理",
                "VaR风险超过阈值", lambda cv, th: cv < th
            ))

            # 检查波动率
            alerts.extend(self._check_metric_alert(
                "volatility", metrics.volatility, "风险管理",
                "波动率超过阈值", lambda cv, th: cv > th
            ))

            # 检查胜率
            alerts.extend(self._check_metric_alert(
                "win_rate", metrics.win_rate, "交易质量",
                "胜率低于阈值", lambda cv, th: cv < th
            ))

        except Exception as e:
            logger.error(f"检查预警失败: {e}")

        return alerts

    def _check_metric_alert(self, metric_name: str, current_value: float,
                            category: str, message_template: str,
                            condition_func: Callable) -> List[AlertMessage]:
        """检查单个指标的预警"""
        alerts = []
        thresholds = self.alert_thresholds.get(metric_name, {})

        for level_name, threshold in thresholds.items():
            if condition_func(current_value, threshold) and abs(current_value) >= abs(threshold):
                level = AlertLevel(level_name)

                alert = AlertMessage(
                    timestamp=datetime.now(),
                    level=level,
                    category=category,
                    message=f"{message_template}: {current_value:.4f}",
                    metric_name=metric_name,
                    current_value=current_value,
                    threshold_value=threshold,
                    recommendation=self._get_recommendation(metric_name, level)
                )
                alerts.append(alert)
                break  # 只触发最高级别的预警

        return alerts

    def _get_recommendation(self, metric_name: str, level: AlertLevel) -> str:
        """获取预警建议"""
        recommendations = {
            "max_drawdown": {
                AlertLevel.WARNING: "建议减少仓位或加强止损",
                AlertLevel.CRITICAL: "建议立即减仓并检查策略",
                AlertLevel.EMERGENCY: "建议停止交易并全面检查策略"
            },
            "sharpe_ratio": {
                AlertLevel.WARNING: "建议优化策略参数",
                AlertLevel.CRITICAL: "建议暂停策略并重新评估",
                AlertLevel.EMERGENCY: "建议停止策略并进行全面检查"
            },
            "var_95": {
                AlertLevel.WARNING: "建议关注风险控制",
                AlertLevel.CRITICAL: "建议加强风险管理措施",
                AlertLevel.EMERGENCY: "建议立即降低风险敞口"
            },
            "volatility": {
                AlertLevel.WARNING: "建议降低策略波动性",
                AlertLevel.CRITICAL: "建议调整策略参数降低波动",
                AlertLevel.EMERGENCY: "建议暂停高波动策略"
            },
            "win_rate": {
                AlertLevel.WARNING: "建议优化入场时机",
                AlertLevel.CRITICAL: "建议重新评估策略逻辑",
                AlertLevel.EMERGENCY: "建议停止策略并重新设计"
            }
        }

        return recommendations.get(metric_name, {}).get(level, "建议咨询专业人士")

    def _store_metrics(self, metrics: RealTimeMetrics):
        """存储指标到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO metrics_history (
                        timestamp, current_return, cumulative_return, current_drawdown,
                        max_drawdown, sharpe_ratio, volatility, var_95, position_count,
                        trade_count, win_rate, profit_factor, execution_time,
                        memory_usage, cpu_usage
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metrics.timestamp.isoformat(),
                    metrics.current_return,
                    metrics.cumulative_return,
                    metrics.current_drawdown,
                    metrics.max_drawdown,
                    metrics.sharpe_ratio,
                    metrics.volatility,
                    metrics.var_95,
                    metrics.position_count,
                    metrics.trade_count,
                    metrics.win_rate,
                    metrics.profit_factor,
                    metrics.execution_time,
                    metrics.memory_usage,
                    metrics.cpu_usage
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"存储指标失败: {e}")

    def _store_alerts(self, alerts: List[AlertMessage]):
        """存储预警到数据库"""
        try:
            if not alerts:
                return

            with sqlite3.connect(self.db_path) as conn:
                for alert in alerts:
                    conn.execute("""
                        INSERT INTO alerts_history (
                            timestamp, level, category, message, metric_name,
                            current_value, threshold_value, recommendation
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        alert.timestamp.isoformat(),
                        alert.level.value,
                        alert.category,
                        alert.message,
                        alert.metric_name,
                        alert.current_value,
                        alert.threshold_value,
                        alert.recommendation
                    ))
                conn.commit()

        except Exception as e:
            logger.error(f"存储预警失败: {e}")

    def generate_real_time_dashboard(self, output_path: str = "reports/real_time_dashboard.html"):
        """生成实时仪表板"""
        try:
            if not self.metrics_history:
                logger.warning("没有监控数据，无法生成仪表板")
                return

            # 创建子图
            fig = make_subplots(
                rows=3, cols=2,
                subplot_titles=[
                    "累积收益率", "回撤分析",
                    "风险指标", "交易统计",
                    "系统性能", "预警统计"
                ],
                specs=[
                    [{"secondary_y": False}, {"secondary_y": False}],
                    [{"secondary_y": True}, {"secondary_y": False}],
                    [{"secondary_y": True}, {"type": "bar"}]
                ]
            )

            # 准备数据
            timestamps = [m.timestamp for m in self.metrics_history]
            cumulative_returns = [
                m.cumulative_return for m in self.metrics_history]
            drawdowns = [m.current_drawdown for m in self.metrics_history]
            sharpe_ratios = [m.sharpe_ratio for m in self.metrics_history]
            volatilities = [m.volatility for m in self.metrics_history]
            win_rates = [m.win_rate for m in self.metrics_history]
            trade_counts = [m.trade_count for m in self.metrics_history]
            execution_times = [m.execution_time for m in self.metrics_history]
            memory_usages = [m.memory_usage for m in self.metrics_history]

            # 1. 累积收益率
            fig.add_trace(
                go.Scatter(x=timestamps, y=cumulative_returns,
                           name="累积收益率", line=dict(color="green")),
                row=1, col=1
            )

            # 2. 回撤分析
            fig.add_trace(
                go.Scatter(x=timestamps, y=drawdowns, name="当前回撤",
                           fill='tonexty', line=dict(color="red")),
                row=1, col=2
            )

            # 3. 风险指标
            fig.add_trace(
                go.Scatter(x=timestamps, y=sharpe_ratios,
                           name="Sharpe比率", line=dict(color="blue")),
                row=2, col=1
            )
            fig.add_trace(
                go.Scatter(x=timestamps, y=volatilities,
                           name="波动率", line=dict(color="orange")),
                row=2, col=1, secondary_y=True
            )

            # 4. 交易统计
            fig.add_trace(
                go.Scatter(x=timestamps, y=win_rates, name="胜率",
                           line=dict(color="purple")),
                row=2, col=2
            )

            # 5. 系统性能
            fig.add_trace(
                go.Scatter(x=timestamps, y=execution_times,
                           name="执行时间", line=dict(color="brown")),
                row=3, col=1
            )
            fig.add_trace(
                go.Scatter(x=timestamps, y=memory_usages,
                           name="内存使用", line=dict(color="pink")),
                row=3, col=1, secondary_y=True
            )

            # 6. 预警统计
            alert_counts = self._get_alert_statistics()
            fig.add_trace(
                go.Bar(x=list(alert_counts.keys()), y=list(
                    alert_counts.values()), name="预警次数"),
                row=3, col=2
            )

            # 更新布局
            fig.update_layout(
                title="实时回测监控仪表板",
                height=1000,
                showlegend=True,
                template=self.chart_config["theme"]
            )

            # 保存仪表板
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            fig.write_html(output_path)

            logger.info(f"实时仪表板已生成: {output_path}")

        except Exception as e:
            logger.error(f"生成实时仪表板失败: {e}")

    def _get_alert_statistics(self) -> Dict[str, int]:
        """获取预警统计"""
        try:
            alert_counts = {}
            for alert in self.alerts_history:
                level = alert.level.value
                alert_counts[level] = alert_counts.get(level, 0) + 1
            return alert_counts

        except Exception:
            return {}

    def generate_performance_report(self, output_path: str = "reports/performance_report.html") -> str:
        """生成性能报告"""
        try:
            if not self.metrics_history:
                return "没有监控数据"

            latest_metrics = self.metrics_history[-1]

            # 生成HTML报告
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>实时回测性能报告</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                    .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }}
                    .metric-card {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }}
                    .alert {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                    .critical {{ background-color: #f8d7da; border-color: #f5c6cb; }}
                    .emergency {{ background-color: #d1ecf1; border-color: #bee5eb; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>实时回测性能报告</h1>
                    <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>监控级别: {self.monitoring_level.value}</p>
                </div>
                
                <h2>关键指标</h2>
                <div class="metrics">
                    <div class="metric-card">
                        <h3>累积收益率</h3>
                        <p>{latest_metrics.cumulative_return:.2%}</p>
                    </div>
                    <div class="metric-card">
                        <h3>最大回撤</h3>
                        <p>{latest_metrics.max_drawdown:.2%}</p>
                    </div>
                    <div class="metric-card">
                        <h3>Sharpe比率</h3>
                        <p>{latest_metrics.sharpe_ratio:.3f}</p>
                    </div>
                    <div class="metric-card">
                        <h3>年化波动率</h3>
                        <p>{latest_metrics.volatility:.2%}</p>
                    </div>
                    <div class="metric-card">
                        <h3>胜率</h3>
                        <p>{latest_metrics.win_rate:.2%}</p>
                    </div>
                    <div class="metric-card">
                        <h3>交易次数</h3>
                        <p>{latest_metrics.trade_count}</p>
                    </div>
                </div>
                
                <h2>系统性能</h2>
                <div class="metrics">
                    <div class="metric-card">
                        <h3>执行时间</h3>
                        <p>{latest_metrics.execution_time:.3f}秒</p>
                    </div>
                    <div class="metric-card">
                        <h3>内存使用</h3>
                        <p>{latest_metrics.memory_usage:.1f}%</p>
                    </div>
                    <div class="metric-card">
                        <h3>CPU使用</h3>
                        <p>{latest_metrics.cpu_usage:.1f}%</p>
                    </div>
                </div>
                
                <h2>最近预警</h2>
                {self._generate_alerts_html()}
                
            </body>
            </html>
            """

            # 保存报告
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"性能报告已生成: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"生成性能报告失败: {e}")
            return ""

    def _generate_alerts_html(self) -> str:
        """生成预警HTML"""
        try:
            if not self.alerts_history:
                return "<p>暂无预警信息</p>"

            # 获取最近的预警（最多10条）
            recent_alerts = self.alerts_history[-10:]

            html = ""
            for alert in reversed(recent_alerts):  # 最新的在前
                css_class = "alert"
                if alert.level == AlertLevel.CRITICAL:
                    css_class += " critical"
                elif alert.level == AlertLevel.EMERGENCY:
                    css_class += " emergency"

                html += f"""
                <div class="{css_class}">
                    <strong>{alert.level.value.upper()}</strong> - {alert.category}<br>
                    {alert.message}<br>
                    <small>时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</small><br>
                    <small>建议: {alert.recommendation}</small>
                </div>
                """

            return html

        except Exception:
            return "<p>预警信息加载失败</p>"

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        try:
            if not self.metrics_history:
                return {"status": "no_data", "message": "暂无监控数据"}

            latest = self.metrics_history[-1]

            # 计算统计信息
            returns = [m.cumulative_return for m in self.metrics_history]
            drawdowns = [m.max_drawdown for m in self.metrics_history]
            sharpe_ratios = [m.sharpe_ratio for m in self.metrics_history]

            return {
                "status": "active" if self.is_monitoring else "stopped",
                "monitoring_level": self.monitoring_level.value,
                "data_points": len(self.metrics_history),
                "latest_metrics": {
                    "timestamp": latest.timestamp.isoformat(),
                    "cumulative_return": latest.cumulative_return,
                    "max_drawdown": latest.max_drawdown,
                    "sharpe_ratio": latest.sharpe_ratio,
                    "trade_count": latest.trade_count
                },
                "statistics": {
                    "avg_return": np.mean(returns),
                    "max_return": max(returns),
                    "min_return": min(returns),
                    "avg_drawdown": np.mean(drawdowns),
                    "max_drawdown": max(drawdowns),
                    "avg_sharpe": np.mean(sharpe_ratios)
                },
                "alerts": {
                    "total_alerts": len(self.alerts_history),
                    "recent_alerts": len([a for a in self.alerts_history if a.timestamp > datetime.now() - timedelta(hours=1)])
                }
            }

        except Exception as e:
            logger.error(f"获取监控摘要失败: {e}")
            return {"status": "error", "message": str(e)}

# 便捷函数

def create_real_time_monitor(
        monitoring_level: MonitoringLevel = MonitoringLevel.REAL_TIME,
        update_interval: float = 1.0) -> RealTimeBacktestMonitor:
    """创建实时监控器"""
    return RealTimeBacktestMonitor(monitoring_level, update_interval)

def start_monitoring_session(
    backtest_engine: Any,
    data: pd.DataFrame,
    monitoring_level: MonitoringLevel = MonitoringLevel.REAL_TIME,
    **kwargs
) -> RealTimeBacktestMonitor:
    """启动监控会话"""
    monitor = create_real_time_monitor(monitoring_level)
    monitor.start_monitoring(backtest_engine, data, **kwargs)
    return monitor
