"""
分析服务
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.schemas.analysis import AnalysisFilter, ChartRequest
from core.trading.order_analyzer import OrderAnalyzer
from core.containers.service_container import ServiceContainer
from core.events.event_bus import EventBus


class AnalysisService:
    """
    分析服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.service_container = ServiceContainer()
        self.event_bus = EventBus()
        self.order_analyzer = OrderAnalyzer(self.service_container, self.event_bus)
    
    def generate_comprehensive_report(self, filter_params: AnalysisFilter) -> Dict[str, Any]:
        """
        生成综合分析报告
        """
        start_time, end_time = self._get_time_range(filter_params)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        return report
    
    def analyze_order_execution(self, filter_params: AnalysisFilter) -> Dict[str, Any]:
        """
        订单执行分析
        """
        start_time, end_time = self._get_time_range(filter_params)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        return report.get("execution_analysis", {})
    
    def analyze_slippage(self, filter_params: AnalysisFilter) -> Dict[str, Any]:
        """
        滑点分析
        """
        start_time, end_time = self._get_time_range(filter_params)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        return report.get("slippage_analysis", {})
    
    def analyze_volume(self, filter_params: AnalysisFilter) -> Dict[str, Any]:
        """
        成交量分析
        """
        start_time, end_time = self._get_time_range(filter_params)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        return report.get("volume_analysis", {})
    
    def analyze_efficiency(self, filter_params: AnalysisFilter) -> Dict[str, Any]:
        """
        订单效率分析
        """
        start_time, end_time = self._get_time_range(filter_params)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        return report.get("efficiency_analysis", {})
    
    def generate_execution_chart(self, chart_request: ChartRequest) -> Optional[str]:
        """
        生成订单执行图表
        """
        start_time, end_time = self._get_time_range(chart_request)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        chart_path = self.order_analyzer.generate_execution_chart(report, chart_type=chart_request.chart_type)
        
        return chart_path
    
    def generate_slippage_chart(self, chart_request: ChartRequest) -> Optional[str]:
        """
        生成滑点分析图表
        """
        start_time, end_time = self._get_time_range(chart_request)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        chart_path = self.order_analyzer.generate_slippage_chart(report, chart_type=chart_request.chart_type)
        
        return chart_path
    
    def generate_volume_chart(self, chart_request: ChartRequest) -> Optional[str]:
        """
        生成成交量分析图表
        """
        start_time, end_time = self._get_time_range(chart_request)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        chart_path = self.order_analyzer.generate_volume_chart(report, chart_type=chart_request.chart_type)
        
        return chart_path
    
    def generate_efficiency_chart(self, chart_request: ChartRequest) -> Optional[str]:
        """
        生成订单效率图表
        """
        start_time, end_time = self._get_time_range(chart_request)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        chart_path = self.order_analyzer.generate_efficiency_chart(report, chart_type=chart_request.chart_type)
        
        return chart_path
    
    def export_pdf_report(self, chart_request: ChartRequest) -> Optional[str]:
        """
        导出PDF报告
        """
        start_time, end_time = self._get_time_range(chart_request)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        from datetime import datetime
        import os
        
        os.makedirs("reports", exist_ok=True)
        file_path = f"reports/order_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        success = self.order_analyzer.export_report_with_charts(report, file_path, format="pdf")
        
        if success:
            return file_path
        
        return None
    
    def export_html_report(self, chart_request: ChartRequest) -> Optional[str]:
        """
        导出HTML报告
        """
        start_time, end_time = self._get_time_range(chart_request)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        from datetime import datetime
        import os
        
        os.makedirs("reports", exist_ok=True)
        file_path = f"reports/order_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        success = self.order_analyzer.export_report_with_charts(report, file_path, format="html")
        
        if success:
            return file_path
        
        return None
    
    def export_csv_report(self, chart_request: ChartRequest) -> Optional[str]:
        """
        导出CSV报告
        """
        start_time, end_time = self._get_time_range(chart_request)
        
        report = self.order_analyzer.analyze_period(start_time, end_time)
        
        from datetime import datetime
        import os
        import csv
        
        os.makedirs("reports", exist_ok=True)
        file_path = f"reports/order_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                writer.writerow(["Report Time", report.get("report_time", "")])
                writer.writerow(["Period", report.get("period", "")])
                writer.writerow([])
                
                summary = report.get("summary", {})
                writer.writerow(["Summary"])
                for key, value in summary.items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                execution_analysis = report.get("execution_analysis", {})
                writer.writerow(["Execution Analysis"])
                for key, value in execution_analysis.items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                slippage_analysis = report.get("slippage_analysis", {})
                writer.writerow(["Slippage Analysis"])
                for key, value in slippage_analysis.items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                volume_analysis = report.get("volume_analysis", {})
                writer.writerow(["Volume Analysis"])
                for key, value in volume_analysis.items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                efficiency_analysis = report.get("efficiency_analysis", {})
                writer.writerow(["Efficiency Analysis"])
                for key, value in efficiency_analysis.items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                recommendations = report.get("recommendations", [])
                writer.writerow(["Recommendations"])
                for rec in recommendations:
                    writer.writerow([rec])
            
            return file_path
        
        except Exception as e:
            print(f"导出CSV报告失败: {e}")
            return None
    
    def _get_time_range(self, filter_params) -> tuple:
        """
        获取时间范围
        """
        if filter_params.start_time and filter_params.end_time:
            return filter_params.start_time, filter_params.end_time
        
        end_time = datetime.now()
        
        if filter_params.period == "day":
            start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif filter_params.period == "week":
            start_time = end_time - timedelta(days=7)
        elif filter_params.period == "month":
            start_time = end_time - timedelta(days=30)
        elif filter_params.period == "quarter":
            start_time = end_time - timedelta(days=90)
        elif filter_params.period == "year":
            start_time = end_time - timedelta(days=365)
        else:
            start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return start_time, end_time
