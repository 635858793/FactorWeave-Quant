"""
插件中心

统一插件管理中心，负责插件的发现、注册、管理和监控。
专注于数据源插件的统一管理，提供插件能力映射和性能指标收集。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger
from core.plugin_types import AssetType, DataType, PluginType
from core.data_source_extensions import PluginInfo, HealthCheckResult
from core.enums import PluginStatus
from plugins.plugin_interface import IDataSourcePlugin

logger = logger.bind(module=__name__)


@dataclass
class PluginMetrics:
    """插件性能指标"""
    plugin_id: str
    total_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    quality_score: float = 1.0
    availability_score: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PluginCapability:
    """插件能力定义"""
    plugin_id: str
    supported_asset_types: List[AssetType]
    supported_data_types: List[DataType]
    supported_markets: List[str]
    priority: int = 50
    quality_rating: float = 1.0
    reliability_rating: float = 1.0


class PluginCenter:
    """
    插件中心 - 统一插件管理

    基于现有PluginManager增强，专注于数据源插件的统一管理，
    提供插件发现、注册、能力映射、性能监控等功能。
    """

    def __init__(self, plugin_manager):
        """
        初始化插件中心

        Args:
            plugin_manager: 现有的插件管理器实例
        """
        self.plugin_manager = plugin_manager
        self.data_source_plugins: Dict[str, Any] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self.plugin_health: Dict[str, HealthCheckResult] = {}
        self.plugin_metrics: Dict[str, PluginMetrics] = {}
        self.plugin_capabilities: Dict[str, PluginCapability] = {}
        self.plugin_status: Dict[str, PluginStatus] = {}

        # 插件能力索引 - 快速查找
        self._capability_index: Dict[Tuple[DataType, AssetType], List[str]] = {}
        self._market_index: Dict[str, List[str]] = {}

        # 线程安全
        self._lock = threading.RLock()

        # 健康检查配置
        self.health_check_interval = 300  # 5分钟
        self.last_health_check = datetime.now()

        logger.info("插件中心初始化完成")

    def discover_and_register_plugins(self) -> Dict[str, str]:
        """
        发现并注册所有数据源插件 - 增强版

        Returns:
            Dict[str, str]: 注册结果 {plugin_id: status}
        """
        registration_results = {}

        try:
            with self._lock:
                # 1. 获取所有已加载的插件
                all_plugins = self.plugin_manager.get_all_plugins()

                logger.info(f"开始插件发现和注册，共发现 {len(all_plugins)} 个插件")

                # 2. 筛选数据源插件 - 增强筛选逻辑
                for plugin_name, plugin_instance in all_plugins.items():
                    try:
                        if self._is_data_source_plugin(plugin_instance):
                            result = self._register_data_source_plugin(plugin_name, plugin_instance)
                            registration_results[plugin_name] = "success" if result else "failed"

                            # 增强：自动配置插件优先级
                            if result:
                                self._auto_configure_plugin_priority(plugin_name, plugin_instance)
                        else:
                            registration_results[plugin_name] = "skipped_not_data_source"

                    except Exception as e:
                        logger.error(f"注册插件失败 {plugin_name}: {e}")
                        registration_results[plugin_name] = f"error: {str(e)}"

                # 3. 构建能力索引 - 增强索引构建
                self._build_capability_indexes()

                # 4. 构建性能基准索引
                self._build_performance_baseline()

                # 5. 执行初始健康检查 - 增强健康检查
                self._perform_initial_health_check()

                # 6. 启动后台监控任务
                self._start_background_monitoring()

                logger.info(f"插件发现和注册完成，成功注册 {len(self.data_source_plugins)} 个数据源插件")

        except Exception as e:
            logger.error(f"插件发现和注册过程异常: {e}")

        return registration_results

    def _is_data_source_plugin(self, plugin_instance) -> bool:
        """检查是否为数据源插件"""
        # 方法1: 检查是否实现了IDataSourcePlugin接口
        if isinstance(plugin_instance, IDataSourcePlugin):
            return True

        # 方法2: 检查是否有数据源插件的核心方法（兼容现有插件）
        required_methods = ['get_supported_data_types', 'fetch_data']
        has_required_methods = all(hasattr(plugin_instance, method) for method in required_methods)

        if has_required_methods:
            return True

        # 方法3: 检查插件信息中的类型（支持PluginInfo结构）
        if hasattr(plugin_instance, 'plugin_info'):
            plugin_info = plugin_instance.plugin_info
            if hasattr(plugin_info, 'plugin_type'):
                return plugin_info.plugin_type == PluginType.DATA_SOURCE
            # 检查是否包含数据源相关的数据类型
            if hasattr(plugin_info, 'supported_data_types') and plugin_info.supported_data_types:
                return True

        # 方法4: 检查类名或模块名是否包含数据源标识
        class_name = plugin_instance.__class__.__name__.lower()
        module_name = plugin_instance.__class__.__module__.lower()

        data_source_indicators = [
            'datasource', 'data_source', 'dataplugin', 'data_plugin',
            'stockplugin', 'cryptoplugin', 'financeplugin'
        ]

        for indicator in data_source_indicators:
            if indicator in class_name or indicator in module_name:
                return True

        return False

    def _register_data_source_plugin(self, plugin_id: str, plugin: Any) -> bool:
        """注册数据源插件"""
        try:
            # 存储插件实例
            self.data_source_plugins[plugin_id] = plugin

            # 初始化插件指标
            self.plugin_metrics[plugin_id] = PluginMetrics(plugin_id=plugin_id)

            # 初始化插件状态
            self.plugin_status[plugin_id] = PluginStatus.ACTIVE

            # 获取插件配置
            self.plugin_configs[plugin_id] = self._extract_plugin_config(plugin)

            # 分析插件能力
            capability = self._analyze_plugin_capability(plugin_id, plugin)
            self.plugin_capabilities[plugin_id] = capability

            logger.info(f"数据源插件注册成功: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"注册数据源插件失败 {plugin_id}: {e}")
            return False

    def _extract_plugin_config(self, plugin: Any) -> Dict[str, Any]:
        """提取插件配置"""
        config = {}

        # 优先使用 get_plugin_info() 方法
        if hasattr(plugin, 'get_plugin_info'):
            try:
                # 获取插件标识信息用于调试
                plugin_class_name = plugin.__class__.__name__ if hasattr(plugin, '__class__') else 'Unknown'
                plugin_module = plugin.__module__ if hasattr(plugin, '__module__') else 'Unknown'
                logger.debug(f"正在调用插件 {plugin_class_name} ({plugin_module}) 的get_plugin_info方法")
                plugin_info = plugin.get_plugin_info()
                # 安全地获取插件信息，处理可能缺失的capabilities参数
                if hasattr(plugin_info, 'name'):
                    config['name'] = plugin_info.name
                else:
                    config['name'] = getattr(plugin_info, 'name', 'Unknown')

                config['version'] = getattr(plugin_info, 'version', '1.0')
                config['description'] = getattr(plugin_info, 'description', '')
                config['author'] = getattr(plugin_info, 'author', '')

                # 处理capabilities参数，如果不存在则提供默认值
                if hasattr(plugin_info, 'capabilities'):
                    config['capabilities'] = plugin_info.capabilities
                else:
                    # 提供默认的capabilities
                    config['capabilities'] = {
                        'data_types': getattr(plugin_info, 'supported_data_types', []),
                        'asset_types': getattr(plugin_info, 'supported_asset_types', []),
                        'features': []
                    }
                    logger.debug(f"为插件 {config['name']} 提供默认capabilities")

            except Exception as e:
                logger.warning(f"调用插件 {plugin_class_name} ({plugin_module}) 的get_plugin_info失败: {e}")
                import traceback
                logger.debug(f"详细错误信息: {traceback.format_exc()}")
                # 提供基本的默认配置
                config.update({
                    'name': 'Unknown Plugin',
                    'version': '1.0',
                    'description': '',
                    'author': '',
                    'capabilities': {'data_types': [], 'asset_types': [], 'features': []}
                })
        # 备用：使用 plugin_info 属性
        elif hasattr(plugin, 'plugin_info'):
            plugin_info = plugin.plugin_info
            config['name'] = getattr(plugin_info, 'name', 'Unknown')
            config['version'] = getattr(plugin_info, 'version', '1.0')
            config['description'] = getattr(plugin_info, 'description', '')
            config['author'] = getattr(plugin_info, 'author', '')

            # 处理capabilities参数
            if hasattr(plugin_info, 'capabilities'):
                config['capabilities'] = plugin_info.capabilities
            else:
                config['capabilities'] = {
                    'data_types': getattr(plugin_info, 'supported_data_types', []),
                    'asset_types': getattr(plugin_info, 'supported_asset_types', []),
                    'features': []
                }

        # 获取支持的数据类型
        if hasattr(plugin, 'get_supported_data_types'):
            try:
                config['supported_data_types'] = plugin.get_supported_data_types()
            except Exception as e:
                logger.warning(f"获取插件支持的数据类型失败: {e}")
                config['supported_data_types'] = []

        # 获取数据源名称
        if hasattr(plugin, 'get_data_source_name'):
            try:
                config['data_source_name'] = plugin.get_data_source_name()
            except Exception as e:
                logger.warning(f"获取数据源名称失败: {e}")
                config['data_source_name'] = 'Unknown'

        # 确保capabilities字段存在
        if 'capabilities' not in config:
            config['capabilities'] = {
                'data_types': config.get('supported_data_types', []),
                'asset_types': config.get('supported_asset_types', []),
                'features': []
            }
            logger.debug(f"为插件 {config.get('name', 'Unknown')} 添加默认capabilities")

        return config

    def _analyze_plugin_capability(self, plugin_id: str, plugin: Any) -> PluginCapability:
        """分析插件能力"""
        supported_asset_types = []
        supported_data_types = []
        supported_markets = []

        # 从插件配置中获取支持的数据类型
        config = self.plugin_configs.get(plugin_id, {})
        data_types = config.get('supported_data_types', [])

        # 转换为DataType枚举
        for data_type in data_types:
            try:
                if isinstance(data_type, str):
                    # 尝试映射字符串到DataType枚举
                    dt = self._map_string_to_data_type(data_type)
                    if dt:
                        supported_data_types.append(dt)
                elif isinstance(data_type, DataType):
                    supported_data_types.append(data_type)
            except Exception as e:
                logger.warning(f"转换数据类型失败 {data_type}: {e}")

        # 根据插件名称推断支持的资产类型和市场
        plugin_name = plugin_id.lower()
        if 'stock' in plugin_name or 'tongdaxin' in plugin_name or 'eastmoney' in plugin_name:
            supported_asset_types.append(AssetType.STOCK_A)
            supported_markets.extend(['SH', 'SZ'])
        elif 'crypto' in plugin_name or 'binance' in plugin_name or 'okx' in plugin_name:
            supported_asset_types.append(AssetType.CRYPTO)
            supported_markets.extend(['BINANCE', 'OKX', 'HUOBI'])
        elif 'future' in plugin_name or 'ctp' in plugin_name:
            supported_asset_types.append(AssetType.FUTURES)
            supported_markets.extend(['CFFEX', 'DCE', 'SHFE', 'CZCE'])
        elif 'bond' in plugin_name:
            supported_asset_types.append(AssetType.BOND)
            supported_markets.extend(['IB', 'SH', 'SZ'])
        elif 'forex' in plugin_name:
            supported_asset_types.append(AssetType.FOREX)
            supported_markets.extend(['FOREX'])
        else:
            # 默认支持股票
            supported_asset_types.append(AssetType.STOCK_A)
            supported_markets.extend(['SH', 'SZ'])

        return PluginCapability(
            plugin_id=plugin_id,
            supported_asset_types=supported_asset_types,
            supported_data_types=supported_data_types,
            supported_markets=supported_markets,
            priority=50,
            quality_rating=1.0,
            reliability_rating=1.0
        )

    def _map_string_to_data_type(self, data_type_str: str) -> Optional[DataType]:
        """将字符串映射到 DataType 枚举"""
        mapping = {
            # 英文映射
            'historical_kline': DataType.HISTORICAL_KLINE,
            'kline': DataType.HISTORICAL_KLINE,
            'real_time_quote': DataType.REAL_TIME_QUOTE,
            'realtime': DataType.REAL_TIME_QUOTE,
            'fundamental': DataType.FUNDAMENTAL,
            'stock_list': DataType.ASSET_LIST,
            'asset_list': DataType.ASSET_LIST,
            'sector_fund_flow': DataType.SECTOR_FUND_FLOW,
            'stock_daily': DataType.HISTORICAL_KLINE,
            'stock_intraday': DataType.HISTORICAL_KLINE,
            'stock_info': DataType.FUNDAMENTAL,
            
            # 中文映射（UI 显示名）
            'K 线数据': DataType.HISTORICAL_KLINE,
            '实时行情': DataType.REAL_TIME_QUOTE,
            '基本面数据': DataType.FUNDAMENTAL,
            '资产列表': DataType.ASSET_LIST,
            '板块资金流': DataType.SECTOR_FUND_FLOW,
            '盘口深度': DataType.MARKET_DEPTH,
            '逐笔成交': DataType.TRADE_TICK,
            'Tick 数据': DataType.TICK_DATA,
            '委托账本': DataType.ORDER_BOOK,
            'Level2 数据': DataType.LEVEL2_DATA,
            '新闻数据': DataType.NEWS,
            '公告数据': DataType.ANNOUNCEMENT,
            '资金流数据': DataType.FUND_FLOW,
            '个股资金流': DataType.INDIVIDUAL_FUND_FLOW,
            '主力资金流': DataType.MAIN_FUND_FLOW,
            '板块数据': DataType.SECTOR_DATA,
            '技术指标': DataType.TECHNICAL_INDICATORS,
            '分时数据': DataType.INTRADAY_DATA,
            '股票基本信息': DataType.STOCK_BASIC_INFO,
        }
        
        # 处理大小写：英文转小写，中文保持原样
        if data_type_str and data_type_str.isascii():
            return mapping.get(data_type_str.lower())
        else:
            return mapping.get(data_type_str)

    def _build_capability_indexes(self) -> None:
        """构建能力索引"""
        self._capability_index.clear()
        self._market_index.clear()

        for plugin_id, capability in self.plugin_capabilities.items():
            # 构建数据类型-资产类型索引
            for data_type in capability.supported_data_types:
                for asset_type in capability.supported_asset_types:
                    key = (data_type, asset_type)
                    if key not in self._capability_index:
                        self._capability_index[key] = []
                    self._capability_index[key].append(plugin_id)

            # 构建市场索引
            for market in capability.supported_markets:
                if market not in self._market_index:
                    self._market_index[market] = []
                self._market_index[market].append(plugin_id)

        logger.debug(f"构建能力索引完成，数据类型-资产类型索引: {len(self._capability_index)} 项，市场索引: {len(self._market_index)} 项")

    def _perform_initial_health_check(self) -> None:
        """执行初始健康检查"""
        for plugin_id, plugin in self.data_source_plugins.items():
            try:
                if hasattr(plugin, 'test_connection'):
                    is_healthy = plugin.test_connection()

                    self.plugin_health[plugin_id] = HealthCheckResult(
                        is_healthy=is_healthy,
                        message="" if is_healthy else "Connection test failed",
                        response_time=0.0,
                        timestamp=datetime.now()
                    )

                    if not is_healthy:
                        self.plugin_status[plugin_id] = PluginStatus.ERROR
                        logger.warning(f"插件 {plugin_id} 初始健康检查失败")
                    else:
                        logger.debug(f"插件 {plugin_id} 初始健康检查通过")

            except Exception as e:
                logger.error(f"插件 {plugin_id} 健康检查异常: {e}")
                self.plugin_status[plugin_id] = PluginStatus.ERROR

    def get_available_plugins(self, data_type: DataType, asset_type: AssetType,
                              market: Optional[str] = None) -> List[str]:
        """
        获取可用插件列表

        Args:
            data_type: 数据类型
            asset_type: 资产类型
            market: 市场（可选）

        Returns:
            List[str]: 可用插件ID列表
        """
        available_plugins = []

        try:
            with self._lock:
                # 从能力索引中查找支持该数据类型和资产类型的插件
                key = (data_type, asset_type)
                candidate_plugins = self._capability_index.get(key, [])

                # 如果指定了市场，进一步过滤
                if market and market in self._market_index:
                    market_plugins = set(self._market_index[market])
                    candidate_plugins = [p for p in candidate_plugins if p in market_plugins]

                # 过滤掉不可用的插件
                for plugin_id in candidate_plugins:
                    if self._is_plugin_available(plugin_id):
                        available_plugins.append(plugin_id)

                logger.debug(f"查找可用插件: {data_type.value}/{asset_type.value}/{market} -> {len(available_plugins)} 个")

        except Exception as e:
            logger.error(f"获取可用插件列表失败: {e}")

        return available_plugins

    def _is_plugin_available(self, plugin_id: str) -> bool:
        """检查插件是否可用"""
        # 检查插件状态
        status = self.plugin_status.get(plugin_id, PluginStatus.UNKNOWN)
        if status in [PluginStatus.DISABLED, PluginStatus.ERROR]:
            return False

        # 检查健康状态
        health = self.plugin_health.get(plugin_id)
        if health and not health.is_healthy:
            # 如果健康检查较久，可能需要重新检查
            time_since_check = datetime.now() - health.timestamp
            if time_since_check.total_seconds() > self.health_check_interval:
                return True  # 给机会重新检查
            return False

        return True

    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        """
        获取插件实例

        Args:
            plugin_id: 插件ID

        Returns:
            Optional[IDataSourcePlugin]: 插件实例
        """
        return self.data_source_plugins.get(plugin_id)

    def update_plugin_metrics(self, plugin_id: str, success: bool,
                              response_time: float, quality_score: float = 1.0) -> None:
        """
        更新插件指标

        Args:
            plugin_id: 插件ID
            success: 请求是否成功
            response_time: 响应时间
            quality_score: 质量分数
        """
        try:
            with self._lock:
                if plugin_id not in self.plugin_metrics:
                    self.plugin_metrics[plugin_id] = PluginMetrics(plugin_id=plugin_id)

                metrics = self.plugin_metrics[plugin_id]
                metrics.total_requests += 1
                metrics.updated_at = datetime.now()

                if success:
                    metrics.success_requests += 1
                    metrics.last_success_time = datetime.now()
                else:
                    metrics.failed_requests += 1
                    metrics.last_failure_time = datetime.now()

                # 更新平均响应时间
                if response_time > 0:
                    current_avg = metrics.avg_response_time
                    total_requests = metrics.total_requests
                    metrics.avg_response_time = (current_avg * (total_requests - 1) + response_time) / total_requests

                # 更新质量分数（使用指数移动平均）
                alpha = 0.1  # 平滑因子
                metrics.quality_score = alpha * quality_score + (1 - alpha) * metrics.quality_score

                # 更新可用性分数
                if metrics.total_requests > 0:
                    availability = metrics.success_requests / metrics.total_requests
                    metrics.availability_score = availability

                logger.debug(f"更新插件指标: {plugin_id}, 成功: {success}, 响应时间: {response_time:.3f}s")

        except Exception as e:
            logger.error(f"更新插件指标失败 {plugin_id}: {e}")

    def get_plugin_metrics(self, plugin_id: str) -> Optional[PluginMetrics]:
        """
        获取插件指标

        Args:
            plugin_id: 插件ID

        Returns:
            Optional[PluginMetrics]: 插件指标
        """
        return self.plugin_metrics.get(plugin_id)

    def get_all_plugin_metrics(self) -> Dict[str, PluginMetrics]:
        """
        获取所有插件指标

        Returns:
            Dict[str, PluginMetrics]: 所有插件指标
        """
        return self.plugin_metrics.copy()

    def perform_health_check(self, plugin_id: Optional[str] = None) -> Dict[str, HealthCheckResult]:
        """
        执行健康检查

        Args:
            plugin_id: 指定插件ID，None表示检查所有插件

        Returns:
            Dict[str, HealthCheckResult]: 健康检查结果
        """
        results = {}

        plugins_to_check = [plugin_id] if plugin_id else list(self.data_source_plugins.keys())

        for pid in plugins_to_check:
            if pid in self.data_source_plugins:
                try:
                    plugin = self.data_source_plugins[pid]
                    start_time = datetime.now()

                    if hasattr(plugin, 'test_connection'):
                        is_healthy = plugin.test_connection()
                    else:
                        is_healthy = True  # 假设健康

                    response_time = (datetime.now() - start_time).total_seconds()

                    result = HealthCheckResult(
                        is_healthy=is_healthy,
                        message="" if is_healthy else "Health check failed",
                        response_time=response_time,
                        timestamp=datetime.now()
                    )

                    self.plugin_health[pid] = result
                    results[pid] = result

                    # 更新插件状态
                    if is_healthy:
                        self.plugin_status[pid] = PluginStatus.ACTIVE
                    else:
                        self.plugin_status[pid] = PluginStatus.ERROR

                except Exception as e:
                    result = HealthCheckResult(
                        is_healthy=False,
                        message=str(e),
                        response_time=0.0,
                        timestamp=datetime.now()
                    )

                    self.plugin_health[pid] = result
                    results[pid] = result
                    self.plugin_status[pid] = PluginStatus.ERROR

                    logger.error(f"插件 {pid} 健康检查异常: {e}")

        self.last_health_check = datetime.now()
        return results

    def get_plugin_info(self, plugin_id: str) -> Dict[str, Any]:
        """
        获取插件信息

        Args:
            plugin_id: 插件ID

        Returns:
            Dict[str, Any]: 插件信息
        """
        info = {
            'plugin_id': plugin_id,
            'exists': plugin_id in self.data_source_plugins
        }

        if plugin_id in self.data_source_plugins:
            info.update({
                'config': self.plugin_configs.get(plugin_id, {}),
                'capability': self.plugin_capabilities.get(plugin_id),
                'metrics': self.plugin_metrics.get(plugin_id),
                'health': self.plugin_health.get(plugin_id),
                'status': self.plugin_status.get(plugin_id)
            })

        return info

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取插件中心统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        total_plugins = len(self.data_source_plugins)
        active_plugins = sum(1 for status in self.plugin_status.values()
                             if status == PluginStatus.ACTIVE)
        error_plugins = sum(1 for status in self.plugin_status.values()
                            if status == PluginStatus.ERROR)

        total_requests = sum(metrics.total_requests for metrics in self.plugin_metrics.values())
        total_success = sum(metrics.success_requests for metrics in self.plugin_metrics.values())

        return {
            'total_plugins': total_plugins,
            'active_plugins': active_plugins,
            'error_plugins': error_plugins,
            'disabled_plugins': total_plugins - active_plugins - error_plugins,
            'total_requests': total_requests,
            'total_success': total_success,
            'success_rate': total_success / total_requests if total_requests > 0 else 0.0,
            'capability_index_size': len(self._capability_index),
            'market_index_size': len(self._market_index),
            'last_health_check': self.last_health_check
        }

    # ==================== 新增增强功能 ====================

    def _auto_configure_plugin_priority(self, plugin_id: str, plugin_instance) -> None:
        """
        自动配置插件优先级

        Args:
            plugin_id: 插件ID
            plugin_instance: 插件实例
        """
        try:
            capability = self.plugin_capabilities.get(plugin_id)
            if not capability:
                return

            # 基于插件特性自动设置优先级
            priority = 50  # 默认优先级

            # 根据插件名称调整优先级
            plugin_name = plugin_id.lower()
            if 'tongdaxin' in plugin_name:
                priority = 10  # 通达信优先级最高
            elif 'eastmoney' in plugin_name:
                priority = 20  # 东方财富次之
            elif 'akshare' in plugin_name:
                priority = 30  # AKShare第三
            elif 'tushare' in plugin_name:
                priority = 40  # Tushare第四
            elif 'yahoo' in plugin_name or 'yfinance' in plugin_name:
                priority = 60  # 国外数据源优先级较低
            elif 'test' in plugin_name or 'mock' in plugin_name:
                priority = 90  # 测试插件优先级最低

            # 根据支持的数据类型调整优先级
            if DataType.HISTORICAL_KLINE in capability.supported_data_types:
                priority -= 5  # 支持K线数据的插件优先级提升
            if DataType.REAL_TIME_QUOTE in capability.supported_data_types:
                priority -= 3  # 支持实时行情的插件优先级提升

            # 更新插件能力中的优先级
            capability.priority = priority

            logger.debug(f"自动配置插件优先级: {plugin_id} -> {priority}")

        except Exception as e:
            logger.error(f"自动配置插件优先级失败 {plugin_id}: {e}")

    def _build_performance_baseline(self) -> None:
        """构建性能基准索引"""
        try:
            # 为每个插件建立性能基准
            for plugin_id in self.data_source_plugins.keys():
                if plugin_id not in self.plugin_metrics:
                    continue

                metrics = self.plugin_metrics[plugin_id]

                # 设置初始性能基准
                baseline = {
                    'expected_response_time': 2.0,  # 期望响应时间2秒
                    'min_success_rate': 0.95,       # 最低成功率95%
                    'max_error_rate': 0.05,         # 最大错误率5%
                    'performance_grade': 'A'        # 性能等级
                }

                # 根据插件类型调整基准
                capability = self.plugin_capabilities.get(plugin_id)
                if capability:
                    if DataType.REAL_TIME_QUOTE in capability.supported_data_types:
                        baseline['expected_response_time'] = 1.0  # 实时数据要求更快
                        baseline['min_success_rate'] = 0.98
                    elif DataType.HISTORICAL_KLINE in capability.supported_data_types:
                        baseline['expected_response_time'] = 3.0  # 历史数据可以稍慢
                        baseline['min_success_rate'] = 0.90

                # 存储基准到插件指标中
                metrics.performance_baseline = baseline

            logger.info("性能基准索引构建完成")

        except Exception as e:
            logger.error(f"构建性能基准索引失败: {e}")

    def _start_background_monitoring(self) -> None:
        """启动后台监控任务"""
        try:
            # 这里可以启动定期的后台任务
            # 例如：定期健康检查、性能优化、指标收集等
            logger.info("后台监控任务启动完成")

            # 设置定期优化任务（这里只是标记，实际实现可能需要定时器）
            self._schedule_periodic_optimization()

        except Exception as e:
            logger.error(f"启动后台监控任务失败: {e}")

    def _schedule_periodic_optimization(self) -> None:
        """安排定期优化任务"""
        # 这里可以实现定期的插件性能优化
        # 例如：调整插件优先级、清理过期缓存、优化路由策略等
        pass

    def register_plugin_dynamically(self, plugin_id: str, plugin_instance) -> bool:
        """
        动态注册插件

        Args:
            plugin_id: 插件ID
            plugin_instance: 插件实例

        Returns:
            bool: 注册是否成功
        """
        try:
            with self._lock:
                # 检查是否为数据源插件
                if not self._is_data_source_plugin(plugin_instance):
                    logger.warning(f"插件 {plugin_id} 不是数据源插件，无法动态注册")
                    return False

                # 注册插件
                result = self._register_data_source_plugin(plugin_id, plugin_instance)

                if result:
                    # 自动配置优先级
                    self._auto_configure_plugin_priority(plugin_id, plugin_instance)

                    # 重建索引
                    self._build_capability_indexes()

                    # 执行健康检查
                    self.perform_health_check(plugin_id)

                    logger.info(f"动态注册插件成功: {plugin_id}")
                else:
                    logger.error(f"动态注册插件失败: {plugin_id}")

                return result

        except Exception as e:
            logger.error(f"动态注册插件异常 {plugin_id}: {e}")
            return False

    def unregister_plugin_dynamically(self, plugin_id: str) -> bool:
        """
        动态注销插件

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 注销是否成功
        """
        try:
            with self._lock:
                if plugin_id not in self.data_source_plugins:
                    logger.warning(f"插件 {plugin_id} 不存在，无法注销")
                    return False

                # 移除插件相关数据
                del self.data_source_plugins[plugin_id]

                if plugin_id in self.plugin_configs:
                    del self.plugin_configs[plugin_id]

                if plugin_id in self.plugin_health:
                    del self.plugin_health[plugin_id]

                if plugin_id in self.plugin_metrics:
                    del self.plugin_metrics[plugin_id]

                if plugin_id in self.plugin_capabilities:
                    del self.plugin_capabilities[plugin_id]

                if plugin_id in self.plugin_status:
                    del self.plugin_status[plugin_id]

                # 重建索引
                self._build_capability_indexes()

                logger.info(f"动态注销插件成功: {plugin_id}")
                return True

        except Exception as e:
            logger.error(f"动态注销插件异常 {plugin_id}: {e}")
            return False

    def get_plugin_performance_report(self, plugin_id: str) -> Dict[str, Any]:
        """
        获取插件性能报告

        Args:
            plugin_id: 插件ID

        Returns:
            Dict[str, Any]: 性能报告
        """
        if plugin_id not in self.data_source_plugins:
            return {'error': f'插件 {plugin_id} 不存在'}

        try:
            metrics = self.plugin_metrics.get(plugin_id)
            health = self.plugin_health.get(plugin_id)
            capability = self.plugin_capabilities.get(plugin_id)
            status = self.plugin_status.get(plugin_id)

            report = {
                'plugin_id': plugin_id,
                'status': status.value if status else 'unknown',
                'performance_metrics': {
                    'total_requests': metrics.total_requests if metrics else 0,
                    'success_requests': metrics.success_requests if metrics else 0,
                    'failed_requests': metrics.failed_requests if metrics else 0,
                    'success_rate': (metrics.success_requests / max(metrics.total_requests, 1)) if metrics else 0.0,
                    'avg_response_time': metrics.avg_response_time if metrics else 0.0,
                    'quality_score': metrics.quality_score if metrics else 0.0,
                    'availability_score': metrics.availability_score if metrics else 0.0
                },
                'health_status': {
                    'is_healthy': health.is_healthy if health else False,
                    'last_check': health.timestamp if health else None,
                    'message': health.message if health else 'No health data'
                },
                'capabilities': {
                    'supported_asset_types': [at.value for at in capability.supported_asset_types] if capability else [],
                    'supported_data_types': [dt.value for dt in capability.supported_data_types] if capability else [],
                    'supported_markets': capability.supported_markets if capability else [],
                    'priority': capability.priority if capability else 50,
                    'quality_rating': capability.quality_rating if capability else 1.0,
                    'reliability_rating': capability.reliability_rating if capability else 1.0
                }
            }

            # 添加性能基准对比
            if metrics and hasattr(metrics, 'performance_baseline'):
                baseline = metrics.performance_baseline
                report['performance_analysis'] = {
                    'meets_response_time_target': metrics.avg_response_time <= baseline['expected_response_time'],
                    'meets_success_rate_target': (metrics.success_requests / max(metrics.total_requests, 1)) >= baseline['min_success_rate'],
                    'performance_grade': self._calculate_performance_grade(metrics, baseline)
                }

            return report

        except Exception as e:
            logger.error(f"获取插件性能报告失败 {plugin_id}: {e}")
            return {'error': f'获取性能报告失败: {str(e)}'}

    def _calculate_performance_grade(self, metrics: PluginMetrics, baseline: Dict[str, Any]) -> str:
        """计算插件性能等级"""
        try:
            success_rate = metrics.success_requests / max(metrics.total_requests, 1)
            response_time = metrics.avg_response_time

            # 计算得分
            score = 0

            # 成功率评分 (40%)
            if success_rate >= baseline['min_success_rate']:
                score += 40
            elif success_rate >= baseline['min_success_rate'] * 0.9:
                score += 30
            elif success_rate >= baseline['min_success_rate'] * 0.8:
                score += 20
            else:
                score += 10

            # 响应时间评分 (30%)
            if response_time <= baseline['expected_response_time']:
                score += 30
            elif response_time <= baseline['expected_response_time'] * 1.5:
                score += 20
            elif response_time <= baseline['expected_response_time'] * 2:
                score += 10
            else:
                score += 5

            # 质量分数评分 (20%)
            if metrics.quality_score >= 0.9:
                score += 20
            elif metrics.quality_score >= 0.8:
                score += 15
            elif metrics.quality_score >= 0.7:
                score += 10
            else:
                score += 5

            # 可用性评分 (10%)
            if metrics.availability_score >= 0.95:
                score += 10
            elif metrics.availability_score >= 0.9:
                score += 8
            elif metrics.availability_score >= 0.8:
                score += 5
            else:
                score += 2

            # 根据总分确定等级
            if score >= 90:
                return 'A+'
            elif score >= 80:
                return 'A'
            elif score >= 70:
                return 'B'
            elif score >= 60:
                return 'C'
            else:
                return 'D'

        except Exception as e:
            logger.error(f"计算性能等级失败: {e}")
            return 'Unknown'

    def get_capability_matrix(self) -> Dict[str, Any]:
        """
        获取插件能力矩阵

        Returns:
            Dict[str, Any]: 能力矩阵
        """
        try:
            matrix = {
                'asset_type_coverage': {},
                'data_type_coverage': {},
                'market_coverage': {},
                'capability_gaps': [],
                'redundancy_analysis': {}
            }

            # 分析资产类型覆盖
            for asset_type in AssetType:
                supporting_plugins = []
                for plugin_id, capability in self.plugin_capabilities.items():
                    if asset_type in capability.supported_asset_types:
                        supporting_plugins.append({
                            'plugin_id': plugin_id,
                            'priority': capability.priority,
                            'quality_rating': capability.quality_rating
                        })

                matrix['asset_type_coverage'][asset_type.value] = {
                    'plugin_count': len(supporting_plugins),
                    'plugins': sorted(supporting_plugins, key=lambda x: x['priority'])
                }

            # 分析数据类型覆盖
            for data_type in DataType:
                supporting_plugins = []
                for plugin_id, capability in self.plugin_capabilities.items():
                    if data_type in capability.supported_data_types:
                        supporting_plugins.append({
                            'plugin_id': plugin_id,
                            'priority': capability.priority,
                            'quality_rating': capability.quality_rating
                        })

                matrix['data_type_coverage'][data_type.value] = {
                    'plugin_count': len(supporting_plugins),
                    'plugins': sorted(supporting_plugins, key=lambda x: x['priority'])
                }

            # 分析市场覆盖
            all_markets = set()
            for capability in self.plugin_capabilities.values():
                all_markets.update(capability.supported_markets)

            for market in all_markets:
                supporting_plugins = []
                for plugin_id, capability in self.plugin_capabilities.items():
                    if market in capability.supported_markets:
                        supporting_plugins.append({
                            'plugin_id': plugin_id,
                            'priority': capability.priority,
                            'quality_rating': capability.quality_rating
                        })

                matrix['market_coverage'][market] = {
                    'plugin_count': len(supporting_plugins),
                    'plugins': sorted(supporting_plugins, key=lambda x: x['priority'])
                }

            # 识别能力缺口
            for asset_type in AssetType:
                for data_type in DataType:
                    key = (data_type, asset_type)
                    if key not in self._capability_index or not self._capability_index[key]:
                        matrix['capability_gaps'].append({
                            'asset_type': asset_type.value,
                            'data_type': data_type.value,
                            'severity': 'high' if data_type == DataType.HISTORICAL_KLINE else 'medium'
                        })

            # 冗余分析
            for key, plugins in self._capability_index.items():
                if len(plugins) > 1:
                    data_type, asset_type = key
                    matrix['redundancy_analysis'][f"{data_type.value}_{asset_type.value}"] = {
                        'plugin_count': len(plugins),
                        'plugins': plugins,
                        'redundancy_level': 'high' if len(plugins) > 3 else 'medium'
                    }

            return matrix

        except Exception as e:
            logger.error(f"获取能力矩阵失败: {e}")
            return {'error': f'获取能力矩阵失败: {str(e)}'}

    def optimize_plugin_configuration(self) -> Dict[str, Any]:
        """
        优化插件配置

        Returns:
            Dict[str, Any]: 优化结果
        """
        optimization_results = {
            'optimized_plugins': [],
            'recommendations': [],
            'performance_improvements': {}
        }

        try:
            with self._lock:
                for plugin_id, metrics in self.plugin_metrics.items():
                    if metrics.total_requests < 10:
                        continue  # 数据不足，跳过优化

                    capability = self.plugin_capabilities.get(plugin_id)
                    if not capability:
                        continue

                    # 基于性能数据调整插件配置
                    success_rate = metrics.success_requests / metrics.total_requests
                    avg_response_time = metrics.avg_response_time

                    optimizations = []

                    # 优化优先级
                    if success_rate > 0.95 and avg_response_time < 2.0:
                        # 高性能插件，提升优先级
                        if capability.priority > 10:
                            old_priority = capability.priority
                            capability.priority = max(10, capability.priority - 10)
                            optimizations.append(f"优先级从 {old_priority} 提升到 {capability.priority}")

                    elif success_rate < 0.8 or avg_response_time > 5.0:
                        # 低性能插件，降低优先级
                        if capability.priority < 80:
                            old_priority = capability.priority
                            capability.priority = min(80, capability.priority + 10)
                            optimizations.append(f"优先级从 {old_priority} 降低到 {capability.priority}")

                    # 优化质量评级
                    old_quality = capability.quality_rating
                    new_quality = min(1.0, max(0.1, success_rate * metrics.quality_score))
                    if abs(new_quality - old_quality) > 0.1:
                        capability.quality_rating = new_quality
                        optimizations.append(f"质量评级从 {old_quality:.2f} 调整到 {new_quality:.2f}")

                    # 优化可靠性评级
                    old_reliability = capability.reliability_rating
                    new_reliability = min(1.0, max(0.1, success_rate * metrics.availability_score))
                    if abs(new_reliability - old_reliability) > 0.1:
                        capability.reliability_rating = new_reliability
                        optimizations.append(f"可靠性评级从 {old_reliability:.2f} 调整到 {new_reliability:.2f}")

                    if optimizations:
                        optimization_results['optimized_plugins'].append({
                            'plugin_id': plugin_id,
                            'optimizations': optimizations
                        })

                # 重建索引以反映优化结果
                self._build_capability_indexes()

                # 生成优化建议
                self._generate_optimization_recommendations(optimization_results)

                logger.info(f"插件配置优化完成，优化了 {len(optimization_results['optimized_plugins'])} 个插件")

        except Exception as e:
            logger.error(f"插件配置优化失败: {e}")
            optimization_results['error'] = str(e)

        return optimization_results

    def _generate_optimization_recommendations(self, results: Dict[str, Any]) -> None:
        """生成优化建议"""
        try:
            recommendations = []

            # 分析能力缺口
            capability_matrix = self.get_capability_matrix()
            if 'capability_gaps' in capability_matrix:
                for gap in capability_matrix['capability_gaps']:
                    recommendations.append({
                        'type': 'capability_gap',
                        'priority': gap['severity'],
                        'description': f"缺少支持 {gap['asset_type']} 资产类型的 {gap['data_type']} 数据源插件",
                        'suggestion': "考虑添加相应的数据源插件或扩展现有插件的能力"
                    })

            # 分析性能问题
            for plugin_id, metrics in self.plugin_metrics.items():
                if metrics.total_requests > 10:
                    success_rate = metrics.success_requests / metrics.total_requests
                    if success_rate < 0.8:
                        recommendations.append({
                            'type': 'performance_issue',
                            'priority': 'high',
                            'plugin_id': plugin_id,
                            'description': f"插件 {plugin_id} 成功率过低 ({success_rate:.2%})",
                            'suggestion': "检查插件配置、网络连接或考虑替换插件"
                        })

                    if metrics.avg_response_time > 5.0:
                        recommendations.append({
                            'type': 'performance_issue',
                            'priority': 'medium',
                            'plugin_id': plugin_id,
                            'description': f"插件 {plugin_id} 响应时间过长 ({metrics.avg_response_time:.2f}s)",
                            'suggestion': "优化插件配置或考虑使用更快的替代插件"
                        })

            results['recommendations'] = recommendations

        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
