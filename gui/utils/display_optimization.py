"""
显示优化模块
实现高DPI显示器和触摸屏的优化支持，确保UI元素在各种显示设备上的清晰度
"""

from loguru import logger
import os
import sys
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QScrollBar,
    QTabWidget, QGroupBox, QFrame, QSizePolicy, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import (
    QScreen, QPixmap, QIcon, QFont, QFontMetrics, QPainter,
    QPixmapCache, QTransform, QPalette, QColor
)
import threading

class DisplayType(Enum):
    """显示器类型枚举"""
    STANDARD = "standard"      # 标准显示器
    HIGH_DPI = "high_dpi"     # 高DPI显示器
    RETINA = "retina"         # Retina显示器
    ULTRA_HIGH_DPI = "ultra_high_dpi"  # 超高DPI显示器

class TouchCapability(Enum):
    """触摸能力枚举"""
    NONE = "none"             # 无触摸
    SINGLE_TOUCH = "single"   # 单点触摸
    MULTI_TOUCH = "multi"     # 多点触摸
    PEN_TOUCH = "pen"         # 笔触摸

class ScalingMode(Enum):
    """缩放模式枚举"""
    SYSTEM = "system"         # 系统缩放
    APPLICATION = "application"  # 应用程序缩放
    CUSTOM = "custom"         # 自定义缩放
    AUTO = "auto"             # 自动缩放

@dataclass
class DisplayInfo:
    """显示器信息数据类"""
    screen_name: str
    width: int
    height: int
    physical_width_mm: float
    physical_height_mm: float
    dpi_x: float
    dpi_y: float
    device_pixel_ratio: float
    display_type: DisplayType
    touch_capability: TouchCapability
    color_depth: int = 24
    refresh_rate: float = 60.0
    is_primary: bool = False

@dataclass
class TouchTarget:
    """触摸目标数据类"""
    min_size: int = 44        # 最小触摸目标尺寸 (像素)
    recommended_size: int = 48  # 推荐触摸目标尺寸
    spacing: int = 8          # 触摸目标间距
    edge_margin: int = 16     # 边缘边距

@dataclass
class DPIConfig:
    """DPI配置数据类"""
    base_dpi: float = 96.0    # 基准DPI
    scale_factor: float = 1.0  # 缩放因子
    font_scale: float = 1.0   # 字体缩放
    icon_scale: float = 1.0   # 图标缩放
    spacing_scale: float = 1.0  # 间距缩放
    touch_targets: TouchTarget = field(default_factory=TouchTarget)

    def copy(self) -> 'DPIConfig':
        """创建配置的深拷贝"""
        return DPIConfig(
            base_dpi=self.base_dpi,
            scale_factor=self.scale_factor,
            font_scale=self.font_scale,
            icon_scale=self.icon_scale,
            spacing_scale=self.spacing_scale,
            touch_targets=TouchTarget(
                min_size=self.touch_targets.min_size,
                recommended_size=self.touch_targets.recommended_size,
                spacing=self.touch_targets.spacing,
                edge_margin=self.touch_targets.edge_margin
            )
        )

