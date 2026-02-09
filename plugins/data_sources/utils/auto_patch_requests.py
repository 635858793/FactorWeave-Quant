"""
自动为所有HTTP请求添加反爬虫功能

在插件加载时自动应用，无需修改每个插件
"""

import functools
from loguru import logger

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests库未安装")

from .retry_helper import (
    get_random_headers, get_conservative_headers, get_minimal_anti_crawler_headers,
    get_ultra_conservative_headers, is_connection_error
)


# 标记是否已应用补丁
_PATCH_APPLIED = False

# 全局Session对象（带连接池和重试策略）
_GLOBAL_SESSION = None

# 配置选项
AUTO_PATCH_CONFIG = {
    'enable_connection_pool': True,   # 是否使用连接池
    'pool_connections': 10,            # 连接池大小
    'pool_maxsize': 20,                # 最大连接数
    'max_retries': 3,                  # 最大重试次数
    'timeout': 30,                     # 默认超时（秒）
    'log_level': 'debug',              # 日志级别：debug, info, warning, error
    'retry_backoff_factor': 1.0,       # 重试指数退避因子
}


def get_global_session():
    """
    获取全局Session对象（带连接池和自动重试）
    
    使用AUTO_PATCH_CONFIG配置：
    - 连接池大小：可配置
    - 最大重试：可配置
    - 重试状态码：429, 500, 502, 503, 504
    - 连接超时：可配置
    - Keep-Alive：启用
    """
    global _GLOBAL_SESSION
    
    if _GLOBAL_SESSION is None and AUTO_PATCH_CONFIG.get('enable_connection_pool', True):
        _GLOBAL_SESSION = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=AUTO_PATCH_CONFIG.get('max_retries', 3),
            backoff_factor=AUTO_PATCH_CONFIG.get('retry_backoff_factor', 1.0),
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # 配置HTTP和HTTPS适配器
        adapter = HTTPAdapter(
            pool_connections=AUTO_PATCH_CONFIG.get('pool_connections', 10),
            pool_maxsize=AUTO_PATCH_CONFIG.get('pool_maxsize', 20),
            max_retries=retry_strategy,
            pool_block=False  # 连接池满时不阻塞
        )
        
        _GLOBAL_SESSION.mount("http://", adapter)
        _GLOBAL_SESSION.mount("https://", adapter)
        
        # 设置Keep-Alive
        _GLOBAL_SESSION.headers.update({'Connection': 'keep-alive'})
        
        logger.debug(f"创建全局Session对象（连接池:{AUTO_PATCH_CONFIG['pool_connections']}, "
                    f"最大重试:{AUTO_PATCH_CONFIG['max_retries']}, "
                    f"超时:{AUTO_PATCH_CONFIG['timeout']}秒）")
    
    return _GLOBAL_SESSION


def _smart_request_with_retry(original_func, *args, **kwargs):
    """
    智能请求处理，支持连接错误重试
    
    Args:
        original_func: 原始请求函数
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        请求结果
    """
    max_retries = 2
    retry_delay = 1.0
    
    for attempt in range(max_retries + 1):
        try:
            # 创建kwargs的副本，避免修改原始参数
            current_kwargs = kwargs.copy()
            
            # 添加默认超时（防止连接挂起）
            if 'timeout' not in current_kwargs:
                current_kwargs['timeout'] = AUTO_PATCH_CONFIG.get('timeout', 30)
            
            # 添加连接池配置（复用连接，减少RemoteDisconnected）
            if 'adapter' not in current_kwargs:
                # 使用Session对象可以复用连接
                pass  # requests会自动处理连接池
            
            # 根据尝试次数选择请求头策略
            if attempt == 0:
                # 第一次尝试：使用智能策略
                if 'headers' not in current_kwargs or not current_kwargs['headers']:
                    current_kwargs['headers'] = get_conservative_headers()
                else:
                    anti_crawler_headers = get_minimal_anti_crawler_headers()
                    for key, value in anti_crawler_headers.items():
                        if key not in current_kwargs['headers']:
                            current_kwargs['headers'][key] = value
            elif attempt == 1:
                # 第二次尝试：使用超保守策略
                logger.debug("连接错误，使用超保守请求头重试")
                current_kwargs['headers'] = get_ultra_conservative_headers()
                # 添加额外延迟
                import time
                time.sleep(retry_delay)
            else:
                # 最后一次尝试：使用最保守策略
                logger.debug("连接错误，使用最保守请求头重试")
                current_kwargs['headers'] = get_ultra_conservative_headers()
                # 添加更长延迟
                import time
                time.sleep(retry_delay * 2)
            
            return original_func(*args, **current_kwargs)
            
        except Exception as e:
            if is_connection_error(e) and attempt < max_retries:
                logger.debug(f"检测到连接错误，准备重试 (尝试 {attempt + 1}/{max_retries + 1}): {str(e)[:100]}")
                continue
            else:
                # 非连接错误或重试次数用完
                if is_connection_error(e):
                    # 根据配置的日志级别记录（避免刷屏）
                    log_level = AUTO_PATCH_CONFIG.get('log_level', 'debug')
                    error_msg = f"连接错误重试失败，已尝试 {attempt + 1} 次: {str(e)[:150]}"
                    
                    if log_level == 'error':
                        logger.error(error_msg)
                    elif log_level == 'warning':
                        logger.warning(error_msg)
                    elif log_level == 'info':
                        logger.info(error_msg)
                    else:  # debug
                        logger.debug(error_msg)
                raise e


def patch_requests_globally():
    """
    全局补丁requests库，为所有HTTP请求添加反爬虫功能
    
    这个函数会修改requests.get和requests.post的默认行为：
    1. 自动添加浏览器请求头
    2. 保留用户自定义的请求头
    
    Returns:
        bool: 是否成功应用补丁
    """
    global _PATCH_APPLIED
    
    if _PATCH_APPLIED:
        logger.debug("requests补丁已经应用，跳过")
        return True
    
    if not REQUESTS_AVAILABLE:
        logger.warning("requests库不可用，无法应用补丁")
        return False
    
    try:
        # 保存原始函数
        original_get = requests.get
        original_post = requests.post
        original_request = requests.request
        
        @functools.wraps(original_get)
        def patched_get(*args, **kwargs):
            """修补后的requests.get - 智能反爬虫策略"""
            return _smart_request_with_retry(original_get, *args, **kwargs)
        
        @functools.wraps(original_post)
        def patched_post(*args, **kwargs):
            """修补后的requests.post - 智能反爬虫策略"""
            return _smart_request_with_retry(original_post, *args, **kwargs)
        
        @functools.wraps(original_request)
        def patched_request(*args, **kwargs):
            """修补后的requests.request - 智能反爬虫策略"""
            return _smart_request_with_retry(original_request, *args, **kwargs)
        
        # 应用补丁
        requests.get = patched_get
        requests.post = patched_post
        requests.request = patched_request
        
        # 也修补Session类
        original_session_request = requests.Session.request
        
        @functools.wraps(original_session_request)
        def patched_session_request(self, *args, **kwargs):
            """修补后的Session.request - 智能反爬虫策略"""
            return _smart_request_with_retry(original_session_request, self, *args, **kwargs)
        
        requests.Session.request = patched_session_request
        
        _PATCH_APPLIED = True
        logger.info("已为所有HTTP请求应用反爬虫补丁（requests库）")
        return True
        
    except Exception as e:
        logger.error(f"应用requests补丁失败: {e}")
        return False


# 自动应用补丁
# 当这个模块被导入时，自动应用
if REQUESTS_AVAILABLE:
    patch_requests_globally()

