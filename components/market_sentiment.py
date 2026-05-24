import numpy as np
import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDateTime
from PyQt5.QtGui import QColor, QPalette, QPainter, QMovie
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
import time
from typing import Dict, Any, Optional, List, Union
from core.services.unified_data_manager import UnifiedDataManager
from datetime import datetime
from gui.ui_components import BaseAnalysisPanel
import traceback
from utils.config_manager import ConfigManager
from utils.template_manager import TemplateManager
from gui.widgets.analysis_tabs.base_tab import BaseAnalysisTab
from loguru import logger


class DataUpdateThread(QThread):
    """数据更新线程"""
    data_updated = pyqtSignal(dict)  # 数据更新信号
    error_occurred = pyqtSignal(str)  # 错误信号
    status_changed = pyqtSignal(str)  # 状态信号

    def __init__(self, data_manager: UnifiedDataManager):
        super().__init__()
        self.data_manager = data_manager
        # 纯Loguru架构，移除log_manager依赖
        self.running = False
        self.update_interval = 60  # 更新间隔（秒）
        self.retry_interval = 5    # 重试间隔（秒）
        self.max_retries = 3       # 最大重试次数

    def run(self):
        """运行更新线程"""
        self.running = True
        retry_count = 0

        while self.running:
            try:
                # 获取最新数据
                logger.info("[线程] 正在更新数据...")
                self.status_changed.emit("正在更新数据...")
                sentiment_data = self.data_manager.get_market_sentiment()

                if sentiment_data:
                    # 发送信号更新UI
                    self.data_updated.emit(sentiment_data)
                    logger.info("[线程] 数据更新成功")
                    self.status_changed.emit("数据更新成功")
                    retry_count = 0  # 重置重试计数
                else:
                    raise ValueError("获取数据为空")

            except Exception as e:
                retry_count += 1
                error_msg = f"更新市场情绪数据失败 ({retry_count}/{self.max_retries}): {str(e)}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                logger.warning("[线程] 更新失败，准备重试...")
                self.status_changed.emit("更新失败，准备重试...")

                if retry_count >= self.max_retries:
                    logger.info(
                        "[线程] 达到最大重试次数，等待下一轮更新")
                    self.status_changed.emit("达到最大重试次数，等待下一轮更新")
                    retry_count = 0
                    time.sleep(self.update_interval)
                else:
                    time.sleep(self.retry_interval)
                continue

            # 正常更新后的等待
            for _ in range(self.update_interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("[线程] 已停止更新")
        self.status_changed.emit("已停止更新")

    def stop(self):
        """停止更新线程"""
        self.running = False
        self.status_changed.emit("已停止更新")


class MarketSentimentWidget(BaseAnalysisTab):
    """市场情绪分析组件，继承统一分析面板基类"""

    def __init__(self, parent=None, data_manager=None, chart_widget=None):
        """初始化市场情绪组件

        Args:
            parent: 父窗口
            data_manager: 数据管理器实例
            # log_manager: 已迁移到Loguru日志系统
            chart_widget: 主图表控件实例
        """
        super().__init__(parent)  # log_manager已迁移到Loguru
        self.data_manager = data_manager
        self.chart_widget = chart_widget
        self.template_manager = TemplateManager(
            template_dir="templates/market_sentiment")
        # 修复：初始化数据缓存，防止未定义报错
        self._data_cache = {}
        self._cache_time = {}
        self._custom_indicators = {}
        self._alerts = {}
        self._sentiment_cache = {}
        self._sentiment_cache_time = {}

        # 初始化情绪数据服务
        self._sentiment_service = None
        self._initialize_sentiment_service()

        self.init_ui()

        # 示例：增加情绪阈值参数输入
        self.sentiment_threshold = QSpinBox()
        self.sentiment_threshold.setRange(0, 100)
        self.sentiment_threshold.setValue(50)
        self.add_param_widget("情绪阈值", self.sentiment_threshold)

        # 使用统一的数据更新线程
        if self.data_manager:
            self.update_thread = self.create_data_update_thread(
                data_fetcher=self._fetch_market_sentiment_data,
                update_interval=60,  # 60秒更新间隔
                max_retries=3,
                retry_interval=5
            )
            self.update_thread.start()

            # 主动拉取一次数据，确保初始有数据展示
            try:
                data = self._fetch_market_sentiment_data()
                if data:
                    self._on_data_updated(data)
            except Exception as e:
                self._on_thread_error(f"初始化拉取市场情绪数据失败: {str(e)}")

    def _fetch_market_sentiment_data(self) -> dict:
        """获取市场情绪数据 - 使用真实插件数据源"""
        try:
            # 尝试使用情绪数据服务获取真实数据
            if hasattr(self, '_sentiment_service') and self._sentiment_service:
                # 确保使用所有可用插件（清空选中插件列表）
                self._sentiment_service.clear_selected_plugins()

                response = self._sentiment_service.get_sentiment_data()
                if response.success and response.data:
                    # 转换为组件期望的格式
                    sentiment_index = (response.composite_score + 1) / 2  # 转换到0-1范围
                    market_heat = sentiment_index * 100  # 转换为0-100范围

                    result = {
                        'sentiment_index': sentiment_index,
                        'market_heat': market_heat,
                        'timestamp': response.update_time,
                        'data_quality': response.data_quality,
                        'source': 'plugin',
                        'raw_data': response.data  # 保留原始数据
                    }

                    logger.info(f" 市场情绪组件使用真实插件数据，情绪指数: {sentiment_index:.3f}")

                    return result

                else:
                    logger.warning(f" 情绪数据服务返回错误: {response.error_message}")

            # 检查原数据管理器
            if hasattr(self.data_manager, 'get_market_sentiment'):
                return self.data_manager.get_market_sentiment()

            # 最后回退到模拟数据（明确标识）
            return {
                'sentiment_index': 0.65,
                'market_heat': 75,
                'timestamp': datetime.now(),
                'source': 'simulated',
                'note': '使用模拟数据 - 请配置真实数据源'
            }

        except Exception as e:
            logger.error(f" 获取市场情绪数据失败: {e}")

            # 错误时返回安全的回退数据
            return {
                'sentiment_index': 0.5,
                'market_heat': 50,
                'timestamp': datetime.now(),
                'source': 'error_fallback',
                'error': str(e)
            }

    def init_ui(self):
        """初始化UI"""
        self.main_layout = self.layout()

        # 创建情绪分数显示
        score_layout = QHBoxLayout()
        score_label = QLabel("市场情绪分数:")
        self.sentiment_score_label = QLabel("0.00")
        self.sentiment_score_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #1976d2; padding: 4px 12px; border-radius: 8px; background: #e3f2fd;")
        score_layout.addWidget(score_label)
        score_layout.addWidget(self.sentiment_score_label)
        score_layout.addStretch()
        self.main_layout.addLayout(score_layout)
        # 移除了直接的akshare调用，现在通过插件系统获取数据
        # 只保留情绪指数走势图表
        self.create_sentiment_chart(self.main_layout)

        # 创建市场热度指示器
        self.create_market_heat_indicator(self.main_layout)

        # 创建状态栏
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("状态:"))
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666666;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.main_layout.addLayout(status_layout)

        # 控制按钮区（分析、导出、模板管理、自定义指标）
        button_layout = QHBoxLayout()
        self.analyze_button = QPushButton("市场情绪分析")
        self.analyze_button.setStyleSheet(
            "background: #1976d2; color: white; font-weight: bold; border-radius: 8px; padding: 6px 18px;")
        self.analyze_button.setToolTip("点击进行市场情绪分析")
        self.analyze_button.clicked.connect(self.on_sentiment_analyze)
        button_layout.addWidget(self.analyze_button)

        self.export_button = QPushButton("导出结果")
        self.export_button.setStyleSheet(
            "background: #43a047; color: white; font-weight: bold; border-radius: 8px; padding: 6px 18px;")
        self.export_button.setToolTip("导出分析结果为图片")
        self.export_button.clicked.connect(self.export_data)
        button_layout.addWidget(self.export_button)

        self.template_button = QPushButton("模板管理")
        self.template_button.setStyleSheet(
            "background: #ffa000; color: white; font-weight: bold; border-radius: 8px; padding: 6px 18px;")
        self.template_button.setToolTip("管理情绪分析参数模板")
        self.template_button.clicked.connect(self.show_template_manager_dialog)
        button_layout.addWidget(self.template_button)

        self.main_layout.addLayout(button_layout)

    def create_sentiment_chart(self, layout=None):
        """创建市场情绪图表

        Args:
            layout: 可选的布局对象，如果提供则将图表添加到该布局中

        Returns:
            QChartView: 图表视图对象
        """
        try:
            # 创建图表
            chart = QChart()
            chart.setTitle("市场情绪")
            chart.setAnimationOptions(QChart.SeriesAnimations)

            # 创建数据系列
            self.sentiment_series = QLineSeries()
            self.sentiment_series.setName("情绪指数")

            # 创建X轴
            self.sentiment_axis_x = QValueAxis()
            self.sentiment_axis_x.setTitleText("时间")
            self.sentiment_axis_x.setLabelFormat("%d")

            # 创建Y轴
            self.sentiment_axis_y = QValueAxis()
            self.sentiment_axis_y.setTitleText("情绪值")
            self.sentiment_axis_y.setRange(0, 100)  # 使用整数范围
            self.sentiment_axis_y.setLabelFormat("%d")

            # 添加系列和轴到图表
            chart.addSeries(self.sentiment_series)
            chart.addAxis(self.sentiment_axis_x, Qt.AlignBottom)
            chart.addAxis(self.sentiment_axis_y, Qt.AlignLeft)

            # 关联系列和轴
            self.sentiment_series.attachAxis(self.sentiment_axis_x)
            self.sentiment_series.attachAxis(self.sentiment_axis_y)

            # 创建图表视图
            chart_view = QChartView(chart)
            chart_view.setRenderHint(QPainter.Antialiasing)

            # 设置图表视图的大小策略
            chart_view.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            chart_view.setMinimumHeight(300)

            # 保存图表相关对象的引用
            self.sentiment_chart = chart
            self.sentiment_chart_view = chart_view

            # 如果提供了布局，添加图表视图
            if layout is not None:
                layout.addWidget(chart_view)

            logger.info("市场情绪图表创建成功")
            return chart_view

        except Exception as e:
            logger.error(f"创建市场情绪图表失败: {str(e)}")
            return None

    def create_market_heat_indicator(self, layout):
        """美化市场热度指示器"""
        heat_layout = QHBoxLayout()
        heat_layout.addWidget(QLabel("市场热度:"))
        self.heat_progress = QProgressBar()
        self.heat_progress.setRange(0, 100)
        self.heat_progress.setTextVisible(True)
        self.heat_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #90caf9;
                border-radius: 12px;
                text-align: center;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e3f2fd, stop:1 #bbdefb);
                height: 28px;
                font-size: 16px;
                color: #1976d2;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #43a047, stop:1 #1976d2);
                border-radius: 12px;
            }
        """)
        heat_layout.addWidget(self.heat_progress)
        layout.addLayout(heat_layout)

    def set_heat_progress(self, value):
        value = max(0, min(100, int(value)))
        self.heat_progress.setValue(value)

    def set_heat_progress_error(self, message="分析失败"):
        self.heat_progress.setStyleSheet(
            "QProgressBar::chunk {background-color: #FF0000;}")
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #FF5252;")

    def create_control_buttons(self, layout):
        """创建控制按钮 - 使用基类统一方法"""
        # 使用基类的统一控制按钮布局创建方法
        control_layout = self.create_control_buttons_layout(
            include_export=True,
            include_alert=True,
            custom_buttons=None
        )
        layout.addLayout(control_layout)

    def _get_cached_data(self, key, max_age=60):
        """获取缓存数据"""
        if key in self._data_cache:
            if time.time() - self._cache_time[key] < max_age:
                return self._data_cache[key]
        return None

    def add_custom_indicator(self, name, calculator):
        """添加自定义指标"""
        self._custom_indicators[name] = calculator
        self._refresh_indicators()

    def set_alert(self, indicator, threshold, callback):
        """设置指标预警"""
        self._alerts[indicator] = {
            'threshold': threshold,
            'callback': callback
        }

    def export_data(self):
        """增强导出功能，支持导出表格和图表，操作写日志 - 使用基类统一方法"""
        try:
            # 使用基类的统一文件保存对话框
            file_path = self.show_save_file_dialog(
                title="导出分析结果",
                default_name="market_sentiment_analysis",
                file_filter="Excel Files (*.xlsx);;CSV Files (*.csv);;PNG Files (*.png)"
            )

            if file_path:
                if file_path.endswith('.xlsx') or file_path.endswith('.csv'):
                    # 导出表格数据
                    export_data = []
                    for row in range(self.sentiment_table.rowCount()):
                        row_data = []
                        for col in range(self.sentiment_table.columnCount()):
                            item = self.sentiment_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        export_data.append(row_data)

                    # 使用基类的统一导出方法
                    if self.export_data_to_file(export_data, file_path):
                        self.show_info_message("导出成功", f"表格已导出到: {file_path}")
                    else:
                        self.show_error_message("导出失败", "导出表格数据时发生错误")

                elif file_path.endswith('.png'):
                    # 导出图表
                    if hasattr(self, 'sentiment_chart_view'):
                        pixmap = self.sentiment_chart_view.grab()
                        pixmap.save(file_path)
                        logger.info(f"图表已导出到: {file_path}")
                        self.show_info_message("导出成功", f"图表已导出到: {file_path}")
                    else:
                        logger.warning("未找到图表控件，无法导出图表")
                        self.show_warning_message("导出失败", "未找到图表控件，无法导出图表")
        except Exception as e:
            logger.error(f"导出失败: {str(e)}")
            self.show_error_message("导出错误", f"导出失败: {str(e)}")

    def show_alert_dialog(self):
        """显示预警设置对话框 - 使用基类统一方法"""
        # 使用基类的统一信息消息框
        self.show_info_message("预警功能", "预警功能正在开发中，敬请期待！")

    def get_cached_sentiment(self) -> dict:
        """获取缓存的市场情绪数据，智能动态失效"""
        now = datetime.now()
        if hasattr(self, '_sentiment_cache') and hasattr(self, '_sentiment_cache_time'):
            # 智能缓存时长：数据越新缓存越久，最短30秒，最长300秒
            cache_data = self._sentiment_cache
            ts = cache_data.get('timestamp')
            if ts and isinstance(ts, datetime):
                age = (now - ts).total_seconds()
                if age < 60:
                    max_age = 300  # 5分钟
                elif age < 300:
                    max_age = 120  # 2分钟
                else:
                    max_age = 30   # 30秒
            else:
                max_age = 60
            if (now - self._sentiment_cache_time).total_seconds() < max_age:
                return self._sentiment_cache
        return None

    def show_loading_skeleton(self):
        """显示骨架屏动画（增强版）"""
        if not hasattr(self, '_skeleton_label'):
            self._skeleton_label = QLabel("加载中...", self)
            self._skeleton_label.setAlignment(Qt.AlignCenter)
            self._skeleton_label.setStyleSheet(
                "font-size: 22px; color: #cccccc; background: #f7f9fa; border-radius: 12px; padding: 32px 0; border: 2px dashed #90caf9;")
            try:
                self._movie = QMovie("resources/images/loading.gif")
                if self._movie.isValid():
                    self._skeleton_label.setMovie(self._movie)
                    self._movie.start()
            except Exception:
                pass
            self.main_layout.addWidget(self._skeleton_label)
        self._skeleton_label.show()
        self._skeleton_label.raise_()

    def hide_loading_skeleton(self):
        if hasattr(self, '_skeleton_label'):
            self._skeleton_label.hide()

    def update_sentiment_data(self, data: dict):
        """只更新情绪分数和多市场走势"""
        try:
            logger.info(f"收到市场情绪数据: {data}")
            # 1. 情绪分数
            score = data.get('sentiment_index')
            if isinstance(score, (int, float)):
                self.sentiment_score_label.setText(f"{score:.3f}")
                self.sentiment_score_label.setStyleSheet(
                    "font-size: 20px; font-weight: bold; color: #1976d2; padding: 4px 12px; border-radius: 8px; background: #e3f2fd;")
                logger.info(f"市场情绪分数显示: {score:.3f}")
            else:
                self.sentiment_score_label.setText("暂无数据")
                self.sentiment_score_label.setStyleSheet(
                    "font-size: 20px; color: #999999; font-weight: bold;")
                logger.warning("市场情绪分数字段缺失或为None")

            # 2. 多市场情绪指数走势
            if hasattr(self.data_manager, 'get_market_sentiment_history'):
                all_history = self.data_manager.get_market_sentiment_history(
                    days=60)
                self._update_sentiment_chart_multi(all_history)
            else:
                self._update_sentiment_chart_multi([])

            # 3. 热度指示器
            if hasattr(self, 'heat_progress'):
                heat = data.get('market_heat')
                if heat is not None:
                    try:
                        heat = float(heat)
                        self.heat_progress.setValue(int(heat))
                        logger.info(f"市场热度显示: {heat}")
                    except Exception:
                        self.heat_progress.setValue(0)
                        logger.warning("市场热度字段格式异常")
                else:
                    self.heat_progress.setValue(0)
                    logger.warning("市场热度字段缺失")
        except Exception as e:
            logger.error(f"更新市场情绪数据失败: {str(e)}")
            logger.error(traceback.format_exc())

    def _update_sentiment_chart_multi(self, all_history):
        """多市场情绪走势曲线"""
        try:
            if not hasattr(self, 'sentiment_chart'):
                return
            self.sentiment_chart.removeAllSeries()
            has_data = False
            for market_data in all_history:
                market = market_data.get('market', '未知')
                history = market_data.get('history', [])
                if not history:
                    continue
                series = QLineSeries()
                series.setName(market)
                for i, item in enumerate(history):
                    v = item.get('sentiment_index')
                    if v is not None:
                        series.append(i, float(v))
                if series.count() > 0:
                    self.sentiment_chart.addSeries(series)
                    series.attachAxis(self.sentiment_axis_x)
                    series.attachAxis(self.sentiment_axis_y)
                    has_data = True
            # X轴范围
            self.sentiment_axis_x.setRange(0, 59)
            self.sentiment_axis_x.setTitleText("最近60天")
            # Y轴范围自适应
            self.sentiment_axis_y.setRange(0, 2)
            self.sentiment_axis_y.setTitleText("情绪指数/收盘价")
            if not has_data:
                self.sentiment_chart.setTitle("暂无数据")
            else:
                self.sentiment_chart.setTitle("市场情绪走势（近60天）")
            if hasattr(self, 'sentiment_chart_view'):
                self.sentiment_chart_view.update()
        except Exception as e:
            logger.error(f"多市场情绪走势渲染失败: {str(e)}")

    def _update_ui_safely(self, data: dict):
        """在主线程中安全地更新UI，数据缺失时所有UI区域显示暂无数据，并写日志"""
        try:
            if not data or data.get('sentiment_index') is None:
                self.sentiment_score_label.setText("暂无市场情绪数据")
                self.sentiment_score_label.setStyleSheet(
                    "font-size: 20px; color: #999999; font-weight: bold;")
                if hasattr(self, 'sentiment_table'):
                    self.sentiment_table.clearContents()
                    for row in range(self.sentiment_table.rowCount()):
                        for col in range(self.sentiment_table.columnCount()):
                            self.sentiment_table.setItem(
                                row, col, QTableWidgetItem("暂无数据"))
                if hasattr(self, 'sentiment_series'):
                    self.sentiment_series.clear()
                if hasattr(self, 'heat_progress'):
                    self.heat_progress.setValue(0)
                logger.warning("UI刷新时市场情绪数据缺失，所有UI区域已置为暂无数据")
                return
            self._data_cache.update(data)
            self._cache_time[datetime.now()] = data
            self._update_sentiment_index(data)
            self._update_heat_indicator(data)
            self._update_charts(data)
            self._check_alerts(data)
        except Exception as e:
            logger.error(f"更新UI失败: {e}")

    def _update_sentiment_index(self, data: dict):
        """
        更新情绪分数标签
        Args:
            data: 市场情绪数据字典
        """
        try:
            sentiment_index = data.get('sentiment_index', 0)
            if hasattr(self, 'sentiment_score_label'):
                self.sentiment_score_label.setText(f"{sentiment_index:.3f}")
                # 设置颜色
                if sentiment_index >= 70:
                    self.sentiment_score_label.setStyleSheet(
                        "font-size: 16px; font-weight: bold; color: #ff4d4f;")
                elif sentiment_index >= 50:
                    self.sentiment_score_label.setStyleSheet(
                        "font-size: 16px; font-weight: bold; color: #faad14;")
                else:
                    self.sentiment_score_label.setStyleSheet(
                        "font-size: 16px; font-weight: bold; color: #52c41a;")
        except Exception as e:
            logger.error(f"更新情绪分数标签失败: {e}")

    def _update_sentiment_chart(self, data):
        """更新情绪图表

        Args:
            data: 市场情绪数据
        """
        try:
            if not hasattr(self, 'sentiment_chart') or not hasattr(self, 'sentiment_series'):
                logger.warning("情绪图表未初始化")
                return
            # 清除现有数据
            self.sentiment_series.clear()
            # 添加数据点
            sentiment_data = data.get('sentiment_index', {})
            values = []
            if isinstance(sentiment_data, dict):
                for i, (date, value) in enumerate(sentiment_data.items()):
                    if isinstance(value, (int, float)):
                        self.sentiment_series.append(i, int(value))
                        values.append(float(value))
            elif isinstance(sentiment_data, (list, tuple)):
                for i, value in enumerate(sentiment_data):
                    if isinstance(value, (int, float)):
                        self.sentiment_series.append(i, int(value))
                        values.append(float(value))
            elif isinstance(sentiment_data, (int, float)):
                self.sentiment_series.append(0, int(sentiment_data))
                values.append(float(sentiment_data))
            # 更新X轴范围
            points_count = self.sentiment_series.count()
            if points_count > 0:
                self.sentiment_axis_x.setRange(0, points_count - 1)
            # 更新Y轴范围（保持0-100的整数范围）
            self.sentiment_axis_y.setRange(0, 100)
            # 在图表顶部添加最大、最小、均值
            if hasattr(self, 'sentiment_chart') and values:
                max_val = max(values)
                min_val = min(values)
                mean_val = np.mean(values)
                # 通过QChart的title增强显示
                self.sentiment_chart.setTitle(
                    f"市场情绪（最大: {max_val:.3f}  最小: {min_val:.3f}  均值: {mean_val:.3f}）")
            # 更新图表
            if hasattr(self, 'sentiment_chart_view'):
                self.sentiment_chart_view.update()
            logger.info("情绪图表更新成功")
        except Exception as e:
            logger.error(f"更新情绪图表失败: {str(e)}")

    def _update_heat_indicator(self, data):
        """更新热度指示器"""
        try:
            heat_value = data.get('market_heat', 0)
            if isinstance(heat_value, (int, float)):
                self.heat_progress.setValue(int(heat_value))
                self._update_heat_color(float(heat_value))
            else:
                logger.warning(f"无效的热度值: {heat_value}")
        except Exception as e:
            logger.error(f"更新热度指示器失败: {e}")

    def _check_alerts(self, data):
        """检查预警条件"""
        for indicator, alert in self._alerts.items():
            value = data.get(indicator, 0)
            if value >= alert['threshold']:
                alert['callback'](indicator, value)

    def closeEvent(self, event):
        """关闭事件处理"""
        if hasattr(self, 'update_thread'):
            self.update_thread.stop()
            self.update_thread.wait()
        super().closeEvent(event)

    def _get_status(self, name: str, value: float) -> str:
        """获取指标状态

        Args:
            name: 指标名称
            value: 指标值

        Returns:
            str: 状态描述
        """
        if name == '情绪指数':
            if value > 50:
                return '乐观'
            elif value < -50:
                return '悲观'
            else:
                return '中性'
        elif name == "成交量比":
            if value > 1.5:
                return "活跃"
            elif value < 0.5:
                return "低迷"
            else:
                return "正常"
        elif name == "上涨家数":
            if value > 2000:
                return "强势"
            elif value < 500:
                return "弱势"
            else:
                return "中性"
        elif name == "下跌家数":
            if value > 2000:
                return "弱势"
            elif value < 500:
                return "强势"
            else:
                return "中性"
        return "未知"

    def _get_status_color(self, status):
        """获取状态颜色"""
        color_map = {
            "极度悲观": "#FF1744",
            "悲观": "#FF5252",
            "中性": "#757575",
            "乐观": "#69F0AE",
            "极度乐观": "#00C853",
            "极度看空": "#FF1744",
            "看空": "#FF5252",
            "看多": "#69F0AE",
            "极度看多": "#00C853",
            "低迷": "#FF1744",
            "偏低": "#FF5252",
            "正常": "#757575",
            "活跃": "#69F0AE",
            "热络": "#00C853",
            "过热": "#FF1744",
            "大幅流出": "#FF1744",
            "流出": "#FF5252",
            "平衡": "#757575",
            "流入": "#69F0AE",
            "大幅流入": "#00C853"
        }
        return QColor(color_map.get(status, "#757575"))

    def _update_heat_color(self, value):
        """更新热度指示器颜色"""
        if value < 20:
            color = "#FF1744"  # 深红
        elif value < 40:
            color = "#FF5252"  # 红
        elif value < 60:
            color = "#757575"  # 灰
        elif value < 80:
            color = "#69F0AE"  # 浅绿
        else:
            color = "#00C853"  # 深绿

        self.heat_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)

    def handle_error(self, error_msg: str):
        """处理错误信息

        Args:
            error_msg: 错误信息
        """
        logger.error(error_msg)
        if hasattr(self, 'status_label'):
            self.status_label.setText(error_msg)
            self.status_label.setStyleSheet("color: #FF5252;")  # 红色

    def handle_status_change(self, status: str):
        """处理状态变化

        Args:
            status: 状态信息
        """
        logger.info(f"[状态变更] {status}")
        if hasattr(self, 'status_label'):
            self.status_label.setText(status)
            self.status_label.setStyleSheet("color: #666666;")  # 灰色

    def on_sentiment_analyze(self):
        """分析前校验参数并强制拉取最新数据"""
        valid, msg = self.validate_params()
        if not valid:
            self.set_status_message(msg, error=True)
            self.sentiment_threshold.setToolTip(msg)
            return
        self.set_status_message("参数校验通过，正在分析...", error=False)
        self.sentiment_threshold.setToolTip("")
        try:
            logger.info("分析按钮被点击，强制拉取最新市场情绪数据")
            if hasattr(self.data_manager, 'get_market_sentiment'):
                data = self.data_manager.get_market_sentiment()
                if data:
                    self.update_sentiment_data(data)
                    self.set_status_message("分析完成", error=False)
                else:
                    self.set_status_message("未获取到市场情绪数据", error=True)
                    logger.warning("分析未获取到数据")
            else:
                self.set_status_message(
                    "数据管理器未实现get_market_sentiment", error=True)
        except Exception as e:
            self.set_status_message(f"分析失败: {str(e)}", error=True)
            logger.error(f"分析失败: {str(e)}")

    def show_template_manager_dialog(self):
        """显示模板管理对话框 - 使用基类统一方法"""
        # 使用基类的统一对话框创建方法
        dialog = self.create_standard_dialog("模板管理", 800, 600)

        # 创建对话框内容
        layout = self.create_standard_layout("vbox", spacing=15)

        # 添加模板列表
        template_list = QListWidget()
        template_list.addItems(["默认模板", "自定义模板1", "自定义模板2"])
        layout.addWidget(QLabel("可用模板:"))
        layout.addWidget(template_list)

        # 创建按钮布局
        button_layout = self.create_button_layout([
            ("应用模板", lambda: self._apply_template(
                template_list, dialog), '#4CAF50'),
            ("删除模板", lambda: self._delete_template(template_list), '#F44336'),
            ("新建模板", self._create_new_template, '#2196F3')
        ])
        layout.addLayout(button_layout)

        # 创建对话框按钮
        button_box = self.create_dialog_button_box("ok_cancel")
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.setLayout(layout)
        self.center_dialog(dialog)

        return dialog.exec_()

    def _apply_template(self, list_widget, dialog):
        """应用模板"""
        current_item = list_widget.currentItem()
        if current_item:
            template_name = current_item.text()
            self.show_info_message("模板应用", f"已应用模板: {template_name}")
            dialog.accept()
        else:
            self.show_warning_message("选择模板", "请先选择一个模板")

    def _delete_template(self, list_widget):
        """删除模板"""
        current_item = list_widget.currentItem()
        if current_item:
            template_name = current_item.text()
            if template_name == "默认模板":
                self.show_warning_message("删除失败", "默认模板不能删除")
                return

            result = self.show_question_message(
                "确认删除", f"确定要删除模板 '{template_name}' 吗？")
            if result == QMessageBox.Yes:
                row = list_widget.row(current_item)
                list_widget.takeItem(row)
                self.show_info_message("删除成功", f"模板 '{template_name}' 已删除")
        else:
            self.show_warning_message("选择模板", "请先选择要删除的模板")

    def _create_new_template(self):
        """创建新模板"""
        self.show_info_message("新建模板", "新建模板功能正在开发中")

    def _update_charts(self, data: dict):
        """
        更新市场情绪相关图表（兼容入口）
        Args:
            data: 市场情绪数据
        """
        self._update_sentiment_chart(data)

    def update_auto_refresh_interval(self):
        """更新自动刷新间隔"""
        interval = self.auto_refresh_spin.value()
        if hasattr(self, 'update_thread'):
            self.update_thread.update_interval = interval
        logger.info(f"自动刷新间隔已设置为{interval}秒")

    def show_custom_indicator_dialog(self):
        """显示自定义指标对话框 - 使用基类统一方法"""
        # 使用基类的统一对话框创建方法
        dialog = self.create_standard_dialog("自定义指标", 600, 400)

        layout = self.create_standard_layout("vbox", spacing=10)

        # 指标名称
        layout.addWidget(QLabel("指标名称:"))
        name_edit = QLineEdit()
        layout.addWidget(name_edit)

        # 指标公式
        layout.addWidget(QLabel("指标公式:"))
        formula_edit = QTextEdit()
        formula_edit.setMaximumHeight(100)
        layout.addWidget(formula_edit)

        # 按钮
        button_box = self.create_dialog_button_box("ok_cancel")
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.setLayout(layout)
        self.center_dialog(dialog)

        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text().strip()
            formula = formula_edit.toPlainText().strip()
            if name and formula:
                self.show_info_message("指标创建", f"自定义指标 '{name}' 创建成功")
            else:
                self.show_warning_message("输入错误", "请填写完整的指标名称和公式")

    def _run_analysis_async(self, button, analysis_func, *args, **kwargs):
        original_text = button.text()
        button.setText("取消")
        button._interrupted = False

        def on_cancel():
            button._interrupted = True
            button.setText(original_text)
            button.setEnabled(True)
            # 重新绑定分析逻辑
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(lambda: self._run_analysis_async(
                button, analysis_func, *args, **kwargs))

        try:
            button.clicked.disconnect()
        except Exception:
            pass
        button.clicked.connect(on_cancel)

        def task():
            try:
                if not getattr(button, '_interrupted', False):
                    result = analysis_func(*args, **kwargs)
                    return result
            except Exception as e:
                logger.error(f"分析异常: {str(e)}")
                return None
            finally:
                QTimer.singleShot(0, lambda: on_done(None))

        def on_done(future):
            button.setText(original_text)
            button.setEnabled(True)
            # 重新绑定分析逻辑
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(lambda: self._run_analysis_async(
                button, analysis_func, *args, **kwargs))
        import os
        from concurrent.futures import ThreadPoolExecutor
        if not hasattr(self, '_thread_pool'):
            self._thread_pool = ThreadPoolExecutor(os.cpu_count() * 2)
        future = self._thread_pool.submit(task)
        # 只需在finally中恢复，无需重复回调

    def analyze_sentiment(self):
        self._run_analysis_async(
            self.analyze_button, self._analyze_sentiment_impl)

    def export_data(self):
        self._run_analysis_async(self.export_button, self._export_data_impl)

    def refresh_data(self):
        self._run_analysis_async(self.refresh_button, self._refresh_data_impl)
    # ... 其余耗时分析按钮同理 ...

    def update_sentiment_table(self, data: dict):
        """更新市场情绪表格，添加统计行和极值高亮"""
        if not hasattr(self, 'sentiment_table'):
            return
        df = data.get('sentiment_table_df')
        if not isinstance(df, pd.DataFrame) or df.empty:
            return
        self.sentiment_table.setRowCount(len(df) + 3)
        # 填充数据
        for i, row in df.iterrows():
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                self.sentiment_table.setItem(i, j, item)
        # 统计行
        mean_vals = df.mean(numeric_only=True)
        max_vals = df.max(numeric_only=True)
        min_vals = df.min(numeric_only=True)
        col_count = df.shape[1]
        # 均值行
        for j in range(col_count):
            item = QTableWidgetItem(
                f"{mean_vals.iloc[j]:.3f}" if pd.api.types.is_number(mean_vals.iloc[j]) else "")
            item.setBackground(QColor("#fffde7"))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sentiment_table.setItem(len(df), j, item)
        # 最大行
        for j in range(col_count):
            item = QTableWidgetItem(
                f"{max_vals.iloc[j]:.3f}" if pd.api.types.is_number(max_vals.iloc[j]) else "")
            item.setBackground(QColor("#ffe082"))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sentiment_table.setItem(len(df)+1, j, item)
        # 最小行
        for j in range(col_count):
            item = QTableWidgetItem(
                f"{min_vals.iloc[j]:.3f}" if pd.api.types.is_number(min_vals.iloc[j]) else "")
            item.setBackground(QColor("#ffccbc"))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sentiment_table.setItem(len(df)+2, j, item)
        # 极值高亮
        for j in range(col_count):
            max_idx = df.iloc[:, j].idxmax() if pd.api.types.is_numeric_dtype(
                df.iloc[:, j]) else None
            min_idx = df.iloc[:, j].idxmin() if pd.api.types.is_numeric_dtype(
                df.iloc[:, j]) else None
            if max_idx is not None:
                self.sentiment_table.item(
                    max_idx, j).setBackground(QColor("#b2ff59"))
            if min_idx is not None:
                self.sentiment_table.item(
                    min_idx, j).setBackground(QColor("#ffcdd2"))

    def _initialize_sentiment_service(self):
        """初始化情绪数据服务"""
        try:
            from core.containers.service_container import get_service_container
        except ImportError:
            logger.debug("ServiceContainer不可用，跳过情绪数据服务初始化")
            self._sentiment_service = None
            return

        try:
            from core.services.sentiment_data_service import SentimentDataService
        except ImportError:
            logger.debug("SentimentDataService模块不存在（已清理），跳过情绪数据服务初始化")
            self._sentiment_service = None
            return

        try:
            container = get_service_container()
            if container:
                try:
                    self._sentiment_service = container.resolve(SentimentDataService)
                    logger.info("市场情绪组件：情绪数据服务初始化成功")
                except Exception as resolve_error:
                    logger.warning(f"无法从服务容器获取情绪数据服务: {resolve_error}")
                    self._try_manual_service_creation()
            else:
                self._try_manual_service_creation()
        except Exception as e:
            logger.error(f"市场情绪组件：初始化情绪数据服务失败: {e}")
            self._sentiment_service = None

    def _try_manual_service_creation(self):
        """尝试手动创建情绪数据服务"""
        try:
            from core.services.sentiment_data_service import SentimentDataService, SentimentDataServiceConfig
        except ImportError:
            logger.debug("SentimentDataService模块不存在（已清理），跳过手动创建情绪数据服务")
            self._sentiment_service = None
            return

        try:
            from plugins.sentiment_data_sources import (
                FMPSentimentPlugin, ExordeSentimentPlugin, NewsSentimentPlugin,
                VIXSentimentPlugin, CryptoSentimentPlugin, AVAILABLE_PLUGINS
            )

            # 创建服务配置
            config = SentimentDataServiceConfig(
                cache_duration_minutes=5,
                auto_refresh_interval_minutes=10,
                enable_auto_refresh=False  # 在UI中手动控制刷新
            )

            # 创建服务
            self._sentiment_service = SentimentDataService(config=config)  # log_manager已迁移到Loguru

            # 注册真实数据源插件（排除模拟数据插件）
            plugin_configs = [
                # 只注册有真实API的插件
                # ('fmp_sentiment', FMPSentimentPlugin, 10, 0.25),  # 需要API Key
                # ('exorde_sentiment', ExordeSentimentPlugin, 20, 0.20),  # 需要API Key
                # ('news_sentiment', NewsSentimentPlugin, 30, 0.15),  # 基于模拟数据，已禁用
                ('vix_sentiment', VIXSentimentPlugin, 40, 0.50),  # 有真实数据源（Yahoo Finance）
                # ('crypto_sentiment', CryptoSentimentPlugin, 50, 0.15),  # 需要API Key
            ]

            registered_count = 0
            for plugin_name, plugin_class, priority, weight in plugin_configs:
                try:
                    plugin_instance = plugin_class()
                    if self._sentiment_service.register_plugin(plugin_name, plugin_instance, priority=priority, weight=weight):
                        registered_count += 1
                        logger.info(f" 市场情绪组件：注册插件: {plugin_name}")
                except Exception as e:
                    logger.warning(f" 市场情绪组件：注册插件 {plugin_name} 失败: {e}")

            # 初始化服务
            if self._sentiment_service.initialize():
                logger.info(f" 市场情绪组件：手动创建情绪数据服务成功，已注册 {registered_count} 个插件")
            else:
                logger.error("市场情绪组件：情绪数据服务初始化失败")
                self._sentiment_service = None

        except Exception as e:
            logger.error(f" 市场情绪组件：手动创建情绪数据服务失败: {e}")
            self._sentiment_service = None

