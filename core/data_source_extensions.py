from loguru import logger
"""
数据源插件扩展接口
为FactorWeave-Quant插件化提供标准化的数据源插件接口和适配器
"""

import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Import AssetType and DataType from plugin_types instead of redefining them
from .plugin_types import AssetType, DataType


@dataclass
class PluginInfo:
    """插件信息"""
    id: str
    name: str
    version: str
    description: str
    author: str
    supported_asset_types: List[AssetType]
    supported_data_types: List[DataType]
    capabilities: Dict[str, Any]
    chinese_name: Optional[str] = None  # 中文名称，用于更好的用户识别


@dataclass
class HealthCheckResult:
    """健康检查结果 - 统一版本，兼容所有参数"""
    is_healthy: bool
    message: str
    # 兼容两种时间参数命名
    response_time: float = 0.0              # 响应时间(毫秒) - 主要参数
    response_time_ms: Optional[float] = None  # 兼容参数
    # 兼容两种时间戳参数
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳 - 主要参数
    last_check_time: Optional[datetime] = None  # 兼容参数
    # 兼容健康评分参数（如 level2_realtime_plugin 传入 score=）
    score: Optional[float] = None                # 健康评分 0~1
    # 兼容不同的详细信息参数
    extra_info: Dict[str, Any] = field(default_factory=dict)  # 额外信息 - 主要参数
    details: Optional[Dict[str, Any]] = None    # 兼容参数
    # 其他可选参数
    status_code: int = 200                      # HTTP状态码
    error_message: Optional[str] = None         # 错误信息（兼容参数）

    def __post_init__(self):
        """后处理，统一参数"""
        # 统一响应时间
        if self.response_time_ms is not None:
            self.response_time = self.response_time_ms
        elif self.response_time_ms is None:
            self.response_time_ms = self.response_time

        # 统一时间戳
        if self.last_check_time is not None:
            self.timestamp = self.last_check_time
        elif self.last_check_time is None:
            self.last_check_time = self.timestamp

        # 统一详细信息
        if self.details is not None:
            self.extra_info.update(self.details)
        elif not self.details:
            self.details = self.extra_info

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'is_healthy': self.is_healthy,
            'message': self.message,
            'response_time': self.response_time,
            'response_time_ms': self.response_time_ms,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'score': self.score,
            'extra_info': self.extra_info,
            'details': self.details,
            'status_code': self.status_code,
            'error_message': self.error_message
        }


@dataclass
class ConnectionInfo:
    """连接信息"""
    is_connected: bool
    connection_time: Optional[datetime]
    last_activity: Optional[datetime]
    connection_params: Dict[str, Any]
    error_message: Optional[str] = None


