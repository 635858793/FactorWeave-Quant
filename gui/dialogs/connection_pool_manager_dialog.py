#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连接池管理主对话框

提供统一的连接池管理界面，整合以下功能：
1. 连接池列表 - 显示所有连接池的状态
2. 配置管理 - 配置连接池参数
3. 自适应配置 - 配置自适应连接池调整参数
4. 实时监控 - 监控连接池使用情况
5. 历史记录 - 查看连接池调整历史

作者: AI Assistant
日期: 2025-01-13
版本: 2.0（已集成自适应配置）
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QGroupBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QComboBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QProgressBar, QFrame,
    QSlider
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from loguru import logger

from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import deque


class ConnectionPoolListWidget(QWidget):
    """连接池列表组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database_service = None
        self._init_ui()
        self._init_service()
        self._start_refresh_timer()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("连接池列表")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh_pools)
        toolbar_layout.addWidget(self.refresh_btn)
        
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)
        
        # 连接池表格
        self.pool_table = QTableWidget()
        self.pool_table.setColumnCount(6)
        self.pool_table.setHorizontalHeaderLabels([
            "连接池名称", "数据库类型", "状态", "活跃连接", "空闲连接", "使用率"
        ])
        self.pool_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pool_table.setAlternatingRowColors(True)
        self.pool_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pool_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.pool_table)
    
    def _init_service(self):
        """初始化服务"""
        try:
            from core.containers import get_service_container
            from core.services.database_service import DatabaseService
            
            container = get_service_container()
            self.database_service = container.resolve(DatabaseService)
            logger.info("连接池列表组件已初始化")
        except Exception as e:
            logger.warning(f"初始化连接池列表组件失败: {e}")
    
    def _start_refresh_timer(self):
        """启动定时刷新"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_pools)
        self.refresh_timer.start(5000)  # 每5秒刷新一次
    
    def _refresh_pools(self):
        """刷新连接池列表"""
        if not self.database_service:
            return
        
        try:
            # 收集所有连接池信息
            pool_info_list = []
            
            # 1. DatabaseService管理的连接池
            for pool_name in self.database_service._connection_pools.keys():
                config = self.database_service._pool_configs.get(pool_name)
                metrics = self.database_service.get_pool_metrics(pool_name)
                
                pool_info_list.append({
                    'name': pool_name,
                    'config': config,
                    'metrics': metrics,
                    'source': 'DatabaseService'
                })
            
            # 2. FactorWeaveAnalyticsDB的连接池（如果存在）
            try:
                from core.database.factorweave_analytics_db import get_analytics_db
                analytics_db = get_analytics_db()
                
                if hasattr(analytics_db, 'pool') and analytics_db.pool:
                    # 获取连接池状态
                    pool_status = analytics_db.get_pool_status()
                    
                    # 检查是否已在列表中（避免重复）
                    analytics_pool_name = 'analytics_duckdb'
                    if not any(p['name'] == analytics_pool_name for p in pool_info_list):
                        pool_info_list.append({
                            'name': analytics_pool_name,
                            'config': None,  # FactorWeaveAnalyticsDB使用不同的配置方式
                            'metrics': None,  # 需要从pool_status获取
                            'source': 'FactorWeaveAnalyticsDB',
                            'pool_status': pool_status
                        })
            except Exception as e:
                logger.debug(f"无法获取FactorWeaveAnalyticsDB连接池信息: {e}")
            
            # 更新表格
            self.pool_table.setRowCount(len(pool_info_list))
            
            for row, pool_info in enumerate(pool_info_list):
                try:
                    pool_name = pool_info['name']
                    config = pool_info['config']
                    metrics = pool_info['metrics']
                    source = pool_info['source']
                    
                    # 连接池名称
                    self.pool_table.setItem(row, 0, QTableWidgetItem(pool_name))
                    
                    # 数据库类型（从配置中获取，更准确）
                    if config:
                        if config.db_type.name == "DUCKDB":
                            db_type = "DuckDB"
                        elif config.db_type.name == "SQLITE":
                            db_type = "SQLite"
                        else:
                            db_type = config.db_type.name
                    else:
                        # 回退到从名称推断
                        if "duckdb" in pool_name.lower():
                            db_type = "DuckDB"
                        elif "sqlite" in pool_name.lower():
                            db_type = "SQLite"
                        else:
                            db_type = "未知"
                    self.pool_table.setItem(row, 1, QTableWidgetItem(db_type))
                    
                    # 状态和连接信息
                    if source == 'FactorWeaveAnalyticsDB' and 'pool_status' in pool_info:
                        # 从FactorWeaveAnalyticsDB的pool_status获取信息
                        pool_status = pool_info['pool_status']
                        total = pool_status.get('pool_size', 0)
                        active = pool_status.get('checked_out', 0)
                        idle = pool_status.get('checked_in', 0)
                        
                        # 状态
                        if total == 0:
                            status = "未初始化"
                        elif active == 0:
                            status = "空闲"
                        elif active < total:
                            status = "部分使用"
                        else:
                            status = "满载"
                        self.pool_table.setItem(row, 2, QTableWidgetItem(status))
                        
                        # 活跃连接
                        self.pool_table.setItem(row, 3, QTableWidgetItem(str(active)))
                        
                        # 空闲连接
                        self.pool_table.setItem(row, 4, QTableWidgetItem(str(idle)))
                        
                        # 使用率
                        usage = active / max(total, 1)
                        usage_text = f"{usage * 100:.1f}%"
                        usage_item = QTableWidgetItem(usage_text)
                        
                        # 根据使用率设置颜色
                        if usage > 0.8:
                            usage_item.setForeground(QColor("#e74c3c"))  # 红色
                        elif usage > 0.6:
                            usage_item.setForeground(QColor("#f39c12"))  # 橙色
                        else:
                            usage_item.setForeground(QColor("#27ae60"))  # 绿色
                        
                        self.pool_table.setItem(row, 5, usage_item)
                    elif metrics:
                        # 从DatabaseService的metrics获取信息
                        total = metrics.total_connections
                        active = metrics.active_connections
                        idle = total - active
                        
                        # 状态
                        if total == 0:
                            status = "未初始化"
                        elif active == 0:
                            status = "空闲"
                        elif active < total:
                            status = "部分使用"
                        else:
                            status = "满载"
                        self.pool_table.setItem(row, 2, QTableWidgetItem(status))
                        
                        # 活跃连接
                        self.pool_table.setItem(row, 3, QTableWidgetItem(str(active)))
                        
                        # 空闲连接
                        self.pool_table.setItem(row, 4, QTableWidgetItem(str(idle)))
                        
                        # 使用率
                        usage = active / max(total, 1)
                        usage_text = f"{usage * 100:.1f}%"
                        usage_item = QTableWidgetItem(usage_text)
                        
                        # 根据使用率设置颜色
                        if usage > 0.8:
                            usage_item.setForeground(QColor("#e74c3c"))  # 红色
                        elif usage > 0.6:
                            usage_item.setForeground(QColor("#f39c12"))  # 橙色
                        else:
                            usage_item.setForeground(QColor("#27ae60"))  # 绿色
                        
                        self.pool_table.setItem(row, 5, usage_item)
                    else:
                        self.pool_table.setItem(row, 2, QTableWidgetItem("未知"))
                        self.pool_table.setItem(row, 3, QTableWidgetItem("-"))
                        self.pool_table.setItem(row, 4, QTableWidgetItem("-"))
                        self.pool_table.setItem(row, 5, QTableWidgetItem("-"))
                        
                except Exception as e:
                    logger.warning(f"获取连接池 {pool_info['name']} 指标失败: {e}")
                    
        except Exception as e:
            logger.error(f"刷新连接池列表失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        event.accept()


class ConnectionPoolConfigWidget(QWidget):
    """连接池配置组件（简化版）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = None
        self.db = None
        self._init_db()
        self.init_ui()
        self.load_config()
    
    def _init_db(self):
        """初始化数据库和配置管理器"""
        try:
            from core.database.factorweave_analytics_db import FactorWeaveAnalyticsDB
            self.db = FactorWeaveAnalyticsDB()
            self.config_manager = self.db.config_manager
            logger.info("连接池配置组件已初始化")
        except Exception as e:
            logger.error(f"初始化连接池配置组件失败: {e}")
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("连接池配置")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)
        
        # 手动配置设置
        config_group = QGroupBox("手动配置")
        config_layout = QFormLayout()
        config_layout.setSpacing(10)

        # 连接池大小
        self.pool_size_slider = QSlider(Qt.Horizontal)
        self.pool_size_slider.setRange(1, 50)
        self.pool_size_slider.setValue(5)
        self.pool_size_label = QLabel("5")
        pool_layout = QHBoxLayout()
        pool_layout.addWidget(self.pool_size_slider, 1)
        pool_layout.addWidget(self.pool_size_label)
        pool_size_desc = QLabel("初始连接数量，建议5-20")
        pool_size_desc.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        pool_size_desc.setWordWrap(True)
        config_layout.addRow("连接池大小 (1-50):", pool_layout)
        config_layout.addRow("", pool_size_desc)

        # 最大溢出
        self.max_overflow_slider = QSlider(Qt.Horizontal)
        self.max_overflow_slider.setRange(0, 100)
        self.max_overflow_slider.setValue(10)
        self.max_overflow_label = QLabel("10")
        overflow_layout = QHBoxLayout()
        overflow_layout.addWidget(self.max_overflow_slider, 1)
        overflow_layout.addWidget(self.max_overflow_label)
        overflow_desc = QLabel("额外可创建的连接数量，高峰期使用")
        overflow_desc.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        overflow_desc.setWordWrap(True)
        config_layout.addRow("最大溢出 (0-100):", overflow_layout)
        config_layout.addRow("", overflow_desc)

        # 超时时间
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 300.0)
        self.timeout_spin.setValue(30.0)
        self.timeout_spin.setSuffix(" 秒")
        timeout_desc = QLabel("获取连接的最长等待时间，超时则报错")
        timeout_desc.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        timeout_desc.setWordWrap(True)
        config_layout.addRow("获取连接超时:", self.timeout_spin)
        config_layout.addRow("", timeout_desc)

        # 回收时间
        self.recycle_spin = QSpinBox()
        self.recycle_spin.setRange(60, 86400)
        self.recycle_spin.setValue(3600)
        self.recycle_spin.setSuffix(" 秒")
        recycle_desc = QLabel("连接回收周期，防止长期连接失效")
        recycle_desc.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        recycle_desc.setWordWrap(True)
        config_layout.addRow("连接回收时间:", self.recycle_spin)
        config_layout.addRow("", recycle_desc)

        # 内存限制
        self.memory_spin = QDoubleSpinBox()
        self.memory_spin.setRange(0, 128)
        self.memory_spin.setValue(0)
        self.memory_spin.setSpecialValueText("自动")
        self.memory_spin.setSuffix(" GB")
        memory_desc = QLabel("DuckDB内存使用上限，0表示自动管理")
        memory_desc.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        memory_desc.setWordWrap(True)
        config_layout.addRow("内存限制:", self.memory_spin)
        config_layout.addRow("", memory_desc)

        # 线程数
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 32)
        self.threads_spin.setValue(0)
        self.threads_spin.setSpecialValueText("自动")
        threads_desc = QLabel("并行查询线程数，0表示使用CPU核心数")
        threads_desc.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        threads_desc.setWordWrap(True)
        config_layout.addRow("线程数:", self.threads_spin)
        config_layout.addRow("", threads_desc)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("应用配置")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_config)
        button_layout.addWidget(self.apply_btn)
        
        self.reset_btn = QPushButton("重置默认")
        self.reset_btn.clicked.connect(self.reset_config)
        button_layout.addWidget(self.reset_btn)
        
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self.refresh_status)
        button_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(button_layout)
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def load_config(self):
        """加载当前配置"""
        if not self.config_manager:
            return
        
        try:
            from core.database.connection_pool_config import ConnectionPoolConfig
            pool_config = self.config_manager.load_pool_config()
            
            self.pool_size_slider.setValue(pool_config.pool_size)
            self.max_overflow_slider.setValue(pool_config.max_overflow)
            self.timeout_spin.setValue(pool_config.timeout)
            self.recycle_spin.setValue(pool_config.pool_recycle)
            
            opt_config = self.config_manager.load_optimization_config()
            self.memory_spin.setValue(opt_config.memory_limit_gb or 0)
            self.threads_spin.setValue(opt_config.threads or 0)
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
    
    def refresh_status(self):
        """刷新当前状态"""
        if not self.db:
            return
        
        try:
            status = self.db.get_pool_status()
            pool_size = status.get('pool_size', 'N/A')
            checked_out = status.get('checked_out', 0)
            self.status_label.setText(f"当前状态: 池大小={pool_size}, 活跃连接={checked_out}")
        except Exception as e:
            logger.error(f"刷新状态失败: {e}")
    
    def apply_config(self):
        """应用配置"""
        if not self.config_manager or not self.db:
            QMessageBox.warning(self, "错误", "配置管理器未初始化")
            return
        
        try:
            from core.database.connection_pool_config import (
                ConnectionPoolConfig,
                DuckDBOptimizationConfig
            )
            
            pool_config = ConnectionPoolConfig(
                pool_size=self.pool_size_slider.value(),
                max_overflow=self.max_overflow_slider.value(),
                timeout=self.timeout_spin.value(),
                pool_recycle=self.recycle_spin.value()
            )
            
            valid, msg = pool_config.validate()
            if not valid:
                QMessageBox.warning(self, "配置错误", msg)
                return
            
            self.config_manager.save_pool_config(pool_config)
            
            opt_config = DuckDBOptimizationConfig(
                memory_limit_gb=self.memory_spin.value() or None,
                threads=self.threads_spin.value() or None
            )
            self.config_manager.save_optimization_config(opt_config)
            
            if self.db.reload_pool(pool_config):
                self.status_label.setText("配置已成功应用！")
                QMessageBox.information(self, "成功", "连接池配置已更新并立即生效！")
            else:
                self.status_label.setText("应用失败: 热重载失败")
                QMessageBox.critical(self, "应用失败", "连接池热重载失败")
                
        except Exception as e:
            logger.error(f"应用配置失败: {e}")
            self.status_label.setText(f"错误: {str(e)}")
            QMessageBox.critical(self, "错误", f"应用配置失败:\n{str(e)}")
    
    def reset_config(self):
        """重置为默认配置"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置为默认配置吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from core.database.connection_pool_config import ConnectionPoolConfig
                default_config = ConnectionPoolConfig()
                
                if self.config_manager:
                    self.config_manager.save_pool_config(default_config)
                
                if self.db and self.db.reload_pool(default_config):
                    self.load_config()
                    self.status_label.setText("已重置为默认配置")
                    QMessageBox.information(self, "重置成功", "已重置为默认配置并立即生效")
            except Exception as e:
                logger.error(f"重置配置失败: {e}")
                QMessageBox.critical(self, "错误", f"重置失败:\n{str(e)}")


class ConnectionPoolHistoryWidget(QWidget):
    """连接池历史记录组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_data = deque(maxlen=1000)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("连接池调整历史")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.clicked.connect(self._clear_history)
        toolbar_layout.addWidget(self.clear_btn)
        
        self.export_csv_btn = QPushButton("导出CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        toolbar_layout.addWidget(self.export_csv_btn)
        
        self.export_json_btn = QPushButton("导出JSON")
        self.export_json_btn.clicked.connect(self._export_json)
        toolbar_layout.addWidget(self.export_json_btn)
        
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)
        
        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "连接池", "调整前", "调整后", "原因"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.history_table)
    
    def add_record(self, pool_name: str, old_size: int, new_size: int, reason: str):
        """添加记录"""
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pool_name": pool_name,
            "old_size": old_size,
            "new_size": new_size,
            "reason": reason
        }
        self.history_data.append(record)
        
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        
        # 时间
        self.history_table.setItem(row, 0, QTableWidgetItem(record["time"]))
        
        # 连接池名称
        self.history_table.setItem(row, 1, QTableWidgetItem(pool_name))
        
        # 调整前
        self.history_table.setItem(row, 2, QTableWidgetItem(str(old_size)))
        
        # 调整后
        new_item = QTableWidgetItem(str(new_size))
        if new_size > old_size:
            new_item.setForeground(QColor("#27ae60"))  # 绿色（扩容）
        else:
            new_item.setForeground(QColor("#e74c3c"))  # 红色（缩容）
        self.history_table.setItem(row, 3, new_item)
        
        # 原因
        self.history_table.setItem(row, 4, QTableWidgetItem(reason))
    
    def _clear_history(self):
        """清空历史"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有历史记录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.history_data.clear()
            self.history_table.setRowCount(0)
    
    def _export_csv(self):
        """导出CSV"""
        try:
            import csv
            
            filename = f"connection_pool_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["时间", "连接池", "调整前", "调整后", "原因"])
                
                for record in self.history_data:
                    writer.writerow([
                        record["time"],
                        record["pool_name"],
                        record["old_size"],
                        record["new_size"],
                        record["reason"]
                    ])
            
            QMessageBox.information(self, "导出成功", f"历史记录已导出到 {filename}")
            
        except Exception as e:
            logger.error(f"导出CSV失败: {e}")
            QMessageBox.critical(self, "导出失败", f"导出CSV失败: {str(e)}")
    
    def _export_json(self):
        """导出JSON"""
        try:
            import json
            
            filename = f"connection_pool_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(list(self.history_data), f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "导出成功", f"历史记录已导出到 {filename}")
            
        except Exception as e:
            logger.error(f"导出JSON失败: {e}")
            QMessageBox.critical(self, "导出失败", f"导出JSON失败: {str(e)}")


class ConnectionPoolManagerDialog(QDialog):
    """连接池管理主对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("连接池管理")
        self.setMinimumSize(900, 600)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 创建TabWidget
        self.tab_widget = QTabWidget()
        
        # Tab1: 连接池列表
        self.list_widget = ConnectionPoolListWidget()
        self.tab_widget.addTab(self.list_widget, "连接池列表")
        
        # Tab2: 配置管理
        self.config_widget = ConnectionPoolConfigWidget()
        self.tab_widget.addTab(self.config_widget, "配置管理")
        
        # Tab3: 自适应配置（新增）
        self._init_adaptive_config_tab()
        
        # Tab4: 实时监控
        self._init_monitor_tab()
        
        # Tab5: 历史记录
        self.history_widget = ConnectionPoolHistoryWidget()
        self.tab_widget.addTab(self.history_widget, "历史记录")
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _init_adaptive_config_tab(self):
        """初始化自适应配置Tab"""
        try:
            from gui.widgets.adaptive_pool_config_widget_v2 import AdaptivePoolConfigWidget
            self.adaptive_config_widget = AdaptivePoolConfigWidget()
            self.tab_widget.addTab(self.adaptive_config_widget, "自适应配置")
        except Exception as e:
            logger.warning(f"加载自适应配置组件失败: {e}")
            
            # 创建占位界面
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            
            status_group = QGroupBox("自适应配置")
            status_layout = QFormLayout(status_group)
            
            status_label = QLabel("自适应配置组件加载失败")
            status_layout.addRow("状态:", status_label)
            
            placeholder_layout.addWidget(status_group)
            placeholder_layout.addStretch()
            
            self.tab_widget.addTab(placeholder, "自适应配置")
    
    def _init_monitor_tab(self):
        """初始化监控Tab"""
        try:
            from gui.widgets.adaptive_pool_monitor_widget import AdaptivePoolMonitorWidget
            self.monitor_widget = AdaptivePoolMonitorWidget()
            self.tab_widget.addTab(self.monitor_widget, "实时监控")
        except Exception as e:
            logger.warning(f"加载监控组件失败: {e}")
            
            # 创建占位监控界面
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            
            status_group = QGroupBox("监控状态")
            status_layout = QFormLayout(status_group)
            
            self.monitor_status_label = QLabel("监控服务未启用")
            status_layout.addRow("状态:", self.monitor_status_label)
            
            placeholder_layout.addWidget(status_group)
            placeholder_layout.addStretch()
            
            self.tab_widget.addTab(placeholder, "实时监控")
    
    def closeEvent(self, event):
        """关闭事件"""
        event.accept()


def show_connection_pool_manager(parent=None):
    """显示连接池管理对话框"""
    dialog = ConnectionPoolManagerDialog(parent)
    return dialog.exec_()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    dialog = ConnectionPoolManagerDialog()
    dialog.show()
    
    sys.exit(app.exec_())
