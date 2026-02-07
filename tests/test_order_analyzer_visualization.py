"""
测试订单分析器可视化功能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from core.trading.order_analyzer import OrderAnalyzer, AnalysisPeriod
from core.containers import ServiceContainer
from core.events import EventBus


def test_visualization():
    """测试可视化功能"""
    try:
        print("=" * 60)
        print("开始测试订单分析器可视化功能")
        print("=" * 60)

        service_container = ServiceContainer()
        event_bus = EventBus()
        analyzer = OrderAnalyzer(service_container, event_bus)

        print("\n1. 生成综合分析报告...")
        report = analyzer.generate_comprehensive_report(AnalysisPeriod.DAY)

        if not report:
            print("❌ 综合分析报告生成失败")
            return False

        print("综合分析报告生成成功")
        print(f"   - 报告时间: {report.get('report_time', '未知')}")
        print(f"   - 分析周期: {report.get('period', '未知')}")

        summary = report.get('summary', {})
        print(f"\n2. 执行摘要:")
        print(f"   - 总订单数: {summary.get('total_orders', 0)}")
        print(f"   - 成交率: {summary.get('fill_rate', 0):.2%}")
        print(f"   - 平均滑点: {summary.get('avg_slippage', 0):.4%}")
        print(f"   - 效率分数: {summary.get('efficiency_score', 0):.2%}")
        print(f"   - 总体评级: {summary.get('overall_rating', '无数据')}")

        print("\n3. 生成订单执行图表...")
        execution_chart = analyzer.generate_execution_chart(report, chart_type='bar')
        if execution_chart:
            print(f"订单执行图表生成成功: {execution_chart}")
        else:
            print("❌ 订单执行图表生成失败")

        print("\n4. 生成滑点分析图表...")
        slippage_chart = analyzer.generate_slippage_chart(report, chart_type='line')
        if slippage_chart:
            print(f"滑点分析图表生成成功: {slippage_chart}")
        else:
            print("❌ 滑点分析图表生成失败")

        print("\n5. 生成成交量分析图表...")
        volume_chart = analyzer.generate_volume_chart(report, chart_type='bar')
        if volume_chart:
            print(f"成交量分析图表生成成功: {volume_chart}")
        else:
            print("❌ 成交量分析图表生成失败")

        print("\n6. 生成订单效率图表...")
        efficiency_chart = analyzer.generate_efficiency_chart(report, chart_type='radar')
        if efficiency_chart:
            print(f"订单效率图表生成成功: {efficiency_chart}")
        else:
            print("❌ 订单效率图表生成失败")

        print("\n7. 导出带图表的HTML报告...")
        html_report_path = f"reports/order_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        os.makedirs(os.path.dirname(html_report_path), exist_ok=True)

        if analyzer.export_report_with_charts(report, html_report_path, format='html'):
            print(f"HTML报告导出成功: {html_report_path}")
        else:
            print("❌ HTML报告导出失败")

        print("\n8. 导出带图表的PDF报告...")
        pdf_report_path = f"reports/order_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        if analyzer.export_report_with_charts(report, pdf_report_path, format='pdf'):
            print(f"PDF报告导出成功: {pdf_report_path}")
        else:
            print("❌ PDF报告导出失败（可能需要安装reportlab）")

        print("\n" + "=" * 60)
        print("可视化功能测试完成")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_visualization()
    sys.exit(0 if success else 1)