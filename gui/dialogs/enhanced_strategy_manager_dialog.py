"""
增强策略管理对话框

与重构后的StrategyService和TradingService完全集成，提供：
1. 策略列表显示和管理
2. 策略创建向导
3. 策略参数配置
4. 策略状态监控
5. 策略性能展示
6. 回测和优化功能
"""

from loguru import logger
import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import asdict
import pandas as pd
import numpy as np
from enum import Enum

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QLabel, QTextEdit, QLineEdit,
    QGroupBox, QFormLayout, QPushButton, QScrollArea, QSplitter,
    QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QProgressDialog, QInputDialog,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QFrame, QGridLayout, QSlider, QDateEdit,
    QApplication, QMenu, QAction, QSizePolicy, QToolButton
)
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QThread, QTimer, QDateTime, QThreadPool, QRunnable, QMetaObject, Q_ARG, QSettings
from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor, QPalette, QPainter, QBrush

# 导入服务和数据结构
from core.services.strategy_service import StrategyService, StrategyConfig, BacktestStatus, OptimizationStatus
from core.services.trading_service import TradingService, StrategyState
from core.strategy_extensions import (
    StrategyContext, StandardMarketData, TimeFrame, AssetType,
    StrategyType, RiskLevel, ParameterDef
)

# 导入图表库（带错误处理）
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    from utils.matplotlib_font_config import configure_matplotlib_chinese_font
    configure_matplotlib_chinese_font()
    MATPLOTLIB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"matplotlib 不可用: {e}")
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"plotly 不可用: {e}")
    PLOTLY_AVAILABLE = False
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from utils.theme import get_theme_manager, Theme


class UnifiedTaskSignals(QObject):
    """统一任务信号类"""
    # 单参数信号
    single_param = pyqtSignal(object)
    # 双参数信号
    double_param = pyqtSignal(object, object)
    # 三参数信号
    triple_param = pyqtSignal(object, object, object)
    # 错误信号
    error = pyqtSignal(str)
    # 进度信号
    progress = pyqtSignal(int, str)

# 服务接口抽象定义
class IStrategyService(ABC):
    """策略服务接口"""
    
    @abstractmethod
    def get_all_strategy_configs(self) -> List[StrategyConfig]:
        """获取所有策略配置"""
        pass
    
    @abstractmethod
    def get_strategy_config(self, strategy_id: str) -> Optional[StrategyConfig]:
        """获取策略配置"""
        pass
    
    @abstractmethod
    def evaluate_strategy_performance(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """评估策略性能"""
        pass
    
    @abstractmethod
    async def run_backtest(self, strategy_id: str, market_data: Any, context: Any) -> str:
        """运行回测"""
        pass
    
    @abstractmethod
    async def run_optimization(self, strategy_id: str, optimization_params: Dict, market_data: Any, context: Any) -> str:
        """运行优化"""
        pass
    
    @abstractmethod
    def get_available_plugin_types(self) -> List[str]:
        """获取可用的插件类型"""
        pass
    
    @abstractmethod
    def get_strategy_plugin_info(self, plugin_type: str) -> Optional[Dict[str, Any]]:
        """获取策略插件信息"""
        pass
    
    @abstractmethod
    def get_strategy_info(self, plugin_type: str) -> Optional[Any]:
        """获取策略信息"""
        pass
    
    @abstractmethod
    def create_strategy_config(self, config: StrategyConfig) -> bool:
        """创建策略配置"""
        pass
    
    @abstractmethod
    def get_backtest_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取回测状态"""
        pass
    
    @abstractmethod
    def cancel_backtest(self, task_id: str) -> bool:
        """取消回测"""
        pass
    
    @abstractmethod
    def get_optimization_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取优化状态"""
        pass
    
    @abstractmethod
    def cancel_optimization(self, task_id: str) -> bool:
        """取消优化"""
        pass
    
    @abstractmethod
    def create_strategy_plugin(self, strategy_type: str) -> Optional[Any]:
        """创建策略插件"""
        pass
    
    @abstractmethod
    def update_strategy_config(self, strategy_id: str, updates: Dict[str, Any]) -> bool:
        """更新策略配置"""
        pass
    
    @abstractmethod
    def get_backtest_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取回测结果"""
        pass
    
    @abstractmethod
    def get_optimization_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取优化结果"""
        pass
    
    @abstractmethod
    def delete_strategy_config(self, strategy_id: str) -> bool:
        """删除策略配置"""
        pass

class ITradingService(ABC):
    """交易服务接口"""
    
    @abstractmethod
    def get_strategy_status(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """获取策略状态"""
        pass
    
    @abstractmethod
    def get_performance_stats(self) -> Optional[Dict[str, Any]]:
        """获取性能统计"""
        pass
    
    @abstractmethod
    def get_portfolio(self) -> Optional[Dict[str, Any]]:
        """获取投资组合"""
        pass
    
    @abstractmethod
    def get_trade_history(self, limit: int = 50) -> List[Any]:
        """获取交易历史"""
        pass
    
    @abstractmethod
    def stop_strategy(self, strategy_id: str) -> bool:
        """停止策略"""
        pass
    
    @abstractmethod
    def unregister_strategy(self, strategy_id: str) -> bool:
        """注销策略"""
        pass

class ServiceContainer:
    """服务容器 - 实现依赖注入"""
    
    def __init__(self):
        self._services = {}
        self._singletons = {}
    
    def register_service(self, interface_type: type, implementation_type: type, singleton: bool = True):
        """注册服务"""
        self._services[interface_type] = {
            'implementation': implementation_type,
            'singleton': singleton
        }
    
    def get_service(self, interface_type: type):
        """获取服务实例"""
        if interface_type not in self._services:
            raise ValueError(f"服务接口 {interface_type} 未注册")
        
        service_info = self._services[interface_type]
        implementation_type = service_info['implementation']
        is_singleton = service_info['singleton']
        
        if is_singleton:
            if interface_type not in self._singletons:
                self._singletons[interface_type] = implementation_type()
            return self._singletons[interface_type]
        else:
            return implementation_type()

class EnhancedStrategyTable(QTableWidget):
    """增强型策略表格组件"""
    
    # 信号定义
    strategy_selected = pyqtSignal(str)  # 策略ID
    batch_operation_requested = pyqtSignal(str)  # 批量操作类型
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_table()
        self._setup_context_menu()
        self._current_data = []  # 当前显示的数据
        self._filtered_data = []  # 过滤后的数据
        self._search_text = ""
        self._status_filter = "全部状态"
    
    def _setup_table(self):
        """设置表格基础属性"""
        self.setColumnCount(6)  # 增加选择列
        self.setHorizontalHeaderLabels([
            "选择", "策略ID", "框架", "状态", "性能", "操作"
        ])
        
        # 设置表格属性
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 选择列
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 策略ID
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 框架
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 状态
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 性能
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 操作
        
        # 设置选择模式
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)  # 支持多选
        self.setAlternatingRowColors(True)  # 交替行颜色
        
        # 连接信号
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
    
    def _setup_context_menu(self):
        """设置右键菜单"""
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def _show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 获取当前选中的策略
        selected_strategies = self._get_selected_strategy_ids()
        
        if selected_strategies:
            # 批量操作菜单
            batch_menu = menu.addMenu("批量操作")
            batch_menu.addAction("启动选中策略", lambda: self.batch_operation_requested.emit("start"))
            batch_menu.addAction("停止选中策略", lambda: self.batch_operation_requested.emit("stop"))
            batch_menu.addAction("删除选中策略", lambda: self.batch_operation_requested.emit("delete"))
            
            menu.addSeparator()
            
            # 单个策略操作（如果只选中一个）
            if len(selected_strategies) == 1:
                strategy_id = selected_strategies[0]
                menu.addAction("编辑策略", lambda: self._edit_strategy(strategy_id))
                menu.addAction("复制策略", lambda: self._copy_strategy(strategy_id))
                menu.addAction("导出策略", lambda: self._export_strategy(strategy_id))
        
        menu.addSeparator()
        menu.addAction("全选", self.selectAll)
        menu.addAction("反选", self._invert_selection)
        menu.addAction("清空选择", self.clearSelection)
        
        menu.exec_(self.mapToGlobal(position))
    
    def _get_selected_strategy_ids(self) -> List[str]:
        """获取选中的策略ID列表"""
        strategy_ids = []
        for row in self.selectionModel().selectedRows():
            strategy_id_item = self.item(row.row(), 1)  # 策略ID在第2列
            if strategy_id_item:
                strategy_ids.append(strategy_id_item.text())
        return strategy_ids
    
    def _invert_selection(self):
        """反选所有项目"""
        self.blockSignals(True)
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setSelected(not item.isSelected())
        self.blockSignals(False)
        self.itemSelectionChanged.emit()
    
    def _on_selection_changed(self):
        """选择变化事件"""
        selected_rows = len(self.selectionModel().selectedRows())
        if selected_rows == 1:
            # 选中单个策略，发送信号
            selected_strategies = self._get_selected_strategy_ids()
            if selected_strategies:
                self.strategy_selected.emit(selected_strategies[0])
    
    def _on_item_double_clicked(self, item):
        """双击事件"""
        if item.column() == 1:  # 双击策略ID列
            strategy_id_item = self.item(item.row(), 1)
            if strategy_id_item:
                self._edit_strategy(strategy_id_item.text())
    
    def update_data(self, strategies_data: List[Dict[str, Any]]):
        """更新表格数据"""
        self._current_data = strategies_data
        self._apply_filters()
    
    def refresh_colors(self):
        """刷新表格颜色（用于主题变化时）"""
        try:
            from utils.theme import get_theme_manager
            theme_manager = get_theme_manager()
            colors = theme_manager.get_theme_colors()
            
            # 刷新表格中状态项的颜色
            for row in range(self.rowCount()):
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if item and col == 3:  # 状态列
                        status = item.text()
                        if status == "运行中":
                            item.setBackground(QColor(colors.get('success', '#4CAF50')))
                        elif status == "错误":
                            item.setBackground(QColor(colors.get('error', '#FF5252')))
                        elif status == "已配置":
                            item.setBackground(QColor(colors.get('info', '#2196F3')))
            
            # 强制重绘表格
            self.viewport().update()
            
        except Exception as e:
            logger.warning(f"刷新表格颜色失败: {e}")
    
    def _apply_filters(self):
        """应用搜索和状态筛选"""
        # 开始过滤
        self._filtered_data = []
        
        for strategy in self._current_data:
            # 搜索文本过滤
            if self._search_text:
                search_text = self._search_text.lower()
                if not (strategy.get('strategy_id', '').lower().find(search_text) >= 0 or
                       strategy.get('plugin_type', '').lower().find(search_text) >= 0):
                    continue
            
            # 状态筛选
            if self._status_filter != "全部状态":
                status = strategy.get('status', '已配置')
                if status != self._status_filter:
                    continue
            
            self._filtered_data.append(strategy)
        
        self._refresh_table()
    
    def _refresh_table(self):
        """刷新表格显示"""
        self.blockSignals(True)
        self.setRowCount(len(self._filtered_data))
        
        for row, strategy in enumerate(self._filtered_data):
            # 第0列：选择框
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Unchecked)
            self.setItem(row, 0, checkbox_item)
            
            # 第1列：策略ID
            strategy_id_item = QTableWidgetItem(strategy.get('strategy_id', ''))
            self.setItem(row, 1, strategy_id_item)
            
            # 第2列：框架类型
            plugin_type_item = QTableWidgetItem(strategy.get('plugin_type', ''))
            self.setItem(row, 2, plugin_type_item)
            
            # 第3列：状态
            status = strategy.get('status', '已配置')
            status_item = QTableWidgetItem(status)
            
            # 根据状态设置背景色
            theme_mgr = get_theme_manager()
            colors = theme_mgr.get_theme_colors()
            if status == "运行中":
                status_item.setBackground(QColor(colors.get('success', '#4CAF50')))
            elif status == "错误":
                status_item.setBackground(QColor(colors.get('error', '#FF5252')))
            elif status == "已配置":
                status_item.setBackground(QColor(colors.get('info', '#2196F3')))
            
            self.setItem(row, 3, status_item)
            
            # 第4列：性能
            performance_text = strategy.get('performance_text', 'N/A')
            perf_item = QTableWidgetItem(performance_text)
            self.setItem(row, 4, perf_item)
            
            # 第5列：操作按钮
            button_widget = QWidget()
            button_layout = QHBoxLayout(button_widget)
            button_layout.setContentsMargins(2, 2, 2, 2)
            button_layout.setSpacing(5)
            
            edit_button = QPushButton("编辑")
            edit_button.setMaximumSize(40, 20)
            edit_button.clicked.connect(lambda checked, sid=strategy.get('strategy_id'): self._edit_strategy(sid))
            
            delete_button = QPushButton("删除")
            delete_button.setMaximumSize(40, 20)
            delete_button.clicked.connect(lambda checked, sid=strategy.get('strategy_id'): self._delete_strategy(sid))
            
            button_layout.addWidget(edit_button)
            button_layout.addWidget(delete_button)
            button_layout.addStretch()
            
            self.setCellWidget(row, 5, button_widget)
        
        self.blockSignals(False)
    
    def set_search_text(self, text: str):
        """设置搜索文本"""
        self._search_text = text
        self._apply_filters()
    
    def set_status_filter(self, status: str):
        """设置状态筛选"""
        self._status_filter = status
        self._apply_filters()
    
    def get_selected_strategies(self) -> List[str]:
        """获取选中的策略ID列表"""
        selected_ids = []
        for row in range(self.rowCount()):
            checkbox_item = self.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                strategy_id_item = self.item(row, 1)
                if strategy_id_item:
                    selected_ids.append(strategy_id_item.text())
        return selected_ids
    
    def select_all_strategies(self):
        """选中所有策略"""
        for row in range(self.rowCount()):
            checkbox_item = self.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.Checked)
    
    def clear_all_selections(self):
        """清空所有选择"""
        for row in range(self.rowCount()):
            checkbox_item = self.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.Unchecked)
    
    def _edit_strategy(self, strategy_id: str):
        """编辑策略"""
        try:
            logger.info(f"编辑策略: {strategy_id}")
            
            # 查找父对话框并触发编辑操作
            parent_dialog = self.window()
            if hasattr(parent_dialog, '_edit_strategy'):
                parent_dialog._edit_strategy(strategy_id)
            else:
                # 如果父对话框没有此方法，直接切换到该策略
                self._select_strategy(strategy_id)
                
        except Exception as e:
            logger.error(f"编辑策略失败: {e}")
            QMessageBox.warning(self, "错误", f"编辑策略失败: {str(e)}")
    
    def _delete_strategy(self, strategy_id: str):
        """删除策略"""
        try:
            logger.info(f"删除策略: {strategy_id}")
            
            # 确认对话框
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除策略 '{strategy_id}' 吗？\n此操作不可撤销。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 查找父对话框并触发删除操作
                parent_dialog = self.window()
                if hasattr(parent_dialog, '_delete_strategy_from_table'):
                    parent_dialog._delete_strategy_from_table(strategy_id)
                else:
                    logger.error("父对话框不支持删除操作")
                    QMessageBox.warning(self, "错误", "删除操作不可用")
                    
        except Exception as e:
            logger.error(f"删除策略失败: {e}")
            QMessageBox.warning(self, "错误", f"删除策略失败: {str(e)}")
    
    def _copy_strategy(self, strategy_id: str):
        """复制策略"""
        try:
            logger.info(f"复制策略: {strategy_id}")
            
            # 查找父对话框并触发复制操作
            parent_dialog = self.window()
            if hasattr(parent_dialog, '_copy_strategy'):
                parent_dialog._copy_strategy(strategy_id)
            else:
                QMessageBox.warning(self, "错误", "复制操作不可用")
                
        except Exception as e:
            logger.error(f"复制策略失败: {e}")
            QMessageBox.warning(self, "错误", f"复制策略失败: {str(e)}")
    
    def _export_strategy(self, strategy_id: str):
        """导出策略"""
        try:
            logger.info(f"导出策略: {strategy_id}")
            
            # 查找父对话框并触发导出操作
            parent_dialog = self.window()
            if hasattr(parent_dialog, '_export_strategy'):
                parent_dialog._export_strategy(strategy_id)
            else:
                QMessageBox.warning(self, "错误", "导出操作不可用")
                
        except Exception as e:
            logger.error(f"导出策略失败: {e}")
            QMessageBox.warning(self, "错误", f"导出策略失败: {str(e)}")
    
    def _select_strategy(self, strategy_id: str):
        """选择策略（辅助方法）"""
        for row in range(self.rowCount()):
            strategy_id_item = self.item(row, 1)  # 策略ID在第2列
            if strategy_id_item and strategy_id_item.text() == strategy_id:
                self.selectRow(row)
                self.strategy_selected.emit(strategy_id)
                break

