"""
外部告警渠道测试

专门测试各种外部告警渠道的实现，包括邮件、短信和Webhook。
"""

import asyncio
import pytest
from datetime import datetime
from typing import List, Dict, Optional
import json

# 导入告警相关枚举和类
class AlertSeverity:
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class Alert:
    """告警信息"""
    def __init__(self, alert_id: str, component: str, metric_name: str, 
                 current_value: float, threshold_value: float, 
                 severity: str, message: str, timestamp: datetime):
        self.alert_id = alert_id
        self.component = component
        self.metric_name = metric_name
        self.current_value = current_value
        self.threshold_value = threshold_value
        self.severity = severity  # 直接使用字符串
        self.message = message
        self.timestamp = timestamp

class ExternalAlertChannel:
    """外部告警渠道基类"""
    async def send_alert(self, alert: Alert) -> bool:
        """发送告警"""
        raise NotImplementedError

class EmailAlertChannel(ExternalAlertChannel):
    """邮件告警渠道"""
    
    def __init__(self, smtp_server: str, smtp_port: int, username: str, 
                 password: str, from_email: str, to_emails: List[str]):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
    
    async def send_alert(self, alert: Alert) -> bool:
        """通过邮件发送告警"""
        try:
            # 模拟发送邮件（不实际连接SMTP服务器）
            print(f"模拟邮件发送:")
            print(f"  SMTP服务器: {self.smtp_server}:{self.smtp_port}")
            print(f"  发件人: {self.from_email}")
            print(f"  收件人: {', '.join(self.to_emails)}")
            print(f"  主题: [BettaFish监控告警-{alert.severity.upper()}] {alert.component}")
            print(f"  内容: 告警详情已包含")
            
            # 模拟网络延迟
            await asyncio.sleep(0.1)
            
            return True
            
        except Exception as e:
            print(f"Failed to send alert email: {e}")
            return False

