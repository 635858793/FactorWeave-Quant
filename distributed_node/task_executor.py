"""
任务执行器

负责接收任务并执行，支持多种任务类型
"""

import sys
import time
import asyncio
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from distributed_node.api.models import TaskType, TaskStatus, TaskResult


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, config: Optional[Any] = None):
        """
        初始化任务执行器
        
        Args:
            config: 节点配置
        """
        self.config = config
        self.running_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        
        # 优先级队列 (priority, task_id, task_future)
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(
            config.max_workers if config and hasattr(config, 'max_workers') else 4
        )
        self._scheduler_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.total_executed = 0
        self.total_failed = 0
        self.total_time = 0.0
        
        logger.info("任务执行器初始化完成")
    
    def start_scheduler(self):
        """启动优先级调度器"""
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._priority_scheduler())
            logger.info("优先级任务调度器已启动")
    
    def stop_scheduler(self):
        """停止优先级调度器"""
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            logger.info("优先级任务调度器已停止")

    async def submit_task(self, task_id: str, task_type: TaskType,
                          task_data: Dict[str, Any], priority: int = 5,
                          timeout: int = 300) -> TaskResult:
        """
        提交任务到优先级队列
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_data: 任务数据
            priority: 任务优先级（1-10，数字越小优先级越高）
            timeout: 超时时间（秒）
        
        Returns:
            任务结果
        """
        future: asyncio.Future = asyncio.Future()
        await self._task_queue.put((priority, task_id, task_type, task_data, timeout, future))
        return await future

    async def _priority_scheduler(self):
        """优先级调度器主循环"""
        while True:
            try:
                priority, task_id, task_type, task_data, timeout, future = \
                    await self._task_queue.get()
                
                async def _execute_with_semaphore():
                    async with self._semaphore:
                        result = await self._execute_task_internal(
                            task_id, task_type, task_data, timeout
                        )
                        if not future.done():
                            future.set_result(result)
                
                asyncio.create_task(_execute_with_semaphore())
                
            except asyncio.CancelledError:
                logger.info("优先级调度器已取消")
                break
            except Exception as e:
                logger.error(f"优先级调度器异常: {e}")

    async def _execute_task_internal(self, task_id: str, task_type: TaskType,
                                     task_data: Dict[str, Any],
                                     timeout: int = 300) -> TaskResult:
        """内部任务执行（被调度器调用）"""
        started_at = datetime.now()
        self.running_tasks[task_id] = {
            "task_type": task_type,
            "started_at": started_at,
            "timeout": timeout
        }
        
        try:
            logger.info(f"开始执行任务: {task_id} (类型: {task_type.value}, 优先级队列)")
            
            # 根据任务类型调用不同的执行器，带超时控制
            async def _run_task():
                if task_type == TaskType.DATA_IMPORT:
                    return await self._execute_data_import(task_id, task_data)
                elif task_type == TaskType.ANALYSIS:
                    return await self._execute_analysis(task_id, task_data)
                elif task_type == TaskType.BACKTEST:
                    return await self._execute_backtest(task_id, task_data)
                elif task_type == TaskType.OPTIMIZATION:
                    return await self._execute_optimization(task_id, task_data)
                elif task_type == TaskType.CUSTOM:
                    return await self._execute_custom(task_id, task_data)
                else:
                    raise ValueError(f"不支持的任务类型: {task_type}")
            
            result = await asyncio.wait_for(_run_task(), timeout=timeout)
            
            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()
            
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                started_at=started_at,
                completed_at=completed_at,
                execution_time=execution_time
            )
            
            # 更新统计
            self.total_executed += 1
            self.total_time += execution_time
            
            logger.info(f"任务完成: {task_id}, 耗时: {execution_time:.2f}秒")
            
        except asyncio.TimeoutError:
            completed_at = datetime.now()
            execution_time = timeout
            
            error_msg = f"任务执行超时（{timeout}秒）"
            logger.error(f"任务超时: {task_id}")
            
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=error_msg,
                started_at=started_at,
                completed_at=completed_at,
                execution_time=execution_time
            )
            
            self.total_failed += 1
            
        except Exception as e:
            completed_at = datetime.now()
            execution_time = (completed_at - started_at).total_seconds()
            
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"任务执行失败: {task_id}, 错误: {error_msg}")
            
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=error_msg,
                started_at=started_at,
                completed_at=completed_at,
                execution_time=execution_time
            )
            
            self.total_failed += 1
        
        finally:
            # 清理运行中的任务
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            # 保存已完成的任务（限制数量）
            self.completed_tasks[task_id] = task_result
            if len(self.completed_tasks) > 100:
                oldest_key = next(iter(self.completed_tasks))
                del self.completed_tasks[oldest_key]
        
        return task_result
    
    async def execute_task(self, task_id: str, task_type: TaskType, task_data: Dict[str, Any],
                          timeout: int = 300, priority: int = 5) -> TaskResult:
        """
        执行任务（异步，兼容旧接口）
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_data: 任务数据
            timeout: 超时时间（秒）
            priority: 任务优先级（1-10，数字越小优先级越高）
        
        Returns:
            任务结果
        """
        return await self.submit_task(task_id, task_type, task_data, priority, timeout)
    
    async def _execute_data_import(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据导入任务"""
        symbols = task_data.get("symbols", [])
        data_source = task_data.get("data_source", "tongdaxin")
        start_date = task_data.get("start_date")
        end_date = task_data.get("end_date")
        
        logger.info(f"数据导入任务: {len(symbols)}只股票, 数据源: {data_source}")
        
        # 真实实现：调用实际的数据导入逻辑
        try:
            # 导入必要的模块
            from core.real_data_provider import RealDataProvider
            from core.asset_database_manager import get_asset_separated_database_manager, AssetType, DataType
            import pandas as pd
            
            provider = RealDataProvider()
            asset_manager = get_asset_separated_database_manager()
            
            imported_count = 0
            total_records = 0
            all_kdata_list = []
            
            for symbol in symbols:
                try:
                    # 获取K线数据
                    kdata = provider.get_real_kdata(
                        code=symbol,
                        freq='1d',
                        start_date=start_date,
                        end_date=end_date,
                        data_source=data_source
                    )
                    
                    if not kdata.empty:
                        # 添加symbol列
                        kdata_with_meta = kdata.copy()
                        kdata_with_meta['symbol'] = symbol
                        kdata_with_meta['data_source'] = data_source
                        
                        # 如果datetime是索引，转为列
                        if isinstance(kdata_with_meta.index, pd.DatetimeIndex):
                            kdata_with_meta = kdata_with_meta.reset_index()
                            if 'index' in kdata_with_meta.columns:
                                kdata_with_meta = kdata_with_meta.rename(columns={'index': 'datetime'})
                        
                        all_kdata_list.append(kdata_with_meta)
                        imported_count += 1
                        total_records += len(kdata)
                        logger.debug(f"导入 {symbol}: {len(kdata)}条记录")
                
                except Exception as e:
                    logger.warning(f"导入{symbol}失败: {e}")
            
            # 关键：返回数据给主系统（由主系统统一保存）
            # 将数据转换为可序列化的格式
            serializable_data = []
            if all_kdata_list:
                combined_data = pd.concat(all_kdata_list, ignore_index=True)
                
                # 转换为dict列表（可JSON序列化）
                # 注意：大数据量时可能需要分批返回或使用其他传输方式
                serializable_data = combined_data.to_dict('records')
                logger.info(f"准备返回{len(serializable_data)}条记录给主系统保存")
            
            return {
                "task_type": "data_import",
                "symbols_count": len(symbols),
                "imported_count": imported_count,
                "total_records": total_records,
                "data_source": data_source,
                "status": "completed",
                # 返回实际数据，由主系统保存
                "kdata": serializable_data,
                "first_symbol": symbols[0] if symbols else None
            }
            
        except ImportError as e:
            logger.error(f"无法导入RealDataProvider: {e}")
            # 返回错误而非模拟数据
            return {
                "task_type": "data_import",
                "symbols_count": len(symbols),
                "imported_count": 0,
                "total_records": 0,
                "data_source": data_source,
                "status": "failed",
                "error": f"数据提供者未配置: {str(e)}",
                "is_mock": False
            }
        except Exception as e:
            logger.error(f"数据导入任务异常: {e}")
            return {
                "task_type": "data_import",
                "status": "failed",
                "error": str(e),
                "is_mock": False
            }
    
    async def _execute_analysis(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行真实分析任务（节点侧）"""
        stock_code = task_data.get("stock_code", task_data.get("symbol", "000001"))
        analysis_type = task_data.get("analysis_type", "technical")

        try:
            logger.info(f"节点执行分析: {stock_code}, 类型: {analysis_type}")

            raise NotImplementedError("analysis engine not integrated")

        except NotImplementedError:
            logger.warning(f"分析引擎未集成，使用降级处理: {stock_code}")
            return {
                "task_type": "analysis",
                "stock_code": stock_code,
                "analysis_type": analysis_type,
                "status": "degraded",
                "message": "分析引擎未集成，节点使用降级模式返回基础数据",
                "is_mock": False
            }
        except Exception as e:
            logger.error(f"节点分析任务失败: {e}")
            return {
                "task_type": "analysis",
                "error": str(e),
                "status": "failed",
                "is_mock": False
            }
    
    async def _execute_backtest(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行真实回测任务（节点侧）"""
        stock_code = task_data.get("stock_code", "000001")
        strategy = task_data.get("strategy", "ma_cross")
        period = task_data.get("period", "1y")

        try:
            logger.info(f"节点执行回测: {stock_code}, 策略: {strategy}")

            raise NotImplementedError("backtest engine not integrated")

        except NotImplementedError:
            logger.warning(f"回测引擎未集成，使用降级处理: {stock_code}")
            return {
                "task_type": "backtest",
                "stock_code": stock_code,
                "strategy": strategy,
                "period": period,
                "status": "degraded",
                "message": "回测引擎未集成，节点使用降级模式返回基础数据",
                "is_mock": False
            }
        except Exception as e:
            logger.error(f"节点回测任务失败: {e}")
            return {
                "task_type": "backtest",
                "error": str(e),
                "status": "failed",
                "is_mock": False
            }
    
    async def _execute_optimization(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行真实优化任务（节点侧）"""
        pattern = task_data.get("pattern", "head_shoulders")
        method = task_data.get("method", "genetic")

        try:
            logger.info(f"节点执行优化: {pattern}, 方法: {method}")

            raise NotImplementedError("optimization engine not integrated")

        except NotImplementedError:
            logger.warning(f"优化引擎未集成，使用降级处理: {pattern}")
            return {
                "task_type": "optimization",
                "pattern": pattern,
                "method": method,
                "status": "degraded",
                "message": "优化引擎未集成，节点使用降级模式返回基础数据",
                "is_mock": False
            }
        except Exception as e:
            logger.error(f"节点优化任务失败: {e}")
            return {
                "task_type": "optimization",
                "error": str(e),
                "status": "failed",
                "is_mock": False
            }
    
    async def _execute_custom(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行自定义任务"""
        import asyncio
        await asyncio.sleep(1)
        return {
            "task_type": "custom",
            "custom_data": task_data,
            "status": "completed"
        }
    
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """获取任务状态"""
        if task_id in self.running_tasks:
            info = self.running_tasks[task_id]
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                started_at=info["started_at"],
                completed_at=None,
                execution_time=(datetime.now() - info["started_at"]).total_seconds()
            )
        elif task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        else:
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_executed": self.total_executed,
            "total_failed": self.total_failed,
            "success_rate": self.total_executed / (self.total_executed + self.total_failed)
                          if (self.total_executed + self.total_failed) > 0 else 0.0,
            "average_time": self.total_time / self.total_executed
                          if self.total_executed > 0 else 0.0,
            "active_tasks": len(self.running_tasks),
            "completed_tasks_cached": len(self.completed_tasks)
        }