class DisplayDetector:
    """显示器检测器"""

    def __init__(self):
        self.displays: Dict[str, DisplayInfo] = {}
        self.primary_display: Optional[DisplayInfo] = None
        self.lock = threading.Lock()

    def detect_displays(self) -> Dict[str, DisplayInfo]:
        """检测所有显示器"""
        try:
            with self.lock:
                self.displays.clear()

                app = QApplication.instance()
                if not app:
                    logger.warning("QApplication实例不存在")
                    return {}

                screens = app.screens()

                for i, screen in enumerate(screens):
                    display_info = self._analyze_screen(screen, i)
                    self.displays[display_info.screen_name] = display_info

                    if screen == app.primaryScreen():
                        self.primary_display = display_info
                        display_info.is_primary = True

                # logger.info(f"检测到 {len(self.displays)} 个显示器")
                return self.displays.copy()

        except Exception as e:
            logger.error(f"检测显示器失败: {e}")
            return {}

    def _analyze_screen(self, screen: QScreen, index: int) -> DisplayInfo:
        """分析屏幕信息"""
        try:
            # 获取基本信息
            geometry = screen.geometry()
            physical_size = screen.physicalSize()

            width = geometry.width()
            height = geometry.height()
            physical_width_mm = physical_size.width()
            physical_height_mm = physical_size.height()

            # 计算DPI
            dpi_x = screen.physicalDotsPerInchX()
            dpi_y = screen.physicalDotsPerInchY()
            device_pixel_ratio = screen.devicePixelRatio()

            # 判断显示器类型
            display_type = self._determine_display_type(dpi_x, dpi_y, device_pixel_ratio)

            # 检测触摸能力
            touch_capability = self._detect_touch_capability()

            # 获取其他信息
            color_depth = screen.depth()
            refresh_rate = screen.refreshRate()

            display_info = DisplayInfo(
                screen_name=f"Display_{index}",
                width=width,
                height=height,
                physical_width_mm=physical_width_mm,
                physical_height_mm=physical_height_mm,
                dpi_x=dpi_x,
                dpi_y=dpi_y,
                device_pixel_ratio=device_pixel_ratio,
                display_type=display_type,
                touch_capability=touch_capability,
                color_depth=color_depth,
                refresh_rate=refresh_rate
            )

            logger.debug(f"屏幕分析完成: {display_info.screen_name}, DPI: {dpi_x:.1f}x{dpi_y:.1f}, 类型: {display_type.value}")

            return display_info

        except Exception as e:
            logger.error(f"分析屏幕失败: {e}")
            # 返回默认信息
            return DisplayInfo(
                screen_name=f"Display_{index}",
                width=1920, height=1080,
                physical_width_mm=510, physical_height_mm=287,
                dpi_x=96, dpi_y=96, device_pixel_ratio=1.0,
                display_type=DisplayType.STANDARD,
                touch_capability=TouchCapability.NONE
            )

    def _determine_display_type(self, dpi_x: float, dpi_y: float, device_pixel_ratio: float) -> DisplayType:
        """判断显示器类型"""
        avg_dpi = (dpi_x + dpi_y) / 2

        if device_pixel_ratio >= 3.0 or avg_dpi >= 300:
            return DisplayType.ULTRA_HIGH_DPI
        elif device_pixel_ratio >= 2.0 or avg_dpi >= 200:
            return DisplayType.RETINA
        elif device_pixel_ratio >= 1.5 or avg_dpi >= 144:
            return DisplayType.HIGH_DPI
        else:
            return DisplayType.STANDARD

    def _detect_touch_capability(self) -> TouchCapability:
        """检测触摸能力"""
        try:
            # 在Windows上检测触摸屏
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                # 获取系统指标
                SM_MAXIMUMTOUCHES = 95
                max_touches = ctypes.windll.user32.GetSystemMetrics(SM_MAXIMUMTOUCHES)

                if max_touches > 10:
                    return TouchCapability.MULTI_TOUCH
                elif max_touches > 0:
                    return TouchCapability.SINGLE_TOUCH
                else:
                    return TouchCapability.NONE

            # 在其他平台上的检测逻辑
            # 这里可以添加Linux和macOS的触摸检测

            return TouchCapability.NONE

        except Exception as e:
            logger.error(f"检测触摸能力失败: {e}")
            return TouchCapability.NONE

    def get_primary_display(self) -> Optional[DisplayInfo]:
        """获取主显示器信息"""
        return self.primary_display

    def get_display_by_name(self, name: str) -> Optional[DisplayInfo]:
        """根据名称获取显示器信息"""
        return self.displays.get(name)