class IDataSourcePlugin(ABC):
    """
    数据源插件接口

    为FactorWeave-Quant插件化提供标准化的数据源接口
    支持多资产类型、多数据类型、连接管理、健康检查等功能
    """

    @property
    @abstractmethod
    def plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        pass

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """
        连接数据源

        Args:
            **kwargs: 连接参数

        Returns:
            bool: 连接是否成功
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        断开数据源连接

        Returns:
            bool: 断开是否成功
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        检查连接状态

        Returns:
            bool: 是否已连接
        """
        pass

    @abstractmethod
    def get_connection_info(self) -> ConnectionInfo:
        """
        获取连接信息

        Returns:
            ConnectionInfo: 连接详细信息
        """
        pass

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """
        健康检查

        Returns:
            HealthCheckResult: 健康检查结果
        """
        pass

    @abstractmethod
    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """
        获取资产列表

        Args:
            asset_type: 资产类型
            market: 市场代码（可选）

        Returns:
            List[Dict[str, Any]]: 资产列表
        """
        pass

    @abstractmethod
    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易代码
            freq: 频率 (D/W/M/H/30m/15m/5m/1m)
            start_date: 开始日期
            end_date: 结束日期
            count: 数据条数

        Returns:
            pd.DataFrame: K线数据
        """
        pass

    @abstractmethod
    def get_real_time_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """
        获取实时行情

        Args:
            symbols: 交易代码列表

        Returns:
            pd.DataFrame: 实时行情数据
        """
        pass

    def get_tick_data(self, symbol: str, date: str = None) -> pd.DataFrame:
        """
        获取Tick数据（可选实现）

        Args:
            symbol: 交易代码
            date: 日期

        Returns:
            pd.DataFrame: Tick数据
        """
        return pd.DataFrame()

    def get_fundamental_data(self, symbol: str) -> Dict[str, Any]:
        """
        获取基本面数据（可选实现）

        Args:
            symbol: 交易代码

        Returns:
            Dict[str, Any]: 基本面数据
        """
        return {}

    def get_financial_reports(self, symbol: str, report_type: str = "annual") -> pd.DataFrame:
        """
        获取财务报表数据（可选实现）

        Args:
            symbol: 交易代码
            report_type: 报表类型 (annual/quarterly)

        Returns:
            pd.DataFrame: 财务报表数据
        """
        return pd.DataFrame()

    def search_symbols(self, keyword: str, asset_type: AssetType = None) -> List[Dict[str, Any]]:
        """
        搜索交易代码（可选实现）

        Args:
            keyword: 搜索关键词
            asset_type: 资产类型过滤

        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        return []

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取插件统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "last_request_time": None,
            "uptime": 0.0
        }

    def get_supported_frequencies(self) -> List[str]:
        """
        获取支持的频率列表

        Returns:
            List[str]: 支持的频率
        """
        return ["D", "W", "M"]

    def get_supported_markets(self) -> List[str]:
        """
        获取支持的市场列表

        Returns:
            List[str]: 支持的市场
        """
        return []

    def get_supported_adjustment_types(self) -> List[str]:
        """
        获取支持的复权类型列表

        Returns:
            List[str]: 支持的复权类型
                - 'qfq': 前复权
                - 'hfq': 后复权
                - 'none': 不复权
                - 'both': 前复权和后复权都支持
        """
        return ['none']

    def validate_symbol(self, symbol: str, asset_type: AssetType = None) -> bool:
        """
        验证交易代码是否有效

        Args:
            symbol: 交易代码
            asset_type: 资产类型

        Returns:
            bool: 是否有效
        """
        return True

    def normalize_symbol(self, symbol: str, asset_type: AssetType = None) -> str:
        """
        标准化交易代码

        Args:
            symbol: 原始交易代码
            asset_type: 资产类型

        Returns:
            str: 标准化后的交易代码
        """
        return symbol

    def get_config_schema(self) -> Dict[str, Any]:
        """
        获取配置模式

        Returns:
            Dict[str, Any]: 配置模式
        """
        return {}

    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证配置

        Args:
            config: 配置字典

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        return True, ""

    def update_config(self, config: Dict[str, Any]) -> bool:
        """
        更新配置

        Args:
            config: 新配置

        Returns:
            bool: 更新是否成功
        """
        return True


