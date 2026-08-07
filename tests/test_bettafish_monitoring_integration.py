"""
BettaFish监控集成测试
测试高级监控服务与EventBus系统的集成功能
"""

import asyncio
import unittest
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import json
from typing import Dict, Any

from core.services.bettafish_advanced_monitoring_service import (
    BettaFishAdvancedMonitoringService, 
    EmailAlertChannel, 
    SMSAlertChannel, 
    WebhookAlertChannel,
    TrendDirection
)
from core.services.bettafish_monitoring_integration import (
    BettaFishMonitoringIntegration,
    create_test_monitoring_integration
)
from core.services.bettafish_monitoring_service import (
    AlertSeverity, ComponentStatus
)
from core.events.event_bus import EventBus


class TestBettaFishMonitoringIntegration(unittest.TestCase):
    """BettaFish监控集成测试"""

    def setUp(self):
        """设置测试环境"""
        self.event_bus = EventBus()
        self.integration = BettaFishMonitoringIntegration(self.event_bus)
        
        # 测试配置
        self.test_config = {
            "external_alerts": {
                "email": {
                    "enabled": False
                },
                "sms": {
                    "enabled": False
                },
                "webhook": {
                    "enabled": False
                }
            },
            "thresholds": {
                "performance": {
                    "bettafish_agent": {
                        "response_time": {"warning": 3.0, "critical": 10.0},
                        "error_rate": {"warning": 0.05, "critical": 0.15}
                    }
                },
                "trend_analysis": {
                    "window_size": 6,
                    "min_data_points": 5,
                    "confidence_threshold": 0.5,
                    "change_rate_threshold": 0.1
                },
                "anomaly_detection": {
                    "window_size": 6,
                    "min_data_points": 5,
                    "z_score_threshold": 2.0,
                    "iqr_multiplier": 1.0
                }
            },
            "visualization": {
                "enabled": False,
                "update_interval": 30
            }
        }

    def test_integration_initialization(self):
        """测试集成初始化"""
        # 配置集成服务
        self.integration.configure(self.test_config)
        
        # 初始化集成服务
        self.assertFalse(self.integration.is_initialized)
        
        # 使用asyncio.run来执行异步初始化
        asyncio.run(self.integration.initialize())
        
        # 检查初始化状态
        self.assertTrue(self.integration.is_initialized)
        self.assertIsNotNone(self.integration.advanced_monitoring_service)
        
        # 验证监控服务已启动
        monitoring_service = self.integration.get_monitoring_service()
        self.assertIsNotNone(monitoring_service)
        self.assertTrue(monitoring_service.monitoring_active)

    async def async_test_external_alert_channels(self):
        """测试外部告警渠道注册"""
        # 创建模拟邮件告警渠道
        email_channel = Mock(spec=EmailAlertChannel)
        email_channel.send_alert = AsyncMock(return_value=True)
        
        # 注册外部告警渠道
        monitoring_service = self.integration.get_monitoring_service()
        self.assertIsNotNone(monitoring_service)
        
        monitoring_service.register_external_alert_channel(email_channel)
        self.assertEqual(len(monitoring_service.external_alert_channels), 1)
        self.assertIs(monitoring_service.external_alert_channels[0], email_channel)

    def test_event_listeners_registration(self):
        """测试事件监听器注册"""
        # 配置并初始化集成服务
        self.integration.configure(self.test_config)
        asyncio.run(self.integration.initialize())
        
        # 检查事件监听器是否已注册
        self.assertIn("service.started", self.event_bus._handlers)
        self.assertIn("service.stopped", self.event_bus._handlers)
        self.assertIn("service.error", self.event_bus._handlers)
        self.assertIn("bettafish.agent.started", self.event_bus._handlers)
        self.assertIn("bettafish.agent.stopped", self.event_bus._handlers)
        self.assertIn("bettafish.analysis.completed", self.event_bus._handlers)
        self.assertIn("bettafish.analysis.failed", self.event_bus._handlers)

    async def async_test_event_handling(self):
        """测试事件处理"""
        # 配置并初始化集成服务
        self.integration.configure(self.test_config)
        await self.integration.initialize()
        
        # 发布测试事件
        service_started_event = {
            "service_name": "test_service"
        }
        self.event_bus.publish("service.started", **service_started_event)
        
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        # 发布BettaFish相关事件
        bettafish_agent_started_event = {
            "agent_name": "test_bettafish_agent"
        }
        self.event_bus.publish("bettafish.agent.started", **bettafish_agent_started_event)
        
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        # 验证事件统计
        stats = self.event_bus.get_stats()
        self.assertGreater(stats['events_published'], 0)
        self.assertGreater(stats['events_handled'], 0)

    async def async_test_monitoring_functionality(self):
        """测试监控功能"""
        # 配置并初始化集成服务
        self.integration.configure(self.test_config)
        await self.integration.initialize()
        
        monitoring_service = self.integration.get_monitoring_service()
        self.assertIsNotNone(monitoring_service)
        
        # 添加测试组件健康状态 (R238 修复: 必须用 _check_all_components 实际检查的组件名
        # "bettafish_agent", 否则 metrics_history 无数据, 趋势分析查询 0 点)
        test_component = "bettafish_agent"
        monitoring_service.component_health[test_component] = {
            "status": ComponentStatus.HEALTHY,
            "last_check": datetime.now(),
            "metrics": {
                "response_time": 2.5,
                "error_rate": 0.02,
                "success_count": 100,
                "error_count": 2
            }
        }
        
        # 手动触发监控检查 (R238 修复: 趋势分析要求 >= min_data_points=5 个数据点,
        # 单次检查仅 1 点, 循环 6 次积累足够历史数据)
        for _ in range(6):
            await monitoring_service._check_all_components()

        # 等待趋势分析和异常检测完成
        await asyncio.sleep(1)
        
        # 验证分析结果
        self.assertGreater(len(monitoring_service.performance_trends), 0)
        self.assertGreaterEqual(len(monitoring_service.anomaly_detection_results), 0)

    async def async_test_external_alert_sending(self):
        """测试外部告警发送"""
        # 创建模拟外部告警渠道
        mock_email_channel = Mock(spec=EmailAlertChannel)
        mock_email_channel.send_alert = AsyncMock(return_value=True)
        
        mock_sms_channel = Mock(spec=SMSAlertChannel)
        mock_sms_channel.send_alert = AsyncMock(return_value=True)
        
        mock_webhook_channel = Mock(spec=WebhookAlertChannel)
        mock_webhook_channel.send_alert = AsyncMock(return_value=True)
        
        # 配置并初始化集成服务
        self.integration.configure(self.test_config)
        await self.integration.initialize()
        
        monitoring_service = self.integration.get_monitoring_service()
        self.assertIsNotNone(monitoring_service)
        
        # 注册外部告警渠道
        monitoring_service.register_external_alert_channel(mock_email_channel)
        monitoring_service.register_external_alert_channel(mock_sms_channel)
        monitoring_service.register_external_alert_channel(mock_webhook_channel)
        
        # 创建一个测试告警
        from core.services.bettafish_monitoring_service import Alert
        test_alert = Alert(
            alert_id="test_alert_001",
            component="test_component",
            metric_name="response_time",
            current_value=15.0,
            threshold_value=10.0,
            severity=AlertSeverity.CRITICAL,
            message="响应时间超过阈值",
            timestamp=datetime.now()
        )
        
        # 发送外部告警
        await monitoring_service._send_external_alert_notifications(test_alert)
        
        # 验证所有外部告警渠道都被调用
        mock_email_channel.send_alert.assert_called_once_with(test_alert)
        mock_sms_channel.send_alert.assert_called_once_with(test_alert)
        mock_webhook_channel.send_alert.assert_called_once_with(test_alert)

    async def async_test_trend_analysis(self):
        """测试趋势分析功能"""
        # 配置并初始化集成服务
        self.integration.configure(self.test_config)
        await self.integration.initialize()
        
        monitoring_service = self.integration.get_monitoring_service()
        self.assertIsNotNone(monitoring_service)
        
        # 准备测试数据
        test_component = "test_bettafish_agent"
        test_metric = "response_time"
        
        # 生成测试历史数据
        base_time = datetime.now() - timedelta(hours=12)
        test_metrics = []
        for i in range(10):
            timestamp = base_time + timedelta(minutes=i*72)  # 每72分钟一个点，12小时内10个点
            value = 2.0 + i * 0.5  # 递增的趋势
            test_metrics.append(monitoring_service.PerformanceMetric(
                timestamp=timestamp,
                value=value,
                component=test_component,
                name=test_metric,
                metric_type=monitoring_service.MetricType.RESPONSE_TIME
            ))
        
        # 直接调用趋势分析方法
        trend_result = await monitoring_service._analyze_metric_trend(
            test_component, test_metric, test_metrics
        )
        
        # 验证趋势分析结果
        self.assertIsNotNone(trend_result)
        self.assertEqual(trend_result.component, test_component)
        self.assertEqual(trend_result.metric_name, test_metric)
        self.assertEqual(trend_result.direction, TrendDirection.UP)
        self.assertGreater(trend_result.change_rate, 0)
        self.assertGreater(trend_result.confidence, 0)

    async def async_test_anomaly_detection(self):
        """测试异常检测功能"""
        # 配置并初始化集成服务
        self.integration.configure(self.test_config)
        await self.integration.initialize()
        
        monitoring_service = self.integration.get_monitoring_service()
        self.assertIsNotNone(monitoring_service)
        
        # 准备测试数据（包含一个异常值）
        test_component = "test_bettafish_agent"
        test_metric = "response_time"
        
        # 生成正常数据 + 一个异常值
        base_time = datetime.now() - timedelta(hours=12)
        test_metrics = []
        for i in range(15):
            timestamp = base_time + timedelta(minutes=i*48)  # 每48分钟一个点
            if i == 10:  # 第10个点是异常值
                value = 20.0  # 远高于正常值
            else:
                value = 2.5 + (i * 0.1)  # 正常范围
            test_metrics.append(monitoring_service.PerformanceMetric(
                timestamp=timestamp,
                value=value,
                component=test_component,
                name=test_metric,
                metric_type=monitoring_service.MetricType.RESPONSE_TIME
            ))
        
        # 直接调用异常检测方法
        anomaly_result = await monitoring_service._detect_anomalies(
            test_component, test_metric, test_metrics
        )
        
        # 验证异常检测结果
        self.assertIsNotNone(anomaly_result)
        self.assertEqual(anomaly_result.component, test_component)
        self.assertEqual(anomaly_result.metric_name, test_metric)
        self.assertGreater(anomaly_result.anomaly_score, 0)

    async def async_test_shutdown(self):
        """测试服务关闭"""
        # 配置并初始化集成服务
        self.integration.configure(self.test_config)
        await self.integration.initialize()
        
        self.assertTrue(self.integration.is_initialized)
        
        # 关闭服务
        await self.integration.shutdown()
        
        # 验证服务已关闭
        self.assertFalse(self.integration.is_initialized)

    def test_create_test_integration(self):
        """测试创建测试监控集成"""
        async def run_test():
            test_integration = await create_test_monitoring_integration()
            
            self.assertIsNotNone(test_integration)
            self.assertTrue(test_integration.is_initialized)
            self.assertIsNotNone(test_integration.get_monitoring_service())
            
            # 关闭测试集成
            await test_integration.shutdown()
        
        asyncio.run(run_test())

    def run_async_test(self, test_func):
        """运行异步测试的辅助方法"""
        asyncio.run(test_func())

    def test_all_integration_features(self):
        """集成测试：测试所有集成功能"""
        # 配置集成服务
        self.integration.configure(self.test_config)
        
        # 初始化集成服务
        self.run_async_test(self.async_test_monitoring_functionality)
        
        # 测试外部告警渠道
        self.run_async_test(self.async_test_external_alert_channels)
        
        # 测试事件处理
        self.run_async_test(self.async_test_event_handling)
        
        # 测试外部告警发送
        self.run_async_test(self.async_test_external_alert_sending)
        
        # 测试趋势分析
        self.run_async_test(self.async_test_trend_analysis)
        
        # 测试异常检测
        self.run_async_test(self.async_test_anomaly_detection)
        
        # 测试服务关闭
        self.run_async_test(self.async_test_shutdown)
        
        # 验证最终状态
        self.assertFalse(self.integration.is_initialized)


