"""
混合推荐异步工作线程

包含处理混合推荐API调用的异步工作线程类
"""

import json
import os
import requests
import time
from typing import Dict, Any, List, Optional

from PyQt5.QtCore import QRunnable, QThread, QObject, pyqtSignal, QTimer
from loguru import logger

# API服务器地址配置
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 30  # API超时时间（秒）

def get_api_base_url():
    """获取API基础URL，从配置服务加载"""
    try:
        from core.services.config_service import ConfigService
        from core.containers import get_service_container
        container = get_service_container()
        config_service = container.resolve(ConfigService)
        logger.info("从服务容器获取配置服务成功")

        api_url = config_service.get('hybrid_api.url', 'http://localhost:8000')
        logger.info(f"从配置加载API地址: {api_url}")
        return api_url
    except Exception as e:
        logger.warning(f"无法从配置服务获取API地址，使用默认值: {e}")
        return API_BASE_URL

def update_api_base_url():
    """更新全局API基础URL"""
    global API_BASE_URL
    API_BASE_URL = get_api_base_url()
    logger.info(f"API基础URL已更新为: {API_BASE_URL}")

class HybridRecommendationSignals(QObject):
    """混合推荐信号"""
    recommendations_ready = pyqtSignal(list)  # 推荐结果就绪信号
    error_occurred = pyqtSignal(str)  # 错误信号
    finished = pyqtSignal()  # 完成信号


class HybridRecommendationWorker(QRunnable):
    """混合推荐获取工作线程"""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """初始化混合推荐工作线程

        Args:
            params: 推荐参数，如果为None则使用默认参数
        """
        super().__init__()
        self.params = params or {
            'user_id': 'default_user',
            'context': {'category': 'all'},
            'stock_codes': []
        }
        self.signals = HybridRecommendationSignals()
        self.is_cancelled = False
        self.logger = logger.bind(module=__name__)

    def run(self):
        """在后台线程中获取混合推荐数据"""
        try:
            self.logger.debug("开始获取混合推荐数据")

            # 动态获取API地址
            current_api_url = get_api_base_url()
            url = f"{current_api_url}/api/hybrid/recommendation"
            headers = {'Content-Type': 'application/json'}

            # 在后台线程中发送请求（不涉及UI更新）
            response = requests.post(url, json=self.params, headers=headers, timeout=API_TIMEOUT)

            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"API请求失败: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                self.signals.error_occurred.emit(error_msg)
                self.signals.finished.emit()
                return

            # 解析响应数据
            try:
                data = response.json()
                recommendations = data.get('recommendations', [])
                self.logger.debug(f"获取到 {len(recommendations)} 个推荐结果")
                
                # 通过信号传递推荐数据（只在后台线程中准备数据，不更新UI）
                self.signals.recommendations_ready.emit(recommendations)
            except json.JSONDecodeError as e:
                error_msg = f"解析API响应失败: {str(e)}"
                self.logger.error(error_msg)
                self.signals.error_occurred.emit(error_msg)
            
            # 发送完成信号
            self.signals.finished.emit()

        except requests.RequestException as e:
            error_msg = f"API请求异常: {str(e)}"
            self.logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.finished.emit()
        except Exception as e:
            error_msg = f"获取混合推荐失败: {str(e)}"
            self.logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.finished.emit()

    def cancel(self):
        """取消请求"""
        self.is_cancelled = True


class CacheManagementSignals(QObject):
    """缓存管理信号"""
    success = pyqtSignal(str)  # 成功信号
    error_occurred = pyqtSignal(str)  # 错误信号
    finished = pyqtSignal()  # 完成信号


