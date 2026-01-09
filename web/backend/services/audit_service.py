"""
审计服务
"""

from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.models.security import SecurityAuditLog


class AuditService:
    """
    审计服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_audit_log(
        self,
        user_id: Optional[int],
        username: Optional[str],
        action: str,
        resource_type: Optional[str],
        resource_id: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        request_method: Optional[str],
        request_path: Optional[str],
        request_params: Optional[str],
        response_status: Optional[int],
        response_time: Optional[int],
        success: Optional[bool],
        error_message: Optional[str]
    ) -> SecurityAuditLog:
        """
        创建审计日志
        """
        audit_log = SecurityAuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            request_params=request_params,
            response_status=response_status,
            response_time=response_time,
            success=success,
            error_message=error_message,
            created_at=datetime.now()
        )
        
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        
        return audit_log
    
    def get_audit_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> tuple:
        """
        获取审计日志
        """
        query = self.db.query(SecurityAuditLog)
        
        if user_id:
            query = query.filter(SecurityAuditLog.user_id == user_id)
        
        if action:
            query = query.filter(SecurityAuditLog.action == action)
        
        if resource_type:
            query = query.filter(SecurityAuditLog.resource_type == resource_type)
        
        if start_time:
            query = query.filter(SecurityAuditLog.created_at >= start_time)
        
        if end_time:
            query = query.filter(SecurityAuditLog.created_at <= end_time)
        
        total = query.count()
        
        logs = query.order_by(SecurityAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return logs, total
    
    def get_audit_log_by_id(self, log_id: int) -> Optional[SecurityAuditLog]:
        """
        获取审计日志详情
        """
        return self.db.query(SecurityAuditLog).filter(SecurityAuditLog.id == log_id).first()
    
    def get_audit_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        获取审计摘要
        """
        start_time = datetime.now() - timedelta(days=days)
        
        query = """
            SELECT 
                action,
                COUNT(*) as count,
                SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_count
            FROM security_audit_logs 
            WHERE created_at >= :start_time
            GROUP BY action
        """
        
        stats = self.db.execute(text(query), {"start_time": start_time}).fetchall()
        
        return {
            "period": f"{days}天",
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "action_stats": [
                {
                    "action": stat.action,
                    "count": stat.count,
                    "success_count": stat.success_count,
                    "failed_count": stat.failed_count,
                    "success_rate": round(stat.success_count / stat.count * 100, 2) if stat.count > 0 else 0
                } for stat in stats
            ],
            "total_operations": sum(stat.count for stat in stats),
            "total_success": sum(stat.success_count for stat in stats),
            "total_failed": sum(stat.failed_count for stat in stats),
            "overall_success_rate": round(sum(stat.success_count for stat in stats) / sum(stat.count for stat in stats) * 100, 2) if sum(stat.count for stat in stats) > 0 else 0
        }
    
    def get_user_activity(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        获取用户活动统计
        """
        start_time = datetime.now() - timedelta(days=days)
        
        query = """
            SELECT 
                action,
                COUNT(*) as count,
                COUNT(DISTINCT DATE(created_at)) as active_days
            FROM security_audit_logs 
            WHERE user_id = :user_id AND created_at >= :start_time
            GROUP BY action
        """
        
        stats = self.db.execute(text(query), {"user_id": user_id, "start_time": start_time}).fetchall()
        
        total_actions = self.db.query(SecurityAuditLog).filter(
            SecurityAuditLog.user_id == user_id,
            SecurityAuditLog.created_at >= start_time
        ).count()
        
        unique_ips = self.db.query(SecurityAuditLog.ip_address).filter(
            SecurityAuditLog.user_id == user_id,
            SecurityAuditLog.created_at >= start_time
        ).distinct().count()
        
        return {
            "user_id": user_id,
            "period": f"{days}天",
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "total_actions": total_actions,
            "unique_ips": unique_ips,
            "action_stats": [
                {
                    "action": stat.action,
                    "count": stat.count,
                    "active_days": stat.active_days
                } for stat in stats
            ]
        }
    
    def get_resource_activity(self, resource_type: str, days: int = 30) -> Dict[str, Any]:
        """
        获取资源活动统计
        """
        start_time = datetime.now() - timedelta(days=days)
        
        query = """
            SELECT 
                action,
                COUNT(*) as count,
                SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_count
            FROM security_audit_logs 
            WHERE resource_type = :resource_type AND created_at >= :start_time
            GROUP BY action
        """
        
        stats = self.db.execute(text(query), {"resource_type": resource_type, "start_time": start_time}).fetchall()
        
        total_actions = self.db.query(SecurityAuditLog).filter(
            SecurityAuditLog.resource_type == resource_type,
            SecurityAuditLog.created_at >= start_time
        ).count()
        
        return {
            "resource_type": resource_type,
            "period": f"{days}天",
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "total_actions": total_actions,
            "action_stats": [
                {
                    "action": stat.action,
                    "count": stat.count,
                    "success_count": stat.success_count,
                    "failed_count": stat.failed_count,
                    "success_rate": round(stat.success_count / stat.count * 100, 2) if stat.count > 0 else 0
                } for stat in stats
            ]
        }
    
    def get_security_events(self, days: int = 7) -> Dict[str, Any]:
        """
        获取安全事件
        """
        start_time = datetime.now() - timedelta(days=days)
        
        failed_logins = self.db.query(SecurityAuditLog).filter(
            SecurityAuditLog.action == "login",
            SecurityAuditLog.success == False,
            SecurityAuditLog.created_at >= start_time
        ).count()
        
        unauthorized_access = self.db.query(SecurityAuditLog).filter(
            SecurityAuditLog.response_status == 403,
            SecurityAuditLog.created_at >= start_time
        ).count()
        
        errors = self.db.query(SecurityAuditLog).filter(
            SecurityAuditLog.success == False,
            SecurityAuditLog.created_at >= start_time
        ).count()
        
        suspicious_ips = self.db.execute(text("""
            SELECT ip_address, COUNT(*) as count
            FROM security_audit_logs
            WHERE success = false AND created_at >= :start_time
            GROUP BY ip_address
            HAVING count >= 5
            ORDER BY count DESC
            LIMIT 10
        """), {"start_time": start_time}).fetchall()
        
        return {
            "period": f"{days}天",
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "failed_logins": failed_logins,
            "unauthorized_access": unauthorized_access,
            "errors": errors,
            "suspicious_ips": [
                {
                    "ip_address": ip.ip_address,
                    "failed_attempts": ip.count
                } for ip in suspicious_ips
            ]
        }
    
    def get_trend_data(self, days: int = 30) -> Dict[str, Any]:
        """
        获取趋势数据
        """
        start_time = datetime.now() - timedelta(days=days)
        
        query = """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total,
                SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed
            FROM security_audit_logs 
            WHERE created_at >= :start_time
            GROUP BY DATE(created_at)
            ORDER BY date
        """
        
        stats = self.db.execute(text(query), {"start_time": start_time}).fetchall()
        
        return {
            "period": f"{days}天",
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "trend": [
                {
                    "date": stat.date,
                    "total": stat.total,
                    "success": stat.success,
                    "failed": stat.failed
                } for stat in stats
            ]
        }
    
    def export_audit_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "csv"
    ) -> Optional[str]:
        """
        导出审计日志
        """
        import os
        import csv
        
        logs, _ = self.get_audit_logs(
            page=1,
            page_size=100000,
            start_time=start_time,
            end_time=end_time
        )
        
        export_dir = "data/exports"
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(export_dir, f"audit_logs_{timestamp}.{format}")
        
        try:
            if format == "csv":
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "ID", "User ID", "Username", "Action", "Resource Type",
                        "Resource ID", "IP Address", "User Agent", "Request Method",
                        "Request Path", "Request Params", "Response Status",
                        "Response Time", "Success", "Error Message", "Created At"
                    ])
                    
                    for log in logs:
                        writer.writerow([
                            log.id,
                            log.user_id,
                            log.username,
                            log.action,
                            log.resource_type,
                            log.resource_id,
                            log.ip_address,
                            log.user_agent,
                            log.request_method,
                            log.request_path,
                            log.request_params,
                            log.response_status,
                            log.response_time,
                            log.success,
                            log.error_message,
                            log.created_at
                        ])
                
                return file_path
            
            return None
        
        except Exception as e:
            print(f"导出审计日志失败: {e}")
            return None
    
    def delete_old_logs(self, days: int = 90) -> int:
        """
        删除旧日志
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        
        deleted = self.db.query(SecurityAuditLog).filter(
            SecurityAuditLog.created_at < cutoff_time
        ).delete()
        
        self.db.commit()
        
        return deleted
