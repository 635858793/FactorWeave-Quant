#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控中心功能验证和回归测试脚本
验证所有修复的功能是否正常工作
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# 导入必要的模块
from core.monitoring.performance_monitor import PerformanceMonitor, PerformanceAlert
from core.services.alert_rule_engine import AlertRuleEngine, AlertRule
from core.services.alert_deduplication_service import AlertDeduplicationService
from core.services.notification_service import NotificationService
from core.risk_rule_manager import get_risk_rule_manager, RiskRule
from db.models.alert_config_models import get_alert_config_database


class TestResults:
    """测试结果收集器"""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        """添加测试结果"""
        self.results.append({
            'test_name': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status} - {test_name}")
        if message:
            print(f"  {message}")
    
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "="*80)
        print("测试摘要")
        print("="*80)
        print(f"总测试数: {self.passed + self.failed}")
        print(f"通过: {self.passed}")
        print(f"失败: {self.failed}")
        print(f"通过率: {self.passed / (self.passed + self.failed) * 100:.2f}%")
        print("="*80)
        
        if self.failed > 0:
            print("\n失败的测试:")
            for result in self.results:
                if not result['passed']:
                    print(f"  - {result['test_name']}: {result['message']}")


def test_performance_monitor_alert_engine_integration(results: TestResults):
    """测试 PerformanceMonitor 与 AlertRuleEngine 的集成"""
    print("\n" + "="*80)
    print("测试 P0-1: PerformanceMonitor 与 AlertRuleEngine 集成")
    print("="*80)
    
    try:
        # 创建 AlertRuleEngine
        dedup_service = AlertDeduplicationService()
        alert_engine = AlertRuleEngine(dedup_service)
        
        # 创建 PerformanceMonitor
        monitor = PerformanceMonitor()
        
        # 检查是否有 _connect_alert_system 方法
        if hasattr(monitor, '_connect_alert_system'):
            results.add_result(
                "PerformanceMonitor 有 _connect_alert_system 方法",
                True
            )
        else:
            results.add_result(
                "PerformanceMonitor 有 _connect_alert_system 方法",
                False,
                "缺少 _connect_alert_system 方法"
            )
            return
        
        # 检查是否有 _on_alert_raised 方法
        if hasattr(monitor, '_on_alert_raised'):
            results.add_result(
                "PerformanceMonitor 有 _on_alert_raised 方法",
                True
            )
        else:
            results.add_result(
                "PerformanceMonitor 有 _on_alert_raised 方法",
                False,
                "缺少 _on_alert_raised 方法"
            )
            return
        
        # 调用 _connect_alert_system
        monitor._connect_alert_system()
        
        # 检查是否成功连接
        if hasattr(monitor, 'alert_rule_engine') and monitor.alert_rule_engine is not None:
            results.add_result(
                "PerformanceMonitor 成功连接到 AlertRuleEngine",
                True
            )
        else:
            results.add_result(
                "PerformanceMonitor 成功连接到 AlertRuleEngine",
                False,
                "alert_rule_engine 未正确初始化"
            )
        
    except Exception as e:
        results.add_result(
            "PerformanceMonitor 与 AlertRuleEngine 集成",
            False,
            f"测试过程中发生错误: {str(e)}"
        )


def test_notification_service_load_alert_rules(results: TestResults):
    """测试 NotificationService 的 _load_alert_rules 方法"""
    print("\n" + "="*80)
    print("测试 P0-2: NotificationService _load_alert_rules 方法")
    print("="*80)
    
    try:
        # 创建 NotificationService 实例
        notification_service = NotificationService()
        
        # 检查是否有 _load_alert_rules 方法
        if hasattr(notification_service, '_load_alert_rules'):
            results.add_result(
                "NotificationService 有 _load_alert_rules 方法",
                True
            )
        else:
            results.add_result(
                "NotificationService 有 _load_alert_rules 方法",
                False,
                "缺少 _load_alert_rules 方法"
            )
            return
        
        # 检查是否有 _parse_condition 方法
        if hasattr(notification_service, '_parse_condition'):
            results.add_result(
                "NotificationService 有 _parse_condition 方法",
                True
            )
        else:
            results.add_result(
                "NotificationService 有 _parse_condition 方法",
                False,
                "缺少 _parse_condition 方法"
            )
            return
        
        # 检查是否有 _parse_alert_level 方法
        if hasattr(notification_service, '_parse_alert_level'):
            results.add_result(
                "NotificationService 有 _parse_alert_level 方法",
                True
            )
        else:
            results.add_result(
                "NotificationService 有 _parse_alert_level 方法",
                False,
                "缺少 _parse_alert_level 方法"
            )
            return
        
        # 检查是否有 _get_channels_from_settings 方法
        if hasattr(notification_service, '_get_channels_from_settings'):
            results.add_result(
                "NotificationService 有 _get_channels_from_settings 方法",
                True
            )
        else:
            results.add_result(
                "NotificationService 有 _get_channels_from_settings 方法",
                False,
                "缺少 _get_channels_from_settings 方法"
            )
            return
        
        # 测试加载告警规则
        try:
            notification_service._load_alert_rules()
            results.add_result(
                "NotificationService 成功加载告警规则",
                True
            )
        except Exception as e:
            results.add_result(
                "NotificationService 成功加载告警规则",
                False,
                f"加载告警规则失败: {str(e)}"
            )
        
    except Exception as e:
        results.add_result(
            "NotificationService _load_alert_rules 方法",
            False,
            f"测试过程中发生错误: {str(e)}"
        )


