"""
告警去重服务

提供告警消息去重、聚合和管理功能，避免重复告警对系统造成干扰。
支持基于时间窗口、消息内容、告警级别等多种去重策略。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2025-09-29
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import hashlib
import json

from loguru import logger


class AlertLevel(Enum):
    """告警级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertMessage:
    """告警消息"""
    id: str
    level: AlertLevel
    category: str
    message: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_resolved: bool = False
    resolution_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "level": self.level.value,
            "category": self.category,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "is_resolved": self.is_resolved,
            "resolution_time": self.resolution_time.isoformat() if self.resolution_time else None
        }

    def get_fingerprint(self) -> str:
        """获取告警指纹用于去重"""
        content = f"{self.category}:{self.message}:{self.source}"
        return hashlib.md5(content.encode()).hexdigest()


class DeduplicationStrategy(Enum):
    """去重策略"""
    TIME_WINDOW = "time_window"      # 时间窗口去重
    CONTENT_HASH = "content_hash"    # 内容哈希去重
    LEVEL_BASED = "level_based"      # 基于级别去重
    HYBRID = "hybrid"                # 混合策略


@dataclass
class DeduplicationConfig:
    """去重配置"""
    strategy: DeduplicationStrategy = DeduplicationStrategy.HYBRID
    time_window_minutes: int = 5
    max_duplicates: int = 10
    level_weights: Dict[AlertLevel, float] = field(default_factory=lambda: {
        AlertLevel.DEBUG: 0.1,
        AlertLevel.INFO: 0.3,
        AlertLevel.WARNING: 0.5,
        AlertLevel.ERROR: 0.8,
        AlertLevel.CRITICAL: 1.0
    })


