"""
响应式布局管理器
为EnhancedDataImportWidget提供响应式布局支持，实现自适应屏幕尺寸的界面调整
"""

from loguru import logger
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QScrollArea, QTabWidget, QGroupBox, QFrame, QApplication
)
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QSize, QRect
from PyQt5.QtGui import QResizeEvent, QScreen
import threading

class ScreenSize(Enum):
    """屏幕尺寸分类枚举"""
    EXTRA_SMALL = "xs"  # < 576px
    SMALL = "sm"        # 576px - 768px
    MEDIUM = "md"       # 768px - 992px
    LARGE = "lg"        # 992px - 1200px
    EXTRA_LARGE = "xl"  # >= 1200px

class LayoutMode(Enum):
    """布局模式枚举"""
    COMPACT = "compact"      # 紧凑模式
    NORMAL = "normal"        # 正常模式
    EXPANDED = "expanded"    # 扩展模式
    TOUCH = "touch"          # 触摸友好模式

class Orientation(Enum):
    """方向枚举"""
    PORTRAIT = "portrait"    # 竖屏
    LANDSCAPE = "landscape"  # 横屏

@dataclass
class BreakpointConfig:
    """断点配置数据类"""
    min_width: int
    max_width: int
    columns: int
    spacing: int
    margins: Tuple[int, int, int, int]  # top, right, bottom, left
    font_scale: float = 1.0
    touch_friendly: bool = False

@dataclass
class ResponsiveConfig:
    """响应式配置数据类"""
    breakpoints: Dict[ScreenSize, BreakpointConfig] = field(default_factory=dict)
    adaptive_spacing: bool = True
    adaptive_fonts: bool = True
    touch_optimization: bool = True
    animation_enabled: bool = True

    def __post_init__(self):
        if not self.breakpoints:
            self.breakpoints = {
                ScreenSize.EXTRA_SMALL: BreakpointConfig(
                    min_width=0, max_width=575, columns=1, spacing=8,
                    margins=(8, 8, 8, 8), font_scale=0.9, touch_friendly=True
                ),
                ScreenSize.SMALL: BreakpointConfig(
                    min_width=576, max_width=767, columns=2, spacing=12,
                    margins=(12, 12, 12, 12), font_scale=0.95, touch_friendly=True
                ),
                ScreenSize.MEDIUM: BreakpointConfig(
                    min_width=768, max_width=991, columns=2, spacing=16,
                    margins=(16, 16, 16, 16), font_scale=1.0, touch_friendly=False
                ),
                ScreenSize.LARGE: BreakpointConfig(
                    min_width=992, max_width=1199, columns=3, spacing=20,
                    margins=(20, 20, 20, 20), font_scale=1.0, touch_friendly=False
                ),
                ScreenSize.EXTRA_LARGE: BreakpointConfig(
                    min_width=1200, max_width=9999, columns=4, spacing=24,
                    margins=(24, 24, 24, 24), font_scale=1.0, touch_friendly=False
                )
            }

@dataclass
class ComponentConfig:
    """组件配置数据类"""
    component_id: str
    widget: QWidget
    min_width: int = 200
    min_height: int = 100
    preferred_width: int = 400
    preferred_height: int = 300
    max_width: int = 9999
    max_height: int = 9999
    collapsible: bool = False
    priority: int = 1  # 1=最高优先级，数字越大优先级越低
    responsive_rules: Dict[ScreenSize, Dict[str, Any]] = field(default_factory=dict)

