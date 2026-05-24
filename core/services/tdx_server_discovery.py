"""
TDX服务器发现服务
提供联网查询和发现最新可用的TDX服务器IP地址功能
"""

import asyncio
import json
from loguru import logger
import socket
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed



class TdxServerDiscoveryService:
    """TDX服务器发现服务"""

    def __init__(self):
        # 内置的常用TDX服务器列表
        self.builtin_servers = [
            # 深圳主站
            ("119.147.212.81", 7709),
            ("119.147.212.76", 7709),
            ("119.147.212.75", 7709),

            # 上海主站
            ("114.80.63.12", 7709),
            ("114.80.63.35", 7709),
            ("114.80.80.222", 7709),

            # 深圳备用
            ("119.147.171.206", 7709),
            ("119.147.164.57", 7709),
            ("119.147.164.58", 7709),

            # 广州备用
            ("113.105.142.136", 7709),
            ("113.105.142.133", 7709),

            # 杭州备用
            ("180.153.18.170", 7709),
            ("180.153.18.171", 7709),
            ("180.153.39.51", 7709),

            # 北京备用
            ("124.74.236.94", 7709),
            ("124.74.236.42", 7709),

            # 其他地区
            ("218.75.126.9", 7709),
            ("218.4.54.69", 7709),
            ("140.207.202.181", 7709),
            ("140.207.202.187", 7709),
            ("59.173.18.69", 7709),
            ("59.173.18.140", 7709),
        ]

        # 在线服务器列表源
        self.online_sources = [
            "https://raw.githubusercontent.com/rainx/pytdx/master/pytdx/config/hosts.py",
            "https://gitee.com/better319/pytdx-data/raw/master/hosts.json",
        ]

        self.timeout = 3  # 连接超时时间
        self.max_workers = 10  # 最大并发测试数

    async def discover_servers(self, include_online: bool = True,
                               test_connectivity: bool = True) -> List[Dict]:
        """
        发现可用的TDX服务器

        Args:
            include_online: 是否包含在线源
            test_connectivity: 是否测试连接性

        Returns:
            服务器列表，每个服务器包含host, port, status, response_time等信息
        """
        logger.info("开始发现TDX服务器...")

        # 1. 收集服务器列表
        all_servers = set(self.builtin_servers)

        if include_online:
            online_servers = await self._fetch_online_servers()
            all_servers.update(online_servers)

        logger.info(f"收集到 {len(all_servers)} 个服务器地址")

        # 2. 测试连接性
        server_results = []
        if test_connectivity:
            server_results = await self._test_servers_async(list(all_servers))
        else:
            # 不测试连接性，直接返回列表
            for host, port in all_servers:
                server_results.append({
                    'host': host,
                    'port': port,
                    'status': 'unknown',
                    'response_time': None,
                    'last_tested': datetime.now().isoformat(),
                    'location': self._guess_location(host),
                    'source': 'builtin'
                })

        # 3. 排序（可用的在前，响应时间短的在前）
        server_results.sort(key=lambda x: (
            x['status'] != 'available',  # 可用的排在前面
            x['response_time'] if x['response_time'] is not None else 999
        ))

        logger.info(f"发现完成，可用服务器: {sum(1 for s in server_results if s['status'] == 'available')}")

        return server_results

    async def _fetch_online_servers(self) -> List[Tuple[str, int]]:
        """从在线源获取服务器列表"""
        online_servers = []

        for source_url in self.online_sources:
            try:
                logger.debug(f"正在从在线源获取服务器列表: {source_url}")

                # 使用异步HTTP请求
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(source_url, timeout=10)
                )

                if response.status_code == 200:
                    servers = self._parse_online_source(response.text, source_url)
                    online_servers.extend(servers)
                    logger.debug(f"从 {source_url} 获取到 {len(servers)} 个服务器")

            except Exception as e:
                logger.warning(f"从在线源获取服务器失败 {source_url}: {e}")
                continue

        return online_servers

    def _parse_online_source(self, content: str, source_url: str) -> List[Tuple[str, int]]:
        """解析在线源内容"""
        servers = []

        try:
            if 'hosts.py' in source_url:
                # 解析Python格式的hosts文件
                servers = self._parse_python_hosts(content)
            elif 'hosts.json' in source_url:
                # 解析JSON格式
                servers = self._parse_json_hosts(content)
            else:
                # 尝试通用解析
                servers = self._parse_generic_hosts(content)

        except Exception as e:
            logger.warning(f"解析在线源内容失败 {source_url}: {e}")

        return servers

    def _parse_python_hosts(self, content: str) -> List[Tuple[str, int]]:
        """解析Python格式的hosts文件"""
        servers = []

        # 简单的正则匹配IP地址和端口
        import re

        # 匹配类似 ("119.147.212.81", 7709) 的格式
        pattern = r'["\'](\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})["\'],?\s*(\d+)'
        matches = re.findall(pattern, content)

        for ip, port in matches:
            try:
                servers.append((ip, int(port)))
            except ValueError:
                continue

        return servers

    def _parse_json_hosts(self, content: str) -> List[Tuple[str, int]]:
        """解析JSON格式的hosts文件"""
        servers = []

        try:
            data = json.loads(content)

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'host' in item and 'port' in item:
                        servers.append((item['host'], int(item['port'])))
                    elif isinstance(item, list) and len(item) >= 2:
                        servers.append((item[0], int(item[1])))
            elif isinstance(data, dict) and 'servers' in data:
                for server in data['servers']:
                    servers.append((server['host'], int(server['port'])))

        except json.JSONDecodeError:
            pass

        return servers

    def _parse_generic_hosts(self, content: str) -> List[Tuple[str, int]]:
        """通用解析，尝试从文本中提取IP和端口"""
        servers = []
        import re

        # 匹配IP:端口格式
        pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)'
        matches = re.findall(pattern, content)

        for ip, port in matches:
            try:
                servers.append((ip, int(port)))
            except ValueError:
                continue

        return servers

    async def _test_servers_async(self, servers: List[Tuple[str, int]]) -> List[Dict]:
        """异步测试服务器连接性"""
        results = []

        # 使用线程池进行并发测试
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有测试任务
            future_to_server = {
                executor.submit(self._test_single_server, host, port): (host, port)
                for host, port in servers
            }

            # 收集结果
            for future in as_completed(future_to_server):
                host, port = future_to_server[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.debug(f"测试服务器失败 {host}:{port} - {e}")
                    results.append({
                        'host': host,
                        'port': port,
                        'status': 'error',
                        'response_time': None,
                        'last_tested': datetime.now().isoformat(),
                        'location': self._guess_location(host),
                        'source': 'builtin',
                        'error': str(e)
                    })

        return results

    def _test_single_server(self, host: str, port: int) -> Dict:
        """测试单个服务器连接性"""
        start_time = time.time()

        try:
            # 创建socket连接测试
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)

            result = sock.connect_ex((host, port))
            sock.close()

            response_time = (time.time() - start_time) * 1000  # 转换为毫秒

            if result == 0:
                status = 'available'
                logger.debug(f"服务器可用: {host}:{port} ({response_time:.1f}ms)")
            else:
                status = 'unavailable'
                logger.debug(f"服务器不可用: {host}:{port}")

        except Exception as e:
            status = 'error'
            response_time = None
            logger.debug(f"服务器测试错误: {host}:{port} - {e}")

        return {
            'host': host,
            'port': port,
            'status': status,
            'response_time': response_time,
            'last_tested': datetime.now().isoformat(),
            'location': self._guess_location(host),
            'source': 'builtin'
        }

    def _guess_location(self, ip: str) -> str:
        """根据IP地址猜测服务器位置（详细描述）"""
        # 详细的IP地址位置映射 - 与pytdx hosts.py保持一致
        location_mapping = {
            # 上海电信主站
            '180.153.18.170': '上海电信主站Z1',
            '180.153.18.171': '上海电信主站Z2', 
            '180.153.18.172': '上海电信主站Z80',
            '180.153.39.51': '上海电信主站Z3',
            
            # 北京联通主站
            '202.108.253.130': '北京联通主站Z1',
            '202.108.253.131': '北京联通主站Z2',
            '202.108.253.139': '北京联通主站Z80',
            
            # 杭州系列
            '60.191.117.167': '杭州电信主站J1',
            '115.238.56.198': '杭州电信主站J2',
            '218.75.126.9': '杭州电信主站J3',
            '115.238.90.165': '杭州电信主站J4',
            '124.160.88.183': '杭州联通主站J1',
            '60.12.136.250': '杭州联通主站J2',
            '218.108.98.244': '杭州华数主站J1',
            '218.108.47.69': '杭州华数主站J2',
            
            # 长城国瑞系列
            '218.85.139.19': '长城国瑞电信1',
            '218.85.139.20': '长城国瑞电信2',
            '58.23.131.163': '长城国瑞网通',
            
            # 上证云系列
            '218.6.170.47': '上证云成都电信一',
            '123.125.108.14': '上证云北京联通一',
            
            # 云行情系列
            '114.80.63.12': '云行情上海电信Z1',
            '114.80.63.35': '云行情上海电信Z2',
            
            # 其他地区
            '223.94.89.115': '义乌移动主站J1',
            '218.57.11.101': '青岛联通主站W1',
            '58.58.33.123': '青岛电信主站W1',
            '14.17.75.71': '深圳电信主站Z1',
            '119.147.212.81': '招商证券深圳行情',
            
            # 华泰证券系列
            '221.231.141.60': '华泰证券(南京电信)',
            '101.227.73.20': '华泰证券(上海电信)',
            '101.227.77.254': '华泰证券(上海电信二)',
            '14.215.128.18': '华泰证券(深圳电信)',
            '59.173.18.140': '华泰证券(武汉电信)',
            '60.28.23.80': '华泰证券(天津联通)',
            '218.60.29.136': '华泰证券(沈阳联通)',
            '122.192.35.44': '华泰证券(南京联通)',
        }

        # 首先检查精确匹配
        if ip in location_mapping:
            return location_mapping[ip]
        
        # 如果没有精确匹配，使用前缀匹配
        prefix_mapping = {
            '119.147.': '深圳地区',
            '114.80.': '上海地区',
            '113.105.': '广州地区',
            '180.153.': '上海地区',
            '124.74.': '北京地区',
            '218.75.': '杭州地区',
            '218.4.': '上海地区',
            '140.207.': '上海地区',
            '59.173.': '武汉地区',
            '202.108.': '北京地区',
            '60.191.': '杭州地区',
            '115.238.': '杭州地区',
            '124.160.': '杭州地区',
            '218.108.': '杭州地区',
            '218.85.': '国瑞系列',
            '58.23.': '国瑞系列',
            '218.6.': '成都地区',
            '123.125.': '北京地区',
            '223.94.': '义乌地区',
            '218.57.': '青岛地区',
            '58.58.': '青岛地区',
            '14.17.': '深圳地区',
            '221.231.': '南京地区',
            '101.227.': '上海地区',
            '14.215.': '深圳地区',
            '60.28.': '天津地区',
            '218.60.': '沈阳地区',
            '122.192.': '南京地区',
        }

        for prefix, location in prefix_mapping.items():
            if ip.startswith(prefix):
                return location

        return f'未知地区({ip})'

    async def get_fastest_servers(self, limit: int = 5) -> List[Dict]:
        """获取最快的服务器"""
        all_servers = await self.discover_servers(include_online=True, test_connectivity=True)

        # 筛选可用服务器并按响应时间排序
        available_servers = [
            server for server in all_servers
            if server['status'] == 'available' and server['response_time'] is not None
        ]

        available_servers.sort(key=lambda x: x['response_time'])

        return available_servers[:limit]

    async def update_server_database(self, database_manager) -> int:
        """更新数据库中的服务器列表"""
        try:
            # 发现服务器
            servers = await self.discover_servers(include_online=True, test_connectivity=True)

            # 保存到数据库
            updated_count = 0
            for server in servers:
                success = database_manager.save_tdx_server(
                    host=server['host'],
                    port=server['port'],
                    status=server['status'],
                    response_time=server['response_time'],
                    location=server['location'],
                    last_tested=server['last_tested']
                )
                if success:
                    updated_count += 1

            logger.info(f"数据库更新完成，共更新 {updated_count} 个服务器")
            return updated_count

        except Exception as e:
            logger.error(f"更新服务器数据库失败: {e}")
            return 0

