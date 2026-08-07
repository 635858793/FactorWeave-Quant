from loguru import logger
"""
云端API服务模块

提供云端数据同步、配置管理、任务协调等功能。
"""

import json
import requests
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from urllib.parse import urljoin
import hashlib
import hmac
import base64


@dataclass
class CloudConfig:
    """云端配置"""
    api_url: str
    api_key: str
    secret_key: str
    timeout: int = 30
    retry_count: int = 3
    sync_interval: int = 300  # 5分钟
    enable_ssl: bool = True

    def get_auth_headers(self, method: str, path: str, timestamp: str) -> Dict[str, str]:
        """生成认证头"""
        message = f"{method.upper()}{path}{timestamp}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return {
            'Authorization': f'HMAC-SHA256 {self.api_key}:{signature}',
            'X-Timestamp': timestamp,
            'Content-Type': 'application/json'
        }

@dataclass
class SyncTask:
    """同步任务"""
    task_id: str
    task_type: str  # upload, download, sync
    resource_type: str  # config, data, strategy, indicator
    resource_id: str
    status: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0
    created_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now()

class CloudAPIClient:
    """云端API客户端"""

    def __init__(self, config: CloudConfig):
        """
        初始化云端API客户端

        Args:
            config: 云端配置
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'FactorWeave-Quant /2.0 Cloud Client'
        })

        # 配置SSL验证
        if not config.enable_ssl:
            # R238-NEW-P1-CWE-295 修复 (2026-08-01): 显式告警 + 禁止生产环境禁用 SSL
            # Why: verify=False 时 HMAC 凭据明文传输 (CWE-295, CVSS 5.9), R51 #5 显式记录降级日志
            # Fix: 保留配置兼容测试环境, 但强制显式 warning (不静默) + 环境变量守卫生产环境
            import os as _os
            _env = _os.environ.get('HIKYUU_APP_ENV', 'dev').lower()
            if _env in ('prod', 'production'):
                raise RuntimeError(
                    "cloud_api_service: enable_ssl=False 在生产环境禁用 (CWE-295 拒绝, "
                    "HMAC 凭据明文传输风险). 请配置 enable_ssl=True 或设置 HIKYUU_APP_ENV=dev"
                )
            self.session.verify = False
            logger.warning(
                "[CWE-295 显式降级] cloud_api_service: enable_ssl=False, SSL 验证已禁用, "
                "HMAC 凭据将明文传输. 仅限测试环境, 生产环境必须 enable_ssl=True"
            )

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发送API请求

        Args:
            method: HTTP方法
            endpoint: API端点
            data: 请求数据

        Returns:
            响应数据
        """
        url = urljoin(self.config.api_url, endpoint)
        timestamp = str(int(time.time()))

        # 生成认证头
        headers = self.config.get_auth_headers(method, endpoint, timestamp)

        for attempt in range(self.config.retry_count):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(
                        url, headers=headers, timeout=self.config.timeout)
                elif method.upper() == 'POST':
                    response = self.session.post(
                        url, headers=headers, json=data, timeout=self.config.timeout)
                elif method.upper() == 'PUT':
                    response = self.session.put(
                        url, headers=headers, json=data, timeout=self.config.timeout)
                elif method.upper() == 'DELETE':
                    response = self.session.delete(
                        url, headers=headers, timeout=self.config.timeout)
                else:
                    raise ValueError(f"不支持的HTTP方法: {method}")

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"API请求失败 (尝试 {attempt + 1}/{self.config.retry_count}): {e}")
                if attempt == self.config.retry_count - 1:
                    raise
                time.sleep(2 ** attempt)  # 指数退避

    def upload_config(self, config_data: Dict[str, Any]) -> bool:
        """上传配置"""
        try:
            response = self._make_request(
                'POST', '/api/v1/config', config_data)
            return response.get('success', False)
        except Exception as e:
            logger.error(f"上传配置失败: {e}")
            return False

    def download_config(self) -> Optional[Dict[str, Any]]:
        """下载配置"""
        try:
            response = self._make_request('GET', '/api/v1/config')
            return response.get('data')
        except Exception as e:
            logger.error(f"下载配置失败: {e}")
            return None

    def upload_strategy(self, strategy_data: Dict[str, Any]) -> bool:
        """上传策略"""
        try:
            response = self._make_request(
                'POST', '/api/v1/strategies', strategy_data)
            return response.get('success', False)
        except Exception as e:
            logger.error(f"上传策略失败: {e}")
            return False

    def download_strategies(self) -> List[Dict[str, Any]]:
        """下载策略列表"""
        try:
            response = self._make_request('GET', '/api/v1/strategies')
            return response.get('data', [])
        except Exception as e:
            logger.error(f"下载策略失败: {e}")
            return []

    def upload_indicator(self, indicator_data: Dict[str, Any]) -> bool:
        """上传指标"""
        try:
            response = self._make_request(
                'POST', '/api/v1/indicators', indicator_data)
            return response.get('success', False)
        except Exception as e:
            logger.error(f"上传指标失败: {e}")
            return False

    def download_indicators(self) -> List[Dict[str, Any]]:
        """下载指标列表"""
        try:
            response = self._make_request('GET', '/api/v1/indicators')
            return response.get('data', [])
        except Exception as e:
            logger.error(f"下载指标失败: {e}")
            return []

    def sync_data(self, data_type: str, last_sync: Optional[datetime] = None) -> Dict[str, Any]:
        """同步数据"""
        try:
            params = {'type': data_type}
            if last_sync:
                params['since'] = last_sync.isoformat()

            response = self._make_request('GET', '/api/v1/sync', params)
            return response.get('data', {})
        except Exception as e:
            logger.error(f"同步数据失败: {e}")
            return {}

    def get_server_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        try:
            response = self._make_request('GET', '/api/v1/status')
            return response.get('data', {})
        except Exception as e:
            logger.error(f"获取服务器状态失败: {e}")
            return {}

