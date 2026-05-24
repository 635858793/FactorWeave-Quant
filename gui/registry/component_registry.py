"""
UI组件注册管理系统
实现UI组件的统一注册和生命周期管理，支持组件的动态加载和卸载
"""

from loguru import logger
import weakref
from typing import Dict, List, Optional, Any, Callable, Type, Set, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
import threading
import gc
import inspect

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.enums import ComponentState, ComponentType

class LoadingStrategy(Enum):
    """加载策略枚举"""
    EAGER = "eager"          # 立即加载
    LAZY = "lazy"            # 延迟加载
    ON_DEMAND = "on_demand"  # 按需加载
    PRELOAD = "preload"      # 预加载

@dataclass
class ComponentDependency:
    """组件依赖数据类"""
    component_id: str
    required: bool = True
    version: Optional[str] = None
    load_order: int = 0  # 加载顺序，数字越小越先加载

@dataclass
class ComponentMetadata:
    """组件元数据数据类"""
    component_id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    component_type: ComponentType = ComponentType.WIDGET
    loading_strategy: LoadingStrategy = LoadingStrategy.LAZY
    dependencies: List[ComponentDependency] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class ComponentRegistration:
    """组件注册信息数据类"""
    metadata: ComponentMetadata
    factory: Callable[..., QWidget]
    instance: Optional[QWidget] = None
    state: ComponentState = ComponentState.REGISTERED
    parent_id: Optional[str] = None
    children_ids: Set[str] = field(default_factory=set)
    load_count: int = 0
    last_loaded: Optional[datetime] = None
    last_unloaded: Optional[datetime] = None
    error_message: Optional[str] = None

class ComponentFactory:
    """组件工厂"""
    
    def __init__(self):
        self.factories: Dict[str, Callable] = {}
        self.templates: Dict[str, Dict[str, Any]] = {}
    
    def register_factory(self, component_id: str, factory: Callable):
        """注册组件工厂"""
        self.factories[component_id] = factory
        logger.debug(f"组件工厂已注册: {component_id}")
    
    def unregister_factory(self, component_id: str):
        """注销组件工厂"""
        if component_id in self.factories:
            del self.factories[component_id]
            logger.debug(f"组件工厂已注销: {component_id}")
    
    def create_component(self, component_id: str, **kwargs) -> Optional[QWidget]:
        """创建组件实例"""
        try:
            if component_id not in self.factories:
                logger.error(f"组件工厂不存在: {component_id}")
                return None
            
            factory = self.factories[component_id]
            
            # 合并模板参数
            template_kwargs = self.templates.get(component_id, {})
            merged_kwargs = {**template_kwargs, **kwargs}
            
            # 创建实例
            instance = factory(**merged_kwargs)
            
            if not isinstance(instance, QWidget):
                logger.error(f"工厂返回的不是QWidget实例: {component_id}")
                return None
            
            logger.debug(f"组件实例已创建: {component_id}")
            return instance
            
        except Exception as e:
            logger.error(f"创建组件实例失败: {component_id}, 错误: {e}")
            return None
    
    def set_template(self, component_id: str, template: Dict[str, Any]):
        """设置组件模板参数"""
        self.templates[component_id] = template
    
    def get_template(self, component_id: str) -> Dict[str, Any]:
        """获取组件模板参数"""
        return self.templates.get(component_id, {})

