#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户管理对话框

提供账户、持仓、资金的管理功能
"""

from loguru import logger
from datetime import datetime
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QFrame,
    QGroupBox, QMessageBox, QHeaderView, QAbstractItemView,
    QMenu, QAction, QSplitter, QDoubleSpinBox, QSpinBox, QWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from core.trading.account_models import (
    Account, Position, FundInfo, AccountQuery, PositionQuery,
    AccountStatus, PositionSide, InstitutionType, TradingInterfaceType
)
from core.trading.account_manager import AccountManager
from core.containers import get_service_container
from core.events import get_event_bus
from core.plugin_types import AssetType


class AccountManagementDialog(QDialog):
    """账户管理对话框"""

    def __init__(self, parent=None):
        """
        初始化账户管理对话框

        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.service_container = get_service_container()
        self.event_bus = get_event_bus()
        self.account_manager = self.service_container.resolve(AccountManager)

        self.accounts: List[Account] = []
        self.positions: List[Position] = []
        self.fund_infos: Dict[str, FundInfo] = {}

        self.init_ui()
        self.subscribe_events()
        self.load_accounts()

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("账户管理")
            self.setMinimumSize(1350, 800)

            layout = QVBoxLayout(self)

            # 创建标签页
            self.tab_widget = QTabWidget()

            # 账户标签页
            self.account_tab = self.create_account_tab()
            self.tab_widget.addTab(self.account_tab, "账户")

            # 持仓标签页
            self.position_tab = self.create_position_tab()
            self.tab_widget.addTab(self.position_tab, "持仓")

            # 资金标签页
            self.fund_tab = self.create_fund_tab()
            self.tab_widget.addTab(self.fund_tab, "资金")

            layout.addWidget(self.tab_widget)

            # 状态栏
            self.status_label = QLabel("就绪")
            self.status_label.setStyleSheet("color: #666; padding: 5px;")
            layout.addWidget(self.status_label)

        except Exception as e:
            logger.error(f"初始化账户管理对话框UI失败: {e}")

    def create_account_tab(self):
        """创建账户标签页"""
        try:
            tab = QWidget()
            layout = QVBoxLayout(tab)

            # 工具栏
            toolbar = QFrame()
            toolbar_layout = QHBoxLayout(toolbar)

            create_btn = QPushButton("创建账户")
            create_btn.clicked.connect(self.show_create_account_dialog)
            toolbar_layout.addWidget(create_btn)

            simnow_btn = QPushButton("快速配置SimNow账户")
            simnow_btn.clicked.connect(self.show_simnow_config_dialog)
            simnow_btn.setStyleSheet("background-color: #4CAF50; color: white;")
            toolbar_layout.addWidget(simnow_btn)

            refresh_btn = QPushButton("刷新")
            refresh_btn.clicked.connect(self.load_accounts)
            toolbar_layout.addWidget(refresh_btn)

            # 实时同步开关
            self.realtime_sync_checkbox = QPushButton("实时同步: 关")
            self.realtime_sync_checkbox.setCheckable(True)
            self.realtime_sync_checkbox.setChecked(False)
            self.realtime_sync_checkbox.clicked.connect(self.toggle_realtime_sync)
            self.realtime_sync_checkbox.setStyleSheet("""
                QPushButton { background-color: #f0f0f0; color: #666; padding: 5px 10px; border-radius: 4px; }
                QPushButton:checked { background-color: #4CAF50; color: white; }
            """)
            toolbar_layout.addWidget(self.realtime_sync_checkbox)

            # 同步间隔
            self.sync_interval_spin = QSpinBox()
            self.sync_interval_spin.setRange(5, 300)
            self.sync_interval_spin.setValue(30)
            self.sync_interval_spin.setSuffix(" 秒")
            self.sync_interval_spin.setToolTip("持仓同步间隔(秒)")
            toolbar_layout.addWidget(QLabel("间隔:"))
            toolbar_layout.addWidget(self.sync_interval_spin)

            # 强制同步按钮
            force_sync_btn = QPushButton("强制同步")
            force_sync_btn.clicked.connect(self.force_sync_positions)
            force_sync_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 5px 10px; border-radius: 4px;")
            toolbar_layout.addWidget(force_sync_btn)

            toolbar_layout.addStretch()

            layout.addWidget(toolbar)

            # 账户表格
            self.account_table = QTableWidget()
            self.account_table.setColumnCount(12)
            self.account_table.setHorizontalHeaderLabels([
                "账户ID", "账户名称", "账户类型", "状态", "余额", "可用余额",
                "冻结余额", "市值", "总资产", "盈亏", "盈亏比例", "操作"
            ])

            header = self.account_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.Interactive)

            self.account_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.account_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.account_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.account_table.setAlternatingRowColors(True)
            self.account_table.doubleClicked.connect(self.on_account_double_clicked)

            layout.addWidget(self.account_table)

            return tab

        except Exception as e:
            logger.error(f"创建账户标签页失败: {e}")
            return QWidget()

    def create_position_tab(self):
        """创建持仓标签页"""
        try:
            tab = QWidget()
            layout = QVBoxLayout(tab)

            # 工具栏
            toolbar = QFrame()
            toolbar_layout = QHBoxLayout(toolbar)

            refresh_btn = QPushButton("刷新")
            refresh_btn.clicked.connect(self.load_positions)
            toolbar_layout.addWidget(refresh_btn)

            toolbar_layout.addStretch()

            layout.addWidget(toolbar)

            # 持仓表格
            self.position_table = QTableWidget()
            self.position_table.setColumnCount(13)
            self.position_table.setHorizontalHeaderLabels([
                "持仓ID", "账户ID", "资产类型", "股票代码", "股票名称",
                "方向", "数量", "可用数量", "开仓价", "当前价",
                "市值", "盈亏", "盈亏比例", "操作"
            ])

            header = self.position_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.Interactive)

            self.position_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.position_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.position_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.position_table.setAlternatingRowColors(True)

            layout.addWidget(self.position_table)

            return tab

        except Exception as e:
            logger.error(f"创建持仓标签页失败: {e}")
            return QWidget()

    def create_fund_tab(self):
        """创建资金标签页"""
        try:
            tab = QWidget()
            layout = QVBoxLayout(tab)

            # 工具栏
            toolbar = QFrame()
            toolbar_layout = QHBoxLayout(toolbar)

            refresh_btn = QPushButton("刷新")
            refresh_btn.clicked.connect(self.load_funds)
            toolbar_layout.addWidget(refresh_btn)

            toolbar_layout.addStretch()

            layout.addWidget(toolbar)

            # 资金表格
            self.fund_table = QTableWidget()
            self.fund_table.setColumnCount(11)
            self.fund_table.setHorizontalHeaderLabels([
                "账户ID", "总余额", "可用余额", "冻结余额", "市值",
                "总资产", "盈亏", "盈亏比例", "已用保证金", "可用保证金", "更新时间"
            ])

            header = self.fund_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.Interactive)

            self.fund_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.fund_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.fund_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.fund_table.setAlternatingRowColors(True)

            layout.addWidget(self.fund_table)

            return tab

        except Exception as e:
            logger.error(f"创建资金标签页失败: {e}")
            return QWidget()

    def subscribe_events(self):
        """订阅事件"""
        try:
            self.event_bus.subscribe('account_created', self.on_account_created_event)
            self.event_bus.subscribe('account_updated', self.on_account_updated_event)
            self.event_bus.subscribe('account_deleted', self.on_account_deleted_event)
            self.event_bus.subscribe('position_created', self.on_position_created_event)
            self.event_bus.subscribe('position_updated', self.on_position_updated_event)
            self.event_bus.subscribe('fund_updated', self.on_fund_updated_event)
        except Exception as e:
            logger.error(f"订阅事件失败: {e}")

    def load_accounts(self):
        """加载账户列表"""
        try:
            self.status_label.setText("正在加载账户...")

            query = AccountQuery(limit=1000, sort_by="update_time", sort_order="desc")
            self.accounts = self.account_manager.query_accounts(query)

            self.update_account_table()

            self.status_label.setText(f"加载完成，共 {len(self.accounts)} 个账户")

        except Exception as e:
            logger.error(f"加载账户失败: {e}")
            self.status_label.setText(f"加载失败: {str(e)}")

    def update_account_table(self):
        """更新账户表格"""
        try:
            self.account_table.setRowCount(0)

            for account in self.accounts:
                row = self.account_table.rowCount()
                self.account_table.insertRow(row)

                self.account_table.setItem(row, 0, QTableWidgetItem(account.account_id))
                self.account_table.setItem(row, 1, QTableWidgetItem(account.account_name))
                self.account_table.setItem(row, 2, QTableWidgetItem(account.account_type))
                self.account_table.setItem(row, 3, QTableWidgetItem(account.status.value))
                self.account_table.setItem(row, 4, QTableWidgetItem(f"{account.balance:.2f}"))
                self.account_table.setItem(row, 5, QTableWidgetItem(f"{account.available_balance:.2f}"))
                self.account_table.setItem(row, 6, QTableWidgetItem(f"{account.frozen_balance:.2f}"))
                self.account_table.setItem(row, 7, QTableWidgetItem(f"{account.market_value:.2f}"))
                self.account_table.setItem(row, 8, QTableWidgetItem(f"{account.total_assets:.2f}"))
                self.account_table.setItem(row, 9, QTableWidgetItem(f"{account.profit_loss:.2f}"))
                self.account_table.setItem(row, 10, QTableWidgetItem(f"{account.profit_loss_ratio:.2%}"))

                operation_widget = QWidget()
                operation_layout = QHBoxLayout(operation_widget)
                operation_layout.setContentsMargins(2, 2, 2, 2)
                operation_layout.setSpacing(2)

                edit_btn = QPushButton("编辑")
                edit_btn.clicked.connect(self._create_account_edit_handler(account))
                edit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                edit_btn.setMinimumWidth(50)
                edit_btn.setMaximumWidth(50)
                operation_layout.addWidget(edit_btn)

                delete_btn = QPushButton("删除")
                delete_btn.clicked.connect(self._create_account_delete_handler(account))
                delete_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                delete_btn.setMinimumWidth(50)
                delete_btn.setMaximumWidth(50)
                operation_layout.addWidget(delete_btn)

                operation_layout.addStretch()
                self.account_table.setCellWidget(row, 11, operation_widget)

        except Exception as e:
            logger.error(f"更新账户表格失败: {e}")

    def _create_account_edit_handler(self, account: Account):
        """创建账户编辑处理器"""
        def handler(checked=False):
            self.show_edit_account_dialog(account)
        return handler

    def _create_account_delete_handler(self, account: Account):
        """创建账户删除处理器"""
        def handler(checked=False):
            self.delete_account(account)
        return handler

    def show_edit_account_dialog(self, account: Account):
        """显示编辑账户对话框"""
        try:
            dialog = EditAccountDialog(self.account_manager, account, self)
            if dialog.exec_() == QDialog.Accepted:
                self.load_accounts()
        except Exception as e:
            logger.error(f"显示编辑账户对话框失败: {e}")

    def delete_account(self, account: Account):
        """删除账户"""
        try:
            reply = QMessageBox.question(
                self, 
                '确认删除', 
                f'确定要删除账户 "{account.account_name}" ({account.account_id}) 吗？\n\n此操作不可恢复！',
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if self.account_manager.delete_account(account.account_id):
                    QMessageBox.information(self, '成功', f'账户删除成功: {account.account_id}')
                    self.load_accounts()
                else:
                    QMessageBox.warning(self, '失败', '账户删除失败')
        except Exception as e:
            logger.error(f"删除账户失败: {e}")
            QMessageBox.critical(self, '错误', f'删除账户失败: {str(e)}')

    def load_positions(self):
        """加载持仓列表"""
        try:
            self.status_label.setText("正在加载持仓...")

            query = PositionQuery(limit=1000, sort_by="update_time", sort_order="desc")
            self.positions = self.account_manager.query_positions(query)

            self.update_position_table()

            self.status_label.setText(f"加载完成，共 {len(self.positions)} 个持仓")

        except Exception as e:
            logger.error(f"加载持仓失败: {e}")
            self.status_label.setText(f"加载失败: {str(e)}")

    def update_position_table(self):
        """更新持仓表格"""
        try:
            self.position_table.setRowCount(0)

            for position in self.positions:
                row = self.position_table.rowCount()
                self.position_table.insertRow(row)

                self.position_table.setItem(row, 0, QTableWidgetItem(position.position_id))
                self.position_table.setItem(row, 1, QTableWidgetItem(position.account_id))
                self.position_table.setItem(row, 2, QTableWidgetItem(position.asset_type.value))
                self.position_table.setItem(row, 3, QTableWidgetItem(position.stock_code))
                self.position_table.setItem(row, 4, QTableWidgetItem(position.stock_name))
                self.position_table.setItem(row, 5, QTableWidgetItem(position.side.value))
                self.position_table.setItem(row, 6, QTableWidgetItem(str(position.quantity)))
                self.position_table.setItem(row, 7, QTableWidgetItem(str(position.available_quantity)))
                self.position_table.setItem(row, 8, QTableWidgetItem(f"{position.open_price:.2f}"))
                self.position_table.setItem(row, 9, QTableWidgetItem(f"{position.current_price:.2f}"))
                self.position_table.setItem(row, 10, QTableWidgetItem(f"{position.market_value:.2f}"))
                self.position_table.setItem(row, 11, QTableWidgetItem(f"{position.profit_loss:.2f}"))
                self.position_table.setItem(row, 12, QTableWidgetItem(f"{position.profit_loss_ratio:.2%}"))

        except Exception as e:
            logger.error(f"更新持仓表格失败: {e}")

    def load_funds(self):
        """加载资金信息"""
        try:
            self.status_label.setText("正在加载资金信息...")

            self.fund_infos = {}

            for account in self.accounts:
                fund_info = self.account_manager.get_fund_info(account.account_id)
                if fund_info:
                    self.fund_infos[account.account_id] = fund_info

            self.update_fund_table()

            self.status_label.setText(f"加载完成，共 {len(self.fund_infos)} 个账户的资金信息")

        except Exception as e:
            logger.error(f"加载资金信息失败: {e}")
            self.status_label.setText(f"加载失败: {str(e)}")

    def toggle_realtime_sync(self):
        """切换实时同步开关"""
        try:
            if self.realtime_sync_checkbox.isChecked():
                interval = self.sync_interval_spin.value()
                self.account_manager.enable_realtime_sync(interval_seconds=interval)
                self.realtime_sync_checkbox.setText("实时同步: 开")
                self.status_label.setText(f"实时持仓同步已启用，间隔 {interval} 秒")
            else:
                self.account_manager.disable_realtime_sync()
                self.realtime_sync_checkbox.setText("实时同步: 关")
                self.status_label.setText("实时持仓同步已禁用")
        except Exception as e:
            logger.error(f"切换实时同步失败: {e}")
            self.status_label.setText(f"操作失败: {str(e)}")

    def force_sync_positions(self):
        """强制同步所有持仓"""
        try:
            self.status_label.setText("正在强制同步持仓...")
            results = self.account_manager.force_sync_all_positions()
            success_count = sum(1 for v in results.values() if v)
            self.status_label.setText(f"强制同步完成: {success_count}/{len(results)} 个账户成功")
            self.load_positions()
        except Exception as e:
            logger.error(f"强制同步持仓失败: {e}")
            self.status_label.setText(f"同步失败: {str(e)}")

    def update_fund_table(self):
        """更新资金表格"""
        try:
            self.fund_table.setRowCount(0)

            for fund_info in self.fund_infos.values():
                row = self.fund_table.rowCount()
                self.fund_table.insertRow(row)

                self.fund_table.setItem(row, 0, QTableWidgetItem(fund_info.account_id))
                self.fund_table.setItem(row, 1, QTableWidgetItem(f"{fund_info.total_balance:.2f}"))
                self.fund_table.setItem(row, 2, QTableWidgetItem(f"{fund_info.available_balance:.2f}"))
                self.fund_table.setItem(row, 3, QTableWidgetItem(f"{fund_info.frozen_balance:.2f}"))
                self.fund_table.setItem(row, 4, QTableWidgetItem(f"{fund_info.market_value:.2f}"))
                self.fund_table.setItem(row, 5, QTableWidgetItem(f"{fund_info.total_assets:.2f}"))
                self.fund_table.setItem(row, 6, QTableWidgetItem(f"{fund_info.profit_loss:.2f}"))
                self.fund_table.setItem(row, 7, QTableWidgetItem(f"{fund_info.profit_loss_ratio:.2%}"))
                self.fund_table.setItem(row, 8, QTableWidgetItem(f"{fund_info.margin_used:.2f}"))
                self.fund_table.setItem(row, 9, QTableWidgetItem(f"{fund_info.margin_available:.2f}"))
                self.fund_table.setItem(row, 10, QTableWidgetItem(fund_info.update_time.strftime("%Y-%m-%d %H:%M:%S")))

        except Exception as e:
            logger.error(f"更新资金表格失败: {e}")

    def show_create_account_dialog(self):
        """显示创建账户对话框"""
        try:
            dialog = CreateAccountDialog(self.account_manager, self)
            if dialog.exec_() == QDialog.Accepted:
                self.load_accounts()
        except Exception as e:
            logger.error(f"显示创建账户对话框失败: {e}")

    def show_account_detail(self, account: Account):
        """显示账户详情"""
        try:
            summary = self.account_manager.get_account_summary(account.account_id)
            if summary:
                dialog = AccountDetailDialog(summary, self)
                dialog.exec_()
        except Exception as e:
            logger.error(f"显示账户详情失败: {e}")

    def on_account_double_clicked(self, item):
        """账户双击事件"""
        try:
            row = item.row()
            account_id = self.account_table.item(row, 0).text()
            account = next((a for a in self.accounts if a.account_id == account_id), None)

            if account:
                self.show_account_detail(account)

        except Exception as e:
            logger.error(f"账户双击事件处理失败: {e}")

    def on_account_created_event(self, event):
        """账户创建事件"""
        try:
            self.load_accounts()
        except Exception as e:
            logger.error(f"处理账户创建事件失败: {e}")
        finally:
            pass

    def on_account_updated_event(self, event):
        """账户更新事件"""
        try:
            self.load_accounts()
        except Exception as e:
            logger.error(f"处理账户更新事件失败: {e}")
        finally:
            pass

    def on_account_deleted_event(self, event):
        """账户删除事件"""
        try:
            self.load_accounts()
        except Exception as e:
            logger.error(f"处理账户删除事件失败: {e}")
        finally:
            pass

    def on_position_created_event(self, event):
        """持仓创建事件"""
        try:
            self.load_positions()
        except Exception as e:
            logger.error(f"处理持仓创建事件失败: {e}")
        finally:
            pass

    def on_position_updated_event(self, event):
        """持仓更新事件"""
        try:
            self.load_positions()
        except Exception as e:
            logger.error(f"处理持仓更新事件失败: {e}")
        finally:
            pass

    def on_fund_updated_event(self, event):
        """资金更新事件"""
        try:
            self.load_funds()
        except Exception as e:
            logger.error(f"处理资金更新事件失败: {e}")
        finally:
            pass


class CreateAccountDialog(QDialog):
    """创建账户对话框"""

    def __init__(self, account_manager: AccountManager, parent=None):
        super().__init__(parent)
        self.account_manager = account_manager
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("创建账户")
            self.setMinimumSize(700, 600)

            layout = QVBoxLayout(self)

            scroll_area = QWidget()
            scroll_layout = QVBoxLayout(scroll_area)

            form_layout = QGridLayout()

            row = 0

            # 基本信息
            form_layout.addWidget(QLabel("账户ID*:"), row, 0)
            self.account_id_input = QLineEdit()
            self.account_id_input.setPlaceholderText("例如: ACC001")
            form_layout.addWidget(self.account_id_input, row, 1)
            row += 1

            form_layout.addWidget(QLabel("账户名称*:"), row, 0)
            self.account_name_input = QLineEdit()
            self.account_name_input.setPlaceholderText("例如: 主账户")
            form_layout.addWidget(self.account_name_input, row, 1)
            row += 1

            form_layout.addWidget(QLabel("账户类型*:"), row, 0)
            self.account_type_combo = QComboBox()
            self.account_type_combo.addItems(["股票账户", "期货账户", "期权账户", "加密货币账户", "外汇账户"])
            self.account_type_combo.currentTextChanged.connect(self.on_account_type_changed)
            form_layout.addWidget(self.account_type_combo, row, 1)
            row += 1

            form_layout.addWidget(QLabel("机构名称*:"), row, 0)
            self.institution_name_input = QLineEdit()
            self.institution_name_input.setPlaceholderText("例如: 中信证券")
            form_layout.addWidget(self.institution_name_input, row, 1)
            row += 1

            form_layout.addWidget(QLabel("机构类型:"), row, 0)
            self.institution_type_combo = QComboBox()
            self.institution_type_combo.addItems([
                InstitutionType.BROKER.value,
                InstitutionType.FUTURES_COMPANY.value,
                InstitutionType.BANK.value,
                InstitutionType.INSURANCE.value,
                InstitutionType.FUND_COMPANY.value,
                InstitutionType.OTHER.value
            ])
            self.institution_type_combo.setCurrentText(InstitutionType.BROKER.value)
            form_layout.addWidget(self.institution_type_combo, row, 1)
            row += 1

            form_layout.addWidget(QLabel("交易接口类型*:"), row, 0)
            self.trading_interface_type_combo = QComboBox()
            self.trading_interface_type_combo.addItems([
                TradingInterfaceType.MOCK.value,
                TradingInterfaceType.CTP.value,
                TradingInterfaceType.XTP.value,
                TradingInterfaceType.XTP_PRO.value,
                TradingInterfaceType.TORA.value,
                TradingInterfaceType.OMS.value,
                TradingInterfaceType.CUSTOM.value,
                TradingInterfaceType.MINIQMT.value,
                TradingInterfaceType.BINANCE.value,
                TradingInterfaceType.BINANCE_FUTURES.value,
                TradingInterfaceType.OKX.value,
                TradingInterfaceType.OKX_FUTURES.value,
                TradingInterfaceType.HUOBI.value,
                TradingInterfaceType.HUOBI_FUTURES.value,
                TradingInterfaceType.BITGET.value,
                TradingInterfaceType.BYBIT.value
            ])
            self.trading_interface_type_combo.setCurrentText(TradingInterfaceType.MOCK.value)
            self.trading_interface_type_combo.currentTextChanged.connect(self.on_trading_interface_type_changed)
            form_layout.addWidget(self.trading_interface_type_combo, row, 1)
            row += 1

            form_layout.addWidget(QLabel("初始余额*:"), row, 0)
            self.balance_spin = QDoubleSpinBox()
            self.balance_spin.setRange(0, 100000000.0)
            self.balance_spin.setValue(100000.0)
            self.balance_spin.setDecimals(2)
            form_layout.addWidget(self.balance_spin, row, 1)
            row += 1

            scroll_layout.addLayout(form_layout)

            # CTP配置
            self.ctp_group = QGroupBox("CTP交易接口配置")
            ctp_layout = QGridLayout()

            ctp_layout.addWidget(QLabel("期货公司代码:"), 0, 0)
            self.ctp_broker_id_input = QLineEdit()
            self.ctp_broker_id_input.setPlaceholderText("例如: 9999")
            ctp_layout.addWidget(self.ctp_broker_id_input, 0, 1)

            ctp_layout.addWidget(QLabel("投资者代码:"), 1, 0)
            self.ctp_investor_id_input = QLineEdit()
            self.ctp_investor_id_input.setPlaceholderText("例如: your_investor_id")
            ctp_layout.addWidget(self.ctp_investor_id_input, 1, 1)

            ctp_layout.addWidget(QLabel("密码:"), 2, 0)
            self.ctp_password_input = QLineEdit()
            self.ctp_password_input.setEchoMode(QLineEdit.Password)
            self.ctp_password_input.setPlaceholderText("CTP账户密码")
            ctp_layout.addWidget(self.ctp_password_input, 2, 1)

            ctp_layout.addWidget(QLabel("交易前置地址:"), 3, 0)
            self.ctp_trade_front_input = QLineEdit()
            self.ctp_trade_front_input.setPlaceholderText("例如: tcp://180.168.146.187:10130")
            ctp_layout.addWidget(self.ctp_trade_front_input, 3, 1)

            ctp_layout.addWidget(QLabel("行情前置地址:"), 4, 0)
            self.ctp_quote_front_input = QLineEdit()
            self.ctp_quote_front_input.setPlaceholderText("例如: tcp://180.168.146.187:10131")
            ctp_layout.addWidget(self.ctp_quote_front_input, 4, 1)

            ctp_layout.addWidget(QLabel("应用ID:"), 5, 0)
            self.ctp_app_id_input = QLineEdit()
            self.ctp_app_id_input.setPlaceholderText("例如: simnow_client_test")
            ctp_layout.addWidget(self.ctp_app_id_input, 5, 1)

            ctp_layout.addWidget(QLabel("认证码:"), 6, 0)
            self.ctp_auth_code_input = QLineEdit()
            self.ctp_auth_code_input.setPlaceholderText("例如: 0000000000000000")
            ctp_layout.addWidget(self.ctp_auth_code_input, 6, 1)

            ctp_layout.addWidget(QLabel("产品信息:"), 7, 0)
            self.ctp_product_info_input = QLineEdit()
            self.ctp_product_info_input.setPlaceholderText("例如: simnow_client_test")
            ctp_layout.addWidget(self.ctp_product_info_input, 7, 1)

            self.ctp_group.setLayout(ctp_layout)
            self.ctp_group.setVisible(False)
            scroll_layout.addWidget(self.ctp_group)

            # XTP配置
            self.xtp_group = QGroupBox("XTP交易接口配置")
            xtp_layout = QGridLayout()

            xtp_layout.addWidget(QLabel("账户ID:"), 0, 0)
            self.xtp_account_id_input = QLineEdit()
            self.xtp_account_id_input.setPlaceholderText("例如: your_xtp_account")
            xtp_layout.addWidget(self.xtp_account_id_input, 0, 1)

            xtp_layout.addWidget(QLabel("密码:"), 1, 0)
            self.xtp_password_input = QLineEdit()
            self.xtp_password_input.setEchoMode(QLineEdit.Password)
            self.xtp_password_input.setPlaceholderText("XTP账户密码")
            xtp_layout.addWidget(self.xtp_password_input, 1, 1)

            xtp_layout.addWidget(QLabel("服务器地址:"), 2, 0)
            self.xtp_server_address_input = QLineEdit()
            self.xtp_server_address_input.setPlaceholderText("例如: 120.27.0.1:6001")
            xtp_layout.addWidget(self.xtp_server_address_input, 2, 1)

            xtp_layout.addWidget(QLabel("客户端ID:"), 3, 0)
            self.xtp_client_id_input = QSpinBox()
            self.xtp_client_id_input.setRange(0, 999999)
            xtp_layout.addWidget(self.xtp_client_id_input, 3, 1)

            xtp_layout.addWidget(QLabel("软件密钥:"), 4, 0)
            self.xtp_software_key_input = QLineEdit()
            self.xtp_software_key_input.setPlaceholderText("XTP软件密钥")
            xtp_layout.addWidget(self.xtp_software_key_input, 4, 1)

            xtp_layout.addWidget(QLabel("行情柜台地址:"), 5, 0)
            self.xtp_md_address_input = QLineEdit()
            self.xtp_md_address_input.setPlaceholderText("例如: 120.27.0.1:6002")
            xtp_layout.addWidget(self.xtp_md_address_input, 5, 1)

            xtp_layout.addWidget(QLabel("协议类型:"), 6, 0)
            self.xtp_protocol_combo = QComboBox()
            self.xtp_protocol_combo.addItems(["tcp", "udp"])
            xtp_layout.addWidget(self.xtp_protocol_combo, 6, 1)

            xtp_layout.addWidget(QLabel("缓冲区大小:"), 7, 0)
            self.xtp_buffer_size_input = QSpinBox()
            self.xtp_buffer_size_input.setRange(0, 102400)
            xtp_layout.addWidget(self.xtp_buffer_size_input, 7, 1)

            xtp_layout.addWidget(QLabel("交易柜台地址:"), 8, 0)
            self.xtp_td_address_input = QLineEdit()
            self.xtp_td_address_input.setPlaceholderText("例如: 120.27.0.1:6001")
            xtp_layout.addWidget(self.xtp_td_address_input, 8, 1)

            self.xtp_group.setLayout(xtp_layout)
            self.xtp_group.setVisible(False)
            scroll_layout.addWidget(self.xtp_group)
            
            # 币安配置
            self.binance_group = QGroupBox("币安（Binance）配置")
            binance_layout = QGridLayout()
            
            binance_layout.addWidget(QLabel("API Key:"), 0, 0)
            self.binance_api_key_input = QLineEdit()
            self.binance_api_key_input.setPlaceholderText("币安API Key")
            binance_layout.addWidget(self.binance_api_key_input, 0, 1)
            
            binance_layout.addWidget(QLabel("Secret Key:"), 1, 0)
            self.binance_secret_key_input = QLineEdit()
            self.binance_secret_key_input.setEchoMode(QLineEdit.Password)
            self.binance_secret_key_input.setPlaceholderText("币安Secret Key")
            binance_layout.addWidget(self.binance_secret_key_input, 1, 1)
            
            binance_layout.addWidget(QLabel("REST API地址:"), 2, 0)
            self.binance_rest_url_input = QLineEdit()
            self.binance_rest_url_input.setPlaceholderText("https://api.binance.com")
            binance_layout.addWidget(self.binance_rest_url_input, 2, 1)
            
            binance_layout.addWidget(QLabel("WebSocket地址:"), 3, 0)
            self.binance_ws_url_input = QLineEdit()
            self.binance_ws_url_input.setPlaceholderText("wss://stream.binance.com:9443")
            binance_layout.addWidget(self.binance_ws_url_input, 3, 1)
            
            self.binance_group.setLayout(binance_layout)
            self.binance_group.setVisible(False)
            scroll_layout.addWidget(self.binance_group)
            
            # 币安合约配置
            self.binance_futures_group = QGroupBox("币安合约（Binance Futures）配置")
            binance_futures_layout = QGridLayout()
            
            binance_futures_layout.addWidget(QLabel("API Key:"), 0, 0)
            self.binance_futures_api_key_input = QLineEdit()
            self.binance_futures_api_key_input.setPlaceholderText("币安合约API Key")
            binance_futures_layout.addWidget(self.binance_futures_api_key_input, 0, 1)
            
            binance_futures_layout.addWidget(QLabel("Secret Key:"), 1, 0)
            self.binance_futures_secret_key_input = QLineEdit()
            self.binance_futures_secret_key_input.setEchoMode(QLineEdit.Password)
            self.binance_futures_secret_key_input.setPlaceholderText("币安合约Secret Key")
            binance_futures_layout.addWidget(self.binance_futures_secret_key_input, 1, 1)
            
            binance_futures_layout.addWidget(QLabel("REST API地址:"), 2, 0)
            self.binance_futures_rest_url_input = QLineEdit()
            self.binance_futures_rest_url_input.setPlaceholderText("https://fapi.binance.com")
            binance_futures_layout.addWidget(self.binance_futures_rest_url_input, 2, 1)
            
            binance_futures_layout.addWidget(QLabel("WebSocket地址:"), 3, 0)
            self.binance_futures_ws_url_input = QLineEdit()
            self.binance_futures_ws_url_input.setPlaceholderText("wss://fstream.binance.com")
            binance_futures_layout.addWidget(self.binance_futures_ws_url_input, 3, 1)
            
            self.binance_futures_group.setLayout(binance_futures_layout)
            self.binance_futures_group.setVisible(False)
            scroll_layout.addWidget(self.binance_futures_group)
            
            # OKX配置
            self.okx_group = QGroupBox("OKX配置")
            okx_layout = QGridLayout()
            
            okx_layout.addWidget(QLabel("API Key:"), 0, 0)
            self.okx_api_key_input = QLineEdit()
            self.okx_api_key_input.setPlaceholderText("OKX API Key")
            okx_layout.addWidget(self.okx_api_key_input, 0, 1)
            
            okx_layout.addWidget(QLabel("Secret Key:"), 1, 0)
            self.okx_secret_key_input = QLineEdit()
            self.okx_secret_key_input.setEchoMode(QLineEdit.Password)
            self.okx_secret_key_input.setPlaceholderText("OKX Secret Key")
            okx_layout.addWidget(self.okx_secret_key_input, 1, 1)
            
            okx_layout.addWidget(QLabel("Passphrase:"), 2, 0)
            self.okx_passphrase_input = QLineEdit()
            self.okx_passphrase_input.setPlaceholderText("OKX Passphrase")
            okx_layout.addWidget(self.okx_passphrase_input, 2, 1)
            
            okx_layout.addWidget(QLabel("REST API地址:"), 3, 0)
            self.okx_rest_url_input = QLineEdit()
            self.okx_rest_url_input.setPlaceholderText("https://www.okx.com")
            okx_layout.addWidget(self.okx_rest_url_input, 3, 1)
            
            okx_layout.addWidget(QLabel("WebSocket地址:"), 4, 0)
            self.okx_ws_url_input = QLineEdit()
            self.okx_ws_url_input.setPlaceholderText("wss://ws.okx.com:8443")
            okx_layout.addWidget(self.okx_ws_url_input, 4, 1)
            
            self.okx_group.setLayout(okx_layout)
            self.okx_group.setVisible(False)
            scroll_layout.addWidget(self.okx_group)
            
            # OKX合约配置
            self.okx_futures_group = QGroupBox("OKX合约配置")
            okx_futures_layout = QGridLayout()
            
            okx_futures_layout.addWidget(QLabel("API Key:"), 0, 0)
            self.okx_futures_api_key_input = QLineEdit()
            self.okx_futures_api_key_input.setPlaceholderText("OKX合约API Key")
            okx_futures_layout.addWidget(self.okx_futures_api_key_input, 0, 1)
            
            okx_futures_layout.addWidget(QLabel("Secret Key:"), 1, 0)
            self.okx_futures_secret_key_input = QLineEdit()
            self.okx_futures_secret_key_input.setEchoMode(QLineEdit.Password)
            self.okx_futures_secret_key_input.setPlaceholderText("OKX合约Secret Key")
            okx_futures_layout.addWidget(self.okx_futures_secret_key_input, 1, 1)
            
            okx_futures_layout.addWidget(QLabel("Passphrase:"), 2, 0)
            self.okx_futures_passphrase_input = QLineEdit()
            self.okx_futures_passphrase_input.setPlaceholderText("OKX合约Passphrase")
            okx_futures_layout.addWidget(self.okx_futures_passphrase_input, 2, 1)
            
            okx_futures_layout.addWidget(QLabel("REST API地址:"), 3, 0)
            self.okx_futures_rest_url_input = QLineEdit()
            self.okx_futures_rest_url_input.setPlaceholderText("https://www.okx.com")
            okx_futures_layout.addWidget(self.okx_futures_rest_url_input, 3, 1)
            
            okx_futures_layout.addWidget(QLabel("WebSocket地址:"), 4, 0)
            self.okx_futures_ws_url_input = QLineEdit()
            self.okx_futures_ws_url_input.setPlaceholderText("wss://ws.okx.com:8443")
            okx_futures_layout.addWidget(self.okx_futures_ws_url_input, 4, 1)
            
            self.okx_futures_group.setLayout(okx_futures_layout)
            self.okx_futures_group.setVisible(False)
            scroll_layout.addWidget(self.okx_futures_group)
            
            # 火币配置
            self.huobi_group = QGroupBox("火币（Huobi/HTX）配置")
            huobi_layout = QGridLayout()
            
            huobi_layout.addWidget(QLabel("API Key:"), 0, 0)
            self.huobi_api_key_input = QLineEdit()
            self.huobi_api_key_input.setPlaceholderText("火币API Key")
            huobi_layout.addWidget(self.huobi_api_key_input, 0, 1)
            
            huobi_layout.addWidget(QLabel("Secret Key:"), 1, 0)
            self.huobi_secret_key_input = QLineEdit()
            self.huobi_secret_key_input.setEchoMode(QLineEdit.Password)
            self.huobi_secret_key_input.setPlaceholderText("火币Secret Key")
            huobi_layout.addWidget(self.huobi_secret_key_input, 1, 1)
            
            huobi_layout.addWidget(QLabel("REST API地址:"), 2, 0)
            self.huobi_rest_url_input = QLineEdit()
            self.huobi_rest_url_input.setPlaceholderText("https://api.huobi.pro")
            huobi_layout.addWidget(self.huobi_rest_url_input, 2, 1)
            
            huobi_layout.addWidget(QLabel("WebSocket地址:"), 3, 0)
            self.huobi_ws_url_input = QLineEdit()
            self.huobi_ws_url_input.setPlaceholderText("wss://api.huobi.pro/ws")
            huobi_layout.addWidget(self.huobi_ws_url_input, 3, 1)
            
            self.huobi_group.setLayout(huobi_layout)
            self.huobi_group.setVisible(False)
            scroll_layout.addWidget(self.huobi_group)
            
            # 火币合约配置
            self.huobi_futures_group = QGroupBox("火币合约配置")
            huobi_futures_layout = QGridLayout()
            
            huobi_futures_layout.addWidget(QLabel("API Key:"), 0, 0)
            self.huobi_futures_api_key_input = QLineEdit()
            self.huobi_futures_api_key_input.setPlaceholderText("火币合约API Key")
            huobi_futures_layout.addWidget(self.huobi_futures_api_key_input, 0, 1)
            
            huobi_futures_layout.addWidget(QLabel("Secret Key:"), 1, 0)
            self.huobi_futures_secret_key_input = QLineEdit()
            self.huobi_futures_secret_key_input.setEchoMode(QLineEdit.Password)
            self.huobi_futures_secret_key_input.setPlaceholderText("火币合约Secret Key")
            huobi_futures_layout.addWidget(self.huobi_futures_secret_key_input, 1, 1)
            
            huobi_futures_layout.addWidget(QLabel("REST API地址:"), 2, 0)
            self.huobi_futures_rest_url_input = QLineEdit()
            self.huobi_futures_rest_url_input.setPlaceholderText("https://api.hbdm.com")
            huobi_futures_layout.addWidget(self.huobi_futures_rest_url_input, 2, 1)
            
            huobi_futures_layout.addWidget(QLabel("WebSocket地址:"), 3, 0)
            self.huobi_futures_ws_url_input = QLineEdit()
            self.huobi_futures_ws_url_input.setPlaceholderText("wss://api.hbdm.com/ws")
            huobi_futures_layout.addWidget(self.huobi_futures_ws_url_input, 3, 1)
            
            self.huobi_futures_group.setLayout(huobi_futures_layout)
            self.huobi_futures_group.setVisible(False)
            scroll_layout.addWidget(self.huobi_futures_group)
            
            # Bitget配置
            self.bitget_group = QGroupBox("Bitget配置")
            bitget_layout = QGridLayout()
            
            bitget_layout.addWidget(QLabel("API Key:"), 0, 0)
            self.bitget_api_key_input = QLineEdit()
            self.bitget_api_key_input.setPlaceholderText("Bitget API Key")
            bitget_layout.addWidget(self.bitget_api_key_input, 0, 1)
            
            bitget_layout.addWidget(QLabel("Secret Key:"), 1, 0)
            self.bitget_secret_key_input = QLineEdit()
            self.bitget_secret_key_input.setEchoMode(QLineEdit.Password)
            self.bitget_secret_key_input.setPlaceholderText("Bitget Secret Key")
            bitget_layout.addWidget(self.bitget_secret_key_input, 1, 1)
            
            bitget_layout.addWidget(QLabel("Passphrase:"), 2, 0)
            self.bitget_passphrase_input = QLineEdit()
            self.bitget_passphrase_input.setPlaceholderText("Bitget Passphrase")
            bitget_layout.addWidget(self.bitget_passphrase_input, 2, 1)
            
            bitget_layout.addWidget(QLabel("REST API地址:"), 3, 0)
            self.bitget_rest_url_input = QLineEdit()
            self.bitget_rest_url_input.setPlaceholderText("https://api.bitget.com")
            bitget_layout.addWidget(self.bitget_rest_url_input, 3, 1)
            
            bitget_layout.addWidget(QLabel("WebSocket地址:"), 4, 0)
            self.bitget_ws_url_input = QLineEdit()
            self.bitget_ws_url_input.setPlaceholderText("wss://ws.bitget.com")
            bitget_layout.addWidget(self.bitget_ws_url_input, 4, 1)
            
            self.bitget_group.setLayout(bitget_layout)
            self.bitget_group.setVisible(False)
            scroll_layout.addWidget(self.bitget_group)
            
            # Bybit配置
            self.bybit_group = QGroupBox("Bybit配置")
            bybit_layout = QGridLayout()
            
            bybit_layout.addWidget(QLabel("API Key:"), 0, 0)
            self.bybit_api_key_input = QLineEdit()
            self.bybit_api_key_input.setPlaceholderText("Bybit API Key")
            bybit_layout.addWidget(self.bybit_api_key_input, 0, 1)
            
            bybit_layout.addWidget(QLabel("Secret Key:"), 1, 0)
            self.bybit_secret_key_input = QLineEdit()
            self.bybit_secret_key_input.setEchoMode(QLineEdit.Password)
            self.bybit_secret_key_input.setPlaceholderText("Bybit Secret Key")
            bybit_layout.addWidget(self.bybit_secret_key_input, 1, 1)
            
            bybit_layout.addWidget(QLabel("REST API地址:"), 2, 0)
            self.bybit_rest_url_input = QLineEdit()
            self.bybit_rest_url_input.setPlaceholderText("https://api.bybit.com")
            bybit_layout.addWidget(self.bybit_rest_url_input, 2, 1)
            
            bybit_layout.addWidget(QLabel("WebSocket地址:"), 3, 0)
            self.bybit_ws_url_input = QLineEdit()
            self.bybit_ws_url_input.setPlaceholderText("wss://stream.bybit.com")
            bybit_layout.addWidget(self.bybit_ws_url_input, 3, 1)
            
            self.bybit_group.setLayout(bybit_layout)
            self.bybit_group.setVisible(False)
            scroll_layout.addWidget(self.bybit_group)

            # miniQMT配置
            self.miniqmt_group = QGroupBox("miniQMT交易接口配置")
            miniqmt_layout = QGridLayout()

            miniqmt_layout.addWidget(QLabel("账户ID:"), 0, 0)
            self.miniqmt_account_id_input = QLineEdit()
            self.miniqmt_account_id_input.setPlaceholderText("miniQMT账户ID")
            miniqmt_layout.addWidget(self.miniqmt_account_id_input, 0, 1)

            miniqmt_layout.addWidget(QLabel("密码:"), 1, 0)
            self.miniqmt_password_input = QLineEdit()
            self.miniqmt_password_input.setEchoMode(QLineEdit.Password)
            self.miniqmt_password_input.setPlaceholderText("miniQMT密码")
            miniqmt_layout.addWidget(self.miniqmt_password_input, 1, 1)

            miniqmt_layout.addWidget(QLabel("服务器IP:"), 2, 0)
            self.miniqmt_ip_input = QLineEdit()
            self.miniqmt_ip_input.setPlaceholderText("127.0.0.1")
            miniqmt_layout.addWidget(self.miniqmt_ip_input, 2, 1)

            miniqmt_layout.addWidget(QLabel("端口:"), 3, 0)
            self.miniqmt_port_input = QSpinBox()
            self.miniqmt_port_input.setRange(1, 65535)
            self.miniqmt_port_input.setValue(58610)
            miniqmt_layout.addWidget(self.miniqmt_port_input, 3, 1)

            self.miniqmt_group.setLayout(miniqmt_layout)
            self.miniqmt_group.setVisible(False)
            scroll_layout.addWidget(self.miniqmt_group)

            layout.addWidget(scroll_area)

            button_layout = QHBoxLayout()

            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(self.reject)
            button_layout.addWidget(cancel_btn)

            create_btn = QPushButton("创建")
            create_btn.clicked.connect(self.create_account)
            button_layout.addWidget(create_btn)

            layout.addLayout(button_layout)

        except Exception as e:
            logger.error(f"初始化创建账户对话框UI失败: {e}")

    def on_account_type_changed(self, account_type: str):
        """账户类型改变事件"""
        pass

    def on_trading_interface_type_changed(self, interface_type: str):
        """交易接口类型改变事件"""
        if interface_type == TradingInterfaceType.CTP.value:
            self.ctp_group.setVisible(True)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
        elif interface_type in [TradingInterfaceType.XTP.value, TradingInterfaceType.XTP_PRO.value]:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(True)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
        elif interface_type == TradingInterfaceType.BINANCE.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(True)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
        elif interface_type == TradingInterfaceType.BINANCE_FUTURES.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(True)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
        elif interface_type == TradingInterfaceType.OKX.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(True)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
        elif interface_type == TradingInterfaceType.OKX_FUTURES.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(True)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
        elif interface_type == TradingInterfaceType.HUOBI.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(True)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
        elif interface_type == TradingInterfaceType.HUOBI_FUTURES.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(True)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
        elif interface_type == TradingInterfaceType.BITGET.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(True)
            self.bybit_group.setVisible(False)
        elif interface_type == TradingInterfaceType.BYBIT.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(True)
        elif interface_type == TradingInterfaceType.MINIQMT.value:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
            self.miniqmt_group.setVisible(True)
        else:
            self.ctp_group.setVisible(False)
            self.xtp_group.setVisible(False)
            self.binance_group.setVisible(False)
            self.binance_futures_group.setVisible(False)
            self.okx_group.setVisible(False)
            self.okx_futures_group.setVisible(False)
            self.huobi_group.setVisible(False)
            self.huobi_futures_group.setVisible(False)
            self.bitget_group.setVisible(False)
            self.bybit_group.setVisible(False)
            self.miniqmt_group.setVisible(False)

    def create_account(self):
        """创建账户"""
        def parse_address(address):
            """解析地址字符串，返回(ip, port)"""
            if not address or ':' not in address:
                return '', 0
            parts = address.rsplit(':', 1)
            if len(parts) != 2:
                return '', 0
            ip, port = parts
            try:
                return ip.strip(), int(port.strip())
            except ValueError:
                return ip.strip(), 0
        
        try:
            account_id = self.account_id_input.text().strip()
            if not account_id:
                QMessageBox.warning(self, '警告', '请输入账户ID')
                return

            account_name = self.account_name_input.text().strip()
            if not account_name:
                QMessageBox.warning(self, '警告', '请输入账户名称')
                return

            account_type = self.account_type_combo.currentText()
            institution_name = self.institution_name_input.text().strip()
            if not institution_name:
                QMessageBox.warning(self, '警告', '请输入机构名称')
                return

            institution_type = InstitutionType(self.institution_type_combo.currentText())
            trading_interface_type = TradingInterfaceType(self.trading_interface_type_combo.currentText())
            balance = self.balance_spin.value()

            md_ip, md_port = parse_address(self.xtp_md_address_input.text().strip())
            td_ip, td_port = parse_address(self.xtp_td_address_input.text().strip())

            account = Account(
                account_id=account_id,
                account_name=account_name,
                account_type=account_type,
                status=AccountStatus.ACTIVE,
                balance=balance,
                available_balance=balance,
                frozen_balance=0.0,
                market_value=0.0,
                total_assets=balance,
                profit_loss=0.0,
                profit_loss_ratio=0.0,
                create_time=datetime.now(),
                update_time=datetime.now(),
                institution_name=institution_name,
                institution_type=institution_type,
                trading_interface_type=trading_interface_type,
                ctp_broker_id=self.ctp_broker_id_input.text().strip(),
                ctp_investor_id=self.ctp_investor_id_input.text().strip(),
                ctp_password=self.ctp_password_input.text(),
                ctp_trade_front=self.ctp_trade_front_input.text().strip(),
                ctp_quote_front=self.ctp_quote_front_input.text().strip(),
                ctp_app_id=self.ctp_app_id_input.text().strip(),
                ctp_auth_code=self.ctp_auth_code_input.text().strip(),
                ctp_product_info=self.ctp_product_info_input.text().strip(),
                xtp_account_id=self.xtp_account_id_input.text().strip(),
                xtp_password=self.xtp_password_input.text(),
                xtp_server_address=self.xtp_server_address_input.text().strip(),
                xtp_client_id=self.xtp_client_id_input.value(),
                xtp_software_key=self.xtp_software_key_input.text().strip(),
                xtp_md_ip=md_ip,
                xtp_md_port=md_port,
                xtp_protocol=self.xtp_protocol_combo.currentText(),
                xtp_buffer_size=self.xtp_buffer_size_input.value(),
                xtp_td_ip=td_ip,
                xtp_td_port=td_port,
                binance_api_key=self.binance_api_key_input.text().strip(),
                binance_secret_key=self.binance_secret_key_input.text(),
                binance_rest_url=self.binance_rest_url_input.text().strip(),
                binance_ws_url=self.binance_ws_url_input.text().strip(),
                binance_futures_api_key=self.binance_futures_api_key_input.text().strip(),
                binance_futures_secret_key=self.binance_futures_secret_key_input.text(),
                binance_futures_rest_url=self.binance_futures_rest_url_input.text().strip(),
                binance_futures_ws_url=self.binance_futures_ws_url_input.text().strip(),
                okx_api_key=self.okx_api_key_input.text().strip(),
                okx_secret_key=self.okx_secret_key_input.text(),
                okx_passphrase=self.okx_passphrase_input.text(),
                okx_rest_url=self.okx_rest_url_input.text().strip(),
                okx_ws_url=self.okx_ws_url_input.text().strip(),
                okx_futures_api_key=self.okx_futures_api_key_input.text().strip(),
                okx_futures_secret_key=self.okx_futures_secret_key_input.text(),
                okx_futures_passphrase=self.okx_futures_passphrase_input.text(),
                okx_futures_rest_url=self.okx_futures_rest_url_input.text().strip(),
                okx_futures_ws_url=self.okx_futures_ws_url_input.text().strip(),
                huobi_api_key=self.huobi_api_key_input.text().strip(),
                huobi_secret_key=self.huobi_secret_key_input.text(),
                huobi_rest_url=self.huobi_rest_url_input.text().strip(),
                huobi_ws_url=self.huobi_ws_url_input.text().strip(),
                huobi_futures_api_key=self.huobi_futures_api_key_input.text().strip(),
                huobi_futures_secret_key=self.huobi_futures_secret_key_input.text(),
                huobi_futures_rest_url=self.huobi_futures_rest_url_input.text().strip(),
                huobi_futures_ws_url=self.huobi_futures_ws_url_input.text().strip(),
                bitget_api_key=self.bitget_api_key_input.text().strip(),
                bitget_secret_key=self.bitget_secret_key_input.text(),
                bitget_passphrase=self.bitget_passphrase_input.text(),
                bitget_rest_url=self.bitget_rest_url_input.text().strip(),
                bitget_ws_url=self.bitget_ws_url_input.text().strip(),
                bybit_api_key=self.bybit_api_key_input.text().strip(),
                bybit_secret_key=self.bybit_secret_key_input.text(),
                bybit_rest_url=self.bybit_rest_url_input.text().strip(),
                bybit_ws_url=self.bybit_ws_url_input.text().strip(),
                miniqmt_account_id=self.miniqmt_account_id_input.text().strip(),
                miniqmt_password=self.miniqmt_password_input.text(),
                miniqmt_ip=self.miniqmt_ip_input.text().strip(),
                miniqmt_port=self.miniqmt_port_input.value()
            )

            if self.account_manager.create_account(account):
                QMessageBox.information(self, '成功', f'账户创建成功: {account_id}')
                self.accept()
            else:
                QMessageBox.warning(self, '失败', '账户创建失败')

        except Exception as e:
            logger.error(f"创建账户失败: {e}")
            QMessageBox.critical(self, '错误', f'创建账户失败: {str(e)}')


class AccountDetailDialog(QDialog):
    """账户详情对话框"""

    def __init__(self, summary: Dict, parent=None):
        super().__init__(parent)
        self.summary = summary
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("账户详情")
            self.setMinimumSize(800, 600)

            layout = QVBoxLayout(self)

            account = self.summary['account']
            positions = self.summary['positions']
            fund_info = self.summary['fund_info']

            # 账户信息
            account_group = QGroupBox("账户信息")
            account_layout = QGridLayout()

            account_layout.addWidget(QLabel("账户ID:"), 0, 0)
            account_layout.addWidget(QLabel(account['account_id']), 0, 1)

            account_layout.addWidget(QLabel("账户名称:"), 1, 0)
            account_layout.addWidget(QLabel(account['account_name']), 1, 1)

            account_layout.addWidget(QLabel("账户类型:"), 2, 0)
            account_layout.addWidget(QLabel(account['account_type']), 2, 1)

            account_layout.addWidget(QLabel("状态:"), 3, 0)
            account_layout.addWidget(QLabel(account['status']), 3, 1)

            account_layout.addWidget(QLabel("总资产:"), 4, 0)
            account_layout.addWidget(QLabel(f"{account['total_assets']:.2f}"), 4, 1)

            account_layout.addWidget(QLabel("盈亏:"), 5, 0)
            account_layout.addWidget(QLabel(f"{account['profit_loss']:.2f}"), 5, 1)

            account_group.setLayout(account_layout)
            layout.addWidget(account_group)

            # 持仓信息
            position_group = QGroupBox("持仓信息")
            position_layout = QVBoxLayout()

            position_table = QTableWidget()
            position_table.setColumnCount(8)
            position_table.setHorizontalHeaderLabels([
                "持仓ID", "股票代码", "股票名称", "方向", "数量",
                "开仓价", "当前价", "盈亏"
            ])

            for pos in positions:
                row = position_table.rowCount()
                position_table.insertRow(row)

                position_table.setItem(row, 0, QTableWidgetItem(pos['position_id']))
                position_table.setItem(row, 1, QTableWidgetItem(pos['stock_code']))
                position_table.setItem(row, 2, QTableWidgetItem(pos['stock_name']))
                position_table.setItem(row, 3, QTableWidgetItem(pos['side']))
                position_table.setItem(row, 4, QTableWidgetItem(str(pos['quantity'])))
                position_table.setItem(row, 5, QTableWidgetItem(f"{pos['open_price']:.2f}"))
                position_table.setItem(row, 6, QTableWidgetItem(f"{pos['current_price']:.2f}"))
                position_table.setItem(row, 7, QTableWidgetItem(f"{pos['profit_loss']:.2f}"))

            position_layout.addWidget(position_table)
            position_group.setLayout(position_layout)
            layout.addWidget(position_group)

            # 资金信息
            if fund_info:
                fund_group = QGroupBox("资金信息")
                fund_layout = QGridLayout()

                fund_layout.addWidget(QLabel("总余额:"), 0, 0)
                fund_layout.addWidget(QLabel(f"{fund_info['total_balance']:.2f}"), 0, 1)

                fund_layout.addWidget(QLabel("可用余额:"), 1, 0)
                fund_layout.addWidget(QLabel(f"{fund_info['available_balance']:.2f}"), 1, 1)

                fund_layout.addWidget(QLabel("冻结余额:"), 2, 0)
                fund_layout.addWidget(QLabel(f"{fund_info['frozen_balance']:.2f}"), 2, 1)

                fund_layout.addWidget(QLabel("市值:"), 3, 0)
                fund_layout.addWidget(QLabel(f"{fund_info['market_value']:.2f}"), 3, 1)

                fund_layout.addWidget(QLabel("总资产:"), 4, 0)
                fund_layout.addWidget(QLabel(f"{fund_info['total_assets']:.2f}"), 4, 1)

                fund_group.setLayout(fund_layout)
                layout.addWidget(fund_group)

            # 关闭按钮
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn)

        except Exception as e:
            logger.error(f"初始化账户详情对话框UI失败: {e}")


