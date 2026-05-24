from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强的信号UI组件
集成真实数据和专业布局设计
"""

from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QLabel, QFrame, QPushButton, QTabWidget, QScrollArea,
                             QGroupBox, QGridLayout, QProgressBar, QTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt5.QtGui import QFont, QColor

from core.services.integrated_signal_aggregator_service import IntegratedSignalAggregatorService
try:
    from gui.widgets.sentiment_overview_widget import SentimentOverviewWidget
except ImportError:
    SentimentOverviewWidget = None
from gui.widgets.smart_alert_widget import SmartAlertWidget
from gui.widgets.signal_aggregator import AggregatedAlert, TradingSignal

logger = logger


class RealDataWorker(QThread):
    """真实数据获取工作线程"""

    data_updated = pyqtSignal(str, dict)  # stock_code, data
    alerts_updated = pyqtSignal(str, list)  # stock_code, alerts
    error_occurred = pyqtSignal(str, str)  # stock_code, error_message

    def __init__(self, signal_service: IntegratedSignalAggregatorService):
        super().__init__()
        self.signal_service = signal_service
        self.current_stock_code = None
        self.is_running = False

    def set_stock_code(self, stock_code: str):
        """设置要分析的股票代码"""
        self.current_stock_code = stock_code

    def run(self):
        """执行数据获取和分析"""
        if not self.current_stock_code or not self.signal_service:
            return

        self.is_running = True

        try:
            import asyncio

            # 创建事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # 分析股票信号
                alerts = loop.run_until_complete(
                    self.signal_service.analyze_stock_signals(self.current_stock_code)
                )

                if alerts:
                    self.alerts_updated.emit(self.current_stock_code, alerts)

                # 获取统计信息
                stats = self.signal_service.get_signal_statistics(self.current_stock_code)
                self.data_updated.emit(self.current_stock_code, stats)

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"数据获取失败: {e}")
            self.error_occurred.emit(self.current_stock_code, str(e))
        finally:
            self.is_running = False


class ProfessionalPriceWidget(QFrame):
    """专业价格显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)

        # 标题
        title_label = QLabel("实时行情")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; padding-bottom: 5px;")

        # 价格信息网格
        grid_layout = QGridLayout()

        # 当前价格
        self.price_label = QLabel("---")
        price_font = QFont()
        price_font.setPointSize(16)
        price_font.setBold(True)
        self.price_label.setFont(price_font)

        # 涨跌幅
        self.change_label = QLabel("---")
        change_font = QFont()
        change_font.setPointSize(10)
        self.change_label.setFont(change_font)

        # 成交量
        self.volume_label = QLabel("成交量: ---")
        self.volume_label.setStyleSheet("color: #7f8c8d; font-size: 9pt;")

        # 成交额
        self.amount_label = QLabel("成交额: ---")
        self.amount_label.setStyleSheet("color: #7f8c8d; font-size: 9pt;")

        grid_layout.addWidget(QLabel("当前价格:"), 0, 0)
        grid_layout.addWidget(self.price_label, 0, 1)
        grid_layout.addWidget(QLabel("涨跌幅:"), 1, 0)
        grid_layout.addWidget(self.change_label, 1, 1)
        grid_layout.addWidget(self.volume_label, 2, 0, 1, 2)
        grid_layout.addWidget(self.amount_label, 3, 0, 1, 2)

        layout.addWidget(title_label)
        layout.addLayout(grid_layout)
        layout.addStretch()

        self.setLayout(layout)

    def update_price_data(self, price_data: Dict[str, Any]):
        """更新价格数据"""
        try:
            current_price = price_data.get('current_price', 0)
            change_percent = price_data.get('change_percent', 0)
            volume = price_data.get('volume', 0)
            amount = price_data.get('amount', 0)

            # 更新价格
            self.price_label.setText(f"{current_price:.2f}")

            # 更新涨跌幅（带颜色）
            change_text = f"{change_percent:+.2f}%"
            if change_percent > 0:
                color = "#e74c3c"  # 红色
                self.price_label.setStyleSheet("color: #e74c3c;")
            elif change_percent < 0:
                color = "#27ae60"  # 绿色
                self.price_label.setStyleSheet("color: #27ae60;")
            else:
                color = "#2c3e50"  # 默认
                self.price_label.setStyleSheet("color: #2c3e50;")

            self.change_label.setText(change_text)
            self.change_label.setStyleSheet(f"color: {color}; font-weight: bold;")

            # 更新成交量和成交额
            self.volume_label.setText(f"成交量: {self._format_volume(volume)}")
            self.amount_label.setText(f"成交额: {self._format_amount(amount)}")

        except Exception as e:
            logger.error(f"更新价格数据失败: {e}")

    def _format_volume(self, volume: float) -> str:
        """格式化成交量"""
        if volume >= 10000:
            return f"{volume/10000:.1f}万手"
        else:
            return f"{volume:.0f}手"

    def _format_amount(self, amount: float) -> str:
        """格式化成交额"""
        if amount >= 100000000:  # 1亿
            return f"{amount/100000000:.1f}亿"
        elif amount >= 10000:  # 1万
            return f"{amount/10000:.1f}万"
        else:
            return f"{amount:.0f}"


