"""
现代UI协调器
建立统一的UI组件管理和协调系统，整合Enhanced和Modern两套UI风格
"""

from loguru import logger
from typing import Dict, List, Optional, Any, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                           QSplitter, QFrame, QLabel, QProgressBar, QGroupBox)
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
from PyQt5.QtGui import QFont, QPalette, QColor
import threading

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.enums import ComponentState, ComponentType

class UIStyle(Enum):
    """UI风格枚举"""
    ENHANCED = "enhanced"
    MODERN = "modern"
    UNIFIED = "unified"

@dataclass
class ComponentInfo:
    """组件信息数据类"""
    component_id: str
    component_type: ComponentType
    ui_style: UIStyle
    widget: Optional[QWidget] = None
    state: ComponentState = ComponentState.INACTIVE
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class StyleConfig:
    """样式配置数据类"""
    primary_color: str = "#2196F3"
    secondary_color: str = "#FFC107"
    success_color: str = "#4CAF50"
    warning_color: str = "#FF9800"
    error_color: str = "#F44336"
    background_color: str = "#FAFAFA"
    surface_color: str = "#FFFFFF"
    text_primary: str = "#212121"
    text_secondary: str = "#757575"
    border_color: str = "#E0E0E0"
    
    # 字体配置
    font_family: str = "Microsoft YaHei UI"
    font_size_small: int = 10
    font_size_normal: int = 12
    font_size_large: int = 14
    font_size_title: int = 16
    
    # 间距配置
    spacing_small: int = 4
    spacing_normal: int = 8
    spacing_large: int = 16
    spacing_xlarge: int = 24
    
    # 圆角配置
    border_radius_small: int = 4
    border_radius_normal: int = 8
    border_radius_large: int = 12

class ComponentRegistry:
    """组件注册表"""
    
    def __init__(self):
        self.components: Dict[str, ComponentInfo] = {}
        self.component_factories: Dict[str, Callable] = {}
        self.style_configs: Dict[UIStyle, StyleConfig] = {
            UIStyle.ENHANCED: StyleConfig(),
            UIStyle.MODERN: StyleConfig(
                primary_color="#1976D2",
                secondary_color="#FF5722",
                background_color="#F5F5F5"
            ),
            UIStyle.UNIFIED: StyleConfig(
                primary_color="#3F51B5",
                secondary_color="#E91E63",
                background_color="#FFFFFF"
            )
        }
        self.lock = threading.Lock()
    
    def register_component(self, component_info: ComponentInfo) -> bool:
        """注册组件"""
        try:
            with self.lock:
                if component_info.component_id in self.components:
                    logger.warning(f"组件 {component_info.component_id} 已存在，将被覆盖")
                
                self.components[component_info.component_id] = component_info
                logger.debug(f"组件已注册: {component_info.component_id}")
                return True
                
        except Exception as e:
            logger.error(f"注册组件失败: {e}")
            return False
    
    def unregister_component(self, component_id: str) -> bool:
        """注销组件"""
        try:
            with self.lock:
                if component_id in self.components:
                    del self.components[component_id]
                    logger.debug(f"组件已注销: {component_id}")
                    return True
                else:
                    logger.warning(f"组件 {component_id} 不存在")
                    return False
                    
        except Exception as e:
            logger.error(f"注销组件失败: {e}")
            return False
    
    def get_component(self, component_id: str) -> Optional[ComponentInfo]:
        """获取组件信息"""
        with self.lock:
            return self.components.get(component_id)
    
    def get_components_by_type(self, component_type: ComponentType) -> List[ComponentInfo]:
        """按类型获取组件"""
        with self.lock:
            return [comp for comp in self.components.values() if comp.component_type == component_type]
    
    def get_components_by_style(self, ui_style: UIStyle) -> List[ComponentInfo]:
        """按风格获取组件"""
        with self.lock:
            return [comp for comp in self.components.values() if comp.ui_style == ui_style]
    
    def register_factory(self, component_type: str, factory: Callable):
        """注册组件工厂"""
        self.component_factories[component_type] = factory
    
    def create_component(self, component_type: str, **kwargs) -> Optional[QWidget]:
        """使用工厂创建组件"""
        try:
            if component_type in self.component_factories:
                return self.component_factories[component_type](**kwargs)
            else:
                logger.warning(f"未找到组件工厂: {component_type}")
                return None
                
        except Exception as e:
            logger.error(f"创建组件失败: {e}")
            return None

