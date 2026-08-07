from loguru import logger
"""
告警事件处理器

监听系统告警事件，将其转换为告警历史记录
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List

from core.services.alert_deduplication_service import (
    get_alert_deduplication_service, AlertMessage, AlertLevel
)

from core.services.external_alert_channels_service import (
    get_alert_manager, AlertMessage as ExternalAlertMessage
)


class AlertEventHandler:
    """告警事件处理器"""

    def __init__(self):
        self.alert_service = get_alert_deduplication_service()
        self.alert_history_file = None
        self.external_alert_manager = get_alert_manager()
        self._init_history_file()

    def _init_history_file(self):
        """初始化告警历史文件"""
        try:
            config_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'config')
            os.makedirs(config_dir, exist_ok=True)
            self.alert_history_file = os.path.join(config_dir, 'alert_history.json')
        except Exception as e:
            logger.error(f"初始化告警历史文件失败: {e}")

    async def _send_external_alert(self, alert: AlertMessage):
        """
        发送外部告警

        Args:
            alert: 告警消息
        """
        try:
            # 指标字段统一存放于 metadata (R242-A-002): AlertMessage 本体无 metric_name 等字段
            meta = alert.metadata or {}
            external_alert = ExternalAlertMessage(
                alert_id=alert.id,
                component=alert.category,
                metric_name=meta.get('metric_name') or "unknown",
                current_value=meta.get('current_value') or 0.0,
                threshold_value=meta.get('threshold_value') or 0.0,
                severity=alert.level.value,
                message=alert.message,
                timestamp=alert.timestamp,
                metadata={
                    "recommendation": meta.get('recommendation', ''),
                    "category": alert.category
                }
            )

            # 发送到所有外部告警渠道
            results = await self.external_alert_manager.send_alert(external_alert)

            # 记录发送结果
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            logger.info(f"外部告警发送完成: {success_count}/{total_count} 渠道成功")

            return results

        except Exception as e:
            logger.error(f"发送外部告警失败: {e}")
            return {}

    def _coerce_timestamp(self, value: Any) -> datetime:
        """将时间戳 (float/str/datetime) 统一为 datetime"""
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)) and value:
            try:
                return datetime.fromtimestamp(value)
            except (ValueError, OSError):
                pass
        return datetime.now()

    def _send_external_alert_async(self, alert: AlertMessage) -> None:
        """异步发送外部告警 (R242-A-002 新增, 供新 handler 复用)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._send_external_alert(alert))
            else:
                loop.run_until_complete(self._send_external_alert(alert))
        except Exception as e:
            logger.warning(f"发送外部告警失败: {e}")

    def _dispatch_alert(self, level, category: str, message: str, source: str,
                        metadata: Dict[str, Any] = None) -> None:
        """统一告警分发: 去重 → 落历史文件 → 外部渠道 (R242-A-002 新增)

        process_alert 签名 (alert_deduplication_service.py:130) 接收分离参数,
        返回 AlertMessage 对象或 None (去重时返回 None)
        """
        try:
            alert = self.alert_service.process_alert(
                level=level, category=category, message=message,
                source=source, metadata=metadata or {})
            if alert is not None:
                self._save_alert_to_file(alert)
                logger.info(f"处理告警: {message}")
                self._send_external_alert_async(alert)
        except Exception as e:
            logger.error(f"分发告警失败: {e}")

    def _resource_type_metric_name(self, resource_type) -> str:
        """ResourceType 枚举 → 标准指标名 (对齐 _get_resource_recommendation key)"""
        mapping = {
            'CPU': 'cpu_usage',
            'MEMORY': 'memory_usage',
            'DISK': 'disk_usage',
            'NETWORK': 'network_usage',
        }
        name = getattr(resource_type, 'name', str(resource_type or 'unknown')).upper()
        return mapping.get(name, name.lower())

    def _map_alert_severity(self, severity) -> AlertLevel:
        """AlertSeverity (resource_monitor) → AlertLevel (去重服务) 映射"""
        if severity is None:
            return AlertLevel.WARNING
        mapping = {
            'INFO': AlertLevel.INFO,
            'WARNING': AlertLevel.WARNING,
            'ERROR': AlertLevel.ERROR,
            'CRITICAL': AlertLevel.CRITICAL,
        }
        name = getattr(severity, 'name', str(severity)).upper()
        return mapping.get(name, AlertLevel.WARNING)

    def handle_resource_threshold_exceeded(self, event_data) -> None:
        """处理资源阈值超标事件

        R242-A-002 补全孤儿事件订阅: core/metrics/aggregation_service.py:307 发布
        'ResourceThresholdExceeded' (CPU/内存/磁盘任一超限), 原无订阅者 (ORPHAN_PUB)
        """
        try:
            cpu = getattr(event_data, 'cpu_percent', None)
            memory = getattr(event_data, 'memory_percent', None)
            disk = getattr(event_data, 'disk_percent', None)
            timestamp = self._coerce_timestamp(getattr(event_data, 'timestamp', None))

            overruns = []
            if cpu is not None and float(cpu) > 80:
                overruns.append(("CPU使用率", float(cpu), 80.0))
            if memory is not None and float(memory) > 80:
                overruns.append(("内存使用率", float(memory), 80.0))
            if disk is not None and float(disk) > 90:
                overruns.append(("磁盘使用率", float(disk), 90.0))

            for name, value, threshold in overruns:
                alert_msg = f"{name} ({value:.1f}%) 超过阈值 ({threshold:.0f}%)"
                alert_info = self._parse_resource_alert(alert_msg)
                if alert_info:
                    self._dispatch_alert(
                        # R242-A-003: 资源超限即 WARNING, 原倍率重算 (ratio<1.2)
                        # 致百分比指标超限告警恒为 INFO
                        level=AlertLevel.WARNING,
                        category="系统资源",
                        message=alert_msg,
                        source="MetricsAggregationService",
                        metadata={
                            'metric_name': alert_info['metric_name'],
                            'current_value': alert_info['current_value'],
                            'threshold_value': alert_info['threshold_value'],
                            'recommendation': self._get_resource_recommendation(
                                alert_info['metric_name']),
                            'timestamp': timestamp.isoformat(),
                        }
                    )
        except Exception as e:
            logger.error(f"处理资源阈值告警事件失败: {e}")

    def handle_application_threshold_exceeded(self, event_data) -> None:
        """处理应用阈值超标事件

        R242-A-002 补全孤儿事件订阅: core/metrics/aggregation_service.py:339 发布
        'ApplicationThresholdExceeded' (操作耗时>5s 或执行失败), 原无订阅者 (ORPHAN_PUB)
        """
        try:
            operation_name = getattr(event_data, 'operation_name', 'unknown')
            duration = getattr(event_data, 'duration', None)
            was_successful = getattr(event_data, 'was_successful', True)
            timestamp = self._coerce_timestamp(getattr(event_data, 'timestamp', None))

            # 执行失败告警不依赖消息解析, 直接分发
            if not was_successful:
                self._dispatch_alert(
                    level=AlertLevel.ERROR,
                    category="应用性能",
                    message=f"操作 '{operation_name}' 执行失败",
                    source="MetricsAggregationService",
                    metadata={
                        'metric_name': operation_name,
                        'current_value': 0.0,
                        'threshold_value': 0.0,
                        'recommendation': self._get_application_recommendation(operation_name),
                        'timestamp': timestamp.isoformat(),
                    }
                )

            # 响应时间超标告警
            if duration is not None and float(duration) > 5.0:
                alert_msg = f"操作 '{operation_name}' 响应时间 ({float(duration):.2f}秒) 超过阈值 (5秒)"
                alert_info = self._parse_application_alert(alert_msg, operation_name)
                if alert_info:
                    self._dispatch_alert(
                        level=self._determine_alert_level(
                            alert_info['current_value'], alert_info['threshold_value']),
                        category="应用性能",
                        message=alert_msg,
                        source="MetricsAggregationService",
                        metadata={
                            'metric_name': alert_info['metric_name'],
                            'current_value': alert_info['current_value'],
                            'threshold_value': alert_info['threshold_value'],
                            'recommendation': self._get_application_recommendation(
                                alert_info['metric_name']),
                            'timestamp': timestamp.isoformat(),
                        }
                    )
        except Exception as e:
            logger.error(f"处理应用阈值告警事件失败: {e}")

    def handle_resource_alert_event(self, event_data) -> None:
        """处理 ResourceAlertEvent (core/performance/resource_monitor.py:448 发布)

        R242-A-002 修复命名错配: 发布端类名 'ResourceAlertEvent', 原订阅端 'ResourceAlert'
        → 告警链路断裂 (订阅方永远收不到)
        """
        try:
            alert = getattr(event_data, 'alert', None)
            if alert is None:
                logger.warning("ResourceAlertEvent 缺少 alert 字段, 跳过")
                return

            timestamp = self._coerce_timestamp(getattr(alert, 'timestamp', None))
            resource_type = getattr(alert, 'resource_type', None)
            metric_name = self._resource_type_metric_name(resource_type)
            current_value = getattr(alert, 'current_value', 0.0)
            threshold_value = getattr(alert, 'threshold_value', 0.0)
            message = getattr(alert, 'message', '资源告警')

            self._dispatch_alert(
                # R242-A-003: 采用 ResourceAlert 权威 severity 字段,
                # 不再按 _determine_alert_level 倍率重算 (百分比指标下会降级为 INFO)
                level=self._map_alert_severity(getattr(alert, 'severity', None)),
                category="系统资源",
                message=message,
                source="ResourceMonitor",
                metadata={
                    'metric_name': metric_name,
                    'current_value': float(current_value),
                    'threshold_value': float(threshold_value),
                    'recommendation': self._get_resource_recommendation(metric_name),
                    'alert_id': getattr(alert, 'alert_id', ''),
                    'timestamp': timestamp.isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"处理 ResourceAlertEvent 失败: {e}")

    def _parse_resource_alert(self, alert_msg: str) -> Dict[str, Any]:
        """解析资源告警消息"""
        try:
            # 解析格式如: "CPU使用率 (85.5%) 超过阈值 (80%)"
            if "CPU使用率" in alert_msg:
                metric_name = "cpu_usage"
            elif "内存使用率" in alert_msg:
                metric_name = "memory_usage"
            elif "磁盘使用率" in alert_msg:
                metric_name = "disk_usage"
            else:
                return None

            # 提取数值
            import re
            pattern = r'\((\d+\.?\d*)%?\)'
            matches = re.findall(pattern, alert_msg)

            if len(matches) >= 2:
                current_value = float(matches[0])
                threshold_value = float(matches[1])

                return {
                    'metric_name': metric_name,
                    'current_value': current_value,
                    'threshold_value': threshold_value
                }

        except Exception as e:
            logger.warning(f"解析资源告警消息失败: {e}")

        return None

    def _parse_application_alert(self, alert_msg: str, operation: str) -> Dict[str, Any]:
        """解析应用告警消息"""
        try:
            if "响应时间" in alert_msg:
                metric_name = "response_time"
                # 解析格式如: "操作 'query_data' 响应时间 (3.25秒) 超过阈值 (2秒)"
                import re
                pattern = r'\((\d+\.?\d*)秒?\)'
                matches = re.findall(pattern, alert_msg)

                if len(matches) >= 2:
                    current_value = float(matches[0])
                    threshold_value = float(matches[1])

                    return {
                        'metric_name': metric_name,
                        'current_value': current_value,
                        'threshold_value': threshold_value
                    }

            elif "错误率" in alert_msg:
                metric_name = "error_rate"
                # 解析格式如: "操作 'query_data' 错误率 (15%) 超过阈值 (10%)"
                import re
                pattern = r'\((\d+\.?\d*)%?\)'
                matches = re.findall(pattern, alert_msg)

                if len(matches) >= 2:
                    current_value = float(matches[0])
                    threshold_value = float(matches[1])

                    return {
                        'metric_name': metric_name,
                        'current_value': current_value,
                        'threshold_value': threshold_value
                    }

        except Exception as e:
            logger.warning(f"解析应用告警消息失败: {e}")

        return None

    def _determine_alert_level(self, current_value: float, threshold_value: float) -> AlertLevel:
        """确定告警级别"""
        ratio = current_value / threshold_value if threshold_value > 0 else 1

        if ratio >= 2.0:
            return AlertLevel.CRITICAL
        elif ratio >= 1.5:
            return AlertLevel.ERROR
        elif ratio >= 1.2:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO

    def _get_resource_recommendation(self, metric_name: str) -> str:
        """获取资源告警建议"""
        recommendations = {
            'cpu_usage': "检查CPU密集型进程，优化算法复杂度，考虑增加计算资源",
            'memory_usage': "检查内存泄漏，优化数据结构，清理不必要的缓存",
            'disk_usage': "清理临时文件，归档历史数据，扩展存储空间"
        }
        return recommendations.get(metric_name, "监控相关指标，分析具体原因")

    def _get_application_recommendation(self, metric_name: str) -> str:
        """获取应用告警建议"""
        recommendations = {
            'response_time': "优化数据库查询，减少网络延迟，使用缓存机制",
            'error_rate': "检查错误日志，增强错误处理，提高系统容错性"
        }
        return recommendations.get(metric_name, "分析应用日志，优化相关功能")

    def _save_alert_to_file(self, alert: AlertMessage):
        """保存告警到文件"""
        if not self.alert_history_file:
            return

        try:
            # 读取现有历史
            history_data = {'history': []}
            if os.path.exists(self.alert_history_file):
                with open(self.alert_history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)

            # 转换告警为字典格式
            alert_dict = {
                'timestamp': alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'level': self._convert_level_to_chinese(alert.level),
                'type': alert.category,
                'message': alert.message,
                'status': '已解决' if alert.is_resolved else '活跃'
            }

            # 添加新告警
            history_data['history'].append(alert_dict)

            # 保持最近1000条记录
            if len(history_data['history']) > 1000:
                history_data['history'] = history_data['history'][-1000:]

            # 保存到文件
            with open(self.alert_history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存告警到文件失败: {e}")

    def _convert_level_to_chinese(self, level: AlertLevel) -> str:
        """转换告警级别为中文"""
        level_mapping = {
            AlertLevel.INFO: '信息',
            AlertLevel.WARNING: '警告',
            AlertLevel.ERROR: '错误',
            AlertLevel.CRITICAL: '严重'
        }
        return level_mapping.get(level, '未知')


# 全局处理器实例
_alert_event_handler = None


def get_alert_event_handler() -> AlertEventHandler:
    """获取告警事件处理器实例"""
    global _alert_event_handler
    if _alert_event_handler is None:
        _alert_event_handler = AlertEventHandler()
    return _alert_event_handler


def register_alert_handlers(event_bus):
    """注册告警事件处理器到事件总线"""
    try:
        handler = get_alert_event_handler()

        # R242-B-002 修复 (2026-08-04): 移除死代码孤儿订阅 "ResourceAlert"/"ApplicationAlert"
        # Why: 全项目 0 发布方 (types.py 中同名类在 R243-C 已删除, 原资源监控发布的是
        #      ResourceAlertEvent 类名), 对应 handler 为死代码, 且旧 dict 分支
        #      process_alert(alert) 传对象必 TypeError。删除死订阅 + 死 handler (原 L79-223)。

        # R242-A-002 修复 (2026-08-04): 补全孤儿告警事件订阅, 闭合告警调用链
        # Why: aggregation_service 发布 ResourceThresholdExceeded/ApplicationThresholdExceeded
        #      (aggregation_service.py:313/345), resource_monitor 发布 ResourceAlertEvent
        #      (resource_monitor.py:453) — 均无订阅者 (ORPHAN_PUB), 告警链路断裂
        event_bus.subscribe(
            "ResourceThresholdExceeded", handler.handle_resource_threshold_exceeded)
        event_bus.subscribe(
            "ApplicationThresholdExceeded", handler.handle_application_threshold_exceeded)
        event_bus.subscribe("ResourceAlertEvent", handler.handle_resource_alert_event)

        logger.info("告警事件处理器已注册到事件总线")

    except Exception as e:
        logger.error(f"注册告警事件处理器失败: {e}")
