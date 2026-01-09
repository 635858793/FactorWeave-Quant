#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部告警渠道服务

提供多种外部告警渠道，包括邮件、短信、Webhook等。
"""

import asyncio
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod
from loguru import logger
import aiohttp
import hashlib


@dataclass
class AlertMessage:
    """告警消息"""
    alert_id: str
    component: str
    metric_name: str
    current_value: float
    threshold_value: float
    severity: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AlertSeverity:
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ExternalAlertChannel(ABC):
    """外部告警渠道基类"""

    @abstractmethod
    async def send_alert(self, alert: AlertMessage) -> bool:
        """
        发送告警

        Args:
            alert: 告警消息

        Returns:
            bool: 是否发送成功
        """
        pass

    @abstractmethod
    def get_channel_name(self) -> str:
        """获取渠道名称"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查渠道是否可用"""
        pass


class EmailAlertChannel(ExternalAlertChannel):
    """邮件告警渠道"""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        from_name: str = "BettaFish监控系统",
        to_emails: List[str] = None,
        use_tls: bool = True
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.to_emails = to_emails or []
        self.use_tls = use_tls

    def get_channel_name(self) -> str:
        return "邮件"

    def is_available(self) -> bool:
        return bool(self.smtp_server and self.username and self.password and self.to_emails)

    async def send_alert(self, alert: AlertMessage) -> bool:
        """通过邮件发送告警"""
        try:
            if not self.is_available():
                logger.warning("邮件告警渠道配置不完整，无法发送")
                return False

            # 创建邮件内容
            subject = f"[{alert.severity.upper()}] {alert.component} - {alert.metric_name}"
            body = self._format_email_body(alert)

            # 创建邮件对象
            msg = MIMEMultipart('alternative')
            msg['From'] = formataddr((self.from_name, self.from_email))
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = subject

            # 添加文本内容
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)

            # 发送邮件
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._send_smtp,
                msg
            )

            logger.info(f"邮件告警发送成功: {alert.alert_id}")
            return True

        except Exception as e:
            logger.error(f"邮件告警发送失败: {e}")
            return False

    def _send_smtp(self, msg: MIMEMultipart):
        """发送SMTP邮件"""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)

    def _format_email_body(self, alert: AlertMessage) -> str:
        """格式化邮件正文"""
        body = f"""
告警详情
========

告警ID: {alert.alert_id}
组件: {alert.component}
指标: {alert.metric_name}
当前值: {alert.current_value}
阈值: {alert.threshold_value}
级别: {alert.severity}
时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

消息:
{alert.message}
"""
        if alert.metadata:
            body += f"\n附加信息:\n{json.dumps(alert.metadata, indent=2, ensure_ascii=False)}"

        return body


class SMSAlertChannel(ExternalAlertChannel):
    """短信告警渠道"""

    def __init__(
        self,
        provider: str = "mock",
        api_key: str = None,
        api_secret: str = None,
        from_number: str = None,
        to_numbers: List[str] = None,
        sign_name: str = "BettaFish"
    ):
        self.provider = provider.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.from_number = from_number
        self.to_numbers = to_numbers or []
        self.sign_name = sign_name

    def get_channel_name(self) -> str:
        return "短信"

    def is_available(self) -> bool:
        return bool(self.to_numbers)

    async def send_alert(self, alert: AlertMessage) -> bool:
        """通过短信发送告警"""
        try:
            if not self.is_available():
                logger.warning("短信告警渠道配置不完整，无法发送")
                return False

            message = self._format_message(alert)

            if self.provider == "tencent":
                return await self._send_tencent_sms(message)
            elif self.provider == "aliyun":
                return await self._send_aliyun_sms(message)
            elif self.provider == "huawei":
                return await self._send_huawei_sms(message)
            else:
                return await self._send_mock_sms(message)

        except Exception as e:
            logger.error(f"短信告警发送失败: {e}")
            return False

    def _format_message(self, alert: AlertMessage) -> str:
        """格式化短信消息"""
        return (
            f"[{alert.severity.upper()}] {alert.component}\n"
            f"{alert.metric_name}: {alert.current_value} (阈值: {alert.threshold_value})\n"
            f"{alert.message}"
        )

    async def _send_tencent_sms(self, message: str) -> bool:
        """发送腾讯云短信"""
        logger.info(f"模拟发送腾讯云短信: {message}")
        await asyncio.sleep(0.1)
        return True

    async def _send_aliyun_sms(self, message: str) -> bool:
        """发送阿里云短信"""
        logger.info(f"模拟发送阿里云短信: {message}")
        await asyncio.sleep(0.1)
        return True

    async def _send_huawei_sms(self, message: str) -> bool:
        """发送华为云短信"""
        logger.info(f"模拟发送华为云短信: {message}")
        await asyncio.sleep(0.1)
        return True

    async def _send_mock_sms(self, message: str) -> bool:
        """模拟发送短信"""
        logger.info(f"模拟发送短信: {message}")
        await asyncio.sleep(0.1)
        return True