class StyleManager:
    """样式管理器"""
    
    def __init__(self, registry: ComponentRegistry):
        self.registry = registry
        self.current_style = UIStyle.UNIFIED
        self.style_sheets: Dict[UIStyle, str] = {}
        self._generate_style_sheets()
    
    def _generate_style_sheets(self):
        """生成样式表"""
        for style, config in self.registry.style_configs.items():
            self.style_sheets[style] = self._create_style_sheet(config)
    
    def _create_style_sheet(self, config: StyleConfig) -> str:
        """创建样式表"""
        return f"""
        /* 基础样式 */
        QWidget {{
            font-family: {config.font_family};
            font-size: {config.font_size_normal}px;
            color: {config.text_primary};
            background-color: {config.background_color};
        }}
        
        /* 按钮样式 */
        QPushButton {{
            background-color: {config.primary_color};
            color: white;
            border: none;
            border-radius: {config.border_radius_normal}px;
            padding: {config.spacing_normal}px {config.spacing_large}px;
            font-weight: bold;
        }}
        
        QPushButton:hover {{
            background-color: {self._darken_color(config.primary_color, 0.1)};
        }}
        
        QPushButton:pressed {{
            background-color: {self._darken_color(config.primary_color, 0.2)};
        }}
        
        QPushButton:disabled {{
            background-color: {config.border_color};
            color: {config.text_secondary};
        }}
        
        /* 输入框样式 */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            border: 1px solid {config.border_color};
            border-radius: {config.border_radius_small}px;
            padding: {config.spacing_normal}px;
            background-color: {config.surface_color};
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {config.primary_color};
        }}
        
        /* 标签页样式 */
        QTabWidget::pane {{
            border: 1px solid {config.border_color};
            background-color: {config.surface_color};
        }}
        
        QTabBar::tab {{
            background-color: {config.background_color};
            border: 1px solid {config.border_color};
            padding: {config.spacing_normal}px {config.spacing_large}px;
            margin-right: 2px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {config.primary_color};
            color: white;
        }}
        
        QTabBar::tab:hover {{
            background-color: {self._lighten_color(config.primary_color, 0.8)};
        }}
        
        /* 进度条样式 */
        QProgressBar {{
            border: 1px solid {config.border_color};
            border-radius: {config.border_radius_small}px;
            text-align: center;
            background-color: {config.background_color};
        }}
        
        QProgressBar::chunk {{
            background-color: {config.primary_color};
            border-radius: {config.border_radius_small}px;
        }}
        
        /* 分组框样式 */
        QGroupBox {{
            font-weight: bold;
            border: 2px solid {config.border_color};
            border-radius: {config.border_radius_normal}px;
            margin-top: {config.spacing_normal}px;
            padding-top: {config.spacing_normal}px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {config.spacing_large}px;
            padding: 0 {config.spacing_normal}px 0 {config.spacing_normal}px;
        }}
        
        /* 表格样式 */
        QTableWidget {{
            gridline-color: {config.border_color};
            background-color: {config.surface_color};
            alternate-background-color: {config.background_color};
        }}
        
        QHeaderView::section {{
            background-color: {config.primary_color};
            color: white;
            padding: {config.spacing_normal}px;
            border: none;
        }}
        
        /* 滚动条样式 */
        QScrollBar:vertical {{
            background-color: {config.background_color};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {config.border_color};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {config.text_secondary};
        }}
        """
    
    def _darken_color(self, color: str, factor: float) -> str:
        """加深颜色"""
        # 简化实现，实际应该解析颜色并调整亮度
        return color
    
    def _lighten_color(self, color: str, factor: float) -> str:
        """减淡颜色"""
        # 简化实现，实际应该解析颜色并调整亮度
        return color
    
    def apply_style(self, widget: QWidget, style: UIStyle = None):
        """应用样式"""
        try:
            target_style = style or self.current_style
            
            if target_style in self.style_sheets:
                widget.setStyleSheet(self.style_sheets[target_style])
                logger.debug(f"样式已应用: {target_style.value}")
            else:
                logger.warning(f"未找到样式: {target_style.value}")
                
        except Exception as e:
            logger.error(f"应用样式失败: {e}")
    
    def set_global_style(self, style: UIStyle):
        """设置全局样式"""
        try:
            self.current_style = style
            
            # 应用到所有已注册的组件
            for component_info in self.registry.components.values():
                if component_info.widget:
                    self.apply_style(component_info.widget, style)
            
            logger.info(f"全局样式已设置: {style.value}")
            
        except Exception as e:
            logger.error(f"设置全局样式失败: {e}")

