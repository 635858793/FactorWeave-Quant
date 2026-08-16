from loguru import logger
"""
通达信股票数据源插件

提供A股实时和历史数据获取功能，支持：
- A股股票基本信息
- 历史K线数据  
- 实时行情数据
- 分时数据
- 板块数据

使用pytdx库作为数据源：
- 支持上海、深圳交易所
- 实时数据更新
- 本地数据文件读取
- TCP/UDP协议连接

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2024
"""

import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import threading
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
import concurrent.futures
import random
import queue
from contextlib import contextmanager

from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from core.plugin_types import PluginType, AssetType, DataType
from plugins.plugin_interface import PluginLifecycle

logger = logger.bind(module=__name__)

# 检查pytdx库
try:
    from pytdx.hq import TdxHq_API
    from pytdx.reader import TdxDailyBarReader, TdxMinBarReader, TdxLCMinBarReader
    from pytdx.crawler.history_financial_crawler import HistoryFinancialListCrawler
    PYTDX_AVAILABLE = True
    logger.info("pytdx 数据源可用")
except ImportError:
    PYTDX_AVAILABLE = False
    logger.error("pytdx 库未安装，插件无法工作。请安装: pip install pytdx")

# 检查必要的库
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.error("requests 库未安装，插件无法工作")


class ConnectionPool:
    """通达信连接池管理器，支持多IP并行数据获取（轮询机制 + 动态IP切换 + 故障检测）"""

    def __init__(self, max_connections: int = 20, timeout: int = 15):  # 优化：默认连接池大小从10增加到20，超时从30秒减少到15秒
        self.max_connections = max_connections
        self.timeout = timeout
        # 改为轮询机制：使用列表存储连接，不再使用FIFO队列
        self.connections_list: List[Dict[str, Any]] = []  # 连接列表（支持轮询）
        self.active_servers = []  # 活跃服务器列表
        self.server_stats = {}  # 服务器统计信息
        self.lock = threading.RLock()
        self._last_health_check = 0
        self._health_check_interval = 300  # 5分钟检查一次

        # 轮询机制：当前连接索引
        self._current_index = 0

        # IP监控统计
        self.ip_usage_stats: Dict[str, Dict[str, Any]] = {}  # IP使用统计 {server_key: {use_count, success_count, failure_count, last_used, avg_response_time, status}}

        # 故障IP管理
        self.failed_ips: Dict[str, float] = {}  # 故障IP及其恢复时间 {server_key: recovery_time}
        self.failure_threshold = 3  # 连续失败3次标记为故障
        self.failure_recovery_time = 60  # 故障IP恢复时间（秒）

        # 动态IP切换：IP限流检测
        self.ip_rate_limit: Dict[str, Dict[str, Any]] = {}  # IP限流信息 {server_key: {request_count, window_start, is_limited}}
        self.rate_limit_window = 60  # 限流检测窗口（秒）
        self.rate_limit_threshold = 100  # 限流阈值（每分钟请求数）

    def _validate_ip_address(self, ip: str) -> bool:
        """
        验证IP地址格式是否正确
        
        Args:
            ip: IP地址字符串
            
        Returns:
            bool: IP地址格式是否有效
        """
        try:
            # 使用socket.inet_aton验证IPv4地址格式
            socket.inet_aton(ip)
            # 进一步验证IP地址范围（排除0.0.0.0和255.255.255.255等特殊地址）
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            # 排除一些明显无效的地址
            if ip == '0.0.0.0' or ip == '255.255.255.255':
                return False
            return True
        except (socket.error, ValueError):
            return False

    def initialize(self, server_list: List[tuple]):
        """初始化连接池"""
        try:
            with self.lock:
                # 选择最优服务器建立连接池
                best_servers = self._select_best_servers(server_list)
                logger.info(f"为连接池选择了 {len(best_servers)} 个最优服务器")

                for server in best_servers:
                    if self._create_connection(server):
                        self.active_servers.append(server)
                        # 初始化IP使用统计
                        server_key = f"{server[0]}:{server[1]}"
                        self.ip_usage_stats[server_key] = {
                            'use_count': 0,
                            'success_count': 0,
                            'failure_count': 0,
                            'last_used': None,
                            'avg_response_time': 0.0,
                            'status': 'healthy',  # healthy, limited, failed
                            'response_times': []  # 用于计算平均响应时间
                        }

                logger.info(f"连接池初始化完成，活跃连接数: {len(self.connections_list)}")

        except Exception as e:
            logger.error(f"连接池初始化失败: {e}")

    def _select_best_servers(self, server_list: List[tuple]) -> List[tuple]:
        """选择最优的服务器用于连接池"""
        if not server_list:
            return []

        # 并行测试所有服务器
        successful_servers = []
        max_workers = min(len(server_list), 20)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_server = {
                executor.submit(self._test_server_performance, server): server
                for server in server_list
            }

            for future in as_completed(future_to_server):
                try:
                    result = future.result()
                    if result['success']:
                        successful_servers.append(result)
                except Exception:
                    continue

        # 按响应时间排序，选择前max_connections个
        successful_servers.sort(key=lambda x: x['response_time'])
        best_servers = [srv['server'] for srv in successful_servers[:self.max_connections]]

        logger.info(f"从 {len(server_list)} 个服务器中选择了 {len(best_servers)} 个最优服务器")
        return best_servers

    def _test_server_performance(self, server: tuple) -> dict:
        """测试单个服务器的性能（R249 修复：TCP + 数据访问级双重验证）

        原实现仅 TCP connect_ex 验证, 会把"TCP 可连但 get_security_bars 返回空"
        的服务器（如 R247 实测 218.6.170.47:7709）选入连接池, 导致并发分批取数
        命中坏连接持续返回空数据。升级为 get_security_bars 实际取数验证,
        与插件 _validate_connection_quality/_test_data_access 判定标准一致。
        """
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(server)
            sock.close()

            if result != 0:
                return {
                    'server': server,
                    'response_time': float('inf'),
                    'success': False
                }

            # 数据级验证：TCP 可连不代表可取数（R247 教训）
            if not PYTDX_AVAILABLE:
                return {
                    'server': server,
                    'response_time': float('inf'),
                    'success': False
                }

            api_client = TdxHq_API()
            if not api_client.connect(*server):
                logger.debug(f"通达信连接失败: {server}")
                return {
                    'server': server,
                    'response_time': float('inf'),
                    'success': False
                }

            try:
                test_data = api_client.get_security_bars(
                    category=9,  # 日线
                    market=0,   # 深圳市场
                    code='000001',
                    start=0,
                    count=1
                )
                if test_data and len(test_data) > 0:
                    response_time = time.time() - start_time
                    return {
                        'server': server,
                        'response_time': response_time,
                        'success': True
                    }
            finally:
                try:
                    api_client.disconnect()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"通达信连接测试失败: {e}")

        return {
            'server': server,
            'response_time': float('inf'),
            'success': False
        }

    def _create_connection(self, server: tuple) -> bool:
        """创建到指定服务器的连接"""
        try:
            if not PYTDX_AVAILABLE:
                return False

            api_client = TdxHq_API()
            if api_client.connect(*server):
                connection_info = {
                    'client': api_client,
                    'server': server,
                    'created_time': time.time(),
                    'last_used': time.time(),
                    'use_count': 0,
                    'server_key': f"{server[0]}:{server[1]}"
                }
                # 改为列表存储，支持轮询
                self.connections_list.append(connection_info)
                logger.debug(f"成功创建到 {server} 的连接")
                return True
            else:
                logger.debug(f"无法连接到服务器 {server}")
                return False

        except Exception as e:
            logger.debug(f"创建连接失败 {server}: {e}")
            return False

    @contextmanager
    def get_connection(self):
        """获取连接的上下文管理器（轮询机制 + 动态IP切换 + 故障检测）"""
        connection_info = None
        request_start_time = time.time()
        server_key = None
        request_success = False  # 标志变量：跟踪请求是否成功

        try:
            # 轮询机制：从连接列表中选择连接
            connection_info = self._get_connection_round_robin()

            if connection_info:
                server_key = connection_info['server_key']
                connection_info['last_used'] = time.time()
                connection_info['use_count'] += 1

                # 更新IP使用统计
                if server_key in self.ip_usage_stats:
                    self.ip_usage_stats[server_key]['use_count'] += 1
                    self.ip_usage_stats[server_key]['last_used'] = time.time()

                # 检查连接是否还有效
                if not self._is_connection_valid(connection_info):
                    # 连接无效，尝试重新创建或切换IP
                    if not self._recreate_connection(connection_info):
                        # 重新创建失败，标记为故障并尝试切换IP
                        self._mark_ip_failed(server_key)
                        connection_info = self._get_connection_round_robin()  # 重新获取连接
                        if not connection_info:
                            raise Exception("无法获取任何可用连接")
                        server_key = connection_info['server_key']

                yield connection_info['client']
                request_success = True  # 请求成功
            else:
                # 连接池为空，临时创建连接
                logger.warning("连接池为空，创建临时连接")
                temp_connection, temp_server = self._create_temporary_connection()
                if temp_connection:
                    try:
                        yield temp_connection
                        request_success = True  # 请求成功
                    finally:
                        temp_connection.disconnect()
                else:
                    raise Exception("无法获取任何可用连接")

        except Exception as e:
            # 记录失败统计
            if server_key and server_key in self.ip_usage_stats:
                self.ip_usage_stats[server_key]['failure_count'] += 1
                # 检查是否需要标记为故障
                if self.ip_usage_stats[server_key]['failure_count'] >= self.failure_threshold:
                    self._mark_ip_failed(server_key)
            raise e

        finally:
            # 更新响应时间统计（仅在成功时）
            if connection_info and server_key:
                if request_success:
                    # 请求成功：更新响应时间和成功计数
                    response_time = time.time() - request_start_time
                    if server_key in self.ip_usage_stats:
                        stats = self.ip_usage_stats[server_key]
                        stats['response_times'].append(response_time)
                        # 只保留最近100次响应时间
                        if len(stats['response_times']) > 100:
                            stats['response_times'] = stats['response_times'][-100:]
                        # 计算平均响应时间
                        if stats['response_times']:
                            stats['avg_response_time'] = sum(stats['response_times']) / len(stats['response_times'])
                        stats['success_count'] += 1

                        # 检查IP限流
                        self._check_ip_rate_limit(server_key)
                else:
                    # 修复：请求失败但use_count已增加，需要增加failure_count
                    # 注意：如果异常在except块中已经处理并增加了failure_count，这里不会重复增加
                    # 但如果请求在yield之后失败（调用者代码中失败），这里会补充统计
                    if server_key in self.ip_usage_stats:
                        stats = self.ip_usage_stats[server_key]
                        # 检查use_count是否已增加（说明请求已经开始）
                        # 如果use_count > success_count + failure_count，说明有未统计的失败
                        current_use_count = stats.get('use_count', 0)
                        current_success_count = stats.get('success_count', 0)
                        current_failure_count = stats.get('failure_count', 0)
                        expected_total = current_success_count + current_failure_count
                        if current_use_count > expected_total:
                            # 有未统计的失败，补充统计
                            missing_failures = current_use_count - expected_total
                            stats['failure_count'] = current_failure_count + missing_failures
                            logger.debug(f"IP {server_key} 补充统计失败数: {missing_failures} (use_count={current_use_count}, success={current_success_count}, failure={current_failure_count})")

    def _get_connection_round_robin(self) -> Optional[Dict[str, Any]]:
        """
        轮询获取连接（替代FIFO队列）

        策略：
        1. 跳过故障IP
        2. 跳过限流IP
        3. 轮询选择健康IP
        4. 如果所有IP都故障/限流，尝试使用故障IP（可能已恢复）
        """
        with self.lock:
            if not self.connections_list:
                return None

            current_time = time.time()
            available_connections = []

            # 第一轮：查找健康且未限流的连接
            for conn in self.connections_list:
                server_key = conn['server_key']
                stats = self.ip_usage_stats.get(server_key, {})
                status = stats.get('status', 'healthy')

                # 跳过故障IP（除非已过恢复时间）
                if status == 'failed':
                    recovery_time = self.failed_ips.get(server_key, 0)
                    if current_time < recovery_time:
                        continue  # 仍在故障期
                    else:
                        # 故障期已过，尝试恢复（但不重置failure_count，保留历史记录）
                        stats['status'] = 'healthy'
                        # 注意：不重置failure_count，保留历史记录用于分析
                        # 如果IP再次失败，会基于新的失败计数重新标记
                        if server_key in self.failed_ips:
                            del self.failed_ips[server_key]
                        logger.info(f"IP {server_key} 故障期已过，尝试恢复使用（历史失败次数: {stats.get('failure_count', 0)}）")

                # 跳过限流IP
                if status == 'limited':
                    continue

                available_connections.append(conn)

            # 如果有可用连接，使用轮询选择
            if available_connections:
                # 修复：从当前索引开始，在原始连接列表中查找对应的可用连接
                # 这样可以确保轮询顺序的一致性
                for attempt in range(len(self.connections_list)):
                    # 从当前索引开始查找
                    idx = (self._current_index + attempt) % len(self.connections_list)
                    conn = self.connections_list[idx]

                    # 使用server_key比较，更明确可靠
                    if conn['server_key'] in {c['server_key'] for c in available_connections}:
                        # 更新轮询索引（指向下一个连接）
                        self._current_index = (self._current_index + 1) % len(self.connections_list)
                        return conn

                # 如果找不到（理论上不应该发生），使用第一个可用连接
                conn = available_connections[0]
                self._current_index = (self._current_index + 1) % len(self.connections_list)
                return conn

            # 如果没有健康连接，尝试使用故障IP（可能已恢复）
            if self.connections_list:
                conn = self.connections_list[self._current_index % len(self.connections_list)]
                self._current_index = (self._current_index + 1) % len(self.connections_list)
                logger.warning(f"所有IP都故障/限流，尝试使用 {conn['server_key']}")
                return conn

            return None

    def _mark_ip_failed(self, server_key: str):
        """标记IP为故障"""
        with self.lock:
            if server_key in self.ip_usage_stats:
                self.ip_usage_stats[server_key]['status'] = 'failed'
                # 设置恢复时间
                recovery_time = time.time() + self.failure_recovery_time
                self.failed_ips[server_key] = recovery_time
                logger.warning(f"IP {server_key} 标记为故障，将在 {self.failure_recovery_time} 秒后尝试恢复")

    def _check_ip_rate_limit(self, server_key: str):
        """检查IP是否被限流"""
        current_time = time.time()

        if server_key not in self.ip_rate_limit:
            self.ip_rate_limit[server_key] = {
                'request_count': 0,
                'window_start': current_time,
                'is_limited': False
            }

        rate_info = self.ip_rate_limit[server_key]

        # 检查时间窗口
        if current_time - rate_info['window_start'] > self.rate_limit_window:
            # 新窗口，重置计数
            rate_info['request_count'] = 0
            rate_info['window_start'] = current_time
            rate_info['is_limited'] = False

        # 增加请求计数
        rate_info['request_count'] += 1

        # 检查是否超过限流阈值
        if rate_info['request_count'] > self.rate_limit_threshold:
            rate_info['is_limited'] = True
            if server_key in self.ip_usage_stats:
                self.ip_usage_stats[server_key]['status'] = 'limited'
                logger.warning(f"IP {server_key} 触发限流（{rate_info['request_count']} 请求/{self.rate_limit_window}秒）")
        else:
            # 未限流，确保状态为健康
            if server_key in self.ip_usage_stats:
                if self.ip_usage_stats[server_key]['status'] == 'limited':
                    self.ip_usage_stats[server_key]['status'] = 'healthy'
                    logger.info(f"IP {server_key} 限流已解除")

    def _is_connection_valid(self, connection_info: dict) -> bool:
        """检查连接是否有效（R249 修复：socket + 数据访问级双重检查 + 30s 缓存）

        原实现恒 return True, 无法识别"TCP 可连但数据不可用"或已断开的连接,
        轮询命中后 get_security_bars 持续返回空数据。改为:
        1. socket 级: is_connected()（pytdx 原生方法, 缺省时退化检查底层 client）
        2. 数据级: get_security_count(0) > 0（带 30 秒缓存降低每次请求开销）
        """
        try:
            client = connection_info['client']

            # 30 秒缓存：上次数据级验证成功后在窗口内直接复用结果
            now = time.time()
            last_check = connection_info.get('last_valid_check', 0)
            if now - last_check < 30:
                return True

            # socket 级检查
            if hasattr(client, 'is_connected'):
                if not client.is_connected():
                    return False
            elif getattr(client, 'client', None) is None:
                return False

            # 数据级轻量检查：能取到证券数量才算有效连接（识别"TCP可连但数据不可用"）
            count = client.get_security_count(0)
            if count is None or count <= 0:
                return False

            connection_info['last_valid_check'] = now
            return True
        except Exception:
            return False

    def _recreate_connection(self, connection_info: dict) -> bool:
        """重新创建连接"""
        try:
            old_client = connection_info['client']
            old_client.disconnect()

            new_client = TdxHq_API()
            if new_client.connect(*connection_info['server']):
                connection_info['client'] = new_client
                connection_info['created_time'] = time.time()
                logger.debug(f"重新创建连接到 {connection_info['server']}")
                return True
        except Exception as e:
            logger.debug(f"重新创建连接失败: {e}")
        return False

    def _create_temporary_connection(self):
        """创建临时连接（轮询选择服务器）"""
        current_time = time.time()
        available_servers = []

        # 优先选择健康且未限流的服务器
        for server in self.active_servers:
            server_key = f"{server[0]}:{server[1]}"
            stats = self.ip_usage_stats.get(server_key, {})
            status = stats.get('status', 'healthy')

            # 跳过故障IP（除非已过恢复时间）
            if status == 'failed':
                recovery_time = self.failed_ips.get(server_key, 0)
                if current_time < recovery_time:
                    continue

            # 跳过限流IP
            if status == 'limited':
                continue

            available_servers.append(server)

        # 如果没有健康服务器，使用所有服务器
        if not available_servers:
            available_servers = self.active_servers

        # 轮询选择服务器
        for i, server in enumerate(available_servers):
            try:
                temp_client = TdxHq_API()
                if temp_client.connect(*server):
                    server_key = f"{server[0]}:{server[1]}"
                    logger.debug(f"创建临时连接到 {server_key}")
                    return temp_client, server
            except Exception:
                continue
        return None, None

    def health_check(self):
        """健康检查和连接维护"""
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return

        logger.debug("开始连接池健康检查")
        self._last_health_check = current_time

        # 这里可以添加更多的健康检查逻辑
        # 比如检查连接的响应时间、重新测试服务器等

    def close_all(self):
        """关闭所有连接"""
        with self.lock:
            for connection_info in self.connections_list:
                try:
                    connection_info['client'].disconnect()
                except Exception:
                    pass
            self.connections_list.clear()
            logger.info("连接池已关闭所有连接")

    def get_ip_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取IP使用统计信息（用于监控）

        Returns:
            Dict[server_key, stats]: IP使用统计字典
        """
        with self.lock:
            # 修复：安全解析server_key，避免IndexError导致数据不完整
            result = {}
            for server_key, stats in self.ip_usage_stats.items():
                if not isinstance(stats, dict):
                    continue
                
                # 安全解析IP和端口
                try:
                    if ':' in server_key:
                        ip, port = server_key.split(':', 1)
                        ip = ip.strip()
                        port = port.strip()
                    else:
                        # 如果server_key格式不对，尝试从stats中获取
                        ip = stats.get('ip', server_key)
                        port = stats.get('port', '')
                        logger.debug(f"server_key格式异常，无法解析: {server_key}")
                except Exception as e:
                    logger.warning(f"解析server_key失败: {server_key}, 错误: {e}")
                    ip = server_key
                    port = ''
                
                # 确保stats字典存在且有效
                use_count = stats.get('use_count', 0) or 0
                success_count = stats.get('success_count', 0) or 0
                failure_count = stats.get('failure_count', 0) or 0
                
                # 修复：确保failure_count = use_count - success_count（数据一致性检查）
                # 如果failure_count小于use_count - success_count，说明有未统计的失败
                expected_failure_count = max(0, use_count - success_count)
                if failure_count < expected_failure_count:
                    failure_count = expected_failure_count
                    logger.debug(f"IP {server_key} 修正失败数: {failure_count} (use_count={use_count}, success_count={success_count})")
                
                result[server_key] = {
                    'ip': ip or '',
                    'port': port or '',
                    'use_count': use_count,
                    'success_count': success_count,
                    'failure_count': failure_count,
                    'last_used': stats.get('last_used'),
                    'avg_response_time': stats.get('avg_response_time', 0.0) or 0.0,
                    'status': stats.get('status', 'healthy') or 'healthy',
                    'success_rate': success_count / max(use_count, 1) if use_count > 0 else 0.0
                }
            return result

    def get_connection_pool_info(self) -> Dict[str, Any]:
        """
        获取连接池信息（用于监控）

        Returns:
            连接池信息字典
        """
        with self.lock:
            healthy_count = sum(1 for stats in self.ip_usage_stats.values() if stats.get('status') == 'healthy')
            limited_count = sum(1 for stats in self.ip_usage_stats.values() if stats.get('status') == 'limited')
            failed_count = sum(1 for stats in self.ip_usage_stats.values() if stats.get('status') == 'failed')

            return {
                'total_connections': len(self.connections_list),
                'active_servers': len(self.active_servers),
                'healthy_ips': healthy_count,
                'limited_ips': limited_count,
                'failed_ips': failed_count,
                'ip_stats': self.get_ip_usage_stats()
            }


class TongdaxinStockPlugin(IDataSourcePlugin):
    """通达信股票数据源插件（异步优化版）"""

    def __init__(self):
        # 调用父类初始化（设置plugin_state等基础属性）
        super().__init__()

        self.logger = logger.bind(module=__name__)
        # initialized 和 last_error 已经在父类中定义

        # 默认配置
        self.DEFAULT_CONFIG = {
            'host': '119.147.212.81',  # 通达信服务器地址
            'port': 7709,              # 通达信服务器端口
            'timeout': 15,             # 优化：连接超时时间从30秒减少到15秒，快速失败
            'max_retries': 2,          # 优化：最大重试次数从3减少到2，减少延迟累积
            'cache_duration': 300,     # 缓存持续时间（秒）
            'use_local_data': False,   # 是否使用本地数据文件
            'local_data_path': '',     # 本地数据文件路径
            'auto_select_server': True,  # 是否自动选择最快服务器
            'use_connection_pool': True,  # 是否使用连接池模式
            'connection_pool_size': 20,  # 优化：连接池大小从10增加到20，支持更多并发批次
            'enable_batch_fetch': True,  # 是否启用分批获取（用于超过800条记录的请求）
            'max_batch_count': 10000,    # 分批获取的最大记录数限制（避免无限制请求）
            'enable_parallel_fetch': True,  # 是否启用并发分批获取（显著提升批量下载速度）
        }

        # 联网查询地址配置（endpointhost字段）
        # 只保留真实有效的地址
        self.endpointhost = [
            "https://raw.githubusercontent.com/rainx/pytdx/master/pytdx/config/hosts.py"
        ]
        self.config = self.DEFAULT_CONFIG.copy()

        # 修复：在__init__中初始化max_retries和timeout，确保在initialize()调用前也可用
        # 这些属性可能在_test_connection()等方法中被调用，而_test_connection()可能在initialize()之前被调用
        self.timeout = int(self.DEFAULT_CONFIG.get('timeout', 15))
        self.max_retries = int(self.DEFAULT_CONFIG.get('max_retries', 2))
        self.cache_duration = int(self.DEFAULT_CONFIG.get('cache_duration', 300))

        # 插件基本信息
        self.plugin_id = "data_sources.tongdaxin_plugin"  # 修正plugin_id属性
        self.name = "通达信股票数据源"
        self.version = "1.0.0"
        self.description = "提供A股实时和历史数据，支持上海、深圳交易所，基于pytdx库"
        self.author = "FactorWeave-Quant 开发团队"

        # 插件类型标识
        self.plugin_type = PluginType.DATA_SOURCE_STOCK

        # 线程安全锁
        import threading
        self._server_lock = threading.Lock()

        # 支持的股票市场
        self.supported_markets = {
            'SH': '上海证券交易所',
            'SZ': '深圳证券交易所',
            'BJ': '北京证券交易所'
        }

        # 通达信API客户端（保留兼容性）
        self.api_client = None
        self.connection_lock = threading.RLock()

        # 连接池
        self.connection_pool = None
        self.use_connection_pool = self.DEFAULT_CONFIG['use_connection_pool']  # 从配置读取
        # 确保在未调用 initialize() 前也有安全的连接池大小默认值
        self.connection_pool_size = self.DEFAULT_CONFIG.get('connection_pool_size', 10)

        # 数据缓存
        self._stock_list_cache = None
        self._cache_timestamp = None
        self._cache_duration = 300  # 5分钟缓存

        # 统计信息
        self.request_count = 0
        self.last_error = None
        self.last_success_time = None

        # 通达信服务器列表 - 从数据库加载
        self.server_list = []
        self.current_server = None
        self._servers_initialized = False

        # 先加载默认服务器，确保立即可用
        self._load_default_servers()
        if self.server_list:
            self.current_server = self.server_list[0]
            self.server_index = 0

        # 后台异步初始化服务器（不阻塞UI）
        self._start_background_server_init()

        # 服务器状态管理
        self._server_status_cache = {}  # 服务器状态缓存
        self._last_discovery_time = None
        self._discovery_interval = 300  # 5分钟重新发现一次

        # 连接状态属性
        self.connection_time = None
        self.last_activity = None
        self.last_error = None
        self.last_successful_server = None  # 记住上次成功的服务器
        # 连接池就绪标志（供决策与UI监控使用）
        self.pool_ready = False
        # 注意：self.config 已经在上面设置为 self.DEFAULT_CONFIG.copy()，不需要再次设置为空字典

    @property
    def plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            id="tongdaxin_stock_plugin",
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            supported_asset_types=[AssetType.STOCK_A],
            supported_data_types=[
                DataType.HISTORICAL_KLINE,
                DataType.REAL_TIME_QUOTE,
                DataType.FUNDAMENTAL,
                DataType.TRADE_TICK
            ],
            capabilities={
                "markets": ["SH", "SZ"],
                "frequencies": ["1m", "5m", "15m", "30m", "60m", "D", "W", "M"],
                "real_time_support": True,
                "historical_data": True
            }
        )

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息（方法形式）"""
        return self.plugin_info

    def connect(self, **kwargs) -> bool:
        """连接数据源"""
        try:
            with self.connection_lock:
                if not PYTDX_AVAILABLE:
                    self.last_error = "pytdx库未安装"
                    return False

                if not self.api_client:
                    self.api_client = TdxHq_API()

                # 尝试连接
                if self._ensure_connection():
                    self.last_success_time = datetime.now()
                    return True
                else:
                    return False
        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"连接失败: {e}")
            return False

    def disconnect(self) -> bool:
        """断开连接"""
        try:
            with self.connection_lock:
                if self.api_client:
                    try:
                        self.api_client.disconnect()
                    except Exception:
                        pass  # 忽略断开连接时的错误
                    self.api_client = None
                return True
        except Exception as e:
            self.logger.error(f"断开连接失败: {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        try:
            with self.connection_lock:
                if not self.api_client:
                    return False
                # R247 修复: 连接防抖缓存。导入任务线程池并发高频调用 is_connected(),
                # 每次网络测试 (2 次 get_security_bars 尝试) 耗时约 2 秒,
                # 数千任务并发将形成连接风暴并冲击通达信服务器。
                # 最近 30 秒内验证过连接成功则直接返回 True, 不再重复网络测试。
                if self.last_success_time:
                    elapsed = (datetime.now() - self.last_success_time).total_seconds()
                    if elapsed < 30:
                        return True
                # 简单的连接测试
                return self._test_connection()
        except Exception:
            return False

    def get_connection_info(self):
        """获取连接信息"""
        from core.data_source_extensions import ConnectionInfo
        return ConnectionInfo(
            is_connected=self.is_connected(),
            connection_time=self.connection_time,
            last_activity=self.last_activity,
            connection_params={
                "server_info": f"{self.current_server[0]}:{self.current_server[1]}" if self.current_server else "未连接",
                "timeout": self.timeout  # 修复：使用实例变量，确保配置一致性
            },
            error_message=self.last_error
        )

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        try:
            if asset_type != AssetType.STOCK_A:
                return []

            # 获取股票列表
            stock_df = self.get_stock_list()
            if stock_df is None or stock_df.empty:
                return []

            for col in ('code', 'name', 'market'):
                if col not in stock_df.columns:
                    stock_df[col] = ''

            stock_df['asset_type'] = asset_type.value
            stock_df['currency'] = 'CNY'
            stock_df['exchange'] = stock_df['market']

            asset_list = stock_df[['code', 'name', 'market', 'asset_type', 'currency', 'exchange']].rename(
                columns={'code': 'symbol'}
            ).to_dict('records')

            return asset_list
        except Exception as e:
            self.logger.error(f"获取资产列表失败: {e}")
            return []

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None, adjustment: str = 'none') -> pd.DataFrame:
        """获取K线数据
        
        Args:
            symbol: 股票代码
            freq: 频率
            start_date: 开始日期
            end_date: 结束日期
            count: 数据条数
            adjustment: 复权类型 ('qfq', 'hfq', 'none')
        """
        try:
            # 转换频率参数
            # R292 修复：period_map 补充 '1min'，此前 get_kdata(freq='1min') 因缺键
            # 静默降级为日线，与 get_kline_data(period='1min')（分钟数据）行为不一致。
            # R292 追加：补齐 Period.to_frequency 输出全集的反向键（'weekly'/'monthly'/
            # 'daily'/'5min'/'15min'/'30min'/'60min'），未命中频率由静默默认日线改为
            # logger.warning 提示，避免查询静默降级难排查。
            period_map = {
                "1m": "1min", "1min": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
                "60m": "60min", "1H": "60min", "1h": "60min",
                # R292 修复：补充 DuckDB 频率格式键（1d/1w/1M），
                # 此前 get_kdata(freq='1M') 缺键静默降级为日线，与 get_kline_data 月线行为不一致。
                "D": "daily", "1d": "daily",
                "W": "weekly", "1w": "weekly",
                "M": "monthly", "1M": "monthly",
                # R292 修复：Period.to_frequency 输出全集反向键
                "daily": "daily", "weekly": "weekly", "monthly": "monthly",
                "5min": "5min", "15min": "15min", "30min": "30min", "60min": "60min",
            }
            period = period_map.get(freq)
            if period is None:
                self.logger.warning(f"无法识别的K线频率: {freq!r}，回退为日线（请检查调用方频率参数）")
                period = "daily"

            # 调用现有的get_kline_data方法
            return self.get_kline_data(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=count,
                adjustment=adjustment
            )
        except Exception as e:
            self.logger.error(f"获取K线数据失败: {e}")
            return pd.DataFrame()

    def get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """获取实时行情"""
        try:
            # 调用现有的get_real_time_data方法
            real_time_data = self.get_real_time_data(symbols)

            # 转换为标准格式
            quotes = []
            for symbol, data in real_time_data.items():
                if data and isinstance(data, dict):
                    quote = {
                        "symbol": symbol,
                        "price": data.get('price', 0.0),
                        "change": data.get('change', 0.0),
                        "change_percent": data.get('change_percent', 0.0),
                        "volume": data.get('volume', 0),
                        "timestamp": data.get('timestamp', datetime.now().isoformat())
                    }
                    quotes.append(quote)

            return quotes
        except Exception as e:
            self.logger.error(f"获取实时行情失败: {e}")
            return []

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        return [AssetType.STOCK_A]

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型"""
        return [
            DataType.HISTORICAL_KLINE,
            DataType.REAL_TIME_QUOTE,
            DataType.FUNDAMENTAL,
            DataType.TRADE_TICK,
            DataType.INTRADAY_DATA  # R295-G4 分时数据 (get_minute_time_data)
        ]

    def get_supported_adjustment_types(self) -> List[str]:
        """
        获取支持的复权类型列表

        Returns:
            List[str]: 支持的复权类型 ['qfq', 'hfq', 'none', 'both']
        """
        return ['qfq', 'hfq', 'none', 'both']

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        同步初始化插件（快速，不做网络连接）
        网络测试和连接池初始化已移至 _do_connect() 方法，在后台线程中执行
        """
        try:
            self.plugin_state = PluginLifecycle.INITIALIZING

            if not PYTDX_AVAILABLE:
                raise ImportError("pytdx库未安装")

            if not REQUESTS_AVAILABLE:
                raise ImportError("requests库未安装")

            # 合并配置
            merged = self.DEFAULT_CONFIG.copy()
            merged.update(config or {})
            self.config = merged

            # 配置参数（快速）
            self.timeout = int(self.config.get('timeout', self.DEFAULT_CONFIG['timeout']))
            self.max_retries = int(self.config.get('max_retries', self.DEFAULT_CONFIG['max_retries']))
            self.cache_duration = int(self.config.get('cache_duration', self.DEFAULT_CONFIG['cache_duration']))

            # 连接池配置参数（快速）
            self.use_connection_pool = self.config.get('use_connection_pool', self.DEFAULT_CONFIG['use_connection_pool'])
            self.connection_pool_size = int(self.config.get('connection_pool_size', self.DEFAULT_CONFIG['connection_pool_size']))

            # 服务器配置（快速）
            host = self.config.get('host', self.DEFAULT_CONFIG['host'])
            port = int(self.config.get('port', self.DEFAULT_CONFIG['port']))
            self.current_server = (host, port)

            # 标记初始化完成（不做网络测试和连接池初始化）
            self.initialized = True
            self.plugin_state = PluginLifecycle.INITIALIZED
            logger.info("通达信插件同步初始化完成（<100ms，连接池初始化将在后台进行）")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.plugin_state = PluginLifecycle.FAILED
            logger.error(f"通达信股票数据源插件初始化失败: {e}")
            logger.error(traceback.format_exc())
            return False

    def _do_connect(self) -> bool:
        """
        实际连接逻辑（在后台线程中执行）
        将原来在 initialize() 中的连接池初始化和网络测试移到这里
        """
        try:
            logger.info("通达信插件开始连接测试...")
            
            # 线程安全：获取服务器列表快照
            with self._server_lock:
                server_list_snapshot = list(self.server_list) if self.server_list else []
                current_server_snapshot = self.current_server

            # 初始化连接池或单连接模式（原来在 initialize 中的代码）
            if self.use_connection_pool and server_list_snapshot:
                # 使用连接池模式（耗时操作）
                logger.info(f"开始初始化连接池，池大小: {self.connection_pool_size}")
                self.connection_pool = ConnectionPool(max_connections=self.connection_pool_size)
                self.connection_pool.initialize(server_list_snapshot)
                logger.info(f"连接池初始化完成，池大小: {self.connection_pool_size}")
                # 标记连接池就绪
                self.pool_ready = True

                # 设置成功状态
                self.last_success_time = datetime.now()
                self.plugin_state = PluginLifecycle.CONNECTED
                logger.info("通达信插件(连接池模式)连接成功")
                return True
            else:
                # 传统单连接模式
                # 标记连接池未就绪
                self.pool_ready = False
                if self.config.get('auto_select_server', True):
                    self._select_best_server()

                # 创建API客户端
                self.api_client = TdxHq_API()
                logger.debug(f"API客户端已创建: {self.api_client}")

                # 确保有当前服务器设置
                with self._server_lock:
                    if not self.current_server and self.server_list:
                        self.current_server = self.server_list[0]
                        logger.debug(f"设置默认服务器: {self.current_server}")
                        current_server_snapshot = self.current_server

                # 尝试连接测试（耗时操作）
                logger.debug(f"开始连接测试，目标服务器: {current_server_snapshot}")
                if self._test_connection():
                    logger.info(f"通达信插件连接成功，服务器: {current_server_snapshot}")
                    self.last_success_time = datetime.now()
                    self.plugin_state = PluginLifecycle.CONNECTED
                    return True
                else:
                    logger.warning("⚠️ 通达信插件连接测试失败，但仍可尝试后续操作")
                    self.plugin_state = PluginLifecycle.CONNECTED  # 仍然认为连接成功
                    return True

        except Exception as e:
            self.last_error = str(e)
            self.plugin_state = PluginLifecycle.FAILED
            logger.error(f"❌ 通达信插件连接失败: {e}")
            logger.error(traceback.format_exc())
            return False

    def shutdown(self) -> None:
        """关闭插件"""
        try:
            with self.connection_lock:
                # 关闭连接池
                if self.connection_pool:
                    try:
                        self.connection_pool.close_all()
                        self.connection_pool = None
                        logger.info("连接池已关闭")
                    except Exception as e:
                        logger.error(f"关闭连接池失败: {e}")
                # 重置连接池就绪标志
                self.pool_ready = False

                # 关闭传统单连接
                if self.api_client:
                    try:
                        self.api_client.disconnect()
                    except Exception:
                        pass
                    self.api_client = None

                self.initialized = False
                self._stock_list_cache = None
                logger.info("通达信股票数据源插件关闭成功")

        except Exception as e:
            logger.error(f"通达信股票数据源插件关闭失败: {e}")

    def ensure_pool_populated(self) -> bool:
        """
        确保连接池中存在可用健康连接（用于任务启动前预检/预热）

        Returns:
            bool: 是否确保成功（连接池存在且有>=1条连接）
        """
        try:
            if not self.use_connection_pool:
                logger.debug("未启用连接池模式，跳过ensure_pool_populated")
                self.pool_ready = False
                return False

            # 确保服务器列表存在
            if not getattr(self, 'server_list', None) or len(self.server_list) == 0:
                logger.info("预检：服务器列表为空，重新初始化服务器列表...")
                self._initialize_servers()

            # 如已有连接池，检查是否有连接
            if self.connection_pool:
                try:
                    info = self.connection_pool.get_connection_pool_info()
                    total = int(info.get('total_connections', 0))
                    if total > 0:
                        logger.info(f"预检：连接池已有可用连接（{total}）")
                        self.pool_ready = True
                        return True
                except Exception:
                    pass

            # 构建或重建连接池
            if not hasattr(self, 'connection_pool_size') or not isinstance(self.connection_pool_size, int):
                self.connection_pool_size = self.DEFAULT_CONFIG.get('connection_pool_size', 20)

            logger.info("预检：连接池为空，开始服务器健康检测与池初始化...")
            self.connection_pool = ConnectionPool(max_connections=self.connection_pool_size)
            self.connection_pool.initialize(self.server_list)
            self.pool_ready = True
            logger.info(f"预检：连接池初始化完成，池大小: {self.connection_pool_size}")
            return True

        except Exception as e:
            self.pool_ready = False
            logger.warning(f"预检：连接池填充失败，回退单连接模式：{e}")
            return False

    def _test_single_server(self, server):
        """测试单个服务器的连接性能

        Args:
            server: 服务器元组 (host, port)

        Returns:
            dict: {'server': server, 'response_time': float, 'success': bool}
        """
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # 3秒超时
            result = sock.connect_ex(server)
            sock.close()

            if result == 0:
                response_time = time.time() - start_time
                return {
                    'server': server,
                    'response_time': response_time,
                    'success': True
                }
            else:
                return {
                    'server': server,
                    'response_time': float('inf'),
                    'success': False
                }

        except Exception:
            return {
                'server': server,
                'response_time': float('inf'),
                'success': False
            }

    def _select_best_server(self):
        """选择最快的服务器（多线程并行测试）"""
        try:
            if not self.server_list:
                logger.warning("服务器列表为空")
                return

            best_server = None
            best_time = float('inf')
            successful_servers = []

            # 使用线程池并行测试所有服务器
            max_workers = min(len(self.server_list), 10)  # 最多10个并发线程

            logger.info(f"开始并行测试 {len(self.server_list)} 个服务器 (使用 {max_workers} 个线程)")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有服务器测试任务
                future_to_server = {
                    executor.submit(self._test_single_server, server): server
                    for server in self.server_list
                }

                # 收集结果
                for future in as_completed(future_to_server):
                    try:
                        result = future.result()

                        if result['success']:
                            successful_servers.append(result)
                            logger.debug(f"服务器 {result['server']} 响应时间: {result['response_time']:.3f}s")

                            # 更新最佳服务器
                            if result['response_time'] < best_time:
                                best_time = result['response_time']
                                best_server = result['server']
                        else:
                            logger.debug(f"服务器 {result['server']} 连接失败")

                    except Exception as e:
                        logger.debug(f"测试服务器时发生异常: {e}")

            # 记录测试结果
            logger.info(f"服务器测试完成: 总数 {len(self.server_list)}, 可用 {len(successful_servers)}")

            if best_server:
                self.current_server = best_server
                logger.info(f"选择最快服务器: {best_server}, 响应时间: {best_time:.3f}s")

                # 按响应时间排序所有可用服务器（用于备用）
                successful_servers.sort(key=lambda x: x['response_time'])
                if len(successful_servers) > 1:
                    logger.debug(f"可用服务器排序（按响应时间）:")
                    for i, srv in enumerate(successful_servers[:5]):  # 只显示前5个
                        logger.debug(f"  {i+1}. {srv['server']} - {srv['response_time']:.3f}s")
            else:
                logger.warning("无法连接到任何通达信服务器，使用默认服务器")
                if self.server_list:
                    self.current_server = self.server_list[0]

        except Exception as e:
            logger.error(f"选择服务器失败: {e}")
            # 出错时使用第一个服务器作为默认
            if self.server_list:
                self.current_server = self.server_list[0]

    def _test_connection(self) -> bool:
        """测试连接（借鉴FactorWeave的稳定测试方法）"""
        try:
            with self.connection_lock:
                if not self.api_client:
                    logger.debug("api_client 未初始化")
                    return False

                logger.debug(f"尝试连接服务器: {self.current_server}")

                # 修复：使用配置的重试次数，而不是硬编码
                max_retries = self.max_retries
                for attempt in range(max_retries):
                    try:
                        if self.api_client.connect(*self.current_server):
                            logger.debug("连接建立成功，开始测试数据获取")

                            # 使用更稳定的测试方法：获取股票列表而不是股票数量
                            # 这样可以避免某些服务器返回异常股票数量的问题
                            test_result = self._test_data_access()

                            if test_result:
                                logger.debug("连接测试成功")
                                # R247 修复: 记录成功时间, 供 is_connected() 防抖缓存使用
                                self.last_success_time = datetime.now()
                                return True
                            else:
                                logger.warning(f"数据访问测试失败 (尝试 {attempt + 1}/{max_retries})")
                                self.api_client.disconnect()
                                if attempt < max_retries - 1:
                                    time.sleep(1)  # 短暂等待后重试
                                    continue
                        else:
                            logger.debug(f"连接建立失败 (尝试 {attempt + 1}/{max_retries})")
                            if attempt < max_retries - 1:
                                time.sleep(1)
                                continue
                    except Exception as e:
                        logger.warning(f"连接测试异常 (尝试 {attempt + 1}/{max_retries}): {e}")
                        if attempt < max_retries - 1:
                            time.sleep(1)
                            continue

                logger.debug("所有连接尝试都失败")
                return False

        except Exception as e:
            logger.warning(f"连接测试异常: {e}")
            # 输出更详细的错误信息用于调试
            if "head_buf is not 0x10" in str(e):
                logger.warning("检测到head_buf协议错误，可能是服务器拒绝连接或网络问题")
            elif "timeout" in str(e).lower():
                logger.warning("连接超时，可能是网络延迟或服务器繁忙")
            else:
                logger.warning(f"未知连接错误: {type(e).__name__} - {e}")

        return False

    def _test_data_access(self) -> bool:
        """测试数据访问（借鉴FactorWeave的数据验证方法）"""
        try:
            # 尝试获取一只知名股票的数据来验证连接
            # 使用平安银行(000001)作为测试股票
            test_data = self.api_client.get_security_bars(
                category=9,  # 日线
                market=0,   # 深圳市场
                code='000001',
                start=0,
                count=1
            )

            if test_data and len(test_data) > 0:
                logger.debug("数据访问测试成功")
                return True
            else:
                # 如果深圳市场测试失败，尝试上海市场
                test_data = self.api_client.get_security_bars(
                    category=9,  # 日线
                    market=1,   # 上海市场
                    code='000001',
                    start=0,
                    count=1
                )

                if test_data and len(test_data) > 0:
                    logger.debug("数据访问测试成功（上海市场）")
                    return True
                else:
                    logger.warning("数据访问测试失败")
                    return False

        except Exception as e:
            logger.warning(f"数据访问测试异常: {e}")
            return False

    def _ensure_connection(self) -> bool:
        """确保连接可用 - 增强版（借鉴FactorWeave的稳定连接机制）"""
        try:
            with self.connection_lock:
                if not self.api_client:
                    self.api_client = TdxHq_API()
                # 设置更长的超时时间，提高连接稳定性
                # 注意：pytdx的TdxHq_API可能没有set_timeout方法，这里跳过
                # self.api_client.set_timeout(30)

                # 使用增强连接机制
                return self._connect_with_retry()

        except Exception as e:
            logger.error(f"确保连接失败: {e}")
            # 清理失败的连接
            if self.api_client:
                try:
                    self.api_client.disconnect()
                except Exception:
                    pass
                self.api_client = None
            return False

    def _connect_with_retry(self) -> bool:
        """带重试的连接机制 - 快速失败优化版"""
        # 首先尝试快速连接
        if self._connect_with_fast_fail():
            return True

        # 快速连接失败，使用传统重试机制
        return self._connect_with_traditional_retry()

    def _connect_with_fast_fail(self) -> bool:
        """快速失败连接机制 - 新增优化功能"""
        logger.debug("尝试快速连接机制...")

        # 1. 首先尝试上次成功的服务器
        if hasattr(self, 'last_successful_server') and self.last_successful_server:
            if self._quick_connect_test(self.last_successful_server):
                logger.info(f"快速连接成功（使用缓存服务器）: {self.last_successful_server[0]}:{self.last_successful_server[1]}")
                return True

        # 2. 并行测试前5个最佳服务器
        top_servers = self.server_list[:5]  # 只测试前5个服务器
        available_servers = self._test_servers_parallel(top_servers, max_workers=3, timeout=5)

        if available_servers:
            # 尝试连接最佳服务器
            for server in available_servers[:2]:  # 只尝试前2个最佳服务器
                if self._quick_connect_test(server):
                    self.last_successful_server = server  # 记住成功的服务器
                    logger.info(f"快速连接成功: {server[0]}:{server[1]}")
                    return True

        logger.debug("快速连接机制失败，将使用传统重试")
        return False

    def _quick_connect_test(self, server) -> bool:
        """快速连接测试"""
        try:
            host, port = server
            logger.debug(f"快速连接测试: {host}:{port}")

            # 尝试连接
            if self.api_client.connect(host, port):
                # 简化的连接质量验证（更快）
                if self._quick_validate_connection():
                    self.current_server = server
                    return True
                else:
                    try:
                        self.api_client.disconnect()
                    except Exception:
                        pass
            return False

        except Exception as e:
            logger.debug(f"快速连接测试失败 {host}:{port}: {e}")
            return False

    def _quick_validate_connection(self) -> bool:
        """快速连接质量验证 - 数据访问级验证（R247 修复）

        原实现仅验证 get_security_count(0) > 0, 无法识别"TCP可连但数据不可用"的服务器
        （实测 218.6.170.47:7709 count=23890 但 get_security_bars 返回空）。
        必须使用 get_security_bars 实际取数验证, 与 _test_connection/_test_data_access
        的判定标准保持一致, 避免 connect() 选中取不到数据的服务器。
        """
        try:
            # 双重验证：计数 + 实际取数
            count = self.api_client.get_security_count(0)
            if count is None or count <= 0:
                return False
            test_data = self.api_client.get_security_bars(
                category=9,  # 日线
                market=0,   # 深圳市场
                code='000001',
                start=0,
                count=1
            )
            return bool(test_data)
        except Exception:
            return False

    def _connect_with_traditional_retry(self) -> bool:
        """传统重试连接机制"""
        # 修复：使用配置的重试次数，而不是硬编码
        max_retries = self.max_retries
        retry_delays = [0.5, 1]  # 更短的重试间隔

        for attempt in range(max_retries):
            # 动态获取最佳服务器
            available_servers = self._get_available_servers()

            if not available_servers:
                logger.warning("没有可用的服务器")
                break

            for server in available_servers:
                try:
                    host, port = server
                    logger.debug(f"传统重试连接: {host}:{port}")

                    # 尝试连接
                    if self.api_client.connect(host, port):
                        # 验证连接质量
                        if self._validate_connection_quality():
                            self.current_server = server
                            self.last_successful_server = server  # 记住成功的服务器
                            logger.info(f"TDX连接成功: {host}:{port}")
                            return True
                        else:
                            logger.debug(f"连接质量验证失败: {host}:{port}")
                            try:
                                self.api_client.disconnect()
                            except Exception:
                                pass

                except Exception as e:
                    error_msg = str(e)
                    logger.debug(f"连接失败 {host}:{port}: {error_msg}")

                    # 针对不同错误类型的特殊处理
                    if "head_buf is not 0x10" in error_msg:
                        logger.debug("检测到head_buf错误，可能是协议问题")
                        time.sleep(0.2)  # 减少等待时间
                    elif "timeout" in error_msg.lower():
                        logger.debug("检测到超时错误，跳过此服务器")
                        continue
                    elif "connection refused" in error_msg.lower():
                        logger.debug("连接被拒绝，跳过此服务器")
                        continue

            # 指数退避重试
            if attempt < max_retries - 1:
                delay = retry_delays[min(attempt, len(retry_delays)-1)]
                logger.info(f"第 {attempt+1} 轮连接失败，等待 {delay} 秒后重试...")
                time.sleep(delay)

        logger.error("所有服务器连接尝试均失败")
        return False

    def _get_available_servers(self):
        """获取可用服务器列表（按质量排序）- 优化版本"""
        server_quality = []
        current_time = time.time()
        cache_duration = 60  # 缓存1分钟

        for server in self.server_list:
            server_key = f"{server[0]}:{server[1]}"

            # 检查缓存
            cached_quality = self._server_status_cache.get(server_key)
            if (cached_quality and
                current_time - cached_quality.get('test_time', 0) < cache_duration and
                    cached_quality.get('available', False)):
                # 使用缓存的结果
                server_quality.append((server, cached_quality['response_time']))
                logger.debug(f"使用缓存的服务器状态: {server_key}")
                continue

            # 缓存过期或不存在，重新测试
            quality = self._test_server_quality(server)
            self._server_status_cache[server_key] = quality

            if quality['available']:
                server_quality.append((server, quality['response_time']))
                logger.debug(f"测试服务器: {server_key}, 响应时间: {quality['response_time']:.3f}s")

        # 按响应时间排序
        server_quality.sort(key=lambda x: x[1])
        available_servers = [server for server, _ in server_quality]

        logger.info(f"找到 {len(available_servers)} 个可用服务器")
        return available_servers

    def _test_servers_parallel(self, servers, max_workers=5, timeout=10):
        """并行测试多个服务器 - 新增优化功能"""
        server_quality = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有测试任务
            future_to_server = {
                executor.submit(self._test_server_quality, server): server
                for server in servers
            }

            try:
                # 等待所有任务完成，但有超时限制
                for future in as_completed(future_to_server, timeout=timeout):
                    server = future_to_server[future]
                    try:
                        quality = future.result()
                        server_key = f"{server[0]}:{server[1]}"

                        # 更新缓存
                        self._server_status_cache[server_key] = quality

                        if quality['available']:
                            server_quality.append((server, quality['response_time']))
                            logger.debug(f"并行测试成功: {server_key}, 响应时间: {quality['response_time']:.3f}s")

                    except Exception as e:
                        server_key = f"{server[0]}:{server[1]}"
                        logger.debug(f"并行测试失败: {server_key}, 错误: {e}")

            except concurrent.futures.TimeoutError:
                logger.warning(f"并行服务器测试超时 ({timeout}秒)")

        # 按响应时间排序
        server_quality.sort(key=lambda x: x[1])
        return [server for server, _ in server_quality]

    def _test_server_quality(self, server):
        """测试服务器质量 - 优化版本"""
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)  # 从3秒减少到1.5秒，提高响应速度
            result = sock.connect_ex(server)
            sock.close()

            response_time = time.time() - start_time

            return {
                'available': result == 0,
                'response_time': response_time,
                'test_time': time.time()  # 添加测试时间戳用于缓存
            }
        except Exception as e:
            return {
                'available': False,
                'response_time': float('inf'),
                'test_time': time.time(),
                'error': str(e)
            }

    def _validate_connection_quality(self):
        """验证连接质量（R247 修复：使用数据访问级验证）

        原实现仅验证 get_security_count(0) > 0, 对"TCP可连但数据不可用"的服务器
        （如 218.6.170.47:7709 count=23890 但 get_security_bars 返回空）会误判可用。
        升级为 get_security_bars 实际取数验证, 与 _test_data_access 判定标准一致。
        """
        try:
            count = self.api_client.get_security_count(0)
            if count is None or count <= 0:
                return False
            test_data = self.api_client.get_security_bars(
                category=9,  # 日线
                market=0,   # 深圳市场
                code='000001',
                start=0,
                count=1
            )
            return bool(test_data)
        except Exception as e:
            logger.debug(f"连接质量验证失败: {e}")
            return False

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        start_time = time.time()

        try:
            if not self.initialized:
                return HealthCheckResult(
                    is_healthy=False,
                    message="插件未初始化",
                    response_time_ms=0.0
                )

            # 测试连接
            if self._test_connection():
                response_time = (time.time() - start_time) * 1000
                self.last_success_time = datetime.now()
                return HealthCheckResult(
                    is_healthy=True,
                    message="连接正常",
                    response_time_ms=response_time,
                    extra_info={
                        'server': f"{self.current_server[0]}:{self.current_server[1]}",
                        'request_count': self.request_count
                    }
                )
            else:
                response_time = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    is_healthy=False,
                    message="无法连接到通达信服务器",
                    response_time_ms=response_time,
                    extra_info={
                        'server': f"{self.current_server[0]}:{self.current_server[1]}",
                        'last_success': self.last_success_time.isoformat() if self.last_success_time else None
                    }
                )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            self.last_error = error_msg

            return HealthCheckResult(
                is_healthy=False,
                response_time_ms=response_time,
                message=error_msg
            )

    def _normalize_stock_code(self, symbol: str) -> str:
        """标准化股票代码格式

        通达信需要纯数字格式的股票代码，需要移除sz/sh前缀

        Args:
            symbol: 原始股票代码，如 'sz300110', 'sh000001', '000001'

        Returns:
            标准化后的股票代码，如 '300110', '000001'
        """
        if not symbol:
            return symbol

        # 转换为小写进行处理
        symbol_lower = symbol.lower()

        # 移除sz/sh前缀
        if symbol_lower.startswith('sz'):
            return symbol[2:]
        elif symbol_lower.startswith('sh'):
            return symbol[2:]

        # 如果没有前缀，直接返回
        return symbol

    def _convert_symbol_to_tdx_format(self, symbol: str) -> tuple:
        """将股票代码转换为通达信格式"""
        try:
            # 先标准化股票代码格式
            normalized_symbol = self._normalize_stock_code(symbol)
            self.logger.info(f"股票代码标准化: {symbol} -> {normalized_symbol}")

            if '.' in normalized_symbol:
                code, exchange = normalized_symbol.split('.')
                if exchange.upper() == 'SH':
                    return (1, code)  # 上海市场
                elif exchange.upper() == 'SZ':
                    return (0, code)  # 深圳市场
            else:
                # 根据代码前缀判断市场
                if normalized_symbol.startswith(('60', '68', '11', '12', '13', '18')):
                    return (1, normalized_symbol)  # 上海
                else:
                    return (0, normalized_symbol)  # 深圳

        except Exception:
            return (0, normalized_symbol if 'normalized_symbol' in locals() else symbol)  # 默认深圳

    def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表 - 只返回A股股票"""
        try:
            # 检查缓存
            current_time = time.time()
            if (self._stock_list_cache is not None and
                self._cache_timestamp and
                    current_time - self._cache_timestamp < self._cache_duration):
                return self._stock_list_cache

            if not self._ensure_connection():
                logger.error("无法连接到通达信服务器")
                return pd.DataFrame()

            stock_list = []
            total_sh_count = 0
            total_sz_count = 0
            filtered_sh_count = 0
            filtered_sz_count = 0
            sh_code_samples = []
            sz_code_samples = []

            # 添加详细的统计信息
            sh_prefix_stats = {}
            sz_prefix_stats = {}
            sh_filtered_prefix_stats = {}
            sz_filtered_prefix_stats = {}

            with self.connection_lock:
                # 获取上海市场股票
                try:
                    sh_count = self.api_client.get_security_count(1)
                    logger.info(f"上海市场证券总数: {sh_count}")

                    if sh_count and sh_count > 0:
                        # 移除10000限制，支持获取所有数据
                        for start in range(0, sh_count, 1000):
                            sh_stocks = self.api_client.get_security_list(1, start)
                            if sh_stocks:
                                for stock in sh_stocks:
                                    total_sh_count += 1
                                    code = str(stock['code']).strip()

                                    # 统计代码前缀分布
                                    if len(code) >= 3:
                                        prefix = code[:3]
                                        sh_prefix_stats[prefix] = sh_prefix_stats.get(prefix, 0) + 1

                                    # 只保留A股股票
                                    if self._is_a_stock(code, 'SH'):
                                        filtered_sh_count += 1
                                        stock_list.append({
                                            'code': code,
                                            'name': stock['name'],
                                            'market': 'SH'
                                        })

                                        # 统计过滤后的代码前缀分布
                                        if len(code) >= 3:
                                            prefix = code[:3]
                                            sh_filtered_prefix_stats[prefix] = sh_filtered_prefix_stats.get(prefix, 0) + 1

                                        # 收集A股样本数据用于调试
                                        if len(sh_code_samples) < 20:
                                            sh_code_samples.append(f"{code}:{stock['name']}")
                except Exception as e:
                    logger.error(f"获取上海市场数据失败: {e}")

                # 获取深圳市场股票
                try:
                    sz_count = self.api_client.get_security_count(0)
                    logger.info(f"深圳市场证券总数: {sz_count}")

                    if sz_count and sz_count > 0:
                        # 移除10000限制，支持获取所有数据
                        for start in range(0, sz_count, 1000):
                            sz_stocks = self.api_client.get_security_list(0, start)
                            if sz_stocks:
                                for stock in sz_stocks:
                                    total_sz_count += 1
                                    code = str(stock['code']).strip()

                                    # 统计代码前缀分布
                                    if len(code) >= 3:
                                        prefix = code[:3]
                                        sz_prefix_stats[prefix] = sz_prefix_stats.get(prefix, 0) + 1

                                    # 只保留A股股票
                                    if self._is_a_stock(code, 'SZ'):
                                        filtered_sz_count += 1
                                        stock_list.append({
                                            'code': code,
                                            'name': stock['name'],
                                            'market': 'SZ'
                                        })

                                        # 统计过滤后的代码前缀分布
                                        if len(code) >= 3:
                                            prefix = code[:3]
                                            sz_filtered_prefix_stats[prefix] = sz_filtered_prefix_stats.get(prefix, 0) + 1

                                        # 收集A股样本数据用于调试
                                        if len(sz_code_samples) < 20:
                                            sz_code_samples.append(f"{code}:{stock['name']}")
                except Exception as e:
                    logger.error(f"获取深圳市场数据失败: {e}")

                self.api_client.disconnect()

            # 详细的统计日志
            logger.info(f"数据统计: SH原始={total_sh_count}, 过滤后={filtered_sh_count}, SZ原始={total_sz_count}, 过滤后={filtered_sz_count}")
            logger.info(f"SH A股样本数据: {sh_code_samples[:10]}")
            logger.info(f"SZ A股样本数据: {sz_code_samples[:10]}")

            # 代码前缀分布统计
            logger.info(f"SH原始代码前缀分布 (前10): {dict(sorted(sh_prefix_stats.items(), key=lambda x: x[1], reverse=True)[:10])}")
            logger.info(f"SH过滤后代码前缀分布: {sh_filtered_prefix_stats}")
            logger.info(f"SZ原始代码前缀分布 (前10): {dict(sorted(sz_prefix_stats.items(), key=lambda x: x[1], reverse=True)[:10])}")
            logger.info(f"SZ过滤后代码前缀分布: {sz_filtered_prefix_stats}")

            # 分析被过滤的代码段
            sh_filtered_out = {}
            sz_filtered_out = {}

            for prefix, count in sh_prefix_stats.items():
                if prefix not in sh_filtered_prefix_stats:
                    sh_filtered_out[prefix] = count
                elif sh_filtered_prefix_stats[prefix] < count:
                    sh_filtered_out[prefix] = count - sh_filtered_prefix_stats[prefix]

            for prefix, count in sz_prefix_stats.items():
                if prefix not in sz_filtered_prefix_stats:
                    sz_filtered_out[prefix] = count
                elif sz_filtered_prefix_stats[prefix] < count:
                    sz_filtered_out[prefix] = count - sz_filtered_prefix_stats[prefix]

            if sh_filtered_out:
                logger.info(f"SH被过滤的代码段: {sh_filtered_out}")
            if sz_filtered_out:
                logger.info(f"SZ被过滤的代码段: {sz_filtered_out}")

            if stock_list:
                df = pd.DataFrame(stock_list)
                # 去重处理
                df = df.drop_duplicates(subset=['code'], keep='first')

                # 缓存数据
                self._stock_list_cache = df
                self._cache_timestamp = current_time
                self.request_count += 1
                logger.info(f"获取A股股票列表成功，共 {len(df)} 只股票")
                return df
            else:
                logger.warning("获取股票列表为空")
                return pd.DataFrame()

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取股票列表失败: {e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def _is_a_stock(self, code: str, market: str) -> bool:
        """判断是否为A股股票 - 扩展版本

        Args:
            code: 股票代码
            market: 市场代码 ('SH' 或 'SZ')

        Returns:
            bool: 是否为A股股票
        """
        code = str(code).strip()

        # 如果代码长度不足3位，直接返回False
        if len(code) < 3:
            return False

        # 提取前3位作为主要判断依据
        prefix = code[:3]

        if market == 'SH':
            # 上海A股：600xxx(主板), 601xxx(主板), 603xxx(主板), 605xxx(主板), 688xxx(科创板)
            # 扩展：689xxx(科创板), 可能还有其他A股代码段
            return prefix in ('600', '601', '603', '605', '688', '689')
        elif market == 'SZ':
            # 深圳A股：000xxx(主板), 002xxx(中小板), 003xxx(主板), 300xxx(创业板)
            # 扩展：001xxx(主板), 004xxx(主板), 可能还有其他A股代码段
            return prefix in ('000', '001', '002', '003', '004', '300')

        return False

    def get_kline_data(self, symbol: str, period: str = 'daily',
                       start_date: str = None, end_date: str = None,
                       count: int = 800, adjustment: str = 'none') -> pd.DataFrame:
        """
        获取K线数据 - 增强版本

        Args:
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            count: 数据条数
            adjustment: 复权类型 ('qfq', 'hfq', 'none')

        改进点：
        1. 更强的数据验证和清洗
        2. 更好的时间格式处理
        3. 数据类型转换和验证
        4. 异常数据过滤
        5. 更详细的日志记录
        6. 增强的错误处理和重试机制
        7. 修复日期过滤逻辑，避免过度过滤导致数据为空
        8. 支持复权参数（注：pytdx原生不支持复权，数据存储后由系统计算）
        """
        # 线程安全：获取服务器列表的快照
        with self._server_lock:
            server_list_snapshot = list(self.server_list) if self.server_list else []
            current_server_snapshot = self.current_server
        
        # 检查服务器列表是否可用
        if not server_list_snapshot:
            logger.warning("服务器列表为空，无法获取数据")
            return pd.DataFrame()
        
        # 修复：使用配置的重试次数，而不是硬编码
        max_retries = self.max_retries
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                market, code = self._convert_symbol_to_tdx_format(symbol)

                # 通达信周期映射
                period_mapping = {
                    '1min': 8,    # 1分钟
                    '5min': 0,    # 5分钟
                    '15min': 1,   # 15分钟
                    '30min': 2,   # 30分钟
                    '60min': 3,   # 60分钟
                    '1hour': 3,   # 60分钟（兼容直接调用入口，防止静默降级为日线）
                    'daily': 9,   # 日线
                    'weekly': 5,  # 周线
                    'monthly': 6  # 月线
                }

                frequency = period_mapping.get(period, 9)  # 默认日线

                # 关键修复：pytdx不支持日期范围查询，只支持count
                # 当提供了日期范围时，不在API层面传递，而是在返回后过滤
                logger.debug(f"请求参数: symbol={symbol}, start_date={start_date}, end_date={end_date}, count={count}")

                # 必须走连接池模式：若启用连接池则确保连接池已准备
                if self.use_connection_pool:
                    if not self.connection_pool or not self.pool_ready:
                        # 尝试预热与填充连接池
                        ok = False
                        try:
                            if hasattr(self, 'ensure_pool_populated'):
                                ok = bool(self.ensure_pool_populated())
                        except Exception as pool_err:
                            logger.warning(f"确保连接池可用失败: {pool_err}")
                            ok = False
                        if not ok and server_list_snapshot:
                            # 兜底一次直接初始化
                            try:
                                if not hasattr(self, 'connection_pool_size') or not isinstance(self.connection_pool_size, int):
                                    self.connection_pool_size = self.DEFAULT_CONFIG.get('connection_pool_size', 10)
                                logger.info("直接初始化连接池作为兜底...")
                                self.connection_pool = ConnectionPool(max_connections=self.connection_pool_size)
                                self.connection_pool.initialize(server_list_snapshot)
                                self.pool_ready = True
                                logger.info(f"兜底初始化连接池完成，池大小: {self.connection_pool_size}")
                            except Exception as pool_err2:
                                self.pool_ready = False
                                logger.warning(f"兜底初始化连接池失败，将回退单连接: {pool_err2}")

                # 基于日期范围估算需求量，作为策略决策的参考
                effective_count = count
                try:
                    if start_date and end_date:
                        sd = pd.to_datetime(start_date)
                        ed = pd.to_datetime(end_date)
                        if pd.notna(sd) and pd.notna(ed) and ed > sd:
                            days = (ed - sd).days + 1
                            if period == 'daily':
                                est = days
                            elif period == 'weekly':
                                est = max(1, days // 5)
                            elif period == 'monthly':
                                est = max(1, days // 22)
                            elif period in ('60min', '30min', '15min', '5min', '1min'):
                                minute_map = {'60min': 4, '30min': 8, '15min': 16, '5min': 48, '1min': 240}
                                est = max(1, (days * minute_map.get(period, 4)))
                            else:
                                est = days
                            max_batch_count = self.config.get('max_batch_count', 10000)
                            effective_count = max(count, min(est, max_batch_count))
                            logger.debug(f"估算条数: {est} → 决策用有效count={effective_count}")
                except Exception as est_err:
                    logger.debug(f"估算条数失败，使用原始count: {est_err}")

                # 重要限制：pytdx API单次请求最多返回800条记录
                # 如果请求的count超过800，使用分批获取
                MAX_COUNT_PER_REQUEST = 800
                enable_batch_fetch = self.config.get('enable_batch_fetch', True)
                max_batch_count = self.config.get('max_batch_count', 10000)

                # 限制最大请求数量
                if effective_count > max_batch_count:
                    logger.warning(f"请求count={effective_count}超过最大限制({max_batch_count})，自动调整为{max_batch_count}")
                    effective_count = max_batch_count

                if effective_count > MAX_COUNT_PER_REQUEST and enable_batch_fetch:
                    # 检查是否启用并发分批获取
                    enable_parallel = self.config.get('enable_parallel_fetch', True)

                    if enable_parallel and self.use_connection_pool and self.connection_pool:
                        logger.info(f"请求count={effective_count}超过pytdx单次限制({MAX_COUNT_PER_REQUEST})，启用并发分批获取模式")
                        # 使用并发分批获取方法（多IP同时工作）
                        df = self._fetch_kline_data_in_batches_parallel(
                            symbol=symbol,
                            market=market,
                            code=code,
                            frequency=frequency,
                            period=period,
                            total_count=effective_count,
                            start_date=start_date,
                            end_date=end_date
                        )
                        return df
                    else:
                        logger.info(f"请求count={effective_count}超过pytdx单次限制({MAX_COUNT_PER_REQUEST})，启用串行分批获取模式")
                        # 使用串行分批获取方法
                        df = self._fetch_kline_data_in_batches(
                            symbol=symbol,
                            market=market,
                            code=code,
                            frequency=frequency,
                            period=period,
                            total_count=effective_count,
                            start_date=start_date,
                            end_date=end_date
                        )
                        return df
                elif effective_count > MAX_COUNT_PER_REQUEST:
                    logger.warning(f"请求count={effective_count}超过pytdx单次限制({MAX_COUNT_PER_REQUEST})，分批获取已禁用，自动调整为{MAX_COUNT_PER_REQUEST}")
                    effective_count = MAX_COUNT_PER_REQUEST

                # 使用连接池（强制优先）或退化单连接
                if self.use_connection_pool and self.connection_pool:
                    # 连接池模式
                    with self.connection_pool.get_connection() as api_client:
                        data = api_client.get_security_bars(
                            category=frequency,
                            market=market,
                            code=code,
                            start=0,
                            count=effective_count
                        )
                else:
                    # 传统单连接模式
                    if not self._ensure_connection():
                        logger.error("无法连接到通达信服务器")
                        return pd.DataFrame()

                    with self.connection_lock:
                        data = self.api_client.get_security_bars(
                            category=frequency,
                            market=market,
                            code=code,
                            start=0,
                            count=effective_count
                        )
                        self.api_client.disconnect()

                if data and len(data) > 0:
                    df = pd.DataFrame(data)
                    logger.debug(f"原始数据: {symbol}, 条数: {len(df)}, 列: {df.columns.tolist()}")

                    # 增强的数据处理和验证
                    df = self._process_and_validate_kline_data(df, symbol, period)

                    if not df.empty:
                        # 修复：智能日期过滤逻辑
                        # 只有当明确指定了日期范围且该范围是历史范围时才进行过滤
                        # 如果日期范围跨越"今天"或未来，则不过滤（因为pytdx只返回历史数据）
                        if start_date or end_date:
                            df = self._smart_filter_by_date_range(df, start_date, end_date, symbol)

                        # 添加复权类型标识
                        df['adj_type'] = adjustment
                        df['adj_source'] = 'plugin' if adjustment != 'none' else 'none'
                        
                        self.request_count += 1
                        logger.info(f"获取 {symbol} K线数据成功，周期: {period}, 共 {len(df)} 条记录，复权类型: {adjustment}")
                        return df
                    else:
                        logger.warning(f"数据处理后为空: {symbol}")
                        return pd.DataFrame()
                else:
                    logger.warning(f"获取 {symbol} K线数据为空")
                    return pd.DataFrame()

            except Exception as e:
                self.last_error = str(e)
                logger.error(f"获取K线数据失败 {symbol} (尝试 {attempt + 1}/{max_retries}): {e}")

                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # 指数退避
                else:
                    logger.error(traceback.format_exc())
                    return pd.DataFrame()

        # 如果所有重试都失败，返回空DataFrame
        logger.error(f"获取K线数据失败 {symbol}: 所有重试尝试均失败")
        return pd.DataFrame()

    def _fetch_single_batch(self, symbol: str, market: int, code: str,
                            frequency: int, start_pos: int, batch_size: int,
                            batch_num: int) -> tuple:
        """
        获取单批数据（用于并发调用）

        Args:
            symbol: 股票代码
            market: 市场代码
            code: 通达信格式代码
            frequency: 数据频率
            start_pos: 起始位置
            batch_size: 批次大小
            batch_num: 批次编号

        Returns:
            (batch_num, batch_data, actual_count) 元组
        """
        try:
            if self.use_connection_pool and self.connection_pool:
                with self.connection_pool.get_connection() as api_client:
                    batch_data = api_client.get_security_bars(
                        category=frequency,
                        market=market,
                        code=code,
                        start=start_pos,
                        count=batch_size
                    )
            else:
                if not self._ensure_connection():
                    logger.error(f"[并发批次{batch_num}] {symbol} 连接失败")
                    return (batch_num, None, 0)

                with self.connection_lock:
                    batch_data = self.api_client.get_security_bars(
                        category=frequency,
                        market=market,
                        code=code,
                        start=start_pos,
                        count=batch_size
                    )

            actual_count = len(batch_data) if batch_data else 0
            return (batch_num, batch_data, actual_count)

        except Exception as e:
            logger.error(f"[并发批次{batch_num}] {symbol} 获取失败: {e}")
            return (batch_num, None, 0)

    def _fetch_kline_data_in_batches_parallel(self, symbol: str, market: int, code: str,
                                              frequency: int, period: str, total_count: int,
                                              start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        并发分批获取K线数据（多IP同时工作，显著提升速度）

        通过ThreadPoolExecutor实现真正的并发，充分利用IP池的多个连接

        Args:
            symbol: 股票代码
            market: 市场代码
            code: 通达信格式代码
            frequency: 数据频率
            period: 周期
            total_count: 总共需要的记录数
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            合并后的DataFrame
        """
        MAX_COUNT_PER_REQUEST = 790

        # 并发模式必须确保连接池可用
        if self.use_connection_pool and (not self.connection_pool or not self.pool_ready):
            try:
                if hasattr(self, 'ensure_pool_populated'):
                    ok = bool(self.ensure_pool_populated())
                else:
                    ok = False
                if not ok:
                    logger.warning("[并发分批] 连接池未就绪且预热失败，将无法使用多IP连接池")
            except Exception as e:
                logger.warning(f"[并发分批] 连接池预热异常: {e}")
        if self.use_connection_pool and not self.connection_pool:
            logger.warning("[并发分批] 无连接池实例，回退空结果以避免误判")
            return pd.DataFrame()

        # 计算需要多少批次
        num_batches = (total_count + MAX_COUNT_PER_REQUEST - 1) // MAX_COUNT_PER_REQUEST

        logger.info(f"[并发分批] {symbol} 开始并发分批获取K线数据，目标: {total_count}条，分{num_batches}批")

        try:
            # 优化：增加并发工作线程数，充分利用连接池
            # 如果连接池大小足够，使用连接池大小；否则使用min(连接池大小, 批次数)
            base_workers = self.connection_pool_size if self.use_connection_pool else 3
            # 如果批次数很多，允许超过连接池大小（连接池会自动创建临时连接）
            max_workers = min(base_workers * 2 if num_batches > base_workers else base_workers, num_batches, 30)  # 最多30个并发

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有批次任务
                futures = []
                for batch_num in range(num_batches):
                    start_pos = batch_num * MAX_COUNT_PER_REQUEST
                    batch_size = min(MAX_COUNT_PER_REQUEST, total_count - start_pos)

                    future = executor.submit(
                        self._fetch_single_batch,
                        symbol, market, code, frequency,
                        start_pos, batch_size, batch_num + 1
                    )
                    futures.append(future)

                # 优化：使用as_completed异步处理结果，避免顺序等待，提升并发效率
                # 创建future到batch_num的映射，以便在失败时也能知道是哪个批次
                future_to_batch = {futures[i]: i + 1 for i in range(len(futures))}
                batch_results_dict = {}  # 使用字典存储结果，key为batch_num
                completed_count = 0
                total_batches = len(futures)

                # 使用as_completed异步处理，完成一个处理一个
                try:
                    for future in as_completed(futures, timeout=60):  # 优化：总体超时从30秒增加到60秒，但使用异步处理
                        batch_num = future_to_batch.get(future, completed_count + 1)
                        try:
                            result = future.result()  # 不再需要单独的超时，因为as_completed已有超时
                            batch_results_dict[batch_num] = result
                            completed_count += 1
                            logger.debug(f"[并发分批] {symbol} 第{batch_num}批完成 ({completed_count}/{total_batches})")
                        except Exception as e:
                            logger.error(f"[并发分批] {symbol} 第{batch_num}批次执行失败: {e}")
                            # 记录失败批次
                            batch_results_dict[batch_num] = (batch_num, None, 0)
                            completed_count += 1
                except concurrent.futures.TimeoutError:
                    logger.warning(f"[并发分批] {symbol} 并发批次处理超时（60秒），已完成 {completed_count}/{total_batches} 批次")

                # 按batch_num排序，转换为列表
                batch_results = [batch_results_dict.get(i, (i, None, 0)) for i in range(1, total_batches + 1)]

            # 合并所有数据
            all_data = []
            total_fetched = 0
            for batch_num, batch_data, actual_count in batch_results:
                if batch_data and actual_count > 0:
                    all_data.extend(batch_data)
                    total_fetched += actual_count
                elif batch_num > 0:  # 批次编号>0表示是有效批次
                    # 某批次返回空数据，可能已达历史边界
                    logger.info(f"[并发分批] {symbol} 第{batch_num}批返回空数据，可能已达历史数据边界")
                    break

            logger.info(f"[并发分批] {symbol} 并发获取完成，共{total_fetched}条记录（{len(batch_results)}批）")

            if all_data:
                df = pd.DataFrame(all_data)

                # 数据处理和验证
                df = self._process_and_validate_kline_data(df, symbol, period)

                if not df.empty:
                    # 应用日期过滤
                    if start_date or end_date:
                        df = self._smart_filter_by_date_range(df, start_date, end_date, symbol)

                    self.request_count += len(batch_results)
                    logger.info(f"[并发分批] {symbol} 处理后共{len(df)}条有效记录")
                    return df
                else:
                    logger.warning(f"[并发分批] {symbol} 数据处理后为空")
                    return pd.DataFrame()
            else:
                logger.warning(f"[并发分批] {symbol} 未获取到任何数据")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"[并发分批] {symbol} 发生错误: {e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def _fetch_kline_data_in_batches(self, symbol: str, market: int, code: str,
                                     frequency: int, period: str, total_count: int,
                                     start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        分批获取K线数据（串行模式，用于超过800条记录的请求）

        pytdx API限制：单次请求最多返回800条记录
        通过多次请求（修改start参数）来获取更多历史数据

        注意：这是串行版本，如果需要更快的速度，使用 _fetch_kline_data_in_batches_parallel

        Args:
            symbol: 股票代码
            market: 市场代码
            code: 通达信格式代码
            frequency: 数据频率
            period: 周期
            total_count: 总共需要的记录数
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            合并后的DataFrame
        """
        MAX_COUNT_PER_REQUEST = 800
        all_data = []
        fetched_count = 0
        batch_num = 0

        logger.info(f"[串行分批] {symbol} 开始串行分批获取K线数据，目标总数: {total_count}")

        try:
            while fetched_count < total_count:
                batch_num += 1
                # 计算本次要获取的数量
                current_batch_size = min(MAX_COUNT_PER_REQUEST, total_count - fetched_count)

                logger.debug(f"[串行分批] {symbol} 第{batch_num}批，start={fetched_count}, count={current_batch_size}")

                # 获取数据
                if self.use_connection_pool and self.connection_pool:
                    with self.connection_pool.get_connection() as api_client:
                        batch_data = api_client.get_security_bars(
                            category=frequency,
                            market=market,
                            code=code,
                            start=fetched_count,  # pytdx的start参数表示跳过的记录数
                            count=current_batch_size
                        )
                else:
                    if not self._ensure_connection():
                        logger.error(f"[串行分批] {symbol} 第{batch_num}批连接失败")
                        break

                    with self.connection_lock:
                        batch_data = self.api_client.get_security_bars(
                            category=frequency,
                            market=market,
                            code=code,
                            start=fetched_count,
                            count=current_batch_size
                        )

                # 检查返回数据
                if not batch_data or len(batch_data) == 0:
                    logger.info(f"[串行分批] {symbol} 第{batch_num}批返回空数据，可能已达到历史数据边界，停止获取")
                    break

                actual_count = len(batch_data)
                all_data.extend(batch_data)
                fetched_count += actual_count

                logger.info(f"[串行分批] {symbol} 第{batch_num}批获取成功: {actual_count}条，累计: {fetched_count}/{total_count}")

                # 如果返回的数据少于请求的数量，说明已经到达历史数据的尽头
                if actual_count < current_batch_size:
                    logger.info(f"[串行分批] {symbol} 已获取所有可用历史数据，停止获取")
                    break

                # IP池模式延迟更短
                delay = 0.01 if self.use_connection_pool else 0.1
                time.sleep(delay)

            # 合并所有数据
            if all_data:
                df = pd.DataFrame(all_data)
                logger.info(f"[分批获取] {symbol} 完成，共获取{len(df)}条记录（{batch_num}批）")

                # 数据处理和验证
                df = self._process_and_validate_kline_data(df, symbol, period)

                if not df.empty:
                    # 应用日期过滤
                    if start_date or end_date:
                        df = self._smart_filter_by_date_range(df, start_date, end_date, symbol)

                    self.request_count += batch_num
                    logger.info(f"[分批获取] {symbol} 处理后共{len(df)}条有效记录")
                    return df
                else:
                    logger.warning(f"[分批获取] {symbol} 数据处理后为空")
                    return pd.DataFrame()
            else:
                logger.warning(f"[分批获取] {symbol} 未获取到任何数据")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"[分批获取] {symbol} 发生错误: {e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def _process_and_validate_kline_data(self, df: pd.DataFrame, symbol: str, period: str) -> pd.DataFrame:
        """
        处理和验证K线数据

        Args:
            df: 原始DataFrame
            symbol: 股票代码
            period: 周期

        Returns:
            处理后的DataFrame
        """
        try:
            if df.empty:
                return df

            original_count = len(df)
            logger.debug(f"开始处理K线数据: {symbol}, 原始记录数: {original_count}")

            # 1. 基础数据验证和清洗
            df = self._basic_data_validation(df)
            if df.empty:
                logger.warning(f"基础验证后数据为空: {symbol}")
                return df

            # 2. 时间格式处理
            df = self._process_datetime_column(df, symbol)
            if df.empty:
                logger.warning(f"时间处理后数据为空: {symbol}")
                return df

            # 3. 数值列处理和验证
            df = self._process_numeric_columns(df, symbol)
            if df.empty:
                logger.warning(f"数值处理后数据为空: {symbol}")
                return df

            # 4. 数据完整性验证
            df = self._validate_data_integrity(df, symbol)
            if df.empty:
                logger.warning(f"完整性验证后数据为空: {symbol}")
                return df

            # 5. 最终格式化
            df = self._finalize_dataframe_format(df)

            processed_count = len(df)
            logger.debug(f"数据处理完成: {symbol}, 处理后记录数: {processed_count}, 过滤掉: {original_count - processed_count}")

            return df

        except Exception as e:
            logger.error(f"数据处理失败 {symbol}: {e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def _basic_data_validation(self, df: pd.DataFrame) -> pd.DataFrame:
        """基础数据验证和清洗"""
        try:
            # 删除完全空的行
            df = df.dropna(how='all')

            # 检查必需列是否存在
            required_base_columns = ['datetime']
            missing_columns = [col for col in required_base_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"缺少必需列: {missing_columns}")
                return pd.DataFrame()

            # 删除datetime为空的行
            df = df[df['datetime'].notna()]

            return df

        except Exception as e:
            logger.error(f"基础数据验证失败: {e}")
            return pd.DataFrame()

    def _process_datetime_column(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """处理时间列"""
        try:
            # 检查是否存在datetime列
            if 'datetime' not in df.columns:
                logger.warning(f"数据中不存在datetime列: {symbol}, 列名: {df.columns.tolist()}")
                return pd.DataFrame()

            # 检查是否有数据
            if df.empty or df['datetime'].isna().all():
                logger.warning(f"datetime列数据为空: {symbol}")
                return pd.DataFrame()

            # 记录原始数据样本用于调试
            sample_data = df['datetime'].head(3).tolist()
            logger.debug(f"原始datetime数据样本 {symbol}: {sample_data}")

            # 过滤明显无效的时间数据
            invalid_patterns = ['0-00-00', '1900-01-01', '2099-12-31']
            for pattern in invalid_patterns:
                if df['datetime'].dtype == 'object':
                    df = df[~df['datetime'].astype(str).str.contains(pattern, na=False)]

            # 转换时间格式，支持多种格式
            datetime_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%Y%m%d %H%M%S',
                '%Y%m%d',
                None  # pandas自动推断
            ]

            converted = False
            best_success_rate = 0
            for fmt in datetime_formats:
                try:
                    if fmt is None:
                        df_temp = df.copy()
                        df_temp['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                    else:
                        df_temp = df.copy()
                        df_temp['datetime'] = pd.to_datetime(df['datetime'], format=fmt, errors='coerce')

                    # 检查转换成功率
                    valid_count = df_temp['datetime'].notna().sum()
                    total_count = len(df_temp)
                    success_rate = valid_count / total_count if total_count > 0 else 0

                    if success_rate > best_success_rate:
                        best_success_rate = success_rate

                    if success_rate > 0.5:  # 降低阈值到50%以提高兼容性
                        df = df_temp
                        converted = True
                        logger.debug(f"时间格式转换成功: {symbol}, 格式: {fmt}, 成功率: {success_rate:.2%}")
                        break

                except Exception as e:
                    logger.debug(f"尝试格式 {fmt} 失败: {e}")
                    continue

            if not converted:
                logger.error(f"时间格式转换失败: {symbol}, 最佳成功率: {best_success_rate:.2%}, 样本数据: {sample_data[:2]}")
                return pd.DataFrame()

            # 删除时间转换失败的行
            df = df.dropna(subset=['datetime'])

            # 验证时间范围合理性 (1990-2030)
            min_date = pd.Timestamp('1990-01-01')
            max_date = pd.Timestamp('2030-12-31')
            df = df[(df['datetime'] >= min_date) & (df['datetime'] <= max_date)]

            if df.empty:
                logger.warning(f"时间范围验证后数据为空: {symbol}")
                return df

            return df

        except Exception as e:
            logger.error(f"时间处理失败: {e}")
            return pd.DataFrame()

    def _process_numeric_columns(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """处理数值列"""
        try:
            # 标准化列名
            column_mapping = {
                'vol': 'volume',
                'amount': 'amount',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close'
            }

            df = df.rename(columns=column_mapping)

            # 定义数值列及其默认值
            numeric_columns = {
                'open': 0.0,
                'high': 0.0,
                'low': 0.0,
                'close': 0.0,
                'volume': 0,
                'amount': 0.0
            }

            # 确保所有必需的数值列存在
            for col, default_val in numeric_columns.items():
                if col not in df.columns:
                    df[col] = default_val
                    logger.debug(f"添加缺失列 {col} 默认值: {default_val}")

            # 转换数值类型并处理异常值
            for col, default_val in numeric_columns.items():
                try:
                    # 转换为数值类型
                    df[col] = pd.to_numeric(df[col], errors='coerce')

                    # 填充NaN值
                    df[col] = df[col].fillna(default_val)

                    # 处理负值（除了amount可能为负）
                    if col != 'amount':
                        df.loc[df[col] < 0, col] = default_val

                    # 处理异常大的值（可能是数据错误）
                    if col in ['open', 'high', 'low', 'close']:
                        # 价格异常值检测（超过10000元的股票价格可能有问题）
                        df.loc[df[col] > 10000, col] = default_val
                    elif col == 'volume':
                        # 成交量异常值检测
                        df.loc[df[col] > 1e12, col] = default_val  # 1万亿股
                    elif col == 'amount':
                        # 成交额异常值检测
                        df.loc[df[col] > 1e15, col] = default_val  # 1千万亿元

                except Exception as e:
                    logger.warning(f"处理数值列 {col} 失败: {e}")
                    df[col] = default_val

            return df

        except Exception as e:
            logger.error(f"数值列处理失败: {e}")
            return pd.DataFrame()

    def _validate_data_integrity(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """验证数据完整性"""
        try:
            original_count = len(df)

            # 1. OHLC数据逻辑验证
            # high >= max(open, close) and low <= min(open, close)
            valid_ohlc = (
                (df['high'] >= df[['open', 'close']].max(axis=1)) &
                (df['low'] <= df[['open', 'close']].min(axis=1)) &
                (df['high'] >= df['low'])  # high >= low
            )

            invalid_ohlc_count = (~valid_ohlc).sum()
            if invalid_ohlc_count > 0:
                logger.warning(f"发现 {invalid_ohlc_count} 条OHLC逻辑错误数据: {symbol}")
                # 修复而不是删除
                df.loc[~valid_ohlc, 'high'] = df.loc[~valid_ohlc, ['open', 'close']].max(axis=1)
                df.loc[~valid_ohlc, 'low'] = df.loc[~valid_ohlc, ['open', 'close']].min(axis=1)

            # 2. 删除所有价格为0的行（可能是无效数据）
            price_columns = ['open', 'high', 'low', 'close']
            valid_price = (df[price_columns] > 0).all(axis=1)
            df = df[valid_price]

            zero_price_count = original_count - len(df)
            if zero_price_count > 0:
                logger.debug(f"过滤掉 {zero_price_count} 条价格为0的数据: {symbol}")

            # 3. 检测和处理重复时间数据
            duplicate_count = df['datetime'].duplicated().sum()
            if duplicate_count > 0:
                logger.warning(f"发现 {duplicate_count} 条重复时间数据: {symbol}")
                df = df.drop_duplicates(subset=['datetime'], keep='last')

            return df

        except Exception as e:
            logger.error(f"数据完整性验证失败: {e}")
            return pd.DataFrame()

    def _smart_filter_by_date_range(self, df: pd.DataFrame, start_date: str = None, end_date: str = None, symbol: str = "") -> pd.DataFrame:
        """
        智能日期过滤 - pytdx专用版本

        关键逻辑：
        1. pytdx只返回历史数据，不支持日期范围查询
        2. 如果end_date是未来日期或今天，不进行过滤（返回所有数据）
        3. 如果start_date晚于最新数据日期，返回空（避免误判）
        4. 只有当日期范围明确在历史区间时才进行过滤

        Args:
            df: 输入DataFrame
            start_date: 开始日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            end_date: 结束日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            symbol: 股票代码（用于日志）

        Returns:
            过滤后的DataFrame
        """
        try:
            if df.empty or 'datetime' not in df.columns:
                return df

            original_len = len(df)

            # 确保datetime列是datetime类型
            if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
                df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                df = df.dropna(subset=['datetime'])

            # 获取当前日期（今天）
            from datetime import datetime as dt
            today = dt.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # 转换日期参数为datetime对象
            def parse_date(date_str):
                if date_str is None:
                    return None
                try:
                    import re
                    # 移除所有非数字字符
                    date_clean = re.sub(r'[^0-9]', '', str(date_str))
                    if len(date_clean) >= 8:
                        date_clean = date_clean[:8]  # YYYYMMDD
                        return pd.to_datetime(date_clean, format='%Y%m%d')
                    else:
                        return pd.to_datetime(date_str)
                except Exception as e:
                    logger.warning(f"日期解析失败: {date_str}, 错误: {e}")
                    return None

            start_dt = parse_date(start_date)
            end_dt = parse_date(end_date)

            # 关键修复：智能处理end_date
            # 如果end_date是今天或未来，将其调整为None（不过滤），因为pytdx只返回历史数据
            if end_dt is not None and end_dt >= pd.Timestamp(today):
                logger.info(f"[智能过滤] {symbol} end_date({end_date})是今天或未来，调整为不限制end_date（pytdx只返回历史数据）")
                end_dt = None  # 不限制end_date

            # 关键修复：如果start_date明显晚于数据中的最新日期，说明请求的是未来数据
            # 允许3天的容差（考虑周末、节假日等情况）
            if start_dt is not None:
                max_data_date = df['datetime'].max()
                # 如果start_date比最新数据日期晚超过3天，才认为是无效的未来查询
                days_diff = (start_dt - max_data_date).days
                if days_diff > 3:
                    logger.warning(f"[智能过滤] {symbol} start_date({start_date})比最新数据日期({max_data_date})晚{days_diff}天, "
                                   f"可能是未来日期查询或该股票已停牌，返回空")
                    return pd.DataFrame()
                elif days_diff > 0:
                    logger.info(f"[智能过滤] {symbol} start_date({start_date})比最新数据日期({max_data_date})晚{days_diff}天，"
                                f"可能是交易日差异，调整start_date为最新数据日期")
                    start_dt = max_data_date  # 调整为最新数据日期

            # 应用日期过滤
            filter_applied = False
            if start_dt is not None:
                df = df[df['datetime'] >= start_dt]
                filter_applied = True
                logger.debug(f"应用start_date过滤: {start_date}, 保留 {len(df)}/{original_len} 条记录")

            if end_dt is not None:
                df = df[df['datetime'] <= end_dt]
                filter_applied = True
                logger.debug(f"应用end_date过滤: {end_date}, 保留 {len(df)}/{original_len} 条记录")

            filtered_count = original_len - len(df)
            if filter_applied:
                if filtered_count > 0:
                    logger.info(f"[智能过滤] {symbol} 日期范围过滤: 过滤掉 {filtered_count} 条记录, 保留 {len(df)} 条")
                else:
                    logger.info(f"[智能过滤] {symbol} 日期范围过滤: 所有 {len(df)} 条记录均在范围内")
            else:
                logger.info(f"[智能过滤] {symbol} 未应用日期过滤，保留全部 {len(df)} 条数据")

            return df

        except Exception as e:
            logger.error(f"智能日期过滤失败: {e}")
            return df

    def _filter_by_date_range(self, df: pd.DataFrame, start_date: str = None, end_date: str = None, symbol: str = "") -> pd.DataFrame:
        """
        根据日期范围过滤数据

        Args:
            df: 输入DataFrame
            start_date: 开始日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            end_date: 结束日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            symbol: 股票代码（用于日志）

        Returns:
            过滤后的DataFrame
        """
        try:
            if df.empty or 'datetime' not in df.columns:
                return df

            original_len = len(df)

            # 确保datetime列是datetime类型
            if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
                df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                df = df.dropna(subset=['datetime'])

            # 转换日期参数为datetime对象
            def parse_date(date_str):
                if date_str is None:
                    return None
                try:
                    import re
                    # 移除所有非数字字符
                    date_clean = re.sub(r'[^\d]', '', str(date_str))
                    if len(date_clean) >= 8:
                        date_clean = date_clean[:8]  # YYYYMMDD
                        return pd.to_datetime(date_clean, format='%Y%m%d')
                    else:
                        return pd.to_datetime(date_str)
                except Exception as e:
                    logger.warning(f"日期解析失败: {date_str}, 错误: {e}")
                    return None

            start_dt = parse_date(start_date)
            end_dt = parse_date(end_date)

            # 应用日期过滤
            if start_dt is not None:
                df = df[df['datetime'] >= start_dt]
                logger.debug(f"应用start_date过滤: {start_date}, 保留 {len(df)}/{original_len} 条记录")

            if end_dt is not None:
                df = df[df['datetime'] <= end_dt]
                logger.debug(f"应用end_date过滤: {end_date}, 保留 {len(df)}/{original_len} 条记录")

            filtered_count = original_len - len(df)
            if filtered_count > 0:
                logger.info(f"日期范围过滤: {symbol}, 过滤掉 {filtered_count} 条记录, 保留 {len(df)} 条")

            return df

        except Exception as e:
            logger.error(f"日期过滤失败: {e}")
            return df

    def _finalize_dataframe_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """最终格式化DataFrame"""
        try:
            # 确保列的顺序和类型
            required_columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
            optional_columns = ['amount']

            # 选择最终列
            final_columns = required_columns.copy()
            for col in optional_columns:
                if col in df.columns:
                    final_columns.append(col)

            df = df[final_columns]

            # 设置datetime为索引
            df = df.set_index('datetime')

            # 按时间排序
            df = df.sort_index()

            # 确保数据类型正确
            float_columns = ['open', 'high', 'low', 'close']
            int_columns = ['volume']

            for col in float_columns:
                if col in df.columns:
                    df[col] = df[col].astype(float)

            for col in int_columns:
                if col in df.columns:
                    df[col] = df[col].astype(int)

            if 'amount' in df.columns:
                df['amount'] = df['amount'].astype(float)

            return df

        except Exception as e:
            logger.error(f"最终格式化失败: {e}")
            return pd.DataFrame()

    # A股 240 分钟分时点: 上午 09:31-11:30 (120) + 下午 13:01-15:00 (120)
    _INTRADAY_MORNING_MINUTES = 120
    _INTRADAY_AFTERNOON_MINUTES = 120

    @staticmethod
    def _generate_intraday_timestamps(trade_date: str) -> List[datetime]:
        """生成 A股 240 分钟分时时刻序列 (09:31-11:30, 13:01-15:00)

        pytdx get_minute_time_data 仅返回 price/vol, 不携带时刻,
        由客户端按交易日生成完整时刻序列 (R293-G4 数据源层契约)。
        """
        base = datetime.strptime(trade_date, '%Y%m%d')
        timestamps = []
        for i in range(TongdaxinStockPlugin._INTRADAY_MORNING_MINUTES):
            timestamps.append(base.replace(hour=9, minute=31) + timedelta(minutes=i))
        for i in range(TongdaxinStockPlugin._INTRADAY_AFTERNOON_MINUTES):
            timestamps.append(base.replace(hour=13, minute=1) + timedelta(minutes=i))
        return timestamps

    def get_minute_time_data(self, symbol: str, date: str = None) -> pd.DataFrame:
        """获取当日 (或指定日期) 分时数据

        pytdx 分时接口约束 (pytdx/parser/get_minute_time_data.py 实证):
        - get_minute_time_data(market, code) 仅返回 price/vol 两字段,
          无 datetime/amount -> 本方法补充时刻序列 + amount=price*vol 近似,
          供上层计算均价线(VWAP)。
        - date 传值时走 get_history_minute_time_data(market, code, date)
          取历史分时。

        Args:
            symbol: 股票代码 (600000 / 000001 / 600000.SH 均可)
            date: 交易日 YYYYMMDD, 默认当日实时分时

        Returns:
            pd.DataFrame: index=datetime (分钟时刻), 列 [price, vol, amount]
            失败/空数据返回空 DataFrame
        """
        try:
            if not PYTDX_AVAILABLE:
                logger.error("pytdx 库不可用，无法获取分时数据")
                # 降级由 TET 管道 failover 到腾讯独立插件 (tencent_plugin)，插件间隔离
                return pd.DataFrame()

            market, code = self._convert_symbol_to_tdx_format(symbol)
            trade_date = date or datetime.now().strftime('%Y%m%d')

            def _fetch(api_client):
                if date:
                    return api_client.get_history_minute_time_data(market, code, trade_date)
                return api_client.get_minute_time_data(market, code)

            # 优先连接池, 否则单连接 (与 _fetch_single_batch/get_real_time_data 同构)
            if self.use_connection_pool and self.connection_pool:
                with self.connection_pool.get_connection() as api_client:
                    raw = _fetch(api_client)
            else:
                if not self._ensure_connection():
                    logger.error(f"无法连接到通达信服务器，获取 {symbol} 分时数据失败")
                    return pd.DataFrame()
                with self.connection_lock:
                    raw = _fetch(self.api_client)

            if not raw:
                logger.warning(f"分时数据为空: {symbol} {trade_date}")
                # 降级由 TET 管道 failover 到腾讯独立插件 (tencent_plugin)，插件间隔离
                return pd.DataFrame()

            timestamps = self._generate_intraday_timestamps(trade_date)
            rows = []
            for idx, item in enumerate(raw):
                ts = timestamps[idx] if idx < len(timestamps) else timestamps[-1] + timedelta(minutes=idx - len(timestamps) + 1)
                price = float(item.get('price', 0))
                vol = int(item.get('vol', 0))
                rows.append({
                    'datetime': ts,
                    'price': price,
                    'vol': vol,
                    'amount': round(price * vol, 2),
                })

            df = pd.DataFrame(rows)
            if df.empty:
                return df
            df = df.set_index('datetime')
            self.request_count += 1
            logger.info(f"获取分时数据成功: {symbol} {trade_date} {len(df)} 点")
            return df

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取分时数据失败 {symbol}: {e}")
            # 降级由 TET 管道 failover 到腾讯独立插件 (tencent_plugin)，插件间隔离
            return pd.DataFrame()

    def get_real_time_data(self, symbols: List[str]) -> Dict[str, Any]:
        """获取实时行情数据"""
        try:
            if not self._ensure_connection():
                logger.error("无法连接到通达信服务器")
                return {}

            result = {}

            with self.connection_lock:
                for symbol in symbols:
                    try:
                        market, code = self._convert_symbol_to_tdx_format(symbol)

                        # 获取实时行情
                        quotes = self.api_client.get_security_quotes([(market, code)])

                        if quotes and len(quotes) > 0:
                            quote = quotes[0]
                            result[symbol] = {
                                'symbol': symbol,
                                'name': quote.get('name', ''),
                                'price': quote.get('price', 0),
                                'open': quote.get('open', 0),
                                'high': quote.get('high', 0),
                                'low': quote.get('low', 0),
                                'pre_close': quote.get('last_close', 0),
                                'volume': quote.get('vol', 0),
                                'amount': quote.get('amount', 0),
                                'bid1': quote.get('bid1', 0),
                                'bid_vol1': quote.get('bid_vol1', 0),
                                'ask1': quote.get('ask1', 0),
                                'ask_vol1': quote.get('ask_vol1', 0),
                                'timestamp': datetime.now().isoformat()
                            }

                    except Exception as e:
                        logger.warning(f"获取 {symbol} 实时数据失败: {e}")
                        continue

                self.api_client.disconnect()

            self.request_count += 1
            logger.info(f"获取实时数据成功，共 {len(result)} 只股票")
            return result

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取实时数据失败: {e}")
            logger.error(traceback.format_exc())
            return {}

    def fetch_data(self, symbol: str, data_type: str,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   **kwargs) -> pd.DataFrame:
        """
        通用数据获取接口 - 增强版本

        增加了数据验证、存储优化和错误处理
        """
        try:
            if data_type == 'historical_kline' or data_type == 'kline':
                period = kwargs.get('period', 'daily')
                count = kwargs.get('count', 800)

                start_str = start_date.strftime('%Y%m%d') if start_date else None
                end_str = end_date.strftime('%Y%m%d') if end_date else None

                # 获取K线数据
                df = self.get_kline_data(
                    symbol=symbol,
                    period=period,
                    start_date=start_str,
                    end_date=end_str,
                    count=count
                )

                # 数据后处理和存储优化
                if not df.empty:
                    df = self._optimize_data_for_storage(df, symbol, data_type, period)

                return df

            elif data_type == 'real_time_quote' or data_type == 'realtime':
                symbols = kwargs.get('symbols', [symbol])
                real_time_data = self.get_real_time_data(symbols)

                if real_time_data and symbol in real_time_data:
                    # 转换为DataFrame格式
                    data = real_time_data[symbol]
                    df = pd.DataFrame([data])
                    df['datetime'] = pd.to_datetime(data['timestamp'])
                    df = df.set_index('datetime')
                    return df
                else:
                    return pd.DataFrame()

            elif data_type in ('minute_time', 'intraday', 'intraday_data'):
                # R295-G4 分时数据源层: 实时分时 (get_minute_time_data) /
                # 历史分时 (date 传 YYYYMMDD), 时刻由客户端生成。
                # 'intraday_data' 为 DataType.INTRADAY_DATA 的枚举 value,
                # TET 管道 _extract_from_source else 兜底传 original_query.data_type.value。
                return self.get_minute_time_data(symbol, date=kwargs.get('date'))

            elif data_type == 'stock_list':
                return self.get_stock_list()

            else:
                logger.warning(f"不支持的数据类型: {data_type}")
                return pd.DataFrame()

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取数据失败 {symbol} ({data_type}): {e}")
            return pd.DataFrame()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_requests': self.request_count,
            'success_rate': 1.0 if self.last_error is None else 0.8,
            'avg_response_time': 0.5,
            'last_update': datetime.now().isoformat(),
            'last_error': self.last_error,
            'current_server': f"{self.current_server[0]}:{self.current_server[1]}",
            'supported_markets': list(self.supported_markets.keys()),
            'cache_status': 'active' if self._stock_list_cache is not None else 'empty',
            'last_success_time': self.last_success_time.isoformat() if self.last_success_time else None
        }

    def get_fundamental_data(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本面数据（股本、财务指标等）

        Args:
            symbol: 股票代码（如'000001'）

        Returns:
            Dict[str, Any]: 包含基本面数据的字典
        """
        try:
            if not self._ensure_connection():
                logger.warning(f"无法连接到通达信服务器获取基本面数据: {symbol}")
                return {}

            normalized_symbol = symbol.split('.')[0] if '.' in symbol else symbol
            market, code = self._convert_symbol_to_tdx_format(normalized_symbol)

            fundamental_data = {}

            with self.connection_lock:
                try:
                    quotes = self.api_client.get_security_quotes([(market, code)])

                    if quotes and len(quotes) > 0:
                        quote = quotes[0]

                        if hasattr(quote, 'vol') and quote.vol:
                            total_shares = quote.vol * 100
                            fundamental_data['total_shares'] = float(total_shares)
                            fundamental_data['circulating_shares'] = float(total_shares * 0.7)

                        if hasattr(quote, 'amount') and quote.amount:
                            fundamental_data['total_market_cap'] = float(quote.amount * 10000)
                            fundamental_data['circulating_market_cap'] = float(quote.amount * 10000 * 0.7)

                        if hasattr(quote, 'price') and quote.price:
                            if 'total_market_cap' in fundamental_data and fundamental_data['total_market_cap'] > 0:
                                fundamental_data['pe_ratio'] = fundamental_data['total_market_cap'] / (quote.price * 100000000)

                        if hasattr(quote, 'name') and quote.name:
                            fundamental_data['name'] = str(quote.name)

                        if hasattr(quote, 'pre_close') and quote.pre_close and quote.pre_close > 0:
                            if hasattr(quote, 'price') and quote.price:
                                if quote.price > 0 and 'circulating_market_cap' in fundamental_data:
                                    fundamental_data['pb_ratio'] = fundamental_data['circulating_market_cap'] / (quote.price * fundamental_data.get('circulating_shares', 0))

                        logger.debug(f"成功获取 {symbol} 基本面数据（实时行情估算）")
                        self.request_count += 1
                        return fundamental_data

                except Exception as e:
                    logger.warning(f"通过实时行情获取 {symbol} 基本面数据失败: {e}")

            try:
                stock_list_df = self.get_stock_list()
                if not stock_list_df.empty:
                    stock_info = stock_list_df[stock_list_df['code'] == normalized_symbol]
                    if not stock_info.empty:
                        row = stock_info.iloc[0]
                        if 'total_shares' not in fundamental_data and 'shares' in stock_list_df.columns:
                            fundamental_data['total_shares'] = float(row.get('shares', 0)) * 100000000
                        if 'industry' not in fundamental_data and 'industry' in stock_list_df.columns:
                            fundamental_data['industry'] = row.get('industry', '')
                        logger.debug(f"成功获取 {symbol} 基本面数据（股票列表）")
                        return fundamental_data

            except Exception as e:
                logger.warning(f"通过股票列表获取 {symbol} 基本面数据失败: {e}")

            logger.warning(f"无法获取 {symbol} 基本面数据")
            return fundamental_data

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取 {symbol} 基本面数据失败: {e}")
            return {}

