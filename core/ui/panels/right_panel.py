from loguru import logger
"""
右侧面板 - 修复版

修复问题：
1. 形态分析标签页数据设置问题
2. 基础功能组件NoneType错误
3. 数据更新时的组件访问问题
"""

import traceback
from typing import Dict, Any, List
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTabWidget, QTextEdit,
    QProgressBar, QMessageBox, QFrame, QGroupBox,
    QTableWidget, QTableWidgetItem, QSpinBox,
    QAbstractItemView, QLineEdit,
    QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from .base_panel import BasePanel
from core.performance import get_performance_monitor
from core.events import AnalysisCompleteEvent, UIDataReadyEvent
from core.services.analysis_service import AnalysisService
from core.services.backtest_result_manager import BacktestResultManager, BacktestResult

# 导入完整的技术分析标签页
try:
    from gui.widgets.analysis_tabs.technical_tab import TechnicalAnalysisTab
    TECHNICAL_TAB_AVAILABLE = True
except ImportError as e:
    # 修复：只记录实际导入失败的情况，忽略内部依赖模块的缺失
    error_msg = str(e)
    # 如果错误信息中包含 enhanced_kline_technical_tab，说明是内部依赖问题，使用 debug 级别
    if 'enhanced_kline_technical_tab' in error_msg:
        logger.debug(f"TechnicalAnalysisTab 内部依赖模块未实现（enhanced_kline_technical_tab），这是正常的: {e}")
    else:
        logger.warning(f"无法导入TechnicalAnalysisTab: {e}")
    TECHNICAL_TAB_AVAILABLE = False

# 导入其他专业分析标签页
try:
    from gui.widgets.analysis_tabs.pattern_tab import PatternAnalysisTab
    from gui.widgets.analysis_tabs.trend_tab import TrendAnalysisTab
    from gui.widgets.analysis_tabs.wave_tab import WaveAnalysisTab
    from gui.widgets.analysis_tabs.sector_flow_tab import SectorFlowTab
    from gui.widgets.analysis_tabs.hotspot_tab import HotspotAnalysisTab
    PROFESSIONAL_TABS_AVAILABLE = True
    ENHANCED_SENTIMENT_AVAILABLE = True
except ImportError as e:
    # 修复：只记录实际导入失败的情况，忽略内部依赖模块的缺失
    error_msg = str(e)
    # 如果错误信息中包含 enhanced_kline_technical_tab，说明是内部依赖问题，使用 debug 级别
    if 'enhanced_kline_technical_tab' in error_msg:
        logger.debug(f"专业分析标签页内部依赖模块未实现（enhanced_kline_technical_tab），这是正常的: {e}")
    else:
        logger.warning(f"无法导入专业分析标签页: {e}")
    PROFESSIONAL_TABS_AVAILABLE = False
    ENHANCED_SENTIMENT_AVAILABLE = False

# 情绪分析标签页已移除（优化性能，避免不必要的网络请求）
PROFESSIONAL_SENTIMENT_AVAILABLE = False

# 导入K线技术分析标签页
# 修复：enhanced_kline_technical_tab模块暂未实现，暂时禁用
KLINE_TECHNICAL_AVAILABLE = False
# try:
#     from gui.widgets.analysis_tabs.enhanced_kline_technical_tab import EnhancedKLineTechnicalTab
#     KLINE_TECHNICAL_AVAILABLE = True
# except ImportError as e:
#     logger.warning(f"无法导入K线技术分析标签页: {e}")
#     KLINE_TECHNICAL_AVAILABLE = False

# 导入AnalysisToolsPanel
try:
    from gui.ui_components import AnalysisToolsPanel
    ANALYSIS_TOOLS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"无法导入AnalysisToolsPanel: {e}")
    ANALYSIS_TOOLS_AVAILABLE = False

# 导入TradingPanel
try:
    from gui.widgets.trading_panel import TradingPanel
    TRADING_PANEL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"无法导入TradingPanel: {e}")
    TRADING_PANEL_AVAILABLE = False





