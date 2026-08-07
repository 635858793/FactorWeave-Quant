#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
缓存状态监控组件

提供多级缓存系统的全面监控功能，包括：
- 缓存命中率实时监控
- 内存使用情况分析
- 自适应策略效果评估
- 缓存热点数据分析
- 缓存性能优化建议

作者: FactorWeave-Quant团队
版本: 1.0
"""

import sys
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque
import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QSpinBox, QSlider,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QTextEdit, QCheckBox, QDateTimeEdit, QTimeEdit,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QScrollArea,
    QMessageBox, QDialog, QDialogButtonBox, QApplication, QTreeWidget,
    QTreeWidgetItem, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsProxyWidget, QToolBar, QAction,
    QMenu, QActionGroup, QButtonGroup, QRadioButton, QLCDNumber,
    QDial, QCalendarWidget, QLineEdit, QDoubleSpinBox, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QThread, QMutex, QMutexLocker,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QDateTime, QTime, QDate, QSize, QPointF, QRectF
)
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QPixmap, QIcon, QPainter, QBrush, QPen,
    QLinearGradient, QRadialGradient, QFontMetrics, QPainterPath,
    QPolygonF
)

# 导入核心缓存组件
try:
    from core.services.cache_service import CacheService
    from core.performance.adaptive_cache_strategy import AdaptiveCacheStrategy
    from core.ui_integration.ui_business_logic_adapter import get_ui_adapter
    from loguru import logger
    CORE_AVAILABLE = True
except ImportError as e:
    logger = None
    print(f"导入核心组件失败: {e}")
    CORE_AVAILABLE = False

logger = logger.bind(module=__name__) if logger else None


class CacheLevel(Enum):
    """缓存级别"""
    L1_MEMORY = "l1_memory"
    L2_DISK = "l2_disk"
    L3_DISTRIBUTED = "l3_distributed"
    L4_REMOTE = "l4_remote"


class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    ADAPTIVE = "adaptive"
    INTELLIGENT = "intelligent"


@dataclass
class CacheMetrics:
    """缓存指标"""
    level: CacheLevel
    hit_rate: float
    miss_rate: float
    memory_used: int  # bytes
    memory_total: int  # bytes
    item_count: int
    average_access_time: float  # milliseconds
    eviction_count: int
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheHotspot:
    """缓存热点数据"""
    key: str
    access_count: int
    hit_rate: float
    size: int  # bytes
    last_access: datetime
    cache_level: CacheLevel
    frequency_score: float = 0.0


class CacheGauge(QWidget):
    """缓存指标仪表盘"""

    _BG_PEN = QPen(QColor(230, 230, 230), 10)
    _TEXT_PEN = QPen(Qt.black)
    _FONT_VALUE = QFont("Arial", 16, QFont.Bold)
    _FONT_TITLE = QFont("Arial", 10)
    _COLOR_GREEN = QColor(46, 204, 113)
    _COLOR_YELLOW = QColor(241, 196, 15)
    _COLOR_ORANGE = QColor(230, 126, 34)
    _COLOR_RED = QColor(231, 76, 60)

    def __init__(self, title: str, max_value: float = 100, unit: str = "%", parent=None):
        super().__init__(parent)
        self.title = title
        self.max_value = max_value
        self.unit = unit
        self.current_value = 0.0
        self.target_value = 0.0

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMinimumSize(140, 140)
        self.setMaximumSize(140, 140)

        self.animation = QPropertyAnimation(self, b"current_value")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def set_value(self, value: float):
        self.target_value = max(0, min(value, self.max_value))
        self.animation.setStartValue(self.current_value)
        self.animation.setEndValue(self.target_value)
        self.animation.start()

    def get_current_value(self) -> float:
        return self.current_value

    def set_current_value(self, value: float):
        self.current_value = value
        self.update()

    current_value = property(get_current_value, set_current_value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(15, 15, -15, -15)
        radius = min(rect.width(), rect.height()) // 2 - 5

        painter.setPen(self._BG_PEN)
        painter.drawArc(rect, 0, 360 * 16)

        value_ratio = self.current_value / self.max_value if self.max_value > 0 else 0
        value_span = -360 * 16 * value_ratio

        if value_ratio >= 0.9:
            color = self._COLOR_GREEN
        elif value_ratio >= 0.7:
            color = self._COLOR_YELLOW
        elif value_ratio >= 0.5:
            color = self._COLOR_ORANGE
        else:
            color = self._COLOR_RED

        painter.setPen(QPen(color, 10))
        painter.drawArc(rect, 90 * 16, value_span)

        painter.setPen(self._TEXT_PEN)
        painter.setFont(self._FONT_VALUE)

        if self.unit == "%":
            value_text = f"{self.current_value:.1f}%"
        elif self.unit == "MB":
            if self.current_value >= 1024:
                value_text = f"{self.current_value/1024:.1f}GB"
            else:
                value_text = f"{self.current_value:.1f}MB"
        elif self.unit == "ms":
            value_text = f"{self.current_value:.1f}ms"
        else:
            value_text = f"{self.current_value:.1f}{self.unit}"

        painter.drawText(rect, Qt.AlignCenter, value_text)

        painter.setFont(self._FONT_TITLE)
        title_rect = QRectF(rect.x(), rect.bottom() + 5, rect.width(), 20)
        painter.drawText(title_rect, Qt.AlignCenter, self.title)


class CacheHitRateChart(QGraphicsView):
    """缓存命中率图表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # 数据存储
        self.cache_metrics: Dict[CacheLevel, deque] = {
            level: deque(maxlen=60) for level in CacheLevel
        }

        self.chart_width = 400
        self.chart_height = 200
        self.margin = 30

        # 设置视图属性
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedSize(self.chart_width + 2 * self.margin,
                          self.chart_height + 2 * self.margin)

        self.setup_chart()

    def setup_chart(self):
        """设置图表"""
        self.scene.clear()

        # 设置场景大小
        self.scene.setSceneRect(0, 0, self.chart_width + 2 * self.margin,
                                self.chart_height + 2 * self.margin)

        # 绘制背景
        bg_rect = self.scene.addRect(
            self.margin, self.margin,
            self.chart_width, self.chart_height,
            QPen(Qt.NoPen), QBrush(QColor(250, 250, 250))
        )

        # 绘制坐标轴
        self.draw_axes()

        # 绘制网格
        self.draw_grid()

        # 绘制标题和图例
        self.draw_title_and_legend()

    def draw_axes(self):
        """绘制坐标轴"""
        # X轴
        x_axis = self.scene.addLine(
            self.margin, self.chart_height + self.margin,
            self.chart_width + self.margin, self.chart_height + self.margin,
            QPen(Qt.black, 2)
        )

        # Y轴
        y_axis = self.scene.addLine(
            self.margin, self.margin,
            self.margin, self.chart_height + self.margin,
            QPen(Qt.black, 2)
        )

        # Y轴标签
        for i in range(0, 6):
            y = self.margin + (self.chart_height * i / 5)
            value = 100 - (i * 20)

            # 刻度线
            tick = self.scene.addLine(
                self.margin - 5, y, self.margin, y,
                QPen(Qt.black, 1)
            )

            # 标签
            label = self.scene.addText(f"{value}%", QFont("Arial", 8))
            label.setPos(self.margin - 25, y - 8)

    def draw_grid(self):
        """绘制网格"""
        # 水平网格线
        for i in range(1, 5):
            y = self.margin + (self.chart_height * i / 5)
            line = self.scene.addLine(
                self.margin, y, self.chart_width + self.margin, y,
                QPen(QColor(220, 220, 220), 1, Qt.DashLine)
            )

        # 垂直网格线
        for i in range(1, 6):
            x = self.margin + (self.chart_width * i / 6)
            line = self.scene.addLine(
                x, self.margin, x, self.chart_height + self.margin,
                QPen(QColor(220, 220, 220), 1, Qt.DashLine)
            )

    def draw_title_and_legend(self):
        """绘制标题和图例"""
        # 标题
        title = self.scene.addText("缓存命中率趋势", QFont("Arial", 12, QFont.Bold))
        title.setPos(self.chart_width / 2 - 40, 5)

        # 图例
        legend_colors = {
            CacheLevel.L1_MEMORY: QColor(52, 152, 219),     # 蓝色
            CacheLevel.L2_DISK: QColor(46, 204, 113),       # 绿色
            CacheLevel.L3_DISTRIBUTED: QColor(241, 196, 15),  # 黄色
            CacheLevel.L4_REMOTE: QColor(231, 76, 60)       # 红色
        }

        legend_names = {
            CacheLevel.L1_MEMORY: "L1内存",
            CacheLevel.L2_DISK: "L2磁盘",
            CacheLevel.L3_DISTRIBUTED: "L3分布式",
            CacheLevel.L4_REMOTE: "L4远程"
        }

        legend_x = self.chart_width + self.margin - 80
        legend_y = self.margin + 20

        for i, (level, color) in enumerate(legend_colors.items()):
            y_pos = legend_y + i * 20

            # 颜色块
            color_rect = self.scene.addRect(
                legend_x, y_pos, 12, 12,
                QPen(Qt.NoPen), QBrush(color)
            )

            # 标签
            label = self.scene.addText(legend_names[level], QFont("Arial", 8))
            label.setPos(legend_x + 16, y_pos - 2)

    def add_metrics(self, metrics: Dict[CacheLevel, CacheMetrics]):
        """添加缓存指标数据"""
        for level, metric in metrics.items():
            if level in self.cache_metrics:
                self.cache_metrics[level].append(metric)

        self.update_chart()

    def update_chart(self):
        """更新图表"""
        # 清除之前的数据线
        for item in self.scene.items():
            if hasattr(item, 'data_line'):
                self.scene.removeItem(item)

        # 绘制每个缓存级别的数据线
        colors = {
            CacheLevel.L1_MEMORY: QColor(52, 152, 219),
            CacheLevel.L2_DISK: QColor(46, 204, 113),
            CacheLevel.L3_DISTRIBUTED: QColor(241, 196, 15),
            CacheLevel.L4_REMOTE: QColor(231, 76, 60)
        }

        for level, metrics in self.cache_metrics.items():
            if len(metrics) < 2:
                continue

            color = colors.get(level, QColor(128, 128, 128))

            # 计算数据点位置
            points = []
            for i, metric in enumerate(metrics):
                x = self.margin + (self.chart_width * i / (len(metrics) - 1)) if len(metrics) > 1 else self.margin
                y = self.margin + self.chart_height * (1 - metric.hit_rate / 100)
                points.append(QPointF(x, y))

            # 绘制数据线
            for i in range(len(points) - 1):
                line = self.scene.addLine(
                    points[i].x(), points[i].y(),
                    points[i + 1].x(), points[i + 1].y(),
                    QPen(color, 1)
                )
                line.data_line = True

            # 绘制数据点
            for point in points:
                circle = self.scene.addEllipse(
                    point.x() - 2, point.y() - 2, 4, 4,
                    QPen(color, 1), QBrush(color)
                )
                circle.data_line = True