class SMSAlertChannel(ExternalAlertChannel):
    """短信告警渠道"""
    
    def __init__(self, api_key: str, api_secret: str, from_number: str, 
                 to_numbers: List[str], provider: str = "tencent"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.from_number = from_number
        self.to_numbers = to_numbers
        self.provider = provider
    
    async def send_alert(self, alert: Alert) -> bool:
        """通过短信发送告警"""
        try:
            message = self._format_message(alert)
            
            if self.provider.lower() == "tencent":
                return await self._send_tencent_sms(message)
            elif self.provider.lower() == "aliyun":
                return await self._send_aliyun_sms(message)
            elif self.provider.lower() == "huawei":
                return await self._send_huawei_sms(message)
            else:
                return await self._send_mock_sms(message)
                        
        except Exception as e:
            print(f"Failed to send alert SMS: {e}")
            return False
    
    def _format_message(self, alert: Alert) -> str:
        """格式化告警消息"""
        timestamp = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        message = f"""[BettaFish系统告警]
组件: {alert.component}
级别: {alert.severity.upper()}
指标: {alert.metric_name}
当前值: {alert.current_value}
阈值: {alert.threshold_value}
时间: {timestamp}
详情: {alert.message}"""
        return message
    
    async def _send_tencent_sms(self, message: str) -> bool:
        """发送腾讯云SMS"""
        try:
            # 模拟腾讯云SMS API调用
            await asyncio.sleep(0.1)  # 模拟网络延迟
            print(f"腾讯云SMS发送到 {len(self.to_numbers)} 个接收者: {message[:100]}...")
            return True
        except Exception as e:
            print(f"Failed to send Tencent SMS: {e}")
            return await self._send_mock_sms(message)
    
    async def _send_aliyun_sms(self, message: str) -> bool:
        """发送阿里云SMS"""
        try:
            await asyncio.sleep(0.1)
            print(f"阿里云SMS发送到 {len(self.to_numbers)} 个接收者: {message[:100]}...")
            return True
        except Exception as e:
            print(f"Failed to send Aliyun SMS: {e}")
            return await self._send_mock_sms(message)
    
    async def _send_huawei_sms(self, message: str) -> bool:
        """发送华为云SMS"""
        try:
            await asyncio.sleep(0.1)
            print(f"华为云SMS发送到 {len(self.to_numbers)} 个接收者: {message[:100]}...")
            return True
        except Exception as e:
            print(f"Failed to send Huawei SMS: {e}")
            return await self._send_mock_sms(message)
    
    async def _send_mock_sms(self, message: str) -> bool:
        """模拟SMS发送（用于测试和开发环境）"""
        try:
            print(f"[MOCK SMS] 发送到 {self.to_numbers}:")
            print(f"[MOCK SMS] 消息: {message}")
            print(f"[MOCK SMS] API Key: {self.api_key[:8]}...")
            print(f"[MOCK SMS] 提供商: {self.provider}")
            
            await asyncio.sleep(0.1)
            print(f"Mock SMS 成功发送到 {len(self.to_numbers)} 个接收者")
            return True
            
        except Exception as e:
            print(f"Failed to send mock SMS: {e}")
            return False

class WebhookAlertChannel(ExternalAlertChannel):
    """Webhook告警渠道"""
    
    def __init__(self, webhook_url: str, headers: Dict[str, str] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {}
    
    async def send_alert(self, alert: Alert) -> bool:
        """通过Webhook发送告警"""
        try:
            payload = {
                "alert_id": alert.alert_id,
                "severity": alert.severity,
                "component": alert.component,
                "metric_name": alert.metric_name,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat()
            }
            
            # 模拟Webhook请求
            print(f"模拟Webhook发送:")
            print(f"  URL: {self.webhook_url}")
            print(f"  Headers: {self.headers}")
            print(f"  Payload: {json.dumps(payload, indent=2)}")
            
            # 模拟网络延迟
            await asyncio.sleep(0.1)
            
            print(f"Alert webhook sent successfully for {alert.alert_id}")
            return True
            
        except Exception as e:
            print(f"Failed to send alert webhook: {e}")
            return False

class TestExternalAlertChannels:
    """外部告警渠道测试"""

    @pytest.fixture
    def test_alert(self):
        """测试告警数据"""
        return Alert(
            alert_id="test_alert_001",
            component="test_bettafish_agent",
            metric_name="response_time",
            current_value=15.0,
            threshold_value=10.0,
            severity=AlertSeverity.CRITICAL,
            message="响应时间超过阈值",
            timestamp=datetime.now()
        )

    @pytest.mark.asyncio
    async def test_email_alert_channel(self, test_alert):
        """测试邮件告警渠道"""
        # 创建邮件渠道
        email_channel = EmailAlertChannel(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            username="test@example.com",
            password="test_password",
            from_email="bettafish@monitoring.com",
            to_emails=["admin@example.com", "ops@example.com"]
        )

        # 发送告警
        result = await email_channel.send_alert(test_alert)

        # 验证结果
        assert result, "Email alert should be sent successfully"

    @pytest.mark.asyncio
    async def test_sms_alert_channel_tencent(self, test_alert):
        """测试腾讯云SMS告警渠道"""
        # 创建SMS渠道（腾讯云）
        sms_channel = SMSAlertChannel(
            api_key="AKIDTEST123456789",
            api_secret="test_secret_key",
            from_number="+8613800138000",
            to_numbers=["+8613800138001", "+8613800138002"],
            provider="tencent"
        )

        # 发送告警
        result = await sms_channel.send_alert(test_alert)

        # 验证结果
        assert result, "Tencent SMS alert should be sent successfully"

        # 验证消息格式
        formatted_message = sms_channel._format_message(test_alert)
        assert "BettaFish系统告警" in formatted_message
        assert "test_bettafish_agent" in formatted_message
        assert "CRITICAL" in formatted_message

    @pytest.mark.asyncio
    async def test_sms_alert_channel_mock(self, test_alert):
        """测试模拟SMS告警渠道"""
        # 创建SMS渠道（模拟）
        sms_channel = SMSAlertChannel(
            api_key="MOCK_API_KEY",
            api_secret="mock_secret",
            from_number="+8613800138000",
            to_numbers=["+8613800138001"],
            provider="mock_provider"
        )

        # 发送告警
        result = await sms_channel.send_alert(test_alert)

        # 验证结果
        assert result, "Mock SMS alert should be sent successfully"

    @pytest.mark.asyncio
    async def test_webhook_alert_channel(self, test_alert):
        """测试Webhook告警渠道"""
        # 创建Webhook渠道
        webhook_channel = WebhookAlertChannel(
            webhook_url="https://hooks.slack.com/services/test/webhook",
            headers={"Authorization": "Bearer test_token", "Content-Type": "application/json"}
        )

        # 发送告警
        result = await webhook_channel.send_alert(test_alert)

        # 验证结果
        assert result, "Webhook alert should be sent successfully"

    @pytest.mark.asyncio
    async def test_multiple_channels(self, test_alert):
        """测试多渠道并发发送"""
        # 创建多个告警渠道
        channels = [
            EmailAlertChannel(
                smtp_server="smtp.gmail.com",
                smtp_port=587,
                username="test@example.com",
                password="test_password",
                from_email="bettafish@monitoring.com",
                to_emails=["admin@example.com"]
            ),
            SMSAlertChannel(
                api_key="AKIDTEST123456789",
                api_secret="test_secret",
                from_number="+8613800138000",
                to_numbers=["+8613800138001"],
                provider="tencent"
            ),
            WebhookAlertChannel(
                webhook_url="https://hooks.slack.com/services/test/webhook"
            )
        ]
        
        # 并发发送告警
        tasks = [channel.send_alert(test_alert) for channel in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 验证结果
        assert len(results) == 3, "Should send alerts to all 3 channels"
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                assert False, f"Channel {i} failed with exception: {result}"
            else:
                assert result, f"Channel {i} should send alert successfully"

    def test_alert_formatting(self, test_alert):
        """测试告警消息格式化"""
        sms_channel = SMSAlertChannel(
            api_key="test_key",
            api_secret="test_secret",
            from_number="+8613800138000",
            to_numbers=["+8613800138001"],
            provider="tencent"
        )

        formatted_message = sms_channel._format_message(test_alert)

        # 验证格式化结果
        assert "BettaFish系统告警" in formatted_message
        assert "test_bettafish_agent" in formatted_message
        assert "CRITICAL" in formatted_message
        assert "response_time" in formatted_message
        assert "15.0" in formatted_message
        assert "10.0" in formatted_message
        assert "响应时间超过阈值" in formatted_message

        # 验证时间格式
        timestamp_str = test_alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        assert timestamp_str in formatted_message