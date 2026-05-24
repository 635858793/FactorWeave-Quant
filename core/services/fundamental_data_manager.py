#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fundamental Data Manager
基本面数据管理器

负责财务报表、公司公告、分析师评级等基本面数据的获取、处理和标准化。
使用真实的数据源API，集成多个基本面数据提供商。

主要功能：
1. 财务报表数据获取和处理
2. 公司公告智能解析
3. 分析师评级数据管理
4. 数据质量验证和标准化
5. 多数据源聚合和去重

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

from core.plugin_types import AssetType, DataType
from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from core.tet_data_pipeline import StandardQuery, StandardData
from core.data_standardization_engine import DataStandardizationEngine
from core.data_validator import DataValidator
from core.services.announcement_parser import AnnouncementParser

logger = logger.bind(module=__name__)

class FundamentalDataManager:
    """
    基本面数据管理器
    负责财务报表、公司公告、分析师评级等基本面数据的获取、处理和标准化。
    """

    def __init__(self, data_standardizer: DataStandardizationEngine, data_validator: DataValidator, announcement_parser: AnnouncementParser, uni_plugin_manager: 'UniPluginDataManager'):
        self.data_standardizer = data_standardizer
        self.data_validator = data_validator
        self.announcement_parser = announcement_parser
        self.uni_plugin_manager = uni_plugin_manager  # 通过TET框架调用插件
        self.fundamental_plugins: Dict[str, Any] = {}
        logger.info("FundamentalDataManager 初始化完成，集成TET框架。")

    async def register_fundamental_plugin(self, plugin_id: str, plugin: IDataSourcePlugin):
        """注册基本面数据源插件"""
        self.fundamental_plugins[plugin_id] = plugin
        logger.info(f"基本面数据源插件 '{plugin_id}' 已注册。")

    async def get_financial_statements(self, symbol: str, report_type: str, periods: int, asset_type: AssetType, source_plugin_id: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取财务报表数据
        通过TET框架统一调用插件API
        """
        logger.info(f"通过TET框架获取财务报表: 股票={symbol}, 类型={report_type}, 周期={periods}, 插件={source_plugin_id}")

        try:
            # 通过TET框架构建查询
            from core.tet_data_pipeline import StandardQuery
            query = StandardQuery(
                symbol=symbol,
                data_type=DataType.FINANCIAL_STATEMENT,
                asset_type=asset_type,
                source_plugin_id=source_plugin_id,
                extra_params={
                    'report_type': report_type,
                    'periods': periods
                }
            )

            # 通过TET框架调用插件
            context = await self.uni_plugin_manager.create_request_context(query)
            result = await self.uni_plugin_manager.execute_data_request(context)

            if result:
                # 处理返回的数据
                processed_data = await self._process_financial_data(result, context.actual_plugin_id, symbol, report_type)
                if processed_data is not None and not processed_data.empty:
                    logger.info(f"通过TET框架成功获取 {len(processed_data)} 条财务数据")
                    return processed_data
                else:
                    logger.warning(f"TET框架返回的财务数据处理失败: {symbol}")
            else:
                logger.warning(f"TET框架未返回财务报表数据: {symbol}")

        except Exception as e:
            logger.error(f"通过TET框架获取财务报表失败: {e}")
            import traceback
            logger.debug(f"详细错误信息: {traceback.format_exc()}")

        return None

    async def _process_financial_data(self, raw_data: Union[Dict, List[Dict]], plugin_id: str, symbol: str, report_type: str) -> Optional[pd.DataFrame]:
        """处理财务数据"""
        try:
            # 统一数据格式
            if isinstance(raw_data, dict):
                data_list = [raw_data]
            elif isinstance(raw_data, list):
                data_list = raw_data
            else:
                logger.error(f"不支持的财务数据格式: {type(raw_data)}")
                return None

            # 数据标准化和验证
            standard_data_list = []
            for item in data_list:
                try:
                    # 添加基本信息
                    item['symbol'] = symbol
                    item['report_type'] = report_type
                    item['source'] = plugin_id

                    # 数据标准化
                    standard_item = self.data_standardizer.standardize_fundamental_data(item, DataType.FINANCIAL_STATEMENT, plugin_id)

                    # 数据验证
                    if self.data_validator.validate_fundamental_data(standard_item, DataType.FINANCIAL_STATEMENT):
                        standard_data_list.append(standard_item)
                    else:
                        logger.warning(f"财务数据项验证失败，跳过: {item.get('period', 'unknown')}")

                except Exception as e:
                    logger.warning(f"处理财务数据项失败: {e}")
                    continue

            if standard_data_list:
                df = pd.DataFrame(standard_data_list)
                # 按报告期排序
                if 'report_date' in df.columns:
                    df = df.sort_values('report_date', ascending=False)
                return df
            else:
                logger.warning(f"所有财务数据项都验证失败")
                return None

        except Exception as e:
            logger.error(f"处理财务数据失败: {e}")
            return None

    async def get_company_announcements(self, symbol: str, announcement_type: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, source_plugin_id: Optional[str] = None) -> List[Dict]:
        """
        获取公司公告
        使用真实的API调用获取公告数据
        """
        logger.info(f"获取公司公告: 股票={symbol}, 类型={announcement_type}, 插件={source_plugin_id}")

        all_announcements = []

        for plugin_id, plugin in self.fundamental_plugins.items():
            if source_plugin_id and plugin_id != source_plugin_id:
                continue

            try:
                # 检查插件能力
                plugin_info = plugin.get_plugin_info()
                if DataType.ANNOUNCEMENT not in plugin_info.capabilities.get('data_types', []):
                    logger.debug(f"插件 {plugin_id} 不支持公告数据")
                    continue

                # 调用插件API获取公告
                raw_announcements = None
                if hasattr(plugin, 'get_company_announcements'):
                    raw_announcements = await plugin.get_company_announcements(symbol, announcement_type, start_date, end_date)
                elif hasattr(plugin, 'get_announcements'):
                    raw_announcements = await plugin.get_announcements(symbol, announcement_type, start_date, end_date)
                elif hasattr(plugin, 'fetch_company_news'):
                    raw_announcements = await plugin.fetch_company_news(symbol, start_date, end_date)
                else:
                    logger.warning(f"插件 {plugin_id} 不支持公告获取")
                    continue

                if raw_announcements:
                    processed_announcements = await self._process_announcement_data(raw_announcements, plugin_id, symbol)
                    all_announcements.extend(processed_announcements)
                    logger.info(f"从插件 {plugin_id} 获取到 {len(processed_announcements)} 条公告")

            except Exception as e:
                logger.error(f"从插件 {plugin_id} 获取公司公告失败: {e}")

        # 去重和排序
        unique_announcements = self._deduplicate_announcements(all_announcements)
        logger.info(f"获取公司公告完成，共 {len(unique_announcements)} 条（去重后）")

        return unique_announcements

    async def _process_announcement_data(self, raw_announcements: List[Dict], plugin_id: str, symbol: str) -> List[Dict]:
        """处理公告数据"""
        processed_announcements = []

        for raw_anno in raw_announcements:
            try:
                # 添加基本信息
                raw_anno['symbol'] = symbol
                raw_anno['source'] = plugin_id

                # 数据标准化
                standard_anno = self.data_standardizer.standardize_fundamental_data(raw_anno, DataType.ANNOUNCEMENT, plugin_id)

                # 数据验证
                if self.data_validator.validate_fundamental_data(standard_anno, DataType.ANNOUNCEMENT):
                    # 使用公告解析引擎进行智能解析
                    parsed_anno = self.announcement_parser.parse_announcement(standard_anno)
                    processed_announcements.append(parsed_anno)
                else:
                    logger.warning(f"公告数据验证失败，跳过: {raw_anno.get('title', 'unknown')}")

            except Exception as e:
                logger.warning(f"处理公告数据失败: {e}")
                continue

        return processed_announcements

    def _deduplicate_announcements(self, announcements: List[Dict]) -> List[Dict]:
        """公告去重"""
        seen_titles = set()
        unique_announcements = []

        # 按发布时间排序
        sorted_announcements = sorted(announcements, key=lambda x: x.get('publish_date', ''), reverse=True)

        for announcement in sorted_announcements:
            title = announcement.get('title', '')
            # 简单的标题去重
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_announcements.append(announcement)

        return unique_announcements

    async def get_analyst_ratings(self, symbol: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, source_plugin_id: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取分析师评级数据
        使用真实的API调用获取评级数据
        """
        logger.info(f"获取分析师评级: 股票={symbol}, 插件={source_plugin_id}")

        all_ratings = []

        for plugin_id, plugin in self.fundamental_plugins.items():
            if source_plugin_id and plugin_id != source_plugin_id:
                continue

            try:
                # 检查插件能力
                plugin_info = plugin.get_plugin_info()
                if DataType.ANALYST_RATING not in plugin_info.capabilities.get('data_types', []):
                    logger.debug(f"插件 {plugin_id} 不支持分析师评级数据")
                    continue

                # 调用插件API获取评级
                raw_ratings = None
                if hasattr(plugin, 'get_analyst_ratings'):
                    raw_ratings = await plugin.get_analyst_ratings(symbol, start_date, end_date)
                elif hasattr(plugin, 'get_research_reports'):
                    raw_ratings = await plugin.get_research_reports(symbol, start_date, end_date)
                elif hasattr(plugin, 'fetch_analyst_data'):
                    raw_ratings = await plugin.fetch_analyst_data(symbol, start_date, end_date)
                else:
                    logger.warning(f"插件 {plugin_id} 不支持分析师评级获取")
                    continue

                if raw_ratings:
                    processed_ratings = await self._process_rating_data(raw_ratings, plugin_id, symbol)
                    all_ratings.extend(processed_ratings)
                    logger.info(f"从插件 {plugin_id} 获取到 {len(processed_ratings)} 条评级")

            except Exception as e:
                logger.error(f"从插件 {plugin_id} 获取分析师评级失败: {e}")

        if all_ratings:
            df = pd.DataFrame(all_ratings)
            # 按评级日期排序
            if 'rating_date' in df.columns:
                df = df.sort_values('rating_date', ascending=False)
            logger.info(f"获取分析师评级完成，共 {len(df)} 条")
            return df
        else:
            logger.warning(f"未获取到 {symbol} 的分析师评级数据")
            return None

    async def _process_rating_data(self, raw_ratings: Union[Dict, List[Dict]], plugin_id: str, symbol: str) -> List[Dict]:
        """处理评级数据"""
        processed_ratings = []

        # 统一数据格式
        if isinstance(raw_ratings, dict):
            ratings_list = [raw_ratings]
        else:
            ratings_list = raw_ratings

        for raw_rating in ratings_list:
            try:
                # 添加基本信息
                raw_rating['symbol'] = symbol
                raw_rating['source'] = plugin_id

                # 数据标准化
                standard_rating = self.data_standardizer.standardize_fundamental_data(raw_rating, DataType.ANALYST_RATING, plugin_id)

                # 数据验证
                if self.data_validator.validate_fundamental_data(standard_rating, DataType.ANALYST_RATING):
                    processed_ratings.append(standard_rating)
                else:
                    logger.warning(f"分析师评级数据验证失败，跳过: {raw_rating.get('institution', 'unknown')}")

            except Exception as e:
                logger.warning(f"处理分析师评级数据失败: {e}")
                continue

        return processed_ratings

    async def get_comprehensive_fundamental_data(self, symbol: str, asset_type: AssetType) -> Dict[str, Any]:
        """
        获取综合基本面数据
        包括财务报表、公告和分析师评级的综合信息
        """
        logger.info(f"获取综合基本面数据: {symbol}")

        comprehensive_data = {
            'symbol': symbol,
            'asset_type': asset_type.value,
            'update_time': datetime.now().isoformat(),
            'financial_statements': {},
            'announcements': [],
            'analyst_ratings': None,
            'summary': {}
        }

        try:
            # 获取财务报表（最近4个季度）
            financial_tasks = []
            for report_type in ['income_statement', 'balance_sheet', 'cash_flow']:
                task = self.get_financial_statements(symbol, report_type, 4, asset_type)
                financial_tasks.append((report_type, task))

            # 并行获取财务数据
            for report_type, task in financial_tasks:
                try:
                    financial_data = await task
                    if financial_data is not None and not financial_data.empty:
                        comprehensive_data['financial_statements'][report_type] = financial_data.to_dict('records')
                except Exception as e:
                    logger.warning(f"获取 {report_type} 失败: {e}")

            # 获取最近3个月的公告
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            announcements = await self.get_company_announcements(symbol, start_date=start_date, end_date=end_date)
            comprehensive_data['announcements'] = announcements[:20]  # 最多20条

            # 获取最近6个月的分析师评级
            start_date = end_date - timedelta(days=180)
            ratings = await self.get_analyst_ratings(symbol, start_date=start_date, end_date=end_date)
            if ratings is not None and not ratings.empty:
                comprehensive_data['analyst_ratings'] = ratings.to_dict('records')

            # 生成摘要
            comprehensive_data['summary'] = self._generate_fundamental_summary(comprehensive_data)

            logger.info(f"综合基本面数据获取完成: {symbol}")
            return comprehensive_data

        except Exception as e:
            logger.error(f"获取综合基本面数据失败: {e}")
            comprehensive_data['error'] = str(e)
            return comprehensive_data

    def _generate_fundamental_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """生成基本面数据摘要"""
        summary = {
            'financial_health': 'unknown',
            'recent_announcements_count': len(data.get('announcements', [])),
            'analyst_consensus': 'unknown',
            'data_completeness': 0.0
        }

        try:
            # 计算数据完整性
            completeness_score = 0
            if data.get('financial_statements'):
                completeness_score += 0.4
            if data.get('announcements'):
                completeness_score += 0.3
            if data.get('analyst_ratings'):
                completeness_score += 0.3

            summary['data_completeness'] = completeness_score

            # 分析师共识
            ratings = data.get('analyst_ratings')
            if ratings:
                rating_values = [r.get('rating_numeric', 0) for r in ratings if r.get('rating_numeric')]
                if rating_values:
                    avg_rating = sum(rating_values) / len(rating_values)
                    if avg_rating >= 4:
                        summary['analyst_consensus'] = 'strong_buy'
                    elif avg_rating >= 3:
                        summary['analyst_consensus'] = 'buy'
                    elif avg_rating >= 2:
                        summary['analyst_consensus'] = 'hold'
                    else:
                        summary['analyst_consensus'] = 'sell'

            # 财务健康度（简化评估）
            financial_statements = data.get('financial_statements', {})
            if financial_statements.get('income_statement'):
                # 基于收入增长等指标进行简单评估
                summary['financial_health'] = 'stable'  # 简化处理

        except Exception as e:
            logger.warning(f"生成基本面摘要失败: {e}")

        return summary
