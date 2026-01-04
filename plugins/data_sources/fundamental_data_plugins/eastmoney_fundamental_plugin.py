#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eastmoney Fundamental Data Plugin
东方财富基本面数据源插件

提供东方财富的财务报表、公司公告、分析师评级数据。
使用真实的东方财富API接口，不包含任何模拟数据。

支持的数据类型：
- 财务报表（利润表、资产负债表、现金流量表）
- 公司公告
- 分析师评级

作者: FactorWeave-Quant Team
版本: 1.0.0
日期: 2024
"""

import asyncio
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import pandas as pd
from loguru import logger

from plugins.plugin_interface import IDataSourcePlugin, PluginLifecycle
from core.data_source_extensions import PluginInfo, HealthCheckResult
from core.plugin_types import AssetType, DataType, PluginType
from core.tet_data_pipeline import StandardQuery, StandardData

logger = logger.bind(module=__name__)


class EastmoneyFundamentalPlugin(IDataSourcePlugin):
    """
    东方财富基本面数据源插件
    提供东方财富的财务报表、公司公告、分析师评级数据。
    """

    def __init__(self, plugin_id: str = "eastmoney_fundamental_plugin"):
        self.plugin_id = plugin_id
        self.logger = logger.bind(plugin_id=self.plugin_id)

        # 必须显式初始化这些属性（IDataSourcePlugin是抽象基类，不提供默认实现）
        self.initialized = False
        self.last_error = None
        self.plugin_state = PluginLifecycle.CREATED  # 初始状态（插件对象已创建）

        self._is_connected = False
        self.session = requests.Session()

        # 设置请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://emweb.securities.eastmoney.com/',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        })

        # API端点配置
        self.api_endpoints = {
            'financial': 'https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax',
            'announcements': 'https://np-anotice-stock.eastmoney.com/api/security/ann',
            'research': 'https://reportapi.eastmoney.com/report/list'
        }

        self.logger.info(f"{self.plugin_id} 初始化完成。")

    def get_plugin_info(self) -> PluginInfo:
        """返回插件信息"""
        return PluginInfo(
            id=self.plugin_id,
            name="Eastmoney Fundamental Data Plugin",
            description="提供东方财富的财务报表、公司公告、分析师评级数据",
            version="1.0.0",
            author="FactorWeave-Quant Team",
            plugin_type=PluginType.DATA_SOURCE,
            capabilities={
                'data_types': [DataType.FINANCIAL_STATEMENT, DataType.ANNOUNCEMENT, DataType.ANALYST_RATING],
                'asset_types': [AssetType.STOCK_A, AssetType.FUND],
                'features': ['financial_reports', 'company_news', 'analyst_research']
            }
        )

    async def connect(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """连接到东方财富数据服务"""
        self.logger.info(f"尝试连接到 {self.plugin_id} 数据服务...")

        try:
            # 测试连接
            test_url = "https://www.eastmoney.com"
            response = self.session.get(test_url, timeout=10)

            if response.status_code == 200:
                self._is_connected = True
                self.logger.info(f"成功连接到 {self.plugin_id} 数据服务。")
                return True
            else:
                self.logger.error(f"连接测试失败: HTTP {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            return False

    async def disconnect(self) -> bool:
        """断开连接"""
        self.logger.info(f"尝试断开 {self.plugin_id} 数据服务...")
        self.session.close()
        self._is_connected = False
        self.logger.info(f"已从 {self.plugin_id} 数据服务断开。")
        return True

    async def health_check(self) -> HealthCheckResult:
        """执行健康检查"""
        try:
            if not self._is_connected:
                await self.connect()

            # 简单的健康检查
            test_response = self.session.get("https://www.eastmoney.com", timeout=5)
            if test_response.status_code == 200:
                return HealthCheckResult(is_healthy=True, message="连接正常")
            else:
                return HealthCheckResult(is_healthy=False, message=f"HTTP错误: {test_response.status_code}")

        except Exception as e:
            return HealthCheckResult(is_healthy=False, message=f"健康检查失败: {e}")

    async def get_data(self, query: StandardQuery) -> Union[List[Dict], pd.DataFrame, None]:
        """通用数据获取接口"""
        self.logger.warning(f"基本面数据插件 {self.plugin_id} 不通过 get_data 方法获取数据，请使用具体方法。")
        return None

    async def get_financial_statements(self, symbol: str, report_type: str, periods: int, asset_type: AssetType) -> Optional[List[Dict]]:
        """
        获取财务报表数据
        使用东方财富真实API获取数据
        """
        self.logger.info(f"从 {self.plugin_id} 获取 {symbol} 的 {report_type} 报表数据 (最近 {periods} 期)...")

        try:
            # 确保连接
            if not self._is_connected:
                await self.connect()

            # 构建API请求参数
            report_type_map = {
                'income_statement': 'lrb',  # 利润表
                'balance_sheet': 'zcfzb',   # 资产负债表
                'cash_flow': 'xjllb'        # 现金流量表
            }

            report_code = report_type_map.get(report_type, 'lrb')

            params = {
                'code': symbol,
                'type': report_code,
                'reportDateType': '0',  # 0-年报，1-中报，2-季报
                'reportType': '1',      # 1-单季度，2-累计
                'dates': str(periods)
            }

            # 发送API请求
            response = self.session.get(self.api_endpoints['financial'], params=params, timeout=15)

            if response.status_code == 200:
                try:
                    data = response.json()

                    if data and 'data' in data and data['data']:
                        # 解析财务数据
                        financial_data = self._parse_financial_data(data['data'], symbol, report_type)
                        self.logger.info(f"成功获取 {symbol} 的 {report_type} 数据，共 {len(financial_data)} 期")
                        return financial_data
                    else:
                        self.logger.warning(f"东方财富API返回空数据: {symbol}")
                        return None

                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON解析失败: {e}")
                    return None
            else:
                self.logger.error(f"东方财富API请求失败: HTTP {response.status_code}")
                return None

        except requests.RequestException as e:
            self.logger.error(f"网络请求失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"获取财务报表数据失败: {e}")
            return None

    def _parse_financial_data(self, raw_data: List[Dict], symbol: str, report_type: str) -> List[Dict]:
        """解析东方财富财务数据"""
        financial_records = []

        try:
            for record in raw_data:
                parsed_record = {
                    'symbol': symbol,
                    'report_type': report_type,
                    'report_date': record.get('REPORT_DATE', ''),
                    'source': self.plugin_id,
                    'update_time': datetime.now().isoformat()
                }

                # 根据报表类型解析不同字段
                if report_type == 'income_statement':
                    parsed_record.update({
                        'total_revenue': self._safe_float(record.get('TOTAL_OPERATE_INCOME')),
                        'operating_revenue': self._safe_float(record.get('OPERATE_INCOME')),
                        'net_profit': self._safe_float(record.get('NETPROFIT')),
                        'eps': self._safe_float(record.get('BASIC_EPS')),
                        'operating_profit': self._safe_float(record.get('OPERATE_PROFIT')),
                        'total_profit': self._safe_float(record.get('TOTAL_PROFIT')),
                        'operating_cost': self._safe_float(record.get('OPERATE_COST')),
                        'gross_profit': self._safe_float(record.get('GROSS_PROFIT'))
                    })
                elif report_type == 'balance_sheet':
                    parsed_record.update({
                        'total_assets': self._safe_float(record.get('TOTAL_ASSETS')),
                        'total_liabilities': self._safe_float(record.get('TOTAL_LIABILITIES')),
                        'total_equity': self._safe_float(record.get('TOTAL_EQUITY')),
                        'current_assets': self._safe_float(record.get('TOTAL_CURRENT_ASSETS')),
                        'current_liabilities': self._safe_float(record.get('TOTAL_CURRENT_LIABILITIES')),
                        'fixed_assets': self._safe_float(record.get('FIXED_ASSETS')),
                        'intangible_assets': self._safe_float(record.get('INTANGIBLE_ASSETS'))
                    })
                elif report_type == 'cash_flow':
                    parsed_record.update({
                        'operating_cash_flow': self._safe_float(record.get('NETCASH_OPERATE')),
                        'investing_cash_flow': self._safe_float(record.get('NETCASH_INVEST')),
                        'financing_cash_flow': self._safe_float(record.get('NETCASH_FINANCE')),
                        'net_cash_flow': self._safe_float(record.get('CCE_ADD')),
                        'free_cash_flow': self._safe_float(record.get('FREE_CASH_FLOW'))
                    })

                financial_records.append(parsed_record)

        except Exception as e:
            self.logger.error(f"解析财务数据失败: {e}")

        return financial_records

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            if value is None or value == '' or value == '--' or value == 0:
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    async def get_company_announcements(self, symbol: str, announcement_type: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict]:
        """
        获取公司公告
        使用东方财富真实API获取公告数据
        """
        self.logger.info(f"从 {self.plugin_id} 获取 {symbol} 的公司公告 (类型: {announcement_type})...")

        try:
            # 确保连接
            if not self._is_connected:
                await self.connect()

            # 设置默认时间范围
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=365)  # 默认获取一年内的公告

            # 构建API请求参数
            params = {
                'cb': 'jQuery',
                'pageSize': '50',
                'pageIndex': '1',
                'securityCode': symbol,
                'category': '',  # 公告类别
                'column': 'szse',  # 交易所
                'tabName': 'fulltext',
                'sortName': 'time',
                'sortType': '-1',
                'isHLtitle': 'true'
            }

            # 发送API请求
            response = self.session.get(self.api_endpoints['announcements'], params=params, timeout=15)

            if response.status_code == 200:
                try:
                    # 处理JSONP响应
                    content = response.text
                    if content.startswith('jQuery'):
                        # 提取JSON部分
                        start_idx = content.find('(') + 1
                        end_idx = content.rfind(')')
                        json_content = content[start_idx:end_idx]
                        data = json.loads(json_content)
                    else:
                        data = response.json()

                    if data and 'data' in data and data['data']:
                        # 解析公告数据
                        announcements = self._parse_announcement_data(data['data'], symbol, start_date, end_date)
                        self.logger.info(f"成功获取 {symbol} 的公告数据，共 {len(announcements)} 条")
                        return announcements
                    else:
                        self.logger.warning(f"东方财富公告API返回空数据: {symbol}")
                        return []

                except json.JSONDecodeError as e:
                    self.logger.error(f"公告数据JSON解析失败: {e}")
                    return []
            else:
                self.logger.error(f"东方财富公告API请求失败: HTTP {response.status_code}")
                return []

        except requests.RequestException as e:
            self.logger.error(f"公告数据网络请求失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"获取公司公告失败: {e}")
            return []

    def _parse_announcement_data(self, raw_data: List[Dict], symbol: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """解析东方财富公告数据"""
        announcements = []

        try:
            for record in raw_data:
                # 解析公告时间
                announce_time_str = record.get('NOTICE_DATE', '')
                if announce_time_str:
                    try:
                        announce_time = datetime.strptime(announce_time_str, '%Y-%m-%d %H:%M:%S')
                        # 过滤时间范围
                        if not (start_date <= announce_time <= end_date):
                            continue
                    except ValueError:
                        continue
                else:
                    continue

                announcement = {
                    'symbol': symbol,
                    'title': record.get('NOTICE_TITLE', ''),
                    'publish_date': announce_time_str,
                    'announcement_type': record.get('SECURITY_TYPE_NAME', ''),
                    'content': record.get('NOTICE_CONTENT', ''),
                    'url': record.get('ADJUNCT_URL', ''),
                    'source': self.plugin_id,
                    'importance': self._assess_announcement_importance(record.get('NOTICE_TITLE', '')),
                    'update_time': datetime.now().isoformat()
                }

                announcements.append(announcement)

        except Exception as e:
            self.logger.error(f"解析公告数据失败: {e}")

        return announcements

    def _assess_announcement_importance(self, title: str) -> str:
        """评估公告重要性"""
        high_importance_keywords = ['重大', '停牌', '重组', '收购', '分红', '业绩', '年报', '中报']
        medium_importance_keywords = ['公告', '提示', '澄清', '说明']

        title_lower = title.lower()

        for keyword in high_importance_keywords:
            if keyword in title_lower:
                return 'high'

        for keyword in medium_importance_keywords:
            if keyword in title_lower:
                return 'medium'

        return 'low'

    async def get_analyst_ratings(self, symbol: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Optional[List[Dict]]:
        """
        获取分析师评级数据
        使用东方财富真实API获取研报数据
        """
        self.logger.info(f"从 {self.plugin_id} 获取 {symbol} 的分析师评级数据...")

        try:
            # 确保连接
            if not self._is_connected:
                await self.connect()

            # 构建API请求参数
            params = {
                'cb': 'datatable',
                'pageSize': '50',
                'pageNo': '1',
                'sortColumns': 'REPORT_DATE',
                'sortTypes': '-1',
                'reportName': 'RPT_RESEARCH_REPORT',
                'columns': 'SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,REPORT_TITLE,RESEARCHER_NAME,ORGNAME,INVEST_RATING,INDUSTRY_RATING',
                'filter': f'(SECURITY_CODE="{symbol}")'
            }

            # 发送API请求
            response = self.session.get(self.api_endpoints['research'], params=params, timeout=15)

            if response.status_code == 200:
                try:
                    # 处理JSONP响应
                    content = response.text
                    if content.startswith('datatable'):
                        # 提取JSON部分
                        start_idx = content.find('(') + 1
                        end_idx = content.rfind(')')
                        json_content = content[start_idx:end_idx]
                        data = json.loads(json_content)
                    else:
                        data = response.json()

                    if data and 'result' in data and 'data' in data['result']:
                        # 解析研报数据
                        ratings = self._parse_analyst_rating_data(data['result']['data'], symbol, start_date, end_date)
                        self.logger.info(f"成功获取 {symbol} 的分析师评级数据，共 {len(ratings)} 条")
                        return ratings
                    else:
                        self.logger.warning(f"东方财富研报API返回空数据: {symbol}")
                        return []

                except json.JSONDecodeError as e:
                    self.logger.error(f"研报数据JSON解析失败: {e}")
                    return []
            else:
                self.logger.error(f"东方财富研报API请求失败: HTTP {response.status_code}")
                return []

        except requests.RequestException as e:
            self.logger.error(f"研报数据网络请求失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"获取分析师评级失败: {e}")
            return []

    def _parse_analyst_rating_data(self, raw_data: List[Dict], symbol: str, start_date: Optional[datetime], end_date: Optional[datetime]) -> List[Dict]:
        """解析东方财富分析师评级数据"""
        ratings = []

        try:
            for record in raw_data:
                # 解析评级时间
                rating_date_str = record.get('REPORT_DATE', '')
                if rating_date_str:
                    try:
                        rating_date = datetime.strptime(rating_date_str, '%Y-%m-%d %H:%M:%S')
                        # 过滤时间范围
                        if start_date and end_date:
                            if not (start_date <= rating_date <= end_date):
                                continue
                    except ValueError:
                        continue
                else:
                    continue

                rating = {
                    'symbol': symbol,
                    'rating_date': rating_date_str,
                    'institution': record.get('ORGNAME', ''),
                    'analyst': record.get('RESEARCHER_NAME', ''),
                    'report_title': record.get('REPORT_TITLE', ''),
                    'investment_rating': record.get('INVEST_RATING', ''),
                    'industry_rating': record.get('INDUSTRY_RATING', ''),
                    'rating_numeric': self._convert_rating_to_numeric(record.get('INVEST_RATING', '')),
                    'source': self.plugin_id,
                    'update_time': datetime.now().isoformat()
                }

                ratings.append(rating)

        except Exception as e:
            self.logger.error(f"解析分析师评级数据失败: {e}")

        return ratings

    def _convert_rating_to_numeric(self, rating_text: str) -> Optional[float]:
        """将评级文本转换为数值"""
        rating_map = {
            '强烈推荐': 5.0,
            '推荐': 4.0,
            '买入': 4.0,
            '增持': 3.5,
            '中性': 3.0,
            '持有': 3.0,
            '减持': 2.0,
            '卖出': 1.0,
            '强烈卖出': 0.5
        }

        return rating_map.get(rating_text, None)

    # 其他必需的抽象方法实现
    async def get_asset_list(self, asset_type: AssetType) -> List[Dict]:
        self.logger.warning(f"基本面数据插件 {self.plugin_id} 不提供资产列表功能。")
        return []

    async def get_kline_data(self, symbol: str, period: str, start_date: datetime, end_date: datetime, asset_type: AssetType) -> pd.DataFrame:
        self.logger.warning(f"基本面数据插件 {self.plugin_id} 不提供K线数据功能。")
        return pd.DataFrame()
