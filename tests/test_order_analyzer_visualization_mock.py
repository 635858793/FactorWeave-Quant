"""
测试订单分析器可视化功能（不依赖数据库）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from core.trading.order_analyzer import OrderAnalyzer, AnalysisPeriod
from core.containers import ServiceContainer
from core.events import EventBus


def test_visualization_mock():
    """使用模拟数据测试可视化功能"""
    try:
        print("=" * 60)
        print("开始测试订单分析器可视化功能（使用模拟数据）")
        print("=" * 60)

        service_container = ServiceContainer()
        event_bus = EventBus()
        analyzer = OrderAnalyzer(service_container, event_bus)

        print("\n1. 创建模拟分析报告...")
        report = {
            'report_time': datetime.now().isoformat(),
            'period': 'day',
            'execution_analysis': {
                'period': 'day',
                'total_orders': 100,
                'filled_orders': 85,
                'cancelled_orders': 10,
                'rejected_orders': 5,
                'fill_rate': 0.85,
                'avg_execution_time': 2.5,
                'avg_fill_ratio': 0.95,
                'total_value': 1000000.0,
                'filled_value': 850000.0,
                'total_commission': 5000.0,
                'avg_order_value': 10000.0,
                'avg_fill_value': 10000.0
            },
            'slippage_analysis': {
                'period': 'day',
                'avg_slippage': 0.0005,
                'max_slippage': 0.0020,
                'min_slippage': -0.0010,
                'slippage_std': 0.0008,
                'positive_slippage_count': 40,
                'negative_slippage_count': 45,
                'avg_positive_slippage': 0.0008,
                'avg_negative_slippage': -0.0003
            },
            'volume_analysis': {
                'period': 'day',
                'total_volume': 50000,
                'avg_volume_per_order': 500,
                'max_volume': 2000,
                'min_volume': 100,
                'volume_std': 300.0,
                'buy_volume': 25000,
                'sell_volume': 25000,
                'buy_sell_ratio': 1.0
            },
            'efficiency_analysis': {
                'period': 'day',
                'efficiency_score': 0.85,
                'fill_efficiency': 0.85,
                'cost_efficiency': 0.95,
                'time_efficiency': 0.80,
                'overall_rating': 'Good'
            },
            'summary': {
                'total_orders': 100,
                'fill_rate': 0.85,
                'avg_slippage': 0.0005,
                'efficiency_score': 0.85,
                'overall_rating': 'Good'
            },
            'recommendations': [
                '订单执行情况良好，继续保持',
                '建议优化订单价格设置以提高成交率',
                '建议关注滑点变化，优化执行时机'
            ]
        }

        print("模拟分析报告创建成功")

        summary = report.get('summary', {})
        print(f"\n2. 执行摘要:")
        print(f"   - Total Orders: {summary.get('total_orders', 0)}")
        print(f"   - Fill Rate: {summary.get('fill_rate', 0):.2%}")
        print(f"   - Avg Slippage: {summary.get('avg_slippage', 0):.4%}")
        print(f"   - Efficiency Score: {summary.get('efficiency_score', 0):.2%}")
        print(f"   - Overall Rating: {summary.get('overall_rating', 'No Data')}")

        print("\n3. 生成订单执行图表...")
        execution_chart = analyzer.generate_execution_chart(report, chart_type='bar')
        if execution_chart:
            print(f"订单执行图表生成成功: {execution_chart}")
            print(f"   文件存在: {os.path.exists(execution_chart)}")
            if os.path.exists(execution_chart):
                file_size = os.path.getsize(execution_chart)
                print(f"   文件大小: {file_size} bytes")
        else:
            print("❌ 订单执行图表生成失败")

        print("\n4. 生成滑点分析图表...")
        slippage_chart = analyzer.generate_slippage_chart(report, chart_type='line')
        if slippage_chart:
            print(f"滑点分析图表生成成功: {slippage_chart}")
            print(f"   文件存在: {os.path.exists(slippage_chart)}")
            if os.path.exists(slippage_chart):
                file_size = os.path.getsize(slippage_chart)
                print(f"   文件大小: {file_size} bytes")
        else:
            print("❌ 滑点分析图表生成失败")

        print("\n5. 生成成交量分析图表...")
        volume_chart = analyzer.generate_volume_chart(report, chart_type='bar')
        if volume_chart:
            print(f"成交量分析图表生成成功: {volume_chart}")
            print(f"   文件存在: {os.path.exists(volume_chart)}")
            if os.path.exists(volume_chart):
                file_size = os.path.getsize(volume_chart)
                print(f"   文件大小: {file_size} bytes")
        else:
            print("❌ 成交量分析图表生成失败")

        print("\n6. 生成订单效率图表...")
        efficiency_chart = analyzer.generate_efficiency_chart(report, chart_type='radar')
        if efficiency_chart:
            print(f"订单效率图表生成成功: {efficiency_chart}")
            print(f"   文件存在: {os.path.exists(efficiency_chart)}")
            if os.path.exists(efficiency_chart):
                file_size = os.path.getsize(efficiency_chart)
                print(f"   文件大小: {file_size} bytes")
        else:
            print("❌ 订单效率图表生成失败")

        print("\n7. 导出带图表的HTML报告...")
        os.makedirs('reports', exist_ok=True)
        html_report_path = f"reports/order_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        if analyzer.export_report_with_charts(report, html_report_path, format='html'):
            print(f"HTML报告导出成功: {html_report_path}")
            print(f"   文件存在: {os.path.exists(html_report_path)}")
            if os.path.exists(html_report_path):
                file_size = os.path.getsize(html_report_path)
                print(f"   文件大小: {file_size} bytes")
        else:
            print("❌ HTML报告导出失败")

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
    success = test_visualization_mock()
    sys.exit(0 if success else 1)