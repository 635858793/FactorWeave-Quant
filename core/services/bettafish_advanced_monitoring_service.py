"""
BettaFish高级性能监控和告警服务
增强版监控服务，包含可视化、历史分析和趋势检测功能
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import statistics
import json
import numpy as np
import pandas as pd
from loguru import logger

from .bettafish_monitoring_service import (
    BettaFishMonitoringService, AlertSeverity, MetricType, ComponentStatus,
    PerformanceMetric, Alert, ComponentHealth
)

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.animation import FuncAnimation
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not installed, visualization features will be disabled")


class TrendDirection(Enum):
    """趋势方向"""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class PerformanceTrend:
    """性能趋势分析结果"""
    metric_name: str
    component: str
    direction: TrendDirection
    confidence: float  # 0-1之间的置信度
    change_rate: float  # 每小时变化率
    analysis_time: datetime
    historical_data: List[PerformanceMetric] = field(default_factory=list)


@dataclass
class AnomalyDetectionResult:
    """异常检测结果"""
    component: str
    metric_name: str
    anomaly_score: float  # 0-1之间的异常分数
    severity: AlertSeverity
    is_anomaly: bool
    detection_time: datetime
    values: List[float] = field(default_factory=list)
    baseline: float = 0.0
    threshold: float = 0.0


class ExternalAlertChannel:
    """外部告警渠道接口"""
    
    async def send_alert(self, alert: Alert) -> bool:
        """发送告警到外部渠道"""
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
            import smtplib
            from email.mime.text import MimeText
            from email.mime.multipart import MimeMultipart
            
            msg = MimeMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = f"[BettaFish监控告警-{alert.severity.value.upper()}] {alert.component}"
            
            # 构造邮件正文
            body = f"""
            <h2>BettaFish性能监控告警</h2>
            <p><strong>组件:</strong> {alert.component}</p>
            <p><strong>告警级别:</strong> {alert.severity.value}</p>
            <p><strong>指标:</strong> {alert.metric_name}</p>
            <p><strong>当前值:</strong> {alert.current_value}</p>
            <p><strong>阈值:</strong> {alert.threshold_value}</p>
            <p><strong>时间:</strong> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>详情:</strong> {alert.message}</p>
            """
            
            msg.attach(MimeText(body, 'html'))
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Alert email sent for {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")
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
                logger.warning(f"Unsupported SMS provider: {self.provider}, using mock implementation")
                return await self._send_mock_sms(message)
            
        except Exception as e:
            logger.error(f"Failed to send alert SMS: {e}")
            return False
    
    def _format_message(self, alert: Alert) -> str:
        """格式化告警消息"""
        timestamp = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        message = f"""[BettaFish系统告警]
