from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右键菜单管理器

统一管理各种组件的右键菜单，提供丰富的上下文操作
"""

import sys
import os
import traceback
from typing import Dict, Any, List, Optional, Callable
from PyQt5.QtWidgets import (
    QMenu, QAction, QActionGroup, QWidget, QApplication,
    QMessageBox, QInputDialog, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QIcon, QKeySequence, QCursor

class ContextMenuManager(QObject):
    """右键菜单管理器"""

    # 信号定义
    action_triggered = pyqtSignal(str, dict)  # 动作触发信号
    stock_selected = pyqtSignal(str)  # 股票选择信号
    indicator_changed = pyqtSignal(str, bool)  # 指标变化信号
    period_changed = pyqtSignal(str)  # 周期变化信号
    chart_type_changed = pyqtSignal(str)  # 图表类型变化信号
    export_requested = pyqtSignal(str, dict)  # 导出请求信号

    def __init__(self, parent=None):
        """
        初始化右键菜单管理器

        Args:
            parent: 父对象
        """
        super().__init__(parent)
        self.logger = logger.bind(module=__name__)

        # 菜单缓存
        self.menu_cache = {}

        # 当前上下文
        self.current_context = {}

        # 配置管理器
        self.config_manager = None
        self.data_manager = None

        self.logger.info("右键菜单管理器初始化完成")

    def set_managers(self, config_manager=None, data_manager=None):
        """设置管理器"""
        self.config_manager = config_manager
        self.data_manager = data_manager

    def create_stock_list_menu(self, stock_code: str = None, widget: QWidget = None) -> QMenu:
        """
        创建股票列表右键菜单

        Args:
            stock_code: 股票代码
            widget: 触发菜单的组件

        Returns:
            QMenu: 右键菜单
        """
        try:
            menu = QMenu(widget)
            self.current_context = {'type': 'stock_list',
                                    'stock_code': stock_code, 'widget': widget}

            if stock_code:
                # 股票相关操作
                view_action = QAction("查看详情", menu)
                view_action.setIcon(QIcon(":/icons/view.png"))
                view_action.triggered.connect(lambda: self.action_triggered.emit(
                    "view_detail", self.current_context))
                menu.addAction(view_action)

                add_chart_action = QAction("添加到图表", menu)
                add_chart_action.setIcon(QIcon(":/icons/chart.png"))
                add_chart_action.triggered.connect(
                    lambda: self.action_triggered.emit("add_to_chart", self.current_context))
                menu.addAction(add_chart_action)

                add_watch_action = QAction("添加到自选", menu)
                add_watch_action.setIcon(QIcon(":/icons/star.png"))
                add_watch_action.triggered.connect(
                    lambda: self.action_triggered.emit("add_to_watch", self.current_context))
                menu.addAction(add_watch_action)

                menu.addSeparator()

                # 分析操作
                analyze_menu = QMenu("技术分析", menu)
                analyze_menu.setIcon(QIcon(":/icons/analyze.png"))

                trend_action = QAction("趋势分析", analyze_menu)
                trend_action.triggered.connect(lambda: self.action_triggered.emit(
                    "trend_analysis", self.current_context))
                analyze_menu.addAction(trend_action)

                pattern_action = QAction("形态识别", analyze_menu)
                pattern_action.triggered.connect(lambda: self.action_triggered.emit(
                    "pattern_recognition", self.current_context))
                analyze_menu.addAction(pattern_action)

                support_action = QAction("支撑阻力", analyze_menu)
                support_action.triggered.connect(lambda: self.action_triggered.emit(
                    "support_resistance", self.current_context))
                analyze_menu.addAction(support_action)

                menu.addMenu(analyze_menu)

                # 数据操作
                data_menu = QMenu("数据操作", menu)
                data_menu.setIcon(QIcon(":/icons/data.png"))

                export_action = QAction("导出数据", data_menu)
                export_action.triggered.connect(
                    lambda: self.action_triggered.emit("export_data", self.current_context))
                data_menu.addAction(export_action)

                quality_action = QAction("数据质量检查", data_menu)
                quality_action.triggered.connect(
                    lambda: self.action_triggered.emit("quality_check", self.current_context))
                data_menu.addAction(quality_action)

                update_action = QAction("更新数据", data_menu)
                update_action.triggered.connect(
                    lambda: self.action_triggered.emit("update_data", self.current_context))
                data_menu.addAction(update_action)

                menu.addMenu(data_menu)

                menu.addSeparator()

            # 列表操作
            refresh_action = QAction("刷新列表", menu)
            refresh_action.setIcon(QIcon(":/icons/refresh.png"))
            refresh_action.setShortcut(QKeySequence("F5"))
            refresh_action.triggered.connect(
                lambda: self.action_triggered.emit("refresh_list", self.current_context))
            menu.addAction(refresh_action)

            filter_action = QAction("筛选设置", menu)
            filter_action.setIcon(QIcon(":/icons/filter.png"))
            filter_action.triggered.connect(lambda: self.action_triggered.emit(
                "filter_settings", self.current_context))
            menu.addAction(filter_action)

            return menu

        except Exception as e:
            self.logger.error(f"创建股票列表菜单失败: {e}")
            return QMenu(widget)

    def create_chart_menu(self, chart_type: str = "candlestick", widget: QWidget = None) -> QMenu:
        """
        创建图表右键菜单

        Args:
            chart_type: 图表类型
            widget: 触发菜单的组件

        Returns:
            QMenu: 右键菜单
        """
        try:
            menu = QMenu(widget)
            self.current_context = {'type': 'chart',
                                    'chart_type': chart_type, 'widget': widget}

            # 图表类型切换
            chart_type_menu = QMenu("图表类型", menu)
            chart_type_menu.setIcon(QIcon(":/icons/chart_type.png"))

            chart_type_group = QActionGroup(chart_type_menu)
            chart_types = [
                ("K线图", "candlestick"),
                ("分时图", "line"),
                ("美国线", "ohlc"),
                ("收盘价线", "close")
            ]

            for name, type_code in chart_types:
                action = QAction(name, chart_type_menu)
                action.setCheckable(True)
                action.setChecked(type_code == chart_type)
                action.triggered.connect(
                    lambda checked, t=type_code: self.chart_type_changed.emit(t))
                chart_type_group.addAction(action)
                chart_type_menu.addAction(action)

            menu.addMenu(chart_type_menu)

            # 周期切换
            period_menu = QMenu("时间周期", menu)
            period_menu.setIcon(QIcon(":/icons/period.png"))

            period_group = QActionGroup(period_menu)
            periods = [
                ("1分钟", "1min"),
                ("5分钟", "5min"),
                ("15分钟", "15min"),
                ("30分钟", "30min"),
                ("60分钟", "60min"),
                ("日线", "D"),
                ("周线", "W"),
                ("月线", "M")
            ]

            for name, period_code in periods:
                action = QAction(name, period_menu)
                action.setCheckable(True)
                action.triggered.connect(
                    lambda checked, p=period_code: self.period_changed.emit(p))
                period_group.addAction(action)
                period_menu.addAction(action)

            menu.addMenu(period_menu)

            # 技术指标
            indicator_menu = QMenu("技术指标", menu)
            indicator_menu.setIcon(QIcon(":/icons/indicator.png"))

            # 趋势指标
            trend_menu = QMenu("趋势指标", indicator_menu)
            trend_indicators = [
                ("MA均线", "MA"),
                ("EMA指数均线", "EMA"),
                ("BOLL布林带", "BOLL"),
                ("SAR抛物线", "SAR")
            ]

            for name, indicator_code in trend_indicators:
                action = QAction(name, trend_menu)
                action.setCheckable(True)
                action.triggered.connect(
                    lambda checked, i=indicator_code: self.indicator_changed.emit(i, checked))
                trend_menu.addAction(action)

            indicator_menu.addMenu(trend_menu)

            # 震荡指标
            oscillator_menu = QMenu("震荡指标", indicator_menu)
            oscillator_indicators = [
                ("RSI相对强弱", "RSI"),
                ("KDJ随机指标", "KDJ"),
                ("MACD指数平滑", "MACD"),
                ("CCI顺势指标", "CCI")
            ]

            for name, indicator_code in oscillator_indicators:
                action = QAction(name, oscillator_menu)
                action.setCheckable(True)
                action.triggered.connect(
                    lambda checked, i=indicator_code: self.indicator_changed.emit(i, checked))
                oscillator_menu.addAction(action)

            indicator_menu.addMenu(oscillator_menu)

            # 成交量指标
            volume_menu = QMenu("成交量指标", indicator_menu)
            volume_indicators = [
                ("VOL成交量", "VOL"),
                ("OBV能量潮", "OBV"),
                ("VR成交量比率", "VR")
            ]

            for name, indicator_code in volume_indicators:
                action = QAction(name, volume_menu)
                action.setCheckable(True)
                action.triggered.connect(
                    lambda checked, i=indicator_code: self.indicator_changed.emit(i, checked))
                volume_menu.addAction(action)

            indicator_menu.addMenu(volume_menu)

            menu.addMenu(indicator_menu)

            menu.addSeparator()

            # 图表操作
            zoom_in_action = QAction("放大", menu)
            zoom_in_action.setIcon(QIcon(":/icons/zoom_in.png"))
            zoom_in_action.setShortcut(QKeySequence("Ctrl++"))
            zoom_in_action.triggered.connect(
                lambda: self.action_triggered.emit("zoom_in", self.current_context))
            menu.addAction(zoom_in_action)

            zoom_out_action = QAction("缩小", menu)
            zoom_out_action.setIcon(QIcon(":/icons/zoom_out.png"))
            zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
            zoom_out_action.triggered.connect(
                lambda: self.action_triggered.emit("zoom_out", self.current_context))
            menu.addAction(zoom_out_action)

            reset_zoom_action = QAction("重置缩放", menu)
            reset_zoom_action.setIcon(QIcon(":/icons/reset.png"))
            reset_zoom_action.setShortcut(QKeySequence("Ctrl+0"))
            reset_zoom_action.triggered.connect(
                lambda: self.action_triggered.emit("reset_zoom", self.current_context))
            menu.addAction(reset_zoom_action)

            menu.addSeparator()

            # 分析工具
            analysis_menu = QMenu("分析工具", menu)
            analysis_menu.setIcon(QIcon(":/icons/tools.png"))

            crosshair_action = QAction("十字光标", analysis_menu)
            crosshair_action.setCheckable(True)
            crosshair_action.triggered.connect(lambda checked: self.action_triggered.emit(
                "crosshair", {**self.current_context, 'enabled': checked}))
            analysis_menu.addAction(crosshair_action)

            trend_line_action = QAction("趋势线", analysis_menu)
            trend_line_action.triggered.connect(
                lambda: self.action_triggered.emit("trend_line", self.current_context))
            analysis_menu.addAction(trend_line_action)

            fibonacci_action = QAction("斐波那契回调", analysis_menu)
            fibonacci_action.triggered.connect(
                lambda: self.action_triggered.emit("fibonacci", self.current_context))
            analysis_menu.addAction(fibonacci_action)

            rectangle_action = QAction("矩形选区", analysis_menu)
            rectangle_action.triggered.connect(
                lambda: self.action_triggered.emit("rectangle", self.current_context))
            analysis_menu.addAction(rectangle_action)

            menu.addMenu(analysis_menu)

            # 数据操作
            data_menu = QMenu("数据操作", menu)
            data_menu.setIcon(QIcon(":/icons/data.png"))

            export_chart_action = QAction("导出图表", data_menu)
            export_chart_action.triggered.connect(
                lambda: self.action_triggered.emit("export_chart", self.current_context))
            data_menu.addAction(export_chart_action)

            export_data_action = QAction("导出数据", data_menu)
            export_data_action.triggered.connect(
                lambda: self.action_triggered.emit("export_data", self.current_context))
            data_menu.addAction(export_data_action)

            statistics_action = QAction("区间统计", data_menu)
            statistics_action.triggered.connect(lambda: self.action_triggered.emit(
                "interval_statistics", self.current_context))
            data_menu.addAction(statistics_action)

            menu.addMenu(data_menu)

            return menu

        except Exception as e:
            self.logger.error(f"创建图表菜单失败: {e}")
            return QMenu(widget)

    def create_watchlist_menu(self, stock_code: str = None, widget: QWidget = None) -> QMenu:
        """
        创建自选股右键菜单

        Args:
            stock_code: 股票代码
            widget: 触发菜单的组件

        Returns:
            QMenu: 右键菜单
        """
        try:
            menu = QMenu(widget)
            self.current_context = {'type': 'watchlist',
                                    'stock_code': stock_code, 'widget': widget}

            if stock_code:
                # 股票操作
                view_action = QAction("查看详情", menu)
                view_action.setIcon(QIcon(":/icons/view.png"))
                view_action.triggered.connect(lambda: self.action_triggered.emit(
                    "view_detail", self.current_context))
                menu.addAction(view_action)

                chart_action = QAction("显示图表", menu)
                chart_action.setIcon(QIcon(":/icons/chart.png"))
                chart_action.triggered.connect(
                    lambda: self.action_triggered.emit("show_chart", self.current_context))
                menu.addAction(chart_action)

                menu.addSeparator()

                # 自选股操作
                remove_action = QAction("移出自选", menu)
                remove_action.setIcon(QIcon(":/icons/remove.png"))
                remove_action.triggered.connect(lambda: self.action_triggered.emit(
                    "remove_from_watch", self.current_context))
                menu.addAction(remove_action)

                move_up_action = QAction("上移", menu)
                move_up_action.setIcon(QIcon(":/icons/up.png"))
                move_up_action.triggered.connect(
                    lambda: self.action_triggered.emit("move_up", self.current_context))
                menu.addAction(move_up_action)

                move_down_action = QAction("下移", menu)
                move_down_action.setIcon(QIcon(":/icons/down.png"))
                move_down_action.triggered.connect(
                    lambda: self.action_triggered.emit("move_down", self.current_context))
                menu.addAction(move_down_action)

                menu.addSeparator()

                # 分组操作
                group_menu = QMenu("分组管理", menu)
                group_menu.setIcon(QIcon(":/icons/group.png"))

                create_group_action = QAction("创建分组", group_menu)
                create_group_action.triggered.connect(
                    lambda: self.action_triggered.emit("create_group", self.current_context))
                group_menu.addAction(create_group_action)

                move_to_group_action = QAction("移动到分组", group_menu)
                move_to_group_action.triggered.connect(
                    lambda: self.action_triggered.emit("move_to_group", self.current_context))
                group_menu.addAction(move_to_group_action)

                menu.addMenu(group_menu)

                # 提醒设置
                alert_menu = QMenu("价格提醒", menu)
                alert_menu.setIcon(QIcon(":/icons/alert.png"))

                price_alert_action = QAction("设置价格提醒", alert_menu)
                price_alert_action.triggered.connect(
                    lambda: self.action_triggered.emit("price_alert", self.current_context))
                alert_menu.addAction(price_alert_action)

                volume_alert_action = QAction("设置成交量提醒", alert_menu)
                volume_alert_action.triggered.connect(
                    lambda: self.action_triggered.emit("volume_alert", self.current_context))
                alert_menu.addAction(volume_alert_action)

                menu.addMenu(alert_menu)

                menu.addSeparator()

            # 列表操作
            add_stock_action = QAction("添加股票", menu)
            add_stock_action.setIcon(QIcon(":/icons/add.png"))
            add_stock_action.triggered.connect(
                lambda: self.action_triggered.emit("add_stock", self.current_context))
            menu.addAction(add_stock_action)

            import_action = QAction("导入自选股", menu)
            import_action.setIcon(QIcon(":/icons/import.png"))
            import_action.triggered.connect(lambda: self.action_triggered.emit(
                "import_watchlist", self.current_context))
            menu.addAction(import_action)

            export_action = QAction("导出自选股", menu)
            export_action.setIcon(QIcon(":/icons/export.png"))
            export_action.triggered.connect(lambda: self.action_triggered.emit(
                "export_watchlist", self.current_context))
            menu.addAction(export_action)

            return menu

        except Exception as e:
            self.logger.error(f"创建自选股菜单失败: {e}")
            return QMenu(widget)

    def create_indicator_menu(self, indicator_name: str = None, widget: QWidget = None) -> QMenu:
        """
        创建技术指标右键菜单

        Args:
            indicator_name: 指标名称
            widget: 触发菜单的组件

        Returns:
            QMenu: 右键菜单
        """
        try:
            menu = QMenu(widget)
            self.current_context = {
                'type': 'indicator', 'indicator_name': indicator_name, 'widget': widget}

            if indicator_name:
                # 指标操作
                settings_action = QAction("指标设置", menu)
                settings_action.setIcon(QIcon(":/icons/settings.png"))
                settings_action.triggered.connect(lambda: self.action_triggered.emit(
                    "indicator_settings", self.current_context))
                menu.addAction(settings_action)

                remove_action = QAction("移除指标", menu)
                remove_action.setIcon(QIcon(":/icons/remove.png"))
                remove_action.triggered.connect(lambda: self.action_triggered.emit(
                    "remove_indicator", self.current_context))
                menu.addAction(remove_action)

                menu.addSeparator()

            # 添加指标
            add_menu = QMenu("添加指标", menu)
            add_menu.setIcon(QIcon(":/icons/add.png"))

            # 按分类添加指标
            categories = {
                "趋势指标": ["MA", "EMA", "BOLL", "SAR", "MACD"],
                "震荡指标": ["RSI", "KDJ", "CCI", "WR"],
                "成交量指标": ["VOL", "OBV", "VR", "AD"],
                "其他指标": ["ATR", "BIAS", "ROC", "PSY"]
            }

            for category, indicators in categories.items():
                category_menu = QMenu(category, add_menu)
                for indicator in indicators:
                    action = QAction(indicator, category_menu)
                    action.triggered.connect(lambda checked, i=indicator: self.action_triggered.emit(
                        "add_indicator", {**self.current_context, 'indicator': i}))
                    category_menu.addAction(action)
                add_menu.addMenu(category_menu)

            menu.addMenu(add_menu)

            # 指标模板
            template_menu = QMenu("指标模板", menu)
            template_menu.setIcon(QIcon(":/icons/template.png"))

            save_template_action = QAction("保存模板", template_menu)
            save_template_action.triggered.connect(
                lambda: self.action_triggered.emit("save_template", self.current_context))
            template_menu.addAction(save_template_action)

            load_template_action = QAction("加载模板", template_menu)
            load_template_action.triggered.connect(
                lambda: self.action_triggered.emit("load_template", self.current_context))
            template_menu.addAction(load_template_action)

            menu.addMenu(template_menu)

            return menu

        except Exception as e:
            self.logger.error(f"创建指标菜单失败: {e}")
            return QMenu(widget)

    def create_data_table_menu(self, table_type: str = "kdata", widget: QWidget = None) -> QMenu:
        """
        创建数据表格右键菜单

        Args:
            table_type: 表格类型
            widget: 触发菜单的组件

        Returns:
            QMenu: 右键菜单
        """
        try:
            menu = QMenu(widget)
            self.current_context = {'type': 'data_table',
                                    'table_type': table_type, 'widget': widget}

            # 表格操作
            copy_action = QAction("复制", menu)
            copy_action.setIcon(QIcon(":/icons/copy.png"))
            copy_action.setShortcut(QKeySequence("Ctrl+C"))
            copy_action.triggered.connect(
                lambda: self.action_triggered.emit("copy_data", self.current_context))
            menu.addAction(copy_action)

            copy_all_action = QAction("复制全部", menu)
            copy_all_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
            copy_all_action.triggered.connect(
                lambda: self.action_triggered.emit("copy_all_data", self.current_context))
            menu.addAction(copy_all_action)

            menu.addSeparator()

            # 导出操作
            export_excel_action = QAction("导出到Excel", menu)
            export_excel_action.setIcon(QIcon(":/icons/excel.png"))
            export_excel_action.triggered.connect(
                lambda: self.action_triggered.emit("export_excel", self.current_context))
            menu.addAction(export_excel_action)

            export_csv_action = QAction("导出到CSV", menu)
            export_csv_action.setIcon(QIcon(":/icons/csv.png"))
            export_csv_action.triggered.connect(
                lambda: self.action_triggered.emit("export_csv", self.current_context))
            menu.addAction(export_csv_action)

            menu.addSeparator()

            # 视图操作
            view_menu = QMenu("视图设置", menu)
            view_menu.setIcon(QIcon(":/icons/view.png"))

            column_action = QAction("列设置", view_menu)
            column_action.triggered.connect(lambda: self.action_triggered.emit(
                "column_settings", self.current_context))
            view_menu.addAction(column_action)

            filter_action = QAction("筛选设置", view_menu)
            filter_action.triggered.connect(lambda: self.action_triggered.emit(
                "filter_settings", self.current_context))
            view_menu.addAction(filter_action)

            sort_action = QAction("排序设置", view_menu)
            sort_action.triggered.connect(lambda: self.action_triggered.emit(
                "sort_settings", self.current_context))
            view_menu.addAction(sort_action)

            menu.addMenu(view_menu)

            # 刷新
            refresh_action = QAction("刷新数据", menu)
            refresh_action.setIcon(QIcon(":/icons/refresh.png"))
            refresh_action.setShortcut(QKeySequence("F5"))
            refresh_action.triggered.connect(
                lambda: self.action_triggered.emit("refresh_data", self.current_context))
            menu.addAction(refresh_action)

            return menu

        except Exception as e:
            self.logger.error(f"创建数据表格菜单失败: {e}")
            return QMenu(widget)

    def show_context_menu(self, menu_type: str, position=None, **kwargs) -> QMenu:
        """
        显示右键菜单

        Args:
            menu_type: 菜单类型
            position: 显示位置
            **kwargs: 其他参数

        Returns:
            QMenu: 创建的菜单
        """
        try:
            menu = None

            if menu_type == "stock_list":
                menu = self.create_stock_list_menu(
                    kwargs.get('stock_code'),
                    kwargs.get('widget')
                )
            elif menu_type == "chart":
                menu = self.create_chart_menu(
                    kwargs.get('chart_type', 'candlestick'),
                    kwargs.get('widget')
                )
            elif menu_type == "watchlist":
                menu = self.create_watchlist_menu(
                    kwargs.get('stock_code'),
                    kwargs.get('widget')
                )
            elif menu_type == "indicator":
                menu = self.create_indicator_menu(
                    kwargs.get('indicator_name'),
                    kwargs.get('widget')
                )
            elif menu_type == "data_table":
                menu = self.create_data_table_menu(
                    kwargs.get('table_type', 'kdata'),
                    kwargs.get('widget')
                )

            if menu:
                if position:
                    menu.exec_(position)
                else:
                    menu.exec_(QCursor.pos())

            return menu

        except Exception as e:
            self.logger.error(f"显示右键菜单失败: {e}")
            return None

    def handle_action(self, action_name: str, context: Dict[str, Any]):
        """
        处理菜单动作

        Args:
            action_name: 动作名称
            context: 上下文信息
        """
        try:
            self.logger.debug(f"处理菜单动作: {action_name}, 上下文: {context}")

            # 发射信号，由具体的处理器处理
            self.action_triggered.emit(action_name, context)

        except Exception as e:
            self.logger.error(f"处理菜单动作失败: {e}")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel

    app = QApplication(sys.argv)

    # 测试窗口
    window = QMainWindow()
    window.setWindowTitle("右键菜单测试")
    window.setGeometry(100, 100, 800, 600)

    label = QLabel("右键点击测试菜单", window)
    label.setAlignment(Qt.AlignCenter)
    window.setCentralWidget(label)

    # 创建菜单管理器
    menu_manager = ContextMenuManager()

    def show_test_menu():
        menu_manager.show_context_menu(
            "stock_list",
            stock_code="000001",
            widget=label
        )

    # 设置右键事件
    def contextMenuEvent(event):
        show_test_menu()

    label.contextMenuEvent = contextMenuEvent

    window.show()
    sys.exit(app.exec_())
