"""
统一熔断器接口定义

本模块定义了FactorWeave-Quant系统中熔断器组件的统一接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from enum import Enum
import asyncio


class CircuitBreakerState(Enum):
    """熔断器状态枚举"""
    CLOSED = "closed"      # 关闭状态，正常执行
    OPEN = "open"          # 打开状态，拒绝执行
    HALF_OPEN = "half_open"  # 半开状态，试探性执行


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""

    # 基础配置
    failure_threshold: int = 5        # 失败阈值
    recovery_timeout: int = 60        # 恢复超时(秒)
    half_open_max_calls: int = 3      # 半开状态最大调用次数

    # 高级配置
    failure_rate_threshold: float = 0.5  # 失败率阈值
    window_size: int = 100               # 滑动窗口大小
    min_calls_threshold: int = 10        # 最小调用次数阈值

    # 自适应配置
    adaptive_threshold: bool = False     # 是否启用自适应阈值
    initial_threshold: int = 5           # 初始阈值
    threshold_adjustment_factor: float = 0.1  # 阈值调整因子

    # 监控配置
    enable_metrics: bool = True          # 是否启用指标收集
    metrics_window: int = 300            # 指标窗口(秒)

    # 扩展配置
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitBreakerMetrics:
    """熔断器指标"""

    # 基础统计
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0

    # 状态统计
    state_changes: int = 0
    last_state_change: Optional[datetime] = None
    current_state: CircuitBreakerState = CircuitBreakerState.CLOSED

    # 性能统计
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = float('inf')

    # 时间统计
    start_time: datetime = field(default_factory=datetime.now)
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.successful_calls / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def failure_rate(self) -> float:
        """失败率"""
        return self.failed_calls / self.total_calls if self.total_calls > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        from dataclasses import asdict
        result = asdict(self)
        result['success_rate'] = self.success_rate
        result['failure_rate'] = self.failure_rate
        result['current_state'] = self.current_state.value
        result['start_time'] = self.start_time.isoformat()
        if self.last_state_change:
            result['last_state_change'] = self.last_state_change.isoformat()
        if self.last_success_time:
            result['last_success_time'] = self.last_success_time.isoformat()
        if self.last_failure_time:
            result['last_failure_time'] = self.last_failure_time.isoformat()
        return result


class ICircuitBreaker(ABC):
    """统一熔断器接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """熔断器名称"""
        pass

    @property
    @abstractmethod
    def state(self) -> CircuitBreakerState:
        """当前状态"""
        pass

    @abstractmethod
    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """执行受保护的操作

        Args:
            operation: 要执行的操作
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Any: 操作结果

        Raises:
            CircuitBreakerOpenError: 熔断器打开时抛出
            Exception: 操作执行异常
        """
        pass

    @abstractmethod
    async def can_execute(self) -> bool:
        """检查是否可以执行操作

        Returns:
            bool: 是否可以执行
        """
        pass

    @abstractmethod
    async def record_success(self, response_time: float) -> None:
        """记录成功执行

        Args:
            response_time: 响应时间(秒)
        """
        pass

    @abstractmethod
    async def record_failure(self, error: Exception, response_time: float = 0.0) -> None:
        """记录失败执行

        Args:
            error: 异常信息
            response_time: 响应时间(秒)
        """
        pass

    @abstractmethod
    async def get_metrics(self) -> CircuitBreakerMetrics:
        """获取熔断器指标

        Returns:
            CircuitBreakerMetrics: 指标信息
        """
        pass

    @abstractmethod
    async def reset(self) -> None:
        """重置熔断器状态"""
        pass

    async def force_open(self) -> None:
        """强制打开熔断器"""
        # 默认实现，子类可以重写
        pass

    async def force_close(self) -> None:
        """强制关闭熔断器"""
        # 默认实现，子类可以重写
        pass

    async def get_health_score(self) -> float:
        """获取健康分数 (0-1)

        Returns:
            float: 健康分数
        """
        metrics = await self.get_metrics()
        if metrics.total_calls == 0:
            return 1.0

        # 基于成功率和响应时间计算健康分数
        success_score = metrics.success_rate

        # 响应时间分数 (假设1秒以内为满分)
        time_score = max(0, 1 - (metrics.avg_response_time - 1.0) * 0.1) if metrics.avg_response_time > 1.0 else 1.0

        # 状态分数
        state_score = 1.0 if self.state == CircuitBreakerState.CLOSED else 0.5 if self.state == CircuitBreakerState.HALF_OPEN else 0.0

        # 综合分数
        return (success_score * 0.5 + time_score * 0.3 + state_score * 0.2)


class CircuitBreakerError(Exception):
    """熔断器异常基类"""

    def __init__(self, message: str, circuit_breaker_name: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.circuit_breaker_name = circuit_breaker_name


class CircuitBreakerOpenError(CircuitBreakerError):
    """熔断器打开异常"""
    pass


class CircuitBreakerConfigError(CircuitBreakerError):
    """熔断器配置异常"""
    pass


class CircuitBreakerNotFoundError(CircuitBreakerError):
    """熔断器未找到异常"""
    pass
