#!/usr/bin/env python3
"""
真实数据提供器

提供真实的市场数据，替换项目中的虚假数据和测试数据
使用系统统一组件，确保数据的真实性和可靠性
"""

from loguru import logger
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime, timedelta
import threading
import time

# 使用系统统一组件
from core.system_adapters import get_config, get_data_validator
from core.services.unified_data_manager import UnifiedDataManager
from core.plugin_types import AssetType

class RealDataProvider:
    """真实数据提供器 - 提供真实的市场数据"""

    def __init__(self):
        """初始化真实数据提供器"""
        self.logger = logger.bind(module=__name__)
        self.config = get_config()
        self.validator = get_data_validator()

        # 初始化数据管理器 - 使用工厂方法
        try:
            from utils.manager_factory import get_manager_factory, get_data_manager
            factory = get_manager_factory()
            self.data_manager = get_data_manager()
        except ImportError:
            from .services.unified_data_manager import get_unified_data_manager
            self.data_manager = get_unified_data_manager()

        # 缓存管理
        self._cache = {}
        self._cache_lock = threading.RLock()
        self._cache_ttl = self.config.get(
            'real_data', {}).get('cache_ttl', 300)  # 5分钟缓存

        # 数据源连接池管理
        self._data_source_pool = {}  # 空闲实例池 {data_source: [instances]}
        self._active_instances = {}  # 正在使用的实例 {data_source: count}
        self._pool_lock = threading.RLock()
        self._max_pool_size = 5  # 默认值，将从数据库动态加载
        self._pool_timeout = 30  # 连接池超时时间
        self._pool_cleanup_interval = 300  # 连接池清理间隔

        # 动态加载数据源实例池配置
        self._load_pool_config_from_database()

        # 启动后台清理定时器（按 _pool_cleanup_interval 清理实例池）
        self._cleanup_thread_stop = False
        self._start_cleanup_timer()

        # 默认股票池
        self._default_stocks = [
            '000001',  # 平安银行
            '000002',  # 万科A
            '000858',  # 五粮液
            '002415',  # 海康威视
            '600000',  # 浦发银行
            '600036',  # 招商银行
            '600519',  # 贵州茅台
            '600887',  # 伊利股份
            '000858',  # 五粮液
            '002304'   # 洋河股份
        ]

        self.logger.info("真实数据提供器初始化完成")

    def _load_pool_config_from_database(self):
        """从数据库动态加载数据源实例池配置"""
        try:
            from db.models.plugin_models import get_data_source_config_manager

            config_manager = get_data_source_config_manager()
            all_configs = config_manager.get_all_plugin_configs()

            # 获取默认配置（使用第一个启用的数据源配置，或使用系统默认值）
            if all_configs:
                # 使用第一个配置的线程池设置作为全局设置
                # 注意：由于set_pool_config()会更新所有插件的配置，所以所有插件的pool配置应该是一致的
                first_config = next(iter(all_configs.values()))
                loaded_max_pool_size = first_config.get('max_pool_size', 5)
                loaded_pool_timeout = first_config.get('pool_timeout', 30)
                loaded_pool_cleanup_interval = first_config.get('pool_cleanup_interval', 300)
                
                # 更新实例变量
                self._max_pool_size = loaded_max_pool_size
                self._pool_timeout = loaded_pool_timeout
                self._pool_cleanup_interval = loaded_pool_cleanup_interval

                self.logger.info(f"从数据库加载数据源实例池配置: max_pool_size={self._max_pool_size}, "
                                 f"pool_timeout={self._pool_timeout}, pool_cleanup_interval={self._pool_cleanup_interval}")
            else:
                self.logger.info("未找到数据源配置，使用默认的数据源实例池配置")

        except Exception as e:
            self.logger.warning(f"从数据库加载线程池配置失败，使用默认值: {e}", exc_info=True)

    def reload_pool_config(self):
        """重新加载数据源实例池配置（用于UI动态更新）"""
        self.logger.info("重新加载数据源实例池配置...")
        self._load_pool_config_from_database()

        # 清理现有连接池以应用新配置
        self.cleanup_data_source_pool()
        self.logger.info("数据源实例池配置已重新加载并清理连接池")

    def _start_cleanup_timer(self):
        """启动后台定时清理任务，周期性清理实例池，避免长期占用"""
        def _worker():
            while not self._cleanup_thread_stop:
                try:
                    time.sleep(max(30, int(self._pool_cleanup_interval)))
                    self.cleanup_data_source_pool()
                except Exception as e:
                    self.logger.debug(f"实例池定时清理异常: {e}")
        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def set_pool_config(self, max_pool_size: int = None, pool_timeout: int = None, pool_cleanup_interval: int = None) -> None:
        """
        通过UI动态设置数据源实例池配置并立即生效（无需依赖DB）
        """
        try:
            with self._pool_lock:
                if isinstance(max_pool_size, int) and max_pool_size > 0:
                    self._max_pool_size = max_pool_size
                if isinstance(pool_timeout, int) and pool_timeout > 0:
                    self._pool_timeout = pool_timeout
                if isinstance(pool_cleanup_interval, int) and pool_cleanup_interval > 0:
                    self._pool_cleanup_interval = pool_cleanup_interval
            # 应用新配置：清理当前池，新的请求将按新上限创建/复用
            self.cleanup_data_source_pool()
            self.logger.info(f"数据源实例池配置已更新: max_pool_size={self._max_pool_size}, "
                             f"pool_timeout={self._pool_timeout}, pool_cleanup_interval={self._pool_cleanup_interval}")

            # 尝试持久化到数据库（若可用）
            try:
                from db.models.plugin_models import get_data_source_config_manager
                cfg_mgr = get_data_source_config_manager()
                payload = {
                    'max_pool_size': self._max_pool_size,
                    'pool_timeout': self._pool_timeout,
                    'pool_cleanup_interval': self._pool_cleanup_interval
                }
                persisted = False
                # 优先使用明确的API
                if hasattr(cfg_mgr, 'set_pool_config'):
                    cfg_mgr.set_pool_config(**payload)  # type: ignore
                    persisted = True
                elif hasattr(cfg_mgr, 'save_config'):
                    # 保存到统一键名下
                    cfg_mgr.save_config('instance_pool', payload)  # type: ignore
                    persisted = True
                elif hasattr(cfg_mgr, 'update_config'):
                    cfg_mgr.update_config('instance_pool', payload)  # type: ignore
                    persisted = True
                elif hasattr(cfg_mgr, 'set_global_setting'):
                    # 分别写入（某些管理器只支持K/V）
                    cfg_mgr.set_global_setting('max_pool_size', self._max_pool_size)  # type: ignore
                    cfg_mgr.set_global_setting('pool_timeout', self._pool_timeout)  # type: ignore
                    cfg_mgr.set_global_setting('pool_cleanup_interval', self._pool_cleanup_interval)  # type: ignore
                    persisted = True

                if persisted:
                    self.logger.info("数据源实例池配置已持久化到数据库")
                else:
                    self.logger.debug("未检测到可用的配置持久化API，跳过数据库持久化")
            except Exception as persist_err:
                # 持久化失败不影响运行时生效
                self.logger.warning(f"实例池配置持久化失败（忽略继续）: {persist_err}")
        except Exception as e:
            self.logger.error(f"更新数据源实例池配置失败: {e}")

    def _get_pooled_data_manager(self, data_source: Optional[str] = None):
        """获取池化的数据管理器实例

        Args:
            data_source: 数据源名称

        Returns:
            数据管理器实例
        """
        if not data_source:
            return self.data_manager

        with self._pool_lock:
            # 检查连接池中是否已有该数据源的实例
            if data_source not in self._data_source_pool:
                self._data_source_pool[data_source] = []
            if data_source not in self._active_instances:
                self._active_instances[data_source] = 0

            pool = self._data_source_pool[data_source]

            # 如果池中有可用实例，直接返回
            if pool:
                instance = pool.pop(0)
                self._active_instances[data_source] += 1
                self.logger.debug(f"从连接池获取数据源实例: {data_source} (活跃: {self._active_instances[data_source]}, 空闲: {len(pool)})")
                return instance

            # 如果池为空，创建新实例（但不超过最大池大小）
            total_idle = sum(len(p) for p in self._data_source_pool.values())
            total_active = sum(self._active_instances.values())
            total_instances = total_idle + total_active
            
            if total_instances < self._max_pool_size:
                # 创建新的数据管理器实例
                try:
                    from .services.unified_data_manager import get_unified_data_manager
                    new_instance = get_unified_data_manager()
                    self._active_instances[data_source] += 1
                    self.logger.debug(f"创建新的数据源实例: {data_source} (总实例: {total_instances + 1}/{self._max_pool_size})")
                    return new_instance
                except Exception as e:
                    self.logger.warning(f"创建数据源实例失败: {e}")
                    return self.data_manager
            else:
                # 池已满，返回默认实例
                self.logger.debug(f"连接池已满，使用默认数据管理器: {data_source} (总实例: {total_instances}/{self._max_pool_size})")
                return self.data_manager

    def _return_pooled_data_manager(self, instance, data_source: Optional[str] = None):
        """将数据管理器实例返回到连接池

        Args:
            instance: 数据管理器实例
            data_source: 数据源名称
        """
        if not data_source or instance == self.data_manager:
            return  # 默认实例不需要返回池中

        with self._pool_lock:
            if data_source in self._data_source_pool:
                pool = self._data_source_pool[data_source]
                if len(pool) < self._max_pool_size and instance not in pool:
                    pool.append(instance)
                    # 减少活跃实例计数
                    if data_source in self._active_instances and self._active_instances[data_source] > 0:
                        self._active_instances[data_source] -= 1
                    self.logger.debug(f"数据源实例返回连接池: {data_source} (活跃: {self._active_instances.get(data_source, 0)}, 空闲: {len(pool)})")

    def cleanup_data_source_pool(self):
        """清理数据源连接池"""
        with self._pool_lock:
            total_idle = sum(len(pool) for pool in self._data_source_pool.values())
            total_active = sum(self._active_instances.values())
            total_instances = total_idle + total_active
            self._data_source_pool.clear()
            self._active_instances.clear()
            self.logger.info(f"数据源连接池已清理，释放了 {total_idle} 个空闲实例（活跃实例: {total_active}）")

    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态信息"""
        with self._pool_lock:
            status = {
                'max_pool_size': self._max_pool_size,
                'pools': {}
            }

            # 统计空闲和活跃实例
            total_idle = 0
            total_active = 0
            
            # 修复：确保所有数据源都被统计，即使池为空
            # 合并所有已知的数据源（从pool和active_instances）
            all_data_sources = set(self._data_source_pool.keys()) | set(self._active_instances.keys())
            
            for data_source in all_data_sources:
                idle_count = len(self._data_source_pool.get(data_source, []))
                active_count = self._active_instances.get(data_source, 0)
                total_idle += idle_count
                total_active += active_count
                
                status['pools'][data_source] = {
                    'idle_instances': idle_count,
                    'active_instances': active_count,
                    'total_instances': idle_count + active_count,
                    'pool_utilization': f"{idle_count + active_count}/{self._max_pool_size}"
                }

            # 总实例数 = 空闲 + 活跃
            total_instances = total_idle + total_active
            status['total_instances'] = total_instances
            status['total_idle'] = total_idle
            status['total_active'] = total_active
            status['total_utilization'] = f"{total_instances}/{self._max_pool_size}"
            
            # 修复：添加调试日志，便于排查统计问题
            if total_instances == 0:
                self.logger.debug(f"实例池统计为0: 数据源池={list(self._data_source_pool.keys())}, 活跃实例={dict(self._active_instances)}")

            return status

    def _get_plugin_adjustment_types(self, data_source: str = None) -> List[str]:
        """获取插件支持的复权类型"""
        try:
            data_manager = self._get_pooled_data_manager(data_source)
            
            if hasattr(data_manager, '_uni_plugin_manager') and data_manager._uni_plugin_manager:
                plugin = data_manager._uni_plugin_manager._get_plugin_for_asset(
                    data_source or '通达信'
                )
                if plugin and hasattr(plugin, 'get_supported_adjustment_types'):
                    return plugin.get_supported_adjustment_types()
            
            return ['none']
        except Exception as e:
            self.logger.debug(f"获取插件复权类型失败: {e}")
            return ['none']

    def check_data_exists(self, code: str, freq: str = 'D',
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        检查指定股票的数据是否已存在于数据库中

        Args:
            code: 股票代码
            freq: 频率 ('D', 'W', 'M', '60', '30', '15', '5', '1')
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            Dict包含存在性信息: {
                'exists': bool,  # 是否存在数据
                'count': int,    # 现有数据条数
                'date_range': tuple,  # 现有数据的日期范围
                'missing_dates': list  # 缺失的日期（如果指定了日期范围）
            }
        """
        try:
            self.logger.debug(f"检查数据存在性: {code}, 频率: {freq}")

            # 尝试获取现有数据
            existing_data = self.data_manager.get_kdata(
                stock_code=code,
                period=freq,
                count=250  # 默认获取250条数据进行检查
            )

            result = {
                'exists': not existing_data.empty,
                'count': len(existing_data),
                'date_range': None,
                'missing_dates': []
            }

            if not existing_data.empty:
                # 获取日期范围
                if 'datetime' in existing_data.columns:
                    dates = pd.to_datetime(existing_data['datetime'])
                elif existing_data.index.name == 'datetime':
                    dates = pd.to_datetime(existing_data.index)
                else:
                    dates = existing_data.index

                result['date_range'] = (dates.min(), dates.max())

                # 如果指定了日期范围，检查缺失的日期
                if start_date and end_date:
                    expected_dates = pd.date_range(start=start_date, end=end_date, freq='D')
                    existing_dates = pd.to_datetime(dates).normalize()
                    missing_dates = expected_dates.difference(existing_dates)
                    result['missing_dates'] = missing_dates.strftime('%Y-%m-%d').tolist()

            self.logger.debug(f"数据存在性检查结果: {code} - 存在: {result['exists']}, 条数: {result['count']}")
            return result

        except Exception as e:
            self.logger.error(f"检查数据存在性失败 {code}: {e}")
            return {
                'exists': False,
                'count': 0,
                'date_range': None,
                'missing_dates': []
            }

    def get_real_kdata(self, code: str, freq: str = 'D',
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       count: int = 250,
                       data_source: Optional[str] = None,
                       asset_type: Optional[str] = None,
                       adjustment: str = 'none') -> pd.DataFrame:
        """获取真实K线数据

        Args:
            code: 股票代码
            freq: 频率 ('D', 'W', 'M', '60', '30', '15', '5', '1')
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            count: 数据条数（当未指定日期时使用）
            data_source: 数据源名称
            asset_type: 资产类型
            adjustment: 复权类型 ('qfq', 'hfq', 'none')

        Returns:
            真实K线数据DataFrame
        """
        try:
            cache_key = f"kdata_{code}_{freq}_{start_date}_{end_date}_{count}"

            # 检查缓存
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                self.logger.debug(f"从缓存获取K线数据: {code}")
                return cached_data

            self.logger.info(f"[数据获取] 获取真实K线数据: {code}, 频率: {freq}, 数据源: {data_source or '默认'}, count: {count}, 日期范围: {start_date} ~ {end_date}")

            # 使用连接池获取数据管理器实例
            data_manager_instance = self._get_pooled_data_manager(data_source)

            try:
                # 统一资产类型转换逻辑（支持AssetType对象、枚举值字符串、中文名称）
                final_asset_type = None
                if asset_type:
                    # 0. 如果已经是AssetType对象，直接使用
                    if isinstance(asset_type, AssetType):
                        final_asset_type = asset_type
                        self.logger.debug(f"资产类型已是AssetType对象: {final_asset_type.value}")
                    elif isinstance(asset_type, str):
                        # 1. 尝试作为枚举值字符串（如"stock_a"）
                        try:
                            final_asset_type = AssetType(asset_type)
                            self.logger.debug(f"从枚举值字符串转换: '{asset_type}' -> {final_asset_type.value}")
                        except ValueError:
                            # 2. 尝试从中文显示名称转换（如"A股"）
                            try:
                                from ..ui_asset_type_utils import parse_asset_type_from_combo
                                final_asset_type = parse_asset_type_from_combo(asset_type)
                                self.logger.debug(f"从中文名称转换: '{asset_type}' -> {final_asset_type.value}")
                            except Exception as e:
                                # 3. 转换失败，使用默认值
                                self.logger.warning(f"无法解析资产类型 '{asset_type}' (类型: {type(asset_type)}): {e}，使用默认值 STOCK_A")
                                final_asset_type = AssetType.STOCK_A
                    else:
                        self.logger.warning(f"资产类型格式不支持 (类型: {type(asset_type)}, 值: {asset_type})，使用默认值 STOCK_A")
                        final_asset_type = AssetType.STOCK_A

                if data_source:
                    kdata = data_manager_instance.get_kdata_from_source(
                        stock_code=code,
                        period=freq,
                        count=count,
                        data_source=data_source,
                        asset_type=final_asset_type,
                        start_date=start_date,
                        end_date=end_date,
                        adjustment=adjustment
                    )
                else:
                    kdata = data_manager_instance.get_kdata_from_source(
                        stock_code=code,
                        period=freq,
                        count=count,
                        data_source=None,
                        asset_type=final_asset_type,
                        start_date=start_date,
                        end_date=end_date,
                        adjustment=adjustment
                    )
            finally:
                # 将实例返回连接池
                self._return_pooled_data_manager(data_manager_instance, data_source)

            # 数据验证
            if kdata.empty:
                self.logger.warning(f"获取到空的K线数据: {code}")
                return pd.DataFrame()

            # 确保数据完整性
            kdata = self._validate_and_clean_kdata(kdata, code)

            # 缓存数据
            self._set_to_cache(cache_key, kdata)

            self.logger.info(f"[数据获取] 成功获取真实K线数据: {code}, 数据量: {len(kdata)}, 日期范围: {kdata['datetime'].min() if not kdata.empty and 'datetime' in kdata.columns else 'N/A'} ~ {kdata['datetime'].max() if not kdata.empty and 'datetime' in kdata.columns else 'N/A'}")
            return kdata

        except Exception as e:
            self.logger.error(f"获取真实K线数据失败 {code}: {e}")
            return pd.DataFrame()

    def get_real_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取单个股票实时行情（不持久化）

        Args:
            symbol: 股票代码

        Returns:
            Dict 包含: symbol, code, name, price, change, change_pct, volume, amount 等
            如果获取失败返回 None
        """
        try:
            if not self.data_manager:
                self.logger.warning("数据管理器未初始化")
                return None

            uni_plugin_manager = self.data_manager.get_uni_plugin_manager()
            if not uni_plugin_manager:
                self.logger.warning("UniPluginManager 不可用")
                return None

            from ..plugin_types import AssetType
            result = uni_plugin_manager.get_real_time_data(
                symbols=[symbol],
                asset_type=AssetType.STOCK_A
            )

            if isinstance(result, pd.DataFrame):
                if not result.empty:
                    row = result.iloc[0]
                    quote_dict = row.to_dict()
                    quote_dict['symbol'] = symbol
                    return quote_dict
            elif isinstance(result, dict):
                return result.get(symbol)

            self.logger.warning(f"未获取到 {symbol} 的实时行情数据")
            return None

        except Exception as e:
            self.logger.error(f"获取实时行情失败: {symbol}, {e}")
            return None

    def get_multiple_stocks_data(self, codes: List[str], freq: str = 'D',
                                 count: int = 250) -> Dict[str, pd.DataFrame]:
        """批量获取多只股票的真实数据

        Args:
            codes: 股票代码列表
            freq: 频率
            count: 每只股票的数据条数

        Returns:
            股票代码到K线数据的映射
        """
        try:
            self.logger.info(f"批量获取真实数据: {len(codes)} 只股票")

            results = {}
            success_count = 0
            failed_count = 0

            for code in codes:
                try:
                    kdata = self.get_real_kdata(code, freq=freq, count=count)
                    if not kdata.empty:
                        results[code] = kdata
                        success_count += 1
                        self.logger.debug(f"成功获取数据: {code}")
                    else:
                        failed_count += 1
                        self.logger.warning(f"获取数据为空: {code}")
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"获取数据失败 {code}: {e}")

            self.logger.info(f"批量获取完成: 成功 {success_count}, 失败 {failed_count}")
            return results

        except Exception as e:
            self.logger.error(f"批量获取真实数据失败: {e}")
            return {}

    def get_default_test_stocks(self, count: int = 5) -> List[str]:
        """获取默认的测试股票列表

        Args:
            count: 返回股票数量

        Returns:
            股票代码列表
        """
        try:
            # 从股票池中选择活跃的股票
            available_stocks = []

            for code in self._default_stocks:
                try:
                    # 检查股票是否有效
                    test_data = self.get_real_kdata(code, count=5)
                    if not test_data.empty:
                        available_stocks.append(code)
                        if len(available_stocks) >= count:
                            break
                except Exception:
                    continue

            if len(available_stocks) < count:
                self.logger.warning(
                    f"只找到 {len(available_stocks)} 只有效股票，少于请求的 {count} 只")

            self.logger.info(f"获取默认测试股票: {available_stocks}")
            return available_stocks[:count]

        except Exception as e:
            self.logger.error(f"获取默认测试股票失败: {e}")
            return self._default_stocks[:count]

    def create_real_test_datasets(self, pattern_name: str, count: int = 5) -> List[Dict[str, Any]]:
        """创建真实的测试数据集，替换虚假数据

        Args:
            pattern_name: 形态名称
            count: 数据集数量

        Returns:
            真实测试数据集列表
        """
        try:
            self.logger.info(f"创建真实测试数据集: {pattern_name}, 数量: {count}")

            # 获取测试股票
            test_stocks = self.get_default_test_stocks(count)

            datasets = []
            for i, code in enumerate(test_stocks):
                try:
                    # 获取真实K线数据
                    kdata = self.get_real_kdata(code, count=250)

                    if kdata.empty:
                        self.logger.warning(f"股票 {code} 数据为空，跳过")
                        continue

                    # 创建数据集
                    dataset = {
                        'name': f"{pattern_name}_real_dataset_{i+1}",
                        'code': code,
                        'data': kdata,
                        'pattern_name': pattern_name,
                        'data_source': 'real_market',
                        'created_at': datetime.now(),
                        'data_count': len(kdata),
                        'date_range': {
                            'start': kdata.index[0] if len(kdata) > 0 else None,
                            'end': kdata.index[-1] if len(kdata) > 0 else None
                        }
                    }

                    datasets.append(dataset)
                    self.logger.debug(f"创建数据集: {code}, 数据量: {len(kdata)}")

                except Exception as e:
                    self.logger.error(f"创建数据集失败 {code}: {e}")

            self.logger.info(f"成功创建 {len(datasets)} 个真实测试数据集")
            return datasets

        except Exception as e:
            self.logger.error(f"创建真实测试数据集失败: {e}")
            return []

    def get_real_stock_list(self, market: str = 'all', limit: int = 100) -> List[str]:
        """获取真实股票列表

        Args:
            market: 市场类型 ('all', 'sh', 'sz', 'bj')
            limit: 返回数量限制

        Returns:
            股票代码列表
        """
        try:
            self.logger.info(f"获取真实股票列表: 市场={market}, 限制={limit}")

            # 使用数据管理器获取股票列表
            stock_df = self.data_manager.get_stock_list(market=market)

            if stock_df.empty:
                self.logger.warning("获取到空的股票列表")
                return []

            # 提取股票代码
            if 'code' in stock_df.columns:
                codes = stock_df['code'].tolist()
            elif stock_df.index.name == 'code':
                codes = stock_df.index.tolist()
            else:
                codes = stock_df.iloc[:, 0].tolist()  # 假设第一列是代码

            # 限制数量（0表示不限制）
            if limit > 0:
                codes = codes[:limit]

            self.logger.info(f"获取到 {len(codes)} 只股票")
            return codes

        except Exception as e:
            self.logger.error(f"获取真实股票列表失败: {e}")
            return []

    def _validate_and_clean_kdata(self, kdata: pd.DataFrame, code: str) -> pd.DataFrame:
        """验证和清理K线数据

        Args:
            kdata: K线数据
            code: 股票代码

        Returns:
            清理后的K线数据
        """
        try:
            if kdata.empty:
                return kdata

            # 关键修复：在处理任何数据前，先解决datetime索引/列歧义问题
            # 如果datetime既是索引又是列，会导致"'datetime' is both an index level and a column label"错误
            if 'datetime' in kdata.columns and (kdata.index.name == 'datetime' or isinstance(kdata.index, pd.DatetimeIndex)):
                self.logger.debug(f"[{code}] 检测到datetime既是列又是索引，重置索引")
                kdata = kdata.reset_index(drop=True)

            # 确保必要的列存在
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = [
                col for col in required_columns if col not in kdata.columns]

            if missing_columns:
                self.logger.warning(f"股票 {code} 缺少列: {missing_columns}")
                return pd.DataFrame()

            # 移除无效数据
            kdata = kdata.dropna(subset=required_columns)

            # 确保价格关系正确 (high >= low, high >= open, high >= close, low <= open, low <= close)
            invalid_mask = (
                (kdata['high'] < kdata['low']) |
                (kdata['high'] < kdata['open']) |
                (kdata['high'] < kdata['close']) |
                (kdata['low'] > kdata['open']) |
                (kdata['low'] > kdata['close'])
            )

            if invalid_mask.any():
                invalid_count = invalid_mask.sum()
                self.logger.warning(
                    f"股票 {code} 有 {invalid_count} 条无效价格关系数据，已移除")
                kdata = kdata[~invalid_mask]

            # 确保成交量为正数
            kdata = kdata[kdata['volume'] > 0]

            # 添加code字段（如果不存在）
            if 'code' not in kdata.columns:
                kdata['code'] = code

            # 修复：确保datetime是列而不是索引
            # 这样可以避免后续验证时"datetime is both an index level and a column label"错误
            if 'datetime' in kdata.columns:
                kdata['datetime'] = pd.to_datetime(kdata['datetime'])
                # 不设置datetime为索引，保持为列以兼容后续数据验证
            elif isinstance(kdata.index, pd.DatetimeIndex):
                # 如果datetime是索引，转换为列
                kdata = kdata.reset_index(drop=False)
                if kdata.index.name == 'datetime' or 'datetime' not in kdata.columns:
                    kdata = kdata.reset_index(drop=True)
            
            # 按datetime列排序（如果存在）
            if 'datetime' in kdata.columns:
                kdata = kdata.sort_values('datetime').reset_index(drop=True)
            else:
                # 如果没有datetime列但有索引，则按索引排序
                kdata = kdata.sort_index()

            self.logger.debug(f"数据验证完成: {code}, 有效数据量: {len(kdata)}")
            return kdata

        except Exception as e:
            self.logger.error(f"验证和清理K线数据失败 {code}: {e}")
            return pd.DataFrame()

    def _get_from_cache(self, key: str) -> Optional[pd.DataFrame]:
        """从缓存获取数据"""
        with self._cache_lock:
            if key in self._cache:
                data, timestamp = self._cache[key]
                if time.time() - timestamp < self._cache_ttl:
                    return data.copy()
                else:
                    del self._cache[key]
            return None

    def _set_to_cache(self, key: str, data: pd.DataFrame):
        """设置数据到缓存"""
        with self._cache_lock:
            self._cache[key] = (data.copy(), time.time())

    def clear_cache(self):
        """清空缓存"""
        with self._cache_lock:
            self._cache.clear()
            self.logger.info("真实数据提供器缓存已清空")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._cache_lock:
            current_time = time.time()
            valid_count = 0
            expired_count = 0

            for key, (data, timestamp) in self._cache.items():
                if current_time - timestamp < self._cache_ttl:
                    valid_count += 1
                else:
                    expired_count += 1

            return {
                'total_cached': len(self._cache),
                'valid_cached': valid_count,
                'expired_cached': expired_count,
                'cache_ttl': self._cache_ttl
            }

    def import_stock_data_with_validation(self, codes: List[str], freq: str = 'D',
                                          start_date: Optional[str] = None,
                                          end_date: Optional[str] = None,
                                          skip_existing: bool = True,
                                          progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        批量导入股票数据，支持存在性检查和跳过逻辑

        Args:
            codes: 股票代码列表
            freq: 数据频率
            start_date: 开始日期
            end_date: 结束日期
            skip_existing: 是否跳过已存在的数据
            progress_callback: 进度回调函数

        Returns:
            导入结果统计
        """
        try:
            self.logger.info(f"开始批量导入股票数据: {len(codes)}只股票, 频率: {freq}")

            results = {
                'total_stocks': len(codes),
                'imported_stocks': 0,
                'skipped_stocks': 0,
                'failed_stocks': 0,
                'import_details': [],
                'validation_results': []
            }

            for i, code in enumerate(codes):
                try:
                    # 更新进度
                    if progress_callback:
                        progress_callback(f"处理股票 {code} ({i+1}/{len(codes)})")

                    # 检查数据是否已存在
                    if skip_existing:
                        existence_check = self.check_data_exists(code, freq, start_date, end_date)

                        if existence_check['exists'] and existence_check['count'] > 0:
                            self.logger.info(f"跳过已存在数据: {code} (现有 {existence_check['count']} 条记录)")
                            results['skipped_stocks'] += 1
                            results['import_details'].append({
                                'code': code,
                                'status': 'skipped',
                                'reason': f"已存在 {existence_check['count']} 条记录",
                                'existing_count': existence_check['count'],
                                'date_range': existence_check['date_range']
                            })
                            continue

                    # 导入数据
                    data = self.get_real_kdata(code, freq, start_date, end_date)

                    if not data.empty:
                        # 这里可以添加实际的数据库写入逻辑
                        # 目前只是获取数据，实际项目中需要调用数据管理器的保存方法
                        results['imported_stocks'] += 1
                        results['import_details'].append({
                            'code': code,
                            'status': 'imported',
                            'records_count': len(data),
                            'date_range': (data.index.min(), data.index.max()) if not data.empty else None
                        })
                        self.logger.info(f"成功导入: {code} ({len(data)} 条记录)")
                    else:
                        # 检查是否是无效股票代码
                        if self._is_invalid_stock_code(code):
                            self.logger.warning(f"无效股票代码，标记为跳过: {code}")
                            results['skipped_stocks'] += 1
                            results['import_details'].append({
                                'code': code,
                                'status': 'skipped',
                                'reason': '无效股票代码',
                                'note': '股票代码不存在或已退市'
                            })
                        else:
                            results['failed_stocks'] += 1
                            results['import_details'].append({
                                'code': code,
                                'status': 'failed',
                                'reason': '无法获取数据（网络或数据源问题）'
                            })
                            self.logger.warning(f"导入失败: {code} - 无法获取数据")

                except Exception as e:
                    results['failed_stocks'] += 1
                    results['import_details'].append({
                        'code': code,
                        'status': 'failed',
                        'reason': str(e)
                    })
                    self.logger.error(f"导入股票 {code} 失败: {e}")

            # 导入后验证
            if results['imported_stocks'] > 0:
                validation_results = self.validate_imported_data(codes, freq, start_date, end_date)
                results['validation_results'] = validation_results

            self.logger.info(f"批量导入完成: 总计 {results['total_stocks']}, "
                             f"导入 {results['imported_stocks']}, "
                             f"跳过 {results['skipped_stocks']}, "
                             f"失败 {results['failed_stocks']}")

            return results

        except Exception as e:
            self.logger.error(f"批量导入失败: {e}")
            return {
                'total_stocks': len(codes),
                'imported_stocks': 0,
                'skipped_stocks': 0,
                'failed_stocks': len(codes),
                'import_details': [],
                'validation_results': [],
                'error': str(e)
            }

    def validate_imported_data(self, codes: List[str], freq: str = 'D',
                               start_date: Optional[str] = None,
                               end_date: Optional[str] = None,
                               sample_ratio: float = 0.1) -> Dict[str, Any]:
        """
        验证导入的数据质量（抽查验证）

        Args:
            codes: 股票代码列表
            freq: 数据频率
            start_date: 开始日期
            end_date: 结束日期
            sample_ratio: 抽查比例 (0.0-1.0)

        Returns:
            验证结果
        """
        try:
            import random

            # 计算抽查数量
            sample_size = max(1, int(len(codes) * sample_ratio))
            sample_codes = random.sample(codes, min(sample_size, len(codes)))

            self.logger.info(f"开始抽查验证: 从 {len(codes)} 只股票中抽查 {len(sample_codes)} 只")

            validation_results = {
                'total_sampled': len(sample_codes),
                'valid_count': 0,
                'invalid_count': 0,
                'validation_details': [],
                'quality_score': 0.0
            }

            for code in sample_codes:
                try:
                    # 检查数据完整性
                    data = self.get_real_kdata(code, freq, start_date, end_date)

                    if data.empty:
                        validation_results['invalid_count'] += 1
                        validation_results['validation_details'].append({
                            'code': code,
                            'status': 'invalid',
                            'reason': '数据为空'
                        })
                        continue

                    # 基本数据质量检查
                    issues = []

                    # 检查必要字段
                    required_fields = ['open', 'high', 'low', 'close', 'volume']
                    missing_fields = [field for field in required_fields if field not in data.columns]
                    if missing_fields:
                        issues.append(f"缺失字段: {missing_fields}")

                    # 检查数据异常
                    if not missing_fields:
                        # 检查价格逻辑
                        invalid_prices = (data['high'] < data['low']) | (data['high'] < data['open']) | (data['high'] < data['close']) | (data['low'] > data['open']) | (data['low'] > data['close'])
                        if invalid_prices.any():
                            issues.append(f"价格逻辑异常: {invalid_prices.sum()} 条记录")

                        # 检查零值或负值
                        zero_negative = (data[['open', 'high', 'low', 'close']] <= 0).any(axis=1)
                        if zero_negative.any():
                            issues.append(f"价格零值或负值: {zero_negative.sum()} 条记录")

                        # 检查成交量异常
                        if (data['volume'] < 0).any():
                            issues.append("成交量负值")

                    if issues:
                        validation_results['invalid_count'] += 1
                        validation_results['validation_details'].append({
                            'code': code,
                            'status': 'invalid',
                            'reason': '; '.join(issues),
                            'records_count': len(data)
                        })
                    else:
                        validation_results['valid_count'] += 1
                        validation_results['validation_details'].append({
                            'code': code,
                            'status': 'valid',
                            'records_count': len(data),
                            'date_range': (data.index.min(), data.index.max())
                        })

                except Exception as e:
                    validation_results['invalid_count'] += 1
                    validation_results['validation_details'].append({
                        'code': code,
                        'status': 'error',
                        'reason': str(e)
                    })

            # 计算质量分数
            if validation_results['total_sampled'] > 0:
                validation_results['quality_score'] = validation_results['valid_count'] / validation_results['total_sampled']

            self.logger.info(f"抽查验证完成: 有效 {validation_results['valid_count']}, "
                             f"无效 {validation_results['invalid_count']}, "
                             f"质量分数: {validation_results['quality_score']:.2%}")

            return validation_results

        except Exception as e:
            self.logger.error(f"数据验证失败: {e}")
            return {
                'total_sampled': 0,
                'valid_count': 0,
                'invalid_count': 0,
                'validation_details': [],
                'quality_score': 0.0,
                'error': str(e)
            }

    def _is_invalid_stock_code(self, code: str) -> bool:
        """
        检查股票代码是否无效

        Args:
            code: 股票代码

        Returns:
            True if 股票代码无效, False otherwise
        """
        try:
            # 基本格式检查
            if not code or len(code) < 6:
                return True

            # 检查是否包含非数字字符（除了前缀）
            if not code.replace('sh', '').replace('sz', '').replace('bj', '').isdigit():
                return True

            # 尝试通过数据管理器验证股票代码
            try:
                # 获取少量数据来验证股票代码的有效性
                test_data = self.data_manager.get_kdata(
                    stock_code=code,
                    period='D',
                    count=1
                )

                # 如果能获取到数据，说明股票代码有效
                # 如果获取不到数据，可能是无效代码或网络问题
                # 这里我们需要进一步判断
                return False  # 暂时认为是网络问题，不是无效代码

            except Exception as e:
                error_msg = str(e).lower()

                # 检查错误信息中是否包含"无效"、"不存在"等关键词
                invalid_keywords = [
                    '无效', 'invalid', '不存在', 'not found',
                    '股票代码无效', 'stock code invalid',
                    '已退市', 'delisted'
                ]

                for keyword in invalid_keywords:
                    if keyword in error_msg:
                        return True

                # 其他错误认为是网络或数据源问题
                return False

        except Exception as e:
            self.logger.debug(f"检查股票代码有效性时出错 {code}: {e}")
            # 出错时保守处理，认为不是无效代码
            return False

    def get_invalid_stock_codes_report(self, codes: List[str]) -> Dict[str, Any]:
        """
        生成无效股票代码报告

        Args:
            codes: 股票代码列表

        Returns:
            无效股票代码报告
        """
        try:
            invalid_codes = []
            valid_codes = []

            self.logger.info(f"开始检查 {len(codes)} 个股票代码的有效性...")

            for i, code in enumerate(codes):
                try:
                    if self._is_invalid_stock_code(code):
                        invalid_codes.append(code)
                        self.logger.debug(f"发现无效股票代码: {code}")
                    else:
                        valid_codes.append(code)

                    # 每100个代码报告一次进度
                    if (i + 1) % 100 == 0:
                        self.logger.info(f"已检查 {i + 1}/{len(codes)} 个股票代码")

                except Exception as e:
                    self.logger.warning(f"检查股票代码 {code} 时出错: {e}")
                    valid_codes.append(code)  # 出错时保守处理

            report = {
                'total_codes': len(codes),
                'valid_codes': valid_codes,
                'invalid_codes': invalid_codes,
                'valid_count': len(valid_codes),
                'invalid_count': len(invalid_codes),
                'invalid_ratio': len(invalid_codes) / len(codes) if codes else 0
            }

            self.logger.info(f"股票代码检查完成: 总计 {report['total_codes']}, "
                             f"有效 {report['valid_count']}, "
                             f"无效 {report['invalid_count']}, "
                             f"无效率 {report['invalid_ratio']:.2%}")

            return report

        except Exception as e:
            self.logger.error(f"生成无效股票代码报告失败: {e}")
            return {
                'total_codes': len(codes),
                'valid_codes': codes,
                'invalid_codes': [],
                'valid_count': len(codes),
                'invalid_count': 0,
                'invalid_ratio': 0.0,
                'error': str(e)
            }