class DPIOptimizer:
    """DPI优化器"""

    def __init__(self):
        self.configs: Dict[DisplayType, DPIConfig] = {}
        self.current_config: Optional[DPIConfig] = None
        self._setup_default_configs()

    def _setup_default_configs(self):
        """设置默认配置"""
        # 标准显示器配置
        self.configs[DisplayType.STANDARD] = DPIConfig(
            base_dpi=96.0,
            scale_factor=1.0,
            font_scale=1.0,
            icon_scale=1.0,
            spacing_scale=1.0,
            touch_targets=TouchTarget(min_size=32, recommended_size=36, spacing=6, edge_margin=12)
        )

        # 高DPI显示器配置
        self.configs[DisplayType.HIGH_DPI] = DPIConfig(
            base_dpi=144.0,
            scale_factor=1.5,
            font_scale=1.2,
            icon_scale=1.5,
            spacing_scale=1.3,
            touch_targets=TouchTarget(min_size=44, recommended_size=48, spacing=8, edge_margin=16)
        )

        # Retina显示器配置
        self.configs[DisplayType.RETINA] = DPIConfig(
            base_dpi=192.0,
            scale_factor=2.0,
            font_scale=1.4,
            icon_scale=2.0,
            spacing_scale=1.5,
            touch_targets=TouchTarget(min_size=48, recommended_size=56, spacing=10, edge_margin=20)
        )

        # 超高DPI显示器配置
        self.configs[DisplayType.ULTRA_HIGH_DPI] = DPIConfig(
            base_dpi=288.0,
            scale_factor=3.0,
            font_scale=1.6,
            icon_scale=3.0,
            spacing_scale=1.8,
            touch_targets=TouchTarget(min_size=56, recommended_size=64, spacing=12, edge_margin=24)
        )

    def get_config_for_display(self, display_info: DisplayInfo) -> DPIConfig:
        """获取显示器对应的配置"""
        config = self.configs.get(display_info.display_type, self.configs[DisplayType.STANDARD]).copy()

        # 根据实际DPI调整配置
        actual_scale = display_info.device_pixel_ratio
        if actual_scale > 1.0:
            config.scale_factor = actual_scale
            config.font_scale = min(2.0, 1.0 + (actual_scale - 1.0) * 0.5)
            config.icon_scale = actual_scale
            config.spacing_scale = min(2.0, 1.0 + (actual_scale - 1.0) * 0.3)

        # 根据触摸能力调整触摸目标
        if display_info.touch_capability != TouchCapability.NONE:
            config.touch_targets.min_size = max(44, int(config.touch_targets.min_size * config.scale_factor))
            config.touch_targets.recommended_size = max(48, int(config.touch_targets.recommended_size * config.scale_factor))
            config.touch_targets.spacing = max(8, int(config.touch_targets.spacing * config.scale_factor))
            config.touch_targets.edge_margin = max(16, int(config.touch_targets.edge_margin * config.scale_factor))

        return config

    def set_current_config(self, config: DPIConfig):
        """设置当前配置"""
        self.current_config = config

    def get_current_config(self) -> Optional[DPIConfig]:
        """获取当前配置"""
        return self.current_config