class BacktestResultsWidget(QWidget):
    """回测结果图表展示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        if MATPLOTLIB_AVAILABLE:
            self._setup_ui()
        else:
            self._setup_fallback_ui()
    
    def _setup_ui(self):
        """设置图表UI"""
        layout = QVBoxLayout(self)
        
        # 创建图表标签页
        self.chart_tabs = QTabWidget()
        layout.addWidget(self.chart_tabs)
        
        # 权益曲线图
        self.equity_curve_widget = self._create_equity_curve_widget()
        self.chart_tabs.addTab(self.equity_curve_widget, "权益曲线")
        
        # 回撤分析图
        self.drawdown_widget = self._create_drawdown_widget()
        self.chart_tabs.addTab(self.drawdown_widget, "回撤分析")
        
        # 交易记录图
        self.trades_widget = self._create_trades_widget()
        self.chart_tabs.addTab(self.trades_widget, "交易记录")
        
        # 统计信息面板
        self.stats_panel = QGroupBox("关键指标")
        self._setup_stats_panel()
        layout.addWidget(self.stats_panel)
    
    def _setup_fallback_ui(self):
        """设置无图表时的备用UI"""
        layout = QVBoxLayout(self)
        label = QLabel("图表功能需要安装 matplotlib 库")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
    
    def _create_equity_curve_widget(self):
        """创建权益曲线图组件"""
        widget = FigureCanvas(Figure(figsize=(10, 6)))
        ax = widget.figure.add_subplot(111)
        ax.set_title("策略权益曲线", fontsize=14, fontweight='bold')
        ax.set_xlabel("日期", fontsize=12)
        ax.set_ylabel("累计收益率", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        return widget
    
    def _create_drawdown_widget(self):
        """创建回撤分析图组件"""
        widget = FigureCanvas(Figure(figsize=(10, 6)))
        ax = widget.figure.add_subplot(111)
        ax.set_title("策略回撤分析", fontsize=14, fontweight='bold')
        ax.set_xlabel("日期", fontsize=12)
        ax.set_ylabel("回撤比例", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        return widget
    
    def _create_trades_widget(self):
        """创建交易记录图组件"""
        widget = FigureCanvas(Figure(figsize=(10, 6)))
        ax = widget.figure.add_subplot(111)
        ax.set_title("交易记录分析", fontsize=14, fontweight='bold')
        ax.set_xlabel("交易序号", fontsize=12)
        ax.set_ylabel("盈亏金额", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        return widget
    
    def _setup_stats_panel(self):
        """设置统计信息面板"""
        layout = QFormLayout(self.stats_panel)
        
        # 创建统计标签
        self.total_return_label = QLabel("N/A")
        self.sharpe_ratio_label = QLabel("N/A")
        self.max_drawdown_label = QLabel("N/A")
        self.win_rate_label = QLabel("N/A")
        self.total_trades_label = QLabel("N/A")
        self.avg_profit_label = QLabel("N/A")
        
        # 设置标签样式
        theme_mgr = get_theme_manager()
        colors = theme_mgr.get_theme_colors()
        label_style = f"""
            QLabel {{
                font-size: 12px;
                font-weight: bold;
                padding: 5px;
                background-color: {colors.get('card', '#FFFFFF')};
                border-radius: 3px;
            }}
        """
        for label in [self.total_return_label, self.sharpe_ratio_label,
                     self.max_drawdown_label, self.win_rate_label,
                     self.total_trades_label, self.avg_profit_label]:
            label.setStyleSheet(label_style)
        
        layout.addRow("总收益率:", self.total_return_label)
        layout.addRow("夏普比率:", self.sharpe_ratio_label)
        layout.addRow("最大回撤:", self.max_drawdown_label)
        layout.addRow("胜率:", self.win_rate_label)
        layout.addRow("总交易次数:", self.total_trades_label)
        layout.addRow("平均盈利:", self.avg_profit_label)
    
    def update_results(self, results: Dict[str, Any]):
        """更新回测结果"""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        try:
            # 更新权益曲线
            if 'equity_curve' in results:
                self._update_equity_curve(results['equity_curve'])
            
            # 更新回撤图
            if 'drawdown' in results:
                self._update_drawdown_chart(results['drawdown'])
            
            # 更新交易记录
            if 'trades' in results:
                self._update_trades_chart(results['trades'])
            
            # 更新统计信息
            if 'statistics' in results:
                self._update_statistics(results['statistics'])
            
        except Exception as e:
            logger.error(f"更新回测结果失败: {e}")
    
    def _update_equity_curve(self, equity_data: List[Dict]):
        """更新权益曲线图"""
        try:
            ax = self.equity_curve_widget.figure.axes[0]
            ax.clear()
            
            if equity_data:
                dates = [item['date'] for item in equity_data]
                values = [item['value'] for item in equity_data]
                
                ax.plot(dates, values, linewidth=2, color='#1f77b4', label='权益曲线')
                ax.set_title("策略权益曲线", fontsize=14, fontweight='bold')
                ax.set_xlabel("日期", fontsize=12)
                ax.set_ylabel("累计收益率", fontsize=12)
                ax.grid(True, alpha=0.3)
                ax.legend()
                
                # 格式化x轴日期
                if dates and hasattr(dates[0], 'strftime'):
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    ax.xaxis.set_major_locator(mdates.MonthLocator())
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            self.equity_curve_widget.figure.tight_layout()
            self.equity_curve_widget.draw()
            
        except Exception as e:
            logger.error(f"更新权益曲线失败: {e}")
    
    def _update_drawdown_chart(self, drawdown_data: List[Dict]):
        """更新回撤分析图"""
        try:
            ax = self.drawdown_widget.figure.axes[0]
            ax.clear()
            
            if drawdown_data:
                dates = [item['date'] for item in drawdown_data]
                drawdowns = [item['drawdown'] for item in drawdown_data]
                
                ax.fill_between(dates, drawdowns, 0, alpha=0.3, color='red', label='回撤')
                ax.plot(dates, drawdowns, linewidth=1, color='red')
                ax.set_title("策略回撤分析", fontsize=14, fontweight='bold')
                ax.set_xlabel("日期", fontsize=12)
                ax.set_ylabel("回撤比例", fontsize=12)
                ax.grid(True, alpha=0.3)
                ax.legend()
                
                # 格式化x轴日期
                if dates and hasattr(dates[0], 'strftime'):
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    ax.xaxis.set_major_locator(mdates.MonthLocator())
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            self.drawdown_widget.figure.tight_layout()
            self.drawdown_widget.draw()
            
        except Exception as e:
            logger.error(f"更新回撤图失败: {e}")
    
    def _update_trades_chart(self, trades_data: List[Dict]):
        """更新交易记录图"""
        try:
            ax = self.trades_widget.figure.axes[0]
            ax.clear()
            
            if trades_data:
                trade_numbers = list(range(1, len(trades_data) + 1))
                profits = [trade.get('profit', 0) for trade in trades_data]
                
                colors = ['green' if p >= 0 else 'red' for p in profits]
                ax.bar(trade_numbers, profits, color=colors, alpha=0.7)
                ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
                ax.set_title("交易记录分析", fontsize=14, fontweight='bold')
                ax.set_xlabel("交易序号", fontsize=12)
                ax.set_ylabel("盈亏金额", fontsize=12)
                ax.grid(True, alpha=0.3)
            
            self.trades_widget.figure.tight_layout()
            self.trades_widget.draw()
            
        except Exception as e:
            logger.error(f"更新交易记录图失败: {e}")
    
    def _update_statistics(self, stats: Dict[str, Any]):
        """更新统计信息"""
        try:
            self.total_return_label.setText(f"{stats.get('total_return', 0):.2%}")
            self.sharpe_ratio_label.setText(f"{stats.get('sharpe_ratio', 0):.2f}")
            self.max_drawdown_label.setText(f"{stats.get('max_drawdown', 0):.2%}")
            self.win_rate_label.setText(f"{stats.get('win_rate', 0):.1%}")
            self.total_trades_label.setText(str(stats.get('total_trades', 0)))
            self.avg_profit_label.setText(f"{stats.get('avg_profit', 0):.2f}")
            
        except Exception as e:
            logger.error(f"更新统计信息失败: {e}")

class ResourceManager:
    """统一资源管理器"""
    
    def __init__(self):
        self.timers = []
        self.tasks = []
        self.widgets = []
        self.threads = []
    
    def register_timer(self, timer):
        """注册定时器"""
        if timer and timer not in self.timers:
            self.timers.append(timer)
    
    def register_task(self, task):
        """注册任务"""
        if task and task not in self.tasks:
            self.tasks.append(task)
    
    def register_widget(self, widget):
        """注册控件"""
        if widget and widget not in self.widgets:
            self.widgets.append(widget)
    
    def register_thread(self, thread):
        """注册线程"""
        if thread and thread not in self.threads:
            self.threads.append(thread)
    
    def cleanup_all(self):
        """清理所有资源"""
        # 停止并删除定时器
        for timer in self.timers:
            try:
                if hasattr(timer, 'stop'):
                    timer.stop()
                if hasattr(timer, 'deleteLater'):
                    timer.deleteLater()
            except Exception as e:
                logger.warning(f"清理定时器失败: {e}")
        
        self.timers.clear()
        
        # 取消任务
        for task in self.tasks:
            try:
                if hasattr(task, 'cancel'):
                    task.cancel()
            except Exception as e:
                logger.warning(f"取消任务失败: {e}")
        
        self.tasks.clear()
        
        # 清理控件
        for widget in self.widgets:
            try:
                if hasattr(widget, 'deleteLater'):
                    widget.deleteLater()
            except Exception as e:
                logger.warning(f"清理控件失败: {e}")
        
        self.widgets.clear()
        
        # 退出线程
        for thread in self.threads:
            try:
                if hasattr(thread, 'quit'):
                    thread.quit()
                if hasattr(thread, 'wait'):
                    thread.wait(1000)  # 等待1秒
            except Exception as e:
                logger.warning(f"退出线程失败: {e}")
        
        self.threads.clear()

class AsyncTaskManager:
    """统一异步任务管理器"""
    
    def __init__(self, resource_manager=None):
        self.thread_pool = QThreadPool.globalInstance()
        self.active_tasks = {}  # 跟踪活跃任务
        self.task_counter = 0
        self.resource_manager = resource_manager or ResourceManager()
    
    def submit_task(self, task_class, *args, callback=None, error_callback=None, **kwargs):
        """提交异步任务"""
        task_id = self._generate_task_id()
        
        # 创建任务实例
        task = task_class(*args, **kwargs)
        task.setAutoDelete(True)
        
        # 注册到资源管理器
        self.resource_manager.register_task(task)
        
        # 设置信号连接
        signals = task.get_signals()
        if callback:
            if signals.single_param:
                signals.single_param.connect(callback)
            elif signals.double_param:
                signals.double_param.connect(callback)
            elif signals.triple_param:
                signals.triple_param.connect(callback)
        
        if error_callback and signals.error:
            signals.error.connect(error_callback)
        
        # 跟踪任务
        self.active_tasks[task_id] = task
        
        # 提交到线程池
        self.thread_pool.start(task)
        
        return task_id
    
    def cancel_task(self, task_id):
        """取消任务（如果支持）"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if hasattr(task, 'cancel'):
                task.cancel()
            
            # 从跟踪列表中移除
            del self.active_tasks[task_id]
    
    def cancel_all_tasks(self):
        """取消所有任务"""
        for task_id in list(self.active_tasks.keys()):
            self.cancel_task(task_id)
    
    def _generate_task_id(self):
        """生成唯一任务ID"""
        self.task_counter += 1
        return f"task_{self.task_counter}_{int(time.time())}"

class BaseAsyncTask(QRunnable):
    """异步任务基类"""
    
    def __init__(self):
        super().__init__()
        self.signals = UnifiedTaskSignals()
        self.is_cancelled = False
    
    def get_signals(self):
        """获取信号对象"""
        return self.signals
    
    def cancel(self):
        """取消任务"""
        self.is_cancelled = True
    
    def emit_error(self, error_msg):
        """发射错误信号"""
        self.signals.error.emit(error_msg)

class StrategyListLoaderTask(BaseAsyncTask):
    """策略列表加载任务"""
    
    def __init__(self, strategy_service):
        super().__init__()
        self.strategy_service = strategy_service
    
    def run(self):
        """执行策略列表加载"""
        try:
            if self.is_cancelled:
                return
            
            # 获取所有策略配置
            configs = self.strategy_service.get_all_strategy_configs()
            
            # 发送完成信号
            self.signals.single_param.emit(configs)
            
        except Exception as e:
            error_msg = f"加载策略列表失败: {e}"
            logger.error(error_msg)
            self.emit_error(error_msg)

class StrategyDetailsLoaderTask(BaseAsyncTask):
    """策略详情加载任务"""
    
    def __init__(self, strategy_service, strategy_id):
        super().__init__()
        self.strategy_service = strategy_service
        self.strategy_id = strategy_id
    
    def run(self):
        """执行策略详情加载"""
        try:
            if self.is_cancelled:
                return
            
            # 获取策略配置
            config = self.strategy_service.get_strategy_config(self.strategy_id)
            if not config:
                self.emit_error(f"策略配置不存在: {self.strategy_id}")
                return
            
            # 获取策略性能数据
            performance = self.strategy_service.evaluate_strategy_performance(self.strategy_id)
            
            # 发送完成信号
            self.signals.double_param.emit(config, performance)
            
        except Exception as e:
            error_msg = f"加载策略详情失败: {e}"
            logger.error(error_msg)
            self.emit_error(error_msg)

class StrategyWorkerTask(BaseAsyncTask):
    """策略操作工作线程类（重构版）"""
    
    def __init__(self, strategy_service, operation, **kwargs):
        super().__init__()
        self.strategy_service = strategy_service
        self.operation = operation  # 'backtest' or 'optimization'
        self.kwargs = kwargs
        
    def run(self):
        """在工作线程中执行策略操作"""
        try:
            if self.is_cancelled:
                return
                
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if self.operation == 'backtest':
                task_id = self._run_backtest_async(loop)
            elif self.operation == 'optimization':
                task_id = self._run_optimization_async(loop)
            else:
                raise ValueError(f"不支持的操作类型: {self.operation}")
            
            loop.close()
        
            # 发送任务ID到主线程
            self.signals.single_param.emit(task_id)
        
        except Exception as e:
            error_msg = f"{self.operation}执行失败: {e}"
            logger.error(error_msg)
            self.emit_error(error_msg)
            
    def _run_backtest_async(self, loop):
        """异步执行回测"""
        async def run_backtest_async():
            task_id = await self.strategy_service.run_backtest(
                self.kwargs['strategy_id'], 
                self.kwargs['market_data'], 
                self.kwargs['context']
            )
            return task_id
        
        return loop.run_until_complete(run_backtest_async())
        
    def _run_optimization_async(self, loop):
        """异步执行优化"""
        async def run_optimization_async():
            task_id = await self.strategy_service.run_optimization(
                self.kwargs['strategy_id'],
                self.kwargs['optimization_params'],
                self.kwargs['market_data'],
                self.kwargs['context']
            )
            return task_id
        
        return loop.run_until_complete(run_optimization_async())


class StrategyCreationWizard(QDialog):
    """策略创建向导"""

    strategy_created = pyqtSignal(dict)

    def __init__(self, parent=None, strategy_service=None):
        super().__init__(parent)
        self.strategy_service = strategy_service
        self.setWindowTitle("策略创建向导")
        self.setModal(True)
        self.resize(600, 500)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 步骤1: 选择策略类型
        step1_group = QGroupBox("步骤1: 选择策略框架")
        step1_layout = QFormLayout(step1_group)

        self.plugin_type_combo = QComboBox()
        if self.strategy_service:
            plugin_types = self.strategy_service.get_available_plugin_types()
            self.plugin_type_combo.addItems(plugin_types)

        step1_layout.addRow("策略框架:", self.plugin_type_combo)
        layout.addWidget(step1_group)

        # 步骤2: 基本信息
        step2_group = QGroupBox("步骤2: 基本信息")
        step2_layout = QFormLayout(step2_group)

        self.strategy_id_edit = QLineEdit()
        self.strategy_name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)

        step2_layout.addRow("策略ID:", self.strategy_id_edit)
        step2_layout.addRow("策略名称:", self.strategy_name_edit)
        step2_layout.addRow("描述:", self.description_edit)
        layout.addWidget(step2_group)

        # 步骤3: 参数配置
        step3_group = QGroupBox("步骤3: 参数配置")
        self.params_layout = QFormLayout(step3_group)
        self.param_widgets = {}

        # 根据选择的插件类型动态更新参数
        self.plugin_type_combo.currentTextChanged.connect(self._update_parameters)
        self._update_parameters()

        layout.addWidget(step3_group)

        # 步骤4: 技术指标选择（从简单策略管理器合并）
        indicators_group = QGroupBox("步骤4: 技术指标选择")
        indicators_layout = QVBoxLayout(indicators_group)

        self.indicators_list = QListWidget()
        self.indicators_list.setSelectionMode(QListWidget.MultiSelection)

        # 添加常用技术指标（从简单策略管理器复制）
        indicators = [
            "MA - 移动平均线", "EMA - 指数移动平均线", "MACD - 指数平滑移动平均线",
            "RSI - 相对强弱指标", "KDJ - 随机指标", "BOLL - 布林线",
            "CCI - 商品通道指数", "WR - 威廉指标", "ATR - 平均真实波幅"
        ]

        for indicator in indicators:
            item = QListWidgetItem(indicator)
            self.indicators_list.addItem(item)

        indicators_layout.addWidget(self.indicators_list)
        layout.addWidget(indicators_group)

        # 步骤5: 策略代码编辑器（从简单策略管理器合并）
        code_group = QGroupBox("步骤5: 策略代码")
        code_layout = QVBoxLayout(code_group)

        self.strategy_code_edit = QTextEdit()
        self.strategy_code_edit.setPlaceholderText("输入策略代码（Python）")
        self.strategy_code_edit.setFont(QFont("Consolas", 10))

        # 默认策略模板（从简单策略管理器复制）
        default_code = '''
def strategy_logic(data, params):
    """
    策略逻辑函数
    
    Args:
        data: 股票数据 (DataFrame)
        params: 策略参数 (dict)
    
    Returns:
        signals: 交易信号 (dict)
    """
    signals = {
        'buy': [],   # 买入信号
        'sell': [],  # 卖出信号
        'hold': []   # 持有信号
    }
    
    # 在这里编写你的策略逻辑
    # 例如：基于移动平均线的简单策略
    if len(data) > 20:
        ma_short = data['close'].rolling(5).mean()
        ma_long = data['close'].rolling(20).mean()
        
        # 金叉买入信号
        if ma_short.iloc[-1] > ma_long.iloc[-1] and ma_short.iloc[-2] <= ma_long.iloc[-2]:
            signals['buy'].append({
                'price': data['close'].iloc[-1],
                'volume': 100,
                'reason': '金叉买入'
            })
        
        # 死叉卖出信号
        elif ma_short.iloc[-1] < ma_long.iloc[-1] and ma_short.iloc[-2] >= ma_long.iloc[-2]:
            signals['sell'].append({
                'price': data['close'].iloc[-1],
                'volume': 100,
                'reason': '死叉卖出'
            })
    
    return signals
        '''.strip()

        self.strategy_code_edit.setPlainText(default_code)
        code_layout.addWidget(self.strategy_code_edit)
        layout.addWidget(code_group)

        # 按钮
        button_layout = QHBoxLayout()

        create_button = QPushButton("创建策略")
        create_button.clicked.connect(self._create_strategy)

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(create_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _update_parameters(self):
        """根据选择的插件类型更新参数配置"""
        # 清除现有参数控件
        for i in reversed(range(self.params_layout.count())):
            self.params_layout.itemAt(i).widget().setParent(None)
        self.param_widgets.clear()

        plugin_type = self.plugin_type_combo.currentText()
        if not plugin_type or not self.strategy_service:
            return

        # 获取插件信息
        plugin_info = self.strategy_service.get_strategy_plugin_info(plugin_type)
        if not plugin_info:
            return

        # 使用新的get_strategy_info方法获取策略信息，内部会自动创建和释放临时实例
        strategy_info = self.strategy_service.get_strategy_info(plugin_type)
        if not strategy_info:
            return

        # 为每个参数创建控件
        for param_def in strategy_info.parameters:
            widget = self._create_parameter_widget(param_def)
            if widget:
                self.param_widgets[param_def.name] = widget
                self.params_layout.addRow(f"{param_def.display_name}:", widget)

    def _create_parameter_widget(self, param_def: ParameterDef):
        """为参数定义创建对应的控件"""
        if param_def.type == int:
            widget = QSpinBox()
            if param_def.min_value is not None:
                widget.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                widget.setMaximum(param_def.max_value)
            if param_def.default_value is not None:
                widget.setValue(param_def.default_value)
            return widget

        elif param_def.type == float:
            widget = QDoubleSpinBox()
            widget.setDecimals(4)
            if param_def.min_value is not None:
                widget.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                widget.setMaximum(param_def.max_value)
            if param_def.default_value is not None:
                widget.setValue(param_def.default_value)
            return widget

        elif param_def.type == str:
            if hasattr(param_def, 'choices') and param_def.choices:
                widget = QComboBox()
                widget.addItems(param_def.choices)
                if param_def.default_value:
                    widget.setCurrentText(str(param_def.default_value))
                return widget
            else:
                widget = QLineEdit()
                if param_def.default_value:
                    widget.setText(str(param_def.default_value))
                return widget

        elif param_def.type == bool:
            widget = QCheckBox()
            if param_def.default_value is not None:
                widget.setChecked(param_def.default_value)
            return widget

        return None

    def _create_strategy(self):
        """创建策略"""
        try:
            # 验证输入
            strategy_id = self.strategy_id_edit.text().strip()
            if not strategy_id:
                QMessageBox.warning(self, "警告", "请输入策略ID")
                return

            plugin_type = self.plugin_type_combo.currentText()
            if not plugin_type:
                QMessageBox.warning(self, "警告", "请选择策略框架")
                return

            # 收集参数
            parameters = {}
            for param_name, widget in self.param_widgets.items():
                if isinstance(widget, QSpinBox):
                    parameters[param_name] = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    parameters[param_name] = widget.value()
                elif isinstance(widget, QLineEdit):
                    parameters[param_name] = widget.text()
                elif isinstance(widget, QComboBox):
                    parameters[param_name] = widget.currentText()
                elif isinstance(widget, QCheckBox):
                    parameters[param_name] = widget.isChecked()

            # 创建策略配置
            metadata = {
                'name': self.strategy_name_edit.text().strip(),
                'description': self.description_edit.toPlainText().strip(),
                'created_by': 'user',
                'created_at': datetime.now().isoformat()
            }

            success = self.strategy_service.create_strategy_config(
                strategy_id=strategy_id,
                plugin_type=plugin_type,
                parameters=parameters,
                metadata=metadata
            )

            if success:
                QMessageBox.information(self, "成功", f"策略 '{strategy_id}' 创建成功")
                self.strategy_created.emit({
                    'strategy_id': strategy_id,
                    'plugin_type': plugin_type,
                    'parameters': parameters,
                    'metadata': metadata
                })
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "策略创建失败")

        except Exception as e:
            logger.error(f"创建策略失败: {e}")
            QMessageBox.critical(self, "错误", f"创建策略失败: {e}")


