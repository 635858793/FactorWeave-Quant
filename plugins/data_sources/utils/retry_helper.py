"""
数据源插件重试助手

提供通用的重试机制和错误处理，包括反爬虫策略
"""

import time
import functools
import random
import threading
from typing import Callable, Any, Optional, Type, Tuple
from loguru import logger


# 全局频率限制器（线程安全）
class GlobalRateLimiter:
    """
    全局频率限制器
    避免并发请求过多触发API限流
    """

    def __init__(self, min_interval: float = 0.3):
        self.min_interval = min_interval
        self.last_request_time = 0
        self.lock = threading.Lock()

    def wait(self):
        """等待到合适的时间再发送请求"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time

            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                time.sleep(wait_time)

            self.last_request_time = time.time()


# 全局限流器实例（所有API共享）- 调整为更保守的策略
_global_rate_limiter = GlobalRateLimiter(min_interval=1.0)


def set_global_rate_limit(min_interval: float):
    """
    设置全局请求最小间隔

    Args:
        min_interval: 最小请求间隔（秒），建议0.3-1.0秒

    Example:
        # 更保守的限流策略
        set_global_rate_limit(0.5)
    """
    global _global_rate_limiter
    _global_rate_limiter = GlobalRateLimiter(min_interval=min_interval)
    logger.info(f"全局请求频率限制已设置为: {min_interval}秒/请求")


# 常用User-Agent列表（模拟真实浏览器）
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]


def get_random_headers():
    """
    获取随机请求头（反爬虫）

    Returns:
        包含常用请求头的字典
    """
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }


def get_conservative_headers():
    """
    获取保守的请求头（避免触发反爬虫机制）
    
    Returns:
        包含基本请求头的字典
    """
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }


def get_minimal_anti_crawler_headers():
    """
    获取最小化的反爬虫请求头（避免与现有headers冲突）
    
    Returns:
        包含必要反爬虫请求头的字典
    """
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }


def get_ultra_conservative_headers():
    """
    获取超保守的请求头（用于连接错误时的重试）
    
    Returns:
        包含最保守请求头的字典
    """
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
    }


def is_connection_error(exception):
    """
    检测是否是连接相关错误
    
    Args:
        exception: 异常对象
        
    Returns:
        bool: 是否是连接错误
    """
    error_str = str(exception).lower()
    connection_keywords = [
        'connection aborted', 'remote disconnected', 'connection refused',
        'timeout', 'network', 'socket', 'connection reset',
        'remote end closed', 'connection broken'
    ]
    return any(keyword in error_str for keyword in connection_keywords)


def apply_anti_crawler_delay(min_delay: float = 0.5, max_delay: float = 2.0):
    """
    应用随机延迟（模拟人类行为，避免触发反爬虫）

    Args:
        min_delay: 最小延迟（秒）
        max_delay: 最大延迟（秒）
    """
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


def retry_on_connection_error(
    max_retries: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 1.5,
    exceptions: Tuple[Type[Exception], ...] = (ConnectionError, TimeoutError, Exception),
    default_return: Any = None,
    log_prefix: str = "API调用",
    use_anti_crawler: bool = True  # 是否使用反爬虫策略
):
    """
    重试装饰器 - 处理网络连接错误

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子（每次重试延迟乘以此因子）
        exceptions: 需要重试的异常类型元组
        default_return: 失败时的默认返回值
        log_prefix: 日志前缀

    Returns:
        装饰后的函数

    Example:
        @retry_on_connection_error(max_retries=3, initial_delay=2.0)
        def fetch_data(symbol):
            return ak.stock_zh_a_hist(symbol=symbol)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retry_delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    # 应用全局频率限制（避免并发请求过多）
                    _global_rate_limiter.wait()

                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"{log_prefix}成功 (重试{attempt}次后)")
                    return result

                except exceptions as e:
                    last_exception = e

                    # 判断是否是连接相关错误
                    error_str = str(e).lower()
                    is_connection_error = any(keyword in error_str for keyword in [
                        'connection', 'remote', 'timeout', 'disconnect',
                        'refused', 'reset', 'broken pipe', 'timed out',
                        'aborted', 'closed connection', 'without response'
                    ])
                    
                    # 检测是否是反爬虫导致的连接拒绝
                    is_anti_crawler_blocked = any(keyword in error_str for keyword in [
                        'aborted', 'closed connection', 'without response',
                        'forbidden', 'blocked', 'rate limit'
                    ])

                    if attempt < max_retries - 1:
                        if is_connection_error:
                            # 显示详细错误信息便于诊断
                            logger.warning(f"⚠️  {log_prefix}失败 (尝试 {attempt + 1}/{max_retries}): {str(e)[:200]}")
                        else:
                            logger.warning(f"⚠️  {log_prefix}失败 (尝试 {attempt + 1}/{max_retries}): {e}")

                        # 针对反爬虫阻塞的特殊处理
                        if is_anti_crawler_blocked:
                            # 使用更长的延迟和更保守的策略
                            actual_delay = retry_delay * 2 + random.uniform(2.0, 5.0)
                            logger.warning(f"检测到反爬虫阻塞，使用保守策略，等待{actual_delay:.1f}秒后重试...")
                            time.sleep(actual_delay)
                        elif use_anti_crawler:
                            # 普通反爬虫策略
                            actual_delay = retry_delay + random.uniform(0, 1.0)
                            logger.info(f"等待{actual_delay:.1f}秒后重试（含随机延迟）...")
                            time.sleep(actual_delay)
                        else:
                            logger.info(f"等待{retry_delay:.1f}秒后重试...")
                            time.sleep(retry_delay)

                        retry_delay *= backoff_factor
                    else:
                        # 最后一次尝试也失败
                        if is_connection_error:
                            logger.error(f"❌ {log_prefix}最终失败 (已重试{max_retries}次): 网络连接不稳定")
                            logger.info("建议: 1) 检查网络连接 2) 稍后再试 3) 使用其他数据源")
                        else:
                            logger.error(f"❌ {log_prefix}最终失败 (已重试{max_retries}次): {e}")

            # 所有重试都失败，返回默认值
            return default_return

        return wrapper
    return decorator


