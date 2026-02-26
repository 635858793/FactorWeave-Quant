#!/usr/bin/env python3
"""
回测UI功能全面测试脚本
测试所有回测相关组件的功能完整性
"""

import sys
import os
import traceback
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
log_file = project_root / "logs" / f"backtest_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.makedirs(log_file.parent, exist_ok=True)

from loguru import logger
logger.remove()
logger.add(str(log_file), level="DEBUG", format="{time} | {level} | {message}")
logger.add(sys.stderr, level="INFO", format="{time} | {level} | {message}")

class BacktestUITester:
    """回测UI功能测试类"""

    def __init__(self):
        self.test_results = []
        self.passed_count = 0
        self.failed_count = 0

    def log_test(self, test_name, status, details=""):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.test_results.append(result)

        if status == "PASS":
            self.passed_count += 1
            logger.info(f"✅ {test_name}: PASS")
        else:
            self.failed_count += 1
            logger.error(f"❌ {test_name}: FAIL - {details}")

    def test_imports(self):
        """测试1: 验证所有核心模块导入"""
        logger.info("\n" + "="*60)
        logger.info("测试1: 验证核心模块导入")
        logger.info("="*60)

        # 测试ProfessionalBacktestWidget
        try:
            from gui.widgets.backtest_widget import ProfessionalBacktestWidget
            self.log_test(
                "ProfessionalBacktestWidget导入",
                "PASS",
                f"类定义: {ProfessionalBacktestWidget.__name__}"
            )

            # 检查内部类
            from gui.widgets.backtest_widget import RealTimeChart, MetricsPanel, ControlPanel
            self.log_test(
                "ProfessionalBacktestWidget内部类导入",
                "PASS",
                f"RealTimeChart, MetricsPanel, ControlPanel"
            )
        except Exception as e:
            self.log_test("ProfessionalBacktestWidget导入", "FAIL", str(e))

        # 测试ModernUnifiedPerformanceWidget
        try:
            from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
            self.log_test(
                "ModernUnifiedPerformanceWidget导入",
                "PASS",
                f"类定义: {ModernUnifiedPerformanceWidget.__name__}"
            )
        except Exception as e:
            self.log_test("ModernUnifiedPerformanceWidget导入", "FAIL", str(e))

        # 测试RightPanel回测模块
        try:
            from core.ui.panels.right_panel import RightPanel
            self.log_test(
                "RightPanel导入",
                "PASS",
                f"类定义: {RightPanel.__name__}"
            )
        except Exception as e:
            self.log_test("RightPanel导入", "FAIL", str(e))

        # 测试BacktestUILauncher
        try:
            from gui.backtest_ui_launcher import BacktestUILauncher
            self.log_test(
                "BacktestUILauncher导入",
                "PASS",
                f"类定义: {BacktestUILauncher.__name__}"
            )
        except Exception as e:
            self.log_test("BacktestUILauncher导入", "FAIL", str(e))

        # 测试RealTimeBacktestMonitor
        try:
            from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
            self.log_test(
                "RealTimeBacktestMonitor导入",
                "PASS",
                f"类定义: {RealTimeBacktestMonitor.__name__}"
            )
        except Exception as e:
            self.log_test("RealTimeBacktestMonitor导入", "FAIL", str(e))

        # 测试ProfessionalUISystem
        try:
            from backtest.professional_ui_system import ProfessionalUISystem
            self.log_test(
                "ProfessionalUISystem导入",
                "PASS",
                f"类定义: {ProfessionalUISystem.__name__}"
            )
        except Exception as e:
            self.log_test("ProfessionalUISystem导入", "FAIL", str(e))

        # 测试StrategyPerformanceMonitor
        try:
            from gui.widgets.strategy_performance_monitor import StrategyPerformanceMonitor
            self.log_test(
                "StrategyPerformanceMonitor导入",
                "PASS",
                f"类定义: {StrategyPerformanceMonitor.__name__}"
            )
        except Exception as e:
            self.log_test("StrategyPerformanceMonitor导入", "FAIL", str(e))

    def test_class_hierarchy(self):
        """测试2: 验证类继承关系和方法完整性"""
        logger.info("\n" + "="*60)
        logger.info("测试2: 验证类继承关系和方法")
        logger.info("="*60)

        # 测试ProfessionalBacktestWidget
        try:
            from gui.widgets.backtest_widget import ProfessionalBacktestWidget
            from PyQt5.QtWidgets import QWidget

            # 验证继承关系
            if issubclass(ProfessionalBacktestWidget, QWidget):
                self.log_test(
                    "ProfessionalBacktestWidget继承QWidget",
                    "PASS",
                    "正确继承自QWidget"
                )
            else:
                self.log_test(
                    "ProfessionalBacktestWidget继承QWidget",
                    "FAIL",
                    "未正确继承QWidget"
                )

            # 验证必需方法
            required_methods = [
                'init_ui', 'create_dashboard', 'run_backtest',
                'load_result', 'export_result'
            ]

            for method in required_methods:
                if hasattr(ProfessionalBacktestWidget, method):
                    self.log_test(
                        f"ProfessionalBacktestWidget.{method}()",
                        "PASS",
                        "方法存在"
                    )
                else:
                    self.log_test(
                        f"ProfessionalBacktestWidget.{method}()",
                        "FAIL",
                        "方法不存在"
                    )

        except Exception as e:
            self.log_test("ProfessionalBacktestWidget类结构", "FAIL", str(e))

        # 测试ModernUnifiedPerformanceWidget
        try:
            from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget

            required_methods = ['init_ui', 'refresh_data', 'export_report']
            for method in required_methods:
                if hasattr(ModernUnifiedPerformanceWidget, method):
                    self.log_test(
                        f"ModernUnifiedPerformanceWidget.{method}()",
                        "PASS",
                        "方法存在"
                    )
                else:
                    self.log_test(
                        f"ModernUnifiedPerformanceWidget.{method}()",
                        "FAIL",
                        "方法不存在"
                    )

        except Exception as e:
            self.log_test("ModernUnifiedPerformanceWidget类结构", "FAIL", str(e))

    def test_integration_points(self):
        """测试3: 验证集成点正确性"""
        logger.info("\n" + "="*60)
        logger.info("测试3: 验证集成点")
        logger.info("="*60)

        # 测试MainWindowCoordinator中的回测集成
        try:
            from core.coordinators.main_window_coordinator import MainWindowCoordinator

            # 验证必需方法
            backtest_methods = [
                '_create_professional_backtest_widget',
                '_on_professional_backtest',
                '_create_standalone_backtest_window',
                '_on_performance_center'
            ]

            for method in backtest_methods:
                if hasattr(MainWindowCoordinator, method):
                    self.log_test(
                        f"MainWindowCoordinator.{method}()",
                        "PASS",
                        "方法存在"
                    )
                else:
                    self.log_test(
                        f"MainWindowCoordinator.{method}()",
                        "FAIL",
                        "方法不存在"
                    )

        except Exception as e:
            self.log_test("MainWindowCoordinator回测集成", "FAIL", str(e))

        # 测试MenuBar中的回测菜单
        try:
            from gui.menu_bar import MenuBar

            # 验证必需属性
            menu_attrs = [
                'professional_backtest_action',
                'backtest_action',
                'performance_menu'
            ]

            for attr in menu_attrs:
                if hasattr(MenuBar, attr):
                    self.log_test(
                        f"MenuBar.{attr}",
                        "PASS",
                        "属性存在"
                    )
                else:
                    self.log_test(
                        f"MenuBar.{attr}",
                        "FAIL",
                        "属性不存在"
                    )

        except Exception as e:
            self.log_test("MenuBar回测菜单", "FAIL", str(e))

    def test_right_panel_backtest(self):
        """测试4: 验证RightPanel回测模块"""
        logger.info("\n" + "="*60)
        logger.info("测试4: 验证RightPanel回测模块")
        logger.info("="*60)

        try:
            from core.ui.panels.right_panel import RightPanel

            # 验证必需方法
            required_methods = [
                '_create_backtest_tab',
                '_setup_backtest_connections',
                '_on_delete_result',
                '_on_clear_results',
                '_on_export_results'
            ]

            for method in required_methods:
                if hasattr(RightPanel, method):
                    self.log_test(
                        f"RightPanel.{method}()",
                        "PASS",
                        "方法存在"
                    )
                else:
                    self.log_test(
                        f"RightPanel.{method}()",
                        "FAIL",
                        "方法不存在"
                    )

            # 验证_backtest_result_manager导入
            import inspect
            source = inspect.getsource(RightPanel)
            if 'BacktestResultManager' in source:
                self.log_test(
                    "RightPanel.BacktestResultManager引用",
                    "PASS",
                    "正确导入BacktestResultManager"
                )
            else:
                self.log_test(
                    "RightPanel.BacktestResultManager引用",
                    "FAIL",
                    "未找到BacktestResultManager引用"
                )

        except Exception as e:
            self.log_test("RightPanel回测模块", "FAIL", str(e))

    def test_service_dependencies(self):
        """测试5: 验证服务依赖"""
        logger.info("\n" + "="*60)
        logger.info("测试5: 验证服务依赖")
        logger.info("="*60)

        # 测试服务容器
        try:
            from core.containers import get_service_container
            container = get_service_container()
            self.log_test(
                "服务容器获取",
                "PASS",
                f"容器类型: {type(container).__name__}"
            )
        except Exception as e:
            self.log_test("服务容器获取", "FAIL", str(e))

        # 测试事件总线
        try:
            from core.events import get_event_bus
            event_bus = get_event_bus()
            self.log_test(
                "事件总线获取",
                "PASS",
                f"事件总线类型: {type(event_bus).__name__}"
            )
        except Exception as e:
            self.log_test("事件总线获取", "FAIL", str(e))

        # 测试配置管理器
        try:
            from core.config import get_config_manager
            config = get_config_manager()
            self.log_test(
                "配置管理器获取",
                "PASS",
                f"配置类型: {type(config).__name__}"
            )
        except Exception as e:
            self.log_test("配置管理器获取", "FAIL", str(e))

    def test_performance_tabs(self):
        """测试6: 验证性能监控Tab组件"""
        logger.info("\n" + "="*60)
        logger.info("测试6: 验证性能监控Tab组件")
        logger.info("="*60)

        tab_tests = [
            (
                "gui.widgets.performance.tabs.strategy_performance_tab",
                "ModernStrategyPerformanceTab"
            ),
            (
                "gui.widgets.performance.tabs.system_monitor_tab",
                "ModernSystemMonitorTab"
            ),
            (
                "gui.widgets.performance.tabs.algorithm_optimization_tab",
                "ModernAlgorithmOptimizationTab"
            ),
            (
                "gui.widgets.performance.tabs.risk_control_center_tab",
                "ModernRiskControlCenterTab"
            ),
            (
                "gui.widgets.performance.tabs.trading_execution_monitor_tab",
                "ModernTradingExecutionMonitorTab"
            ),
        ]

        for module_path, class_name in tab_tests:
            try:
                module = __import__(module_path, fromlist=[class_name])
                cls = getattr(module, class_name)
                self.log_test(
                    f"{class_name}导入",
                    "PASS",
                    f"从{module_path}导入"
                )
            except Exception as e:
                self.log_test(
                    f"{class_name}导入",
                    "FAIL",
                    f"导入失败: {str(e)[:100]}"
                )

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("\n" + "="*70)
        logger.info("         开始回测UI功能全面测试")
        logger.info("="*70)
        logger.info(f"测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")

        # 执行测试
        self.test_imports()
        self.test_class_hierarchy()
        self.test_integration_points()
        self.test_right_panel_backtest()
        self.test_service_dependencies()
        self.test_performance_tabs()

        # 输出测试摘要
        logger.info("\n" + "="*70)
        logger.info("                    测试摘要")
        logger.info("="*70)
        logger.info(f"总测试数: {len(self.test_results)}")
        logger.info(f"通过: {self.passed_count} ✅")
        logger.info(f"失败: {self.failed_count} ❌")
        logger.info(f"通过率: {self.passed_count/len(self.test_results)*100:.1f}%")
        logger.info("")

        # 输出失败项
        if self.failed_count > 0:
            logger.error("\n失败测试详情:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    logger.error(f"  - {result['test_name']}: {result['details']}")

        logger.info(f"\n测试日志文件: {log_file}")
        logger.info("="*70)

        return self.passed_count, self.failed_count


if __name__ == "__main__":
    # 创建测试实例
    tester = BacktestUITester()

    # 运行测试
    try:
        passed, failed = tester.run_all_tests()

        # 返回退出码
        sys.exit(0 if failed == 0 else 1)

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