class RightPanel(BasePanel):
    """
    右侧面板 - 修复版

    功能：
    1. 技术指标分析
    2. 买卖信号分析
    3. 风险评估
    4. 历史回测结果
    5. 热点分析与资金流向（情绪分析已优化移除）
    """

    # 定义信号
    analysis_completed = pyqtSignal(str, dict)  # 股票代码, 分析结果

    def __init__(self,
                 parent: QWidget,
                 coordinator,
                 width: int = 350,
                 **kwargs):
        """
        初始化右侧面板

        Args:
            parent: 父窗口组件
            coordinator: 主窗口协调器
            width: 面板宽度
            **kwargs: 其他参数
        """
        # 通过服务容器获取分析服务
        self.analysis_service = None
        if coordinator and hasattr(coordinator, 'service_container') and coordinator.service_container:
            try:
                self.analysis_service = coordinator.service_container.resolve(AnalysisService)
            except Exception as e:
                logger.warning(f"无法获取AnalysisService: {e}")
        self.width = width

        # 当前状态
        self._current_stock_code = ''
        self._current_stock_name = ''
        self._analysis_type = 'comprehensive'  # 默认使用综合分析

        # 分析数据
        self._analysis_data = None

        # 专业标签页列表
        self._professional_tabs = []
        self._has_basic_tabs = False  # 标记是否创建了基础标签页

        # 优化2：待更新标签页跟踪（懒加载机制）
        self._pending_tab_updates = {}  # {tab_index: kline_data}
        self._tab_stock_code = {}       # {tab_index: stock_code} 跟踪每个标签页的数据

        # 性能优化管理器
        self._performance_manager = None
        
        # 回测结果管理器
        self._backtest_result_manager = BacktestResultManager()

        super().__init__(parent, coordinator, **kwargs)
        
        # 订阅回测完成事件
        self.coordinator.event_bus.subscribe(AnalysisCompleteEvent, self._on_analysis_complete)
    
    def _init_ui_events(self) -> None:
        """初始化UI事件连接"""
        try:
            # 过滤按钮点击事件
            filter_button = self.get_widget('filter_button')
            if filter_button:
                filter_button.clicked.connect(self._on_filter_button_clicked)
            
            # 单条删除按钮点击事件
            delete_button = self.get_widget('delete_button')
            if delete_button:
                delete_button.clicked.connect(self._on_delete_button_clicked)
            
            # 清空当前股票按钮点击事件
            clear_stock_button = self.get_widget('clear_stock_button')
            if clear_stock_button:
                clear_stock_button.clicked.connect(self._on_clear_stock_button_clicked)
            
            # 清空全部按钮点击事件
            clear_all_button = self.get_widget('clear_all_button')
            if clear_all_button:
                clear_all_button.clicked.connect(self._on_clear_all_button_clicked)
            
            # 导出按钮点击事件
            export_button = self.get_widget('export_button')
            if export_button:
                export_button.clicked.connect(self._on_export_button_clicked)
            
            # 回测结果列表点击事件
            results_table = self.get_widget('results_table')
            if results_table:
                results_table.cellClicked.connect(self._on_results_table_cell_clicked)
            
            # 分页控件事件
            page_spinbox = self.get_widget('page_spinbox')
            if page_spinbox:
                page_spinbox.valueChanged.connect(self._on_page_changed)
            
            # 每页大小变化事件
            page_size_combo = self.get_widget('page_size_combo')
            if page_size_combo:
                page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
            
            # 上一页按钮
            prev_button = self.get_widget('prev_button')
            if prev_button:
                prev_button.clicked.connect(self._on_prev_page)
            
            # 下一页按钮
            next_button = self.get_widget('next_button')
            if next_button:
                next_button.clicked.connect(self._on_next_page)
            
            # AI选股按钮点击事件
            ai_run_btn = self.get_widget('ai_run_btn')
            if ai_run_btn:
                ai_run_btn.clicked.connect(self._on_ai_select_stocks)
            
            # AI选股导出按钮点击事件
            export_ai_btn = self.get_widget('export_ai_btn')
            if export_ai_btn:
                export_ai_btn.clicked.connect(self._on_export_ai_results)
            
            logger.info("UI事件连接初始化完成")
        except Exception as e:
            logger.error(f"初始化UI事件连接失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_filter_button_clicked(self) -> None:
        """处理过滤按钮点击事件"""
        try:
            logger.info("过滤按钮被点击")
            
            # 重置页码到第一页
            self._current_page = 1
            self._page_spinbox.setValue(1)
            
            # 刷新结果列表（会自动应用过滤条件和分页）
            self._refresh_results_table()
            
        except Exception as e:
            logger.error(f"处理过滤按钮点击事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_delete_button_clicked(self) -> None:
        """处理单条删除按钮点击事件"""
        try:
            logger.info("删除按钮被点击")
            
            # 获取选中的行
            results_table = self.get_widget('results_table')
            if not results_table:
                return
            
            selected_rows = results_table.selectedItems()
            if not selected_rows:
                QMessageBox.warning(self, "警告", "请先选择要删除的回测结果")
                return
            
            # 获取选中行的索引
            selected_row = selected_rows[0].row()
            
            # 获取股票代码
            stock_code_item = results_table.item(selected_row, 0)
            stock_code = stock_code_item.text() if stock_code_item else self._current_stock_code
            
            # 删除回测结果
            success = self._backtest_result_manager.delete_result(stock_code, selected_row)
            if success:
                # 更新回测结果列表
                self._refresh_results_table()
                QMessageBox.information(self, "成功", "回测结果删除成功")
            else:
                QMessageBox.warning(self, "失败", "回测结果删除失败")
            
        except Exception as e:
            logger.error(f"处理删除按钮点击事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_clear_stock_button_clicked(self) -> None:
        """处理清空当前股票按钮点击事件"""
        try:
            logger.info("清空当前股票按钮被点击")
            
            # 确认对话框
            reply = QMessageBox.question(
                self,
                "确认清空",
                f"确定要清空{self._current_stock_name}({self._current_stock_code})的所有回测结果吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 清空当前股票的回测结果
                self._backtest_result_manager.clear_results(self._current_stock_code)
                # 更新回测结果列表
                self._refresh_results_table()
                # 清空回测结果显示
                self._clear_backtest_results()
                QMessageBox.information(self, "成功", "当前股票的回测结果已清空")
            
        except Exception as e:
            logger.error(f"处理清空当前股票按钮点击事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_clear_all_button_clicked(self) -> None:
        """处理清空全部按钮点击事件"""
        try:
            logger.info("清空全部按钮被点击")
            
            # 确认对话框
            reply = QMessageBox.question(
                self,
                "确认清空",
                "确定要清空所有回测结果吗？此操作不可恢复！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 清空所有回测结果
                self._backtest_result_manager.clear_results()
                # 更新回测结果列表
                self._refresh_results_table()
                # 清空回测结果显示
                self._clear_backtest_results()
                QMessageBox.information(self, "成功", "所有回测结果已清空")
            
        except Exception as e:
            logger.error(f"处理清空全部按钮点击事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_export_button_clicked(self) -> None:
        """处理导出按钮点击事件"""
        try:
            logger.info("导出按钮被点击")
            
            # 获取保存文件名
            from PyQt5.QtWidgets import QFileDialog
            options = QFileDialog.Options()
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出回测结果",
                f"回测结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel文件 (*.xlsx);;CSV文件 (*.csv);;JSON文件 (*.json)",
                options=options
            )
            
            if not file_path:
                return
            
            # 确定导出格式
            file_format = 'excel'
            if file_path.endswith('.csv'):
                file_format = 'csv'
            elif file_path.endswith('.json'):
                file_format = 'json'
            
            # 获取过滤条件
            strategy_filter = self.get_widget('strategy_filter')
            min_return_filter = self.get_widget('min_return_filter')
            max_return_filter = self.get_widget('max_return_filter')
            min_success_filter = self.get_widget('min_success_filter')
            max_success_filter = self.get_widget('max_success_filter')
            
            # 提取过滤条件
            strategy_name = strategy_filter.text() if strategy_filter else None
            
            # 转换数值过滤条件
            min_return = float(min_return_filter.text()) if min_return_filter and min_return_filter.text() else None
            max_return = float(max_return_filter.text()) if max_return_filter and max_return_filter.text() else None
            min_success_rate = float(min_success_filter.text()) if min_success_filter and min_success_filter.text() else None
            max_success_rate = float(max_success_filter.text()) if max_success_filter and max_success_filter.text() else None
            
            # 导出回测结果
            success = self._backtest_result_manager.export_results(
                file_path=file_path,
                file_format=file_format,
                stock_code=self._current_stock_code,
                strategy_name=strategy_name,
                min_return=min_return,
                max_return=max_return,
                min_success_rate=min_success_rate,
                max_success_rate=max_success_rate
            )
            
            if success:
                QMessageBox.information(self, "成功", f"回测结果已导出到{file_path}")
            else:
                QMessageBox.warning(self, "失败", "回测结果导出失败")
            
        except Exception as e:
            logger.error(f"处理导出按钮点击事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_results_table_cell_clicked(self, row: int, column: int) -> None:
        """处理回测结果列表点击事件"""
        try:
            logger.info(f"回测结果列表单元格被点击: 行{row}, 列{column}")
            
            # 获取过滤条件，保持与当前显示一致
            strategy_filter = self.get_widget('strategy_filter')
            min_return_filter = self.get_widget('min_return_filter')
            max_return_filter = self.get_widget('max_return_filter')
            min_success_filter = self.get_widget('min_success_filter')
            max_success_filter = self.get_widget('max_success_filter')
            
            # 提取过滤条件
            strategy_name = strategy_filter.text() if strategy_filter else None
            min_return = float(min_return_filter.text()) if min_return_filter and min_return_filter.text() else None
            max_return = float(max_return_filter.text()) if max_return_filter and max_return_filter.text() else None
            min_success_rate = float(min_success_filter.text()) if min_success_filter and min_success_filter.text() else None
            max_success_rate = float(max_success_filter.text()) if max_success_filter and max_success_filter.text() else None
            
            # 获取当前页的回测结果
            current_page_results, _ = self._backtest_result_manager.get_filtered_results(
                stock_code=self._current_stock_code,
                strategy_name=strategy_name,
                min_return=min_return,
                max_return=max_return,
                min_success_rate=min_success_rate,
                max_success_rate=max_success_rate,
                page=self._current_page,
                page_size=self._page_size
            )
            
            if row < len(current_page_results):
                # 获取选中的回测结果
                selected_result = current_page_results[row]
                
                # 更新回测结果显示
                backtest_data = {
                    "is_professional": selected_result.is_professional,
                    "results": selected_result.backtest_results,
                    "trades": selected_result.trades
                }
                self._update_backtest_results_safe(backtest_data)
            
        except Exception as e:
            logger.error(f"处理回测结果列表点击事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _update_results_table(self, results: List[BacktestResult]) -> None:
        """更新回测结果列表"""
        try:
            results_table = self.get_widget('results_table')
            if not results_table:
                return
            
            # 清空表格
            results_table.setRowCount(0)
            
            # 添加回测结果
            for i, result in enumerate(results):
                # 计算收益率和成功率
                return_value = 0.0
                success_rate = 0.0
                
                if isinstance(result.backtest_results, dict):
                    return_value = result.backtest_results.get('avg_return', 0)
                    if return_value == 0 and 'risk_metrics' in result.backtest_results:
                        return_value = result.backtest_results['risk_metrics'].get('总收益率', 0)
                    elif return_value == 0 and 'performance' in result.backtest_results:
                        return_value = result.backtest_results['performance'].get('total_return', 0)
                    
                    success_rate = result.backtest_results.get('success_rate', 0)
                    if success_rate == 0 and 'performance' in result.backtest_results:
                        success_rate = result.backtest_results['performance'].get('win_rate', 0)
                
                # 添加行
                results_table.insertRow(i)
                
                # 股票代码
                results_table.setItem(i, 0, QTableWidgetItem(result.stock_code))
                
                # 策略名称
                results_table.setItem(i, 1, QTableWidgetItem(result.strategy_name))
                
                # 回测时间
                backtest_time = datetime.fromtimestamp(result.backtest_time).strftime('%Y-%m-%d %H:%M:%S')
                results_table.setItem(i, 2, QTableWidgetItem(backtest_time))
                
                # 收益率
                return_item = QTableWidgetItem(f"{return_value:+.2%}")
                if return_value > 0:
                    return_item.setBackground(QColor('#d4edda'))
                elif return_value < 0:
                    return_item.setBackground(QColor('#f8d7da'))
                results_table.setItem(i, 3, return_item)
                
                # 成功率
                success_item = QTableWidgetItem(f"{success_rate:.2%}")
                results_table.setItem(i, 4, success_item)
            
            logger.info(f"回测结果列表已更新，共{len(results)}条记录")
            
        except Exception as e:
            logger.error(f"更新回测结果列表失败: {e}")
            logger.error(traceback.format_exc())
    
    def _refresh_results_table(self) -> None:
        """刷新回测结果列表"""
        try:
            logger.info(f"刷新回测结果列表，当前页码: {self._current_page}, 每页大小: {self._page_size}")
            
            # 获取过滤条件
            strategy_filter = self.get_widget('strategy_filter')
            min_return_filter = self.get_widget('min_return_filter')
            max_return_filter = self.get_widget('max_return_filter')
            min_success_filter = self.get_widget('min_success_filter')
            max_success_filter = self.get_widget('max_success_filter')
            
            # 提取过滤条件
            strategy_name = strategy_filter.text() if strategy_filter else None
            min_return = float(min_return_filter.text()) if min_return_filter and min_return_filter.text() else None
            max_return = float(max_return_filter.text()) if max_return_filter and max_return_filter.text() else None
            min_success_rate = float(min_success_filter.text()) if min_success_filter and min_success_filter.text() else None
            max_success_rate = float(max_success_filter.text()) if max_success_filter and max_success_filter.text() else None
            
            # 获取过滤后的回测结果（带分页）
            results, total = self._backtest_result_manager.get_filtered_results(
                stock_code=self._current_stock_code,
                strategy_name=strategy_name,
                min_return=min_return,
                max_return=max_return,
                min_success_rate=min_success_rate,
                max_success_rate=max_success_rate,
                page=self._current_page,
                page_size=self._page_size
            )
            
            # 更新回测结果列表
            self._update_results_table(results)
            
            # 更新分页控件
            self._total_pages = (total + self._page_size - 1) // self._page_size
            self._page_spinbox.setMaximum(self._total_pages)
            self._total_pages_label.setText(f"/ {self._total_pages}")
            
            logger.info(f"回测结果列表刷新完成，共{total}条记录，分{self._total_pages}页，当前第{self._current_page}页")
            
        except Exception as e:
            logger.error(f"刷新回测结果列表失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_page_changed(self, page: int) -> None:
        """处理页码变化事件"""
        try:
            logger.info(f"页码变化: {self._current_page} -> {page}")
            self._current_page = page
            self._refresh_results_table()
        except Exception as e:
            logger.error(f"处理页码变化事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_page_size_changed(self, page_size: str) -> None:
        """处理每页大小变化事件"""
        try:
            new_page_size = int(page_size)
            logger.info(f"每页大小变化: {self._page_size} -> {new_page_size}")
            self._page_size = new_page_size
            self._current_page = 1  # 重置到第一页
            self._refresh_results_table()
        except Exception as e:
            logger.error(f"处理每页大小变化事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_prev_page(self) -> None:
        """处理上一页按钮点击事件"""
        try:
            if self._current_page > 1:
                logger.info(f"上一页: {self._current_page} -> {self._current_page - 1}")
                self._current_page -= 1
                self._page_spinbox.setValue(self._current_page)
                self._refresh_results_table()
        except Exception as e:
            logger.error(f"处理上一页按钮点击事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_next_page(self) -> None:
        """处理下一页按钮点击事件"""
        try:
            if self._current_page < self._total_pages:
                logger.info(f"下一页: {self._current_page} -> {self._current_page + 1}")
                self._current_page += 1
                self._page_spinbox.setValue(self._current_page)
                self._refresh_results_table()
        except Exception as e:
            logger.error(f"处理下一页按钮点击事件失败: {e}")
            logger.error(traceback.format_exc())

    def _create_widgets(self) -> None:
        """创建UI组件"""
    
        # 创建主布局
        main_layout = QVBoxLayout(self._root_frame)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # 股票信息框
        stock_info_frame = QFrame()
        stock_info_frame.setFrameStyle(QFrame.StyledPanel)
        main_layout.addWidget(stock_info_frame)
        self.add_widget('stock_info_frame', stock_info_frame)

        stock_info_layout = QHBoxLayout(stock_info_frame)
        stock_info_layout.setContentsMargins(10, 10, 10, 10)
        stock_info_layout.setSpacing(8)

        # 股票代码和名称
        stock_label = QLabel("请选择股票")
        stock_label.setStyleSheet(
            "font-size: 14px; font-weight: bold;")
        stock_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        stock_info_layout.addWidget(stock_label)
        self.add_widget('stock_label', stock_label)

        # 分隔符
        separator = QLabel("技术分析 - 当前资产")
        separator.setStyleSheet(
            "font-size: 14px; color: #2ee2e6; margin: 0 5px; font-weight: bold;")
        separator.setAlignment(Qt.AlignCenter)
        stock_info_layout.addWidget(separator)

        # 分析时间
        analysis_time_label = QLabel("")
        analysis_time_label.setStyleSheet("font-size: 12px; color: #cc757d;")
        analysis_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        stock_info_layout.addWidget(analysis_time_label)
        self.add_widget('analysis_time_label', analysis_time_label)

        # 进度条
        progress_bar = QProgressBar()
        progress_bar.setVisible(False)
        progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(progress_bar)
        self.add_widget('progress_bar', progress_bar)

        # 创建标签页
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        self.add_widget('tab_widget', tab_widget)

        # 专业技术分析标签页
        if TECHNICAL_TAB_AVAILABLE:
            config_manager = None
            try:
                if self.coordinator and hasattr(self.coordinator, 'service_container'):
                    from utils.config_manager import ConfigManager
                    config_manager = self.coordinator.service_container.resolve(ConfigManager)
            except Exception as e:
                logger.warning(f"无法获取ConfigManager: {e}")

            self._technical_tab = TechnicalAnalysisTab(config_manager)
            tab_widget.addTab(self._technical_tab, "技术分析")
            self.add_widget('technical_tab', self._technical_tab)
            self._professional_tabs.append(self._technical_tab)

            # 🔧 修复：连接指标计算完成信号，通知主图更新
            self._technical_tab.indicator_calculated.connect(self._on_indicator_calculated)
            logger.info("已连接technical_tab的indicator_calculated信号")

        # 专业分析标签页
        if PROFESSIONAL_TABS_AVAILABLE:
            # 形态分析 - 异步初始化
            try:
                self._pattern_tab = PatternAnalysisTab(config_manager, event_bus=self.coordinator.event_bus)
                tab_widget.addTab(self._pattern_tab, "形态分析")
                self.add_widget('pattern_tab', self._pattern_tab)
                self._professional_tabs.append(self._pattern_tab)
            except Exception as e:
                logger.error(f"创建形态分析标签页失败: {e}")

            # 趋势分析 - 异步初始化
            try:
                self._trend_tab = TrendAnalysisTab(config_manager)
                tab_widget.addTab(self._trend_tab, "趋势分析")
                self.add_widget('trend_tab', self._trend_tab)
                self._professional_tabs.append(self._trend_tab)
            except Exception as e:
                logger.error(f"创建趋势分析标签页失败: {e}")

            # 波浪分析 - 异步初始化
            try:
                self._wave_tab = WaveAnalysisTab(config_manager)
                tab_widget.addTab(self._wave_tab, "波浪分析")
                self.add_widget('wave_tab', self._wave_tab)
                self._professional_tabs.append(self._wave_tab)
            except Exception as e:
                logger.error(f"创建波浪分析标签页失败: {e}")

            # 情绪分析标签页已移除（优化性能，避免不必要的网络请求）
            # 不再创建情绪分析标签页，已被热点分析等功能替代
            logger.info("情绪分析标签页已优化移除，可使用热点分析等功能")
            import time
            # K线技术分析 - 使用服务容器
            # 注释掉整个K线技术分析标签页创建代码，因为enhanced_kline_technical_tab模块暂未实现
            # if KLINE_TECHNICAL_AVAILABLE:
            #     try:
            #         logger.info("开始创建K线技术分析标签页...")
            #
            #         start_time = time.time()
            #
            #         logger.info("导入K线技术分析标签页模块...")
            #         logger.info("K线技术分析标签页模块导入成功")
            #
            #         logger.info("创建K线技术分析标签页实例...")
            #         self._kline_technical_tab = EnhancedKLineTechnicalTab(
            #             config_manager=config_manager
            #         )
            #
            #         create_time = time.time()
            #         logger.info(f"⏱ K线技术分析标签页实例创建耗时: {(create_time - start_time):.2f}秒")
            #
            #         logger.info("添加K线技术分析标签页到UI...")
            #         tab_widget.addTab(self._kline_technical_tab, "K线技术")
            #
            #         # 注册到组件管理
            #         logger.info("注册K线技术分析标签页到组件管理...")
            #         self.add_widget('kline_technical_tab', self._kline_technical_tab)
            #         self._professional_tabs.append(self._kline_technical_tab)
            #
            #         end_time = time.time()
            #         logger.info(f" K线技术分析标签页创建完成，总耗时: {(end_time - start_time):.2f}秒")
            #     except Exception as kline_error:
            #         logger.error(f" K线技术分析标签页创建失败: {kline_error}")
            #         logger.error(traceback.format_exc())

            # 修复：板块资金流 - 使用服务容器（缩进修复，应在 if PROFESSIONAL_TABS_AVAILABLE 块内）
            try:
                logger.info("开始创建板块资金流标签页...")
                start_time = time.time()

                logger.info("导入板块资金流标签页模块...")
                logger.info("板块资金流标签页模块导入成功")

                logger.info("创建板块资金流标签页实例...")
                self._sector_flow_tab = SectorFlowTab(
                    config_manager=config_manager,
                    service_container=self.coordinator.service_container
                )

                create_time = time.time()
                logger.info(f"⏱ 板块资金流标签页实例创建耗时: {(create_time - start_time):.2f}秒")

                logger.info("添加板块资金流标签页到UI...")
                tab_widget.addTab(self._sector_flow_tab, "板块资金流")

                # 注册到组件管理
                logger.info("注册板块资金流标签页到组件管理...")
                self.add_widget('sector_flow_tab', self._sector_flow_tab)
                self._professional_tabs.append(self._sector_flow_tab)

                end_time = time.time()
                logger.info(f" 板块资金流标签页创建完成，总耗时: {(end_time - start_time):.2f}秒")
            except Exception as e:
                logger.error(f" 板块资金流标签页创建失败: {e}")
                logger.error(traceback.format_exc())

            # 热点分析 - 使用服务容器
            try:
                self._hotspot_tab = HotspotAnalysisTab(
                    config_manager=config_manager,
                    service_container=self.coordinator.service_container
                )
                tab_widget.addTab(self._hotspot_tab, "热点分析")

                # 注册到组件管理
                self.add_widget('hotspot_tab', self._hotspot_tab)
                self._professional_tabs.append(self._hotspot_tab)

                logger.info("热点分析标签页创建完成")
            except Exception as e:
                logger.error(f" 热点分析标签页创建失败: {e}")
                logger.error(traceback.format_exc())

        # 基础功能标签页（如果专业标签页不可用时的后备方案，或者总是创建）
        # 修复：总是创建基础标签页，但只有在需要时才显示
        self._create_signal_tab(tab_widget)
        self._create_risk_tab(tab_widget)
        self._create_backtest_tab(tab_widget)
        # 注释掉普通AI选股tab，使用增强AI选股面板
        # self._create_ai_stock_tab(tab_widget)
        self._create_industry_tab(tab_widget)
        self._has_basic_tabs = True
        
        # 初始化UI事件连接 - 移到组件创建之后
        self._init_ui_events()

        # 如果有专业标签页，隐藏基础标签页
        if PROFESSIONAL_TABS_AVAILABLE:
            # 隐藏基础标签页（将它们移到不可见状态，但保持组件存在）
            for i in range(tab_widget.count()):
                if tab_widget.tabText(i) in ["买卖信号", "风险评估", "历史回测", "AI选股", "行业分析"]:
                    tab_widget.removeTab(i)
                    break

        # 批量分析工具标签页
        if ANALYSIS_TOOLS_AVAILABLE:
            # 创建一个继承自QWidget的包装器来传递log_manager
            class AnalysisToolsWrapper(QWidget):
                def __init__(self, parent, logger):
                    super().__init__(parent)
                    # log_manager已迁移到Loguru

            wrapper = AnalysisToolsWrapper(self._root_frame, logger)
            self._analysis_tools_panel = AnalysisToolsPanel(parent=wrapper)
            tab_widget.addTab(self._analysis_tools_panel, "批量分析")
            self.add_widget('analysis_tools_panel', self._analysis_tools_panel)

        # 实盘交易标签页
        if TRADING_PANEL_AVAILABLE:
            try:
                # 从服务容器获取交易服务
                trading_service = None
                if self.coordinator and hasattr(self.coordinator, 'service_container'):
                    from core.services.trading_service import TradingService
                    trading_service = self.coordinator.service_container.resolve(TradingService)

                if trading_service:
                    self._trading_panel = TradingPanel(
                        trading_service=trading_service,
                        event_bus=self.coordinator.event_bus,
                        parent=self._root_frame
                    )
                    tab_widget.addTab(self._trading_panel, "实盘交易")
                    self.add_widget('trading_panel', self._trading_panel)
                    logger.info("实盘交易标签页创建成功")
                else:
                    logger.warning("无法获取TradingService，跳过实盘交易标签页")

            except Exception as e:
                logger.error(f" 创建实盘交易标签页失败: {e}")
                logger.error(traceback.format_exc())

        # 性能监控标签页已删除 - 根据用户要求移除

        # 控制按钮框架
        button_frame = QFrame()
        main_layout.addWidget(button_frame)
        self.add_widget('button_frame', button_frame)

        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 5, 0, 0)
        button_layout.setSpacing(5)

        # 刷新分析按钮
        refresh_btn = QPushButton("刷新分析")
        refresh_btn.clicked.connect(self._refresh_analysis)
        button_layout.addWidget(refresh_btn)
        self.add_widget('refresh_btn', refresh_btn)

        # 导出报告按钮
        export_btn = QPushButton("导出报告")
        export_btn.clicked.connect(self._export_report)
        button_layout.addWidget(export_btn)
        self.add_widget('export_btn', export_btn)

        # 状态标签
        status_label = QLabel("就绪")
        status_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        main_layout.addWidget(status_label)
        self.add_widget('status_label', status_label)

        # 在所有标签页创建完成后，初始化性能管理器
        QTimer.singleShot(100, self._initialize_performance_manager)

    def _create_signal_tab(self, parent: QTabWidget) -> None:
        """创建买卖信号标签页"""
        signal_widget = QWidget()
        parent.addTab(signal_widget, "买卖信号")
        self.add_widget('signal_widget', signal_widget)

        layout = QVBoxLayout(signal_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 当前信号组
        current_signal_group = QGroupBox("当前信号")
        layout.addWidget(current_signal_group)
        self.add_widget('current_signal_group', current_signal_group)

        current_signal_layout = QVBoxLayout(current_signal_group)

        # 信号状态标签
        signal_status_label = QLabel("暂无信号")
        signal_status_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #6c757d; padding: 20px;")
        signal_status_label.setAlignment(Qt.AlignCenter)
        current_signal_layout.addWidget(signal_status_label)
        self.add_widget('signal_status_label', signal_status_label)

        # 信号历史组
        signal_history_group = QGroupBox("信号历史")
        layout.addWidget(signal_history_group)
        self.add_widget('signal_history_group', signal_history_group)

        signal_history_layout = QVBoxLayout(signal_history_group)

        # 信号历史表格
        signal_table = QTableWidget(0, 5)
        signal_table.setHorizontalHeaderLabels(['时间', '信号', '价格', '强度', '收益'])
        signal_table.horizontalHeader().setStretchLastSection(True)
        signal_table.setAlternatingRowColors(True)
        signal_history_layout.addWidget(signal_table)
        self.add_widget('signal_table', signal_table)

        # 信号统计组
        signal_stats_group = QGroupBox("信号统计")
        layout.addWidget(signal_stats_group)
        self.add_widget('signal_stats_group', signal_stats_group)

        signal_stats_layout = QVBoxLayout(signal_stats_group)

        # 信号统计文本
        signal_stats_text = QTextEdit()
        signal_stats_text.setReadOnly(True)
        signal_stats_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        signal_stats_layout.addWidget(signal_stats_text)
        self.add_widget('signal_stats_text', signal_stats_text)

    def _create_risk_tab(self, parent: QTabWidget) -> None:
        """创建风险评估标签页"""
        risk_widget = QWidget()
        parent.addTab(risk_widget, "风险评估")
        self.add_widget('risk_widget', risk_widget)

        layout = QVBoxLayout(risk_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 风险等级组
        risk_level_group = QGroupBox("风险等级")
        layout.addWidget(risk_level_group)
        self.add_widget('risk_level_group', risk_level_group)

        risk_level_layout = QVBoxLayout(risk_level_group)

        # 风险等级标签
        risk_level_label = QLabel("未知\n风险评分: --")
        risk_level_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #6c757d; padding: 15px;")
        risk_level_label.setAlignment(Qt.AlignCenter)
        risk_level_layout.addWidget(risk_level_label)
        self.add_widget('risk_level_label', risk_level_label)

        # 风险指标组
        risk_metrics_group = QGroupBox("风险指标")
        layout.addWidget(risk_metrics_group)
        self.add_widget('risk_metrics_group', risk_metrics_group)

        risk_metrics_layout = QVBoxLayout(risk_metrics_group)

        # 风险指标表格
        risk_table = QTableWidget(0, 2)
        risk_table.setHorizontalHeaderLabels(['指标', '数值'])
        risk_table.horizontalHeader().setStretchLastSection(True)
        risk_table.setAlternatingRowColors(True)
        risk_metrics_layout.addWidget(risk_table)
        self.add_widget('risk_table', risk_table)

        # 风险建议组
        risk_advice_group = QGroupBox("风险建议")
        layout.addWidget(risk_advice_group)
        self.add_widget('risk_advice_group', risk_advice_group)

        risk_advice_layout = QVBoxLayout(risk_advice_group)

        # 风险建议文本
        risk_advice_text = QTextEdit()
        risk_advice_text.setReadOnly(True)
        risk_advice_layout.addWidget(risk_advice_text)
        self.add_widget('risk_advice_text', risk_advice_text)

    def _create_backtest_tab(self, parent: QTabWidget) -> None:
        """创建历史回测标签页"""
        backtest_widget = QWidget()
        parent.addTab(backtest_widget, "历史回测")
        self.add_widget('backtest_widget', backtest_widget)

        layout = QVBoxLayout(backtest_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 回测结果管理组
        backtest_manager_group = QGroupBox("回测结果管理")
        layout.addWidget(backtest_manager_group)
        self.add_widget('backtest_manager_group', backtest_manager_group)

        backtest_manager_layout = QVBoxLayout(backtest_manager_group)

        # 过滤条件区域
        filter_layout = QGridLayout()
        backtest_manager_layout.addLayout(filter_layout)

        # 策略名称过滤
        filter_layout.addWidget(QLabel("策略名称:"), 0, 0)
        strategy_filter = QLineEdit()
        strategy_filter.setPlaceholderText("输入策略名称进行过滤")
        filter_layout.addWidget(strategy_filter, 0, 1)
        self.add_widget('strategy_filter', strategy_filter)

        # 收益率范围过滤
        filter_layout.addWidget(QLabel("收益率范围:"), 1, 0)
        return_layout = QHBoxLayout()
        min_return_filter = QLineEdit()
        min_return_filter.setPlaceholderText("最小")
        min_return_filter.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return_layout.addWidget(min_return_filter)
        return_layout.addWidget(QLabel("到"))
        max_return_filter = QLineEdit()
        max_return_filter.setPlaceholderText("最大")
        max_return_filter.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return_layout.addWidget(max_return_filter)
        filter_layout.addLayout(return_layout, 1, 1)
        self.add_widget('min_return_filter', min_return_filter)
        self.add_widget('max_return_filter', max_return_filter)

        # 成功率范围过滤
        filter_layout.addWidget(QLabel("成功率范围:"), 2, 0)
        success_layout = QHBoxLayout()
        min_success_filter = QLineEdit()
        min_success_filter.setPlaceholderText("最小")
        min_success_filter.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        success_layout.addWidget(min_success_filter)
        success_layout.addWidget(QLabel("到"))
        max_success_filter = QLineEdit()
        max_success_filter.setPlaceholderText("最大")
        max_success_filter.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        success_layout.addWidget(max_success_filter)
        filter_layout.addLayout(success_layout, 2, 1)
        self.add_widget('min_success_filter', min_success_filter)
        self.add_widget('max_success_filter', max_success_filter)

        # 过滤按钮
        filter_button = QPushButton("应用过滤")
        filter_layout.addWidget(filter_button, 3, 0, 1, 2)
        self.add_widget('filter_button', filter_button)

        # 回测结果列表
        results_list_group = QGroupBox("回测结果列表")
        backtest_manager_layout.addWidget(results_list_group)
        self.add_widget('results_list_group', results_list_group)

        results_list_layout = QVBoxLayout(results_list_group)

        # 回测结果列表
        results_table = QTableWidget(0, 5)
        results_table.setHorizontalHeaderLabels(['股票代码', '策略名称', '回测时间', '收益率', '成功率'])
        results_table.horizontalHeader().setStretchLastSection(True)
        results_table.setAlternatingRowColors(True)
        results_table.setSelectionMode(QAbstractItemView.SingleSelection)
        results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        results_list_layout.addWidget(results_table)
        self.add_widget('results_table', results_table)
        
        # 分页控件
        pagination_layout = QHBoxLayout()
        results_list_layout.addLayout(pagination_layout)
        
        # 当前页码
        pagination_layout.addWidget(QLabel("页码:"))
        self._current_page = 1
        self._page_size = 10
        self._total_pages = 1
        
        # 页码输入
        self._page_spinbox = QSpinBox()
        self._page_spinbox.setMinimum(1)
        self._page_spinbox.setMaximum(1)
        self._page_spinbox.setValue(1)
        pagination_layout.addWidget(self._page_spinbox)
        self.add_widget('page_spinbox', self._page_spinbox)
        
        # 总页数
        self._total_pages_label = QLabel("/ 1")
        pagination_layout.addWidget(self._total_pages_label)
        self.add_widget('total_pages_label', self._total_pages_label)
        
        # 每页大小
        pagination_layout.addWidget(QLabel("每页:"))
        self._page_size_combo = QComboBox()
        self._page_size_combo.addItems(['10', '20', '50', '100'])
        self._page_size_combo.setCurrentText('10')
        pagination_layout.addWidget(self._page_size_combo)
        self.add_widget('page_size_combo', self._page_size_combo)
        
        # 翻页按钮
        prev_button = QPushButton("上一页")
        pagination_layout.addWidget(prev_button)
        self.add_widget('prev_button', prev_button)
        
        next_button = QPushButton("下一页")
        pagination_layout.addWidget(next_button)
        self.add_widget('next_button', next_button)

        # 按钮组
        buttons_layout = QHBoxLayout()
        backtest_manager_layout.addLayout(buttons_layout)

        # 单条删除按钮
        delete_button = QPushButton("删除选中")
        buttons_layout.addWidget(delete_button)
        self.add_widget('delete_button', delete_button)

        # 按股票清空按钮
        clear_stock_button = QPushButton("清空当前股票")
        buttons_layout.addWidget(clear_stock_button)
        self.add_widget('clear_stock_button', clear_stock_button)

        # 全部清空按钮
        clear_all_button = QPushButton("清空全部")
        buttons_layout.addWidget(clear_all_button)
        self.add_widget('clear_all_button', clear_all_button)

        # 导出按钮
        export_button = QPushButton("导出结果")
        buttons_layout.addWidget(export_button)
        self.add_widget('export_button', export_button)

        # 回测结果组
        backtest_results_group = QGroupBox("回测结果")
        layout.addWidget(backtest_results_group)
        self.add_widget('backtest_results_group', backtest_results_group)

        backtest_results_layout = QVBoxLayout(backtest_results_group)

        # 回测结果表格
        backtest_table = QTableWidget(0, 2)
        backtest_table.setHorizontalHeaderLabels(['指标', '数值'])
        backtest_table.horizontalHeader().setStretchLastSection(True)
        backtest_table.setAlternatingRowColors(True)
        backtest_results_layout.addWidget(backtest_table)
        self.add_widget('backtest_table', backtest_table)

        # 交易记录组
        trade_records_group = QGroupBox("交易记录")
        layout.addWidget(trade_records_group)
        self.add_widget('trade_records_group', trade_records_group)

        trade_records_layout = QVBoxLayout(trade_records_group)

        # 交易记录表格
        trade_table = QTableWidget(0, 5)
        trade_table.setHorizontalHeaderLabels(['日期', '操作', '价格', '数量', '收益'])
        trade_table.horizontalHeader().setStretchLastSection(True)
        trade_table.setAlternatingRowColors(True)
        trade_records_layout.addWidget(trade_table)
        self.add_widget('trade_table', trade_table)

    def _create_ai_stock_tab(self, parent: QTabWidget) -> None:
        """创建AI选股标签页"""
        ai_stock_widget = QWidget()
        parent.addTab(ai_stock_widget, "AI选股")
        self.add_widget('ai_stock_widget', ai_stock_widget)

        layout = QVBoxLayout(ai_stock_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 选股条件组
        condition_group = QGroupBox("选股条件")
        condition_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(condition_group)
        self.add_widget('ai_condition_group', condition_group)

        condition_layout = QVBoxLayout(condition_group)

        # 自然语言输入
        condition_text = QTextEdit()
        condition_text.setPlaceholderText("请输入选股需求（如：高ROE、低估值、强势资金流等）")
        condition_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        condition_layout.addWidget(condition_text)
        self.add_widget('ai_condition_text', condition_text)

        type_layout_main = QVBoxLayout()

        # 选股类型选择
        type_layout = QHBoxLayout()
        condition_layout.addLayout(type_layout)

        type_layout.addWidget(QLabel("选股类型:"))
        type_combo = QComboBox()
        type_combo.addItems([
            "价值投资", "成长投资", "趋势跟踪", "均值回归",
            "动量策略", "技术分析", "基本面分析", "量化选股"
        ])
        type_layout.addWidget(type_combo)
        self.add_widget('ai_type_combo', type_combo)

        # 风险偏好
        risk_layout = QHBoxLayout()
        condition_layout.addLayout(risk_layout)

        risk_layout.addWidget(QLabel("风险偏好:"))
        risk_combo = QComboBox()
        risk_combo.addItems(["保守", "稳健", "积极", "激进"])
        risk_layout.addWidget(risk_combo)
        self.add_widget('ai_risk_combo', risk_combo)

        type_layout_main.addLayout(type_layout)
        type_layout_main.addLayout(risk_layout)

        # 执行按钮
        ai_run_btn = QPushButton("一键AI选股")
        ai_run_btn.setStyleSheet(
            "background-color: #28a745; font-size: 14px; padding: 8px;")
        condition_layout.addWidget(ai_run_btn)
        self.add_widget('ai_run_btn', ai_run_btn)

        # 选股结果组
        result_group = QGroupBox("选股结果")
        layout.addWidget(result_group)
        self.add_widget('ai_result_group', result_group)

        result_layout = QVBoxLayout(result_group)

        # 结果表格
        result_table = QTableWidget(0, 6)
        result_table.setHorizontalHeaderLabels(
            ['股票代码', '股票名称', '推荐理由', '评分', '风险等级', '建议仓位'])
        result_table.horizontalHeader().setStretchLastSection(True)
        result_table.setAlternatingRowColors(True)
        result_layout.addWidget(result_table)
        self.add_widget('ai_result_table', result_table)

        # 导出按钮
        export_ai_btn = QPushButton("导出选股结果")
        result_layout.addWidget(export_ai_btn)
        self.add_widget('export_ai_btn', export_ai_btn)

    def _create_industry_tab(self, parent: QTabWidget) -> None:
        """创建行业分析标签页"""
        industry_widget = QWidget()
        parent.addTab(industry_widget, "行业分析")
        self.add_widget('industry_widget', industry_widget)

        layout = QVBoxLayout(industry_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 行业概况组
        overview_group = QGroupBox("行业概况")
        layout.addWidget(overview_group)
        self.add_widget('industry_overview_group', overview_group)

        overview_layout = QVBoxLayout(overview_group)

        # 行业信息表格
        overview_table = QTableWidget(0, 2)
        overview_table.setHorizontalHeaderLabels(['指标', '数值'])
        overview_table.horizontalHeader().setStretchLastSection(True)
        overview_table.setAlternatingRowColors(True)
        overview_layout.addWidget(overview_table)
        self.add_widget('industry_overview_table', overview_table)

        # 板块表现组
        performance_group = QGroupBox("板块表现")
        layout.addWidget(performance_group)
        self.add_widget('industry_performance_group', performance_group)

        performance_layout = QVBoxLayout(performance_group)

        # 表现表格
        performance_table = QTableWidget(0, 4)
        performance_table.setHorizontalHeaderLabels(
            ['板块', '涨跌幅', '成交额', '领涨股'])
        performance_table.horizontalHeader().setStretchLastSection(True)
        performance_table.setAlternatingRowColors(True)
        performance_layout.addWidget(performance_table)
        self.add_widget('industry_performance_table', performance_table)

        # 热点分析组
        hotspot_group = QGroupBox("热点分析")
        layout.addWidget(hotspot_group)
        self.add_widget('industry_hotspot_group', hotspot_group)

        hotspot_layout = QVBoxLayout(hotspot_group)

        # 热点文本
        hotspot_text = QTextEdit()
        hotspot_text.setReadOnly(True)
        hotspot_layout.addWidget(hotspot_text)
        self.add_widget('industry_hotspot_text', hotspot_text)

        # 刷新按钮
        refresh_industry_btn = QPushButton("刷新行业数据")
        layout.addWidget(refresh_industry_btn)
        self.add_widget('refresh_industry_btn', refresh_industry_btn)

        layout.addStretch()

    def _bind_events(self) -> None:
        """注册事件处理器"""
        self.event_bus.subscribe(UIDataReadyEvent, self._on_ui_data_ready)
        logger.debug("RightPanel已订阅UIDataReadyEvent事件")

        # 优化2：连接标签页切换信号，实现懒加载
        tab_widget = self.get_widget('tab_widget')
        if tab_widget:
            tab_widget.currentChanged.connect(self._on_tab_changed)
            logger.debug("已连接标签页切换信号（懒加载机制）")

    def _initialize_performance_manager(self) -> None:
        """初始化性能管理器"""
        try:
            # 获取标签页组件
            tab_widget = self.get_widget('tab_widget')

            # 使用统一性能监控系统
            self._performance_manager = get_performance_monitor()

            # 标签页性能监控已通过统一系统自动启用
            logger.info("标签页性能监控已启用")

            logger.info("统一性能监控系统已集成")

            # 统一性能监控标签页已自动连接到性能监控系统
            if hasattr(self, '_performance_monitor_tab') and self._performance_monitor_tab:
                logger.info("统一性能监控标签页已就绪")

        except Exception as e:
            logger.error(f" 性能管理器初始化失败: {e}")

    def _register_tabs_with_performance_monitor(self):
        """标签页性能监控已通过统一系统自动处理"""
        logger.info(f" 标签页性能监控已启用，共监控 {len(self._professional_tabs)} 个标签页")

    def _update_tab_with_performance_manager(self, tab, data, progressive=False):
        """更新标签页数据（兼容性方法）"""
        try:
            if hasattr(tab, 'set_kdata'):
                if progressive and hasattr(tab, 'append_kdata'):
                    tab.append_kdata(data)
                else:
                    tab.set_kdata(data)
            logger.debug(f"标签页数据更新完成: {type(tab).__name__}")
        except Exception as e:
            logger.error(f"标签页数据更新失败: {type(tab).__name__}, 错误: {e}")

    def _show_performance_monitor(self):
        """显示性能监控窗口"""
        try:
            from gui.widgets.modern_performance_widget import show_modern_performance_monitor
            self._performance_monitor = show_modern_performance_monitor(self)
            if self._performance_monitor:
                logger.info("性能监控窗口已打开")
            else:
                logger.error("无法打开性能监控窗口")

        except Exception as e:
            logger.error(f"显示性能监控窗口失败: {e}")

    def _initialize_data(self) -> None:
        """初始化数据"""
        # 初始状态下显示提示信息
        self._update_status("请在左侧选择一只股票以开始分析")

    @pyqtSlot(UIDataReadyEvent)
    def _on_ui_data_ready(self, event: UIDataReadyEvent) -> None:
        """处理UI数据就绪事件，使用性能管理器优化加载"""
        try:
            logger.info(f"RightPanel收到UIDataReadyEvent，股票: {event.stock_code}")

            # 检查是否是新股票
            is_new_stock = self._current_stock_code != event.stock_code

            # 更新股票信息
            self._current_stock_code = event.stock_code
            self._current_stock_name = event.stock_name
            self.get_widget('stock_label').setText(
                f"{self._current_stock_name} ({self._current_stock_code})")

            # 如果是新股票，重置性能管理器状态和清空旧回测结果
            if is_new_stock:
                logger.info(f"切换到新股票，清空旧回测结果: {event.stock_code}")
                # 清空旧股票的回测结果显示
                self._clear_backtest_results()
                if self._performance_manager:
                    self._performance_manager.reset_for_new_stock(event.stock_code)

            # 从事件中直接获取分析数据和K线数据
            analysis_data = event.ui_data.get('analysis')
            kline_data = event.ui_data.get('kline_data')

            # 使用性能管理器更新专业标签页
            if kline_data is not None and not kline_data.empty and self._performance_manager:
                logger.info(f"使用性能管理器更新专业标签页，数据长度: {len(kline_data)}")
                self._update_professional_tabs_with_performance_manager(kline_data)
            elif kline_data is not None and not kline_data.empty:
                # 回退到原有机制（如果性能管理器不可用）
                logger.warning("性能管理器不可用，使用原有更新机制")
                self._async_update_professional_tabs(kline_data)

            # 更新基础功能标签页（只有在组件存在时）
            if self._has_basic_tabs:
                self._update_analysis_display(analysis_data or {})

            # 更新状态为数据加载完成
            self._update_status(f"已加载 {self._current_stock_name} 数据，分析完成")

            logger.info(f"RightPanel已成功更新 {event.stock_code} 的分析数据")

        except Exception as e:
            logger.error(f"处理UIDataReadyEvent失败: {e}")
            logger.error(traceback.format_exc())

    def _update_professional_tabs_with_performance_manager(self, kline_data):
        """优化2：使用性能管理器更新专业标签页（懒加载机制）"""
        try:
            tab_widget = self.get_widget('tab_widget')
            if not tab_widget:
                logger.warning("标签页组件不存在，跳过更新")
                return

            # 获取当前激活的标签页索引
            current_index = tab_widget.currentIndex()
            logger.info(f"当前激活标签页索引: {current_index}/{len(self._professional_tabs)}")

            # 为每个标签页更新数据或标记为待更新
            for i, tab in enumerate(self._professional_tabs):
                # 获取标签页类型
                tab_type = type(tab).__name__.lower().replace('tab', '').replace('analysis', '')

                # 检查标签页是否跳过K线数据
                if hasattr(tab, 'skip_kdata') and getattr(tab, 'skip_kdata') is True:
                    logger.debug(f"跳过标签页（skip_kdata=True）: {tab_type}")
                    continue

                # 懒加载：只更新当前激活的标签页
                if i == current_index:
                    logger.info(f"立即更新当前激活标签页: {tab_type} (索引{i})")
                    # 使用性能管理器更新数据
                    self._performance_manager.update_tab_data(
                        stock_code=self._current_stock_code,
                        tab_id=tab_type,
                        tab_widget=tab,  # 传递tab组件本身
                        data=kline_data,
                        use_cache=True
                    )
                    # 记录已更新
                    self._tab_stock_code[i] = self._current_stock_code
                else:
                    # 标记为待更新
                    logger.debug(f"标记标签页为待更新: {tab_type} (索引{i})")
                    self._pending_tab_updates[i] = kline_data
                    # 清除旧的股票代码标记
                    if i in self._tab_stock_code:
                        del self._tab_stock_code[i]

            logger.info(f"✓ 懒加载完成：立即更新1个标签页，待更新{len(self._pending_tab_updates)}个")

        except Exception as e:
            logger.error(f"✗ 性能管理器更新标签页失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 回退到原有机制
            self._async_update_professional_tabs(kline_data)

    def _on_tab_changed(self, index: int):
        """优化2：标签页切换处理器（懒加载触发）"""
        try:
            # logger.info(f"标签页切换到索引: {index}")

            # 检查是否有待更新的数据
            if index in self._pending_tab_updates:
                kline_data = self._pending_tab_updates.pop(index)
                logger.info(f"加载待更新标签页数据（索引{index}）")

                # 获取对应的标签页
                if index < len(self._professional_tabs):
                    tab = self._professional_tabs[index]
                    tab_type = type(tab).__name__.lower().replace('tab', '').replace('analysis', '')

                    # 使用性能管理器更新数据
                    if self._performance_manager:
                        self._performance_manager.update_tab_data(
                            stock_code=self._current_stock_code,
                            tab_id=tab_type,
                            tab_widget=tab,
                            data=kline_data,
                            use_cache=True
                        )
                        # 记录已更新
                        self._tab_stock_code[index] = self._current_stock_code
                        logger.info(f"✓ 懒加载完成：{tab_type}")
                    else:
                        logger.warning("性能管理器不可用，跳过更新")
                else:
                    logger.warning(f"标签页索引{index}超出范围（总数{len(self._professional_tabs)}）")
            else:
                # 检查是否需要刷新（股票已变更）
                if index in self._tab_stock_code and self._tab_stock_code[index] != self._current_stock_code:
                    logger.debug(f"标签页{index}的股票已变更，但数据已在待更新队列中")

        except Exception as e:
            logger.error(f"标签页切换处理失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _async_update_professional_tabs(self, kline_data):
        """性能优化：并行更新专业标签页，避免阻塞UI线程"""
        try:
            from PyQt5.QtCore import QTimer
            from concurrent.futures import ThreadPoolExecutor

            # 性能优化：使用线程池并行更新标签页
            if not hasattr(self, '_tab_update_executor'):
                self._tab_update_executor = ThreadPoolExecutor(max_workers=min(3, len(self._professional_tabs)))

            # 创建一个队列来管理标签页更新
            self._tab_update_queue = list(self._professional_tabs)
            self._current_kline_data = kline_data

            # 使用定时器批量处理标签页更新
            if not hasattr(self, '_tab_update_timer'):
                self._tab_update_timer = QTimer()
                self._tab_update_timer.setSingleShot(True)
                self._tab_update_timer.timeout.connect(self._process_next_tab_update)

            # 延迟开始处理，确保UI渲染完成
            self._tab_update_timer.start(100)  # 100ms后开始处理

        except Exception as e:
            logger.error(f"异步更新专业标签页失败: {e}")
            # 如果异步更新失败，回退到同步更新
            self._sync_update_professional_tabs(kline_data)

    def _process_next_tab_update(self):
        """性能优化：并行处理多个标签页更新"""
        try:
            if not hasattr(self, '_tab_update_queue') or not self._tab_update_queue:
                logger.debug("所有专业标签页数据更新完成")
                return

            # 性能优化：并行处理多个标签页（最多3个）
            tabs_to_update = []
            for _ in range(min(3, len(self._tab_update_queue))):
                if self._tab_update_queue:
                    tabs_to_update.append(self._tab_update_queue.pop(0))

            if not tabs_to_update:
                return

            # 使用线程池并行更新
            if hasattr(self, '_tab_update_executor'):
                futures = []
                for tab in tabs_to_update:
                    if hasattr(tab, 'skip_kdata') and getattr(tab, 'skip_kdata') is True:
                        logger.debug(f"跳过向{type(tab).__name__}传递K线数据（skip_kdata=True）")
                        continue

                    # 提交更新任务到线程池
                    future = self._tab_update_executor.submit(self._update_single_tab, tab)
                    futures.append(future)

                # 等待所有更新完成（可选，也可以不等待）
                # for future in futures:
                #     try:
                #         future.result(timeout=5)  # 5秒超时
                #     except Exception as e:
                #         logger.error(f"标签页更新失败: {e}")
            else:
                # 回退到串行更新
                for tab in tabs_to_update:
                    self._update_single_tab(tab)

            # 如果还有更多标签页需要处理，调度下一次更新
            if self._tab_update_queue:
                self._tab_update_timer.start(50)  # 优化：减少间隔到50ms，提升并行度

        except Exception as e:
            logger.error(f"处理标签页更新失败: {e}")

    def _update_single_tab(self, tab):
        """更新单个标签页的数据（线程安全）"""
        try:
            if hasattr(tab, 'set_kdata'):
                tab.set_kdata(self._current_kline_data)
                # 如果是形态分析标签页，确保数据正确设置
                if hasattr(tab, 'kdata'):
                    tab.kdata = self._current_kline_data
                logger.debug(f"K线数据已传递到{type(tab).__name__}")
        except Exception as e:
            logger.error(f"传递K线数据到{type(tab).__name__}失败: {e}")

    def _sync_update_professional_tabs(self, kline_data):
        """同步更新专业标签页（作为异步更新的备用方案）"""
        try:
            # 传递到所有专业标签页
            for tab in self._professional_tabs:
                if hasattr(tab, 'set_kdata'):
                    try:
                        tab.set_kdata(kline_data)
                        # 如果是形态分析标签页，确保数据正确设置
                        if hasattr(tab, 'kdata'):
                            tab.kdata = kline_data
                        logger.debug(f"K线数据已传递到{type(tab).__name__}")
                    except Exception as e:
                        logger.error(f"传递K线数据到{type(tab).__name__}失败: {e}")
        except Exception as e:
            logger.error(f"同步更新专业标签页失败: {e}")

    def _on_analysis_complete(self, event: AnalysisCompleteEvent) -> None:
        """处理分析完成事件，特别是回测结果"""
        try:
            logger.info(f"收到分析完成事件: {event.stock_code}, 类型: {event.analysis_type}")
            
            # 如果是回测结果，更新回测显示
            if event.analysis_type == "backtest" and event.results and "backtest" in event.results:
                self._update_backtest_results_safe(event.results["backtest"])
                # 刷新回测结果列表
                self._refresh_results_table()
            
        except Exception as e:
            logger.error(f"处理分析完成事件失败: {e}")
            logger.error(traceback.format_exc())
    
    def _update_analysis_display(self, analysis_data: Dict[str, Any]) -> None:
        """更新分析数据显示"""
        try:
            # 更新信号分析（安全检查）
            if 'signals' in analysis_data:
                self._update_signal_analysis_safe(analysis_data['signals'])

            # 更新风险评估（安全检查）
            if 'risk' in analysis_data:
                self._update_risk_analysis_safe(analysis_data['risk'])

            # 更新回测结果（安全检查）
            if 'backtest' in analysis_data:
                self._update_backtest_results_safe(analysis_data['backtest'])
            else:
                # 从回测结果管理器获取最新回测结果
                latest_result = self._backtest_result_manager.get_latest_result(self._current_stock_code)
                if latest_result:
                    backtest_data = {
                        "is_professional": latest_result.is_professional,
                        "results": latest_result.backtest_results,
                        "trades": latest_result.trades
                    }
                    self._update_backtest_results_safe(backtest_data)

        except Exception as e:
            logger.error(f"更新分析数据显示失败: {e}")
            logger.error(traceback.format_exc())

    def _update_signal_analysis_safe(self, signal_data: Dict[str, Any]) -> None:
        """安全更新信号分析"""
        try:
            # 更新当前信号状态
            signal_status_label = self.get_widget('signal_status_label')
            if signal_status_label:
                current_signal = signal_data.get('current', {})
                if current_signal:
                    signal_type = current_signal.get('type', 'unknown')
                    signal_strength = current_signal.get('strength', 0)
                    signal_status_label.setText(
                        f"{signal_type.upper()}\n强度: {signal_strength}")

                    # 设置信号颜色
                    if signal_type == 'buy':
                        signal_status_label.setStyleSheet(
                            "font-size: 18px; font-weight: bold; color: #28a745; padding: 20px;")
                    elif signal_type == 'sell':
                        signal_status_label.setStyleSheet(
                            "font-size: 18px; font-weight: bold; color: #dc3545; padding: 20px;")
                    else:
                        signal_status_label.setStyleSheet(
                            "font-size: 18px; font-weight: bold; color: #6c757d; padding: 20px;")
                else:
                    signal_status_label.setText("暂无信号")

            # 更新信号历史表格
            signal_table = self.get_widget('signal_table')
            if signal_table:
                signal_table.setRowCount(0)

                signals = signal_data.get('history', [])
                for signal in signals[-10:]:  # 只显示最近10个信号
                    row = signal_table.rowCount()
                    signal_table.insertRow(row)
                    signal_table.setItem(row, 0, QTableWidgetItem(signal.get('time', '')))
                    signal_table.setItem(row, 1, QTableWidgetItem(signal.get('type', '')))
                    signal_table.setItem(row, 2, QTableWidgetItem(str(signal.get('price', ''))))
                    signal_table.setItem(row, 3, QTableWidgetItem(str(signal.get('strength', ''))))
                    signal_table.setItem(row, 4, QTableWidgetItem(
                        f"{signal.get('return', 0):.2f}%"))

            # 更新信号统计
            signal_stats_text = self.get_widget('signal_stats_text')
            if signal_stats_text:
                stats = signal_data.get('statistics', {})
                stats_text = f"""
信号总数: {stats.get('total_signals', 0)}
买入信号: {stats.get('buy_signals', 0)}
卖出信号: {stats.get('sell_signals', 0)}
胜率: {stats.get('win_rate', 0):.1f}%
平均收益: {stats.get('avg_return', 0):.2f}%
                """.strip()
                signal_stats_text.setPlainText(stats_text)

        except Exception as e:
            logger.error(f"Failed to update signal analysis: {e}")

    def _update_risk_analysis_safe(self, risk_data: Dict[str, Any]) -> None:
        """安全更新风险评估"""
        try:
            # 更新风险等级
            risk_level_label = self.get_widget('risk_level_label')
            if risk_level_label:
                risk_level = risk_data.get('level', 'unknown')
                risk_score = risk_data.get('score', 0)

                risk_level_label.setText(
                    f"{risk_level.upper()}\n风险评分: {risk_score}")

                # 设置风险等级颜色
                if risk_level == 'low':
                    risk_level_label.setStyleSheet(
                        "font-size: 18px; font-weight: bold; color: #28a745; padding: 15px;")
                elif risk_level == 'medium':
                    risk_level_label.setStyleSheet(
                        "font-size: 18px; font-weight: bold; color: #ffc107; padding: 15px;")
                elif risk_level == 'high':
                    risk_level_label.setStyleSheet(
                        "font-size: 18px; font-weight: bold; color: #dc3545; padding: 15px;")
                else:
                    risk_level_label.setStyleSheet(
                        "font-size: 18px; font-weight: bold; color: #6c757d; padding: 15px;")

            # 更新风险指标表格
            risk_table = self.get_widget('risk_table')
            if risk_table:
                risk_table.setRowCount(0)

                metrics = risk_data.get('metrics', {})
                for metric_name, metric_value in metrics.items():
                    row = risk_table.rowCount()
                    risk_table.insertRow(row)
                    risk_table.setItem(row, 0, QTableWidgetItem(metric_name))
                    risk_table.setItem(row, 1, QTableWidgetItem(str(metric_value)))

            # 更新风险建议
            risk_advice_text = self.get_widget('risk_advice_text')
            if risk_advice_text:
                advice = risk_data.get('advice', '暂无风险建议')
                risk_advice_text.setPlainText(advice)

        except Exception as e:
            logger.error(f"Failed to update risk analysis: {e}")

    def _clear_backtest_results(self) -> None:
        """清空回测结果显示"""
        try:
            logger.info("清空回测结果显示")
            
            # 清空回测结果表格
            backtest_table = self.get_widget('backtest_table')
            if backtest_table:
                backtest_table.setRowCount(0)
            
            # 清空交易记录表格
            trade_table = self.get_widget('trade_table')
            if trade_table:
                trade_table.setRowCount(0)
            
        except Exception as e:
            logger.error(f"清空回测结果失败: {e}")
            logger.error(traceback.format_exc())
    
    def _update_backtest_results_safe(self, backtest_data: Dict[str, Any]) -> None:
        """安全更新回测结果"""
        try:
            # 判断是否为专业回测结果格式
            is_professional = backtest_data.get('is_professional', False)
            
            # 更新回测结果表格
            backtest_table = self.get_widget('backtest_table')
            if backtest_table:
                backtest_table.setRowCount(0)

                if is_professional:
                    # 专业回测结果 - 按类别分组显示
                    self._populate_professional_backtest_table(backtest_table, backtest_data)
                else:
                    # 传统回测结果 - 直接显示所有指标
                    results = backtest_data.get('results', {})
                    for metric_name, metric_value in results.items():
                        row = backtest_table.rowCount()
                        backtest_table.insertRow(row)
                        backtest_table.setItem(row, 0, QTableWidgetItem(metric_name))
                        backtest_table.setItem(row, 1, QTableWidgetItem(str(metric_value)))

            # 更新交易记录表格
            trade_table = self.get_widget('trade_table')
            if trade_table:
                trade_table.setRowCount(0)

                trades = backtest_data.get('trades', [])
                for trade in trades[-20:]:  # 只显示最近20笔交易
                    row = trade_table.rowCount()
                    trade_table.insertRow(row)
                    trade_table.setItem(
                        row, 0, QTableWidgetItem(trade.get('date', '')))
                    trade_table.setItem(
                        row, 1, QTableWidgetItem(trade.get('action', '')))
                    trade_table.setItem(row, 2, QTableWidgetItem(
                        str(trade.get('price', ''))))
                    trade_table.setItem(row, 3, QTableWidgetItem(
                        str(trade.get('quantity', ''))))

                    profit = trade.get('profit', 0)
                    profit_item = QTableWidgetItem(f"{profit:.2f}")
                    if profit > 0:
                        profit_item.setBackground(QColor('#d4edda'))
                    elif profit < 0:
                        profit_item.setBackground(QColor('#f8d7da'))
                    trade_table.setItem(row, 4, profit_item)

        except Exception as e:
            logger.error(f"Failed to update backtest results: {e}")

    def _populate_professional_backtest_table(self, table: QTableWidget, backtest_data: Dict[str, Any]) -> None:
        """填充专业回测结果表格"""
        try:
            # 基础信息
            basic_info = backtest_data.get('basic_info', {})
            if basic_info:
                # 添加分组标题
                self._add_table_section(table, "📊 回测信息")
                self._add_table_row(table, "回测引擎", basic_info.get('engine', 'N/A'))
                self._add_table_row(table, "计算时间", basic_info.get('timestamp', 'N/A'))
                self._add_table_row(table, "回测期间", basic_info.get('period_days', 0))
                
                # 收益指标
                returns = backtest_data.get('returns', {})
                self._add_table_section(table, "📈 收益指标")
                self._add_table_row(table, "总收益率", f"{returns.get('total_return', 0):.2%}")
                self._add_table_row(table, "年化收益率", f"{returns.get('annualized_return', 0):.2%}")

                # 风险指标
                risks = backtest_data.get('risks', {})
                self._add_table_section(table, "📉 风险指标")
                self._add_table_row(table, "波动率", f"{risks.get('volatility', 0):.2%}")
                self._add_table_row(table, "最大回撤", f"{risks.get('max_drawdown', 0):.2%}")

                # 风险调整收益
                risk_adjusted = backtest_data.get('risk_adjusted', {})
                self._add_table_section(table, "🎯 风险调整收益")
                self._add_table_row(table, "夏普比率", f"{risk_adjusted.get('sharpe_ratio', 0):.3f}")
                self._add_table_row(table, "Sortino比率", f"{risk_adjusted.get('sortino_ratio', 0):.3f}")
                self._add_table_row(table, "Calmar比率", f"{risk_adjusted.get('calmar_ratio', 0):.3f}")

                # 交易统计
                trading = backtest_data.get('trading_stats', {})
                self._add_table_section(table, "📊 交易统计")
                self._add_table_row(table, "总交易次数", trading.get('total_trades', 0))
                self._add_table_row(table, "胜率", f"{trading.get('win_rate', 0):.1%}")
                self._add_table_row(table, "盈亏比", f"{trading.get('profit_factor', 0):.2f}:1")

                # Alpha/Beta
                benchmark = backtest_data.get('benchmark', {})
                self._add_table_section(table, "🎯 基准表现")
                self._add_table_row(table, "Alpha", f"{benchmark.get('alpha', 0):.3f}")
                self._add_table_row(table, "Beta", f"{benchmark.get('beta', 1.0):.3f}")
                
        except Exception as e:
            logger.error(f"填充专业回测表格失败: {e}")
            # 降级到简单显示
            results = backtest_data.get('results', {})
            for metric_name, metric_value in results.items():
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(metric_name))
                table.setItem(row, 1, QTableWidgetItem(str(metric_value)))

    def _add_table_section(self, table: QTableWidget, section_title: str) -> None:
        """在表格中添加分组标题"""
        row = table.rowCount()
        table.insertRow(row)
        section_item = QTableWidgetItem(section_title)
        section_item.setBackground(QColor('#e9ecef'))
        section_item.setFont(QFont("Arial", 9, QFont.Bold))
        table.setItem(row, 0, section_item)
        # 合并单元格
        table.setSpan(row, 0, 1, 2)

    def _add_table_row(self, table: QTableWidget, name: str, value: str) -> None:
        """在表格中添加数据行"""
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(name))
        table.setItem(row, 1, QTableWidgetItem(value))

    def _update_status(self, message: str) -> None:
        """更新状态"""
        status_label = self.get_widget('status_label')
        if status_label:
            status_label.setText(message)

    def _refresh_analysis(self) -> None:
        """刷新分析数据"""
        if not self._current_stock_code:
            self._update_status("请在左侧选择一只股票以开始分析")
            return

        # 更新状态显示正在刷新
        self._update_status(f"正在刷新 {self._current_stock_name} 的分析数据...")

        try:
            # 发布事件请求重新加载数据
            from core.events import StockSelectedEvent

            if self.coordinator and hasattr(self.coordinator, 'event_bus'):
                self.coordinator.event_bus.publish(StockSelectedEvent(
                    stock_code=self._current_stock_code,
                    stock_name=self._current_stock_name
                ))
                logger.info(f"请求刷新 {self._current_stock_code} 的数据...")
            else:
                self._update_status("无法刷新数据：缺少事件总线")

        except Exception as e:
            logger.error(f"刷新分析数据失败: {e}")
            self._update_status("刷新失败")

    def _export_report(self) -> None:
        """导出分析报告"""
        if not self._current_stock_code:
            self._update_status("请先选择股票再导出报告")
            return

        self._update_status("报告导出功能开发中...")
        # TODO: 实现报告导出功能

    def get_current_stock_info(self) -> Dict[str, str]:
        """获取当前股票信息"""
        return {
            'code': self._current_stock_code,
            'name': self._current_stock_name
        }

    def _on_indicator_calculated(self, indicator_type: str, indicator_results: dict):
        """
        处理指标计算完成信号，更新主图显示指标

        Args:
            indicator_type: 指标类型（"batch"或具体指标名）
            indicator_results: 指标计算结果字典
        """
        try:
            logger.info(f"🎯 收到指标计算完成信号: type={indicator_type}, results包含{len(indicator_results)}个指标")

            # 获取中间面板和图表组件
            if not self.coordinator:
                logger.warning("coordinator不存在，无法更新主图")
                return

            # 获取main_window
            main_window = self.coordinator._main_window if hasattr(self.coordinator, "_main_window") else None
            if not main_window:
                logger.warning("main_window不存在，无法更新主图")
                return

            # 查找中间面板
            middle_panel = None
            for panel_name, panel in self.coordinator._panels.items():
                if "middle" in panel_name.lower() or "chart" in panel_name.lower():
                    middle_panel = panel
                    break

            if not middle_panel:
                logger.warning("未找到中间面板，无法更新主图")
                return

            # 获取chart_widget
            chart_widget = None
            if hasattr(middle_panel, "chart_canvas"):
                # chart_canvas是一个容器，内部包含真正的chart_widget
                chart_canvas = middle_panel.chart_canvas
                if hasattr(chart_canvas, 'chart_widget'):
                    chart_widget = chart_canvas.chart_widget
                else:
                    chart_widget = chart_canvas
            elif hasattr(middle_panel, "get_widget"):
                # 通过get_widget获取chart_canvas
                chart_canvas = middle_panel.get_widget("chart_canvas")
                if chart_canvas and hasattr(chart_canvas, 'chart_widget'):
                    chart_widget = chart_canvas.chart_widget
                else:
                    chart_widget = chart_canvas

            if not chart_widget:
                logger.warning("未找到chart_widget，无法更新主图")
                return

            # 获取当前K线数据
            if not hasattr(chart_widget, "current_kdata") or chart_widget.current_kdata is None or chart_widget.current_kdata.empty:
                logger.warning("chart_widget没有可用的K线数据，无法更新")
                return

            logger.info(f"准备更新主图，K线数据长度: {len(chart_widget.current_kdata)}")

            # 定义内置指标列表
            builtin_indicators = {
                'MA', 'MACD', 'RSI', 'BOLL', 'KDJ', 'CCI', 'OBV'
            }

            # 更新active_indicators（将计算结果转换为指标列表，并根据名称智能判断group）
            active_indicators = []
            for i, indicator_name in enumerate(indicator_results.keys()):
                if not indicator_name:
                    logger.warning(f"跳过无效指标名称: {indicator_name}")
                    continue
                
                # 根据指标名称判断group：builtin或talib
                # 判断指标分组：内置、talib 或自定义（中文名）
                if indicator_name in builtin_indicators:
                    group = 'builtin'
                elif any('\u4e00' <= ch <= '\u9fff' for ch in indicator_name):  # 含中文字符即为自定义
                    group = 'custom'
                else:
                    group = 'talib'
                
                indicator_entry = {
                    "name": indicator_name,
                    "params": {},  # 参数已包含在计算结果中
                    "group": group
                }
                
                # 验证指标条目
                if isinstance(indicator_entry, dict) and indicator_entry.get('name'):
                    active_indicators.append(indicator_entry)
                else:
                    logger.warning(f"移除无效指标 #{i}: {indicator_entry}")

            # 验证active_indicators列表
            validated_indicators = []
            for i, ind in enumerate(active_indicators):
                if ind is not None and isinstance(ind, dict) and ind.get('name'):
                    validated_indicators.append(ind)
                else:
                    logger.warning(f"移除无效指标 #{i}: {ind}")
            
            chart_widget.active_indicators = validated_indicators
            logger.info(f"设置active_indicators: {[ind['name'] for ind in active_indicators]}")
            logger.info(f"指标分组信息: {[(ind['name'], ind['group']) for ind in active_indicators]}")

            # 调用update_chart更新图表，传递指标数据
            chart_widget.update_chart({
                "kdata": chart_widget.current_kdata,
                "indicators_data": indicator_results
            })
            logger.info(f"主图更新完成")

        except Exception as e:
            logger.error(f"处理指标计算完成信号失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _on_ai_select_stocks(self) -> None:
        """处理AI选股按钮点击事件"""
        try:
            logger.info("AI选股按钮被点击")
            
            # 获取用户输入
            condition_text = self.get_widget('ai_condition_text')
            if not condition_text:
                logger.warning("AI选股条件输入框未找到")
                QMessageBox.warning(self, "警告", "AI选股条件输入框未找到")
                return
            
            user_input = condition_text.toPlainText().strip()
            if not user_input:
                QMessageBox.warning(self, "警告", "请输入选股需求")
                return
            
            type_combo = self.get_widget('ai_type_combo')
            if not type_combo:
                logger.warning("AI选股类型选择框未找到")
                QMessageBox.warning(self, "警告", "AI选股类型选择框未找到")
                return
            
            strategy_type = type_combo.currentText()
            
            risk_combo = self.get_widget('ai_risk_combo')
            if not risk_combo:
                logger.warning("AI选股风险偏好选择框未找到")
                QMessageBox.warning(self, "警告", "AI选股风险偏好选择框未找到")
                return
            
            risk_level = risk_combo.currentText()
            
            # 获取服务容器
            from core.containers import get_service_container
            container = get_service_container()
            if not container:
                logger.warning("服务容器不可用")
                QMessageBox.warning(self, "警告", "服务容器不可用")
                return
            
            # 获取AI选股集成服务
            try:
                from core.services.ai_selection_integration_service import (
                    AISelectionIntegrationService,
                    StockSelectionCriteria,
                    SelectionStrategy,
                    RiskLevel
                )
            except ImportError as e:
                logger.error(f"无法导入AI选股集成服务: {e}")
                QMessageBox.critical(self, "错误", f"AI选股服务不可用: {str(e)}")
                return
            
            if not container.is_registered(AISelectionIntegrationService):
                logger.warning("AI选股集成服务未注册")
                QMessageBox.warning(self, "警告", "AI选股服务未注册")
                return
            
            ai_selection_service = container.resolve(AISelectionIntegrationService)
            
            # 显示进度提示
            result_table = self.get_widget('ai_result_table')
            if result_table:
                result_table.setRowCount(0)
            
            # 执行选股
            logger.info(f"开始AI选股: strategy={strategy_type}, risk={risk_level}, input={user_input}")
            
            # 使用异步方式执行选股
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 判断是否使用自然语言解析
                use_nlp = self._should_use_nlp(user_input)
                
                if use_nlp:
                    # 使用自然语言解析
                    logger.info("使用自然语言解析模式")
                    
                    # 映射策略类型
                    strategy_map = {
                        "价值投资": SelectionStrategy.VALUE_BASED,
                        "成长投资": SelectionStrategy.GROWTH_BASED,
                        "趋势跟踪": SelectionStrategy.MOMENTUM_BASED,
                        "均值回归": SelectionStrategy.QUALITY_BASED,
                        "动量策略": SelectionStrategy.MOMENTUM_BASED,
                        "技术分析": SelectionStrategy.TECH_ANALYSIS,
                        "基本面分析": SelectionStrategy.QUALITY_BASED,
                        "量化选股": SelectionStrategy.QUANTITATIVE
                    }
                    
                    selection_strategy = strategy_map.get(strategy_type, SelectionStrategy.QUANTITATIVE)
                    
                    result = loop.run_until_complete(
                        ai_selection_service.select_stocks_with_nlp(
                            user_input=user_input,
                            strategy_type=selection_strategy
                        )
                    )
                else:
                    # 使用传统选股模式
                    logger.info("使用传统选股模式")
                    
                    # 转换UI输入为选股标准
                    criteria = self._convert_ui_to_criteria(user_input, strategy_type, risk_level)
                    
                    result = loop.run_until_complete(
                        ai_selection_service.select_stocks_with_explanation(
                            strategy_id=strategy_type,
                            criteria=criteria
                        )
                    )
                
                # 显示结果
                self._display_ai_selection_results(result)
                
                logger.info(f"AI选股完成: 选中{len(result.selected_stocks)}只股票")
                QMessageBox.information(
                    self,
                    "AI选股完成",
                    f"成功选中 {len(result.selected_stocks)} 只股票"
                )
                
            except Exception as e:
                logger.error(f"AI选股失败: {e}")
                logger.error(traceback.format_exc())
                QMessageBox.critical(self, "错误", f"AI选股失败: {str(e)}")
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"处理AI选股按钮点击事件失败: {e}")
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "错误", f"AI选股失败: {str(e)}")
    
    def _should_use_nlp(self, user_input: str) -> bool:
        """判断是否应该使用自然语言解析
        
        Args:
            user_input: 用户输入
            
        Returns:
            是否使用自然语言解析
        """
        # 如果输入包含自然语言特征，使用 NLP 解析
        nlp_keywords = [
            "高", "低", "好", "坏", "强", "弱", "大", "小",
            "超过", "低于", "大于", "小于", "优于", "差于",
            "想要", "需要", "希望", "寻找", "推荐",
            "ROE", "PE", "PB", "估值", "成长", "价值",
            "资金流", "动量", "趋势", "技术", "基本面"
        ]
        
        # 检查是否包含自然语言关键词
        for keyword in nlp_keywords:
            if keyword in user_input:
                return True
        
        # 如果输入长度较长，也使用 NLP 解析
        if len(user_input) > 20:
            return True
        
        return False
    
    def _convert_ui_to_criteria(
        self,
        user_input: str,
        strategy_type: str,
        risk_level: str
    ):
        """将UI输入转换为选股标准
        
        Args:
            user_input: 用户输入的选股需求
            strategy_type: 选股类型
            risk_level: 风险偏好
            
        Returns:
            StockSelectionCriteria 对象
        """
        from core.services.ai_selection_integration_service import (
            StockSelectionCriteria,
            SelectionStrategy,
            RiskLevel
        )
        
        # 映射策略类型
        strategy_map = {
            "价值投资": SelectionStrategy.VALUE_BASED,
            "成长投资": SelectionStrategy.GROWTH_BASED,
            "趋势跟踪": SelectionStrategy.MOMENTUM_BASED,
            "均值回归": SelectionStrategy.QUALITY_BASED,
            "动量策略": SelectionStrategy.MOMENTUM_BASED,
            "技术分析": SelectionStrategy.TECH_ANALYSIS,
            "基本面分析": SelectionStrategy.QUALITY_BASED,
            "量化选股": SelectionStrategy.QUANTITATIVE
        }
        
        # 映射风险等级
        risk_map = {
            "保守": RiskLevel.CONSERVATIVE,
            "稳健": RiskLevel.MODERATE,
            "积极": RiskLevel.AGGRESSIVE,
            "激进": RiskLevel.AGGRESSIVE
        }
        
        return StockSelectionCriteria(
            strategy_type=strategy_map.get(strategy_type, SelectionStrategy.QUANTITATIVE),
            risk_level=risk_map.get(risk_level, RiskLevel.MODERATE)
        )
    
    def _display_ai_selection_results(self, result) -> None:
        """显示AI选股结果
        
        Args:
            result: StockSelectionResult 对象
        """
        try:
            result_table = self.get_widget('ai_result_table')
            if not result_table:
                logger.warning("AI选股结果表格未找到")
                return
            
            # 清空表格
            result_table.setRowCount(0)
            
            # 填充结果
            selected_stocks = result.selected_stocks
            explanations = result.explanations
            
            for i, stock_code in enumerate(selected_stocks):
                # 查找对应的解释
                explanation = None
                for exp in explanations:
                    if exp.stock_code == stock_code:
                        explanation = exp
                        break
                
                if explanation:
                    # 股票代码
                    result_table.setItem(i, 0, QTableWidgetItem(stock_code))
                    
                    # 股票名称（暂时使用代码，后续可以从数据服务获取）
                    result_table.setItem(i, 1, QTableWidgetItem(stock_code))
                    
                    # 推荐理由
                    reason = explanation.selection_reason if explanation else "无"
                    result_table.setItem(i, 2, QTableWidgetItem(reason))
                    
                    # 评分
                    score = explanation.score if explanation else 0
                    result_table.setItem(i, 3, QTableWidgetItem(f"{score:.2f}"))
                    
                    # 风险等级
                    risk_assessment = explanation.risk_assessment if explanation else {}
                    risk_level = risk_assessment.get('level', '未知')
                    result_table.setItem(i, 4, QTableWidgetItem(risk_level))
                    
                    # 建议仓位
                    recommendation_strength = explanation.recommendation_strength if explanation else 'moderate'
                    position_map = {
                        'strong': '重仓',
                        'moderate': '中仓',
                        'weak': '轻仓'
                    }
                    position = position_map.get(recommendation_strength, '中仓')
                    result_table.setItem(i, 5, QTableWidgetItem(position))
            
            logger.info(f"AI选股结果已显示: {len(selected_stocks)}只股票")
            
        except Exception as e:
            logger.error(f"显示AI选股结果失败: {e}")
            logger.error(traceback.format_exc())
    
    def _on_export_ai_results(self) -> None:
        """处理导出AI选股结果按钮点击事件"""
        try:
            logger.info("导出AI选股结果按钮被点击")
            
            result_table = self.get_widget('ai_result_table')
            if not result_table:
                logger.warning("AI选股结果表格未找到")
                QMessageBox.warning(self, "警告", "AI选股结果表格未找到")
                return
            
            if result_table.rowCount() == 0:
                QMessageBox.warning(self, "警告", "没有可导出的AI选股结果")
                return
            
            # 获取文件保存路径
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存AI选股结果",
                "",
                "Excel Files (*.xlsx);;CSV Files (*.csv);;All Files (*)"
            )
            
            if not file_path:
                logger.info("用户取消了文件保存")
                return
            
            # 导出数据
            import pandas as pd
            data = []
            for row in range(result_table.rowCount()):
                row_data = []
                for col in range(result_table.columnCount()):
                    item = result_table.item(row, col)
                    row_data.append(item.text() if item else "")
                data.append(row_data)
            
            # 创建DataFrame
            df = pd.DataFrame(
                data,
                columns=[
                    '股票代码', '股票名称', '推荐理由', 
                    '评分', '风险等级', '建议仓位'
                ]
            )
            
            # 保存文件
            if file_path.endswith('.xlsx'):
                df.to_excel(file_path, index=False)
            else:
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            
            logger.info(f"AI选股结果已导出到: {file_path}")
            QMessageBox.information(
                self,
                "导出成功",
                f"AI选股结果已导出到:\n{file_path}"
            )
            
        except Exception as e:
            logger.error(f"导出AI选股结果失败: {e}")
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def resizeEvent(self, event):
        """窗口大小改变事件处理"""
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self):
        """更新响应式布局"""
        try:
            window_width = self.width()
            window_height = self.height()

            logger.debug(f"RightPanel 响应式布局更新: {window_width}x{window_height}")

            # 更新收益率范围过滤框宽度
            min_return_filter = self.get_widget('min_return_filter')
            if min_return_filter:
                filter_width = max(60, int(window_width * 0.08))
                min_return_filter.setMinimumWidth(filter_width)
                min_return_filter.setMaximumWidth(int(window_width * 0.12))

            max_return_filter = self.get_widget('max_return_filter')
            if max_return_filter:
                filter_width = max(60, int(window_width * 0.08))
                max_return_filter.setMinimumWidth(filter_width)
                max_return_filter.setMaximumWidth(int(window_width * 0.12))

            # 更新成功率范围过滤框宽度
            min_success_filter = self.get_widget('min_success_filter')
            if min_success_filter:
                filter_width = max(60, int(window_width * 0.08))
                min_success_filter.setMinimumWidth(filter_width)
                min_success_filter.setMaximumWidth(int(window_width * 0.12))

            max_success_filter = self.get_widget('max_success_filter')
            if max_success_filter:
                filter_width = max(60, int(window_width * 0.08))
                max_success_filter.setMinimumWidth(filter_width)
                max_success_filter.setMaximumWidth(int(window_width * 0.12))

        except Exception as e:
            logger.error(f"更新响应式布局失败: {e}")