class WebhookAlertChannel(ExternalAlertChannel):
    """Webhook告警渠道"""

    def __init__(
        self,
        webhook_url: str,
        method: str = "POST",
        headers: Dict[str, str] = None,
        timeout: int = 10,
        retry_count: int = 3
    ):
        self.webhook_url = webhook_url
        self.method = method.upper()
        self.headers = headers or {}
        self.timeout = timeout
        self.retry_count = retry_count

    def get_channel_name(self) -> str:
        return "Webhook"

    def is_available(self) -> bool:
        return bool(self.webhook_url)

    async def send_alert(self, alert: AlertMessage) -> bool:
        """通过Webhook发送告警"""
        try:
            if not self.is_available():
                logger.warning("Webhook告警渠道配置不完整，无法发送")
                return False

            # 准备请求数据
            payload = {
                "alert_id": alert.alert_id,
                "component": alert.component,
                "metric_name": alert.metric_name,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "severity": alert.severity,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "metadata": alert.metadata
            }

            # 发送请求
            for attempt in range(self.retry_count):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.request(
                            method=self.method,
                            url=self.webhook_url,
                            json=payload,
                            headers=self.headers,
                            timeout=aiohttp.ClientTimeout(total=self.timeout)
                        ) as response:
                            if response.status == 200:
                                logger.info(f"Webhook告警发送成功: {alert.alert_id}")
                                return True
                            else:
                                logger.warning(f"Webhook返回错误状态: {response.status}")
                                return False
                except Exception as e:
                    if attempt < self.retry_count - 1:
                        logger.warning(f"Webhook发送失败，重试 {attempt + 1}/{self.retry_count}: {e}")
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"Webhook告警发送失败: {e}")
                        return False

            return False

        except Exception as e:
            logger.error(f"Webhook告警发送失败: {e}")
            return False


