"""
测试通知和审计服务
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend.config.database import get_db, init_db
from web.backend.services.notification_service import NotificationService
from web.backend.services.audit_service import AuditService
from web.backend.schemas.notification import (
    NotificationCreate, NotificationPreferenceCreate
)


def test_notification_service():
    """
    测试通知服务
    """
    print("=== 测试通知服务 ===")
    
    db = next(get_db())
    notification_service = NotificationService(db)
    
    try:
        # 创建测试通知
        notification_data = NotificationCreate(
            user_id=1,
            title="测试通知",
            content="这是一条测试通知",
            type="info",
            channels=["in_app"]
        )
        
        notification = notification_service.send_notification(notification_data)
        print(f"✓ 创建通知成功: ID={notification.id}")
        
        # 获取通知列表
        notifications, total, unread_count = notification_service.get_notifications(
            user_id=1,
            page=1,
            page_size=10
        )
        print(f"✓ 获取通知列表: 总数={total}, 未读={unread_count}")
        
        # 获取通知统计
        stats = notification_service.get_notification_stats(user_id=1)
        print(f"✓ 获取通知统计: 总数={stats['total']}, 未读={stats['unread']}")
        
        # 标记为已读
        success = notification_service.mark_as_read(notification.id, user_id=1)
        print(f"✓ 标记为已读: {success}")
        
        # 更新通知偏好设置
        preference_data = NotificationPreferenceCreate(
            email_enabled=True,
            sms_enabled=False,
            in_app_enabled=True,
            order_notifications=True,
            account_notifications=True,
            system_notifications=True,
            security_notifications=True
        )
        
        preference = notification_service.update_user_preferences(user_id=1, preferences=preference_data)
        print(f"✓ 更新通知偏好设置成功")
        
        # 测试订单通知
        order_success = notification_service.send_order_notification(
            user_id=1,
            order_id="TEST001",
            order_status="filled",
            message="订单TEST001已成交"
        )
        print(f"✓ 发送订单通知: {order_success}")
        
        # 测试账户通知
        account_success = notification_service.send_account_notification(
            user_id=1,
            account_id="ACC001",
            message="账户ACC001余额变动",
            notification_type="warning"
        )
        print(f"✓ 发送账户通知: {account_success}")
        
        # 测试安全通知
        security_success = notification_service.send_security_notification(
            user_id=1,
            message="检测到异常登录",
            notification_type="error"
        )
        print(f"✓ 发送安全通知: {security_success}")
        
        print("\n✓ 通知服务测试通过\n")
        
    except Exception as e:
        print(f"\n✗ 通知服务测试失败: {e}\n")
        raise
    finally:
        db.close()


def test_audit_service():
    """
    测试审计服务
    """
    print("=== 测试审计服务 ===")
    
    db = next(get_db())
    audit_service = AuditService(db)
    
    try:
        # 创建审计日志
        audit_log = audit_service.create_audit_log(
            user_id=1,
            username="test_user",
            action="login",
            resource_type="user",
            resource_id="1",
            ip_address="127.0.0.1",
            user_agent="Test Agent",
            request_method="POST",
            request_path="/api/v1/auth/login",
            request_params='{"username":"test"}',
            response_status=200,
            response_time=100,
            success=True,
            error_message=None
        )
        print(f"✓ 创建审计日志成功: ID={audit_log.id}")
        
        # 获取审计日志列表
        logs, total = audit_service.get_audit_logs(
            page=1,
            page_size=10
        )
        print(f"✓ 获取审计日志列表: 总数={total}")
        
        # 获取审计摘要
        summary = audit_service.get_audit_summary(days=30)
        print(f"✓ 获取审计摘要: 操作数={summary['total_operations']}, 成功率={summary['overall_success_rate']}%")
        
        # 获取用户活动统计
        user_activity = audit_service.get_user_activity(user_id=1, days=30)
        print(f"✓ 获取用户活动统计: 总操作数={user_activity['total_actions']}, 唯一IP数={user_activity['unique_ips']}")
        
        # 获取资源活动统计
        resource_activity = audit_service.get_resource_activity(resource_type="order", days=30)
        print(f"✓ 获取资源活动统计: 资源类型={resource_activity['resource_type']}, 操作数={resource_activity['total_actions']}")
        
        # 获取安全事件
        security_events = audit_service.get_security_events(days=7)
        print(f"✓ 获取安全事件: 失败登录={security_events['failed_logins']}, 未授权访问={security_events['unauthorized_access']}")
        
        # 获取趋势数据
        trend_data = audit_service.get_trend_data(days=30)
        print(f"✓ 获取趋势数据: 趋势点数={len(trend_data['trend'])}")
        
        # 导出审计日志
        export_path = audit_service.export_audit_logs(format="csv")
        if export_path:
            print(f"✓ 导出审计日志成功: {export_path}")
        
        print("\n✓ 审计服务测试通过\n")
        
    except Exception as e:
        print(f"\n✗ 审计服务测试失败: {e}\n")
        raise
    finally:
        db.close()


def test_integration():
    """
    测试集成功能
    """
    print("=== 测试集成功能 ===")
    
    db = next(get_db())
    notification_service = NotificationService(db)
    audit_service = AuditService(db)
    
    try:
        # 模拟用户登录并记录审计日志
        audit_log = audit_service.create_audit_log(
            user_id=1,
            username="test_user",
            action="login",
            resource_type="user",
            resource_id="1",
            ip_address="127.0.0.1",
            user_agent="Test Agent",
            request_method="POST",
            request_path="/api/v1/auth/login",
            request_params='{"username":"test"}',
            response_status=200,
            response_time=100,
            success=True,
            error_message=None
        )
        print(f"✓ 用户登录审计日志记录成功")
        
        # 发送登录成功通知
        notification_data = NotificationCreate(
            user_id=1,
            title="登录成功",
            content="您于" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "成功登录系统",
            type="success",
            channels=["in_app"]
        )
        
        notification = notification_service.send_notification(notification_data)
        print(f"✓ 登录成功通知发送成功")
        
        # 模拟订单操作并记录审计日志
        audit_log = audit_service.create_audit_log(
            user_id=1,
            username="test_user",
            action="create",
            resource_type="order",
            resource_id="TEST002",
            ip_address="127.0.0.1",
            user_agent="Test Agent",
            request_method="POST",
            request_path="/api/v1/orders",
            request_params='{"symbol":"000001","price":10.0,"volume":100}',
            response_status=200,
            response_time=50,
            success=True,
            error_message=None
        )
        print(f"✓ 订单创建审计日志记录成功")
        
        # 使用专用方法发送订单通知
        order_success = notification_service.send_order_notification(
            user_id=1,
            order_id="TEST002",
            order_status="submitted",
            message="订单TEST002已提交"
        )
        print(f"✓ 订单通知发送成功")
        
        # 模拟安全事件并记录审计日志
        audit_log = audit_service.create_audit_log(
            user_id=1,
            username="test_user",
            action="login",
            resource_type="user",
            resource_id="1",
            ip_address="192.168.1.100",
            user_agent="Suspicious Agent",
            request_method="POST",
            request_path="/api/v1/auth/login",
            request_params='{"username":"test"}',
            response_status=401,
            response_time=200,
            success=False,
            error_message="Invalid password"
        )
        print(f"✓ 安全事件审计日志记录成功")
        
        # 使用专用方法发送安全通知
        security_success = notification_service.send_security_notification(
            user_id=1,
            message="检测到来自IP 192.168.1.100的异常登录尝试",
            notification_type="warning"
        )
        print(f"✓ 安全通知发送成功")
        
        # 获取综合统计
        notification_stats = notification_service.get_notification_stats(user_id=1)
        audit_summary = audit_service.get_audit_summary(days=1)
        
        print(f"\n=== 综合统计 ===")
        print(f"通知统计: 总数={notification_stats['total']}, 未读={notification_stats['unread']}")
        print(f"审计统计: 操作数={audit_summary['total_operations']}, 成功率={audit_summary['overall_success_rate']}%")
        
        print("\n✓ 集成功能测试通过\n")
        
    except Exception as e:
        print(f"\n✗ 集成功能测试失败: {e}\n")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("\n开始测试通知和审计服务...\n")
    
    # 初始化数据库
    init_db()
    
    # 测试通知服务
    test_notification_service()
    
    # 测试审计服务
    test_audit_service()
    
    # 测试集成功能
    test_integration()
    
    print("所有测试完成!")
