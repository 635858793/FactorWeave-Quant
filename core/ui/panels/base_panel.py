from loguru import logger
"""
基础面板类

所有UI面板的基类，提供通用的功能和接口。
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod

from PyQt5.QtWidgets import QWidget, QFrame
from PyQt5.QtCore import Qt, QObject, pyqtSlot
from PyQt5.sip import wrappertype

if TYPE_CHECKING:
    from core.coordinators.main_window_coordinator import MainWindowCoordinator


class QObjectMeta(wrappertype, type(ABC)):
    """解决QObject和ABC元类冲突的自定义元类"""
    pass

class BasePanel(QObject, ABC, metaclass=QObjectMeta):
    """
    基础面板类

    提供所有面板的通用功能：
    1. 生命周期管理
    2. 主题支持
    3. 事件处理
    4. 资源管理
    """

    def __init__(self,
                 parent: QWidget,
                 coordinator: 'MainWindowCoordinator',
                 **kwargs):
        """
        初始化基础面板

        Args:
            parent: 父窗口组件
            coordinator: 主窗口协调器
            **kwargs: 其他参数
        """
        super().__init__(parent)

        self.parent = parent
        self.coordinator = coordinator

        # 安全获取event_bus
        self.event_bus = None
        if coordinator and hasattr(coordinator, 'event_bus'):
            self.event_bus = coordinator.event_bus
        elif coordinator is None:
            # 如果没有协调器，创建一个简单的空事件总线
            class NullEventBus:
                def publish(self, event): pass
                def subscribe(self, event_type, handler): pass
                def unsubscribe(self, event_type, handler): pass
            self.event_bus = NullEventBus()

        # 面板状态
        self._initialized = False
        self._disposed = False

        # UI组件
        self._root_frame: Optional[QFrame] = None
        self._widgets: Dict[str, QWidget] = {}

        # 配置
        self._config = kwargs

        # 当前主题
        self._current_theme: Optional[Dict[str, Any]] = None

        # 初始化面板
        self._initialize()

    def _initialize(self) -> None:
        """初始化面板"""
        try:
            # 创建根框架
            self._create_root_frame()

            # 创建UI组件
            self._create_widgets()

            # 绑定事件
            self._bind_events()

            # 初始化数据
            self._initialize_data()

            self._initialized = True
            logger.info(f"{self.__class__.__name__} initialized successfully")

        except Exception as e:
            logger.error(
                f"Failed to initialize {self.__class__.__name__}: {e}")
            raise

    def _create_root_frame(self) -> None:
        """创建根框架"""
        self._root_frame = QFrame(self.parent)
        self._root_frame.setFrameStyle(QFrame.StyledPanel)
        self._widgets['root'] = self._root_frame

    @abstractmethod
    def _create_widgets(self) -> None:
        """创建UI组件（子类实现）"""
        pass

    def _bind_events(self) -> None:
        """绑定事件（子类可重写）"""
        pass

    def _initialize_data(self) -> None:
        """初始化数据（子类可重写）"""
        pass

    def apply_theme(self, theme: Dict[str, Any]) -> None:
        """应用主题"""
        try:
            self._current_theme = theme
            self._apply_theme_to_widgets(theme)
            logger.debug(f"Applied theme to {self.__class__.__name__}")

        except Exception as e:
            logger.error(
                f"Failed to apply theme to {self.__class__.__name__}: {e}")

    def _apply_theme_to_widgets(self, theme: Dict[str, Any]) -> None:
        """应用主题到组件（子类可重写）
        
        支持两种数据结构：
        1. 嵌套结构: {'colors': {'background': '...', 'foreground': '...'}}
        2. 扁平结构: {'background': '...', 'foreground': '...'}
        """
        colors = theme.get('colors', theme)
        
        if not colors or not isinstance(colors, dict):
            colors = theme
        
        fonts = theme.get('fonts', {})

        if self._root_frame:
            bg_color = colors.get('chart_panel_bg', colors.get('background', '#ffffff'))
            fg_color = colors.get('chart_text', colors.get('foreground', '#000000'))

            try:
                self._root_frame.setStyleSheet(f"""
                    QFrame {{
                        background-color: {bg_color};
                        color: {fg_color};
                    }}
                """)
            except Exception as e:
                logger.debug(f"Failed to apply theme styles: {e}")

    def get_widget(self, name: str) -> Optional[QWidget]:
        """获取指定名称的组件"""
        return self._widgets.get(name)

    def add_widget(self, name: str, widget: QWidget) -> None:
        """添加组件到管理列表"""
        self._widgets[name] = widget

    def remove_widget(self, name: str) -> None:
        """从管理列表中移除组件"""
        if name in self._widgets:
            del self._widgets[name]

    def show_message(self, message: str, level: str = 'info') -> None:
        """显示消息（通过协调器）"""
        if self.coordinator:
            self.coordinator.show_message(message, level)

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def is_disposed(self) -> bool:
        """检查是否已释放"""
        return self._disposed

    def dispose(self) -> None:
        """释放资源"""
        if self._disposed:
            return

        try:
            # 释放子类资源
            self._do_dispose()

            # 清理组件
            for widget in self._widgets.values():
                try:
                    if hasattr(widget, 'deleteLater'):
                        widget.deleteLater()
                except:
                    pass

            self._widgets.clear()

            # 清理根框架
            if self._root_frame:
                try:
                    self._root_frame.deleteLater()
                except:
                    pass
                self._root_frame = None

            self._disposed = True
            logger.info(f"{self.__class__.__name__} disposed")

        except Exception as e:
            logger.error(f"Error disposing {self.__class__.__name__}: {e}")

    def _do_dispose(self) -> None:
        """释放子类资源（子类可重写）"""
        pass

    # 事件处理方法（子类可重写）
    def on_stock_selected(self, event) -> None:
        """处理股票选择事件"""
        pass

    def on_chart_update(self, event) -> None:
        """处理图表更新事件"""
        pass

    def on_analysis_complete(self, event) -> None:
        """处理分析完成事件"""
        pass

    def on_data_update(self, event) -> None:
        """处理数据更新事件"""
        pass

    def on_error(self, event) -> None:
        """处理错误事件"""
        pass

    def on_theme_changed(self, event) -> None:
        """处理主题变化事件"""
        if hasattr(event, 'theme'):
            self.apply_theme(event.theme)
