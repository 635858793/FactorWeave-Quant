"""
安全服务
"""

from sqlalchemy.orm import Session
from typing import List, Tuple, Optional
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.models.security import IPWhitelist, IPBlacklist, SecurityAuditLog
from web.backend.schemas.security import SecurityConfigUpdate, IPWhitelistCreate, IPBlacklistCreate
from web.backend.config.security import security_config


class SecurityService:
    """
    安全服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_security_config(self):
        """
        获取安全配置
        """
        return security_config
    
    def update_security_config(self, config: SecurityConfigUpdate):
        """
        更新安全配置
        """
        if config.ip_whitelist_enabled is not None:
            security_config.ip_whitelist_enabled = config.ip_whitelist_enabled
        
        if config.ip_blacklist_enabled is not None:
            security_config.ip_blacklist_enabled = config.ip_blacklist_enabled
        
        if config.request_signature_enabled is not None:
            security_config.request_signature_enabled = config.request_signature_enabled
        
        if config.https_force is not None:
            security_config.https_force = config.https_force
        
        if config.hsts_max_age is not None:
            security_config.hsts_max_age = config.hsts_max_age
        
        return security_config
    
    def get_ip_whitelist(
        self,
        page: int = 1,
        page_size: int = 20,
        ip_address: str = None,
        description: str = None,
        is_active: bool = None
    ) -> Tuple[List[IPWhitelist], int]:
        """
        获取IP白名单
        """
        query = self.db.query(IPWhitelist)
        
        if ip_address:
            query = query.filter(IPWhitelist.ip_address.like(f"%{ip_address}%"))
        
        if description:
            query = query.filter(IPWhitelist.description.like(f"%{description}%"))
        
        if is_active is not None:
            query = query.filter(IPWhitelist.is_active == is_active)
        
        total = query.count()
        
        whitelist = query.order_by(IPWhitelist.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return whitelist, total
    
    def add_ip_whitelist(self, ip_whitelist: IPWhitelistCreate) -> IPWhitelist:
        """
        添加IP白名单
        """
        whitelist = IPWhitelist(
            ip_address=ip_whitelist.ip_address,
            ip_range=ip_whitelist.ip_range,
            description=ip_whitelist.description,
            is_active=True
        )
        
        self.db.add(whitelist)
        self.db.commit()
        self.db.refresh(whitelist)
        
        return whitelist
    
    def remove_ip_whitelist(self, whitelist_id: int) -> bool:
        """
        移除IP白名单
        """
        whitelist = self.db.query(IPWhitelist).filter(IPWhitelist.id == whitelist_id).first()
        
        if not whitelist:
            return False
        
        self.db.delete(whitelist)
        self.db.commit()
        
        return True
    
    def get_ip_blacklist(
        self,
        page: int = 1,
        page_size: int = 20,
        ip_address: str = None,
        description: str = None,
        is_active: bool = None
    ) -> Tuple[List[IPBlacklist], int]:
        """
        获取IP黑名单
        """
        query = self.db.query(IPBlacklist)
        
        if ip_address:
            query = query.filter(IPBlacklist.ip_address.like(f"%{ip_address}%"))
        
        if description:
            query = query.filter(IPBlacklist.description.like(f"%{description}%"))
        
        if is_active is not None:
            query = query.filter(IPBlacklist.is_active == is_active)
        
        total = query.count()
        
        blacklist = query.order_by(IPBlacklist.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return blacklist, total
    
    def add_ip_blacklist(self, ip_blacklist: IPBlacklistCreate) -> IPBlacklist:
        """
        添加IP黑名单
        """
        blacklist = IPBlacklist(
            ip_address=ip_blacklist.ip_address,
            ip_range=ip_blacklist.ip_range,
            description=ip_blacklist.description,
            reason=ip_blacklist.reason,
            is_active=True
        )
        
        self.db.add(blacklist)
        self.db.commit()
        self.db.refresh(blacklist)
        
        return blacklist
    
    def remove_ip_blacklist(self, blacklist_id: int) -> bool:
        """
        移除IP黑名单
        """
        blacklist = self.db.query(IPBlacklist).filter(IPBlacklist.id == blacklist_id).first()
        
        if not blacklist:
            return False
        
        self.db.delete(blacklist)
        self.db.commit()
        
        return True
    
    def get_audit_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: int = None,
        action: str = None,
        resource_type: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> Tuple[List[SecurityAuditLog], int]:
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
    
    def export_audit_logs(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        format: str = "csv"
    ) -> Optional[str]:
        """
        导出审计日志
        """
        from datetime import datetime
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
    
    def security_scan(self, scan_type: str = "full") -> Dict[str, Any]:
        """
        安全扫描
        """
        results = {
            "scan_type": scan_type,
            "scan_time": datetime.now().isoformat(),
            "vulnerabilities": [],
            "warnings": [],
            "info": []
        }
        
        if scan_type in ["full", "sql_injection"]:
            sql_injection_results = self._scan_sql_injection()
            results["vulnerabilities"].extend(sql_injection_results)
        
        if scan_type in ["full", "xss"]:
            xss_results = self._scan_xss()
            results["vulnerabilities"].extend(xss_results)
        
        if scan_type in ["full", "csrf"]:
            csrf_results = self._scan_csrf()
            results["warnings"].extend(csrf_results)
        
        if scan_type in ["full", "file_upload"]:
            file_upload_results = self._scan_file_upload()
            results["warnings"].extend(file_upload_results)
        
        if scan_type in ["full", "command_injection"]:
            command_injection_results = self._scan_command_injection()
            results["vulnerabilities"].extend(command_injection_results)
        
        if scan_type in ["full", "path_traversal"]:
            path_traversal_results = self._scan_path_traversal()
            results["vulnerabilities"].extend(path_traversal_results)
        
        results["total_vulnerabilities"] = len(results["vulnerabilities"])
        results["total_warnings"] = len(results["warnings"])
        results["total_info"] = len(results["info"])
        
        return results
    
    def get_security_summary(self) -> Dict[str, Any]:
        """
        获取安全摘要
        """
        total_users = self.db.query(self.db.query(IPWhitelist).count()).scalar()
        total_whitelist = self.db.query(IPWhitelist).filter(IPWhitelist.is_active == True).count()
        total_blacklist = self.db.query(IPBlacklist).filter(IPBlacklist.is_active == True).count()
        total_audit_logs = self.db.query(SecurityAuditLog).count()
        
        recent_logs = self.db.query(SecurityAuditLog).filter(
            SecurityAuditLog.created_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        failed_logins = self.db.query(SecurityAuditLog).filter(
            SecurityAuditLog.action == "login",
            SecurityAuditLog.success == False
        ).count()
        
        return {
            "total_whitelist": total_whitelist,
            "total_blacklist": total_blacklist,
            "total_audit_logs": total_audit_logs,
            "recent_audit_logs": recent_logs,
            "failed_logins": failed_logins,
            "security_level": self._calculate_security_level()
        }
    
    def _scan_sql_injection(self) -> List[Dict[str, Any]]:
        """
        扫描SQL注入漏洞
        """
        vulnerabilities = []
        
        if not security_config.SQL_INJECTION_ENABLED:
            vulnerabilities.append({
                "type": "SQL Injection",
                "severity": "high",
                "message": "SQL注入防护未启用"
            })
        
        return vulnerabilities
    
    def _scan_xss(self) -> List[Dict[str, Any]]:
        """
        扫描XSS漏洞
        """
        vulnerabilities = []
        
        if not security_config.XSS_ENABLED:
            vulnerabilities.append({
                "type": "XSS",
                "severity": "high",
                "message": "XSS防护未启用"
            })
        
        return vulnerabilities
    
    def _scan_csrf(self) -> List[Dict[str, Any]]:
        """
        扫描CSRF漏洞
        """
        warnings = []
        
        if not security_config.CSRF_ENABLED:
            warnings.append({
                "type": "CSRF",
                "severity": "medium",
                "message": "CSRF防护未启用"
            })
        
        return warnings
    
    def _scan_file_upload(self) -> List[Dict[str, Any]]:
        """
        扫描文件上传漏洞
        """
        warnings = []
        
        if not security_config.FILE_UPLOAD_ENABLED:
            warnings.append({
                "type": "File Upload",
                "severity": "medium",
                "message": "文件上传安全检查未启用"
            })
        
        return warnings
    
    def _scan_command_injection(self) -> List[Dict[str, Any]]:
        """
        扫描命令注入漏洞
        """
        vulnerabilities = []
        
        if not security_config.COMMAND_INJECTION_ENABLED:
            vulnerabilities.append({
                "type": "Command Injection",
                "severity": "high",
                "message": "命令注入防护未启用"
            })
        
        return vulnerabilities
    
    def _scan_path_traversal(self) -> List[Dict[str, Any]]:
        """
        扫描路径遍历漏洞
        """
        vulnerabilities = []
        
        if not security_config.PATH_TRAVERSAL_ENABLED:
            vulnerabilities.append({
                "type": "Path Traversal",
                "severity": "high",
                "message": "路径遍历防护未启用"
            })
        
        return vulnerabilities
    
    def _calculate_security_level(self) -> str:
        """
        计算安全等级
        """
        score = 100
        
        if not security_config.SQL_INJECTION_ENABLED:
            score -= 20
        
        if not security_config.XSS_ENABLED:
            score -= 20
        
        if not security_config.CSRF_ENABLED:
            score -= 10
        
        if not security_config.FILE_UPLOAD_ENABLED:
            score -= 10
        
        if not security_config.COMMAND_INJECTION_ENABLED:
            score -= 20
        
        if not security_config.PATH_TRAVERSAL_ENABLED:
            score -= 20
        
        if score >= 80:
            return "high"
        elif score >= 60:
            return "medium"
        else:
            return "low"