# 全局真实数据提供器实例
_real_data_provider: Optional[RealDataProvider] = None
_provider_lock = threading.RLock()

def get_real_data_provider() -> RealDataProvider:
    """获取全局真实数据提供器实例

    Returns:
        真实数据提供器实例
    """
    global _real_data_provider

    with _provider_lock:
        if _real_data_provider is None:
            _real_data_provider = RealDataProvider()

        return _real_data_provider

def initialize_real_data_provider() -> RealDataProvider:
    """初始化真实数据提供器

    Returns:
        真实数据提供器实例
    """
    global _real_data_provider

    with _provider_lock:
        _real_data_provider = RealDataProvider()
        return _real_data_provider

# 便捷函数

def get_real_kdata(code: str, **kwargs) -> pd.DataFrame:
    """获取真实K线数据的便捷函数"""
    provider = get_real_data_provider()
    return provider.get_real_kdata(code, **kwargs)

def create_real_test_data(pattern_name: str = "test", count: int = 5) -> List[Dict[str, Any]]:
    """创建真实测试数据的便捷函数"""
    provider = get_real_data_provider()
    return provider.create_real_test_datasets(pattern_name, count)

def get_real_stock_list(**kwargs) -> List[str]:
    """获取真实股票列表的便捷函数"""
    provider = get_real_data_provider()
    return provider.get_real_stock_list(**kwargs)

def import_stock_data_with_validation(codes: List[str], **kwargs) -> Dict[str, Any]:
    """批量导入股票数据的便捷函数"""
    provider = get_real_data_provider()
    return provider.import_stock_data_with_validation(codes, **kwargs)

def check_data_exists(code: str, **kwargs) -> Dict[str, Any]:
    """检查数据存在性的便捷函数"""
    provider = get_real_data_provider()
    return provider.check_data_exists(code, **kwargs)
