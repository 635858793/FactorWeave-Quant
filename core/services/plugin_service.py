"""
统一插件服务 - 架构精简重构版本

整合所有插件管理器功能，提供统一的插件管理接口。
整合PluginManager、PluginCenter、AsyncPluginDiscovery等。
完全重构以符合15个核心服务的架构精简目标。
"""

import asyncio
import threading
import time
import os
import sys
import json
import importlib
import importlib.util
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
from collections import defaultdict

from loguru import logger

from .base_service import BaseService
from ..events import EventBus, get_event_bus
from ..containers import ServiceContainer, get_service_container
from ..plugin_types import PluginType, AssetType, DataType
from ..data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from ..enums import PluginLifecycle
from .metrics_base import add_dict_interface


class PluginLifecycleStage(Enum):
    """插件生命周期阶段"""
    DISCOVER = "discover"
    VALIDATE = "validate"
    LOAD = "load"
    INITIALIZE = "initialize"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    REMOVE = "remove"


class PluginPriority(Enum):
    """插件优先级"""
    CRITICAL = 0    # 关键插件
    HIGH = 1        # 高优先级
    NORMAL = 2      # 普通优先级
    LOW = 3         # 低优先级
    OPTIONAL = 4    # 可选插件


@dataclass
class PluginDependency:
    """插件依赖"""
    name: str
    version_requirement: Optional[str] = None
    optional: bool = False


@dataclass
class PluginMetadata:
    """插件元数据"""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    state: PluginLifecycle
    priority: PluginPriority = PluginPriority.NORMAL

    # 时间信息
    discovery_time: datetime = field(default_factory=datetime.now)
    load_time: Optional[datetime] = None
    initialization_time: Optional[datetime] = None
    activation_time: Optional[datetime] = None

    # 依赖和兼容性
    dependencies: List[PluginDependency] = field(default_factory=list)
    supported_assets: List[AssetType] = field(default_factory=list)
    supported_data_types: List[DataType] = field(default_factory=list)
    min_version: Optional[str] = None
    max_version: Optional[str] = None

    # 运行时信息
    plugin_instance: Optional[Any] = None
    plugin_class: Optional[Type] = None
    plugin_module: Optional[Any] = None
    plugin_path: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)

    # 健康状态
    health_status: Optional[HealthCheckResult] = None
    last_health_check: Optional[datetime] = None
    error_message: Optional[str] = None
    error_count: int = 0

    # 统计信息
    usage_count: int = 0
    last_used: Optional[datetime] = None


@dataclass
class PluginEvent:
    """插件事件"""
    plugin_id: str
    event_type: str
    stage: PluginLifecycleStage
    timestamp: datetime
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time: float = 0.0


@add_dict_interface
@dataclass
class PluginMetrics:
    """插件服务指标"""
    # 基础指标字段（与BaseService一致）
    initialization_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    operation_count: int = 0

    # 插件服务特定字段
    total_plugins: int = 0
    discovered_plugins: int = 0
    loaded_plugins: int = 0
    active_plugins: int = 0
    failed_plugins: int = 0
    discovery_time: float = 0.0
    load_time: float = 0.0
    last_discovery: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.now)


