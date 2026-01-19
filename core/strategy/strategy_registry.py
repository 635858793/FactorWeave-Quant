from loguru import logger
#!/usr/bin/env python3
"""
策略注册器

提供线程安全的策略注册、发现和管理功能
集成数据库存储，使用系统统一组件
"""

import threading
import importlib
import inspect
from typing import Dict, List, Optional, Any, Type, Callable
from datetime import datetime
from pathlib import Path

# 使用系统统一组件
from core.adapters import get_config
from .base_strategy import BaseStrategy, StrategyType

class StrategyInfo:
    """策略信息类，用于封装策略基本信息"""

    def __init__(self, strategy_id: str, name: str, description: str = "",
                 category: str = "", author: str = "", version: str = "1.0.0"):
        self.strategy_id = strategy_id
        self.name = name
        self.description = description
        self.category = category
        self.author = author
        self.version = version

    def __repr__(self):
        return f"StrategyInfo(id={self.strategy_id}, name={self.name})"

class StrategyRegistry:
    """策略注册器"""

    def __init__(self):
        """初始化策略注册器"""
        self.logger = logger.bind(module=__name__)
        self.config = get_config()
        
        # 使用DatabaseService替代StrategyDatabaseManager
        self.database_service = None
        self._database_service_initialized = False
        
        # 线程安全的策略存储
        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._listeners: List[Callable] = []
        self._lock = threading.RLock()

        self.logger.info("策略注册器初始化完成")

    def _ensure_database_service(self):
        """确保DatabaseService已初始化"""
        if self._database_service_initialized:
            return
            
        try:
            from core.containers.service_container import get_service_container
            from core.services.database_service import DatabaseService
            container = get_service_container()
            self.database_service = container.resolve(DatabaseService)
            if self.database_service is not None:
                self._database_service_initialized = True
                self.logger.info("成功获取DatabaseService")
        except Exception as e:
            self.logger.warning(f"无法获取DatabaseService: {e}")
            self.database_service = None

    def register(self, strategy_name: str, strategy_class: Type[BaseStrategy],
                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        注册策略

        Args:
            strategy_name: 策略名称
            strategy_class: 策略类
            metadata: 策略元数据

        Returns:
            是否注册成功
        """
        try:
            with self._lock:
                # 验证策略类
                if not issubclass(strategy_class, BaseStrategy):
                    raise ValueError(f"策略类必须继承自BaseStrategy: {strategy_class}")

                # 提取元数据
                if metadata is None:
                    metadata = self._extract_metadata(strategy_class)
                else:
                    # 如果提供了metadata但缺少strategy_type，尝试从策略类提取
                    if 'strategy_type' not in metadata:
                        extracted_metadata = self._extract_metadata(strategy_class)
                        metadata['strategy_type'] = extracted_metadata['strategy_type']

                # 确保元数据包含必要信息
                metadata.setdefault('name', strategy_name)
                metadata.setdefault('class_name', strategy_class.__name__)
                metadata.setdefault('module', strategy_class.__module__)
                metadata.setdefault(
                    'registered_at', datetime.now().isoformat())

                # 注册到内存
                self._strategies[strategy_name] = strategy_class
                self._metadata[strategy_name] = metadata

                # 注册到数据库
                try:
                    self._ensure_database_service()
                    if self.database_service:
                        strategy_id = self.database_service.register_strategy(
                            strategy_class, metadata)
                        metadata['database_id'] = strategy_id
                    else:
                        self.logger.warning("DatabaseService不可用，仅注册到内存")
                except Exception as e:
                    self.logger.warning(f"数据库注册失败，仅注册到内存: {e}")

                # 通知监听器
                self._notify_listeners('register', strategy_name, metadata)

                self.logger.info(f"策略注册成功: {strategy_name}")
                return True

        except Exception as e:
            self.logger.error(f"策略注册失败 {strategy_name}: {e}")
            return False

    def unregister(self, strategy_name: str) -> bool:
        """
        注销策略

        Args:
            strategy_name: 策略名称

        Returns:
            是否注销成功
        """
        try:
            with self._lock:
                if strategy_name not in self._strategies:
                    self.logger.warning(f"策略不存在: {strategy_name}")
                    return False

                # 从内存中移除
                strategy_class = self._strategies.pop(strategy_name)
                metadata = self._metadata.pop(strategy_name)

                # 从数据库中软删除
                try:
                    self._ensure_database_service()
                    if self.database_service:
                        # 使用database_id进行删除
                        database_id = metadata.get('database_id')
                        if database_id:
                            self.database_service.delete_strategy(database_id)
                    else:
                        self.logger.warning("DatabaseService不可用，无法从数据库删除")
                except Exception as e:
                    self.logger.warning(f"数据库删除失败: {e}")

                # 通知监听器
                self._notify_listeners('unregister', strategy_name, metadata)

                self.logger.info(f"策略注销成功: {strategy_name}")
                return True

        except Exception as e:
            self.logger.error(f"策略注销失败 {strategy_name}: {e}")
            return False

    def get_strategy_class(self, strategy_name: str) -> Optional[Type[BaseStrategy]]:
        """
        获取策略类

        Args:
            strategy_name: 策略名称

        Returns:
            策略类或None
        """
        with self._lock:
            strategy_class = self._strategies.get(strategy_name)

            if strategy_class is None:
                # 尝试从数据库加载
                strategy_class = self._load_strategy_from_database(
                    strategy_name)

            return strategy_class

    def get_strategy_metadata(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        获取策略元数据

        Args:
            strategy_name: 策略名称

        Returns:
            策略元数据或None
        """
        with self._lock:
            metadata = self._metadata.get(strategy_name)

            if metadata is None:
                # 尝试从数据库获取
                self._ensure_database_service()
                if self.database_service:
                    # 先从数据库获取策略信息
                    all_strategies = self.database_service.list_strategies()
                    # 查找匹配的策略
                    for strategy_info in all_strategies:
                        if strategy_info['name'] == strategy_name:
                            metadata = strategy_info.get('metadata', {})
                            metadata.update({
                                'name': strategy_info['name'],
                                'version': strategy_info['version'],
                                'author': strategy_info['author'],
                                'description': strategy_info['description'],
                                'category': strategy_info['category'],
                                'database_id': strategy_info['id']
                            })
                            self._metadata[strategy_name] = metadata
                            break
                else:
                    self.logger.warning("DatabaseService不可用，无法从数据库获取策略元数据")

            return metadata

    def list_strategies(self, category: Optional[str] = None,
                        strategy_type: Optional[StrategyType] = None) -> List[str]:
        """
        列出策略名称

        Args:
            category: 策略分类过滤
            strategy_type: 策略类型过滤

        Returns:
            策略名称列表
        """
        with self._lock:
            # 合并内存和数据库中的策略
            all_strategies = set(self._strategies.keys())

            # 从数据库获取策略列表
            try:
                self._ensure_database_service()
                if self.database_service:
                    db_strategies = self.database_service.list_strategies()
                    all_strategies.update(s['name'] for s in db_strategies)
                else:
                    self.logger.warning("DatabaseService不可用，无法从数据库获取策略列表")
            except Exception as e:
                self.logger.warning(f"从数据库获取策略列表失败: {e}")

            # 过滤策略
            filtered_strategies = []
            for strategy_name in all_strategies:
                metadata = self.get_strategy_metadata(strategy_name)
                if metadata:
                    # 分类过滤
                    if category and metadata.get('category') != category:
                        continue

                    # 类型过滤
                    if strategy_type:
                        strategy_type_str = metadata.get(
                            'strategy_type', 'CUSTOM')
                        if strategy_type_str != strategy_type.value:
                            continue

                    filtered_strategies.append(strategy_name)

            return sorted(filtered_strategies)

    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有策略的元数据

        Returns:
            策略元数据字典
        """
        with self._lock:
            all_metadata = {}

            # 获取所有策略名称
            strategy_names = self.list_strategies()

            for strategy_name in strategy_names:
                metadata = self.get_strategy_metadata(strategy_name)
                if metadata:
                    all_metadata[strategy_name] = metadata

            return all_metadata

    def search_strategies(self, query: str) -> List[str]:
        """
        搜索策略

        Args:
            query: 搜索关键词

        Returns:
            匹配的策略名称列表
        """
        query_lower = query.lower()
        matched_strategies = []

        all_metadata = self.get_all_metadata()

        for strategy_name, metadata in all_metadata.items():
            # 搜索策略名称
            if query_lower in strategy_name.lower():
                matched_strategies.append(strategy_name)
                continue

            # 搜索描述
            description = metadata.get('description', '').lower()
            if query_lower in description:
                matched_strategies.append(strategy_name)
                continue

            # 搜索分类
            category = metadata.get('category', '').lower()
            if query_lower in category:
                matched_strategies.append(strategy_name)
                continue

            # 搜索作者
            author = metadata.get('author', '').lower()
            if query_lower in author:
                matched_strategies.append(strategy_name)
                continue

        return sorted(matched_strategies)

    def get_all_strategies(self) -> List[StrategyInfo]:
        """
        获取所有策略信息

        Returns:
            策略信息对象列表
        """
        strategies = []

        try:
            # 获取所有策略的元数据
            all_metadata = self.get_all_metadata()

            for strategy_name, metadata in all_metadata.items():
                # 创建策略信息对象
                strategy_info = StrategyInfo(
                    strategy_id=metadata.get('database_id', strategy_name),
                    name=metadata.get('name', strategy_name),
                    description=metadata.get('description', ''),
                    category=metadata.get('category', ''),
                    author=metadata.get('author', ''),
                    version=metadata.get('version', '1.0.0')
                )
                strategies.append(strategy_info)

            self.logger.debug(f"获取到 {len(strategies)} 个策略信息")
            return strategies

        except Exception as e:
            self.logger.error(f"获取策略信息列表失败: {e}")
            return []

    def add_listener(self, listener: Callable[[str, str, Dict[str, Any]], None]):
        """
        添加事件监听器

        Args:
            listener: 监听器函数，接收(event_type, strategy_name, metadata)参数
        """
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)
                self.logger.debug(f"添加策略事件监听器: {listener}")

    def remove_listener(self, listener: Callable):
        """
        移除事件监听器

        Args:
            listener: 监听器函数
        """
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
                self.logger.debug(f"移除策略事件监听器: {listener}")

    def auto_discover_strategies(self, search_paths: Optional[List[str]] = None) -> int:
        """
        自动发现策略

        Args:
            search_paths: 搜索路径列表

        Returns:
            发现的策略数量
        """
        if search_paths is None:
            # 从配置获取搜索路径
            search_paths = self.config.get(
                'strategy_discovery', {}).get('paths', ['strategies'])

        discovered_count = 0

        for search_path in search_paths:
            try:
                path = Path(search_path)
                if not path.exists():
                    continue

                # 搜索Python文件
                for py_file in path.rglob('*.py'):
                    if py_file.name.startswith('_'):
                        continue

                    try:
                        # 构建模块名
                        relative_path = py_file.relative_to(Path.cwd())
                        module_name = str(relative_path.with_suffix(
                            '')).replace('/', '.').replace('\\', '.')

                        # 导入模块
                        module = importlib.import_module(module_name)

                        # 查找策略类
                        for name, obj in inspect.getmembers(module, inspect.isclass):
                            if (issubclass(obj, BaseStrategy) and
                                obj != BaseStrategy and
                                    obj.__module__ == module_name):

                                # 检查是否已注册
                                strategy_name = getattr(
                                    obj, '_strategy_name', name)
                                if strategy_name not in self._strategies:
                                    metadata = self._extract_metadata(obj)
                                    if self.register(strategy_name, obj, metadata):
                                        discovered_count += 1

                    except Exception as e:
                        self.logger.debug(f"导入模块失败 {py_file}: {e}")
                        continue

            except Exception as e:
                self.logger.warning(f"搜索路径失败 {search_path}: {e}")
                continue

        self.logger.info(f"自动发现策略完成: 发现 {discovered_count} 个策略")
        return discovered_count

    def reload_strategy(self, strategy_name: str) -> bool:
        """
        重新加载策略

        Args:
            strategy_name: 策略名称

        Returns:
            是否重新加载成功
        """
        try:
            with self._lock:
                if strategy_name not in self._strategies:
                    self.logger.warning(f"策略不存在: {strategy_name}")
                    return False

                # 获取原始信息
                old_class = self._strategies[strategy_name]
                old_metadata = self._metadata[strategy_name]

                # 重新导入模块
                module_name = old_class.__module__
                module = importlib.reload(importlib.import_module(module_name))

                # 获取新的策略类
                new_class = getattr(module, old_class.__name__)

                # 更新注册
                new_metadata = self._extract_metadata(new_class)
                new_metadata.update({
                    'name': strategy_name,
                    'reloaded_at': datetime.now().isoformat()
                })

                self._strategies[strategy_name] = new_class
                self._metadata[strategy_name] = new_metadata

                # 更新数据库
                try:
                    self._ensure_database_service()
                    if self.database_service:
                        self.database_service.register_strategy(new_class, new_metadata)
                    else:
                        self.logger.warning("DatabaseService不可用，无法更新数据库")
                except Exception as e:
                    self.logger.warning(f"数据库更新失败: {e}")

                # 通知监听器
                self._notify_listeners('reload', strategy_name, new_metadata)

                self.logger.info(f"策略重新加载成功: {strategy_name}")
                return True

        except Exception as e:
            self.logger.error(f"策略重新加载失败 {strategy_name}: {e}")
            return False

    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册器统计信息"""
        with self._lock:
            stats = {
                'total_strategies': len(self._strategies),
                'memory_strategies': len(self._strategies),
                'listeners_count': len(self._listeners)
            }

            # 按类型统计
            type_counts = {}
            for metadata in self._metadata.values():
                strategy_type = metadata.get('strategy_type', 'CUSTOM')
                type_counts[strategy_type] = type_counts.get(
                    strategy_type, 0) + 1
            stats['by_type'] = type_counts

            # 按分类统计
            category_counts = {}
            for metadata in self._metadata.values():
                category = metadata.get('category', 'uncategorized')
                category_counts[category] = category_counts.get(
                    category, 0) + 1
            stats['by_category'] = category_counts

            # 数据库统计
            try:
                self._ensure_database_service()
                if self.database_service:
                    db_stats = self.database_service.get_database_stats()
                    stats['database'] = db_stats
                else:
                    stats['database'] = {}
            except Exception as e:
                self.logger.warning(f"获取数据库统计失败: {e}")
                stats['database'] = {}

            return stats

    def _extract_metadata(self, strategy_class: Type[BaseStrategy]) -> Dict[str, Any]:
        """提取策略元数据"""
        metadata = {
            'class_name': strategy_class.__name__,
            'module': strategy_class.__module__,
            'description': strategy_class.__doc__ or '',
            'version': getattr(strategy_class, '__version__', '1.0.0'),
            'author': getattr(strategy_class, '__author__', ''),
            'category': getattr(strategy_class, '__category__', ''),
            'strategy_type': getattr(strategy_class, '_strategy_type', StrategyType.CUSTOM).value,
            'extracted_at': datetime.now().isoformat()
        }

        # 提取参数信息和策略类型
        try:
            instance = strategy_class("temp_instance")
            if hasattr(instance, 'get_parameter_info'):
                metadata['parameters'] = instance.get_parameter_info()
            # 从实例中提取 strategy_type（优先级高于类属性）
            if hasattr(instance, 'strategy_type') and isinstance(instance.strategy_type, StrategyType):
                metadata['strategy_type'] = instance.strategy_type.value
        except Exception as e:
            self.logger.debug(f"提取参数信息失败 {strategy_class}: {e}")

        return metadata

    def _load_strategy_from_database(self, strategy_name: str) -> Optional[Type[BaseStrategy]]:
        """从数据库加载策略类"""
        try:
            if not self.database_service:
                return None

            # 先从数据库查找策略
            all_strategies = self.database_service.list_strategies()
            db_info = None
            for strategy_info in all_strategies:
                if strategy_info['name'] == strategy_name:
                    db_info = strategy_info
                    break

            if not db_info:
                return None

            class_path = db_info.get('class_path', '')
            if not class_path:
                return None

            # 解析类路径
            module_name, class_name = class_path.rsplit('.', 1)

            # 导入模块和类
            module = importlib.import_module(module_name)
            strategy_class = getattr(module, class_name)

            # 验证类型
            if not issubclass(strategy_class, BaseStrategy):
                return None

            # 注册到内存
            metadata = db_info.get('metadata', {})
            self._strategies[strategy_name] = strategy_class
            self._metadata[strategy_name] = metadata

            self.logger.info(f"从数据库加载策略: {strategy_name}")
            return strategy_class

        except Exception as e:
            self.logger.error(f"从数据库加载策略失败 {strategy_name}: {e}")
            return None

    def _notify_listeners(self, event_type: str, strategy_name: str, metadata: Dict[str, Any]):
        """通知事件监听器"""
        for listener in self._listeners:
            try:
                listener(event_type, strategy_name, metadata)
            except Exception as e:
                self.logger.error(f"事件监听器执行失败 {listener}: {e}")

# 全局单例实例
_strategy_registry = None
_registry_lock = threading.Lock()

# 延迟注册队列（用于在服务容器初始化之前注册策略）
_pending_registrations = []
_pending_registrations_lock = threading.Lock()

def get_strategy_registry() -> StrategyRegistry:
    """获取策略注册器单例"""
    global _strategy_registry

    if _strategy_registry is None:
        with _registry_lock:
            if _strategy_registry is None:
                _strategy_registry = StrategyRegistry()

    return _strategy_registry

def register_strategy(strategy_name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    策略注册装饰器（支持延迟注册）

    Args:
        strategy_name: 策略名称
        metadata: 策略元数据
    """
    def decorator(strategy_class: Type[BaseStrategy]):
        # 设置策略名称属性
        strategy_class._strategy_name = strategy_name

        # 合并元数据
        final_metadata = metadata or {}
        final_metadata['name'] = strategy_name

        # 尝试获取注册器
        try:
            from core.containers.service_container import get_service_container
            container = get_service_container()
            if container.is_registered(StrategyRegistry):
                registry = container.resolve(StrategyRegistry)
                registry.register(strategy_name, strategy_class, final_metadata)
            else:
                raise Exception("StrategyRegistry not registered")
        except Exception:
            # 如果服务容器未初始化，将注册信息保存到待注册队列
            with _pending_registrations_lock:
                _pending_registrations.append({
                    'strategy_name': strategy_name,
                    'strategy_class': strategy_class,
                    'metadata': final_metadata
                })

        return strategy_class

    return decorator

def process_pending_registrations():
    """处理待注册的策略队列"""
    global _pending_registrations

    with _pending_registrations_lock:
        if not _pending_registrations:
            return

        try:
            from core.containers.service_container import get_service_container
            container = get_service_container()
            registry = container.resolve(StrategyRegistry)

            for registration in _pending_registrations:
                try:
                    registry.register(
                        registration['strategy_name'],
                        registration['strategy_class'],
                        registration['metadata']
                    )
                except Exception as e:
                    logger.error(f"注册策略失败 {registration['strategy_name']}: {e}")

            logger.info(f"成功处理 {len(_pending_registrations)} 个待注册策略")
            _pending_registrations.clear()
        except Exception as e:
            logger.error(f"处理待注册策略失败: {e}")
