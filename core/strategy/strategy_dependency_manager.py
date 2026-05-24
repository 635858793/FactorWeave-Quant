"""
策略依赖关系管理器

提供策略之间的依赖关系管理、依赖解析和拓扑排序功能
"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class DependencyType(Enum):
    """依赖类型"""
    REQUIRED = "required"      # 必需依赖
    OPTIONAL = "optional"      # 可选依赖
    CONFLICT = "conflict"      # 冲突依赖


@dataclass
class StrategyDependency:
    """策略依赖定义"""
    strategy_name: str
    dependency_name: str
    dependency_type: DependencyType
    version_requirement: Optional[str] = None
    description: str = ""


@dataclass
class StrategyDependencyGraph:
    """策略依赖图"""
    
    def __init__(self):
        self._dependencies: Dict[str, List[StrategyDependency]] = {}
        self._reverse_dependencies: Dict[str, List[StrategyDependency]] = {}
        self._lock = object()
    
    def add_dependency(self, dependency: StrategyDependency):
        """添加依赖关系"""
        with self._lock:
            if dependency.strategy_name not in self._dependencies:
                self._dependencies[dependency.strategy_name] = []
            
            self._dependencies[dependency.strategy_name].append(dependency)
            
            if dependency.dependency_name not in self._reverse_dependencies:
                self._reverse_dependencies[dependency.dependency_name] = []
            
            self._reverse_dependencies[dependency.dependency_name].append(dependency)
            
            logger.debug(f"添加依赖: {dependency.strategy_name} -> {dependency.dependency_name}")
    
    def remove_dependency(self, strategy_name: str, dependency_name: str):
        """移除依赖关系"""
        with self._lock:
            if strategy_name in self._dependencies:
                self._dependencies[strategy_name] = [
                    dep for dep in self._dependencies[strategy_name]
                    if dep.dependency_name != dependency_name
                ]
            
            if dependency_name in self._reverse_dependencies:
                self._reverse_dependencies[dependency_name] = [
                    dep for dep in self._reverse_dependencies[dependency_name]
                    if dep.strategy_name != strategy_name
                ]
            
            logger.debug(f"移除依赖: {strategy_name} -> {dependency_name}")
    
    def get_dependencies(self, strategy_name: str) -> List[StrategyDependency]:
        """获取策略的所有依赖"""
        return self._dependencies.get(strategy_name, [])
    
    def get_dependents(self, strategy_name: str) -> List[StrategyDependency]:
        """获取依赖该策略的所有策略"""
        return self._reverse_dependencies.get(strategy_name, [])
    
    def has_circular_dependency(self) -> Optional[List[str]]:
        """检测循环依赖
        
        Returns:
            Optional[List[str]]: 如果存在循环依赖，返回循环中的策略名称列表；否则返回None
        """
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            if node in rec_stack:
                cycle_start = path.index(node)
                return path[cycle_start:]
            
            if node in visited:
                return None
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for dep in self._dependencies.get(node, []):
                result = dfs(dep.dependency_name, path)
                if result:
                    return result
            
            rec_stack.remove(node)
            path.pop()
            return None
        
        for strategy in self._dependencies.keys():
            cycle = dfs(strategy, [])
            if cycle:
                logger.warning(f"检测到循环依赖: {' -> '.join(cycle)}")
                return cycle
        
        return None
    
    def topological_sort(self) -> Tuple[bool, List[str]]:
        """拓扑排序
        
        Returns:
            Tuple[bool, List[str]]: (是否成功, 排序后的策略名称列表)
        """
        in_degree = {strategy: 0 for strategy in self._dependencies.keys()}
        
        for deps in self._dependencies.values():
            for dep in deps:
                if dep.dependency_name in in_degree:
                    in_degree[dep.dependency_name] += 1
        
        queue = [strategy for strategy, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            for dep in self._dependencies.get(current, []):
                if dep.dependency_name in in_degree:
                    in_degree[dep.dependency_name] -= 1
                    if in_degree[dep.dependency_name] == 0:
                        queue.append(dep.dependency_name)
        
        if len(result) != len(in_degree):
            logger.error("拓扑排序失败：存在循环依赖")
            return False, []
        
        return True, result
    
    def get_execution_order(self, strategy_names: List[str]) -> Tuple[bool, List[str]]:
        """获取策略执行顺序
        
        Args:
            strategy_names: 需要执行的策略名称列表
            
        Returns:
            Tuple[bool, List[str]]: (是否成功, 执行顺序列表)
        """
        relevant_graph = StrategyDependencyGraph()
        
        for strategy in strategy_names:
            for dep in self._dependencies.get(strategy, []):
                if dep.dependency_name in strategy_names:
                    relevant_graph.add_dependency(dep)
        
        return relevant_graph.topological_sort()
    
    def validate_dependencies(self, strategy_names: List[str]) -> Tuple[bool, List[str]]:
        """验证依赖关系
        
        Args:
            strategy_names: 需要验证的策略名称列表
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误消息列表)
        """
        errors = []
        strategy_set = set(strategy_names)
        
        for strategy in strategy_names:
            for dep in self._dependencies.get(strategy, []):
                if dep.dependency_name not in strategy_set:
                    if dep.dependency_type == DependencyType.REQUIRED:
                        errors.append(f"策略 {strategy} 缺少必需依赖: {dep.dependency_name}")
                    else:
                        logger.warning(f"策略 {strategy} 缺少可选依赖: {dep.dependency_name}")
                
                if dep.dependency_type == DependencyType.CONFLICT:
                    if dep.dependency_name in strategy_set:
                        errors.append(f"策略 {strategy} 与 {dep.dependency_name} 存在冲突")
        
        cycle = self.has_circular_dependency()
        if cycle:
            errors.append(f"存在循环依赖: {' -> '.join(cycle)}")
        
        return len(errors) == 0, errors
    
    def get_dependency_tree(self, strategy_name: str, level: int = 0) -> List[Tuple[int, str]]:
        """获取依赖树
        
        Args:
            strategy_name: 策略名称
            level: 当前层级
            
        Returns:
            List[Tuple[int, str]]: (层级, 策略名称) 列表
        """
        result = [(level, strategy_name)]
        
        for dep in self._dependencies.get(strategy_name, []):
            result.extend(self.get_dependency_tree(dep.dependency_name, level + 1))
        
        return result
    
    def clear(self):
        """清空依赖图"""
        with self._lock:
            self._dependencies.clear()
            self._reverse_dependencies.clear()
            logger.debug("依赖图已清空")


class StrategyDependencyManager:
    """策略依赖管理器"""
    
    def __init__(self):
        self.graph = StrategyDependencyGraph()
        self._strategy_versions: Dict[str, str] = {}
        self._lock = object()
    
    def register_strategy(self, strategy_name: str, version: str = "1.0.0"):
        """注册策略
        
        Args:
            strategy_name: 策略名称
            version: 策略版本
        """
        with self._lock:
            self._strategy_versions[strategy_name] = version
            logger.debug(f"注册策略: {strategy_name} v{version}")
    
    def add_dependency(self, strategy_name: str, dependency_name: str,
                   dependency_type: DependencyType = DependencyType.REQUIRED,
                   version_requirement: Optional[str] = None,
                   description: str = ""):
        """添加策略依赖
        
        Args:
            strategy_name: 策略名称
            dependency_name: 依赖的策略名称
            dependency_type: 依赖类型
            version_requirement: 版本要求
            description: 依赖描述
        """
        dependency = StrategyDependency(
            strategy_name=strategy_name,
            dependency_name=dependency_name,
            dependency_type=dependency_type,
            version_requirement=version_requirement,
            description=description
        )
        self.graph.add_dependency(dependency)
    
    def remove_strategy(self, strategy_name: str):
        """移除策略及其依赖关系
        
        Args:
            strategy_name: 策略名称
        """
        with self._lock:
            deps = self.graph.get_dependencies(strategy_name)
            for dep in deps:
                self.graph.remove_dependency(strategy_name, dep.dependency_name)
            
            dependents = self.graph.get_dependents(strategy_name)
            for dep in dependents:
                self.graph.remove_dependency(dep.strategy_name, strategy_name)
            
            if strategy_name in self._strategy_versions:
                del self._strategy_versions[strategy_name]
            
            logger.info(f"移除策略: {strategy_name}")
    
    def get_execution_order(self, strategy_names: List[str]) -> Tuple[bool, List[str]]:
        """获取策略执行顺序
        
        Args:
            strategy_names: 需要执行的策略名称列表
            
        Returns:
            Tuple[bool, List[str]]: (是否成功, 执行顺序列表)
        """
        valid, errors = self.graph.validate_dependencies(strategy_names)
        if not valid:
            logger.error(f"依赖验证失败: {errors}")
            return False, []
        
        return self.graph.get_execution_order(strategy_names)
    
    def validate_strategies(self, strategy_names: List[str]) -> Tuple[bool, List[str]]:
        """验证策略依赖关系
        
        Args:
            strategy_names: 策略名称列表
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误消息列表)
        """
        return self.graph.validate_dependencies(strategy_names)
    
    def get_dependency_tree(self, strategy_name: str) -> List[Tuple[int, str]]:
        """获取策略依赖树
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            List[Tuple[int, str]]: (层级, 策略名称) 列表
        """
        return self.graph.get_dependency_tree(strategy_name)
    
    def has_circular_dependency(self) -> Optional[List[str]]:
        """检测循环依赖
        
        Returns:
            Optional[List[str]]: 如果存在循环依赖，返回循环中的策略名称列表；否则返回None
        """
        return self.graph.has_circular_dependency()
    
    def get_all_strategies(self) -> List[str]:
        """获取所有注册的策略"""
        return list(self._strategy_versions.keys())
    
    def get_strategy_version(self, strategy_name: str) -> Optional[str]:
        """获取策略版本
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            Optional[str]: 策略版本，如果策略不存在则返回None
        """
        return self._strategy_versions.get(strategy_name)
    
    def clear(self):
        """清空所有策略和依赖关系"""
        self.graph.clear()
        with self._lock:
            self._strategy_versions.clear()
            logger.info("策略依赖管理器已清空")


def get_strategy_dependency_manager() -> StrategyDependencyManager:
    """获取策略依赖管理器单例"""
    if not hasattr(get_strategy_dependency_manager, '_instance'):
        get_strategy_dependency_manager._instance = StrategyDependencyManager()
    return get_strategy_dependency_manager._instance
