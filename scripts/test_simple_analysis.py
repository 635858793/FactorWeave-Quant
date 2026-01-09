"""
简单测试订单分析器
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.trading.order_analyzer import OrderAnalyzer, AnalysisPeriod
from core.containers import get_service_container
from core.events import get_event_bus


def test_simple_analysis():
    """简单测试订单分析器"""
    try:
        logger.info("=" * 80)
        logger.info("开始简单测试订单分析器")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()

        # 2. 创建订单分析器
        logger.info("\n2. 创建订单分析器...")
        analyzer = OrderAnalyzer(service_container, event_bus)
        logger.info("✅ 订单分析器创建成功")

        # 3. 测试基础分析
        logger.info("\n3. 测试基础订单执行分析...")
        try:
            execution_analysis = analyzer.analyze_order_execution(AnalysisPeriod.DAY)
            logger.info(f"✅ 订单执行分析完成:")
            logger.info(f"   - 总订单数: {execution_analysis.total_orders}")
            logger.info(f"   - 成交率: {execution_analysis.fill_rate:.2%}")
        except Exception as e:
            logger.error(f"❌ 订单执行分析失败: {e}")
            import traceback
            traceback.print_exc()

        # 4. 测试综合报告
        logger.info("\n4. 测试综合分析报告...")
        try:
            report = analyzer.generate_comprehensive_report(AnalysisPeriod.DAY)
            if report:
                logger.info(f"✅ 综合分析报告生成成功")
                summary = report.get('summary', {})
                logger.info(f"   - 总订单数: {summary.get('total_orders', 0)}")
                logger.info(f"   - 成交率: {summary.get('fill_rate', 0):.2%}")
                logger.info(f"   - 综合评级: {summary.get('overall_rating', 'N/A')}")
            else:
                logger.warning("⚠️  没有生成综合分析报告")
        except Exception as e:
            logger.error(f"❌ 综合分析报告生成失败: {e}")
            import traceback
            traceback.print_exc()

        logger.info("\n" + "=" * 80)
        logger.info("✅ 简单测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 简单测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = test_simple_analysis()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