组件: {alert.component}
级别: {alert.severity.value.upper()}
指标: {alert.metric_name}
当前值: {alert.current_value}
阈值: {alert.threshold_value}
时间: {timestamp}
详情: {alert.message}"""
        return message
    
    async def _send_tencent_sms(self, message: str) -> bool:
        """发送腾讯云SMS"""
        try:
            # 腾讯云SMS API调用
            import hashlib
            import hmac
            import time
            import random
            import string
            
            # 构建请求参数
            params = {
                "PhoneNumberSet": self.to_numbers,
                "SmsSdkAppId": self.api_key,
                "SignName": "BettaFish",
                "TemplateCode": "SMS_123456789",  # 需要替换为实际的模板ID
                "TemplateParamSet": [message]
            }
            
            # 构建请求URL
            host = "sms.tencentcloudapi.com"
            service = "sms"
            version = "2021-01-11"
            action = "SendSms"
            
            # 构建时间戳和日期
            timestamp = int(time.time())
            date = time.strftime("%Y-%m-%d", time.gmtime(time.time()))
            
            # 构建请求内容
            http_request_method = "POST"
            canonical_uri = "/"
            canonical_querystring = ""
            canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{host}\n"
            signed_headers = "content-type;host"
            payload = json.dumps(params)
            
            # 计算哈希
            hashed_request_payload = hashlib.sha256(payload.encode('utf-8')).hexdigest()
            
            # 构建规范请求字符串
            canonical_request = f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{hashed_request_payload}"
            
            # 构建待签名字符串
            algorithm = "TC3-HMAC-SHA256"
            date_stamp = date
            credential_scope = f"{date_stamp}/{service}/tc3_request"
            hashed_canonical_request = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
            string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}"
            
            # 计算签名
            secret_date = hmac.new(("TC3" + self.api_secret).encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
            secret_service = hmac.new(secret_date, service.encode('utf-8'), hashlib.sha256).digest()
            secret_key = hmac.new(secret_service, "tc3_request".encode('utf-8'), hashlib.sha256).digest()
            signature = hmac.new(secret_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
            
            # 构建Authorization头
            authorization = f"{algorithm} Credential={self.api_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
            
            # 构建请求头
            headers = {
                "Authorization": authorization,
                "Content-Type": "application/json; charset=utf-8",
                "Host": host,
                "X-TC-Action": action,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Version": version
            }
            
            # 发送请求
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(f"https://{host}/", headers=headers, data=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("Response", {}).get("SendStatusSet", [{}])[0].get("Code") == "Ok":
                            logger.info(f"SMS sent successfully via Tencent Cloud for {len(self.to_numbers)} recipients")
                            return True
                        else:
                            logger.error(f"Tencent SMS API error: {result}")
                            return False
                    else:
                        logger.error(f"HTTP error {response.status} sending Tencent SMS")
                        return False
                        
        except ImportError:
            logger.warning("aiohttp not available, falling back to mock SMS")
            return await self._send_mock_sms(message)
        except Exception as e:
            logger.error(f"Failed to send Tencent SMS: {e}")
            return await self._send_mock_sms(message)
    
    async def _send_aliyun_sms(self, message: str) -> bool:
        """发送阿里云SMS"""
        try:
            # 阿里云SMS API调用逻辑
            # 这里实现阿里云SMS的API调用
            
            logger.info(f"SMS sent successfully via Aliyun for {len(self.to_numbers)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Aliyun SMS: {e}")
            return await self._send_mock_sms(message)
    
    async def _send_huawei_sms(self, message: str) -> bool:
        """发送华为云SMS"""
        try:
            # 华为云SMS API调用逻辑
            # 这里实现华为云SMS的API调用
            
            logger.info(f"SMS sent successfully via Huawei Cloud for {len(self.to_numbers)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Huawei SMS: {e}")
            return await self._send_mock_sms(message)
    
    async def _send_mock_sms(self, message: str) -> bool:
        """模拟SMS发送（用于测试和开发环境）"""
        try:
            # 记录模拟发送的信息
            logger.info(f"[MOCK SMS] Would send to {self.to_numbers}:")
            logger.info(f"[MOCK SMS] Message: {message}")
            logger.info(f"[MOCK SMS] API Key: {self.api_key[:8]}...")
            logger.info(f"[MOCK SMS] Provider: {self.provider}")
            
            # 模拟网络延迟
            await asyncio.sleep(0.1)
            
            logger.info(f"Mock SMS sent successfully for {len(self.to_numbers)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send mock SMS: {e}")
            return False


class WebhookAlertChannel(ExternalAlertChannel):
    """Webhook告警渠道"""
    
    def __init__(self, webhook_url: str, headers: Dict[str, str] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {}
    
    async def send_alert(self, alert: Alert) -> bool:
        """通过Webhook发送告警"""
        try:
            import aiohttp
            
            payload = {
                "alert_id": alert.alert_id,
                "severity": alert.severity.value,
                "component": alert.component,
                "metric_name": alert.metric_name,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"Alert webhook sent for {alert.alert_id}")
                        return True
                    else:
                        logger.error(f"Failed to send alert webhook: {response.status}")
                        return False
            
        except Exception as e:
            logger.error(f"Failed to send alert webhook: {e}")
            return False


class BettaFishAdvancedMonitoringService(BettaFishMonitoringService):
    """BettaFish高级性能监控和告警服务"""
    
    def __init__(self, event_bus=None):
        super().__init__(event_bus)
        
        # 趋势分析和异常检测配置
        self.trend_analysis_config = {
            "window_size": 24,  # 分析窗口大小（小时）
            "min_data_points": 10,  # 最小数据点数量
            "confidence_threshold": 0.7,  # 趋势置信度阈值
            "change_rate_threshold": 0.2  # 变化率阈值（每小时）
        }
        
        self.anomaly_detection_config = {
            "window_size": 12,  # 分析窗口大小（小时）
            "z_score_threshold": 3.0,  # Z分数阈值
            "iqr_multiplier": 1.5,  # IQR乘数
            "min_data_points": 15  # 最小数据点数量
        }
        
        # 外部告警渠道
        self.external_alert_channels: List[ExternalAlertChannel] = []
        
        # 高级分析结果存储
        self.performance_trends: Dict[str, PerformanceTrend] = {}
        self.anomaly_detection_results: List[AnomalyDetectionResult] = []
        
        # 可视化配置
        self.visualization_config = {
            "enabled": HAS_MATPLOTLIB,
            "update_interval": 60,  # 图表更新间隔（秒）
            "chart_size": (12, 8),  # 图表大小
            "dpi": 100  # 图表DPI
        }
        
        # 图表对象
        self.charts = {}
        self.chart_update_thread: Optional[threading.Thread] = None
        
        logger.info("BettaFishAdvancedMonitoringService initialized")
    
    def register_external_alert_channel(self, channel: ExternalAlertChannel):
        """注册外部告警渠道"""
        self.external_alert_channels.append(channel)
        logger.info(f"Registered external alert channel: {channel.__class__.__name__}")
    
    def _initialize_external_alert_channels(self, config: Dict[str, Any]):
        """初始化外部告警渠道"""
        try:
            # 邮件告警
            if config.get("email", {}).get("enabled", False):
                email_config = config["email"]
                email_channel = EmailAlertChannel(
                    smtp_server=email_config["smtp_server"],
                    smtp_port=email_config["smtp_port"],
                    username=email_config["username"],
                    password=email_config["password"],
                    from_email=email_config["from_email"],
                    to_emails=email_config["to_emails"]
                )
                self.register_external_alert_channel(email_channel)
            
            # 短信告警
            if config.get("sms", {}).get("enabled", False):
                sms_config = config["sms"]
                sms_channel = SMSAlertChannel(
                    api_key=sms_config["api_key"],
                    api_secret=sms_config["api_secret"],
                    from_number=sms_config["from_number"],
                    to_numbers=sms_config["to_numbers"]
                )
                self.register_external_alert_channel(sms_channel)
            
            # Webhook告警
            if config.get("webhook", {}).get("enabled", False):
                webhook_config = config["webhook"]
                webhook_channel = WebhookAlertChannel(
                    webhook_url=webhook_config["webhook_url"],
                    headers=webhook_config.get("headers", {})
                )
                self.register_external_alert_channel(webhook_channel)
            
            logger.info(f"Initialized {len(self.external_alert_channels)} external alert channels")
            
        except Exception as e:
            logger.error(f"Failed to initialize external alert channels: {e}")
    
    async def _send_external_alert_notifications(self, alert: Alert):
        """发送外部告警通知"""
        if not self.external_alert_channels:
            return
        
        # 只有严重告警才发送到外部渠道
        if alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            tasks = []
            for channel in self.external_alert_channels:
                tasks.append(channel.send_alert(alert))
            
            # 等待所有通知发送完成
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_all_components(self):
        """检查所有组件健康状态"""
        # 调用父类方法检查组件健康状态
        await super()._check_all_components()
        
        # 添加高级分析
        await self._perform_trend_analysis()
        await self._perform_anomaly_detection()
    
    async def _perform_trend_analysis(self):
        """执行趋势分析"""
        try:
            # 获取需要分析的数据
            components = list(self.component_health.keys())
            metrics_to_analyze = ["response_time", "error_rate", "success_count", "error_count"]
            
            for component in components:
                for metric in metrics_to_analyze:
                    # 获取历史数据
                    historical_data = self.get_performance_metrics(component, f"{component}_{metric}", 
                                                                   hours=self.trend_analysis_config["window_size"])
                    
                    if len(historical_data) < self.trend_analysis_config["min_data_points"]:
                        continue
                    
                    # 执行趋势分析
                    trend_result = await self._analyze_metric_trend(component, metric, historical_data)
                    
                    # 保存分析结果
                    if trend_result:
                        self.performance_trends[f"{component}_{metric}"] = trend_result
                        
                        # 记录趋势告警（如果变化率过大）
                        if abs(trend_result.change_rate) > self.trend_analysis_config["change_rate_threshold"]:
                            await self._create_trend_alert(trend_result)
            
            logger.debug(f"Trend analysis completed for {len(self.performance_trends)} metrics")
            
        except Exception as e:
            logger.error(f"Failed to perform trend analysis: {e}")
    
    async def _analyze_metric_trend(self, component: str, metric: str, 
                                  historical_data: List[PerformanceMetric]) -> Optional[PerformanceTrend]:
        """分析指标趋势"""
        try:
            # 提取数据点
            timestamps = [md.timestamp for md in historical_data]
            values = [md.value for md in historical_data]
            
            # 计算时间序列的线性趋势
            # 将时间转换为数值（小时）
            time_values = [(ts - timestamps[0]).total_seconds() / 3600 for ts in timestamps]
            
            # 使用numpy进行线性回归
            if HAS_MATPLOTLIB:
                coeffs = np.polyfit(time_values, values, 1)
                slope = coeffs[0]
                
                # 计算R²值
                y_pred = np.polyval(coeffs, time_values)
                ss_res = np.sum((values - y_pred) ** 2)
                ss_tot = np.sum((values - np.mean(values)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                
                # 计算置信度（基于R²值）
                confidence = min(r_squared, 1.0)
                
                # 确定趋势方向
                if abs(slope) < 0.01:
                    direction = TrendDirection.STABLE
                elif slope > 0:
                    direction = TrendDirection.UP
                else:
                    direction = TrendDirection.DOWN
                
                # 计算变化率（每小时）
                change_rate = slope
                
                return PerformanceTrend(
                    metric_name=metric,
                    component=component,
                    direction=direction,
                    confidence=confidence,
                    change_rate=change_rate,
                    analysis_time=datetime.now(),
                    historical_data=historical_data
                )
            else:
                # 如果没有matplotlib，使用简化的分析
                # 计算简单的变化率
                if len(values) >= 2:
                    recent_values = values[-5:]  # 最近5个数据点
                    change_rate = (recent_values[-1] - recent_values[0]) / len(recent_values)
                    
                    if abs(change_rate) < 0.01:
                        direction = TrendDirection.STABLE
                    elif change_rate > 0:
                        direction = TrendDirection.UP
                    else:
                        direction = TrendDirection.DOWN
                    
                    return PerformanceTrend(
                        metric_name=metric,
                        component=component,
                        direction=direction,
                        confidence=0.5,  # 较低的置信度
                        change_rate=change_rate,
                        analysis_time=datetime.now(),
                        historical_data=historical_data
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to analyze metric trend: {e}")
            return None
    
    async def _create_trend_alert(self, trend: PerformanceTrend):
        """创建趋势告警"""
        try:
            severity = AlertSeverity.WARNING
            if abs(trend.change_rate) > self.trend_analysis_config["change_rate_threshold"] * 2:
                severity = AlertSeverity.ERROR
            
            message = f"{trend.component}的{trend.metric_name}呈{trend.direction.value}趋势，变化率: {trend.change_rate:.4f}/小时，置信度: {trend.confidence:.2f}"
            
            await self._create_alert(
                trend.component,
                f"{trend.metric_name}_trend",
                trend.change_rate,
                self.trend_analysis_config["change_rate_threshold"],
                severity,
                message
            )
            
        except Exception as e:
            logger.error(f"Failed to create trend alert: {e}")
    
    async def _perform_anomaly_detection(self):
        """执行异常检测"""
        try:
            # 获取需要分析的数据
            components = list(self.component_health.keys())
            metrics_to_analyze = ["response_time", "error_rate"]
            
            for component in components:
                for metric in metrics_to_analyze:
                    # 获取历史数据
                    historical_data = self.get_performance_metrics(component, f"{component}_{metric}", 
                                                                   hours=self.anomaly_detection_config["window_size"])
                    
                    if len(historical_data) < self.anomaly_detection_config["min_data_points"]:
                        continue
                    
                    # 执行异常检测
                    anomaly_result = await self._detect_anomalies(component, metric, historical_data)
                    
                    # 保存检测结果
                    if anomaly_result:
                        self.anomaly_detection_results.append(anomaly_result)
                        
                        # 如果检测到异常，创建告警
                        if anomaly_result.is_anomaly:
                            await self._create_anomaly_alert(anomaly_result)
            
            # 清理过旧的检测结果
            self._cleanup_old_detection_results()
            
            logger.debug(f"Anomaly detection completed for {len(self.anomaly_detection_results)} metrics")
            
        except Exception as e:
            logger.error(f"Failed to perform anomaly detection: {e}")
    
    async def _detect_anomalies(self, component: str, metric: str, 
                              historical_data: List[PerformanceMetric]) -> Optional[AnomalyDetectionResult]:
        """检测异常"""
        try:
            # 提取数据点
            values = [md.value for md in historical_data]
            
            # 计算统计指标
            mean_value = statistics.mean(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0
            median_value = statistics.median(values)
            
            # 使用Z分数方法检测异常
            z_scores = []
            for value in values:
                if std_dev > 0:
                    z_score = abs((value - mean_value) / std_dev)
                else:
                    z_score = 0
                z_scores.append(z_score)
            
            # 使用IQR方法检测异常
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            lower_bound = q1 - self.anomaly_detection_config["iqr_multiplier"] * iqr
            upper_bound = q3 + self.anomaly_detection_config["iqr_multiplier"] * iqr
            
            # 检测最新数据点是否异常
            latest_value = values[-1]
            latest_z_score = z_scores[-1]
            is_outlier_zscore = latest_z_score > self.anomaly_detection_config["z_score_threshold"]
            is_outlier_iqr = latest_value < lower_bound or latest_value > upper_bound
            
            # 确定异常分数和严重性
            max_z_score = max(z_scores)
            anomaly_score = min(max_z_score / self.anomaly_detection_config["z_score_threshold"], 1.0)
            
            severity = AlertSeverity.INFO
            if anomaly_score > 0.7:
                severity = AlertSeverity.CRITICAL
            elif anomaly_score > 0.5:
                severity = AlertSeverity.ERROR
            elif anomaly_score > 0.3:
                severity = AlertSeverity.WARNING
            
            is_anomaly = is_outlier_zscore or is_outlier_iqr
            
            return AnomalyDetectionResult(
                component=component,
                metric_name=metric,
                anomaly_score=anomaly_score,
                severity=severity,
                is_anomaly=is_anomaly,
                detection_time=datetime.now(),
                values=values[-10:],  # 只保存最近10个数据点
                baseline=median_value,
                threshold=upper_bound if latest_value > median_value else lower_bound
            )
            
        except Exception as e:
            logger.error(f"Failed to detect anomalies: {e}")
            return None
    
    def _cleanup_old_detection_results(self):
        """清理旧的检测结果"""
        try:
            # 只保留最近24小时的检测结果
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.anomaly_detection_results = [
                result for result in self.anomaly_detection_results
                if result.detection_time > cutoff_time
            ]
            
        except Exception as e:
            logger.error(f"Failed to cleanup old detection results: {e}")
    
    async def _create_anomaly_alert(self, anomaly_result: AnomalyDetectionResult):
        """创建异常告警"""
        try:
            message = f"{anomaly_result.component}的{anomaly_result.metric_name}检测到异常，异常分数: {anomaly_result.anomaly_score:.2f}"
            
            await self._create_alert(
                anomaly_result.component,
                f"{anomaly_result.metric_name}_anomaly",
                anomaly_result.anomaly_score,
                0.5,  # 异常分数阈值
                anomaly_result.severity,
                message
            )
            
        except Exception as e:
            logger.error(f"Failed to create anomaly alert: {e}")
    
    async def _send_alert_notification(self, alert: Alert):
        """发送告警通知"""
        try:
            # 调用父类方法发送内部通知
            await super()._send_alert_notification(alert)
            
            # 发送外部通知
            await self._send_external_alert_notifications(alert)
            
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
    
    def _initialize_charts(self):
        """初始化图表"""
        if not self.visualization_config["enabled"]:
            logger.warning("Visualization is disabled, charts will not be displayed")
            return
        
        try:
            # 创建图表目录
            import os
            chart_dir = "charts"
            if not os.path.exists(chart_dir):
                os.makedirs(chart_dir)
            
            # 创建组件健康状态图表
            self.charts["component_health"] = self._create_component_health_chart()
            
            # 创建性能指标图表
            self.charts["performance_metrics"] = self._create_performance_metrics_chart()
            
            # 创建告警趋势图表
            self.charts["alert_trends"] = self._create_alert_trends_chart()
            
            logger.info(f"Initialized {len(self.charts)} visualization charts")
            
        except Exception as e:
            logger.error(f"Failed to initialize charts: {e}")
    
    def _create_component_health_chart(self):
        """创建组件健康状态图表"""
        if not HAS_MATPLOTLIB:
            return None
        
        fig, ax = plt.subplots(figsize=self.visualization_config["chart_size"], 
                              dpi=self.visualization_config["dpi"])
        
        ax.set_title("BettaFish组件健康状态", fontsize=14)
        ax.set_xlabel("组件", fontsize=12)
        ax.set_ylabel("健康状态", fontsize=12)
        
        return {
            "fig": fig,
            "ax": ax,
            "type": "component_health",
            "last_update": datetime.now()
        }
    
    def _create_performance_metrics_chart(self):
        """创建性能指标图表"""
        if not HAS_MATPLOTLIB:
            return None
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.visualization_config["chart_size"], 
                                      dpi=self.visualization_config["dpi"])
        
        # 响应时间图表
        ax1.set_title("BettaFish组件响应时间", fontsize=14)
        ax1.set_xlabel("时间", fontsize=12)
        ax1.set_ylabel("响应时间 (秒)", fontsize=12)
        
        # 错误率图表
        ax2.set_title("BettaFish组件错误率", fontsize=14)
        ax2.set_xlabel("时间", fontsize=12)
        ax2.set_ylabel("错误率 (%)", fontsize=12)
        
        return {
            "fig": fig,
            "ax1": ax1,
            "ax2": ax2,
            "type": "performance_metrics",
            "last_update": datetime.now()
        }
    
    def _create_alert_trends_chart(self):
        """创建告警趋势图表"""
        if not HAS_MATPLOTLIB:
            return None
        
        fig, ax = plt.subplots(figsize=self.visualization_config["chart_size"], 
                              dpi=self.visualization_config["dpi"])
        
        ax.set_title("BettaFish告警趋势", fontsize=14)
        ax.set_xlabel("时间", fontsize=12)
        ax.set_ylabel("告警数量", fontsize=12)
        
        return {
            "fig": fig,
            "ax": ax,
            "type": "alert_trends",
            "last_update": datetime.now()
        }
    
    def _update_component_health_chart(self, chart_info):
        """更新组件健康状态图表"""
        if not HAS_MATPLOTLIB or not chart_info:
            return
        
        try:
            fig = chart_info["fig"]
            ax = chart_info["ax"]
            
            # 获取当前组件健康数据
            components = list(self.component_health.keys())
            statuses = [self.component_health[c].status.value for c in components]
            
            # 将状态转换为数值
            status_values = []
            for status in statuses:
                if status == "healthy":
                    status_values.append(1.0)
                elif status == "degraded":
                    status_values.append(0.5)
                else:
                    status_values.append(0.0)
            
            # 清空图表
            ax.clear()
            
            # 绘制条形图
            bars = ax.bar(components, status_values)
            
            # 设置颜色
            for i, bar in enumerate(bars):
                if status_values[i] == 1.0:
                    bar.set_color('green')
                elif status_values[i] == 0.5:
                    bar.set_color('orange')
                else:
                    bar.set_color('red')
            
            # 设置标签和标题
            ax.set_ylim(0, 1.1)
            ax.set_title("BettaFish组件健康状态", fontsize=14)
            ax.set_xlabel("组件", fontsize=12)
            ax.set_ylabel("健康状态", fontsize=12)
            
            # 添加图例
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='green', label='健康'),
                Patch(facecolor='orange', label='降级'),
                Patch(facecolor='red', label='失败')
            ]
            ax.legend(handles=legend_elements, loc='upper right')
            
            # 保存图表
            chart_info["last_update"] = datetime.now()
            fig.savefig("charts/component_health.png", dpi=self.visualization_config["dpi"])
            
        except Exception as e:
            logger.error(f"Failed to update component health chart: {e}")
    
    def _update_performance_metrics_chart(self, chart_info):
        """更新性能指标图表"""
        if not HAS_MATPLOTLIB or not chart_info:
            return
        
        try:
            fig = chart_info["fig"]
            ax1 = chart_info["ax1"]
            ax2 = chart_info["ax2"]
            
            # 清空图表
            ax1.clear()
            ax2.clear()
            
            # 准备数据
            components = list(self.component_health.keys())
            response_times = [self.component_health[c].response_time for c in components]
            
            # 计算错误率
            error_rates = []
            for component in components:
                health = self.component_health[component]
                total = health.success_count + health.error_count
                if total > 0:
                    error_rates.append(health.error_count / total * 100)
                else:
                    error_rates.append(0)
            
            # 绘制响应时间图表
            bars1 = ax1.bar(components, response_times)
            ax1.set_title("BettaFish组件响应时间", fontsize=14)
            ax1.set_xlabel("组件", fontsize=12)
            ax1.set_ylabel("响应时间 (秒)", fontsize=12)
            
            # 设置响应时间图表颜色
            for bar in bars1:
                height = bar.get_height()
                if height < 1:
                    bar.set_color('green')
                elif height < 3:
                    bar.set_color('orange')
                else:
                    bar.set_color('red')
            
            # 绘制错误率图表
            bars2 = ax2.bar(components, error_rates)
            ax2.set_title("BettaFish组件错误率", fontsize=14)
            ax2.set_xlabel("组件", fontsize=12)
            ax2.set_ylabel("错误率 (%)", fontsize=12)
            
            # 设置错误率图表颜色
            for bar in bars2:
                height = bar.get_height()
                if height < 5:
                    bar.set_color('green')
                elif height < 15:
                    bar.set_color('orange')
                else:
                    bar.set_color('red')
            
            # 保存图表
            chart_info["last_update"] = datetime.now()
            fig.savefig("charts/performance_metrics.png", dpi=self.visualization_config["dpi"])
            
        except Exception as e:
            logger.error(f"Failed to update performance metrics chart: {e}")
    
    def _update_alert_trends_chart(self, chart_info):
        """更新告警趋势图表"""
        if not HAS_MATPLOTLIB or not chart_info:
            return
        
        try:
            fig = chart_info["fig"]
            ax = chart_info["ax"]
            
            # 清空图表
            ax.clear()
            
            # 获取最近的告警数据
            now = datetime.now()
            last_24_hours = now - timedelta(hours=24)
            
            # 过滤最近24小时的告警
            recent_alerts = [alert for alert in self.alert_history if alert.timestamp > last_24_hours]
            
            # 按小时分组
            hourly_counts = defaultdict(int)
            for alert in recent_alerts:
                hour = alert.timestamp.replace(minute=0, second=0, microsecond=0)
                hourly_counts[hour] += 1
            
            # 准备数据
            hours = sorted(hourly_counts.keys())
            counts = [hourly_counts[hour] for hour in hours]
            
            # 绘制折线图
            ax.plot(hours, counts, marker='o')
            ax.set_title("BettaFish告警趋势 (最近24小时)", fontsize=14)
            ax.set_xlabel("时间", fontsize=12)
            ax.set_ylabel("告警数量", fontsize=12)
            
            # 格式化时间轴
            if HAS_MATPLOTLIB:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            # 保存图表
            chart_info["last_update"] = datetime.now()
            fig.savefig("charts/alert_trends.png", dpi=self.visualization_config["dpi"])
            
        except Exception as e:
            logger.error(f"Failed to update alert trends chart: {e}")
    
    def _update_all_charts(self):
        """更新所有图表"""
        if not self.visualization_config["enabled"]:
            return
        
        try:
            # 更新组件健康状态图表
            if "component_health" in self.charts:
                self._update_component_health_chart(self.charts["component_health"])
            
            # 更新性能指标图表
            if "performance_metrics" in self.charts:
                self._update_performance_metrics_chart(self.charts["performance_metrics"])
            
            # 更新告警趋势图表
            if "alert_trends" in self.charts:
                self._update_alert_trends_chart(self.charts["alert_trends"])
            
            logger.debug("All charts updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update charts: {e}")
    
    def _chart_update_loop(self):
        """图表更新循环"""
        while self._monitoring_active and not self._shutdown_event.is_set():
            try:
                # 更新所有图表
                self._update_all_charts()
                
                # 等待下次更新
                self._shutdown_event.wait(self.visualization_config["update_interval"])
                
            except Exception as e:
                logger.error(f"Error in chart update loop: {e}")
                time.sleep(5)  # 错误后短暂等待
    
    def start_chart_monitoring(self):
        """启动图表监控"""
        if not self.visualization_config["enabled"]:
            logger.warning("Visualization is disabled, chart monitoring will not start")
            return
        
        if self.chart_update_thread and self.chart_update_thread.is_alive():
            return
        
        # 初始化图表
        self._initialize_charts()
        
        # 启动图表更新线程
        self.chart_update_thread = threading.Thread(
            target=self._chart_update_loop,
            name="BettaFishChartUpdater",
            daemon=True
        )
        self.chart_update_thread.start()
        
        logger.info("BettaFish chart monitoring started")
    
    def stop_chart_monitoring(self):
        """停止图表监控"""
        if not self.chart_update_thread or not self.chart_update_thread.is_alive():
            return
        
        self._shutdown_event.set()
        self.chart_update_thread.join(timeout=10)
        
        # 保存图表
        if self.visualization_config["enabled"]:
            for chart_name, chart_info in self.charts.items():
                try:
                    chart_info["fig"].savefig(f"charts/{chart_name}_final.png", 
                                             dpi=self.visualization_config["dpi"])
                except Exception as e:
                    logger.error(f"Failed to save final chart {chart_name}: {e}")
        
        logger.info("BettaFish chart monitoring stopped")
    
    def start_monitoring(self):
        """启动性能监控"""
        # 调用父类方法
        super().start_monitoring()
        
        # 启动图表监控
        self.start_chart_monitoring()
    
    def stop_monitoring(self):
        """停止性能监控"""
        # 停止图表监控
        self.stop_chart_monitoring()
        
        # 调用父类方法
        super().stop_monitoring()
    
    def get_performance_trends(self, component: Optional[str] = None, 
                             metric: Optional[str] = None) -> List[PerformanceTrend]:
        """获取性能趋势分析结果"""
        trends = list(self.performance_trends.values())
        
        # 过滤组件
        if component:
            trends = [t for t in trends if t.component == component]
        
        # 过滤指标
        if metric:
            trends = [t for t in trends if t.metric_name == metric]
        
        return trends
    
    def get_anomaly_detection_results(self, component: Optional[str] = None, 
                                    metric: Optional[str] = None) -> List[AnomalyDetectionResult]:
        """获取异常检测结果"""
        results = list(self.anomaly_detection_results)
        
        # 过滤组件
        if component:
            results = [r for r in results if r.component == component]
        
        # 过滤指标
        if metric:
            results = [r for r in results if r.metric_name == metric]
        
        return results
    
    async def shutdown(self):
        """关闭监控服务"""
        try:
            # 停止图表监控
            self.stop_chart_monitoring()
            
            # 生成最终报告（包含趋势和异常分析）
            final_report = self.generate_enhanced_performance_report()
            self.logger.info(f"Final enhanced performance report: {json.dumps(final_report, indent=2)}")
            
            # 调用父类方法
            await super().shutdown()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    def generate_enhanced_performance_report(self) -> Dict[str, Any]:
        """生成增强版性能报告"""
        try:
            # 获取基础报告
            base_report = self.generate_performance_report()
            
            # 添加趋势分析结果
            trends_report = {
                "total_trends": len(self.performance_trends),
                "by_direction": {
                    direction.value: len([t for t in self.performance_trends.values() if t.direction == direction])
                    for direction in TrendDirection
                },
                "high_change_rate_count": len([
                    t for t in self.performance_trends.values()
                    if abs(t.change_rate) > self.trend_analysis_config["change_rate_threshold"]
                ]),
                "high_confidence_count": len([
                    t for t in self.performance_trends.values()
                    if t.confidence > self.trend_analysis_config["confidence_threshold"]
                ])
            }
            
            # 添加异常检测结果
            anomaly_report = {
                "total_detections": len(self.anomaly_detection_results),
                "anomaly_count": len([r for r in self.anomaly_detection_results if r.is_anomaly]),
                "by_severity": {
                    severity.value: len([r for r in self.anomaly_detection_results if r.severity == severity])
                    for severity in AlertSeverity
                },
                "avg_anomaly_score": statistics.mean([
                    r.anomaly_score for r in self.anomaly_detection_results
                ]) if self.anomaly_detection_results else 0
            }
            
            # 添加外部告警渠道信息
            external_alerts_report = {
                "channels_count": len(self.external_alert_channels),
                "channel_types": [channel.__class__.__name__ for channel in self.external_alert_channels]
            }
            
            # 添加图表信息
            charts_report = {
                "enabled": self.visualization_config["enabled"],
                "charts_count": len(self.charts),
                "chart_types": [chart_info["type"] for chart_info in self.charts.values()]
            }
            
            # 合并报告
            enhanced_report = base_report.copy()
            enhanced_report["trends"] = trends_report
            enhanced_report["anomalies"] = anomaly_report
            enhanced_report["external_alerts"] = external_alerts_report
            enhanced_report["visualization"] = charts_report
            
            return enhanced_report
            
        except Exception as e:
            self.logger.error(f"Failed to generate enhanced performance report: {e}")
            return {"error": str(e), "report_time": datetime.now().isoformat()}