class TouchOptimizer:
    """触摸优化器"""

    def __init__(self, dpi_config: DPIConfig):
        self.dpi_config = dpi_config
        self.touch_targets = dpi_config.touch_targets

    def optimize_widget_for_touch(self, widget: QWidget):
        """为触摸优化组件"""
        try:
            # 优化按钮
            if isinstance(widget, QPushButton):
                self._optimize_button(widget)

            # 优化标签页
            elif isinstance(widget, QTabWidget):
                self._optimize_tab_widget(widget)

            # 优化滚动条
            elif isinstance(widget, QScrollBar):
                self._optimize_scrollbar(widget)

            # 递归优化子组件
            for child in widget.findChildren(QWidget):
                self.optimize_widget_for_touch(child)

        except Exception as e:
            logger.error(f"触摸优化失败: {e}")

    def _optimize_button(self, button: QPushButton):
        """优化按钮"""
        try:
            # 设置最小尺寸
            min_size = self.touch_targets.min_size
            button.setMinimumSize(min_size, min_size)

            # 设置推荐尺寸
            recommended_size = self.touch_targets.recommended_size
            button.resize(max(button.width(), recommended_size),
                          max(button.height(), recommended_size))

            # 增加内边距
            padding = self.touch_targets.spacing
            button.setStyleSheet(f"""
                QPushButton {{
                    padding: {padding}px {padding * 2}px;
                    min-height: {min_size}px;
                }}
            """)

        except Exception as e:
            logger.error(f"优化按钮失败: {e}")

    def _optimize_tab_widget(self, tab_widget: QTabWidget):
        """优化标签页组件"""
        try:
            # 增加标签页高度
            min_height = self.touch_targets.min_size
            tab_widget.setStyleSheet(f"""
                QTabBar::tab {{
                    min-height: {min_height}px;
                    padding: {self.touch_targets.spacing}px {self.touch_targets.spacing * 2}px;
                }}
            """)

        except Exception as e:
            logger.error(f"优化标签页失败: {e}")

    def _optimize_scrollbar(self, scrollbar: QScrollBar):
        """优化滚动条"""
        try:
            # 增加滚动条宽度
            width = max(16, self.touch_targets.min_size // 3)

            if scrollbar.orientation() == Qt.Vertical:
                scrollbar.setMinimumWidth(width)
            else:
                scrollbar.setMinimumHeight(width)

            scrollbar.setStyleSheet(f"""
                QScrollBar:vertical {{
                    width: {width}px;
                }}
                QScrollBar:horizontal {{
                    height: {width}px;
                }}
                QScrollBar::handle {{
                    min-height: {self.touch_targets.min_size}px;
                    min-width: {self.touch_targets.min_size}px;
                }}
            """)

        except Exception as e:
            logger.error(f"优化滚动条失败: {e}")

class IconScaler:
    """图标缩放器"""

    def __init__(self, scale_factor: float):
        self.scale_factor = scale_factor
        self.icon_cache: Dict[str, QIcon] = {}
        self.pixmap_cache: Dict[Tuple[str, int, int], QPixmap] = {}

    def scale_icon(self, icon: QIcon, base_size: int) -> QIcon:
        """缩放图标"""
        try:
            scaled_size = int(base_size * self.scale_factor)

            # 检查缓存
            cache_key = f"{id(icon)}_{scaled_size}"
            if cache_key in self.icon_cache:
                return self.icon_cache[cache_key]

            # 创建缩放后的图标
            pixmap = icon.pixmap(scaled_size, scaled_size)
            scaled_icon = QIcon(pixmap)

            # 缓存结果
            self.icon_cache[cache_key] = scaled_icon

            return scaled_icon

        except Exception as e:
            logger.error(f"缩放图标失败: {e}")
            return icon

    def scale_pixmap(self, pixmap: QPixmap, target_width: int, target_height: int) -> QPixmap:
        """缩放像素图"""
        try:
            # 检查缓存
            cache_key = (str(id(pixmap)), target_width, target_height)
            if cache_key in self.pixmap_cache:
                return self.pixmap_cache[cache_key]

            # 缩放像素图
            scaled_pixmap = pixmap.scaled(
                target_width, target_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # 缓存结果
            self.pixmap_cache[cache_key] = scaled_pixmap

            return scaled_pixmap

        except Exception as e:
            logger.error(f"缩放像素图失败: {e}")
            return pixmap

    def clear_cache(self):
        """清空缓存"""
        self.icon_cache.clear()
        self.pixmap_cache.clear()

class FontScaler:
    """字体缩放器"""

    def __init__(self, scale_factor: float):
        self.scale_factor = scale_factor
        self.font_cache: Dict[str, QFont] = {}

    def scale_font(self, font: QFont) -> QFont:
        """缩放字体"""
        try:
            # 检查缓存
            cache_key = f"{font.family()}_{font.pointSize()}_{self.scale_factor}"
            if cache_key in self.font_cache:
                return self.font_cache[cache_key]

            # 创建缩放后的字体
            scaled_font = QFont(font)
            original_size = font.pointSize()
            if original_size > 0:
                scaled_size = max(8, int(original_size * self.scale_factor))
                scaled_font.setPointSize(scaled_size)
            else:
                # 使用像素大小
                pixel_size = font.pixelSize()
                if pixel_size > 0:
                    scaled_pixel_size = max(10, int(pixel_size * self.scale_factor))
                    scaled_font.setPixelSize(scaled_pixel_size)

            # 缓存结果
            self.font_cache[cache_key] = scaled_font

            return scaled_font

        except Exception as e:
            logger.error(f"缩放字体失败: {e}")
            return font

    def apply_to_widget(self, widget: QWidget):
        """应用字体缩放到组件"""
        try:
            current_font = widget.font()
            scaled_font = self.scale_font(current_font)
            widget.setFont(scaled_font)

            # 递归应用到子组件
            for child in widget.findChildren(QWidget):
                self.apply_to_widget(child)

        except Exception as e:
            logger.error(f"应用字体缩放失败: {e}")

    def clear_cache(self):
        """清空缓存"""
        self.font_cache.clear()

class DisplayOptimizationManager(QObject):
    """显示优化管理器主类"""

    # 信号定义
    display_changed = pyqtSignal(dict)  # display_info
    optimization_applied = pyqtSignal(str)  # optimization_type

    def __init__(self):
        super().__init__()

        # 核心组件
        self.display_detector = DisplayDetector()
        self.dpi_optimizer = DPIOptimizer()
        self.touch_optimizer: Optional[TouchOptimizer] = None
        self.icon_scaler: Optional[IconScaler] = None
        self.font_scaler: Optional[FontScaler] = None

        # 状态管理
        self.current_display: Optional[DisplayInfo] = None
        self.current_config: Optional[DPIConfig] = None
        self.optimization_enabled = True
        self.managed_widgets: List[QWidget] = []

        # 监控定时器
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._monitor_display_changes)
        self.monitor_timer.start(5000)  # 每5秒检查一次

        # 初始化
        self._initialize()

        logger.info("显示优化管理器已初始化")

    def _initialize(self):
        """初始化"""
        try:
            # 检测显示器
            displays = self.display_detector.detect_displays()

            if displays:
                # 使用主显示器
                primary_display = self.display_detector.get_primary_display()
                if primary_display:
                    self.set_target_display(primary_display)

        except Exception as e:
            logger.error(f"初始化显示优化失败: {e}")

    def set_target_display(self, display_info: DisplayInfo):
        """设置目标显示器"""
        try:
            self.current_display = display_info

            # 获取优化配置
            config = self.dpi_optimizer.get_config_for_display(display_info)
            self.current_config = config
            self.dpi_optimizer.set_current_config(config)

            # 创建优化器
            self.touch_optimizer = TouchOptimizer(config)
            self.icon_scaler = IconScaler(config.icon_scale)
            self.font_scaler = FontScaler(config.font_scale)

            # 应用优化
            self._apply_optimizations()

            # 发送信号
            self.display_changed.emit({
                'display_type': display_info.display_type.value,
                'dpi': f"{display_info.dpi_x:.1f}x{display_info.dpi_y:.1f}",
                'device_pixel_ratio': display_info.device_pixel_ratio,
                'touch_capability': display_info.touch_capability.value,
                'scale_factor': config.scale_factor
            })

            logger.info(f"目标显示器已设置: {display_info.display_type.value}, 缩放: {config.scale_factor}")

        except Exception as e:
            logger.error(f"设置目标显示器失败: {e}")

    def _apply_optimizations(self):
        """应用优化"""
        try:
            if not self.optimization_enabled or not self.current_config:
                return

            # 应用到已注册的组件
            for widget in self.managed_widgets:
                self.optimize_widget(widget)

            # 设置应用程序级别的优化
            self._apply_application_optimizations()

            self.optimization_applied.emit("all")

        except Exception as e:
            logger.error(f"应用优化失败: {e}")

    def _apply_application_optimizations(self):
        """应用应用程序级别的优化"""
        try:
            app = QApplication.instance()
            if not app:
                return

            # 设置高DPI pixmap支持（可在应用创建后设置）
            if self.current_display and self.current_display.display_type != DisplayType.STANDARD:
                app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

                # 设置缩放因子
                if hasattr(app, 'setHighDpiScaleFactorRoundingPolicy'):
                    app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        except Exception as e:
            logger.error(f"应用应用程序优化失败: {e}")

    def _monitor_display_changes(self):
        """监控显示器变化"""
        try:
            # 重新检测显示器
            displays = self.display_detector.detect_displays()

            if displays:
                primary_display = self.display_detector.get_primary_display()

                # 检查是否有变化
                if (not self.current_display or
                    not primary_display or
                    primary_display.screen_name != self.current_display.screen_name or
                        abs(primary_display.device_pixel_ratio - self.current_display.device_pixel_ratio) > 0.1):

                    if primary_display:
                        logger.info("检测到显示器变化，重新优化")
                        self.set_target_display(primary_display)

        except Exception as e:
            logger.error(f"监控显示器变化失败: {e}")

    # 公共接口方法
    def register_widget(self, widget: QWidget):
        """注册需要优化的组件"""
        if widget not in self.managed_widgets:
            self.managed_widgets.append(widget)
            if self.optimization_enabled:
                self.optimize_widget(widget)

    def unregister_widget(self, widget: QWidget):
        """注销组件"""
        if widget in self.managed_widgets:
            self.managed_widgets.remove(widget)

    def optimize_widget(self, widget: QWidget):
        """优化单个组件"""
        try:
            if not self.current_config:
                return

            # 字体缩放
            if self.font_scaler:
                self.font_scaler.apply_to_widget(widget)

            # 触摸优化
            if (self.touch_optimizer and
                self.current_display and
                    self.current_display.touch_capability != TouchCapability.NONE):
                self.touch_optimizer.optimize_widget_for_touch(widget)

            # 图标缩放
            if self.icon_scaler:
                self._scale_widget_icons(widget)

            logger.debug(f"组件优化完成: {widget.__class__.__name__}")

        except Exception as e:
            logger.error(f"优化组件失败: {e}")

    def _scale_widget_icons(self, widget: QWidget):
        """缩放组件图标"""
        try:
            # 优化按钮图标
            if isinstance(widget, QPushButton) and not widget.icon().isNull():
                icon = widget.icon()
                icon_size = widget.iconSize()
                scaled_icon = self.icon_scaler.scale_icon(icon, max(icon_size.width(), 16))
                widget.setIcon(scaled_icon)

                # 调整图标尺寸
                scaled_size = int(max(icon_size.width(), 16) * self.current_config.icon_scale)
                widget.setIconSize(QSize(scaled_size, scaled_size))

            # 递归处理子组件
            for child in widget.findChildren(QWidget):
                self._scale_widget_icons(child)

        except Exception as e:
            logger.error(f"缩放组件图标失败: {e}")

    def enable_optimization(self, enabled: bool = True):
        """启用/禁用优化"""
        self.optimization_enabled = enabled
        if enabled:
            self._apply_optimizations()

    def get_current_display_info(self) -> Optional[DisplayInfo]:
        """获取当前显示器信息"""
        return self.current_display

    def get_current_config(self) -> Optional[DPIConfig]:
        """获取当前配置"""
        return self.current_config

    def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        try:
            stats = {
                'optimization_enabled': self.optimization_enabled,
                'managed_widgets': len(self.managed_widgets),
                'current_display': None,
                'current_config': None
            }

            if self.current_display:
                stats['current_display'] = {
                    'type': self.current_display.display_type.value,
                    'dpi': f"{self.current_display.dpi_x:.1f}x{self.current_display.dpi_y:.1f}",
                    'device_pixel_ratio': self.current_display.device_pixel_ratio,
                    'touch_capability': self.current_display.touch_capability.value,
                    'resolution': f"{self.current_display.width}x{self.current_display.height}"
                }

            if self.current_config:
                stats['current_config'] = {
                    'scale_factor': self.current_config.scale_factor,
                    'font_scale': self.current_config.font_scale,
                    'icon_scale': self.current_config.icon_scale,
                    'spacing_scale': self.current_config.spacing_scale,
                    'touch_target_size': self.current_config.touch_targets.recommended_size
                }

            return stats

        except Exception as e:
            logger.error(f"获取优化统计失败: {e}")
            return {'error': str(e)}

_display_optimization_manager: Optional[DisplayOptimizationManager] = None


def get_display_optimization_manager() -> DisplayOptimizationManager:
    """获取显示优化管理器实例（延迟初始化）"""
    global _display_optimization_manager
    if _display_optimization_manager is None:
        _display_optimization_manager = DisplayOptimizationManager()
    return _display_optimization_manager

def optimize_application_for_display():
    """为当前显示器优化应用程序"""
    manager = get_display_optimization_manager()

    # 获取主窗口并注册
    app = QApplication.instance()
    if app:
        for widget in app.topLevelWidgets():
            manager.register_widget(widget)

def setup_high_dpi_support():
    """设置高DPI支持"""
    try:
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        # 设置缩放策略
        if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
            QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )

        logger.info("高DPI支持已设置")

    except Exception as e:
        logger.error(f"设置高DPI支持失败: {e}")

