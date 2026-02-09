#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险监控模块通知功能单元测试

测试覆盖范围：
1. 通知服务暂停/恢复功能
2. 告警通知配置传递机制
3. RiskAlert 和 RiskRule 通知字段
4. 通知发送方法的参数传递
"""

import sys
import os
import tempfile
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

import pytest

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger


class TestNotificationServicePauseResume:
    """测试通知服务暂停/恢复功能"""

    def test_pause_service(self):
        """测试暂停通知服务"""
        try:
            from core.services.notification_service import NotificationService

            service = NotificationService()
            service._do_initialize()

            assert service.is_notification_paused() == False, "初始状态应为未暂停"

            result = service.pause_notification_service()
            assert result == True, "暂停操作应返回成功"
            assert service.is_notification_paused() == True, "暂停后状态应为True"

            service._do_dispose()
            logger.info("✓ 测试暂停通知服务通过")

        except Exception as e:
            logger.error(f"✗ 测试暂停通知服务失败: {e}")
            raise

    def test_resume_service(self):
        """测试恢复通知服务"""
        try:
            from core.services.notification_service import NotificationService

            service = NotificationService()
            service._do_initialize()

            service.pause_notification_service()
            assert service.is_notification_paused() == True, "暂停后状态应为True"

            result = service.resume_notification_service()
            assert result == True, "恢复操作应返回成功"
            assert service.is_notification_paused() == False, "恢复后状态应为False"

            service._do_dispose()
            logger.info("✓ 测试恢复通知服务通过")

        except Exception as e:
            logger.error(f"✗ 测试恢复通知服务失败: {e}")
            raise

    def test_stop_all_notifications(self):
        """测试完全停止通知服务（包含队列清理）"""
        try:
            from core.services.notification_service import NotificationService

            service = NotificationService()
            service._do_initialize()

            with service._message_lock:
                service._pending_messages.append("test_message_1")
                service._pending_messages.append("test_message_2")

            assert len(service._pending_messages) == 2, "应有2条待发送消息"

            result = service.stop_all_notifications()
            assert result == True, "停止操作应返回成功"
            assert service.is_notification_paused() == True, "停止后应处于暂停状态"
            assert len(service._pending_messages) == 0, "队列应被清空"

            service.resume_notification_service()
            service._do_dispose()
            logger.info("✓ 测试完全停止通知服务通过")

        except Exception as e:
            logger.error(f"✗ 测试完全停止通知服务失败: {e}")
            raise

    def test_pause_resume_toggle(self):
        """测试暂停/恢复切换功能"""
        try:
            from core.services.notification_service import NotificationService

            service = NotificationService()
            service._do_initialize()

            for i in range(3):
                service.pause_notification_service()
                assert service.is_notification_paused() == True, f"第{i+1}次暂停后状态错误"

                service.resume_notification_service()
                assert service.is_notification_paused() == False, f"第{i+1}次恢复后状态错误"

            service._do_dispose()
            logger.info("✓ 测试暂停/恢复切换通过")

        except Exception as e:
            logger.error(f"✗ 测试暂停/恢复切换失败: {e}")
            raise


class TestRiskAlertNotificationFields:
    """测试 RiskAlert 通知字段"""

    def test_risk_alert_notification_fields_default(self):
        """测试 RiskAlert 默认通知字段"""
        try:
            from core.risk_rule_manager import RiskAlert

            alert = RiskAlert()

            assert alert.email_notification == False, "邮件通知默认应为False"
            assert alert.sms_notification == False, "短信通知默认应为False"
            assert alert.desktop_notification == True, "桌面通知默认应为True"
            assert alert.sound_notification == True, "声音通知默认应为True"
            assert alert.webhook_notification == False, "Webhook通知默认应为False"
            assert alert.dingtalk_notification == False, "钉钉通知默认应为False"

            assert alert.email_recipients == "", "邮件收件人默认应为空"
            assert alert.sms_recipients == "", "短信收件人默认应为空"
            assert alert.webhook_url == "", "Webhook URL默认应为空"
            assert alert.dingtalk_webhook_url == "", "钉钉Webhook URL默认应为空"

            logger.info("✓ 测试 RiskAlert 默认通知字段通过")

        except Exception as e:
            logger.error(f"✗ 测试 RiskAlert 默认通知字段失败: {e}")
            raise

    def test_risk_alert_notification_fields_custom(self):
        """测试 RiskAlert 自定义通知字段"""
        try:
            from core.risk_rule_manager import RiskAlert

            alert = RiskAlert(
                rule_id=1,
                rule_name="测试规则",
                metric_name="VaR(95%)",
                metric_value=15.5,
                threshold_value=10.0,
                alert_level="高",
                message="测试告警消息",
                email_notification=True,
                sms_notification=True,
                desktop_notification=True,
                sound_notification=False,
                webhook_notification=True,
                dingtalk_notification=False,
                email_recipients="test@example.com",
                sms_recipients="13800138000",
                webhook_url="https://hooks.example.com/test",
                dingtalk_webhook_url=""
            )

            assert alert.email_notification == True, "邮件通知应启用"
            assert alert.sms_notification == True, "短信通知应启用"
            assert alert.desktop_notification == True, "桌面通知应启用"
            assert alert.sound_notification == False, "声音通知应禁用"
            assert alert.webhook_notification == True, "Webhook通知应启用"
            assert alert.dingtalk_notification == False, "钉钉通知应禁用"

            assert alert.email_recipients == "test@example.com", "邮件收件人应正确设置"
            assert alert.sms_recipients == "13800138000", "短信收件人应正确设置"
            assert alert.webhook_url == "https://hooks.example.com/test", "Webhook URL应正确设置"
            assert alert.dingtalk_webhook_url == "", "钉钉Webhook URL应为空"

            logger.info("✓ 测试 RiskAlert 自定义通知字段通过")

        except Exception as e:
            logger.error(f"✗ 测试 RiskAlert 自定义通知字段失败: {e}")
            raise


class TestRiskRuleNotificationFields:
    """测试 RiskRule 通知字段"""

    def test_risk_rule_notification_fields(self):
        """测试 RiskRule 通知字段"""
        try:
            from core.risk_rule_manager import RiskRule

            rule = RiskRule(
                name="测试风险规则",
                rule_type="VaR风险",
                metric_name="VaR(95%)",
                operator=">",
                threshold_value=10.0,
                email_notification=True,
                sms_notification=False,
                desktop_notification=True,
                sound_notification=True,
                webhook_notification=False,
                dingtalk_notification=True,
                email_recipients="admin@example.com",
                sms_recipients="13900139000",
                webhook_url="",
                dingtalk_webhook_url="https://oapi.dingtalk.com/robot/send?token=xxx"
            )

            assert rule.email_notification == True, "邮件通知应启用"
            assert rule.sms_notification == False, "短信通知应禁用"
            assert rule.desktop_notification == True, "桌面通知应启用"
            assert rule.sound_notification == True, "声音通知应启用"
            assert rule.webhook_notification == False, "Webhook通知应禁用"
            assert rule.dingtalk_notification == True, "钉钉通知应启用"

            assert rule.email_recipients == "admin@example.com", "邮件收件人应正确设置"
            assert rule.sms_recipients == "13900139000", "短信收件人应正确设置"
            assert rule.webhook_url == "", "Webhook URL应为空"
            assert rule.dingtalk_webhook_url == "https://oapi.dingtalk.com/robot/send?token=xxx", "钉钉Webhook URL应正确设置"

            logger.info("✓ 测试 RiskRule 通知字段通过")

        except Exception as e:
            logger.error(f"✗ 测试 RiskRule 通知字段失败: {e}")
            raise


class TestAlertCreationWithNotificationConfig:
    """测试告警创建时通知配置的传递"""

    def test_create_alert_with_notification_config(self):
        """测试创建告警时复制通知配置"""
        try:
            from core.risk_rule_manager import RiskRule, RiskAlert
            from datetime import datetime

            rule = RiskRule(
                id=1,
                name="测试VaR规则",
                rule_type="VaR风险",
                priority="高",
                metric_name="VaR(95%)",
                operator=">",
                threshold_value=10.0,
                threshold_unit="%",
                message_template="【风险告警】{rule_name}：{metric} = {value}，超过阈值 {threshold}",
                email_notification=True,
                sms_notification=True,
                desktop_notification=True,
                sound_notification=False,
                webhook_notification=True,
                dingtalk_notification=False,
                email_recipients="risk@example.com",
                sms_recipients="18600186000",
                webhook_url="https://webhook.example.com/alert",
                dingtalk_webhook_url=""
            )

            risk_metrics = {"VaR(95%)": 12.5}

            from core.risk_rule_manager import RiskRuleManager
            manager = RiskRuleManager.__new__(RiskRuleManager)
            manager.db_path = ':memory:'
            manager._last_check_time = {}
            manager._notification_config = {"enable_deduplication": False}

            alert = manager._create_alert(rule, risk_metrics)

            assert alert is not None, "告警创建应成功"

            assert alert.rule_id == 1, "规则ID应正确传递"
            assert alert.rule_name == "测试VaR规则", "规则名称应正确传递"
            assert alert.metric_name == "VaR(95%)", "指标名称应正确传递"
            assert alert.metric_value == 12.5, "指标值应正确传递"
            assert alert.threshold_value == 10.0, "阈值应正确传递"
            assert alert.alert_level == "高", "告警级别应正确传递"

            assert alert.email_notification == True, "邮件通知配置应正确传递"
            assert alert.sms_notification == True, "短信通知配置应正确传递"
            assert alert.desktop_notification == True, "桌面通知配置应正确传递"
            assert alert.sound_notification == False, "声音通知配置应正确传递"
            assert alert.webhook_notification == True, "Webhook通知配置应正确传递"
            assert alert.dingtalk_notification == False, "钉钉通知配置应正确传递"

            assert alert.email_recipients == "risk@example.com", "邮件收件人应正确传递"
            assert alert.sms_recipients == "18600186000", "短信收件人应正确传递"
            assert alert.webhook_url == "https://webhook.example.com/alert", "Webhook URL应正确传递"
            assert alert.dingtalk_webhook_url == "", "钉钉Webhook URL应正确传递"

            logger.info("✓ 测试告警创建时通知配置传递通过")

        except Exception as e:
            logger.error(f"✗ 测试告警创建时通知配置传递失败: {e}")
            raise


class TestNotificationDispatch:
    """测试通知分发逻辑"""

    def test_getattr_with_default_values(self):
        """测试 getattr 获取带默认值的通知配置"""
        try:
            from core.risk_rule_manager import RiskAlert

            alert_with_config = RiskAlert(
                rule_id=1,
                rule_name="测试规则",
                email_notification=True,
                desktop_notification=False
            )

            assert getattr(alert_with_config, 'email_notification', True) == True
            assert getattr(alert_with_config, 'desktop_notification', True) == False
            assert getattr(alert_with_config, 'sms_notification', False) == False
            assert getattr(alert_with_config, 'sound_notification', True) == True

            alert_without_config = RiskAlert(
                rule_id=2,
                rule_name="旧版告警"
            )

            assert getattr(alert_without_config, 'email_notification', False) == False
            assert getattr(alert_without_config, 'desktop_notification', True) == True
            assert getattr(alert_without_config, 'sound_notification', True) == True
            assert getattr(alert_without_config, 'sms_notification', False) == False

            logger.info("✓ 测试 getattr 默认值获取通过")

        except Exception as e:
            logger.error(f"✗ 测试 getattr 默认值获取失败: {e}")
            raise

    def test_notification_dispatch_logic(self):
        """测试通知分发逻辑"""
        try:
            from core.risk_rule_manager import RiskAlert

            email_alert = RiskAlert(
                rule_id=1,
                rule_name="邮件规则",
                email_notification=True,
                sms_notification=False,
                desktop_notification=False,
                sound_notification=False,
                webhook_notification=False,
                dingtalk_notification=False,
                email_recipients="test@example.com"
            )

            sms_alert = RiskAlert(
                rule_id=2,
                rule_name="短信规则",
                email_notification=False,
                sms_notification=True,
                desktop_notification=False,
                sound_notification=False,
                webhook_notification=False,
                dingtalk_notification=False,
                sms_recipients="13800138000"
            )

            all_channel_alert = RiskAlert(
                rule_id=3,
                rule_name="全渠道规则",
                email_notification=True,
                sms_notification=True,
                desktop_notification=True,
                sound_notification=True,
                webhook_notification=True,
                dingtalk_notification=True,
                email_recipients="admin@example.com",
                sms_recipients="13900139000",
                webhook_url="https://hooks.example.com",
                dingtalk_webhook_url="https://oapi.dingtalk.com/robot/send?token=xxx"
            )

            email_channels = []
            if getattr(email_alert, 'email_notification', False):
                email_channels.append('email')
            if getattr(email_alert, 'sms_notification', False):
                email_channels.append('sms')
            if getattr(email_alert, 'desktop_notification', True):
                email_channels.append('desktop')
            if getattr(email_alert, 'sound_notification', True):
                email_channels.append('sound')
            if getattr(email_alert, 'webhook_notification', False):
                email_channels.append('webhook')
            if getattr(email_alert, 'dingtalk_notification', False):
                email_channels.append('dingtalk')

            assert email_channels == ['email'], f"邮件告警渠道应为['email']，实际为{email_channels}"

            sms_channels = []
            if getattr(sms_alert, 'email_notification', False):
                sms_channels.append('email')
            if getattr(sms_alert, 'sms_notification', False):
                sms_channels.append('sms')
            if getattr(sms_alert, 'desktop_notification', True):
                sms_channels.append('desktop')
            if getattr(sms_alert, 'sound_notification', True):
                sms_channels.append('sound')
            if getattr(sms_alert, 'webhook_notification', False):
                sms_channels.append('webhook')
            if getattr(sms_alert, 'dingtalk_notification', False):
                sms_channels.append('dingtalk')

            assert sms_channels == ['sms'], f"短信告警渠道应为['sms']，实际为{sms_channels}"

            all_channels = []
            if getattr(all_channel_alert, 'email_notification', False):
                all_channels.append('email')
            if getattr(all_channel_alert, 'sms_notification', False):
                all_channels.append('sms')
            if getattr(all_channel_alert, 'desktop_notification', True):
                all_channels.append('desktop')
            if getattr(all_channel_alert, 'sound_notification', True):
                all_channels.append('sound')
            if getattr(all_channel_alert, 'webhook_notification', False):
                all_channels.append('webhook')
            if getattr(all_channel_alert, 'dingtalk_notification', False):
                all_channels.append('dingtalk')

            assert all_channels == ['email', 'sms', 'desktop', 'sound', 'webhook', 'dingtalk'], \
                f"全渠道告警渠道应有6个，实际为{len(all_channels)}个"

            logger.info("✓ 测试通知分发逻辑通过")

        except Exception as e:
            logger.error(f"✗ 测试通知分发逻辑失败: {e}")
            raise


class TestSendNotificationParameters:
    """测试通知发送方法参数"""

    def test_send_notification_parameter_name(self):
        """测试 send_notification 方法参数名"""
        try:
            from core.services.notification_service import NotificationService

            service = NotificationService()
            service._notification_config = {"enable_deduplication": False}
            service._do_initialize()

            timestamp = datetime.now().isoformat()

            with patch.object(service, '_send_message_internal') as mock_send:
                result = service.send_notification(
                    title=f"测试标题 {timestamp}",
                    content=f"测试内容 {timestamp}",
                    channels=["default_email"],
                    notification_config={'email_recipients': 'test@example.com'}
                )

                assert result != "", "send_notification应返回消息ID"

                assert len(service._pending_messages) == 1, \
                    f"消息应被添加到队列，实际数量: {len(service._pending_messages)}"

                message = service._pending_messages[0]
                assert 'email_recipients' in message.metadata, \
                    "notification_config应合并到metadata"
                assert message.metadata['email_recipients'] == 'test@example.com', \
                    "email_recipients值应正确传递"

            service._do_dispose()
            logger.info("✓ 测试 send_notification 参数名通过")

        except Exception as e:
            logger.error(f"✗ 测试 send_notification 参数名失败: {e}")
            raise

    def test_email_notification_with_recipients(self):
        """测试邮件通知收件人传递"""
        try:
            from core.services.notification_service import NotificationService

            service = NotificationService()
            service._notification_config = {"enable_deduplication": False}
            service._do_initialize()

            timestamp = datetime.now().isoformat()

            service.send_notification(
                title=f"[高] VaR风险告警 {timestamp}",
                content=f"当前VaR(95%)达到12.5%，超过阈值10% - {timestamp}",
                channels=["default_email"],
                notification_config={
                    'email_recipients': 'admin@example.com,risk@example.com'
                }
            )

            assert len(service._pending_messages) == 1, \
                f"消息应被添加到队列，实际数量: {len(service._pending_messages)}"

            message = service._pending_messages[0]
            recipients = message.metadata.get('email_recipients', '')
            assert recipients == 'admin@example.com,risk@example.com', \
                f"收件人应为'admin@example.com,risk@example.com'，实际为'{recipients}'"

            service._do_dispose()
            logger.info("✓ 测试邮件通知收件人传递通过")

        except Exception as e:
            logger.error(f"✗ 测试邮件通知收件人传递失败: {e}")
            raise


class TestRuleConfigDialogHint:
    """测试规则配置对话框提示文字"""

    def test_dialog_has_notification_hint(self):
        """测试对话框包含通知配置提示"""
        try:
            import sys
            from pathlib import Path

            dialog_path = Path(__file__).parent.parent / 'gui' / 'dialogs' / 'risk_rule_config_dialog.py'

            if not dialog_path.exists():
                pytest.skip("risk_rule_config_dialog.py 不存在，跳过测试")

            content = dialog_path.read_text(encoding='utf-8')

            assert '提示：如需配置邮件服务器、钉钉Webhook等通知渠道' in content, \
                "对话框应包含通知配置提示文字"
            assert '告警配置' in content, \
                "提示应指引用户前往告警配置页面"
            assert '配置通知服务' in content, \
                "提示应提及配置通知服务按钮"

            assert 'open_notification_config' not in content or \
                   content.count('open_notification_config') <= 1, \
                "重复的open_notification_config方法应被移除"

            logger.info("✓ 测试规则配置对话框提示文字通过")

        except Exception as e:
            logger.error(f"✗ 测试规则配置对话框提示文字失败: {e}")
            raise


def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("开始运行风险监控模块通知功能测试")
    logger.info("=" * 60)

    test_classes = [
        TestNotificationServicePauseResume,
        TestRiskAlertNotificationFields,
        TestRiskRuleNotificationFields,
        TestAlertCreationWithNotificationConfig,
        TestNotificationDispatch,
        TestSendNotificationParameters,
        TestRuleConfigDialogHint,
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_class in test_classes:
        logger.info(f"\n{'=' * 40}")
        logger.info(f"测试类: {test_class.__name__}")
        logger.info(f"{'=' * 40}")

        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in methods:
            try:
                method = getattr(instance, method_name)
                method()
                passed += 1
            except pytest.skip.Exception as e:
                logger.warning(f"⏭ 跳过: {method_name}: {e}")
                skipped += 1
            except Exception as e:
                logger.error(f"✗ 失败: {method_name}: {e}")
                failed += 1

    logger.info(f"\n{'=' * 60}")
    logger.info(f"测试完成统计")
    logger.info(f"{'=' * 60}")
    logger.info(f"通过: {passed}")
    logger.info(f"失败: {failed}")
    logger.info(f"跳过: {skipped}")
    logger.info(f"{'=' * 60}")

    if failed > 0:
        return False
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
