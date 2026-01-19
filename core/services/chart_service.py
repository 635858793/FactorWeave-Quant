from loguru import logger

from core.plugin_types import AssetType
"""
图表服务模块

负责图表的创建、渲染和管理。
"""

import pandas as pd
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from .base_service import CacheableService, ConfigurableService
from ..events import ChartUpdateEvent, StockSelectedEvent, EventBus
from ..utils.data_standardizer import DataStandardizer

if TYPE_CHECKING:
    from .unified_data_manager import UnifiedDataManager

# 错误类型枚举
class ErrorType:
    DATA_LOAD_ERROR = "data_load_error"
    RENDER_ERROR = "render_error"
    UNKNOWN_ERROR = "unknown_error"

# 错误处理器
class ErrorHandler:
    """错误处理器"""

    def __init__(self):
        self.error_callbacks = {}
        self.error_history = []
        self.max_history = 100

    def handle_error(self, error_type: str, error_msg: str, callback=None, context=None):
        """处理错误"""
        error_info = {
            'type': error_type,
            'message': error_msg,
            'timestamp': asyncio.get_event_loop().time(),
            'context': context or {}
        }

        # 记录错误
        self.error_history.append(error_info)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)

        # 调用错误回调
        if callback:
            try:
                callback(error_info)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

        # 调用注册的错误处理器
        if error_type in self.error_callbacks:
            for cb in self.error_callbacks[error_type]:
                try:
                    cb(error_info)
                except Exception as e:
                    logger.error(f"Error in registered error handler: {e}")

    def register_error_handler(self, error_type: str, callback):
        """注册错误处理器"""
        if error_type not in self.error_callbacks:
            self.error_callbacks[error_type] = []
        self.error_callbacks[error_type].append(callback)

    def get_error_history(self):
        """获取错误历史"""
        return self.error_history

