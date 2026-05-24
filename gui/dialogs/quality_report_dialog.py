#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量报告对话框

提供数据质量检查结果的可视化展示和分析功能
"""

import ast
import sys
import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QComboBox, QLineEdit, QPushButton, QTabWidget, QGroupBox,
    QFormLayout, QHeaderView, QMessageBox, QFileDialog, QWidget,
    QGridLayout, QCheckBox, QSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .base_dialog import BaseDialog

# 尝试导入可视化库
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

class QualityReportDialog(BaseDialog):
    """数据质量报告对话框"""

    def __init__(self, reports: List[Dict[str, Any]], parent=None):
        """
        初始化数据质量报告对话框

        Args:
            reports: 质量报告数据列表
            parent: 父窗口
        """
        super().__init__(
            parent,
            title="数据质量报告",
            size=(1400, 900),
            settings_key="QualityReportDialog"
        )
        self.reports = reports
        self.filtered_reports = reports.copy()

        self.init_ui()
        self.fill_table_and_charts()

    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 创建筛选区域
        filter_widget = self.create_filter_widget()
        layout.addWidget(filter_widget)

        # 创建表格
        self.create_table()
        layout.addWidget(self.table)

        # 创建可视化标签页
        if WEB_ENGINE_AVAILABLE and PLOTLY_AVAILABLE:
            chart_tabs = self.create_chart_tabs()
            layout.addWidget(chart_tabs)
        else:
            # 如果没有可视化库，显示提示信息
            info_label = QLabel("可视化功能需要安装 plotly 和 PyQtWebEngine")
            info_label.setStyleSheet("color: orange; padding: 10px;")
            layout.addWidget(info_label)

        # 创建按钮区域
        button_widget = self.create_button_widget()
        layout.addWidget(button_widget)

    def create_filter_widget(self) -> QWidget:
        """创建筛选区域"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 最低评分筛选
        layout.addWidget(QLabel("最低评分:"))
        self.filter_score = QComboBox()
        self.filter_score.addItems(["全部", "60", "70", "80", "90"])
        self.filter_score.currentTextChanged.connect(self.apply_filters)
        layout.addWidget(self.filter_score)

        # 分组方式
        layout.addWidget(QLabel("分组:"))
        self.group_combo = QComboBox()
        group_fields = ["无分组", "市场", "行业", "评分区间"]
        self.group_combo.addItems(group_fields)
        self.group_combo.currentTextChanged.connect(self.apply_filters)
        layout.addWidget(self.group_combo)

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索股票代码/异常/警告...")
        self.search_edit.textChanged.connect(self.apply_filters)
        layout.addWidget(self.search_edit)

        layout.addStretch()
        return widget

    def create_table(self):
        """创建数据表格"""
        self.table = QTableWidget()
        columns = [
            "股票代码", "评分", "市场", "行业", "缺失字段",
            "异常值", "空值分布", "价格关系异常", "业务逻辑异常",
            "主要错误", "主要警告"
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

    def create_chart_tabs(self) -> QTabWidget:
        """创建可视化标签页"""
        tabs = QTabWidget()

        if WEB_ENGINE_AVAILABLE:
            # 字段分布直方图
            self.hist_view = QWebEngineView()
            tabs.addTab(self.hist_view, "字段分布直方图")

            # 字段箱线图
            self.box_view = QWebEngineView()
            tabs.addTab(self.box_view, "字段箱线图")

            # 异常点可视化
            self.outlier_view = QWebEngineView()
            tabs.addTab(self.outlier_view, "异常点分布")

            # 评分趋势折线图
            self.score_trend_view = QWebEngineView()
            tabs.addTab(self.score_trend_view, "评分趋势")

            # 批量分布热力图
            self.heatmap_view = QWebEngineView()
            tabs.addTab(self.heatmap_view, "分布热力图")

            # 地图（如有地理信息）
            self.map_view = QWebEngineView()
            tabs.addTab(self.map_view, "异常分布地图")

        return tabs

    def create_button_widget(self) -> QWidget:
        """创建按钮区域"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 导出按钮
        export_btn = QPushButton("导出Excel")
        export_btn.clicked.connect(self.export_data)
        layout.addWidget(export_btn)

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.fill_table_and_charts)
        layout.addWidget(refresh_btn)

        layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return widget

    def apply_filters(self):
        """应用筛选条件"""
        try:
            min_score = 0 if self.filter_score.currentText(
            ) == "全部" else int(self.filter_score.currentText())
            keyword = self.search_edit.text().strip().lower()

            self.filtered_reports = []
            for report in self.reports:
                # 评分筛选
                if report.get("quality_score", 100) < min_score:
                    continue

                # 关键词筛选
                if keyword:
                    searchable_text = " ".join([
                        str(report.get("code", "")),
                        str(report.get("errors", "")),
                        str(report.get("warnings", ""))
                    ]).lower()

                    if keyword not in searchable_text:
                        continue

                self.filtered_reports.append(report)

            # 重新填充表格和图表
            self.fill_table_and_charts()

        except Exception as e:
            logger.error(f"应用筛选失败: {e}")

    def fill_table_and_charts(self):
        """填充表格和图表数据"""
        try:
            self.fill_table()
            if WEB_ENGINE_AVAILABLE and PLOTLY_AVAILABLE:
                self.fill_charts()
        except Exception as e:
            logger.error(f"填充数据失败: {e}")

    def fill_table(self):
        """填充表格数据"""
        try:
            group_by = self.group_combo.currentText()

            # 根据分组方式组织数据
            group_map = self.group_data(group_by)

            # 清空表格
            self.table.setRowCount(0)

            # 填充表格数据
            for group, group_list in group_map.items():
                for report in group_list:
                    row = self.table.rowCount()
                    self.table.insertRow(row)

                    # 填充各列数据
                    self.table.setItem(row, 0, QTableWidgetItem(
                        str(report.get("code", ""))))
                    self.table.setItem(row, 1, QTableWidgetItem(
                        str(report.get("quality_score", ""))))
                    self.table.setItem(row, 2, QTableWidgetItem(
                        str(report.get("market", ""))))
                    self.table.setItem(row, 3, QTableWidgetItem(
                        str(report.get("industry", ""))))
                    self.table.setItem(row, 4, QTableWidgetItem(
                        str(report.get("missing_fields", ""))))
                    self.table.setItem(row, 5, QTableWidgetItem(
                        str(report.get("anomaly_stats", ""))))
                    self.table.setItem(row, 6, QTableWidgetItem(
                        str(report.get("empty_ratio", ""))))
                    self.table.setItem(row, 7, QTableWidgetItem(
                        str(report.get("price_relation_errors", ""))))
                    self.table.setItem(row, 8, QTableWidgetItem(
                        str(report.get("logic_errors", ""))))
                    self.table.setItem(row, 9, QTableWidgetItem(
                        ", ".join(report.get("errors", []))))
                    self.table.setItem(row, 10, QTableWidgetItem(
                        ", ".join(report.get("warnings", []))))

        except Exception as e:
            logger.error(f"填充表格失败: {e}")

    def group_data(self, group_by: str) -> Dict[str, List[Dict]]:
        """根据分组方式组织数据"""
        group_map = {}

        if group_by == "无分组":
            group_map["全部"] = self.filtered_reports
        elif group_by == "市场":
            for report in self.filtered_reports:
                key = report.get("market", "未知")
                group_map.setdefault(key, []).append(report)
        elif group_by == "行业":
            for report in self.filtered_reports:
                key = report.get("industry", "未知")
                group_map.setdefault(key, []).append(report)
        elif group_by == "评分区间":
            for report in self.filtered_reports:
                score = report.get("quality_score", 100)
                if score >= 90:
                    key = "90-100"
                elif score >= 80:
                    key = "80-89"
                elif score >= 70:
                    key = "70-79"
                elif score >= 60:
                    key = "60-69"
                else:
                    key = "<60"
                group_map.setdefault(key, []).append(report)

        return group_map

    def fill_charts(self):
        """填充图表数据"""
        if not self.filtered_reports:
            self.clear_charts()
            return

        try:
            df = pd.DataFrame(self.filtered_reports)

            # 字段分布直方图
            self.create_histogram(df)

            # 字段箱线图
            self.create_boxplot(df)

            # 异常点可视化
            self.create_outlier_plot(df)

            # 评分趋势
            self.create_score_trend(df)

            # 分布热力图
            self.create_heatmap(df)

            # 地图
            self.create_map(df)

        except Exception as e:
            logger.error(f"创建图表失败: {e}")
            self.clear_charts()

    def create_histogram(self, df: pd.DataFrame):
        """创建字段分布直方图"""
        try:
            if "quality_score" in df.columns:
                fig = px.histogram(df, x="quality_score",
                                   nbins=20, title="质量评分分布直方图")
                self.hist_view.setHtml(fig.to_html(include_plotlyjs='cdn'))
            else:
                self.hist_view.setHtml("<b>无评分数据</b>")
        except Exception as e:
            self.hist_view.setHtml(f"<b>创建直方图失败: {e}</b>")

    def create_boxplot(self, df: pd.DataFrame):
        """创建箱线图"""
        try:
            if "quality_score" in df.columns:
                fig = px.box(df, y="quality_score", title="质量评分箱线图")
                self.box_view.setHtml(fig.to_html(include_plotlyjs='cdn'))
            else:
                self.box_view.setHtml("<b>无评分数据</b>")
        except Exception as e:
            self.box_view.setHtml(f"<b>创建箱线图失败: {e}</b>")

    def create_outlier_plot(self, df: pd.DataFrame):
        """创建异常点可视化"""
        try:
            if "anomaly_stats" in df.columns:
                # 计算异常点数量
                anomaly_counts = []
                for stats in df["anomaly_stats"]:
                    try:
                        if isinstance(stats, str):
                            stats = ast.literal_eval(stats)
                        count = len(stats) if isinstance(stats, dict) else 0
                        anomaly_counts.append(count)
                    except (ValueError, SyntaxError):
                        anomaly_counts.append(0)
                    except Exception:
                        anomaly_counts.append(0)

                fig = go.Figure(go.Scatter(
                    y=anomaly_counts,
                    mode='markers',
                    marker=dict(color='red', size=8)
                ))
                fig.update_layout(
                    title="异常点分布", xaxis_title="样本", yaxis_title="异常点数")
                self.outlier_view.setHtml(fig.to_html(include_plotlyjs='cdn'))
            else:
                self.outlier_view.setHtml("<b>无异常点数据</b>")
        except Exception as e:
            self.outlier_view.setHtml(f"<b>创建异常点图失败: {e}</b>")

    def create_score_trend(self, df: pd.DataFrame):
        """创建评分趋势图"""
        try:
            if "quality_score" in df.columns:
                fig = go.Figure(go.Scatter(
                    y=df["quality_score"],
                    mode='lines+markers',
                    line=dict(color='blue')
                ))
                fig.update_layout(
                    title="评分趋势", xaxis_title="样本", yaxis_title="评分")
                self.score_trend_view.setHtml(
                    fig.to_html(include_plotlyjs='cdn'))
            else:
                self.score_trend_view.setHtml("<b>无评分数据</b>")
        except Exception as e:
            self.score_trend_view.setHtml(f"<b>创建趋势图失败: {e}</b>")

    def create_heatmap(self, df: pd.DataFrame):
        """创建分布热力图"""
        try:
            if "market" in df.columns and "quality_score" in df.columns:
                industry_col = "industry" if "industry" in df.columns else "market"
                pivot = pd.pivot_table(
                    df,
                    index="market",
                    columns=industry_col,
                    values="quality_score",
                    aggfunc='mean',
                    fill_value=0
                )
                fig = px.imshow(pivot, title="市场-行业评分热力图", aspect="auto")
                self.heatmap_view.setHtml(fig.to_html(include_plotlyjs='cdn'))
            else:
                self.heatmap_view.setHtml("<b>无市场或行业数据</b>")
        except Exception as e:
            self.heatmap_view.setHtml(f"<b>创建热力图失败: {e}</b>")

    def create_map(self, df: pd.DataFrame):
        """创建地图"""
        try:
            if "region" in df.columns and "lat" in df.columns and "lon" in df.columns:
                fig = px.density_mapbox(
                    df,
                    lat="lat",
                    lon="lon",
                    z="quality_score",
                    radius=10,
                    center=dict(lat=35, lon=105),
                    zoom=3,
                    mapbox_style="carto-positron",
                    title="异常分布地图"
                )
                self.map_view.setHtml(fig.to_html(include_plotlyjs='cdn'))
            else:
                self.map_view.setHtml("<b>无地理信息</b>")
        except Exception as e:
            self.map_view.setHtml(f"<b>创建地图失败: {e}</b>")

    def clear_charts(self):
        """清空图表"""
        if hasattr(self, 'hist_view'):
            self.hist_view.setHtml("<b>无数据</b>")
        if hasattr(self, 'box_view'):
            self.box_view.setHtml("<b>无数据</b>")
        if hasattr(self, 'outlier_view'):
            self.outlier_view.setHtml("<b>无数据</b>")
        if hasattr(self, 'score_trend_view'):
            self.score_trend_view.setHtml("<b>无数据</b>")
        if hasattr(self, 'heatmap_view'):
            self.heatmap_view.setHtml("<b>无数据</b>")
        if hasattr(self, 'map_view'):
            self.map_view.setHtml("<b>无数据</b>")

    def export_data(self):
        """导出数据到Excel"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出数据质量报告",
                f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel Files (*.xlsx)"
            )

            if file_path:
                df = pd.DataFrame(self.filtered_reports)
                df.to_excel(file_path, index=False)
                QMessageBox.information(self, "导出成功", f"报告已导出到: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")

def show_quality_report_dialog(reports: List[Dict[str, Any]], parent=None):
    """显示数据质量报告对话框"""
    dialog = QualityReportDialog(reports, parent)
    dialog.exec_()

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    # 测试数据
    test_reports = [
        {
            "code": "000001",
            "quality_score": 85.5,
            "market": "深圳",
            "industry": "银行",
            "missing_fields": 2,
            "anomaly_stats": {"high": 3, "low": 1},
            "empty_ratio": 0.05,
            "price_relation_errors": 0,
            "logic_errors": 1,
            "errors": ["价格异常"],
            "warnings": ["成交量偏低"]
        },
        {
            "code": "000002",
            "quality_score": 92.3,
            "market": "深圳",
            "industry": "地产",
            "missing_fields": 0,
            "anomaly_stats": {"high": 1},
            "empty_ratio": 0.02,
            "price_relation_errors": 0,
            "logic_errors": 0,
            "errors": [],
            "warnings": []
        }
    ]

    app = QApplication(sys.argv)
    show_quality_report_dialog(test_reports)
    sys.exit(app.exec_())