class AlertDeduplicationService:
    """
    告警去重服务

    提供智能的告警去重功能，避免重复告警对系统造成干扰。
    支持多种去重策略和配置选项。
    """

    def __init__(self, config: DeduplicationConfig = None):
        """
        初始化告警去重服务

        Args:
            config: 去重配置
        """
        self.config = config or DeduplicationConfig()
        self.logger = logger.bind(module="AlertDeduplicationService")

        # 告警存储
        self._alerts: Dict[str, AlertMessage] = {}
        self._alert_history: deque = deque(maxlen=10000)

        # 去重统计
        self._dedup_stats = {
            "total_alerts": 0,
            "deduplicated_alerts": 0,
            "active_alerts": 0,
            "resolved_alerts": 0
        }

        # 线程安全
        self._lock = threading.RLock()

        # 清理定时器
        self._cleanup_timer = None
        self._start_cleanup_timer()

        self.logger.info("告警去重服务初始化完成")

    def process_alert(self, level: AlertLevel, category: str, message: str,
                      source: str, metadata: Dict[str, Any] = None) -> Optional[AlertMessage]:
        """
        处理告警消息

        Args:
            level: 告警级别
            category: 告警类别
            message: 告警消息
            source: 告警源
            metadata: 元数据

        Returns:
            AlertMessage: 如果是新告警则返回告警对象，如果被去重则返回None
        """
        with self._lock:
            # 创建告警消息
            alert_id = self._generate_alert_id(level, category, message, source)
            alert = AlertMessage(
                id=alert_id,
                level=level,
                category=category,
                message=message,
                source=source,
                metadata=metadata or {}
            )

            # 检查是否需要去重
            if self._should_deduplicate(alert):
                self._dedup_stats["deduplicated_alerts"] += 1
                self.logger.debug(f"告警被去重: {alert.id}")
                return None

            # 存储告警
            self._alerts[alert.id] = alert
            self._alert_history.append(alert)

            # 更新统计
            self._dedup_stats["total_alerts"] += 1
            self._dedup_stats["active_alerts"] += 1

            self.logger.info(f"新告警: {alert.level.value} - {alert.category} - {alert.message}")
            return alert

    def resolve_alert(self, alert_id: str) -> bool:
        """
        解决告警

        Args:
            alert_id: 告警ID

        Returns:
            bool: 是否成功解决
        """
        with self._lock:
            if alert_id in self._alerts:
                alert = self._alerts[alert_id]
                alert.is_resolved = True
                alert.resolution_time = datetime.now()

                self._dedup_stats["active_alerts"] -= 1
                self._dedup_stats["resolved_alerts"] += 1

                self.logger.info(f"告警已解决: {alert_id}")
                return True

            return False

    def get_active_alerts(self, level: AlertLevel = None,
                          category: str = None) -> List[AlertMessage]:
        """
        获取活跃告警

        Args:
            level: 过滤级别
            category: 过滤类别

        Returns:
            List[AlertMessage]: 活跃告警列表
        """
        with self._lock:
            alerts = [alert for alert in self._alerts.values() if not alert.is_resolved]

            if level:
                alerts = [alert for alert in alerts if alert.level == level]

            if category:
                alerts = [alert for alert in alerts if alert.category == category]

            return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def get_alert_history(self, hours: int = 24) -> List[AlertMessage]:
        """
        获取告警历史

        Args:
            hours: 历史时间范围（小时）

        Returns:
            List[AlertMessage]: 历史告警列表
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            history = [alert for alert in self._alert_history
                       if alert.timestamp >= cutoff_time]

            return sorted(history, key=lambda x: x.timestamp, reverse=True)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取去重统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._lock:
            stats = self._dedup_stats.copy()

            # 计算去重率
            total = stats["total_alerts"] + stats["deduplicated_alerts"]
            if total > 0:
                stats["deduplication_rate"] = stats["deduplicated_alerts"] / total
            else:
                stats["deduplication_rate"] = 0.0

            # 添加级别分布
            level_distribution = defaultdict(int)
            for alert in self._alerts.values():
                level_distribution[alert.level.value] += 1

            stats["level_distribution"] = dict(level_distribution)

            return stats

    def _should_deduplicate(self, alert: AlertMessage) -> bool:
        """
        判断是否应该去重

        Args:
            alert: 告警消息

        Returns:
            bool: 是否应该去重
        """
        if self.config.strategy == DeduplicationStrategy.TIME_WINDOW:
            return self._check_time_window_dedup(alert)
        elif self.config.strategy == DeduplicationStrategy.CONTENT_HASH:
            return self._check_content_hash_dedup(alert)
        elif self.config.strategy == DeduplicationStrategy.LEVEL_BASED:
            return self._check_level_based_dedup(alert)
        elif self.config.strategy == DeduplicationStrategy.HYBRID:
            return self._check_hybrid_dedup(alert)

        return False

    def _check_time_window_dedup(self, alert: AlertMessage) -> bool:
        """时间窗口去重检查"""
        fingerprint = alert.get_fingerprint()
        cutoff_time = datetime.now() - timedelta(minutes=self.config.time_window_minutes)

        # 检查相同指纹的告警
        similar_alerts = [
            existing_alert for existing_alert in self._alerts.values()
            if (existing_alert.get_fingerprint() == fingerprint and
                existing_alert.timestamp >= cutoff_time and
                not existing_alert.is_resolved)
        ]

        return len(similar_alerts) >= self.config.max_duplicates

    def _check_content_hash_dedup(self, alert: AlertMessage) -> bool:
        """内容哈希去重检查"""
        fingerprint = alert.get_fingerprint()

        # 检查是否存在相同指纹的活跃告警
        for existing_alert in self._alerts.values():
            if (existing_alert.get_fingerprint() == fingerprint and
                    not existing_alert.is_resolved):
                return True

        return False

    def _check_level_based_dedup(self, alert: AlertMessage) -> bool:
        """基于级别的去重检查"""
        # 高级别告警不去重
        if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            return False

        # 低级别告警更容易被去重
        fingerprint = alert.get_fingerprint()
        level_weight = self.config.level_weights.get(alert.level, 0.5)
        max_allowed = int(self.config.max_duplicates * level_weight)

        similar_count = sum(1 for existing_alert in self._alerts.values()
                            if (existing_alert.get_fingerprint() == fingerprint and
                                not existing_alert.is_resolved))

        return similar_count >= max_allowed

    def _check_hybrid_dedup(self, alert: AlertMessage) -> bool:
        """混合策略去重检查"""
        # 结合时间窗口和级别策略
        return (self._check_time_window_dedup(alert) or
                self._check_level_based_dedup(alert))

    def _generate_alert_id(self, level: AlertLevel, category: str,
                           message: str, source: str) -> str:
        """生成告警ID"""
        content = f"{level.value}:{category}:{message}:{source}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _start_cleanup_timer(self) -> None:
        """启动清理定时器"""
        def cleanup():
            self._cleanup_expired_alerts()
            # 重新设置定时器
            self._cleanup_timer = threading.Timer(300, cleanup)  # 5分钟清理一次
            self._cleanup_timer.daemon = True
            self._cleanup_timer.start()

        self._cleanup_timer = threading.Timer(300, cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup_expired_alerts(self) -> None:
        """清理过期告警"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=24)
            expired_ids = []

            for alert_id, alert in self._alerts.items():
                if alert.timestamp < cutoff_time and alert.is_resolved:
                    expired_ids.append(alert_id)

            for alert_id in expired_ids:
                del self._alerts[alert_id]

            if expired_ids:
                self.logger.info(f"清理了 {len(expired_ids)} 个过期告警")

    def dispose(self) -> None:
        """清理资源"""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()

        self.logger.info("告警去重服务已停止")


# 全局服务实例
_alert_deduplication_service: Optional[AlertDeduplicationService] = None


def get_alert_deduplication_service(config: DeduplicationConfig = None) -> AlertDeduplicationService:
    """
    获取告警去重服务的全局实例

    Args:
        config: 去重配置

    Returns:
        AlertDeduplicationService: 服务实例
    """
    global _alert_deduplication_service

    if _alert_deduplication_service is None:
        _alert_deduplication_service = AlertDeduplicationService(config)

    return _alert_deduplication_service


def initialize_alert_deduplication_service(config=None) -> AlertDeduplicationService:
    """
    初始化告警去重服务

    Args:
        config: 去重配置

    Returns:
        AlertDeduplicationService: 服务实例
    """
    global _alert_deduplication_service

    if _alert_deduplication_service is not None:
        _alert_deduplication_service.dispose()

    _alert_deduplication_service = AlertDeduplicationService(config)
    return _alert_deduplication_service
