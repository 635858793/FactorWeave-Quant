#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能模型选择对话框

提供完整的智能模型选择功能界面，包括：
- 模型选择控制
- 增强评估功能
- 可视化功能
- 性能监控
"""

import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QWidget, QPushButton, QLabel,
    QGroupBox, QFileDialog, QMessageBox, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QProgressBar, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont

from core.ai.intelligent_selection import IntelligentModelSelector
from gui.widgets.intelligent_model_selection.control_panel import IntelligentModelControlPanel
from gui.widgets.intelligent_model_selection.performance_panel import ModelPerformancePanel

from core.containers import get_service_container
from core.services.unified_data_manager import get_unified_data_manager
from core.services.ai_prediction_service import AIPredictionService
from core.services.prediction_tracking_service import PredictionTrackingService

logger = logging.getLogger(__name__)


class EnhancedEvaluationWorker(QThread):
    """增强评估工作线程"""
    
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str, int)
    error = pyqtSignal(str)
    
    def __init__(self, selector: IntelligentModelSelector, model_type: str,
                 y_true, y_pred, y_pred_proba=None, task_type='classification'):
        super().__init__()
        self.selector = selector
        self.model_type = model_type
        self.y_true = y_true
        self.y_pred = y_pred
        self.y_pred_proba = y_pred_proba
        self.task_type = task_type
    
    def run(self):
        """执行评估"""
        try:
            self.progress.emit("开始增强评估...", 10)
            
            # 执行增强评估
            performance = self.selector.evaluate_model_performance_enhanced(
                model_type=self.model_type,
                y_true=self.y_true,
                y_pred=self.y_pred,
                y_pred_proba=self.y_pred_proba,
                task_type=self.task_type
            )
            
            self.progress.emit("评估完成", 100)
            
            self.finished.emit({
                'performance': performance,
                'model_type': self.model_type,
                'task_type': self.task_type
            })
            
        except Exception as e:
            logger.error(f"增强评估失败: {e}")
            self.error.emit(str(e))


class VisualizationWorker(QThread):
    """可视化工作线程"""
    
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str, int)
    error = pyqtSignal(str)
    
    def __init__(self, selector: IntelligentModelSelector, model_type: str,
                 y_true, y_pred, y_pred_proba=None, task_type='classification',
                 save_dir=None, feature_names=None, feature_importance=None):
        super().__init__()
        self.selector = selector
        self.model_type = model_type
        self.y_true = y_true
        self.y_pred = y_pred
        self.y_pred_proba = y_pred_proba
        self.task_type = task_type
        self.save_dir = save_dir
        self.feature_names = feature_names
        self.feature_importance = feature_importance
    
    def run(self):
        """执行可视化"""
        try:
            self.progress.emit("开始生成可视化图表...", 10)
            
            # 执行可视化
            chart_paths = self.selector.visualize_model_performance(
                model_type=self.model_type,
                y_true=self.y_true,
                y_pred=self.y_pred,
                y_pred_proba=self.y_pred_proba,
                task_type=self.task_type,
                save_dir=self.save_dir,
                feature_names=self.feature_names,
                feature_importance=self.feature_importance
            )
            
            self.progress.emit("可视化完成", 100)
            
            self.finished.emit({
                'chart_paths': chart_paths,
                'model_type': self.model_type,
                'task_type': self.task_type
            })
            
        except Exception as e:
            logger.error(f"可视化失败: {e}")
            self.error.emit(str(e))


class IntelligentModelSelectionDialog(QDialog):
    """智能模型选择对话框"""
    
    def __init__(self, parent=None, service_container=None):
        super().__init__(parent)
        self.service_container = service_container or get_service_container()
        self.intelligent_selector = None
        self.evaluation_worker = None
        self.visualization_worker = None
        
        # 获取系统服务
        self.data_manager = get_unified_data_manager()
        self.ai_prediction_service = None
        self.prediction_tracking_service = None
        
        self.init_ui()
        self.setup_connections()
        self.initialize_services()
        self.initialize_selector()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("智能模型选择 - 增强评估与可视化")
        self.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 1. 控制面板选项卡
        control_tab = self._create_control_tab()
        self.tab_widget.addTab(control_tab, "🎛️ 控制面板")
        
        # 2. 增强评估选项卡
        evaluation_tab = self._create_evaluation_tab()
        self.tab_widget.addTab(evaluation_tab, "📊 增强评估")
        
        # 3. 可视化选项卡
        visualization_tab = self._create_visualization_tab()
        self.tab_widget.addTab(visualization_tab, "📈 可视化")
        
        # 4. 性能监控选项卡
        performance_tab = self._create_performance_tab()
        self.tab_widget.addTab(performance_tab, "📉 性能监控")
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.setMinimumWidth(100)
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        # 应用样式
        self._apply_styles()
    
    def _create_control_tab(self) -> QWidget:
        """创建控制面板选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 创建控制面板
        self.control_panel = IntelligentModelControlPanel()
        layout.addWidget(self.control_panel)
        
        return tab
    
    def _create_evaluation_tab(self) -> QWidget:
        """创建增强评估选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 评估配置区域
        config_group = QGroupBox("评估配置")
        config_layout = QGridLayout(config_group)
        
        # 股票代码选择
        config_layout.addWidget(QLabel("股票代码:"), 0, 0)
        self.stock_code_edit = QLineEdit()
        self.stock_code_edit.setPlaceholderText("输入股票代码，如: 000001")
        self.stock_code_edit.setText("000001")
        config_layout.addWidget(self.stock_code_edit, 0, 1)
        
        # 周期选择
        config_layout.addWidget(QLabel("K线周期:"), 1, 0)
        self.period_combo = QComboBox()
        self.period_combo.addItems(["D", "W", "M", "1", "5", "15", "30", "60"])
        self.period_combo.setCurrentText("D")
        config_layout.addWidget(self.period_combo, 1, 1)
        
        # 数据条数
        config_layout.addWidget(QLabel("数据条数:"), 2, 0)
        self.data_count_spin = QSpinBox()
        self.data_count_spin.setRange(100, 5000)
        self.data_count_spin.setValue(500)
        self.data_count_spin.setSuffix(" 条")
        config_layout.addWidget(self.data_count_spin, 2, 1)
        
        # 模型类型选择
        config_layout.addWidget(QLabel("模型类型:"), 3, 0)
        self.model_type_combo = QComboBox()
        self.model_type_combo.addItems([
            "xgboost", "random_forest", "lstm", "gru",
            "linear_regression", "ensemble"
        ])
        self.model_type_combo.setCurrentText("xgboost")
        config_layout.addWidget(self.model_type_combo, 3, 1)
        
        # 任务类型选择
        config_layout.addWidget(QLabel("任务类型:"), 4, 0)
        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems(["classification", "regression"])
        self.task_type_combo.setCurrentText("classification")
        config_layout.addWidget(self.task_type_combo, 4, 1)
        
        layout.addWidget(config_group)
        
        # 评估按钮
        eval_button_layout = QHBoxLayout()
        self.evaluate_btn = QPushButton("🚀 开始增强评估")
        self.evaluate_btn.setMinimumHeight(40)
        self.evaluate_btn.clicked.connect(self._on_evaluate)
        eval_button_layout.addWidget(self.evaluate_btn)
        layout.addLayout(eval_button_layout)
        
        # 进度条
        self.eval_progress = QProgressBar()
        self.eval_progress.setVisible(False)
        layout.addWidget(self.eval_progress)
        
        # 评估结果区域
        result_group = QGroupBox("评估结果")
        result_layout = QVBoxLayout(result_group)
        
        self.eval_result_text = QLabel("等待评估...")
        self.eval_result_text.setAlignment(Qt.AlignTop)
        self.eval_result_text.setStyleSheet("""
            QLabel {
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f9f9f9;
                font-family: Consolas, monospace;
            }
        """)
        self.eval_result_text.setMinimumHeight(200)
        result_layout.addWidget(self.eval_result_text)
        
        layout.addWidget(result_group)
        
        return tab
    
    def _create_visualization_tab(self) -> QWidget:
        """创建可视化选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 可视化配置区域
        config_group = QGroupBox("可视化配置")
        config_layout = QGridLayout(config_group)
        
        # 股票代码选择
        config_layout.addWidget(QLabel("股票代码:"), 0, 0)
        self.viz_stock_code_edit = QLineEdit()
        self.viz_stock_code_edit.setPlaceholderText("输入股票代码，如: 000001")
        self.viz_stock_code_edit.setText("000001")
        config_layout.addWidget(self.viz_stock_code_edit, 0, 1)
        
        # 周期选择
        config_layout.addWidget(QLabel("K线周期:"), 1, 0)
        self.viz_period_combo = QComboBox()
        self.viz_period_combo.addItems(["D", "W", "M", "1", "5", "15", "30", "60"])
        self.viz_period_combo.setCurrentText("D")
        config_layout.addWidget(self.viz_period_combo, 1, 1)
        
        # 数据条数
        config_layout.addWidget(QLabel("数据条数:"), 2, 0)
        self.viz_data_count_spin = QSpinBox()
        self.viz_data_count_spin.setRange(100, 5000)
        self.viz_data_count_spin.setValue(500)
        self.viz_data_count_spin.setSuffix(" 条")
        config_layout.addWidget(self.viz_data_count_spin, 2, 1)
        
        # 模型类型选择
        config_layout.addWidget(QLabel("模型类型:"), 3, 0)
        self.viz_model_type_combo = QComboBox()
        self.viz_model_type_combo.addItems([
            "xgboost", "random_forest", "lstm", "gru",
            "linear_regression", "ensemble"
        ])
        self.viz_model_type_combo.setCurrentText("xgboost")
        config_layout.addWidget(self.viz_model_type_combo, 3, 1)
        
        # 任务类型选择
        config_layout.addWidget(QLabel("任务类型:"), 4, 0)
        self.viz_task_type_combo = QComboBox()
        self.viz_task_type_combo.addItems(["classification", "regression"])
        self.viz_task_type_combo.setCurrentText("classification")
        config_layout.addWidget(self.viz_task_type_combo, 4, 1)
        
        # 保存目录
        config_layout.addWidget(QLabel("保存目录:"), 5, 0)
        self.save_dir_edit = QLabel("未选择")
        self.save_dir_edit.setStyleSheet("""
            QLabel {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
        """)
        config_layout.addWidget(self.save_dir_edit, 5, 1)
        
        self.browse_dir_btn = QPushButton("📁 浏览")
        self.browse_dir_btn.clicked.connect(self._on_browse_directory)
        config_layout.addWidget(self.browse_dir_btn, 5, 2)
        
        layout.addWidget(config_group)
        
        # 可视化按钮
        viz_button_layout = QHBoxLayout()
        self.visualize_btn = QPushButton("📊 生成可视化图表")
        self.visualize_btn.setMinimumHeight(40)
        self.visualize_btn.clicked.connect(self._on_visualize)
        viz_button_layout.addWidget(self.visualize_btn)
        layout.addLayout(viz_button_layout)
        
        # 进度条
        self.viz_progress = QProgressBar()
        self.viz_progress.setVisible(False)
        layout.addWidget(self.viz_progress)
        
        # 可视化结果区域
        result_group = QGroupBox("可视化结果")
        result_layout = QVBoxLayout(result_group)
        
        self.viz_result_text = QLabel("等待生成可视化图表...")
        self.viz_result_text.setAlignment(Qt.AlignTop)
        self.viz_result_text.setStyleSheet("""
            QLabel {
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f9f9f9;
                font-family: Consolas, monospace;
            }
        """)
        self.viz_result_text.setMinimumHeight(200)
        result_layout.addWidget(self.viz_result_text)
        
        layout.addWidget(result_group)
        
        return tab
    
    def _create_performance_tab(self) -> QWidget:
        """创建性能监控选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 创建性能面板
        self.performance_panel = ModelPerformancePanel()
        layout.addWidget(self.performance_panel)
        
        return tab
    
    def _apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background: white;
            }
            QTabBar::tab {
                background: #e1e1e1;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #007bff;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin: 8px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
                font-weight: bold;
            }
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                background-color: #3498db;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
            }
            QSpinBox, QDoubleSpinBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
            }
        """)
    
    def setup_connections(self):
        """设置信号连接"""
        pass
    
    def initialize_services(self):
        """初始化系统服务"""
        try:
            # 获取AI预测服务
            if self.service_container:
                try:
                    from core.services.ai_prediction_service import AIPredictionService
                    if self.service_container.is_registered(AIPredictionService):
                        self.ai_prediction_service = self.service_container.resolve(AIPredictionService)
                        logger.info("AI预测服务初始化成功")
                except Exception as e:
                    logger.warning(f"AI预测服务初始化失败: {e}")
            
            # 获取预测跟踪服务
            if self.service_container:
                try:
                    from core.services.prediction_tracking_service import PredictionTrackingService
                    if self.service_container.is_registered(PredictionTrackingService):
                        self.prediction_tracking_service = self.service_container.resolve(PredictionTrackingService)
                        logger.info("预测跟踪服务初始化成功")
                except Exception as e:
                    logger.warning(f"预测跟踪服务初始化失败: {e}")
            
            logger.info("系统服务初始化完成")
            
        except Exception as e:
            logger.error(f"系统服务初始化失败: {e}")
    
    def initialize_selector(self):
        """初始化智能选择器"""
        try:
            self.intelligent_selector = IntelligentModelSelector()
            self.control_panel.set_intelligent_selector(self.intelligent_selector)
            logger.info("智能选择器初始化成功")
        except Exception as e:
            logger.error(f"智能选择器初始化失败: {e}")
            QMessageBox.warning(self, "警告", f"智能选择器初始化失败: {str(e)}")
    
    def _prepare_evaluation_data(self, stock_code: str, period: str, count: int, task_type: str):
        """
        准备评估数据
        
        Args:
            stock_code: 股票代码
            period: K线周期
            count: 数据条数
            task_type: 任务类型
            
        Returns:
            (y_true, y_pred, y_pred_proba) 元组
        """
        try:
            import numpy as np
            import pandas as pd
            
            # 从UnifiedDataManager获取K线数据
            if self.data_manager:
                kdata = self.data_manager.get_kdata(stock_code, period, count)
                
                if kdata is None or kdata.empty:
                    logger.warning(f"无法获取股票 {stock_code} 的K线数据")
                    return None, None, None
                
                logger.info(f"成功获取 {stock_code} 的K线数据，记录数: {len(kdata)}")
                
                # 使用AI预测服务生成预测结果
                if self.ai_prediction_service:
                    try:
                        # 根据任务类型选择预测方法
                        if task_type == 'classification':
                            # 使用趋势预测（分类任务）
                            trend_result = self.ai_prediction_service.predict_trend(kdata, timeframe=5)
                            
                            if trend_result:
                                # 生成真实标签和预测标签
                                # 这里使用简单的逻辑：如果价格上涨则为1，否则为0
                                if 'close' in kdata.columns:
                                    price_change = kdata['close'].pct_change().dropna()
                                    y_true = (price_change > 0).astype(int).values
                                    
                                    # 使用预测结果
                                    direction = trend_result.get('direction', '震荡')
                                    confidence = trend_result.get('confidence', 0.5)
                                    
                                    # 将方向转换为预测标签
                                    if direction == '上涨':
                                        prediction_label = 1
                                    elif direction == '下跌':
                                        prediction_label = 0
                                    else:
                                        # 震荡时使用置信度决定
                                        prediction_label = 1 if confidence > 0.5 else 0
                                    
                                    y_pred = np.array([prediction_label] * len(y_true))
                                    
                                    # 生成预测概率（基于置信度）
                                    y_pred_proba = np.full(len(y_true), confidence)
                                    
                                    # 确保长度一致
                                    min_len = min(len(y_true), len(y_pred))
                                    y_true = y_true[:min_len]
                                    y_pred = y_pred[:min_len]
                                    y_pred_proba = y_pred_proba[:min_len]
                                    
                                    logger.info(f"分类数据准备完成: y_true={len(y_true)}, y_pred={len(y_pred)}, direction={direction}, confidence={confidence}")
                                    return y_true, y_pred, y_pred_proba
                        else:
                            # 使用价格预测（回归任务）
                            price_result = self.ai_prediction_service.predict_price(kdata, horizon=5)
                            
                            if price_result:
                                # 生成真实标签和预测标签
                                if 'close' in kdata.columns:
                                    y_true = kdata['close'].values
                                    
                                    # 使用预测结果
                                    current_price = price_result.get('current_price', 0.0)
                                    target_low = price_result.get('target_low', 0.0)
                                    target_high = price_result.get('target_high', 0.0)
                                    
                                    # 计算预测价格（使用目标价的平均值）
                                    if target_low > 0 and target_high > 0:
                                        predicted_price = (target_low + target_high) / 2
                                    elif current_price > 0:
                                        predicted_price = current_price
                                    else:
                                        predicted_price = y_true[-1]  # 使用最后一个价格
                                    
                                    y_pred = np.full(len(y_true), predicted_price)
                                    y_pred_proba = None
                                    
                                    # 确保长度一致
                                    min_len = min(len(y_true), len(y_pred))
                                    y_true = y_true[:min_len]
                                    y_pred = y_pred[:min_len]
                                    
                                    logger.info(f"回归数据准备完成: y_true={len(y_true)}, y_pred={len(y_pred)}, predicted_price={predicted_price}")
                                    return y_true, y_pred, y_pred_proba
                    except Exception as e:
                        logger.warning(f"AI预测服务生成预测失败: {e}")
                        logger.warning(traceback.format_exc())
                
                # 如果AI预测服务不可用，使用简单的统计方法
                logger.info("使用统计方法生成预测数据")
                
                if 'close' in kdata.columns:
                    if task_type == 'classification':
                        # 分类任务：预测涨跌
                        price_change = kdata['close'].pct_change().dropna()
                        y_true = (price_change > 0).astype(int).values
                        
                        # 简单预测：基于移动平均
                        ma = kdata['close'].rolling(window=5).mean().dropna()
                        y_pred = ((kdata['close'].shift(-1) > ma).dropna() > 0).astype(int).values
                        y_pred_proba = np.random.rand(len(y_true))
                        
                        # 确保长度一致
                        min_len = min(len(y_true), len(y_pred))
                        y_true = y_true[:min_len]
                        y_pred = y_pred[:min_len]
                        y_pred_proba = y_pred_proba[:min_len]
                        
                        return y_true, y_pred, y_pred_proba
                    else:
                        # 回归任务：预测价格
                        y_true = kdata['close'].values
                        y_pred = kdata['close'].rolling(window=5).mean().fillna(method='bfill').values
                        y_pred_proba = None
                        
                        return y_true, y_pred, y_pred_proba
                
            logger.warning("无法准备评估数据")
            return None, None, None
            
        except Exception as e:
            logger.error(f"准备评估数据失败: {e}")
            return None, None, None
    
    def _on_evaluate(self):
        """执行增强评估"""
        if not self.intelligent_selector:
            QMessageBox.warning(self, "警告", "智能选择器未初始化")
            return
        
        try:
            # 获取配置参数
            stock_code = self.stock_code_edit.text().strip()
            period = self.period_combo.currentText()
            count = self.data_count_spin.value()
            model_type = self.model_type_combo.currentText()
            task_type = self.task_type_combo.currentText()
            
            if not stock_code:
                QMessageBox.warning(self, "警告", "请输入股票代码")
                return
            
            # 准备评估数据
            self.eval_result_text.setText("正在获取数据并准备评估...")
            y_true, y_pred, y_pred_proba = self._prepare_evaluation_data(
                stock_code, period, count, task_type
            )
            
            if y_true is None or y_pred is None:
                QMessageBox.warning(self, "警告", "无法准备评估数据，请检查股票代码和网络连接")
                self.eval_result_text.setText("评估失败：无法获取数据")
                return
            
            # 创建工作线程
            self.evaluation_worker = EnhancedEvaluationWorker(
                self.intelligent_selector,
                model_type,
                y_true,
                y_pred,
                y_pred_proba,
                task_type
            )
            
            # 连接信号
            self.evaluation_worker.progress.connect(self._on_eval_progress)
            self.evaluation_worker.finished.connect(self._on_eval_finished)
            self.evaluation_worker.error.connect(self._on_eval_error)
            
            # 显示进度条
            self.eval_progress.setVisible(True)
            self.eval_progress.setValue(0)
            self.evaluate_btn.setEnabled(False)
            
            # 启动线程
            self.evaluation_worker.start()
            
        except Exception as e:
            logger.error(f"启动评估失败: {e}")
            QMessageBox.critical(self, "错误", f"启动评估失败: {str(e)}")
    
    def _on_eval_progress(self, message: str, value: int):
        """评估进度更新"""
        self.eval_progress.setValue(value)
    
    def _on_eval_finished(self, result: dict):
        """评估完成"""
        try:
            performance = result['performance']
            model_type = result['model_type']
            task_type = result['task_type']
            
            # 显示结果
            result_text = f"模型类型: {model_type}\n"
            result_text += f"任务类型: {task_type}\n\n"
            
            result_text += "=== 基础指标 ===\n"
            if performance.basic_performance and performance.basic_performance.metrics:
                metrics = performance.basic_performance.metrics
                result_text += f"准确率: {metrics.accuracy:.4f}\n"
                result_text += f"精确率: {metrics.precision:.4f}\n"
                result_text += f"召回率: {metrics.recall:.4f}\n"
                result_text += f"F1分数: {metrics.f1_score:.4f}\n"
                result_text += f"MAPE: {metrics.mape:.4f}\n"
                result_text += f"夏普比率: {metrics.sharpe_ratio:.4f}\n"
            
            result_text += "\n=== 增强指标 ===\n"
            if performance.enhanced_metrics:
                if performance.enhanced_metrics.classification_metrics:
                    cls_metrics = performance.enhanced_metrics.classification_metrics
                    result_text += f"ROC AUC: {performance.roc_auc:.4f}\n"
                    result_text += f"PR AUC: {performance.pr_auc:.4f}\n"
                    result_text += f"平衡准确率: {cls_metrics.get('balanced_accuracy', 0):.4f}\n"
                    result_text += f"马修斯相关系数: {cls_metrics.get('mcc', 0):.4f}\n"
                    result_text += f"Cohen's Kappa: {cls_metrics.get('cohen_kappa', 0):.4f}\n"
                    result_text += f"特异性: {cls_metrics.get('specificity', 0):.4f}\n"
                    result_text += f"敏感性: {cls_metrics.get('sensitivity', 0):.4f}\n"
                
                if performance.enhanced_metrics.regression_metrics:
                    reg_metrics = performance.enhanced_metrics.regression_metrics
                    result_text += f"R²分数: {reg_metrics.get('r2_score', 0):.4f}\n"
                    result_text += f"调整R²分数: {reg_metrics.get('adjusted_r2_score', 0):.4f}\n"
                    result_text += f"RMSE: {reg_metrics.get('rmse', 0):.4f}\n"
                    result_text += f"MAPE: {reg_metrics.get('mape', 0):.4f}\n"
                    result_text += f"中位数绝对误差: {reg_metrics.get('medae', 0):.4f}\n"
            
            result_text += f"\n综合评分: {performance.basic_performance.composite_score:.4f}\n"
            result_text += f"可靠性评分: {performance.basic_performance.reliability_score:.4f}\n"
            result_text += f"样本数: {performance.basic_performance.sample_size}\n"
            
            self.eval_result_text.setText(result_text)
            
            # 隐藏进度条
            self.eval_progress.setVisible(False)
            self.evaluate_btn.setEnabled(True)
            
            QMessageBox.information(self, "成功", "增强评估完成！")
            
        except Exception as e:
            logger.error(f"显示评估结果失败: {e}")
            QMessageBox.critical(self, "错误", f"显示评估结果失败: {str(e)}")
    
    def _on_eval_error(self, error_message: str):
        """评估错误"""
        self.eval_result_text.setText(f"评估失败: {error_message}")
        self.eval_progress.setVisible(False)
        self.evaluate_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"评估失败: {error_message}")
    
    def _on_browse_directory(self):
        """浏览目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择保存目录", ""
        )
        if directory:
            self.save_dir_edit.setText(directory)
    
    def _on_visualize(self):
        """执行可视化"""
        if not self.intelligent_selector:
            QMessageBox.warning(self, "警告", "智能选择器未初始化")
            return
        
        try:
            # 获取配置参数
            stock_code = self.viz_stock_code_edit.text().strip()
            period = self.viz_period_combo.currentText()
            count = self.viz_data_count_spin.value()
            model_type = self.viz_model_type_combo.currentText()
            task_type = self.viz_task_type_combo.currentText()
            save_dir = self.save_dir_edit.text()
            
            if save_dir == "未选择":
                save_dir = None
            
            if not stock_code:
                QMessageBox.warning(self, "警告", "请输入股票代码")
                return
            
            # 准备可视化数据
            self.viz_result_text.setText("正在获取数据并准备可视化...")
            y_true, y_pred, y_pred_proba = self._prepare_evaluation_data(
                stock_code, period, count, task_type
            )
            
            if y_true is None or y_pred is None:
                QMessageBox.warning(self, "警告", "无法准备可视化数据，请检查股票代码和网络连接")
                self.viz_result_text.setText("可视化失败：无法获取数据")
                return
            
            # 生成特征名称和重要性（仅用于演示）
            import numpy as np
            if task_type == 'classification':
                feature_names = [f'feature_{i}' for i in range(10)]
                feature_importance = np.random.rand(10)
            else:
                feature_names = None
                feature_importance = None
            
            # 创建工作线程
            self.visualization_worker = VisualizationWorker(
                self.intelligent_selector,
                model_type,
                y_true,
                y_pred,
                y_pred_proba,
                task_type,
                save_dir,
                feature_names,
                feature_importance
            )
            
            # 连接信号
            self.visualization_worker.progress.connect(self._on_viz_progress)
            self.visualization_worker.finished.connect(self._on_viz_finished)
            self.visualization_worker.error.connect(self._on_viz_error)
            
            # 显示进度条
            self.viz_progress.setVisible(True)
            self.viz_progress.setValue(0)
            self.visualize_btn.setEnabled(False)
            
            # 启动线程
            self.visualization_worker.start()
            
        except Exception as e:
            logger.error(f"启动可视化失败: {e}")
            QMessageBox.critical(self, "错误", f"启动可视化失败: {str(e)}")
    
    def _on_viz_progress(self, message: str, value: int):
        """可视化进度更新"""
        self.viz_progress.setValue(value)
    
    def _on_viz_finished(self, result: dict):
        """可视化完成"""
        try:
            chart_paths = result['chart_paths']
            model_type = result['model_type']
            task_type = result['task_type']
            
            # 显示结果
            result_text = f"模型类型: {model_type}\n"
            result_text += f"任务类型: {task_type}\n\n"
            result_text += "=== 生成的图表 ===\n\n"
            
            if chart_paths:
                for chart_type, path in chart_paths.items():
                    if path:
                        result_text += f"{chart_type}: {path}\n"
                    else:
                        result_text += f"{chart_type}: 已显示（未保存）\n"
            else:
                result_text += "未生成任何图表\n"
            
            self.viz_result_text.setText(result_text)
            
            # 隐藏进度条
            self.viz_progress.setVisible(False)
            self.visualize_btn.setEnabled(True)
            
            QMessageBox.information(self, "成功", "可视化图表生成完成！")
            
        except Exception as e:
            logger.error(f"显示可视化结果失败: {e}")
            QMessageBox.critical(self, "错误", f"显示可视化结果失败: {str(e)}")
    
    def _on_viz_error(self, error_message: str):
        """可视化错误"""
        self.viz_result_text.setText(f"可视化失败: {error_message}")
        self.viz_progress.setVisible(False)
        self.visualize_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"可视化失败: {error_message}")