class EditAccountDialog(QDialog):
    """编辑账户对话框"""

    def __init__(self, account_manager: AccountManager, account: Account, parent=None):
        super().__init__(parent)
        self.account_manager = account_manager
        self.account = account
        self.init_ui()
        self.load_account_data()

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("编辑账户")
            self.setMinimumSize(700, 600)

            layout = QVBoxLayout(self)

            scroll_area = QWidget()
            scroll_layout = QVBoxLayout(scroll_area)

            form_layout = QGridLayout()

            row = 0

            form_layout.addWidget(QLabel("账户ID*:"), row, 0)
            self.account_id_input = QLineEdit()
            self.account_id_input.setPlaceholderText("例如: ACC001")
            self.account_id_input.setEnabled(False)
            form_layout.addWidget(self.account_id_input, row, 1)
            row += 1

            form_layout.addWidget(QLabel("账户名称*:"), row, 0)
            self.account_name_input = QLineEdit()
            self.account_name_input.setPlaceholderText("例如: 主账户")
            form_layout.addWidget(self.account_name_input, row, 1)
            row += 1

            form_layout.addWidget(QLabel("账户类型*:"), row, 0)
            self.account_type_combo = QComboBox()
            self.account_type_combo.addItems(["股票账户", "期货账户", "期权账户", "加密货币账户", "外汇账户"])
            self.account_type_combo.currentTextChanged.connect(self.on_account_type_changed)
            form_layout.addWidget(self.account_type_combo, row, 1)
            row += 1

            form_layout.addWidget(QLabel("机构名称*:"), row, 0)
            self.institution_name_input = QLineEdit()
            self.institution_name_input.setPlaceholderText("例如: 中信证券")
            form_layout.addWidget(self.institution_name_input, row, 1)
            row += 1

            form_layout.addWidget(QLabel("机构类型:"), row, 0)
            self.institution_type_combo = QComboBox()
            self.institution_type_combo.addItems([
                InstitutionType.BROKER.value,
                InstitutionType.FUTURES_COMPANY.value,
                InstitutionType.BANK.value,
                InstitutionType.INSURANCE.value,
                InstitutionType.FUND_COMPANY.value,
                InstitutionType.OTHER.value
            ])
            self.institution_type_combo.setCurrentText(InstitutionType.BROKER.value)
            form_layout.addWidget(self.institution_type_combo, row, 1)
            row += 1

            form_layout.addWidget(QLabel("交易接口类型*:"), row, 0)
            self.trading_interface_type_combo = QComboBox()
            self.trading_interface_type_combo.addItems([
                TradingInterfaceType.MOCK.value,
                TradingInterfaceType.CTP.value,
                TradingInterfaceType.XTP.value,
                TradingInterfaceType.XTP_PRO.value,
                TradingInterfaceType.TORA.value,
                TradingInterfaceType.OMS.value,
                TradingInterfaceType.CUSTOM.value,
                TradingInterfaceType.BINANCE.value,
                TradingInterfaceType.BINANCE_FUTURES.value,
                TradingInterfaceType.OKX.value,
                TradingInterfaceType.OKX_FUTURES.value,
                TradingInterfaceType.HUOBI.value,
                TradingInterfaceType.HUOBI_FUTURES.value,
                TradingInterfaceType.BITGET.value,
                TradingInterfaceType.BYBIT.value
            ])
            self.trading_interface_type_combo.setCurrentText(TradingInterfaceType.MOCK.value)
            self.trading_interface_type_combo.currentTextChanged.connect(self.on_trading_interface_type_changed)
            form_layout.addWidget(self.trading_interface_type_combo, row, 1)
            row += 1

            form_layout.addWidget(QLabel("初始余额*:"), row, 0)
            self.balance_spin = QDoubleSpinBox()
            self.balance_spin.setRange(0, 100000000.0)
            self.balance_spin.setValue(100000.0)
            self.balance_spin.setDecimals(2)
            form_layout.addWidget(self.balance_spin, row, 1)
            row += 1

            scroll_layout.addLayout(form_layout)

            # CTP配置
            self.ctp_group = QGroupBox("CTP交易接口配置")
            ctp_layout = QGridLayout()

            ctp_layout.addWidget(QLabel("期货公司代码:"), 0, 0)
            self.ctp_broker_id_input = QLineEdit()
            self.ctp_broker_id_input.setPlaceholderText("例如: 9999")
            ctp_layout.addWidget(self.ctp_broker_id_input, 0, 1)

            ctp_layout.addWidget(QLabel("投资者代码:"), 1, 0)
            self.ctp_investor_id_input = QLineEdit()
            self.ctp_investor_id_input.setPlaceholderText("例如: your_investor_id")
            ctp_layout.addWidget(self.ctp_investor_id_input, 1, 1)

            ctp_layout.addWidget(QLabel("密码:"), 2, 0)
            self.ctp_password_input = QLineEdit()
            self.ctp_password_input.setEchoMode(QLineEdit.Password)
            self.ctp_password_input.setPlaceholderText("CTP账户密码")
            ctp_layout.addWidget(self.ctp_password_input, 2, 1)

            ctp_layout.addWidget(QLabel("交易前置地址:"), 3, 0)
            self.ctp_trade_front_input = QLineEdit()
            self.ctp_trade_front_input.setPlaceholderText("例如: tcp://180.168.146.187:10130")
            ctp_layout.addWidget(self.ctp_trade_front_input, 3, 1)

            ctp_layout.addWidget(QLabel("行情前置地址:"), 4, 0)
            self.ctp_quote_front_input = QLineEdit()
            self.ctp_quote_front_input.setPlaceholderText("例如: tcp://180.168.146.187:10131")
            ctp_layout.addWidget(self.ctp_quote_front_input, 4, 1)

            ctp_layout.addWidget(QLabel("应用ID:"), 5, 0)
            self.ctp_app_id_input = QLineEdit()
            self.ctp_app_id_input.setPlaceholderText("例如: simnow_client_test")
            ctp_layout.addWidget(self.ctp_app_id_input, 5, 1)

            ctp_layout.addWidget(QLabel("认证码:"), 6, 0)
            self.ctp_auth_code_input = QLineEdit()
            self.ctp_auth_code_input.setPlaceholderText("例如: 0000000000000000")
            ctp_layout.addWidget(self.ctp_auth_code_input, 6, 1)

            ctp_layout.addWidget(QLabel("产品信息:"), 7, 0)
            self.ctp_product_info_input = QLineEdit()
            self.ctp_product_info_input.setPlaceholderText("例如: simnow_client_test")
            ctp_layout.addWidget(self.ctp_product_info_input, 7, 1)

            self.ctp_group.setLayout(ctp_layout)
            self.ctp_group.setVisible(False)
            scroll_layout.addWidget(self.ctp_group)

            # XTP配置
            self.xtp_group = QGroupBox("XTP交易接口配置")
            xtp_layout = QGridLayout()

            xtp_layout.addWidget(QLabel("账户ID:"), 0, 0)
            self.xtp_account_id_input = QLineEdit()
            self.xtp_account_id_input.setPlaceholderText("例如: your_xtp_account")
            xtp_layout.addWidget(self.xtp_account_id_input, 0, 1)

            xtp_layout.addWidget(QLabel("密码:"), 1, 0)
            self.xtp_password_input = QLineEdit()
            self.xtp_password_input.setEchoMode(QLineEdit.Password)
            self.xtp_password_input.setPlaceholderText("XTP账户密码")
            xtp_layout.addWidget(self.xtp_password_input, 1, 1)

            xtp_layout.addWidget(QLabel("服务器地址:"), 2, 0)
            self.xtp_server_address_input = QLineEdit()
            self.xtp_server_address_input.setPlaceholderText("例如: 120.27.0.1:6001")
            xtp_layout.addWidget(self.xtp_server_address_input, 2, 1)

            xtp_layout.addWidget(QLabel("客户端ID:"), 3, 0)
            self.xtp_client_id_input = QSpinBox()
            self.xtp_client_id_input.setRange(0, 999999)
            xtp_layout.addWidget(self.xtp_client_id_input, 3, 1)

            xtp_layout.addWidget(QLabel("软件密钥:"), 4, 0)
            self.xtp_software_key_input = QLineEdit()
            self.xtp_software_key_input.setPlaceholderText("XTP软件密钥")
            xtp_layout.addWidget(self.xtp_software_key_input, 4, 1)

            xtp_layout.addWidget(QLabel("行情柜台地址:"), 5, 0)
            self.xtp_md_address_input = QLineEdit()
            self.xtp_md_address_input.setPlaceholderText("例如: 120.27.0.1:6002")
            xtp_layout.addWidget(self.xtp_md_address_input, 5, 1)

            xtp_layout.addWidget(QLabel("协议类型:"), 6, 0)
            self.xtp_protocol_combo = QComboBox()
            self.xtp_protocol_combo.addItems(["tcp", "udp"])
            xtp_layout.addWidget(self.xtp_protocol_combo, 6, 1)

            xtp_layout.addWidget(QLabel("缓冲区大小:"), 7, 0)
            self.xtp_buffer_size_input = QSpinBox()
            self.xtp_buffer_size_input.setRange(0, 102400)
            xtp_layout.addWidget(self.xtp_buffer_size_input, 7, 1)

            xtp_layout.addWidget(QLabel("交易柜台地址:"), 8, 0)
            self.xtp_td_address_input = QLineEdit()
            self.xtp_td_address_input.setPlaceholderText("例如: 120.27.0.1:6001")
            xtp_layout.addWidget(self.xtp_td_address_input, 8, 1)

            self.xtp_group.setLayout(xtp_layout)
            self.xtp_group.setVisible(False)
            scroll_layout.addWidget(self.xtp_group)

            layout.addWidget(scroll_area)

            # 按钮区域
            button_layout = QHBoxLayout()
            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(self.reject)
            button_layout.addWidget(cancel_btn)

            save_btn = QPushButton("保存")
            save_btn.clicked.connect(self.update_account)
            button_layout.addWidget(save_btn)

            layout.addLayout(button_layout)

        except Exception as e:
            logger.error(f"初始化编辑账户对话框UI失败: {e}")

    def load_account_data(self):
        """加载账户数据到表单"""
        try:
            self.account_id_input.setText(self.account.account_id)
            self.account_name_input.setText(self.account.account_name)
            self.account_type_combo.setCurrentText(self.account.account_type)
            self.institution_name_input.setText(self.account.institution_name)
            self.institution_type_combo.setCurrentText(self.account.institution_type.value if self.account.institution_type else InstitutionType.BROKER.value)
            self.trading_interface_type_combo.setCurrentText(self.account.trading_interface_type.value if self.account.trading_interface_type else TradingInterfaceType.MOCK.value)
            self.balance_spin.setValue(self.account.balance)

            # CTP配置
            if self.account.ctp_broker_id:
                self.ctp_broker_id_input.setText(self.account.ctp_broker_id)
            if self.account.ctp_investor_id:
                self.ctp_investor_id_input.setText(self.account.ctp_investor_id)
            if self.account.ctp_password:
                self.ctp_password_input.setText(self.account.ctp_password)
            if self.account.ctp_trade_front:
                self.ctp_trade_front_input.setText(self.account.ctp_trade_front)
            if self.account.ctp_quote_front:
                self.ctp_quote_front_input.setText(self.account.ctp_quote_front)
            if self.account.ctp_app_id:
                self.ctp_app_id_input.setText(self.account.ctp_app_id)
            if self.account.ctp_auth_code:
                self.ctp_auth_code_input.setText(self.account.ctp_auth_code)
            if self.account.ctp_product_info:
                self.ctp_product_info_input.setText(self.account.ctp_product_info)

            # XTP配置
            if self.account.xtp_account_id:
                self.xtp_account_id_input.setText(self.account.xtp_account_id)
            if self.account.xtp_password:
                self.xtp_password_input.setText(self.account.xtp_password)
            if self.account.xtp_server_address:
                self.xtp_server_address_input.setText(self.account.xtp_server_address)
            if self.account.xtp_client_id:
                self.xtp_client_id_input.setValue(self.account.xtp_client_id)
            if self.account.xtp_software_key:
                self.xtp_software_key_input.setText(self.account.xtp_software_key)
            if self.account.xtp_md_ip and self.account.xtp_md_port:
                self.xtp_md_address_input.setText(f"{self.account.xtp_md_ip}:{self.account.xtp_md_port}")
            if self.account.xtp_protocol:
                self.xtp_protocol_combo.setCurrentText(self.account.xtp_protocol)
            if self.account.xtp_buffer_size:
                self.xtp_buffer_size_input.setValue(self.account.xtp_buffer_size)
            if self.account.xtp_td_ip and self.account.xtp_td_port:
                self.xtp_td_address_input.setText(f"{self.account.xtp_td_ip}:{self.account.xtp_td_port}")

            # 显示对应的配置组
            self.on_trading_interface_type_changed(self.trading_interface_type_combo.currentText())

        except Exception as e:
            logger.error(f"加载账户数据失败: {e}")

    def on_account_type_changed(self, account_type: str):
        """账户类型改变事件"""
        pass

    def on_trading_interface_type_changed(self, interface_type: str):
        """交易接口类型改变事件"""
        try:
            self.ctp_group.setVisible(interface_type == TradingInterfaceType.CTP.value)
            self.xtp_group.setVisible(interface_type in [TradingInterfaceType.XTP.value, TradingInterfaceType.XTP_PRO.value])
        except Exception as e:
            logger.error(f"交易接口类型改变事件处理失败: {e}")

    def update_account(self):
        """更新账户"""
        def parse_address(address):
            """解析地址字符串，返回(ip, port)"""
            if not address or ':' not in address:
                return '', 0
            parts = address.rsplit(':', 1)
            if len(parts) != 2:
                return '', 0
            ip, port = parts
            try:
                return ip.strip(), int(port.strip())
            except ValueError:
                return ip.strip(), 0

        try:
            account_id = self.account_id_input.text().strip()
            if not account_id:
                QMessageBox.warning(self, '警告', '请输入账户ID')
                return

            account_name = self.account_name_input.text().strip()
            if not account_name:
                QMessageBox.warning(self, '警告', '请输入账户名称')
                return

            account_type = self.account_type_combo.currentText()
            institution_name = self.institution_name_input.text().strip()
            if not institution_name:
                QMessageBox.warning(self, '警告', '请输入机构名称')
                return

            institution_type = InstitutionType(self.institution_type_combo.currentText())
            trading_interface_type = TradingInterfaceType(self.trading_interface_type_combo.currentText())
            balance = self.balance_spin.value()

            md_ip, md_port = parse_address(self.xtp_md_address_input.text().strip())
            td_ip, td_port = parse_address(self.xtp_td_address_input.text().strip())

            updated_account = Account(
                account_id=account_id,
                account_name=account_name,
                account_type=account_type,
                status=self.account.status,
                balance=balance,
                available_balance=self.account.available_balance,
                frozen_balance=self.account.frozen_balance,
                market_value=self.account.market_value,
                total_assets=self.account.total_assets,
                profit_loss=self.account.profit_loss,
                profit_loss_ratio=self.account.profit_loss_ratio,
                create_time=self.account.create_time,
                update_time=datetime.now(),
                institution_name=institution_name,
                institution_type=institution_type,
                trading_interface_type=trading_interface_type,
                ctp_broker_id=self.ctp_broker_id_input.text().strip(),
                ctp_investor_id=self.ctp_investor_id_input.text().strip(),
                ctp_password=self.ctp_password_input.text(),
                ctp_trade_front=self.ctp_trade_front_input.text().strip(),
                ctp_quote_front=self.ctp_quote_front_input.text().strip(),
                ctp_app_id=self.ctp_app_id_input.text().strip(),
                ctp_auth_code=self.ctp_auth_code_input.text().strip(),
                ctp_product_info=self.ctp_product_info_input.text().strip(),
                xtp_account_id=self.xtp_account_id_input.text().strip(),
                xtp_password=self.xtp_password_input.text(),
                xtp_server_address=self.xtp_server_address_input.text().strip(),
                xtp_client_id=self.xtp_client_id_input.value(),
                xtp_software_key=self.xtp_software_key_input.text().strip(),
                xtp_md_ip=md_ip,
                xtp_md_port=md_port,
                xtp_protocol=self.xtp_protocol_combo.currentText(),
                xtp_buffer_size=self.xtp_buffer_size_input.value(),
                xtp_td_ip=td_ip,
                xtp_td_port=td_port,
                binance_api_key=self.account.binance_api_key,
                binance_secret_key=self.account.binance_secret_key,
                binance_rest_url=self.account.binance_rest_url,
                binance_ws_url=self.account.binance_ws_url,
                binance_futures_api_key=self.account.binance_futures_api_key,
                binance_futures_secret_key=self.account.binance_futures_secret_key,
                binance_futures_rest_url=self.account.binance_futures_rest_url,
                binance_futures_ws_url=self.account.binance_futures_ws_url,
                okx_api_key=self.account.okx_api_key,
                okx_secret_key=self.account.okx_secret_key,
                okx_passphrase=self.account.okx_passphrase,
                okx_rest_url=self.account.okx_rest_url,
                okx_ws_url=self.account.okx_ws_url,
                okx_futures_api_key=self.account.okx_futures_api_key,
                okx_futures_secret_key=self.account.okx_futures_secret_key,
                okx_futures_passphrase=self.account.okx_futures_passphrase,
                okx_futures_rest_url=self.account.okx_futures_rest_url,
                okx_futures_ws_url=self.account.okx_futures_ws_url,
                huobi_api_key=self.account.huobi_api_key,
                huobi_secret_key=self.account.huobi_secret_key,
                huobi_rest_url=self.account.huobi_rest_url,
                huobi_ws_url=self.account.huobi_ws_url,
                huobi_futures_api_key=self.account.huobi_futures_api_key,
                huobi_futures_secret_key=self.account.huobi_futures_secret_key,
                huobi_futures_rest_url=self.account.huobi_futures_rest_url,
                huobi_futures_ws_url=self.account.huobi_futures_ws_url,
                bitget_api_key=self.account.bitget_api_key,
                bitget_secret_key=self.account.bitget_secret_key,
                bitget_passphrase=self.account.bitget_passphrase,
                bitget_rest_url=self.account.bitget_rest_url,
                bitget_ws_url=self.account.bitget_ws_url,
                bybit_api_key=self.account.bybit_api_key,
                bybit_secret_key=self.account.bybit_secret_key,
                bybit_rest_url=self.account.bybit_rest_url,
                bybit_ws_url=self.account.bybit_ws_url
            )

            if self.account_manager.update_account(updated_account):
                QMessageBox.information(self, '成功', f'账户更新成功: {account_id}')
                self.accept()
            else:
                QMessageBox.warning(self, '失败', '账户更新失败')

        except Exception as e:
            logger.error(f"更新账户失败: {e}")
            QMessageBox.critical(self, '错误', f'更新账户失败: {str(e)}')


    def show_simnow_config_dialog(self):
        """显示SimNow快速配置对话框"""
        try:
            dialog = SimNowConfigDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                investor_id = dialog.investor_id_input.text().strip()
                password = dialog.password_input.text().strip()
                environment = dialog.environment_combo.currentData()
                account_name = dialog.account_name_input.text().strip()
                
                if not investor_id or not password:
                    QMessageBox.warning(self, "错误", "请填写SimNow账号和密码")
                    return
                
                from core.trading.simnow_config import SimNowAccountCreator
                
                account = SimNowAccountCreator.create_simnow_account(
                    investor_id=investor_id,
                    password=password,
                    environment=environment,
                    account_name=account_name
                )
                
                success = self.account_manager.add_account(account)
                
                if success:
                    QMessageBox.information(self, "成功", f"SimNow账户创建成功: {account.account_id}\n\n请前往SimNow官网激活账户后使用")
                    self.load_accounts()
                else:
                    QMessageBox.warning(self, "失败", "SimNow账户创建失败，请检查配置")
                    
        except Exception as e:
            logger.error(f"显示SimNow配置对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"显示SimNow配置对话框失败: {e}")


class SimNowConfigDialog(QDialog):
    """SimNow快速配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SimNow快速配置")
        self.setMinimumSize(500, 400)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        info_label = QLabel(
            "SimNow是上期技术提供的CTP模拟交易环境\n"
            "使用前请先在SimNow官网注册账号并激活\n"
            "官网地址: www.simnow.com.cn"
        )
        info_label.setStyleSheet("color: #666; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(info_label)
        
        form_layout = QGridLayout()
        
        row = 0
        
        form_layout.addWidget(QLabel("SimNow账号*:"), row, 0)
        self.investor_id_input = QLineEdit()
        self.investor_id_input.setPlaceholderText("在SimNow官网注册的账号")
        form_layout.addWidget(self.investor_id_input, row, 1)
        row += 1
        
        form_layout.addWidget(QLabel("密码*:"), row, 0)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("SimNow登录密码")
        form_layout.addWidget(self.password_input, row, 1)
        row += 1
        
        form_layout.addWidget(QLabel("环境:"), row, 0)
        self.environment_combo = QComboBox()
        from core.trading.simnow_config import SimNowEnvironment, SimNowEnvironmentInfo
        
        for env in SimNowEnvironment:
            info = SimNowEnvironmentInfo.get_environment_info(env)
            self.environment_combo.addItem(info.get('name', env.value), env)
        
        self.environment_combo.currentIndexChanged.connect(self._on_environment_changed)
        form_layout.addWidget(self.environment_combo, row, 1)
        row += 1
        
        self.env_info_label = QLabel()
        self.env_info_label.setWordWrap(True)
        self.env_info_label.setStyleSheet("color: #666; padding: 5px;")
        form_layout.addWidget(self.env_info_label, row, 0, 1, 2)
        row += 1
        
        form_layout.addWidget(QLabel("账户名称:"), row, 0)
        self.account_name_input = QLineEdit()
        self.account_name_input.setText("SimNow期货账户")
        form_layout.addWidget(self.account_name_input, row, 1)
        row += 1
        
        layout.addLayout(form_layout)
        
        config_label = QLabel(
            "默认配置:\n"
            "  BrokerID: 9999\n"
            "  AppID: simnow_client_test\n"
            "  AuthCode: 0000000000000000\n"
            "  初始资金: 两千万"
        )
        config_label.setStyleSheet("color: #888; padding: 10px; background-color: #fafafa; border-radius: 5px;")
        layout.addWidget(config_label)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self._on_environment_changed(0)
    
    def _on_environment_changed(self, index):
        """环境改变事件"""
        try:
            from core.trading.simnow_config import SimNowEnvironment, SimNowEnvironmentInfo
            
            env = self.environment_combo.currentData()
            info = SimNowEnvironmentInfo.get_environment_info(env)
            
            if info:
                text = f"说明: {info.get('description', '')}\n"
                text += f"交易时间: {info.get('trading_hours', '')}"
                
                notes = info.get('notes', [])
                if notes:
                    text += "\n注意事项:\n"
                    for note in notes:
                        text += f"  - {note}\n"
                
                self.env_info_label.setText(text)
                self.account_name_input.setText(f"SimNow-{info.get('name', env.value)}")
                
        except Exception as e:
            logger.error(f"环境改变事件处理失败: {e}")