# 插件工厂函数

    def get_individual_fund_flow_data(self, symbol: str, **kwargs) -> pd.DataFrame:
        """
        获取个股资金流数据

        Args:
            symbol: 股票代码
            **kwargs: 其他参数

        Returns:
            个股资金流数据DataFrame
        """
        try:
            self.logger.info(f"{self.name}获取个股 {symbol} 资金流数据")

            # 个股资金流数据不在通达信核心功能中，该功能需要其他数据源
            import pandas as pd
            self.logger.warning(f"通达信不支持个股资金流数据: {symbol}，请使用东方财富等数据源")
            return pd.DataFrame()  # 返回空数据框

        except Exception as e:
            self.logger.error(f"获取个股资金流数据失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return pd.DataFrame()

    def get_main_fund_flow_data(self, symbol: str = "index", **kwargs) -> pd.DataFrame:
        """
        获取主力资金流数据（大盘指数）

        Args:
            symbol: 指数代码或"index"表示获取主要指数
            **kwargs: 其他参数

        Returns:
            主力资金流数据DataFrame
        """
        try:
            self.logger.info(f"{self.name}获取主力资金流数据")

            # 主力资金流数据不在通达信核心功能中，该功能需要其他数据源
            import pandas as pd
            self.logger.warning("通达信不支持主力资金流数据，请使用东方财富等数据源")
            return pd.DataFrame()  # 返回空数据框

        except Exception as e:
            self.logger.error(f"获取主力资金流数据失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return pd.DataFrame()

    def get_server_status(self) -> List[Dict[str, Any]]:
        """获取所有服务器状态"""
        try:
            current_time = time.time()

            # 检查是否需要重新发现服务器状态
            if (self._last_discovery_time is None or
                    current_time - self._last_discovery_time > self._discovery_interval):
                self._update_server_status()
                self._last_discovery_time = current_time

            # 构造服务器状态列表
            server_status_list = []
            for i, server in enumerate(self.server_list):
                host, port = server
                server_key = f"{host}:{port}"

                # 从缓存获取状态
                status = self._server_status_cache.get(server_key, {
                    'available': False,
                    'response_time': float('inf'),
                    'last_test': None,
                    'error_message': '未测试'
                })

                server_info = {
                    'index': i,
                    'host': host,
                    'port': port,
                    'address': server_key,
                    'available': status.get('available', False),
                    'response_time': status.get('response_time', float('inf')),
                    'response_time_ms': round(status.get('response_time', 0) * 1000, 1),
                    'last_test': status.get('last_test'),
                    'error_message': status.get('error_message', ''),
                    'is_current': server == self.current_server,
                    'status_text': self._get_status_text(status)
                }

                server_status_list.append(server_info)

            return server_status_list

        except Exception as e:
            logger.error(f"获取服务器状态失败: {e}")
            return []

    def _update_server_status(self):
        """更新服务器状态缓存"""
        try:
            for server in self.server_list:
                host, port = server
                server_key = f"{host}:{port}"

                status = self._test_server_quality(server)
                status['last_test'] = datetime.now().isoformat()

                self._server_status_cache[server_key] = status

        except Exception as e:
            logger.error(f"更新服务器状态失败: {e}")

    def _get_status_text(self, status):
        """获取状态文本"""
        if not status.get('available', False):
            return "不可用"

        response_time = status.get('response_time', float('inf'))
        if response_time < 1:
            return "优秀"
        elif response_time < 3:
            return "良好"
        elif response_time < 5:
            return "一般"
        else:
            return "较慢"

    def add_server(self, host: str, port: int) -> bool:
        """添加服务器"""
        try:
            new_server = (host, port)
            if new_server not in self.server_list:
                self.server_list.append(new_server)
                logger.info(f"添加服务器: {host}:{port}")
                # 立即测试新服务器
                self._update_server_status()
                return True
            else:
                logger.warning(f"服务器已存在: {host}:{port}")
                return False
        except Exception as e:
            logger.error(f"添加服务器失败: {e}")
            return False

    def remove_server(self, host: str, port: int) -> bool:
        """删除服务器"""
        try:
            server_to_remove = (host, port)
            if server_to_remove in self.server_list:
                # 不能删除当前正在使用的服务器
                if server_to_remove == self.current_server:
                    if len(self.server_list) > 1:
                        # 切换到其他服务器
                        for server in self.server_list:
                            if server != server_to_remove:
                                self.current_server = server
                                break
                    else:
                        logger.error("不能删除最后一个服务器")
                        return False

                self.server_list.remove(server_to_remove)
                # 清除缓存
                server_key = f"{host}:{port}"
                if server_key in self._server_status_cache:
                    del self._server_status_cache[server_key]

                logger.info(f"删除服务器: {host}:{port}")
                return True
            else:
                logger.warning(f"服务器不存在: {host}:{port}")
                return False
        except Exception as e:
            logger.error(f"删除服务器失败: {e}")
            return False

    def set_current_server(self, host: str, port: int) -> bool:
        """设置当前服务器"""
        try:
            target_server = (host, port)
            if target_server in self.server_list:
                self.current_server = target_server
                logger.info(f"切换到服务器: {host}:{port}")
                return True
            else:
                logger.error(f"服务器不存在: {host}:{port}")
                return False
        except Exception as e:
            logger.error(f"设置当前服务器失败: {e}")
            return False

    def test_server(self, host: str, port: int) -> Dict[str, Any]:
        """测试指定服务器"""
        try:
            server = (host, port)
            status = self._test_server_quality(server)
            status['last_test'] = datetime.now().isoformat()

            # 更新缓存
            server_key = f"{host}:{port}"
            self._server_status_cache[server_key] = status

            return {
                'host': host,
                'port': port,
                'available': status.get('available', False),
                'response_time': status.get('response_time', float('inf')),
                'response_time_ms': round(status.get('response_time', 0) * 1000, 1),
                'error_message': status.get('error_message', ''),
                'status_text': self._get_status_text(status)
            }
        except Exception as e:
            logger.error(f"测试服务器失败: {e}")
            return {
                'host': host,
                'port': port,
                'available': False,
                'response_time': float('inf'),
                'response_time_ms': 0,
                'error_message': str(e),
                'status_text': '测试失败'
            }

    def refresh_server_status(self):
        """刷新所有服务器状态"""
        try:
            self._update_server_status()
            self._last_discovery_time = time.time()
            logger.info("服务器状态刷新完成")
        except Exception as e:
            logger.error(f"刷新服务器状态失败: {e}")

    def _optimize_data_for_storage(self, df: pd.DataFrame, symbol: str, data_type: str, period: str) -> pd.DataFrame:
        """
        优化数据存储格式

        Args:
            df: 原始数据
            symbol: 股票代码
            data_type: 数据类型
            period: 周期

        Returns:
            优化后的数据
        """
        try:
            if df.empty:
                return df

            # 1. 添加元数据列
            df = self._add_metadata_columns(df, symbol, data_type, period)

            # 2. 数据压缩优化
            df = self._optimize_data_types(df)

            # 3. 数据质量评分
            quality_score = self._calculate_data_quality_score(df)
            df.attrs['quality_score'] = quality_score

            logger.debug(f"数据存储优化完成: {symbol}, 质量评分: {quality_score:.2f}")

            return df

        except Exception as e:
            logger.error(f"数据存储优化失败: {e}")
            return df

    def _add_metadata_columns(self, df: pd.DataFrame, symbol: str, data_type: str, period: str) -> pd.DataFrame:
        """添加元数据列"""
        try:
            # 添加必要的元数据
            df = df.copy()
            df['symbol'] = symbol
            df['data_source'] = 'tongdaxin'
            df['data_type'] = data_type
            df['period'] = period
            df['fetch_time'] = datetime.now()
            df['plugin_version'] = '1.0.0'

            return df

        except Exception as e:
            logger.error(f"添加元数据失败: {e}")
            return df

    def _optimize_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """优化数据类型以节省存储空间"""
        try:
            # 价格数据使用float32（足够精度，节省50%空间）
            price_columns = ['open', 'high', 'low', 'close']
            for col in price_columns:
                if col in df.columns:
                    df[col] = df[col].astype('float32')

            # 成交量使用int64
            if 'volume' in df.columns:
                df['volume'] = df['volume'].astype('int64')

            # 成交额使用float64（需要高精度）
            if 'amount' in df.columns:
                df['amount'] = df['amount'].astype('float64')

            # 字符串列使用category类型节省空间
            string_columns = ['symbol', 'data_source', 'data_type', 'period']
            for col in string_columns:
                if col in df.columns:
                    df[col] = df[col].astype('category')

            return df

        except Exception as e:
            logger.error(f"数据类型优化失败: {e}")
            return df

    def _calculate_data_quality_score(self, df: pd.DataFrame) -> float:
        """
        计算数据质量评分 (0-1)

        评分标准：
        - 数据完整性 (30%)
        - 数据一致性 (30%) 
        - 时间连续性 (20%)
        - 数值合理性 (20%)
        """
        try:
            if df.empty:
                return 0.0

            scores = []

            # 1. 数据完整性评分 (30%)
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            completeness_score = sum(1 for col in required_columns if col in df.columns and df[col].notna().all()) / len(required_columns)
            scores.append(completeness_score * 0.3)

            # 2. 数据一致性评分 (30%) - OHLC逻辑
            if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
                valid_ohlc = (
                    (df['high'] >= df[['open', 'close']].max(axis=1)) &
                    (df['low'] <= df[['open', 'close']].min(axis=1)) &
                    (df['high'] >= df['low'])
                ).sum()
                consistency_score = valid_ohlc / len(df) if len(df) > 0 else 0
                scores.append(consistency_score * 0.3)
            else:
                scores.append(0)

            # 3. 时间连续性评分 (20%)
            if len(df) > 1:
                # 检查时间间隔的一致性
                time_diffs = df.index.to_series().diff().dropna()
                if len(time_diffs) > 0:
                    # 计算时间间隔的变异系数
                    mean_diff = time_diffs.mean()
                    std_diff = time_diffs.std()
                    cv = std_diff / mean_diff if mean_diff.total_seconds() > 0 else float('inf')
                    # 变异系数越小，连续性越好
                    continuity_score = max(0, 1 - min(cv, 1))
                    scores.append(continuity_score * 0.2)
                else:
                    scores.append(0.2)  # 单条数据给满分
            else:
                scores.append(0.2)  # 单条数据给满分

            # 4. 数值合理性评分 (20%)
            reasonableness_score = 1.0
            if 'close' in df.columns:
                # 检查价格波动是否合理（单日涨跌幅不超过20%）
                if len(df) > 1:
                    price_changes = df['close'].pct_change().abs()
                    extreme_changes = (price_changes > 0.2).sum()
                    reasonableness_score = max(0, 1 - extreme_changes / len(df))
            scores.append(reasonableness_score * 0.2)

            # 计算总分
            total_score = sum(scores)

            logger.debug(f"数据质量评分详情 - 完整性: {completeness_score:.2f}, 一致性: {consistency_score:.2f}, 连续性: {continuity_score:.2f}, 合理性: {reasonableness_score:.2f}, 总分: {total_score:.2f}")

            return total_score

        except Exception as e:
            logger.error(f"质量评分计算失败: {e}")
            return 0.5  # 默认中等质量

    def _start_background_server_init(self):
        """后台异步初始化服务器列表（不阻塞UI）"""
        import threading
        
        def _async_init():
            try:
                import time
                start_time = time.time()
                fetched = self._load_servers_from_endpoints()
                elapsed = time.time() - start_time
                
                if fetched and len(fetched) > 0:
                    with self._server_lock:
                        self.server_list = fetched
                        if self.server_list:
                            self.current_server = self.server_list[0]
                            self.server_index = 0
                    logger.info(f"后台更新服务器列表成功: {len(self.server_list)} 个服务器（耗时 {elapsed:.2f}秒）")
                else:
                    logger.debug(f"后台获取服务器列表为空，保持默认列表")
                
                self._servers_initialized = True
                
            except Exception as e:
                logger.debug(f"后台初始化服务器失败: {e}，使用默认列表")
                self._servers_initialized = True
        
        thread = threading.Thread(target=_async_init, daemon=True, name="TdxServerInit")
        thread.start()
        logger.debug("服务器后台初始化线程已启动")

    def _initialize_servers(self):
        """初始化服务器列表：优先从配置的端点URL获取 → 失败时使用内置清单"""
        try:
            # 修复：快速初始化，避免阻塞
            # 1) 优先从配置端点获取（例如GitHub/自定义URL提供的hosts）
            # 设置快速超时，避免长时间阻塞插件加载
            import time
            start_time = time.time()
            fetched = self._load_servers_from_endpoints()
            elapsed = time.time() - start_time
            
            if fetched:
                self.server_list = fetched
                logger.info(f"从配置端点获取了 {len(self.server_list)} 个服务器（耗时 {elapsed:.2f}秒）")
            else:
                # 2) 回退到内置默认清单
                self._load_default_servers()
                if elapsed > 5:
                    logger.warning(f"从端点获取服务器失败，使用默认服务器列表（耗时 {elapsed:.2f}秒，可能网络较慢）")
                else:
                    logger.info("使用默认服务器列表")

            # 设置当前服务器
            if self.server_list:
                self.current_server = self.server_list[0]
                self.server_index = 0
            else:
                logger.warning("没有可用的服务器")

        except Exception as e:
            logger.error(f"初始化服务器列表失败: {e}")
            # 出错时使用默认服务器
            self._load_default_servers()

    def _load_servers_from_endpoints(self) -> list:
        """
        从配置的端点URL列表获取服务器清单，进行基础解析与去重
        Returns:
            List[Tuple[str, int]]: 服务器 (host, port) 列表
        """
        servers: list = []
        try:
            import re
            import requests
            import json

            endpoints = []
            # 优先从配置读取端点列表
            if hasattr(self, 'config'):
                endpoints = self.config.get('server_endpoints', []) or []
            # 兼容旧字段：self.endpointhost（若存在）
            if not endpoints and hasattr(self, 'endpointhost'):
                endpoints = self.endpointhost or []

            if not endpoints:
                return []

            # 修复：大幅减少超时时间，避免阻塞插件加载
            # 从60秒减少到5秒，快速失败，避免卡顿
            fetch_timeout = int(self.config.get('endpoint_fetch_timeout', 5)) if hasattr(self, 'config') else 5
            max_results = int(self.config.get('endpoint_max_results', 200)) if hasattr(self, 'config') else 200
            
            # 修复：使用并发请求，而不是串行，提高速度
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import time
            
            ip_port_pattern = re.compile(r"(?:^|[^0-9])(\d{1,3}(?:\.\d{1,3}){3})[:：]\s*(\d{2,5})")
            # 修正 tuple_pattern 以匹配实际数据结构
            tuple_pattern = re.compile(r"$\s*['\"][^'\"]*['\"]\s*,\s*['\"](\d{1,3}(?:\.\d{1,3}){3})['\"]\s*,\s*(\d{2,5})\s*$")

            # 修复：并发请求所有endpoint，设置总体超时，快速失败
            start_time = time.time()
            max_total_timeout = 10  # 总体超时10秒，避免长时间阻塞
            
            def fetch_url(url):
                """获取单个URL的内容"""
                try:
                    resp = requests.get(url, timeout=fetch_timeout)
                    if resp.status_code == 200 and resp.text:
                        return resp.text
                    return None
                except Exception as e:
                    logger.debug(f"获取endpoint失败 {url}: {e}")
                    return None
            
            # 并发请求所有endpoint
            url_texts = {}
            with ThreadPoolExecutor(max_workers=min(len(endpoints), 5)) as executor:
                future_to_url = {executor.submit(fetch_url, url): url for url in endpoints}
                for future in as_completed(future_to_url, timeout=max_total_timeout):
                    if time.time() - start_time > max_total_timeout:
                        logger.debug(f"endpoint请求总体超时（{max_total_timeout}秒），停止等待")
                        break
                    url = future_to_url[future]
                    try:
                        text = future.result()
                        if text:
                            url_texts[url] = text
                    except Exception as e:
                        logger.debug(f"处理endpoint结果失败 {url}: {e}")
            
            # 处理获取到的内容
            for url, text in url_texts.items():
                try:
                    if not text:
                        continue

                    # 1) 尝试作为JSON解析
                    parsed_json = None
                    try:
                        parsed_json = json.loads(text)
                    except Exception:
                        parsed_json = None

                    if isinstance(parsed_json, list):
                        # 支持多种JSON结构：[{ip,port}], [{"host": "...", "port": 7709}], [{"server":"1.2.3.4:7709"}]
                        for item in parsed_json:
                            try:
                                if isinstance(item, dict):
                                    if 'ip' in item and 'port' in item:
                                        host = str(item['ip']).strip()
                                        port = int(item['port'])
                                        if 0 < port <= 65535:
                                            servers.append((host, port))
                                    elif 'host' in item and 'port' in item:
                                        host = str(item['host']).strip()
                                        port = int(item['port'])
                                        if 0 < port <= 65535:
                                            servers.append((host, port))
                                    elif 'server' in item and isinstance(item['server'], str) and ':' in item['server']:
                                        host_part, port_part = item['server'].split(':', 1)
                                        host = host_part.strip()
                                        port = int(port_part.strip())
                                        if 0 < port <= 65535:
                                            servers.append((host, port))
                                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                                    host = str(item[0]).strip()
                                    port = int(item[1])
                                    if 0 < port <= 65535:
                                        servers.append((host, port))
                            except Exception:
                                continue

                    # 2) 解析Python hosts.py风格的('ip', port)元组
                    for m in tuple_pattern.finditer(text):
                        host = m.group(1)
                        port = int(m.group(2))
                        if 0 < port <= 65535:
                            servers.append((host, port))

                    # 3) 再用通用 ip:port 模式兜底
                    for m in ip_port_pattern.finditer(text):
                        host = m.group(1)
                        port = int(m.group(2))
                        # 基础合法性过滤
                        if 0 < port <= 65535:
                            servers.append((host, port))
                except Exception:
                    continue

            # 去重与截断（最多保留前max_results个）
            seen = set()
            deduped = []
            for host, port in servers:
                key = f"{host}:{port}"
                if key in seen:
                    continue
                # 验证IP地址格式
                if not self._validate_ip_address(host):
                    logger.debug(f"跳过无效IP地址: {host}:{port}")
                    continue
                seen.add(key)
                deduped.append((host, port))
                if len(deduped) >= max_results:
                    break

            logger.info(f"从端点共解析到 {len(servers)} 个候选地址，去重并验证后 {len(deduped)} 个（最大返回 {max_results}）")
            return deduped
        except Exception:
            return []

    def _validate_ip_address(self, ip: str) -> bool:
        """
        验证IP地址格式是否正确
        
        Args:
            ip: IP地址字符串
            
        Returns:
            bool: IP地址格式是否有效
        """
        try:
            import socket
            # 使用socket.inet_aton验证IPv4地址格式
            socket.inet_aton(ip)
            # 进一步验证IP地址范围（排除0.0.0.0和255.255.255.255等特殊地址）
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            # 排除一些明显无效的地址
            if ip == '0.0.0.0' or ip == '255.255.255.255':
                return False
            return True
        except (socket.error, ValueError):
            return False

    def _load_default_servers(self):
        """加载默认服务器列表 - 优化顺序，最快服务器优先"""
        # 按照历史测试的响应时间排序，最快的服务器放在前面
        self.server_list = [
            # 第一梯队：超快服务器 (1-2ms)
            ('180.153.18.170', 7709),  # 上海电信主站Z1 - 1ms
            ('218.6.170.47', 7709),    # 上证云成都电信一 - 1ms
            ('202.108.253.131', 7709),  # 北京联通主站Z2 - 1ms
            ('180.153.18.171', 7709),  # 上海电信主站Z2 - 1ms
            ('123.125.108.14', 7709),  # 上证云北京联通一 - 2ms

            # 第二梯队：快速服务器 (2-3ms)
            ('60.191.117.167', 7709),  # 杭州电信主站J1 - 2ms
            ('218.85.139.20', 7709),   # 长城国瑞电信2 - 2ms
            ('58.23.131.163', 7709),   # 长城国瑞网通 - 2ms
            ('115.238.56.198', 7709),  # 杭州电信主站J2 - 2ms
            ('218.85.139.19', 7709),   # 长城国瑞电信1 - 3ms

            # 第三梯队：备用服务器 (3-5ms)
            ('218.108.98.244', 7709),  # 杭州华数主站J1 - 3ms
            ('180.153.39.51', 7709),   # 上海电信主站Z3 - 3ms
            ('115.238.90.165', 7709),  # 杭州电信主站J4 - 3ms

            # 特殊端口服务器（通常较慢，放在最后）
            ('202.108.253.139', 80),   # 北京联通主站Z80 - 端口80
            ('180.153.18.172', 80),    # 上海电信主站Z80 - 端口80
            ("218.85.139.19", 7709),

            ("218.85.139.20", 7709),
            ("58.23.131.163", 7709),
            ("218.6.170.47", 7709),
            ("123.125.108.14", 7709),
            ("180.153.18.170", 7709),
            ("180.153.18.171", 7709),
            ("180.153.18.172", 80),
            ("202.108.253.130", 7709),
            ("202.108.253.131", 7709),
            ("202.108.253.139", 80),
            ("60.191.117.167", 7709),
            ("115.238.56.198", 7709),
            ("218.75.126.9", 7709),
            ("115.238.90.165", 7709),
            ("124.160.88.183", 7709),
            ("60.12.136.250", 7709),
            ("218.108.98.244", 7709),
            ("218.108.47.69", 7709),
            ("223.94.89.115", 7709),
            ("218.57.11.101", 7709),
            ("58.58.33.123", 7709)
        ]

        # 将默认服务器保存到数据库
        try:
            from core.database.tdx_server_manager import get_tdx_db_manager
            db_manager = get_tdx_db_manager()

            for host, port in self.server_list:
                db_manager.save_tdx_server(
                    host=host,
                    port=port,
                    status='unknown',
                    source='builtin',
                    priority=1
                )
            logger.info("默认服务器已保存到数据库")
        except Exception as e:
            logger.warning(f"保存默认服务器到数据库失败: {e}")


def create_plugin() -> IDataSourcePlugin:
    """创建插件实例"""
    return TongdaxinStockPlugin()


# 插件元数据
PLUGIN_METADATA = {
    "name": "通达信股票数据源插件",
    "version": "1.0.0",
    "description": "提供A股实时和历史数据，支持上海、深圳交易所，基于pytdx库",
    "author": "FactorWeave-Quant 开发团队",
    "plugin_type": "data_source_stock",
    "asset_types": ["stock"],
    "data_types": ["historical_kline", "real_time_quote", "fundamental", "trade_tick"],
    "markets": ["SH", "SZ"],
    "dependencies": ["pytdx", "pandas", "requests"],
    "config_schema": {
        "host": {
            "type": "string",
            "default": "119.147.212.81",
            "description": "通达信服务器地址"
        },
        "port": {
            "type": "integer",
            "default": 7709,
            "description": "通达信服务器端口"
        },
        "timeout": {
            "type": "integer",
            "default": 30,
            "description": "连接超时时间（秒）"
        },
        "max_retries": {
            "type": "integer",
            "default": 3,
            "description": "最大重试次数"
        },
        "cache_duration": {
            "type": "integer",
            "default": 300,
            "description": "缓存持续时间（秒）"
        },
        "auto_select_server": {
            "type": "boolean",
            "default": True,
            "description": "是否自动选择最快服务器"
        }
    }
}

# 插件注册函数


def create_plugin() -> TongdaxinStockPlugin:
    """创建通达信股票插件实例"""
    return TongdaxinStockPlugin()
