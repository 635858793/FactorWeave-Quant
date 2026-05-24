#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare数据源插件

基于AKShare库提供板块资金流数据，支持：
- 板块资金流排行
- 主力资金净流入数据
- 超大单、大单、中单、小单资金流数据

使用akshare库作为数据源：
- 支持概念板块和行业板块
- 实时数据更新
- 丰富的资金流指标

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2024
"""

import time
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd

from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from core.plugin_types import PluginType, AssetType, DataType
from plugins.plugin_interface import PluginLifecycle
from plugins.data_sources.utils.retry_helper import retry_on_connection_error, log_execution_time
from loguru import logger

# 检查akshare库
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True

    # 应用反爬虫补丁（自动为所有AKShare请求添加浏览器请求头）
    try:
        from plugins.data_sources.utils.akshare_wrapper import patch_akshare_headers
        if patch_akshare_headers():
            logger.info("AKShare反爬虫补丁已激活")
    except Exception as patch_error:
        logger.warning(f"AKShare反爬虫补丁应用失败（将使用默认配置）: {patch_error}")

    AKSHARE_AVAILABLE = True
    logger.info("akshare 数据源可用")
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.error("akshare 库未安装，插件无法工作。请安装: pip install akshare")


class AKSharePlugin(IDataSourcePlugin):
    """AKShare数据源插件（异步优化版）"""

    def __init__(self):
        # 调用父类初始化（设置plugin_state等基础属性）
        super().__init__()

        self.logger = logger.bind(module=__name__)
        
        # 修复：显式初始化initialized和last_error属性
        self.initialized = False  # 插件初始化状态
        self.last_error = None    # 最后一次错误信息
        self.plugin_state = PluginLifecycle.CREATED  # 插件状态

        # 插件基本信息
        self.plugin_id = "data_sources.stock.akshare_plugin"  # 修复：添加stock层级
        self.name = "AKShare数据源插件"
        self.version = "1.0.0"
        self.description = "基于AKShare库的板块资金流数据源插件"
        self.author = "FactorWeave-Quant 开发团队"

        # 插件类型标识
        self.plugin_type = PluginType.DATA_SOURCE_STOCK

        # 支持的资产类型
        self.supported_asset_types = [AssetType.STOCK_A, AssetType.SECTOR]

        # 连接状态属性
        self.connection_time = None
        self.last_activity = None
        self.config = {}

        # 缓存设置
        self.cache_duration = 300  # 5分钟缓存
        self.last_cache_time = None
        self.cached_data = None
        
        # 注意：此时只是对象创建完成，真正的初始化（如配置加载）在initialize()方法中
        # plugin_state 已经在父类 __init__ 中设置为 CREATED（第223行），第65行也设置了（冗余但无害）
        # initialized 标志在 initialize() 方法中设置为 True
        # 不需要在这里设置 initialized = True，因为父类已经设置为 False（第227行）

    def get_version(self) -> str:
        """获取插件版本"""
        return self.version

    def get_description(self) -> str:
        """获取插件描述"""
        return self.description

    def get_author(self) -> str:
        """获取插件作者"""
        return self.author

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        return self.supported_asset_types

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型"""
        return [
            DataType.SECTOR_FUND_FLOW,    # 板块资金流数据（主要功能）
            DataType.REAL_TIME_QUOTE,     # 实时行情
            DataType.ASSET_LIST,          # 资产列表
            DataType.FUNDAMENTAL,          # 基本面数据（股本等）
            DataType.HISTORICAL_KLINE     # 支持K线数据
        ]

    def get_supported_adjustment_types(self) -> List[str]:
        """
        获取支持的复权类型列表

        Returns:
            List[str]: 支持的复权类型 ['qfq', 'hfq', 'none', 'both']
        """
        return ['qfq', 'hfq', 'none', 'both']

    def get_capabilities(self) -> Dict[str, Any]:
        """获取插件能力"""
        return {
            "markets": ["CN"],  # 中国市场
            "asset_types": ["stock", "sector"],
            "data_types": ["sector_fund_flow", "real_time_quote", "asset_list", "fundamental"],
            "real_time_support": True,
            "historical_data": False,  # 主要提供当日数据
            "sector_fund_flow": True,
            "rate_limit": "无限制",
            "cache_enabled": True,
            "primary_strength": "sector_fund_flow"
        }

    def get_priority(self) -> int:
        """获取插件优先级"""
        return 20  # 中等优先级

    def get_weight(self) -> float:
        """获取插件权重"""
        return 0.8  # 较高权重，数据质量好

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        # 创建 PluginInfo 对象，包括中文名称属性
        plugin_info = PluginInfo(
            id=self.plugin_id,
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            supported_asset_types=self.supported_asset_types,
            supported_data_types=self.get_supported_data_types(),
            capabilities={
                'real_time': True,
                'historical': False,
                'sector_fund_flow': True,
                'asset_list': True,
                'fundamental': True,
                'rate_limit': 0,  # 无限制
                'cache_enabled': True,
                'primary_strength': 'sector_fund_flow'
            },
            # 直接在构造函数中设置中文名称
            chinese_name=self.name  # AKShare数据源插件
        )

        return plugin_info

    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """同步初始化插件（快速，不做网络连接）"""
        try:
            self.plugin_state = PluginLifecycle.INITIALIZING

            # 检查 akshare 库是否可用
            if not AKSHARE_AVAILABLE:
                self.last_error = "akshare库未安装"
                self.plugin_state = PluginLifecycle.FAILED
                self.logger.error("AkShare插件初始化失败: akshare库未安装")
                self.logger.error("请安装: pip install akshare")
                return False

            # 合并配置
            if config:
                self.config.update(config)

            # 标记初始化完成
            self.initialized = True
            self.plugin_state = PluginLifecycle.INITIALIZED
            self.logger.info("AkShare插件同步初始化完成（<10ms）")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.plugin_state = PluginLifecycle.FAILED
            self.logger.error(f"AkShare插件初始化失败: {e}")
            return False

    def _do_connect(self) -> bool:
        """实际连接逻辑（在后台线程中执行）"""
        try:
            if not AKSHARE_AVAILABLE:
                self.plugin_state = PluginLifecycle.FAILED
                self.logger.error("❌ AkShare库不可用")
                return False

            # 简单测试：获取一条数据
            self.logger.info("AkShare插件测试连接...")
            test_df = ak.stock_sector_fund_flow_rank()

            if test_df is not None and not test_df.empty:
                self.logger.info("AkShare插件连接测试成功")
                self.plugin_state = PluginLifecycle.CONNECTED
                self.connection_time = datetime.now()
                self.last_activity = datetime.now()
                return True
            else:
                self.logger.warning("⚠️ AkShare插件测试返回空数据，但仍认为可用")
                self.plugin_state = PluginLifecycle.CONNECTED
                self.connection_time = datetime.now()
                self.last_activity = datetime.now()
                return True

        except Exception as e:
            self.last_error = str(e)
            self.plugin_state = PluginLifecycle.FAILED
            self.logger.error(f"❌ AkShare插件连接失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False

    # 连接管理
    def _internal_connect(self, **kwargs) -> bool:
        """内部连接实现"""
        try:
            if not AKSHARE_AVAILABLE:
                self.last_error = "akshare库未安装"
                return False

            # AKShare不需要显式连接，只需要检查库是否可用
            self.connection_time = datetime.now()
            self.last_activity = datetime.now()
            self.initialized = True

            self.logger.info("AKShare数据源连接成功")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"AKShare数据源连接失败: {e}")
            return False

    def _internal_disconnect(self) -> bool:
        """内部断开连接实现"""
        try:
            self.initialized = False
            self.connection_time = None
            self.last_activity = None
            self.cached_data = None
            self.last_cache_time = None

            self.logger.info("AKShare数据源断开连接")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"AKShare数据源断开连接失败: {e}")
            return False

    def fetch_data(self, symbol: str, data_type: str, **params) -> Any:
        """获取数据的通用接口"""
        try:
            if not self.initialized:
                if not self._internal_connect():
                    return None

            self.last_activity = datetime.now()

            if data_type == "sector_fund_flow":
                return self.get_sector_fund_flow_data(**params)
            else:
                self.logger.warning(f"不支持的数据类型: {data_type}")
                return None

        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"获取数据失败: {e}")
            return None

    def get_sector_fund_flow_data(self, data_type=None, **params) -> pd.DataFrame:
        """获取板块资金流数据

        Args:
            data_type: 数据类型（兼容性参数，可选）
            **params: 查询参数
                - limit: 返回记录数，默认50
                - use_cache: 是否使用缓存，默认True
                - indicator: 指标类型

        Returns:
            pd.DataFrame: 板块资金流数据
        """
        try:
            if not AKSHARE_AVAILABLE:
                self.logger.error("akshare库不可用")
                return pd.DataFrame()

            limit = params.get('limit', 50)
            use_cache = params.get('use_cache', True)

            # 检查缓存
            if use_cache and self._is_cache_valid():
                self.logger.info("使用缓存的板块资金流数据")
                return self.cached_data.head(limit) if self.cached_data is not None else pd.DataFrame()

            self.logger.info("获取AKShare板块资金流数据...")
            
            # 添加保守的请求延迟，避免触发反爬虫机制
            time.sleep(1.5)  # 保守延迟

            # 调用AKShare API
            raw_data = ak.stock_sector_fund_flow_rank()

            if raw_data is None or raw_data.empty:
                self.logger.warning("AKShare未返回板块资金流数据")
                return pd.DataFrame()

            # 数据标准化（向量化处理）
            raw_data = raw_data.reset_index(drop=True)
            standardized_data = raw_data.apply(
                lambda row: {
                    'sector_code': f'AK_{int(row.name) + 1:03d}',
                    'sector_name': str(row.get('名称', '')),
                    'change_percent': self._safe_float(row.get('今日涨跌幅', 0)),
                    'main_net_inflow': self._safe_float(row.get('今日主力净流入-净额', 0)),
                    'main_net_inflow_pct': self._safe_float(row.get('今日主力净流入-净占比', 0)),
                    'super_large_net_inflow': self._safe_float(row.get('今日超大单净流入-净额', 0)),
                    'super_large_net_inflow_pct': self._safe_float(row.get('今日超大单净流入-净占比', 0)),
                    'large_net_inflow': self._safe_float(row.get('今日大单净流入-净额', 0)),
                    'large_net_inflow_pct': self._safe_float(row.get('今日大单净流入-净占比', 0)),
                    'medium_net_inflow': self._safe_float(row.get('今日中单净流入-净额', 0)),
                    'medium_net_inflow_pct': self._safe_float(row.get('今日中单净流入-净占比', 0)),
                    'small_net_inflow': self._safe_float(row.get('今日小单净流入-净额', 0)),
                    'small_net_inflow_pct': self._safe_float(row.get('今日小单净流入-净占比', 0)),
                    'top_stock': str(row.get('今日主力净流入最大股', '')),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'data_source': 'akshare'
                }, axis=1
            ).tolist()

            if not standardized_data:
                self.logger.warning("没有有效的板块数据")
                return pd.DataFrame()

            df = pd.DataFrame(standardized_data)

            # 更新缓存
            self.cached_data = df
            self.last_cache_time = datetime.now()

            self.logger.info(f"成功获取AKShare板块资金流数据: {len(df)} 条记录")
            return df.head(limit)

        except Exception as e:
            self.logger.error(f"获取AKShare板块资金流数据失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return pd.DataFrame()

    def _safe_float(self, value) -> float:
        """安全转换为浮点数"""
        try:
            if value is None or value == '':
                return 0.0

            # 处理百分号
            if isinstance(value, str) and '%' in value:
                value = value.replace('%', '')

            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self.cached_data is None or self.last_cache_time is None:
            return False

        cache_age = (datetime.now() - self.last_cache_time).total_seconds()
        return cache_age < self.cache_duration

    # 实现抽象方法
    def connect(self, **kwargs) -> bool:
        """连接数据源"""
        return self._internal_connect(**kwargs)

    def disconnect(self) -> bool:
        """断开连接"""
        return self._internal_disconnect()

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.initialized

    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息"""
        return {
            'plugin_id': self.plugin_id,
            'name': self.name,
            'connected': self.initialized,
            'connection_time': self.connection_time.isoformat() if self.connection_time else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'last_error': self.last_error,
            'akshare_available': AKSHARE_AVAILABLE
        }

    @property
    def plugin_info(self) -> PluginInfo:
        """获取插件信息（属性形式）"""
        info = self.get_plugin_info()
        # 确保 chinese_name 属性存在
        if not hasattr(info, 'chinese_name'):
            info.chinese_name = self.name
        return info

    def health_check(self) -> HealthCheckResult:
        """健康检查（方法形式）"""
        return self.perform_health_check()

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        try:
            if asset_type == AssetType.STOCK_A:
                # 使用AKShare获取股票列表
                import akshare as ak
                stock_list = ak.stock_info_a_code_name()
                if not stock_list.empty:
                    assets = stock_list.assign(
                        symbol=stock_list['code'],
                        market='A股',
                        asset_type='stock',
                        category='股票'
                    )[['symbol', 'name', 'market', 'asset_type', 'code', 'category']].to_dict('records')
                    self.logger.info(f"AKShare获取股票列表成功: {len(assets)} 只股票")
                    return assets
            return []
        except Exception as e:
            self.logger.error(f"AKShare获取资产列表失败: {e}")
            return []

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None, adjustment: str = 'none') -> pd.DataFrame:
        """获取K线数据

        Args:
            symbol: 股票代码（如'000001'或'000001.SZ'）
            freq: 频率（'D'=日线、'W'=周线、'M'=月线）
            start_date: 开始日期（格式：'2023-01-01'或'20230101'）
            end_date: 结束日期（格式：'2023-12-31'或'20231231'）
            count: 数据条数（可选）
            adjustment: 复权类型 ('qfq', 'hfq', 'none')

        Returns:
            pd.DataFrame: K线数据（包含datetime, open, high, low, close, volume等）
        """
        try:
            if not AKSHARE_AVAILABLE:
                self.logger.warning("AKShare库未可用，无法获取K线数据")
                return pd.DataFrame()

            # 移除后缀（如'.SZ'、'.SH'）
            symbol_clean = symbol.split('.')[0] if '.' in symbol else symbol

            # 转换频率参数
            period_map = {
                'D': 'daily',
                'd': 'daily',
                'W': 'weekly',
                'w': 'weekly',
                'M': 'monthly',
                'm': 'monthly',
                'daily': 'daily',
                'weekly': 'weekly',
                'monthly': 'monthly'
            }
            period = period_map.get(freq, 'daily')

            # 转换日期格式（AKShare需要YYYYMMDD格式）
            def format_date(date_input):
                """将各种日期格式转换为AKShare要求的YYYYMMDD格式"""
                if date_input is None:
                    return None

                import datetime as dt
                import re

                # 如果是 datetime 对象
                if isinstance(date_input, dt.datetime):
                    return date_input.strftime('%Y%m%d')
                elif isinstance(date_input, dt.date):
                    return date_input.strftime('%Y%m%d')

                # 如果是字符串
                if isinstance(date_input, str):
                    date_str = date_input.strip()

                    # 正则匹配 YYYY-MM-DD 或 YYYYMMDD 或包含时间戳的日期格式
                    # 匹配格式：YYYY-MM-DD 或 YYYYMMDD
                    match = re.search(r'(\d{4})[-/]?(\d{2})[-/]?(\d{2})', date_str)
                    if match:
                        year, month, day = match.groups()
                        return f'{year}{month}{day}'

                    # 备用方案：移除所有非数字字符，获取前8个数字
                    date_clean = ''.join(c for c in date_str if c.isdigit())
                    if len(date_clean) >= 8:
                        return date_clean[:8]
                    elif len(date_clean) == 6:  # YYMMDD格式
                        return '20' + date_clean

                return None

            ak_start_date = format_date(start_date)
            ak_end_date = format_date(end_date)

            # 调用AKShare获取K线数据（带自动重试机制）
            self.logger.debug(f"从AKShare获取K线数据: {symbol_clean}, 周期: {period}, 范围: {ak_start_date}-{ak_end_date}")

            # 使用重试装饰器包装API调用
            @retry_on_connection_error(
                max_retries=3,
                initial_delay=2.0,
                backoff_factor=1.5,
                default_return=pd.DataFrame(),
                log_prefix=f"AKShare获取{symbol_clean}"
            )
            def fetch_kline_data():
                # 复权类型映射
                adjustment_map = {
                    'qfq': 'qfq',   # 前复权
                    'hfq': 'hfq',   # 后复权
                    'none': '',     # 不复权
                    'both': 'qfq'   # 默认前复权
                }
                adjust = adjustment_map.get(adjustment, '')
                
                return ak.stock_zh_a_hist(
                    symbol=symbol_clean,
                    period=period,
                    start_date=ak_start_date,
                    end_date=ak_end_date,
                    adjust=adjust  # 动态复权参数
                )

            df = fetch_kline_data()

            if df.empty:
                self.logger.warning(f"AKShare未返回{symbol}的K线数据。依然无法获取数据 (symbol={symbol_clean}, period={period}, dates={ak_start_date}~{ak_end_date})")
                self.logger.info(f"建议使用其他数据源获取{symbol}的K线数据（如：新浪财经、东方财富等）")
                return pd.DataFrame()

            # 标准化列名（AKShare返回的是中文列名）
            # 预期列名：日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
            column_mapping = {
                '日期': 'datetime',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover'
            }

            # 重命名列
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})

            # 处理日期列
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')

            # 确保关键列存在且为数值类型
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 限制数据条数（如果指定了count）
            if count and len(df) > count:
                df = df.tail(count)
            
            # 添加复权类型标识
            df['adj_type'] = adjustment
            df['adj_source'] = 'plugin'

            self.logger.info(f"从AKShare成功获取{symbol}的K线数据: {len(df)}条记录，复权类型: {adjustment}")
            return df

        except Exception as e:
            self.logger.error(f"从AKShare获取K线数据失败 {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """获取实时行情"""
        # AKShare插件主要用于板块资金流，暂不实现实时行情
        return []

    def get_fundamental_data(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本面数据（股本、财务指标等）

        Args:
            symbol: 股票代码（如'000001'）

        Returns:
            Dict[str, Any]: 包含基本面数据的字典
                - total_shares: 总股本（股）
                - circulating_shares: 流通股本（股）
                - total_market_cap: 总市值（元）
                - circulating_market_cap: 流通市值（元）
                - industry: 所属行业
                - list_date: 上市日期（YYYYMMDD格式）
                - pe_ratio: 市盈率
                - pb_ratio: 市净率
                - roe: 净资产收益率
                - roa: 总资产收益率
                - debt_ratio: 负债率
        """
        try:
            if not AKSHARE_AVAILABLE:
                self.logger.error("akshare库不可用，无法获取基本面数据")
                return {}

            # 检查缓存
            cache_key = f"fundamental_{symbol}"
            if self._is_cache_valid() and hasattr(self, 'cached_fundamental_data'):
                if cache_key in self.cached_fundamental_data:
                    self.logger.debug(f"使用缓存的基本面数据: {symbol}")
                    return self.cached_fundamental_data[cache_key]

            self.logger.info(f"从AKShare获取股票 {symbol} 的基本面数据...")

            # 添加请求延迟，避免触发反爬虫机制
            time.sleep(1.0)

            fundamental_data = {}

            # 调用AKShare API获取个股信息
            try:
                df = ak.stock_individual_info_em(symbol=symbol)

                if df is not None and not df.empty:
                    # 将DataFrame转换为字典，便于查找
                    info_dict = pd.Series(
                        df['value'].values,
                        index=df['item'].astype(str).str.strip()
                    ).to_dict()

                    # 提取总股本
                    if '总股本' in info_dict:
                        try:
                            fundamental_data['total_shares'] = float(info_dict['总股本'])
                        except (ValueError, TypeError):
                            self.logger.warning(f"无法解析总股本: {info_dict['总股本']}")
                            fundamental_data['total_shares'] = 0.0

                    # 提取流通股本
                    if '流通股' in info_dict:
                        try:
                            fundamental_data['circulating_shares'] = float(info_dict['流通股'])
                        except (ValueError, TypeError):
                            self.logger.warning(f"无法解析流通股: {info_dict['流通股']}")
                            fundamental_data['circulating_shares'] = 0.0

                    # 提取总市值
                    if '总市值' in info_dict:
                        try:
                            fundamental_data['total_market_cap'] = float(info_dict['总市值'])
                        except (ValueError, TypeError):
                            fundamental_data['total_market_cap'] = 0.0

                    # 提取流通市值
                    if '流通市值' in info_dict:
                        try:
                            fundamental_data['circulating_market_cap'] = float(info_dict['流通市值'])
                        except (ValueError, TypeError):
                            fundamental_data['circulating_market_cap'] = 0.0

                    # 提取行业信息
                    if '行业' in info_dict:
                        fundamental_data['industry'] = str(info_dict['行业'])

                    # 提取上市日期
                    if '上市时间' in info_dict:
                        fundamental_data['list_date'] = str(info_dict['上市时间'])
            except Exception as e:
                self.logger.warning(f"获取个股基本信息失败: {e}")

            # 获取财务指标数据
            # 注意：AKShare的stock_financial_analysis_indicator_em API目前不稳定，暂时跳过
            # 如果需要财务指标，可以考虑使用其他数据源或等待AKShare API修复
            try:
                # 尝试使用stock_financial_abstract获取部分财务数据
                time.sleep(0.5)
                financial_abstract_df = ak.stock_financial_abstract(symbol=symbol)

                if financial_abstract_df is not None and not financial_abstract_df.empty:
                    # 查找净资产收益率指标 - 注意指标名称是"净资产收益率(ROE)"
                    roe_row = financial_abstract_df[financial_abstract_df['指标'] == '净资产收益率(ROE)']
                    if roe_row.empty:
                        # 尝试另一个可能的名称
                        roe_row = financial_abstract_df[financial_abstract_df['指标'].str.contains('净资产收益率', na=False)]
                    
                    if not roe_row.empty:
                        try:
                            roe_value = roe_row.iloc[0]['20250930']
                            if pd.notna(roe_value) and roe_value != '-':
                                fundamental_data['roe'] = float(roe_value) / 100  # 转换为小数
                                self.logger.debug(f"成功获取净资产收益率: {roe_value}")
                        except (ValueError, TypeError):
                            self.logger.debug(f"字段解析失败: 净资产收益率={roe_value}")

                    # 查找总资产收益率指标 - 尝试多个可能的名称
                    roa_row = financial_abstract_df[financial_abstract_df['指标'].str.contains('总资产报酬率|总资产收益率', na=False)]
                    if not roa_row.empty:
                        try:
                            # 获取最新的数据列（排除'指标'列）
                            data_columns = [col for col in roa_row.columns if col != '指标']
                            if data_columns:
                                latest_column = data_columns[0]  # 通常第一列是最新的
                                roa_value = roa_row.iloc[0][latest_column]
                                if pd.notna(roa_value) and roa_value != '-':
                                    fundamental_data['roa'] = float(roa_value) / 100  # 转换为小数
                                    self.logger.debug(f"成功获取总资产收益率: {roa_value}")
                        except (ValueError, TypeError):
                            self.logger.debug(f"字段解析失败: 总资产收益率={roa_value}")

                    # 查找资产负债率指标
                    debt_ratio_row = financial_abstract_df[financial_abstract_df['指标'].str.contains('资产负债率', na=False)]
                    if not debt_ratio_row.empty:
                        try:
                            debt_ratio_value = debt_ratio_row.iloc[0]['20250930']
                            if pd.notna(debt_ratio_value) and debt_ratio_value != '-':
                                fundamental_data['debt_ratio'] = float(debt_ratio_value) / 100  # 转换为小数
                                self.logger.debug(f"成功获取资产负债率: {debt_ratio_value}")
                        except (ValueError, TypeError):
                            self.logger.debug(f"字段解析失败: 资产负债率={debt_ratio_value}")

                    self.logger.info(f"成功从财务摘要获取部分财务指标数据")
            except Exception as e:
                self.logger.warning(f"获取财务摘要数据失败: {e}")

            # 尝试获取PE、PB等估值指标
            try:
                time.sleep(0.5)
                a_stock_df = ak.stock_zh_a_spot_em()
                
                if a_stock_df is not None and not a_stock_df.empty:
                    # 查找对应股票的估值数据
                    stock_row = a_stock_df[a_stock_df['代码'] == symbol]
                    
                    if not stock_row.empty:
                        # 提取PE、PB等估值指标
                        try:
                            pe_value = stock_row.iloc[0]['市盈率-动态']
                            if pd.notna(pe_value) and pe_value != '-':
                                fundamental_data['pe_ratio'] = float(pe_value)
                                self.logger.debug(f"成功获取市盈率: {pe_value}")
                        except (KeyError, ValueError, TypeError):
                            self.logger.debug(f"字段解析失败: 市盈率={pe_value}")
                        
                        try:
                            pb_value = stock_row.iloc[0]['市净率']
                            if pd.notna(pb_value) and pb_value != '-':
                                fundamental_data['pb_ratio'] = float(pb_value)
                                self.logger.debug(f"成功获取市净率: {pb_value}")
                        except (KeyError, ValueError, TypeError):
                            self.logger.debug(f"字段解析失败: 市净率={pb_value}")
                        
                        self.logger.info(f"成功从实时行情获取估值指标数据")
            except Exception as e:
                self.logger.warning(f"获取估值指标数据失败: {e}")

            # 注意：PE、PB等估值指标需要实时行情数据，不在此处获取
            # 这些指标通常由实时行情数据源提供

            # 添加数据源标识
            fundamental_data['data_source'] = 'akshare'
            fundamental_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 缓存结果
            if not hasattr(self, 'cached_fundamental_data'):
                self.cached_fundamental_data = {}
            self.cached_fundamental_data[cache_key] = fundamental_data

            self.logger.info(f"成功获取股票 {symbol} 的基本面数据: {len(fundamental_data)} 个字段")
            return fundamental_data

        except Exception as e:
            self.logger.error(f"从AKShare获取股票 {symbol} 的基本面数据失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {}

    def perform_health_check(self) -> HealthCheckResult:
        """执行健康检查"""
        try:
            if not AKSHARE_AVAILABLE:
                return HealthCheckResult(
                    is_healthy=False,
                    message="akshare库未安装",
                    response_time=0,
                    extra_info={'error': 'akshare library not available'}
                )

            start_time = time.time()

            # 尝试获取少量数据进行健康检查
            test_data = ak.stock_sector_fund_flow_rank()

            response_time = (time.time() - start_time) * 1000  # 转换为毫秒

            if test_data is not None and not test_data.empty:
                return HealthCheckResult(
                    is_healthy=True,
                    message=f"AKShare数据源健康，获取到{len(test_data)}条数据",
                    response_time=response_time,
                    extra_info={
                        'data_count': len(test_data),
                        'cache_status': 'valid' if self._is_cache_valid() else 'expired'
                    }
                )
            else:
                return HealthCheckResult(
                    is_healthy=False,
                    message="AKShare数据源无数据返回",
                    response_time=response_time,
                    extra_info={'error': 'no data returned'}
                )

        except Exception as e:
            return HealthCheckResult(
                is_healthy=False,
                message=f"健康检查异常: {str(e)}",
                response_time=0,
                extra_info={'error': str(e)}
            )


# 插件注册
def create_plugin() -> AKSharePlugin:
    """创建插件实例"""
    return AKSharePlugin()


# 用于兼容性的别名
AKShareDataSourcePlugin = AKSharePlugin
