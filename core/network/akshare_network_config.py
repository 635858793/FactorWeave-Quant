"""
AkShare网络配置管理器
处理AkShare的网络连接、代理设置和IP限制问题
"""

import requests
import time
from loguru import logger
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import random

class AkShareNetworkConfig:
    """AkShare网络配置管理器"""

    def __init__(self):
        self.session = requests.Session()
        self.proxies = []
        self.current_proxy = None
        self.request_count = 0
        self.last_request_time = None
        self.rate_limit_delay = 1.0  # 默认1秒延迟
        self.max_requests_per_minute = 30  # 每分钟最大请求数
        self.ip_blocked = False
        self.last_block_time = None
        self.block_duration = timedelta(hours=1)  # IP被封时等待1小时

        # 设置默认请求头
        self._setup_default_headers()

        # 设置超时
        self.timeout = (10, 30)  # 连接超时10秒，读取超时30秒

    def _setup_default_headers(self):
        """设置默认请求头"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        self.session.headers.update(headers)

    def add_proxy(self, proxy_url: str, proxy_type: str = 'http'):
        """
        添加代理

        Args:
            proxy_url: 代理URL，格式如 'ip:port' 或 'username:password@ip:port'
            proxy_type: 代理类型，支持 'http', 'https', 'socks5'
        """
        try:
            if proxy_type.lower() == 'socks5':
                proxy_dict = {
                    'http': f'socks5://{proxy_url}',
                    'https': f'socks5://{proxy_url}'
                }
            else:
                proxy_dict = {
                    'http': f'http://{proxy_url}',
                    'https': f'https://{proxy_url}'
                }

            # 测试代理可用性
            if self._test_proxy(proxy_dict):
                self.proxies.append({
                    'url': proxy_url,
                    'type': proxy_type,
                    'config': proxy_dict,
                    'success_count': 0,
                    'failure_count': 0,
                    'last_used': None
                })
                logger.info(f"添加代理成功: {proxy_url}")
                return True
            else:
                logger.warning(f"代理测试失败: {proxy_url}")
                return False

        except Exception as e:
            logger.error(f"添加代理失败 {proxy_url}: {e}")
            return False

    def _test_proxy(self, proxy_dict: Dict) -> bool:
        """测试代理可用性"""
        try:
            test_session = requests.Session()
            test_session.proxies.update(proxy_dict)
            test_session.timeout = (5, 10)

            # 测试连接到百度
            response = test_session.get('https://www.baidu.com', timeout=10)
            return response.status_code == 200

        except Exception:
            return False

    def rotate_proxy(self):
        """轮换代理"""
        if not self.proxies:
            return False

        # 选择成功率最高的可用代理
        available_proxies = [p for p in self.proxies if p['failure_count'] < 5]

        if not available_proxies:
            logger.warning("没有可用的代理")
            return False

        # 按成功率排序
        best_proxy = max(available_proxies,
                         key=lambda x: x['success_count'] / max(x['success_count'] + x['failure_count'], 1))

        self.current_proxy = best_proxy
        self.session.proxies.update(best_proxy['config'])

        logger.info(f"切换到代理: {best_proxy['url']}")
        return True

    def clear_proxy(self):
        """清除代理设置"""
        self.session.proxies.clear()
        self.current_proxy = None
        logger.info("已清除代理设置")

    def set_rate_limit(self, delay_seconds: float, max_requests_per_minute: int = 30):
        """
        设置请求频率限制

        Args:
            delay_seconds: 请求间隔（秒）
            max_requests_per_minute: 每分钟最大请求数
        """
        self.rate_limit_delay = delay_seconds
        self.max_requests_per_minute = max_requests_per_minute
        logger.info(f"设置请求频率限制: {delay_seconds}秒间隔, {max_requests_per_minute}次/分钟")

    def check_rate_limit(self) -> bool:
        """检查是否需要等待（频率限制）"""
        now = datetime.now()

        # 检查IP是否被封
        if self.ip_blocked and self.last_block_time:
            if now - self.last_block_time < self.block_duration:
                remaining = self.block_duration - (now - self.last_block_time)
                logger.warning(f"IP仍被封禁，还需等待 {remaining}")
                return False
            else:
                self.ip_blocked = False
                logger.info("IP封禁时间已过，恢复正常")

        # 检查请求间隔
        if self.last_request_time:
            elapsed = (now - self.last_request_time).total_seconds()
            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                logger.debug(f"频率限制，等待 {wait_time:.1f} 秒")
                time.sleep(wait_time)

        return True

    def make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        发起HTTP请求（带频率限制和错误处理）

        Args:
            method: HTTP方法 ('GET', 'POST', etc.)
            url: 请求URL
            **kwargs: requests参数

        Returns:
            Response对象

        Raises:
            Exception: 请求失败时抛出异常
        """
        # 设置超时
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout

        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            # 每次重试前检查频率限制
            if not self.check_rate_limit():
                raise Exception("IP被封禁或频率限制")

            try:
                # 发起请求
                response = self.session.request(method, url, **kwargs)

                # 记录请求时间
                self.last_request_time = datetime.now()
                self.request_count += 1

                # 检查响应状态
                if response.status_code == 200:
                    # 请求成功
                    if self.current_proxy:
                        self.current_proxy['success_count'] += 1
                        self.current_proxy['last_used'] = datetime.now()

                    logger.debug(f"请求成功: {url} (状态码: {response.status_code})")
                    return response

                elif response.status_code in [429, 403, 406]:
                    # 可能被限制
                    logger.warning(f"可能被限制: {url} (状态码: {response.status_code})")
                    self._handle_rate_limit()

                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        raise Exception(f"请求被限制: {response.status_code}")

                else:
                    # 其他错误状态码
                    logger.warning(f"请求错误: {url} (状态码: {response.status_code})")
                    raise Exception(f"请求失败: {response.status_code}")

            except requests.exceptions.ProxyError as e:
                logger.warning(f"代理错误: {e}")
                if self.current_proxy:
                    self.current_proxy['failure_count'] += 1

                # 尝试切换代理
                if self.rotate_proxy():
                    continue
                else:
                    self.clear_proxy()

            except requests.exceptions.Timeout as e:
                logger.warning(f"请求超时: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    raise Exception(f"请求超时: {e}")

            except requests.exceptions.ConnectionError as e:
                logger.warning(f"连接错误: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    raise Exception(f"连接失败: {e}")

            except Exception as e:
                logger.error(f"请求异常: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    raise

        raise Exception(f"请求失败，已重试 {max_retries} 次")

    def _handle_rate_limit(self):
        """处理频率限制"""
        self.ip_blocked = True
        self.last_block_time = datetime.now()

        logger.warning("检测到IP可能被封，标记为被封状态")

        # 尝试切换代理
        if self.proxies and self.rotate_proxy():
            self.ip_blocked = False
            logger.info("已切换代理，尝试恢复")
        else:
            logger.warning(f"没有可用代理，将等待 {self.block_duration}")

    def get_status(self) -> Dict[str, Any]:
        """获取网络配置状态"""
        status = {
            'request_count': self.request_count,
            'current_proxy': self.current_proxy['url'] if self.current_proxy else None,
            'total_proxies': len(self.proxies),
            'available_proxies': len([p for p in self.proxies if p['failure_count'] < 5]),
            'ip_blocked': self.ip_blocked,
            'last_request_time': self.last_request_time.isoformat() if self.last_request_time else None,
            'rate_limit_delay': self.rate_limit_delay,
            'max_requests_per_minute': self.max_requests_per_minute
        }

        if self.ip_blocked and self.last_block_time:
            remaining = self.block_duration - (datetime.now() - self.last_block_time)
            status['block_remaining'] = str(remaining) if remaining.total_seconds() > 0 else "已解除"

        return status

    def reset_session(self):
        """重置会话"""
        self.session.close()
        self.session = requests.Session()
        self._setup_default_headers()

        if self.current_proxy:
            self.session.proxies.update(self.current_proxy['config'])

        logger.info("会话已重置")

    def load_proxy_list(self, proxy_list: List[str]):
        """
        批量加载代理列表

        Args:
            proxy_list: 代理列表，格式如 ['ip1:port1', 'ip2:port2', ...]
        """
        success_count = 0
        for proxy_url in proxy_list:
            try:
                if self.add_proxy(proxy_url):
                    success_count += 1
            except Exception as e:
                logger.error(f"加载代理失败 {proxy_url}: {e}")

        logger.info(f"代理加载完成: {success_count}/{len(proxy_list)} 个代理可用")
        return success_count

# 全局网络配置实例
_network_config = None

def get_akshare_network_config() -> AkShareNetworkConfig:
    """获取AkShare网络配置实例"""
    global _network_config
    if _network_config is None:
        _network_config = AkShareNetworkConfig()
    return _network_config

def configure_akshare_network(delay_seconds: float = 1.0,
                              max_requests_per_minute: int = 30,
                              proxies: List[str] = None) -> AkShareNetworkConfig:
    """
    配置AkShare网络设置

    Args:
        delay_seconds: 请求间隔
        max_requests_per_minute: 每分钟最大请求数
        proxies: 代理列表

    Returns:
        网络配置实例
    """
    config = get_akshare_network_config()
    config.set_rate_limit(delay_seconds, max_requests_per_minute)

    if proxies:
        config.load_proxy_list(proxies)

    return config