def batch_retry_wrapper(
    func: Callable,
    items: list,
    max_retries: int = 2,
    item_name: str = "项目"
) -> Tuple[list, list]:
    """
    批量处理的重试包装器

    对列表中的每个项目应用函数，对失败的项目进行重试

    Args:
        func: 处理单个项目的函数
        items: 要处理的项目列表
        max_retries: 每个项目的最大重试次数
        item_name: 项目名称（用于日志）

    Returns:
        (成功列表, 失败列表)

    Example:
        def download_stock(symbol):
            return fetch_data(symbol)

        success, failed = batch_retry_wrapper(
            download_stock,
            ['000001', '000002', '000003'],
            max_retries=2,
            item_name="股票"
        )
    """
    success_items = []
    failed_items = []
    retry_queue = items.copy()

    for attempt in range(max_retries + 1):
        if not retry_queue:
            break

        if attempt > 0:
            logger.info(f"重试失败的{len(retry_queue)}个{item_name} (第{attempt}次重试)")

        current_failed = []

        for item in retry_queue:
            try:
                result = func(item)
                if result is not None:  # 假设None表示失败
                    success_items.append((item, result))
                else:
                    current_failed.append(item)
            except Exception as e:
                logger.warning(f"{item_name} {item} 处理失败: {e}")
                current_failed.append(item)

        retry_queue = current_failed

        if retry_queue and attempt < max_retries:
            delay = 3 * (attempt + 1)  # 递增延迟
            logger.info(f"等待{delay}秒后重试...")
            time.sleep(delay)

    failed_items = retry_queue

    if failed_items:
        logger.warning(f"⚠️  批量处理完成: 成功{len(success_items)}, 失败{len(failed_items)}")
    else:
        logger.info(f"批量处理全部成功: {len(success_items)}个{item_name}")

    return success_items, failed_items


def with_timeout(timeout_seconds: float = 30):
    """
    超时装饰器

    Args:
        timeout_seconds: 超时时间（秒）

    Example:
        @with_timeout(timeout_seconds=30)
        def slow_function():
            # 长时间运行的函数
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"函数执行超时 (>{timeout_seconds}秒)")

            # 设置超时信号
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))

            try:
                result = func(*args, **kwargs)
            finally:
                # 取消超时
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result

        return wrapper
    return decorator


def log_execution_time(func: Callable) -> Callable:
    """
    记录函数执行时间的装饰器

    Example:
        @log_execution_time
        def fetch_data():
            # ...
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import time
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"⏱️  {func.__name__} 执行时间: {elapsed:.2f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ {func.__name__} 失败 (耗时{elapsed:.2f}秒): {e}")
            raise

    return wrapper
