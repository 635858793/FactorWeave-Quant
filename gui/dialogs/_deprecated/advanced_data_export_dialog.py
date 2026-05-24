#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级数据导出对话框

【已废弃 - DEPRECATED】

此文件已被新的统一数据管理对话框替代：
- 新文件：data_management_dialog_unified.py
- 新类：UnifiedDataManagementDialog

本文件保留仅用于向后兼容性，将在未来版本中删除。
建议迁移到新的统一数据管理对话框。

原有功能：
- 高级数据导出功能
- 支持多种导出格式（Excel、CSV、JSON、Parquet）
- 数据预览和导出历史

作者: FactorWeave-Quant团队
版本: 1.0 (已废弃)
废弃日期: 2026-05-13
"""

import warnings
warnings.warn(
    "AdvancedDataExportDialog is deprecated and will be removed in a future version. "
    "Use UnifiedDataManagementDialog from data_management_dialog_unified.py instead.",
    DeprecationWarning,
    stacklevel=2
)

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton, QGroupBox,
    QMessageBox, QProgressBar, QFileDialog, QTextEdit, QSpinBox, QWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from loguru import logger
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from .base_dialog import BaseDialog

class DataExportThread(QThread):
    """数据导出线程"""
    
    progress_updated = pyqtSignal(int, str)
    export_completed = pyqtSignal(str)
    export_failed = pyqtSignal(str)
    
    def __init__(self, data: pd.DataFrame, export_config: Dict[str, Any]):
        super().__init__()
        self.data = data
        self.export_config = export_config
    
    def run(self):
        """执行导出"""
        try:
            self.progress_updated.emit(10, "准备导出数据...")
            
            export_format = self.export_config['format']
            file_path = self.export_config['file_path']
            
            self.progress_updated.emit(30, f"导出为{export_format}格式...")
            
            if export_format == 'Excel':
                self.data.to_excel(file_path, index=False)
            elif export_format == 'CSV':
                self.data.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif export_format == 'JSON':
                self.data.to_json(file_path, orient='records', date_format='iso')
            elif export_format == 'Parquet':
                self.data.to_parquet(file_path)
            
            self.progress_updated.emit(90, "完成导出...")
            self.export_completed.emit(file_path)
            
        except Exception as e:
            self.export_failed.emit(str(e))

class AdvancedDataExportDialog(BaseDialog):
    """高级数据导出对话框"""
    
    def __init__(self, data: Optional[pd.DataFrame] = None, parent=None):
        super().__init__(
            parent,
            title="高级数据导出",
            min_size=(600, 500),
            settings_key="AdvancedDataExportDialog"
        )
        self.data = data
        self.export_thread = None
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        
        layout = QVBoxLayout(self)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 导出设置标签页
        export_tab = self._create_export_settings_tab()
        tab_widget.addTab(export_tab, "导出设置")
        
        # 数据预览标签页
        preview_tab = self._create_data_preview_tab()
        tab_widget.addTab(preview_tab, "数据预览")
        
        # 导出历史标签页
        history_tab = self._create_export_history_tab()
        tab_widget.addTab(history_tab, "导出历史")
        
        layout.addWidget(tab_widget)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("开始导出")
        self.export_btn.clicked.connect(self.start_export)
        button_layout.addWidget(self.export_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def _create_export_settings_tab(self):
        """创建导出设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 格式选择
        format_group = QGroupBox("导出格式")
        format_layout = QGridLayout(format_group)
        
        format_layout.addWidget(QLabel("文件格式:"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(['Excel', 'CSV', 'JSON', 'Parquet'])
        format_layout.addWidget(self.format_combo, 0, 1)
        
        format_layout.addWidget(QLabel("文件路径:"), 1, 0)
        self.file_path_edit = QLineEdit()
        format_layout.addWidget(self.file_path_edit, 1, 1)
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_file_path)
        format_layout.addWidget(self.browse_btn, 1, 2)
        
        layout.addWidget(format_group)
        
        # 数据选择
        data_group = QGroupBox("数据选择")
        data_layout = QGridLayout(data_group)
        
        self.include_index_cb = QCheckBox("包含索引")
        data_layout.addWidget(self.include_index_cb, 0, 0)
        
        self.include_header_cb = QCheckBox("包含列标题")
        self.include_header_cb.setChecked(True)
        data_layout.addWidget(self.include_header_cb, 0, 1)
        
        data_layout.addWidget(QLabel("行数限制:"), 1, 0)
        self.row_limit_spin = QSpinBox()
        self.row_limit_spin.setRange(0, 1000000)
        self.row_limit_spin.setValue(0)  # 0表示无限制
        self.row_limit_spin.setSpecialValueText("无限制")
        data_layout.addWidget(self.row_limit_spin, 1, 1)
        
        layout.addWidget(data_group)
        
        layout.addStretch()
        return tab
    
    def _create_data_preview_tab(self):
        """创建数据预览标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 数据信息
        info_group = QGroupBox("数据信息")
        info_layout = QGridLayout(info_group)
        
        self.data_shape_label = QLabel("形状: 未加载")
        info_layout.addWidget(self.data_shape_label, 0, 0)
        
        self.data_size_label = QLabel("大小: 未知")
        info_layout.addWidget(self.data_size_label, 0, 1)
        
        layout.addWidget(info_group)
        
        # 数据预览
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
        
        # 更新预览
        self._update_data_preview()
        
        layout.addStretch()
        return tab
    
    def _create_export_history_tab(self):
        """创建导出历史标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        history_group = QGroupBox("最近导出")
        history_layout = QVBoxLayout(history_group)
        
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setPlainText("暂无导出历史")
        history_layout.addWidget(self.history_text)
        
        layout.addWidget(history_group)
        
        return tab
    
    def _update_data_preview(self):
        """更新数据预览"""
        if self.data is not None:
            shape_text = f"形状: {self.data.shape[0]} 行 × {self.data.shape[1]} 列"
            self.data_shape_label.setText(shape_text)
            
            # 估算数据大小
            size_mb = self.data.memory_usage(deep=True).sum() / 1024 / 1024
            size_text = f"大小: {size_mb:.2f} MB"
            self.data_size_label.setText(size_text)
            
            # 显示前几行数据
            preview_data = self.data.head(10).to_string()
            self.preview_text.setPlainText(preview_data)
        else:
            self.data_shape_label.setText("形状: 未加载")
            self.data_size_label.setText("大小: 未知")
            self.preview_text.setPlainText("无数据可预览")
    
    def browse_file_path(self):
        """浏览文件路径"""
        format_name = self.format_combo.currentText()
        extensions = {
            'Excel': '*.xlsx',
            'CSV': '*.csv',
            'JSON': '*.json',
            'Parquet': '*.parquet'
        }
        
        file_filter = f"{format_name} 文件 ({extensions[format_name]})"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"保存{format_name}文件", 
            f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extensions[format_name][2:]}",
            file_filter
        )
        
        if file_path:
            self.file_path_edit.setText(file_path)
    
    def start_export(self):
        """开始导出"""
        if self.data is None:
            QMessageBox.warning(self, "错误", "没有可导出的数据")
            return
        
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "错误", "请选择导出文件路径")
            return
        
        # 准备导出配置
        export_config = {
            'format': self.format_combo.currentText(),
            'file_path': file_path,
            'include_index': self.include_index_cb.isChecked(),
            'include_header': self.include_header_cb.isChecked(),
            'row_limit': self.row_limit_spin.value()
        }
        
        # 处理行数限制
        export_data = self.data
        if export_config['row_limit'] > 0:
            export_data = self.data.head(export_config['row_limit'])
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.export_btn.setEnabled(False)
        
        # 开始导出线程
        self.export_thread = DataExportThread(export_data, export_config)
        self.export_thread.progress_updated.connect(self._on_progress_updated)
        self.export_thread.export_completed.connect(self._on_export_completed)
        self.export_thread.export_failed.connect(self._on_export_failed)
        self.export_thread.start()
    
    def _on_progress_updated(self, progress: int, message: str):
        """进度更新回调"""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)
    
    def _on_export_completed(self, file_path: str):
        """导出完成回调"""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.export_btn.setEnabled(True)
        
        QMessageBox.information(self, "成功", f"数据已成功导出到: {file_path}")
        self.accept()
    
    def _on_export_failed(self, error: str):
        """导出失败回调"""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.export_btn.setEnabled(True)
        
        QMessageBox.critical(self, "错误", f"导出失败: {error}")
    
    def set_data(self, data: pd.DataFrame):
        """设置要导出的数据"""
        self.data = data
        self._update_data_preview()

def show_advanced_export_dialog(data: pd.DataFrame = None, parent=None):
    """显示高级数据导出对话框"""
    dialog = AdvancedDataExportDialog(data, parent)
    return dialog.exec_()
