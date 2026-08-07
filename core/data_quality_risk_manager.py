"""
数据质量风险管理器

实现数据质量风险评估、监控和管理功能，为交易系统提供
数据质量保障和风险控制机制。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-17
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

from loguru import logger
from .risk.data_quality_monitor import DataQualityMonitor, QualityReport, QualityLevel, QualityIssue


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"           # 低风险
    MEDIUM = "medium"     # 中等风险
    HIGH = "high"         # 高风险
    CRITICAL = "critical"  # 严重风险


class RiskAction(Enum):
    """风险处理动作"""
    CONTINUE = "continue"         # 继续使用
    WARNING = "warning"           # 警告
    THROTTLE = "throttle"         # 限流
    FALLBACK = "fallback"         # 降级
    BLOCK = "block"               # 阻断


@dataclass
class RiskAssessment:
    """风险评估结果"""
    risk_level: RiskLevel
    risk_score: float
    recommended_action: RiskAction
    quality_report: QualityReport
    risk_factors: List[str]
    mitigation_strategies: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "recommended_action": self.recommended_action.value,
            "quality_report": self.quality_report.to_dict(),
            "risk_factors": self.risk_factors,
            "mitigation_strategies": self.mitigation_strategies,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class RiskThresholds:
    """风险阈值配置"""
    # 质量分数阈值
    quality_critical_threshold: float = 0.5
    quality_high_risk_threshold: float = 0.7
    quality_medium_risk_threshold: float = 0.85

    # 连续失败阈值
    consecutive_failures_critical: int = 5
    consecutive_failures_high: int = 3
    consecutive_failures_medium: int = 2

    # 时间窗口内失败率阈值
    failure_rate_window_minutes: int = 30
    failure_rate_critical: float = 0.8
    failure_rate_high: float = 0.6
    failure_rate_medium: float = 0.4

    # 数据延迟阈值（秒）
    data_delay_critical: int = 600   # 10分钟
    data_delay_high: int = 300       # 5分钟
    data_delay_medium: int = 120     # 2分钟


class DataQualityRiskManager:
    """
    数据质量风险管理器

    负责评估数据质量风险，制定风险控制策略，
    并提供实时的风险监控和预警功能。
    """

    def __init__(self, thresholds: RiskThresholds = None):
        """
        初始化数据质量风险管理器

        Args:
            thresholds: 风险阈值配置
        """
        self.thresholds = thresholds or RiskThresholds()
        self.quality_monitor = DataQualityMonitor()
        self.logger = logger.bind(module="DataQualityRiskManager")

        # 风险历史记录
        self.risk_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # 数据源状态跟踪
        self.source_status: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # 风险回调函数
        self.risk_callbacks: List[Callable[[RiskAssessment], None]] = []

        # 统计信息
        self.risk_stats = {
            "total_assessments": 0,
            "low_risk_count": 0,
            "medium_risk_count": 0,
            "high_risk_count": 0,
            "critical_risk_count": 0,
            "blocked_requests": 0,
            "fallback_activations": 0
        }

        self.logger.info("数据质量风险管理器初始化完成")

    def assess_risk(self, data: Any, data_source: str, data_type: str = "unknown",
                    context: Dict[str, Any] = None) -> RiskAssessment:
        """
        评估数据质量风险

        Args:
            data: 要评估的数据
            data_source: 数据源标识
            data_type: 数据类型
            context: 额外上下文信息

        Returns:
            RiskAssessment: 风险评估结果
        """
        try:
            context = context or {}

            # 1. 进行数据质量评估
            quality_report = self.quality_monitor.evaluate_data_quality(
                data, data_type, context
            )

            # 2. 获取数据源历史状态
            source_history = self._get_source_history(data_source)

            # 3. 计算风险分数
            risk_score = self._calculate_risk_score(quality_report, source_history, context)

            # 4. 确定风险等级
            risk_level = self._determine_risk_level(risk_score, quality_report)

            # 5. 推荐处理动作
            recommended_action = self._recommend_action(risk_level, quality_report, source_history)

            # 6. 识别风险因素
            risk_factors = self._identify_risk_factors(quality_report, source_history, context)

            # 7. 生成缓解策略
            mitigation_strategies = self._generate_mitigation_strategies(
                risk_level, risk_factors, quality_report
            )

            # 8. 创建风险评估结果
            assessment = RiskAssessment(
                risk_level=risk_level,
                risk_score=risk_score,
                recommended_action=recommended_action,
                quality_report=quality_report,
                risk_factors=risk_factors,
                mitigation_strategies=mitigation_strategies
            )

            # 9. 更新历史记录和统计
            self._update_risk_history(data_source, assessment)
            self._update_risk_stats(assessment)

            # 10. 触发风险回调
            self._trigger_risk_callbacks(assessment)

            self.logger.debug(f"数据源 {data_source} 风险评估完成: {risk_level.value}")

            return assessment

        except Exception as e:
            self.logger.error(f"风险评估失败: {e}")
            return self._create_error_assessment(str(e), data_source, data_type)

    def execute_with_monitoring(self, plugin_id: str, method: Callable, **kwargs) -> Tuple[Any, Any]:
        """
        执行插件方法并监控数据质量
        
        Args:
            plugin_id: 插件ID
            method: 要执行的方法
            **kwargs: 方法参数
            
        Returns:
            Tuple[Any, Any]: (执行结果, 验证结果)
        """
        import time
        from datetime import datetime
        
        try:
            # 记录开始时间
            start_time = time.time()
            
            # 执行方法
            result = method(**kwargs)
            
            # 计算执行时间
            execution_time = time.time() - start_time
            
            # 评估数据质量
            context = {
                'plugin_id': plugin_id,
                'execution_time': execution_time,
                'timestamp': datetime.now()
            }
            
            # 进行风险评估
            assessment = self.assess_risk(
                data=result,
                data_source=plugin_id,
                data_type=kwargs.get('data_type', 'unknown'),
                context=context
            )
            
            # 创建验证结果
            # R249 修复：打破"失败→历史累加→永久拒绝"恶性循环。
            # risk_score 包含历史连续失败累加（_calculate_risk_score 中
            # consecutive_failures*0.1 + 近期失败率*0.3），当数据源此前连续失败多次后,
            # 即使本次返回的数据质量优秀（quality_score>=0.9 且 EXCELLENT/GOOD 且无关键质量缺陷），
            # 也会因 risk_score 被抬高到 high/critical 而被误拒。此时应以数据质量为准放行。
            risk_level_value = assessment.risk_level.value
            quality_report = assessment.quality_report
            is_valid = risk_level_value not in ['critical', 'high']
            if not is_valid:
                quality_level_value = getattr(quality_report.quality_level, 'value', None)
                has_critical_issue = any(
                    getattr(issue, 'severity', '') in ('critical', 'high')
                    for issue in quality_report.issues
                )
                if (quality_report.overall_score >= 0.9
                        and quality_level_value in ('excellent', 'good')
                        and not has_critical_issue):
                    is_valid = True

            # R255 修复：匿名类补充 plugin_id 属性。
            # 此前结构无 plugin_id，导致下游 uni_plugin_data_manager 通过
            # getattr(validation_result, 'plugin_id', None) 溯源 data_source 恒为 None，
            # 落库列恒回退硬编码 'tet_plugin'，failover 后路由健康度也记错插件。
            validation_result = type('ValidationResult', (), {
                'is_valid': is_valid,
                'quality_score': quality_report.overall_score,
                'risk_level': risk_level_value,
                'assessment': assessment,
                'plugin_id': plugin_id
            })()
            
            return result, validation_result
            
        except Exception as e:
            self.logger.error(f"执行插件方法时出错 {plugin_id}: {e}")
            
            # 创建失败的验证结果
            # R255 修复：与成功分支一致补充 plugin_id 属性，保证数据源溯源链路完整
            validation_result = type('ValidationResult', (), {
                'is_valid': False,
                'quality_score': 0.0,
                'risk_level': 'critical',
                'error': str(e),
                'plugin_id': plugin_id
            })()
            
            return None, validation_result


    def _calculate_risk_score(self, quality_report: QualityReport,
                              source_history: List[Dict], context: Dict[str, Any]) -> float:
        """计算风险分数"""
        base_score = 1.0 - quality_report.overall_score  # 质量分数越低，风险越高

        # 历史失败率影响
        if source_history:
            recent_failures = sum(1 for record in source_history[-10:]
                                  if record.get("risk_level") in ["high", "critical"])
            failure_rate = recent_failures / min(len(source_history), 10)
            base_score += failure_rate * 0.3

        # 连续失败影响
        consecutive_failures = self._count_consecutive_failures(source_history)
        if consecutive_failures > 0:
            base_score += min(consecutive_failures * 0.1, 0.5)

        # 数据延迟影响
        data_delay = context.get("data_delay", 0)
        if data_delay > self.thresholds.data_delay_medium:
            delay_penalty = min(data_delay / self.thresholds.data_delay_critical, 1.0) * 0.2
            base_score += delay_penalty

        # 关键问题影响
        critical_issues = [issue for issue in quality_report.issues
                           if issue.severity == "critical"]
        base_score += len(critical_issues) * 0.15

        return min(base_score, 1.0)

    def _determine_risk_level(self, risk_score: float, quality_report: QualityReport) -> RiskLevel:
        """确定风险等级"""
        # 基于风险分数的基本判断
        if risk_score >= 0.8 or quality_report.quality_level == QualityLevel.CRITICAL:
            return RiskLevel.CRITICAL
        elif risk_score >= 0.6 or quality_report.quality_level == QualityLevel.POOR:
            return RiskLevel.HIGH
        elif risk_score >= 0.4 or quality_report.quality_level == QualityLevel.FAIR:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _recommend_action(self, risk_level: RiskLevel, quality_report: QualityReport,
                          source_history: List[Dict]) -> RiskAction:
        """推荐处理动作"""
        if risk_level == RiskLevel.CRITICAL:
            # 检查是否有可用的备用数据源
            if self._has_fallback_available():
                return RiskAction.FALLBACK
            else:
                return RiskAction.BLOCK

        elif risk_level == RiskLevel.HIGH:
            # 检查连续失败次数
            consecutive_failures = self._count_consecutive_failures(source_history)
            if consecutive_failures >= self.thresholds.consecutive_failures_high:
                return RiskAction.FALLBACK if self._has_fallback_available() else RiskAction.THROTTLE
            else:
                return RiskAction.WARNING

        elif risk_level == RiskLevel.MEDIUM:
            return RiskAction.WARNING

        else:
            return RiskAction.CONTINUE

    def _identify_risk_factors(self, quality_report: QualityReport,
                               source_history: List[Dict], context: Dict[str, Any]) -> List[str]:
        """识别风险因素"""
        risk_factors = []

        # 质量相关风险因素
        if quality_report.overall_score < self.thresholds.quality_critical_threshold:
            risk_factors.append("数据质量严重不足")

        for issue in quality_report.issues:
            if issue.severity in ["critical", "high"]:
                risk_factors.append(f"{issue.metric.value}问题: {issue.description}")

        # 历史相关风险因素
        if source_history:
            consecutive_failures = self._count_consecutive_failures(source_history)
            if consecutive_failures >= self.thresholds.consecutive_failures_medium:
                risk_factors.append(f"连续失败 {consecutive_failures} 次")

            # 计算时间窗口内的失败率
            failure_rate = self._calculate_recent_failure_rate(source_history)
            if failure_rate >= self.thresholds.failure_rate_medium:
                risk_factors.append(f"近期失败率过高: {failure_rate:.1%}")

        # 上下文相关风险因素
        data_delay = context.get("data_delay", 0)
        if data_delay > self.thresholds.data_delay_medium:
            risk_factors.append(f"数据延迟过高: {data_delay}秒")

        if context.get("network_issues"):
            risk_factors.append("网络连接不稳定")

        if context.get("high_load"):
            risk_factors.append("系统负载过高")

        return risk_factors

    def _generate_mitigation_strategies(self, risk_level: RiskLevel,
                                        risk_factors: List[str],
                                        quality_report: QualityReport) -> List[str]:
        """生成缓解策略"""
        strategies = []

        if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            strategies.append("启用备用数据源")
            strategies.append("增加数据验证检查")
            strategies.append("降低数据获取频率")

        if risk_level == RiskLevel.CRITICAL:
            strategies.append("暂停自动交易")
            strategies.append("人工干预确认")

        # 基于具体风险因素的策略
        for factor in risk_factors:
            if "连续失败" in factor:
                strategies.append("重置数据源连接")
            elif "延迟过高" in factor:
                strategies.append("优化网络配置")
            elif "完整性" in factor:
                strategies.append("增加数据补全机制")
            elif "准确性" in factor:
                strategies.append("加强数据校验")

        # 基于质量问题的策略
        for issue in quality_report.issues:
            if issue.recommendation not in strategies:
                strategies.append(issue.recommendation)

        return list(set(strategies))  # 去重

    def _get_source_history(self, data_source: str) -> List[Dict]:
        """获取数据源历史记录"""
        return list(self.risk_history.get(data_source, []))

    def _count_consecutive_failures(self, source_history: List[Dict]) -> int:
        """计算连续失败次数"""
        consecutive_count = 0

        for record in reversed(source_history):
            if record.get("risk_level") in ["high", "critical"]:
                consecutive_count += 1
            else:
                break

        return consecutive_count

    def _calculate_recent_failure_rate(self, source_history: List[Dict]) -> float:
        """计算近期失败率"""
        if not source_history:
            return 0.0

        cutoff_time = datetime.now() - timedelta(minutes=self.thresholds.failure_rate_window_minutes)

        recent_records = [
            record for record in source_history
            if record.get("timestamp", datetime.min) >= cutoff_time
        ]

        if not recent_records:
            return 0.0

        failure_count = sum(1 for record in recent_records
                            if record.get("risk_level") in ["high", "critical"])

        return failure_count / len(recent_records)

    def _has_fallback_available(self) -> bool:
        """检查是否有可用的备用数据源（真实探测，不再恒为 True）"""
        # 1. 优先检查自身是否持有可用的回退数据源引用
        for attr in ("data_source_fallback", "_data_source_fallback"):
            if getattr(self, attr, None) is not None:
                return True
        # 2. 检查 core.data_source_fallback.DATA_SOURCE_FALLBACK 链中是否存在非 mock_data 的真实回退源
        try:
            from core.data_source_fallback import DATA_SOURCE_FALLBACK
            for chain in DATA_SOURCE_FALLBACK.values():
                for source in chain:
                    if source and source != "mock_data":
                        return True
        except Exception as e:
            self.logger.debug(f"检查数据源回退配置失败: {e}")
        return False

    def _update_risk_history(self, data_source: str, assessment: RiskAssessment) -> None:
        """更新风险历史记录"""
        record = {
            "timestamp": assessment.timestamp,
            "risk_level": assessment.risk_level.value,
            "risk_score": assessment.risk_score,
            "quality_score": assessment.quality_report.overall_score,
            "recommended_action": assessment.recommended_action.value
        }

        self.risk_history[data_source].append(record)

    def _update_risk_stats(self, assessment: RiskAssessment) -> None:
        """更新风险统计"""
        self.risk_stats["total_assessments"] += 1

        level_key = f"{assessment.risk_level.value}_risk_count"
        if level_key in self.risk_stats:
            self.risk_stats[level_key] += 1

        if assessment.recommended_action == RiskAction.BLOCK:
            self.risk_stats["blocked_requests"] += 1
        elif assessment.recommended_action == RiskAction.FALLBACK:
            self.risk_stats["fallback_activations"] += 1

    def _trigger_risk_callbacks(self, assessment: RiskAssessment) -> None:
        """触发风险回调"""
        for callback in self.risk_callbacks:
            try:
                callback(assessment)
            except Exception as e:
                self.logger.error(f"风险回调执行失败: {e}")

    def _create_error_assessment(self, error_message: str, data_source: str,
                                 data_type: str) -> RiskAssessment:
        """创建错误评估结果"""
        from .risk.data_quality_monitor import QualityReport, QualityLevel, QualityIssue, QualityMetric

        error_report = QualityReport(
            overall_score=0.0,
            quality_level=QualityLevel.CRITICAL,
            metrics={},
            issues=[QualityIssue(
                QualityMetric.VALIDITY, "critical",
                f"风险评估错误: {error_message}",
                0.0, 1.0,
                "检查风险评估逻辑"
            )],
            recommendations=["修复风险评估错误"],
            data_info={"type": "error", "data_type": data_type}
        )

        return RiskAssessment(
            risk_level=RiskLevel.CRITICAL,
            risk_score=1.0,
            recommended_action=RiskAction.BLOCK,
            quality_report=error_report,
            risk_factors=[f"评估错误: {error_message}"],
            mitigation_strategies=["修复系统错误", "人工干预"]
        )

    def add_risk_callback(self, callback: Callable[[RiskAssessment], None]) -> None:
        """添加风险回调函数"""
        self.risk_callbacks.append(callback)

    def remove_risk_callback(self, callback: Callable[[RiskAssessment], None]) -> None:
        """移除风险回调函数"""
        if callback in self.risk_callbacks:
            self.risk_callbacks.remove(callback)

    def get_risk_statistics(self) -> Dict[str, Any]:
        """获取风险统计信息"""
        total = self.risk_stats["total_assessments"]

        if total == 0:
            return self.risk_stats

        stats = self.risk_stats.copy()
        stats.update({
            "low_risk_rate": stats["low_risk_count"] / total,
            "medium_risk_rate": stats["medium_risk_count"] / total,
            "high_risk_rate": stats["high_risk_count"] / total,
            "critical_risk_rate": stats["critical_risk_count"] / total,
            "block_rate": stats["blocked_requests"] / total,
            "fallback_rate": stats["fallback_activations"] / total
        })

        return stats

    def get_quality_statistics(self) -> Dict[str, Any]:
        """获取质量统计信息"""
        total = self.risk_stats["total_assessments"]

        if total == 0:
            return {
                "completeness": 0,
                "accuracy": 0,
                "timeliness": 0,
                "consistency": 0,
                "validity": 0,
                "uniqueness": 0
            }

        quality_metrics = {
            "completeness": 0,
            "accuracy": 0,
            "timeliness": 0,
            "consistency": 0,
            "validity": 0,
            "uniqueness": 0
        }

        all_quality_scores = []

        for source, history in self.risk_history.items():
            if history:
                recent_quality_scores = [record.get("quality_score", 0) for record in list(history)[-10:]]
                all_quality_scores.extend(recent_quality_scores)

        if all_quality_scores:
            avg_quality = np.mean(all_quality_scores)
            quality_metrics["completeness"] = avg_quality
            quality_metrics["accuracy"] = avg_quality * 0.98
            quality_metrics["timeliness"] = avg_quality * 0.95
            quality_metrics["consistency"] = avg_quality * 0.97
            quality_metrics["validity"] = avg_quality * 0.96
            quality_metrics["uniqueness"] = avg_quality * 0.99

        return quality_metrics

    def get_source_risk_profile(self, data_source: str, days: int = 7) -> Dict[str, Any]:
        """获取数据源风险画像"""
        history = self.risk_history.get(data_source, [])

        if not history:
            return {"message": "没有历史数据", "data_source": data_source}

        cutoff_time = datetime.now() - timedelta(days=days)
        recent_history = [
            record for record in history
            if record.get("timestamp", datetime.min) >= cutoff_time
        ]

        if not recent_history:
            return {"message": "没有近期数据", "data_source": data_source}

        # 计算各种统计指标
        risk_levels = [record["risk_level"] for record in recent_history]
        risk_scores = [record["risk_score"] for record in recent_history]
        quality_scores = [record["quality_score"] for record in recent_history]

        profile = {
            "data_source": data_source,
            "analysis_period_days": days,
            "total_assessments": len(recent_history),
            "risk_distribution": {
                "low": risk_levels.count("low"),
                "medium": risk_levels.count("medium"),
                "high": risk_levels.count("high"),
                "critical": risk_levels.count("critical")
            },
            "average_risk_score": np.mean(risk_scores),
            "average_quality_score": np.mean(quality_scores),
            "risk_trend": self._calculate_risk_trend(recent_history),
            "consecutive_failures": self._count_consecutive_failures(recent_history),
            "recent_failure_rate": self._calculate_recent_failure_rate(recent_history)
        }

        return profile

    def _calculate_risk_trend(self, history: List[Dict]) -> str:
        """计算风险趋势"""
        if len(history) < 2:
            return "insufficient_data"

        scores = [record["risk_score"] for record in history]

        # 比较前半段和后半段的平均分数
        mid_point = len(scores) // 2
        early_avg = np.mean(scores[:mid_point]) if mid_point > 0 else scores[0]
        recent_avg = np.mean(scores[mid_point:])

        if recent_avg > early_avg + 0.1:
            return "increasing"
        elif recent_avg < early_avg - 0.1:
            return "decreasing"
        else:
            return "stable"

    def reset_source_history(self, data_source: str) -> None:
        """重置数据源历史记录"""
        if data_source in self.risk_history:
            self.risk_history[data_source].clear()
            self.logger.info(f"已重置数据源 {data_source} 的历史记录")

    def set_risk_thresholds(self, thresholds: RiskThresholds) -> None:
        """设置风险阈值"""
        self.thresholds = thresholds
        self.logger.info("风险阈值已更新")

    def assess_quality(self, data: Any = None, data_type: str = "unknown",
                       context: Dict[str, Any] = None) -> Dict[str, Any]:
        """评估数据质量 (HVD-241-P0-A 补全)

        Why: gui/dialogs/data_management_dialog_unified.py:1424 调用 assess_quality(),
             但本类历史上只有 assess_risk() → GUI 数据质量检查必抛 AttributeError (R241-A 子智能体发现)
        Fix: 委托 self.quality_monitor (DataQualityMonitor) 评估, 返回平铺质量报告,
             兼容 dialog L1425-1438 的字段消费 (quality_score/completeness/accuracy 等)
        """
        try:
            report = self.quality_monitor.evaluate_data_quality(
                data, data_type, context or {}
            )
            metrics = report.metrics or {}
            return {
                "quality_score": int(round(report.overall_score * 100)),
                "quality_level": report.quality_level.value,
                "completeness": int(round(metrics.get("completeness", 0) * 100)),
                "accuracy": int(round(metrics.get("accuracy", 0) * 100)),
                "timeliness": int(round(metrics.get("timeliness", 0) * 100)),
                "consistency": int(round(metrics.get("consistency", 0) * 100)),
                "uniqueness": int(round(metrics.get("uniqueness", 0) * 100)),
                "issues": len(report.issues),
                "recommendations": report.recommendations,
            }
        except Exception as e:
            self.logger.error(f"数据质量评估失败: {e}")
            return {
                "quality_score": 0, "quality_level": "unknown",
                "completeness": 0, "accuracy": 0, "timeliness": 0,
                "consistency": 0, "uniqueness": 0, "issues": 0,
                "recommendations": [],
            }

    # HVD-241-P0-A: 空循环死代码方法 (业务代码零调用) 已删除
    # 删除依据: 641-657 循环体为空操作 (650-651 注释"暂时跳过"), 无退出条件,
    #           全项目 *.py 零调用 (R241-A 子智能体 + 主智能体双重验证)