class CacheWarmupWorker(QRunnable):
    """缓存预热工作线程"""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """初始化缓存预热工作线程

        Args:
            params: 预热参数，如果为None则使用默认参数
        """
        super().__init__()
        self.params = params or {
            'user_id': 'default_user',
            'context': {'category': 'all'},
            'stock_codes': []
        }
        self.signals = CacheManagementSignals()
        self.is_cancelled = False
        self.logger = logger.bind(module=__name__)

    def run(self):
        """在后台线程中预热缓存"""
        try:
            self.logger.debug("开始预热缓存")

            # 构建API请求
            url = f"{API_BASE_URL}/api/hybrid/cache/warm"
            headers = {'Content-Type': 'application/json'}

            # 在后台线程中发送请求
            response = requests.post(url, json=self.params, headers=headers, timeout=API_TIMEOUT)

            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"缓存预热失败: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                self.signals.error_occurred.emit(error_msg)
                self.signals.finished.emit()
                return

            # 解析响应数据
            try:
                data = response.json()
                message = data.get('message', '缓存预热完成')
                self.logger.info(message)
                self.signals.success.emit(message)
            except json.JSONDecodeError as e:
                error_msg = f"解析API响应失败: {str(e)}"
                self.logger.error(error_msg)
                self.signals.error_occurred.emit(error_msg)
            
            # 发送完成信号
            self.signals.finished.emit()

        except requests.RequestException as e:
            error_msg = f"API请求异常: {str(e)}"
            self.logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.finished.emit()
        except Exception as e:
            error_msg = f"缓存预热失败: {str(e)}"
            self.logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.finished.emit()

    def cancel(self):
        """取消请求"""
        self.is_cancelled = True


class CacheClearWorker(QRunnable):
    """缓存清空工作线程"""

    def __init__(self):
        """初始化缓存清空工作线程"""
        super().__init__()
        self.signals = CacheManagementSignals()
        self.is_cancelled = False
        self.logger = logger.bind(module=__name__)

    def run(self):
        """在后台线程中清空缓存"""
        try:
            self.logger.debug("开始清空缓存")

            # 构建API请求
            url = f"{API_BASE_URL}/api/hybrid/cache/clear"
            headers = {'Content-Type': 'application/json'}

            # 在后台线程中发送请求
            response = requests.post(url, headers=headers, timeout=API_TIMEOUT)

            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"清空缓存失败: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                self.signals.error_occurred.emit(error_msg)
                self.signals.finished.emit()
                return

            # 解析响应数据
            try:
                data = response.json()
                message = data.get('message', '缓存清空完成')
                self.logger.info(message)
                self.signals.success.emit(message)
            except json.JSONDecodeError as e:
                error_msg = f"解析API响应失败: {str(e)}"
                self.logger.error(error_msg)
                self.signals.error_occurred.emit(error_msg)
            
            # 发送完成信号
            self.signals.finished.emit()

        except requests.RequestException as e:
            error_msg = f"API请求异常: {str(e)}"
            self.logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.finished.emit()
        except Exception as e:
            error_msg = f"清空缓存失败: {str(e)}"
            self.logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.finished.emit()

    def cancel(self):
        """取消请求"""
        self.is_cancelled = True


class CacheStatsWorker(QRunnable):
    """缓存统计获取工作线程"""

    def __init__(self):
        """初始化缓存统计获取工作线程"""
        super().__init__()
        self.signals = CacheManagementSignals()
        self.stats_data = None
        self.is_cancelled = False
        self.logger = logger.bind(module=__name__)

    def run(self):
        """在后台线程中获取缓存统计信息"""
        try:
            self.logger.debug("开始获取缓存统计信息")

            # 构建API请求
            url = f"{API_BASE_URL}/api/hybrid/cache/stats"
            headers = {'Content-Type': 'application/json'}

            # 在后台线程中发送请求
            response = requests.get(url, headers=headers, timeout=API_TIMEOUT)

            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"获取缓存统计失败: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                self.signals.error_occurred.emit(error_msg)
                self.signals.finished.emit()
                return

            # 解析响应数据
            try:
                data = response.json()
                self.stats_data = data.get('statistics', {})
                message = data.get('message', '获取缓存统计成功')
                self.logger.info(message)
                self.signals.success.emit(message)
            except json.JSONDecodeError as e:
                error_msg = f"解析API响应失败: {str(e)}"
                self.logger.error(error_msg)
                self.signals.error_occurred.emit(error_msg)
            
            # 发送完成信号
            self.signals.finished.emit()

        except requests.RequestException as e:
            error_msg = f"API请求异常: {str(e)}"
            self.logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.finished.emit()
        except Exception as e:
            error_msg = f"获取缓存统计失败: {str(e)}"
            self.logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.finished.emit()

    def get_stats_data(self) -> Optional[Dict[str, Any]]:
        """获取统计数据

        Returns:
            缓存统计数据
        """
        return self.stats_data

    def cancel(self):
        """取消请求"""
        self.is_cancelled = True