class ComponentLifecycleManager:
    """组件生命周期管理器"""
    
    def __init__(self, registry: ComponentRegistry):
        self.registry = registry
        self.lifecycle_callbacks: Dict[str, List[Callable]] = {
            'created': [],
            'activated': [],
            'deactivated': [],
            'destroyed': []
        }
    
    def add_lifecycle_callback(self, event: str, callback: Callable):
        """添加生命周期回调"""
        if event in self.lifecycle_callbacks:
            self.lifecycle_callbacks[event].append(callback)
    
    def create_component(self, component_id: str, component_type: ComponentType, 
                        ui_style: UIStyle, widget: QWidget = None) -> ComponentInfo:
        """创建组件"""
        try:
            component_info = ComponentInfo(
                component_id=component_id,
                component_type=component_type,
                ui_style=ui_style,
                widget=widget,
                state=ComponentState.INACTIVE
            )
            
            # 注册组件
            if self.registry.register_component(component_info):
                # 触发创建回调
                for callback in self.lifecycle_callbacks['created']:
                    try:
                        callback(component_info)
                    except Exception as e:
                        logger.error(f"创建回调执行失败: {e}")
                
                logger.info(f"组件已创建: {component_id}")
                return component_info
            else:
                raise Exception("组件注册失败")
                
        except Exception as e:
            logger.error(f"创建组件失败: {e}")
            raise
    
    def activate_component(self, component_id: str) -> bool:
        """激活组件"""
        try:
            component_info = self.registry.get_component(component_id)
            if not component_info:
                logger.warning(f"组件不存在: {component_id}")
                return False
            
            component_info.state = ComponentState.ACTIVE
            component_info.last_updated = datetime.now()
            
            # 显示组件
            if component_info.widget:
                component_info.widget.show()
            
            # 触发激活回调
            for callback in self.lifecycle_callbacks['activated']:
                try:
                    callback(component_info)
                except Exception as e:
                    logger.error(f"激活回调执行失败: {e}")
            
            logger.debug(f"组件已激活: {component_id}")
            return True
            
        except Exception as e:
            logger.error(f"激活组件失败: {e}")
            return False
    
    def deactivate_component(self, component_id: str) -> bool:
        """停用组件"""
        try:
            component_info = self.registry.get_component(component_id)
            if not component_info:
                logger.warning(f"组件不存在: {component_id}")
                return False
            
            component_info.state = ComponentState.INACTIVE
            component_info.last_updated = datetime.now()
            
            # 隐藏组件
            if component_info.widget:
                component_info.widget.hide()
            
            # 触发停用回调
            for callback in self.lifecycle_callbacks['deactivated']:
                try:
                    callback(component_info)
                except Exception as e:
                    logger.error(f"停用回调执行失败: {e}")
            
            logger.debug(f"组件已停用: {component_id}")
            return True
            
        except Exception as e:
            logger.error(f"停用组件失败: {e}")
            return False
    
    def destroy_component(self, component_id: str) -> bool:
        """销毁组件"""
        try:
            component_info = self.registry.get_component(component_id)
            if not component_info:
                logger.warning(f"组件不存在: {component_id}")
                return False
            
            # 触发销毁回调
            for callback in self.lifecycle_callbacks['destroyed']:
                try:
                    callback(component_info)
                except Exception as e:
                    logger.error(f"销毁回调执行失败: {e}")
            
            # 销毁widget
            if component_info.widget:
                component_info.widget.deleteLater()
            
            # 注销组件
            self.registry.unregister_component(component_id)
            
            logger.info(f"组件已销毁: {component_id}")
            return True
            
        except Exception as e:
            logger.error(f"销毁组件失败: {e}")
            return False

