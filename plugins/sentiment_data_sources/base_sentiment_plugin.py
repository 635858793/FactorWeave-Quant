from loguru import logger
"""
情绪数据源插件基类
提供情绪分析数据获取的标准接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass

from core.plugin_types import PluginType, PluginCategory
from plugins.sentiment_data_source_interface import (
    ISentimentDataSource,
    SentimentData,
    SentimentResponse,
    SentimentStatus,
    TradingSignal
)

@dataclass
class SentimentPluginInfo:
    """情绪数据源插件信息结构"""
    name: str  # 中文显示名称
    version: str
    description: str  # 中文描述
    author: str
    plugin_type: str = "sentiment"  # 使用正确的插件类型
    category: str = "core"
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

# 移除本地重复定义的类，使用统一接口

class BaseSentimentPlugin(ISentimentDataSource):
    """情绪数据源插件基类"""

    def __init__(self):
        self.context = None
        self.cache = {}
        self.cache_timeout = 300  # 5分钟缓存
        self.last_update = None
        # 创建本地logger作为备用
        self._local_logger = logger

    def _safe_log(self, level: str, message: str):
        """安全的日志记录方法"""
        try:
            getattr(logger, level, logger.info)(message)
        except Exception:
            logger.info(f"[{level.upper()}] {message}")

    def get_plugin_info(self) -> SentimentPluginInfo:
        """
        获取插件信息，包含中文名称和描述

        子类可以重写此方法以提供特定的插件信息，
        如果不重写，将使用metadata属性中的信息

        Returns:
            SentimentPluginInfo: 插件信息对象
        """
        try:
            # 获取metadata属性
            metadata = getattr(self, 'metadata', {})

            # 提取插件信息，优先使用metadata中的值
            name = metadata.get('name', self.__class__.__name__)
            version = metadata.get('version', '1.0.0')
            description = metadata.get('description', '')
            author = metadata.get('author', '')

            # 提取标签信息
            tags = metadata.get('tags', [])
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(',') if tag.strip()]

            return SentimentPluginInfo(
                name=name,
                version=version,
                description=description,
                author=author,
                plugin_type="sentiment",
                category="core",
                tags=tags
            )
        except Exception as e:
            self._safe_log("warning", f"获取插件信息失败，使用默认信息: {e}")
            return SentimentPluginInfo(
                name=self.__class__.__name__,
                version="1.0.0",
                description="情绪数据源插件",
                author="Unknown",
                plugin_type="sentiment",
                category="core",
                tags=["情绪分析"]
            )

    def initialize(self, config: dict = None, context=None) -> bool:
        """初始化插件"""
        try:
            if context is not None:
                self.context = context

            if self.context is not None:
                # log_manager已迁移到Loguru, 'log_manager', None)
                # 尝试获取插件配置，如果context没有该方法也不会报错
                if hasattr(context, 'get_plugin_config'):
                    plugin_info = self.get_plugin_info()
                    self.config = context.get_plugin_config(plugin_info.name)
                else:
                    self.config = {}
            else:
                # 处理context为None的情况，使用默认配置
                # log_manager已迁移到Loguru
                self.config = {}

            return True
        except Exception as e:
            self._safe_log("error", f"插件初始化失败: {e}")
            return False

    def cleanup(self) -> None:
        """清理插件资源"""
        try:
            # 清理缓存
            self.cache.clear()

            # 子类可以重写此方法进行特定的清理操作
            if hasattr(self, '_cleanup_resources'):
                self._cleanup_resources()

        except Exception as e:
            self._safe_log("error", f"插件清理失败: {e}")

    def test_connection(self) -> bool:
        """测试插件连接状态

        子类可以重写此方法实现具体的连接测试逻辑
        默认实现：轻量级连接测试，避免阻塞UI
        """
        try:
            # 方法1：如果子类实现了_test_connection方法，调用它
            if hasattr(self, '_test_connection'):
                return self._test_connection()

            # 方法2：快速连接测试（不执行耗时的数据获取）
            # 只检查基本配置和初始化状态
            if hasattr(self, 'config') and self.config:
                # 检查是否有API相关配置且已正确设置
                api_fields = ['api_key', 'access_token', 'secret_key', 'app_id']
                for field in api_fields:
                    if field in self.config:
                        # 如果有API配置字段，检查是否非空
                        if not self.config.get(field):
                            self._safe_log("info", f"插件配置不完整: {field} 为空")
                            return False
                        return True

            # 方法3：检查插件是否已正确初始化
            if hasattr(self, 'context') and self.context is not None:
                return True
            elif not hasattr(self, 'context'):
                # 如果插件不需要context，也认为连接正常
                return True

            return True  # 默认认为连接正常（避免阻塞）

        except Exception as e:
            self._safe_log("warning", f"连接测试失败: {e}")
            return False

    def test_connection_async(self) -> bool:
        """异步连接测试（用于深度测试）

        此方法可以在后台线程中调用，执行更深入的连接测试
        """
        try:
            # 方法1：如果子类实现了_test_connection_async方法，调用它
            if hasattr(self, '_test_connection_async'):
                return self._test_connection_async()

            # 方法2：尝试获取测试数据（可能耗时）
            import threading
            import time

            result = [False]  # 使用列表以便在嵌套函数中修改

            def test_fetch():
                try:
                    test_response = self.fetch_sentiment_data()
                    if test_response and hasattr(test_response, 'success'):
                        result[0] = test_response.success
                    elif test_response is not None:
                        result[0] = True
                except Exception as e:
                    self._safe_log("debug", f"异步连接测试异常: {e}")
                    result[0] = False

            # 在单独线程中执行，避免阻塞
            test_thread = threading.Thread(target=test_fetch, daemon=True)
            test_thread.start()
            test_thread.join(timeout=5.0)  # 最多等待5秒

            if test_thread.is_alive():
                self._safe_log("info", "异步连接测试超时，假设连接正常")
                return True

            return result[0]

        except Exception as e:
            self._safe_log("warning", f"异步连接测试失败: {e}")
            return False

    def is_connected(self) -> bool:
        """检查插件是否已连接

        默认实现：简单的状态检查
        子类可以重写此方法实现更精确的连接状态检查
        """
        try:
            # 方法1：如果子类实现了_is_connected方法，调用它
            if hasattr(self, '_is_connected'):
                return self._is_connected()

            # 方法2：检查插件是否已初始化
            if not hasattr(self, 'context'):
                return False

            # 方法3：如果有API密钥等配置，检查是否已设置
            if hasattr(self, 'config') and self.config:
                # 检查是否有API相关配置
                api_fields = ['api_key', 'access_token', 'secret_key', 'app_id']
                has_api_config = any(field in self.config for field in api_fields)
                if has_api_config:
                    # 如果需要API配置，检查是否已设置
                    return any(self.config.get(field) for field in api_fields if field in self.config)

            # 默认认为已连接（对于不需要特殊连接的插件）
            return True

        except Exception as e:
            self._safe_log("warning", f"连接状态检查失败: {e}")
            return False

    def fetch_sentiment_data(self, use_cache: bool = True, **kwargs) -> SentimentResponse:
        """
        获取情绪数据
        """
        pass

    @abstractmethod
    def _fetch_raw_sentiment_data(self, **kwargs) -> SentimentResponse:
        """
        获取原始情绪数据（子类实现）

        Args:
            **kwargs: 扩展参数

        Returns:
            SentimentResponse: 情绪数据响应
        """
        pass

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self.last_update:
            return False

        elapsed = (datetime.now() - self.last_update).total_seconds()
        return elapsed < self.cache_timeout

    def validate_data_quality(self, data: List[SentimentData]) -> float:
        """验证数据质量"""
        if not data:
            return 0.0

        quality_score = 0.0

        # 检查数据完整性
        complete_data = [d for d in data if d.value is not None and d.timestamp is not None]
        completeness = len(complete_data) / len(data)
        quality_score += completeness * 0.4

        # 检查数据时效性
        current_time = datetime.now()
        recent_data = [d for d in complete_data
                       if (current_time - d.timestamp).total_seconds() < 86400]  # 24小时内
        timeliness = len(recent_data) / len(complete_data) if complete_data else 0
        quality_score += timeliness * 0.3

        # 检查数据置信度
        avg_confidence = np.mean([d.confidence for d in complete_data]) if complete_data else 0
        quality_score += avg_confidence * 0.3

        return min(1.0, quality_score)

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "cache_timeout": 300,
            "retry_times": 3,
            "request_timeout": 30,
            "enable_cache": True,
            "data_source_priority": 1.0
        }

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置"""
        try:
            required_fields = ["cache_timeout", "retry_times", "request_timeout"]
            return all(field in config for field in required_fields)
        except Exception:
            return False

    def _handle_plugin_error(self, error: Exception, operation: str) -> SentimentResponse:
        """处理插件错误"""
        error_msg = f"插件操作失败 [{operation}]: {str(error)}"
        self._safe_log("error", error_msg)

        return SentimentResponse(
            success=False,
            data=[],
            composite_score=50.0,  # 中性分数
            error_message=error_msg,
            data_quality="error",
            update_time=datetime.now()
        )