# 全局服务实例
_discovery_service = None

def get_discovery_service() -> TdxServerDiscoveryService:
    """获取服务发现实例"""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = TdxServerDiscoveryService()
    return _discovery_service

# 便捷函数
async def discover_tdx_servers(include_online: bool = True) -> List[Dict]:
    """发现TDX服务器的便捷函数"""
    service = get_discovery_service()
    return await service.discover_servers(include_online=include_online)

async def get_fastest_tdx_servers(limit: int = 5) -> List[Dict]:
    """获取最快TDX服务器的便捷函数"""
    service = get_discovery_service()
    return await service.get_fastest_servers(limit=limit)

def discover_servers() -> List[Dict]:
    """
    同步版本的服务器发现函数

    Returns:
        List[Dict]: 服务器列表，每个元素包含host, port, description等信息
    """
    try:
        service = get_discovery_service()
        # 使用asyncio运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            servers = loop.run_until_complete(service.discover_servers())
            return servers
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"同步服务器发现失败: {e}")
        # 返回内置服务器列表作为后备
        service = get_discovery_service()
        return [
            {
                "host": server[0],
                "ip": server[0],
                "port": server[1],
                "description": f"TDX服务器 {server[0]}",
                "response_time": 0,
                "availability": "unknown"
            }
            for server in service.builtin_servers[:10]
        ]