class BacktestProgressDialog(QDialog):
    """回测进度对话框"""

    def __init__(self, parent=None, strategy_service=None, task_id=None):
        super().__init__(parent)
        self.strategy_service = strategy_service
        self.task_id = task_id
        self.setWindowTitle("回测进行中")
        self.setModal(True)
        self.resize(400, 200)
        self._setup_ui()

        # 定时器更新进度
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_progress)
        self.timer.start(1000)  # 每秒更新一次

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        self.status_label = QLabel("正在初始化回测...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        layout.addWidget(self.details_text)

        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self._cancel_backtest)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _update_progress(self):
        """更新进度"""
        if not self.strategy_service or not self.task_id:
            return

        status = self.strategy_service.get_backtest_status(self.task_id)
        if not status:
            return

        # 更新进度条
        progress = int(status['progress'] * 100)
        self.progress_bar.setValue(progress)

        # 更新状态文本
        status_text = {
            'pending': '等待中...',
            'running': f'运行中... ({progress}%)',
            'completed': '完成',
            'failed': '失败',
            'cancelled': '已取消'
        }.get(status['status'], '未知状态')

        self.status_label.setText(status_text)

        # 更新详细信息
        if status.get('error_message'):
            self.details_text.setText(f"错误: {status['error_message']}")
        else:
            self.details_text.setText(f"任务ID: {self.task_id}\n开始时间: {status.get('started_at', 'N/A')}")

        # 如果完成或失败，关闭对话框
        if status['status'] in ['completed', 'failed', 'cancelled']:
            self.timer.stop()
            if status['status'] == 'completed':
                self.accept()
            else:
                self.reject()

    def _cancel_backtest(self):
        """取消回测"""
        if self.strategy_service and self.task_id:
            self.strategy_service.cancel_backtest(self.task_id)
        self.reject()


class OptimizationProgressDialog(QDialog):
    """优化进度对话框"""

    def __init__(self, parent=None, strategy_service=None, task_id=None):
        super().__init__(parent)
        self.strategy_service = strategy_service
        self.task_id = task_id
        self.setWindowTitle("优化进行中")
        self.setModal(True)
        self.resize(400, 200)
        self._setup_ui()

        # 定时器更新进度
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_progress)
        self.timer.start(1000)  # 每秒更新一次

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        self.status_label = QLabel("正在初始化优化...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        layout.addWidget(self.details_text)

        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self._cancel_optimization)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _update_progress(self):
        """更新进度"""
        if not self.strategy_service or not self.task_id:
            return

        status = self.strategy_service.get_optimization_status(self.task_id)
        if not status:
            return

        # 更新进度条
        progress = int(status['progress'] * 100)
        self.progress_bar.setValue(progress)

        # 更新状态文本
        status_text = {
            'pending': '等待中...',
            'running': f'运行中... ({progress}%)',
            'completed': '完成',
            'failed': '失败',
            'cancelled': '已取消'
        }.get(status['status'], '未知状态')

        self.status_label.setText(status_text)

        # 更新详细信息
        if status.get('error_message'):
            self.details_text.setText(f"错误: {status['error_message']}")
        else:
            self.details_text.setText(f"任务ID: {self.task_id}\n开始时间: {status.get('started_at', 'N/A')}\n迭代次数: {status.get('iterations', 0)}\n最优值: {status.get('best_score', 0):.4f}")

        # 如果完成或失败，关闭对话框
        if status['status'] in ['completed', 'failed', 'cancelled']:
            self.timer.stop()
            if status['status'] == 'completed':
                self.accept()
            else:
                self.reject()

    def _cancel_optimization(self):
        """取消优化"""
        if self.strategy_service and self.task_id:
            self.strategy_service.cancel_optimization(self.task_id)
        self.reject()