def test_risk_rule_dingtalk_fields(results: TestResults):
    """测试 RiskRule 类的 dingtalk_notification 字段"""
    print("\n" + "="*80)
    print("测试 P1-1: RiskRule 类 dingtalk_notification 字段")
    print("="*80)
    
    try:
        # 创建一个 RiskRule 实例
        rule = RiskRule()
        
        # 检查是否有 dingtalk_notification 字段
        if hasattr(rule, 'dingtalk_notification'):
            results.add_result(
                "RiskRule 有 dingtalk_notification 字段",
                True
            )
        else:
            results.add_result(
                "RiskRule 有 dingtalk_notification 字段",
                False,
                "缺少 dingtalk_notification 字段"
            )
            return
        
        # 检查是否有 email_recipients 字段
        if hasattr(rule, 'email_recipients'):
            results.add_result(
                "RiskRule 有 email_recipients 字段",
                True
            )
        else:
            results.add_result(
                "RiskRule 有 email_recipients 字段",
                False,
                "缺少 email_recipients 字段"
            )
            return
        
        # 检查是否有 sms_recipients 字段
        if hasattr(rule, 'sms_recipients'):
            results.add_result(
                "RiskRule 有 sms_recipients 字段",
                True
            )
        else:
            results.add_result(
                "RiskRule 有 sms_recipients 字段",
                False,
                "缺少 sms_recipients 字段"
            )
            return
        
        # 检查是否有 webhook_url 字段
        if hasattr(rule, 'webhook_url'):
            results.add_result(
                "RiskRule 有 webhook_url 字段",
                True
            )
        else:
            results.add_result(
                "RiskRule 有 webhook_url 字段",
                False,
                "缺少 webhook_url 字段"
            )
            return
        
        # 检查是否有 dingtalk_webhook_url 字段
        if hasattr(rule, 'dingtalk_webhook_url'):
            results.add_result(
                "RiskRule 有 dingtalk_webhook_url 字段",
                True
            )
        else:
            results.add_result(
                "RiskRule 有 dingtalk_webhook_url 字段",
                False,
                "缺少 dingtalk_webhook_url 字段"
            )
            return
        
        # 测试设置这些字段
        rule.dingtalk_notification = True
        rule.email_recipients = "test@example.com"
        rule.sms_recipients = "13800138000"
        rule.webhook_url = "https://example.com/webhook"
        rule.dingtalk_webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=xxx"
        
        if rule.dingtalk_notification and rule.email_recipients and rule.sms_recipients and rule.webhook_url and rule.dingtalk_webhook_url:
            results.add_result(
                "RiskRule 字段可以正确设置",
                True
            )
        else:
            results.add_result(
                "RiskRule 字段可以正确设置",
                False,
                "字段设置失败"
            )
        
    except Exception as e:
        results.add_result(
            "RiskRule 类 dingtalk_notification 字段",
            False,
            f"测试过程中发生错误: {str(e)}"
        )


def test_notification_config_ui_integration(results: TestResults):
    """测试通知服务配置 UI 的集成"""
    print("\n" + "="*80)
    print("测试 P1-2: 通知服务配置 UI 集成")
    print("="*80)
    
    try:
        from gui.widgets.performance.tabs.risk_control_center_tab import ModernRiskControlCenterTab
        
        # 检查是否有 _configure_notification_service 方法
        if hasattr(ModernRiskControlCenterTab, '_configure_notification_service'):
            results.add_result(
                "ModernRiskControlCenterTab 有 _configure_notification_service 方法",
                True
            )
        else:
            results.add_result(
                "ModernRiskControlCenterTab 有 _configure_notification_service 方法",
                False,
                "缺少 _configure_notification_service 方法"
            )
            return
        
        # 检查是否有 _reload_notification_config 方法
        if hasattr(ModernRiskControlCenterTab, '_reload_notification_config'):
            results.add_result(
                "ModernRiskControlCenterTab 有 _reload_notification_config 方法",
                True
            )
        else:
            results.add_result(
                "ModernRiskControlCenterTab 有 _reload_notification_config 方法",
                False,
                "缺少 _reload_notification_config 方法"
            )
            return
        
    except Exception as e:
        results.add_result(
            "通知服务配置 UI 集成",
            False,
            f"测试过程中发生错误: {str(e)}"
        )


