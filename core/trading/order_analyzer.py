"""
订单分析器

负责订单数据分析
"""

from loguru import logger
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics

from core.trading.order_models import Order, OrderFill, OrderQuery, OrderType, OrderStatus
from core.trading.order_repository import OrderRepository
from core.containers import ServiceContainer
from core.events import EventBus
from core.plugin_types import AssetType
from collections import defaultdict
import json


class AnalysisPeriod(Enum):
    """分析周期"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    CUSTOM = "custom"


@dataclass
class OrderExecutionAnalysis:
    """订单执行分析"""
    period: str
    total_orders: int
    filled_orders: int
    cancelled_orders: int
    rejected_orders: int
    fill_rate: float
    avg_execution_time: float
    avg_fill_ratio: float
    total_value: float
    filled_value: float
    total_commission: float
    avg_order_value: float
    avg_fill_value: float

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'period': self.period,
            'total_orders': self.total_orders,
            'filled_orders': self.filled_orders,
            'cancelled_orders': self.cancelled_orders,
            'rejected_orders': self.rejected_orders,
            'fill_rate': self.fill_rate,
            'avg_execution_time': self.avg_execution_time,
            'avg_fill_ratio': self.avg_fill_ratio,
            'total_value': self.total_value,
            'filled_value': self.filled_value,
            'total_commission': self.total_commission,
            'avg_order_value': self.avg_order_value,
            'avg_fill_value': self.avg_fill_value
        }


@dataclass
class SlippageAnalysis:
    """滑点分析"""
    period: str
    avg_slippage: float
    max_slippage: float
    min_slippage: float
    slippage_std: float
    positive_slippage_count: int
    negative_slippage_count: int
    avg_positive_slippage: float
    avg_negative_slippage: float

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'period': self.period,
            'avg_slippage': self.avg_slippage,
            'max_slippage': self.max_slippage,
            'min_slippage': self.min_slippage,
            'slippage_std': self.slippage_std,
            'positive_slippage_count': self.positive_slippage_count,
            'negative_slippage_count': self.negative_slippage_count,
            'avg_positive_slippage': self.avg_positive_slippage,
            'avg_negative_slippage': self.avg_negative_slippage
        }


@dataclass
class VolumeAnalysis:
    """成交量分析"""
    period: str
    total_volume: int
    avg_volume_per_order: int
    max_volume: int
    min_volume: int
    volume_std: float
    buy_volume: int
    sell_volume: int
    buy_sell_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'period': self.period,
            'total_volume': self.total_volume,
            'avg_volume_per_order': self.avg_volume_per_order,
            'max_volume': self.max_volume,
            'min_volume': self.min_volume,
            'volume_std': self.volume_std,
            'buy_volume': self.buy_volume,
            'sell_volume': self.sell_volume,
            'buy_sell_ratio': self.buy_sell_ratio
        }


@dataclass
class OrderEfficiencyAnalysis:
    """订单效率分析"""
    period: str
    efficiency_score: float
    fill_efficiency: float
    cost_efficiency: float
    time_efficiency: float
    overall_rating: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'period': self.period,
            'efficiency_score': self.efficiency_score,
            'fill_efficiency': self.fill_efficiency,
            'cost_efficiency': self.cost_efficiency,
            'time_efficiency': self.time_efficiency,
            'overall_rating': self.overall_rating
        }


class OrderAnalyzer:
    """订单分析器"""

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        self.service_container = service_container
        self.event_bus = event_bus

        self.repository: OrderRepository = None

        self._initialize()

        logger.info("订单分析器初始化完成")

    def _initialize(self):
        """初始化"""
        self.repository = OrderRepository(self.service_container, self.event_bus)

    def analyze_order_execution(self, period: AnalysisPeriod = AnalysisPeriod.DAY,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None) -> OrderExecutionAnalysis:
        """分析订单执行"""
        try:
            if isinstance(period, str):
                period = AnalysisPeriod(period)
            logger.info(f"开始分析订单执行: {period.value}")

            # 1. 确定时间范围
            if start_time is None or end_time is None:
                start_time, end_time = self._get_period_range(period)

            # 2. 查询订单
            query = OrderQuery(limit=10000)
            orders = self.repository.query_orders(query)

            # 3. 过滤时间范围内的订单
            period_orders = [o for o in orders if start_time <= o.create_time <= end_time]

            if not period_orders:
                logger.warning("时间范围内没有订单")
                return self._empty_execution_analysis(period.value)

            # 4. 统计订单状态
            total_orders = len(period_orders)
            filled_orders = len([o for o in period_orders if o.order_status == OrderStatus.FILLED])
            cancelled_orders = len([o for o in period_orders if o.order_status == OrderStatus.CANCELLED])
            rejected_orders = len([o for o in period_orders if o.order_status == OrderStatus.REJECTED])

            # 5. 计算成交率
            fill_rate = filled_orders / total_orders if total_orders > 0 else 0

            # 6. 计算平均执行时间
            execution_times = [
                (order.execute_time - order.create_time).total_seconds()
                for order in period_orders
                if order.execute_time and order.create_time
            ]

            avg_execution_time = statistics.mean(execution_times) if execution_times else 0

            # 7. 计算平均成交比例
            fill_ratios = [o.fill_ratio for o in period_orders if o.filled_quantity > 0]
            avg_fill_ratio = statistics.mean(fill_ratios) if fill_ratios else 0

            # 8. 计算订单价值
            total_value = sum(o.total_value for o in period_orders)
            filled_value = sum(o.filled_value for o in period_orders)
            total_commission = sum(o.commission for o in period_orders)

            avg_order_value = total_value / total_orders if total_orders > 0 else 0
            avg_fill_value = filled_value / filled_orders if filled_orders > 0 else 0

            # 9. 生成分析结果
            analysis = OrderExecutionAnalysis(
                period=period.value,
                total_orders=total_orders,
                filled_orders=filled_orders,
                cancelled_orders=cancelled_orders,
                rejected_orders=rejected_orders,
                fill_rate=fill_rate,
                avg_execution_time=avg_execution_time,
                avg_fill_ratio=avg_fill_ratio,
                total_value=total_value,
                filled_value=filled_value,
                total_commission=total_commission,
                avg_order_value=avg_order_value,
                avg_fill_value=avg_fill_value
            )

            logger.info(f"订单执行分析完成: {analysis.to_dict()}")
            return analysis

        except Exception as e:
            logger.error(f"分析订单执行异常: {e}")
            return self._empty_execution_analysis(period.value)

    def analyze_slippage(self, period: AnalysisPeriod = AnalysisPeriod.DAY,
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> SlippageAnalysis:
        """分析滑点"""
        try:
            if isinstance(period, str):
                period = AnalysisPeriod(period)
            logger.info(f"开始分析滑点: {period.value}")

            # 1. 确定时间范围
            if start_time is None or end_time is None:
                start_time, end_time = self._get_period_range(period)

            # 2. 查询已成交订单
            query = OrderQuery(order_status=OrderStatus.FILLED, limit=10000)
            orders = self.repository.query_orders(query)

            # 3. 过滤时间范围内的订单
            period_orders = [o for o in orders if start_time <= o.create_time <= end_time]

            if not period_orders:
                logger.warning("时间范围内没有已成交订单")
                return self._empty_slippage_analysis(period.value)

            # 4. 计算滑点（假设滑点 = (成交价格 - 订单价格) / 订单价格）
            slippages = [
                (order.filled_price - order.order_price) / order.order_price
                for order in period_orders
                if order.order_price > 0 and order.filled_price > 0
            ]

            if not slippages:
                logger.warning("没有可计算的滑点数据")
                return self._empty_slippage_analysis(period.value)

            # 5. 计算滑点统计
            avg_slippage = statistics.mean(slippages)
            max_slippage = max(slippages)
            min_slippage = min(slippages)
            slippage_std = statistics.stdev(slippages) if len(slippages) > 1 else 0

            # 6. 分类滑点
            positive_slippages = [s for s in slippages if s > 0]
            negative_slippages = [s for s in slippages if s < 0]

            positive_slippage_count = len(positive_slippages)
            negative_slippage_count = len(negative_slippages)

            avg_positive_slippage = statistics.mean(positive_slippages) if positive_slippages else 0
            avg_negative_slippage = statistics.mean(negative_slippages) if negative_slippages else 0

            # 7. 生成分析结果
            analysis = SlippageAnalysis(
                period=period.value,
                avg_slippage=avg_slippage,
                max_slippage=max_slippage,
                min_slippage=min_slippage,
                slippage_std=slippage_std,
                positive_slippage_count=positive_slippage_count,
                negative_slippage_count=negative_slippage_count,
                avg_positive_slippage=avg_positive_slippage,
                avg_negative_slippage=avg_negative_slippage
            )

            logger.info(f"滑点分析完成: {analysis.to_dict()}")
            return analysis

        except Exception as e:
            logger.error(f"分析滑点异常: {e}")
            return self._empty_slippage_analysis(period.value)

    def analyze_volume(self, period: AnalysisPeriod = AnalysisPeriod.DAY,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None) -> VolumeAnalysis:
        """分析成交量"""
        try:
            if isinstance(period, str):
                period = AnalysisPeriod(period)
            logger.info(f"开始分析成交量: {period.value}")

            # 1. 确定时间范围
            if start_time is None or end_time is None:
                start_time, end_time = self._get_period_range(period)

            # 2. 查询订单
            query = OrderQuery(limit=10000)
            orders = self.repository.query_orders(query)

            # 3. 过滤时间范围内的订单
            period_orders = [o for o in orders if start_time <= o.create_time <= end_time]

            if not period_orders:
                logger.warning("时间范围内没有订单")
                return self._empty_volume_analysis(period.value)

            # 4. 统计成交量
            volumes = [o.order_quantity for o in period_orders]
            total_volume = sum(volumes)

            # 5. 计算成交量统计
            avg_volume = statistics.mean(volumes) if volumes else 0
            max_volume = max(volumes) if volumes else 0
            min_volume = min(volumes) if volumes else 0
            volume_std = statistics.stdev(volumes) if len(volumes) > 1 else 0

            # 6. 分类买卖成交量
            buy_orders = [o for o in period_orders if o.order_type == OrderType.BUY]
            sell_orders = [o for o in period_orders if o.order_type == OrderType.SELL]

            buy_volume = sum(o.order_quantity for o in buy_orders)
            sell_volume = sum(o.order_quantity for o in sell_orders)

            # 7. 计算买卖比例
            buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')

            # 8. 生成分析结果
            analysis = VolumeAnalysis(
                period=period.value,
                total_volume=total_volume,
                avg_volume_per_order=avg_volume,
                max_volume=max_volume,
                min_volume=min_volume,
                volume_std=volume_std,
                buy_volume=buy_volume,
                sell_volume=sell_volume,
                buy_sell_ratio=buy_sell_ratio
            )

            logger.info(f"成交量分析完成: {analysis.to_dict()}")
            return analysis

        except Exception as e:
            logger.error(f"分析成交量异常: {e}")
            return self._empty_volume_analysis(period.value)

    def analyze_order_efficiency(self, period: AnalysisPeriod = AnalysisPeriod.DAY,
                              start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None) -> OrderEfficiencyAnalysis:
        """分析订单效率"""
        try:
            if isinstance(period, str):
                period = AnalysisPeriod(period)
            logger.info(f"开始分析订单效率: {period.value}")

            # 1. 获取订单执行分析
            execution_analysis = self.analyze_order_execution(period, start_time, end_time)

            # 2. 获取滑点分析
            slippage_analysis = self.analyze_slippage(period, start_time, end_time)

            # 3. 计算成交效率（成交率）
            fill_efficiency = execution_analysis.fill_rate

            # 4. 计算成本效率（基于滑点）
            cost_efficiency = max(0, 1 - abs(slippage_analysis.avg_slippage) * 10)

            # 5. 计算时间效率（基于平均执行时间）
            time_efficiency = max(0, 1 - execution_analysis.avg_execution_time / 300)

            # 6. 计算综合效率分数
            efficiency_score = (fill_efficiency * 0.4 +
                             cost_efficiency * 0.3 +
                             time_efficiency * 0.3)

            # 7. 评定等级
            if efficiency_score >= 0.9:
                overall_rating = "优秀"
            elif efficiency_score >= 0.8:
                overall_rating = "良好"
            elif efficiency_score >= 0.7:
                overall_rating = "中等"
            elif efficiency_score >= 0.6:
                overall_rating = "较差"
            else:
                overall_rating = "差"

            # 8. 生成分析结果
            analysis = OrderEfficiencyAnalysis(
                period=period.value,
                efficiency_score=efficiency_score,
                fill_efficiency=fill_efficiency,
                cost_efficiency=cost_efficiency,
                time_efficiency=time_efficiency,
                overall_rating=overall_rating
            )

            logger.info(f"订单效率分析完成: {analysis.to_dict()}")
            return analysis

        except Exception as e:
            logger.error(f"分析订单效率异常: {e}")
            return self._empty_efficiency_analysis(period.value)

    def generate_comprehensive_report(self, period: AnalysisPeriod = AnalysisPeriod.DAY) -> Dict[str, Any]:
        """生成综合分析报告"""
        try:
            if isinstance(period, str):
                period = AnalysisPeriod(period)
            logger.info(f"开始生成综合分析报告: {period.value}")

            # 1. 执行各项分析
            execution_analysis = self.analyze_order_execution(period)
            slippage_analysis = self.analyze_slippage(period)
            volume_analysis = self.analyze_volume(period)
            efficiency_analysis = self.analyze_order_efficiency(period)

            # 2. 生成综合报告
            report = {
                'report_time': datetime.now().isoformat(),
                'period': period.value,
                'execution_analysis': execution_analysis.to_dict(),
                'slippage_analysis': slippage_analysis.to_dict(),
                'volume_analysis': volume_analysis.to_dict(),
                'efficiency_analysis': efficiency_analysis.to_dict(),
                'summary': {
                    'total_orders': execution_analysis.total_orders,
                    'fill_rate': execution_analysis.fill_rate,
                    'avg_slippage': slippage_analysis.avg_slippage,
                    'efficiency_score': efficiency_analysis.efficiency_score,
                    'overall_rating': efficiency_analysis.overall_rating
                },
                'recommendations': self._generate_recommendations(
                    execution_analysis,
                    slippage_analysis,
                    efficiency_analysis
                )
            }

            logger.info(f"综合分析报告生成完成")
            return report

        except Exception as e:
            logger.error(f"生成综合分析报告异常: {e}")
            return {}

    def _get_period_range(self, period: AnalysisPeriod) -> Tuple[datetime, datetime]:
        """获取时间范围"""
        end_time = datetime.now()

        if period == AnalysisPeriod.HOUR:
            start_time = end_time - timedelta(hours=1)
        elif period == AnalysisPeriod.DAY:
            start_time = end_time - timedelta(days=1)
        elif period == AnalysisPeriod.WEEK:
            start_time = end_time - timedelta(weeks=1)
        elif period == AnalysisPeriod.MONTH:
            start_time = end_time - timedelta(days=30)
        else:
            start_time = end_time - timedelta(days=1)

        return start_time, end_time

    def _empty_execution_analysis(self, period: str) -> OrderExecutionAnalysis:
        """空执行分析"""
        return OrderExecutionAnalysis(
            period=period,
            total_orders=0,
            filled_orders=0,
            cancelled_orders=0,
            rejected_orders=0,
            fill_rate=0,
            avg_execution_time=0,
            avg_fill_ratio=0,
            total_value=0,
            filled_value=0,
            total_commission=0,
            avg_order_value=0,
            avg_fill_value=0
        )

    def _empty_slippage_analysis(self, period: str) -> SlippageAnalysis:
        """空滑点分析"""
        return SlippageAnalysis(
            period=period,
            avg_slippage=0,
            max_slippage=0,
            min_slippage=0,
            slippage_std=0,
            positive_slippage_count=0,
            negative_slippage_count=0,
            avg_positive_slippage=0,
            avg_negative_slippage=0
        )

    def _empty_volume_analysis(self, period: str) -> VolumeAnalysis:
        """空成交量分析"""
        return VolumeAnalysis(
            period=period,
            total_volume=0,
            avg_volume_per_order=0,
            max_volume=0,
            min_volume=0,
            volume_std=0,
            buy_volume=0,
            sell_volume=0,
            buy_sell_ratio=0
        )

    def _empty_efficiency_analysis(self, period: str) -> OrderEfficiencyAnalysis:
        """空效率分析"""
        return OrderEfficiencyAnalysis(
            period=period,
            efficiency_score=0,
            fill_efficiency=0,
            cost_efficiency=0,
            time_efficiency=0,
            overall_rating="无数据"
        )

    def _generate_recommendations(self, execution_analysis: OrderExecutionAnalysis,
                               slippage_analysis: SlippageAnalysis,
                               efficiency_analysis: OrderEfficiencyAnalysis) -> List[str]:
        """生成建议"""
        recommendations = []

        # 基于成交率的建议
        if execution_analysis.fill_rate < 0.8:
            recommendations.append("成交率较低，建议检查订单价格设置和市场流动性")

        # 基于滑点的建议
        if abs(slippage_analysis.avg_slippage) > 0.001:
            recommendations.append("平均滑点较大，建议优化订单执行策略")

        # 基于效率的建议
        if efficiency_analysis.efficiency_score < 0.7:
            recommendations.append("订单效率较低，建议优化订单参数和执行时机")

        # 基于执行时间的建议
        if execution_analysis.avg_execution_time > 10:
            recommendations.append("平均执行时间较长，建议优化交易接口连接")

        if not recommendations:
            recommendations.append("订单执行情况良好，继续保持")

        return recommendations

    def analyze_by_asset_type(self, period: AnalysisPeriod = AnalysisPeriod.DAY,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None) -> Dict[str, OrderExecutionAnalysis]:
        """按资产类型分析订单执行"""
        try:
            if isinstance(period, str):
                period = AnalysisPeriod(period)
            logger.info(f"开始按资产类型分析订单执行: {period.value}")

            # 1. 确定时间范围
            if start_time is None or end_time is None:
                start_time, end_time = self._get_period_range(period)

            # 2. 查询订单
            query = OrderQuery(limit=10000)
            orders = self.repository.query_orders(query)

            # 3. 过滤时间范围内的订单
            period_orders = [o for o in orders if start_time <= o.create_time <= end_time]

            if not period_orders:
                logger.warning("时间范围内没有订单")
                return {}

            # 4. 按资产类型分组
            asset_orders = defaultdict(list)
            for order in period_orders:
                asset_orders[order.asset_type].append(order)

            # 5. 对每种资产类型进行分析
            analyses = {}
            for asset_type, orders_list in asset_orders.items():
                analysis = self._analyze_orders_for_asset(orders_list, period.value, asset_type.value)
                analyses[asset_type.value] = analysis

            logger.info(f"按资产类型分析完成: {len(analyses)} 种资产类型")
            return analyses

        except Exception as e:
            logger.error(f"按资产类型分析订单执行异常: {e}")
            return {}

    def _analyze_orders_for_asset(self, orders: List[Order], period: str, asset_type: str) -> OrderExecutionAnalysis:
        """分析特定资产类型的订单"""
        if not orders:
            return self._empty_execution_analysis(period)

        total_orders = len(orders)
        filled_orders = len([o for o in orders if o.order_status == OrderStatus.FILLED])
        cancelled_orders = len([o for o in orders if o.order_status == OrderStatus.CANCELLED])
        rejected_orders = len([o for o in orders if o.order_status == OrderStatus.REJECTED])

        fill_rate = filled_orders / total_orders if total_orders > 0 else 0

        execution_times = [
            (order.execute_time - order.create_time).total_seconds()
            for order in orders
            if order.execute_time and order.create_time
        ]

        avg_execution_time = statistics.mean(execution_times) if execution_times else 0

        fill_ratios = [o.fill_ratio for o in orders if o.filled_quantity > 0]
        avg_fill_ratio = statistics.mean(fill_ratios) if fill_ratios else 0

        total_value = sum(o.total_value for o in orders)
        filled_value = sum(o.filled_value for o in orders)
        total_commission = sum(o.commission for o in orders)

        avg_order_value = total_value / total_orders if total_orders > 0 else 0
        avg_fill_value = filled_value / filled_orders if filled_orders > 0 else 0

        return OrderExecutionAnalysis(
            period=period,
            total_orders=total_orders,
            filled_orders=filled_orders,
            cancelled_orders=cancelled_orders,
            rejected_orders=rejected_orders,
            fill_rate=fill_rate,
            avg_execution_time=avg_execution_time,
            avg_fill_ratio=avg_fill_ratio,
            total_value=total_value,
            filled_value=filled_value,
            total_commission=total_commission,
            avg_order_value=avg_order_value,
            avg_fill_value=avg_fill_value
        )

    def compare_asset_performance(self, period: AnalysisPeriod = AnalysisPeriod.DAY,
                                start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """对比不同资产类型的性能"""
        try:
            logger.info(f"开始对比资产类型性能: {period.value}")

            # 1. 获取按资产类型的分析
            asset_analyses = self.analyze_by_asset_type(period, start_time, end_time)

            if not asset_analyses:
                logger.warning("没有资产类型数据")
                return {}

            # 2. 提取关键指标
            comparison = {
                'period': period.value,
                'asset_types': list(asset_analyses.keys()),
                'metrics': {
                    'fill_rate': {asset: analysis.fill_rate for asset, analysis in asset_analyses.items()},
                    'avg_execution_time': {asset: analysis.avg_execution_time for asset, analysis in asset_analyses.items()},
                    'total_orders': {asset: analysis.total_orders for asset, analysis in asset_analyses.items()},
                    'total_value': {asset: analysis.total_value for asset, analysis in asset_analyses.items()},
                    'avg_fill_ratio': {asset: analysis.avg_fill_ratio for asset, analysis in asset_analyses.items()}
                },
                'rankings': self._calculate_rankings(asset_analyses)
            }

            logger.info(f"资产类型性能对比完成")
            return comparison

        except Exception as e:
            logger.error(f"对比资产类型性能异常: {e}")
            return {}

    def _calculate_rankings(self, asset_analyses: Dict[str, OrderExecutionAnalysis]) -> Dict[str, List[str]]:
        """计算资产类型排名"""
        rankings = {}

        # 按成交率排名
        fill_rate_ranking = sorted(
            asset_analyses.items(),
            key=lambda x: x[1].fill_rate,
            reverse=True
        )
        rankings['fill_rate'] = [asset for asset, _ in fill_rate_ranking]

        # 按执行时间排名（越短越好）
        execution_time_ranking = sorted(
            asset_analyses.items(),
            key=lambda x: x[1].avg_execution_time
        )
        rankings['execution_time'] = [asset for asset, _ in execution_time_ranking]

        # 按订单数量排名
        total_orders_ranking = sorted(
            asset_analyses.items(),
            key=lambda x: x[1].total_orders,
            reverse=True
        )
        rankings['total_orders'] = [asset for asset, _ in total_orders_ranking]

        return rankings

    def generate_multi_asset_report(self, period: AnalysisPeriod = AnalysisPeriod.DAY) -> Dict[str, Any]:
        """生成多资产综合分析报告"""
        try:
            logger.info(f"开始生成多资产综合分析报告: {period.value}")

            # 1. 执行各项分析
            execution_analysis = self.analyze_order_execution(period)
            slippage_analysis = self.analyze_slippage(period)
            volume_analysis = self.analyze_volume(period)
            efficiency_analysis = self.analyze_order_efficiency(period)

            # 2. 按资产类型分析
            asset_analyses = self.analyze_by_asset_type(period)

            # 3. 资产类型对比
            asset_comparison = self.compare_asset_performance(period)

            # 4. 生成综合报告
            report = {
                'report_time': datetime.now().isoformat(),
                'period': period.value,
                'overall_analysis': {
                    'execution_analysis': execution_analysis.to_dict(),
                    'slippage_analysis': slippage_analysis.to_dict(),
                    'volume_analysis': volume_analysis.to_dict(),
                    'efficiency_analysis': efficiency_analysis.to_dict()
                },
                'asset_type_analysis': {
                    asset_type: analysis.to_dict()
                    for asset_type, analysis in asset_analyses.items()
                },
                'asset_comparison': asset_comparison,
                'summary': {
                    'total_orders': execution_analysis.total_orders,
                    'asset_types_count': len(asset_analyses),
                    'fill_rate': execution_analysis.fill_rate,
                    'avg_slippage': slippage_analysis.avg_slippage,
                    'efficiency_score': efficiency_analysis.efficiency_score,
                    'overall_rating': efficiency_analysis.overall_rating,
                    'best_performing_asset': asset_comparison.get('rankings', {}).get('fill_rate', [''])[0] if asset_comparison.get('rankings') else '',
                    'most_active_asset': asset_comparison.get('rankings', {}).get('total_orders', [''])[0] if asset_comparison.get('rankings') else ''
                },
                'recommendations': self._generate_multi_asset_recommendations(
                    execution_analysis,
                    slippage_analysis,
                    efficiency_analysis,
                    asset_analyses
                )
            }

            logger.info(f"多资产综合分析报告生成完成")
            return report

        except Exception as e:
            logger.error(f"生成多资产综合分析报告异常: {e}")
            return {}

    def _generate_multi_asset_recommendations(self, execution_analysis: OrderExecutionAnalysis,
                                             slippage_analysis: SlippageAnalysis,
                                             efficiency_analysis: OrderEfficiencyAnalysis,
                                             asset_analyses: Dict[str, OrderExecutionAnalysis]) -> List[str]:
        """生成多资产建议"""
        recommendations = []

        # 基于整体成交率的建议
        if execution_analysis.fill_rate < 0.8:
            recommendations.append("整体成交率较低，建议检查订单价格设置和市场流动性")

        # 基于整体滑点的建议
        if abs(slippage_analysis.avg_slippage) > 0.001:
            recommendations.append("整体平均滑点较大，建议优化订单执行策略")

        # 基于整体效率的建议
        if efficiency_analysis.efficiency_score < 0.7:
            recommendations.append("整体订单效率较低，建议优化订单参数和执行时机")

        # 基于资产类型差异的建议
        if asset_analyses:
            fill_rates = [analysis.fill_rate for analysis in asset_analyses.values()]
            if max(fill_rates) - min(fill_rates) > 0.3:
                recommendations.append("不同资产类型的成交率差异较大，建议针对特定资产类型优化策略")

            execution_times = [analysis.avg_execution_time for analysis in asset_analyses.values()]
            if max(execution_times) - min(execution_times) > 5:
                recommendations.append("不同资产类型的执行时间差异较大，建议检查特定资产类型的交易接口性能")

        # 基于执行时间的建议
        if execution_analysis.avg_execution_time > 10:
            recommendations.append("平均执行时间较长，建议优化交易接口连接")

        if not recommendations:
            recommendations.append("订单执行情况良好，继续保持")

        return recommendations

    def export_report_to_json(self, report: Dict[str, Any], file_path: str) -> bool:
        """导出报告到JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"报告已导出到: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出报告失败: {e}")
            return False

    def generate_execution_chart(self, report: Dict[str, Any], chart_type: str = 'bar') -> Optional[str]:
        """生成订单执行图表"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import os

            logger.info("开始生成订单执行图表")

            execution_analysis = report.get('execution_analysis', {})
            if not execution_analysis:
                logger.warning("没有订单执行分析数据")
                return None

            fig, ax = plt.subplots(figsize=(12, 6))

            categories = ['Total Orders', 'Filled', 'Cancelled', 'Rejected']
            values = [
                execution_analysis.get('total_orders', 0),
                execution_analysis.get('filled_orders', 0),
                execution_analysis.get('cancelled_orders', 0),
                execution_analysis.get('rejected_orders', 0)
            ]

            colors = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12']

            if chart_type == 'bar':
                bars = ax.bar(categories, values, color=colors)
                ax.set_title('Order Execution Status', fontsize=14, fontweight='bold')
                ax.set_ylabel('Number of Orders', fontsize=12)

                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2., height,
                           f'{int(height)}',
                           ha='center', va='bottom', fontsize=10)

            elif chart_type == 'pie':
                ax.pie(values, labels=categories, autopct='%1.1f%%', colors=colors)
                ax.set_title('Order Execution Ratio', fontsize=14, fontweight='bold')

            plt.tight_layout()

            charts_dir = 'charts'
            if not os.path.exists(charts_dir):
                os.makedirs(charts_dir)

            file_path = os.path.join(charts_dir, f"order_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"订单执行图表生成成功: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"生成订单执行图表失败: {e}")
            return None

    def generate_slippage_chart(self, report: Dict[str, Any], chart_type: str = 'line') -> Optional[str]:
        """生成滑点分析图表"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import os

            logger.info("开始生成滑点分析图表")

            slippage_analysis = report.get('slippage_analysis', {})
            if not slippage_analysis:
                logger.warning("没有滑点分析数据")
                return None

            fig, ax = plt.subplots(figsize=(12, 6))

            categories = ['Avg Slippage', 'Max Slippage', 'Min Slippage']
            values = [
                slippage_analysis.get('avg_slippage', 0) * 100,
                slippage_analysis.get('max_slippage', 0) * 100,
                slippage_analysis.get('min_slippage', 0) * 100
            ]

            if chart_type == 'line':
                ax.plot(categories, values, marker='o', linewidth=2, markersize=10, color='#3498db')
                ax.fill_between(categories, values, alpha=0.3, color='#3498db')
                ax.set_title('Slippage Analysis', fontsize=14, fontweight='bold')
                ax.set_ylabel('Slippage (%)', fontsize=12)
                ax.grid(True, alpha=0.3)

                for i, (cat, val) in enumerate(zip(categories, values)):
                    ax.text(i, val, f'{val:.4f}%', ha='center', va='bottom', fontsize=10)

            elif chart_type == 'bar':
                colors = ['#e74c3c' if val > 0 else '#2ecc71' for val in values]
                bars = ax.bar(categories, values, color=colors)
                ax.set_title('Slippage Analysis', fontsize=14, fontweight='bold')
                ax.set_ylabel('Slippage (%)', fontsize=12)
                ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2., height,
                           f'{height:.4f}%',
                           ha='center', va='bottom' if height > 0 else 'top', fontsize=10)

            plt.tight_layout()

            charts_dir = 'charts'
            if not os.path.exists(charts_dir):
                os.makedirs(charts_dir)

            file_path = os.path.join(charts_dir, f"slippage_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"滑点分析图表生成成功: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"生成滑点分析图表失败: {e}")
            return None

    def generate_volume_chart(self, report: Dict[str, Any], chart_type: str = 'bar') -> Optional[str]:
        """生成成交量分析图表"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import os

            logger.info("开始生成成交量分析图表")

            volume_analysis = report.get('volume_analysis', {})
            if not volume_analysis:
                logger.warning("没有成交量分析数据")
                return None

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

            categories = ['Total Volume', 'Avg Volume', 'Max Volume', 'Min Volume']
            values = [
                volume_analysis.get('total_volume', 0),
                volume_analysis.get('avg_volume_per_order', 0),
                volume_analysis.get('max_volume', 0),
                volume_analysis.get('min_volume', 0)
            ]

            colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']

            bars = ax1.bar(categories, values, color=colors)
            ax1.set_title('Volume Statistics', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Volume', fontsize=12)
            ax1.tick_params(axis='x', rotation=45)

            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width() / 2., height,
                        f'{int(height)}',
                        ha='center', va='bottom', fontsize=10)

            buy_volume = volume_analysis.get('buy_volume', 0)
            sell_volume = volume_analysis.get('sell_volume', 0)

            ax2.pie([buy_volume, sell_volume], labels=['Buy Volume', 'Sell Volume'],
                   autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'])
            ax2.set_title('Buy/Sell Volume Ratio', fontsize=14, fontweight='bold')

            plt.tight_layout()

            charts_dir = 'charts'
            if not os.path.exists(charts_dir):
                os.makedirs(charts_dir)

            file_path = os.path.join(charts_dir, f"volume_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"成交量分析图表生成成功: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"生成成交量分析图表失败: {e}")
            return None

    def generate_efficiency_chart(self, report: Dict[str, Any], chart_type: str = 'radar') -> Optional[str]:
        """生成订单效率图表"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import numpy as np
            import os

            logger.info("开始生成订单效率图表")

            efficiency_analysis = report.get('efficiency_analysis', {})
            if not efficiency_analysis:
                logger.warning("没有订单效率分析数据")
                return None

            fig, ax = plt.subplots(figsize=(10, 8))

            categories = ['Fill Efficiency', 'Cost Efficiency', 'Time Efficiency']
            values = [
                efficiency_analysis.get('fill_efficiency', 0) * 100,
                efficiency_analysis.get('cost_efficiency', 0) * 100,
                efficiency_analysis.get('time_efficiency', 0) * 100
            ]

            if chart_type == 'radar':
                N = len(categories)
                angles = [n / float(N) * 2 * np.pi for n in range(N)]
                values += values[:1]
                angles += angles[:1]

                ax = plt.subplot(111, polar=True)
                ax.plot(angles, values, 'o-', linewidth=2, color='#3498db')
                ax.fill(angles, values, alpha=0.25, color='#3498db')
                ax.set_xticks(angles[:-1])
                ax.set_xticklabels(categories, fontsize=12)
                ax.set_ylim(0, 100)
                ax.set_title('Order Efficiency Analysis', fontsize=14, fontweight='bold', pad=20)

                for angle, value in zip(angles[:-1], values[:-1]):
                    ax.text(angle, value + 5, f'{value:.1f}%', ha='center', va='center', fontsize=10)

            elif chart_type == 'bar':
                colors = ['#2ecc71', '#3498db', '#f39c12']
                bars = ax.bar(categories, values, color=colors)
                ax.set_title('Order Efficiency Analysis', fontsize=14, fontweight='bold')
                ax.set_ylabel('Efficiency (%)', fontsize=12)
                ax.set_ylim(0, 100)

                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2., height,
                           f'{height:.1f}%',
                           ha='center', va='bottom', fontsize=10)

                efficiency_score = efficiency_analysis.get('efficiency_score', 0) * 100
                overall_rating = efficiency_analysis.get('overall_rating', 'No Data')
                ax.text(0.5, 0.95, f'Overall Efficiency: {efficiency_score:.1f}% ({overall_rating})',
                       transform=ax.transAxes, ha='center', va='top', fontsize=12,
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()

            charts_dir = 'charts'
            if not os.path.exists(charts_dir):
                os.makedirs(charts_dir)

            file_path = os.path.join(charts_dir, f"efficiency_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"订单效率图表生成成功: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"生成订单效率图表失败: {e}")
            return None

    def export_report_with_charts(self, report: Dict[str, Any], file_path: str, format: str = 'pdf') -> bool:
        """导出带图表的报告"""
        try:
            import os
            from PIL import Image

            logger.info(f"开始导出带图表的报告: {file_path}")

            execution_chart = self.generate_execution_chart(report)
            slippage_chart = self.generate_slippage_chart(report)
            volume_chart = self.generate_volume_chart(report)
            efficiency_chart = self.generate_efficiency_chart(report)

            if format == 'pdf':
                try:
                    from reportlab.lib.pagesizes import letter, A4
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.units import inch
                    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
                    from reportlab.lib import colors

                    doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
                    story = []
                    styles = getSampleStyleSheet()

                    title_style = ParagraphStyle(
                        'CustomTitle',
                        parent=styles['Heading1'],
                        fontSize=24,
                        textColor=colors.HexColor('#2c3e50'),
                        spaceAfter=30
                    )

                    heading_style = ParagraphStyle(
                        'CustomHeading',
                        parent=styles['Heading2'],
                        fontSize=16,
                        textColor=colors.HexColor('#34495e'),
                        spaceAfter=12
                    )

                    story.append(Paragraph("Order Analysis Report", title_style))
                    story.append(Spacer(1, 12))

                    report_time = report.get('report_time', 'Unknown')
                    period = report.get('period', 'Unknown')
                    story.append(Paragraph(f"Report Time: {report_time}", styles['Normal']))
                    story.append(Paragraph(f"Analysis Period: {period}", styles['Normal']))
                    story.append(Spacer(1, 24))

                    summary = report.get('summary', {})
                    story.append(Paragraph("Executive Summary", heading_style))

                    summary_data = [
                        ['Metric', 'Value'],
                        ['Total Orders', str(summary.get('total_orders', 0))],
                        ['Fill Rate', f"{summary.get('fill_rate', 0):.2%}"],
                        ['Avg Slippage', f"{summary.get('avg_slippage', 0):.4%}"],
                        ['Efficiency Score', f"{summary.get('efficiency_score', 0):.2%}"],
                        ['Overall Rating', summary.get('overall_rating', 'No Data')]
                    ]

                    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
                    summary_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))

                    story.append(summary_table)
                    story.append(Spacer(1, 24))

                    story.append(Paragraph("Chart Analysis", heading_style))

                    if execution_chart and os.path.exists(execution_chart):
                        img = Image(execution_chart, width=6*inch, height=3*inch)
                        story.append(img)
                        story.append(Spacer(1, 12))

                    if slippage_chart and os.path.exists(slippage_chart):
                        img = Image(slippage_chart, width=6*inch, height=3*inch)
                        story.append(img)
                        story.append(Spacer(1, 12))

                    if volume_chart and os.path.exists(volume_chart):
                        img = Image(volume_chart, width=6*inch, height=3*inch)
                        story.append(img)
                        story.append(Spacer(1, 12))

                    if efficiency_chart and os.path.exists(efficiency_chart):
                        img = Image(efficiency_chart, width=6*inch, height=4*inch)
                        story.append(img)
                        story.append(Spacer(1, 12))

                    recommendations = report.get('recommendations', [])
                    if recommendations:
                        story.append(Paragraph("Recommendations", heading_style))
                        for i, rec in enumerate(recommendations, 1):
                            story.append(Paragraph(f"{i}. {rec}", styles['Normal']))
                            story.append(Spacer(1, 6))

                    doc.build(story)

                    logger.info(f"带图表的PDF报告导出成功: {file_path}")
                    return True

                except ImportError:
                    logger.warning("reportlab未安装，尝试使用其他方式导出")

            if format == 'html':
                summary = report.get('summary', {})
                recommendations = report.get('recommendations', [])

                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Order Analysis Report</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        h1 {{ color: #2c3e50; }}
                        h2 {{ color: #34495e; }}
                        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                        th {{ background-color: #3498db; color: white; }}
                        tr:nth-child(even) {{ background-color: #f2f2f2; }}
                        .chart {{ margin: 20px 0; text-align: center; }}
                        img {{ max-width: 100%; height: auto; }}
                    </style>
                </head>
                <body>
                    <h1>Order Analysis Report</h1>
                    <p>Report Time: {report.get('report_time', 'Unknown')}</p>
                    <p>Analysis Period: {report.get('period', 'Unknown')}</p>
                    
                    <h2>Executive Summary</h2>
                    <table>
                        <tr><th>Metric</th><th>Value</th></tr>
                        <tr><td>Total Orders</td><td>{summary.get('total_orders', 0)}</td></tr>
                        <tr><td>Fill Rate</td><td>{summary.get('fill_rate', 0):.2%}</td></tr>
                        <tr><td>Avg Slippage</td><td>{summary.get('avg_slippage', 0):.4%}</td></tr>
                        <tr><td>Efficiency Score</td><td>{summary.get('efficiency_score', 0):.2%}</td></tr>
                        <tr><td>Overall Rating</td><td>{summary.get('overall_rating', 'No Data')}</td></tr>
                    </table>
                    
                    <h2>Chart Analysis</h2>
                """

                if execution_chart and os.path.exists(execution_chart):
                    html_content += f'<div class="chart"><h3>Order Execution Status</h3><img src="{os.path.basename(execution_chart)}"></div>'

                if slippage_chart and os.path.exists(slippage_chart):
                    html_content += f'<div class="chart"><h3>Slippage Analysis</h3><img src="{os.path.basename(slippage_chart)}"></div>'

                if volume_chart and os.path.exists(volume_chart):
                    html_content += f'<div class="chart"><h3>Volume Analysis</h3><img src="{os.path.basename(volume_chart)}"></div>'

                if efficiency_chart and os.path.exists(efficiency_chart):
                    html_content += f'<div class="chart"><h3>Order Efficiency Analysis</h3><img src="{os.path.basename(efficiency_chart)}"></div>'

                if recommendations:
                    html_content += '<h2>Recommendations</h2><ul>'
                    for rec in recommendations:
                        html_content += f'<li>{rec}</li>'
                    html_content += '</ul>'

                html_content += '</body></html>'

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                logger.info(f"带图表的HTML报告导出成功: {file_path}")
                return True

            logger.error(f"不支持的导出格式: {format}")
            return False

        except Exception as e:
            logger.error(f"导出带图表的报告失败: {e}")
            return False

    def analyze_order_path(self, order_id: str) -> Dict[str, Any]:
        """
        分析订单执行路径

        Args:
            order_id: 订单ID

        Returns:
            Dict[str, Any]: 订单执行路径分析
        """
        try:
            logger.info(f"开始分析订单执行路径: {order_id}")

            # 1. 获取订单
            order = self.repository.get_order(order_id)
            if not order:
                logger.error(f"订单不存在: {order_id}")
                return {}

            # 2. 获取成交记录
            fills = self.repository.get_order_fills(order_id, order.asset_type)

            # 3. 分析执行路径
            path_analysis = {
                'order_id': order_id,
                'create_time': order.create_time.isoformat(),
                'submit_time': order.execute_time.isoformat() if order.execute_time else None,
                'completion_time': None,
                'total_duration': None,
                'submit_duration': None,
                'execution_duration': None,
                'status_changes': [],
                'fills': [],
                'path_stages': []
            }

            # 4. 计算时间
            if order.execute_time:
                submit_duration = (order.execute_time - order.create_time).total_seconds()
                path_analysis['submit_duration'] = submit_duration

            if fills:
                last_fill_time = max(fill.fill_time for fill in fills)
                path_analysis['completion_time'] = last_fill_time.isoformat()
                path_analysis['total_duration'] = (last_fill_time - order.create_time).total_seconds()

                if order.execute_time:
                    path_analysis['execution_duration'] = (last_fill_time - order.execute_time).total_seconds()

            # 5. 状态变化
            path_analysis['status_changes'].append({
                'status': 'PENDING',
                'time': order.create_time.isoformat()
            })

            if order.execute_time:
                path_analysis['status_changes'].append({
                    'status': 'SUBMITTED',
                    'time': order.execute_time.isoformat()
                })

            if order.order_status == OrderStatus.FILLED:
                path_analysis['status_changes'].append({
                    'status': 'FILLED',
                    'time': path_analysis['completion_time']
                })
            elif order.order_status == OrderStatus.CANCELLED:
                path_analysis['status_changes'].append({
                    'status': 'CANCELLED',
                    'time': order.update_time.isoformat()
                })
            elif order.order_status == OrderStatus.REJECTED:
                path_analysis['status_changes'].append({
                    'status': 'REJECTED',
                    'time': order.update_time.isoformat()
                })

            # 6. 成交记录
            for fill in fills:
                path_analysis['fills'].append({
                    'fill_id': fill.fill_id,
                    'fill_price': fill.fill_price,
                    'fill_quantity': fill.fill_quantity,
                    'fill_time': fill.fill_time.isoformat(),
                    'commission': fill.commission
                })

            # 7. 执行阶段
            if order.create_time:
                path_analysis['path_stages'].append({
                    'stage': '创建',
                    'time': order.create_time.isoformat(),
                    'duration': 0
                })

            if order.execute_time:
                path_analysis['path_stages'].append({
                    'stage': '提交',
                    'time': order.execute_time.isoformat(),
                    'duration': path_analysis['submit_duration']
                })

            if path_analysis['completion_time']:
                path_analysis['path_stages'].append({
                    'stage': '成交',
                    'time': path_analysis['completion_time'],
                    'duration': path_analysis['execution_duration']
                })

            logger.info(f"订单执行路径分析完成: {order_id}")
            return path_analysis

        except Exception as e:
            logger.error(f"分析订单执行路径失败: {e}")
            return {}

    def analyze_order_cost(self, order_id: str) -> Dict[str, Any]:
        """
        分析订单成本

        Args:
            order_id: 订单ID

        Returns:
            Dict[str, Any]: 订单成本分析
        """
        try:
            logger.info(f"开始分析订单成本: {order_id}")

            # 1. 获取订单
            order = self.repository.get_order(order_id)
            if not order:
                logger.error(f"订单不存在: {order_id}")
                return {}

            # 2. 获取成交记录
            fills = self.repository.get_order_fills(order_id, order.asset_type)

            # 3. 计算各项成本
            cost_analysis = {
                'order_id': order_id,
                'order_value': order.order_price * order.order_quantity,
                'filled_value': 0,
                'commission': 0,
                'slippage_cost': 0,
                'total_cost': 0,
                'cost_ratio': 0,
                'fills': []
            }

            # 4. 计算成交成本
            for fill in fills:
                fill_value = fill.fill_price * fill.fill_quantity
                cost_analysis['filled_value'] += fill_value
                cost_analysis['commission'] += fill.commission

                # 计算滑点成本
                slippage = abs(fill.fill_price - order.order_price) * fill.fill_quantity
                cost_analysis['slippage_cost'] += slippage

                cost_analysis['fills'].append({
                    'fill_id': fill.fill_id,
                    'fill_price': fill.fill_price,
                    'fill_quantity': fill.fill_quantity,
                    'fill_value': fill_value,
                    'commission': fill.commission,
                    'slippage': slippage
                })

            # 5. 计算总成本
            cost_analysis['total_cost'] = cost_analysis['commission'] + cost_analysis['slippage_cost']

            # 6. 计算成本比例
            if cost_analysis['filled_value'] > 0:
                cost_analysis['cost_ratio'] = cost_analysis['total_cost'] / cost_analysis['filled_value']

            logger.info(f"订单成本分析完成: {order_id}")
            return cost_analysis

        except Exception as e:
            logger.error(f"分析订单成本失败: {e}")
            return {}

    def analyze_order_timing(self, period: AnalysisPeriod = AnalysisPeriod.DAY) -> Dict[str, Any]:
        """
        分析订单时间特征

        Args:
            period: 分析周期

        Returns:
            Dict[str, Any]: 订单时间分析
        """
        try:
            if isinstance(period, str):
                period = AnalysisPeriod(period)
            logger.info(f"开始分析订单时间特征: {period.value}")

            # 1. 确定时间范围
            start_time, end_time = self._get_period_range(period)

            # 2. 查询订单
            query = OrderQuery(limit=10000)
            orders = self.repository.query_orders(query)

            # 3. 过滤时间范围内的订单
            period_orders = [o for o in orders if start_time <= o.create_time <= end_time]

            if not period_orders:
                logger.warning("时间范围内没有订单")
                return {}

            # 4. 分析时间特征
            timing_analysis = {
                'period': period.value,
                'total_orders': len(period_orders),
                'hourly_distribution': {},
                'daily_distribution': {},
                'weekday_distribution': {},
                'submit_times': [],
                'execution_times': [],
                'waiting_times': []
            }

            # 5. 按小时统计
            for order in period_orders:
                hour = order.create_time.hour
                if hour not in timing_analysis['hourly_distribution']:
                    timing_analysis['hourly_distribution'][hour] = 0
                timing_analysis['hourly_distribution'][hour] += 1

                # 按星期统计
                weekday = order.create_time.strftime('%A')
                if weekday not in timing_analysis['weekday_distribution']:
                    timing_analysis['weekday_distribution'][weekday] = 0
                timing_analysis['weekday_distribution'][weekday] += 1

                # 提交时间
                timing_analysis['submit_times'].append(order.create_time)

                # 执行时间
                if order.execute_time:
                    timing_analysis['execution_times'].append(order.execute_time)

                    # 等待时间
                    waiting_time = (order.execute_time - order.create_time).total_seconds()
                    timing_analysis['waiting_times'].append(waiting_time)

            # 6. 计算统计信息
            if timing_analysis['waiting_times']:
                timing_analysis['avg_waiting_time'] = statistics.mean(timing_analysis['waiting_times'])
                timing_analysis['max_waiting_time'] = max(timing_analysis['waiting_times'])
                timing_analysis['min_waiting_time'] = min(timing_analysis['waiting_times'])

            # 7. 找出最活跃的时间段
            if timing_analysis['hourly_distribution']:
                best_hour = max(timing_analysis['hourly_distribution'].items(), key=lambda x: x[1])
                timing_analysis['most_active_hour'] = {
                    'hour': best_hour[0],
                    'count': best_hour[1]
                }

            if timing_analysis['weekday_distribution']:
                best_weekday = max(timing_analysis['weekday_distribution'].items(), key=lambda x: x[1])
                timing_analysis['most_active_weekday'] = {
                    'weekday': best_weekday[0],
                    'count': best_weekday[1]
                }

            logger.info(f"订单时间特征分析完成: {period.value}")
            return timing_analysis

        except Exception as e:
            logger.error(f"分析订单时间特征失败: {e}")
            return {}

    def analyze_order_risk(self, order_id: str) -> Dict[str, Any]:
        """
        分析订单风险

        Args:
            order_id: 订单ID

        Returns:
            Dict[str, Any]: 订单风险分析
        """
        try:
            logger.info(f"开始分析订单风险: {order_id}")

            # 1. 获取订单
            order = self.repository.get_order(order_id)
            if not order:
                logger.error(f"订单不存在: {order_id}")
                return {}

            # 2. 获取成交记录
            fills = self.repository.get_order_fills(order_id, order.asset_type)

            # 3. 计算风险指标
            risk_analysis = {
                'order_id': order_id,
                'risk_level': 'LOW',
                'risk_score': 0,
                'risk_factors': [],
                'market_risk': 0,
                'execution_risk': 0,
                'liquidity_risk': 0,
                'concentration_risk': 0
            }

            # 4. 市场风险（基于滑点）
            if fills:
                slippages = []
                for fill in fills:
                    slippage = abs(fill.fill_price - order.order_price) / order.order_price
                    slippages.append(slippage)

                avg_slippage = statistics.mean(slippages) if slippages else 0
                risk_analysis['market_risk'] = min(avg_slippage * 100, 100)

                if avg_slippage > 0.01:
                    risk_analysis['risk_factors'].append('高滑点风险')

            # 5. 执行风险（基于等待时间）
            if order.execute_time:
                waiting_time = (order.execute_time - order.create_time).total_seconds()
                if waiting_time > 30:
                    risk_analysis['execution_risk'] = min(waiting_time / 60, 100)
                    risk_analysis['risk_factors'].append('执行延迟风险')

            # 6. 流动性风险（基于订单大小）
            if order.order_quantity > 10000:
                risk_analysis['liquidity_risk'] = min(order.order_quantity / 100000, 100)
                risk_analysis['risk_factors'].append('大额订单流动性风险')

            # 7. 集中度风险（基于资产类型）
            if order.asset_type in [AssetType.FUTURES, AssetType.OPTION]:
                risk_analysis['concentration_risk'] = 30
                risk_analysis['risk_factors'].append('衍生品集中度风险')

            # 8. 计算综合风险评分
            risk_analysis['risk_score'] = (
                risk_analysis['market_risk'] * 0.3 +
                risk_analysis['execution_risk'] * 0.3 +
                risk_analysis['liquidity_risk'] * 0.25 +
                risk_analysis['concentration_risk'] * 0.15
            )

            # 9. 确定风险等级
            if risk_analysis['risk_score'] < 30:
                risk_analysis['risk_level'] = 'LOW'
            elif risk_analysis['risk_score'] < 60:
                risk_analysis['risk_level'] = 'MEDIUM'
            else:
                risk_analysis['risk_level'] = 'HIGH'

            logger.info(f"订单风险分析完成: {order_id} - 风险等级: {risk_analysis['risk_level']}")
            return risk_analysis

        except Exception as e:
            logger.error(f"分析订单风险失败: {e}")
            return {}

    def predict_order_fill_probability(self, order_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        预测订单成交概率

        Args:
            order_request: 订单请求参数

        Returns:
            Dict[str, Any]: 预测结果
        """
        try:
            logger.info("开始预测订单成交概率")

            # 1. 获取历史订单数据
            query = OrderQuery(limit=10000)
            orders = self.repository.query_orders(query)

            # 2. 筛选相似订单
            similar_orders = []
            for order in orders:
                if (order.stock_code == order_request.get('stock_code') and
                    order.order_type.value == order_request.get('order_type') and
                    order.asset_type.value == order_request.get('asset_type')):
                    similar_orders.append(order)

            if not similar_orders:
                return {
                    'probability': 0.5,
                    'confidence': 'LOW',
                    'factors': {
                        'historical_data': '无历史数据',
                        'market_conditions': '未知'
                    }
                }

            # 3. 计算成交率
            filled_orders = [o for o in similar_orders if o.order_status == OrderStatus.FILLED]
            fill_probability = len(filled_orders) / len(similar_orders)

            # 4. 分析影响因子
            factors = {
                'historical_data': f'基于 {len(similar_orders)} 个历史订单',
                'fill_rate': f'历史成交率: {fill_probability:.2%}',
                'sample_size': '样本量充足' if len(similar_orders) > 100 else '样本量有限'
            }

            # 5. 确定置信度
            if len(similar_orders) > 100:
                confidence = 'HIGH'
            elif len(similar_orders) > 10:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'

            logger.info(f"订单成交概率预测完成: {fill_probability:.2%} (置信度: {confidence})")
            return {
                'probability': fill_probability,
                'confidence': confidence,
                'factors': factors
            }

        except Exception as e:
            logger.error(f"预测订单成交概率失败: {e}")
            return {
                'probability': 0.5,
                'confidence': 'LOW',
                'factors': {
                    'error': str(e)
                }
            }

    def export_report_to_csv(self, report: Dict[str, Any], file_path: str) -> bool:
        """导出报告到CSV文件"""
        try:
            import csv

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # 写入整体分析
                writer.writerow(['整体分析'])
                writer.writerow(['指标', '值'])

                overall = report.get('overall_analysis', {})
                if 'execution_analysis' in overall:
                    for key, value in overall['execution_analysis'].items():
                        writer.writerow([key, value])

                writer.writerow([])

                # 写入资产类型分析
                writer.writerow(['资产类型分析'])
                asset_analysis = report.get('asset_type_analysis', {})
                for asset_type, analysis in asset_analysis.items():
                    writer.writerow([f'资产类型: {asset_type}'])
                    for key, value in analysis.items():
                        writer.writerow([key, value])
                    writer.writerow([])

                # 写入建议
                writer.writerow(['建议'])
                recommendations = report.get('recommendations', [])
                for i, rec in enumerate(recommendations, 1):
                    writer.writerow([i, rec])

            logger.info(f"报告已导出到: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出报告失败: {e}")
            return False