class TechnicalIndicatorSummary(QFrame):
    """技术指标摘要组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.indicator_widgets = {}
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)

        # 标题
        title_label = QLabel("技术指标")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; padding-bottom: 5px;")

        # 指标网格
        self.grid_layout = QGridLayout()
        self.create_indicator_widgets()

        layout.addWidget(title_label)
        layout.addLayout(self.grid_layout)
        layout.addStretch()

        self.setLayout(layout)

    def create_indicator_widgets(self):
        """创建指标显示组件"""
        indicators = [
            ("RSI", "相对强弱"),
            ("MACD", "异同移动平均"),
            ("KDJ", "随机指标"),
            ("BOLL", "布林带")
        ]

        for i, (key, name) in enumerate(indicators):
            row = i // 2
            col = (i % 2) * 2

            # 指标名称
            name_label = QLabel(f"{key}:")
            name_label.setStyleSheet("font-size: 9pt; color: #34495e;")

            # 指标值
            value_label = QLabel("---")
            value_label.setStyleSheet("font-size: 9pt; font-weight: bold;")

            self.indicator_widgets[key] = value_label

            self.grid_layout.addWidget(name_label, row, col)
            self.grid_layout.addWidget(value_label, row, col + 1)

    def update_indicators(self, indicators: Dict[str, Any]):
        """更新技术指标"""
        try:
            # RSI
            if 'rsi' in indicators:
                rsi_value = float(indicators['rsi'])
                rsi_text = f"{rsi_value:.1f}"
                rsi_color = self._get_rsi_color(rsi_value)
                self.indicator_widgets['RSI'].setText(rsi_text)
                self.indicator_widgets['RSI'].setStyleSheet(f"color: {rsi_color}; font-weight: bold;")

            # MACD
            if 'macd' in indicators:
                macd_data = indicators['macd']
                if isinstance(macd_data, dict):
                    dif = float(macd_data.get('dif', 0))
                    dea = float(macd_data.get('dea', 0))
                    signal = "多头" if dif > dea else "空头"
                    color = "#e74c3c" if dif > dea else "#27ae60"
                    self.indicator_widgets['MACD'].setText(signal)
                    self.indicator_widgets['MACD'].setStyleSheet(f"color: {color}; font-weight: bold;")

            # KDJ
            if 'kdj' in indicators:
                kdj_data = indicators['kdj']
                if isinstance(kdj_data, dict):
                    k = float(kdj_data.get('k', 50))
                    d = float(kdj_data.get('d', 50))
                    if k > 80 and d > 80:
                        signal = "超买"
                        color = "#e74c3c"
                    elif k < 20 and d < 20:
                        signal = "超卖"
                        color = "#27ae60"
                    else:
                        signal = "正常"
                        color = "#3498db"

                    self.indicator_widgets['KDJ'].setText(signal)
                    self.indicator_widgets['KDJ'].setStyleSheet(f"color: {color}; font-weight: bold;")

            # BOLL
            if 'bollinger' in indicators:
                boll_data = indicators['bollinger']
                if isinstance(boll_data, dict):
                    # 简化显示布林带状态
                    self.indicator_widgets['BOLL'].setText("正常")
                    self.indicator_widgets['BOLL'].setStyleSheet("color: #3498db; font-weight: bold;")

        except Exception as e:
            logger.error(f"更新技术指标失败: {e}")

    def _get_rsi_color(self, rsi_value: float) -> str:
        """获取RSI颜色"""
        if rsi_value >= 70:
            return "#e74c3c"  # 超买 - 红色
        elif rsi_value <= 30:
            return "#27ae60"  # 超卖 - 绿色
        else:
            return "#3498db"  # 正常 - 蓝色


class ProfessionalTradingInterface(QWidget):
    """专业交易界面"""

    # 信号
    stock_changed = pyqtSignal(str)  # 股票代码变化

    def __init__(self, signal_service: IntegratedSignalAggregatorService, parent=None):
        super().__init__(parent)
        self.signal_service = signal_service
        self.current_stock_code = None

        # UI组件
        self.price_widget = None
        self.sentiment_widget = None
        self.alert_widget = None
        self.indicator_summary = None

        # 数据工作线程
        self.data_worker = None
        self.update_timer = QTimer()

        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        """初始化UI"""
        # 主布局：左右分割
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧：图表区域占位 (70%)
        chart_placeholder = self.create_chart_placeholder()

        # 右侧：信息面板 (30%)
        info_panel = self.create_info_panel()

        main_splitter.addWidget(chart_placeholder)
        main_splitter.addWidget(info_panel)
        main_splitter.setSizes([700, 300])  # 7:3比例

        # 整体布局
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(main_splitter)
        self.setLayout(layout)

    def create_chart_placeholder(self):
        """创建图表区域占位符"""
        placeholder = QFrame()
        placeholder.setFrameStyle(QFrame.StyledPanel)
        placeholder.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px dashed #dee2e6;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout()

        # 占位符标签
        label = QLabel("主图表区域\n(集成现有图表组件)")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 14pt;
                font-weight: bold;
                border: none;
            }
        """)

        layout.addWidget(label)
        placeholder.setLayout(layout)

        return placeholder

    def create_info_panel(self):
        """创建信息面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # 1. 实时价格信息
        self.price_widget = ProfessionalPriceWidget()
        self.price_widget.setMaximumHeight(150)

        # 2. 情绪概览（轻量级）
        if SentimentOverviewWidget is not None:
            self.sentiment_widget = SentimentOverviewWidget()
            self.sentiment_widget.setMaximumHeight(200)

        # 3. 技术指标摘要
        self.indicator_summary = TechnicalIndicatorSummary()
        self.indicator_summary.setMaximumHeight(150)

        # 4. 智能提醒
        self.alert_widget = SmartAlertWidget()

        layout.addWidget(self.price_widget)
        layout.addWidget(self.sentiment_widget)
        layout.addWidget(self.indicator_summary)
        layout.addWidget(self.alert_widget)
        layout.addStretch()

        panel.setLayout(layout)
        return panel

    def setup_connections(self):
        """设置连接"""
        # 定时器连接
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.setInterval(30000)  # 30秒更新一次

        # 情绪数据更新连接
        if self.sentiment_widget:
            self.sentiment_widget.sentiment_updated.connect(self.on_sentiment_updated)

        # 信号聚合器连接
        if self.signal_service and self.signal_service.signal_aggregator:
            self.signal_service.signal_aggregator.alert_generated.connect(
                self.alert_widget.add_alert)
            self.signal_service.signal_aggregator.signal_detected.connect(
                self._on_signal_detected)

    def set_stock_code(self, stock_code: str):
        """设置股票代码"""
        if stock_code != self.current_stock_code:
            self.current_stock_code = stock_code
            self.stock_changed.emit(stock_code)

            # 立即更新数据
            self.update_data()

            # 启动定时更新
            if not self.update_timer.isActive():
                self.update_timer.start()

    def update_data(self):
        """更新数据"""
        if not self.current_stock_code or not self.signal_service:
            return

        try:
            # 创建数据工作线程
            if self.data_worker and self.data_worker.isRunning():
                return  # 避免重复创建线程

            self.data_worker = RealDataWorker(self.signal_service)
            self.data_worker.set_stock_code(self.current_stock_code)

            # 连接信号
            self.data_worker.data_updated.connect(self.on_data_updated)
            self.data_worker.alerts_updated.connect(self.on_alerts_updated)
            self.data_worker.error_occurred.connect(self.on_error_occurred)

            # 启动线程
            self.data_worker.start()

        except Exception as e:
            logger.error(f"更新数据失败: {e}")

    def on_data_updated(self, stock_code: str, stats: Dict[str, Any]):
        """数据更新回调"""
        try:
            if stock_code != self.current_stock_code:
                return

            logger.info(f"收到股票 {stock_code} 的数据更新")

            # 这里可以根据stats更新价格和指标显示
            # 实际实现中需要从stats中提取相应数据

        except Exception as e:
            logger.error(f"处理数据更新失败: {e}")

    def on_alerts_updated(self, stock_code: str, alerts: List[AggregatedAlert]):
        """警报更新回调"""
        try:
            if stock_code != self.current_stock_code:
                return

            logger.info(f"收到股票 {stock_code} 的 {len(alerts)} 个警报")

            # 更新智能提醒组件
            if self.alert_widget:
                for alert in alerts:
                    self.alert_widget.add_alert(alert)

        except Exception as e:
            logger.error(f"处理警报更新失败: {e}")

    def on_error_occurred(self, stock_code: str, error_message: str):
        """错误处理回调"""
        logger.error(f"股票 {stock_code} 数据获取错误: {error_message}")

    def on_sentiment_updated(self, sentiment_data: Dict[str, Any]):
        """情绪数据更新回调"""
        try:
            logger.debug(f"情绪数据已更新: {list(sentiment_data.keys())}")
        except Exception as e:
            logger.error(f"处理情绪数据更新失败: {e}")

    def _on_signal_detected(self, signal: TradingSignal):
        """单个信号检测回调"""
        try:
            logger.info(f"检测到交易信号: {signal.direction} {signal.message} "
                       f"(强度: {signal.strength.name}, 置信度: {signal.confidence:.0%})")
        except Exception as e:
            logger.error(f"处理信号检测失败: {e}")

    def cleanup(self):
        """清理资源"""
        if self.update_timer.isActive():
            self.update_timer.stop()

        if self.data_worker and self.data_worker.isRunning():
            self.data_worker.quit()
            self.data_worker.wait()


class FloatingSignalPanel(QWidget):
    """浮动信号面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Tool |
            Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.draggable = True
        self.mouse_press_pos = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        # 半透明背景样式
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 0.9);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: white;
            }
            QLabel {
                color: white;
                background: transparent;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 5px;
                color: white;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("实时信号")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self.hide)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_btn)

        # 信号内容区域
        self.content_area = QScrollArea()
        self.content_area.setFixedSize(300, 200)
        self.content_area.setWidgetResizable(True)
        self.content_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.content_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.addStretch()
        content_widget.setLayout(self.content_layout)
        self.content_area.setWidget(content_widget)

        layout.addLayout(title_layout)
        layout.addWidget(self.content_area)

        self.setLayout(layout)
        self.setFixedSize(330, 250)

    def add_signal_message(self, message: str, level: str = "info"):
        """添加信号消息"""
        try:
            # 颜色映射
            colors = {
                "info": "#3498db",
                "warning": "#f39c12",
                "danger": "#e74c3c",
                "success": "#27ae60"
            }

            color = colors.get(level, "#3498db")

            # 创建消息标签
            msg_label = QLabel(message)
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet(f"color: {color}; padding: 5px; font-size: 9pt;")

            # 插入到顶部
            self.content_layout.insertWidget(0, msg_label)

            # 限制消息数量
            if self.content_layout.count() > 20:
                old_widget = self.content_layout.itemAt(19).widget()
                if old_widget:
                    old_widget.deleteLater()

        except Exception as e:
            logger.error(f"添加信号消息失败: {e}")

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton and self.draggable:
            self.mouse_press_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if (event.buttons() == Qt.LeftButton and
            self.mouse_press_pos is not None and
                self.draggable):
            self.move(event.globalPos() - self.mouse_press_pos)
            event.accept()
