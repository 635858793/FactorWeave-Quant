#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
from core.services.unified_data_manager import get_unified_data_manager
数据缺失智能管理器
负责检测数据缺失、分析原因、提供解决方案
"""

import asyncio
from typing import Dict, List, Optional, Callable, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    from core.plugin_types import AssetType, DataType, PluginType
    from core.asset_type_identifier import AssetTypeIdentifier
    from core.data_router import DataRouter, DataRequest
    from core.asset_database_manager import AssetSeparatedDatabaseManager
    from loguru import logger
except ImportError as e:
    print(f"导入核心组件失败: {e}")
    logger = None

class DataAvailabilityStatus(Enum):
    """数据可用性状态"""
    AVAILABLE = "available"  # 数据可用
    MISSING = "missing"  # 数据缺失
    PARTIAL = "partial"  # 部分数据
    OUTDATED = "outdated"  # 数据过期
    ERROR = "error"  # 错误状态

@dataclass
class DataAvailabilityInfo:
    """数据可用性信息"""
    symbol: str
    asset_type: AssetType
    data_type: DataType
    status: DataAvailabilityStatus
    available_range: Optional[Tuple[datetime, datetime]] = None
    missing_ranges: List[Tuple[datetime, datetime]] = field(default_factory=list)
    suggested_plugins: List[str] = field(default_factory=list)
    error_message: str = ""
    last_check: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1-5, 5最高优先级

@dataclass
class DataDownloadTask:
    """数据下载任务"""
    task_id: str
    symbol: str
    asset_type: AssetType
    data_type: DataType
    date_range: Tuple[datetime, datetime]
    plugin_name: str
    status: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class DataMissingManager:
    """数据缺失智能管理器"""

    def __init__(self):
        self.asset_identifier = None
        self.data_router = None
        self.data_manager = None
        self.db_manager = None

        # 缓存和状态
        self.availability_cache: Dict[str, DataAvailabilityInfo] = {}
        self.download_tasks: Dict[str, DataDownloadTask] = {}
        self.plugin_status_cache: Dict[str, bool] = {}

        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="DataMissingManager")

        # 回调函数
        self.data_missing_callbacks: List[Callable] = []
        self.download_progress_callbacks: List[Callable] = []

        # R237 HVD-237-B-005: dispose 幂等标志 (R78 铁律 #6)
        self._disposed = False

        # 初始化
        self._initialize_components()

    def _initialize_components(self):
        """初始化核心组件"""
        try:
            from core.services.unified_data_manager import get_unified_data_manager
            self.asset_identifier = AssetTypeIdentifier()
            self.data_router = DataRouter()
            self.data_manager = get_unified_data_manager()
            self.db_manager = AssetSeparatedDatabaseManager()

            if logger:
                logger.info("数据缺失管理器初始化完成")
        except Exception as e:
            if logger:
                logger.error(f"初始化数据缺失管理器失败: {e}")

    def register_data_missing_callback(self, callback: Callable):
        """注册数据缺失回调"""
        self.data_missing_callbacks.append(callback)

    def register_download_progress_callback(self, callback: Callable):
        """注册下载进度回调"""
        self.download_progress_callbacks.append(callback)

    def check_data_availability(self, symbol: str, data_type: DataType,
                                date_range: Optional[Tuple[datetime, datetime]] = None) -> DataAvailabilityInfo:
        """检查数据可用性"""
        try:
            # 识别资产类型
            asset_type = self.asset_identifier.identify_asset_type(symbol) if self.asset_identifier else AssetType.STOCK_A

            # 生成缓存键
            cache_key = f"{symbol}_{asset_type.value}_{data_type.value}"

            # 检查缓存
            if cache_key in self.availability_cache:
                cached_info = self.availability_cache[cache_key]
                # 如果缓存未过期（5分钟内），直接返回
                if (datetime.now() - cached_info.last_check).seconds < 300:
                    return cached_info

            # 执行实际检查
            availability_info = self._perform_availability_check(symbol, asset_type, data_type, date_range)

            # 更新缓存
            self.availability_cache[cache_key] = availability_info

            # 如果数据缺失，触发回调
            if availability_info.status in [DataAvailabilityStatus.MISSING, DataAvailabilityStatus.PARTIAL]:
                for callback in self.data_missing_callbacks:
                    try:
                        callback(availability_info)
                    except Exception as e:
                        if logger:
                            logger.error(f"数据缺失回调执行失败: {e}")

            return availability_info

        except Exception as e:
            if logger:
                logger.error(f"检查数据可用性失败: {e}")

            return DataAvailabilityInfo(
                symbol=symbol,
                asset_type=AssetType.STOCK_A,
                data_type=data_type,
                status=DataAvailabilityStatus.ERROR,
                error_message=str(e)
            )

    def _perform_availability_check(self, symbol: str, asset_type: AssetType,
                                    data_type: DataType, date_range: Optional[Tuple[datetime, datetime]]) -> DataAvailabilityInfo:
        """执行实际的可用性检查"""
        try:
            # 检查数据库中的数据
            if not self.db_manager:
                raise Exception("数据库管理器未初始化")

            # 获取数据库连接
            db_path = self.db_manager.get_database_path(asset_type)

            if not db_path or not db_path.exists():
                # 数据库不存在，数据完全缺失
                return DataAvailabilityInfo(
                    symbol=symbol,
                    asset_type=asset_type,
                    data_type=data_type,
                    status=DataAvailabilityStatus.MISSING,
                    suggested_plugins=self._get_suggested_plugins(asset_type, data_type),
                    error_message="数据库不存在"
                )

            # 查询数据范围
            available_range, missing_ranges = self._check_data_range(symbol, asset_type, data_type, date_range)

            # 确定状态
            if not available_range:
                status = DataAvailabilityStatus.MISSING
            elif missing_ranges:
                status = DataAvailabilityStatus.PARTIAL
            else:
                # 检查数据是否过期
                if available_range[1] < datetime.now() - timedelta(days=1):
                    status = DataAvailabilityStatus.OUTDATED
                else:
                    status = DataAvailabilityStatus.AVAILABLE

            return DataAvailabilityInfo(
                symbol=symbol,
                asset_type=asset_type,
                data_type=data_type,
                status=status,
                available_range=available_range,
                missing_ranges=missing_ranges,
                suggested_plugins=self._get_suggested_plugins(asset_type, data_type)
            )

        except Exception as e:
            if logger:
                logger.error(f"执行可用性检查失败: {e}")

            return DataAvailabilityInfo(
                symbol=symbol,
                asset_type=asset_type,
                data_type=data_type,
                status=DataAvailabilityStatus.ERROR,
                error_message=str(e)
            )

    def _check_data_range(self, symbol: str, asset_type: AssetType, data_type: DataType,
                          date_range: Optional[Tuple[datetime, datetime]]) -> Tuple[Optional[Tuple[datetime, datetime]], List[Tuple[datetime, datetime]]]:
        """检查数据范围"""
        try:
            # 这里应该查询实际的数据库
            # 为了演示，返回模拟结果

            # 模拟：假设有部分数据
            if symbol.startswith("00"):  # 深圳股票
                available_start = datetime.now() - timedelta(days=30)
                available_end = datetime.now() - timedelta(days=1)
                available_range = (available_start, available_end)

                # 如果请求的范围更大，计算缺失范围
                missing_ranges = []
                if date_range:
                    req_start, req_end = date_range
                    if req_start < available_start:
                        missing_ranges.append((req_start, available_start))
                    if req_end > available_end:
                        missing_ranges.append((available_end, req_end))

                return available_range, missing_ranges
            else:
                # 模拟：数据完全缺失
                return None, [(datetime.now() - timedelta(days=365), datetime.now())]

        except Exception as e:
            if logger:
                logger.error(f"检查数据范围失败: {e}")
            return None, []

    def _get_suggested_plugins(self, asset_type: AssetType, data_type: DataType) -> List[str]:
        """获取建议的插件"""
        suggestions = []

        try:
            if asset_type in [AssetType.STOCK_A, AssetType.STOCK_B]:
                suggestions.extend(["tongdaxin_stock_plugin", "eastmoney_stock_plugin", "sina_stock_plugin"])
            elif asset_type == AssetType.CRYPTO:
                suggestions.extend(["binance_plugin", "coinbase_plugin"])
            elif asset_type == AssetType.STOCK_US:
                suggestions.extend(["yahoo_finance_plugin", "alpha_vantage_plugin"])
            elif asset_type == AssetType.STOCK_HK:
                suggestions.extend(["tencent_stock_plugin", "sina_hk_plugin"])

            # 根据数据类型过滤
            if data_type == DataType.REAL_TIME_QUOTE:
                # 实时数据优先推荐快速源
                suggestions = [p for p in suggestions if "sina" in p or "tencent" in p] + suggestions

        except Exception as e:
            if logger:
                logger.error(f"获取建议插件失败: {e}")

        return suggestions[:5]  # 最多返回5个建议

    def create_download_task(self, symbol: str, asset_type: AssetType, data_type: DataType,
                             date_range: Tuple[datetime, datetime], plugin_name: str = "") -> str:
        """创建下载任务"""
        try:
            # 生成任务ID
            task_id = f"download_{symbol}_{data_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 如果未指定插件，自动选择
            if not plugin_name:
                suggested_plugins = self._get_suggested_plugins(asset_type, data_type)
                plugin_name = suggested_plugins[0] if suggested_plugins else "auto"

            # 创建任务
            task = DataDownloadTask(
                task_id=task_id,
                symbol=symbol,
                asset_type=asset_type,
                data_type=data_type,
                date_range=date_range,
                plugin_name=plugin_name
            )

            self.download_tasks[task_id] = task

            # 异步执行下载
            self.executor.submit(self._execute_download_task, task_id)

            if logger:
                logger.info(f"创建下载任务: {task_id}")

            return task_id

        except Exception as e:
            if logger:
                logger.error(f"创建下载任务失败: {e}")
            return ""

    def _execute_download_task(self, task_id: str):
        """执行下载任务"""
        try:
            task = self.download_tasks.get(task_id)
            if not task:
                return

            # 更新任务状态
            task.status = "running"
            task.started_at = datetime.now()
            self._notify_download_progress(task_id, 0.0, "开始下载")

            # 模拟下载过程
            for progress in [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
                if task.status != "running":  # 任务被取消
                    return

                task.progress = progress
                self._notify_download_progress(task_id, progress, f"下载进度: {progress*100:.0f}%")

                # 模拟下载时间
                import time
                time.sleep(1)

            # 完成任务
            task.status = "completed"
            task.completed_at = datetime.now()
            task.progress = 1.0
            self._notify_download_progress(task_id, 1.0, "下载完成")

            # 清除相关缓存
            cache_key = f"{task.symbol}_{task.asset_type.value}_{task.data_type.value}"
            if cache_key in self.availability_cache:
                del self.availability_cache[cache_key]

            if logger:
                logger.info(f"下载任务完成: {task_id}")

        except Exception as e:
            if logger:
                logger.error(f"执行下载任务失败: {e}")

            task = self.download_tasks.get(task_id)
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now()
                self._notify_download_progress(task_id, task.progress, f"下载失败: {e}")

    def _notify_download_progress(self, task_id: str, progress: float, message: str):
        """通知下载进度"""
        for callback in self.download_progress_callbacks:
            try:
                callback(task_id, progress, message)
            except Exception as e:
                if logger:
                    logger.error(f"下载进度回调执行失败: {e}")

    def get_download_task(self, task_id: str) -> Optional[DataDownloadTask]:
        """获取下载任务"""
        return self.download_tasks.get(task_id)

    def cancel_download_task(self, task_id: str) -> bool:
        """取消下载任务"""
        try:
            task = self.download_tasks.get(task_id)
            if task and task.status == "running":
                task.status = "cancelled"
                if logger:
                    logger.info(f"取消下载任务: {task_id}")
                return True
            return False
        except Exception as e:
            if logger:
                logger.error(f"取消下载任务失败: {e}")
            return False

    def get_active_tasks(self) -> List[DataDownloadTask]:
        """获取活跃任务"""
        return [task for task in self.download_tasks.values()
                if task.status in ["pending", "running"]]

    def cleanup_completed_tasks(self, older_than_hours: int = 24):
        """清理已完成的任务"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)

            tasks_to_remove = []
            for task_id, task in self.download_tasks.items():
                if (task.status in ["completed", "failed", "cancelled"] and
                        task.completed_at and task.completed_at < cutoff_time):
                    tasks_to_remove.append(task_id)

            for task_id in tasks_to_remove:
                del self.download_tasks[task_id]

            if logger and tasks_to_remove:
                logger.info(f"清理了 {len(tasks_to_remove)} 个已完成的任务")

        except Exception as e:
            if logger:
                logger.error(f"清理任务失败: {e}")

    def get_plugin_availability(self) -> Dict[str, bool]:
        """获取插件可用性"""
        try:
            # 这里应该查询实际的插件状态
            # 为了演示，返回模拟结果
            return {
                "tongdaxin_stock_plugin": True,
                "eastmoney_stock_plugin": True,
                "sina_stock_plugin": False,  # 模拟插件未启用
                "tencent_stock_plugin": True,
                "binance_plugin": False,
                "yahoo_finance_plugin": True
            }
        except Exception as e:
            if logger:
                logger.error(f"获取插件可用性失败: {e}")
            return {}

    def suggest_data_sources(self, symbol: str, data_type: DataType) -> List[Dict[str, Any]]:
        """建议数据源"""
        try:
            asset_type = self.asset_identifier.identify_asset_type(symbol) if self.asset_identifier else AssetType.STOCK_A
            suggested_plugins = self._get_suggested_plugins(asset_type, data_type)
            plugin_status = self.get_plugin_availability()

            suggestions = []
            for plugin in suggested_plugins:
                is_available = plugin_status.get(plugin, False)
                suggestions.append({
                    'plugin_name': plugin,
                    'display_name': plugin.replace('_plugin', '').replace('_', ' ').title(),
                    'is_available': is_available,
                    'asset_types': self._get_plugin_asset_types(plugin),
                    'data_types': self._get_plugin_data_types(plugin),
                    'priority': 1 if is_available else 0
                })

            # 按优先级排序
            suggestions.sort(key=lambda x: x['priority'], reverse=True)

            return suggestions

        except Exception as e:
            if logger:
                logger.error(f"建议数据源失败: {e}")
            return []

    def _get_plugin_asset_types(self, plugin_name: str) -> List[str]:
        """获取插件支持的资产类型"""
        if "stock" in plugin_name:
            return ["STOCK_A", "STOCK_B", "STOCK_HK", "STOCK_US"]
        elif "crypto" in plugin_name or "binance" in plugin_name:
            return ["CRYPTO"]
        else:
            return ["STOCK_A"]

    def _get_plugin_data_types(self, plugin_name: str) -> List[str]:
        """获取插件支持的数据类型"""
        return ["HISTORICAL_KLINE", "REAL_TIME_QUOTE", "FUNDAMENTAL"]

    def close(self):
        """关闭管理器"""
        try:
            # 取消所有运行中的任务
            for task_id, task in self.download_tasks.items():
                if task.status == "running":
                    task.status = "cancelled"

            # 关闭线程池
            self.executor.shutdown(wait=True)

            if logger:
                logger.info("数据缺失管理器已关闭")

        except Exception as e:
            if logger:
                logger.error(f"关闭数据缺失管理器失败: {e}")

    # ========================================================================
    # R237 HVD-237-B-005: 4 链 dispose 治理 (R78 铁律)
    # 业务影响: 2-3 业务方 (smart_data_missing_widget, data_management_widget, smart_data_integration)
    # 业务资源: availability_cache / download_tasks / executor / callbacks
    # ========================================================================
    def dispose(self) -> None:
        """R237 HVD-237-B-005: 4 链 dispose 入口 (R78 铁律 #6 幂等短路)"""
        if getattr(self, '_disposed', False):
            return
        try:
            self.shutdown()
            self.close()
            self.cleanup()
        except Exception as e:
            if logger:
                logger.warning(
                    f"DataMissingManager.dispose 异常: {e}",
                    exc_info=True,
                )
        finally:
            self._disposed = True

    def shutdown(self) -> None:
        """R237 HVD-237-B-005: shutdown - 业务数据清空 (availability_cache / download_tasks)"""
        try:
            if hasattr(self, 'availability_cache') and isinstance(self.availability_cache, dict):
                self.availability_cache.clear()
            if hasattr(self, 'download_tasks') and isinstance(self.download_tasks, dict):
                self.download_tasks.clear()
            if hasattr(self, 'plugin_status_cache') and isinstance(self.plugin_status_cache, dict):
                self.plugin_status_cache.clear()
        except Exception as e:
            if logger:
                logger.warning(
                    f"DataMissingManager.shutdown 异常: {e}",
                    exc_info=True,
                )

    def cleanup(self) -> None:
        """R237 HVD-237-B-005: cleanup - 回调列表清空 + 子组件引用置 None"""
        try:
            if hasattr(self, 'data_missing_callbacks') and isinstance(self.data_missing_callbacks, list):
                self.data_missing_callbacks.clear()
            if hasattr(self, 'download_progress_callbacks') and isinstance(self.download_progress_callbacks, list):
                self.download_progress_callbacks.clear()
            if hasattr(self, 'asset_identifier'):
                self.asset_identifier = None
            if hasattr(self, 'data_router'):
                self.data_router = None
            if hasattr(self, 'data_manager'):
                self.data_manager = None
            if hasattr(self, 'db_manager'):
                self.db_manager = None
        except Exception as e:
            if logger:
                logger.warning(
                    f"DataMissingManager.cleanup 异常: {e}",
                    exc_info=True,
                )

# 全局实例
_data_missing_manager = None

def get_data_missing_manager() -> DataMissingManager:
    """获取数据缺失管理器单例"""
    global _data_missing_manager
    if _data_missing_manager is None:
        _data_missing_manager = DataMissingManager()
    return _data_missing_manager
