"""
分布式HTTP桥接模块

提供HTTP远程调用和本地fallback机制
当有可用节点时通过HTTP调用，否则本地执行

作者: FactorWeave-Quant团队
版本: 1.0.0
日期: 2025-10-23
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

# HTTP客户端
try:
    import httpx
    HTTP_AVAILABLE = True
except ImportError:
    logger.warning("httpx未安装，仅支持本地执行模式")
    HTTP_AVAILABLE = False

from distributed_node.api.models import TaskType, TaskRequest, TaskResult, NodeHealth


class DistributedHTTPBridge:
    """分布式HTTP桥接器"""

    def __init__(self):
        """初始化HTTP桥接器"""
        self.http_client: Optional[httpx.AsyncClient] = None
        self.available_nodes: Dict[str, Dict[str, Any]] = {}
        self.node_health_cache: Dict[str, NodeHealth] = {}

        if HTTP_AVAILABLE:
            self.http_client = httpx.AsyncClient(timeout=300.0)
            logger.info("HTTP桥接器初始化成功")
        else:
            logger.warning("HTTP桥接器以本地模式运行")

    async def execute_task(self,
                           task_id: str,
                           task_type: str,
                           task_data: Dict[str, Any],
                           priority: int = 5,
                           timeout: int = 300) -> TaskResult:
        """
        执行任务（自动选择远程或本地）

        支持任务自动拆分到多个节点并行执行

        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_data: 任务数据
            priority: 优先级
            timeout: 超时时间

        Returns:
            任务结果
        """
        # 检查是否有可用节点
        if self.has_available_nodes():
            try:
                # 新逻辑：支持任务拆分到多个节点
                return await self._execute_distributed(
                    task_id, task_type, task_data, priority, timeout
                )
            except Exception as e:
                logger.warning(f"分布式执行失败，切换到本地执行: {e}")
                return await self._execute_locally(task_id, task_type, task_data, timeout)
        else:
            logger.info("无可用节点，使用本地执行")
            return await self._execute_locally(task_id, task_type, task_data, timeout)

    async def _execute_distributed(self,
                                   task_id: str,
                                   task_type: str,
                                   task_data: Dict[str, Any],
                                   priority: int,
                                   timeout: int) -> TaskResult:
        """
        分布式执行任务（支持任务拆分和多节点并行）

        逻辑：
        1. 如果任务可拆分（如多个股票），拆分到多个节点并行
        2. 如果任务不可拆分，选择单个最佳节点
        3. 收集所有节点的结果并合并
        """
        # 检查任务是否可拆分（当前支持data_import类型的股票列表拆分）
        if task_type == "data_import" and "symbols" in task_data:
            symbols = task_data["symbols"]
            available_nodes = self.get_available_nodes()

            # 如果有多只股票且有多个节点，进行拆分
            if len(symbols) > 1 and len(available_nodes) > 1:
                logger.info(f"任务拆分：{len(symbols)}只股票 → {len(available_nodes)}个节点")
                return await self._execute_split_task(
                    task_id, task_type, task_data, priority, timeout
                )

        # 不可拆分或单节点，使用原有逻辑
        return await self._execute_on_single_node(
            task_id, task_type, task_data, priority, timeout
        )

    async def _execute_split_task(self,
                                  task_id: str,
                                  task_type: str,
                                  task_data: Dict[str, Any],
                                  priority: int,
                                  timeout: int) -> TaskResult:
        """拆分任务到多个节点并行执行"""
        symbols = task_data["symbols"]
        available_nodes = self.get_available_nodes()

        # 将股票列表分配到各个节点
        import math
        symbols_per_node = math.ceil(len(symbols) / len(available_nodes))

        sub_tasks = []
        for i, node in enumerate(available_nodes):
            start_idx = i * symbols_per_node
            end_idx = min(start_idx + symbols_per_node, len(symbols))

            if start_idx >= len(symbols):
                break

            sub_symbols = symbols[start_idx:end_idx]
            sub_task_id = f"{task_id}_node{i}_{node['node_id']}"

            # 创建子任务数据
            sub_task_data = task_data.copy()
            sub_task_data["symbols"] = sub_symbols

            logger.info(f"子任务 {sub_task_id}: {len(sub_symbols)}只股票 → 节点 {node['node_id']}")

            # 创建异步任务
            sub_task = self._execute_on_specific_node(
                node, sub_task_id, task_type, sub_task_data, priority, timeout
            )
            sub_tasks.append(sub_task)

        # 并行等待所有子任务完成
        logger.info(f"并行执行 {len(sub_tasks)} 个子任务...")
        results = await asyncio.gather(*sub_tasks, return_exceptions=True)

        # 合并结果并收集所有节点返回的数据
        total_imported = 0
        total_records = 0
        failed_nodes = []
        all_kdata = []  # 收集所有节点的数据

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"子任务 {i} 失败: {result}")
                failed_nodes.append(i)
            elif result.status == "completed":
                if result.result:
                    total_imported += result.result.get("imported_count", 0)
                    total_records += result.result.get("total_records", 0)

                    # 收集节点返回的数据
                    node_kdata = result.result.get("kdata", [])
                    if node_kdata:
                        all_kdata.extend(node_kdata)
            else:
                failed_nodes.append(i)

        # 关键：主系统统一保存所有节点返回的数据
        saved_to_db = False
        if all_kdata:
            try:
                logger.info(f"主系统开始保存{len(all_kdata)}条记录到数据库...")

                from core.asset_database_manager import get_asset_separated_database_manager, AssetType, DataType
                import pandas as pd

                # 转换为DataFrame
                combined_data = pd.DataFrame(all_kdata)

                # 确定资产类型
                first_symbol = symbols[0]
                asset_type = AssetType.STOCK_A if str(first_symbol).endswith(('.SZ', '.SH')) else AssetType.STOCK_A

                # 保存到主系统数据库
                asset_manager = get_asset_separated_database_manager()
                success = asset_manager.store_standardized_data(
                    data=combined_data,
                    asset_type=asset_type,
                    data_type=DataType.HISTORICAL_KLINE
                )

                if success:
                    saved_to_db = True
                    logger.info(f"主系统已保存数据: {asset_type.value}, {len(combined_data)}条记录")
                else:
                    logger.error(f"❌ 主系统数据保存失败")

            except Exception as e:
                logger.error(f"❌ 主系统保存数据异常: {e}")

        # 构建合并结果
        merged_result = TaskResult(
            task_id=task_id,
            status="completed" if not failed_nodes else "partial_completed",
            result={
                "task_type": "data_import",
                "symbols_count": len(symbols),
                "imported_count": total_imported,
                "total_records": total_records,
                "data_source": task_data.get("data_source"),
                "distributed": True,
                "nodes_used": len(sub_tasks),
                "failed_nodes": len(failed_nodes),
                "saved_to_db": saved_to_db,  # 标记数据是否已保存
                "status": "completed"
            },
            started_at=datetime.now(),
            completed_at=datetime.now(),
            execution_time=0.0
        )

        logger.info(f"分布式任务完成: {total_imported}/{len(symbols)}只股票, {total_records}条记录, "
                    f"使用{len(sub_tasks)}个节点, 失败{len(failed_nodes)}个, 数据已保存: {saved_to_db}")

        return merged_result

    async def _execute_on_specific_node(self,
                                        node: Dict[str, Any],
                                        task_id: str,
                                        task_type: str,
                                        task_data: Dict[str, Any],
                                        priority: int,
                                        timeout: int) -> TaskResult:
        """在指定节点上执行任务"""
        logger.info(f"节点 {node['node_id']} 执行任务 {task_id}")

        # 构建任务请求
        task_request = TaskRequest(
            task_id=task_id,
            task_type=TaskType(task_type),
            task_data=task_data,
            priority=priority,
            timeout=timeout
        )

        # 发送HTTP请求
        url = f"http://{node['host']}:{node['port']}/api/v1/task/execute"

        try:
            response = await self.http_client.post(
                url,
                json=task_request.dict(),
                timeout=timeout
            )
            response.raise_for_status()

            # 等待任务完成
            task_result = await self._wait_for_task_completion(
                node, task_id, timeout
            )

            logger.info(f"任务 {task_id} 在节点 {node['node_id']} 上完成")
            return task_result

        except Exception as e:
            logger.error(f"节点 {node['node_id']} 执行失败: {e}")
            raise

    async def _execute_on_single_node(self,
                                      task_id: str,
                                      task_type: str,
                                      task_data: Dict[str, Any],
                                      priority: int,
                                      timeout: int) -> TaskResult:
        """在远程节点上执行任务"""
        # 选择最佳节点
        node = await self._select_best_node()

        if not node:
            raise Exception("没有可用节点")

        logger.info(f"选择节点 {node['node_id']} 执行任务 {task_id}")

        # 构建任务请求
        task_request = TaskRequest(
            task_id=task_id,
            task_type=TaskType(task_type),
            task_data=task_data,
            priority=priority,
            timeout=timeout
        )

        # 发送HTTP请求
        url = f"http://{node['host']}:{node['port']}/api/v1/task/execute"

        try:
            response = await self.http_client.post(
                url,
                json=task_request.dict(),
                timeout=timeout
            )
            response.raise_for_status()

            # 等待任务完成
            task_result = await self._wait_for_task_completion(
                node, task_id, timeout
            )

            logger.info(f"任务 {task_id} 在节点 {node['node_id']} 上完成")
            return task_result

        except Exception as e:
            logger.error(f"HTTP调用失败: {e}")
            raise

    async def _wait_for_task_completion(self,
                                        node: Dict[str, Any],
                                        task_id: str,
                                        timeout: int) -> TaskResult:
        """等待任务完成"""
        url = f"http://{node['host']}:{node['port']}/api/v1/task/{task_id}/status"

        start_time = datetime.now()
        poll_interval = 1.0  # 1秒轮询一次

        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                response = await self.http_client.get(url, timeout=10.0)
                response.raise_for_status()

                result_data = response.json()
                task_result = TaskResult(**result_data)

                if task_result.status in ["completed", "failed", "cancelled"]:
                    return task_result

                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.warning(f"轮询任务状态失败: {e}")
                await asyncio.sleep(poll_interval)

        # 超时
        raise TimeoutError(f"任务 {task_id} 执行超时")

    async def _execute_locally(self,
                               task_id: str,
                               task_type: str,
                               task_data: Dict[str, Any],
                               timeout: int) -> TaskResult:
        """本地执行任务（fallback模式）"""
        logger.info(f"本地执行任务: {task_id} (类型: {task_type})")

        # 导入本地执行器
        from distributed_node.task_executor import TaskExecutor

        executor = TaskExecutor()

        try:
            result = await executor.execute_task(
                task_id,
                TaskType(task_type),
                task_data,
                timeout
            )

            # 本地执行时也需要保存数据到主系统数据库
            if task_type == "data_import" and result.result:
                kdata = result.result.get("kdata", [])
                if kdata:
                    try:
                        logger.info(f"本地执行：保存{len(kdata)}条记录到数据库...")

                        from core.asset_database_manager import get_asset_separated_database_manager, AssetType, DataType
                        import pandas as pd

                        combined_data = pd.DataFrame(kdata)

                        symbols = task_data.get("symbols", [])
                        if symbols:
                            first_symbol = symbols[0]
                            asset_type = AssetType.STOCK_A if str(first_symbol).endswith(('.SZ', '.SH')) else AssetType.STOCK_A

                            asset_manager = get_asset_separated_database_manager()
                            success = asset_manager.store_standardized_data(
                                data=combined_data,
                                asset_type=asset_type,
                                data_type=DataType.HISTORICAL_KLINE
                            )

                            if success:
                                result.result["saved_to_db"] = True
                                logger.info(f"本地执行：数据已保存: {len(combined_data)}条记录")
                            else:
                                result.result["saved_to_db"] = False
                                logger.error(f"❌ 本地执行：数据保存失败")
                    except Exception as e:
                        logger.error(f"❌ 本地执行保存数据异常: {e}")
                        result.result["saved_to_db"] = False

            logger.info(f"本地任务完成: {task_id}")
            return result
        except Exception as e:
            logger.error(f"本地执行失败: {e}")
            raise

    async def _select_best_node(self) -> Optional[Dict[str, Any]]:
        """选择最佳节点（基于负载和健康状态）"""
        if not self.available_nodes:
            return None

        best_node = None
        best_score = -1

        for node_id, node in self.available_nodes.items():
            # 获取节点健康状态
            health = await self._get_node_health(node)

            if not health or health.status != "healthy":
                continue

            # 计算评分（负载越低越好）
            score = 100.0 - (health.cpu_percent * 0.5 + health.memory_percent * 0.3 +
                             health.active_tasks * 10)

            if score > best_score:
                best_score = score
                best_node = node

        return best_node

    async def _get_node_health(self, node: Dict[str, Any]) -> Optional[NodeHealth]:
        """获取节点健康状态"""
        node_id = node['node_id']

        # 检查缓存（30秒有效期）
        if node_id in self.node_health_cache:
            cached_health = self.node_health_cache[node_id]
            if (datetime.now() - cached_health.last_heartbeat).total_seconds() < 30:
                return cached_health

        # 请求健康状态
        url = f"http://{node['host']}:{node['port']}/api/v1/health"

        try:
            response = await self.http_client.get(url, timeout=5.0)
            response.raise_for_status()

            health_data = response.json()
            health = NodeHealth(**health_data)

            # 更新缓存
            self.node_health_cache[node_id] = health

            return health

        except Exception as e:
            logger.warning(f"获取节点健康状态失败 {node_id}: {e}")
            # 从可用节点列表中移除
            if node_id in self.available_nodes:
                del self.available_nodes[node_id]
            return None

    def add_node(self, node_id: str, host: str, port: int, **kwargs):
        """添加节点"""
        self.available_nodes[node_id] = {
            'node_id': node_id,
            'host': host,
            'port': port,
            **kwargs
        }
        logger.info(f"添加节点: {node_id} ({host}:{port})")

    def remove_node(self, node_id: str):
        """移除节点"""
        if node_id in self.available_nodes:
            del self.available_nodes[node_id]
            logger.info(f"移除节点: {node_id}")

    def has_available_nodes(self) -> bool:
        """是否有可用节点"""
        return len(self.available_nodes) > 0 and HTTP_AVAILABLE

    def get_available_nodes(self) -> List[Dict[str, Any]]:
        """获取可用节点列表"""
        return list(self.available_nodes.values())

    async def close(self):
        """关闭HTTP客户端"""
        if self.http_client:
            await self.http_client.aclose()
            logger.info("HTTP桥接器已关闭")


# 全局实例
_global_bridge: Optional[DistributedHTTPBridge] = None


def get_distributed_bridge() -> DistributedHTTPBridge:
    """获取全局HTTP桥接器实例"""
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = DistributedHTTPBridge()
    return _global_bridge