class ResponsiveLayoutEngine:
    """响应式布局引擎"""

    def __init__(self, config: ResponsiveConfig):
        self.config = config
        self.current_screen_size = ScreenSize.MEDIUM
        self.current_orientation = Orientation.LANDSCAPE
        self.current_layout_mode = LayoutMode.NORMAL
        self.components: Dict[str, ComponentConfig] = {}
        self.layout_cache: Dict[str, Any] = {}

    def register_component(self, component_config: ComponentConfig):
        """注册组件"""
        self.components[component_config.component_id] = component_config
        logger.debug(f"组件已注册: {component_config.component_id}")

    def unregister_component(self, component_id: str):
        """注销组件"""
        if component_id in self.components:
            del self.components[component_id]
            logger.debug(f"组件已注销: {component_id}")

    def detect_screen_size(self, width: int, height: int) -> ScreenSize:
        """检测屏幕尺寸分类"""
        for size, config in self.config.breakpoints.items():
            if config.min_width <= width <= config.max_width:
                return size
        return ScreenSize.MEDIUM

    def detect_orientation(self, width: int, height: int) -> Orientation:
        """检测屏幕方向"""
        return Orientation.LANDSCAPE if width > height else Orientation.PORTRAIT

    def determine_layout_mode(self, screen_size: ScreenSize, orientation: Orientation) -> LayoutMode:
        """确定布局模式"""
        if screen_size in [ScreenSize.EXTRA_SMALL, ScreenSize.SMALL]:
            return LayoutMode.TOUCH if self.config.touch_optimization else LayoutMode.COMPACT
        elif screen_size == ScreenSize.MEDIUM:
            return LayoutMode.NORMAL
        else:
            return LayoutMode.EXPANDED

    def calculate_layout(self, container_width: int, container_height: int) -> Dict[str, Any]:
        """计算布局"""
        try:
            # 检测当前环境
            screen_size = self.detect_screen_size(container_width, container_height)
            orientation = self.detect_orientation(container_width, container_height)
            layout_mode = self.determine_layout_mode(screen_size, orientation)

            # 获取断点配置
            breakpoint = self.config.breakpoints[screen_size]

            # 计算布局参数
            layout_params = {
                'screen_size': screen_size,
                'orientation': orientation,
                'layout_mode': layout_mode,
                'columns': breakpoint.columns,
                'spacing': breakpoint.spacing,
                'margins': breakpoint.margins,
                'font_scale': breakpoint.font_scale,
                'touch_friendly': breakpoint.touch_friendly,
                'container_width': container_width,
                'container_height': container_height
            }

            # 计算组件布局
            component_layouts = self._calculate_component_layouts(layout_params)
            layout_params['components'] = component_layouts

            return layout_params

        except Exception as e:
            logger.error(f"计算布局失败: {e}")
            return {}

    def _calculate_component_layouts(self, layout_params: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """计算组件布局"""
        try:
            screen_size = layout_params['screen_size']
            columns = layout_params['columns']
            container_width = layout_params['container_width']
            spacing = layout_params['spacing']
            margins = layout_params['margins']

            # 计算可用宽度
            available_width = container_width - margins[1] - margins[3] - (columns - 1) * spacing
            column_width = available_width // columns

            component_layouts = {}

            # 按优先级排序组件
            sorted_components = sorted(
                self.components.values(),
                key=lambda c: c.priority
            )

            current_row = 0
            current_col = 0

            for component in sorted_components:
                # 获取组件的响应式规则
                rules = component.responsive_rules.get(screen_size, {})

                # 计算组件尺寸
                width = min(
                    rules.get('width', component.preferred_width),
                    column_width
                )
                height = rules.get('height', component.preferred_height)

                # 检查是否需要换行
                if current_col >= columns:
                    current_row += 1
                    current_col = 0

                # 计算位置
                x = margins[3] + current_col * (column_width + spacing)
                y = margins[0] + current_row * (height + spacing)

                component_layouts[component.component_id] = {
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'visible': rules.get('visible', True),
                    'collapsed': rules.get('collapsed', False)
                }

                current_col += 1

            return component_layouts

        except Exception as e:
            logger.error(f"计算组件布局失败: {e}")
            return {}

class ResponsiveLayoutManager(QObject):
    """响应式布局管理器主类"""

    # 信号定义
    layout_changed = pyqtSignal(dict)  # layout_params
    screen_size_changed = pyqtSignal(str)  # screen_size
    orientation_changed = pyqtSignal(str)  # orientation

    def __init__(self, target_widget: QWidget, config: ResponsiveConfig = None):
        super().__init__()

        self.target_widget = target_widget
        self.config = config or ResponsiveConfig()
        self.layout_engine = ResponsiveLayoutEngine(self.config)

        # 状态管理
        self.current_layout_params: Dict[str, Any] = {}
        self.is_enabled = True
        self.is_animating = False

        # 布局更新定时器（防抖）
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._perform_layout_update)
        self.update_delay = 100  # 100ms延迟

        # 监听窗口大小变化
        self.target_widget.installEventFilter(self)

        # 初始布局
        self._schedule_layout_update()

        logger.info("响应式布局管理器已初始化")

    def eventFilter(self, obj, event):
        """事件过滤器"""
        if obj == self.target_widget and event.type() == event.Resize:
            if self.is_enabled:
                self._schedule_layout_update()
        return super().eventFilter(obj, event)

    def _schedule_layout_update(self):
        """调度布局更新"""
        if not self.is_animating:
            self.update_timer.start(self.update_delay)

    def _perform_layout_update(self):
        """执行布局更新"""
        try:
            if not self.is_enabled:
                return

            # 获取当前尺寸
            size = self.target_widget.size()
            width = size.width()
            height = size.height()

            if width <= 0 or height <= 0:
                return

            # 计算新布局
            new_layout_params = self.layout_engine.calculate_layout(width, height)

            if not new_layout_params:
                return

            # 检查是否需要更新
            if self._should_update_layout(new_layout_params):
                self._apply_layout(new_layout_params)
                self.current_layout_params = new_layout_params
                self.layout_changed.emit(new_layout_params)

                # 发送变化信号
                if 'screen_size' in new_layout_params:
                    self.screen_size_changed.emit(new_layout_params['screen_size'].value)
                if 'orientation' in new_layout_params:
                    self.orientation_changed.emit(new_layout_params['orientation'].value)

        except Exception as e:
            logger.error(f"执行布局更新失败: {e}")

    def _should_update_layout(self, new_params: Dict[str, Any]) -> bool:
        """检查是否需要更新布局"""
        if not self.current_layout_params:
            return True

        # 检查关键参数是否变化
        key_params = ['screen_size', 'orientation', 'layout_mode', 'columns']
        for param in key_params:
            if self.current_layout_params.get(param) != new_params.get(param):
                return True

        return False

    def _apply_layout(self, layout_params: Dict[str, Any]):
        """应用布局"""
        try:
            screen_size = layout_params.get('screen_size')
            layout_mode = layout_params.get('layout_mode')

            # 应用全局样式调整
            self._apply_global_styles(layout_params)

            # 应用组件布局
            components = layout_params.get('components', {})
            for component_id, component_layout in components.items():
                self._apply_component_layout(component_id, component_layout)

            logger.debug(f"布局已应用: {screen_size.value if screen_size else 'unknown'}")

        except Exception as e:
            logger.error(f"应用布局失败: {e}")

    def _apply_global_styles(self, layout_params: Dict[str, Any]):
        """应用全局样式调整"""
        try:
            font_scale = layout_params.get('font_scale', 1.0)
            touch_friendly = layout_params.get('touch_friendly', False)

            # 调整字体大小
            if self.config.adaptive_fonts and font_scale != 1.0:
                self._scale_fonts(font_scale)

            # 应用触摸友好样式
            if touch_friendly and self.config.touch_optimization:
                self._apply_touch_styles()

        except Exception as e:
            logger.error(f"应用全局样式失败: {e}")

    def _scale_fonts(self, scale: float):
        """缩放字体"""
        try:
            from PyQt5.QtGui import QFont

            def _apply_scale(widget: QWidget):
                current_font = widget.font()
                if current_font.pointSize() > 0:
                    new_size = max(6, int(current_font.pointSize() * scale))
                    current_font.setPointSize(new_size)
                elif current_font.pixelSize() > 0:
                    new_size = max(8, int(current_font.pixelSize() * scale))
                    current_font.setPixelSize(new_size)
                widget.setFont(current_font)
                for child in widget.findChildren(QWidget):
                    _apply_scale(child)

            _apply_scale(self.target_widget)

        except Exception as e:
            logger.error(f"缩放字体失败: {e}")

    def _apply_touch_styles(self):
        """应用触摸友好样式"""
        try:
            # 增加按钮尺寸、间距等
            touch_stylesheet = """
            QPushButton {
                min-height: 44px;
                padding: 12px 16px;
            }
            QTabBar::tab {
                min-height: 44px;
                padding: 8px 16px;
            }
            """

            current_style = self.target_widget.styleSheet()
            if "min-height: 44px" not in current_style:
                self.target_widget.setStyleSheet(current_style + touch_stylesheet)

        except Exception as e:
            logger.error(f"应用触摸样式失败: {e}")

    def _apply_component_layout(self, component_id: str, layout: Dict[str, Any]):
        """应用组件布局"""
        try:
            component_config = self.layout_engine.components.get(component_id)
            if not component_config:
                return

            widget = component_config.widget

            # 设置位置和尺寸
            x = layout.get('x', 0)
            y = layout.get('y', 0)
            width = layout.get('width', widget.width())
            height = layout.get('height', widget.height())

            widget.setGeometry(x, y, width, height)

            # 设置可见性
            visible = layout.get('visible', True)
            widget.setVisible(visible)

            # 处理折叠状态
            collapsed = layout.get('collapsed', False)
            if hasattr(widget, 'setCollapsed'):
                widget.setCollapsed(collapsed)

        except Exception as e:
            logger.error(f"应用组件布局失败: {e}")

    # 公共接口方法
    def register_component(self, component_id: str, widget: QWidget, **kwargs):
        """注册组件"""
        component_config = ComponentConfig(
            component_id=component_id,
            widget=widget,
            **kwargs
        )
        self.layout_engine.register_component(component_config)

    def unregister_component(self, component_id: str):
        """注销组件"""
        self.layout_engine.unregister_component(component_id)

    def set_component_responsive_rules(self, component_id: str, rules: Dict[ScreenSize, Dict[str, Any]]):
        """设置组件响应式规则"""
        if component_id in self.layout_engine.components:
            self.layout_engine.components[component_id].responsive_rules = rules
            self._schedule_layout_update()

    def enable_responsive_layout(self, enabled: bool = True):
        """启用/禁用响应式布局"""
        self.is_enabled = enabled
        if enabled:
            self._schedule_layout_update()

    def set_update_delay(self, delay_ms: int):
        """设置更新延迟"""
        self.update_delay = max(50, delay_ms)  # 最小50ms

    def force_layout_update(self):
        """强制布局更新"""
        self.update_timer.stop()
        self._perform_layout_update()

    def get_current_screen_size(self) -> Optional[ScreenSize]:
        """获取当前屏幕尺寸分类"""
        return self.current_layout_params.get('screen_size')

    def get_current_orientation(self) -> Optional[Orientation]:
        """获取当前屏幕方向"""
        return self.current_layout_params.get('orientation')

    def get_current_layout_mode(self) -> Optional[LayoutMode]:
        """获取当前布局模式"""
        return self.current_layout_params.get('layout_mode')

    def get_layout_statistics(self) -> Dict[str, Any]:
        """获取布局统计信息"""
        try:
            return {
                'enabled': self.is_enabled,
                'current_screen_size': self.get_current_screen_size().value if self.get_current_screen_size() else None,
                'current_orientation': self.get_current_orientation().value if self.get_current_orientation() else None,
                'current_layout_mode': self.get_current_layout_mode().value if self.get_current_layout_mode() else None,
                'registered_components': len(self.layout_engine.components),
                'container_size': {
                    'width': self.current_layout_params.get('container_width', 0),
                    'height': self.current_layout_params.get('container_height', 0)
                },
                'layout_params': self.current_layout_params.copy(),
                'update_delay': self.update_delay,
                'is_animating': self.is_animating
            }

        except Exception as e:
            logger.error(f"获取布局统计失败: {e}")
            return {'error': str(e)}

