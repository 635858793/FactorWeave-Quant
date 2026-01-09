#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试高级分析功能
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from datetime import datetime
from core.trading.order_analyzer import OrderAnalyzer, AnalysisPeriod
from core.containers import get_service_container
from core.events import get_event_bus


def test_advanced_analysis():
    """测试高级分析功能"""
    try:
        logger.info("=" * 80)
        logger.info("开始测试高级分析功能")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()
        analyzer = OrderAnalyzer(service_container, event_bus)
        logger.info("✅ 分析器初始化完成")

        # 2. 测试订单执行路径分析
        logger.info("\n2. 测试订单执行路径分析...")
        path_analysis = analyzer.analyze_order_path("TEST_ORDER_001")
        if path_analysis:
            logger.info("✅ 订单执行路径分析完成")
            logger.info(f"   订单ID: {path_analysis.get('order_id')}")
            logger.info(f"   创建时间: {path_analysis.get('create_time')}")
            logger.info(f"   提交时间: {path_analysis.get('submit_time')}")
            logger.info(f"   完成时间: {path_analysis.get('completion_time')}")
            logger.info(f"   总耗时: {path_analysis.get('total_duration')} 秒")
            logger.info(f"   状态变化数: {len(path_analysis.get('status_changes', []))}")
            logger.info(f"   成交记录数: {len(path_analysis.get('fills', []))}")
        else:
            logger.warning("⚠️  订单执行路径分析未返回结果")

        # 3. 测试订单成本分析
        logger.info("\n3. 测试订单成本分析...")
        cost_analysis = analyzer.analyze_order_cost("TEST_ORDER_001")
        if cost_analysis:
            logger.info("✅ 订单成本分析完成")
            logger.info(f"   订单价值: {cost_analysis.get('order_value'):.2f}")
            logger.info(f"   成交价值: {cost_analysis.get('filled_value'):.2f}")
            logger.info(f"   手续费: {cost_analysis.get('commission'):.2f}")
            logger.info(f"   滑点成本: {cost_analysis.get('slippage_cost'):.2f}")
            logger.info(f"   总成本: {cost_analysis.get('total_cost'):.2f}")
            logger.info(f"   成本比例: {cost_analysis.get('cost_ratio'):.4f}")
        else:
            logger.warning("⚠️  订单成本分析未返回结果")

        # 4. 测试订单时间特征分析
        logger.info("\n4. 测试订单时间特征分析...")
        timing_analysis = analyzer.analyze_order_timing(AnalysisPeriod.DAY)
        if timing_analysis:
            logger.info("✅ 订单时间特征分析完成")
            logger.info(f"   总订单数: {timing_analysis.get('total_orders')}")
            logger.info(f"   平均等待时间: {timing_analysis.get('avg_waiting_time'):.2f} 秒")
            logger.info(f"   最大等待时间: {timing_analysis.get('max_waiting_time'):.2f} 秒")
            logger.info(f"   最小等待时间: {timing_analysis.get('min_waiting_time'):.2f} 秒")

            most_active_hour = timing_analysis.get('most_active_hour')
            if most_active_hour:
                logger.info(f"   最活跃时段: {most_active_hour.get('hour')}:00 ({most_active_hour.get('count')} 个订单)")

            most_active_weekday = timing_analysis.get('most_active_weekday')
            if most_active_weekday:
                logger.info(f"   最活跃星期: {most_active_weekday.get('weekday')} ({most_active_weekday.get('count')} 个订单)")
        else:
            logger.warning("⚠️  订单时间特征分析未返回结果")

        # 5. 测试订单风险分析
        logger.info("\n5. 测试订单风险分析...")
        risk_analysis = analyzer.analyze_order_risk("TEST_ORDER_001")
        if risk_analysis:
            logger.info("✅ 订单风险分析完成")
            logger.info(f"   风险等级: {risk_analysis.get('risk_level')}")
            logger.info(f"   风险评分: {risk_analysis.get('risk_score'):.2f}")
            logger.info(f"   市场风险: {risk_analysis.get('market_risk'):.2f}")
            logger.info(f"   执行风险: {risk_analysis.get('execution_risk'):.2f}")
            logger.info(f"   流动性风险: {risk_analysis.get('liquidity_risk'):.2f}")
            logger.info(f"   集中度风险: {risk_analysis.get('concentration_risk'):.2f}")
            logger.info(f"   风险因子: {', '.join(risk_analysis.get('risk_factors', []))}")
        else:
            logger.warning("⚠️  订单风险分析未返回结果")

        # 6. 测试订单成交概率预测
        logger.info("\n6. 测试订单成交概率预测...")
        order_request = {
            'stock_code': '600000',
            'order_type': 'BUY',
            'asset_type': 'STOCK_A'
        }
        prediction = analyzer.predict_order_fill_probability(order_request)
        if prediction:
            logger.info("✅ 订单成交概率预测完成")
            logger.info(f"   成交概率: {prediction.get('probability'):.2%}")
            logger.info(f"   置信度: {prediction.get('confidence')}")

            factors = prediction.get('factors', {})
            for key, value in factors.items():
                logger.info(f"   {key}: {value}")
        else:
            logger.warning("⚠️  订单成交概率预测未返回结果")

        # 7. 测试导出分析结果
        logger.info("\n7. 测试导出分析结果...")
        export_path = "order_analysis_result.json"
        export_data = {
            'path_analysis': path_analysis,
            'cost_analysis': cost_analysis,
            'timing_analysis': timing_analysis,
            'risk_analysis': risk_analysis,
            'prediction': prediction
        }

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ 分析结果已导出到: {export_path}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 高级分析功能测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 高级分析功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = test_advanced_analysis()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