class ModernUICoordinator(QObject):
    """现代UI协调器主类"""
    
    # 信号定义
    component_created = pyqtSignal(str)  # component_id
    component_activated = pyqtSignal(str)
    component_deactivated = pyqtSignal(str)
    component_destroyed = pyqtSignal(str)
    style_changed = pyqtSignal(str)  # style_name
    
    def __init__(self):
        super().__init__()
        
        # 核心组件
        self.registry = ComponentRegistry()
        self.style_manager = StyleManager(self.registry)
        self.lifecycle_manager = ComponentLifecycleManager(self.registry)
        
        # 状态管理
        self.is_initialized = False
        self.active_components: Dict[str, ComponentInfo] = {}
        
        # 定时器用于状态更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_component_states)
        self.update_timer.start(5000)  # 5秒更新一次
        
        # 注册生命周期回调
        self._setup_lifecycle_callbacks()
        
        # 注册默认组件工厂
        self._register_default_factories()
        
        logger.info("现代UI协调器已初始化")
    
    def initialize(self) -> bool:
        """初始化协调器"""
        try:
            if self.is_initialized:
                return True
            
            # 设置默认样式
            self.style_manager.set_global_style(UIStyle.UNIFIED)
            
            # 发现并注册现有组件
            self._discover_existing_components()
            
            self.is_initialized = True
            logger.info("UI协调器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化UI协调器失败: {e}")
            return False
    
    def _setup_lifecycle_callbacks(self):
        """设置生命周期回调"""
        
        def on_component_created(component_info: ComponentInfo):
            self.component_created.emit(component_info.component_id)
        
        def on_component_activated(component_info: ComponentInfo):
            self.active_components[component_info.component_id] = component_info
            self.component_activated.emit(component_info.component_id)
        
        def on_component_deactivated(component_info: ComponentInfo):
            self.active_components.pop(component_info.component_id, None)
            self.component_deactivated.emit(component_info.component_id)
        
        def on_component_destroyed(component_info: ComponentInfo):
            self.active_components.pop(component_info.component_id, None)
            self.component_destroyed.emit(component_info.component_id)
        
        # 注册回调
        self.lifecycle_manager.add_lifecycle_callback('created', on_component_created)
        self.lifecycle_manager.add_lifecycle_callback('activated', on_component_activated)
        self.lifecycle_manager.add_lifecycle_callback('deactivated', on_component_deactivated)
        self.lifecycle_manager.add_lifecycle_callback('destroyed', on_component_destroyed)
    
    def _register_default_factories(self):
        """注册默认组件工厂"""
        
        def create_tab_widget(**kwargs):
            tab_widget = QTabWidget()
            tab_widget.setTabsClosable(kwargs.get('closable', False))
            tab_widget.setMovable(kwargs.get('movable', True))
            return tab_widget
        
        def create_group_box(**kwargs):
            group_box = QGroupBox(kwargs.get('title', ''))
            layout = QVBoxLayout(group_box)
            return group_box
        
        def create_progress_bar(**kwargs):
            progress_bar = QProgressBar()
            progress_bar.setMinimum(kwargs.get('minimum', 0))
            progress_bar.setMaximum(kwargs.get('maximum', 100))
            progress_bar.setValue(kwargs.get('value', 0))
            return progress_bar
        
        # 注册工厂
        self.registry.register_factory('tab_widget', create_tab_widget)
        self.registry.register_factory('group_box', create_group_box)
        self.registry.register_factory('progress_bar', create_progress_bar)
    
    def _discover_existing_components(self):
        """发现并注册现有组件"""
        try:
            # 这里可以扫描现有的UI组件并自动注册
            # 例如：扫描gui/widgets/enhanced_*和gui/widgets/performance/tabs/modern_*
            pass
            
        except Exception as e:
            logger.error(f"发现现有组件失败: {e}")
    
    def _update_component_states(self):
        """更新组件状态"""
        try:
            current_time = datetime.now()
            
            for component_info in self.registry.components.values():
                # 检查组件是否仍然有效
                if component_info.widget and not component_info.widget.isVisible():
                    if component_info.state == ComponentState.ACTIVE:
                        component_info.state = ComponentState.INACTIVE
                        component_info.last_updated = current_time
                
        except Exception as e:
            logger.error(f"更新组件状态失败: {e}")
    
    # 公共接口方法
    def register_component(self, component_id: str, component_type: ComponentType, 
                          ui_style: UIStyle, widget: QWidget = None) -> bool:
        """注册组件"""
        try:
            component_info = self.lifecycle_manager.create_component(
                component_id, component_type, ui_style, widget
            )
            
            # 应用样式
            if widget:
                self.style_manager.apply_style(widget, ui_style)
            
            return True
            
        except Exception as e:
            logger.error(f"注册组件失败: {e}")
            return False
    
    def unregister_component(self, component_id: str) -> bool:
        """注销组件"""
        return self.lifecycle_manager.destroy_component(component_id)
    
    def activate_component(self, component_id: str) -> bool:
        """激活组件"""
        return self.lifecycle_manager.activate_component(component_id)
    
    def deactivate_component(self, component_id: str) -> bool:
        """停用组件"""
        return self.lifecycle_manager.deactivate_component(component_id)
    
    def set_ui_style(self, style: UIStyle):
        """设置UI风格"""
        self.style_manager.set_global_style(style)
        self.style_changed.emit(style.value)
    
    def create_component(self, component_type: str, **kwargs) -> Optional[QWidget]:
        """创建组件"""
        return self.registry.create_component(component_type, **kwargs)
    
    def get_component_info(self, component_id: str) -> Optional[ComponentInfo]:
        """获取组件信息"""
        return self.registry.get_component(component_id)
    
    def get_active_components(self) -> Dict[str, ComponentInfo]:
        """获取活跃组件"""
        return self.active_components.copy()
    
    def get_components_by_type(self, component_type: ComponentType) -> List[ComponentInfo]:
        """按类型获取组件"""
        return self.registry.get_components_by_type(component_type)
    
    def get_components_by_style(self, ui_style: UIStyle) -> List[ComponentInfo]:
        """按风格获取组件"""
        return self.registry.get_components_by_style(ui_style)
    
    def get_coordinator_status(self) -> Dict[str, Any]:
        """获取协调器状态"""
        try:
            return {
                'initialized': self.is_initialized,
                'current_style': self.style_manager.current_style.value,
                'total_components': len(self.registry.components),
                'active_components': len(self.active_components),
                'component_types': {
                    comp_type.value: len(self.get_components_by_type(comp_type))
                    for comp_type in ComponentType
                },
                'ui_styles': {
                    ui_style.value: len(self.get_components_by_style(ui_style))
                    for ui_style in UIStyle
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取协调器状态失败: {e}")
            return {'error': str(e)}

# 全局实例
modern_ui_coordinator = ModernUICoordinator()

def get_modern_ui_coordinator() -> ModernUICoordinator:
    """获取现代UI协调器实例"""
    return modern_ui_coordinator