# 重试管理器
class RetryManager:
    """重试管理器"""

    def __init__(self, max_retries=3, retry_delay=1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def execute_with_retry(self, func, *args, **kwargs):
        """执行带重试的函数"""
        retries = 0
        last_error = None

        while retries < self.max_retries:
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                # 不重试取消的请求
                raise
            except Exception as e:
                last_error = e
                retries += 1
                if retries < self.max_retries:
                    logger.warning(
                        f"Retry {retries}/{self.max_retries} after error: {e}")
                    await asyncio.sleep(self.retry_delay * retries)
                else:
                    logger.error(f"Failed after {retries} retries: {e}")

        # 所有重试都失败
        if last_error:
            raise last_error
        return None

class ChartService(CacheableService, ConfigurableService):
    """
    图表服务

    负责图表的创建、渲染和管理。
    """

    def __init__(self,
                 event_bus: EventBus,
                 config: Optional[Dict[str, Any]] = None,
                 cache_size: int = 100,
                 unified_data_manager: Optional["UnifiedDataManager"] = None,
                 **kwargs):
        """
        初始化图表服务

        Args:
            unified_data_manager: 统一数据管理器
            event_bus: 事件总线
            config: 服务配置
            cache_size: 缓存大小
            **kwargs: 其他参数
        """
        # 初始化各个基类
        super().__init__(**kwargs)
        ConfigurableService.__init__(self, config=config, **kwargs)

        # 移除对unified_data_manager的依赖，改为使用data_standardizer
        try:
            self.data_standardizer = DataStandardizer()
        except Exception as e:
            logger.warning(f"DataStandardizer初始化失败: {e}")
            self.data_standardizer = None

        self._current_chart_type = 'candlestick'
        self._current_period = 'D'
        self._current_indicators = []
        self._current_stock_code = None
        self._chart_themes = {}

        # 错误处理和重试
        self.error_handler = ErrorHandler()
        self.retry_manager = RetryManager(max_retries=3)

        # 请求管理
        self.active_requests: Dict[str, asyncio.Task] = {}
        self.request_lock = asyncio.Lock()

        # 显式初始化，确保属性存在
        if not hasattr(self, 'industry_service'):
            self.industry_service = None

    def _do_initialize(self) -> None:
        """初始化图表服务"""
        try:
            # 加载默认配置
            self._current_chart_type = self.get_config_value(
                'default_chart_type', 'candlestick')
            self._current_period = self.get_config_value('default_period', 'D')
            self._current_indicators = self.get_config_value(
                'default_indicators', [])

            # 初始化图表主题
            self._load_chart_themes()

            logger.info("Chart service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize chart service: {e}")
            raise

    def create_chart(self, stock_code: str, chart_type: str = None,
                     period: str = None, indicators: List[str] = None,
                     time_range: int = 365) -> Optional[Dict[str, Any]]:
        """
        [已废弃] 创建图表。请改为发布StockSelectedEvent事件来触发图表更新。

        Raises:
            NotImplementedError: 此方法已被废弃，以推广事件驱动的异步模型。
        """
        # 方法已移除 - 请使用 StockSelectedEvent 事件
        raise NotImplementedError(
            "create_chart is deprecated. Publish StockSelectedEvent instead.")

    def update_chart_type(self, chart_type: str) -> bool:
        """
        更新图表类型

        Args:
            chart_type: 新的图表类型

        Returns:
            是否成功更新
        """
        self._ensure_initialized()

        try:
            if chart_type in self._get_supported_chart_types():
                self._current_chart_type = chart_type
                logger.info(f"Chart type updated to: {chart_type}")
                # 触发图表重新加载
                if self._current_stock_code:
                    event = StockSelectedEvent(
                        stock_code=self._current_stock_code)
                    self.event_bus.publish(event)
                return True
            else:
                logger.warning(f"Unsupported chart type: {chart_type}")
                return False
        except Exception as e:
            logger.error(f"Failed to update chart type: {e}")
            return False

    def update_period(self, period: str) -> bool:
        """
        更新周期

        Args:
            period: 新的周期

        Returns:
            是否成功更新
        """
        self._ensure_initialized()
        try:
            if period in self.get_supported_periods():
                self._current_period = period
                logger.info(f"Period updated to: {period}")
                # 触发图表重新加载
                if self._current_stock_code:
                    event = StockSelectedEvent(
                        stock_code=self._current_stock_code)
                    self.event_bus.publish(event)
                return True
            else:
                logger.warning(f"Unsupported period: {period}")
                return False
        except Exception as e:
            logger.error(f"Failed to update period: {e}")
            return False

    def add_indicator(self, indicator: str) -> bool:
        """
        添加指标

        Args:
            indicator: 指标名称

        Returns:
            是否成功添加
        """
        self._ensure_initialized()

        try:
            if indicator not in self._current_indicators:
                self._current_indicators.append(indicator)
                logger.info(f"Indicator added: {indicator}")
                # 触发图表重新加载
                if self._current_stock_code:
                    event = StockSelectedEvent(
                        stock_code=self._current_stock_code)
                    self.event_bus.publish(event)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to add indicator: {e}")
            return False

    def remove_indicator(self, indicator: str) -> bool:
        """
        移除指标

        Args:
            indicator: 指标名称

        Returns:
            是否成功移除
        """
        self._ensure_initialized()

        try:
            if indicator in self._current_indicators:
                self._current_indicators.remove(indicator)
                logger.info(f"Indicator removed: {indicator}")
                # 触发图表重新加载
                if self._current_stock_code:
                    event = StockSelectedEvent(
                        stock_code=self._current_stock_code)
                    self.event_bus.publish(event)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove indicator: {e}")
            return False

    def get_current_chart_config(self) -> Dict[str, Any]:
        """
        获取当前图表配置

        Returns:
            当前图表配置
        """
        return {
            'chart_type': self._current_chart_type,
            'period': self._current_period,
            'indicators': self._current_indicators.copy(),
            'stock_code': self._current_stock_code
        }

    def get_supported_chart_types(self) -> List[str]:
        """
        获取支持的图表类型

        Returns:
            支持的图表类型列表
        """
        return self._get_supported_chart_types()

    def get_supported_periods(self) -> List[str]:
        """
        获取支持的周期

        Returns:
            支持的周期列表
        """
        return self._get_supported_periods()

    def get_available_indicators(self) -> List[str]:
        """
        获取可用的指标

        Returns:
            可用的指标列表
        """
        return [
            'MA5', 'MA10', 'MA20', 'MA60',
            'MACD', 'KDJ', 'RSI', 'BOLL',
            'VOL', 'BIAS', 'WR', 'CCI'
        ]

    def get_chart_data(self, stock_code: str, period: str = None,
                       indicators: List[str] = None, time_range: int = 365) -> Dict[str, Any]:
        """
        获取图表数据（为UI层提供的便捷方法）

        Args:
            stock_code: 股票代码
            period: 周期
            indicators: 指标列表
            time_range: 时间范围

        Returns:
            包含K线数据和指标数据的字典
        """
        self._ensure_initialized()

        try:
            # 获取股票服务
            stock_service = self._get_stock_service()
            if not stock_service:
                logger.error("Stock service not available")
                return {}

            # 使用默认值
            period = period or self._current_period
            indicators = indicators or self._current_indicators

            # 获取股票基本信息
            stock_info = stock_service.get_stock_info(stock_code)
            if not stock_info:
                logger.warning(f"Stock info not found for {stock_code}")
                return {}

            # 获取股票名称（处理不同类型的stock_info）
            if hasattr(stock_info, 'name'):
                stock_name = stock_info.name
            elif hasattr(stock_info, 'get'):
                stock_name = stock_info.get('name', stock_code)
            else:
                stock_name = stock_code

            # 获取K线数据
            kline_data = stock_service.get_stock_data(
                stock_code, period, time_range)
            if kline_data is None or kline_data.empty:
                logger.warning(f"No kline data available for {stock_code}")
                return {
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'kline_data': [],
                    'indicators': {},
                    'period': period
                }

            # 转换K线数据为列表格式（适合UI显示）
            kline_list = []
            for _, row in kline_data.iterrows():
                # 格式化日期字符串（只保留日期部分，适合日线图显示）
                if hasattr(row.name, 'strftime'):
                    date_str = row.name.strftime('%Y-%m-%d')
                else:
                    date_str = str(row.name)[:10]  # 取前10个字符作为日期

                kline_list.append({
                    'date': date_str,  # 使用'date'字段名，与middle_panel保持一致
                    'datetime': row.name.strftime('%Y-%m-%d %H:%M:%S') if hasattr(row.name, 'strftime') else str(row.name),
                    'open': float(row.get('open', 0)),
                    'high': float(row.get('high', 0)),
                    'low': float(row.get('low', 0)),
                    'close': float(row.get('close', 0)),
                    'volume': int(row.get('volume', 0))
                })

            # 计算技术指标（这里是简化版本，实际应该调用专门的指标计算服务）
            indicators_data = self._calculate_indicators(
                kline_data, indicators)

            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'kline_data': kline_list,
                'indicators': indicators_data,
                'period': period,
                'last_update': kline_data.index[-1].strftime('%Y-%m-%d %H:%M:%S') if not kline_data.empty else None
            }

        except Exception as e:
            logger.error(f"Failed to get chart data for {stock_code}: {e}")
            return {}

    def _calculate_indicators(self, kline_data: pd.DataFrame, indicators: List[str]) -> Dict[str, Any]:
        """
        计算技术指标

        Args:
            kline_data: K线数据
            indicators: 指标列表

        Returns:
            指标数据字典
        """
        indicators_data = {}

        if kline_data.empty:
            return indicators_data

        try:
            close_prices = kline_data['close']
            high_prices = kline_data['high']
            low_prices = kline_data['low']
            volume = kline_data['volume']

            for indicator in indicators:
                if indicator.startswith('MA') and not indicator.startswith('MACD'):
                    # 移动平均线
                    try:
                        period = int(indicator[2:]) if len(
                            indicator) > 2 else 5
                        ma_values = close_prices.rolling(window=period).mean()
                        indicators_data[indicator] = ma_values.fillna(
                            0).tolist()
                    except ValueError:
                        # 如果无法解析周期，跳过该指标
                        logger.warning(
                            f"Cannot parse period from indicator: {indicator}")
                        continue

                elif indicator == 'VOL':
                    # 成交量
                    indicators_data[indicator] = volume.tolist()

                elif indicator == 'MACD':
                    # MACD指标（简化计算）
                    ema12 = close_prices.ewm(span=12).mean()
                    ema26 = close_prices.ewm(span=26).mean()
                    dif = ema12 - ema26
                    dea = dif.ewm(span=9).mean()
                    macd = (dif - dea) * 2

                    indicators_data['MACD'] = {
                        'DIF': dif.fillna(0).tolist(),
                        'DEA': dea.fillna(0).tolist(),
                        'MACD': macd.fillna(0).tolist()
                    }

                elif indicator == 'RSI':
                    # RSI指标（简化计算）
                    delta = close_prices.diff()
                    gain = (delta.where(delta > 0, 0)
                            ).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)
                            ).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    indicators_data[indicator] = rsi.fillna(50).tolist()

                elif indicator == 'BOLL':
                    # 布林带
                    ma20 = close_prices.rolling(window=20).mean()
                    std20 = close_prices.rolling(window=20).std()
                    upper = ma20 + (std20 * 2)
                    lower = ma20 - (std20 * 2)

                    indicators_data['BOLL'] = {
                        'UPPER': upper.fillna(0).tolist(),
                        'MID': ma20.fillna(0).tolist(),
                        'LOWER': lower.fillna(0).tolist()
                    }

                # 其他指标可以在这里继续添加...

        except Exception as e:
            logger.error(f"Failed to calculate indicators: {e}")

        return indicators_data

    def export_chart(self, format: str = 'png', **kwargs) -> Optional[str]:
        """导出图表"""
        # 实现图表导出逻辑
        logger.warning("导出图表功能待实现")
        return None

    async def _cancel_previous_requests(self):
        """取消先前的请求"""
        async with self.request_lock:
            for request_id, task in list(self.active_requests.items()):
                if not task.done():
                    task.cancel()
                    logger.info(f"已取消先前的请求: {request_id}")
            self.active_requests.clear()

    async def _remove_active_request(self, request_id: str):
        """从活动请求字典中安全地移除一个请求"""
        async with self.request_lock:
            self.active_requests.pop(request_id, None)

    def _on_data_load_error(self, error_info):
        """处理数据加载错误"""
        logger.error(f"数据加载错误: {error_info}")
        code = error_info.get('context', {}).get('code')
        self.chart_loading_failed.emit(code, "Failed to load data")

        # 显示用户友好的错误信息
        self.show_error_message.emit(
            "数据加载失败",
            f"无法加载股票数据，请检查网络连接或稍后再试。\n详情: {error_info.get('message')}"
        )

    def _on_unknown_error(self, error_info):
        """处理未知错误"""
        code = error_info.get('context', {}).get('code')
        self.chart_loading_failed.emit(
            code, f"Error: {error_info.get('message')}")

        # 显示用户友好的错误信息
        self.show_error_message.emit(
            "发生错误",
            f"处理请求时发生错误。\n详情: {error_info.get('message')}"
        )

    async def cancel_previous_requests(self):
        """取消所有先前的图表数据请求"""
        async with self.request_lock:
            if not self.active_requests:
                return

            logger.info(f"正在取消 {len(self.active_requests)} 个活动的图表数据任务...")
            for task_id, task in list(self.active_requests.items()):
                if not task.done():
                    task.cancel()
                    logger.debug(f"已取消图表任务: {task_id}")
            self.active_requests.clear()
            logger.info("所有活动的图表任务均已取消。")


    def _get_data_manager(self):
        """获取数据管理器（已弃用）"""
        # 返回data_standardizer而不是data_manager
        return getattr(self, 'data_standardizer', None)

    def _get_industry_service(self):
        """获取行业服务，处理服务容器可能不存在的情况"""
        if self.industry_service:
            return self.industry_service
        try:
            # 尝试从容器获取
            from core.containers import get_service_container
            self.industry_service = get_service_container().get_service('industry')
            return self.industry_service
        except Exception as e:
            logger.warning(f"无法获取IndustryService: {e}")
            return None

    def _get_stock_service(self):
        """获取股票服务"""
        try:
            # 导入StockService放在方法开始，确保在所有分支中都可用
            from .stock_service import StockService

            if hasattr(self, 'service_container') and self.service_container:
                return self.service_container.resolve(StockService)
            else:
                # 通过全局服务容器获取
                try:
                    from ..containers import get_service_container
                    container = get_service_container()
                    return container.resolve(StockService)
                except ImportError:
                    # 如果没有服务容器，返回None
                    logger.warning("Service container not available")
                    return None
        except Exception as e:
            logger.error(f"Failed to get stock service: {e}")
        return None

    def _get_supported_chart_types(self) -> List[str]:
        """获取支持的图表类型"""
        return ['candlestick', 'line', 'bar', 'area']

    def _get_supported_periods(self) -> List[str]:
        """获取支持的周期"""
        return ['1min', '5min', '15min', '30min', '60min', 'D', 'W', 'M']

    def _get_current_theme(self) -> Dict[str, Any]:
        """获取当前主题"""
        theme_name = self.get_config_value('theme', 'default')
        return self._chart_themes.get(theme_name, self._get_default_theme())

    def _get_default_theme(self) -> Dict[str, Any]:
        """获取默认主题"""
        return {
            # 'background_color': '#ffffff',
            'grid_color': '#e0e0e0',
            'text_color': '#333333',
            'up_color': '#ff4444',
            'down_color': '#00aa00',
            'ma_colors': ['#ff6600', '#0066ff', '#ff00ff', '#00ffff']
        }

    def _get_chart_layout(self, chart_type: str, indicators: List[str]) -> Dict[str, Any]:
        """获取图表布局"""
        layout = {
            'main_chart': {
                'type': chart_type,
                'height': 0.7  # 占总高度的70%
            },
            'sub_charts': []
        }

        # 根据指标添加子图表
        volume_indicators = ['VOL']
        oscillator_indicators = ['MACD', 'KDJ', 'RSI', 'WR', 'CCI']

        for indicator in indicators:
            if indicator in volume_indicators:
                layout['sub_charts'].append({
                    'type': 'volume',
                    'indicators': [indicator],
                    'height': 0.15
                })
            elif indicator in oscillator_indicators:
                layout['sub_charts'].append({
                    'type': 'oscillator',
                    'indicators': [indicator],
                    'height': 0.15
                })

        return layout

    def _load_chart_themes(self) -> None:
        """加载图表主题"""
        self._chart_themes = {
            'default': self._get_default_theme(),
            'dark': {
                # 'background_color': '#1e1e1e',
                'grid_color': '#404040',
                'text_color': '#ffffff',
                'up_color': '#ff4444',
                'down_color': '#00aa00',
                'ma_colors': ['#ff6600', '#0066ff', '#ff00ff', '#00ffff']
            }
        }

    def _clear_period_cache(self) -> None:
        """清除周期相关缓存"""
        keys_to_remove = []
        for key in self._cache.keys():
            if 'chart_' in key and f'_{self._current_period}_' in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._cache[key]

    def _clear_indicator_cache(self) -> None:
        """清除指标相关缓存"""
        # 由于指标列表变化，清除所有图表缓存
        keys_to_remove = []
        for key in self._cache.keys():
            if key.startswith('chart_'):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._cache[key]

    def _do_dispose(self) -> None:
        """清理资源"""
        self._current_stock_code = None
        self._current_indicators.clear()
        self._chart_themes.clear()
        super()._do_dispose()

    def get_kdata(self, stock_code: str, period: str = 'D', count: int = 365, 
                  asset_type: 'AssetType' = None) -> pd.DataFrame:
        """
        获取K线数据（✅ 优化：支持多资产类型，委托给股票服务）

        Args:
            stock_code: 股票代码（或其他资产代码）
            period: 周期
            count: 数据条数
            asset_type: 资产类型（可选，如果不提供则使用默认值）

        Returns:
            K线数据DataFrame
        """
        self._ensure_initialized()

        try:
            # 如果没有提供asset_type，导入默认值
            if asset_type is None:
                from core.plugin_types import AssetType
                asset_type = AssetType.STOCK_A
            
            # 获取股票服务
            stock_service = self._get_stock_service()
            if not stock_service:
                logger.error("Stock service not available for get_kdata")
                return pd.DataFrame()

            # ✅ 委托给股票服务获取数据（传递asset_type）
            kdata = stock_service.get_kdata(stock_code, period, count, asset_type=asset_type)
            if kdata is not None:
                return kdata
            else:
                logger.warning(f"No kdata available for {stock_code} ({asset_type.value if asset_type else 'unknown'})")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Failed to get kdata for {stock_code}: {e}")
            return pd.DataFrame()

    async def get_kdata_async(self, stock_code: str, period: str = 'D', count: int = 365,
                             asset_type: 'AssetType' = None) -> pd.DataFrame:
        """
        获取K线数据（异步版本 - 优化版）

        Args:
            stock_code: 股票代码（或其他资产代码）
            period: 周期
            count: 数据条数
            asset_type: 资产类型（可选，如果不提供则使用默认值）

        Returns:
            K线数据DataFrame
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.get_kdata(stock_code, period, count, asset_type)
        )
