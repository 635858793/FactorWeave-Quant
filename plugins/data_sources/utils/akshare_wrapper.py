"""
AKShare请求包装器

为AKShare添加反爬虫功能，包括：
- 自定义请求头
- 随机延迟
- 请求频率控制
"""

import time
import random
from typing import Any, Callable
from functools import wraps
from loguru import logger

try:
    import akshare as ak
    import requests
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.warning("AKShare或requests未安装，包装器功能不可用")

from .retry_helper import get_random_headers, apply_anti_crawler_delay


class AKShareWrapper:
    """
    AKShare包装器 - 添加反爬虫功能
    
    使用方式:
        wrapper = AKShareWrapper()
        df = wrapper.stock_zh_a_hist(symbol="000001", period="daily")
    """
    
    def __init__(
        self, 
        enable_anti_crawler: bool = True,
        min_delay: float = 0.5,
        max_delay: float = 2.0,
        use_random_headers: bool = True
    ):
        """
        初始化包装器
        
        Args:
            enable_anti_crawler: 是否启用反爬虫功能
            min_delay: 最小请求间隔（秒）
            max_delay: 最大请求间隔（秒）
            use_random_headers: 是否使用随机请求头
        """
        if not AKSHARE_AVAILABLE:
            raise ImportError("AKShare未安装，无法使用包装器")
        
        self.enable_anti_crawler = enable_anti_crawler
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.use_random_headers = use_random_headers
        self.last_request_time = 0
        
        # 配置requests会话（如果可能）
        if self.use_random_headers:
            self._setup_requests_session()
        
        logger.info(f"AKShareWrapper初始化 (反爬虫: {enable_anti_crawler}, 随机头: {use_random_headers})")
    
    def _setup_requests_session(self):
        """设置requests会话的默认请求头"""
        try:
            # 尝试修改requests的默认会话
            session = requests.Session()
            session.headers.update(get_random_headers())
            
            # 尝试将这个会话注入到akshare中（如果可能）
            # 注意：这可能不适用于所有版本的akshare
            if hasattr(ak, '_session'):
                ak._session = session
            
            logger.debug("已设置requests会话的自定义请求头")
        except Exception as e:
            logger.warning(f"设置requests会话失败: {e}")
    
    def _apply_rate_limit(self):
        """应用请求频率限制"""
        if not self.enable_anti_crawler:
            return
        
        # 计算距离上次请求的时间
        elapsed = time.time() - self.last_request_time
        min_interval = self.min_delay
        
        if elapsed < min_interval:
            wait_time = min_interval - elapsed + random.uniform(0, self.max_delay - self.min_delay)
            logger.debug(f"频率限制: 等待{wait_time:.2f}秒")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def __getattr__(self, name: str) -> Callable:
        """
        动态代理AKShare的所有方法
        
        Args:
            name: AKShare函数名
        
        Returns:
            包装后的函数
        """
        if not hasattr(ak, name):
            raise AttributeError(f"AKShare没有属性或方法: {name}")
        
        original_func = getattr(ak, name)
        
        @wraps(original_func)
        def wrapper(*args, **kwargs):
            # 应用频率限制
            self._apply_rate_limit()
            
            # 如果启用反爬虫，添加随机延迟
            if self.enable_anti_crawler:
                apply_anti_crawler_delay(self.min_delay, self.max_delay)
            
            # 调用原始函数
            try:
                result = original_func(*args, **kwargs)
                return result
            except Exception as e:
                logger.warning(f"AKShare {name} 调用失败: {e}")
                raise
        
        return wrapper


def patch_akshare_headers():
    """
    全局修补AKShare的请求头（使用猴子补丁）
    
    注意：这是一个全局操作，会影响所有后续的AKShare调用
    
    使用方式:
        from plugins.data_sources.utils.akshare_wrapper import patch_akshare_headers
        patch_akshare_headers()
        # 之后所有的akshare调用都会使用随机请求头
    """
    if not AKSHARE_AVAILABLE:
        logger.warning("AKShare未安装，无法应用补丁")
        return False
    
    try:
        import requests
        from unittest.mock import patch
        
        # 保存原始的requests.get
        original_get = requests.get
        original_post = requests.post
        
        def patched_get(*args, **kwargs):
            """修补后的requests.get，添加随机请求头"""
            if 'headers' not in kwargs:
                kwargs['headers'] = get_random_headers()
            else:
                # 合并请求头
                kwargs['headers'].update(get_random_headers())
            return original_get(*args, **kwargs)
        
        def patched_post(*args, **kwargs):
            """修补后的requests.post，添加随机请求头"""
            if 'headers' not in kwargs:
                kwargs['headers'] = get_random_headers()
            else:
                # 合并请求头
                kwargs['headers'].update(get_random_headers())
            return original_post(*args, **kwargs)
        
        # 应用猴子补丁
        requests.get = patched_get
        requests.post = patched_post
        
        logger.info("已为AKShare应用反爬虫请求头补丁")
        return True
        
    except Exception as e:
        logger.error(f"应用AKShare补丁失败: {e}")
        return False


# 自动应用补丁（可选）
# 如果需要全局生效，取消下面的注释
# if AKSHARE_AVAILABLE:
#     patch_akshare_headers()

