"""
测试订单分析功能（使用现有订单数据）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from datetime import datetime
from core.trading.order_analyzer import OrderAnalyzer, AnalysisPeriod
from core.containers import get_service_container
from core.events import get_event_bus


def test_analysis_with_existing_data():
    """使用现有数据测试订单分析"""
    try:
        logger.info("=" * 80)
        logger.info("开始测试订单分析功能（使用现有数据）")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()

        # 2. 创建订单分析器
        logger.info("\n2. 创建订单分析器...")
        analyzer = OrderAnalyzer(service_container, event_bus)

        # 3. 测试基础分析
        logger.info("\n3. 测试基础订单执行分析...")
        execution_analysis = analyzer.analyze_order_execution(AnalysisPeriod.DAY)

        logger.info(f"✅ 订单执行分析完成:")
        logger.info(f"   - 总订单数: {execution_analysis.total_orders}")
        logger.info(f"   - 已成交订单: {execution_analysis.filled_orders}")
        logger.info(f"   - 已取消订单: {execution_analysis.cancelled_orders}")
        logger.info(f"   - 已拒绝订单: {execution_analysis.rejected_orders}")
        logger.info(f"   - 成交率: {execution_analysis.fill_rate:.2%}")
        logger.info(f"   - 平均执行时间: {execution_analysis.avg_execution_time:.2f}秒")
        logger.info(f"   - 平均成交比例: {execution_analysis.avg_fill_ratio:.2%}")
        logger.info(f"   - 订单总价值: {execution_analysis.total_value:.2f}")
        logger.info(f"   - 已成交价值: {execution_analysis.filled_value:.2f}")
        logger.info(f"   - 总手续费: {execution_analysis.total_commission:.2f}")

        # 4. 测试滑点分析
        logger.info("\n4. 测试滑点分析...")
        slippage_analysis = analyzer.analyze_slippage(AnalysisPeriod.DAY)

        logger.info(f"✅ 滑点分析完成:")
        logger.info(f"   - 平均滑点: {slippage_analysis.avg_slippage:.4f}")
        logger.info(f"   - 最大滑点: {slippage_analysis.max_slippage:.4f}")
        logger.info(f"   - 最小滑点: {slippage_analysis.min_slippage:.4f}")
        logger.info(f"   - 滑点标准差: {slippage_analysis.slippage_std:.4f}")
        logger.info(f"   - 正滑点数量: {slippage_analysis.positive_slippage_count}")
        logger.info(f"   - 负滑点数量: {slippage_analysis.negative_slippage_count}")
        logger.info(f"   - 平均正滑点: {slippage_analysis.avg_positive_slippage:.4f}")
        logger.info(f"   - 平均负滑点: {slippage_analysis.avg_negative_slippage:.4f}")

        # 5. 测试成交量分析
        logger.info("\n5. 测试成交量分析...")
        volume_analysis = analyzer.analyze_volume(AnalysisPeriod.DAY)

        logger.info(f"✅ 成交量分析完成:")
        logger.info(f"   - 总成交量: {volume_analysis.total_volume}")
        logger.info(f"   - 平均每单成交量: {volume_analysis.avg_volume_per_order:.0f}")
        logger.info(f"   - 最大成交量: {volume_analysis.max_volume}")
        logger.info(f"   - 最小成交量: {volume_analysis.min_volume}")
        logger.info(f"   - 成交量标准差: {volume_analysis.volume_std:.0f}")
        logger.info(f"   - 买入成交量: {volume_analysis.buy_volume}")
        logger.info(f"   - 卖出成交量: {volume_analysis.sell_volume}")
        logger.info(f"   - 买卖比例: {volume_analysis.buy_sell_ratio:.2f}")

        # 6. 测试效率分析
        logger.info("\n6. 测试订单效率分析...")
        efficiency_analysis = analyzer.analyze_order_efficiency(AnalysisPeriod.DAY)

        logger.info(f"✅ 订单效率分析完成:")
        logger.info(f"   - 效率分数: {efficiency_analysis.efficiency_score:.2f}")
        logger.info(f"   - 成交效率: {efficiency_analysis.fill_efficiency:.2f}")
        logger.info(f"   - 成本效率: {efficiency_analysis.cost_efficiency:.2f}")
        logger.info(f"   - 时间效率: {efficiency_analysis.time_efficiency:.2f}")
        logger.info(f"   - 综合评级: {efficiency_analysis.overall_rating}")

        # 7. 测试综合报告
        logger.info("\n7. 测试综合分析报告...")
        report = analyzer.generate_comprehensive_report(AnalysisPeriod.DAY)

        if report:
            logger.info(f"✅ 综合分析报告生成完成:")
            logger.info(f"   - 报告时间: {report.get('report_time', 'N/A')}")
            logger.info(f"   - 分析周期: {report.get('period', 'N/A')}")
            
            summary = report.get('summary', {})
            logger.info(f"   - 总订单数: {summary.get('total_orders', 0)}")
            logger.info(f"   - 成交率: {summary.get('fill_rate', 0):.2%}")
            logger.info(f"   - 平均滑点: {summary.get('avg_slippage', 0):.4f}")
            logger.info(f"   - 效率分数: {summary.get('efficiency_score', 0):.2f}")
            logger.info(f"   - 综合评级: {summary.get('overall_rating', 'N/A')}")
            
            recommendations = report.get('recommendations', [])
            if recommendations:
                logger.info(f"   - 建议 ({len(recommendations)} 条):")
                for i, rec in enumerate(recommendations, 1):
                    logger.info(f"     {i}. {rec}")
        else:
            logger.warning("⚠️  没有生成综合分析报告")

        # 8. 测试按资产类型分析
        logger.info("\n8. 测试按资产类型分析...")
        asset_analyses = analyzer.analyze_by_asset_type(AnalysisPeriod.DAY)

        if asset_analyses:
            logger.info(f"✅ 按资产类型分析完成 ({len(asset_analyses)} 种资产类型):")
            for asset_type, analysis in asset_analyses.items():
                logger.info(f"   - {asset_type}:")
                logger.info(f"     订单数: {analysis.total_orders}")
                logger.info(f"     成交率: {analysis.fill_rate:.2%}")
                logger.info(f"     平均执行时间: {analysis.avg_execution_time:.2f}秒")
                logger.info(f"     订单总价值: {analysis.total_value:.2f}")
        else:
            logger.warning("⚠️  没有资产类型数据")

        # 9. 测试资产类型对比
        logger.info("\n9. 测试资产类型性能对比...")
        asset_comparison = analyzer.compare_asset_performance(AnalysisPeriod.DAY)

        if asset_comparison:
            logger.info(f"✅ 资产类型性能对比完成:")
            logger.info(f"   - 资产类型: {asset_comparison.get('asset_types', [])}")
            
            rankings = asset_comparison.get('rankings', {})
            if 'fill_rate' in rankings:
                logger.info(f"   - 成交率排名: {' > '.join(rankings['fill_rate'][:5])}")
            if 'total_orders' in rankings:
                logger.info(f"   - 订单数量排名: {' > '.join(rankings['total_orders'][:5])}")
            if 'execution_time' in rankings:
                logger.info(f"   - 执行时间排名: {' > '.join(rankings['execution_time'][:5])}")
        else:
            logger.warning("⚠️  没有生成资产类型性能对比")

        # 10. 测试多资产综合报告
        logger.info("\n10. 测试多资产综合分析报告...")
        multi_asset_report = analyzer.generate_multi_asset_report(AnalysisPeriod.DAY)

        if multi_asset_report:
            logger.info(f"✅ 多资产综合分析报告生成完成:")
            
            summary = multi_asset_report.get('summary', {})
            logger.info(f"   - 总订单数: {summary.get('total_orders', 0)}")
            logger.info(f"   - 资产类型数: {summary.get('asset_types_count', 0)}")
            logger.info(f"   - 整体成交率: {summary.get('fill_rate', 0):.2%}")
            logger.info(f"   - 效率分数: {summary.get('efficiency_score', 0):.2f}")
            logger.info(f"   - 综合评级: {summary.get('overall_rating', 'N/A')}")
            
            if summary.get('best_performing_asset'):
                logger.info(f"   - 最佳表现资产: {summary['best_performing_asset']}")
            if summary.get('most_active_asset'):
                logger.info(f"   - 最活跃资产: {summary['most_active_asset']}")
            
            recommendations = multi_asset_report.get('recommendations', [])
            if recommendations:
                logger.info(f"   - 建议 ({len(recommendations)} 条):")
                for i, rec in enumerate(recommendations[:5], 1):
                    logger.info(f"     {i}. {rec}")
        else:
            logger.warning("⚠️  没有生成多资产综合分析报告")

        # 11. 测试导出报告
        logger.info("\n11. 测试导出报告...")
        if multi_asset_report:
            import os
            os.makedirs("data/reports", exist_ok=True)
            
            # 导出JSON
            json_path = "data/reports/order_analysis_report.json"
            success = analyzer.export_report_to_json(multi_asset_report, json_path)
            if success:
                logger.info(f"✅ JSON报告已导出: {json_path}")
            
            # 导出CSV
            csv_path = "data/reports/order_analysis_report.csv"
            success = analyzer.export_report_to_csv(multi_asset_report, csv_path)
            if success:
                logger.info(f"✅ CSV报告已导出: {csv_path}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 订单分析功能测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 测试订单分析功能失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = test_analysis_with_existing_data()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