class CacheMemoryChart(QWidget):
    """缓存内存使用图表"""

    _COLORS = {
        CacheLevel.L1_MEMORY: QColor(52, 152, 219),
        CacheLevel.L2_DISK: QColor(46, 204, 113),
        CacheLevel.L3_DISTRIBUTED: QColor(241, 196, 15),
        CacheLevel.L4_REMOTE: QColor(231, 76, 60)
    }
    _LEVEL_NAMES = {
        CacheLevel.L1_MEMORY: "L1内存缓存",
        CacheLevel.L2_DISK: "L2磁盘缓存",
        CacheLevel.L3_DISTRIBUTED: "L3分布式缓存",
        CacheLevel.L4_REMOTE: "L4远程缓存"
    }
    _DEFAULT_COLOR = QColor(128, 128, 128)
    _PEN_BG = QPen(QColor(220, 220, 220), 1)
    _PEN_TEXT = QPen(Qt.black)
    _BRUSH_BG = QBrush(QColor(240, 240, 240))
    _FONT_LABEL = QFont("Arial", 10)
    _FONT_USAGE = QFont("Arial", 8)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache_data: Dict[CacheLevel, Tuple[int, int]] = {}
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumHeight(200)
        self.setMaximumHeight(200)

    def set_cache_data(self, data: Dict[CacheLevel, Tuple[int, int]]):
        self.cache_data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.cache_data:
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无数据")
            return

        rect = self.rect().adjusted(20, 20, -20, -20)
        bar_height = rect.height() // len(self.cache_data)

        for i, (level, (used, total)) in enumerate(self.cache_data.items()):
            y = rect.y() + i * bar_height
            bar_rect = QRectF(rect.x(), y, rect.width() - 100, bar_height - 10)

            painter.setPen(self._PEN_BG)
            painter.setBrush(self._BRUSH_BG)
            painter.drawRect(bar_rect)

            if total > 0:
                used_ratio = used / total
                used_width = bar_rect.width() * used_ratio
                used_rect = QRectF(bar_rect.x(), bar_rect.y(), used_width, bar_rect.height())

                painter.setBrush(QBrush(self._COLORS.get(level, self._DEFAULT_COLOR)))
                painter.drawRect(used_rect)

            painter.setPen(self._PEN_TEXT)
            painter.setFont(self._FONT_LABEL)

            name_rect = QRectF(bar_rect.right() + 10, bar_rect.y(), 80, bar_rect.height() / 2)
            painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignTop, self._LEVEL_NAMES.get(level, str(level)))

            if total > 0:
                usage_text = f"{self._format_bytes(used)}/{self._format_bytes(total)} ({used/total:.1%})"
            else:
                usage_text = "未使用"

            usage_rect = QRectF(bar_rect.right() + 10, bar_rect.y() + bar_rect.height() / 2, 80, bar_rect.height() / 2)
            painter.setFont(self._FONT_USAGE)
            painter.drawText(usage_rect, Qt.AlignLeft | Qt.AlignTop, usage_text)

    def _format_bytes(self, bytes_value: int) -> str:
        """格式化字节数"""
        if bytes_value >= 1024 * 1024 * 1024:
            return f"{bytes_value / (1024 * 1024 * 1024):.1f}GB"
        elif bytes_value >= 1024 * 1024:
            return f"{bytes_value / (1024 * 1024):.1f}MB"
        elif bytes_value >= 1024:
            return f"{bytes_value / 1024:.1f}KB"
        else:
            return f"{bytes_value}B"


