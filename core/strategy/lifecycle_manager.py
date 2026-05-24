from loguru import logger
"""
策略生命周期管理器 - 完整的策略生命周期管理

提供策略从创建到终止的完整生命周期管理功能
"""

import threading
import warnings
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import pandas as pd
import json

# Loguru导入已移除

from .base_strategy import BaseStrategy
from .strategy_registry import StrategyRegistry
from .strategy_factory import StrategyFactory
from .strategy_engine import StrategyEngine
from .parameter_manager import StrategyParameterManager, ParameterRange
from core.performance import UnifiedPerformanceMonitor as StrategyPerformanceEvaluator, PerformanceStats as StrategyMetrics

class LifecycleStage(Enum):
    """生命周期阶段"""
    CREATED = "created"                    # 已创建
    CONFIGURED = "configured"              # 已配置
    VALIDATED = "validated"                # 已验证
    DEPLOYED = "deployed"                  # 已部署
    RUNNING = "running"                    # 运行中
    PAUSED = "paused"                      # 已暂停
    OPTIMIZING = "optimizing"              # 优化中
    MONITORING = "monitoring"              # 监控中
    ARCHIVED = "archived"                  # 已归档
    TERMINATED = "terminated"              # 已终止

@dataclass
class StrategyLifecycleEvent:
    """策略生命周期事件"""
    timestamp: datetime
    stage: LifecycleStage
    strategy_name: str
    event_type: str
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None

@dataclass
class StrategyInstance:
    """策略实例信息"""
    name: str
    strategy_class_name: str
    current_stage: LifecycleStage
    created_at: datetime
    last_updated: datetime
    configuration: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Optional[StrategyMetrics] = None
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    lifecycle_events: List[StrategyLifecycleEvent] = field(
        default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_event(self, stage: LifecycleStage, event_type: str,
                  details: Dict[str, Any] = None, success: bool = True,
                  error_message: str = None):
        """添加生命周期事件"""
        event = StrategyLifecycleEvent(
            timestamp=datetime.now(),
            stage=stage,
            strategy_name=self.name,
            event_type=event_type,
            details=details or {},
            success=success,
            error_message=error_message
        )
        self.lifecycle_events.append(event)
        self.last_updated = datetime.now()

        if success:
            self.current_stage = stage

class StrategyLifecycleManager:
    """策略生命周期管理器 - 完整的策略生命周期管理"""

    def __init__(self):
        """初始化生命周期管理器"""
        self.logger = logger.bind(module=__name__)

        # 策略实例管理
        self._strategy_instances: Dict[str, StrategyInstance] = {}
        self._lock = threading.RLock()

        # 监控和调度
        self._monitoring_enabled = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_interval = 60  # 秒

        # 事件监听器
        self._event_listeners: List[Callable] = []

        # 统计信息
        self._lifecycle_stats = {
            'total_instances': 0,
            'active_instances': 0,
            'successful_deployments': 0,
            'failed_deployments': 0,
            'total_executions': 0,
            'optimization_runs': 0
        }

    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        return self._lifecycle_stats.copy()

    def get_strategy_lifecycle(self, strategy_name: str) -> Optional[StrategyInstance]:
        """获取策略生命周期信息

        Args:
            strategy_name: 策略名称

        Returns:
            策略实例信息或None
        """
        with self._lock:
            return self._strategy_instances.get(strategy_name)

    def register_strategy_instance(self, strategy: BaseStrategy) -> bool:
        """注册策略实例

        Args:
            strategy: 策略实例

        Returns:
            是否注册成功
        """
        try:
            with self._lock:
                instance = StrategyInstance(
                    name=strategy.name,
                    strategy_class_name=type(strategy).__name__,
                    current_stage=LifecycleStage.CREATED,
                    created_at=datetime.now(),
                    last_updated=datetime.now(),
                    configuration=strategy.get_parameters_dict(),
                    metadata=strategy.metadata.copy()
                )

                instance.add_event(
                    LifecycleStage.CREATED,
                    "strategy_registered",
                    {"strategy_class": type(strategy).__name__}
                )

                self._strategy_instances[strategy.name] = instance
                self._lifecycle_stats['total_instances'] += 1
                self._lifecycle_stats['active_instances'] += 1

                self.logger.info(f"策略实例已注册: {strategy.name}")
                return True

        except Exception as e:
            self.logger.error(f"注册策略实例失败 {strategy.name}: {e}")
            return False

    def update_strategy_stage(self, strategy_name: str, stage: LifecycleStage,
                              event_type: str = None, details: Dict[str, Any] = None) -> bool:
        """更新策略阶段

        Args:
            strategy_name: 策略名称
            stage: 新阶段
            event_type: 事件类型
            details: 事件详情

        Returns:
            是否更新成功
        """
        try:
            with self._lock:
                instance = self._strategy_instances.get(strategy_name)
                if not instance:
                    self.logger.warning(f"策略实例不存在: {strategy_name}")
                    return False

                instance.add_event(
                    stage,
                    event_type or f"stage_changed_to_{stage.value}",
                    details or {}
                )

                self.logger.debug(
                    f"策略 {strategy_name} 阶段更新: {instance.current_stage.value} -> {stage.value}")
                return True

        except Exception as e:
            self.logger.error(f"更新策略阶段失败 {strategy_name}: {e}")
            return False

    def get_all_strategy_instances(self) -> Dict[str, StrategyInstance]:
        """获取所有策略实例"""
        with self._lock:
            return self._strategy_instances.copy()

    def remove_strategy_instance(self, strategy_name: str) -> bool:
        """移除策略实例

        Args:
            strategy_name: 策略名称

        Returns:
            是否移除成功
        """
        try:
            with self._lock:
                if strategy_name in self._strategy_instances:
                    instance = self._strategy_instances[strategy_name]
                    instance.add_event(
                        LifecycleStage.TERMINATED,
                        "strategy_removed"
                    )

                    del self._strategy_instances[strategy_name]
                    self._lifecycle_stats['active_instances'] -= 1

                    self.logger.info(f"策略实例已移除: {strategy_name}")
                    return True
                else:
                    self.logger.warning(f"尝试移除不存在的策略实例: {strategy_name}")
                    return False

        except Exception as e:
            self.logger.error(f"移除策略实例失败 {strategy_name}: {e}")
            return False

    def stop_monitoring(self):
        """停止监控"""
        self._monitoring_enabled = False
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)

    def shutdown(self):
        """关闭生命周期管理器"""
        try:
            self.stop_monitoring()
            self.logger.info("生命周期管理器已关闭")
        except Exception as e:
            self.logger.error(f"关闭生命周期管理器失败: {e}")

    def __del__(self):
        """析构函数"""
        try:
            self.shutdown()
        except Exception:
            pass

# 全局生命周期管理器实例
_lifecycle_manager: Optional[StrategyLifecycleManager] = None
_manager_lock = threading.RLock()

def get_lifecycle_manager() -> StrategyLifecycleManager:
    """获取全局生命周期管理器实例

    Returns:
        生命周期管理器实例
    """
    global _lifecycle_manager

    with _manager_lock:
        if _lifecycle_manager is None:
            _lifecycle_manager = StrategyLifecycleManager()

        return _lifecycle_manager

def initialize_lifecycle_manager() -> StrategyLifecycleManager:
    """初始化生命周期管理器

    Returns:
        生命周期管理器实例
    """
    global _lifecycle_manager

    with _manager_lock:
        _lifecycle_manager = StrategyLifecycleManager()
        return _lifecycle_manager
