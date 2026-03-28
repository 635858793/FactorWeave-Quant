#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eastmoney Unified Data Plugin
东方财富统一数据源插件

整合东方财富的所有数据类型，包括：
- 实时行情数据 (Level-2, Tick, 订单簿)
- 历史K线数据
- 基本面数据 (财务报表、公司公告、分析师评级)
- 宏观经济数据
- 资金流向数据

通过data_type参数统一获取不同类型的数据，简化插件管理。

作者: FactorWeave-Quant Team
版本: 1.0.0
日期: 2024
"""

import asyncio
import requests
import json
import websocket
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import pandas as pd
from loguru import logger

from plugins.plugin_interface import IDataSourcePlugin, PluginLifecycle
from core.data_source_extensions import PluginInfo, HealthCheckResult
from core.plugin_types import AssetType, DataType, PluginType
from core.tet_data_pipeline import StandardQuery, StandardData

logger = logger.bind(module=__name__)


class EastmoneyUnifiedPlugin(IDataSourcePlugin):
    """
    东方财富统一数据源插件
    支持通过data_type参数获取不同类型的数据
    """

    def __init__(self, plugin_id: str = "eastmoney_unified"):
        self.plugin_id = plugin_id
        self.logger = logger.bind(plugin_id=self.plugin_id)

        # 必须显式初始化这些属性（IDataSourcePlugin是抽象基类，不提供默认实现）
        self.initialized = False
        self.last_error = None
        self.plugin_state = PluginLifecycle.CREATED  # 初始状态（插件对象已创建）

        self._is_connected = False
        self.session = requests.Session()

        # 设置通用请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.eastmoney.com/',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        })

        # 统一的API端点配置
        self.api_endpoints = {
            # 实时行情相关
            'realtime_quotes': 'https://push2.eastmoney.com/api/qt/ulist.np/get',
            'level2_data': 'https://push2.eastmoney.com/api/qt/stock/details/get',
            'tick_data': 'https://push2.eastmoney.com/api/qt/stock/fflow/kline/get',

            # 历史数据相关
            'kline_data': 'https://push2his.eastmoney.com/api/qt/stock/kline/get',
            'stock_list': 'https://push2.eastmoney.com/api/qt/clist/get',

            # 基本面数据相关
            'financial_statements': 'https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax',
            'company_announcements': 'https://np-anotice-stock.eastmoney.com/api/security/ann',
            'analyst_ratings': 'https://reportapi.eastmoney.com/report/list',

            # 宏观数据相关
            'macro_data': 'https://datacenter-web.eastmoney.com/api/data/v1/get',

            # 资金流向相关
            'money_flow': 'https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get'
        }

        # WebSocket连接配置
        self.websocket_url = "wss://wss.eastmoney.com/websocket"
        self.websocket_connection = None

        self.logger.info(f"{self.plugin_id} 统一插件初始化完成。")

    def get_plugin_info(self) -> PluginInfo:
        """返回插件信息"""
        return PluginInfo(
            id=self.plugin_id,
            name="Eastmoney Unified Data Plugin",
            description="东方财富统一数据源插件，支持所有数据类型",
            version="1.0.0",
            author="FactorWeave-Quant Team",
            plugin_type=PluginType.DATA_SOURCE,
            capabilities={
                'data_types': [
                    # 实时数据
                    DataType.REAL_TIME_QUOTE, DataType.LEVEL2_DATA, DataType.TICK_DATA, DataType.ORDER_BOOK,
                    # 历史数据
                    DataType.HISTORICAL_KLINE, DataType.STOCK_LIST,
                    # 基本面数据
                    DataType.FINANCIAL_STATEMENT, DataType.ANNOUNCEMENT, DataType.ANALYST_RATING,
                    # 宏观数据
                    DataType.MACRO_ECONOMIC_INDICATOR,
                    # 资金流向
                    DataType.MONEY_FLOW
                ],
                'asset_types': [AssetType.STOCK_A, AssetType.FUND, AssetType.BOND, AssetType.INDEX],
                'features': [
                    'realtime_data', 'historical_data', 'fundamental_data',
                    'macro_data', 'money_flow', 'websocket_support'
                ]
            }
        )

    async def connect(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """连接到东方财富数据服务"""
        self.logger.info(f"尝试连接到 {self.plugin_id} 统一数据服务...")

        try:
            # 测试HTTP连接
            test_url = "https://www.eastmoney.com"
            response = self.session.get(test_url, timeout=10)

            if response.status_code == 200:
                self._is_connected = True
                self.logger.info(f"成功连接到 {self.plugin_id} 统一数据服务。")
                return True
            else:
                self.logger.error(f"连接测试失败: HTTP {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            return False

    async def disconnect(self) -> bool:
        """断开连接"""
        self.logger.info(f"尝试断开 {self.plugin_id} 统一数据服务...")

        # 关闭WebSocket连接
        if self.websocket_connection:
            try:
                self.websocket_connection.close()
                self.websocket_connection = None
            except Exception as e:
                self.logger.warning(f"关闭WebSocket连接失败: {e}")

        # 关闭HTTP会话
        self.session.close()
        self._is_connected = False
        self.logger.info(f"已从 {self.plugin_id} 统一数据服务断开。")
        return True

    async def health_check(self) -> HealthCheckResult:
        """执行健康检查"""
        try:
            if not self._is_connected:
                await self.connect()

            # 测试API连通性
            test_response = self.session.get("https://www.eastmoney.com", timeout=5)
            if test_response.status_code == 200:
                return HealthCheckResult(is_healthy=True, message="连接正常")
            else:
                return HealthCheckResult(is_healthy=False, message=f"HTTP错误: {test_response.status_code}")

        except Exception as e:
            return HealthCheckResult(is_healthy=False, message=f"健康检查失败: {e}")

    async def get_data(self, query: StandardQuery) -> Union[List[Dict], pd.DataFrame, None]:
        """
        统一数据获取接口
        根据data_type参数调用相应的数据获取方法
        """
        self.logger.info(f"通过统一接口获取数据: {query.symbol} - {query.data_type.value}")

        try:
            # 确保连接
            if not self._is_connected:
                await self.connect()

            # 根据数据类型调用相应方法
            if query.data_type == DataType.REAL_TIME_QUOTE:
                return await self._get_realtime_quotes([query.symbol], query.asset_type)

            elif query.data_type == DataType.LEVEL2_DATA:
                return await self._get_level2_data([query.symbol], query.asset_type)

            elif query.data_type == DataType.TICK_DATA:
                return await self._get_tick_data(query.symbol, query.start_date, query.end_date, query.asset_type)

            elif query.data_type == DataType.ORDER_BOOK:
                return await self._get_order_book_data([query.symbol], query.asset_type)

            elif query.data_type == DataType.HISTORICAL_KLINE:
                return await self._get_kline_data(query.symbol, query.extra_params.get('period', 'daily'), query.start_date, query.end_date, query.asset_type)

            elif query.data_type == DataType.STOCK_LIST:
                return await self._get_stock_list(query.asset_type)

            elif query.data_type == DataType.FINANCIAL_STATEMENT:
                return await self._get_financial_statements(query.symbol, query.extra_params.get('report_type', 'income_statement'), query.extra_params.get('periods', 4), query.asset_type)

            elif query.data_type == DataType.ANNOUNCEMENT:
                return await self._get_company_announcements(query.symbol, query.extra_params.get('announcement_type'), query.start_date, query.end_date)

            elif query.data_type == DataType.ANALYST_RATING:
                return await self._get_analyst_ratings(query.symbol, query.start_date, query.end_date)

            elif query.data_type == DataType.MACRO_ECONOMIC_INDICATOR:
                return await self._get_macro_data(query.extra_params.get('indicator_id'), query.extra_params.get('country', 'CN'), query.start_date, query.end_date)

            elif query.data_type == DataType.MONEY_FLOW:
                return await self._get_money_flow_data(query.symbol, query.start_date, query.end_date, query.asset_type)

            else:
                self.logger.warning(f"不支持的数据类型: {query.data_type}")
                return None

        except Exception as e:
            self.logger.error(f"获取数据失败: {e}")
            return None

    # 实时数据获取方法
    async def _get_realtime_quotes(self, symbols: List[str], asset_type: AssetType) -> pd.DataFrame:
        """获取实时行情数据"""
        try:
            # 构建请求参数
            symbols_str = ','.join([self._format_symbol(symbol, asset_type) for symbol in symbols])
            params = {
                'fltt': '2',
                'invt': '2',
                'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f15,f16,f17,f18',
                'secids': symbols_str
            }

            response = self.session.get(self.api_endpoints['realtime_quotes'], params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and 'diff' in data['data']:
                    return self._parse_realtime_quotes(data['data']['diff'])

        except Exception as e:
            self.logger.error(f"获取实时行情失败: {e}")

        return pd.DataFrame()

    async def _get_level2_data(self, symbols: List[str], asset_type: AssetType) -> List[Dict]:
        """获取Level-2数据"""
        level2_data = []

        for symbol in symbols:
            try:
                params = {
                    'secid': self._format_symbol(symbol, asset_type),
                    'fields1': 'f1,f2,f3,f4',
                    'fields2': 'f51,f52,f53,f54,f55'
                }

                response = self.session.get(self.api_endpoints['level2_data'], params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    if data and 'data' in data:
                        level2_item = self._parse_level2_data(data['data'], symbol)
                        if level2_item:
                            level2_data.append(level2_item)

            except Exception as e:
                self.logger.error(f"获取Level-2数据失败 {symbol}: {e}")

        return level2_data

    async def _get_tick_data(self, symbol: str, start_date: datetime, end_date: datetime, asset_type: AssetType) -> List[Dict]:
        """获取Tick数据"""
        try:
            params = {
                'secid': self._format_symbol(symbol, asset_type),
                'fields1': 'f1,f2,f3,f7',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58',
                'lmt': '1000'  # 限制返回数量
            }

            response = self.session.get(self.api_endpoints['tick_data'], params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data:
                    return self._parse_tick_data(data['data'], symbol, start_date, end_date)

        except Exception as e:
            self.logger.error(f"获取Tick数据失败 {symbol}: {e}")

        return []

    # 基本面数据获取方法
    async def _get_financial_statements(self, symbol: str, report_type: str, periods: int, asset_type: AssetType) -> List[Dict]:
        """获取财务报表数据"""
        try:
            report_type_map = {
                'income_statement': 'lrb',
                'balance_sheet': 'zcfzb',
                'cash_flow': 'xjllb'
            }

            report_code = report_type_map.get(report_type, 'lrb')

            params = {
                'code': symbol,
                'type': report_code,
                'reportDateType': '0',
                'reportType': '1',
                'dates': str(periods)
            }

            response = self.session.get(self.api_endpoints['financial_statements'], params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and data['data']:
                    return self._parse_financial_data(data['data'], symbol, report_type)

        except Exception as e:
            self.logger.error(f"获取财务报表失败 {symbol}: {e}")

        return []

    # 工具方法
    def _format_symbol(self, symbol: str, asset_type: AssetType) -> str:
        """格式化股票代码为东方财富格式"""
        if asset_type == AssetType.STOCK_A:
            if symbol.startswith('6'):
                return f"1.{symbol}"  # 上海
            elif symbol.startswith(('0', '3')):
                return f"0.{symbol}"  # 深圳
            elif symbol.startswith(('4', '8', '9')):
                return f"2.{symbol}"  # 北京
        return f"1.{symbol}"  # 默认上海

    def _parse_realtime_quotes(self, raw_data: List[Dict]) -> pd.DataFrame:
        """解析实时行情数据"""
        quotes = []

        for item in raw_data:
            quote = {
                'symbol': item.get('f12', ''),
                'name': item.get('f14', ''),
                'price': self._safe_float(item.get('f2')),
                'change': self._safe_float(item.get('f4')),
                'pct_change': self._safe_float(item.get('f3')),
                'volume': self._safe_float(item.get('f5')),
                'amount': self._safe_float(item.get('f6')),
                'high': self._safe_float(item.get('f15')),
                'low': self._safe_float(item.get('f16')),
                'open': self._safe_float(item.get('f17')),
                'pre_close': self._safe_float(item.get('f18')),
                'timestamp': datetime.now().isoformat(),
                'source': self.plugin_id
            }
            quotes.append(quote)

        return pd.DataFrame(quotes)

    def _parse_level2_data(self, raw_data: Dict, symbol: str) -> Optional[Dict]:
        """解析Level-2数据"""
        if not raw_data:
            return None

        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'bid_prices': [self._safe_float(raw_data.get(f'f{51+i}')) for i in range(5)],
            'bid_volumes': [self._safe_float(raw_data.get(f'f{61+i}')) for i in range(5)],
            'ask_prices': [self._safe_float(raw_data.get(f'f{71+i}')) for i in range(5)],
            'ask_volumes': [self._safe_float(raw_data.get(f'f{81+i}')) for i in range(5)],
            'source': self.plugin_id
        }

    def _parse_tick_data(self, raw_data: Dict, symbol: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """解析Tick数据"""
        ticks = []

        if 'klines' in raw_data:
            for kline in raw_data['klines']:
                # 解析tick数据格式
                parts = kline.split(',')
                if len(parts) >= 6:
                    tick_time_str = parts[0]
                    try:
                        tick_time = datetime.strptime(tick_time_str, '%Y-%m-%d %H:%M')
                        if start_date <= tick_time <= end_date:
                            tick = {
                                'symbol': symbol,
                                'timestamp': tick_time.isoformat(),
                                'price': self._safe_float(parts[1]),
                                'volume': self._safe_float(parts[2]),
                                'amount': self._safe_float(parts[3]),
                                'type': 'buy' if float(parts[4]) > 0 else 'sell',
                                'source': self.plugin_id
                            }
                            ticks.append(tick)
                    except ValueError:
                        continue

        return ticks

    def _parse_financial_data(self, raw_data: List[Dict], symbol: str, report_type: str) -> List[Dict]:
        """解析财务数据"""
        financial_records = []

        for record in raw_data:
            parsed_record = {
                'symbol': symbol,
                'report_type': report_type,
                'report_date': record.get('REPORT_DATE', ''),
                'source': self.plugin_id,
                'update_time': datetime.now().isoformat()
            }

            # 根据报表类型解析字段
            if report_type == 'income_statement':
                parsed_record.update({
                    'total_revenue': self._safe_float(record.get('TOTAL_OPERATE_INCOME')),
                    'net_profit': self._safe_float(record.get('NETPROFIT')),
                    'eps': self._safe_float(record.get('BASIC_EPS'))
                })
            elif report_type == 'balance_sheet':
                parsed_record.update({
                    'total_assets': self._safe_float(record.get('TOTAL_ASSETS')),
                    'total_liabilities': self._safe_float(record.get('TOTAL_LIABILITIES')),
                    'total_equity': self._safe_float(record.get('TOTAL_EQUITY'))
                })

            financial_records.append(parsed_record)

        return financial_records

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            if value is None or value == '' or value == '--':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    # 其他必需的抽象方法实现
    async def get_asset_list(self, asset_type: AssetType) -> List[Dict]:
        """获取资产列表"""
        return await self._get_stock_list(asset_type)

    async def _get_stock_list(self, asset_type: AssetType) -> List[Dict]:
        """获取股票列表"""
        try:
            params = {
                'pn': '1',
                'pz': '5000',
                'po': '1',
                'np': '1',
                'fltt': '2',
                'invt': '2',
                'fid': 'f3',
                'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
                'fields': 'f12,f14,f2,f3,f4,f5,f6'
            }

            response = self.session.get(self.api_endpoints['stock_list'], params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and 'diff' in data['data']:
                    return self._parse_stock_list(data['data']['diff'])

        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")

        return []

    def _parse_stock_list(self, raw_data: List[Dict]) -> List[Dict]:
        """解析股票列表"""
        stocks = []

        for item in raw_data:
            stock = {
                'symbol': item.get('f12', ''),
                'name': item.get('f14', ''),
                'price': self._safe_float(item.get('f2')),
                'change_pct': self._safe_float(item.get('f3')),
                'volume': self._safe_float(item.get('f5')),
                'amount': self._safe_float(item.get('f6')),
                'source': self.plugin_id
            }
            stocks.append(stock)

        return stocks

    async def get_kline_data(self, symbol: str, period: str, start_date: datetime, end_date: datetime, asset_type: AssetType) -> pd.DataFrame:
        """获取K线数据"""
        return await self._get_kline_data(symbol, period, start_date, end_date, asset_type)

    async def _get_kline_data(self, symbol: str, period: str, start_date: datetime, end_date: datetime, asset_type: AssetType) -> pd.DataFrame:
        """获取K线数据实现"""
        try:
            # 周期映射
            period_map = {
                'daily': '101',
                'weekly': '102',
                'monthly': '103',
                '1min': '1',
                '5min': '5',
                '15min': '15',
                '30min': '30',
                '60min': '60'
            }

            klt = period_map.get(period, '101')

            params = {
                'secid': self._format_symbol(symbol, asset_type),
                'klt': klt,
                'fqt': '1',
                'lmt': '1000',
                'end': '20500101',
                'iscca': '1',
                'fields1': 'f1,f2,f3,f4,f5,f6,f7,f8',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'
            }

            response = self.session.get(self.api_endpoints['kline_data'], params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and 'klines' in data['data']:
                    return self._parse_kline_data(data['data']['klines'], symbol, start_date, end_date)

        except Exception as e:
            self.logger.error(f"获取K线数据失败 {symbol}: {e}")

        return pd.DataFrame()

    def _parse_kline_data(self, klines: List[str], symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """解析K线数据"""
        kline_data = []

        for kline in klines:
            parts = kline.split(',')
            if len(parts) >= 11:
                try:
                    kline_date = datetime.strptime(parts[0], '%Y-%m-%d')
                    if start_date <= kline_date <= end_date:
                        kline_item = {
                            'symbol': symbol,
                            'date': kline_date,
                            'open': self._safe_float(parts[1]),
                            'close': self._safe_float(parts[2]),
                            'high': self._safe_float(parts[3]),
                            'low': self._safe_float(parts[4]),
                            'volume': self._safe_float(parts[5]),
                            'amount': self._safe_float(parts[6]),
                            'source': self.plugin_id
                        }
                        kline_data.append(kline_item)
                except ValueError:
                    continue

        return pd.DataFrame(kline_data)

    # 占位方法，用于其他数据类型
    async def _get_order_book_data(self, symbols: List[str], asset_type: AssetType) -> List[Dict]:
        """获取订单簿数据（占位方法）"""
        self.logger.info("订单簿数据获取功能开发中...")
        return []

    async def _get_company_announcements(self, symbol: str, announcement_type: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]) -> List[Dict]:
        """获取公司公告（占位方法）"""
        self.logger.info("公司公告数据获取功能开发中...")
        return []

    async def _get_analyst_ratings(self, symbol: str, start_date: Optional[datetime], end_date: Optional[datetime]) -> List[Dict]:
        """获取分析师评级（占位方法）"""
        self.logger.info("分析师评级数据获取功能开发中...")
        return []

    async def _get_macro_data(self, indicator_id: str, country: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """获取宏观数据（占位方法）"""
        self.logger.info("宏观数据获取功能开发中...")
        return []

    async def _get_money_flow_data(self, symbol: str, start_date: datetime, end_date: datetime, asset_type: AssetType) -> List[Dict]:
        """获取资金流向数据（占位方法）"""
        self.logger.info("资金流向数据获取功能开发中...")
        return []