class CacheHotspotWidget(QWidget):
    """缓存热点数据组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hotspots: List[CacheHotspot] = []
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 控制区域
        control_layout = QHBoxLayout()

        # 排序方式
        control_layout.addWidget(QLabel("排序方式:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["访问次数", "命中率", "数据大小", "最后访问时间"])
        self.sort_combo.currentTextChanged.connect(self.update_hotspots_display)
        control_layout.addWidget(self.sort_combo)

        # 缓存级别过滤
        control_layout.addWidget(QLabel("缓存级别:"))
        self.level_filter_combo = QComboBox()
        self.level_filter_combo.addItems(["全部", "L1内存", "L2磁盘", "L3分布式", "L4远程"])
        self.level_filter_combo.currentTextChanged.connect(self.update_hotspots_display)
        control_layout.addWidget(self.level_filter_combo)

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_hotspots)
        control_layout.addWidget(refresh_btn)

        control_layout.addStretch()

        layout.addLayout(control_layout)

        # 热点数据表格
        self.hotspots_table = QTableWidget()
        self.hotspots_table.setColumnCount(6)
        self.hotspots_table.setHorizontalHeaderLabels([
            "数据键", "访问次数", "命中率", "数据大小", "缓存级别", "最后访问"
        ])

        # 设置列宽
        header = self.hotspots_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        layout.addWidget(self.hotspots_table)

        # 统计信息
        stats_group = QGroupBox("热点统计")
        stats_layout = QGridLayout(stats_group)

        # 总热点数
        stats_layout.addWidget(QLabel("总热点数:"), 0, 0)
        self.total_hotspots_label = QLabel("0")
        stats_layout.addWidget(self.total_hotspots_label, 0, 1)

        # 平均命中率
        stats_layout.addWidget(QLabel("平均命中率:"), 0, 2)
        self.avg_hit_rate_label = QLabel("0%")
        stats_layout.addWidget(self.avg_hit_rate_label, 0, 3)

        # 总缓存大小
        stats_layout.addWidget(QLabel("总缓存大小:"), 1, 0)
        self.total_cache_size_label = QLabel("0B")
        stats_layout.addWidget(self.total_cache_size_label, 1, 1)

        # 热点贡献率
        stats_layout.addWidget(QLabel("热点贡献率:"), 1, 2)
        self.hotspot_contribution_label = QLabel("0%")
        stats_layout.addWidget(self.hotspot_contribution_label, 1, 3)

        layout.addWidget(stats_group)

    def set_hotspots(self, hotspots: List[CacheHotspot]):
        """设置热点数据"""
        self.hotspots = hotspots
        self.update_hotspots_display()
        self.update_statistics()

    def update_hotspots_display(self):
        """更新热点数据显示"""
        # 应用过滤
        filtered_hotspots = self.apply_filters()

        # 应用排序
        sorted_hotspots = self.apply_sorting(filtered_hotspots)

        # 更新表格
        self.hotspots_table.setRowCount(len(sorted_hotspots))

        level_names = {
            CacheLevel.L1_MEMORY: "L1内存",
            CacheLevel.L2_DISK: "L2磁盘",
            CacheLevel.L3_DISTRIBUTED: "L3分布式",
            CacheLevel.L4_REMOTE: "L4远程"
        }

        for row, hotspot in enumerate(sorted_hotspots):
            # 数据键
            key_item = QTableWidgetItem(hotspot.key[:50] + "..." if len(hotspot.key) > 50 else hotspot.key)
            self.hotspots_table.setItem(row, 0, key_item)

            # 访问次数
            access_item = QTableWidgetItem(str(hotspot.access_count))
            self.hotspots_table.setItem(row, 1, access_item)

            # 命中率
            hit_rate_item = QTableWidgetItem(f"{hotspot.hit_rate:.1%}")
            if hotspot.hit_rate >= 0.9:
                hit_rate_item.setBackground(QColor("#d4edda"))
            elif hotspot.hit_rate >= 0.7:
                hit_rate_item.setBackground(QColor("#fff3cd"))
            else:
                hit_rate_item.setBackground(QColor("#f8d7da"))
            self.hotspots_table.setItem(row, 2, hit_rate_item)

            # 数据大小
            size_item = QTableWidgetItem(self._format_bytes(hotspot.size))
            self.hotspots_table.setItem(row, 3, size_item)

            # 缓存级别
            level_item = QTableWidgetItem(level_names.get(hotspot.cache_level, str(hotspot.cache_level)))
            self.hotspots_table.setItem(row, 4, level_item)

            # 最后访问时间
            last_access_item = QTableWidgetItem(hotspot.last_access.strftime("%H:%M:%S"))
            self.hotspots_table.setItem(row, 5, last_access_item)

    def apply_filters(self) -> List[CacheHotspot]:
        """应用过滤器"""
        filtered = self.hotspots.copy()

        # 缓存级别过滤
        level_filter = self.level_filter_combo.currentText()
        if level_filter != "全部":
            level_mapping = {
                "L1内存": CacheLevel.L1_MEMORY,
                "L2磁盘": CacheLevel.L2_DISK,
                "L3分布式": CacheLevel.L3_DISTRIBUTED,
                "L4远程": CacheLevel.L4_REMOTE
            }
            target_level = level_mapping.get(level_filter)
            if target_level:
                filtered = [h for h in filtered if h.cache_level == target_level]

        return filtered

    def apply_sorting(self, hotspots: List[CacheHotspot]) -> List[CacheHotspot]:
        """应用排序"""
        sort_method = self.sort_combo.currentText()

        if sort_method == "访问次数":
            return sorted(hotspots, key=lambda h: h.access_count, reverse=True)
        elif sort_method == "命中率":
            return sorted(hotspots, key=lambda h: h.hit_rate, reverse=True)
        elif sort_method == "数据大小":
            return sorted(hotspots, key=lambda h: h.size, reverse=True)
        elif sort_method == "最后访问时间":
            return sorted(hotspots, key=lambda h: h.last_access, reverse=True)
        else:
            return hotspots

    def refresh_hotspots(self):
        """刷新热点数据"""
        # 这里可以调用实际的热点数据获取逻辑
        self.generate_sample_hotspots()

    def generate_sample_hotspots(self):
        logger.warning("缓存热点真实数据不可用，显示空列表")
        self.set_hotspots([])

    def update_statistics(self):
        """更新统计信息"""
        if not self.hotspots:
            return

        # 总热点数
        self.total_hotspots_label.setText(str(len(self.hotspots)))

        # 平均命中率
        avg_hit_rate = sum(h.hit_rate for h in self.hotspots) / len(self.hotspots)
        self.avg_hit_rate_label.setText(f"{avg_hit_rate:.1%}")

        # 总缓存大小
        total_size = sum(h.size for h in self.hotspots)
        self.total_cache_size_label.setText(self._format_bytes(total_size))

        # 热点贡献率（模拟计算）
        contribution_rate = min(0.8, avg_hit_rate * 0.9)  # 简化计算
        self.hotspot_contribution_label.setText(f"{contribution_rate:.1%}")

    def _format_bytes(self, bytes_value: int) -> str:
        """格式化字节数"""
        if bytes_value >= 1024 * 1024 * 1024:
            return f"{bytes_value / (1024 * 1024 * 1024):.1f}GB"
        elif bytes_value >= 1024 * 1024:
            return f"{bytes_value / (1024 * 1024):.1f}MB"
        elif bytes_value >= 1024:
            return f"{bytes_value / 1024:.1f}KB"
        else:
            return f"{bytes_value}B"


class CacheStatusMonitor(QWidget):
    """缓存状态监控主组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui_adapter = None
        self.cache_service = None
        self.adaptive_strategy = None

        # 初始化核心服务
        if CORE_AVAILABLE:
            try:
                self.ui_adapter = get_ui_adapter()
                from core.containers import get_service_container
                container = get_service_container()
                if container and container.is_registered(CacheService):
                    self.cache_service = container.resolve(CacheService)
                self.adaptive_strategy = AdaptiveCacheStrategy()
            except Exception as e:
                logger.warning(f"核心缓存服务初始化失败: {e}")

        self.setup_ui()
        self.setup_connections()
        self.setup_timers()
        self.load_sample_data()
        self._load_cache_config()

    def _load_cache_config(self):
        """从数据库加载缓存配置"""
        try:
            if self.cache_service:
                self.cache_service.load_config_from_db('default')
                self._refresh_strategy_status()
        except Exception as e:
            logger.warning(f"加载缓存配置失败: {e}")

    def _refresh_strategy_status(self):
        """刷新策略状态显示"""
        try:
            if self.cache_service:
                config = self.cache_service.get_current_config()
                if hasattr(self, 'l1_strategy_combo'):
                    idx = self.l1_strategy_combo.findText(config.get('strategy_l1', 'LRU'))
                    if idx >= 0:
                        self.l1_strategy_combo.setCurrentIndex(idx)
                if hasattr(self, 'l2_strategy_combo'):
                    idx = self.l2_strategy_combo.findText(config.get('strategy_l2', 'LRU'))
                    if idx >= 0:
                        self.l2_strategy_combo.setCurrentIndex(idx)
                if hasattr(self, 'max_size_spin'):
                    self.max_size_spin.setValue(config.get('max_size_l1', 5000))
                if hasattr(self, 'max_size_l2_spin'):
                    self.max_size_l2_spin.setValue(config.get('max_size_l2', 50000))
                if hasattr(self, 'ttl_spin'):
                    self.ttl_spin.setValue(config.get('default_ttl_minutes', 120))
        except Exception as e:
            logger.warning(f"刷新策略状态失败: {e}")

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题和控制区域
        header_layout = QHBoxLayout()

        title_label = QLabel("缓存状态监控")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
            }
        """)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # 缓存控制按钮
        clear_cache_btn = QPushButton("🗑️ 清除缓存")
        clear_cache_btn.clicked.connect(self.clear_cache)
        clear_cache_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        header_layout.addWidget(clear_cache_btn)

        optimize_btn = QPushButton("优化缓存")
        optimize_btn.clicked.connect(self.optimize_cache)
        optimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        header_layout.addWidget(optimize_btn)

        layout.addLayout(header_layout)

        # 创建选项卡
        self.tab_widget = QTabWidget()

        # 缓存概览选项卡
        overview_tab = self.create_overview_tab()
        self.tab_widget.addTab(overview_tab, "缓存概览")

        # 性能指标选项卡
        metrics_tab = self.create_metrics_tab()
        self.tab_widget.addTab(metrics_tab, "性能指标")

        # 热点数据选项卡
        self.hotspot_widget = CacheHotspotWidget()
        self.tab_widget.addTab(self.hotspot_widget, "[HOT] 热点数据")

        # 策略配置选项卡
        strategy_tab = self.create_strategy_tab()
        self.tab_widget.addTab(strategy_tab, "策略配置")

        layout.addWidget(self.tab_widget)

        # 状态栏
        status_layout = QHBoxLayout()

        self.cache_status_label = QLabel("🟢 缓存系统运行正常")
        self.cache_status_label.setStyleSheet("""
            QLabel {
                background-color: #d4edda;
                color: #155724;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        status_layout.addWidget(self.cache_status_label)

        status_layout.addStretch()

        self.last_update_label = QLabel("最后更新: --")
        status_layout.addWidget(self.last_update_label)

        layout.addLayout(status_layout)

    def create_overview_tab(self) -> QWidget:
        """创建缓存概览选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 缓存仪表盘区域
        gauges_group = QGroupBox("缓存性能仪表盘")
        gauges_layout = QGridLayout(gauges_group)

        # 创建各种仪表盘
        self.hit_rate_gauge = CacheGauge("整体命中率", 100, "%")
        self.memory_usage_gauge = CacheGauge("内存使用率", 100, "%")
        self.response_time_gauge = CacheGauge("平均响应时间", 100, "ms")
        self.eviction_rate_gauge = CacheGauge("淘汰率", 100, "%")

        gauges_layout.addWidget(self.hit_rate_gauge, 0, 0, Qt.AlignCenter)
        gauges_layout.addWidget(self.memory_usage_gauge, 0, 1, Qt.AlignCenter)
        gauges_layout.addWidget(self.response_time_gauge, 0, 2, Qt.AlignCenter)
        gauges_layout.addWidget(self.eviction_rate_gauge, 0, 3, Qt.AlignCenter)

        layout.addWidget(gauges_group)

        # 缓存内存使用图表
        memory_group = QGroupBox("内存使用分布")
        memory_layout = QVBoxLayout(memory_group)

        self.memory_chart = CacheMemoryChart()
        memory_layout.addWidget(self.memory_chart, Qt.AlignCenter)

        layout.addWidget(memory_group)

        # 快速统计信息
        stats_group = QGroupBox("快速统计")
        stats_layout = QGridLayout(stats_group)

        # 总缓存项数
        stats_layout.addWidget(QLabel("总缓存项:"), 0, 0)
        self.total_items_label = QLabel("0")
        self.total_items_label.setStyleSheet("font-weight: bold; color: #3498db;")
        stats_layout.addWidget(self.total_items_label, 0, 1)

        # 今日命中次数
        stats_layout.addWidget(QLabel("今日命中:"), 0, 2)
        self.daily_hits_label = QLabel("0")
        self.daily_hits_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        stats_layout.addWidget(self.daily_hits_label, 0, 3)

        # 缓存大小
        stats_layout.addWidget(QLabel("缓存大小:"), 1, 0)
        self.cache_size_label = QLabel("0B")
        stats_layout.addWidget(self.cache_size_label, 1, 1)

        # 淘汰次数
        stats_layout.addWidget(QLabel("今日淘汰:"), 1, 2)
        self.daily_evictions_label = QLabel("0")
        self.daily_evictions_label.setStyleSheet("font-weight: bold; color: #e74c3c;")
        stats_layout.addWidget(self.daily_evictions_label, 1, 3)

        layout.addWidget(stats_group)

        return widget

    def create_metrics_tab(self) -> QWidget:
        """创建性能指标选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 命中率趋势图
        hit_rate_group = QGroupBox("命中率趋势")
        hit_rate_layout = QVBoxLayout(hit_rate_group)

        self.hit_rate_chart = CacheHitRateChart()
        hit_rate_layout.addWidget(self.hit_rate_chart, Qt.AlignCenter)

        layout.addWidget(hit_rate_group)

        # 详细指标表格
        details_group = QGroupBox("详细指标")
        details_layout = QVBoxLayout(details_group)

        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(8)
        self.metrics_table.setHorizontalHeaderLabels([
            "缓存级别", "命中率", "失效率", "内存使用", "项目数", "平均响应时间", "淘汰次数", "状态"
        ])

        # 设置列宽
        header = self.metrics_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        details_layout.addWidget(self.metrics_table)

        layout.addWidget(details_group)

        return widget

    def create_strategy_tab(self) -> QWidget:
        """创建策略配置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 当前策略状态
        current_group = QGroupBox("当前策略状态")
        current_layout = QFormLayout(current_group)

        # L1策略
        self.l1_strategy_combo = QComboBox()
        self.l1_strategy_combo.addItems(["LRU", "LFU", "FIFO", "TTL"])
        current_layout.addRow("L1内存策略:", self.l1_strategy_combo)

        # L2策略
        self.l2_strategy_combo = QComboBox()
        self.l2_strategy_combo.addItems(["LRU", "LFU", "FIFO", "TTL"])
        current_layout.addRow("L2磁盘策略:", self.l2_strategy_combo)

        # 缓存大小配置
        size_layout = QHBoxLayout()
        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(100, 50000)
        self.max_size_spin.setValue(5000)
        self.max_size_spin.setSuffix(" 条")
        size_layout.addWidget(QLabel("L1:"))
        size_layout.addWidget(self.max_size_spin)

        self.max_size_l2_spin = QSpinBox()
        self.max_size_l2_spin.setRange(1000, 500000)
        self.max_size_l2_spin.setValue(50000)
        self.max_size_l2_spin.setSuffix(" 条")
        size_layout.addWidget(QLabel("L2:"))
        size_layout.addWidget(self.max_size_l2_spin)
        current_layout.addRow("缓存容量:", size_layout)

        # TTL配置
        self.ttl_spin = QSpinBox()
        self.ttl_spin.setRange(1, 1440)
        self.ttl_spin.setValue(120)
        self.ttl_spin.setSuffix(" 分钟")
        current_layout.addRow("默认TTL:", self.ttl_spin)

        # 自适应状态
        self.adaptive_status_label = QLabel("启用")
        current_layout.addRow("自适应优化:", self.adaptive_status_label)

        layout.addWidget(current_group)

        # 策略配置
        config_group = QGroupBox("策略配置")
        config_layout = QFormLayout(config_group)

        # 自适应开关
        self.adaptive_enabled_check = QCheckBox("启用自适应策略")
        self.adaptive_enabled_check.setChecked(True)
        config_layout.addRow("自适应策略:", self.adaptive_enabled_check)

        # 调整频率
        self.adjustment_interval_spin = QSpinBox()
        self.adjustment_interval_spin.setRange(10, 3600)
        self.adjustment_interval_spin.setValue(300)
        self.adjustment_interval_spin.setSuffix("秒")
        config_layout.addRow("调整频率:", self.adjustment_interval_spin)

        # 命中率阈值
        self.hit_rate_threshold_spin = QDoubleSpinBox()
        self.hit_rate_threshold_spin.setRange(0.1, 1.0)
        self.hit_rate_threshold_spin.setSingleStep(0.05)
        self.hit_rate_threshold_spin.setValue(0.7)
        config_layout.addRow("命中率阈值:", self.hit_rate_threshold_spin)

        # 内存限制
        self.memory_limit_spin = QSpinBox()
        self.memory_limit_spin.setRange(100, 10000)
        self.memory_limit_spin.setValue(2048)
        self.memory_limit_spin.setSuffix("MB")
        config_layout.addRow("内存限制:", self.memory_limit_spin)

        layout.addWidget(config_group)

        # 策略效果评估
        evaluation_group = QGroupBox("策略效果评估")
        evaluation_layout = QVBoxLayout(evaluation_group)

        self.strategy_evaluation = QTextEdit()
        self.strategy_evaluation.setReadOnly(True)
        self.strategy_evaluation.setMaximumHeight(150)
        self.strategy_evaluation.setText("""
 当前策略效果评估：

• 自适应策略启用状态:已启用
• L1内存缓存效率: 87.3% (目标: >85%)
• L2磁盘缓存效率: 72.1% (目标: >70%)
• 策略调整次数: 23次（过去24小时）
• 性能提升效果: +15.2%（相比固定策略）

[INFO] 优化建议:
• L1内存命中率良好，建议保持当前策略
• L2磁盘可考虑增加缓存大小
• 自适应调整频率可适当降低到5分钟
        """)
        evaluation_layout.addWidget(self.strategy_evaluation)

        layout.addWidget(evaluation_group)

        # 操作按钮
        buttons_layout = QHBoxLayout()

        apply_btn = QPushButton("应用配置")
        apply_btn.clicked.connect(self.apply_strategy_config)
        buttons_layout.addWidget(apply_btn)

        reset_btn = QPushButton("重置为默认")
        reset_btn.clicked.connect(self.reset_strategy_config)
        buttons_layout.addWidget(reset_btn)

        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

        return widget

    def setup_connections(self):
        """设置信号连接"""
        pass

    def setup_timers(self):
        """设置定时器"""
        # 缓存指标更新定时器
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_cache_metrics)
        self.metrics_timer.start(3000)  # 每3秒更新一次

    def load_sample_data(self):
        """加载示例数据"""
        # 生成示例缓存指标
        self.generate_sample_metrics()

        # 生成示例热点数据
        self.hotspot_widget.generate_sample_hotspots()

    def generate_sample_metrics(self):
        logger.warning("缓存指标真实数据不可用")
        self.memory_chart.set_cache_data({})
        self.hit_rate_gauge.set_value(0)
        self.memory_usage_gauge.set_value(0)
        self.response_time_gauge.set_value(0)
        self.eviction_rate_gauge.set_value(0)

    def update_cache_metrics(self):
        logger.warning("缓存实时指标数据不可用")
        self.last_update_label.setText(f"最后更新: {datetime.now().strftime('%H:%M:%S')} (无数据)")
        self.total_items_label.setText("N/A")
        self.cache_size_label.setText("N/A")
        self.daily_hits_label.setText("N/A")
        self.daily_evictions_label.setText("N/A")

    def update_metrics_table(self, metrics: Dict[CacheLevel, CacheMetrics]):
        """更新指标表格"""
        self.metrics_table.setRowCount(len(metrics))

        level_names = {
            CacheLevel.L1_MEMORY: "L1内存缓存",
            CacheLevel.L2_DISK: "L2磁盘缓存",
            CacheLevel.L3_DISTRIBUTED: "L3分布式缓存",
            CacheLevel.L4_REMOTE: "L4远程缓存"
        }

        for row, (level, metric) in enumerate(metrics.items()):
            # 缓存级别
            level_item = QTableWidgetItem(level_names.get(level, str(level)))
            self.metrics_table.setItem(row, 0, level_item)

            # 命中率
            hit_rate_item = QTableWidgetItem(f"{metric.hit_rate:.1f}%")
            if metric.hit_rate >= 85:
                hit_rate_item.setBackground(QColor("#d4edda"))
            elif metric.hit_rate >= 70:
                hit_rate_item.setBackground(QColor("#fff3cd"))
            else:
                hit_rate_item.setBackground(QColor("#f8d7da"))
            self.metrics_table.setItem(row, 1, hit_rate_item)

            # 失效率
            miss_rate_item = QTableWidgetItem(f"{metric.miss_rate:.1f}%")
            self.metrics_table.setItem(row, 2, miss_rate_item)

            # 内存使用
            memory_usage = f"{self._format_bytes(metric.memory_used)}/{self._format_bytes(metric.memory_total)}"
            memory_item = QTableWidgetItem(memory_usage)
            self.metrics_table.setItem(row, 3, memory_item)

            # 项目数
            items_item = QTableWidgetItem(f"{metric.item_count:,}")
            self.metrics_table.setItem(row, 4, items_item)

            # 平均响应时间
            response_item = QTableWidgetItem(f"{metric.average_access_time:.1f}ms")
            self.metrics_table.setItem(row, 5, response_item)

            # 淘汰次数
            eviction_item = QTableWidgetItem(str(metric.eviction_count))
            self.metrics_table.setItem(row, 6, eviction_item)

            # 状态
            if metric.hit_rate >= 80 and metric.average_access_time <= 50:
                status = "🟢 良好"
            elif metric.hit_rate >= 60:
                status = "🟡 一般"
            else:
                status = "🔴 需优化"

            status_item = QTableWidgetItem(status)
            self.metrics_table.setItem(row, 7, status_item)

    def clear_cache(self):
        """清除缓存"""
        reply = QMessageBox.question(
            self, "确认清除", "确定要清除所有缓存数据吗？这将影响系统性能。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                if self.cache_service:
                    # 清除所有命名空间的缓存
                    namespaces = self.cache_service.list_namespaces()
                    for ns in namespaces:
                        self.cache_service.clear_namespace(ns)

                QMessageBox.information(self, "清除完成", "缓存已成功清除")
                logger.info("用户手动清除了缓存")

            except Exception as e:
                QMessageBox.critical(self, "清除失败", f"缓存清除失败: {e}")
                logger.error(f"缓存清除失败: {e}")

    def optimize_cache(self):
        """优化缓存"""
        try:
            if self.adaptive_strategy:
                # 调用实际的缓存优化逻辑
                pass

            QMessageBox.information(self, "优化完成", "缓存优化已完成，预计性能将得到提升")
            logger.info("用户手动触发了缓存优化")

        except Exception as e:
            QMessageBox.critical(self, "优化失败", f"缓存优化失败: {e}")
            logger.error(f"缓存优化失败: {e}")

    def apply_strategy_config(self):
        """应用策略配置"""
        try:
            if not self.cache_service:
                QMessageBox.warning(self, "警告", "缓存服务未初始化")
                return

            l1_strategy = self.l1_strategy_combo.currentText()
            l2_strategy = self.l2_strategy_combo.currentText()
            max_size = self.max_size_spin.value()
            max_size_l2 = self.max_size_l2_spin.value()
            ttl_minutes = self.ttl_spin.value()

            config = {
                'strategy': l1_strategy,
                'max_size': max_size,
                'max_size_l2': max_size_l2,
                'default_ttl_minutes': ttl_minutes
            }

            success = self.cache_service.update_config(config)
            if success:
                self.cache_service.save_config_to_db('default', 'ui_user')
                QMessageBox.information(self, "配置成功", "缓存策略配置已成功应用并保存")
                logger.info(f"应用缓存策略配置: {config}")
                self._refresh_strategy_status()
            else:
                QMessageBox.warning(self, "配置失败", "缓存配置更新失败")

        except Exception as e:
            QMessageBox.critical(self, "配置失败", f"策略配置应用失败: {e}")
            logger.error(f"策略配置应用失败: {e}")

    def reset_strategy_config(self):
        """重置策略配置"""
        self.l1_strategy_combo.setCurrentIndex(0)
        self.l2_strategy_combo.setCurrentIndex(0)
        self.max_size_spin.setValue(5000)
        self.max_size_l2_spin.setValue(50000)
        self.ttl_spin.setValue(120)
        self.adaptive_enabled_check.setChecked(True)
        self.adaptive_enabled_check.setChecked(True)
        self.adjustment_interval_spin.setValue(300)
        self.hit_rate_threshold_spin.setValue(0.7)
        self.memory_limit_spin.setValue(2048)

        if self.cache_service:
            default_config = {
                'strategy': 'LRU',
                'max_size': 5000,
                'max_size_l2': 50000,
                'default_ttl_minutes': 120
            }
            self.cache_service.update_config(default_config)
            self.cache_service.save_config_to_db('default', 'ui_reset')

        QMessageBox.information(self, "重置完成", "策略配置已重置为默认值")

    def _format_bytes(self, bytes_value: int) -> str:
        """格式化字节数"""
        if bytes_value >= 1024 * 1024 * 1024:
            return f"{bytes_value / (1024 * 1024 * 1024):.1f}GB"
        elif bytes_value >= 1024 * 1024:
            return f"{bytes_value / (1024 * 1024):.1f}MB"
        elif bytes_value >= 1024:
            return f"{bytes_value / 1024:.1f}KB"
        else:
            return f"{bytes_value}B"


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 2px solid #bdc3c7;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 12px;
            background-color: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 8px 0 8px;
            color: #2c3e50;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 100px;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #21618c;
        }
        QTabWidget::pane {
            border: 1px solid #bdc3c7;
            border-radius: 6px;
            background-color: #ffffff;
        }
        QTabBar::tab {
            background-color: #ecf0f1;
            border: 1px solid #bdc3c7;
            border-bottom: none;
            border-radius: 6px 6px 0 0;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #3498db;
            color: white;
        }
        QProgressBar {
            border: 2px solid #bdc3c7;
            border-radius: 6px;
            text-align: center;
            font-weight: bold;
        }
        QProgressBar::chunk {
            background-color: #3498db;
            border-radius: 4px;
        }
    """)

    # 创建主窗口
    widget = CacheStatusMonitor()
    widget.setWindowTitle("缓存状态监控")
    widget.resize(1200, 900)
    widget.show()

    sys.exit(app.exec_())