class CloudSyncManager:
    """云端同步管理器"""

    def __init__(self, config: CloudConfig):
        """
        初始化云端同步管理器

        Args:
            config: 云端配置
        """
        self.config = config
        self.client = CloudAPIClient(config)
        self.sync_tasks: List[SyncTask] = []
        self.running = False
        self.sync_thread = None
        self.last_sync_time = None

        # 回调函数
        self.sync_callbacks: List[Callable] = []

    def add_sync_callback(self, callback: Callable):
        """添加同步回调"""
        self.sync_callbacks.append(callback)

    def start_sync(self):
        """启动自动同步"""
        if self.running:
            return

        self.running = True
        self.sync_thread = threading.Thread(
            target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info("云端同步服务已启动")

    def stop_sync(self):
        """停止自动同步"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=10)
        logger.info("云端同步服务已停止")

    def _sync_loop(self):
        """同步循环"""
        while self.running:
            try:
                # 执行同步任务
                self._execute_sync_tasks()

                # 自动同步
                if self._should_auto_sync():
                    self._auto_sync()

                time.sleep(60)  # 每分钟检查一次

            except Exception as e:
                logger.error(f"同步循环错误: {e}")
                time.sleep(60)

    def _should_auto_sync(self) -> bool:
        """判断是否应该自动同步"""
        if not self.last_sync_time:
            return True

        elapsed = datetime.now() - self.last_sync_time
        return elapsed.total_seconds() >= self.config.sync_interval

    def _auto_sync(self):
        """自动同步"""
        try:
            # 同步配置
            self.sync_config()

            # 同步策略
            self.sync_strategies()

            # 同步指标
            self.sync_indicators()

            self.last_sync_time = datetime.now()
            logger.info("自动同步完成")

        except Exception as e:
            logger.error(f"自动同步失败: {e}")

    def sync_config(self) -> bool:
        """同步配置"""
        try:
            # 下载云端配置
            cloud_config = self.client.download_config()
            if cloud_config:
                # 触发配置更新回调
                for callback in self.sync_callbacks:
                    try:
                        callback('config_updated', cloud_config)
                    except Exception as e:
                        logger.error(f"配置更新回调失败: {e}")

            return True

        except Exception as e:
            logger.error(f"同步配置失败: {e}")
            return False

    def sync_strategies(self) -> bool:
        """同步策略"""
        try:
            # 下载云端策略
            cloud_strategies = self.client.download_strategies()
            if cloud_strategies:
                # 触发策略更新回调
                for callback in self.sync_callbacks:
                    try:
                        callback('strategies_updated', cloud_strategies)
                    except Exception as e:
                        logger.error(f"策略更新回调失败: {e}")

            return True

        except Exception as e:
            logger.error(f"同步策略失败: {e}")
            return False

    def sync_indicators(self) -> bool:
        """同步指标"""
        try:
            # 下载云端指标
            cloud_indicators = self.client.download_indicators()
            if cloud_indicators:
                # 触发指标更新回调
                for callback in self.sync_callbacks:
                    try:
                        callback('indicators_updated', cloud_indicators)
                    except Exception as e:
                        logger.error(f"指标更新回调失败: {e}")

            return True

        except Exception as e:
            logger.error(f"同步指标失败: {e}")
            return False

    def _execute_sync_tasks(self):
        """执行同步任务"""
        pending_tasks = [
            task for task in self.sync_tasks if task.status == "pending"]

        for task in pending_tasks:
            try:
                task.status = "running"
                task.start_time = datetime.now()

                if task.task_type == "upload":
                    self._execute_upload_task(task)
                elif task.task_type == "download":
                    self._execute_download_task(task)
                elif task.task_type == "sync":
                    self._execute_sync_task(task)
                else:
                    raise ValueError(f"不支持的任务类型: {task.task_type}")

                task.status = "completed"
                task.end_time = datetime.now()
                task.progress = 100.0

            except Exception as e:
                logger.error(f"执行同步任务失败: {e}")
                task.status = "failed"
                task.error_message = str(e)
                task.end_time = datetime.now()

    def _execute_upload_task(self, task: SyncTask):
        """执行上传任务"""
        # 这里应该根据resource_type和resource_id获取实际数据
        # 为了演示，使用模拟数据
        data = {
            "id": task.resource_id,
            "type": task.resource_type,
            "data": {"mock": "data"}
        }

        if task.resource_type == "config":
            success = self.client.upload_config(data)
        elif task.resource_type == "strategy":
            success = self.client.upload_strategy(data)
        elif task.resource_type == "indicator":
            success = self.client.upload_indicator(data)
        else:
            raise ValueError(f"不支持的资源类型: {task.resource_type}")

        if not success:
            raise Exception("上传失败")

    def _execute_download_task(self, task: SyncTask):
        """执行下载任务"""
        if task.resource_type == "config":
            data = self.client.download_config()
        elif task.resource_type == "strategies":
            data = self.client.download_strategies()
        elif task.resource_type == "indicators":
            data = self.client.download_indicators()
        else:
            raise ValueError(f"不支持的资源类型: {task.resource_type}")

        if not data:
            raise Exception("下载失败")

        # 触发下载完成回调
        for callback in self.sync_callbacks:
            try:
                callback(f'{task.resource_type}_downloaded', data)
            except Exception as e:
                logger.error(f"下载回调失败: {e}")

    def _execute_sync_task(self, task: SyncTask):
        """执行同步任务"""
        if task.resource_type == "config":
            self.sync_config()
        elif task.resource_type == "strategies":
            self.sync_strategies()
        elif task.resource_type == "indicators":
            self.sync_indicators()
        else:
            raise ValueError(f"不支持的资源类型: {task.resource_type}")

    def submit_upload_task(self, resource_type: str, resource_id: str) -> str:
        """提交上传任务"""
        task = SyncTask(
            task_id=f"upload_{resource_type}_{resource_id}_{int(time.time())}",
            task_type="upload",
            resource_type=resource_type,
            resource_id=resource_id
        )

        self.sync_tasks.append(task)
        logger.info(f"提交上传任务: {task.task_id}")
        return task.task_id

    def submit_download_task(self, resource_type: str, resource_id: str = "all") -> str:
        """提交下载任务"""
        task = SyncTask(
            task_id=f"download_{resource_type}_{resource_id}_{int(time.time())}",
            task_type="download",
            resource_type=resource_type,
            resource_id=resource_id
        )

        self.sync_tasks.append(task)
        logger.info(f"提交下载任务: {task.task_id}")
        return task.task_id

    def get_task_status(self, task_id: str) -> Optional[SyncTask]:
        """获取任务状态"""
        for task in self.sync_tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            "running": self.running,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "pending_tasks": len([t for t in self.sync_tasks if t.status == "pending"]),
            "running_tasks": len([t for t in self.sync_tasks if t.status == "running"]),
            "completed_tasks": len([t for t in self.sync_tasks if t.status == "completed"]),
            "failed_tasks": len([t for t in self.sync_tasks if t.status == "failed"])
        }

class CloudAPIService:
    """云端API服务主类"""

    def __init__(self, config: CloudConfig):
        """
        初始化云端API服务

        Args:
            config: 云端配置
        """
        self.config = config
        self.client = CloudAPIClient(config)
        self.sync_manager = CloudSyncManager(config)

    def start_service(self):
        """启动服务"""
        self.sync_manager.start_sync()
        logger.info("云端API服务已启动")

    def stop_service(self):
        """停止服务"""
        self.sync_manager.stop_sync()
        logger.info("云端API服务已停止")

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            status = self.client.get_server_status()
            return status.get('status') == 'online'
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "api_url": self.config.api_url,
            "connected": self.test_connection(),
            "sync_status": self.sync_manager.get_sync_status()
        }