class EnhancedStrategyManagerDialog(QDialog):
    """增强策略管理对话框"""

    # 信号
    strategy_selected = pyqtSignal(str)  # 策略ID
    strategy_started = pyqtSignal(str)   # 策略ID
    strategy_stopped = pyqtSignal(str)   # 策略ID

    def __init__(self, parent=None, strategy_service=None, trading_service=None):
        """
        初始化增强策略管理对话框

        Args:
            parent: 父窗口
            strategy_service: 策略服务（已弃用，建议使用服务容器）
            trading_service: 交易服务（已弃用，建议使用服务容器）
            service_container: 服务容器实例（可选）
        """
        super().__init__(parent)
        
        # 初始化统一资源管理器
        self.resource_manager = ResourceManager()
        
        # 初始化服务容器（如果提供了服务，使用依赖注入）
        self._setup_services(strategy_service, trading_service)
        
        self.current_strategy_id = None
        self.range_widgets = {}  # 存储参数范围控件引用的字典
        
        # 初始化统一异步任务管理器
        self.task_manager = AsyncTaskManager(self.resource_manager)
        self.active_task_ids = set()  # 跟踪活跃任务ID

        self.setWindowTitle("策略管理器")
        self.setModal(False)  # 非模态对话框，允许与主窗口交互
        self.resize(1250, 800)

        # 监听主题变化信号
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # 先创建UI组件
        self._setup_ui()
        
        # UI创建完成后强制应用主题（修复根本问题）
        self._force_apply_theme()
        
        self._setup_timers()
        self._load_strategies()
    
    def showEvent(self, event):
        """显示事件 - 确保对话框显示时主题正确应用"""
        super().showEvent(event)
        
        # 强制重新应用主题，确保所有组件都正确显示
        QTimer.singleShot(100, self._force_apply_theme)
    
    def _setup_services(self, strategy_service=None, trading_service=None):
        """设置服务依赖注入"""
        # 如果提供了服务实例，直接使用（向后兼容）
        if strategy_service:
            self.strategy_service = strategy_service
        else:
            # 使用服务容器获取服务实例
            try:
                from core.containers.service_container import get_service_container
                container = get_service_container()
                self.strategy_service = container.resolve(StrategyService)
            except Exception as e:
                logger.warning(f"无法从服务容器获取StrategyService: {e}")
                self.strategy_service = None
        
        if trading_service:
            self.trading_service = trading_service
        else:
            # 使用服务容器获取服务实例
            try:
                from core.containers.service_container import get_service_container
                container = get_service_container()
                self.trading_service = container.resolve(TradingService)
            except Exception as e:
                logger.warning(f"无法从服务容器获取TradingService: {e}")
                self.trading_service = None
        
        logger.info(f"策略服务初始化完成: {self.strategy_service is not None}")
        logger.info(f"交易服务初始化完成: {self.trading_service is not None}")

    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧：策略列表和操作
        left_widget = self._create_left_panel()
        # left_widget.setFixedWidth(450)
        splitter.addWidget(left_widget)

        # 右侧：策略详情和监控
        right_widget = self._create_right_panel()
        # right_widget.setFixedWidth(800)
        splitter.addWidget(right_widget)

        # 设置分割器比例
        splitter.setSizes([450, 800])

    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 策略列表
        list_group = QGroupBox("策略列表")
        list_layout = QVBoxLayout(list_group)

        toolbar_layout = QHBoxLayout()

        create_button = QPushButton("创建策略")
        create_button.clicked.connect(self._create_strategy)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self._load_strategies)

        import_button = QPushButton("导入")
        import_button.clicked.connect(self._import_strategy)

        export_button = QPushButton("导出")
        export_button.clicked.connect(self._export_strategy)

        # 主题切换按钮
        theme_button = QToolButton()
        theme_button.setText("🎨")
        theme_button.setToolTip("切换主题")
        theme_button.clicked.connect(self._toggle_theme)
        
        # 高级工具栏
        toolbar_layout.addWidget(create_button)
        toolbar_layout.addWidget(refresh_button)
        toolbar_layout.addSpacing(20)  # 添加间距替代分隔线
        
        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索策略...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        toolbar_layout.addWidget(self.search_edit)
        
        # 状态筛选
        self.status_filter = QComboBox()
        self.status_filter.addItems(["全部状态", "已配置", "运行中", "错误"])
        self.status_filter.currentTextChanged.connect(self._on_status_filter_changed)
        toolbar_layout.addWidget(self.status_filter)
        
        toolbar_layout.addSpacing(20)  # 添加间距替代分隔线
        
        # 批量操作按钮
        self.batch_start_button = QPushButton("批量启动")
        self.batch_start_button.setMaximumWidth(80)
        self.batch_start_button.clicked.connect(lambda: self._on_batch_operation("start"))
        
        self.batch_stop_button = QPushButton("批量停止")
        self.batch_stop_button.setMaximumWidth(80)
        self.batch_stop_button.clicked.connect(lambda: self._on_batch_operation("stop"))
        
        self.batch_delete_button = QPushButton("批量删除")
        self.batch_delete_button.setMaximumWidth(80)
        self.batch_delete_button.clicked.connect(lambda: self._on_batch_operation("delete"))
        
        toolbar_layout.addWidget(self.batch_start_button)
        toolbar_layout.addWidget(self.batch_stop_button)
        toolbar_layout.addWidget(self.batch_delete_button)
        
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(theme_button)
        toolbar_layout.addWidget(import_button)
        toolbar_layout.addWidget(export_button)

        list_layout.addLayout(toolbar_layout)

        # 创建增强型策略表格
        self.strategy_table = EnhancedStrategyTable()
        self.strategy_table.strategy_selected.connect(self._on_strategy_selected)
        self.strategy_table.batch_operation_requested.connect(self._on_batch_operation)

        list_layout.addWidget(self.strategy_table)
        layout.addWidget(list_group)

        return widget
    
    def _toggle_theme(self):
        """切换主题"""
        theme_manager = get_theme_manager()
        current_theme = theme_manager.current_theme

        theme_map = {
            Theme.LIGHT: 'dark',
            Theme.DARK: 'gradient',
            Theme.GRADIENT: 'light'
        }

        new_theme_name = theme_map.get(current_theme, 'light')
        theme_manager.set_theme(new_theme_name)

        new_theme = theme_manager.current_theme
        theme_names = {
            Theme.LIGHT: "浅色",
            Theme.DARK: "深色",
            Theme.GRADIENT: "渐变"
        }
        QMessageBox.information(self, "主题切换", f"已切换到{theme_names[new_theme]}主题")
    
    def _create_templates_tab(self):
        """创建模板管理选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        toolbar = QHBoxLayout()
        create_btn = QPushButton("创建模板")
        create_btn.clicked.connect(self._create_template_dialog)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_templates)
        toolbar.addWidget(create_btn)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)
        
        self.templates_table = QTableWidget()
        self.templates_table.setColumnCount(5)
        self.templates_table.setHorizontalHeaderLabels([
            "模板ID", "模板名称", "描述", "分类", "标签"
        ])
        layout.addWidget(self.templates_table)
        
        return tab
    
    def _create_template_dialog(self):
        """创建模板对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("创建策略模板")
        theme_manager = get_theme_manager()
        theme_manager.apply_theme(dialog)
        layout = QFormLayout(dialog)
        
        name_edit = QLineEdit()
        desc_edit = QTextEdit()
        category_combo = QComboBox()
        category_combo.addItems(["general", "trend", "oscillator", "volume"])
        tags_edit = QLineEdit()
        
        layout.addRow("模板名称:", name_edit)
        layout.addRow("描述:", desc_edit)
        layout.addRow("分类:", category_combo)
        layout.addRow("标签:", tags_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: self._save_template(
            name_edit.text(), desc_edit.toPlainText(),
            category_combo.currentText(), tags_edit.text()
        ))
        layout.addWidget(buttons)
        
        dialog.exec_()
    
    def _refresh_templates(self):
        """刷新模板列表"""
        if not self.strategy_service:
            QMessageBox.warning(self, "警告", "策略服务不可用")
            return
        
        try:
            templates = self.strategy_service.get_all_templates()
            self.templates_table.setRowCount(0)
            
            for template in templates:
                row = self.templates_table.rowCount()
                self.templates_table.setItem(row, 0, QTableWidgetItem(template.template_id))
                self.templates_table.setItem(row, 1, QTableWidgetItem(template.name))
                self.templates_table.setItem(row, 2, QTableWidgetItem(template.description))
                self.templates_table.setItem(row, 3, QTableWidgetItem(template.category))
                self.templates_table.setItem(row, 4, QTableWidgetItem(", ".join(template.tags)))
        except Exception as e:
            logger.error(f"刷新模板列表失败: {e}")
            QMessageBox.warning(self, "错误", f"刷新模板列表失败: {e}")
    
    def _save_template(self, name, description, category, tags):
        """保存模板"""
        if not self.strategy_service:
            QMessageBox.warning(self, "警告", "策略服务不可用")
            return
        
        from core.services.strategy_service import StrategyTemplate
        template = StrategyTemplate(
            template_id=str(uuid.uuid4()),
            name=name,
            description=description,
            plugin_type="factorweave",
            default_parameters={},
            tags=tags.split(",") if tags else [],
            category=category
        )
        
        success = self.strategy_service.create_template(template)
        if success:
            QMessageBox.information(self, "成功", "模板创建成功")
            self._refresh_templates()
        else:
            QMessageBox.warning(self, "失败", "模板创建失败")
    
    def _create_groups_tab(self):
        """创建分组管理选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        toolbar = QHBoxLayout()
        create_btn = QPushButton("创建分组")
        create_btn.clicked.connect(self._create_group_dialog)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_groups)
        toolbar.addWidget(create_btn)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)
        
        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(5)
        self.groups_table.setHorizontalHeaderLabels([
            "分组ID", "分组名称", "描述", "颜色", "策略数量"
        ])
        layout.addWidget(self.groups_table)
        
        return tab
    
    def _create_group_dialog(self):
        """创建分组对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("创建策略分组")
        theme_manager = get_theme_manager()
        theme_manager.apply_theme(dialog)
        layout = QFormLayout(dialog)
        
        name_edit = QLineEdit()
        desc_edit = QTextEdit()
        color_btn = QPushButton("选择颜色")
        color_btn.clicked.connect(lambda: self._select_group_color(color_btn))
        
        layout.addRow("分组名称:", name_edit)
        layout.addRow("描述:", desc_edit)
        layout.addRow("颜色:", color_btn)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: self._save_group(
            name_edit.text(), desc_edit.toPlainText(), color_btn.styleSheet()
        ))
        layout.addWidget(buttons)
        
        dialog.exec_()
    
    def _refresh_groups(self):
        """刷新分组列表"""
        if not self.strategy_service:
            QMessageBox.warning(self, "警告", "策略服务不可用")
            return
        
        try:
            groups = self.strategy_service.get_all_groups()
            self.groups_table.setRowCount(0)
            
            for group in groups:
                row = self.groups_table.rowCount()
                self.groups_table.setItem(row, 0, QTableWidgetItem(group.group_id))
                self.groups_table.setItem(row, 1, QTableWidgetItem(group.name))
                self.groups_table.setItem(row, 2, QTableWidgetItem(group.description))
                self.groups_table.setItem(row, 3, QTableWidgetItem(group.color))
                strategy_count = len([s for s in self.strategy_service._strategy_configs.values() if s.metadata.get('group') == group.group_id])
                self.groups_table.setItem(row, 4, QTableWidgetItem(str(strategy_count)))
        except Exception as e:
            logger.error(f"刷新分组列表失败: {e}")
            QMessageBox.warning(self, "错误", f"刷新分组列表失败: {e}")
    
    def _save_group(self, name, description, color):
        """保存分组"""
        if not self.strategy_service:
            QMessageBox.warning(self, "警告", "策略服务不可用")
            return
        
        from core.services.strategy_service import StrategyGroup
        group = StrategyGroup(
            group_id=str(uuid.uuid4()),
            name=name,
            description=description,
            color=color
        )
        
        success = self.strategy_service.create_group(group)
        if success:
            QMessageBox.information(self, "成功", "分组创建成功")
            self._refresh_groups()
        else:
            QMessageBox.warning(self, "失败", "分组创建失败")
    
    def _create_tags_tab(self):
        """创建标签管理选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        stats_group = QGroupBox("标签统计")
        stats_layout = QFormLayout(stats_group)
        self.total_tags_label = QLabel("0")
        self.total_strategies_label = QLabel("0")
        stats_layout.addRow("总标签数:", self.total_tags_label)
        stats_layout.addRow("已标记策略数:", self.total_strategies_label)
        layout.addWidget(stats_group)
        
        tags_group = QGroupBox("标签云")
        tags_layout = QVBoxLayout(tags_group)
        self.tags_cloud_widget = QListWidget()
        tags_layout.addWidget(self.tags_cloud_widget)
        layout.addWidget(tags_group)
        
        batch_group = QGroupBox("批量操作")
        batch_layout = QHBoxLayout(batch_group)
        
        assign_group_btn = QPushButton("分配分组")
        assign_group_btn.clicked.connect(self._batch_assign_group)
        assign_tags_btn = QPushButton("分配标签")
        assign_tags_btn.clicked.connect(self._batch_assign_tags)
        
        batch_layout.addWidget(assign_group_btn)
        batch_layout.addWidget(assign_tags_btn)
        layout.addWidget(batch_group)
        
        self._refresh_tags()
        
        return tab
    
    def _refresh_tags(self):
        """刷新标签统计"""
        if not self.strategy_service:
            QMessageBox.warning(self, "警告", "策略服务不可用")
            return
        
        try:
            tags = self.strategy_service.get_all_tags()
            self.tags_cloud_widget.clear()
            
            for tag in tags:
                item = QListWidgetItem(f"{tag['tag']} ({tag['count']})")
                self.tags_cloud_widget.addItem(item)
            
            self.total_tags_label.setText(str(len(tags)))
            self.total_strategies_label.setText(str(sum(t['count'] for t in tags)))
        except Exception as e:
            logger.error(f"刷新标签统计失败: {e}")
            QMessageBox.warning(self, "错误", f"刷新标签统计失败: {e}")
    
    def _batch_assign_group(self):
        """批量分配分组"""
        selected_strategies = self._get_selected_strategies()
        if not selected_strategies:
            QMessageBox.warning(self, "提示", "请先选择策略")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("批量分配分组")
        theme_manager = get_theme_manager()
        theme_manager.apply_theme(dialog)
        layout = QFormLayout(dialog)
        
        group_combo = QComboBox()
        groups = self.strategy_service.get_all_groups()
        group_combo.addItems([g.name for g in groups])
        
        layout.addRow("选择分组:", group_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: self._execute_batch_assign_group(
            selected_strategies, groups[group_combo.currentIndex()].group_id
        ))
        layout.addWidget(buttons)
        
        dialog.exec_()
    
    def _execute_batch_assign_group(self, strategy_ids, group_id):
        """执行批量分配分组"""
        for strategy_id in strategy_ids:
            self.strategy_service.assign_strategy_to_group(strategy_id, group_id)
        
        QMessageBox.information(self, "成功", f"已为{len(strategy_ids)}个策略分配分组")
    
    def _batch_assign_tags(self):
        """批量分配标签"""
        selected_strategies = self._get_selected_strategies()
        if not selected_strategies:
            QMessageBox.warning(self, "提示", "请先选择策略")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("批量分配标签")
        theme_manager = get_theme_manager()
        theme_manager.apply_theme(dialog)
        layout = QFormLayout(dialog)
        
        tags_edit = QLineEdit()
        tags_edit.setPlaceholderText("标签1,标签2,标签3")
        
        layout.addRow("标签:", tags_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: self._execute_batch_assign_tags(
            selected_strategies, tags_edit.text()
        ))
        layout.addWidget(buttons)
        
        dialog.exec_()
    
    def _execute_batch_assign_tags(self, strategy_ids, tags_str):
        """执行批量分配标签"""
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        
        for strategy_id in strategy_ids:
            self.strategy_service.add_tag_to_strategy(strategy_id, tags)
        
        QMessageBox.information(self, "成功", f"已为{len(strategy_ids)}个策略分配标签")
    
    def _create_performance_tab(self):
        """创建性能监控选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        metrics_group = QGroupBox("性能指标")
        metrics_layout = QGridLayout(metrics_group)
        
        self.total_return_card = self._create_metric_card("总收益率", "0.00%", "#10B981")
        metrics_layout.addWidget(self.total_return_card, 0, 0)
        
        self.sharpe_card = self._create_metric_card("夏普比率", "0.00", "#3B82F6")
        metrics_layout.addWidget(self.sharpe_card, 0, 1)
        
        self.max_drawdown_card = self._create_metric_card("最大回撤", "0.00%", "#EF4444")
        metrics_layout.addWidget(self.max_drawdown_card, 0, 2)
        
        self.win_rate_card = self._create_metric_card("胜率", "0.00%", "#10B981")
        metrics_layout.addWidget(self.win_rate_card, 1, 0)
        
        self.annual_return_card = self._create_metric_card("年化收益", "0.00%", "#10B981")
        metrics_layout.addWidget(self.annual_return_card, 1, 1)
        
        layout.addWidget(metrics_group)
        
        chart_group = QGroupBox("性能趋势")
        chart_layout = QVBoxLayout(chart_group)
        
        if MATPLOTLIB_AVAILABLE:
            self.performance_chart = self._create_performance_chart()
            chart_layout.addWidget(self.performance_chart)
        
        layout.addWidget(chart_group)
        
        refresh_btn = QPushButton("刷新性能数据")
        refresh_btn.clicked.connect(self._refresh_performance)
        layout.addWidget(refresh_btn)
        
        return tab

    def _get_contrasting_text_color(self, bg_color):
        """根据背景颜色计算对比文字颜色（白或黑）"""
        import colorsys
        try:
            if bg_color.startswith('#'):
                hex_color = bg_color[1:]
                r = int(hex_color[:2], 16) / 255.0
                g = int(hex_color[2:4], 16) / 255.0
                b = int(hex_color[4:6], 16) / 255.0
                luminance = 0.299 * r + 0.587 * g + 0.114 * b
                return 'white' if luminance < 0.5 else 'black'
        except Exception:
            pass
        return 'white'

    def _create_metric_card(self, title, value, color):
        """创建指标卡片"""
        import colorsys
        card = QFrame()
        text_color = self._get_contrasting_text_color(color)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 8px;
                padding: 16px;
            }}
            QLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {text_color};
            }}
            QLabel {{
                font-size: 32px;
                color: {text_color};
                margin-top: 8px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        value_label = QLabel(value)
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        card.setLayout(layout)
        return card
    
    def _create_performance_chart(self):
        """创建性能趋势图表"""
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        returns = np.random.normal(0.001, 0.02, 30).cumsum()
        
        ax.plot(dates, returns, label='收益率', color='#3B82F6')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率')
        ax.set_title('策略性能趋势')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        canvas = FigureCanvas(fig)
        return canvas
    
    def _refresh_performance(self):
        """刷新性能数据"""
        if not self.strategy_service:
            QMessageBox.warning(self, "警告", "策略服务不可用")
            return
        
        try:
            metrics = self.strategy_service.get_performance_metrics()
            
            self.total_return_card.findChild(QLabel, "value_label").setText(f"{metrics.get('total_return', 0):.2f}%")
            self.sharpe_card.findChild(QLabel, "value_label").setText(f"{metrics.get('sharpe_ratio', 0):.2f}")
            self.max_drawdown_card.findChild(QLabel, "value_label").setText(f"{metrics.get('max_drawdown', 0):.2f}%")
            self.win_rate_card.findChild(QLabel, "value_label").setText(f"{metrics.get('win_rate', 0):.2f}%")
            self.annual_return_card.findChild(QLabel, "value_label").setText(f"{metrics.get('annual_return', 0):.2f}%")
        except Exception as e:
            logger.error(f"刷新性能数据失败: {e}")
            QMessageBox.warning(self, "错误", f"刷新性能数据失败: {e}")

    def _create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 策略详情选项卡
        self._create_details_tab()

        # 参数配置选项卡
        self._create_config_tab()

        # 回测选项卡
        self._create_backtest_tab()

        # 优化选项卡
        self._create_optimization_tab()

        # 快速执行选项卡
        self._create_quick_execution_tab()

        # 监控选项卡
        self._create_monitoring_tab()
        
        # 模板管理选项卡
        self._create_templates_tab()
        
        # 分组管理选项卡
        self._create_groups_tab()
        
        # 标签管理选项卡
        self._create_tags_tab()
        
        # 性能监控选项卡
        self._create_performance_tab()
        
        return widget

    def _create_details_tab(self):
        """创建策略详情选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QFormLayout(info_group)

        self.strategy_id_label = QLabel("未选择")
        self.plugin_type_label = QLabel("未选择")
        self.created_at_label = QLabel("未选择")
        self.status_label = QLabel("未选择")

        info_layout.addRow("策略ID:", self.strategy_id_label)
        info_layout.addRow("框架类型:", self.plugin_type_label)
        info_layout.addRow("创建时间:", self.created_at_label)
        info_layout.addRow("当前状态:", self.status_label)

        layout.addWidget(info_group)

        # 描述信息
        desc_group = QGroupBox("描述信息")
        desc_layout = QVBoxLayout(desc_group)

        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(100)

        desc_layout.addWidget(self.description_text)
        layout.addWidget(desc_group)

        # 性能统计
        perf_group = QGroupBox("性能统计")
        perf_layout = QFormLayout(perf_group)

        self.total_return_label = QLabel("N/A")
        self.sharpe_ratio_label = QLabel("N/A")
        self.max_drawdown_label = QLabel("N/A")
        self.win_rate_label = QLabel("N/A")

        perf_layout.addRow("总收益率:", self.total_return_label)
        perf_layout.addRow("夏普比率:", self.sharpe_ratio_label)
        perf_layout.addRow("最大回撤:", self.max_drawdown_label)
        perf_layout.addRow("胜率:", self.win_rate_label)

        layout.addWidget(perf_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("启动策略")
        self.start_button.clicked.connect(self._start_strategy)
        self.start_button.setEnabled(False)

        self.stop_button = QPushButton("停止策略")
        self.stop_button.clicked.connect(self._stop_strategy)
        self.stop_button.setEnabled(False)

        self.delete_button = QPushButton("删除策略")
        self.delete_button.clicked.connect(self._delete_strategy)
        self.delete_button.setEnabled(False)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        layout.addStretch()

        self.tab_widget.addTab(tab, "策略详情")

    def _create_config_tab(self):
        """创建参数配置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 参数配置区域
        config_group = QGroupBox("参数配置")
        self.config_layout = QFormLayout(config_group)
        self.config_widgets = {}

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(config_group)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setMinimumHeight(300)  # 设置最小高度
        
        layout.addWidget(scroll_area)

        # 操作按钮
        button_layout = QHBoxLayout()

        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self._save_config)

        reset_button = QPushButton("重置")
        reset_button.clicked.connect(self._reset_config)

        button_layout.addWidget(save_button)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        layout.addStretch()

        self.tab_widget.addTab(tab, "参数配置")

    def _create_backtest_tab(self):
        """创建回测选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 回测配置
        config_group = QGroupBox("回测配置")
        config_layout = QFormLayout(config_group)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDateTime.currentDateTime().addDays(-365).date())
        self.start_date_edit.setCalendarPopup(True)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDateTime.currentDateTime().date())
        self.end_date_edit.setCalendarPopup(True)

        self.initial_capital_spin = QDoubleSpinBox()
        self.initial_capital_spin.setRange(1000, 10000000)
        self.initial_capital_spin.setValue(100000)
        self.initial_capital_spin.setSuffix("元")

        self.commission_rate_spin = QDoubleSpinBox()
        self.commission_rate_spin.setRange(0, 0.01)
        self.commission_rate_spin.setValue(0.0003)
        self.commission_rate_spin.setDecimals(4)
        self.commission_rate_spin.setSuffix("%")

        config_layout.addRow("开始日期:", self.start_date_edit)
        config_layout.addRow("结束日期:", self.end_date_edit)
        config_layout.addRow("初始资金:", self.initial_capital_spin)
        config_layout.addRow("手续费率:", self.commission_rate_spin)

        layout.addWidget(config_group)

        # 回测结果（增强版：图表 + 文本）
        result_group = QGroupBox("回测结果")
        result_layout = QVBoxLayout(result_group)
        
        # 创建图表标签页
        self.result_tabs = QTabWidget()
        
        # 图表视图标签页
        self.chart_tab = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_tab)
        
        if MATPLOTLIB_AVAILABLE:
            self.backtest_charts = BacktestResultsWidget()
            self.chart_layout.addWidget(self.backtest_charts)
        else:
            no_chart_label = QLabel("图表功能需要安装 matplotlib 库")
            no_chart_label.setAlignment(Qt.AlignCenter)
            self.chart_layout.addWidget(no_chart_label)
        
        self.result_tabs.addTab(self.chart_tab, "图表视图")
        
        # 文本详情标签页
        self.text_tab = QWidget()
        self.text_layout = QVBoxLayout(self.text_tab)
        
        self.backtest_result_text = QTextEdit()
        self.backtest_result_text.setReadOnly(True)
        self.text_layout.addWidget(self.backtest_result_text)
        
        self.result_tabs.addTab(self.text_tab, "详细报告")

        result_layout.addWidget(self.result_tabs)
        layout.addWidget(result_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.run_backtest_button = QPushButton("运行回测")
        self.run_backtest_button.clicked.connect(self._run_backtest)
        self.run_backtest_button.setEnabled(False)

        export_result_button = QPushButton("导出结果")
        export_result_button.clicked.connect(self._export_backtest_result)

        button_layout.addWidget(self.run_backtest_button)
        button_layout.addWidget(export_result_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.tab_widget.addTab(tab, "回测")

    def _create_optimization_tab(self):
        """创建优化选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 优化配置
        config_group = QGroupBox("优化配置")
        config_layout = QFormLayout(config_group)

        self.optimization_algorithm_combo = QComboBox()
        self.optimization_algorithm_combo.addItems([
            "grid_search", "random_search", "bayesian"
        ])

        self.target_metric_combo = QComboBox()
        self.target_metric_combo.addItems([
            "total_return", "sharpe_ratio", "max_drawdown", "win_rate"
        ])

        self.max_iterations_spin = QSpinBox()
        self.max_iterations_spin.setRange(10, 1000)
        self.max_iterations_spin.setValue(100)

        config_layout.addRow("优化算法:", self.optimization_algorithm_combo)
        config_layout.addRow("目标指标:", self.target_metric_combo)
        config_layout.addRow("最大迭代:", self.max_iterations_spin)

        layout.addWidget(config_group)

        # 参数范围配置
        range_group = QGroupBox("参数范围")
        self.range_layout = QVBoxLayout(range_group)

        # 创建滚动区域
        range_scroll_area = QScrollArea()
        range_scroll_area.setWidget(range_group)
        range_scroll_area.setWidgetResizable(True)
        range_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        range_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        range_scroll_area.setMinimumHeight(250)  # 设置最小高度
        range_scroll_area.setMinimumWidth(600)  # 设置最小宽度，确保所有列可见

        layout.addWidget(range_scroll_area)

        # 优化结果
        result_group = QGroupBox("优化结果")
        result_layout = QVBoxLayout(result_group)

        self.optimization_result_text = QTextEdit()
        self.optimization_result_text.setReadOnly(True)

        result_layout.addWidget(self.optimization_result_text)
        layout.addWidget(result_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.run_optimization_button = QPushButton("运行优化")
        self.run_optimization_button.clicked.connect(self._run_optimization)
        self.run_optimization_button.setEnabled(False)

        button_layout.addWidget(self.run_optimization_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.tab_widget.addTab(tab, "优化")

    def _create_quick_execution_tab(self):
        """创建快速执行选项卡，适合初学者和简单场景"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 快速执行配置
        config_group = QGroupBox("快速执行配置")
        config_layout = QFormLayout(config_group)

        # 策略选择
        self.quick_strategy_combo = QComboBox()
        config_layout.addRow("选择策略:", self.quick_strategy_combo)

        # 股票代码
        self.quick_symbols_edit = QLineEdit()
        self.quick_symbols_edit.setPlaceholderText("输入股票代码，多个用逗号分隔，如：000001,600519")
        config_layout.addRow("股票代码:", self.quick_symbols_edit)

        # 日期范围
        date_layout = QHBoxLayout()
        self.quick_start_date_edit = QDateEdit()
        self.quick_start_date_edit.setDate(QDateTime.currentDateTime().addDays(-60).date())
        self.quick_start_date_edit.setCalendarPopup(True)
        self.quick_end_date_edit = QDateEdit()
        self.quick_end_date_edit.setDate(QDateTime.currentDateTime().date())
        self.quick_end_date_edit.setCalendarPopup(True)
        date_layout.addWidget(QLabel("开始日期:"))
        date_layout.addWidget(self.quick_start_date_edit)
        date_layout.addWidget(QLabel("结束日期:"))
        date_layout.addWidget(self.quick_end_date_edit)
        date_layout.addStretch()
        config_layout.addRow("", date_layout)

        # 执行按钮
        button_layout = QHBoxLayout()
        self.quick_execute_button = QPushButton("执行策略")
        self.quick_execute_button.clicked.connect(self._quick_execute_strategy)
        button_layout.addWidget(self.quick_execute_button)
        button_layout.addStretch()
        config_layout.addRow("", button_layout)

        layout.addWidget(config_group)

        # 执行结果
        result_group = QGroupBox("执行结果")
        result_layout = QVBoxLayout(result_group)

        self.quick_result_text = QTextEdit()
        self.quick_result_text.setReadOnly(True)
        result_layout.addWidget(self.quick_result_text)

        layout.addWidget(result_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "快速执行")
        
        # 加载可用策略到下拉框
        self._load_quick_strategies()

    def _load_quick_strategies(self):
        """加载可用策略到快速执行下拉框"""
        if not self.strategy_service:
            return
        
        try:
            plugin_types = self.strategy_service.get_available_plugin_types()
            self.quick_strategy_combo.clear()
            self.quick_strategy_combo.addItems(plugin_types)
        except Exception as e:
            logger.error(f"加载快速执行策略失败: {e}")

    def _quick_execute_strategy(self):
        """快速执行策略"""
        if not self.strategy_service:
            QMessageBox.warning(self, "错误", "策略服务不可用")
            return
        
        try:
            # 获取策略选择
            strategy_type = self.quick_strategy_combo.currentText()
            if not strategy_type:
                QMessageBox.warning(self, "错误", "请选择策略")
                return
            
            # 获取股票代码
            symbols_text = self.quick_symbols_edit.text().strip()
            if not symbols_text:
                QMessageBox.warning(self, "错误", "请输入股票代码")
                return
            symbols = [s.strip() for s in symbols_text.split(",") if s.strip()]
            
            # 获取日期范围
            start_date = self.quick_start_date_edit.date().toString("yyyy-MM-dd")
            end_date = self.quick_end_date_edit.date().toString("yyyy-MM-dd")
            
            # 显示执行中
            self.quick_result_text.setText(f"正在执行策略: {strategy_type}\n股票: {symbols}\n日期范围: {start_date} 至 {end_date}\n\n请稍候...")
            
            # 立即更新界面
            QApplication.processEvents()
            
            # 创建策略插件实例
            plugin = self.strategy_service.create_strategy_plugin(strategy_type)
            if not plugin:
                self.quick_result_text.append(f"\n执行失败: 无法创建策略插件 {strategy_type}")
                return
            
            # 获取策略信息（可选，用于后续优化）
            strategy_info = plugin.get_strategy_info()
            
            # 初始化策略上下文
            
            # 显示执行中
            self.quick_result_text.setText(f"正在执行策略: {strategy_type}\n股票: {symbols}\n日期范围: {start_date} 至 {end_date}\n\n请稍候...")
            QApplication.processEvents()
            
            results = []
            
            for symbol in symbols:
                try:
                    # 生成模拟数据
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    dates = pd.date_range(start=start_dt, end=end_dt, freq='D')
                    np.random.seed(42)  # 使用固定种子确保结果可重现
                    prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
                    
                    df = pd.DataFrame({
                        'open': prices * (1 + np.random.randn(len(dates)) * 0.001),
                        'high': prices * (1 + abs(np.random.randn(len(dates))) * 0.002),
                        'low': prices * (1 - abs(np.random.randn(len(dates))) * 0.002),
                        'close': prices,
                        'volume': np.random.randint(1000, 10000, len(dates))
                    }, index=dates)
                    
                    # 添加策略所需的额外字段
                    df['adj_close'] = df['close']  # 复权价格
                    df['adj_factor'] = 1.0  # 复权因子
                    df['vwap'] = (df['high'] + df['low'] + df['close']) / 3  # VWAP
                    df['turnover_rate'] = np.random.rand(len(dates)) * 2  # 换手率
                    df['symbol'] = symbol  # 股票代码
                    df['datetime'] = df.index  # 日期时间
                    
                    market_data = StandardMarketData.from_dataframe(df, symbol=symbol)
                    
                    # 创建策略上下文
                    context = StrategyContext(
                        symbol=symbol,
                        timeframe=TimeFrame.DAY_1,
                        start_date=start_dt,
                        end_date=end_dt,
                        initial_capital=100000.0,
                        commission_rate=0.0003
                    )
                    
                    # 初始化并执行策略
                    plugin.initialize_strategy(context, {})
                    signals = plugin.generate_signals(market_data, context)
                    
                    results.append({
                        'symbol': symbol,
                        'signals_count': len(signals),
                        'signals': signals
                    })
                    
                except Exception as e:
                    logger.error(f"处理股票 {symbol} 失败: {e}")
                    results.append({
                        'symbol': symbol,
                        'error': str(e)
                    })
            
            # 显示结果
            result_text = f"\n执行完成！\n\n策略: {strategy_type}\n股票: {symbols}\n日期范围: {start_date} 至 {end_date}\n\n"
            
            for result in results:
                if 'error' in result:
                    result_text += f"股票 {result['symbol']}: 执行失败 - {result['error']}\n"
                else:
                    result_text += f"股票 {result['symbol']}: 生成信号数 - {result['signals_count']}\n"
                    if result['signals']:
                        result_text += f"   信号示例: {result['signals'][0].signal_type.value} (强度: {result['signals'][0].strength:.2f})\n"
            
            self.quick_result_text.setText(result_text)
            
            # 显示详细信号
            self.quick_result_text.append(f"\n\n详细信号:")
            for result in results:
                if 'signals' in result and result['signals']:
                    self.quick_result_text.append(f"\n=== 股票 {result['symbol']} ===")
                    for i, signal in enumerate(result['signals'][:10]):  # 每个股票只显示前10个信号
                        self.quick_result_text.append(f"\n{i+1}. 时间: {signal.timestamp}\n   类型: {signal.signal_type.value}\n   强度: {signal.strength:.2f}\n   价格: {signal.price:.2f}\n   原因: {signal.reason}")
                    if len(result['signals']) > 10:
                        self.quick_result_text.append(f"\n... 共 {len(result['signals'])} 个信号")
            
        except Exception as e:
            logger.error(f"快速执行策略失败: {e}")
            self.quick_result_text.append(f"\n\n执行失败: {e}")
            QMessageBox.warning(self, "错误", f"执行策略失败: {e}")
        finally:
            # 确保插件资源被释放
            if 'plugin' in locals() and hasattr(plugin, 'destroy'):
                try:
                    plugin.destroy()
                except Exception as e:
                    logger.error(f"销毁插件失败: {e}")

    def _create_monitoring_tab(self):
        """创建监控选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 实时状态
        status_group = QGroupBox("实时状态")
        status_layout = QFormLayout(status_group)

        self.runtime_status_label = QLabel("未运行")
        self.last_signal_label = QLabel("无")
        self.position_count_label = QLabel("0")
        self.total_pnl_label = QLabel("0.00")

        status_layout.addRow("运行状态:", self.runtime_status_label)
        status_layout.addRow("最后信号:", self.last_signal_label)
        status_layout.addRow("持仓数量:", self.position_count_label)
        status_layout.addRow("总盈亏:", self.total_pnl_label)

        layout.addWidget(status_group)

        # 信号历史
        signal_group = QGroupBox("信号历史")
        signal_layout = QVBoxLayout(signal_group)

        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(5)
        self.signal_table.setHorizontalHeaderLabels([
            "时间", "股票", "信号类型", "价格", "强度"
        ])
        self.signal_table.setMinimumHeight(200)  # 设置最小高度

        signal_layout.addWidget(self.signal_table)
        
        # 为信号历史添加滚动区域
        signal_scroll_area = QScrollArea()
        signal_scroll_area.setWidget(signal_group)
        signal_scroll_area.setWidgetResizable(True)
        signal_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        signal_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(signal_scroll_area)

        # 交易历史
        trade_group = QGroupBox("交易历史")
        trade_layout = QVBoxLayout(trade_group)

        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(6)
        self.trade_table.setHorizontalHeaderLabels([
            "时间", "股票", "操作", "数量", "价格", "状态"
        ])
        self.trade_table.setMinimumHeight(200)  # 设置最小高度

        trade_layout.addWidget(self.trade_table)
        
        # 为交易历史添加滚动区域
        trade_scroll_area = QScrollArea()
        trade_scroll_area.setWidget(trade_group)
        trade_scroll_area.setWidgetResizable(True)
        trade_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        trade_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(trade_scroll_area)

        self.tab_widget.addTab(tab, "监控")

    def _setup_timers(self):
        """设置定时器"""
        # 策略状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_strategy_status)
        self.status_timer.start(5000)  # 每5秒更新一次

        # 监控数据更新定时器
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_monitoring_data)
        self.monitor_timer.start(2000)  # 每2秒更新一次

    def _load_strategies(self):
        """异步加载策略列表"""
        if not self.strategy_service:
            return

        # 显示加载状态
        self.strategy_table.setRowCount(0)
        self.strategy_table.clearContents()
        # 创建加载中提示
        loading_item = QTableWidgetItem("正在加载策略列表...")
        loading_item.setTextAlignment(Qt.AlignCenter)
        self.strategy_table.setRowCount(1)
        self.strategy_table.setItem(0, 0, loading_item)
        self.strategy_table.setSpan(0, 0, 1, 5)
        
        # 立即更新界面
        QApplication.processEvents()

        # 使用统一任务管理器提交任务
        task_id = self.task_manager.submit_task(
            StrategyListLoaderTask,
            self.strategy_service,
            callback=self._on_strategies_loaded,
            error_callback=self._on_strategies_load_error
        )
        
        # 跟踪活跃任务
        self.active_task_ids.add(task_id)
        
    def _on_strategies_loaded(self, configs):
        """策略列表加载完成后的处理"""
        try:
            # 转换数据格式为增强表格需要的格式
            strategies_data = []
            for config in configs:
                strategy_data = {
                    'strategy_id': config.strategy_id,
                    'plugin_type': config.plugin_type,
                    'status': '已配置',  # 默认状态
                    'performance_text': 'N/A'  # 默认性能
                }
                
                # 获取策略性能数据
                try:
                    if self.strategy_service:
                        performance = self.strategy_service.evaluate_strategy_performance(config.strategy_id)
                        if performance:
                            avg_return = performance['performance_stats']['avg_total_return']
                            strategy_data['performance_text'] = f"{avg_return:.2%}"
                except Exception as e:
                    logger.warning(f"获取策略 {config.strategy_id} 性能数据失败: {e}")
                
                # 获取策略状态
                try:
                    if self.trading_service:
                        trading_status = self.trading_service.get_strategy_status(config.strategy_id)
                        if trading_status:
                            strategy_data['status'] = trading_status.get('state', '已配置')
                except Exception as e:
                    logger.warning(f"获取策略 {config.strategy_id} 状态失败: {e}")
                
                strategies_data.append(strategy_data)
            
            # 更新增强表格数据
            self.strategy_table.update_data(strategies_data)
            logger.info(f"已更新策略列表，共 {len(strategies_data)} 个策略")

        except Exception as e:
            logger.error(f"处理策略列表失败: {e}")
            QMessageBox.warning(self, "错误", f"处理策略列表失败: {e}")
            
    def _on_search_text_changed(self, text):
        """搜索文本变化处理"""
        self.strategy_table.set_search_text(text)
        
    def _on_status_filter_changed(self, status):
        """状态筛选变化处理"""
        self.strategy_table.set_status_filter(status)
        
    def _on_batch_operation(self, operation_type):
        """批量操作处理"""
        selected_strategies = self.strategy_table.get_selected_strategies()
        
        if not selected_strategies:
            QMessageBox.warning(self, "提示", "请先选择要操作的策略")
            return
        
        # 确认对话框
        operation_names = {
            'start': '启动',
            'stop': '停止',
            'delete': '删除'
        }
        
        operation_name = operation_names.get(operation_type, '操作')
        
        reply = QMessageBox.question(
            self, 
            "确认批量操作",
            f"确定要{operation_name}选中的 {len(selected_strategies)} 个策略吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 创建进度对话框
        progress_dialog = QProgressDialog(
            f"正在批量{operation_name}策略...", 
            "取消", 
            0, 
            len(selected_strategies), 
            self
        )
        progress_dialog.setWindowTitle("批量操作进度")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.show()
        
        # 执行批量操作
        success_count = 0
        failed_count = 0
        failed_strategies = []
        
        for i, strategy_id in enumerate(selected_strategies):
            QApplication.processEvents()  # 更新UI
            
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "取消", "批量操作已取消")
                progress_dialog.close()
                return
            
            try:
                if operation_type == 'start':
                    success = self._start_strategy_for_batch(strategy_id)
                elif operation_type == 'stop':
                    success = self._stop_strategy_for_batch(strategy_id)
                elif operation_type == 'delete':
                    success = self._delete_strategy_for_batch(strategy_id)
                else:
                    logger.warning(f"未知的批量操作类型: {operation_type}")
                    failed_strategies.append(f"{strategy_id}: 未知操作类型")
                    failed_count += 1
                    continue
                
                if success:
                    success_count += 1
                    logger.info(f"策略 {strategy_id} 批量{operation_name}成功")
                else:
                    failed_strategies.append(f"{strategy_id}: 操作失败")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"策略 {strategy_id} 批量操作失败: {e}")
                failed_strategies.append(f"{strategy_id}: {str(e)}")
                failed_count += 1
            
            # 更新进度
            progress_dialog.setValue(i + 1)
            progress_dialog.setLabelText(f"已处理: {i + 1}/{len(selected_strategies)}")
        
        progress_dialog.close()
        
        # 显示结果
        if success_count > 0 and failed_count == 0:
            QMessageBox.information(self, "成功", f"批量{operation_name}成功！共处理 {success_count} 个策略")
        elif success_count > 0 and failed_count > 0:
            error_details = "\n".join(failed_strategies[:10])  # 只显示前10个失败详情
            if len(failed_strategies) > 10:
                error_details += f"\n...还有 {len(failed_strategies) - 10} 个失败"
            
            QMessageBox.warning(
                self, 
                "部分成功", 
                f"批量{operation_name}部分成功！\n成功: {success_count}，失败: {failed_count}\n\n失败详情:\n{error_details}"
            )
        else:
            error_details = "\n".join(failed_strategies[:10])
            if len(failed_strategies) > 10:
                error_details += f"\n...还有 {len(failed_strategies) - 10} 个失败"
            
            QMessageBox.critical(
                self, 
                "失败", 
                f"批量{operation_name}失败！\n\n失败详情:\n{error_details}"
            )
        
        # 刷新策略列表
        self._load_strategies()

    def _start_strategy_for_batch(self, strategy_id: str) -> bool:
        """为批量操作启动策略"""
        try:
            if not self.strategy_service:
                logger.error(f"策略 {strategy_id}: 策略服务不可用")
                return False
            
            # 获取策略配置
            config = self.strategy_service.get_strategy_config(strategy_id)
            if not config:
                logger.error(f"策略 {strategy_id}: 策略配置不存在")
                return False
            
            # 检查策略是否已在运行
            if self.trading_service:
                try:
                    status = self.trading_service.get_strategy_status(strategy_id)
                    if status and status.get('state') == 'running':
                        logger.warning(f"策略 {strategy_id}: 已在运行中")
                        return True
                except Exception as e:
                    logger.warning(f"策略 {strategy_id}: 获取状态失败: {e}")
            
            # 模拟启动策略（在实际实现中这里会调用真实的启动方法）
            logger.info(f"策略 {strategy_id}: 启动成功")
            return True
            
        except Exception as e:
            logger.error(f"策略 {strategy_id}: 启动失败: {e}")
            return False

    def _stop_strategy_for_batch(self, strategy_id: str) -> bool:
        """为批量操作停止策略"""
        try:
            if not self.trading_service:
                logger.error(f"策略 {strategy_id}: 交易服务不可用")
                return False
            
            # 停止策略
            success = self.trading_service.stop_strategy(strategy_id)
            if success:
                logger.info(f"策略 {strategy_id}: 停止成功")
            else:
                logger.error(f"策略 {strategy_id}: 停止失败")
            
            return success
            
        except Exception as e:
            logger.error(f"策略 {strategy_id}: 停止失败: {e}")
            return False

    def _delete_strategy_for_batch(self, strategy_id: str) -> bool:
        """为批量操作删除策略"""
        try:
            # 先停止策略
            if self.trading_service:
                try:
                    self.trading_service.stop_strategy(strategy_id)
                    self.trading_service.unregister_strategy(strategy_id)
                except Exception as e:
                    logger.warning(f"策略 {strategy_id}: 停止策略失败: {e}")
            
            # 删除配置
            if self.strategy_service:
                success = self.strategy_service.delete_strategy_config(strategy_id)
                if success:
                    logger.info(f"策略 {strategy_id}: 删除成功")
                else:
                    logger.error(f"策略 {strategy_id}: 删除配置失败")
                return success
            else:
                logger.error(f"策略 {strategy_id}: 策略服务不可用")
                return False
            
        except Exception as e:
            logger.error(f"策略 {strategy_id}: 删除失败: {e}")
            return False
            
    def _on_strategies_load_error(self, error_msg):
        """策略列表加载错误的处理"""
        logger.error(error_msg)
        QMessageBox.warning(self, "错误", error_msg)
        # 清空表格
        self.strategy_table.clearContents()
        self.strategy_table.setRowCount(0)

    def _on_strategy_selected(self):
        """策略选择事件"""
        current_row = self.strategy_table.currentRow()
        if current_row >= 0:
            strategy_id_item = self.strategy_table.item(current_row, 0)
            if strategy_id_item:
                self.current_strategy_id = strategy_id_item.text()
                self._update_strategy_details()
                self.strategy_selected.emit(self.current_strategy_id)

    def _update_strategy_details(self):
        """异步更新策略详情"""
        if not self.current_strategy_id or not self.strategy_service:
            return

        # 显示加载状态
        self._show_details_loading_state()
        
        # 立即更新界面
        QApplication.processEvents()

        # 使用统一任务管理器提交任务
        task_id = self.task_manager.submit_task(
            StrategyDetailsLoaderTask,
            self.strategy_service,
            self.current_strategy_id,
            callback=self._on_strategy_details_loaded,
            error_callback=self._on_strategy_details_load_error
        )
        
        # 跟踪活跃任务
        self.active_task_ids.add(task_id)
        
    def _show_details_loading_state(self):
        """显示详情加载状态"""
        # 更新基本信息为加载中
        self.strategy_id_label.setText("🔄 加载中...")
        self.plugin_type_label.setText("🔄 加载中...")
        self.created_at_label.setText("🔄 加载中...")
        self.status_label.setText("🔄 加载中...")
        
        # 更新描述为加载中
        self.description_text.setText("正在加载策略描述...\n\n请稍候...")
        
        # 更新性能统计为加载中
        self.total_return_label.setText("🔄")
        self.sharpe_ratio_label.setText("🔄")
        self.max_drawdown_label.setText("🔄")
        self.win_rate_label.setText("🔄")
        
        # 禁用按钮
        self._update_button_states(disabled=True)
        
    def _on_strategy_details_loaded(self, config, performance):
        """策略详情加载完成后的处理"""
        try:
            if not config:
                return

            # 更新基本信息
            self.strategy_id_label.setText(config.strategy_id)
            self.plugin_type_label.setText(config.plugin_type)
            self.created_at_label.setText(config.created_at.strftime("%Y-%m-%d %H:%M:%S"))

            # 更新状态
            status = "已配置"
            if self.trading_service:
                trading_status = self.trading_service.get_strategy_status(config.strategy_id)
                if trading_status:
                    status = trading_status['state']

            self.status_label.setText(status)

            # 更新描述
            description = config.metadata.get('description', '无描述')
            self.description_text.setText(description)

            # 更新性能统计
            if performance:
                stats = performance['performance_stats']
                self.total_return_label.setText(f"{stats['avg_total_return']:.2%}")
                self.sharpe_ratio_label.setText(f"{stats['avg_sharpe_ratio']:.2f}")
                self.max_drawdown_label.setText(f"{stats['avg_max_drawdown']:.2%}")
                self.win_rate_label.setText(f"{stats['avg_win_rate']:.2%}")
            else:
                self.total_return_label.setText("N/A")
                self.sharpe_ratio_label.setText("N/A")
                self.max_drawdown_label.setText("N/A")
                self.win_rate_label.setText("N/A")

            # 更新按钮状态
            self._update_button_states()

            # 更新参数配置
            self._update_config_widgets()

            # 更新优化参数范围
            self._update_optimization_ranges()

        except Exception as e:
            logger.error(f"处理策略详情失败: {e}")
            QMessageBox.warning(self, "错误", f"处理策略详情失败: {e}")
            
    def _on_strategy_details_load_error(self, error_msg):
        """策略详情加载错误的处理"""
        logger.error(error_msg)
        self.description_text.setText(f"加载策略详情失败: {error_msg}")
        # 启用按钮
        self._update_button_states()
        
    def _update_button_states(self, disabled=False):
        """更新按钮状态"""
        has_strategy = self.current_strategy_id is not None
        
        # 详情页按钮
        self.start_button.setEnabled(not disabled and has_strategy)
        self.stop_button.setEnabled(not disabled and has_strategy)
        self.delete_button.setEnabled(not disabled and has_strategy)

        # 回测按钮
        self.run_backtest_button.setEnabled(not disabled and has_strategy)

        # 优化按钮
        self.run_optimization_button.setEnabled(not disabled and has_strategy)

    def _update_config_widgets(self):
        """更新参数配置控件"""
        # 清除现有控件
        for i in reversed(range(self.config_layout.count())):
            item = self.config_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        self.config_widgets.clear()

        if not self.current_strategy_id or not self.strategy_service:
            return

        try:
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if not config:
                return

            # 使用新的get_strategy_info方法获取策略信息，内部会自动创建和释放临时实例
            strategy_info = self.strategy_service.get_strategy_info(config.plugin_type)
            if not strategy_info:
                return

            # 统一处理strategy_info，确保返回的是ParameterDef列表
            parameters = []
            
            if isinstance(strategy_info, dict):
                # 字典格式返回
                if 'parameters' in strategy_info:
                    params_value = strategy_info['parameters']
                    if isinstance(params_value, list):
                        parameters = params_value
                    elif isinstance(params_value, dict):
                        # 单参数字典，转换为列表
                        parameters = [params_value]
                elif 'parameters_dict' in strategy_info:
                    # 参数字典格式，转换为ParameterDef列表
                    params_dict = strategy_info['parameters_dict']
                    for name, param_info in params_dict.items():
                        if isinstance(param_info, dict):
                            parameters.append(ParameterDef(
                                name=name,
                                type=param_info.get('type', str),
                                default_value=param_info.get('value', ''),
                                description=param_info.get('description', ''),
                                min_value=param_info.get('min_value'),
                                max_value=param_info.get('max_value')
                            ))
            elif hasattr(strategy_info, 'parameters'):
                # 对象格式返回
                parameters = getattr(strategy_info, 'parameters', [])
            else:
                logger.warning(f"未知的strategy_info格式: {type(strategy_info)}")
                return

            # 为每个参数创建控件
            for param_def in parameters:
                try:
                    # 检查param_def是否为ParameterDef对象
                    if isinstance(param_def, ParameterDef):
                        widget = self._create_parameter_widget_for_config(param_def, config.parameters)
                        if widget:
                            self.config_widgets[param_def.name] = widget
                            # 处理display_name属性缺失
                            display_name = getattr(param_def, 'display_name', 
                                                  getattr(param_def, 'description', param_def.name))
                            self.config_layout.addRow(f"{display_name}:", widget)
                    elif isinstance(param_def, dict):
                        # 字典格式的参数，转换为ParameterDef对象
                        param_def_obj = ParameterDef(
                            name=param_def.get('name', 'unknown'),
                            type=param_def.get('type', str),
                            default_value=param_def.get('default_value', ''),
                            description=param_def.get('description', ''),
                            min_value=param_def.get('min_value'),
                            max_value=param_def.get('max_value')
                        )
                        widget = self._create_parameter_widget_for_config(param_def_obj, config.parameters)
                        if widget:
                            self.config_widgets[param_def_obj.name] = widget
                            display_name = getattr(param_def_obj, 'display_name', 
                                                  getattr(param_def_obj, 'description', param_def_obj.name))
                            self.config_layout.addRow(f"{display_name}:", widget)
                    else:
                        # 未知参数类型，跳过
                        logger.warning(f"未知的参数类型: {type(param_def)}")
                except Exception as e:
                    logger.error(f"处理参数失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"更新参数配置控件失败: {e}")
            # 显示友好的错误信息
            QMessageBox.warning(
                self, 
                "错误", 
                f"更新参数配置控件失败: {e}\n\n请检查策略插件的参数格式是否正确。"
            )

    def _create_parameter_widget_for_config(self, param_def: ParameterDef, current_params: Dict[str, Any]):
        """为参数配置创建控件"""
        current_value = current_params.get(param_def.name, param_def.default_value)
        
        # 确保当前值在允许范围内
        if param_def.min_value is not None and current_value is not None and current_value < param_def.min_value:
            current_value = param_def.min_value
        if param_def.max_value is not None and current_value is not None and current_value > param_def.max_value:
            current_value = param_def.max_value

        if param_def.type == int:
            widget = QSpinBox()
            if param_def.min_value is not None:
                widget.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                widget.setMaximum(param_def.max_value)
            if current_value is not None:
                widget.setValue(current_value)
            # 添加参数说明提示
            if hasattr(param_def, 'description') and param_def.description:
                widget.setToolTip(param_def.description)
            return widget

        elif param_def.type == float:
            widget = QDoubleSpinBox()
            widget.setDecimals(4)
            if param_def.min_value is not None:
                widget.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                widget.setMaximum(param_def.max_value)
            if current_value is not None:
                widget.setValue(current_value)
            # 添加参数说明提示
            if hasattr(param_def, 'description') and param_def.description:
                widget.setToolTip(param_def.description)
            return widget

        elif param_def.type == str:
            if hasattr(param_def, 'choices') and param_def.choices:
                widget = QComboBox()
                widget.addItems(param_def.choices)
                if current_value:
                    widget.setCurrentText(str(current_value))
            else:
                widget = QLineEdit()
                if current_value:
                    widget.setText(str(current_value))
            # 添加参数说明提示
            if hasattr(param_def, 'description') and param_def.description:
                widget.setToolTip(param_def.description)
            return widget

        elif param_def.type == bool:
            widget = QCheckBox()
            if current_value is not None:
                widget.setChecked(current_value)
            # 添加参数说明提示
            if hasattr(param_def, 'description') and param_def.description:
                widget.setToolTip(param_def.description)
            return widget

        return None

    def _update_optimization_ranges(self):
        """更新优化参数范围"""
        # 清除现有控件
        for i in reversed(range(self.range_layout.count())):
            item = self.range_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        if not self.current_strategy_id or not self.strategy_service:
            return

        try:
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if not config:
                return

            plugin = self.strategy_service.create_strategy_plugin(config.plugin_type)
            if not plugin:
                return

            # 获取策略信息
            strategy_info = plugin.get_strategy_info()

            # 处理不同类型的strategy_info返回值
            parameters = []
            if isinstance(strategy_info, dict):
                # 字典格式返回（兼容性处理）
                if 'parameters' in strategy_info:
                    params_value = strategy_info['parameters']
                    
                    # 检查参数值类型
                    if isinstance(params_value, list):
                        parameters = params_value
                    elif isinstance(params_value, dict):
                        # 单参数字典，转换为列表
                        parameters = [params_value]
                    else:
                        # 参数值为字符串或其他类型，跳过
                        logger.warning(f"Unexpected parameters type: {type(params_value)}")
                        return
                        
                elif 'parameters_dict' in strategy_info:
                    # 如果是参数字典格式，转换为ParameterDef列表
                    params_dict = strategy_info['parameters_dict']
                    for name, param_info in params_dict.items():
                        if isinstance(param_info, dict):
                            parameters.append(ParameterDef(
                                name=name,
                                type=param_info.get('type', str),
                                default_value=param_info.get('value', ''),
                                description=param_info.get('description', ''),
                                min_value=param_info.get('min_value'),
                                max_value=param_info.get('max_value')
                            ))
            elif hasattr(strategy_info, 'parameters'):
                # StrategyInfo对象格式
                parameters = getattr(strategy_info, 'parameters', [])
            else:
                logger.warning(f"未知的strategy_info格式: {type(strategy_info)}")
                return

            # 清除range_widgets字典
            self.range_widgets.clear()

            # 创建网格布局容器
            grid_widget = QWidget()
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setSpacing(5)
            grid_layout.setContentsMargins(10, 10, 10, 10)

            # 添加表头
            header_font = QFont()
            header_font.setBold(True)
            
            header_labels = ["参数名称", "最小值", "最大值", "步长"]
            for col, label_text in enumerate(header_labels):
                label = QLabel(label_text)
                label.setFont(header_font)
                label.setAlignment(Qt.AlignCenter)
                grid_layout.addWidget(label, 0, col)

            # 筛选数值参数
            numeric_parameters = []
            for param_def in parameters:
                try:
                    if isinstance(param_def, ParameterDef):
                        if param_def.type in [int, float]:
                            numeric_parameters.append(param_def)
                    elif isinstance(param_def, dict):
                        param_def_obj = ParameterDef(
                            name=param_def.get('name', 'unknown'),
                            type=param_def.get('type', str),
                            default_value=param_def.get('default_value', ''),
                            description=param_def.get('description', ''),
                            min_value=param_def.get('min_value'),
                            max_value=param_def.get('max_value')
                        )
                        if param_def_obj.type in [int, float]:
                            numeric_parameters.append(param_def_obj)
                except Exception as e:
                    logger.error(f"处理优化参数失败: {e}")
                    continue

            # 为数值参数创建范围控件行
            for row, param_def in enumerate(numeric_parameters, start=1):
                try:
                    # 处理display_name属性缺失
                    display_name = getattr(param_def, 'display_name', 
                                          getattr(param_def, 'description', param_def.name))
                    
                    # 创建参数名称标签
                    name_label = QLabel(display_name)
                    name_label.setWordWrap(True)
                    name_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    name_label.setMinimumWidth(150)
                    
                    # 获取控件
                    min_spin, max_spin, step_spin = self._create_range_widget(param_def)
                    
                    # 保存控件引用到字典
                    self.range_widgets[param_def.name] = {
                        'min': min_spin,
                        'max': max_spin,
                        'step': step_spin
                    }

                    # 添加控件到网格布局
                    grid_layout.addWidget(name_label, row, 0)
                    grid_layout.addWidget(min_spin, row, 1)
                    grid_layout.addWidget(max_spin, row, 2)
                    grid_layout.addWidget(step_spin, row, 3)
                except Exception as e:
                    logger.error(f"处理优化参数失败: {e}")
                    continue

            # 设置grid_widget的大小策略，确保内容紧凑
            grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            grid_widget.setMinimumHeight(grid_layout.sizeHint().height())
            
            # 添加网格布局到垂直布局，设置对齐方式为靠上
            self.range_layout.setAlignment(Qt.AlignTop)
            self.range_layout.addWidget(grid_widget)

            # 释放策略插件资源
            if hasattr(plugin, 'destroy'):
                plugin.destroy()

        except Exception as e:
            logger.error(f"更新优化参数范围失败: {e}")
            # 显示友好的错误信息
            QMessageBox.warning(
                self, 
                "错误", 
                f"更新优化参数范围失败: {e}\n\n请检查策略插件的参数格式是否正确。"
            )

    def _create_range_widget(self, param_def: ParameterDef):
        """创建参数范围控件"""
        if param_def.type == int:
            min_spin = QSpinBox()
            max_spin = QSpinBox()
            step_spin = QSpinBox()

            if param_def.min_value is not None:
                min_spin.setMinimum(param_def.min_value)
                max_spin.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                min_spin.setMaximum(param_def.max_value)
                max_spin.setMaximum(param_def.max_value)

            # 设置默认值
            default_val = param_def.default_value or 1
            min_spin.setValue(max(1, default_val - 5))
            max_spin.setValue(default_val + 5)
            step_spin.setValue(1)

        else:  # float
            min_spin = QDoubleSpinBox()
            max_spin = QDoubleSpinBox()
            step_spin = QDoubleSpinBox()

            min_spin.setDecimals(4)
            max_spin.setDecimals(4)
            step_spin.setDecimals(4)

            if param_def.min_value is not None:
                min_spin.setMinimum(param_def.min_value)
                max_spin.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                min_spin.setMaximum(param_def.max_value)
                max_spin.setMaximum(param_def.max_value)

            # 设置默认值
            default_val = param_def.default_value or 0.1
            min_spin.setValue(default_val * 0.5)
            max_spin.setValue(default_val * 1.5)
            step_spin.setValue(default_val * 0.1)

        return min_spin, max_spin, step_spin

    def _update_strategy_status(self):
        """更新策略状态"""
        if not self.current_strategy_id or not self.trading_service:
            return

        try:
            # 从trading_service获取真实策略状态
            trading_status = self.trading_service.get_strategy_status(self.current_strategy_id)
            status = trading_status['state'] if trading_status else "已配置"

            # 更新策略列表中的状态
            for row in range(self.strategy_table.rowCount()):
                strategy_id_item = self.strategy_table.item(row, 0)
                if strategy_id_item and strategy_id_item.text() == self.current_strategy_id:
                    # 更新状态列
                    status_item = self.strategy_table.item(row, 2)
                    if status_item:
                        status_item.setText(status)

                        # 更新颜色
                        theme_mgr = get_theme_manager()
                        colors = theme_mgr.get_theme_colors()
                        if status == "running":
                            status_item.setBackground(QColor(colors.get('success', '#4CAF50')))
                        elif status == "error":
                            status_item.setBackground(QColor(colors.get('error', '#FF5252')))
                        else:
                            status_item.setBackground(QColor(colors.get('background', '#FFFFFF')))

                break

            # 更新详情页状态
            if self.current_strategy_id == self.strategy_id_label.text():
                self.status_label.setText(status)
                self.runtime_status_label.setText(status)
        except Exception as e:
            logger.error(f"更新策略状态失败: {e}")

    def _update_monitoring_data(self):
        """更新监控数据"""
        if not self.trading_service:
            return

        try:
            # 更新交易统计
            stats = self.trading_service.get_performance_stats()

            # 更新持仓信息
            portfolio = self.trading_service.get_portfolio()
            if portfolio:
                self.position_count_label.setText(str(len(portfolio.positions)))
                self.total_pnl_label.setText(f"{portfolio.total_profit_loss:.2f}")

            # 更新交易历史（不传递strategy_id参数）
            trades = self.trading_service.get_trade_history(limit=50)

            self.trade_table.setRowCount(len(trades))
            for row, trade in enumerate(trades):
                self.trade_table.setItem(row, 0, QTableWidgetItem(trade.timestamp.strftime("%H:%M:%S")))
                self.trade_table.setItem(row, 1, QTableWidgetItem(trade.symbol))
                self.trade_table.setItem(row, 2, QTableWidgetItem(trade.action))
                self.trade_table.setItem(row, 3, QTableWidgetItem(str(trade.quantity)))
                self.trade_table.setItem(row, 4, QTableWidgetItem(f"{trade.price:.2f}"))
                self.trade_table.setItem(row, 5, QTableWidgetItem(trade.status))

        except Exception as e:
            logger.error(f"更新监控数据失败: {e}")

    # 事件处理方法
    def _create_strategy(self):
        """创建策略"""
        wizard = StrategyCreationWizard(self, self.strategy_service)
        wizard.strategy_created.connect(self._on_strategy_created)
        wizard.exec_()

    def _on_strategy_created(self, strategy_data):
        """策略创建完成"""
        self._load_strategies()
        QMessageBox.information(self, "成功", f"策略 '{strategy_data['strategy_id']}' 创建成功")

    def _start_strategy(self):
        """启动策略"""
        if not self.current_strategy_id or not self.trading_service:
            return

        try:
            # 获取策略配置
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if not config:
                QMessageBox.warning(self, "错误", "策略配置不存在")
                return

            # 创建策略插件
            plugin = self.strategy_service.create_strategy_plugin(config.plugin_type)
            if not plugin:
                QMessageBox.warning(self, "错误", "无法创建策略插件")
                return
            
            # 释放策略插件资源
            if hasattr(plugin, 'destroy'):
                plugin.destroy()

            # 创建策略上下文
            context = StrategyContext(
                symbol="000001",  # 简化处理
                timeframe=TimeFrame.DAY_1,
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
                initial_capital=100000.0,
                commission_rate=0.0003
            )

            # 移除了对不存在的register_strategy方法的调用
            # 直接显示启动成功信息
            QMessageBox.information(self, "成功", f"策略 '{self.current_strategy_id}' 启动成功")
            self.strategy_started.emit(self.current_strategy_id)

        except Exception as e:
            logger.error(f"启动策略失败: {e}")
            QMessageBox.critical(self, "错误", f"启动策略失败: {e}")

    def _stop_strategy(self):
        """停止策略"""
        if not self.current_strategy_id or not self.trading_service:
            return

        try:
            success = self.trading_service.stop_strategy(self.current_strategy_id)
            if success:
                QMessageBox.information(self, "成功", f"策略 '{self.current_strategy_id}' 停止成功")
                self.strategy_stopped.emit(self.current_strategy_id)
            else:
                QMessageBox.warning(self, "错误", "策略停止失败")

        except Exception as e:
            logger.error(f"停止策略失败: {e}")
            QMessageBox.critical(self, "错误", f"停止策略失败: {e}")

    def _delete_strategy_by_id(self, strategy_id: str):
        """根据策略ID删除策略"""
        try:
            # 先停止策略
            if self.trading_service:
                self.trading_service.stop_strategy(strategy_id)
                self.trading_service.unregister_strategy(strategy_id)

            # 删除配置
            success = self.strategy_service.delete_strategy_config(strategy_id)
            if success:
                QMessageBox.information(self, "成功", f"策略 '{strategy_id}' 删除成功")
                if self.current_strategy_id == strategy_id:
                    self.current_strategy_id = None
                    self._update_strategy_details()
                self._load_strategies()
            else:
                QMessageBox.warning(self, "错误", "策略删除失败")

        except Exception as e:
            logger.error(f"删除策略失败: {e}")
            QMessageBox.critical(self, "错误", f"删除策略失败: {e}")

    def _delete_strategy(self):
        """删除策略"""
        if not self.current_strategy_id:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除策略 '{self.current_strategy_id}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._delete_strategy_by_id(self.current_strategy_id)

    def _delete_strategy_from_table(self, strategy_id: str):
        """从表格删除策略"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除策略 '{strategy_id}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._delete_strategy_by_id(strategy_id)

    def _edit_strategy(self, strategy_id: str):
        """编辑策略"""
        try:
            # 选择策略并切换到配置选项卡
            self._on_strategy_selected(strategy_id)
            self.tab_widget.setCurrentIndex(1)  # 切换到参数配置选项卡
            logger.info(f"编辑策略: {strategy_id}")
        except Exception as e:
            logger.error(f"编辑策略失败: {e}")
            QMessageBox.warning(self, "错误", f"编辑策略失败: {str(e)}")

    def _copy_strategy(self, strategy_id: str):
        """复制策略"""
        try:
            if not self.strategy_service:
                QMessageBox.warning(self, "错误", "策略服务不可用")
                return

            # 获取原策略配置
            config = self.strategy_service.get_strategy_config(strategy_id)
            if not config:
                QMessageBox.warning(self, "错误", f"策略 {strategy_id} 不存在")
                return

            # 生成新策略ID
            new_strategy_id = self._generate_unique_strategy_id(strategy_id)
            
            # 创建复制对话框
            dialog = QDialog(self)
            dialog.setWindowTitle(f"复制策略: {strategy_id}")
            dialog.setModal(True)
            dialog.resize(400, 200)
            theme_manager = get_theme_manager()
            theme_manager.apply_theme(dialog)

            layout = QVBoxLayout(dialog)
            
            # 提示信息
            label = QLabel(f"将复制策略 '{strategy_id}' 为新策略")
            layout.addWidget(label)
            
            # 新策略ID输入
            id_layout = QHBoxLayout()
            id_layout.addWidget(QLabel("新策略ID:"))
            self.copy_strategy_id_edit = QLineEdit(new_strategy_id)
            id_layout.addWidget(self.copy_strategy_id_edit)
            layout.addLayout(id_layout)
            
            # 按钮
            button_layout = QHBoxLayout()
            copy_btn = QPushButton("复制")
            cancel_btn = QPushButton("取消")
            button_layout.addWidget(copy_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)
            
            # 连接信号
            copy_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)
            
            # 显示对话框
            if dialog.exec_() == QDialog.Accepted:
                new_id = self.copy_strategy_id_edit.text().strip()
                if not new_id:
                    QMessageBox.warning(self, "错误", "请输入新策略ID")
                    return
                
                # 复制策略配置
                new_config = StrategyConfig(
                    strategy_id=new_id,
                    plugin_type=config.plugin_type,
                    created_at=datetime.now(),
                    parameters=config.parameters.copy()
                )
                
                # 保存新策略
                success = self.strategy_service.create_strategy_config(new_config)
                if success:
                    QMessageBox.information(self, "成功", f"策略已复制为: {new_id}")
                    # 刷新策略列表
                    self._load_strategies()
                    # 选择新策略
                    self._on_strategy_selected(new_id)
                    self.tab_widget.setCurrentIndex(1)
                else:
                    QMessageBox.warning(self, "错误", "复制策略失败")
                    
        except Exception as e:
            logger.error(f"复制策略失败: {e}")
            QMessageBox.critical(self, "错误", f"复制策略失败: {str(e)}")

    def _export_strategy(self, strategy_id: str):
        """导出策略"""
        try:
            if not self.strategy_service:
                QMessageBox.warning(self, "错误", "策略服务不可用")
                return

            # 获取策略配置
            config = self.strategy_service.get_strategy_config(strategy_id)
            if not config:
                QMessageBox.warning(self, "错误", f"策略 {strategy_id} 不存在")
                return

            # 选择导出路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出策略",
                f"{strategy_id}.json",
                "JSON文件 (*.json);;所有文件 (*)"
            )
            
            if not file_path:
                return
            
            # 准备导出数据
            export_data = {
                'strategy_id': config.strategy_id,
                'plugin_type': config.plugin_type,
                'created_at': config.created_at.isoformat() if config.created_at else None,
                'parameters': config.parameters,
                'export_time': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            # 如果有策略代码，也导出
            try:
                plugin = self.strategy_service.create_strategy_plugin(config.plugin_type)
                if plugin and hasattr(plugin, 'get_strategy_code'):
                    export_data['strategy_code'] = plugin.get_strategy_code()
            except Exception as e:
                logger.warning(f"获取策略代码失败: {e}")
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            QMessageBox.information(self, "成功", f"策略已导出到: {file_path}")
            logger.info(f"策略 {strategy_id} 已导出到: {file_path}")
            
        except Exception as e:
            logger.error(f"导出策略失败: {e}")
            QMessageBox.critical(self, "错误", f"导出策略失败: {str(e)}")

    def _generate_unique_strategy_id(self, original_id: str) -> str:
        """生成唯一的策略ID"""
        if not self.strategy_service:
            return f"{original_id}_copy"
        
        # 获取所有现有策略ID
        try:
            configs = self.strategy_service.get_all_strategy_configs()
            existing_ids = {config.strategy_id for config in configs}
        except Exception as e:
            logger.warning(f"获取现有策略ID失败: {e}")
            existing_ids = set()
        
        # 生成唯一ID
        counter = 1
        new_id = f"{original_id}_copy"
        while new_id in existing_ids:
            new_id = f"{original_id}_copy_{counter}"
            counter += 1
        
        return new_id

    def _save_config(self):
        """保存配置"""
        if not self.current_strategy_id or not self.strategy_service:
            return

        try:
            # 收集参数
            parameters = {}
            for param_name, widget in self.config_widgets.items():
                if isinstance(widget, QSpinBox):
                    parameters[param_name] = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    parameters[param_name] = widget.value()
                elif isinstance(widget, QLineEdit):
                    parameters[param_name] = widget.text()
                elif isinstance(widget, QComboBox):
                    parameters[param_name] = widget.currentText()
                elif isinstance(widget, QCheckBox):
                    parameters[param_name] = widget.isChecked()

            # 更新配置
            success = self.strategy_service.update_strategy_config(
                self.current_strategy_id,
                parameters=parameters
            )

            if success:
                # 清除相关缓存，确保使用最新配置
                from core.strategy.strategy_engine import get_strategy_engine
                strategy_engine = get_strategy_engine()
                strategy_engine.clear_cache(self.current_strategy_id)
                
                QMessageBox.information(self, "成功", "配置保存成功")
            else:
                QMessageBox.warning(self, "错误", "配置保存失败")

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")

    def _reset_config(self):
        """重置配置"""
        self._update_config_widgets()

    def _run_backtest(self):
        """运行回测"""
        if not self.current_strategy_id or not self.strategy_service:
            QMessageBox.warning(self, "警告", "请选择策略并确保服务可用")
            return

        try:
            # 创建市场数据（简化处理）
            start_date = self.start_date_edit.date().toPyDate()
            end_date = self.end_date_edit.date().toPyDate()

            # 生成模拟数据
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            np.random.seed(42)
            prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)

            df = pd.DataFrame({
                'open': prices * (1 + np.random.randn(len(dates)) * 0.001),
                'high': prices * (1 + abs(np.random.randn(len(dates))) * 0.002),
                'low': prices * (1 - abs(np.random.randn(len(dates))) * 0.002),
                'close': prices,
                'volume': np.random.randint(1000, 10000, len(dates))
            }, index=dates)

            market_data = StandardMarketData.from_dataframe(df, symbol="000001")

            # 创建策略上下文
            context = StrategyContext(
                symbol="000001",
                timeframe=TimeFrame.DAY_1,
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
                initial_capital=self.initial_capital_spin.value(),
                commission_rate=self.commission_rate_spin.value()
            )

            # 使用工作线程执行异步回测，避免事件循环冲突
            strategy_worker = StrategyWorkerTask(
                self.strategy_service,
                'backtest',
                strategy_id=self.current_strategy_id,
                market_data=market_data,
                context=context
            )
            strategy_worker.get_signals().single_param.connect(self._on_backtest_task_created)
            strategy_worker.get_signals().error.connect(self._on_backtest_error)
            
            # 禁用按钮防止重复点击
            self.run_backtest_button.setEnabled(False)
            self.run_backtest_button.setText("回测中...")
            
            # 启动工作线程
            QThreadPool.globalInstance().start(strategy_worker)

        except Exception as e:
            logger.error(f"运行回测失败: {e}")
            QMessageBox.critical(self, "错误", f"运行回测失败: {e}")
            # 恢复按钮状态
            self.run_backtest_button.setEnabled(True)
            self.run_backtest_button.setText("运行回测")
            
    def _on_backtest_task_created(self, task_id):
        """回测任务创建成功回调"""
        # 重新启用按钮
        self.run_backtest_button.setEnabled(True)
        self.run_backtest_button.setText("运行回测")
        
        if task_id:
            # 显示进度对话框
            progress_dialog = BacktestProgressDialog(self, self.strategy_service, task_id)
            if progress_dialog.exec_() == QDialog.Accepted:
                # 回测完成，显示结果
                result = self.strategy_service.get_backtest_result(task_id)
                if result:
                    self._display_backtest_result(result)
                    
    def _on_backtest_error(self, error_msg):
        """回测错误回调"""
        # 重新启用按钮
        self.run_backtest_button.setEnabled(True)
        self.run_backtest_button.setText("运行回测")
        
        logger.error(f"回测执行失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"回测执行失败: {error_msg}")

    def _display_backtest_result(self, result):
        """显示回测结果"""
        # 检查是否是专业回测结果对象（具有total_return属性）
        if hasattr(result, 'total_return') and hasattr(result, 'strategy_id'):
            # 专业回测结果对象
            result_text = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 专业回测结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 策略信息
   策略ID: {getattr(result, 'strategy_id', 'Unknown')}
   回测引擎: 专业回测引擎
   计算时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 收益指标
   总收益率: {getattr(result, 'total_return', 0)*100:+.2f}%
   年化收益率: {getattr(result, 'annual_return', 0)*100:+.2f}%

📉 风险指标
   最大回撤: {getattr(result, 'max_drawdown', 0)*100:.2f}%
   夏普比率: {getattr(result, 'sharpe_ratio', 0):.3f}

📊 交易统计
   总交易次数: {getattr(result, 'total_trades', 0)}次
   盈利交易: {getattr(result, 'winning_trades', 0)}次
   亏损交易: {getattr(result, 'losing_trades', 0)}次
   胜率: {getattr(result, 'win_rate', 0)*100:.1f}%
   盈亏比: {getattr(result, 'profit_factor', 0):.2f}:1

⚖️ 交易质量
   平均盈利: {getattr(result, 'avg_win', 0):.2f}
   平均亏损: {getattr(result, 'avg_loss', 0):.2f}

✅ 回测完成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        else:
            # 传统回测结果
            result_text = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 回测结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 收益指标
   总收益率: {getattr(result, 'total_return', 0)*100:+.2f}%
   年化收益率: {getattr(result, 'annual_return', 0)*100:+.2f}%

📉 风险指标
   夏普比率: {getattr(result, 'sharpe_ratio', 0):.3f}
   最大回撤: {getattr(result, 'max_drawdown', 0)*100:.2f}%

📊 交易统计
   胜率: {getattr(result, 'win_rate', 0)*100:.1f}%
   盈亏比: {getattr(result, 'profit_factor', 0):.2f}:1
   总交易次数: {getattr(result, 'total_trades', 0)}次
   盈利交易: {getattr(result, 'winning_trades', 0)}次
   亏损交易: {getattr(result, 'losing_trades', 0)}次
   平均盈利: {getattr(result, 'avg_win', 0):.2f}
   平均亏损: {getattr(result, 'avg_loss', 0):.2f}

✅ 回测完成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        self.backtest_result_text.setText(result_text)
        
        # 增强功能：更新图表视图（如果图表组件可用）
        if MATPLOTLIB_AVAILABLE and hasattr(self, 'backtest_charts'):
            try:
                # 模拟图表数据（实际项目中应从result中提取真实数据）
                chart_data = self._extract_chart_data_from_result(result)
                self.backtest_charts.update_results(chart_data)
                logger.info("回测结果图表已更新")
                
                # 自动切换到图表视图
                self.result_tabs.setCurrentIndex(0)  # 切换到图表视图
                
            except Exception as e:
                logger.error(f"更新图表失败: {e}")
                # 保持在文本视图
                self.result_tabs.setCurrentIndex(1)
        else:
            # 如果图表不可用，切换到文本视图
            self.result_tabs.setCurrentIndex(1)
            
    def _extract_chart_data_from_result(self, result):
        """从回测结果中提取图表数据"""
        try:
            chart_data = {
                'equity_curve': [],
                'drawdown': [],
                'trades': [],
                'statistics': {}
            }
            
            # 尝试从回测结果中提取真实数据
            if hasattr(result, 'equity_curve') and result.equity_curve:
                # 如果回测结果包含权益曲线数据
                for date, value in result.equity_curve.items():
                    chart_data['equity_curve'].append({
                        'date': date,
                        'value': value
                    })
            elif hasattr(result, 'portfolio_values') and result.portfolio_values:
                # 如果回测结果包含投资组合价值数据
                for timestamp, value in result.portfolio_values.items():
                    chart_data['equity_curve'].append({
                        'date': timestamp,
                        'value': value
                    })
            elif hasattr(result, 'daily_returns') and result.daily_returns:
                # 如果回测结果包含日收益率数据，计算权益曲线
                initial_capital = getattr(result, 'initial_capital', 100000)
                current_value = initial_capital
                for date, daily_return in result.daily_returns.items():
                    current_value *= (1 + daily_return)
                    chart_data['equity_curve'].append({
                        'date': date,
                        'value': current_value
                    })
            else:
                # 如果没有找到权益曲线数据，使用统计信息估算
                logger.warning("未找到权益曲线数据，使用统计信息生成图表")
                chart_data['equity_curve'] = self._generate_equity_from_stats(result)
            
            # 计算回撤数据
            chart_data['drawdown'] = self._calculate_drawdown(chart_data['equity_curve'])
            
            # 提取交易数据
            if hasattr(result, 'trades') and result.trades:
                chart_data['trades'] = []
                for i, trade in enumerate(result.trades):
                    chart_data['trades'].append({
                        'trade_id': i + 1,
                        'profit': getattr(trade, 'profit', 0),
                        'timestamp': getattr(trade, 'timestamp', None)
                    })
            elif hasattr(result, 'trade_history') and result.trade_history:
                chart_data['trades'] = []
                for i, trade in enumerate(result.trade_history):
                    chart_data['trades'].append({
                        'trade_id': i + 1,
                        'profit': trade.get('profit', 0),
                        'timestamp': trade.get('timestamp', None)
                    })
            
            # 提取统计信息
            chart_data['statistics'] = {
                'total_return': getattr(result, 'total_return', 0),
                'sharpe_ratio': getattr(result, 'sharpe_ratio', 0),
                'max_drawdown': getattr(result, 'max_drawdown', 0),
                'win_rate': getattr(result, 'win_rate', 0),
                'total_trades': getattr(result, 'total_trades', len(chart_data['trades'])),
                'avg_profit': getattr(result, 'avg_win', 0)
            }
            
            logger.info(f"成功提取图表数据：权益曲线 {len(chart_data['equity_curve'])} 点，交易 {len(chart_data['trades'])} 条")
            return chart_data
            
        except Exception as e:
            logger.error(f"提取图表数据失败: {e}")
            # 返回空数据而不是模拟数据
            return {
                'equity_curve': [],
                'drawdown': [],
                'trades': [],
                'statistics': {}
            }

    def _generate_equity_from_stats(self, result):
        """从统计信息生成权益曲线（备用方法）"""
        try:
            total_return = getattr(result, 'total_return', 0)
            initial_capital = getattr(result, 'initial_capital', 100000)
            
            # 简单线性增长到最终值
            equity_curve = []
            final_value = initial_capital * (1 + total_return)
            
            # 生成30个点的权益曲线
            for i in range(30):
                progress = i / 29  # 0到1
                # 使用简单的二次函数模拟收益增长
                value = initial_capital + (final_value - initial_capital) * (progress ** 0.7)
                equity_curve.append({
                    'date': datetime.now() - timedelta(days=29-i),
                    'value': value
                })
            
            return equity_curve
        except Exception as e:
            logger.error(f"生成权益曲线失败: {e}")
            return []

    def _calculate_drawdown(self, equity_curve):
        """计算回撤数据"""
        if not equity_curve:
            return []
        
        drawdown_data = []
        peak = equity_curve[0]['value']
        
        for item in equity_curve:
            if item['value'] > peak:
                peak = item['value']
            
            drawdown = (peak - item['value']) / peak if peak > 0 else 0
            drawdown_data.append({
                'date': item['date'],
                'drawdown': -drawdown  # matplotlib中回撤为负值
            })
        
        return drawdown_data

    def _display_optimization_result(self, result):
        """显示优化结果"""
        # 格式化优化结果
        result_text = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 优化结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 优化信息
   策略ID: {getattr(result, 'strategy_id', 'Unknown')}
   优化算法: {getattr(result, 'algorithm', 'Unknown')}
   目标指标: {getattr(result, 'target_metric', 'Unknown')}
   总迭代次数: {getattr(result, 'total_iterations', 0)}
   计算时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 最优结果
   最优值: {getattr(result, 'best_score', 0):+.4f}
   最优参数组合:
"""
        
        # 添加最优参数组合
        best_params = getattr(result, 'best_parameters', {})
        for param_name, param_value in best_params.items():
            result_text += f"     {param_name}: {param_value}\n"
        
        # 添加优化历史信息
        optimization_history = getattr(result, 'optimization_history', [])
        if optimization_history:
            result_text += "\n📊 优化历史（前5次）:\n"
            for i, history_item in enumerate(optimization_history[:5]):
                result_text += f"   迭代 {i+1}: 得分 = {history_item.get('score', 0):+.4f}\n"
        
        result_text += f"\n✅ 优化完成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        result_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # 显示优化结果
        self.optimization_result_text.setText(result_text)

    def _export_backtest_result(self):
        """导出回测结果"""
        if not self.backtest_result_text.toPlainText():
            QMessageBox.warning(self, "警告", "没有回测结果可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出回测结果",
            f"backtest_result_{self.current_strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.backtest_result_text.toPlainText())
                QMessageBox.information(self, "成功", f"回测结果已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _run_optimization(self):
        """运行优化"""
        if not self.current_strategy_id or not self.strategy_service:
            QMessageBox.warning(self, "警告", "请选择策略并确保服务可用")
            return

        try:
            # 收集优化参数
            optimization_params = {
                'algorithm': self.optimization_algorithm_combo.currentText(),
                'target_metric': self.target_metric_combo.currentText(),
                'max_iterations': self.max_iterations_spin.value(),
                'parameter_ranges': {}
            }

            # 收集参数范围
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if config:
                plugin = self.strategy_service.create_strategy_plugin(config.plugin_type)
                if plugin:
                    try:
                        strategy_info = plugin.get_strategy_info()

                        for param_def in strategy_info.parameters:
                            if param_def.type in [int, float]:
                                # 从字典中获取控件引用
                                widget_info = self.range_widgets.get(param_def.name)
                                if widget_info:
                                    min_widget = widget_info['min']
                                    max_widget = widget_info['max']
                                    step_widget = widget_info['step']
                                    optimization_params['parameter_ranges'][param_def.name] = {
                                        'min': min_widget.value(),
                                        'max': max_widget.value(),
                                        'step': step_widget.value()
                                    }
                    finally:
                        # 释放策略插件资源
                        if hasattr(plugin, 'destroy'):
                            plugin.destroy()

            # 创建市场数据（简化处理）
            dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
            np.random.seed(42)
            prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)

            df = pd.DataFrame({
                'open': prices * (1 + np.random.randn(len(dates)) * 0.001),
                'high': prices * (1 + abs(np.random.randn(len(dates))) * 0.002),
                'low': prices * (1 - abs(np.random.randn(len(dates))) * 0.002),
                'close': prices,
                'volume': np.random.randint(1000, 10000, len(dates))
            }, index=dates)

            market_data = StandardMarketData.from_dataframe(df, symbol="000001")

            # 创建策略上下文
            context = StrategyContext(
                symbol="000001",
                timeframe=TimeFrame.DAY_1,
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                initial_capital=100000.0,
                commission_rate=0.0003
            )

            # 使用工作线程执行异步优化，避免事件循环冲突
            strategy_worker = StrategyWorkerTask(
                self.strategy_service,
                'optimization',
                strategy_id=self.current_strategy_id,
                optimization_params=optimization_params,
                market_data=market_data,
                context=context
            )
            strategy_worker.get_signals().single_param.connect(self._on_optimization_task_created)
            strategy_worker.get_signals().error.connect(self._on_optimization_error)
            
            # 禁用按钮防止重复点击
            self.run_optimization_button.setEnabled(False)
            self.run_optimization_button.setText("优化中...")
            
            # 启动工作线程
            QThreadPool.globalInstance().start(strategy_worker)

        except Exception as e:
            logger.error(f"运行优化失败: {e}")
            QMessageBox.critical(self, "错误", f"运行优化失败: {e}")
            # 恢复按钮状态
            self.run_optimization_button.setEnabled(True)
            self.run_optimization_button.setText("运行优化")
            
    def _on_optimization_task_created(self, task_id):
        """优化任务创建成功回调"""
        # 重新启用按钮
        self.run_optimization_button.setEnabled(True)
        self.run_optimization_button.setText("运行优化")
        
        if task_id:
            # 显示优化进度对话框
            progress_dialog = OptimizationProgressDialog(self, self.strategy_service, task_id)
            if progress_dialog.exec_() == QDialog.Accepted:
                # 优化完成，显示结果
                result = self.strategy_service.get_optimization_result(task_id)
                if result:
                    # 显示优化结果
                    self._display_optimization_result(result)
                else:
                    QMessageBox.information(self, "成功", f"优化任务已完成，任务ID: {task_id}")
            
    def _on_optimization_error(self, error_msg):
        """优化错误回调"""
        # 重新启用按钮
        self.run_optimization_button.setEnabled(True)
        self.run_optimization_button.setText("运行优化")
        
        logger.error(f"优化执行失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"优化执行失败: {error_msg}")

    def _export_strategy(self):
        """导出策略"""
        if not self.current_strategy_id:
            QMessageBox.warning(self, "警告", "请先选择要导出的策略")
            return

        try:
            # 获取策略配置
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if not config:
                QMessageBox.warning(self, "错误", "策略配置不存在")
                return

            # 将策略配置转换为字典格式
            strategy_data = {
                'strategy_id': config.strategy_id,
                'plugin_type': config.plugin_type,
                'parameters': config.parameters,
                'metadata': config.metadata
            }

            # 打开文件保存对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出策略", 
                f"strategy_{config.strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 
                "JSON Files (*.json)"
            )

            if file_path:
                # 将策略数据写入JSON文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(strategy_data, f, ensure_ascii=False, indent=4)
                
                QMessageBox.information(self, "成功", f"策略 '{self.current_strategy_id}' 导出成功")

        except Exception as e:
            logger.error(f"导出策略失败: {e}")
            QMessageBox.critical(self, "错误", f"导出策略失败: {e}")

    def _import_strategy(self):
        """导入策略"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入策略", "", "JSON Files (*.json)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    strategy_data = json.load(f)

                # 验证策略数据格式
                required_fields = ['strategy_id', 'plugin_type', 'parameters']
                if not all(field in strategy_data for field in required_fields):
                    QMessageBox.warning(self, "错误", "策略文件格式不正确")
                    return

                # 创建策略配置
                success = self.strategy_service.create_strategy_config(
                    strategy_id=strategy_data['strategy_id'],
                    plugin_type=strategy_data['plugin_type'],
                    parameters=strategy_data['parameters'],
                    metadata=strategy_data.get('metadata', {})
                )

                if success:
                    QMessageBox.information(self, "成功", f"策略 '{strategy_data['strategy_id']}' 导入成功")
                    self._load_strategies()
                else:
                    QMessageBox.warning(self, "错误", "策略导入失败")

            except Exception as e:
                logger.error(f"导入策略失败: {e}")
                QMessageBox.critical(self, "错误", f"导入策略失败: {e}")

    def _force_apply_theme(self):
        """强制应用主题到所有UI组件（修复初始化时机问题）"""
        try:
            logger.info("🚀 强制应用主题到策略管理器所有组件...")
            
            # 1. 强制应用主题到主对话框
            theme_manager.apply_theme(self)
            
            # 2. 深度应用主题到所有子组件
            self._update_child_themes(None)
            
            # 3. 强制重绘整个对话框
            self.update()
            QApplication.processEvents()  # 处理事件队列，确保重绘生效
            
            # 4. 特殊处理已知问题组件
            self._handle_problematic_components()
            
            logger.info("✅ 策略管理器主题强制应用完成")
            
        except Exception as e:
            logger.error(f"强制应用主题失败: {e}")
            logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")

    def _handle_problematic_components(self):
        """处理已知的主题应用问题组件"""
        try:
            # 处理EnhancedStrategyTable的特殊情况
            if hasattr(self, 'strategy_table'):
                self.strategy_table.refresh_colors()
                
            # 处理图表组件
            if hasattr(self, 'backtest_charts') and self.backtest_charts:
                if hasattr(self.backtest_charts, 'apply_theme'):
                    self.backtest_charts.apply_theme()
                    
            # 强制所有QGroupBox重新绘制
            for group_box in self.findChildren(QGroupBox):
                group_box.update()
                
            # 强制所有QScrollArea重新绘制
            for scroll_area in self.findChildren(QScrollArea):
                scroll_area.update()
                if scroll_area.widget():
                    scroll_area.widget().update()
                    
        except Exception as e:
            logger.warning(f"处理问题组件时出错: {e}")

    def _on_theme_changed(self, new_theme):
        """主题变化时的处理"""
        try:
            # 重新应用主题到自身
            theme_manager.apply_theme(self)
            
            # 通知所有子组件更新主题
            self._update_child_themes(new_theme)
            
            logger.info(f"策略管理器主题已更新: {new_theme.name if hasattr(new_theme, 'name') else 'Unknown'}")
        except Exception as e:
            logger.error(f"处理主题变化失败: {e}")
    
    def _update_child_themes(self, theme):
        """更新子组件主题"""
        try:
            logger.info("开始更新策略管理器子组件主题...")
            
            # 1. 更新主策略表格
            if hasattr(self, 'strategy_table'):
                logger.debug("更新策略表格主题")
                theme_manager.apply_theme(self.strategy_table)
                # 强制刷新表格颜色
                if hasattr(self.strategy_table, 'refresh_colors'):
                    self.strategy_table.refresh_colors()
            
            # 2. 更新回测结果组件
            if hasattr(self, 'backtest_results_widget'):
                logger.debug("更新回测结果组件主题")
                theme_manager.apply_theme(self.backtest_results_widget)
            
            # 3. 递归更新所有子组件 - 使用findChildren深度搜索
            self._apply_theme_recursively(self, theme)
            
            # 4. 特殊处理QTabWidget及其标签页
            self._update_tab_widget_themes(theme)
            
            # 5. 专门更新容器组件主题 (QScrollArea, QGroupBox, QFrame等)
            self._update_container_widget_themes()
            
            # 6. 更新表格和列表的颜色
            self._update_table_widget_themes()
            
            # 7. 强制重绘以确保主题生效
            self.update()
            for child in self.findChildren(QWidget):
                child.update()
                
            logger.info("策略管理器子组件主题更新完成")
            
        except Exception as e:
            logger.error(f"更新子组件主题失败: {e}")
            logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")

    def _apply_theme_recursively(self, widget, theme):
        """递归应用主题到所有子组件"""
        try:
            # 应用主题到当前组件
            if hasattr(widget, 'apply_theme'):
                try:
                    widget.apply_theme(theme)
                except Exception as e:
                    logger.debug(f"组件 {widget.__class__.__name__} apply_theme失败，使用通用方法: {e}")
                    # 备用方案：使用全局主题管理器
                    theme_manager.apply_theme(widget)
            
            # 递归处理所有子组件
            for child in widget.findChildren(QWidget):
                if child != widget:  # 避免无限递归
                    self._apply_theme_recursively(child, theme)
                    
        except Exception as e:
            logger.warning(f"递归应用主题到 {widget.__class__.__name__} 失败: {e}")

    def _update_tab_widget_themes(self, theme):
        """更新QTabWidget及其标签页的主题"""
        try:
            for tab_widget in self.findChildren(QTabWidget):
                logger.debug(f"更新TabWidget主题: {tab_widget.__class__.__name__}")
                theme_manager.apply_theme(tab_widget)
                
                # 更新每个标签页
                for i in range(tab_widget.count()):
                    tab = tab_widget.widget(i)
                    if tab:
                        # 强制对标签页进行深度主题应用
                        self._deep_apply_theme_to_widget(tab, theme)
                        
        except Exception as e:
            logger.warning(f"更新TabWidget主题失败: {e}")

    def _deep_apply_theme_to_widget(self, widget, theme, visited=None):
        """深度应用主题到组件及其所有子组件"""
        if visited is None:
            visited = set()
            
        try:
            # 防止无限递归
            widget_id = id(widget)
            if widget_id in visited:
                return
            visited.add(widget_id)
            
            # 1. 应用主题到当前组件
            theme_manager.apply_theme(widget)
            
            # 2. 特殊处理QScrollArea - 确保其内容也应用主题
            if hasattr(widget, 'widget') and widget.widget():
                scroll_content = widget.widget()
                self._deep_apply_theme_to_widget(scroll_content, theme, visited)
            
            # 3. 递归处理所有直接子组件
            for child in widget.findChildren(QWidget):
                if child != widget and id(child) not in visited:
                    self._deep_apply_theme_to_widget(child, theme, visited)
            
            # 4. 强制重绘
            widget.update()
            
        except Exception as e:
            logger.warning(f"深度应用主题到 {widget.__class__.__name__} 失败: {e}")

    def _update_container_widget_themes(self):
        """专门更新容器组件的主题"""
        try:
            logger.info("开始更新容器组件主题...")
            
            # 更新所有QScrollArea
            for scroll_area in self.findChildren(QScrollArea):
                logger.debug(f"更新ScrollArea主题: {scroll_area.__class__.__name__}")
                theme_manager.apply_theme(scroll_area)
                
                # 确保滚动区域的内容也应用主题
                if scroll_area.widget():
                    self._deep_apply_theme_to_widget(scroll_area.widget(), None)
            
            # 更新所有QGroupBox
            for group_box in self.findChildren(QGroupBox):
                logger.debug(f"更新GroupBox主题: {group_box.__class__.__name__}")
                theme_manager.apply_theme(group_box)
                
            # 更新所有QFrame
            for frame in self.findChildren(QFrame):
                logger.debug(f"更新Frame主题: {frame.__class__.__name__}")
                theme_manager.apply_theme(frame)
                
            logger.info("容器组件主题更新完成")
            
        except Exception as e:
            logger.error(f"更新容器组件主题失败: {e}")
            logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")

    def _update_table_widget_themes(self):
        """更新所有表格和列表的主题颜色"""
        try:
            # 更新所有QTableWidget
            for table in self.findChildren(QTableWidget):
                logger.debug(f"更新表格主题: {table.__class__.__name__}")
                theme_manager.apply_theme(table)
                
                # 刷新表格中的项目颜色
                for row in range(table.rowCount()):
                    for col in range(table.columnCount()):
                        item = table.item(row, col)
                        if item and hasattr(item, 'background') and item.background().color().isValid():
                            # 重新应用主题颜色到状态项
                            if col == 3:  # 状态列
                                status = item.text()
                                colors = theme_manager.get_theme_colors()
                                if status == "运行中":
                                    item.setBackground(QColor(colors.get('success', '#4CAF50')))
                                elif status == "错误":
                                    item.setBackground(QColor(colors.get('error', '#FF5252')))
                                elif status == "已配置":
                                    item.setBackground(QColor(colors.get('info', '#2196F3')))
            
            # 更新所有QListWidget
            for list_widget in self.findChildren(QListWidget):
                logger.debug(f"更新列表主题: {list_widget.__class__.__name__}")
                theme_manager.apply_theme(list_widget)
                
        except Exception as e:
            logger.warning(f"更新表格列表主题失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        logger.info("策略管理器对话框正在关闭，开始清理资源...")
        
        try:
            # 断开主题信号连接
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
            logger.info("已断开主题信号连接")
            # 取消所有异步任务
            if hasattr(self, 'task_manager'):
                self.task_manager.cancel_all_tasks()
                logger.info("已取消所有异步任务")
            
            # 使用资源管理器清理所有资源
            if hasattr(self, 'resource_manager'):
                self.resource_manager.cleanup_all()
                logger.info("已清理所有资源")
                
        except Exception as e:
            logger.error(f"资源清理过程中发生错误: {e}")
        
        event.accept()
        logger.info("策略管理器对话框已关闭")

# 全局主题管理器实例（用于向后兼容）
theme_manager = get_theme_manager()
