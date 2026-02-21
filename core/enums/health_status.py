"""
健康状态枚举定义

统一的健康状态枚举，合并了所有模块中的健康状态定义。
"""

from enum import Enum


class HealthStatus(Enum):
    """
    健康状态枚举

    合并了以下模块的健康状态定义：
    - core/services/fault_tolerance_manager.py
    - core/interfaces/data_source.py

    状态说明：
    - HEALTHY: 系统或组件运行正常，所有指标在正常范围内
    - DEGRADED: 系统或组件性能下降，但仍在运行
    - WARNING: 系统或组件出现警告，需要关注
    - CRITICAL: 系统或组件出现严重问题，需要立即处理
    - UNHEALTHY: 系统或组件不健康，无法正常工作
    - FAILED: 系统或组件已失败，无法继续运行
    - UNKNOWN: 系统或组件状态未知，无法确定健康状况
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    CRITICAL = "critical"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value

    def is_healthy(self) -> bool:
        """检查是否处于健康状态"""
        return self in (HealthStatus.HEALTHY,)

    def is_degraded(self) -> bool:
        """检查是否处于降级状态"""
        return self in (HealthStatus.DEGRADED,)

    def is_warning(self) -> bool:
        """检查是否处于警告状态"""
        return self in (HealthStatus.WARNING,)

    def is_critical(self) -> bool:
        """检查是否处于严重状态"""
        return self in (HealthStatus.CRITICAL, HealthStatus.UNHEALTHY)

    def is_failed(self) -> bool:
        """检查是否处于失败状态"""
        return self in (HealthStatus.FAILED,)

    def is_unknown(self) -> bool:
        """检查是否处于未知状态"""
        return self in (HealthStatus.UNKNOWN,)

    def needs_attention(self) -> bool:
        """检查是否需要关注（非健康状态）"""
        return self not in (HealthStatus.HEALTHY,)

    def is_operational(self) -> bool:
        """检查是否仍在运行（非失败状态）"""
        return self not in (HealthStatus.FAILED,)
