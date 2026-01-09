"""
系统服务
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
import sys
import os
import platform
import psutil
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.settings import settings


class SystemService:
    """
    系统服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息
        """
        return {
            "system_name": platform.system(),
            "system_version": platform.version(),
            "system_release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "start_time": self._get_start_time(),
            "uptime": self._get_uptime(),
            "pid": os.getpid()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        获取健康状态
        """
        return {
            "status": "healthy",
            "service": "hikyuu-trading-api",
            "version": settings.APP_VERSION,
            "check_time": datetime.now().isoformat()
        }
    
    def get_system_resources(self) -> Dict[str, Any]:
        """
        获取系统资源
        """
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        
        return {
            "cpu_usage": round(cpu_percent, 2),
            "memory_usage": round(memory.percent, 2),
            "memory_total": round(memory.total / (1024 ** 3), 2),
            "memory_used": round(memory.used / (1024 ** 3), 2),
            "memory_available": round(memory.available / (1024 ** 3), 2),
            "disk_usage": round(disk.percent, 2),
            "disk_total": round(disk.total / (1024 ** 3), 2),
            "disk_used": round(disk.used / (1024 ** 3), 2),
            "disk_free": round(disk.free / (1024 ** 3), 2),
            "network_bytes_sent": network.bytes_sent,
            "network_bytes_recv": network.bytes_recv,
            "network_packets_sent": network.packets_sent,
            "network_packets_recv": network.packets_recv
        }
    
    def get_active_connections(self) -> int:
        """
        获取活跃连接数
        """
        try:
            from web.backend.websocket_manager import manager
            return manager.get_active_connections_count()
        except:
            return 0
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取系统配置
        """
        return {
            "debug": settings.DEBUG,
            "log_level": settings.LOG_LEVEL,
            "max_upload_size": settings.UPLOAD_MAX_FILE_SIZE,
            "session_timeout": settings.SESSION_TIMEOUT_MINUTES,
            "rate_limit_per_minute": settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
            "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
            "cors_origins": settings.CORS_ORIGINS,
            "jwt_access_token_expire_minutes": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "jwt_refresh_token_expire_days": settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
            "two_fa_enabled": settings.TWO_FA_ENABLED,
            "account_lock_enabled": settings.ACCOUNT_LOCK_ENABLED,
            "account_lock_max_attempts": settings.ACCOUNT_LOCK_MAX_ATTEMPTS,
            "account_lock_duration_minutes": settings.ACCOUNT_LOCK_DURATION_MINUTES
        }
    
    def update_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新系统配置
        """
        updated_config = {}
        
        if "debug" in config_data:
            settings.DEBUG = config_data["debug"]
            updated_config["debug"] = settings.DEBUG
        
        if "log_level" in config_data:
            settings.LOG_LEVEL = config_data["log_level"]
            updated_config["log_level"] = settings.LOG_LEVEL
        
        if "max_upload_size" in config_data:
            settings.UPLOAD_MAX_FILE_SIZE = config_data["max_upload_size"]
            updated_config["max_upload_size"] = settings.UPLOAD_MAX_FILE_SIZE
        
        if "session_timeout" in config_data:
            settings.SESSION_TIMEOUT_MINUTES = config_data["session_timeout"]
            updated_config["session_timeout"] = settings.SESSION_TIMEOUT_MINUTES
        
        if "rate_limit_per_minute" in config_data:
            settings.RATE_LIMIT_REQUESTS_PER_MINUTE = config_data["rate_limit_per_minute"]
            updated_config["rate_limit_per_minute"] = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        
        if "rate_limit_enabled" in config_data:
            settings.RATE_LIMIT_ENABLED = config_data["rate_limit_enabled"]
            updated_config["rate_limit_enabled"] = settings.RATE_LIMIT_ENABLED
        
        return updated_config
    
    def create_backup(self, backup_type: str = "full", description: str = None) -> Dict[str, Any]:
        """
        创建备份
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = settings.BACKUPS_DIR
        
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, f"backup_{backup_type}_{timestamp}")
        
        try:
            if backup_type == "full":
                self._create_full_backup(backup_path)
            elif backup_type == "incremental":
                self._create_incremental_backup(backup_path)
            
            backup_info = {
                "backup_type": backup_type,
                "backup_path": backup_path,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "size": self._get_backup_size(backup_path)
            }
            
            backup_info_path = os.path.join(backup_path, "backup_info.json")
            with open(backup_info_path, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, indent=2, ensure_ascii=False)
            
            return backup_info
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def restore_backup(self, backup_path: str) -> Dict[str, Any]:
        """
        恢复备份
        """
        try:
            backup_info_path = os.path.join(backup_path, "backup_info.json")
            
            if not os.path.exists(backup_info_path):
                return {
                    "success": False,
                    "error": "备份信息文件不存在"
                }
            
            with open(backup_info_path, 'r', encoding='utf-8') as f:
                backup_info = json.load(f)
            
            self._restore_backup_data(backup_path)
            
            return {
                "success": True,
                "backup_info": backup_info,
                "restored_at": datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_backups(self) -> list:
        """
        获取备份列表
        """
        backup_dir = settings.BACKUPS_DIR
        
        if not os.path.exists(backup_dir):
            return []
        
        backups = []
        
        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)
            
            if os.path.isdir(item_path):
                backup_info_path = os.path.join(item_path, "backup_info.json")
                
                if os.path.exists(backup_info_path):
                    with open(backup_info_path, 'r', encoding='utf-8') as f:
                        backup_info = json.load(f)
                    
                    backups.append(backup_info)
        
        return sorted(backups, key=lambda x: x["created_at"], reverse=True)
    
    def delete_backup(self, backup_path: str) -> bool:
        """
        删除备份
        """
        try:
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
                return True
            return False
        except Exception as e:
            print(f"删除备份失败: {e}")
            return False
    
    def get_logs(self, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """
        获取系统日志
        """
        log_file = settings.LOG_FILE
        
        if not os.path.exists(log_file):
            return {
                "logs": [],
                "total": 0,
                "page": page,
                "page_size": page_size
            }
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_logs = f.readlines()
            
            total = len(all_logs)
            start = (page - 1) * page_size
            end = start + page_size
            
            logs = []
            for i in range(start, min(end, total)):
                log_line = all_logs[i].strip()
                if log_line:
                    logs.append({
                        "line_number": i + 1,
                        "content": log_line
                    })
            
            return {
                "logs": logs,
                "total": total,
                "page": page,
                "page_size": page_size
            }
        
        except Exception as e:
            return {
                "logs": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "error": str(e)
            }
    
    def clear_logs(self) -> bool:
        """
        清除日志
        """
        try:
            log_file = settings.LOG_FILE
            
            if os.path.exists(log_file):
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write('')
                return True
            return False
        except Exception as e:
            print(f"清除日志失败: {e}")
            return False
    
    def export_logs(self, format: str = "txt") -> Optional[str]:
        """
        导出日志
        """
        log_file = settings.LOG_FILE
        
        if not os.path.exists(log_file):
            return None
        
        export_dir = settings.EXPORT_DIR
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(export_dir, f"system_logs_{timestamp}.{format}")
        
        try:
            if format == "txt":
                shutil.copy2(log_file, export_path)
            elif format == "json":
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_lines = f.readlines()
                
                logs_data = []
                for i, line in enumerate(log_lines):
                    logs_data.append({
                        "line_number": i + 1,
                        "content": line.strip()
                    })
                
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(logs_data, f, indent=2, ensure_ascii=False)
            
            return export_path
        
        except Exception as e:
            print(f"导出日志失败: {e}")
            return None
    
    def restart_system(self) -> Dict[str, Any]:
        """
        重启系统
        """
        try:
            import signal
            import os
            
            os.kill(os.getpid(), signal.SIGTERM)
            
            return {
                "success": True,
                "message": "系统重启中",
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """
        获取系统统计
        """
        resources = self.get_system_resources()
        active_connections = self.get_active_connections()
        
        return {
            "resources": resources,
            "active_connections": active_connections,
            "uptime": self._get_uptime(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_start_time(self) -> str:
        """
        获取启动时间
        """
        try:
            return datetime.fromtimestamp(psutil.boot_time()).isoformat()
        except:
            return "unknown"
    
    def _get_uptime(self) -> str:
        """
        获取运行时间
        """
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = datetime.now().timestamp() - boot_time
            
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            return f"{days}天 {hours}小时 {minutes}分钟"
        except:
            return "unknown"
    
    def _create_full_backup(self, backup_path: str):
        """
        创建完整备份
        """
        os.makedirs(backup_path, exist_ok=True)
        
        data_dir = "data"
        if os.path.exists(data_dir):
            shutil.copytree(data_dir, os.path.join(backup_path, "data"))
    
    def _create_incremental_backup(self, backup_path: str):
        """
        创建增量备份
        """
        os.makedirs(backup_path, exist_ok=True)
        
        data_dir = "data/databases"
        if os.path.exists(data_dir):
            shutil.copytree(data_dir, os.path.join(backup_path, "databases"))
    
    def _get_backup_size(self, backup_path: str) -> int:
        """
        获取备份大小
        """
        total_size = 0
        
        for root, dirs, files in os.walk(backup_path):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        
        return total_size
    
    def _restore_backup_data(self, backup_path: str):
        """
        恢复备份数据
        """
        backup_data_path = os.path.join(backup_path, "data")
        
        if os.path.exists(backup_data_path):
            data_dir = "data"
            
            if os.path.exists(data_dir):
                shutil.rmtree(data_dir)
            
            shutil.copytree(backup_data_path, data_dir)