class ResponsiveTabWidget(QTabWidget):
    """响应式标签页组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.responsive_manager: Optional[ResponsiveLayoutManager] = None
        self.tab_configs: Dict[int, Dict[str, Any]] = {}

    def setup_responsive_behavior(self, config: ResponsiveConfig = None):
        """设置响应式行为"""
        self.responsive_manager = ResponsiveLayoutManager(self, config)
        self.responsive_manager.screen_size_changed.connect(self._on_screen_size_changed)

    def _on_screen_size_changed(self, screen_size: str):
        """屏幕尺寸变化处理"""
        try:
            size_enum = ScreenSize(screen_size)

            # 在小屏幕上隐藏某些标签页
            if size_enum in [ScreenSize.EXTRA_SMALL, ScreenSize.SMALL]:
                self._apply_compact_mode()
            else:
                self._apply_normal_mode()

        except Exception as e:
            logger.error(f"处理屏幕尺寸变化失败: {e}")

    def _apply_compact_mode(self):
        """应用紧凑模式"""
        # 可以隐藏低优先级的标签页
        for i in range(self.count()):
            tab_config = self.tab_configs.get(i, {})
            if tab_config.get('priority', 1) > 2:  # 优先级低于2的隐藏
                self.setTabVisible(i, False)

    def _apply_normal_mode(self):
        """应用正常模式"""
        # 显示所有标签页
        for i in range(self.count()):
            self.setTabVisible(i, True)

    def set_tab_priority(self, index: int, priority: int):
        """设置标签页优先级"""
        if index not in self.tab_configs:
            self.tab_configs[index] = {}
        self.tab_configs[index]['priority'] = priority

class ResponsiveGridLayout(QGridLayout):
    """响应式网格布局"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.responsive_config = ResponsiveConfig()
        self.current_columns = 2

    def addWidget(self, widget, row, column, rowSpan=1, columnSpan=1, alignment=0):
        """添加组件（重写以支持响应式）"""
        super().addWidget(widget, row, column, rowSpan, columnSpan, alignment)

        # 为组件添加响应式属性
        if hasattr(widget, 'setProperty'):
            widget.setProperty('responsive_row', row)
            widget.setProperty('responsive_column', column)
            widget.setProperty('responsive_rowSpan', rowSpan)
            widget.setProperty('responsive_columnSpan', columnSpan)

    def adjust_for_screen_size(self, screen_size: ScreenSize):
        """根据屏幕尺寸调整布局"""
        try:
            breakpoint = self.responsive_config.breakpoints[screen_size]
            target_columns = breakpoint.columns

            if target_columns != self.current_columns:
                self._reorganize_layout(target_columns)
                self.current_columns = target_columns

        except Exception as e:
            logger.error(f"调整网格布局失败: {e}")

    def _reorganize_layout(self, new_columns: int):
        """重新组织布局"""
        try:
            # 获取所有组件
            widgets = []
            for i in range(self.count()):
                item = self.itemAt(i)
                if item and item.widget():
                    widgets.append(item.widget())

            # 清空布局
            while self.count():
                child = self.takeAt(0)
                if child.widget():
                    child.widget().setParent(None)

            # 重新添加组件
            for i, widget in enumerate(widgets):
                row = i // new_columns
                col = i % new_columns
                self.addWidget(widget, row, col)

        except Exception as e:
            logger.error(f"重新组织布局失败: {e}")

def create_responsive_layout_manager(widget: QWidget, **config_kwargs) -> ResponsiveLayoutManager:
    """创建响应式布局管理器的便捷函数"""
    config = ResponsiveConfig(**config_kwargs)
    return ResponsiveLayoutManager(widget, config)

def apply_responsive_behavior(widget: QWidget, **config_kwargs) -> ResponsiveLayoutManager:
    """为组件应用响应式行为的便捷函数"""
    manager = create_responsive_layout_manager(widget, **config_kwargs)

    # 自动注册子组件
    for child in widget.findChildren(QWidget):
        if child.objectName():
            manager.register_component(
                child.objectName(),
                child,
                preferred_width=child.width() or 200,
                preferred_height=child.height() or 100
            )

    return manager