def test_notification_config_reload(results: TestResults):
    """测试通知服务配置更新后立即生效"""
    print("\n" + "="*80)
    print("测试 P1-3: 通知服务配置更新后立即生效")
    print("="*80)
    
    try:
        from gui.widgets.performance.tabs.risk_control_center_tab import ModernRiskControlCenterTab
        
        # 检查 add_risk_rule 方法是否调用 _reload_notification_config
        import inspect
        source = inspect.getsource(ModernRiskControlCenterTab.add_risk_rule)
        
        if '_reload_notification_config' in source:
            results.add_result(
                "add_risk_rule 方法调用 _reload_notification_config",
                True
            )
        else:
            results.add_result(
                "add_risk_rule 方法调用 _reload_notification_config",
                False,
                "add_risk_rule 方法未调用 _reload_notification_config"
            )
        
        # 检查 edit_risk_rule 方法是否调用 _reload_notification_config
        source = inspect.getsource(ModernRiskControlCenterTab.edit_risk_rule)
        
        if '_reload_notification_config' in source:
            results.add_result(
                "edit_risk_rule 方法调用 _reload_notification_config",
                True
            )
        else:
            results.add_result(
                "edit_risk_rule 方法调用 _reload_notification_config",
                False,
                "edit_risk_rule 方法未调用 _reload_notification_config"
            )
        
        # 检查 delete_risk_rule 方法是否调用 _reload_notification_config
        source = inspect.getsource(ModernRiskControlCenterTab.delete_risk_rule)
        
        if '_reload_notification_config' in source:
            results.add_result(
                "delete_risk_rule 方法调用 _reload_notification_config",
                True
            )
        else:
            results.add_result(
                "delete_risk_rule 方法调用 _reload_notification_config",
                False,
                "delete_risk_rule 方法未调用 _reload_notification_config"
            )
        
    except Exception as e:
        results.add_result(
            "通知服务配置更新后立即生效",
            False,
            f"测试过程中发生错误: {str(e)}"
        )


def test_risk_history_persistence(results: TestResults):
    """测试风险历史数据持久化"""
    print("\n" + "="*80)
    print("测试 P1-4: 风险历史数据持久化")
    print("="*80)
    
    try:
        from db.models.alert_config_models import get_alert_config_database
        
        # 获取数据库实例
        db = get_alert_config_database()
        
        # 检查是否有 save_risk_history 方法
        if hasattr(db, 'save_risk_history'):
            results.add_result(
                "AlertConfigDatabase 有 save_risk_history 方法",
                True
            )
        else:
            results.add_result(
                "AlertConfigDatabase 有 save_risk_history 方法",
                False,
                "缺少 save_risk_history 方法"
            )
            return
        
        # 检查是否有 load_risk_history 方法
        if hasattr(db, 'load_risk_history'):
            results.add_result(
                "AlertConfigDatabase 有 load_risk_history 方法",
                True
            )
        else:
            results.add_result(
                "AlertConfigDatabase 有 load_risk_history 方法",
                False,
                "缺少 load_risk_history 方法"
            )
            return
        
        # 测试保存风险历史数据
        try:
            from db.models.alert_config_models import RiskHistoryRecord
            
            test_record = RiskHistoryRecord(
                timestamp=datetime.now().isoformat(),
                overall_risk_score=75.5,
                risk_level="高风险",
                var_95=85.0,
                max_drawdown=12.5,
                volatility=15.0,
                status="警告"
            )
            
            db.save_risk_history(test_record)
            results.add_result(
                "成功保存风险历史数据",
                True
            )
        except Exception as e:
            results.add_result(
                "成功保存风险历史数据",
                False,
                f"保存风险历史数据失败: {str(e)}"
            )
            return
        
        # 测试加载风险历史数据
        try:
            records = db.load_risk_history(limit=1)
            if records and len(records) > 0:
                results.add_result(
                    "成功加载风险历史数据",
                    True
                )
            else:
                results.add_result(
                    "成功加载风险历史数据",
                    False,
                    "加载的风险历史数据为空"
                )
        except Exception as e:
            results.add_result(
                "成功加载风险历史数据",
                False,
                f"加载风险历史数据失败: {str(e)}"
            )
        
    except Exception as e:
        results.add_result(
            "风险历史数据持久化",
            False,
            f"测试过程中发生错误: {str(e)}"
        )