class DataSourcePluginAdapter:
    """
    数据源插件适配器

    将插件接口适配到现有的数据管理系统
    提供统一的访问接口和错误处理
    """

    def __init__(self, plugin: IDataSourcePlugin, plugin_id: str):
        """
        初始化适配器

        Args:
            plugin: 数据源插件实例
            plugin_id: 插件唯一标识
        """
        self.plugin = plugin
        self.plugin_id = plugin_id
        self._connection_info = None
        self._last_health_check = None
        self.logger = logger.bind(module=self.__class__.__name__)

    def connect(self, **kwargs) -> bool:
        """连接数据源"""
        try:
            result = self.plugin.connect(**kwargs)
            if result:
                self._connection_info = self.plugin.get_connection_info()
                self.logger.info(f"数据源插件连接成功: {self.plugin_id}")
            else:
                self.logger.error(f"数据源插件连接失败: {self.plugin_id}")
            return result
        except Exception as e:
            self.logger.error(f"数据源插件连接异常: {self.plugin_id} - {e}")
            return False

    def disconnect(self) -> bool:
        """断开连接"""
        try:
            result = self.plugin.disconnect()
            if result:
                self.logger.info(f"数据源插件断开连接: {self.plugin_id}")
            return result
        except Exception as e:
            self.logger.error(f"数据源插件断开连接异常: {self.plugin_id} - {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态（支持异步插件）"""
        try:
            # 优先使用新的 is_ready() 方法（异步插件）
            if hasattr(self.plugin, 'is_ready'):
                return self.plugin.is_ready()
            # 回退到旧的 is_connected() 方法
            elif hasattr(self.plugin, 'is_connected'):
                return self.plugin.is_connected()
            else:
                return False
        except Exception as e:
            self.logger.error(f"检查连接状态异常: {self.plugin_id} - {e}")
            return False

    def ensure_ready(self, timeout: float = 30.0) -> bool:
        """
        确保插件就绪（用于首次使用时）
        如果插件尚未连接，会等待连接完成

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            bool: 插件是否就绪
        """
        try:
            # 如果已就绪，立即返回
            if self.is_connected():
                return True

            # 如果插件支持异步等待，使用它
            if hasattr(self.plugin, 'wait_until_ready'):
                self.logger.info(f"等待插件就绪: {self.plugin_id} (最多{timeout}秒)...")
                return self.plugin.wait_until_ready(timeout=timeout)

            # 否则返回当前状态
            return self.is_connected()
        except Exception as e:
            self.logger.error(f"等待插件就绪异常: {self.plugin_id} - {e}")
            return False

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            # 检查插件是否有health_check方法
            if hasattr(self.plugin, 'health_check'):
                result = self.plugin.health_check()
                self._last_health_check = result
                return result
            else:
                # 如果插件没有health_check方法，执行基本的连接检查
                return self._basic_health_check()
        except Exception as e:
            self.logger.error(f"健康检查异常: {self.plugin_id} - {e}")
            return HealthCheckResult(
                is_healthy=False,
                status_code=500,
                message=f"健康检查异常: {str(e)}",
                response_time_ms=0.0,
                last_check_time=datetime.now()
            )

    def _basic_health_check(self) -> HealthCheckResult:
        """基本健康检查（用于没有实现health_check方法的插件）"""
        try:
            start_time = datetime.now()

            # 检查插件是否有test_connection方法
            if hasattr(self.plugin, 'test_connection'):
                is_healthy = self.plugin.test_connection()
                status_code = 200 if is_healthy else 503
                message = "连接正常" if is_healthy else "连接失败"
            else:
                # 如果没有test_connection方法，检查插件是否可用
                is_healthy = self.plugin is not None
                status_code = 200 if is_healthy else 503
                message = "插件可用" if is_healthy else "插件不可用"

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            return HealthCheckResult(
                is_healthy=is_healthy,
                status_code=status_code,
                message=message,
                response_time_ms=response_time,
                last_check_time=datetime.now()
            )
        except Exception as e:
            return HealthCheckResult(
                is_healthy=False,
                status_code=500,
                message=f"基本健康检查失败: {str(e)}",
                response_time_ms=0.0,
                last_check_time=datetime.now()
            )

    def get_stock_list(self, market: str = None) -> pd.DataFrame:
        """获取股票列表（兼容现有接口）"""
        try:
            asset_list = self.plugin.get_asset_list(AssetType.STOCK_A, market)
            return pd.DataFrame(asset_list)
        except Exception as e:
            self.logger.error(f"获取股票列表异常: {self.plugin_id} - {e}")
            return pd.DataFrame()

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        try:
            return self.plugin.get_asset_list(asset_type, market)
        except Exception as e:
            self.logger.error(f"获取资产列表异常: {self.plugin_id} - {e}")
            return []

    def get_kdata(self, symbol: str, freq: str = "D", start_date=None,
                  end_date=None, count: int = None,
                  asset_type: Optional[AssetType] = None) -> pd.DataFrame:
        """获取K线数据（R275 签名自适应）

        系统调用约定为 (symbol, freq, start_date, end_date, count)，
        但 BasePluginTemplate 系插件（crypto/wenhua/eastmoney_unified 等）
        使用 (interval/period, limit, datetime日期, asset_type) 签名。
        若直接位置透传会导致参数错位（如 count 被当作 asset_type、字符串日期
        传入 datetime 参数后 .timestamp()/.strftime() 崩溃）。此处按插件实际
        签名关键字转发并归一化参数名与日期类型，杜绝断链。
        """
        try:
            import inspect
            sig = inspect.signature(self.plugin.get_kdata)
            params = sig.parameters

            kwargs = {'symbol': symbol}

            # 周期参数名归一化：freq（标准）/ period / interval
            if 'freq' in params:
                kwargs['freq'] = freq
            elif 'period' in params:
                kwargs['period'] = freq
            elif 'interval' in params:
                kwargs['interval'] = freq

            # 数量参数名归一化：count（标准）/ limit
            if 'count' in params:
                kwargs['count'] = count
            elif 'limit' in params:
                kwargs['limit'] = count or 500

            # 日期类型归一化：仅当插件声明 datetime 类型注解时，将系统 str('YYYYMMDD') 转为
            # datetime（标准插件如东财/baostock 声明 str，原样透传，避免破坏其 beg/end 拼接）
            if 'start_date' in params:
                kwargs['start_date'] = self._normalize_date(
                    start_date, params['start_date'].annotation)
            if 'end_date' in params:
                kwargs['end_date'] = self._normalize_date(
                    end_date, params['end_date'].annotation)

            # 资产类型透传（EastmoneyUnifiedPlugin 依赖，防止 count 错位为 asset_type
            # 导致 _format_symbol 退化为默认上海市场，深市/北市代码格式错误）
            if 'asset_type' in params and asset_type is not None:
                kwargs['asset_type'] = asset_type

            return self.plugin.get_kdata(**kwargs)
        except Exception as e:
            self.logger.error(f"获取K线数据异常: {self.plugin_id} - {e}")
            return pd.DataFrame()

    @staticmethod
    def _normalize_date(value, param_annotation=datetime):
        """将系统 str('YYYYMMDD'/'YYYY-MM-DD') 转为 datetime；None/datetime 原样返回。

        仅当插件参数声明为 datetime 类型（含 Optional[datetime]/Union[datetime, None]，
        如 BasePluginTemplate 系插件）时转换，标准插件声明 str 则原样透传。
        """
        if value is None or isinstance(value, datetime):
            return value
        if not _is_datetime_annotation(param_annotation):
            return value
        s = str(value).replace('-', '').replace('/', '')
        if len(s) == 8 and s.isdigit():
            return datetime.strptime(s, '%Y%m%d')
        return value

    def get_real_time_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情"""
        try:
            return self.plugin.get_real_time_quotes(symbols)
        except Exception as e:
            self.logger.error(f"获取实时行情异常: {self.plugin_id} - {e}")
            return pd.DataFrame()

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return self.plugin.plugin_info

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            return self.plugin.get_statistics()
        except Exception as e:
            self.logger.error(f"获取统计信息异常: {self.plugin_id} - {e}")
            return {}


def _is_datetime_annotation(param_annotation) -> bool:
    """判断插件参数注解是否为 datetime 类型（支持 Optional[datetime]/Union[datetime, None]）"""
    if param_annotation is datetime:
        return True
    if isinstance(param_annotation, str):
        return 'datetime' in param_annotation and 'date' != param_annotation
    try:
        import typing
        args = typing.get_args(param_annotation)
        if args:
            return any(a is datetime for a in args)
    except Exception:
        pass
    return False


def validate_plugin_interface(plugin_instance) -> bool:
    """
    验证插件是否实现了必要的接口

    Args:
        plugin_instance: 插件实例

    Returns:
        bool: 是否符合接口要求
    """
    # 分离plugin_info检查和其他方法检查
    required_methods = [
        'connect', 'disconnect', 'is_connected',
        'get_connection_info', 'health_check', 'get_asset_list',
        'get_kdata', 'get_real_time_quotes'
    ]

    # 检查plugin_info属性（可以是属性或方法）
    if not hasattr(plugin_instance, 'plugin_info'):
        logger.error("数据源插件缺少plugin_info属性")
        return False

    plugin_info = getattr(plugin_instance, 'plugin_info')
    # plugin_info可以是属性(@property)或方法
    if callable(plugin_info):
        # 如果是方法，尝试调用
        try:
            info_result = plugin_info()
            if not info_result:
                logger.error("数据源插件plugin_info方法返回空值")
                return False
        except Exception as e:
            logger.error(f"数据源插件plugin_info方法调用失败: {e}")
            return False
    else:
        # 如果是属性，检查是否为有效对象
        if not plugin_info:
            logger.error("数据源插件plugin_info属性为空")
            return False

    # 检查必要方法
    for method_name in required_methods:
        if not hasattr(plugin_instance, method_name):
            logger.error(f"插件缺少必要方法: {method_name}")
            return False

        method = getattr(plugin_instance, method_name)
        if not callable(method):
            logger.error(f"插件方法不可调用: {method_name}")
            return False

    return True


def create_plugin_adapter(plugin_instance, plugin_id: str) -> Optional[DataSourcePluginAdapter]:
    """
    创建插件适配器

    Args:
        plugin_instance: 插件实例
        plugin_id: 插件标识

    Returns:
        Optional[DataSourcePluginAdapter]: 适配器实例或None
    """
    if not validate_plugin_interface(plugin_instance):
        logger.error(f"插件接口验证失败: {plugin_id}")
        return None

    try:
        adapter = DataSourcePluginAdapter(plugin_instance, plugin_id)
        logger.info(f"插件适配器创建成功: {plugin_id}")
        return adapter
    except Exception as e:
        logger.error(f"创建插件适配器失败: {plugin_id} - {e}")
        return None
