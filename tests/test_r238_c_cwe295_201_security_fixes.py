# -*- coding: utf-8 -*-
"""R238-NEW-P1 CWE-295/CWE-201 安全修复 TDD 测试

验证:
- cloud_api_service: enable_ssl=False 生产环境拒绝 + 显式 warning (CWE-295)
- notification_service: webhook 日志脱敏 (CWE-201)

强约束: CWE-295 + CWE-201 + R51 #5 显式降级日志
TDD: tests/test_r238_c_cwe295_201_security_fixes.py
"""

import os
import unittest
from unittest.mock import patch


class TestCloudAPICWE295(unittest.TestCase):
    """R238-NEW-P1-CWE-295: SSL 验证禁用防护"""

    def test_T01_production_env_rejects_ssl_disabled(self):
        """T01: HIKYUU_APP_ENV=production 时 enable_ssl=False 必须拒绝"""
        os.environ['HIKYUU_APP_ENV'] = 'production'
        try:
            from core.services.cloud_api_service import CloudAPIClient, CloudConfig
            config = CloudConfig(
                api_url='https://api.example.com',
                api_key='test-key',
                secret_key='test-secret',
                enable_ssl=False,
            )
            with self.assertRaises(RuntimeError) as ctx:
                CloudAPIClient(config)
            self.assertIn("CWE-295", str(ctx.exception), "生产环境必须拒绝禁用 SSL")
        finally:
            os.environ['HIKYUU_APP_ENV'] = 'dev'

    def test_T02_dev_env_ssl_disabled_warns(self):
        """T02: dev 环境 enable_ssl=False 记录显式 warning (不静默)"""
        os.environ['HIKYUU_APP_ENV'] = 'dev'
        try:
            from core.services.cloud_api_service import CloudAPIClient, CloudConfig
            config = CloudConfig(
                api_url='https://api.example.com',
                api_key='test-key',
                secret_key='test-secret',
                enable_ssl=False,
            )
            with patch('core.services.cloud_api_service.logger') as mock_logger:
                client = CloudAPIClient(config)
                self.assertIsNotNone(client.session, "客户端应可构造")
                warned = any(
                    'CWE-295' in str(call)
                    for call in mock_logger.warning.call_args_list
                )
                self.assertTrue(warned, "dev 环境禁用 SSL 应显式 warning (R51 #5)")
        finally:
            os.environ['HIKYUU_APP_ENV'] = 'dev'

    def test_T03_ssl_enabled_no_warning(self):
        """T03: enable_ssl=True 正常构造, 无 CWE-295 warning"""
        os.environ['HIKYUU_APP_ENV'] = 'dev'
        try:
            from core.services.cloud_api_service import CloudAPIClient, CloudConfig
            config = CloudConfig(
                api_url='https://api.example.com',
                api_key='test-key',
                secret_key='test-secret',
                enable_ssl=True,
            )
            with patch('core.services.cloud_api_service.logger') as mock_logger:
                client = CloudAPIClient(config)
                for call in mock_logger.warning.call_args_list:
                    self.assertNotIn('CWE-295', str(call), "启用 SSL 不应有 CWE-295 warning")
        finally:
            os.environ['HIKYUU_APP_ENV'] = 'dev'


class TestNotificationCWE201(unittest.TestCase):
    """R238-NEW-P1-CWE-201: webhook 日志脱敏"""

    def _make_channel(self, webhook_url):
        """构造 NotificationChannel (R231 §13.3: dataclass, 非枚举)"""
        from core.services.notification_service import (
            NotificationChannel, NotificationType,
        )
        return NotificationChannel(
            channel_id='ch_webhook_test',
            name='测试Webhook',
            notification_type=NotificationType.WEBHOOK,
            config={'webhook_url': webhook_url},
        )

    def _make_message(self):
        """构造 AlertMessage (dataclass)"""
        from core.services.notification_service import AlertMessage, AlertLevel, AlertStatus
        return AlertMessage(
            message_id='msg_1',
            rule_id='rule_1',
            alert_level=AlertLevel.INFO,
            title='测试告警',
            content='内容',
            channels=['ch_webhook_test'],
            status=AlertStatus.PENDING,
        )

    def _call_send_webhook(self, webhook_url):
        """调用 NotificationService._send_webhook_notification 且 mock urlopen 返回 200"""
        from core.services.notification_service import NotificationService
        svc = NotificationService.__new__(NotificationService)
        message = self._make_message()
        channel = self._make_channel(webhook_url)

        class FakeResp:
            def getcode(self):
                return 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        with patch('urllib.request.urlopen', return_value=FakeResp()) as mock_urlopen:
            with patch('core.services.notification_service.logger') as mock_logger:
                svc._send_webhook_notification(message, channel)
        return mock_logger, mock_urlopen

    def test_T01_log_masks_query_params(self):
        """T01: 日志输出剥离 query 参数 (含 access_token)"""
        secret_url = 'https://oapi.dingtalk.com/robot/send?access_token=SECRET_TOKEN_123'
        mock_logger, _ = self._call_send_webhook(secret_url)
        logged = ''.join(str(c) for c in mock_logger.info.call_args_list)
        self.assertNotIn('SECRET_TOKEN_123', logged, "日志不得泄露 secret token (CWE-201)")
        self.assertIn('oapi.dingtalk.com/robot/send', logged, "日志应保留 host+path 便于排查")

    def test_T02_normal_url_still_logged(self):
        """T02: 无 query 的 URL 正常记录"""
        plain_url = 'https://hooks.example.com/webhook123'
        mock_logger, _ = self._call_send_webhook(plain_url)
        logged = ''.join(str(c) for c in mock_logger.info.call_args_list)
        self.assertIn('hooks.example.com/webhook123', logged, "无敏感参数 URL 应完整记录")


if __name__ == '__main__':
    unittest.main()
