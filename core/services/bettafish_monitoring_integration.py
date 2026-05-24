"""
BettaFish监控服务集成
负责将BettaFish高级监控服务集成到现有系统中
"""

import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger

from .bettafish_monitoring_service import get_bettafish_monitoring_service, initialize_bettafish_monitoring_service
from .bettafish_advanced_monitoring_service import (
    BettaFishAdvancedMonitoringService, EmailAlertChannel, SMSAlertChannel, WebhookAlertChannel
)
from .service_bootstrap import ServiceBootstrap
from .event_bus import EventBus


class BettaFishMonitoringIntegration:
    """BettaFish监控服务集成"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or EventBus()
        self.advanced_monitoring_service: Optional[BettaFishAdvancedMonitoringService] = None
        self.is_initialized = False
        self.integration_config = {}
        
        logger.info("BettaFishMonitoringIntegration initialized")
    
    def configure(self, config: Dict[str, Any]):
        """配置监控服务"""
        self.integration_config = config
        
        logger.info("BettaFish monitoring integration configured")
    
    async def initialize(self):
        """初始化监控服务"""
        if self.is_initialized:
            logger.warning("BettaFish monitoring integration already initialized")
            return
        
        try:
            # 初始化高级监控服务
            self.advanced_monitoring_service = BettaFishAdvancedMonitoringService(self.event_bus)
            
            # 配置外部告警渠道
            await self._configure_external_alert_channels()
            
            # 配置监控阈值
            await self._configure_monitoring_thresholds()
            
            # 配置可视化选项
            await self._configure_visualization_options()
            
            # 注册事件监听器
            await self._register_event_listeners()
            
            # 启动监控服务
            self.advanced_monitoring_service.start_monitoring()
            
            self.is_initialized = True
            logger.info("BettaFish monitoring integration initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize BettaFish monitoring integration: {e}")
            raise
    
    async def _configure_external_alert_channels(self):
        """配置外部告警渠道"""
        try:
            alert_config = self.integration_config.get("external_alerts", {})
            
            # 邮件告警配置
            if alert_config.get("email", {}).get("enabled", False):
                email_config = alert_config["email"]
                email_channel = EmailAlertChannel(
                    smtp_server=email_config["smtp_server"],
                    smtp_port=email_config.get("smtp_port", 587),
                    username=email_config["username"],
                    password=email_config["password"],
                    from_email=email_config["from_email"],
                    to_emails=email_config["to_emails"]
                )
                self.advanced_monitoring_service.register_external_alert_channel(email_channel)
            
            # 短信告警配置
            if alert_config.get("sms", {}).get("enabled", False):
                sms_config = alert_config["sms"]
                sms_channel = SMSAlertChannel(
                    api_key=sms_config["api_key"],
                    api_secret=sms_config["api_secret"],
                    from_number=sms_config["from_number"],
                    to_numbers=sms_config["to_numbers"]
                )
                self.advanced_monitoring_service.register_external_alert_channel(sms_channel)
            
            # Webhook告警配置
            if alert_config.get("webhook", {}).get("enabled", False):
                webhook_config = alert_config["webhook"]
                webhook_channel = WebhookAlertChannel(
                    webhook_url=webhook_config["webhook_url"],
                    headers=webhook_config.get("headers", {})
                )
                self.advanced_monitoring_service.register_external_alert_channel(webhook_channel)
            
            logger.info("External alert channels configured")
            
        except Exception as e:
            logger.error(f"Failed to configure external alert channels: {e}")
    
    async def _configure_monitoring_thresholds(self):
        """配置监控阈值"""
        try:
            threshold_config = self.integration_config.get("thresholds", {})
            
            # 更新性能阈值配置
            if "performance" in threshold_config:
                self.advanced_monitoring_service.performance_thresholds.update(
                    threshold_config["performance"]
                )
            
            # 更新趋势分析配置
            if "trend_analysis" in threshold_config:
                trend_config = threshold_config["trend_analysis"]
                for key, value in trend_config.items():
                    if key in self.advanced_monitoring_service.trend_analysis_config:
                        self.advanced_monitoring_service.trend_analysis_config[key] = value
            
            # 更新异常检测配置
            if "anomaly_detection" in threshold_config:
                anomaly_config = threshold_config["anomaly_detection"]
                for key, value in anomaly_config.items():
                    if key in self.advanced_monitoring_service.anomaly_detection_config:
                        self.advanced_monitoring_service.anomaly_detection_config[key] = value
            
            logger.info("Monitoring thresholds configured")
            
        except Exception as e:
            logger.error(f"Failed to configure monitoring thresholds: {e}")
    
    async def _configure_visualization_options(self):
        """配置可视化选项"""
        try:
            viz_config = self.integration_config.get("visualization", {})
            
            # 更新可视化配置
            for key, value in viz_config.items():
                if key in self.advanced_monitoring_service.visualization_config:
                    self.advanced_monitoring_service.visualization_config[key] = value
            
            logger.info("Visualization options configured")
            
        except Exception as e:
            logger.error(f"Failed to configure visualization options: {e}")
    
    async def _register_event_listeners(self):
        """注册事件监听器"""
        try:
            # 监听服务启动事件
            self.event_bus.subscribe("service.started", self._on_service_started)
            
            # 监听服务停止事件
            self.event_bus.subscribe("service.stopped", self._on_service_stopped)
            
            # 监听错误事件
            self.event_bus.subscribe("service.error", self._on_service_error)
            
            # 监听BettaFish相关事件
            self.event_bus.subscribe("bettafish.agent.started", self._on_bettafish_agent_started)
            self.event_bus.subscribe("bettafish.agent.stopped", self._on_bettafish_agent_stopped)
            self.event_bus.subscribe("bettafish.analysis.completed", self._on_bettafish_analysis_completed)
            self.event_bus.subscribe("bettafish.analysis.failed", self._on_bettafish_analysis_failed)
            
            logger.info("Event listeners registered")
            
        except Exception as e:
            logger.error(f"Failed to register event listeners: {e}")
    
    async def _on_service_started(self, event_data):
        """处理服务启动事件"""
        try:
            service_name = event_data.get("service_name")
            if service_name:
                logger.info(f"Service started: {service_name}")
                
                # 记录服务启动事件到监控系统
                if self.advanced_monitoring_service:
                    # 可以在这里记录服务启动事件
                    pass
                
        except Exception as e:
            logger.error(f"Error handling service started event: {e}")
    
    async def _on_service_stopped(self, event_data):
        """处理服务停止事件"""
        try:
            service_name = event_data.get("service_name")
            if service_name:
                logger.info(f"Service stopped: {service_name}")
                
                # 记录服务停止事件到监控系统
                if self.advanced_monitoring_service:
                    # 可以在这里记录服务停止事件
                    pass
                
        except Exception as e:
            logger.error(f"Error handling service stopped event: {e}")
    
    async def _on_service_error(self, event_data):
        """处理服务错误事件"""
        try:
            service_name = event_data.get("service_name")
            error = event_data.get("error")
            
            if service_name and error:
                logger.error(f"Service error: {service_name} - {error}")
                
                # 将错误事件传递给监控服务
                if self.advanced_monitoring_service:
                    # 这里可以将错误信息传递给监控服务
                    # 例如创建错误指标
                    pass
                
        except Exception as e:
            logger.error(f"Error handling service error event: {e}")
    
    async def _on_bettafish_agent_started(self, event_data):
        """处理BettaFish Agent启动事件"""
        try:
            agent_name = event_data.get("agent_name")
            logger.info(f"BettaFish agent started: {agent_name}")
            
            # 可以在这里记录Agent启动事件
            # 例如更新组件健康状态
            pass
            
        except Exception as e:
            logger.error(f"Error handling BettaFish agent started event: {e}")
    
    async def _on_bettafish_agent_stopped(self, event_data):
        """处理BettaFish Agent停止事件"""
        try:
            agent_name = event_data.get("agent_name")
            logger.info(f"BettaFish agent stopped: {agent_name}")
            
            # 可以在这里记录Agent停止事件
            # 例如更新组件健康状态
            pass
            
        except Exception as e:
            logger.error(f"Error handling BettaFish agent stopped event: {e}")
    
    async def _on_bettafish_analysis_completed(self, event_data):
        """处理BettaFish分析完成事件"""
        try:
            analysis_id = event_data.get("analysis_id")
            duration = event_data.get("duration")
            stock_codes = event_data.get("stock_codes", [])
            
            logger.info(f"BettaFish analysis completed: {analysis_id}, duration: {duration:.2f}s, stocks: {stock_codes}")
            
            # 记录分析完成事件
            if self.advanced_monitoring_service:
                # 更新BettaFish Agent指标
                pass
            
        except Exception as e:
            logger.error(f"Error handling BettaFish analysis completed event: {e}")
    
    async def _on_bettafish_analysis_failed(self, event_data):
        """处理BettaFish分析失败事件"""
        try:
            analysis_id = event_data.get("analysis_id")
            error = event_data.get("error")
            
            logger.error(f"BettaFish analysis failed: {analysis_id} - {error}")
            
            # 记录分析失败事件
            if self.advanced_monitoring_service:
                # 更新BettaFish Agent指标
                pass
            
        except Exception as e:
            logger.error(f"Error handling BettaFish analysis failed event: {e}")
    
    def get_monitoring_service(self) -> Optional[BettaFishAdvancedMonitoringService]:
        """获取监控服务实例"""
        return self.advanced_monitoring_service
    
    async def shutdown(self):
        """关闭监控服务集成"""
        try:
            if not self.is_initialized:
                return

            try:
                self.event_bus.unsubscribe("service.started", self._on_service_started)
                self.event_bus.unsubscribe("service.stopped", self._on_service_stopped)
                self.event_bus.unsubscribe("service.error", self._on_service_error)
                self.event_bus.unsubscribe("bettafish.agent.started", self._on_bettafish_agent_started)
                self.event_bus.unsubscribe("bettafish.agent.stopped", self._on_bettafish_agent_stopped)
                self.event_bus.unsubscribe("bettafish.analysis.completed", self._on_bettafish_analysis_completed)
                self.event_bus.unsubscribe("bettafish.analysis.failed", self._on_bettafish_analysis_failed)
            except Exception as e:
                logger.error(f"Failed to unsubscribe event listeners: {e}")

            if self.advanced_monitoring_service:
                await self.advanced_monitoring_service.shutdown()

            self.is_initialized = False
            logger.info("BettaFish monitoring integration shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# 全局集成服务实例
_bettafish_monitoring_integration: Optional[BettaFishMonitoringIntegration] = None


def get_bettafish_monitoring_integration() -> Optional[BettaFishMonitoringIntegration]:
    """获取全局BettaFish监控集成服务"""
    return _bettafish_monitoring_integration


async def initialize_bettafish_monitoring_integration(
    event_bus: Optional[EventBus] = None,
    config: Dict[str, Any] = None
) -> BettaFishMonitoringIntegration:
    """初始化BettaFish监控集成服务"""
    global _bettafish_monitoring_integration
    _bettafish_monitoring_integration = BettaFishMonitoringIntegration(event_bus)
    
    # 应用配置
    if config:
        _bettafish_monitoring_integration.configure(config)
    
    # 初始化服务
    await _bettafish_monitoring_integration.initialize()
    
    return _bettafish_monitoring_integration


# 用于在服务引导程序中集成的函数
def register_bettafish_monitoring_service(bootstrap: ServiceBootstrap):
    """注册BettaFish监控服务到服务引导程序"""
    
    async def initialize_monitoring():
        # 从配置中获取监控配置
        config = bootstrap.config.get("bettafish_monitoring", {})
        
        # 初始化监控服务
        monitoring_integration = await initialize_bettafish_monitoring_integration(
            event_bus=bootstrap.event_bus,
            config=config
        )
        
        # 返回监控服务实例
        return monitoring_integration.get_monitoring_service()
    
    # 注册初始化函数
    bootstrap.register_initialization_function("bettafish_monitoring", initialize_monitoring)
    
    logger.info("BettaFish monitoring service registered with service bootstrap")


# 用于测试的简单函数
async def create_test_monitoring_integration() -> BettaFishMonitoringIntegration:
    """创建测试用的监控集成服务"""
    
    # 创建简单的测试配置
    test_config = {
        "external_alerts": {
            "email": {
                "enabled": False  # 测试时不启用邮件告警
            },
            "webhook": {
                "enabled": False  # 测试时不启用Webhook告警
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
                "window_size": 12,  # 缩短分析窗口以便测试
                "confidence_threshold": 0.5
            },
            "anomaly_detection": {
                "window_size": 6,  # 缩短分析窗口以便测试
                "z_score_threshold": 2.5
            }
        },
        "visualization": {
            "enabled": False,  # 测试时不启用可视化
            "update_interval": 30  # 缩短更新间隔以便测试
        }
    }
    
    # 创建事件总线
    event_bus = EventBus()
    
    # 初始化监控集成服务
    integration = await initialize_bettafish_monitoring_integration(
        event_bus=event_bus,
        config=test_config
    )
    
    return integration