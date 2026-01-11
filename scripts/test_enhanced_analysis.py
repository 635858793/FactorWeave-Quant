"""
测试增强的订单分析报告功能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from datetime import datetime
from core.trading.order_analyzer import OrderAnalyzer, AnalysisPeriod
from core.containers import get_service_container
from core.events import get_event_bus
from core.trading.order_service import OrderService
from core.trading.order_models import Order, OrderType, OrderStatus
from core.plugin_types import AssetType
import json


def test_enhanced_analysis():
    """测试增强的分析功能"""
    try:
        logger.info("=" * 80)
        logger.info("开始测试增强的订单分析报告功能")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()

        # 2. 创建订单分析器
        logger.info("\n2. 创建订单分析器...")
        analyzer = OrderAnalyzer(service_container, event_bus)

        # 3. 测试按资产类型分析
        logger.info("\n3. 测试按资产类型分析...")
        asset_analyses = analyzer.analyze_by_asset_type(AnalysisPeriod.DAY)

        if asset_analyses:
            logger.info(f"✅ 成功分析 {len(asset_analyses)} 种资产类型:")
            for asset_type, analysis in asset_analyses.items():
                logger.info(f"   - {asset_type}: {analysis.total_orders} 个订单, 成交率: {analysis.fill_rate:.2%}")
        else:
            logger.warning("⚠️  没有找到资产类型数据")

        # 4. 测试资产类型性能对比
        logger.info("\n4. 测试资产类型性能对比...")
        asset_comparison = analyzer.compare_asset_performance(AnalysisPeriod.DAY)

        if asset_comparison:
            logger.info("✅ 成功生成资产类型性能对比:")
            logger.info(f"   - 资产类型: {asset_comparison.get('asset_types', [])}")
            
            rankings = asset_comparison.get('rankings', {})
            if 'fill_rate' in rankings:
                logger.info(f"   - 成交率排名: {' > '.join(rankings['fill_rate'][:5])}")
            if 'total_orders' in rankings:
                logger.info(f"   - 订单数量排名: {' > '.join(rankings['total_orders'][:5])}")
        else:
            logger.warning("⚠️  没有生成资产类型性能对比")

        # 5. 测试多资产综合分析报告
        logger.info("\n5. 测试多资产综合分析报告...")
        multi_asset_report = analyzer.generate_multi_asset_report(AnalysisPeriod.DAY)

        if multi_asset_report:
            logger.info("✅ 成功生成多资产综合分析报告:")
            
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

        # 6. 测试导出JSON报告
        logger.info("\n6. 测试导出JSON报告...")
        if multi_asset_report:
            json_path = "data/reports/multi_asset_report.json"
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            
            success = analyzer.export_report_to_json(multi_asset_report, json_path)
            if success:
                logger.info(f"✅ 成功导出JSON报告: {json_path}")
                
                # 验证文件大小
                file_size = os.path.getsize(json_path)
                logger.info(f"   - 文件大小: {file_size} 字节")
            else:
                logger.error("❌ 导出JSON报告失败")

        # 7. 测试导出CSV报告
        logger.info("\n7. 测试导出CSV报告...")
        if multi_asset_report:
            csv_path = "data/reports/multi_asset_report.csv"
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            
            success = analyzer.export_report_to_csv(multi_asset_report, csv_path)
            if success:
                logger.info(f"✅ 成功导出CSV报告: {csv_path}")
                
                # 验证文件大小
                file_size = os.path.getsize(csv_path)
                logger.info(f"   - 文件大小: {file_size} 字节")
            else:
                logger.error("❌ 导出CSV报告失败")

        # 8. 测试不同时间周期
        logger.info("\n8. 测试不同时间周期...")
        periods = [AnalysisPeriod.HOUR, AnalysisPeriod.DAY, AnalysisPeriod.WEEK, AnalysisPeriod.MONTH]

        for period in periods:
            logger.info(f"\n   测试 {period.value} 周期...")
            report = analyzer.generate_multi_asset_report(period)
            
            if report:
                summary = report.get('summary', {})
                logger.info(f"   ✅ {period.value}: {summary.get('total_orders', 0)} 个订单, "
                          f"成交率: {summary.get('fill_rate', 0):.2%}")
            else:
                logger.warning(f"   ⚠️  {period.value}: 没有数据")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 增强的订单分析报告功能测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 测试增强的订单分析报告功能失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = test_enhanced_analysis()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
