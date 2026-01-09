"""
通知服务
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import sys
import os
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.models.notification import Notification, NotificationPreference
from web.backend.models.user import User
from web.backend.schemas.notification import (
    NotificationCreate, NotificationResponse, NotificationListResponse,
    NotificationPreferenceCreate, NotificationPreferenceResponse,
    NotificationStatsResponse
)
from web.backend.config.settings import settings


class NotificationService:
    """
    通知服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def send_notification(self, notification_data: NotificationCreate) -> Notification:
        """
        创建并发送通知
        """
        notification = Notification(
            user_id=notification_data.user_id,
            title=notification_data.title,
            content=notification_data.content,
            type=notification_data.type,
            channels=notification_data.channels or ["in_app"],
            status="pending"
        )
        
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        
        # 异步发送通知
        self._send_notification_async(notification, notification_data.channels)
        
        return notification
    
    def _send_notification_async(self, notification: Notification, channels: List[str]):
        """
        异步发送通知
        """
        try:
            # 尝试获取运行中的事件循环
            loop = asyncio.get_running_loop()
            
            async def send():
                success = True
                
                if "email" in channels:
                    email_success = await self._send_email_notification(notification)
                    success = success and email_success
                
                if "sms" in channels:
                    sms_success = await self._send_sms_notification(notification)
                    success = success and sms_success
                
                if "in_app" in channels:
                    in_app_success = await self._send_in_app_notification(notification)
                    success = success and in_app_success
                
                # 使用新的数据库会话更新状态
                from web.backend.config.database import SessionLocal
                new_db = SessionLocal()
                try:
                    db_notification = new_db.query(Notification).filter(Notification.id == notification.id).first()
                    if db_notification:
                        db_notification.status = "sent" if success else "failed"
                        db_notification.sent_at = datetime.now()
                        new_db.commit()
                finally:
                    new_db.close()
            
            asyncio.create_task(send())
        except RuntimeError:
            # 如果没有运行中的事件循环，使用同步方式
            import threading
            
            def send_sync():
                success = True
                
                try:
                    if "email" in channels:
                        email_success = self._send_email_notification_sync(notification)
                        success = success and email_success
                    
                    if "sms" in channels:
                        sms_success = self._send_sms_notification_sync(notification)
                        success = success and sms_success
                    
                    if "in_app" in channels:
                        in_app_success = self._send_in_app_notification_sync(notification)
                        success = success and in_app_success
                    
                    # 使用新的数据库会话更新状态
                    from web.backend.config.database import SessionLocal
                    new_db = SessionLocal()
                    try:
                        db_notification = new_db.query(Notification).filter(Notification.id == notification.id).first()
                        if db_notification:
                            db_notification.status = "sent" if success else "failed"
                            db_notification.sent_at = datetime.now()
                            new_db.commit()
                    finally:
                        new_db.close()
                except Exception as e:
                    print(f"发送通知失败: {e}")
                    # 使用新的数据库会话更新失败状态
                    from web.backend.config.database import SessionLocal
                    new_db = SessionLocal()
                    try:
                        db_notification = new_db.query(Notification).filter(Notification.id == notification.id).first()
                        if db_notification:
                            db_notification.status = "failed"
                            new_db.commit()
                    finally:
                        new_db.close()
            
            thread = threading.Thread(target=send_sync)
            thread.start()
    
    def _send_email_notification_sync(self, notification: Notification) -> bool:
        """
        同步发送邮件通知
        """
        try:
            user = self.db.query(User).filter(User.id == notification.user_id).first()
            if not user or not user.email:
                return False
            
            preference = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == notification.user_id
            ).first()
            
            if preference and not preference.email_enabled:
                return False
            
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USERNAME
            msg['To'] = user.email
            msg['Subject'] = notification.title
            
            body = notification.content
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"发送邮件通知失败: {e}")
            return False
    
    def _send_sms_notification_sync(self, notification: Notification) -> bool:
        """
        同步发送短信通知
        """
        try:
            user = self.db.query(User).filter(User.id == notification.user_id).first()
            if not user or not user.phone:
                return False
            
            preference = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == notification.user_id
            ).first()
            
            if preference and not preference.sms_enabled:
                return False
            
            print(f"发送短信通知到 {user.phone}: {notification.content}")
            return True
        except Exception as e:
            print(f"发送短信通知失败: {e}")
            return False
    
    def _send_in_app_notification_sync(self, notification: Notification) -> bool:
        """
        同步发送应用内通知
        """
        try:
            print(f"发送应用内通知: {notification.title}")
            return True
        except Exception as e:
            print(f"发送应用内通知失败: {e}")
            return False
    
    async def _send_email_notification(self, notification: Notification) -> bool:
        """
        发送邮件通知
        """
        try:
            user = self.db.query(User).filter(User.id == notification.user_id).first()
            if not user or not user.email:
                return False
            
            # 检查用户是否启用了邮件通知
            preference = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == notification.user_id
            ).first()
            
            if preference and not preference.email_enabled:
                return False
            
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USERNAME
            msg['To'] = user.email
            msg['Subject'] = notification.title
            
            body = notification.content
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"发送邮件通知失败: {e}")
            return False
    
    async def _send_sms_notification(self, notification: Notification) -> bool:
        """
        发送短信通知
        """
        try:
            user = self.db.query(User).filter(User.id == notification.user_id).first()
            if not user or not user.phone:
                return False
            
            # 检查用户是否启用了短信通知
            preference = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == notification.user_id
            ).first()
            
            if preference and not preference.sms_enabled:
                return False
            
            # 这里集成短信服务提供商API
            # 例如：阿里云短信、腾讯云短信等
            # 示例代码：
            # sms_client = SmsClient(api_key=settings.SMS_API_KEY)
            # result = sms_client.send(user.phone, notification.content)
            # return result.success
            
            print(f"发送短信通知到 {user.phone}: {notification.content}")
            return True
        except Exception as e:
            print(f"发送短信通知失败: {e}")
            return False
    
    async def _send_in_app_notification(self, notification: Notification) -> bool:
        """
        发送应用内通知
        """
        try:
            # 应用内通知已经在数据库中创建，这里可以触发WebSocket推送
            from web.backend.websocket_manager import websocket_manager
            
            # 通过WebSocket推送通知
            await websocket_manager.send_notification(
                notification.user_id,
                {
                    "id": notification.id,
                    "title": notification.title,
                    "content": notification.content,
                    "type": notification.type,
                    "created_at": notification.created_at.isoformat()
                }
            )
            
            return True
        except Exception as e:
            print(f"发送应用内通知失败: {e}")
            return False
    
    def send_bulk_notification(
        self,
        user_ids: List[int],
        title: str,
        content: str,
        notification_type: str = "info",
        channels: Optional[List[str]] = None
    ) -> int:
        """
        批量发送通知
        """
        success_count = 0
        
        for user_id in user_ids:
            notification_data = NotificationCreate(
                user_id=user_id,
                title=title,
                content=content,
                type=notification_type,
                channels=channels or ["in_app"]
            )
            
            notification = self.send_notification(notification_data)
            if notification:
                success_count += 1
        
        return success_count
    
    def get_notifications(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        is_read: Optional[bool] = None,
        notification_type: Optional[str] = None
    ) -> tuple:
        """
        获取通知列表
        """
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        
        if is_read is not None:
            query = query.filter(Notification.read == is_read)
        
        if notification_type:
            query = query.filter(Notification.type == notification_type)
        
        total = query.count()
        notifications = query.order_by(Notification.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        unread_count = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.read == False
        ).count()
        
        return notifications, total, unread_count
    
    def get_notification_by_id(self, notification_id: int) -> Optional[Notification]:
        """
        根据ID获取通知
        """
        return self.db.query(Notification).filter(Notification.id == notification_id).first()
    
    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """
        标记为已读
        """
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if not notification:
            return False
        
        notification.read = True
        notification.read_at = datetime.now()
        self.db.commit()
        
        return True
    
    def mark_all_as_read(self, user_id: int) -> int:
        """
        标记所有为已读
        """
        notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.read == False
        ).all()
        
        for notification in notifications:
            notification.read = True
            notification.read_at = datetime.now()
        
        self.db.commit()
        
        return len(notifications)
    
    def delete_notification(self, notification_id: int, user_id: int) -> bool:
        """
        删除通知
        """
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if not notification:
            return False
        
        self.db.delete(notification)
        self.db.commit()
        
        return True
    
    def delete_all_notifications(self, user_id: int) -> int:
        """
        删除所有通知
        """
        notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id
        ).all()
        
        count = len(notifications)
        
        for notification in notifications:
            self.db.delete(notification)
        
        self.db.commit()
        
        return count
    
    def get_notification_stats(self, user_id: int) -> dict:
        """
        获取通知统计
        """
        total = self.db.query(Notification).filter(Notification.user_id == user_id).count()
        unread = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.read == False
        ).count()
        read = total - unread
        
        # 按类型统计
        type_stats = {}
        for type_name in ["info", "warning", "error", "success"]:
            count = self.db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.type == type_name
            ).count()
            type_stats[type_name] = count
        
        # 最近通知
        recent_notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id
        ).order_by(Notification.created_at.desc()).limit(5).all()
        
        return {
            "total": total,
            "unread": unread,
            "read": read,
            "by_type": type_stats,
            "recent_notifications": recent_notifications
        }
    
    def get_user_preferences(self, user_id: int) -> Optional[NotificationPreference]:
        """
        获取用户通知偏好设置
        """
        return self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
    
    def update_user_preferences(
        self,
        user_id: int,
        preferences: NotificationPreferenceCreate
    ) -> NotificationPreference:
        """
        更新用户通知偏好设置
        """
        preference = self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
        
        if not preference:
            preference = NotificationPreference(user_id=user_id)
            self.db.add(preference)
        
        if preferences.email_enabled is not None:
            preference.email_enabled = preferences.email_enabled
        if preferences.sms_enabled is not None:
            preference.sms_enabled = preferences.sms_enabled
        if preferences.in_app_enabled is not None:
            preference.in_app_enabled = preferences.in_app_enabled
        if preferences.order_notifications is not None:
            preference.order_notifications = preferences.order_notifications
        if preferences.account_notifications is not None:
            preference.account_notifications = preferences.account_notifications
        if preferences.system_notifications is not None:
            preference.system_notifications = preferences.system_notifications
        if preferences.security_notifications is not None:
            preference.security_notifications = preferences.security_notifications
        
        self.db.commit()
        self.db.refresh(preference)
        
        return preference
    
    def send_order_notification(
        self,
        user_id: int,
        order_id: str,
        order_status: str,
        message: str
    ) -> bool:
        """
        发送订单通知
        """
        preference = self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
        
        if preference and not preference.order_notifications:
            return False
        
        notification_data = NotificationCreate(
            user_id=user_id,
            title=f"订单通知 - {order_id}",
            content=message,
            type="info",
            channels=["in_app"]
        )
        
        if preference and preference.email_enabled:
            notification_data.channels.append("email")
        
        if preference and preference.sms_enabled:
            notification_data.channels.append("sms")
        
        notification = self.send_notification(notification_data)
        return notification is not None
    
    def send_account_notification(
        self,
        user_id: int,
        account_id: str,
        message: str,
        notification_type: str = "info"
    ) -> bool:
        """
        发送账户通知
        """
        preference = self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
        
        if preference and not preference.account_notifications:
            return False
        
        notification_data = NotificationCreate(
            user_id=user_id,
            title=f"账户通知 - {account_id}",
            content=message,
            type=notification_type,
            channels=["in_app"]
        )
        
        if preference and preference.email_enabled:
            notification_data.channels.append("email")
        
        if preference and preference.sms_enabled:
            notification_data.channels.append("sms")
        
        notification = self.send_notification(notification_data)
        return notification is not None
    
    def send_security_notification(
        self,
        user_id: int,
        message: str,
        notification_type: str = "warning"
    ) -> bool:
        """
        发送安全通知
        """
        preference = self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).first()
        
        if preference and not preference.security_notifications:
            return False
        
        notification_data = NotificationCreate(
            user_id=user_id,
            title="安全通知",
            content=message,
            type=notification_type,
            channels=["in_app"]
        )
        
        if preference and preference.email_enabled:
            notification_data.channels.append("email")
        
        if preference and preference.sms_enabled:
            notification_data.channels.append("sms")
        
        notification = self.send_notification(notification_data)
        return notification is not None
