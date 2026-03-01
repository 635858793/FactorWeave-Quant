"""
板块数据服务模块

提供板块资金流数据的专门访问服务，包括排行榜查询、历史趋势分析、分时数据获取和历史数据导入功能。
基于现有的UnifiedDataManager和MultiLevelCacheManager构建，确保性能和可靠性。

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2025
"""

import pandas as pd
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from loguru import logger
import traceback

from ..database.table_manager import TableType, get_table_manager
from ..database.duckdb_manager import initialize_duckdb_manager
from ..plugin_types import AssetType, DataType
from ..tet_data_pipeline import TETDataPipeline, StandardQuery, StandardData
from ..performance.cache_manager import MultiLevelCacheManager


class SectorCacheKeys:
    """板块数据缓存键的具体定义"""

    # 板块排行榜缓存
    RANKING_PATTERN = "sector:ranking:{date}:{sort_by}"
    # 示例: "sector:ranking:2023-12-01:main_net_inflow"

    # 单板块历史趋势缓存
    TREND_PATTERN = "sector:trend:{sector_id}:{period_days}"
    # 示例: "sector:trend:BK0001:30"

    # 板块分时数据缓存
    INTRADAY_PATTERN = "sector:intraday:{sector_id}:{date}"
    # 示例: "sector:intraday:BK0001:2023-12-01"

    # 板块统计汇总缓存
    STATS_PATTERN = "sector:stats:{date}:{stat_type}"
    # 示例: "sector:stats:2023-12-01:daily_summary"

    # 实际TTL配置（秒）
    TTL_CONFIG = {
        'realtime_ranking': 300,     # 实时排行榜：5分钟过期
        'daily_trend': 3600,         # 日度趋势：1小时过期
        'intraday_detail': 1800,     # 分时明细：30分钟过期
        'historical_stats': 86400    # 历史统计：24小时过期
    }

    @staticmethod
    def get_ranking_key(date: str, sort_by: str = "main_net_inflow") -> str:
        """生成排行榜缓存键"""
        return f"sector:ranking:{date}:{sort_by}"

    @staticmethod
    def get_trend_key(sector_id: str, period_days: int) -> str:
        """生成趋势数据缓存键"""
        return f"sector:trend:{sector_id}:{period_days}"

    @staticmethod
    def get_intraday_key(sector_id: str, date: str) -> str:
        """生成分时数据缓存键"""
        return f"sector:intraday:{sector_id}:{date}"


