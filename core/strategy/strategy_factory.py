from loguru import logger
"""
策略工厂 - 负责策略实例的创建和管理

提供统一的策略创建接口和实例管理，支持从数据库读取和应用策略
"""

from typing import Dict, List, Any, Optional, Type, Tuple
import importlib
import threading
from datetime import datetime

# 使用系统统一组件
from core.adapters import get_config

from .base_strategy import BaseStrategy, StrategyParameter
from .strategy_registry import StrategyRegistry

class StrategyFactory:
    """策略工厂 - 统一的策略创建和管理"""

    def __init__(self, registry: StrategyRegistry):
        """初始化策略工厂

        Args:
            registry: 策略注册器
        """
        self.logger = logger.bind(module=__name__)
        self.config = get_config()
        self.registry = registry

        # 使用DatabaseService替代StrategyDatabaseManager
        self.database_service = None
        self._database_service_initialized = False

        self._instances: Dict[str, BaseStrategy] = {}
        self._lock = threading.RLock()
        self._creation_stats = {
            'total_created': 0,
            'successful_creations': 0,
            'failed_creations': 0,
            'database_loads': 0,
            'successful_database_loads': 0,
            'failed_database_loads': 0
        }

        self.logger.info("策略工厂初始化完成")

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

    def create_strategy(self, strategy_name: str, instance_name: str = None,
                        **kwargs) -> Optional[BaseStrategy]:
        """创建策略实例

        Args:
            strategy_name: 策略名称
            instance_name: 实例名称，如果为None则使用策略名称
            **kwargs: 策略参数

        Returns:
            策略实例或None
        """
        with self._lock:
            try:
                self.logger.info(f"开始创建策略实例: {strategy_name}")

                # 获取策略类
                strategy_class = self.registry.get_strategy_class(
                    strategy_name)
                if not strategy_class:
                    self.logger.error(f"策略 '{strategy_name}' 未在注册器中找到")
                    self._creation_stats['failed_creations'] += 1
                    return None

                # 生成实例名称
                if instance_name is None:
                    instance_name = strategy_name

                self.logger.debug(
                    f"创建策略实例: {strategy_name} -> {instance_name}")

                # 创建策略实例
                strategy = strategy_class(name=instance_name)

                # 设置参数
                param_count = 0
                for param_name, param_value in kwargs.items():
                    if strategy.set_parameter(param_name, param_value):
                        param_count += 1
                        self.logger.debug(
                            f"设置参数: {param_name} = {param_value}")
                    else:
                        self.logger.warning(
                            f"设置参数失败: {param_name} = {param_value}")

                self.logger.info(f"成功设置 {param_count} 个参数")

                # 验证参数
                valid, errors = strategy.validate_parameters()
                if not valid:
                    error_msg = f"参数验证失败: {'; '.join(errors)}"
                    self.logger.error(f"策略 '{strategy_name}' {error_msg}")
                    self._creation_stats['failed_creations'] += 1
                    return None

                # 缓存实例
                self._instances[instance_name] = strategy

                # 更新统计
                self._creation_stats['total_created'] += 1
                self._creation_stats['successful_creations'] += 1

                self.logger.info(f"策略实例创建成功: {instance_name}")
                return strategy

            except Exception as e:
                self.logger.error(
                    f"创建策略 '{strategy_name}' 失败: {e}", exc_info=True)
                self._creation_stats['total_created'] += 1
                self._creation_stats['failed_creations'] += 1
                return None

    def create_strategy_from_database(self, strategy_name: str, instance_name: str = None) -> Optional[BaseStrategy]:
        """从数据库创建策略实例

        Args:
            strategy_name: 策略名称
            instance_name: 实例名称，如果为None则使用策略名称

        Returns:
            策略实例或None
        """
        with self._lock:
            try:
                self.logger.info(f"开始从数据库加载策略: {strategy_name}")
                self._creation_stats['database_loads'] += 1

                # 从数据库获取策略信息
                self._ensure_database_service()
                if not self.database_service:
                    self.logger.error("DatabaseService不可用")
                    self._creation_stats['failed_database_loads'] +=1
                    return None

                # 先从数据库查找策略
                all_strategies = self.database_service.list_strategies()
                strategy_info = None
                for s in all_strategies:
                    if s['name'] == strategy_name:
                        strategy_info = s
                        break

                if not strategy_info:
                    self.logger.error(f"数据库中未找到策略: {strategy_name}")
                    self._creation_stats['failed_database_loads'] += 1
                    return None

                self.logger.debug(
                    f"从数据库获取策略信息: {strategy_info['name']}, 类型: {strategy_info['strategy_type']}")

                # 动态导入策略类
                strategy_class = self._import_strategy_class(
                    strategy_info['class_path'])
                if not strategy_class:
                    self.logger.error(
                        f"无法导入策略类: {strategy_info['class_path']}")
                    self._creation_stats['failed_database_loads'] += 1
                    return None

                # 生成实例名称
                if instance_name is None:
                    instance_name = strategy_name

                self.logger.debug(
                    f"创建数据库策略实例: {strategy_name} -> {instance_name}")

                # 创建策略实例
                strategy = strategy_class(name=instance_name)

                # 应用数据库中的参数
                parameters = self.database_service.get_strategy_parameters(strategy_info['id'])
                param_count = 0
                for param_name, param_value in parameters.items():
                    if strategy.set_parameter(param_name, param_value):
                        param_count += 1
                        self.logger.debug(
                            f"应用数据库参数: {param_name} = {param_value}")
                    else:
                        self.logger.warning(
                            f"应用数据库参数失败: {param_name} = {param_value}")

                self.logger.info(f"成功应用 {param_count} 个数据库参数")

                # 设置元数据
                strategy.metadata.update(strategy_info.get('metadata', {}))
                strategy.metadata['loaded_from_database'] = True
                strategy.metadata['database_version'] = strategy_info.get(
                    'version', '1.0.0')
                strategy.metadata['database_updated_at'] = strategy_info.get(
                    'updated_at')

                # 验证参数
                valid, errors = strategy.validate_parameters()
                if not valid:
                    error_msg = f"数据库策略参数验证失败: {'; '.join(errors)}"
                    self.logger.error(f"策略 '{strategy_name}' {error_msg}")
                    self._creation_stats['failed_database_loads'] += 1
                    return None

                # 缓存实例
                self._instances[instance_name] = strategy

                # 更新统计
                self._creation_stats['total_created'] += 1
                self._creation_stats['successful_creations'] += 1
                self._creation_stats['successful_database_loads'] += 1

                self.logger.info(f"从数据库创建策略实例成功: {instance_name}")
                return strategy

            except Exception as e:
                self.logger.error(
                    f"从数据库创建策略 '{strategy_name}' 失败: {e}", exc_info=True)
                self._creation_stats['failed_database_loads'] += 1
                return None

    def load_strategies_from_database(self, category: Optional[str] = None,
                                      strategy_type: Optional[str] = None) -> Dict[str, BaseStrategy]:
        """从数据库批量加载策略

        Args:
            category: 策略分类过滤
            strategy_type: 策略类型过滤

        Returns:
            策略名称到实例的映射
        """
        try:
            self.logger.info(
                f"开始从数据库批量加载策略: category={category}, type={strategy_type}")

            self._ensure_database_service()
            if not self.database_service:
                self.logger.warning("DatabaseService不可用")
                return {}

            # 获取策略列表
            strategies_info = self.database_service.list_strategies(
                strategy_type=strategy_type, is_active=True)
            if not strategies_info:
                self.logger.warning("数据库中没有找到匹配的策略")
                return {}

            # 如果需要按category过滤，在内存中过滤
            if category:
                strategies_info = [s for s in strategies_info if s.get('category') == category]

            self.logger.info(f"找到 {len(strategies_info)} 个策略")

            # 批量创建策略实例
            loaded_strategies = {}
            success_count = 0
            failed_count = 0

            for strategy_info in strategies_info:
                strategy_name = strategy_info['name']
                try:
                    strategy = self.create_strategy_from_database(
                        strategy_name)
                    if strategy:
                        loaded_strategies[strategy_name] = strategy
                        success_count += 1
                        self.logger.debug(f"成功加载策略: {strategy_name}")
                    else:
                        failed_count += 1
                        self.logger.warning(f"加载策略失败: {strategy_name}")
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"加载策略 '{strategy_name}' 异常: {e}")

            self.logger.info(
                f"批量加载完成: 成功 {success_count} 个, 失败 {failed_count} 个")
            return loaded_strategies

        except Exception as e:
            self.logger.error(f"批量加载策略失败: {e}", exc_info=True)
            return {}

    def save_strategy_to_database(self, instance_name: str) -> bool:
        """将策略实例保存到数据库

        Args:
            instance_name: 实例名称

        Returns:
            是否保存成功
        """
        try:
            strategy = self.get_strategy(instance_name)
            if not strategy:
                self.logger.error(f"策略实例不存在: {instance_name}")
                return False

            self._ensure_database_service()
            if not self.database_service:
                self.logger.error("DatabaseService不可用")
                return False

            self.logger.info(f"开始保存策略到数据库: {instance_name}")

            # 准备策略元数据
            metadata = {
                'name': strategy.name,
                'strategy_type': strategy.strategy_type.value,
                'version': strategy.metadata.get('version', '1.0.0'),
                'author': strategy.metadata.get('author', ''),
                'description': strategy.metadata.get('description', ''),
                'category': strategy.metadata.get('category', ''),
            }

            # 注册策略到数据库
            strategy_id = self.database_service.register_strategy(
                type(strategy), metadata)

            # 保存参数
            parameters = {}
            if hasattr(strategy, 'parameters'):
                for param_name, param in strategy.parameters.items():
                    parameters[param_name] = param

            self.database_service.save_strategy_parameters(strategy_id, parameters)

            self.logger.info(
                f"策略保存到数据库成功: {instance_name} (ID: {strategy_id})")
            return True

        except Exception as e:
            self.logger.error(
                f"保存策略到数据库失败 '{instance_name}': {e}", exc_info=True)
            return False

    def _import_strategy_class(self, class_path: str) -> Optional[Type[BaseStrategy]]:
        """动态导入策略类

        Args:
            class_path: 类路径，格式为 module.ClassName

        Returns:
            策略类或None
        """
        try:
            self.logger.debug(f"动态导入策略类: {class_path}")

            # 分离模块和类名
            module_path, class_name = class_path.rsplit('.', 1)

            # 导入模块
            module = importlib.import_module(module_path)

            # 获取类
            strategy_class = getattr(module, class_name)

            # 验证是否为策略类
            if not issubclass(strategy_class, BaseStrategy):
                self.logger.error(f"类 {class_path} 不是 BaseStrategy 的子类")
                return None

            self.logger.debug(f"成功导入策略类: {class_path}")
            return strategy_class

        except Exception as e:
            self.logger.error(f"导入策略类失败 {class_path}: {e}")
            return None

    def get_strategy(self, instance_name: str) -> Optional[BaseStrategy]:
        """获取策略实例

        Args:
            instance_name: 实例名称

        Returns:
            策略实例或None
        """
        with self._lock:
            return self._instances.get(instance_name)

    def create_multiple_strategies(self, strategy_configs: List[Dict[str, Any]]) -> Dict[str, BaseStrategy]:
        """批量创建策略实例

        Args:
            strategy_configs: 策略配置列表，每个配置包含name、instance_name和parameters

        Returns:
            实例名称到策略实例的映射
        """
        self.logger.info(f"开始批量创建策略实例: {len(strategy_configs)} 个配置")

        results = {}
        success_count = 0
        failed_count = 0

        for i, config in enumerate(strategy_configs):
            strategy_name = config.get('name')
            instance_name = config.get('instance_name')
            parameters = config.get('parameters', {})

            if not strategy_name:
                self.logger.warning(f"配置 {i+1} 缺少策略名称，跳过")
                failed_count += 1
                continue

            self.logger.debug(
                f"处理配置 {i+1}/{len(strategy_configs)}: {strategy_name}")

            try:
                strategy = self.create_strategy(
                    strategy_name=strategy_name,
                    instance_name=instance_name,
                    **parameters
                )

                if strategy:
                    final_instance_name = instance_name or strategy_name
                    results[final_instance_name] = strategy
                    success_count += 1
                    self.logger.debug(f"成功创建策略实例: {final_instance_name}")
                else:
                    failed_count += 1
                    self.logger.warning(f"创建策略实例失败: {strategy_name}")
            except Exception as e:
                failed_count += 1
                self.logger.error(f"创建策略实例异常 {strategy_name}: {e}")

        self.logger.info(f"批量创建完成: 成功 {success_count} 个, 失败 {failed_count} 个")
        return results

    def clone_strategy(self, source_instance_name: str,
                       target_instance_name: str) -> Optional[BaseStrategy]:
        """克隆策略实例

        Args:
            source_instance_name: 源实例名称
            target_instance_name: 目标实例名称

        Returns:
            克隆的策略实例或None
        """
        with self._lock:
            try:
                self.logger.info(
                    f"开始克隆策略实例: {source_instance_name} -> {target_instance_name}")

                source_strategy = self._instances.get(source_instance_name)
                if not source_strategy:
                    self.logger.error(f"源策略实例不存在: {source_instance_name}")
                    return None

                # 获取源策略的类和参数
                strategy_class = type(source_strategy)
                parameters = source_strategy.get_parameters_dict()

                self.logger.debug(
                    f"克隆策略类: {strategy_class.__name__}, 参数数量: {len(parameters)}")

                # 创建新实例
                cloned_strategy = strategy_class(name=target_instance_name)

                # 复制参数
                param_count = 0
                for param_name, param_value in parameters.items():
                    if cloned_strategy.set_parameter(param_name, param_value):
                        param_count += 1
                    else:
                        self.logger.warning(
                            f"克隆参数失败: {param_name} = {param_value}")

                self.logger.debug(f"成功克隆 {param_count} 个参数")

                # 复制元数据
                cloned_strategy.metadata = source_strategy.metadata.copy()
                cloned_strategy.metadata['cloned_from'] = source_instance_name
                cloned_strategy.metadata['cloned_at'] = str(datetime.now())

                # 缓存实例
                self._instances[target_instance_name] = cloned_strategy

                self.logger.info(f"策略实例克隆成功: {target_instance_name}")
                return cloned_strategy

            except Exception as e:
                self.logger.error(
                    f"克隆策略实例失败 '{source_instance_name}': {e}", exc_info=True)
                return None

    def remove_strategy(self, instance_name: str) -> bool:
        """移除策略实例

        Args:
            instance_name: 实例名称

        Returns:
            是否成功移除
        """
        with self._lock:
            if instance_name in self._instances:
                del self._instances[instance_name]
                self.logger.info(f"策略实例已移除: {instance_name}")
                return True
            else:
                self.logger.warning(f"尝试移除不存在的策略实例: {instance_name}")
                return False

    def list_instances(self) -> List[str]:
        """列出所有策略实例名称"""
        with self._lock:
            instances = list(self._instances.keys())
            self.logger.debug(f"当前策略实例数量: {len(instances)}")
            return instances

    def get_instance_info(self, instance_name: str) -> Optional[Dict[str, Any]]:
        """获取策略实例信息

        Args:
            instance_name: 实例名称

        Returns:
            策略实例信息或None
        """
        with self._lock:
            strategy = self._instances.get(instance_name)
            if strategy:
                self.logger.debug(f"获取策略实例信息: {instance_name}")
                return strategy.get_strategy_info()
            else:
                self.logger.warning(f"策略实例不存在: {instance_name}")
                return None

    def get_all_instances_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有策略实例信息"""
        with self._lock:
            self.logger.debug(f"获取所有策略实例信息: {len(self._instances)} 个实例")
            return {
                name: strategy.get_strategy_info()
                for name, strategy in self._instances.items()
            }

    def clear_instances(self):
        """清空所有策略实例"""
        with self._lock:
            count = len(self._instances)
            self._instances.clear()
            self.logger.info(f"已清空所有策略实例: {count} 个")

    def get_creation_stats(self) -> Dict[str, Any]:
        """获取创建统计信息"""
        with self._lock:
            stats = self._creation_stats.copy()
            stats['current_instances'] = len(self._instances)
            self.logger.debug(f"策略创建统计: {stats}")
            return stats

    def get_factory_stats(self) -> Dict[str, Any]:
        """获取工厂统计信息（别名方法）"""
        return self.get_creation_stats()

    def validate_strategy_config(self, strategy_name: str,
                                 parameters: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证策略配置

        Args:
            strategy_name: 策略名称
            parameters: 参数字典

        Returns:
            (是否有效, 错误信息列表)
        """
        try:
            self.logger.debug(f"验证策略配置: {strategy_name}")

            # 获取策略类
            strategy_class = self.registry.get_strategy_class(strategy_name)
            if not strategy_class:
                error_msg = f"策略不存在: {strategy_name}"
                self.logger.error(error_msg)
                return False, [error_msg]

            # 创建临时实例进行验证
            temp_strategy = strategy_class(name=f"temp_{strategy_name}")

            # 设置参数
            errors = []
            for param_name, param_value in parameters.items():
                if not temp_strategy.set_parameter(param_name, param_value):
                    error_msg = f"无效参数: {param_name} = {param_value}"
                    errors.append(error_msg)
                    self.logger.warning(error_msg)

            # 验证参数
            valid, validation_errors = temp_strategy.validate_parameters()
            if not valid:
                errors.extend(validation_errors)

            if errors:
                self.logger.warning(
                    f"策略配置验证失败 {strategy_name}: {len(errors)} 个错误")
            else:
                self.logger.debug(f"策略配置验证成功: {strategy_name}")

            return len(errors) == 0, errors

        except Exception as e:
            error_msg = f"验证策略配置异常 {strategy_name}: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, [error_msg]

    def get_available_strategies(self) -> List[str]:
        """获取可用策略列表"""
        strategies = self.registry.list_strategies()
        self.logger.debug(f"可用策略数量: {len(strategies)}")
        return strategies

    def get_strategy_metadata(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """获取策略元数据"""
        try:
            metadata = self.registry.get_strategy_metadata(strategy_name)
            if metadata:
                self.logger.debug(f"获取策略元数据: {strategy_name}")
            else:
                self.logger.warning(f"策略元数据不存在: {strategy_name}")
            return metadata
        except Exception as e:
            self.logger.error(f"获取策略元数据失败 {strategy_name}: {e}")
            return None

    def search_strategies(self, query: str) -> List[str]:
        """搜索策略"""
        try:
            self.logger.debug(f"搜索策略: {query}")
            available_strategies = self.get_available_strategies()

            # 简单的名称匹配搜索
            matching_strategies = [
                name for name in available_strategies
                if query.lower() in name.lower()
            ]

            self.logger.debug(f"搜索结果: 找到 {len(matching_strategies)} 个匹配策略")
            return matching_strategies
        except Exception as e:
            self.logger.error(f"搜索策略失败: {e}")
            return []

    def __len__(self) -> int:
        """返回活跃实例数量"""
        with self._lock:
            return len(self._instances)

    def __contains__(self, instance_name: str) -> bool:
        """检查实例是否存在"""
        with self._lock:
            return instance_name in self._instances

    def __iter__(self):
        """迭代器支持"""
        with self._lock:
            return iter(self._instances.values())

# 全局策略工厂实例
_strategy_factory: Optional[StrategyFactory] = None
_factory_lock = threading.RLock()

def get_strategy_factory() -> StrategyFactory:
    """获取全局策略工厂实例

    Returns:
        策略工厂实例
    """
    global _strategy_factory

    with _factory_lock:
        if _strategy_factory is None:
            from .strategy_registry import get_strategy_registry
            registry = get_strategy_registry()
            _strategy_factory = StrategyFactory(registry)

        return _strategy_factory

def initialize_strategy_factory(registry: StrategyRegistry = None) -> StrategyFactory:
    """初始化策略工厂

    Args:
        registry: 策略注册器，如果为None则使用默认注册器

    Returns:
        策略工厂实例
    """
    global _strategy_factory

    with _factory_lock:
        if registry is None:
            registry = get_strategy_registry()

        _strategy_factory = StrategyFactory(registry)
        return _strategy_factory

# 模块级别的便捷函数，用于向后兼容

def create_strategy(strategy_name: str, instance_name: str = None, **kwargs) -> Optional[BaseStrategy]:
    """创建策略实例的便捷函数

    Args:
        strategy_name: 策略名称
        instance_name: 实例名称
        **kwargs: 其他参数

    Returns:
        策略实例
    """
    factory = get_strategy_factory()
    return factory.create_strategy(strategy_name, instance_name, **kwargs)
