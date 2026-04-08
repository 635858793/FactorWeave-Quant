"""
告警规则引擎

提供灵活的告警规则定义、评估和执行功能。
支持多种告警条件、动作和通知方式。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2025-09-29
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import re
from abc import ABC, abstractmethod

from loguru import logger
from .alert_deduplication_service import AlertDeduplicationService, AlertLevel, AlertMessage


class RuleConditionType(Enum):
    """规则条件类型"""
    THRESHOLD = "threshold"          # 阈值条件
    TREND = "trend"                 # 趋势条件
    PATTERN = "pattern"             # 模式条件
    COMPOSITE = "composite"         # 复合条件
    CUSTOM = "custom"               # 自定义条件


class RuleActionType(Enum):
    """规则动作类型"""
    LOG = "log"                     # 记录日志
    EMAIL = "email"                 # 发送邮件
    SMS = "sms"                     # 发送短信
    WEBHOOK = "webhook"             # 调用Webhook
    CALLBACK = "callback"           # 执行回调函数
    CUSTOM = "custom"               # 自定义动作


@dataclass
class RuleCondition:
    """规则条件"""
    condition_type: RuleConditionType
    metric_name: str
    operator: str  # >, <, >=, <=, ==, !=, contains, matches
    threshold_value: Any
    time_window_minutes: int = 5
    evaluation_frequency_seconds: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, current_value: Any, historical_values: List[Any] = None) -> bool:
        """
        评估条件是否满足

        Args:
            current_value: 当前值
            historical_values: 历史值列表

        Returns:
            bool: 条件是否满足
        """
        try:
            if self.condition_type == RuleConditionType.THRESHOLD:
                return self._evaluate_threshold(current_value)
            elif self.condition_type == RuleConditionType.TREND:
                return self._evaluate_trend(current_value, historical_values or [])
            elif self.condition_type == RuleConditionType.PATTERN:
                return self._evaluate_pattern(current_value)
            else:
                return False
        except Exception as e:
            logger.error(f"条件评估失败: {e}")
            return False

    def _evaluate_threshold(self, current_value: Any) -> bool:
        """评估阈值条件"""
        try:
            if self.operator == ">":
                return float(current_value) > float(self.threshold_value)
            elif self.operator == "<":
                return float(current_value) < float(self.threshold_value)
            elif self.operator == ">=":
                return float(current_value) >= float(self.threshold_value)
            elif self.operator == "<=":
                return float(current_value) <= float(self.threshold_value)
            elif self.operator == "==":
                return current_value == self.threshold_value
            elif self.operator == "!=":
                return current_value != self.threshold_value
            elif self.operator == "contains":
                return str(self.threshold_value) in str(current_value)
            elif self.operator == "matches":
                return bool(re.match(str(self.threshold_value), str(current_value)))
            else:
                return False
        except (ValueError, TypeError):
            return False

    def _evaluate_trend(self, current_value: Any, historical_values: List[Any]) -> bool:
        """评估趋势条件"""
        if len(historical_values) < 2:
            return False

        try:
            values = [float(v) for v in historical_values] + [float(current_value)]

            if self.operator == "increasing":
                return all(values[i] < values[i+1] for i in range(len(values)-1))
            elif self.operator == "decreasing":
                return all(values[i] > values[i+1] for i in range(len(values)-1))
            elif self.operator == "stable":
                threshold = float(self.threshold_value)
                return all(abs(values[i] - values[i+1]) <= threshold for i in range(len(values)-1))
            else:
                return False
        except (ValueError, TypeError):
            return False

    def _evaluate_pattern(self, current_value: Any) -> bool:
        """评估模式条件"""
        try:
            pattern = str(self.threshold_value)
            value = str(current_value)

            if self.operator == "regex":
                return bool(re.search(pattern, value))
            elif self.operator == "contains_all":
                keywords = pattern.split(",")
                return all(keyword.strip() in value for keyword in keywords)
            elif self.operator == "contains_any":
                keywords = pattern.split(",")
                return any(keyword.strip() in value for keyword in keywords)
            else:
                return False
        except Exception:
            return False


@dataclass
class RuleAction:
    """规则动作"""
    action_type: RuleActionType
    target: str  # 目标地址、函数名等
    template: str = ""  # 消息模板
    parameters: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 3
    retry_delay_seconds: int = 60

    async def execute(self, alert_context: Dict[str, Any]) -> bool:
        """
        执行动作

        Args:
            alert_context: 告警上下文

        Returns:
            bool: 执行是否成功
        """
        try:
            if self.action_type == RuleActionType.LOG:
                return self._execute_log(alert_context)
            elif self.action_type == RuleActionType.EMAIL:
                return await self._execute_email(alert_context)
            elif self.action_type == RuleActionType.WEBHOOK:
                return await self._execute_webhook(alert_context)
            elif self.action_type == RuleActionType.CALLBACK:
                return self._execute_callback(alert_context)
            else:
                logger.warning(f"不支持的动作类型: {self.action_type}")
                return False
        except Exception as e:
            logger.error(f"动作执行失败: {e}")
            return False

    def _execute_log(self, alert_context: Dict[str, Any]) -> bool:
        """执行日志动作"""
        message = self._format_message(alert_context)
        level = alert_context.get("level", AlertLevel.INFO)

        if level == AlertLevel.CRITICAL:
            logger.critical(message)
        elif level == AlertLevel.ERROR:
            logger.error(message)
        elif level == AlertLevel.WARNING:
            logger.warning(message)
        else:
            logger.info(message)

        return True

    async def _execute_email(self, alert_context: Dict[str, Any]) -> bool:
        """执行邮件动作"""
        # 这里应该集成邮件发送服务
        message = self._format_message(alert_context)
        logger.info(f"发送邮件到 {self.target}: {message}")
        return True

    async def _execute_webhook(self, alert_context: Dict[str, Any]) -> bool:
        """执行Webhook动作"""
        # 这里应该发送HTTP请求
        message = self._format_message(alert_context)
        logger.info(f"调用Webhook {self.target}: {message}")
        return True

    def _execute_callback(self, alert_context: Dict[str, Any]) -> bool:
        """执行回调动作"""
        # 这里应该调用注册的回调函数
        callback_name = self.target
        logger.info(f"执行回调 {callback_name}")
        return True

    def _format_message(self, alert_context: Dict[str, Any]) -> str:
        """格式化消息"""
        if not self.template:
            return json.dumps(alert_context, ensure_ascii=False, indent=2)

        try:
            return self.template.format(**alert_context)
        except KeyError as e:
            logger.warning(f"模板格式化失败，缺少参数: {e}")
            return str(alert_context)


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str
    name: str
    description: str
    conditions: List[RuleCondition]
    actions: List[RuleAction]
    level: AlertLevel = AlertLevel.WARNING
    category: str = "system"
    enabled: bool = True
    cooldown_minutes: int = 5  # 冷却时间，避免频繁告警
    max_executions_per_hour: int = 10  # 每小时最大执行次数
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 运行时状态
    last_execution: Optional[datetime] = None
    execution_count: int = 0
    last_reset_hour: int = field(default_factory=lambda: datetime.now().hour)

    def should_execute(self) -> bool:
        """判断是否应该执行规则"""
        if not self.enabled:
            return False

        now = datetime.now()

        # 检查冷却时间
        if (self.last_execution and
                now - self.last_execution < timedelta(minutes=self.cooldown_minutes)):
            return False

        # 检查每小时执行次数限制
        current_hour = now.hour
        if current_hour != self.last_reset_hour:
            self.execution_count = 0
            self.last_reset_hour = current_hour

        if self.execution_count >= self.max_executions_per_hour:
            return False

        return True

    def mark_executed(self) -> None:
        """标记规则已执行"""
        self.last_execution = datetime.now()
        self.execution_count += 1

    async def evaluate_and_execute(self, metrics: Dict[str, Any],
                                   historical_data: Dict[str, List[Any]] = None) -> bool:
        """
        评估条件并执行动作

        Args:
            metrics: 当前指标值
            historical_data: 历史数据

        Returns:
            bool: 是否触发了告警
        """
        if not self.should_execute():
            return False

        # 评估所有条件
        conditions_met = True
        for condition in self.conditions:
            metric_value = metrics.get(condition.metric_name)
            if metric_value is None:
                conditions_met = False
                break

            historical_values = historical_data.get(condition.metric_name, []) if historical_data else []
            if not condition.evaluate(metric_value, historical_values):
                conditions_met = False
                break

        if not conditions_met:
            return False

        # 执行所有动作
        alert_context = {
            "rule_id": self.rule_id,
            "rule_name": self.name,
            "level": self.level,
            "category": self.category,
            "description": self.description,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
            "tags": self.tags
        }

        success_count = 0
        for action in self.actions:
            try:
                if await action.execute(alert_context):
                    success_count += 1
            except Exception as e:
                logger.error(f"动作执行失败: {e}")

        # 标记已执行
        self.mark_executed()

        logger.info(f"规则 {self.name} 触发告警，执行了 {success_count}/{len(self.actions)} 个动作")
        return True


class AlertRuleEngine:
    """
    告警规则引擎

    管理告警规则的注册、评估和执行。
    支持实时监控和批量处理。
    """

    def __init__(self, dedup_service: AlertDeduplicationService = None):
        """
        初始化告警规则引擎

        Args:
            dedup_service: 告警去重服务
        """
        self.dedup_service = dedup_service
        self.logger = logger.bind(module="AlertRuleEngine")

        # 规则存储
        self._rules: Dict[str, AlertRule] = {}
        self._rule_lock = threading.RLock()

        # 监控状态
        self._monitoring = False
        self._monitor_task = None
        self._monitor_interval = 60  # 秒

        # 指标数据缓存
        self._metrics_cache: Dict[str, Any] = {}
        self._historical_cache: Dict[str, List[Any]] = {}
        self._cache_lock = threading.RLock()

        # 统计信息
        self._stats = {
            "total_rules": 0,
            "active_rules": 0,
            "total_evaluations": 0,
            "triggered_alerts": 0,
            "failed_evaluations": 0
        }

        self.logger.info("告警规则引擎初始化完成")

    def add_rule(self, rule: AlertRule) -> bool:
        """
        添加告警规则

        Args:
            rule: 告警规则

        Returns:
            bool: 添加是否成功
        """
        with self._rule_lock:
            if rule.rule_id in self._rules:
                self.logger.warning(f"规则 {rule.rule_id} 已存在，将被覆盖")

            self._rules[rule.rule_id] = rule
            self._update_stats()

            self.logger.info(f"添加告警规则: {rule.name} ({rule.rule_id})")
            return True

    def remove_rule(self, rule_id: str) -> bool:
        """
        移除告警规则

        Args:
            rule_id: 规则ID

        Returns:
            bool: 移除是否成功
        """
        with self._rule_lock:
            if rule_id in self._rules:
                rule = self._rules.pop(rule_id)
                self._update_stats()
                self.logger.info(f"移除告警规则: {rule.name} ({rule_id})")
                return True

            return False

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """
        获取告警规则

        Args:
            rule_id: 规则ID

        Returns:
            Optional[AlertRule]: 规则对象
        """
        with self._rule_lock:
            return self._rules.get(rule_id)

    def list_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """
        列出所有规则

        Args:
            enabled_only: 是否只返回启用的规则

        Returns:
            List[AlertRule]: 规则列表
        """
        with self._rule_lock:
            rules = list(self._rules.values())

            if enabled_only:
                rules = [rule for rule in rules if rule.enabled]

            return sorted(rules, key=lambda x: x.created_at, reverse=True)

    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        更新指标数据

        Args:
            metrics: 指标数据
        """
        with self._cache_lock:
            # 更新当前指标
            self._metrics_cache.update(metrics)

            # 更新历史数据
            for metric_name, value in metrics.items():
                if metric_name not in self._historical_cache:
                    self._historical_cache[metric_name] = []

                self._historical_cache[metric_name].append(value)

                # 限制历史数据长度
                if len(self._historical_cache[metric_name]) > 100:
                    self._historical_cache[metric_name] = self._historical_cache[metric_name][-50:]

    async def evaluate_rules(self, metrics: Dict[str, Any] = None) -> List[str]:
        """
        评估所有规则

        Args:
            metrics: 指标数据（可选，如果不提供则使用缓存的数据）

        Returns:
            List[str]: 触发的规则ID列表
        """
        if metrics:
            self.update_metrics(metrics)

        triggered_rules = []

        with self._rule_lock:
            for rule in self._rules.values():
                try:
                    self._stats["total_evaluations"] += 1

                    # 评估规则
                    if await rule.evaluate_and_execute(self._metrics_cache, self._historical_cache):
                        triggered_rules.append(rule.rule_id)
                        self._stats["triggered_alerts"] += 1

                        # 发送到去重服务
                        if self.dedup_service:
                            self.dedup_service.process_alert(
                                level=rule.level,
                                category=rule.category,
                                message=f"规则 {rule.name} 触发告警",
                                source="AlertRuleEngine",
                                metadata={
                                    "rule_id": rule.rule_id,
                                    "rule_name": rule.name,
                                    "metrics": self._metrics_cache
                                }
                            )

                except Exception as e:
                    self._stats["failed_evaluations"] += 1
                    self.logger.error(f"规则 {rule.rule_id} 评估失败: {e}")

        return triggered_rules

    def start(self, monitor_interval: int = 60) -> None:
        """
        启动监控

        Args:
            monitor_interval: 监控间隔（秒）
        """
        if self._monitoring:
            self.logger.warning("告警规则引擎已在运行")
            return

        self._monitor_interval = monitor_interval
        self._monitoring = True

        # 启动监控任务 - 修复事件循环问题
        try:
            # 检查是否有运行的事件循环
            loop = asyncio.get_running_loop()
            self._monitor_task = loop.create_task(self._monitor_loop())
        except RuntimeError:
            # 没有运行的事件循环，创建新的事件循环在后台线程中运行
            import threading

            def run_monitor():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self._monitor_task = loop.create_task(self._monitor_loop())
                    loop.run_forever()
                except Exception as e:
                    self.logger.error(f"监控线程启动失败: {e}")

            self._monitor_thread = threading.Thread(target=run_monitor, daemon=True)
            self._monitor_thread.start()

        self.logger.info(f"告警规则引擎已启动，监控间隔: {monitor_interval}秒")

    def stop(self) -> None:
        """停止监控"""
        if not self._monitoring:
            return

        self._monitoring = False

        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

        self.logger.info("告警规则引擎已停止")

    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._monitoring:
            try:
                # 评估所有规则
                await self.evaluate_rules()

                # 等待下次评估
                await asyncio.sleep(self._monitor_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(self._monitor_interval)

    def _update_stats(self) -> None:
        """更新统计信息"""
        with self._rule_lock:
            self._stats["total_rules"] = len(self._rules)
            self._stats["active_rules"] = sum(1 for rule in self._rules.values() if rule.enabled)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._rule_lock:
            stats = self._stats.copy()

            # 添加规则分布信息
            level_distribution = {}
            category_distribution = {}

            for rule in self._rules.values():
                level = rule.level.value
                category = rule.category

                level_distribution[level] = level_distribution.get(level, 0) + 1
                category_distribution[category] = category_distribution.get(category, 0) + 1

            stats["level_distribution"] = level_distribution
            stats["category_distribution"] = category_distribution

            return stats

    def reload_rules_sync(self, rules: List) -> None:
        """
        从热加载服务同步规则（同步方法）

        将数据库模型格式的 AlertRule 转换为业务模型并批量加载

        Args:
            rules: 数据库模型格式的 AlertRule 列表
                   (来自 db.models.alert_config_models.AlertRule)
        """
        try:
            with self._rule_lock:
                self._rules.clear()
                converted_count = 0

                for rule_data in rules:
                    try:
                        business_rule = self._convert_db_rule_to_business_rule(rule_data)
                        if business_rule:
                            self._rules[business_rule.rule_id] = business_rule
                            converted_count += 1
                    except Exception as e:
                        self.logger.error(f"转换规则失败 {getattr(rule_data, 'name', 'unknown')}: {e}")
                        continue

                self._update_stats()
                self.logger.info(f"热加载同步完成: 成功转换 {converted_count}/{len(rules)} 条规则")

        except Exception as e:
            self.logger.error(f"热加载同步失败: {e}")

    def _convert_db_rule_to_business_rule(self, rule_data) -> Optional[AlertRule]:
        """
        将数据库模型转换为业务模型

        Args:
            rule_data: 数据库模型 AlertRule

        Returns:
            Optional[AlertRule]: 业务模型 AlertRule，转换失败返回 None
        """
        try:
            rule_id = str(rule_data.id)
            name = rule_data.name or f"unnamed_rule_{rule_id}"
            description = rule_data.description or ""

            rule_type_map = {
                "系统资源": "system",
                "交易": "trading",
                "数据质量": "data_quality",
                "性能": "performance"
            }
            category = rule_type_map.get(rule_data.rule_type, "system")

            priority_to_level = {
                "低": AlertLevel.INFO,
                "中": AlertLevel.WARNING,
                "高": AlertLevel.ERROR,
                "紧急": AlertLevel.CRITICAL
            }
            level = priority_to_level.get(rule_data.priority, AlertLevel.WARNING)

            operator_map = {
                ">": ">",
                ">=": ">=",
                "<": "<",
                "<=": "<=",
                "==": "==",
                "!=": "!="
            }
            operator = operator_map.get(rule_data.operator, ">")

            condition = RuleCondition(
                condition_type=RuleConditionType.THRESHOLD,
                metric_name=rule_data.metric_name,
                operator=operator,
                threshold_value=float(rule_data.threshold_value),
                time_window_minutes=5,
                evaluation_frequency_seconds=rule_data.check_interval
            )

            actions = []
            if rule_data.desktop_notification or rule_data.sound_notification:
                actions.append(RuleAction(
                    action_type=RuleActionType.LOG,
                    target="internal",
                    template=rule_data.message_template or "{rule_name} 触发告警: {metric_name} {operator} {threshold_value}"
                ))

            if rule_data.email_notification:
                actions.append(RuleAction(
                    action_type=RuleActionType.EMAIL,
                    target=rule_data.email_recipients or "default",
                    template=rule_data.message_template
                ))

            if rule_data.webhook_notification:
                actions.append(RuleAction(
                    action_type=RuleActionType.WEBHOOK,
                    target=rule_data.webhook_url or "default",
                    template=rule_data.message_template
                ))

            if rule_data.dingtalk_notification:
                actions.append(RuleAction(
                    action_type=RuleActionType.WEBHOOK,
                    target=rule_data.dingtalk_webhook_url or "default_dingtalk",
                    template=rule_data.message_template
                ))

            if not actions:
                actions.append(RuleAction(
                    action_type=RuleActionType.LOG,
                    target="internal",
                    template="{rule_name} 触发告警"
                ))

            business_rule = AlertRule(
                rule_id=rule_id,
                name=name,
                description=description,
                conditions=[condition],
                actions=actions,
                level=level,
                category=category,
                enabled=rule_data.enabled,
                cooldown_minutes=rule_data.silence_period // 60 if rule_data.silence_period > 0 else 5,
                max_executions_per_hour=rule_data.max_alerts,
                created_at=datetime.fromisoformat(rule_data.created_at) if rule_data.created_at else datetime.now(),
                updated_at=datetime.fromisoformat(rule_data.updated_at) if rule_data.updated_at else datetime.now()
            )

            return business_rule

        except Exception as e:
            self.logger.error(f"转换规则详细失败: {e}")
            return None

    def dispose(self) -> None:
        """清理资源"""
        self.stop()
        self.logger.info("告警规则引擎已清理")


# 全局服务实例
_alert_rule_engine: Optional[AlertRuleEngine] = None


def get_alert_rule_engine(dedup_service: AlertDeduplicationService = None) -> AlertRuleEngine:
    """
    获取告警规则引擎的全局实例

    Args:
        dedup_service: 告警去重服务

    Returns:
        AlertRuleEngine: 引擎实例
    """
    global _alert_rule_engine

    if _alert_rule_engine is None:
        _alert_rule_engine = AlertRuleEngine(dedup_service)

    return _alert_rule_engine


def initialize_alert_rule_engine(event_bus=None, dedup_service=None) -> AlertRuleEngine:
    """
    初始化告警规则引擎

    Args:
        event_bus: 事件总线（暂未使用）
        dedup_service: 告警去重服务

    Returns:
        AlertRuleEngine: 引擎实例
    """
    global _alert_rule_engine

    if _alert_rule_engine is not None:
        _alert_rule_engine.dispose()

    _alert_rule_engine = AlertRuleEngine(dedup_service)
    return _alert_rule_engine