class SectorDataService:
    """
    板块数据服务类

    提供板块资金流数据的专门访问服务，集成缓存管理和数据库连接器。
    """

    def __init__(self, cache_manager: Optional[MultiLevelCacheManager] = None,
                 tet_pipeline: Optional[TETDataPipeline] = None):
        """
        初始化板块数据服务

        Args:
            cache_manager: 缓存管理器实例
            tet_pipeline: TET数据管道实例
        """
        self.cache_manager = cache_manager
        self.tet_pipeline = tet_pipeline
        self.table_manager = get_table_manager()
        self.duckdb_manager = initialize_duckdb_manager()
        self._initialized = False

        logger.info("SectorDataService 初始化完成")

    def initialize(self) -> bool:
        """
        初始化服务

        Returns:
            bool: 初始化是否成功
        """
        try:
            # 确保必要的表结构已创建
            self._ensure_sector_tables()
            self._initialized = True
            logger.info("SectorDataService 初始化成功")
            return True
        except Exception as e:
            logger.error(f"SectorDataService 初始化失败: {e}")
            logger.error(traceback.format_exc())
            return False

    def _ensure_sector_tables(self):
        """确保板块资金流表已创建"""
        try:
            # 检查板块日度表
            daily_schema = self.table_manager.get_schema(TableType.SECTOR_FUND_FLOW_DAILY)
            if daily_schema is None:
                logger.warning("板块日度资金流表结构未注册")
                return

            # 检查板块分时表
            intraday_schema = self.table_manager.get_schema(TableType.SECTOR_FUND_FLOW_INTRADAY)
            if intraday_schema is None:
                logger.warning("板块分时资金流表结构未注册")
                return

            logger.info("板块资金流表结构验证通过")
        except Exception as e:
            logger.error(f"验证板块表结构失败: {e}")
            raise

    def get_sector_fund_flow_ranking(self, date_range: str, sort_by: str = 'main_net_inflow') -> pd.DataFrame:
        """
        获取板块资金流排行榜

        Args:
            date_range: 时间范围，如 "today", "3d", "5d", "1m"
            sort_by: 排序字段，默认按主力净流入排序

        Returns:
            pd.DataFrame: 板块排行榜数据
        """
        try:
            # 解析日期范围
            target_date = self._parse_date_range(date_range)

            # 生成缓存键
            cache_key = SectorCacheKeys.get_ranking_key(target_date, sort_by)

            # 先尝试从缓存获取
            if self.cache_manager:
                cached_data = self.cache_manager.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"从缓存获取板块排行榜数据: {cache_key}")
                    return pd.DataFrame(cached_data)

            # 缓存未命中，从数据库查询
            data = self._query_ranking_from_database(target_date, sort_by)

            # 更新缓存
            if self.cache_manager and not data.empty:
                ttl = SectorCacheKeys.TTL_CONFIG['realtime_ranking']
                self.cache_manager.set(cache_key, data.to_dict('records'), ttl=ttl)
                logger.debug(f"板块排行榜数据已缓存: {cache_key}")

            return data

        except Exception as e:
            logger.error(f"获取板块资金流排行榜失败: {e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def get_sector_historical_trend(self, sector_id: str, period: int = 30) -> pd.DataFrame:
        """
        获取单板块历史趋势数据

        Args:
            sector_id: 板块ID，如 "BK0001"
            period: 查询天数，默认30天

        Returns:
            pd.DataFrame: 板块历史趋势数据
        """
        try:
            # 生成缓存键
            cache_key = SectorCacheKeys.get_trend_key(sector_id, period)

            # 先尝试从缓存获取
            if self.cache_manager:
                cached_data = self.cache_manager.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"从缓存获取板块趋势数据: {cache_key}")
                    return pd.DataFrame(cached_data)

            # 缓存未命中，从数据库查询
            data = self._query_trend_from_database(sector_id, period)

            # 更新缓存
            if self.cache_manager and not data.empty:
                ttl = SectorCacheKeys.TTL_CONFIG['daily_trend']
                self.cache_manager.set(cache_key, data.to_dict('records'), ttl=ttl)
                logger.debug(f"板块趋势数据已缓存: {cache_key}")

            return data

        except Exception as e:
            logger.error(f"获取板块历史趋势失败: sector_id={sector_id}, period={period}, error={e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def get_sector_intraday_flow(self, sector_id: str, date: str) -> pd.DataFrame:
        """
        获取板块分时资金流数据

        Args:
            sector_id: 板块ID，如 "BK0001"
            date: 查询日期，格式 "YYYY-MM-DD"

        Returns:
            pd.DataFrame: 板块分时资金流数据
        """
        try:
            # 生成缓存键
            cache_key = SectorCacheKeys.get_intraday_key(sector_id, date)

            # 先尝试从缓存获取
            if self.cache_manager:
                cached_data = self.cache_manager.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"从缓存获取板块分时数据: {cache_key}")
                    return pd.DataFrame(cached_data)

            # 缓存未命中，从数据库查询
            data = self._query_intraday_from_database(sector_id, date)

            # 更新缓存
            if self.cache_manager and not data.empty:
                ttl = SectorCacheKeys.TTL_CONFIG['intraday_detail']
                self.cache_manager.set(cache_key, data.to_dict('records'), ttl=ttl)
                logger.debug(f"板块分时数据已缓存: {cache_key}")

            return data

        except Exception as e:
            logger.error(f"获取板块分时资金流失败: sector_id={sector_id}, date={date}, error={e}")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def import_sector_historical_data(self, source: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        导入板块历史数据

        Args:
            source: 数据源名称，如 "akshare", "eastmoney"
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"

        Returns:
            Dict[str, Any]: 导入结果统计信息
        """
        try:
            logger.info(f"开始导入板块历史数据: source={source}, start_date={start_date}, end_date={end_date}")

            # 通过TET数据管道获取数据，失败时fallback到直接数据源
            result = None
            if self.tet_pipeline:
                result = self._import_via_tet_pipeline(source, start_date, end_date)
                if not result.get('success', False):
                    logger.warning(f"TET管道导入失败: {result.get('error', 'Unknown error')}, 回退到直接数据源")
                    result = self._import_via_direct_source(source, start_date, end_date)
            else:
                # 降级到直接数据源获取
                result = self._import_via_direct_source(source, start_date, end_date)

            logger.info(f"板块历史数据导入完成: {result}")
            return result

        except Exception as e:
            logger.error(f"导入板块历史数据失败: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "processed_count": 0,
                "failed_count": 0
            }

    def _parse_date_range(self, date_range: str) -> str:
        """
        解析日期范围到具体日期

        Args:
            date_range: 日期范围字符串

        Returns:
            str: 目标日期，格式 "YYYY-MM-DD"
        """
        today = datetime.now().date()

        if date_range.lower() in ["today", "1d"]:
            return today.strftime("%Y-%m-%d")
        elif date_range.lower() in ["3d"]:
            return (today - timedelta(days=3)).strftime("%Y-%m-%d")
        elif date_range.lower() in ["5d"]:
            return (today - timedelta(days=5)).strftime("%Y-%m-%d")
        elif date_range.lower() in ["1m", "30d"]:
            return (today - timedelta(days=30)).strftime("%Y-%m-%d")
        else:
            # 直接返回传入的日期字符串
            return date_range

    def _query_ranking_from_database(self, target_date: str, sort_by: str) -> pd.DataFrame:
        """
        从数据库查询板块排行榜数据

        Args:
            target_date: 目标日期
            sort_by: 排序字段

        Returns:
            pd.DataFrame: 查询结果
        """
        try:
            # 构造SQL查询
            sql = f"""
            SELECT 
                sector_id,
                sector_name,
                sector_code,
                trade_date,
                main_net_inflow,
                retail_net_inflow,
                total_turnover,
                stock_count,
                rise_count,
                fall_count,
                avg_change_pct,
                rank_by_amount,
                rank_by_ratio,
                data_source,
                data_quality_score
            FROM sector_fund_flow_daily 
            WHERE trade_date = '{target_date}'
            ORDER BY {sort_by} DESC
            LIMIT 100
            """

            # 执行查询（这里需要实际的数据库连接实现）
            # 临时返回空DataFrame，实际实现时需要连接DuckDB执行查询
            logger.warning("数据库查询功能待实现，返回空结果")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"数据库查询板块排行榜失败: {e}")
            return pd.DataFrame()

    def _query_trend_from_database(self, sector_id: str, period: int) -> pd.DataFrame:
        """
        从数据库查询板块趋势数据

        Args:
            sector_id: 板块ID
            period: 查询天数

        Returns:
            pd.DataFrame: 查询结果
        """
        try:
            # 计算开始日期
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=period)

            # 构造SQL查询
            sql = f"""
            SELECT 
                sector_id,
                sector_name,
                trade_date,
                main_net_inflow,
                retail_net_inflow,
                avg_change_pct,
                rank_by_amount,
                data_source
            FROM sector_fund_flow_daily 
            WHERE sector_id = '{sector_id}' 
              AND trade_date >= '{start_date}' 
              AND trade_date <= '{end_date}'
            ORDER BY trade_date ASC
            """

            # 执行查询（这里需要实际的数据库连接实现）
            logger.warning("数据库查询功能待实现，返回空结果")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"数据库查询板块趋势失败: {e}")
            return pd.DataFrame()

    def _query_intraday_from_database(self, sector_id: str, date: str) -> pd.DataFrame:
        """
        从数据库查询板块分时数据

        Args:
            sector_id: 板块ID
            date: 查询日期

        Returns:
            pd.DataFrame: 查询结果
        """
        try:
            # 构造SQL查询
            sql = f"""
            SELECT 
                sector_id,
                trade_date,
                trade_time,
                cumulative_main_inflow,
                cumulative_retail_inflow,
                interval_main_inflow,
                interval_retail_inflow,
                main_inflow_speed,
                active_degree,
                data_source
            FROM sector_fund_flow_intraday 
            WHERE sector_id = '{sector_id}' 
              AND trade_date = '{date}'
            ORDER BY trade_time ASC
            """

            # 执行查询（这里需要实际的数据库连接实现）
            logger.warning("数据库查询功能待实现，返回空结果")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"数据库查询板块分时数据失败: {e}")
            return pd.DataFrame()

    def _import_via_tet_pipeline(self, source: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        通过TET数据管道导入数据

        Args:
            source: 数据源
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict[str, Any]: 导入结果
        """
        try:
            # 构造TET查询
            query = StandardQuery(
                asset_type=AssetType.SECTOR,
                data_type=DataType.SECTOR_FUND_FLOW,
                symbol="",  # 空表示所有板块
                extra_params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_source": source
                }
            )

            # 执行TET管道处理
            result = self.tet_pipeline.process(query)

            if result and result.success:
                # 将数据写入数据库
                processed_count = self._batch_insert_sector_data(result.data)

                return {
                    "success": True,
                    "processed_count": processed_count,
                    "failed_count": 0,
                    "source": source,
                    "date_range": f"{start_date} to {end_date}"
                }
            else:
                logger.warning(f"TET管道处理失败: {result.error if result else 'Unknown error'}")
                return {
                    "success": False,
                    "error": result.error if result else "TET pipeline failed",
                    "processed_count": 0,
                    "failed_count": 1
                }

        except Exception as e:
            logger.error(f"TET管道导入失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "processed_count": 0,
                "failed_count": 1
            }

    def _import_via_direct_source(self, source: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        直接从数据源导入数据（降级方案）

        Args:
            source: 数据源
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict[str, Any]: 导入结果
        """
        try:
            logger.info(f"使用直接数据源导入: {source}")

            if source.lower() == "akshare":
                from plugins.data_sources.stock.akshare_plugin import AKSharePlugin
                from core.plugin_types import AssetType

                akshare_plugin = AKSharePlugin()
                akshare_plugin.initialize()

                periods = ["今日", "3日", "5日", "10日", "20日"]
                total_processed = 0

                for period in periods:
                    try:
                        logger.info(f"获取{period}板块资金流数据...")
                        df = akshare_plugin.get_sector_fund_flow_data(data_type=period)

                        if df is not None and not df.empty:
                            processed_count = self._process_and_store_sector_data(df, period, start_date, end_date)
                            total_processed += processed_count
                            logger.info(f"{period}数据处理完成: {processed_count} 条")
                        else:
                            logger.warning(f"{period}未获取到数据")
                    except Exception as e:
                        logger.error(f"获取{period}数据失败: {e}")
                        continue

                return {
                    "success": total_processed > 0,
                    "error": None if total_processed > 0 else "未获取到任何数据",
                    "processed_count": total_processed,
                    "failed_count": 0 if total_processed > 0 else 1
                }

            else:
                logger.warning(f"暂不支持的数据源: {source}")
                return {
                    "success": False,
                    "error": f"不支持的数据源: {source}",
                    "processed_count": 0,
                    "failed_count": 1
                }

        except Exception as e:
            logger.error(f"直接数据源导入失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "processed_count": 0,
                "failed_count": 1
            }

    def _process_and_store_sector_data(self, df: pd.DataFrame, period: str, start_date: str, end_date: str) -> int:
        """
        处理和存储板块数据

        Args:
            df: 原始数据DataFrame
            period: 数据周期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            int: 处理的数据条数
        """
        try:
            if df.empty:
                return 0

            # 标准化数据格式
            processed_df = self._standardize_sector_data(df, period)

            if processed_df.empty:
                return 0

            # 插入数据库
            return self._batch_insert_sector_data(processed_df)

        except Exception as e:
            logger.error(f"处理和存储板块数据失败: {e}")
            return 0

    def _standardize_sector_data(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """
        标准化板块数据格式

        Args:
            df: 原始数据
            period: 数据周期

        Returns:
            pd.DataFrame: 标准化后的数据
        """
        try:
            # 创建标准化数据框
            standardized_data = []
            current_date = datetime.now().strftime('%Y-%m-%d')

            for _, row in df.iterrows():
                record = {
                    'date': current_date,
                    'sector_name': row.get('名称', ''),
                    'sector_code': row.get('代码', ''),
                    'period': period,
                    'main_net_inflow': self._safe_float_convert(row.get('主力净流入', 0)),
                    'main_net_inflow_ratio': self._safe_float_convert(row.get('主力净流入占比', 0)),
                    'super_large_net_inflow': self._safe_float_convert(row.get('超大单净流入', 0)),
                    'large_net_inflow': self._safe_float_convert(row.get('大单净流入', 0)),
                    'medium_net_inflow': self._safe_float_convert(row.get('中单净流入', 0)),
                    'small_net_inflow': self._safe_float_convert(row.get('小单净流入', 0)),
                    'change_percent': self._safe_float_convert(row.get('涨跌幅', 0)),
                    'turnover_rate': self._safe_float_convert(row.get('换手率', 0)),
                    'volume': self._safe_float_convert(row.get('成交量', 0)),
                    'amount': self._safe_float_convert(row.get('成交额', 0)),
                    'created_at': datetime.now().isoformat()
                }
                standardized_data.append(record)

            return pd.DataFrame(standardized_data)

        except Exception as e:
            logger.error(f"标准化板块数据失败: {e}")
            return pd.DataFrame()

    def _safe_float_convert(self, value) -> float:
        """安全转换为浮点数"""
        try:
            if pd.isna(value) or value is None:
                return 0.0
            if isinstance(value, str):
                # 处理百分比符号
                value = value.replace('%', '').replace(',', '')
                # 处理中文数字单位
                if '万' in value:
                    value = value.replace('万', '')
                    return float(value) * 10000
                elif '亿' in value:
                    value = value.replace('亿', '')
                    return float(value) * 100000000
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _batch_insert_sector_data(self, data: pd.DataFrame) -> int:
        """
        批量插入板块数据到数据库

        Args:
            data: 要插入的数据DataFrame

        Returns:
            int: 成功插入的记录数
        """
        try:
            if data.empty:
                return 0

            if not self.duckdb_manager:
                logger.warning("DuckDB管理器不可用，无法插入数据")
                return 0

            # 获取数据库连接
            conn = self.duckdb_manager.get_connection()
            if not conn:
                logger.warning("无法获取数据库连接")
                return 0

            # 插入到日度表（主要用于板块资金流）
            table_name = "sector_fund_flow_daily"

            # 构建插入SQL
            columns = [
                'date', 'sector_name', 'sector_code', 'period',
                'main_net_inflow', 'main_net_inflow_ratio',
                'super_large_net_inflow', 'large_net_inflow',
                'medium_net_inflow', 'small_net_inflow',
                'change_percent', 'turnover_rate',
                'volume', 'amount', 'created_at'
            ]

            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)

            insert_sql = f"""
                INSERT INTO {table_name} ({column_names})
                VALUES ({placeholders})
            """

            # 准备批量插入的数据
            records = []
            for _, row in data.iterrows():
                record = tuple(row[col] for col in columns)
                records.append(record)

            # 执行批量插入
            conn.executemany(insert_sql, records)

            logger.info(f"成功插入 {len(records)} 条板块资金流数据到表 {table_name}")
            return len(records)

        except Exception as e:
            logger.error(f"批量插入板块数据失败: {e}")
            return 0

    def invalidate_sector_cache(self, sector_id: str):
        """
        失效指定板块的相关缓存

        Args:
            sector_id: 板块ID
        """
        if not self.cache_manager:
            return

        try:
            # 删除该板块相关的所有缓存
            pattern = f"sector:*:{sector_id}:*"
            deleted_count = self.cache_manager.delete_pattern(pattern)
            logger.info(f"已失效板块 {sector_id} 的 {deleted_count} 个缓存条目")
        except Exception as e:
            logger.error(f"失效板块缓存失败: sector_id={sector_id}, error={e}")

    def get_service_status(self) -> Dict[str, Any]:
        """
        获取服务状态

        Returns:
            Dict[str, Any]: 服务状态信息
        """
        return {
            "initialized": self._initialized,
            "cache_manager_available": self.cache_manager is not None,
            "tet_pipeline_available": self.tet_pipeline is not None,
            "table_manager_available": self.table_manager is not None
        }

    def cleanup(self):
        """清理资源"""
        try:
            logger.info("SectorDataService 资源清理完成")
        except Exception as e:
            logger.error(f"SectorDataService 资源清理失败: {e}")


# 全局服务实例
_sector_data_service: Optional[SectorDataService] = None


def get_sector_data_service(cache_manager: Optional[MultiLevelCacheManager] = None,
                            tet_pipeline: Optional[TETDataPipeline] = None) -> SectorDataService:
    """
    获取板块数据服务的全局实例

    Args:
        cache_manager: 缓存管理器
        tet_pipeline: TET数据管道

    Returns:
        SectorDataService: 服务实例
    """
    global _sector_data_service

    if _sector_data_service is None:
        _sector_data_service = SectorDataService(cache_manager, tet_pipeline)
        _sector_data_service.initialize()

    return _sector_data_service