def apply_touch_optimizations(widget: QWidget):
    """为组件应用触摸优化"""
    manager = get_display_optimization_manager()
    manager.register_widget(widget)

class DisplayOptimizer:
    """显示优化器"""

    def __init__(self):
        self.display_manager = get_display_optimization_manager()
        logger.info("显示优化器已初始化")

    def optimize_widget(self, widget: QWidget) -> bool:
        """优化组件显示"""
        try:
            self.display_manager.register_widget(widget)
            return True
        except Exception as e:
            logger.error(f"组件显示优化失败: {e}")
            return False

    def set_high_dpi_scaling(self, enabled: bool = True):
        """设置高DPI缩放"""
        try:
            if enabled:
                setup_high_dpi_support()
            logger.info(f"高DPI缩放已{'启用' if enabled else '禁用'}")
        except Exception as e:
            logger.error(f"设置高DPI缩放失败: {e}")

class VirtualizationManager:
    """虚拟化管理器"""

    def __init__(self):
        self.virtualized_widgets = {}
        logger.info("虚拟化管理器已初始化")

    def enable_virtualization(self, widget: QWidget, enabled: bool = True):
        """启用/禁用组件虚拟化"""
        try:
            widget_id = id(widget)
            self.virtualized_widgets[widget_id] = enabled

            # 为大型表格和列表启用虚拟化
            if hasattr(widget, 'setModel') and enabled:
                # 表格虚拟化
                if hasattr(widget, 'setVerticalScrollMode'):
                    widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
                    widget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

            logger.info(f"组件虚拟化已{'启用' if enabled else '禁用'}")
            return True
        except Exception as e:
            logger.error(f"设置组件虚拟化失败: {e}")
            return False

    def is_virtualized(self, widget: QWidget) -> bool:
        """检查组件是否启用虚拟化"""
        return self.virtualized_widgets.get(id(widget), False)