class DingTalkAlertChannel(ExternalAlertChannel):
    """钉钉告警渠道"""

    def __init__(
        self,
        webhook_url: str,
        secret: str = None,
        at_mobiles: List[str] = None,
        is_at_all: bool = False
    ):
        self.webhook_url = webhook_url
        self.secret = secret
        self.at_mobiles = at_mobiles or []
        self.is_at_all = is_at_all

    def get_channel_name(self) -> str:
        return "钉钉"

    def is_available(self) -> bool:
        return bool(self.webhook_url)

    async def send_alert(self, alert: AlertMessage) -> bool:
        """通过钉钉发送告警"""
        try:
            if not self.is_available():
                logger.warning("钉钉告警渠道配置不完整，无法发送")
                return False

            # 准备钉钉消息格式
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"[{alert.severity.upper()}] {alert.component}",
                    "text": self._format_dingtalk_message(alert)
                }
            }

            # 添加@信息
            if self.at_mobiles or self.is_at_all:
                message["at"] = {
                    "atMobiles": self.at_mobiles,
                    "isAtAll": self.is_at_all
                }

            # 如果配置了secret，计算签名
            if self.secret:
                import time
                import hmac
                import base64
                import urllib.parse

                timestamp = str(round(time.time() * 1000))
                secret_enc = self.secret.encode('utf-8')
                string_to_sign = f'{timestamp}\n{self.secret}'
                string_to_sign_enc = string_to_sign.encode('utf-8')
                hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

                message["timestamp"] = timestamp
                message["sign"] = sign

            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=message,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('errcode') == 0:
                            logger.info(f"钉钉告警发送成功: {alert.alert_id}")
                            return True
                        else:
                            logger.error(f"钉钉返回错误: {result.get('errmsg')}")
                            return False
                    else:
                        logger.error(f"钉钉请求失败: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"钉钉告警发送失败: {e}")
            return False

    def _format_dingtalk_message(self, alert: AlertMessage) -> str:
        """格式化钉钉消息"""
        severity_color = {
            "info": "info",
            "warning": "warning",
            "error": "comment",
            "critical": "warning"
        }.get(alert.severity, "info")

        message = f"""
### <font color={severity_color}>[{alert.severity.upper()}] {alert.component}</font>

**告警ID**: {alert.alert_id}
**指标**: {alert.metric_name}
**当前值**: {alert.current_value}
**阈值**: {alert.threshold_value}
**时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

**消息**:
{alert.message}
"""
        if alert.metadata:
            message += f"\n**附加信息**:\n```json\n{json.dumps(alert.metadata, indent=2, ensure_ascii=False)}\n```"

        return message


class ExternalAlertManager:
    """外部告警管理器"""

    def __init__(self):
        self._channels: List[ExternalAlertChannel] = []
        self._channel_configs: Dict[str, Dict[str, Any]] = {}
        self._config_persistence = None

    def set_config_persistence(self, persistence):
        """
        设置配置持久化

        Args:
            persistence: 配置持久化实例
        """
        self._config_persistence = persistence
        logger.info("设置外部告警渠道配置持久化")

    def register_channel(self, channel: ExternalAlertChannel, config: Dict[str, Any] = None):
        """
        注册告警渠道

        Args:
            channel: 告警渠道
            config: 渠道配置
        """
        self._channels.append(channel)
        if config:
            self._channel_configs[channel.get_channel_name()] = config
            # 保存配置
            self._save_channel_config(channel.get_channel_name(), config)
        logger.info(f"注册告警渠道: {channel.get_channel_name()}")

    def unregister_channel(self, channel_name: str):
        """
        注销告警渠道

        Args:
            channel_name: 渠道名称
        """
        self._channels = [c for c in self._channels if c.get_channel_name() != channel_name]
        if channel_name in self._channel_configs:
            del self._channel_configs[channel_name]
            # 删除配置
            self._delete_channel_config(channel_name)
        logger.info(f"注销告警渠道: {channel_name}")

    def is_channel_enabled(self, channel_type: str) -> bool:
        """
        检查渠道是否启用

        Args:
            channel_type: 渠道类型 (email, sms, webhook, dingtalk)

        Returns:
            是否启用
        """
        channel_name = self._get_channel_name_by_type(channel_type)
        if not channel_name:
            return False

        return any(
            c.get_channel_name() == channel_name and c.is_available()
            for c in self._channels
        )

    def _get_channel_name_by_type(self, channel_type: str) -> Optional[str]:
        """
        根据渠道类型获取渠道名称

        Args:
            channel_type: 渠道类型

        Returns:
            渠道名称
        """
        type_to_name = {
            'email': 'email',
            'sms': 'sms',
            'webhook': 'webhook',
            'dingtalk': 'dingtalk'
        }
        return type_to_name.get(channel_type)

    def _save_channel_config(self, channel_name: str, config: Dict[str, Any]):
        """
        保存渠道配置

        Args:
            channel_name: 渠道名称
            config: 配置
        """
        if self._config_persistence:
            try:
                channel_type = self._get_channel_type_by_name(channel_name)
                if channel_type:
                    self._config_persistence.save_channel_config(channel_type, config)
            except Exception as e:
                logger.error(f"保存渠道配置失败: {e}")

    def _delete_channel_config(self, channel_name: str):
        """
        删除渠道配置

        Args:
            channel_name: 渠道名称
        """
        if self._config_persistence:
            try:
                channel_type = self._get_channel_type_by_name(channel_name)
                if channel_type:
                    self._config_persistence.delete_channel_config(channel_type)
            except Exception as e:
                logger.error(f"删除渠道配置失败: {e}")

    def _get_channel_type_by_name(self, channel_name: str) -> Optional[str]:
        """
        根据渠道名称获取渠道类型

        Args:
            channel_name: 渠道名称

        Returns:
            渠道类型
        """
        name_to_type = {
            'email': 'email',
            'sms': 'sms',
            'webhook': 'webhook',
            'dingtalk': 'dingtalk'
        }
        return name_to_type.get(channel_name)

    def load_all_configs(self) -> bool:
        """
        加载所有渠道配置

        Returns:
            是否加载成功
        """
        if not self._config_persistence:
            return False

        try:
            configs = self._config_persistence.load_all_configs()

            # 根据配置创建渠道
            for channel_type, config in configs.items():
                self._create_channel_from_config(channel_type, config)

            logger.info(f"加载外部告警渠道配置成功: {list(configs.keys())}")
            return True

        except Exception as e:
            logger.error(f"加载所有渠道配置失败: {e}")
            return False

    def _create_channel_from_config(self, channel_type: str, config: Dict[str, Any]):
        """
        根据配置创建渠道

        Args:
            channel_type: 渠道类型
            config: 配置
        """
        try:
            if channel_type == 'email':
                channel = EmailAlertChannel(
                    smtp_server=config.get('smtp_server', ''),
                    smtp_port=config.get('smtp_port', 587),
                    username=config.get('username', ''),
                    password=config.get('password', ''),
                    from_email=config.get('from_email', ''),
                    from_name=config.get('from_name', 'BettaFish监控系统'),
                    to_emails=config.get('to_emails', []),
                    use_tls=config.get('use_tls', True)
                )
                self.register_channel(channel, config)

            elif channel_type == 'sms':
                channel = SMSAlertChannel(
                    provider=config.get('provider', 'mock'),
                    api_key=config.get('api_key', ''),
                    api_secret=config.get('api_secret', ''),
                    from_number=config.get('from_number', ''),
                    to_numbers=config.get('to_numbers', []),
                    sign_name=config.get('sign_name', 'BettaFish')
                )
                self.register_channel(channel, config)

            elif channel_type == 'webhook':
                channel = WebhookAlertChannel(
                    webhook_url=config.get('webhook_url', ''),
                    method=config.get('method', 'POST'),
                    timeout=config.get('timeout', 10),
                    retry_count=config.get('retry_count', 3),
                    headers=config.get('headers', {})
                )
                self.register_channel(channel, config)

            elif channel_type == 'dingtalk':
                channel = DingTalkAlertChannel(
                    webhook_url=config.get('webhook_url', ''),
                    secret=config.get('secret', ''),
                    at_mobiles=config.get('at_mobiles', []),
                    is_at_all=config.get('is_at_all', False)
                )
                self.register_channel(channel, config)

        except Exception as e:
            logger.error(f"根据配置创建渠道失败 [{channel_type}]: {e}")

    async def send_alert(self, alert: AlertMessage) -> Dict[str, bool]:
        """
        发送告警到所有渠道

        Args:
            alert: 告警消息

        Returns:
            Dict[str, bool]: 各渠道发送结果
        """
        results = {}

        for channel in self._channels:
            if not channel.is_available():
                logger.warning(f"告警渠道不可用: {channel.get_channel_name()}")
                results[channel.get_channel_name()] = False
                continue

            try:
                success = await channel.send_alert(alert)
                results[channel.get_channel_name()] = success
            except Exception as e:
                logger.error(f"发送告警到渠道失败: {channel.get_channel_name()}, 错误: {e}")
                results[channel.get_channel_name()] = False

        return results

    async def send_alert_to_channel(
        self,
        alert: AlertMessage,
        channel_name: str
    ) -> bool:
        """
        发送告警到指定渠道

        Args:
            alert: 告警消息
            channel_name: 渠道名称

        Returns:
            bool: 是否发送成功
        """
        for channel in self._channels:
            if channel.get_channel_name() == channel_name:
                if not channel.is_available():
                    logger.warning(f"告警渠道不可用: {channel_name}")
                    return False

                try:
                    return await channel.send_alert(alert)
                except Exception as e:
                    logger.error(f"发送告警到渠道失败: {channel_name}, 错误: {e}")
                    return False

        logger.warning(f"未找到告警渠道: {channel_name}")
        return False

    def get_available_channels(self) -> List[str]:
        """获取可用的告警渠道"""
        return [
            channel.get_channel_name()
            for channel in self._channels
            if channel.is_available()
        ]

    def get_channel_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取渠道配置"""
        return self._channel_configs.copy()


# 全局实例
_alert_manager: Optional[ExternalAlertManager] = None


def get_alert_manager() -> ExternalAlertManager:
    """获取外部告警管理器单例"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = ExternalAlertManager()

        # 设置配置持久化
        try:
            from .external_alert_config_persistence import get_alert_config_persistence
            persistence = get_alert_config_persistence()
            _alert_manager.set_config_persistence(persistence)

            # 加载所有配置
            _alert_manager.load_all_configs()

        except Exception as e:
            logger.warning(f"设置外部告警渠道配置持久化失败: {e}")

    return _alert_manager