class DependencyResolver:
    """依赖解析器"""
    
    def __init__(self, registry: 'ComponentRegistry'):
        self.registry = registry
        self.resolution_cache: Dict[str, List[str]] = {}
    
    def resolve_dependencies(self, component_id: str) -> List[str]:
        """解析组件依赖"""
        try:
            # 检查缓存
            if component_id in self.resolution_cache:
                return self.resolution_cache[component_id]
            
            registration = self.registry.get_registration(component_id)
            if not registration:
                return []
            
            dependencies = registration.metadata.dependencies
            resolved_order = []
            visited = set()
            visiting = set()
            
            def visit(comp_id: str):
                if comp_id in visiting:
                    raise ValueError(f"检测到循环依赖: {comp_id}")
                
                if comp_id in visited:
                    return
                
                visiting.add(comp_id)
                
                # 获取当前组件的依赖
                comp_reg = self.registry.get_registration(comp_id)
                if comp_reg:
                    # 按加载顺序排序依赖
                    sorted_deps = sorted(
                        comp_reg.metadata.dependencies,
                        key=lambda d: d.load_order
                    )
                    
                    for dep in sorted_deps:
                        visit(dep.component_id)
                
                visiting.remove(comp_id)
                visited.add(comp_id)
                
                if comp_id not in resolved_order:
                    resolved_order.append(comp_id)
            
            # 解析所有依赖
            for dep in dependencies:
                visit(dep.component_id)
            
            # 最后添加目标组件
            if component_id not in resolved_order:
                resolved_order.append(component_id)
            
            # 缓存结果
            self.resolution_cache[component_id] = resolved_order
            
            return resolved_order
            
        except Exception as e:
            logger.error(f"解析依赖失败: {component_id}, 错误: {e}")
            return [component_id]  # 返回自身
    
    def validate_dependencies(self, component_id: str) -> bool:
        """验证组件依赖"""
        try:
            registration = self.registry.get_registration(component_id)
            if not registration:
                return False
            
            for dep in registration.metadata.dependencies:
                dep_registration = self.registry.get_registration(dep.component_id)
                
                if not dep_registration:
                    if dep.required:
                        logger.error(f"必需依赖不存在: {dep.component_id}")
                        return False
                    else:
                        logger.warning(f"可选依赖不存在: {dep.component_id}")
                        continue
                
                # 检查版本兼容性
                if dep.version and dep_registration.metadata.version != dep.version:
                    logger.warning(f"依赖版本不匹配: {dep.component_id}, 期望: {dep.version}, 实际: {dep_registration.metadata.version}")
            
            return True
            
        except Exception as e:
            logger.error(f"验证依赖失败: {component_id}, 错误: {e}")
            return False
    
    def clear_cache(self):
        """清空缓存"""
        self.resolution_cache.clear()

class ComponentLifecycleManager:
    """组件生命周期管理器"""
    
    def __init__(self, registry: 'ComponentRegistry'):
        self.registry = registry
        self.lifecycle_hooks: Dict[ComponentState, List[Callable]] = {
            state: [] for state in ComponentState
        }
    
    def add_lifecycle_hook(self, state: ComponentState, hook: Callable):
        """添加生命周期钩子"""
        self.lifecycle_hooks[state].append(hook)
    
    def remove_lifecycle_hook(self, state: ComponentState, hook: Callable):
        """移除生命周期钩子"""
        if hook in self.lifecycle_hooks[state]:
            self.lifecycle_hooks[state].remove(hook)
    
    def transition_state(self, component_id: str, new_state: ComponentState) -> bool:
        """转换组件状态"""
        try:
            registration = self.registry.get_registration(component_id)
            if not registration:
                return False
            
            old_state = registration.state
            
            # 验证状态转换
            if not self._is_valid_transition(old_state, new_state):
                logger.warning(f"无效的状态转换: {old_state.value} -> {new_state.value}")
                return False
            
            # 执行状态转换前的钩子
            self._execute_hooks(ComponentState.UNREGISTERED, component_id, registration, old_state, new_state)
            
            # 更新状态
            registration.state = new_state
            
            # 执行状态转换后的钩子
            self._execute_hooks(new_state, component_id, registration, old_state, new_state)
            
            logger.debug(f"组件状态已转换: {component_id}, {old_state.value} -> {new_state.value}")
            return True
            
        except Exception as e:
            logger.error(f"转换组件状态失败: {component_id}, 错误: {e}")
            return False
    
    def _is_valid_transition(self, from_state: ComponentState, to_state: ComponentState) -> bool:
        """验证状态转换是否有效"""
        valid_transitions = {
            ComponentState.UNREGISTERED: [ComponentState.REGISTERED],
            ComponentState.REGISTERED: [ComponentState.INITIALIZING, ComponentState.DESTROYED],
            ComponentState.INITIALIZING: [ComponentState.INITIALIZED, ComponentState.ERROR],
            ComponentState.INITIALIZED: [ComponentState.LOADING, ComponentState.DESTROYED],
            ComponentState.LOADING: [ComponentState.LOADED, ComponentState.ERROR],
            ComponentState.LOADED: [ComponentState.ACTIVE, ComponentState.UNLOADING],
            ComponentState.ACTIVE: [ComponentState.INACTIVE, ComponentState.UNLOADING],
            ComponentState.INACTIVE: [ComponentState.ACTIVE, ComponentState.UNLOADING],
            ComponentState.UNLOADING: [ComponentState.INITIALIZED, ComponentState.DESTROYED],
            ComponentState.ERROR: [ComponentState.INITIALIZED, ComponentState.DESTROYED],
            ComponentState.DESTROYED: []  # 终态
        }
        
        return to_state in valid_transitions.get(from_state, [])
    
    def _execute_hooks(self, state: ComponentState, component_id: str, 
                      registration: ComponentRegistration, old_state: ComponentState, new_state: ComponentState):
        """执行生命周期钩子"""
        try:
            for hook in self.lifecycle_hooks[state]:
                try:
                    hook(component_id, registration, old_state, new_state)
                except Exception as e:
                    logger.error(f"执行生命周期钩子失败: {e}")
        except Exception as e:
            logger.error(f"执行生命周期钩子失败: {e}")

