"""
UI组件功能测试脚本
测试FeatureControlService、DynamicRiskAdjustmentEngine、HealthMonitor和PerformanceMonitor的UI组件
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
from loguru import logger


def test_feature_control_widget():
    """测试FeatureControlWidget"""
    logger.info("=" * 60)
    logger.info("测试FeatureControlWidget - 功能开关管理")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.feature_control_widget import FeatureControlWidget
        from core.services.feature_control_service import FeatureControlService
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建UI组件
        widget = FeatureControlWidget()
        logger.info("✓ FeatureControlWidget创建成功")
        
        # 测试服务初始化
        if widget.feature_service:
            logger.info("✓ FeatureControlService初始化成功")
        else:
            logger.warning("⚠ FeatureControlService未初始化")
        
        # 测试UI组件
        logger.info("✓ UI组件包含以下标签页:")
        for i in range(widget.tab_widget.count()):
            logger.info(f"  - {widget.tab_widget.tabText(i)}")
        
        # 测试配置表格
        if hasattr(widget, 'config_table'):
            row_count = widget.config_table.rowCount()
            logger.info(f"✓ 配置表格行数: {row_count}")
        
        # 测试状态表格
        if hasattr(widget, 'status_table'):
            row_count = widget.status_table.rowCount()
            logger.info(f"✓ 状态表格行数: {row_count}")
        
        # 测试工具栏按钮
        logger.info("✓ 工具栏按钮:")
        for action in widget.toolbar.actions():
            if not action.isSeparator():
                logger.info(f"  - {action.text()}")
        
        # 测试信号连接
        logger.info("✓ 信号连接:")
        logger.info(f"  - feature_toggled: {widget.feature_toggled}")
        logger.info(f"  - feature_config_updated: {widget.feature_config_updated}")
        
        logger.info("✓ FeatureControlWidget测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ FeatureControlWidget测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dynamic_risk_adjustment_widget():
    """测试DynamicRiskAdjustmentWidget"""
    logger.info("\n" + "=" * 60)
    logger.info("测试DynamicRiskAdjustmentWidget - 风险参数监控")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.dynamic_risk_adjustment_widget import DynamicRiskAdjustmentWidget
        from core.services.dynamic_risk_adjustment_service import DynamicRiskAdjustmentEngine
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建UI组件
        widget = DynamicRiskAdjustmentWidget()
        logger.info("✓ DynamicRiskAdjustmentWidget创建成功")
        
        # 测试引擎初始化
        if widget.risk_engine:
            logger.info("✓ DynamicRiskAdjustmentEngine初始化成功")
            
            # 测试初始参数
            params = widget.risk_engine.current_params
            logger.info(f"✓ 当前参数数量: {len(params)}")
        else:
            logger.warning("⚠ DynamicRiskAdjustmentEngine未初始化")
        
        # 测试UI组件
        logger.info("✓ UI组件包含以下标签页:")
        for i in range(widget.tab_widget.count()):
            logger.info(f"  - {widget.tab_widget.tabText(i)}")
        
        # 测试参数监控表格
        if hasattr(widget, 'params_table'):
            row_count = widget.params_table.rowCount()
            logger.info(f"✓ 参数监控表格行数: {row_count}")
        
        # 测试工具栏按钮
        logger.info("✓ 工具栏按钮:")
        for action in widget.toolbar.actions():
            if not action.isSeparator():
                logger.info(f"  - {action.text()}")
        
        # 测试信号连接
        logger.info("✓ 信号连接:")
        logger.info(f"  - adjustment_executed: {widget.adjustment_executed}")
        logger.info(f"  - strategy_changed: {widget.strategy_changed}")
        
        logger.info("✓ DynamicRiskAdjustmentWidget测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ DynamicRiskAdjustmentWidget测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_health_monitor_widget():
    """测试HealthMonitorWidget"""
    logger.info("\n" + "=" * 60)
    logger.info("测试HealthMonitorWidget - 系统健康状态监控")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.health_monitor_widget import HealthMonitorWidget
        from core.services.fault_tolerance_manager import HealthMonitor, HealthMetrics
        from core.enums import HealthStatus
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建UI组件
        widget = HealthMonitorWidget()
        logger.info("✓ HealthMonitorWidget创建成功")
        
        # 测试监控器初始化
        if widget.health_monitor:
            logger.info("✓ HealthMonitor初始化成功")
            
            # 测试健康阈值
            thresholds = widget.health_monitor.health_thresholds
            logger.info(f"✓ 健康阈值数量: {len(thresholds)}")
        else:
            logger.warning("⚠ HealthMonitor未初始化")
        
        # 测试UI组件
        logger.info("✓ UI组件包含以下标签页:")
        for i in range(widget.tab_widget.count()):
            logger.info(f"  - {widget.tab_widget.tabText(i)}")
        
        # 测试状态指示器
        if hasattr(widget, 'status_widget'):
            logger.info("✓ 状态指示器组件存在")
        
        # 测试指标显示组件
        if hasattr(widget, 'metrics_widget'):
            logger.info("✓ 指标显示组件存在")
        
        # 测试工具栏按钮
        logger.info("✓ 工具栏按钮:")
        for action in widget.toolbar.actions():
            if not action.isSeparator():
                logger.info(f"  - {action.text()}")
        
        # 测试信号连接
        logger.info("✓ 信号连接:")
        logger.info(f"  - health_status_changed: {widget.health_status_changed}")
        
        # 测试模拟健康数据更新
        if widget.health_monitor:
            test_metrics = HealthMetrics(
                cpu_usage=45.0,
                memory_usage=60.0,
                disk_usage=55.0,
                network_latency=150.0,
                error_rate=0.01,
                response_time=500.0,
                active_connections=10
            )
            widget.health_monitor.update_health_metrics("test_node", test_metrics)
            logger.info("✓ 模拟健康数据更新成功")
        
        logger.info("✓ HealthMonitorWidget测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ HealthMonitorWidget测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_monitor_widget():
    """测试PerformanceMonitorWidget"""
    logger.info("\n" + "=" * 60)
    logger.info("测试PerformanceMonitorWidget - 性能指标监控")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.performance_monitor_widget import PerformanceMonitorWidget
        from core.monitoring.performance_monitor import PerformanceMonitor, PerformanceMetric
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建UI组件
        widget = PerformanceMonitorWidget()
        logger.info("✓ PerformanceMonitorWidget创建成功")
        
        # 测试监控器初始化
        if widget.performance_monitor:
            logger.info("✓ PerformanceMonitor初始化成功")
            
            # 测试会话统计
            stats = widget.performance_monitor.session_stats
            logger.info(f"✓ 会话统计: {stats}")
        else:
            logger.warning("⚠ PerformanceMonitor未初始化")
        
        # 测试UI组件
        logger.info("✓ UI组件包含以下标签页:")
        for i in range(widget.tab_widget.count()):
            logger.info(f"  - {widget.tab_widget.tabText(i)}")
        
        # 测试指标显示组件
        if hasattr(widget, 'metrics_widget'):
            logger.info("✓ 指标显示组件存在")
        
        # 测试警报组件
        if hasattr(widget, 'alert_widget'):
            logger.info("✓ 警报显示组件存在")
        
        # 测试工具栏按钮
        logger.info("✓ 工具栏按钮:")
        for action in widget.toolbar.actions():
            if not action.isSeparator():
                logger.info(f"  - {action.text()}")
        
        # 测试信号连接
        logger.info("✓ 信号连接:")
        logger.info(f"  - metric_recorded: {widget.metric_recorded}")
        logger.info(f"  - alert_raised: {widget.alert_raised}")
        logger.info(f"  - recommendation_updated: {widget.recommendation_updated}")
        logger.info(f"  - performance_summary_updated: {widget.performance_summary_updated}")
        
        # 测试模拟性能数据记录
        if widget.performance_monitor:
            test_metric = PerformanceMetric(
                timestamp=time.time(),
                metric_type='render_time',
                value=120.0,
                unit='ms',
                component='volume',
                additional_data={'frame_count': 60}
            )
            widget.performance_monitor.record_metric(
                test_metric.metric_type,
                test_metric.value,
                test_metric.unit,
                test_metric.component,
                test_metric.additional_data
            )
            logger.info("✓ 模拟性能数据记录成功")
        
        logger.info("✓ PerformanceMonitorWidget测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ PerformanceMonitorWidget测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_backend_connections():
    """测试UI与后端的连接"""
    logger.info("\n" + "=" * 60)
    logger.info("测试UI与后端连接")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 测试所有UI组件的导入
        logger.info("✓ 测试UI组件导入:")
        
        from gui.widgets.feature_control_widget import FeatureControlWidget
        logger.info("  ✓ FeatureControlWidget导入成功")
        
        from gui.widgets.dynamic_risk_adjustment_widget import DynamicRiskAdjustmentWidget
        logger.info("  ✓ DynamicRiskAdjustmentWidget导入成功")
        
        from gui.widgets.health_monitor_widget import HealthMonitorWidget
        logger.info("  ✓ HealthMonitorWidget导入成功")
        
        from gui.widgets.performance_monitor_widget import PerformanceMonitorWidget
        logger.info("  ✓ PerformanceMonitorWidget导入成功")
        
        # 测试所有后端服务的导入
        logger.info("✓ 测试后端服务导入:")
        
        from core.services.feature_control_service import FeatureControlService
        logger.info("  ✓ FeatureControlService导入成功")
        
        from core.services.dynamic_risk_adjustment_service import DynamicRiskAdjustmentEngine
        logger.info("  ✓ DynamicRiskAdjustmentEngine导入成功")
        
        from core.services.fault_tolerance_manager import HealthMonitor
        logger.info("  ✓ HealthMonitor导入成功")
        
        from core.monitoring.performance_monitor import PerformanceMonitor
        logger.info("  ✓ PerformanceMonitor导入成功")
        
        # 测试数据类的导入
        logger.info("✓ 测试数据类导入:")
        
        from core.services.fault_tolerance_manager import HealthMetrics
        logger.info("  ✓ HealthMetrics导入成功")
        
        from core.monitoring.performance_monitor import PerformanceMetric, PerformanceAlert
        logger.info("  ✓ PerformanceMetric导入成功")
        logger.info("  ✓ PerformanceAlert导入成功")
        
        # 测试枚举类的导入
        logger.info("✓ 测试枚举类导入:")
        
        from core.enums import HealthStatus
        logger.info("  ✓ HealthStatus导入成功")
        
        logger.info("✓ UI与后端连接测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ UI与后端连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_professional_design():
    """测试UI专业性设计"""
    logger.info("\n" + "=" * 60)
    logger.info("测试UI专业性设计")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        from gui.widgets.feature_control_widget import FeatureControlWidget
        from gui.widgets.dynamic_risk_adjustment_widget import DynamicRiskAdjustmentWidget
        from gui.widgets.health_monitor_widget import HealthMonitorWidget
        from gui.widgets.performance_monitor_widget import PerformanceMonitorWidget
        
        # 测试所有UI组件的专业性设计
        widgets = {
            'FeatureControlWidget': FeatureControlWidget(),
            'DynamicRiskAdjustmentWidget': DynamicRiskAdjustmentWidget(),
            'HealthMonitorWidget': HealthMonitorWidget(),
            'PerformanceMonitorWidget': PerformanceMonitorWidget()
        }
        
        for name, widget in widgets.items():
            logger.info(f"✓ {name}专业性设计检查:")
            
            # 检查是否有工具栏
            if hasattr(widget, 'toolbar'):
                logger.info(f"  ✓ 包含工具栏")
            
            # 检查是否有标签页
            if hasattr(widget, 'tab_widget'):
                tab_count = widget.tab_widget.count()
                logger.info(f"  ✓ 包含{tab_count}个标签页")
            
            # 检查是否有自动刷新功能
            if hasattr(widget, 'update_timer'):
                logger.info(f"  ✓ 包含自动刷新功能")
            
            # 检查是否有信号定义
            signal_count = len([attr for attr in dir(widget) if hasattr(getattr(widget, attr), 'emit')])
            logger.info(f"  ✓ 定义了{signal_count}个信号")
        
        logger.info("✓ UI专业性设计测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ UI专业性设计测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("开始UI组件功能测试")
    logger.info("=" * 60)
    
    results = {}
    
    # 测试各个UI组件
    results['FeatureControlWidget'] = test_feature_control_widget()
    results['DynamicRiskAdjustmentWidget'] = test_dynamic_risk_adjustment_widget()
    results['HealthMonitorWidget'] = test_health_monitor_widget()
    results['PerformanceMonitorWidget'] = test_performance_monitor_widget()
    
    # 测试UI与后端连接
    results['UI与后端连接'] = test_ui_backend_connections()
    
    # 测试UI专业性设计
    results['UI专业性设计'] = test_ui_professional_design()
    
    # 输出测试结果
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("✓ 所有测试通过！")
        return 0
    else:
        logger.error(f"✗ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
