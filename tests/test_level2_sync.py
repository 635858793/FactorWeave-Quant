#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Level-2数据面板与左侧面板的同步功能
"""

import sys
import asyncio
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PyQt5.QtCore import QTimer
from loguru import logger

from core.events.event_bus import EventBus
from core.events.types import StockSelectedEvent
from gui.widgets.enhanced_ui.level2_data_panel import Level2DataPanel


class TestMainWindow(QMainWindow):
    """测试主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Level-2数据面板同步功能测试")
        self.setGeometry(100, 100, 1200, 800)

        # 创建事件总线
        self.event_bus = EventBus()

        # 创建主部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建测试按钮
        test_layout = QVBoxLayout()
        
        self.status_label = QLabel("状态: 等待测试")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: blue;")
        test_layout.addWidget(self.status_label)

        # 测试按钮1：选择股票A
        btn1 = QPushButton("选择股票A (000001)")
        btn1.clicked.connect(lambda: self._select_stock("000001", "平安银行"))
        test_layout.addWidget(btn1)

        # 测试按钮2：选择股票B
        btn2 = QPushButton("选择股票B (600000)")
        btn2.clicked.connect(lambda: self._select_stock("600000", "浦发银行"))
        test_layout.addWidget(btn2)

        # 测试按钮3：选择股票C
        btn3 = QPushButton("选择股票C (000002)")
        btn3.clicked.connect(lambda: self._select_stock("000002", "万科A"))
        test_layout.addWidget(btn3)

        # 测试按钮4：快速切换股票
        btn4 = QPushButton("快速切换股票 (测试防抖)")
        btn4.clicked.connect(self._test_debounce)
        test_layout.addWidget(btn4)

        layout.addLayout(test_layout)

        # 创建Level-2数据面板
        self.level2_panel = Level2DataPanel(
            parent=self,
            event_bus=self.event_bus
        )
        layout.addWidget(self.level2_panel)

        # 连接信号
        self.level2_panel.symbol_selected.connect(self._on_symbol_selected)
        self.level2_panel.error_occurred.connect(self._on_error)

        logger.info("测试窗口初始化完成")

    def _select_stock(self, stock_code: str, stock_name: str):
        """选择股票"""
        try:
            # 创建股票选择事件
            event = StockSelectedEvent(
                stock_code=stock_code,
                stock_name=stock_name,
                market="深圳" if stock_code.startswith("0") else "上海",
                period="D",
                time_range="1M"
            )

            # 发布事件
            self.event_bus.publish(event)

            self.status_label.setText(f"状态: 已选择 {stock_name} ({stock_code})")
            logger.info(f"已发布股票选择事件: {stock_name} ({stock_code})")

        except Exception as e:
            logger.error(f"选择股票失败: {e}")
            self.status_label.setText(f"状态: 选择股票失败 - {e}")

    def _test_debounce(self):
        """测试防抖功能"""
        try:
            logger.info("开始测试防抖功能")

            # 快速切换股票
            stocks = [
                ("000001", "平安银行"),
                ("600000", "浦发银行"),
                ("000002", "万科A"),
                ("600036", "招商银行"),
                ("000858", "五粮液")
            ]

            for i, (code, name) in enumerate(stocks):
                QTimer.singleShot(i * 100, lambda c=code, n=name: self._select_stock(c, n))

            self.status_label.setText("状态: 正在测试防抖功能...")

        except Exception as e:
            logger.error(f"测试防抖功能失败: {e}")
            self.status_label.setText(f"状态: 测试防抖功能失败 - {e}")

    def _on_symbol_selected(self, symbol: str):
        """股票选择信号处理"""
        logger.info(f"Level2DataPanel股票选择信号: {symbol}")
        self.status_label.setText(f"状态: Level2DataPanel已同步到 {symbol}")

    def _on_error(self, error: str):
        """错误信号处理"""
        logger.error(f"Level2DataPanel错误: {error}")
        self.status_label.setText(f"状态: 错误 - {error}")


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 创建测试窗口
    window = TestMainWindow()
    window.show()

    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
