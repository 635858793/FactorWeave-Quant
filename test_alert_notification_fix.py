#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试告警配置通知方式修复后的功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from db.models.alert_config_models import AlertRule, AlertConfigDatabase

def test_database_migration():
    """测试数据库迁移"""
    logger.info("=== 测试数据库迁移 ===")
    
    try:
        # 创建数据库实例
        db = AlertConfigDatabase()
        
        # 测试保存告警规则（包含新的通知字段）
        test_rule = AlertRule(
            name="测试规则-Webhook通知",
            rule_type="系统资源",
            priority="高",
            enabled=True,
            description="测试Webhook和钉钉通知功能",
            metric_name="CPU使用率",
            operator=">",
            threshold_value=80.0,
            threshold_unit="%",
            duration=60,
            check_interval=60,
            silence_period=300,
            max_alerts=10,
            email_notification=True,
            sms_notification=False,
            webhook_notification=True,
            dingtalk_notification=True,
            desktop_notification=True,
            sound_notification=True,
            email_recipients="test@example.com,user@example.com",
            sms_recipients="13800138000,13900139000",
            webhook_url="https://example.com/webhook",
            dingtalk_webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx",
            message_template="测试消息模板"
        )
        
        # 保存规则
        rule_id = db.save_alert_rule(test_rule)
        if rule_id:
            logger.info(f"✓ 告警规则保存成功，ID: {rule_id}")
        else:
            logger.error("✗ 告警规则保存失败")
            return False
        
        # 加载规则
        rules = db.load_alert_rules()
        if rules:
            loaded_rule = rules[0]
            logger.info(f"✓ 告警规则加载成功，共 {len(rules)} 条规则")
            
            # 验证新字段
            assert loaded_rule.webhook_notification == True, "webhook_notification字段值不正确"
            assert loaded_rule.dingtalk_notification == True, "dingtalk_notification字段值不正确"
            logger.info("✓ 新增通知字段验证通过")
            
            # 验证通知参数字段
            assert loaded_rule.email_recipients == "test@example.com,user@example.com", "email_recipients字段值不正确"
            assert loaded_rule.sms_recipients == "13800138000,13900139000", "sms_recipients字段值不正确"
            assert loaded_rule.webhook_url == "https://example.com/webhook", "webhook_url字段值不正确"
            assert loaded_rule.dingtalk_webhook_url == "https://oapi.dingtalk.com/robot/send?access_token=xxx", "dingtalk_webhook_url字段值不正确"
            logger.info("✓ 通知参数字段验证通过")
            
            # 显示规则详情
            logger.info(f"规则详情: {loaded_rule.name}")
            logger.info(f"  - 邮件通知: {loaded_rule.email_notification}")
            logger.info(f"  - 短信通知: {loaded_rule.sms_notification}")
            logger.info(f"  - Webhook通知: {loaded_rule.webhook_notification}")
            logger.info(f"  - 钉钉通知: {loaded_rule.dingtalk_notification}")
            logger.info(f"  - 桌面通知: {loaded_rule.desktop_notification}")
            logger.info(f"  - 声音通知: {loaded_rule.sound_notification}")
            logger.info(f"  - 邮件收件人: {loaded_rule.email_recipients}")
            logger.info(f"  - 短信收件人: {loaded_rule.sms_recipients}")
            logger.info(f"  - Webhook URL: {loaded_rule.webhook_url}")
            logger.info(f"  - 钉钉Webhook URL: {loaded_rule.dingtalk_webhook_url}")
        else:
            logger.error("✗ 告警规则加载失败")
            return False
        
        # 清理测试数据
        db.delete_alert_rule(rule_id)
        logger.info("✓ 测试数据清理完成")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 数据库迁移测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_model_consistency():
    """测试数据模型一致性"""
    logger.info("\n=== 测试数据模型一致性 ===")
    
    try:
        # 测试AlertRule数据类
        rule = AlertRule(
            name="测试规则",
            webhook_notification=True,
            dingtalk_notification=True
        )
        
        # 验证字段存在
        assert hasattr(rule, 'webhook_notification'), "缺少webhook_notification字段"
        assert hasattr(rule, 'dingtalk_notification'), "缺少dingtalk_notification字段"
        logger.info("✓ 数据模型字段验证通过")
        
        # 测试字段默认值
        new_rule = AlertRule()
        assert new_rule.webhook_notification == False, "webhook_notification默认值不正确"
        assert new_rule.dingtalk_notification == False, "dingtalk_notification默认值不正确"
        logger.info("✓ 数据模型默认值验证通过")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 数据模型一致性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_notification_service():
    """测试通知服务"""
    logger.info("\n=== 测试通知服务 ===")
    
    try:
        from core.services.notification_service import NotificationService, NotificationType
        
        # 创建通知服务实例
        service = NotificationService()
        
        # 初始化服务
        service.initialize()
        
        # 测试NotificationType枚举
        assert hasattr(NotificationType, 'WEBHOOK'), "缺少WEBHOOK通知类型"
        assert hasattr(NotificationType, 'DINGTALK'), "缺少DINGTALK通知类型"
        logger.info("✓ 通知类型枚举验证通过")
        
        # 测试默认渠道初始化
        channels = service.get_all_channels()
        channel_types = [ch.notification_type for ch in channels]
        
        assert NotificationType.WEBHOOK in channel_types, "缺少Webhook默认渠道"
        assert NotificationType.DINGTALK in channel_types, "缺少DingTalk默认渠道"
        logger.info("✓ 默认通知渠道初始化验证通过")
        
        # 显示所有渠道
        logger.info(f"可用通知渠道: {len(channels)} 个")
        for channel in channels:
            logger.info(f"  - {channel.name} ({channel.notification_type.value}): {'启用' if channel.enabled else '禁用'}")
        
        # 测试统计字段
        stats = service._notification_stats
        assert hasattr(stats, 'webhook_sent'), "缺少webhook_sent统计字段"
        assert hasattr(stats, 'dingtalk_sent'), "缺少dingtalk_sent统计字段"
        logger.info("✓ 通知统计字段验证通过")
        
        # 清理
        service.dispose()
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 通知服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_notification_parameters_flow():
    """测试通知参数完整流程"""
    logger.info("\n=== 测试通知参数完整流程 ===")
    
    try:
        from core.services.notification_service import NotificationService, NotificationType
        from db.models.alert_config_models import AlertRule as DBAlertRule, AlertConfigDatabase
        from core.services.notification_service import AlertRule as NotificationAlertRule, RuleCondition, AlertLevel
        
        # 1. 创建数据库实例并保存规则
        db = AlertConfigDatabase()
        
        test_rule = DBAlertRule(
            name="测试通知参数流程",
            rule_type="系统资源",
            priority="高",
            enabled=True,
            description="测试通知参数的完整流程",
            metric_name="CPU使用率",
            operator=">",
            threshold_value=80.0,
            threshold_unit="%",
            duration=60,
            check_interval=60,
            silence_period=300,
            max_alerts=10,
            email_notification=True,
            sms_notification=False,
            webhook_notification=True,
            dingtalk_notification=True,
            desktop_notification=True,
            sound_notification=True,
            email_recipients="admin@example.com",
            sms_recipients="13800138000",
            webhook_url="https://example.com/webhook",
            dingtalk_webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx",
            message_template="告警：{rule_name}，当前值：{metric_value}"
        )
        
        rule_id = db.save_alert_rule(test_rule)
        if not rule_id:
            logger.error("✗ 规则保存失败")
            return False
        logger.info(f"✓ 规则保存成功，ID: {rule_id}")
        
        # 2. 从数据库加载规则
        loaded_rules = db.load_alert_rules()
        loaded_rule = loaded_rules[0]
        logger.info(f"✓ 规则加载成功")
        
        # 3. 创建通知服务并添加规则
        service = NotificationService()
        service.initialize()
        
        # 创建NotificationAlertRule对象用于通知服务
        notification_rule = NotificationAlertRule(
            rule_id=f"rule_{rule_id}",
            name=loaded_rule.name,
            description=loaded_rule.description,
            metric_name=loaded_rule.metric_name,
            condition=RuleCondition.GREATER_THAN,
            threshold_value=loaded_rule.threshold_value,
            alert_level=AlertLevel.WARNING,
            channels=["email", "webhook", "dingtalk"],
            enabled=loaded_rule.enabled,
            cooldown_minutes=60,
            metadata={
                'email_recipients': loaded_rule.email_recipients,
                'sms_recipients': loaded_rule.sms_recipients,
                'webhook_url': loaded_rule.webhook_url,
                'dingtalk_webhook_url': loaded_rule.dingtalk_webhook_url,
                'message_template': loaded_rule.message_template
            }
        )
        
        service.add_alert_rule(notification_rule)
        logger.info(f"✓ 规则添加到通知服务")
        
        # 4. 测试发送告警
        message_id = service.send_alert(notification_rule.rule_id, 85.0)
        if message_id:
            logger.info(f"✓ 告警发送成功，消息ID: {message_id}")
        else:
            logger.warning("告警未发送（可能处于冷却期）")
        
        # 5. 验证通知配置参数是否正确传递
        if message_id:
            message = service._messages.get(message_id)
            if message:
                logger.info(f"✓ 消息元数据验证:")
                logger.info(f"  - email_recipients: {message.metadata.get('email_recipients')}")
                logger.info(f"  - sms_recipients: {message.metadata.get('sms_recipients')}")
                logger.info(f"  - webhook_url: {message.metadata.get('webhook_url')}")
                logger.info(f"  - dingtalk_webhook_url: {message.metadata.get('dingtalk_webhook_url')}")
                
                assert message.metadata.get('email_recipients') == "admin@example.com", "邮件收件人参数未正确传递"
                assert message.metadata.get('webhook_url') == "https://example.com/webhook", "Webhook URL参数未正确传递"
                logger.info("✓ 通知参数传递验证通过")
        
        # 清理
        service.dispose()
        db.delete_alert_rule(rule_id)
        logger.info("✓ 测试数据清理完成")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 通知参数流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    logger.info("开始测试告警配置通知方式修复功能\n")
    
    results = []
    
    # 测试数据库迁移
    results.append(("数据库迁移", test_database_migration()))
    
    # 测试数据模型一致性
    results.append(("数据模型一致性", test_data_model_consistency()))
    
    # 测试通知服务
    results.append(("通知服务", test_notification_service()))
    
    # 测试通知参数完整流程
    results.append(("通知参数完整流程", test_notification_parameters_flow()))
    
    # 输出测试结果
    logger.info("\n=== 测试结果汇总 ===")
    all_passed = True
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        logger.info("\n🎉 所有测试通过！")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查日志")
        return 1

if __name__ == "__main__":
    sys.exit(main())