class ComponentLoader:
    """组件加载器"""
    
    def __init__(self, registry: 'ComponentRegistry'):
        self.registry = registry
        self.loading_queue: List[str] = []
        self.loading_lock = threading.Lock()
    
    def load_component(self, component_id: str, **kwargs) -> Optional[QWidget]:
        """加载组件"""
        try:
            registration = self.registry.get_registration(component_id)
            if not registration:
                logger.error(f"组件未注册: {component_id}")
                return None
            
            # 检查是否已加载
            if registration.instance and registration.state == ComponentState.LOADED:
                logger.debug(f"组件已加载: {component_id}")
                return registration.instance
            
            # 转换状态
            if not self.registry.lifecycle_manager.transition_state(component_id, ComponentState.LOADING):
                return None
            
            try:
                # 加载依赖
                dependencies = self.registry.dependency_resolver.resolve_dependencies(component_id)
                for dep_id in dependencies[:-1]:  # 排除自身
                    if not self._ensure_dependency_loaded(dep_id):
                        raise Exception(f"加载依赖失败: {dep_id}")
                
                # 创建组件实例
                instance = self.registry.factory.create_component(component_id, **kwargs)
                if not instance:
                    raise Exception("创建组件实例失败")
                
                # 设置组件属性
                instance.setObjectName(component_id)
                instance.setProperty("component_id", component_id)
                
                # 更新注册信息
                registration.instance = instance
                registration.load_count += 1
                registration.last_loaded = datetime.now()
                
                # 转换状态
                self.registry.lifecycle_manager.transition_state(component_id, ComponentState.LOADED)
                
                logger.info(f"组件加载成功: {component_id}")
                return instance
                
            except Exception as e:
                registration.error_message = str(e)
                self.registry.lifecycle_manager.transition_state(component_id, ComponentState.ERROR)
                raise
                
        except Exception as e:
            logger.error(f"加载组件失败: {component_id}, 错误: {e}")
            return None
    
    def unload_component(self, component_id: str) -> bool:
        """卸载组件"""
        try:
            registration = self.registry.get_registration(component_id)
            if not registration:
                return False
            
            # 检查是否有依赖此组件的其他组件
            dependents = self._find_dependents(component_id)
            if dependents:
                logger.warning(f"组件被其他组件依赖，无法卸载: {component_id}, 依赖者: {dependents}")
                return False
            
            # 转换状态
            if not self.registry.lifecycle_manager.transition_state(component_id, ComponentState.UNLOADING):
                return False
            
            try:
                # 销毁实例
                if registration.instance:
                    registration.instance.deleteLater()
                    registration.instance = None
                
                # 更新注册信息
                registration.last_unloaded = datetime.now()
                
                # 转换状态
                self.registry.lifecycle_manager.transition_state(component_id, ComponentState.INITIALIZED)
                
                logger.info(f"组件卸载成功: {component_id}")
                return True
                
            except Exception as e:
                registration.error_message = str(e)
                self.registry.lifecycle_manager.transition_state(component_id, ComponentState.ERROR)
                raise
                
        except Exception as e:
            logger.error(f"卸载组件失败: {component_id}, 错误: {e}")
            return False
    
    def _ensure_dependency_loaded(self, component_id: str) -> bool:
        """确保依赖已加载"""
        registration = self.registry.get_registration(component_id)
        if not registration:
            return False
        
        if registration.state == ComponentState.LOADED:
            return True
        
        return self.load_component(component_id) is not None
    
    def _find_dependents(self, component_id: str) -> List[str]:
        """查找依赖此组件的其他组件"""
        dependents = []
        
        for reg_id, registration in self.registry.registrations.items():
            if reg_id == component_id:
                continue
            
            for dep in registration.metadata.dependencies:
                if dep.component_id == component_id:
                    dependents.append(reg_id)
                    break
        
        return dependents