def test_risk_rule_crud_operations(results: TestResults):
    """测试风险规则的增删改查操作"""
    print("\n" + "="*80)
    print("测试 P1-5: 风险规则增删改查操作")
    print("="*80)
    
    try:
        # 获取 RiskRuleManager 实例
        rule_manager = get_risk_rule_manager()
        
        # 测试添加规则
        test_rule = RiskRule(
            name="测试规则",
            rule_type="VaR风险",
            priority="高",
            enabled=True,
            description="这是一个测试规则",
            metric_name="VaR(95%)",
            operator=">",
            threshold_value=80.0,
            threshold_unit="%",
            duration=60,
            check_interval=60,
            silence_period=300,
            max_alerts=10,
            email_notification=True,
            sms_notification=False,
            desktop_notification=True,
            sound_notification=True,
            webhook_notification=False,
            dingtalk_notification=True,
            message_template="测试消息模板",
            email_recipients="test@example.com",
            sms_recipients="13800138000",
            webhook_url="https://example.com/webhook",
            dingtalk_webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx"
        )
        
        add_result = rule_manager.add_rule(test_rule)
        if add_result:
            results.add_result(
                "成功添加风险规则",
                True
            )
        else:
            results.add_result(
                "成功添加风险规则",
                False,
                "添加风险规则失败"
            )
            return
        
        # 获取规则 ID
        rule_id = test_rule.id
        
        # 测试查询规则
        retrieved_rule = rule_manager.get_rule(rule_id)
        if retrieved_rule and retrieved_rule.name == "测试规则":
            results.add_result(
                "成功查询风险规则",
                True
            )
        else:
            results.add_result(
                "成功查询风险规则",
                False,
                "查询的风险规则不正确"
            )
            return
        
        # 测试更新规则
        retrieved_rule.description = "更新后的测试规则"
        retrieved_rule.dingtalk_notification = False
        update_result = rule_manager.update_rule(retrieved_rule)
        if update_result:
            results.add_result(
                "成功更新风险规则",
                True
            )
        else:
            results.add_result(
                "成功更新风险规则",
                False,
                "更新风险规则失败"
            )
            return
        
        # 验证更新
        updated_rule = rule_manager.get_rule(rule_id)
        if updated_rule and updated_rule.description == "更新后的测试规则" and not updated_rule.dingtalk_notification:
            results.add_result(
                "风险规则更新正确",
                True
            )
        else:
            results.add_result(
                "风险规则更新正确",
                False,
                "风险规则更新不正确"
            )
            return
        
        # 测试删除规则
        delete_result = rule_manager.delete_rule(rule_id)
        if delete_result:
            results.add_result(
                "成功删除风险规则",
                True
            )
        else:
            results.add_result(
                "成功删除风险规则",
                False,
                "删除风险规则失败"
            )
            return
        
        # 验证删除
        deleted_rule = rule_manager.get_rule(rule_id)
        if deleted_rule is None:
            results.add_result(
                "风险规则删除正确",
                True
            )
        else:
            results.add_result(
                "风险规则删除正确",
                False,
                "风险规则未正确删除"
            )
        
    except Exception as e:
        results.add_result(
            "风险规则增删改查操作",
            False,
            f"测试过程中发生错误: {str(e)}"
        )


def main():
    """主测试函数"""
    print("="*80)
    print("性能监控中心功能验证和回归测试")
    print("="*80)
    print(f"开始时间: {datetime.now().isoformat()}")
    
    # 创建测试结果收集器
    results = TestResults()
    
    # 运行所有测试
    test_performance_monitor_alert_engine_integration(results)
    test_notification_service_load_alert_rules(results)
    test_risk_rule_dingtalk_fields(results)
    test_notification_config_ui_integration(results)
    test_notification_config_reload(results)
    test_risk_history_persistence(results)
    test_risk_rule_crud_operations(results)
    
    # 打印测试摘要
    results.print_summary()
    
    print(f"\n结束时间: {datetime.now().isoformat()}")
    print("="*80)
    
    # 返回测试结果
    return results.failed == 0


if __name__ == "__main__":
    # 创建 QApplication 实例（某些组件需要）
    app = QApplication(sys.argv)
    
    # 运行测试
    success = main()
    
    # 退出
    sys.exit(0 if success else 1)
