#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
响应式图表界面适配

多屏幕尺寸适配、触控优化、响应式布局管理

作者: FactorWeave-Quant团队
版本: 1.0
"""

import math
import time
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from PyQt5.QtWidgets import QApplication, QWidget, QGraphicsView, QGraphicsScene
from PyQt5.QtCore import Qt, QRectF, QSize, QPointF, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap
from collections import defaultdict, deque

class ScreenType(Enum):
    """屏幕类型"""
    MOBILE_SMALL = "mobile_small"      # 手机小屏 (< 600px)
    MOBILE_LARGE = "mobile_large"      # 手机大屏 (600px - 768px)
    TABLET = "tablet"                 # 平板 (768px - 1024px)
    DESKTOP = "desktop"               # 桌面 (1024px - 1440px)
    DESKTOP_LARGE = "desktop_large"   # 大屏 (1440px+)

class LayoutMode(Enum):
    """布局模式"""
    COMPACT = "compact"               # 紧凑模式
    STANDARD = "standard"             # 标准模式
    EXTENDED = "extended"             # 扩展模式

class InteractionMode(Enum):
    """交互模式"""
    MOUSE = "mouse"                   # 鼠标模式
    TOUCH = "touch"                   # 触摸模式
    PEN = "pen"                       # 笔模式

@dataclass
class ScreenInfo:
    """屏幕信息"""
    screen_type: ScreenType
    width: int
    height: int
    dpi: float
    is_touch_device: bool = False
    available_geometry: QRectF = field(default_factory=QRectF)
    safe_area: QRectF = field(default_factory=QRectF)

@dataclass
class LayoutConstraints:
    """布局约束"""
    min_width: int = 300
    max_width: int = 1920
    min_height: int = 200
    max_height: int = 1200
    padding: int = 16
    margin: int = 8
    gap: int = 12

@dataclass
class ResponsiveConfig:
    """响应式配置"""
    # 屏幕断点
    breakpoints: Dict[ScreenType, int] = field(default_factory=lambda: {
        ScreenType.MOBILE_SMALL: 400,
        ScreenType.MOBILE_LARGE: 600,
        ScreenType.TABLET: 768,
        ScreenType.DESKTOP: 1024,
        ScreenType.DESKTOP_LARGE: 1440
    })
    
    # 布局配置
    layout_modes: Dict[ScreenType, LayoutMode] = field(default_factory=lambda: {
        ScreenType.MOBILE_SMALL: LayoutMode.COMPACT,
        ScreenType.MOBILE_LARGE: LayoutMode.COMPACT,
        ScreenType.TABLET: LayoutMode.STANDARD,
        ScreenType.DESKTOP: LayoutMode.STANDARD,
        ScreenType.DESKTOP_LARGE: LayoutMode.EXTENDED
    })
    
    # 触控优化配置
    touch_config: Dict[str, Any] = field(default_factory=lambda: {
        'min_touch_target_size': 44,      # 最小触摸目标尺寸
        'touch_feedback_enabled': True,
        'pinch_zoom_enabled': True,
        'pan_gesture_enabled': True,
        'long_press_threshold': 500,      # 毫秒
        'double_tap_threshold': 300       # 毫秒
    })
    
    # 字体配置
    font_config: Dict[ScreenType, Dict[str, Any]] = field(default_factory=lambda: {
        ScreenType.MOBILE_SMALL: {
            'base_size': 12,
            'title_size': 16,
            'label_size': 11
        },
        ScreenType.MOBILE_LARGE: {
            'base_size': 13,
            'title_size': 17,
            'label_size': 12
        },
        ScreenType.TABLET: {
            'base_size': 14,
            'title_size': 18,
            'label_size': 13
        },
        ScreenType.DESKTOP: {
            'base_size': 14,
            'title_size': 20,
            'label_size': 13
        },
        ScreenType.DESKTOP_LARGE: {
            'base_size': 16,
            'title_size': 22,
            'label_size': 14
        }
    })

class TouchGesture:
    """触摸手势"""
    
    def __init__(self):
        self.start_points = []
        self.end_points = []
        self.start_time = 0
        self.velocity = QPointF(0, 0)
        self.scale = 1.0
        self.rotation = 0.0
        
    def add_point(self, point: QPointF):
        """添加触摸点"""
        self.end_points.append(point)
        if not self.start_points:
            self.start_points.append(point)
            self.start_time = time.time()
    
    def get_distance(self) -> float:
        """获取距离"""
        if len(self.end_points) < 2:
            return 0.0
        start = self.start_points[0] if self.start_points else QPointF(0, 0)
        end = self.end_points[-1]
        return math.sqrt((end.x() - start.x())**2 + (end.y() - start.y())**2)
    
    def get_velocity(self) -> QPointF:
        """获取速度"""
        if len(self.end_points) < 2:
            return QPointF(0, 0)
        
        dt = time.time() - self.start_time
        if dt <= 0:
            return QPointF(0, 0)
        
        start = self.start_points[0]
        end = self.end_points[-1]
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        
        return QPointF(dx / dt, dy / dt)

class ResponsiveChartWidget(QWidget):
    """响应式图表组件"""
    
    # 信号定义
    layout_changed = pyqtSignal(ScreenType, LayoutMode)
    interaction_mode_changed = pyqtSignal(InteractionMode)
    screen_resized = pyqtSignal(int, int)
    
    def __init__(self, config: Optional[ResponsiveConfig] = None, parent=None):
        super().__init__(parent)
        
        # 配置
        self.config = config or ResponsiveConfig()
        
        # 状态
        self.current_screen_type = ScreenType.DESKTOP
        self.current_layout_mode = LayoutMode.STANDARD
        self.current_interaction_mode = InteractionMode.MOUSE
        
        # 手势识别
        self.touch_gestures = {}
        self.active_touches = {}
        self.last_tap_time = {}
        self.gesture_recognition_threshold = 10
        
        # 尺寸管理
        self.constraints = LayoutConstraints()
        self.preferred_size = QSize(800, 600)
        self.minimum_size = QSize(300, 200)
        self.maximum_size = QSize(1920, 1200)
        
        # 响应式元素
        self.chart_elements = {}
        self.responsive_text = {}
        self.responsive_colors = {}
        
        # 定时器
        self.layout_update_timer = QTimer()
        self.layout_update_timer.setSingleShot(True)
        self.layout_update_timer.timeout.connect(self._update_layout)
        
        # 初始化
        self._detect_screen_type()
        self._setup_ui()
        self._setup_responsive_behavior()
    
    def _detect_screen_type(self):
        """检测屏幕类型"""
        screen = QApplication.desktop().screenGeometry()
        width = screen.width()
        height = screen.height()
        
        # 检测屏幕类型
        if width < self.config.breakpoints[ScreenType.MOBILE_LARGE]:
            self.current_screen_type = ScreenType.MOBILE_SMALL
        elif width < self.config.breakpoints[ScreenType.TABLET]:
            self.current_screen_type = ScreenType.MOBILE_LARGE
        elif width < self.config.breakpoints[ScreenType.DESKTOP]:
            self.current_screen_type = ScreenType.TABLET
        elif width < self.config.breakpoints[ScreenType.DESKTOP_LARGE]:
            self.current_screen_type = ScreenType.DESKTOP
        else:
            self.current_screen_type = ScreenType.DESKTOP_LARGE
        
        # 检测是否触摸设备
        is_touch = QApplication.desktop().isVirtualDesktop()
        if hasattr(self, 'event') and hasattr(self.event, 'source'):
            # 更精确的触摸检测
            pass
        
        # 更新布局模式
        self.current_layout_mode = self.config.layout_modes[self.current_screen_type]
        
        self._update_constraints_for_screen_type()
    
    def _update_constraints_for_screen_type(self):
        """根据屏幕类型更新约束"""
        screen_type = self.current_screen_type
        
        if screen_type in [ScreenType.MOBILE_SMALL, ScreenType.MOBILE_LARGE]:
            self.constraints = LayoutConstraints(
                min_width=280,
                max_width=600,
                min_height=200,
                max_height=800,
                padding=8,
                margin=4,
                gap=8
            )
        elif screen_type == ScreenType.TABLET:
            self.constraints = LayoutConstraints(
                min_width=400,
                max_width=1024,
                min_height=300,
                max_height=1000,
                padding=12,
                margin=6,
                gap=10
            )
        else:  # DESKTOP
            self.constraints = LayoutConstraints(
                min_width=600,
                max_width=1920,
                min_height=400,
                max_height=1200,
                padding=16,
                margin=8,
                gap=12
            )
        
        # 设置尺寸限制
        self.setMinimumSize(self.constraints.min_width, self.constraints.min_height)
        self.setMaximumSize(self.constraints.max_width, self.constraints.max_height)
    
    def _setup_ui(self):
        """设置UI"""
        self.setAcceptTouchEvents(True)
        self.setMouseTracking(True)
        
        # 初始化响应式元素
        self._init_responsive_elements()
    
    def _setup_responsive_behavior(self):
        """设置响应式行为"""
        # 窗口大小变化监听
        self.resized.connect(self._on_resize)
        
        # 自动布局更新
        self.layout_update_timer.start(100)  # 100ms延迟更新
    
    def _init_responsive_elements(self):
        """初始化响应式元素"""
        # 根据当前屏幕类型初始化元素
        self._update_responsive_text()
        self._update_responsive_colors()
    
    def _update_responsive_text(self):
        """更新响应式文本"""
        font_config = self.config.font_config[self.current_screen_type]
        
        # 更新标题字体
        title_font = QFont()
        title_font.setPointSize(font_config['title_size'])
        title_font.setBold(True)
        self.responsive_text['title'] = title_font
        
        # 更新标签字体
        label_font = QFont()
        label_font.setPointSize(font_config['label_size'])
        self.responsive_text['label'] = label_font
        
        # 更新基础字体
        base_font = QFont()
        base_font.setPointSize(font_config['base_size'])
        self.responsive_text['base'] = base_font
    
    def _update_responsive_colors(self):
        """更新响应式颜色"""
        screen_type = self.current_screen_type
        
        if screen_type in [ScreenType.MOBILE_SMALL, ScreenType.MOBILE_LARGE]:
            # 手机模式使用更亮、更饱和的颜色
            self.responsive_colors.update({
                'background': QColor(250, 250, 250),
                'primary': QColor(0, 120, 215),
                'secondary': QColor(100, 100, 100),
                'accent': QColor(255, 140, 0)
            })
        else:
            # 桌面模式使用更保守的颜色
            self.responsive_colors.update({
                'background': QColor(245, 245, 245),
                'primary': QColor(0, 90, 158),
                'secondary': QColor(80, 80, 80),
                'accent': QColor(225, 105, 0)
            })
    
    def _on_resize(self, width: int, height: int):
        """窗口大小变化处理"""
        # 检测是否需要改变屏幕类型
        old_screen_type = self.current_screen_type
        self._detect_screen_type()
        
        if self.current_screen_type != old_screen_type:
            # 屏幕类型变化，重新配置布局
            self.layout_changed.emit(self.current_screen_type, self.current_layout_mode)
        
        # 延迟更新布局
        if not self.layout_update_timer.isActive():
            self.layout_update_timer.start(100)
        
        self.screen_resized.emit(width, height)
    
    def _update_layout(self):
        """更新布局"""
        # 重新计算元素位置和大小
        self._recalculate_element_positions()
        self._update_interaction_mode()
        
        # 重绘
        self.update()
    
    def _recalculate_element_positions(self):
        """重新计算元素位置"""
        rect = self.rect()
        padding = self.constraints.padding
        gap = self.constraints.gap
        
        # 根据布局模式调整元素
        if self.current_layout_mode == LayoutMode.COMPACT:
            # 紧凑模式：隐藏非必要元素，缩小间距
            self._apply_compact_layout(rect, padding, gap * 0.5)
        elif self.current_layout_mode == LayoutMode.EXTENDED:
            # 扩展模式：显示更多元素，增加间距
            self._apply_extended_layout(rect, padding, gap * 1.5)
        else:  # STANDARD
            # 标准模式
            self._apply_standard_layout(rect, padding, gap)
    
    def _apply_compact_layout(self, rect: QRectF, padding: int, gap: float):
        """应用紧凑布局"""
        available_rect = QRectF(
            rect.x() + padding,
            rect.y() + padding,
            rect.width() - 2 * padding,
            rect.height() - 2 * padding
        )
        
        # 紧凑模式下只显示主要内容
        chart_rect = QRectF(
            available_rect.x(),
            available_rect.y(),
            available_rect.width(),
            available_rect.height() * 0.9
        )
        
        self.chart_elements['main'] = chart_rect
        
        # 隐藏或缩小工具栏
        tool_rect = QRectF(
            available_rect.x(),
            chart_rect.bottom() + gap,
            available_rect.width(),
            available_rect.height() * 0.1
        )
        self.chart_elements['toolbar'] = tool_rect
    
    def _apply_standard_layout(self, rect: QRectF, padding: int, gap: float):
        """应用标准布局"""
        available_rect = QRectF(
            rect.x() + padding,
            rect.y() + padding,
            rect.width() - 2 * padding,
            rect.height() - 2 * padding
        )
        
        # 标准布局：主要内容 + 侧边工具栏
        main_width = available_rect.width() * 0.8
        sidebar_width = available_rect.width() * 0.2
        
        chart_rect = QRectF(
            available_rect.x(),
            available_rect.y(),
            main_width - gap,
            available_rect.height()
        )
        
        sidebar_rect = QRectF(
            chart_rect.right() + gap,
            available_rect.y(),
            sidebar_width - gap,
            available_rect.height()
        )
        
        self.chart_elements['main'] = chart_rect
        self.chart_elements['sidebar'] = sidebar_rect
    
    def _apply_extended_layout(self, rect: QRectF, padding: int, gap: float):
        """应用扩展布局"""
        available_rect = QRectF(
            rect.x() + padding,
            rect.y() + padding,
            rect.width() - 2 * padding,
            rect.height() - 2 * padding
        )
        
        # 扩展布局：主内容 + 工具栏 + 信息面板
        toolbar_height = available_rect.height() * 0.1
        
        chart_rect = QRectF(
            available_rect.x(),
            available_rect.y() + toolbar_height + gap,
            available_rect.width() - gap * 2,
            available_rect.height() * 0.7
        )
        
        toolbar_rect = QRectF(
            available_rect.x(),
            available_rect.y(),
            available_rect.width(),
            toolbar_height
        )
        
        info_panel_rect = QRectF(
            available_rect.x(),
            chart_rect.bottom() + gap,
            available_rect.width(),
            available_rect.height() * 0.2 - gap
        )
        
        self.chart_elements['main'] = chart_rect
        self.chart_elements['toolbar'] = toolbar_rect
        self.chart_elements['info_panel'] = info_panel_rect
    
    def _update_interaction_mode(self):
        """更新交互模式"""
        # 简单的交互模式检测
        # 在实际应用中，这里可以实现更复杂的逻辑
        if self.current_screen_type in [ScreenType.MOBILE_SMALL, ScreenType.MOBILE_LARGE]:
            new_mode = InteractionMode.TOUCH
        else:
            new_mode = InteractionMode.MOUSE
        
        if new_mode != self.current_interaction_mode:
            self.current_interaction_mode = new_mode
            self.interaction_mode_changed.emit(new_mode)
    
    def add_chart_element(self, element_id: str, element_data: Dict[str, Any]):
        """添加图表元素"""
        self.chart_elements[element_id] = element_data
    
    def get_responsive_value(self, value_name: str, base_value: float) -> float:
        """获取响应式数值"""
        # 根据屏幕类型缩放数值
        scale_factors = {
            ScreenType.MOBILE_SMALL: 0.8,
            ScreenType.MOBILE_LARGE: 0.9,
            ScreenType.TABLET: 1.0,
            ScreenType.DESKTOP: 1.0,
            ScreenType.DESKTOP_LARGE: 1.2
        }
        
        scale = scale_factors.get(self.current_screen_type, 1.0)
        return base_value * scale
    
    def get_touch_gesture(self, gesture_id: str) -> Optional[TouchGesture]:
        """获取触摸手势"""
        return self.touch_gestures.get(gesture_id)
    
    def event(self, event):
        """事件处理"""
        # 处理触摸事件
        if hasattr(event, 'type'):
            if event.type() == event.TouchBegin:
                return self._on_touch_begin(event)
            elif event.type() == event.TouchUpdate:
                return self._on_touch_update(event)
            elif event.type() == event.TouchEnd:
                return self._on_touch_end(event)
        
        return super().event(event)
    
    def _on_touch_begin(self, event):
        """触摸开始处理"""
        for touch in event.touches():
            touch_id = touch.id()
            self.active_touches[touch_id] = touch.pos()
            
            # 识别手势
            if len(self.active_touches) == 1:
                # 单点触摸，可能是点击或拖拽
                gesture = TouchGesture()
                gesture.add_point(touch.pos())
                self.touch_gestures['single'] = gesture
        
        return True
    
    def _on_touch_update(self, event):
        """触摸更新处理"""
        for touch in event.touches():
            touch_id = touch.id()
            if touch_id in self.active_touches:
                self.active_touches[touch_id] = touch.pos()
                
                # 更新手势
                if 'single' in self.touch_gestures:
                    self.touch_gestures['single'].add_point(touch.pos())
        
        return True
    
    def _on_touch_end(self, event):
        """触摸结束处理"""
        for touch in event.changedTouches():
            touch_id = touch.id()
            if touch_id in self.active_touches:
                del self.active_touches[touch_id]
        
        # 手势识别
        self._recognize_gestures()
        return True
    
    def _recognize_gestures(self):
        """识别手势"""
        if 'single' in self.touch_gestures:
            gesture = self.touch_gestures['single']
            distance = gesture.get_distance()
            
            if distance < self.gesture_recognition_threshold:
                # 识别为点击手势
                self._handle_tap_gesture()
            else:
                # 识别为拖拽手势
                self._handle_pan_gesture(gesture)
        
        # 多点触摸处理
        if len(self.active_touches) >= 2:
            self._handle_pinch_gesture()
    
    def _handle_tap_gesture(self):
        """处理点击手势"""
        # 双击检测
        current_time = time.time()
        last_tap = self.last_tap_time.get('default', 0)
        
        if current_time - last_tap < self.config.touch_config['double_tap_threshold']:
            # 双击
            self._handle_double_tap()
        else:
            # 单击
            self._handle_single_tap()
        
        self.last_tap_time['default'] = current_time
    
    def _handle_pan_gesture(self, gesture: TouchGesture):
        """处理拖拽手势"""
        velocity = gesture.get_velocity()
        
        # 实现拖拽逻辑
        if abs(velocity.x()) > 50 or abs(velocity.y()) > 50:
            # 快速拖拽，触发平移
            self._on_pan_gesture(velocity)
    
    def _handle_pinch_gesture(self):
        """处理缩放手势"""
        if self.config.touch_config['pinch_zoom_enabled']:
            self._on_pinch_gesture()
    
    def _handle_single_tap(self):
        """处理单击"""
        pass  # 在实际实现中添加具体逻辑
    
    def _handle_double_tap(self):
        """处理双击"""
        # 重置缩放或执行特定操作
        pass  # 在实际实现中添加具体逻辑
    
    def _on_pan_gesture(self, velocity: QPointF):
        """平移手势"""
        pass  # 在实际实现中添加具体逻辑
    
    def _on_pinch_gesture(self):
        """缩放手势"""
        pass  # 在实际实现中添加具体逻辑
    
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置背景
        painter.fillRect(self.rect(), self.responsive_colors['background'])
        
        # 绘制图表元素
        self._draw_chart_elements(painter)
        
        # 绘制调试信息（开发时可用）
        if hasattr(self, 'debug_mode') and self.debug_mode:
            self._draw_debug_info(painter)
    
    def _draw_chart_elements(self, painter: QPainter):
        """绘制图表元素"""
        for element_id, element_data in self.chart_elements.items():
            if isinstance(element_data, QRectF):
                self._draw_element(painter, element_id, element_data)
    
    def _draw_element(self, painter: QPainter, element_id: str, rect: QRectF):
        """绘制单个元素"""
        if element_id == 'main':
            # 绘制主图表区域
            painter.setPen(QPen(self.responsive_colors['primary'], 2))
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.drawRect(rect)
            
            # 添加标题（如果需要）
            if self.current_layout_mode != LayoutMode.COMPACT:
                painter.setFont(self.responsive_text.get('title', QFont()))
                painter.drawText(rect.topLeft(), "Chart Area")
        
        elif element_id == 'sidebar':
            # 绘制侧边栏
            painter.setPen(QPen(self.responsive_colors['secondary'], 1))
            painter.setBrush(QBrush(self.responsive_colors['primary']))
            painter.drawRect(rect)
            
            painter.setFont(self.responsive_text.get('label', QFont()))
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(rect.center(), "Tools")
        
        elif element_id == 'toolbar':
            # 绘制工具栏
            painter.setPen(QPen(self.responsive_colors['accent'], 2))
            painter.drawRect(rect)
    
    def _draw_debug_info(self, painter: QPainter):
        """绘制调试信息"""
        painter.setFont(self.responsive_text.get('base', QFont()))
        painter.setPen(QPen(QColor(0, 0, 0)))
        
        debug_info = [
            f"Screen Type: {self.current_screen_type.value}",
            f"Layout Mode: {self.current_layout_mode.value}",
            f"Interaction Mode: {self.current_interaction_mode.value}",
            f"Size: {self.width()}x{self.height()}",
            f"Touches: {len(self.active_touches)}"
        ]
        
        y_offset = 10
        for info in debug_info:
            painter.drawText(10, y_offset, info)
            y_offset += 15
    
    def get_screen_info(self) -> ScreenInfo:
        """获取屏幕信息"""
        screen = QApplication.desktop().screenGeometry()
        
        return ScreenInfo(
            screen_type=self.current_screen_type,
            width=screen.width(),
            height=screen.height(),
            dpi=screen.physicalDpiX(),
            is_touch_device=len(self.active_touches) > 0,
            available_geometry=QRectF(screen),
            safe_area=QRectF(screen.x() + 20, screen.y() + 20, 
                           screen.width() - 40, screen.height() - 40)
        )
    
    def set_debug_mode(self, enabled: bool):
        """设置调试模式"""
        self.debug_mode = enabled
        self.update()

class ResponsiveOptimizer:
    """响应式图表组件布局优化器"""
    
    def __init__(self, config: Optional[ResponsiveConfig] = None):
        self.config = config or ResponsiveConfig()
        self.widgets = {}
        self.screen_info = None
        self.layout_history = deque(maxlen=10)
    
    def register_widget(self, widget_id: str, widget: ResponsiveChartWidget):
        """注册响应式组件"""
        self.widgets[widget_id] = widget
        widget.layout_changed.connect(self._on_layout_changed)
        widget.interaction_mode_changed.connect(self._on_interaction_mode_changed)
    
    def update_all_layouts(self):
        """更新所有布局"""
        for widget in self.widgets.values():
            widget._update_layout()
    
    def _on_layout_changed(self, screen_type: ScreenType, layout_mode: LayoutMode):
        """布局变化处理"""
        # 记录布局变化历史
        self.layout_history.append({
            'timestamp': time.time(),
            'screen_type': screen_type,
            'layout_mode': layout_mode
        })
        
        # 可以在这里添加全局布局协调逻辑
        logger.debug(f"布局变化: {screen_type.value} - {layout_mode.value}")
    
    def _on_interaction_mode_changed(self, interaction_mode: InteractionMode):
        """交互模式变化处理"""
        logger.debug(f"交互模式变化: {interaction_mode.value}")
    
    def get_layout_statistics(self) -> Dict[str, Any]:
        """获取布局统计信息"""
        return {
            'total_widgets': len(self.widgets),
            'screen_types': {
                widget_id: widget.current_screen_type.value
                for widget_id, widget in self.widgets.items()
            },
            'layout_modes': {
                widget_id: widget.current_layout_mode.value
                for widget_id, widget in self.widgets.items()
            },
            'layout_history_count': len(self.layout_history)
        }

# 便捷函数
def create_responsive_config(**kwargs) -> ResponsiveConfig:
    """创建响应式配置"""
    return ResponsiveConfig(**kwargs)

def create_responsive_widget(config: Optional[ResponsiveConfig] = None) -> ResponsiveChartWidget:
    """创建响应式图表组件"""
    return ResponsiveChartWidget(config)

def create_layout_manager(config: Optional[ResponsiveConfig] = None) -> ResponsiveOptimizer:
    """创建布局管理器"""
    return ResponsiveOptimizer(config)