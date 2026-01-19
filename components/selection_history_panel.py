"""
选股历史记录面板

提供选股历史记录查看、对比和恢复功能
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from loguru import logger
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import json

from core.containers import get_service_container

# 数据库服务
try:
    from core.services.database_service import DatabaseService
except ImportError:
    DatabaseService = None


class SelectionHistoryPanel(QWidget):
    """选股历史记录面板"""
    
    # 信号定义
    restore_strategy = pyqtSignal(str, dict)  # result_id, criteria
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_service = None
        self.current_page = 1
        self.page_size = 20
        self.total_pages = 1
        self.selected_results = {}  # 选中的历史记录 {result_id: data}
        
        # 初始化服务
        self._init_services()
        
        # 创建UI
        self._create_ui()
        
        # 加载历史记录
        self._load_history()
    
    def _init_services(self):
        """初始化数据库服务"""
        try:
            container = get_service_container()
            if container and DatabaseService:
                self.db_service = container.resolve(DatabaseService)
                logger.info("数据库服务加载成功")
            else:
                logger.warning("数据库服务不可用")
        except Exception as e:
            logger.error(f"数据库服务初始化失败: {e}")
    
    def _create_ui(self):
        """创建UI界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # 筛选区域
        filter_group = QGroupBox("筛选条件")
        filter_layout = QHBoxLayout(filter_group)
        
        # 日期范围
        date_label = QLabel("日期范围:")
        filter_layout.addWidget(date_label)
        
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        filter_layout.addWidget(self.start_date_edit)
        
        to_label = QLabel("至")
        filter_layout.addWidget(to_label)
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        filter_layout.addWidget(self.end_date_edit)
        
        # 策略类型筛选
        strategy_label = QLabel("策略类型:")
        filter_layout.addWidget(strategy_label)
        
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem("全部", "")
        self.strategy_combo.addItem("技术分析", "technical")
        self.strategy_combo.addItem("动量策略", "momentum")
        self.strategy_combo.addItem("价值策略", "value")
        self.strategy_combo.addItem("成长策略", "growth")
        self.strategy_combo.addItem("质量策略", "quality")
        self.strategy_combo.addItem("股息策略", "dividend")
        self.strategy_combo.addItem("量化策略", "quantitative")
        self.strategy_combo.addItem("混合策略", "hybrid")
        filter_layout.addWidget(self.strategy_combo)
        
        # 查询按钮
        query_btn = QPushButton("查询")
        query_btn.clicked.connect(self._on_query_clicked)
        filter_layout.addWidget(query_btn)
        
        # 重置按钮
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._on_reset_clicked)
        filter_layout.addWidget(reset_btn)
        
        filter_layout.addStretch()
        main_layout.addWidget(filter_group)
        
        # 操作区域
        action_group = QGroupBox("操作")
        action_layout = QHBoxLayout(action_group)
        
        # 对比按钮
        self.compare_btn = QPushButton("对比选中记录")
        self.compare_btn.setEnabled(False)
        self.compare_btn.clicked.connect(self._on_compare_clicked)
        action_layout.addWidget(self.compare_btn)
        
        # 恢复按钮
        self.restore_btn = QPushButton("恢复选中策略")
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self._on_restore_clicked)
        action_layout.addWidget(self.restore_btn)
        
        action_layout.addStretch()
        main_layout.addWidget(action_group)
        
        # 历史记录表格
        history_group = QGroupBox("历史记录")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "选股日期", "策略ID", "股票数量", 
            "平均评分", "评分范围", "策略类型", "选择"
        ])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.itemSelectionChanged.connect(self._on_selection_changed)
        history_layout.addWidget(self.history_table)
        
        # 分页控件
        page_layout = QHBoxLayout()
        
        self.prev_page_btn = QPushButton("上一页")
        self.prev_page_btn.clicked.connect(self.prev_page)
        self.prev_page_btn.setEnabled(False)
        page_layout.addWidget(self.prev_page_btn)
        
        self.page_label = QLabel("第 1 页 / 共 1 页")
        self.page_label.setAlignment(Qt.AlignCenter)
        page_layout.addWidget(self.page_label)
        
        self.next_page_btn = QPushButton("下一页")
        self.next_page_btn.clicked.connect(self.next_page)
        self.next_page_btn.setEnabled(False)
        page_layout.addWidget(self.next_page_btn)
        
        page_layout.addStretch()
        history_layout.addLayout(page_layout)
        
        main_layout.addWidget(history_group)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)
    
    def _load_history(self, page: int = 1):
        """加载历史记录"""
        if not self.db_service:
            QMessageBox.warning(self, "错误", "数据库服务不可用")
            return
        
        try:
            # 获取历史记录
            result = self.db_service.get_all_selection_results(
                page=page,
                page_size=self.page_size
            )
            
            self.current_page = result['page']
            self.total_pages = result['total_pages']
            
            # 更新表格
            self._update_history_table(result['data'])
            
            # 更新分页控件
            self._update_page_controls()
            
            # 更新状态
            self.status_label.setText(
                f"共 {result['total']} 条记录，当前第 {page} 页"
            )
            
        except Exception as e:
            logger.error(f"加载历史记录失败: {e}")
            QMessageBox.critical(self, "错误", f"加载历史记录失败: {e}")
    
    def _update_history_table(self, data: List[Dict[str, Any]]):
        """更新历史记录表格"""
        self.history_table.setRowCount(0)
        
        for row_data in data:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            
            # 选股日期
            selection_date = row_data.get('selection_date', '')
            date_item = QTableWidgetItem(str(selection_date) if selection_date else '')
            self.history_table.setItem(row, 0, date_item)
            
            # 策略ID（显示前8位）
            strategy_id = row_data.get('strategy_id', '')
            strategy_item = QTableWidgetItem(strategy_id[:8] + "..." if len(strategy_id) > 8 else strategy_id)
            strategy_item.setToolTip(strategy_id)
            self.history_table.setItem(row, 1, strategy_item)
            
            # 股票数量
            count_item = QTableWidgetItem(str(row_data.get('stock_count', 0)))
            self.history_table.setItem(row, 2, count_item)
            
            # 平均评分
            avg_score = row_data.get('avg_score', 0)
            score_item = QTableWidgetItem(f"{avg_score:.2f}")
            self.history_table.setItem(row, 3, score_item)
            
            # 评分范围
            min_score = row_data.get('min_score', 0)
            max_score = row_data.get('max_score', 0)
            range_item = QTableWidgetItem(f"{min_score:.2f} - {max_score:.2f}")
            self.history_table.setItem(row, 4, range_item)
            
            # 策略类型（从策略ID推断）
            strategy_type = self._infer_strategy_type(strategy_id)
            type_item = QTableWidgetItem(strategy_type)
            self.history_table.setItem(row, 5, type_item)
            
            # 选择复选框
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox.setCheckState(Qt.Unchecked)
            checkbox.setData(Qt.UserRole, row_data.get('result_id'))
            self.history_table.setItem(row, 6, checkbox)
            
            # 存储完整数据
            self.history_table.item(row, 0).setData(Qt.UserRole, row_data)
    
    def _infer_strategy_type(self, strategy_id: str) -> str:
        """从策略ID推断策略类型"""
        # 这里可以通过查询 ai_strategies 表获取准确的策略类型
        # 暂时返回简化显示
        return "未知"
    
    def _update_page_controls(self):
        """更新分页控件状态"""
        self.page_label.setText(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")
        
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)
    
    def _on_selection_changed(self):
        """表格选择变化事件"""
        selected_items = self.history_table.selectedItems()
        if selected_items:
            # 获取选中的行
            selected_rows = set()
            for item in selected_items:
                selected_rows.add(item.row())
            
            # 获取选中的历史记录
            self.selected_results = {}
            for row in selected_rows:
                checkbox_item = self.history_table.item(row, 6)
                if checkbox_item.checkState() == Qt.Checked:
                    result_id = checkbox_item.data(Qt.UserRole)
                    row_data = self.history_table.item(row, 0).data(Qt.UserRole)
                    self.selected_results[result_id] = row_data
            
            # 启用/禁用按钮
            self.compare_btn.setEnabled(len(self.selected_results) >= 2)
            self.restore_btn.setEnabled(len(self.selected_results) == 1)
        else:
            self.selected_results = {}
            self.compare_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
    
    def _on_query_clicked(self):
        """查询按钮点击事件"""
        if not self.db_service:
            return
        
        try:
            # 获取筛选条件
            start_date = self.start_date_edit.date().toPyDate()
            end_date = self.end_date_edit.date().toPyDate()
            strategy_type = self.strategy_combo.currentData()
            
            # 转换为 datetime
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            # 查询历史记录
            results = self.db_service.get_selection_results_by_date_range(
                start_date=start_datetime,
                end_date=end_datetime,
                limit=self.page_size
            )
            
            # 按result_id分组
            grouped_results = {}
            for result in results:
                result_id = result['id'][:36]
                if result_id not in grouped_results:
                    grouped_results[result_id] = {
                        'result_id': result_id,
                        'strategy_id': result['strategy_id'],
                        'selection_date': result['selection_date'],
                        'stock_count': 0,
                        'avg_score': 0,
                        'min_score': float('inf'),
                        'max_score': 0,
                        'stocks': []
                    }
                
                grouped_results[result_id]['stock_count'] += 1
                grouped_results[result_id]['avg_score'] += result['score']
                grouped_results[result_id]['min_score'] = min(
                    grouped_results[result_id]['min_score'],
                    result['score']
                )
                grouped_results[result_id]['max_score'] = max(
                    grouped_results[result_id]['max_score'],
                    result['score']
                )
                grouped_results[result_id]['stocks'].append(result)
            
            # 计算平均分
            for result_id in grouped_results:
                grouped_results[result_id]['avg_score'] /= grouped_results[result_id]['stock_count']
            
            # 更新表格
            self._update_history_table(list(grouped_results.values()))
            
            # 更新状态
            self.status_label.setText(f"查询到 {len(grouped_results)} 条记录")
            
        except Exception as e:
            logger.error(f"查询失败: {e}")
            QMessageBox.critical(self, "错误", f"查询失败: {e}")
    
    def _on_reset_clicked(self):
        """重置按钮点击事件"""
        # 重置筛选条件
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.end_date_edit.setDate(QDate.currentDate())
        self.strategy_combo.setCurrentIndex(0)
        
        # 重新加载历史记录
        self.current_page = 1
        self._load_history()
    
    def _on_compare_clicked(self):
        """对比按钮点击事件"""
        if len(self.selected_results) < 2:
            QMessageBox.warning(self, "警告", "请至少选择2条记录进行对比")
            return
        
        try:
            # 获取选中的result_id列表
            result_ids = list(self.selected_results.keys())
            
            # 调用对比对话框
            from components.selection_history_comparison import SelectionComparisonDialog
            dialog = SelectionComparisonDialog(result_ids, self)
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"对比失败: {e}")
            QMessageBox.critical(self, "错误", f"对比失败: {e}")
    
    def _on_restore_clicked(self):
        """恢复按钮点击事件"""
        if len(self.selected_results) != 1:
            QMessageBox.warning(self, "警告", "请选择1条记录进行恢复")
            return
        
        try:
            # 获取选中的记录
            result_id = list(self.selected_results.keys())[0]
            result_data = self.selected_results[result_id]
            
            # 获取完整的选股结果
            full_results = self.db_service.get_selection_result_by_result_id(result_id)
            
            if not full_results:
                QMessageBox.warning(self, "警告", "无法获取选股结果详情")
                return
            
            # 提取策略配置
            criteria = full_results[0].get('selection_reason', {}).get('criteria', {})
            
            if not criteria:
                QMessageBox.warning(self, "警告", "无法提取策略配置")
                return
            
            # 确认恢复
            reply = QMessageBox.question(
                self,
                "确认恢复",
                f"是否恢复策略配置？\n\n"
                f"选股日期: {result_data.get('selection_date', '')}\n"
                f"股票数量: {result_data.get('stock_count', 0)}\n"
                f"平均评分: {result_data.get('avg_score', 0):.2f}",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 发送恢复信号
                self.restore_strategy.emit(result_id, criteria)
                QMessageBox.information(self, "成功", "策略配置已恢复")
                
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            QMessageBox.critical(self, "错误", f"恢复失败: {e}")
    
    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self._load_history(self.current_page - 1)
    
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self._load_history(self.current_page + 1)
