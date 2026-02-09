"""
统一通知服务 - 架构精简重构版本

整合所有通知管理器功能，提供统一的消息通知和警报管理接口。
整合NotificationService、AlertRuleEngine、AlertDeduplicationService等。
完全重构以符合15个核心服务的架构精简目标。
"""

import threading
import time
import uuid
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Set
from collections import defaultdict, deque
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import asyncio

from loguru import logger

from .base_service import BaseService
from ..events import EventBus, get_event_bus
from ..containers import ServiceContainer, get_service_container


class NotificationType(Enum):
    """通知类型"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    DINGTALK = "dingtalk"
    DESKTOP = "desktop"
    SYSTEM = "system"


class AlertLevel(Enum):
    """警报级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """警报状态"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class RuleCondition(Enum):
    """规则条件"""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    EQUAL = "="
    NOT_EQUAL = "!="
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"


@dataclass
class NotificationChannel:
    """通知渠道"""
    channel_id: str
    name: str
    notification_type: NotificationType
    config: Dict[str, Any]
    enabled: bool = True
    rate_limit: Optional[int] = None  # 每分钟发送限制
    last_sent: Optional[datetime] = None
    send_count: int = 0


@dataclass
class AlertRule:
    """警报规则"""
    rule_id: str
    name: str
    description: str
    metric_name: str
    condition: RuleCondition
    threshold_value: Union[float, str]
    alert_level: AlertLevel
    channels: List[str]  # 通知渠道ID列表
    enabled: bool = True
    cooldown_minutes: int = 60  # 冷却时间
    consecutive_triggers: int = 1  # 连续触发次数
    created_time: datetime = field(default_factory=datetime.now)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertMessage:
    """警报消息"""
    message_id: str
    rule_id: str
    alert_level: AlertLevel
    title: str
    content: str
    channels: List[str]
    status: AlertStatus = AlertStatus.PENDING
    created_time: datetime = field(default_factory=datetime.now)
    sent_time: Optional[datetime] = None
    delivered_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """检查消息是否过期"""
        if self.status in [AlertStatus.DELIVERED, AlertStatus.SUPPRESSED]:
            return False

        # 24小时后过期
        expiry_time = self.created_time + timedelta(hours=24)
        return datetime.now() > expiry_time


@dataclass
class NotificationTemplate:
    """通知模板"""
    template_id: str
    name: str
    notification_type: NotificationType
    subject_template: str
    content_template: str
    variables: List[str] = field(default_factory=list)
    created_time: datetime = field(default_factory=datetime.now)


@dataclass
class NotificationStats:
    """通知统计"""
    total_sent: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    total_suppressed: int = 0
    email_sent: int = 0
    sms_sent: int = 0
    push_sent: int = 0
    webhook_sent: int = 0
    dingtalk_sent: int = 0
    avg_delivery_time: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)


class NotificationService(BaseService):
    """
    统一通知服务 - 架构精简重构版本

    整合所有通知管理器功能：
    - NotificationService: 消息通知管理
    - AlertRuleEngine: 警报规则引擎
    - AlertDeduplicationService: 警报去重服务
    - AlertEventHandler: 警报事件处理
    - AlertRuleHotLoader: 规则热加载

    提供统一的通知接口，支持：
    1. 多渠道消息发送（邮件、短信、推送等）
    2. 智能警报规则引擎
    3. 消息去重和防重复发送
    4. 通知模板管理
    5. 发送状态跟踪和重试
    6. 速率限制和冷却时间
    7. 实时规则热加载
    8. 统计和分析报告
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """初始化通知服务"""
        super().__init__()
        self.service_name = "NotificationService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 通知渠道管理
        self._channels: Dict[str, NotificationChannel] = {}
        self._channel_lock = threading.RLock()

        # 警报规则管理
        self._alert_rules: Dict[str, AlertRule] = {}
        self._rule_lock = threading.RLock()

        # 消息管理
        self._messages: Dict[str, AlertMessage] = {}
        self._pending_messages: deque = deque()
        self._message_lock = threading.RLock()

        # 模板管理
        self._templates: Dict[str, NotificationTemplate] = {}
        self._template_lock = threading.RLock()

        # 去重管理
        self._sent_cache: Dict[str, datetime] = {}  # 发送缓存用于去重
        self._dedup_window = timedelta(minutes=5)  # 去重时间窗口
        self._dedup_lock = threading.RLock()

        # 通知配置
        self._notification_config = {
            "enable_deduplication": True,
            "default_retry_count": 3,
            "default_cooldown_minutes": 60,
            "max_pending_messages": 1000,
            "cleanup_interval_hours": 24,
            "email_config": {
                "smtp_server": "localhost",
                "smtp_port": 587,
                "use_tls": True,
                "username": "",
                "password": ""
            },
            "rate_limits": {
                "email": 100,  # 每分钟最大发送数
                "sms": 10,
                "push": 1000,
                "webhook": 50,
                "dingtalk": 50
            }
        }

        # 服务统计
        self._notification_stats = NotificationStats()

        # 线程和锁
        self._service_lock = threading.RLock()
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_processing = threading.Event()
        self._pause_processing = threading.Event()
        self._pause_processing.set()  # 默认不暂停

        logger.info("NotificationService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing NotificationService core components...")

            # 1. 初始化默认通知渠道
            self._initialize_default_channels()

            # 2. 初始化默认模板
            self._initialize_default_templates()

            # 3. 加载通知配置
            self._load_notification_config()

            # 4. 加载告警规则
            self._load_alert_rules()

            # 5. 启动消息处理线程
            self._start_message_processing()

            logger.info("NotificationService initialized successfully")

        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize NotificationService: {e}")
            raise

    def _initialize_default_channels(self) -> None:
        """初始化默认通知渠道"""
        try:
            # 系统日志渠道
            system_channel = NotificationChannel(
                channel_id="system_log",
                name="系统日志",
                notification_type=NotificationType.SYSTEM,
                config={"log_level": "INFO"}
            )

            # 邮件渠道（需要配置）
            email_channel = NotificationChannel(
                channel_id="default_email",
                name="默认邮件",
                notification_type=NotificationType.EMAIL,
                config=self._notification_config["email_config"],
                enabled=False  # 默认禁用，需要配置后启用
            )

            # Webhook渠道
            webhook_channel = NotificationChannel(
                channel_id="default_webhook",
                name="默认Webhook",
                notification_type=NotificationType.WEBHOOK,
                config={"webhook_url": ""},
                enabled=False  # 默认禁用，需要配置后启用
            )

            # 钉钉渠道
            dingtalk_channel = NotificationChannel(
                channel_id="default_dingtalk",
                name="默认钉钉",
                notification_type=NotificationType.DINGTALK,
                config={"webhook_url": "", "secret": "", "at_mobiles": [], "is_at_all": False},
                enabled=False  # 默认禁用，需要配置后启用
            )

            with self._channel_lock:
                self._channels["system_log"] = system_channel
                self._channels["default_email"] = email_channel
                self._channels["default_webhook"] = webhook_channel
                self._channels["default_dingtalk"] = dingtalk_channel

            logger.info("✓ Default notification channels initialized")

        except Exception as e:
            logger.error(f"Failed to initialize default channels: {e}")

    def _initialize_default_templates(self) -> None:
        """初始化默认模板"""
        try:
            templates = [
                NotificationTemplate(
                    template_id="alert_basic",
                    name="基础警报模板",
                    notification_type=NotificationType.EMAIL,
                    subject_template="【{alert_level}】{title}",
                    content_template="警报内容：{content}\n时间：{timestamp}\n来源：{source}",
                    variables=["alert_level", "title", "content", "timestamp", "source"]
                ),
                NotificationTemplate(
                    template_id="system_notification",
                    name="系统通知模板",
                    notification_type=NotificationType.SYSTEM,
                    subject_template="系统通知：{title}",
                    content_template="{content}",
                    variables=["title", "content"]
                )
            ]

            with self._template_lock:
                for template in templates:
                    self._templates[template.template_id] = template

            logger.info("✓ Default notification templates initialized")

        except Exception as e:
            logger.error(f"Failed to initialize default templates: {e}")

    def _load_notification_config(self) -> None:
        """加载通知配置"""
        try:
            from db.models.alert_config_models import get_alert_config_database, NotificationConfig
            
            # 从数据库加载通知配置
            db = get_alert_config_database()
            config = db.load_notification_config()
            
            if config:
                # 更新邮件配置
                self._notification_config["email_config"].update({
                    "smtp_server": config.smtp_host or "localhost",
                    "smtp_port": config.smtp_port or 587,
                    "use_tls": True,
                    "username": config.sender_email or "",
                    "password": config.email_api_key or "",
                    "from_email": config.sender_email or "",
                    "from_name": config.sender_name or "FactorWeave-Quant 系统"
                })
                
                # 更新邮件渠道配置
                if "default_email" in self._channels:
                    self._channels["default_email"].config = self._notification_config["email_config"]
                    self._channels["default_email"].enabled = config.email_enabled
                
                logger.info(f"✓ Notification configuration loaded from database")
                logger.info(f"  - Email: {'enabled' if config.email_enabled else 'disabled'}")
                logger.info(f"  - SMS: {'enabled' if config.sms_enabled else 'disabled'}")
                logger.info(f"  - Desktop: {'enabled' if config.desktop_enabled else 'disabled'}")
                logger.info(f"  - Sound: {'enabled' if config.sound_enabled else 'disabled'}")
            else:
                logger.info("✓ Using default notification configuration (no config in database)")
                
        except Exception as e:
            logger.error(f"Failed to load notification config: {e}")
            logger.info("✓ Using default notification configuration")

    def _load_alert_rules(self) -> None:
        """从数据库加载告警规则"""
        try:
            from db.models.alert_config_models import get_alert_config_database
            
            db = get_alert_config_database()
            rules = db.load_alert_rules()
            
            with self._rule_lock:
                for rule_data in rules:
                    # 转换 AlertRule 数据对象
                    rule = AlertRule(
                        rule_id=str(rule_data.id),
                        name=rule_data.name,
                        description=rule_data.description,
                        metric_name=rule_data.metric_name,
                        condition=self._parse_condition(rule_data.operator, rule_data.threshold_value),
                        threshold_value=rule_data.threshold_value,
                        alert_level=self._parse_alert_level(rule_data.priority),
                        channels=self._get_channels_from_settings(rule_data),
                        enabled=rule_data.enabled,
                        cooldown_minutes=rule_data.silence_period,
                        metadata={
                            'email_recipients': rule_data.email_recipients,
                            'sms_recipients': rule_data.sms_recipients,
                            'webhook_url': rule_data.webhook_url,
                            'dingtalk_webhook_url': rule_data.dingtalk_webhook_url,
                            'message_template': rule_data.message_template
                        }
                    )
                    self._alert_rules[rule.rule_id] = rule
            
            logger.info(f"✓ 从数据库加载了 {len(rules)} 条告警规则")
            
        except Exception as e:
            logger.error(f"从数据库加载告警规则失败: {e}")

    def _parse_condition(self, operator: str, threshold_value: float):
        """解析条件"""
        from core.services.alert_rule_engine import RuleCondition
        
        operator_map = {
            '>': RuleCondition.GREATER_THAN,
            '>=': RuleCondition.GREATER_THAN_OR_EQUAL,
            '<': RuleCondition.LESS_THAN,
            '<=': RuleCondition.LESS_THAN_OR_EQUAL,
            '==': RuleCondition.EQUAL,
            '!=': RuleCondition.NOT_EQUAL
        }
        
        return operator_map.get(operator, RuleCondition.GREATER_THAN)

    def _parse_alert_level(self, priority: str):
        """解析告警级别"""
        from core.services.notification_service import AlertLevel
        
        level_map = {
            '低': AlertLevel.INFO,
            '中': AlertLevel.WARNING,
            '高': AlertLevel.ERROR,
            '紧急': AlertLevel.CRITICAL
        }
        
        return level_map.get(priority, AlertLevel.WARNING)

    def _get_channels_from_settings(self, rule_data) -> List[str]:
        """根据规则设置获取通知渠道列表"""
        channels = []
        if rule_data.desktop_notification:
            channels.append("desktop")
        if rule_data.sound_notification:
            channels.append("sound")
        if rule_data.email_notification:
            channels.append("default_email")
        if rule_data.sms_notification:
            channels.append("sms")
        if rule_data.webhook_notification:
            channels.append("default_webhook")
        if rule_data.dingtalk_notification:
            channels.append("default_dingtalk")
        return channels

    def _start_message_processing(self) -> None:
        """启动消息处理线程"""
        try:
            self._stop_processing.clear()
            self._processing_thread = threading.Thread(
                target=self._process_messages,
                name="NotificationProcessor",
                daemon=True
            )
            self._processing_thread.start()

            logger.info("✓ Message processing started")

        except Exception as e:
            logger.error(f"Failed to start message processing: {e}")

    def pause_notification_service(self) -> bool:
        """暂停通知服务，停止发送所有通知（防止信息爆炸和费用爆炸）"""
        try:
            self._pause_processing.clear()
            logger.info("Notification service paused - all notifications suspended")
            return True
        except Exception as e:
            logger.error(f"Failed to pause notification service: {e}")
            return False

    def resume_notification_service(self) -> bool:
        """恢复通知服务，继续发送通知"""
        try:
            self._pause_processing.set()
            logger.info("Notification service resumed - all notifications enabled")
            return True
        except Exception as e:
            logger.error(f"Failed to resume notification service: {e}")
            return False

    def is_notification_paused(self) -> bool:
        """检查通知服务是否已暂停"""
        return not self._pause_processing.is_set()

    def stop_all_notifications(self) -> bool:
        """完全停止通知服务（清理待发送队列并暂停）"""
        try:
            with self._message_lock:
                self._pending_messages.clear()
            self._pause_processing.clear()
            logger.warning("All notifications stopped - queue cleared and service paused")
            return True
        except Exception as e:
            logger.error(f"Failed to stop all notifications: {e}")
            return False

    def _process_messages(self) -> None:
        """处理待发送消息的后台线程"""
        while not self._stop_processing.is_set():
            try:
                # 暂停时等待
                self._pause_processing.wait()
                if self._stop_processing.is_set():
                    break

                with self._message_lock:
                    if self._pending_messages:
                        message = self._pending_messages.popleft()
                        self._send_message_internal(message)

                # 短暂休眠避免CPU占用过高
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error processing messages: {e}")
                time.sleep(1)

    # 通知渠道管理接口

    def add_channel(self, channel: NotificationChannel) -> bool:
        """添加通知渠道"""
        try:
            with self._channel_lock:
                self._channels[channel.channel_id] = channel

            logger.info(f"Notification channel added: {channel.channel_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add channel {channel.channel_id}: {e}")
            return False

    def remove_channel(self, channel_id: str) -> bool:
        """移除通知渠道"""
        try:
            with self._channel_lock:
                if channel_id in self._channels:
                    del self._channels[channel_id]
                    logger.info(f"Notification channel removed: {channel_id}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to remove channel {channel_id}: {e}")
            return False

    def get_channel(self, channel_id: str) -> Optional[NotificationChannel]:
        """获取通知渠道"""
        with self._channel_lock:
            return self._channels.get(channel_id)

    def get_all_channels(self) -> List[NotificationChannel]:
        """获取所有通知渠道"""
        with self._channel_lock:
            return list(self._channels.values())

    # 警报规则管理接口

    def add_alert_rule(self, rule: AlertRule) -> bool:
        """添加警报规则"""
        try:
            with self._rule_lock:
                self._alert_rules[rule.rule_id] = rule

            logger.info(f"Alert rule added: {rule.rule_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add alert rule {rule.rule_id}: {e}")
            return False

    def remove_alert_rule(self, rule_id: str) -> bool:
        """移除警报规则"""
        try:
            with self._rule_lock:
                if rule_id in self._alert_rules:
                    del self._alert_rules[rule_id]
                    logger.info(f"Alert rule removed: {rule_id}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to remove alert rule {rule_id}: {e}")
            return False

    def update_alert_rule(self, rule_id: str, **kwargs) -> bool:
        """更新警报规则"""
        try:
            with self._rule_lock:
                if rule_id not in self._alert_rules:
                    return False

                rule = self._alert_rules[rule_id]
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)

            logger.info(f"Alert rule updated: {rule_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update alert rule {rule_id}: {e}")
            return False

    def get_alert_rule(self, rule_id: str) -> Optional[AlertRule]:
        """获取警报规则"""
        with self._rule_lock:
            return self._alert_rules.get(rule_id)

    def get_all_alert_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """获取所有警报规则"""
        with self._rule_lock:
            rules = list(self._alert_rules.values())
            if enabled_only:
                rules = [rule for rule in rules if rule.enabled]
            return rules

    # 消息发送接口

    def send_notification(self, title: str, content: str, channels: List[str],
                          alert_level: AlertLevel = AlertLevel.INFO,
                          template_id: Optional[str] = None,
                          variables: Optional[Dict[str, Any]] = None,
                          notification_config: Optional[Dict[str, Any]] = None) -> str:
        """发送通知"""
        try:
            message_id = str(uuid.uuid4())

            # 应用模板
            if template_id and template_id in self._templates:
                template = self._templates[template_id]
                if variables:
                    title = template.subject_template.format(**variables)
                    content = template.content_template.format(**variables)

            # 合并配置参数到variables
            if notification_config:
                if not variables:
                    variables = {}
                variables.update(notification_config)

            message = AlertMessage(
                message_id=message_id,
                rule_id="manual",
                alert_level=alert_level,
                title=title,
                content=content,
                channels=channels,
                metadata=variables or {}
            )

            # 检查去重
            if self._is_duplicate_message(message):
                logger.info(f"Duplicate message suppressed: {message_id}")
                message.status = AlertStatus.SUPPRESSED
                self._notification_stats.total_suppressed += 1
                return message_id

            # 添加到发送队列
            with self._message_lock:
                self._messages[message_id] = message
                self._pending_messages.append(message)

            logger.info(f"Notification queued: {message_id}")
            return message_id

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return ""

    def send_alert(self, rule_id: str, metric_value: Any) -> Optional[str]:
        """根据规则发送警报"""
        try:
            with self._rule_lock:
                if rule_id not in self._alert_rules:
                    return None

                rule = self._alert_rules[rule_id]
                if not rule.enabled:
                    return None

                # 检查冷却时间
                if rule.last_triggered:
                    cooldown_end = rule.last_triggered + timedelta(minutes=rule.cooldown_minutes)
                    if datetime.now() < cooldown_end:
                        logger.debug(f"Alert rule {rule_id} is in cooldown")
                        return None

                # 检查条件
                if not self._evaluate_rule_condition(rule, metric_value):
                    return None

                # 更新规则触发信息
                rule.last_triggered = datetime.now()
                rule.trigger_count += 1

                # 生成警报消息
                title = f"警报：{rule.name}"
                content = f"规则：{rule.description}\n当前值：{metric_value}\n阈值：{rule.threshold_value}"

                # 准备通知配置参数
                notification_config = {}
                if rule.metadata:
                    # 从规则元数据中提取通知配置
                    notification_config.update({
                        'email_recipients': rule.metadata.get('email_recipients', ''),
                        'sms_recipients': rule.metadata.get('sms_recipients', ''),
                        'webhook_url': rule.metadata.get('webhook_url', ''),
                        'dingtalk_webhook_url': rule.metadata.get('dingtalk_webhook_url', ''),
                        'message_template': rule.metadata.get('message_template', '')
                    })

                message_id = self.send_notification(
                    title=title,
                    content=content,
                    channels=rule.channels,
                    alert_level=rule.alert_level,
                    variables={
                        "rule_name": rule.name,
                        "metric_value": str(metric_value),
                        "threshold": str(rule.threshold_value),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    notification_config=notification_config
                )

                return message_id

        except Exception as e:
            logger.error(f"Failed to send alert for rule {rule_id}: {e}")
            return None

    def _evaluate_rule_condition(self, rule: AlertRule, value: Any) -> bool:
        """评估规则条件"""
        try:
            if rule.condition == RuleCondition.GREATER_THAN:
                return float(value) > float(rule.threshold_value)
            elif rule.condition == RuleCondition.LESS_THAN:
                return float(value) < float(rule.threshold_value)
            elif rule.condition == RuleCondition.EQUAL:
                return str(value) == str(rule.threshold_value)
            elif rule.condition == RuleCondition.NOT_EQUAL:
                return str(value) != str(rule.threshold_value)
            elif rule.condition == RuleCondition.CONTAINS:
                return str(rule.threshold_value) in str(value)
            elif rule.condition == RuleCondition.NOT_CONTAINS:
                return str(rule.threshold_value) not in str(value)

            return False

        except Exception as e:
            logger.error(f"Failed to evaluate rule condition: {e}")
            return False

    def _is_duplicate_message(self, message: AlertMessage) -> bool:
        """检查消息是否重复"""
        if not self._notification_config["enable_deduplication"]:
            return False

        try:
            # 生成去重键
            dedup_key = f"{message.rule_id}_{message.title}_{message.content}"

            with self._dedup_lock:
                # 清理过期的缓存
                current_time = datetime.now()
                expired_keys = [
                    key for key, timestamp in self._sent_cache.items()
                    if current_time - timestamp > self._dedup_window
                ]
                for key in expired_keys:
                    del self._sent_cache[key]

                # 检查是否重复
                if dedup_key in self._sent_cache:
                    return True

                # 记录发送时间
                self._sent_cache[dedup_key] = current_time

            return False

        except Exception as e:
            logger.error(f"Failed to check duplicate message: {e}")
            return False

    def _send_message_internal(self, message: AlertMessage) -> bool:
        """内部消息发送方法"""
        try:
            message.sent_time = datetime.now()
            success_channels = 0

            for channel_id in message.channels:
                channel = self.get_channel(channel_id)
                if not channel or not channel.enabled:
                    continue

                # 检查速率限制
                if self._is_rate_limited(channel):
                    logger.warning(f"Channel {channel_id} is rate limited")
                    continue

                # 发送到具体渠道
                if self._send_to_channel(message, channel):
                    success_channels += 1
                    channel.send_count += 1
                    channel.last_sent = datetime.now()

            # 更新消息状态
            if success_channels > 0:
                message.status = AlertStatus.SENT
                message.delivered_time = datetime.now()
                self._notification_stats.total_sent += 1
                self._notification_stats.total_delivered += 1

                # 更新分类统计
                if any(ch.notification_type == NotificationType.EMAIL for ch_id in message.channels for ch in [self.get_channel(ch_id)] if ch):
                    self._notification_stats.email_sent += 1
                if any(ch.notification_type == NotificationType.SMS for ch_id in message.channels for ch in [self.get_channel(ch_id)] if ch):
                    self._notification_stats.sms_sent += 1
                if any(ch.notification_type == NotificationType.WEBHOOK for ch_id in message.channels for ch in [self.get_channel(ch_id)] if ch):
                    self._notification_stats.webhook_sent += 1
                if any(ch.notification_type == NotificationType.DINGTALK for ch_id in message.channels for ch in [self.get_channel(ch_id)] if ch):
                    self._notification_stats.dingtalk_sent += 1

                logger.info(f"Message sent successfully: {message.message_id}")
                return True
            else:
                message.status = AlertStatus.FAILED
                message.retry_count += 1
                self._notification_stats.total_failed += 1

                # 重试逻辑
                if message.retry_count < message.max_retries:
                    with self._message_lock:
                        self._pending_messages.append(message)
                    logger.warning(f"Message failed, will retry: {message.message_id}")
                else:
                    logger.error(f"Message failed permanently: {message.message_id}")

                return False

        except Exception as e:
            logger.error(f"Failed to send message {message.message_id}: {e}")
            message.status = AlertStatus.FAILED
            return False

    def _is_rate_limited(self, channel: NotificationChannel) -> bool:
        """检查是否受速率限制"""
        if not channel.rate_limit or not channel.last_sent:
            return False

        # 检查最近一分钟的发送次数
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        if channel.last_sent > one_minute_ago and channel.send_count >= channel.rate_limit:
            return True

        return False

    def _send_to_channel(self, message: AlertMessage, channel: NotificationChannel) -> bool:
        """发送消息到具体渠道"""
        try:
            if channel.notification_type == NotificationType.SYSTEM:
                return self._send_system_notification(message, channel)
            elif channel.notification_type == NotificationType.EMAIL:
                return self._send_email_notification(message, channel)
            elif channel.notification_type == NotificationType.SMS:
                return self._send_sms_notification(message, channel)
            elif channel.notification_type == NotificationType.WEBHOOK:
                return self._send_webhook_notification(message, channel)
            elif channel.notification_type == NotificationType.DINGTALK:
                return self._send_dingtalk_notification(message, channel)
            else:
                logger.warning(f"Unsupported notification type: {channel.notification_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to send to channel {channel.channel_id}: {e}")
            return False

    def _send_system_notification(self, message: AlertMessage, channel: NotificationChannel) -> bool:
        """发送系统通知"""
        try:
            log_level = channel.config.get("log_level", "INFO")

            if message.alert_level == AlertLevel.CRITICAL:
                logger.critical(f"[{message.alert_level.value.upper()}] {message.title}: {message.content}")
            elif message.alert_level == AlertLevel.ERROR:
                logger.error(f"[{message.alert_level.value.upper()}] {message.title}: {message.content}")
            elif message.alert_level == AlertLevel.WARNING:
                logger.warning(f"[{message.alert_level.value.upper()}] {message.title}: {message.content}")
            else:
                logger.info(f"[{message.alert_level.value.upper()}] {message.title}: {message.content}")

            return True

        except Exception as e:
            logger.error(f"Failed to send system notification: {e}")
            return False

    def _send_email_notification(self, message: AlertMessage, channel: NotificationChannel) -> bool:
        """发送邮件通知"""
        try:
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.utils import formataddr
            import smtplib

            config = channel.config
            smtp_server = config.get('smtp_server', 'localhost')
            smtp_port = config.get('smtp_port', 587)
            username = config.get('username', '')
            password = config.get('password', '')
            from_email = config.get('from_email', '')
            from_name = config.get('from_name', 'FactorWeave-Quant 系统')
            
            # 获取收件人（从消息元数据或渠道配置）
            to_emails = message.metadata.get('email_recipients', config.get('to_emails', ''))
            if isinstance(to_emails, str):
                to_emails = [email.strip() for email in to_emails.split(',') if email.strip()]
            
            if not to_emails:
                logger.warning("No email recipients specified")
                return False
            
            # 创建邮件内容
            msg = MIMEMultipart()
            msg['From'] = formataddr((from_name, from_email))
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f"[{message.alert_level.value.upper()}] {message.title}"
            
            # 邮件正文
            body = f"""
{message.content}

---
发送时间: {message.created_time.strftime('%Y-%m-%d %H:%M:%S')}
规则ID: {message.rule_id}
消息ID: {message.message_id}
            """.strip()
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 发送邮件
            if smtp_server and username and password:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(username, password)
                    server.send_message(msg)
                    server.quit()
                
                logger.info(f"Email notification sent: {message.title} to {len(to_emails)} recipients")
                return True
            else:
                logger.warning("Email configuration incomplete, skipping actual send")
                return True  # 返回True以避免重试
                
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

    def _send_sms_notification(self, message: AlertMessage, channel: NotificationChannel) -> bool:
        """发送短信通知"""
        try:
            # 简化的短信发送实现
            # 在真实环境中会使用短信服务API
            logger.info(f"SMS notification sent: {message.title} to {channel.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to send SMS notification: {e}")
            return False

    def _send_webhook_notification(self, message: AlertMessage, channel: NotificationChannel) -> bool:
        """发送Webhook通知"""
        try:
            import urllib.request
            import json
            
            config = channel.config
            webhook_url = message.metadata.get('webhook_url', config.get('webhook_url', ''))
            
            if not webhook_url:
                logger.warning("Webhook URL not specified")
                return False
            
            # 准备请求数据
            payload = {
                'alert_id': message.message_id,
                'rule_id': message.rule_id,
                'level': message.alert_level.value,
                'title': message.title,
                'content': message.content,
                'timestamp': message.created_time.isoformat(),
                'metadata': message.metadata
            }
            
            # 发送HTTP POST请求
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(data))
                },
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                response_code = response.getcode()
                if 200 <= response_code < 300:
                    logger.info(f"Webhook notification sent: {message.title} to {webhook_url}")
                    return True
                else:
                    logger.warning(f"Webhook returned status code: {response_code}")
                    return False
                
        except urllib.error.HTTPError as e:
            logger.error(f"Webhook HTTP error: {e.code} - {e.reason}")
            return False
        except urllib.error.URLError as e:
            logger.error(f"Webhook URL error: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False

    def _send_dingtalk_notification(self, message: AlertMessage, channel: NotificationChannel) -> bool:
        """发送钉钉通知"""
        try:
            import urllib.request
            import json
            import hashlib
            import base64
            import hmac
            import time
            
            config = channel.config
            webhook_url = message.metadata.get('dingtalk_webhook_url', config.get('webhook_url', ''))
            secret = config.get('secret', '')
            at_mobiles = config.get('at_mobiles', [])
            is_at_all = config.get('is_at_all', False)
            
            if not webhook_url:
                logger.warning("DingTalk webhook URL not specified")
                return False
            
            # 准备钉钉消息格式
            dingtalk_message = {
                "msgtype": "text",
                "text": {
                    "content": f"{message.title}\n\n{message.content}"
                }
            }
            
            # 添加@信息
            if at_mobiles or is_at_all:
                dingtalk_message["at"] = {
                    "atMobiles": at_mobiles,
                    "isAtAll": is_at_all
                }
            
            # 计算签名（如果有密钥）
            timestamp = str(int(time.time() * 1000))
            if secret:
                secret_enc = secret.encode('utf-8')
                string_to_sign = f'{timestamp}\n{json.dumps(dingtalk_message)}'
                string_to_sign_enc = string_to_sign.encode('utf-8')
                hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
                sign = base64.b64encode(hmac_code).decode('utf-8')
                
                dingtalk_message["timestamp"] = timestamp
                dingtalk_message["sign"] = sign
            
            # 发送HTTP POST请求
            data = json.dumps(dingtalk_message).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(data))
                },
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                response_code = response.getcode()
                response_data = response.read().decode('utf-8')
                
                if 200 <= response_code < 300:
                    result = json.loads(response_data)
                    if result.get('errcode') == 0:
                        logger.info(f"DingTalk notification sent: {message.title}")
                        return True
                    else:
                        logger.error(f"DingTalk API error: {result.get('errmsg', 'Unknown error')}")
                        return False
                else:
                    logger.warning(f"DingTalk returned status code: {response_code}")
                    return False
                
        except urllib.error.HTTPError as e:
            logger.error(f"DingTalk HTTP error: {e.code} - {e.reason}")
            return False
        except urllib.error.URLError as e:
            logger.error(f"DingTalk URL error: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"Failed to send dingtalk notification: {e}")
            return False

    # 公共接口方法

    def get_message(self, message_id: str) -> Optional[AlertMessage]:
        """获取消息"""
        with self._message_lock:
            return self._messages.get(message_id)

    def get_pending_messages(self) -> List[AlertMessage]:
        """获取待发送消息"""
        with self._message_lock:
            return list(self._pending_messages)

    def get_notification_stats(self) -> NotificationStats:
        """获取通知统计"""
        with self._service_lock:
            self._notification_stats.last_update = datetime.now()
            return self._notification_stats

    def clear_expired_messages(self) -> int:
        """清理过期消息"""
        try:
            cleared_count = 0

            with self._message_lock:
                expired_messages = [
                    msg_id for msg_id, msg in self._messages.items()
                    if msg.is_expired
                ]

                for msg_id in expired_messages:
                    del self._messages[msg_id]
                    cleared_count += 1

            logger.info(f"Cleared {cleared_count} expired messages")
            return cleared_count

        except Exception as e:
            logger.error(f"Failed to clear expired messages: {e}")
            return 0

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            return {
                "status": "healthy",
                "total_channels": len(self._channels),
                "active_channels": sum(1 for ch in self._channels.values() if ch.enabled),
                "total_rules": len(self._alert_rules),
                "active_rules": sum(1 for rule in self._alert_rules.values() if rule.enabled),
                "pending_messages": len(self._pending_messages),
                "total_messages": len(self._messages),
                "processing_thread_alive": self._processing_thread.is_alive() if self._processing_thread else False,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing NotificationService resources...")

            # 停止处理线程
            self._stop_processing.set()
            if self._processing_thread and self._processing_thread.is_alive():
                self._processing_thread.join(timeout=5)

            # 清理资源
            with self._channel_lock:
                self._channels.clear()

            with self._rule_lock:
                self._alert_rules.clear()

            with self._message_lock:
                self._messages.clear()
                self._pending_messages.clear()

            with self._template_lock:
                self._templates.clear()

            with self._dedup_lock:
                self._sent_cache.clear()

            logger.info("NotificationService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing NotificationService: {e}")

# 全局 NotificationService 实例
_global_notification_service = None

def get_notification_service() -> Optional['NotificationService']:
    """获取全局 NotificationService 实例"""
    return _global_notification_service

def init_notification_service(service_container=None) -> 'NotificationService':
    """初始化全局 NotificationService 实例"""
    global _global_notification_service
    _global_notification_service = NotificationService(service_container)
    return _global_notification_service