class MemoryManager:
    """内存管理器"""

    def __init__(self):
        self.memory_usage = {}
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_memory)
        self.cleanup_timer.start(30000)  # 30秒清理一次
        logger.info("内存管理器已初始化")

    def track_widget(self, widget: QWidget):
        """跟踪组件内存使用"""
        try:
            widget_id = id(widget)
            self.memory_usage[widget_id] = {
                'widget': widget,
                'created_time': datetime.now(),
                'last_accessed': datetime.now()
            }
        except Exception as e:
            logger.error(f"跟踪组件内存失败: {e}")

    def untrack_widget(self, widget: QWidget):
        """停止跟踪组件内存"""
        try:
            widget_id = id(widget)
            if widget_id in self.memory_usage:
                del self.memory_usage[widget_id]
        except Exception as e:
            logger.error(f"停止跟踪组件内存失败: {e}")

    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            return {
                'rss': memory_info.rss,  # 物理内存
                'vms': memory_info.vms,  # 虚拟内存
                'tracked_widgets': len(self.memory_usage),
                'memory_percent': process.memory_percent()
            }
        except Exception as e:
            logger.error(f"获取内存使用情况失败: {e}")
            return {'error': str(e)}

    def _cleanup_memory(self):
        """清理内存"""
        try:
            # 清理过期的组件引用
            current_time = datetime.now()
            expired_widgets = []

            for widget_id, info in self.memory_usage.items():
                if (current_time - info['last_accessed']).seconds > 300:  # 5分钟未访问
                    expired_widgets.append(widget_id)

            for widget_id in expired_widgets:
                del self.memory_usage[widget_id]

            # 强制垃圾回收
            import gc
            gc.collect()

            if expired_widgets:
                logger.info(f"清理了 {len(expired_widgets)} 个过期组件引用")

        except Exception as e:
            logger.error(f"内存清理失败: {e}")

    def force_cleanup(self):
        """强制清理内存"""
        try:
            self._cleanup_memory()
            # 清理像素图缓存
            QPixmapCache.clear()
            logger.info("强制内存清理完成")
        except Exception as e:
            logger.error(f"强制内存清理失败: {e}")
