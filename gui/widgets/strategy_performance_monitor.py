from loguru import logger
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QFrame, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPainter, QLinearGradient

from core.events import (
    StrategyStartedEvent, StrategyStoppedEvent, SignalGeneratedEvent,
    PerformanceUpdatedEvent, EventType, EventPriority, EventFilter,
    get_event_bus, EventHandler
)
from core.strategy_extensions import TradingPerformanceMetrics


class PerformanceCard(QFrame):
    """性能指标卡片组件"""
    
    def __init__(self, title: str, value: str = "N/A", card_type: str = 'primary', parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.card_type = card_type
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(5)
        
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: #888; font-size: 12px;")
        
        value_label = QLabel(self.value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {self._get_color()};")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        self._apply_style()
    
    def _get_color(self):
        colors = {
            'primary': '#2962FF',
            'return': '#10B981',
            'sharpe': '#3B82F6',
            'drawdown': '#EF4444',
            'win_rate': '#F59E0B'
        }
        return colors.get(self.card_type, '#2962FF')
    
    def _apply_style(self):
        self.setStyleSheet(f"""
            PerformanceCard {{
                background-color: #1E1E1E;
                border-radius: 8px;
                border: 1px solid #333;
            }}
            PerformanceCard:hover {{
                border-color: {self._get_color()};
            }}
        """)
    
    def set_value(self, value: str):
        value_label = self.findChild(QLabel, "value")
        if value_label:
            value_label.setText(value)
    
    def update_metrics(self, metrics: TradingPerformanceMetrics):
        """更新性能指标"""
        pass


class StrategyPerformanceMonitor(QWidget):
    """
    策略性能监控面板
    
    实时监控策略性能指标，支持事件驱动更新。
    """
    
    performance_updated = pyqtSignal(dict)
    logger = logger.bind(module=__name__)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.strategy_id = None
        self.performance_history: List[Dict] = []
        self._event_subscription_ids: list = []
        self._setup_ui()
        self._setup_event_subscription()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        title = QLabel("策略性能监控")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFF;")
        layout.addWidget(title)
        
        self._create_metrics_section(layout)
        self._create_history_section(layout)
        self._create_realtime_chart(layout)
        
        layout.addStretch()
    
    def _create_metrics_section(self, parent_layout):
        metrics_group = QGroupBox("实时性能指标")
        metrics_layout = QGridLayout(metrics_group)
        
        self.total_return_card = PerformanceCard("总收益率", "0.00%", 'return')
        self.sharpe_card = PerformanceCard("夏普比率", "0.00", 'sharpe')
        self.max_drawdown_card = PerformanceCard("最大回撤", "0.00%", 'drawdown')
        self.win_rate_card = PerformanceCard("胜率", "0.0%", 'win_rate')
        self.total_trades_card = PerformanceCard("总交易次数", "0")
        self.profit_factor_card = PerformanceCard("盈亏比", "0.00")
        
        metrics_layout.addWidget(self.total_return_card, 0, 0)
        metrics_layout.addWidget(self.sharpe_card, 0, 1)
        metrics_layout.addWidget(self.max_drawdown_card, 0, 2)
        metrics_layout.addWidget(self.win_rate_card, 0, 3)
        metrics_layout.addWidget(self.total_trades_card, 1, 0)
        metrics_layout.addWidget(self.profit_factor_card, 1, 1)
        
        parent_layout.addWidget(metrics_group)
    
    def _create_history_section(self, parent_layout):
        history_group = QGroupBox("性能历史")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "收益率", "夏普比率", "最大回撤", "胜率", "交易次数", "盈亏比"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setRowCount(0)
        self.history_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.history_table.setMinimumHeight(100)
        self.history_table.setMaximumHeight(150)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #1E1E1E;
                color: #FFF;
                border: 1px solid #333;
            }
            QHeaderView::section {
                background-color: #2D2D2D;
                color: #FFF;
                padding: 5px;
            }
        """)
        
        history_layout.addWidget(self.history_table)
        parent_layout.addWidget(history_group)
    
    def _create_realtime_chart(self, parent_layout):
        chart_group = QGroupBox("收益曲线")
        chart_layout = QVBoxLayout(chart_group)
        
        self.equity_label = QLabel("收益曲线（实时更新）")
        self.equity_label.setStyleSheet("color: #888; font-size: 12px;")
        chart_layout.addWidget(self.equity_label)
        
        parent_layout.addWidget(chart_group)
    
    def _setup_event_subscription(self):
        """设置事件订阅"""
        try:
            event_bus = get_event_bus()

            def performance_handler(event):
                if isinstance(event, PerformanceUpdatedEvent):
                    self._on_performance_updated(event)
                elif isinstance(event, StrategyStoppedEvent):
                    self._on_strategy_stopped(event)

            sub_id1 = event_bus.subscribe(PerformanceUpdatedEvent, performance_handler, priority=0)
            sub_id2 = event_bus.subscribe(StrategyStoppedEvent, performance_handler, priority=0)
            self._event_subscription_ids.extend([sub_id1, sub_id2])

            logger.info("性能监控事件处理器已注册")

        except Exception as e:
            logger.warning(f"注册性能监控事件处理器失败: {e}")
    
    def _on_performance_updated(self, event: PerformanceUpdatedEvent):
        """处理性能更新事件"""
        try:
            if event.performance:
                self._update_metrics(event.performance)
                self._add_to_history(event.performance)
                
                self.performance_updated.emit({
                    'strategy_id': event.strategy_id,
                    'performance': event.performance
                })
                
        except Exception as e:
            self.logger.error(f"处理性能更新事件失败: {e}")
    
    def _on_strategy_stopped(self, event: StrategyStoppedEvent):
        """处理策略停止事件"""
        self.logger.info(f"策略 {event.strategy_id} 已停止")
    
    def _update_metrics(self, metrics: TradingPerformanceMetrics):
        """更新性能指标卡片"""
        self.total_return_card.set_value(f"{metrics.total_return*100:.2f}%")
        self.sharpe_card.set_value(f"{metrics.sharpe_ratio:.2f}")
        self.max_drawdown_card.set_value(f"{metrics.max_drawdown*100:.2f}%")
        self.win_rate_card.set_value(f"{metrics.win_rate*100:.1f}%")
        self.total_trades_card.set_value(str(metrics.total_trades))
        
        profit_factor = self._calculate_profit_factor(metrics)
        self.profit_factor_card.set_value(f"{profit_factor:.2f}")
    
    def _calculate_profit_factor(self, metrics: TradingPerformanceMetrics) -> float:
        """计算盈亏比"""
        if metrics.profitable_trades == 0:
            return 0.0
        if metrics.losing_trades == 0:
            return float('inf') if metrics.profitable_trades > 0 else 0.0
        return metrics.profitable_trades / metrics.losing_trades
    
    def _add_to_history(self, metrics: TradingPerformanceMetrics):
        """添加性能记录到历史"""
        record = {
            'timestamp': datetime.now(),
            'total_return': metrics.total_return,
            'sharpe_ratio': metrics.sharpe_ratio,
            'max_drawdown': metrics.max_drawdown,
            'win_rate': metrics.win_rate,
            'total_trades': metrics.total_trades
        }
        
        self.performance_history.append(record)
        
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        
        self.history_table.setItem(row, 0, QTableWidgetItem(record['timestamp'].strftime("%H:%M:%S")))
        self.history_table.setItem(row, 1, QTableWidgetItem(f"{metrics.total_return*100:.2f}%"))
        self.history_table.setItem(row, 2, QTableWidgetItem(f"{metrics.sharpe_ratio:.2f}"))
        self.history_table.setItem(row, 3, QTableWidgetItem(f"{metrics.max_drawdown*100:.2f}%"))
        self.history_table.setItem(row, 4, QTableWidgetItem(f"{metrics.win_rate*100:.1f}%"))
        self.history_table.setItem(row, 5, QTableWidgetItem(str(metrics.total_trades)))
        self.history_table.setItem(row, 6, QTableWidgetItem(f"{self._calculate_profit_factor(metrics):.2f}"))
        
        if self.history_table.rowCount() > 50:
            self.history_table.removeRow(0)
    
    def start_monitoring(self, strategy_id: str):
        """开始监控指定策略"""
        self.strategy_id = strategy_id
        self.performance_history.clear()
        self.history_table.setRowCount(0)
        self.logger.info(f"开始监控策略: {strategy_id}")
    
    def stop_monitoring(self):
        """停止监控"""
        self.strategy_id = None
        self.performance_history.clear()
        if hasattr(self, '_event_subscription_ids'):
            try:
                from core.events.event_bus import get_event_bus
                event_bus = get_event_bus()
                for sub_id in self._event_subscription_ids:
                    event_bus.unsubscribe(sub_id)
                self._event_subscription_ids.clear()
            except Exception as e:
                self.logger.warning(f"取消事件订阅失败: {e}")
        self.logger.info("停止性能监控")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.performance_history:
            return {}
        
        returns = [r['total_return'] for r in self.performance_history]
        sharpes = [r['sharpe_ratio'] for r in self.performance_history]
        
        return {
            'strategy_id': self.strategy_id,
            'total_records': len(self.performance_history),
            'avg_return': sum(returns) / len(returns) if returns else 0,
            'max_return': max(returns) if returns else 0,
            'min_return': min(returns) if returns else 0,
            'avg_sharpe': sum(sharpes) / len(sharpes) if sharpes else 0,
            'monitoring_duration': (datetime.now() - self.performance_history[0]['timestamp']).total_seconds() if self.performance_history else 0
        }