class PluginService(BaseService):
    """
    统一插件服务 - 架构精简重构版本

    整合所有插件管理器功能：
    - PluginManager: 插件生命周期管理
    - PluginCenter: 插件中心和市场功能
    - AsyncPluginDiscovery: 异步插件发现
    - PluginConfigManager: 插件配置管理
    - 其他插件相关管理器

    提供统一的插件管理接口，支持：
    1. 插件自动发现和注册
    2. 插件生命周期管理（加载、初始化、激活、停用、卸载）
    3. 插件依赖关系解析和管理
    4. 插件健康监控和错误恢复
    5. 插件配置管理和持久化
    6. 插件性能监控和优化
    7. 插件市场和更新管理
    8. 异步插件操作支持
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """
        初始化插件服务

        Args:
            service_container: 服务容器
        """
        super().__init__()
        self.service_name = "PluginService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 插件存储
        self._plugins: Dict[str, PluginMetadata] = {}
        self._plugin_instances: Dict[str, Any] = {}
        self._plugin_modules: Dict[str, Any] = {}
        self._plugin_classes: Dict[str, Type] = {}

        # 插件分类索引
        self._plugins_by_type: Dict[PluginType, List[str]] = defaultdict(list)
        self._plugins_by_state: Dict[PluginLifecycle, List[str]] = defaultdict(list)
        self._plugins_by_priority: Dict[PluginPriority, List[str]] = defaultdict(list)

        # 依赖管理
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_dependency_graph: Dict[str, Set[str]] = defaultdict(set)

        # 事件和指标
        self._event_history: List[PluginEvent] = []
        self._metrics = PluginMetrics()

        # 配置参数
        self._config = {
            "plugin_directories": ["plugins", "extensions"],
            "auto_discovery": True,
            "auto_activate": True,
            "max_load_time": 30.0,
            "max_init_time": 15.0,
            "health_check_interval": 300,  # 5分钟
            "retry_failed_plugins": True,
            "max_retry_count": 3,
            "dependency_timeout": 60.0,
            "enable_hot_reload": False,
            "enable_plugin_isolation": True,
            "config_persistence": True
        }

        # 插件搜索路径
        self._search_paths: List[Path] = []
        self._excluded_paths: Set[Path] = set()

        # 线程和锁
        self._plugin_lock = threading.RLock()
        self._discovery_lock = threading.Lock()
        self._load_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="PluginLoader")  # v2.4: 从5增加到10

        # 监控和统计
        self._start_time = datetime.now()
        self._last_discovery = None
        self._last_health_check = None

        logger.info("PluginService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing PluginService core components...")

            # 1. 设置插件搜索路径
            self._setup_search_paths()

            # 2. 加载插件配置
            self._load_plugin_configs()

            # 3. 发现插件
            self._discover_plugins()

            # 4. 解析依赖关系
            self._resolve_dependencies()

            # 5. 加载插件
            self._load_plugins()

            # 6. 初始化插件
            self._initialize_plugins()

            # 7. 激活插件
            if self._config["auto_activate"]:
                self._activate_plugins()

            # 8. 启动后台任务
            self._start_background_tasks()

            # 9. 验证插件功能
            self._validate_plugin_functionality()

            logger.info("✅ PluginService initialized successfully with comprehensive plugin management")

        except Exception as e:
            logger.error(f"❌ Failed to initialize PluginService: {e}")
            raise

    def _setup_search_paths(self) -> None:
        """设置插件搜索路径"""
        try:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent

            # 添加配置的插件目录
            for plugin_dir in self._config["plugin_directories"]:
                plugin_path = project_root / plugin_dir
                if plugin_path.exists():
                    self._search_paths.append(plugin_path)
                    logger.info(f"✓ Added plugin search path: {plugin_path}")
                else:
                    logger.warning(f"Plugin directory not found: {plugin_path}")

            # 添加到Python路径
            for path in self._search_paths:
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))

        except Exception as e:
            logger.error(f"Failed to setup search paths: {e}")
            raise

    def _load_plugin_configs(self) -> None:
        """加载插件配置"""
        try:
            # 加载全局插件配置
            config_files = ["plugin_config.json", "plugins.json"]

            for search_path in self._search_paths:
                for config_file in config_files:
                    config_path = search_path / config_file
                    if config_path.exists():
                        try:
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config_data = json.load(f)
                                self._config.update(config_data.get('global', {}))
                                logger.info(f"✓ Loaded plugin config from {config_path}")
                        except Exception as e:
                            logger.warning(f"Failed to load config from {config_path}: {e}")

        except Exception as e:
            logger.error(f"Failed to load plugin configs: {e}")

    def _discover_plugins(self) -> None:
        """发现插件"""
        start_time = time.time()

        try:
            with self._discovery_lock:
                discovered_count = 0

                for search_path in self._search_paths:
                    discovered_count += self._discover_plugins_in_path(search_path)

                # 更新指标
                self._metrics.discovered_plugins = discovered_count
                self._metrics.discovery_time = time.time() - start_time
                self._metrics.last_discovery = datetime.now()
                self._last_discovery = datetime.now()

                logger.info(f"✓ Plugin discovery completed: {discovered_count} plugins found in {self._metrics.discovery_time:.2f}s")

        except Exception as e:
            logger.error(f"Plugin discovery failed: {e}")
            raise

    def _discover_plugins_in_path(self, search_path: Path) -> int:
        """在指定路径中发现插件"""
        discovered_count = 0

        try:
            for item in search_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    # 检查是否是插件目录
                    if self._is_plugin_directory(item):
                        plugin_metadata = self._create_plugin_metadata(item)
                        if plugin_metadata:
                            self._register_plugin(plugin_metadata)
                            discovered_count += 1

        except Exception as e:
            logger.error(f"Error discovering plugins in {search_path}: {e}")

        return discovered_count

    def _is_plugin_directory(self, path: Path) -> bool:
        """检查是否是插件目录"""
        # 检查必需文件
        required_files = ["__init__.py"]
        plugin_files = ["plugin.py", "main.py"]

        has_required = all((path / file).exists() for file in required_files)
        has_plugin_file = any((path / file).exists() for file in plugin_files)

        # 检查插件元数据文件
        metadata_files = ["plugin.json", "metadata.json", "info.json"]
        has_metadata = any((path / file).exists() for file in metadata_files)

        return has_required and (has_plugin_file or has_metadata)

    def _create_plugin_metadata(self, plugin_path: Path) -> Optional[PluginMetadata]:
        """创建插件元数据"""
        try:
            plugin_id = plugin_path.name

            # 加载插件信息
            plugin_info = self._load_plugin_info(plugin_path)

            # 创建元数据
            metadata = PluginMetadata(
                plugin_id=plugin_id,
                name=plugin_info.get('name', plugin_id),
                version=plugin_info.get('version', '1.0.0'),
                description=plugin_info.get('description', ''),
                author=plugin_info.get('author', 'Unknown'),
                plugin_type=self._parse_plugin_type(plugin_info.get('type', 'UNKNOWN')),
                state=PluginLifecycle.DISCOVERED,
                priority=self._parse_priority(plugin_info.get('priority', 'NORMAL')),
                plugin_path=str(plugin_path),
                config=plugin_info.get('config', {})
            )

            # 解析依赖
            deps_data = plugin_info.get('dependencies', [])
            metadata.dependencies = [
                PluginDependency(
                    name=dep if isinstance(dep, str) else dep.get('name'),
                    version_requirement=dep.get('version') if isinstance(dep, dict) else None,
                    optional=dep.get('optional', False) if isinstance(dep, dict) else False
                )
                for dep in deps_data
            ]

            # 解析支持的资产类型和数据类型
            if 'supported_assets' in plugin_info:
                metadata.supported_assets = [
                    self._parse_asset_type(asset) for asset in plugin_info['supported_assets']
                ]

            if 'supported_data_types' in plugin_info:
                metadata.supported_data_types = [
                    self._parse_data_type(data_type) for data_type in plugin_info['supported_data_types']
                ]

            return metadata

        except Exception as e:
            logger.error(f"Failed to create plugin metadata for {plugin_path}: {e}")
            return None

    def _load_plugin_info(self, plugin_path: Path) -> Dict[str, Any]:
        """加载插件信息"""
        # 尝试从多个可能的文件加载插件信息
        info_files = ["plugin.json", "metadata.json", "info.json"]

        for info_file in info_files:
            info_path = plugin_path / info_file
            if info_path.exists():
                try:
                    with open(info_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load {info_path}: {e}")

        # 如果没有找到信息文件，尝试从__init__.py中提取
        init_path = plugin_path / "__init__.py"
        if init_path.exists():
            try:
                with open(init_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 提取常见的插件元数据字段
                    info = {}
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.startswith('__name__'):
                            info['name'] = line.split('=')[1].strip().strip('"\'')
                        elif line.startswith('__version__'):
                            info['version'] = line.split('=')[1].strip().strip('"\'')
                        elif line.startswith('__description__'):
                            info['description'] = line.split('=')[1].strip().strip('"\'')
                        elif line.startswith('__author__'):
                            info['author'] = line.split('=')[1].strip().strip('"\'')
                    return info
            except Exception as e:
                logger.warning(f"Failed to extract info from {init_path}: {e}")

        return {}

    def _parse_plugin_type(self, type_str: str) -> PluginType:
        """解析插件类型"""
        try:
            return PluginType(type_str.lower())
        except ValueError:
            # 尝试映射常见的类型名称
            type_mapping = {
                'data_source': PluginType.DATA_SOURCE,
                'datasource': PluginType.DATA_SOURCE,
                'indicator': PluginType.INDICATOR,
                'strategy': PluginType.STRATEGY,
                'analysis': PluginType.ANALYSIS,
                'ui': PluginType.UI_COMPONENT,
                'export': PluginType.EXPORT,
                'notification': PluginType.NOTIFICATION
            }
            return type_mapping.get(type_str.lower(), PluginType.DATA_SOURCE)

    def _parse_priority(self, priority_str: str) -> PluginPriority:
        """解析优先级"""
        try:
            return PluginPriority[priority_str.upper()]
        except KeyError:
            return PluginPriority.NORMAL

    def _parse_asset_type(self, asset_str: str) -> AssetType:
        """解析资产类型"""
        try:
            return AssetType(asset_str.lower())
        except ValueError:
            return AssetType.STOCK_A  # 默认股票类型

    def _parse_data_type(self, data_type_str: str) -> DataType:
        """解析数据类型"""
        try:
            return DataType(data_type_str.lower())
        except ValueError:
            return DataType.REAL_TIME_QUOTE  # 默认实时行情

    def _register_plugin(self, metadata: PluginMetadata) -> None:
        """注册插件"""
        try:
            with self._plugin_lock:
                plugin_id = metadata.plugin_id

                # 检查是否已经注册
                if plugin_id in self._plugins:
                    logger.warning(f"Plugin {plugin_id} already registered, updating...")

                # 注册插件
                self._plugins[plugin_id] = metadata

                # 更新索引
                self._plugins_by_type[metadata.plugin_type].append(plugin_id)
                self._plugins_by_state[metadata.state].append(plugin_id)
                self._plugins_by_priority[metadata.priority].append(plugin_id)

                # 记录事件
                self._record_event(plugin_id, PluginLifecycleStage.DISCOVER, True)

                logger.debug(f"✓ Registered plugin: {plugin_id}")

        except Exception as e:
            logger.error(f"Failed to register plugin {metadata.plugin_id}: {e}")

    def _resolve_dependencies(self) -> None:
        """解析依赖关系"""
        try:
            # 清空依赖图
            self._dependency_graph.clear()
            self._reverse_dependency_graph.clear()

            # 构建依赖图
            for plugin_id, metadata in self._plugins.items():
                for dependency in metadata.dependencies:
                    dep_name = dependency.name

                    # 检查依赖是否存在
                    if dep_name in self._plugins:
                        self._dependency_graph[plugin_id].add(dep_name)
                        self._reverse_dependency_graph[dep_name].add(plugin_id)
                    elif not dependency.optional:
                        logger.warning(f"Plugin {plugin_id} has unmet dependency: {dep_name}")

            # 检查循环依赖
            cycles = self._detect_dependency_cycles()
            if cycles:
                logger.error(f"Detected dependency cycles: {cycles}")

            logger.info(f"✓ Dependency resolution completed for {len(self._plugins)} plugins")

        except Exception as e:
            logger.error(f"Failed to resolve dependencies: {e}")

    def _detect_dependency_cycles(self) -> List[List[str]]:
        """检测依赖循环"""
        def dfs(node: str, visited: Set[str], rec_stack: Set[str], path: List[str]) -> List[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            cycles = []

            for neighbor in self._dependency_graph.get(node, []):
                if neighbor not in visited:
                    cycles.extend(dfs(neighbor, visited, rec_stack, path.copy()))
                elif neighbor in rec_stack:
                    # 找到循环
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            rec_stack.remove(node)
            return cycles

        visited = set()
        all_cycles = []

        for plugin_id in self._plugins:
            if plugin_id not in visited:
                all_cycles.extend(dfs(plugin_id, visited, set(), []))

        return all_cycles

    def _load_plugins(self) -> None:
        """加载插件"""
        start_time = time.time()

        try:
            # 按优先级排序插件
            plugin_load_order = self._get_plugin_load_order()

            loaded_count = 0
            for plugin_id in plugin_load_order:
                if self._load_plugin(plugin_id):
                    loaded_count += 1

            # 更新指标
            self._metrics.loaded_plugins = loaded_count
            self._metrics.load_time = time.time() - start_time

            logger.info(f"✓ Plugin loading completed: {loaded_count} plugins loaded in {self._metrics.load_time:.2f}s")

        except Exception as e:
            logger.error(f"Plugin loading failed: {e}")

    def _get_plugin_load_order(self) -> List[str]:
        """获取插件加载顺序（拓扑排序）"""
        # 拓扑排序，确保依赖先加载
        def topological_sort():
            in_degree = {plugin_id: 0 for plugin_id in self._plugins}

            # 计算入度
            for plugin_id in self._plugins:
                for dep in self._dependency_graph.get(plugin_id, []):
                    if dep in in_degree:
                        in_degree[dep] += 1

            # 按优先级和入度排序
            queue = []
            for plugin_id in self._plugins:
                priority = self._plugins[plugin_id].priority.value
                queue.append((in_degree[plugin_id], priority, plugin_id))

            queue.sort()  # 入度小的先处理，同入度的按优先级排序

            result = []
            remaining = {pid for _, _, pid in queue}

            while queue:
                # 找到入度为0的节点
                for i, (degree, priority, plugin_id) in enumerate(queue):
                    if degree == 0:
                        result.append(plugin_id)
                        remaining.remove(plugin_id)
                        queue.pop(i)

                        # 更新依赖它的节点的入度
                        for j, (d, p, pid) in enumerate(queue):
                            if plugin_id in self._dependency_graph.get(pid, []):
                                queue[j] = (d - 1, p, pid)
                        break
                else:
                    # 如果没有入度为0的节点，说明有循环依赖
                    logger.error(f"Circular dependency detected in remaining plugins: {remaining}")
                    result.extend(remaining)
                    break

            return result

        return topological_sort()

    def _load_plugin(self, plugin_id: str) -> bool:
        """加载单个插件"""
        try:
            metadata = self._plugins[plugin_id]

            if metadata.state != PluginLifecycle.DISCOVERED:
                return True  # 已经加载或失败

            # 检查依赖
            for dependency in metadata.dependencies:
                dep_plugin = self._plugins.get(dependency.name)
                if dep_plugin is None:
                    if not dependency.optional:
                        self._set_plugin_state(plugin_id, PluginLifecycle.FAILED,
                                               f"Missing dependency: {dependency.name}")
                        return False
                elif dep_plugin.state not in [PluginLifecycle.LOADED, PluginLifecycle.INITIALIZED, PluginLifecycle.ACTIVATED]:
                    if not dependency.optional:
                        self._set_plugin_state(plugin_id, PluginLifecycle.FAILED,
                                               f"Dependency not loaded: {dependency.name}")
                        return False

            # 导入插件模块
            plugin_module = self._import_plugin_module(metadata)
            if plugin_module is None:
                self._set_plugin_state(plugin_id, PluginLifecycle.FAILED, "Failed to import module")
                return False

            # 查找插件类
            plugin_class = self._find_plugin_class(plugin_module, metadata)
            if plugin_class is None:
                self._set_plugin_state(plugin_id, PluginLifecycle.FAILED, "Plugin class not found")
                return False

            # 保存模块和类
            self._plugin_modules[plugin_id] = plugin_module
            self._plugin_classes[plugin_id] = plugin_class
            metadata.plugin_module = plugin_module
            metadata.plugin_class = plugin_class
            metadata.load_time = datetime.now()

            # 更新状态
            self._set_plugin_state(plugin_id, PluginLifecycle.LOADED)
            self._record_event(plugin_id, PluginLifecycleStage.LOAD, True)

            logger.debug(f"✓ Loaded plugin: {plugin_id}")
            return True

        except Exception as e:
            error_msg = f"Failed to load plugin {plugin_id}: {e}"
            logger.error(error_msg)
            self._set_plugin_state(plugin_id, PluginLifecycle.FAILED, str(e))
            self._record_event(plugin_id, PluginLifecycleStage.LOAD, False, error_message=str(e))
            return False

    def _import_plugin_module(self, metadata: PluginMetadata) -> Optional[Any]:
        """导入插件模块"""
        try:
            plugin_path = Path(metadata.plugin_path)

            # 尝试多种导入方式
            import_paths = [
                plugin_path / "plugin.py",
                plugin_path / "main.py",
                plugin_path / "__init__.py"
            ]

            for import_path in import_paths:
                if import_path.exists():
                    spec = importlib.util.spec_from_file_location(
                        f"plugin_{metadata.plugin_id}",
                        import_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        return module

            # 尝试包导入
            try:
                return importlib.import_module(metadata.plugin_id)
            except ImportError:
                pass

            return None

        except Exception as e:
            logger.error(f"Failed to import plugin module {metadata.plugin_id}: {e}")
            return None

    def _find_plugin_class(self, module: Any, metadata: PluginMetadata) -> Optional[Type]:
        """查找插件类"""
        try:
            # 常见的插件类名称
            class_names = [
                f"{metadata.name.replace(' ', '')}Plugin",
                f"{metadata.plugin_id.replace('_', '').replace('-', '')}Plugin",
                "Plugin",
                "Main",
                f"{metadata.name.replace(' ', '')}",
                metadata.plugin_id.replace('_', '').replace('-', '')
            ]

            # 查找类
            for class_name in class_names:
                if hasattr(module, class_name):
                    plugin_class = getattr(module, class_name)
                    if isinstance(plugin_class, type):
                        return plugin_class

            # 查找实现了特定接口的类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and self._is_plugin_class(attr):
                    return attr

            return None

        except Exception as e:
            logger.error(f"Failed to find plugin class in {metadata.plugin_id}: {e}")
            return None

    def _is_plugin_class(self, cls: Type) -> bool:
        """检查是否是插件类"""
        # 检查是否实现了常见的插件接口
        plugin_interfaces = ['IPlugin', 'Plugin', 'IDataSourcePlugin']

        for interface in plugin_interfaces:
            # 检查基类
            for base in cls.__mro__:
                if base.__name__ == interface:
                    return True

        # 检查是否有常见的插件方法
        plugin_methods = ['initialize', 'activate', 'deactivate', 'get_data']
        has_plugin_methods = sum(1 for method in plugin_methods if hasattr(cls, method))

        return has_plugin_methods >= 2  # 至少有2个插件方法

    def _initialize_plugins(self) -> None:
        """初始化插件"""
        try:
            initialized_count = 0

            for plugin_id, metadata in self._plugins.items():
                if metadata.state == PluginLifecycle.LOADED:
                    if self._initialize_plugin(plugin_id):
                        initialized_count += 1

            logger.info(f"✓ Plugin initialization completed: {initialized_count} plugins initialized")

        except Exception as e:
            logger.error(f"Plugin initialization failed: {e}")

    def _initialize_plugin(self, plugin_id: str) -> bool:
        """初始化单个插件"""
        try:
            metadata = self._plugins[plugin_id]
            plugin_class = self._plugin_classes[plugin_id]

            # 创建插件实例
            plugin_instance = plugin_class()

            # 调用初始化方法
            if hasattr(plugin_instance, 'initialize'):
                plugin_instance.initialize()

            # 保存实例
            self._plugin_instances[plugin_id] = plugin_instance
            metadata.plugin_instance = plugin_instance
            metadata.initialization_time = datetime.now()

            # 更新状态
            self._set_plugin_state(plugin_id, PluginLifecycle.INITIALIZED)
            self._record_event(plugin_id, PluginLifecycleStage.INITIALIZE, True)

            logger.debug(f"✓ Initialized plugin: {plugin_id}")
            return True

        except Exception as e:
            error_msg = f"Failed to initialize plugin {plugin_id}: {e}"
            logger.error(error_msg)
            self._set_plugin_state(plugin_id, PluginLifecycle.FAILED, str(e))
            self._record_event(plugin_id, PluginLifecycleStage.INITIALIZE, False, error_message=str(e))
            return False

    def _activate_plugins(self) -> None:
        """激活插件"""
        try:
            activated_count = 0

            for plugin_id, metadata in self._plugins.items():
                if metadata.state == PluginLifecycle.INITIALIZED:
                    if self._activate_plugin(plugin_id):
                        activated_count += 1

            self._metrics.active_plugins = activated_count
            logger.info(f"✓ Plugin activation completed: {activated_count} plugins activated")

        except Exception as e:
            logger.error(f"Plugin activation failed: {e}")

    def _activate_plugin(self, plugin_id: str) -> bool:
        """激活单个插件"""
        try:
            metadata = self._plugins[plugin_id]
            plugin_instance = self._plugin_instances[plugin_id]

            # 调用激活方法
            if hasattr(plugin_instance, 'activate'):
                plugin_instance.activate()

            metadata.activation_time = datetime.now()

            # 更新状态
            self._set_plugin_state(plugin_id, PluginLifecycle.ACTIVATED)
            self._record_event(plugin_id, PluginLifecycleStage.ACTIVATE, True)

            logger.debug(f"✓ Activated plugin: {plugin_id}")
            return True

        except Exception as e:
            error_msg = f"Failed to activate plugin {plugin_id}: {e}"
            logger.error(error_msg)
            self._set_plugin_state(plugin_id, PluginLifecycle.FAILED, str(e))
            self._record_event(plugin_id, PluginLifecycleStage.ACTIVATE, False, error_message=str(e))
            return False

    def _start_background_tasks(self) -> None:
        """启动后台任务"""
        try:
            # 启动健康检查任务
            if hasattr(self, '_data_executor'):
                self._data_executor.submit(self._health_check_loop)

            logger.info("✓ Background tasks started")

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    def _validate_plugin_functionality(self) -> None:
        """验证插件功能"""
        try:
            total_plugins = len(self._plugins)
            healthy_plugins = 0

            for plugin_id in self._plugins:
                if self._check_plugin_health(plugin_id):
                    healthy_plugins += 1

            if total_plugins > 0:
                health_rate = healthy_plugins / total_plugins
                logger.info(f"✓ Plugin functionality validation: {healthy_plugins}/{total_plugins} plugins healthy ({health_rate:.1%})")

        except Exception as e:
            logger.error(f"Plugin functionality validation failed: {e}")

    def _set_plugin_state(self, plugin_id: str, state: PluginLifecycle, error_message: Optional[str] = None) -> None:
        """设置插件状态"""
        with self._plugin_lock:
            if plugin_id in self._plugins:
                metadata = self._plugins[plugin_id]
                old_state = metadata.state

                # 更新状态
                metadata.state = state
                metadata.error_message = error_message

                if error_message:
                    metadata.error_count += 1

                # 更新索引
                if old_state != state:
                    self._plugins_by_state[old_state].remove(plugin_id)
                    self._plugins_by_state[state].append(plugin_id)

                # 更新指标
                if state == PluginLifecycle.FAILED:
                    self._metrics.failed_plugins += 1

    def _record_event(self, plugin_id: str, stage: PluginLifecycleStage, success: bool,
                      details: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None) -> None:
        """记录插件事件"""
        event = PluginEvent(
            plugin_id=plugin_id,
            event_type=f"plugin_{stage.value}",
            stage=stage,
            timestamp=datetime.now(),
            success=success,
            details=details or {},
            error_message=error_message
        )

        self._event_history.append(event)

        # 限制事件历史大小
        if len(self._event_history) > 10000:
            self._event_history = self._event_history[-5000:]

    def _health_check_loop(self) -> None:
        """健康检查循环"""
        while not self._shutdown_event.is_set():
            try:
                self._perform_health_checks()
                self._shutdown_event.wait(self._config["health_check_interval"])
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                self._shutdown_event.wait(60)

    def _perform_health_checks(self) -> None:
        """执行健康检查"""
        try:
            for plugin_id in list(self._plugins.keys()):
                self._check_plugin_health(plugin_id)

            self._last_health_check = datetime.now()

        except Exception as e:
            logger.error(f"Health check failed: {e}")

    def _check_plugin_health(self, plugin_id: str) -> bool:
        """检查插件健康状态"""
        try:
            metadata = self._plugins[plugin_id]

            if metadata.state not in [PluginLifecycle.ACTIVATED, PluginLifecycle.INITIALIZED]:
                return False

            plugin_instance = self._plugin_instances.get(plugin_id)
            if plugin_instance is None:
                return False

            # 调用健康检查方法
            if hasattr(plugin_instance, 'health_check'):
                try:
                    health_result = plugin_instance.health_check()
                    metadata.health_status = health_result
                    metadata.last_health_check = datetime.now()

                    if hasattr(health_result, 'is_healthy'):
                        return health_result.is_healthy
                    else:
                        return True  # 如果没有健康状态，假设健康

                except Exception as e:
                    logger.warning(f"Health check failed for plugin {plugin_id}: {e}")
                    return False

            return True  # 没有健康检查方法，假设健康

        except Exception as e:
            logger.error(f"Error checking health for plugin {plugin_id}: {e}")
            return False

    # 公共接口方法

    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        """获取插件实例"""
        return self._plugin_instances.get(plugin_id)

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[str]:
        """按类型获取插件"""
        return self._plugins_by_type.get(plugin_type, [])

    def get_plugins_by_state(self, state: PluginLifecycle) -> List[str]:
        """按状态获取插件"""
        return self._plugins_by_state.get(state, [])

    def get_plugin_metadata(self, plugin_id: str) -> Optional[PluginMetadata]:
        """获取插件元数据"""
        return self._plugins.get(plugin_id)

    def activate_plugin(self, plugin_id: str) -> bool:
        """激活插件"""
        if plugin_id not in self._plugins:
            return False

        metadata = self._plugins[plugin_id]
        if metadata.state == PluginLifecycle.INITIALIZED:
            return self._activate_plugin(plugin_id)

        return False

    def deactivate_plugin(self, plugin_id: str) -> bool:
        """停用插件"""
        try:
            if plugin_id not in self._plugins:
                return False

            metadata = self._plugins[plugin_id]
            if metadata.state != PluginLifecycle.ACTIVATED:
                return False

            plugin_instance = self._plugin_instances.get(plugin_id)
            if plugin_instance and hasattr(plugin_instance, 'deactivate'):
                plugin_instance.deactivate()

            self._set_plugin_state(plugin_id, PluginLifecycle.DEACTIVATED)
            self._record_event(plugin_id, PluginLifecycleStage.DEACTIVATE, True)

            return True

        except Exception as e:
            logger.error(f"Failed to deactivate plugin {plugin_id}: {e}")
            self._record_event(plugin_id, PluginLifecycleStage.DEACTIVATE, False, error_message=str(e))
            return False

    def get_plugin_metrics(self) -> PluginMetrics:
        """获取插件服务指标"""
        with self._plugin_lock:
            self._metrics.total_plugins = len(self._plugins)
            self._metrics.last_update = datetime.now()
            return self._metrics

    def get_plugin_events(self, limit: int = 100) -> List[PluginEvent]:
        """获取插件事件历史"""
        return self._event_history[-limit:]

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            with self._plugin_lock:
                total_plugins = len(self._plugins)
                active_plugins = len(self._plugins_by_state.get(PluginLifecycle.ACTIVATED, []))
                failed_plugins = len(self._plugins_by_state.get(PluginLifecycle.FAILED, []))

                health_rate = active_plugins / total_plugins if total_plugins > 0 else 0

                return {
                    "status": "healthy" if health_rate > 0.5 else "degraded" if health_rate > 0 else "unhealthy",
                    "total_plugins": total_plugins,
                    "active_plugins": active_plugins,
                    "failed_plugins": failed_plugins,
                    "health_rate": health_rate,
                    "last_discovery": self._last_discovery.isoformat() if self._last_discovery else None,
                    "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
                    "uptime_seconds": (datetime.now() - self._start_time).total_seconds()
                }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing PluginService resources...")

            # 停用所有激活的插件
            for plugin_id in list(self._plugins_by_state.get(PluginLifecycle.ACTIVATED, [])):
                self.deactivate_plugin(plugin_id)

            # 关闭线程池
            if self._load_executor:
                self._load_executor.shutdown(wait=True)

            # 清理插件实例
            self._plugin_instances.clear()
            self._plugin_modules.clear()
            self._plugin_classes.clear()

            logger.info("PluginService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing PluginService: {e}")

    @property
    def metrics(self) -> Dict[str, Any]:
        """返回插件服务指标的字典表示"""
        if not hasattr(self, '_plugin_metrics'):
            self._plugin_metrics = self._metrics

        return {
            'total_plugins': self._plugin_metrics.total_plugins,
            'discovered_plugins': self._plugin_metrics.discovered_plugins,
            'loaded_plugins': self._plugin_metrics.loaded_plugins,
            'active_plugins': self._plugin_metrics.active_plugins,
            'failed_plugins': self._plugin_metrics.failed_plugins,
            'discovery_time': self._plugin_metrics.discovery_time,
            'load_time': self._plugin_metrics.load_time,
            'last_discovery': self._plugin_metrics.last_discovery.isoformat() if self._plugin_metrics.last_discovery else None,
            'last_update': self._plugin_metrics.last_update.isoformat()
        }


# 便利函数
def get_plugin_service() -> Optional[PluginService]:
    """获取插件服务实例"""
    try:
        container = get_service_container()
        return container.resolve(PluginService)
    except:
        return None