class ComponentRegistry(QObject):
    """UI组件注册管理器主类"""
    
    # 信号定义
    component_registered = pyqtSignal(str)  # component_id
    component_unregistered = pyqtSignal(str)  # component_id
    component_loaded = pyqtSignal(str)  # component_id
    component_unloaded = pyqtSignal(str)  # component_id
    component_state_changed = pyqtSignal(str, str)  # component_id, new_state
    
    def __init__(self):
        super().__init__()
        
        # 核心组件
        self.registrations: Dict[str, ComponentRegistration] = {}
        self.factory = ComponentFactory()
        self.dependency_resolver = DependencyResolver(self)
        self.lifecycle_manager = ComponentLifecycleManager(self)
        self.loader = ComponentLoader(self)
        
        # 状态管理
        self.is_initialized = False
        self.lock = threading.RLock()
        
        # 清理定时器
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_destroyed_components)
        self.cleanup_timer.start(30000)  # 30秒清理一次
        
        # 注册生命周期钩子
        self._setup_lifecycle_hooks()
        
        logger.info("UI组件注册管理器已初始化")
    
    def _setup_lifecycle_hooks(self):
        """设置生命周期钩子"""
        
        def on_component_loaded(component_id: str, registration: ComponentRegistration, 
                              old_state: ComponentState, new_state: ComponentState):
            if new_state == ComponentState.LOADED:
                self.component_loaded.emit(component_id)
        
        def on_component_unloaded(component_id: str, registration: ComponentRegistration,
                                old_state: ComponentState, new_state: ComponentState):
            if old_state == ComponentState.LOADED and new_state != ComponentState.LOADED:
                self.component_unloaded.emit(component_id)
        
        def on_state_changed(component_id: str, registration: ComponentRegistration,
                           old_state: ComponentState, new_state: ComponentState):
            self.component_state_changed.emit(component_id, new_state.value)
        
        # 注册钩子
        self.lifecycle_manager.add_lifecycle_hook(ComponentState.LOADED, on_component_loaded)
        self.lifecycle_manager.add_lifecycle_hook(ComponentState.INITIALIZED, on_component_unloaded)
        
        # 为所有状态注册状态变化钩子
        for state in ComponentState:
            self.lifecycle_manager.add_lifecycle_hook(state, on_state_changed)
    
    def register_component(self, metadata: ComponentMetadata, factory: Callable) -> bool:
        """注册组件"""
        try:
            with self.lock:
                component_id = metadata.component_id
                
                if component_id in self.registrations:
                    logger.warning(f"组件已注册，将被覆盖: {component_id}")
                
                # 创建注册信息
                registration = ComponentRegistration(
                    metadata=metadata,
                    factory=factory,
                    state=ComponentState.REGISTERED
                )
                
                # 注册工厂
                self.factory.register_factory(component_id, factory)
                
                # 保存注册信息
                self.registrations[component_id] = registration
                
                # 转换状态
                self.lifecycle_manager.transition_state(component_id, ComponentState.INITIALIZED)
                
                # 清空依赖缓存
                self.dependency_resolver.clear_cache()
                
                # 发送信号
                self.component_registered.emit(component_id)
                
                logger.info(f"组件已注册: {component_id}")
                return True
                
        except Exception as e:
            logger.error(f"注册组件失败: {metadata.component_id}, 错误: {e}")
            return False
    
    def unregister_component(self, component_id: str) -> bool:
        """注销组件"""
        try:
            with self.lock:
                if component_id not in self.registrations:
                    logger.warning(f"组件未注册: {component_id}")
                    return False
                
                registration = self.registrations[component_id]
                
                # 卸载组件
                if registration.state in [ComponentState.LOADED, ComponentState.ACTIVE, ComponentState.INACTIVE]:
                    self.loader.unload_component(component_id)
                
                # 转换状态
                self.lifecycle_manager.transition_state(component_id, ComponentState.DESTROYED)
                
                # 注销工厂
                self.factory.unregister_factory(component_id)
                
                # 移除注册信息
                del self.registrations[component_id]
                
                # 清空依赖缓存
                self.dependency_resolver.clear_cache()
                
                # 发送信号
                self.component_unregistered.emit(component_id)
                
                logger.info(f"组件已注销: {component_id}")
                return True
                
        except Exception as e:
            logger.error(f"注销组件失败: {component_id}, 错误: {e}")
            return False
    
    def load_component(self, component_id: str, **kwargs) -> Optional[QWidget]:
        """加载组件"""
        return self.loader.load_component(component_id, **kwargs)
    
    def unload_component(self, component_id: str) -> bool:
        """卸载组件"""
        return self.loader.unload_component(component_id)
    
    def get_component(self, component_id: str) -> Optional[QWidget]:
        """获取组件实例"""
        registration = self.get_registration(component_id)
        return registration.instance if registration else None
    
    def get_registration(self, component_id: str) -> Optional[ComponentRegistration]:
        """获取组件注册信息"""
        return self.registrations.get(component_id)
    
    def get_all_registrations(self) -> Dict[str, ComponentRegistration]:
        """获取所有注册信息"""
        with self.lock:
            return self.registrations.copy()
    
    def get_components_by_type(self, component_type: ComponentType) -> List[str]:
        """按类型获取组件"""
        with self.lock:
            return [
                comp_id for comp_id, reg in self.registrations.items()
                if reg.metadata.component_type == component_type
            ]
    
    def get_components_by_state(self, state: ComponentState) -> List[str]:
        """按状态获取组件"""
        with self.lock:
            return [
                comp_id for comp_id, reg in self.registrations.items()
                if reg.state == state
            ]
    
    def get_loaded_components(self) -> List[str]:
        """获取已加载的组件"""
        return self.get_components_by_state(ComponentState.LOADED)
    
    def validate_component_dependencies(self, component_id: str) -> bool:
        """验证组件依赖"""
        return self.dependency_resolver.validate_dependencies(component_id)
    
    def _cleanup_destroyed_components(self):
        """清理已销毁的组件"""
        try:
            destroyed_components = []
            
            with self.lock:
                for comp_id, registration in list(self.registrations.items()):
                    if registration.state == ComponentState.DESTROYED:
                        destroyed_components.append(comp_id)
            
            for comp_id in destroyed_components:
                if comp_id in self.registrations:
                    del self.registrations[comp_id]
                    logger.debug(f"已清理销毁的组件: {comp_id}")
            
            # 强制垃圾回收
            if destroyed_components:
                gc.collect()
                
        except Exception as e:
            logger.error(f"清理销毁组件失败: {e}")
    
    def get_registry_statistics(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        try:
            with self.lock:
                total_components = len(self.registrations)
                
                # 按状态统计
                state_counts = {}
                for state in ComponentState:
                    state_counts[state.value] = len(self.get_components_by_state(state))
                
                # 按类型统计
                type_counts = {}
                for comp_type in ComponentType:
                    type_counts[comp_type.value] = len(self.get_components_by_type(comp_type))
                
                # 内存使用统计
                loaded_components = self.get_loaded_components()
                memory_usage = 0
                for comp_id in loaded_components:
                    registration = self.registrations[comp_id]
                    if registration.instance:
                        # 简单估算内存使用
                        memory_usage += sys.getsizeof(registration.instance)
                
                return {
                    'total_components': total_components,
                    'loaded_components': len(loaded_components),
                    'state_distribution': state_counts,
                    'type_distribution': type_counts,
                    'estimated_memory_usage': memory_usage,
                    'dependency_cache_size': len(self.dependency_resolver.resolution_cache),
                    'factory_count': len(self.factory.factories),
                    'is_initialized': self.is_initialized
                }
                
        except Exception as e:
            logger.error(f"获取注册表统计失败: {e}")
            return {'error': str(e)}

# 全局实例
component_registry = ComponentRegistry()

def get_component_registry() -> ComponentRegistry:
    """获取组件注册表实例"""
    return component_registry

def register_component(component_id: str, name: str, factory: Callable, **metadata_kwargs) -> bool:
    """注册组件的便捷函数"""
    metadata = ComponentMetadata(
        component_id=component_id,
        name=name,
        **metadata_kwargs
    )
    return get_component_registry().register_component(metadata, factory)

def load_component(component_id: str, **kwargs) -> Optional[QWidget]:
    """加载组件的便捷函数"""
    return get_component_registry().load_component(component_id, **kwargs)

def get_component(component_id: str) -> Optional[QWidget]:
    """获取组件的便捷函数"""
    return get_component_registry().get_component(component_id)