class TestBettaFishAdvancedMonitoringService(unittest.TestCase):
    """BettaFish高级监控服务测试"""

    def setUp(self):
        """设置测试环境"""
        self.event_bus = EventBus()
        self.monitoring_service = BettaFishAdvancedMonitoringService(self.event_bus)

    def test_service_initialization(self):
        """测试服务初始化"""
        self.assertIsNotNone(self.monitoring_service)
        self.assertIsNotNone(self.monitoring_service.trend_analysis_config)
        self.assertIsNotNone(self.monitoring_service.anomaly_detection_config)
        self.assertEqual(len(self.monitoring_service.external_alert_channels), 0)
        self.assertEqual(len(self.monitoring_service.performance_trends), 0)
        self.assertEqual(len(self.monitoring_service.anomaly_detection_results), 0)

    def test_external_alert_channel_registration(self):
        """测试外部告警渠道注册"""
        # 创建模拟外部告警渠道
        mock_channel = Mock(spec=EmailAlertChannel)
        
        # 注册渠道
        self.monitoring_service.register_external_alert_channel(mock_channel)
        
        # 验证注册结果
        self.assertEqual(len(self.monitoring_service.external_alert_channels), 1)
        self.assertIs(self.monitoring_service.external_alert_channels[0], mock_channel)

    def test_configuration_updates(self):
        """测试配置更新"""
        # 测试趋势分析配置更新
        self.monitoring_service.trend_analysis_config["window_size"] = 48
        self.monitoring_service.trend_analysis_config["confidence_threshold"] = 0.8
        
        self.assertEqual(self.monitoring_service.trend_analysis_config["window_size"], 48)
        self.assertEqual(self.monitoring_service.trend_analysis_config["confidence_threshold"], 0.8)
        
        # 测试异常检测配置更新
        self.monitoring_service.anomaly_detection_config["z_score_threshold"] = 2.5
        self.monitoring_service.anomaly_detection_config["iqr_multiplier"] = 2.0
        
        self.assertEqual(self.monitoring_service.anomaly_detection_config["z_score_threshold"], 2.5)
        self.assertEqual(self.monitoring_service.anomaly_detection_config["iqr_multiplier"], 2.0)

    async def async_test_monitoring_start_stop(self):
        """测试监控启动和停止"""
        # 启动监控
        self.monitoring_service.start_monitoring()
        self.assertTrue(self.monitoring_service.monitoring_active)
        
        # 等待一小段时间
        await asyncio.sleep(1)
        
        # 停止监控
        await self.monitoring_service.shutdown()
        self.assertFalse(self.monitoring_service.monitoring_active)

    def run_async_test(self, test_func):
        """运行异步测试的辅助方法"""
        asyncio.run(test_func())

    def test_monitoring_lifecycle(self):
        """测试监控生命周期"""
        self.run_async_test(self.async_test_monitoring_start_stop)


if __name__ == '__main__':
    # 运行所有测试
    unittest.main(verbosity=2)