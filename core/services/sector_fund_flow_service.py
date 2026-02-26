from loguru import logger
"""
板块资金流数据服务

此模块提供统一的板块资金流数据访问接口，支持多数据源切换、
数据缓存、异步加载等功能。

主要功能：
- 支持多数据源（AkShare、东方财富等）
- 统一的数据格式和接口
- 数据缓存和性能优化
- 异步数据加载
- 错误处理和降级策略
"""

import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from .unified_data_manager import UnifiedDataManager


@dataclass
class SectorFlowConfig:
    """板块资金流服务配置"""
    cache_duration_minutes: int = 5  # 缓存持续时间（分钟）
    auto_refresh_interval_minutes: int = 10  # 自动刷新间隔（分钟）
    max_concurrent_requests: int = 3  # 最大并发请求数
    request_timeout_seconds: int = 30  # 请求超时时间（秒）
    enable_cache: bool = True  # 启用缓存
    enable_auto_refresh: bool = True  # 启用自动刷新
    fallback_data_source: str = "akshare"  # 降级数据源


class SectorFundFlowService(QObject):
    """板块资金流数据服务"""

    # 信号定义
    data_updated = pyqtSignal(object)  # 数据更新信号
    error_occurred = pyqtSignal(str)  # 错误信号
    source_changed = pyqtSignal(str)  # 数据源变更信号

    def __init__(self, data_manager: Optional[UnifiedDataManager] = None,
                 config: Optional[SectorFlowConfig] = None):
        """
        初始化板块资金流服务

        Args:
            data_manager: 数据管理器实例
            config: 服务配置
            # log_manager: 已迁移到Loguru日志系统
        """
        super().__init__()

        # 使用数据标准化器替代DataManager
        from core.utils.data_standardizer import DataStandardizer
        self.data_standardizer = DataStandardizer  # 直接使用类，而不是实例
        self.config = config or SectorFlowConfig()
        # 纯Loguru架构，移除log_manager依赖

        # 缓存管理 - 强制使用统一缓存服务
        self._unified_cache = None
        self._cache_namespace = 'sector_fund_flow'
        self._init_unified_cache()

        # 异步执行器
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_requests)

        # 自动刷新定时器 - 延迟初始化
        self._refresh_timer = None

        self._is_initialized = False
        self._current_source = None
        self._available_sources = {}  # 可用数据源注册表
        self._optimal_sources = []    # 最优数据源列表

    def _init_unified_cache(self) -> None:
        """初始化统一缓存服务（强制）"""
        from core.services.cache_service import CacheService
        from core.containers import get_service_container
        
        container = get_service_container()
        if container and container.is_registered(CacheService):
            self._unified_cache = container.resolve(CacheService)
            logger.debug(f"SectorFundFlowService 已连接到统一缓存服务，命名空间: {self._cache_namespace}")
        else:
            raise RuntimeError("统一缓存服务未注册，请确保 CacheService 已在服务容器中注册")

    def _ensure_refresh_timer(self):
        """确保刷新定时器已初始化"""
        if self._refresh_timer is None:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建刷新定时器")
                return
            self._refresh_timer = QTimer()
            self._refresh_timer.timeout.connect(self._auto_refresh)

    def initialize(self) -> bool:
        """初始化服务"""
        try:
            logger.info("初始化板块资金流服务...")
            import time
            start_time = time.time()

            # 检查数据标准化器
            logger.info("检查数据标准化器状态...")
            if self.data_standardizer:
                logger.info("数据标准化器可用")
            else:
                logger.warning("数据标准化器不可用")

            # 启动自动刷新
            logger.info("配置自动刷新设置...")
            if self.config.enable_auto_refresh:
                refresh_start = time.time()
                self._start_auto_refresh()
                refresh_time = time.time()
                logger.info(f" 自动刷新启动完成，耗时: {(refresh_time - refresh_start):.2f}秒")
            else:
                logger.info("ℹ 自动刷新已禁用")

            # 智能检测板块资金流数据源
            self._detect_optimal_data_sources()

            self._is_initialized = True
            logger.info(f" 板块资金流服务初始化完成")

            return True

        except Exception as e:
            logger.error(f" 板块资金流服务初始化失败: {e}")
            return False

    def cleanup(self) -> None:
        """清理服务资源"""
        try:
            logger.info("清理板块资金流服务...")

            # 停止自动刷新
            self._refresh_timer.stop()

            # 关闭执行器
            self._executor.shutdown(wait=True)

            # 清理缓存
            with self._cache_lock:
                self._cache.clear()
                self._cache_timestamps.clear()

            logger.info("板块资金流服务清理完成")

        except Exception as e:
            logger.error(f" 清理板块资金流服务失败: {e}")

    def get_sector_flow_rank(self, indicator: str = "今日", force_refresh: bool = False) -> pd.DataFrame:
        """获取板块资金流排行

        Args:
            indicator: 时间周期（今日、3日、5日、10日、20日）
            force_refresh: 是否强制刷新缓存

        Returns:
            pd.DataFrame: 板块资金流排行数据
        """
        cache_key = f"sector_flow_rank_{indicator}"

        try:
            # 检查缓存
            if not force_refresh and self._is_cache_valid(cache_key):
                logger.info(f"📦 使用缓存的板块资金流排行数据: {indicator}")
                return self._get_from_cache(cache_key)

            logger.info(f"获取板块资金流排行数据: {indicator}")

            # 使用智能数据源选择获取数据
            df = self._get_data_with_smart_routing(indicator)

            if not df.empty:
                # 数据标准化处理
                df = self._standardize_sector_flow_data(df)

                # 更新缓存
                self._update_cache(cache_key, df)

                logger.info(f"板块资金流排行数据获取成功: {len(df)} 条记录")
                self.data_updated.emit({'type': 'sector_flow_rank', 'data': df})

                return df
            else:
                logger.warning("未获取到板块资金流排行数据")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"[ERROR] 获取板块资金流排行失败: {e}")
            self.error_occurred.emit(f"获取板块资金流排行失败: {str(e)}")
            return pd.DataFrame()

    def get_sector_flow_summary(self, symbol: str, indicator: str = "今日") -> pd.DataFrame:
        """获取板块资金流汇总

        Args:
            symbol: 板块名称
            indicator: 时间周期

        Returns:
            pd.DataFrame: 板块资金流汇总数据
        """
        try:
            # 使用AkShare获取板块资金流数据
            import akshare as ak
            df = ak.stock_sector_fund_flow_rank(indicator=indicator)
            
            if not df.empty and symbol:
                # 过滤指定板块
                df = df[df['板块名称'] == symbol]
            
            logger.info(f" 板块资金流汇总获取成功: {symbol}, {len(df)} 条记录")
            return df

        except Exception as e:
            logger.error(f" 获取板块资金流汇总失败: {e}")
            return pd.DataFrame()

    def get_sector_flow_history(self, symbol: str, period: str = "近6月") -> pd.DataFrame:
        """获取板块历史资金流

        Args:
            symbol: 板块名称
            period: 时间周期

        Returns:
            pd.DataFrame: 板块历史资金流数据
        """
        try:
            # 这里可以扩展为支持历史数据获取
            # 当前返回空数据作为占位符
            logger.info(f" 板块历史资金流功能待实现: {symbol}, {period}")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f" 获取板块历史资金流失败: {e}")
            return pd.DataFrame()

    def get_concept_flow_history(self, symbol: str, period: str = "近6月") -> pd.DataFrame:
        """获取概念历史资金流

        Args:
            symbol: 概念名称
            period: 时间周期

        Returns:
            pd.DataFrame: 概念历史资金流数据
        """
        try:
            # 这里可以扩展为支持概念历史数据获取
            # 当前返回空数据作为占位符
            logger.info(f" 概念历史资金流功能待实现: {symbol}, {period}")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f" 获取概念历史资金流失败: {e}")
            return pd.DataFrame()

    def switch_data_source(self, source: str) -> bool:
        """切换数据源

        Args:
            source: 数据源名称

        Returns:
            bool: 是否切换成功
        """
        try:
            logger.info(f" 切换数据源到: {source}")

            # 这里可以扩展为支持数据源切换
            # 当前只是记录日志
            self._current_source = source

            # 清理缓存
            self._clear_cache()

            logger.info(f" 数据源切换成功: {source}")
            self.source_changed.emit(source)

            return True

        except Exception as e:
            logger.error(f" 数据源切换失败: {e}")
            self.error_occurred.emit(f"数据源切换失败: {str(e)}")
            return False

    def _standardize_sector_flow_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化板块资金流数据格式"""
        try:
            # 验证输入数据
            if df is None or not isinstance(df, pd.DataFrame):
                logger.warning(f"无效的输入数据类型: {type(df)}")
                return pd.DataFrame()

            if df.empty:
                logger.warning("输入数据为空")
                return df

            # 标准化列名
            column_mapping = {
                '板块': 'sector_name',
                '今日主力净流入-净额': 'main_net_inflow',
                '今日主力净流入-净占比': 'main_net_inflow_ratio',
                '今日散户净流入-净额': 'retail_net_inflow',
                '今日散户净流入-净占比': 'retail_net_inflow_ratio',
                '今日涨跌幅': 'change_pct'
            }

            # 重命名列
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})

            # 处理重复列（如果存在）
            if df.columns.duplicated().any():
                logger.warning(f"检测到重复列，移除重复: {df.columns[df.columns.duplicated()].tolist()}")
                df = df.loc[:, ~df.columns.duplicated(keep='first')]

            # 数据类型转换
            numeric_columns = ['main_net_inflow', 'main_net_inflow_ratio',
                               'retail_net_inflow', 'retail_net_inflow_ratio', 'change_pct']

            for col in numeric_columns:
                if col in df.columns:
                    # 确保列是Series而不是DataFrame
                    col_data = df[col]
                    if isinstance(col_data, pd.DataFrame):
                        logger.warning(f"列 {col} 仍是DataFrame（不应该），取第一列")
                        col_data = col_data.iloc[:, 0]

                    # 安全的类型转换
                    try:
                        df[col] = pd.to_numeric(col_data, errors='coerce')
                    except Exception as conv_err:
                        logger.warning(f"列 {col} 转换失败: {conv_err}")

            return df

        except Exception as e:
            logger.warning(f"数据标准化失败: {e}")
            return df

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效 - 使用统一缓存服务"""
        if not self.config.enable_cache:
            return False

        if self._unified_cache is None:
            raise RuntimeError("统一缓存服务未初始化")

        cached_data = self._unified_cache.get(cache_key, namespace=self._cache_namespace)
        return cached_data is not None

    def _get_from_cache(self, cache_key: str) -> Any:
        """从缓存获取数据 - 使用统一缓存服务"""
        if self._unified_cache is None:
            raise RuntimeError("统一缓存服务未初始化")

        return self._unified_cache.get(cache_key, namespace=self._cache_namespace)

    def _update_cache(self, cache_key: str, data: Any) -> None:
        """更新缓存 - 使用统一缓存服务"""
        if not self.config.enable_cache:
            return

        if self._unified_cache is None:
            raise RuntimeError("统一缓存服务未初始化")

        from datetime import timedelta
        ttl = timedelta(minutes=self.config.cache_duration_minutes)
        self._unified_cache.set(cache_key, data, ttl=ttl, namespace=self._cache_namespace)

    def _clear_cache(self) -> None:
        """清理缓存"""
        if self._unified_cache is None:
            raise RuntimeError("统一缓存服务未初始化")

        self._unified_cache.clear_namespace(self._cache_namespace)
        logger.info("缓存已清理")

    def _start_auto_refresh(self) -> None:
        """启动自动刷新"""
        self._ensure_refresh_timer()
        if self._refresh_timer is None:
            logger.warning("刷新定时器未初始化，无法启动自动刷新")
            return
        if self.config.auto_refresh_interval_minutes > 0:
            interval_ms = self.config.auto_refresh_interval_minutes * 60 * 1000
            self._refresh_timer.start(interval_ms)
            logger.info(f" 启动自动刷新，间隔 {self.config.auto_refresh_interval_minutes} 分钟")

    def _auto_refresh(self) -> None:
        """自动刷新数据（后台线程执行，避免阻塞UI线程）"""
        try:
            logger.info("[TIME] 调度自动刷新任务...")
            # 将实际刷新任务放入线程池，避免在Qt定时器回调（主线程）中执行重IO/CPU工作
            self._executor.submit(self._run_auto_refresh_task)
        except Exception as e:
            logger.error(f" 自动刷新调度失败: {e}")

    def _run_auto_refresh_task(self) -> None:
        """实际的自动刷新任务，在线程池中执行"""
        try:
            # 这里直接调用现有方法即可；该方法内部会通过Qt信号通知数据更新
            self.get_sector_flow_rank(force_refresh=True)
        except Exception as e:
            logger.error(f" 自动刷新任务执行失败: {e}")

    def _detect_optimal_data_sources(self) -> None:
        """智能检测板块资金流数据的最优数据源"""
        try:
            logger.info("开始检测板块资金流数据源...")

            # 重置数据源注册表
            self._available_sources.clear()
            self._optimal_sources.clear()

            # 系统现在使用AkShare作为主要数据源
            # 设置AkShare为默认和最优数据源
            self._available_sources['akshare'] = {
                'type': 'primary',
                'health_score': 1.0,
                'supports_fund_flow': True,
                'description': 'AkShare板块资金流数据源'
            }
            
            logger.info("AkShare数据源已配置为板块资金流的默认数据源")

        except Exception as e:
            logger.error(f"[ERROR] 数据源检测失败: {e}")
            # 设置默认的降级方案
            self._set_fallback_sources()

    def _detect_tet_data_sources(self) -> None:
        """检测TET框架中支持SECTOR_FUND_FLOW的数据源"""
        try:
            # 由于没有data_manager，这里跳过TET框架检测
            logger.info("跳过TET框架检测（无可用data_manager）")
            return
        except Exception as e:
            logger.error(f"[ERROR] TET数据源检测失败: {e}")

    def _detect_legacy_data_sources(self) -> None:
        """检测传统数据源的板块资金流支持"""
        try:
            # 由于没有data_manager，这里跳过传统数据源检测
            logger.info("跳过传统数据源检测（无可用data_manager）")
            return
        except Exception as e:
            logger.error(f"[ERROR] 传统数据源检测失败: {e}")

    def _check_source_supports_fund_flow(self, source_id: str, router) -> bool:
        """检查TET数据源是否支持板块资金流"""
        try:
            from ..plugin_types import DataType, AssetType

            # 获取数据源实例（可能是适配器或插件）
            source_instance = router.get_data_source(source_id)
            if not source_instance:
                logger.debug(f"数据源 {source_id} 不存在")
                return False

            # 方法1：调用 get_plugin_info() 方法（适配器）
            plugin_info = None
            if hasattr(source_instance, 'get_plugin_info'):
                try:
                    plugin_info = source_instance.get_plugin_info()
                    logger.debug(f"通过 get_plugin_info() 获取插件信息: {source_id}")
                except Exception as e:
                    logger.debug(f"调用 get_plugin_info() 失败: {e}")

            # 方法2：访问 plugin_info 属性（直接插件）
            elif hasattr(source_instance, 'plugin_info'):
                try:
                    plugin_info = source_instance.plugin_info
                    logger.debug(f"通过 plugin_info 属性获取插件信息: {source_id}")
                except Exception as e:
                    logger.debug(f"访问 plugin_info 属性失败: {e}")

            # 方法3：通过适配器的 plugin 属性获取（适配器包装）
            elif hasattr(source_instance, 'plugin'):
                plugin = source_instance.plugin
                if hasattr(plugin, 'plugin_info'):
                    try:
                        plugin_info = plugin.plugin_info
                        logger.debug(f"通过适配器 plugin 属性获取插件信息: {source_id}")
                    except Exception as e:
                        logger.debug(f"通过适配器获取插件信息失败: {e}")

            # 检查插件信息中的支持数据类型
            if plugin_info:
                if hasattr(plugin_info, 'supported_data_types'):
                    supports_fund_flow = DataType.SECTOR_FUND_FLOW in plugin_info.supported_data_types
                    logger.debug(f"数据源 {source_id} 支持数据类型: {plugin_info.supported_data_types}")
                    logger.debug(f"数据源 {source_id} 是否支持板块资金流: {supports_fund_flow}")
                    if supports_fund_flow:
                        return True

            # 回退方案：检查插件实例是否有相关方法
            # 首先获取真正的插件实例（处理适配器包装）
            plugin = source_instance
            if hasattr(source_instance, 'plugin'):
                plugin = source_instance.plugin

            method_names = ['get_sector_fund_flow_data', 'get_fund_flow', 'get_sector_flow']
            for method_name in method_names:
                if hasattr(plugin, method_name):
                    logger.debug(f"数据源 {source_id} 有方法 {method_name}，认为支持板块资金流")
                    return True

            logger.debug(f"🔶 数据源 {source_id} 不支持板块资金流")
            return False

        except Exception as e:
            logger.warning(f"检查数据源 {source_id} 支持情况时出错: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def _check_legacy_source_supports_fund_flow(self, source_id: str, source_instance) -> bool:
        """检查传统数据源是否支持板块资金流"""
        try:
            # AkShare 相关检查
            if 'akshare' in source_id.lower():
                return True

            # 东方财富相关检查
            if 'eastmoney' in source_id.lower():
                return True

            # 检查是否有板块资金流相关方法
            fund_flow_methods = [
                'get_sector_fund_flow',
                'get_fund_flow',
                'stock_sector_fund_flow_rank',
                'sector_fund_flow'
            ]

            for method_name in fund_flow_methods:
                if hasattr(source_instance, method_name):
                    return True

            return False

        except Exception as e:
            logger.debug(f"检查传统数据源 {source_id} 支持情况时出错: {e}")
            return False

    def _get_source_health_score(self, source_id: str, router) -> float:
        """获取TET数据源健康评分"""
        try:
            # 获取数据源指标
            if hasattr(router, 'get_source_metrics'):
                metrics = router.get_source_metrics(source_id)
                if metrics:
                    return metrics.health_score

            # 尝试简单的健康检查
            source_instance = router.get_data_source(source_id)
            if source_instance and hasattr(source_instance, 'health_check'):
                result = source_instance.health_check()
                if hasattr(result, 'is_healthy') and result.is_healthy:
                    return 1.0
                else:
                    return 0.3

            return 0.5  # 默认中等健康度

        except Exception as e:
            logger.debug(f"获取数据源 {source_id} 健康度失败: {e}")
            return 0.1

    def _test_legacy_source_health(self, source_id: str, source_instance) -> float:
        """测试传统数据源健康状态"""
        try:
            # 尝试连接测试
            if hasattr(source_instance, 'test_connection'):
                if source_instance.test_connection():
                    return 0.8
                else:
                    return 0.2

            # 简单可用性检查
            if source_instance is not None:
                return 0.6

            return 0.1

        except Exception as e:
            logger.debug(f"测试传统数据源 {source_id} 健康状态失败: {e}")
            return 0.1

    def _rank_data_sources(self) -> None:
        """根据健康状态和功能支持对数据源进行排序"""
        try:
            # 过滤支持板块资金流的数据源
            fund_flow_sources = {
                source_id: info for source_id, info in self._available_sources.items()
                if info.get('supports_fund_flow', False)
            }

            # 按照优先级排序：健康度 + 数据源类型权重
            def get_priority_score(item):
                source_id, info = item
                health_score = info['health_score']
                type_weight = 1.0 if info['type'] == 'tet_plugin' else 0.8  # TET插件优先

                # 特殊加权
                if 'akshare' in source_id.lower():
                    type_weight += 0.3  # AkShare是板块资金流的专业数据源

                return health_score * type_weight

            # 排序并保存
            sorted_sources = sorted(fund_flow_sources.items(), key=get_priority_score, reverse=True)
            self._optimal_sources = [source_id for source_id, _ in sorted_sources]

        except Exception as e:
            logger.error(f"[ERROR] 数据源排序失败: {e}")

    def _log_detection_results(self) -> None:
        """输出数据源检测结果"""
        try:
            logger.info("板块资金流数据源检测结果:")
            logger.info(f"   总计发现数据源: {len(self._available_sources)} 个")

            fund_flow_count = sum(1 for info in self._available_sources.values()
                                  if info.get('supports_fund_flow', False))
            logger.info(f"   支持板块资金流: {fund_flow_count} 个")

            if self._optimal_sources:
                logger.info("[AWARD] 推荐数据源优先级排序:")
                for i, source_id in enumerate(self._optimal_sources[:3], 1):
                    info = self._available_sources[source_id]
                    logger.info(f"   {i}. {source_id} (健康度: {info['health_score']:.2f}, 类型: {info['type']})")

                # 设置当前最优数据源
                self._current_source = self._optimal_sources[0]
                logger.info(f"自动选择最优数据源: {self._current_source}")
            else:
                logger.warning("未发现支持板块资金流的数据源，将使用模拟数据")
                self._current_source = "mock"

        except Exception as e:
            logger.error(f"[ERROR] 输出检测结果失败: {e}")

    def _set_fallback_sources(self) -> None:
        """设置降级数据源方案"""
        try:
            logger.warning("设置降级数据源方案...")

            # 尝试默认的降级顺序
            fallback_order = ['akshare', 'eastmoney', 'mock']

            for source_id in fallback_order:
                # 由于没有data_manager，直接设置到特定数据源
                if source_id == "akshare":
                    self._current_source = source_id
                    logger.info(f"降级使用数据源: {source_id}")
                    return

            # 最终降级到模拟模式
            self._current_source = "mock"
            logger.info("ℹ️ 降级到模拟数据模式")

        except Exception as e:
            logger.error(f"[ERROR] 设置降级方案失败: {e}")
            self._current_source = "mock"

    def _get_data_with_smart_routing(self, indicator: str = "今日") -> pd.DataFrame:
        """使用智能路由获取板块资金流数据"""
        try:
            # 优先使用TET框架进行智能路由
            if self._try_tet_data_acquisition(indicator) is not None:
                return self._try_tet_data_acquisition(indicator)

            # 降级到最优传统数据源
            return self._try_optimal_legacy_sources(indicator)

        except Exception as e:
            logger.error(f"[ERROR] 智能路由获取数据失败: {e}")
            return pd.DataFrame()

    def _try_tet_data_acquisition(self, indicator: str) -> Optional[pd.DataFrame]:
        """尝试通过TET框架获取数据"""
        try:
            # 由于没有data_manager，TET框架不可用
            return None
        except Exception as e:
            logger.warning(f" TET框架获取数据失败: {e}")
            return None

    def _try_optimal_legacy_sources(self, indicator: str) -> pd.DataFrame:
        """尝试使用最优传统数据源获取数据"""
        try:
            logger.info("降级到传统数据源模式...")

            # 按优先级尝试可用的数据源
            for source_id in self._optimal_sources:
                try:
                    source_info = self._available_sources.get(source_id)
                    if not source_info or not source_info.get('supports_fund_flow', False):
                        continue

                    logger.info(f"尝试数据源: {source_id}")
                    df = self._get_data_from_specific_source(source_id, source_info, indicator)

                    if not df.empty:
                        logger.info(f"成功从 {source_id} 获取数据: {len(df)} 条记录")
                        self._current_source = source_id
                        return df
                    else:
                        logger.warning(f" 数据源 {source_id} 返回空数据")

                except Exception as e:
                    logger.warning(f" 数据源 {source_id} 获取失败: {e}")
                    continue

            # 最后尝试直接使用akshare
            logger.info("尝试直接使用akshare...")
            return self._get_data_from_akshare(indicator)

        except Exception as e:
            logger.error(f"[ERROR] 传统数据源获取失败: {e}")
            return pd.DataFrame()

    def _get_data_from_specific_source(self, source_id: str, source_info: Dict, indicator: str) -> pd.DataFrame:
        """从特定数据源获取数据"""
        try:
            if source_info['type'] == 'tet_plugin':
                # TET插件类型
                router = source_info.get('router')
                if router:
                    source_instance = router.get_data_source(source_id)
                    if source_instance and hasattr(source_instance, 'get_sector_fund_flow_data'):
                        data = source_instance.get_sector_fund_flow_data("sector", indicator=indicator)
                        if isinstance(data, pd.DataFrame):
                            return data
                        elif isinstance(data, list):
                            return pd.DataFrame(data)

            elif source_info['type'] == 'legacy':
                # 传统数据源类型
                source_instance = source_info.get('instance')
                if source_instance:
                    # 尝试各种可能的方法名
                    method_names = ['get_sector_fund_flow', 'get_fund_flow', 'stock_sector_fund_flow_rank']
                    for method_name in method_names:
                        if hasattr(source_instance, method_name):
                            try:
                                method = getattr(source_instance, method_name)
                                if method_name == 'stock_sector_fund_flow_rank':
                                    data = method(indicator=indicator)
                                else:
                                    data = method()

                                if isinstance(data, pd.DataFrame) and not data.empty:
                                    return data
                                elif isinstance(data, dict) and 'sector_flow_rank' in data:
                                    return data['sector_flow_rank']
                            except Exception as e:
                                logger.debug(f"方法 {method_name} 调用失败: {e}")
                                continue

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"从数据源 {source_id} 获取数据时出错: {e}")
            return pd.DataFrame()

    def _get_data_from_akshare(self, indicator: str = "今日") -> pd.DataFrame:
        """直接从akshare获取板块资金流数据"""
        try:
            import akshare as ak
            
            logger.info(f"直接使用akshare获取板块资金流数据...")
            df = ak.stock_sector_fund_flow_rank(indicator=indicator)
            
            if not df.empty:
                self._current_source = "akshare直接调用"
                logger.info(f"akshare成功获取数据: {len(df)} 条记录")
                return df
            else:
                logger.warning("akshare返回空数据")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"akshare数据获取失败: {e}")
            return pd.DataFrame()

    def get_current_optimal_source(self) -> str:
        """获取当前最优数据源"""
        return self._current_source or "unknown"

    def get_available_sources_info(self) -> Dict[str, Any]:
        """获取可用数据源信息"""
        return {
            'available_sources': self._available_sources,
            'optimal_sources': self._optimal_sources,
            'current_source': self._current_source
        }

    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            'is_initialized': self._is_initialized,
            'current_optimal_source': self._current_source,
            'available_sources_count': len(self._available_sources),
            'fund_flow_sources_count': sum(1 for info in self._available_sources.values()
                                           if info.get('supports_fund_flow', False)),
            'cache_enabled': self.config.enable_cache,
            'auto_refresh_enabled': self.config.enable_auto_refresh,
            'cache_size': len(self._cache) if self.config.enable_cache else 0
        }
