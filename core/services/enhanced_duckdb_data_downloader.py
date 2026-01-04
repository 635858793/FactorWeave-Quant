"""
增强DuckDB数据下载服务

专门用于替代FactorWeave-Quant的数据下载功能，提供：
1. 历史K线数据下载和存储
2. 基本面数据下载和存储
3. 实时数据缓存和管理
4. 数据质量验证和清洗
5. 智能增量更新
6. 多数据源聚合

作者: FactorWeave-Quant 开发团队
版本: 2.0.0
日期: 2025
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple
import pandas as pd
import json
from loguru import logger
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

from ..database.duckdb_manager import get_connection_manager
from ..database.duckdb_operations import get_duckdb_operations
from ..database.table_manager import DynamicTableManager
from ..plugin_types import AssetType, DataType
from ..tet_data_pipeline import StandardQuery, TETDataPipeline
from ..data_source_router import DataSourceRouter
from ..asset_database_manager import AssetSeparatedDatabaseManager
from .uni_plugin_data_manager import UniPluginDataManager
from .incremental_data_analyzer import IncrementalDataAnalyzer, DownloadStrategy
from .data_completeness_checker import DataCompletenessChecker
from .incremental_update_recorder import IncrementalUpdateRecorder, UpdateType, UpdateStatus

logger = logger.bind(module=__name__)


class EnhancedDuckDBDataDownloader:
    """
    增强DuckDB数据下载器

    替代FactorWeave-Quant的核心数据获取功能，通过TET框架和插件系统
    实现多数据源的数据下载、存储和管理。新增智能增量下载功能。
    """

    def __init__(self, uni_plugin_manager: UniPluginDataManager,
                 tet_pipeline: TETDataPipeline = None,
                 data_source_router: DataSourceRouter = None,
                 incremental_analyzer: IncrementalDataAnalyzer = None,
                 completeness_checker: DataCompletenessChecker = None,
                 update_recorder: IncrementalUpdateRecorder = None):
        self.uni_plugin_manager = uni_plugin_manager
        self.tet_pipeline = tet_pipeline
        self.data_source_router = data_source_router
        self.incremental_analyzer = incremental_analyzer
        self.completeness_checker = completeness_checker
        self.update_recorder = update_recorder

        self.duckdb_manager = get_connection_manager()
        self.duckdb_operations = get_duckdb_operations()
        self.table_manager = DynamicTableManager()

        # 资产分离数据库管理器
        self.asset_db_manager = AssetSeparatedDatabaseManager.get_instance()

        # 确保数据库目录存在
        base_path = Path("data/databases")
        for asset_type in AssetType:
            db_path = self.asset_db_manager.get_database_path(asset_type)
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 配置参数
        self.config = {
            'batch_size': 100,
            'max_workers': 5,
            'retry_count': 3,
            'retry_delay': 1.0,
            'timeout': 30.0,
            'skip_weekends': True,
            'skip_holidays': True,
            'conflict_resolution': 'replace'
        }

        # 下载缓存
        self._download_cache = {}
        self.executor = ThreadPoolExecutor(max_workers=self.config['max_workers'])

        logger.info("EnhancedDuckDBDataDownloader 初始化完成")

    async def download_historical_kline_data(self,
                                             symbols: List[str],
                                             period: str = 'D',
                                             start_date: Optional[datetime] = None,
                                             end_date: Optional[datetime] = None,
                                             asset_type: AssetType = AssetType.STOCK_A,
                                             force_update: bool = False) -> Dict[str, pd.DataFrame]:
        """
        下载历史K线数据到DuckDB

        Args:
            symbols: 股票代码列表
            period: 周期 (D, W, M, 1m, 5m, 15m, 30m, 60m)
            start_date: 开始日期
            end_date: 结束日期
            asset_type: 资产类型
            force_update: 强制更新

        Returns:
            Dict[symbol, DataFrame]: 下载的数据
        """
        logger.info(f"开始下载历史K线数据: {len(symbols)}只股票, 周期={period}")

        # 设置默认日期范围
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=365 * 2)  # 默认2年数据

        results = {}

        for symbol in symbols:
            try:
                # 检查是否需要更新
                if not force_update:
                    latest_date = await self._get_latest_data_date(symbol, period, asset_type)
                    if latest_date and (end_date - latest_date).days < 1:
                        logger.debug(f"股票 {symbol} 数据已是最新，跳过下载")
                        continue

                # 通过TET框架获取数据
                query = StandardQuery(
                    symbol=symbol,
                    data_type=DataType.HISTORICAL_KLINE,
                    asset_type=asset_type,
                    start_date=start_date,
                    end_date=end_date,
                    extra_params={'period': period}
                )

                context = await self.uni_plugin_manager.create_request_context(query)
                data = await self.uni_plugin_manager.execute_data_request(context)

                if data is not None and not data.empty:
                    # 数据质量验证
                    cleaned_data = self._validate_and_clean_kline_data(data, symbol)

                    if not cleaned_data.empty:
                        # 存储到DuckDB
                        await self._store_kline_data_to_duckdb(cleaned_data, symbol, period, asset_type)
                        results[symbol] = cleaned_data
                        logger.info(f"成功下载并存储 {symbol} K线数据: {len(cleaned_data)} 条")
                    else:
                        logger.warning(f"股票 {symbol} 数据质量验证失败")
                else:
                    logger.warning(f"未获取到股票 {symbol} 的K线数据")

            except Exception as e:
                logger.error(f"下载股票 {symbol} K线数据失败: {e}")

        logger.info(f"历史K线数据下载完成: 成功 {len(results)}/{len(symbols)} 只股票")
        return results

    async def download_fundamental_data(self,
                                        symbols: List[str],
                                        data_types: List[str] = None,
                                        asset_type: AssetType = AssetType.STOCK_A) -> Dict[str, Dict[str, Any]]:
        """
        下载基本面数据到DuckDB

        Args:
            symbols: 股票代码列表
            data_types: 数据类型列表 ['financial_statement', 'announcement', 'analyst_rating']
            asset_type: 资产类型

        Returns:
            Dict[symbol, Dict[data_type, data]]: 下载的数据
        """
        if not data_types:
            data_types = ['financial_statement', 'announcement', 'analyst_rating']

        logger.info(f"开始下载基本面数据: {len(symbols)}只股票, 类型={data_types}")

        results = {}

        for symbol in symbols:
            symbol_results = {}

            for data_type in data_types:
                try:
                    # 构建查询
                    if data_type == 'financial_statement':
                        query_data_type = DataType.FINANCIAL_STATEMENT
                    elif data_type == 'announcement':
                        query_data_type = DataType.ANNOUNCEMENT
                    elif data_type == 'analyst_rating':
                        query_data_type = DataType.ANALYST_RATING
                    else:
                        continue

                    query = StandardQuery(
                        symbol=symbol,
                        data_type=query_data_type,
                        asset_type=asset_type,
                        extra_params={'periods': 4}  # 获取最近4期数据
                    )

                    context = await self.uni_plugin_manager.create_request_context(query)
                    data = await self.uni_plugin_manager.execute_data_request(context)

                    if data is not None:
                        # 存储到DuckDB
                        await self._store_fundamental_data_to_duckdb(data, symbol, data_type)
                        symbol_results[data_type] = data
                        logger.debug(f"成功下载 {symbol} {data_type} 数据")

                except Exception as e:
                    logger.error(f"下载 {symbol} {data_type} 数据失败: {e}")

            if symbol_results:
                results[symbol] = symbol_results

        logger.info(f"基本面数据下载完成: 成功 {len(results)}/{len(symbols)} 只股票")
        return results

    async def download_stock_list(self,
                                  market: str = 'all',
                                  asset_type: AssetType = AssetType.STOCK_A) -> pd.DataFrame:
        """
        下载股票列表到DuckDB

        Args:
            market: 市场代码 ('sh', 'sz', 'bj', 'all')
            asset_type: 资产类型

        Returns:
            DataFrame: 股票列表数据
        """
        logger.info(f"开始下载股票列表: 市场={market}")

        try:
            # 通过TET框架获取股票列表
            query = StandardQuery(
                symbol="",  # 股票列表不需要具体代码
                data_type=DataType.ASSET_LIST,
                asset_type=asset_type,
                extra_params={'market': market}
            )

            context = await self.uni_plugin_manager.create_request_context(query)
            data = await self.uni_plugin_manager.execute_data_request(context)

            if data is not None and not data.empty:
                # 数据清洗和标准化
                cleaned_data = self._validate_and_clean_stock_list(data)

                # 存储到DuckDB
                await self._store_stock_list_to_duckdb(cleaned_data, market)

                logger.info(f"成功下载股票列表: {len(cleaned_data)} 只股票")
                return cleaned_data
            else:
                logger.warning("未获取到股票列表数据")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"下载股票列表失败: {e}")
            return pd.DataFrame()

    async def incremental_update_all_data(self,
                                          symbols: Optional[List[str]] = None,
                                          max_symbols: int = 100) -> Dict[str, Any]:
        """
        增量更新所有数据

        Args:
            symbols: 指定股票列表，None则自动获取
            max_symbols: 最大处理股票数量

        Returns:
            Dict: 更新结果统计
        """
        logger.info("开始增量更新所有数据")

        # 获取股票列表
        if not symbols:
            stock_df = await self.download_stock_list()
            if not stock_df.empty:
                symbols = stock_df['code'].head(max_symbols).tolist()
            else:
                logger.error("无法获取股票列表，增量更新失败")
                return {}

        results = {
            'kline_updated': 0,
            'fundamental_updated': 0,
            'errors': []
        }

        # 更新K线数据
        try:
            kline_results = await self.download_historical_kline_data(
                symbols=symbols,
                period='D',
                start_date=datetime.now() - timedelta(days=7),  # 最近一周
                force_update=False
            )
            results['kline_updated'] = len(kline_results)
        except Exception as e:
            results['errors'].append(f"K线数据更新失败: {e}")

        # 更新基本面数据
        try:
            fundamental_results = await self.download_fundamental_data(
                symbols=symbols[:20],  # 基本面数据更新较慢，限制数量
                data_types=['financial_statement']
            )
            results['fundamental_updated'] = len(fundamental_results)
        except Exception as e:
            results['errors'].append(f"基本面数据更新失败: {e}")

        logger.info(f"增量更新完成: K线={results['kline_updated']}, 基本面={results['fundamental_updated']}")
        return results

    async def download_incremental_data(
        self,
        symbols: List[str],
        end_date: datetime,
        strategy: DownloadStrategy = None,
        task_name: str = None,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        """
        智能增量下载功能

        Args:
            symbols: 股票代码列表
            end_date: 结束日期
            strategy: 下载策略
            task_name: 任务名称
            progress_callback: 进度回调

        Returns:
            Dict: 下载结果统计
        """
        start_time = datetime.now()

        if not self.incremental_analyzer or not self.completeness_checker or not self.update_recorder:
            logger.error("缺少必要的组件进行智能增量下载")
            raise RuntimeError("智能增量下载需要配置 incremental_analyzer, completeness_checker, update_recorder")

        if strategy is None:
            strategy = DownloadStrategy.LATEST_ONLY

        task_name = task_name or f"智能增量下载 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # 创建任务跟踪
        task_id = self.update_recorder.create_update_task(
            task_name=task_name,
            symbols=symbols,
            date_range=(end_date - timedelta(days=30), end_date),
            update_type=UpdateType.INCREMENTAL,
            strategy=strategy.value
        )

        # 开始任务
        self.update_recorder.start_task(task_id)

        try:
            # 分析增量需求
            download_plan = await self.incremental_analyzer.analyze_incremental_requirements(
                symbols, end_date, strategy,
                self.config['skip_weekends'], self.config['skip_holidays']
            )

            # 更新任务信息
            self.update_recorder.update_task_progress(
                task_id, 0, 0, 0, 0, 0, 0.0, download_plan.symbols_to_skip_reason
            )

            # 下载符号数据
            success_count = 0
            failed_count = 0
            skipped_count = len(download_plan.symbols_to_skip)
            total_records = 0

            if not download_plan.symbols_to_download:
                logger.info("没有需要下载的股票")
                self.update_recorder.complete_task(task_id, 0, 0)
                return {
                    'task_id': task_id,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'skipped_count': skipped_count,
                    'total_records': total_records,
                    'execution_time': 0
                }

            # 分批处理符号
            for i in range(0, len(download_plan.symbols_to_download), self.config['batch_size']):
                batch = download_plan.symbols_to_download[i:i + self.config['batch_size']]

                batch_results = await self._download_symbol_batch(
                    batch, download_plan.download_ranges, strategy
                )

                # 更新统计信息
                success_count += batch_results['success_count']
                failed_count += batch_results['failed_count']
                total_records += batch_results['total_records']

                # 更新进度
                completed_symbols = success_count + failed_count
                total_symbols = len(download_plan.symbols_to_download)
                progress = (completed_symbols / total_symbols) * 100

                self.update_recorder.update_task_progress(
                    task_id, completed_symbols, success_count, failed_count,
                    skipped_count, total_records, progress
                )

                # 调用进度回调
                if progress_callback:
                    progress_callback(progress, completed_symbols, total_symbols)

            # 完成任务
            execution_time = (datetime.now() - start_time).total_seconds()
            self.update_recorder.complete_task(task_id, total_records, execution_time)

            return {
                'task_id': task_id,
                'success_count': success_count,
                'failed_count': failed_count,
                'skipped_count': skipped_count,
                'total_records': total_records,
                'execution_time': execution_time
            }

        except Exception as e:
            logger.error(f"智能增量下载失败: {str(e)}")
            self.update_recorder.fail_task(task_id, str(e))
            raise

    async def _download_symbol_batch(
        self,
        symbols: List[str],
        download_ranges: Dict[str, Tuple[datetime, datetime]],
        strategy: DownloadStrategy
    ) -> Dict[str, int]:
        """
        下载一批符号数据

        Args:
            symbols: 符号列表
            download_ranges: 下载范围
            strategy: 下载策略

        Returns:
            Dict: 批下载结果
        """
        success_count = 0
        failed_count = 0
        total_records = 0
        error_messages = {}

        # 创建下载任务
        tasks = []
        for symbol in symbols:
            task = self._download_single_symbol(
                symbol, download_ranges[symbol], strategy
            )
            tasks.append(task)

        # 并发执行任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, Exception):
                logger.error(f"下载 {symbol} 失败: {str(result)}")
                failed_count += 1
                error_messages[symbol] = str(result)
            else:
                success_count += 1
                total_records += result['records_count']

        # 存储错误消息
        if error_messages:
            self.update_recorder.update_task_progress(
                '', 0, success_count, failed_count, 0, 0, 0.0, error_messages
            )

        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'total_records': total_records
        }

    async def _download_single_symbol(
        self,
        symbol: str,
        download_range: Tuple[datetime, datetime],
        strategy: DownloadStrategy
    ) -> Dict[str, int]:
        """
        下载单个符号数据

        Args:
            symbol: 股票符号
            download_range: 下载范围
            strategy: 下载策略

        Returns:
            Dict: 下载结果
        """
        start_date, end_date = download_range

        try:
            # 构建查询
            query = StandardQuery(
                symbol=symbol,
                data_type=DataType.HISTORICAL_KLINE,
                asset_type=AssetType.STOCK_A,
                start_date=start_date,
                end_date=end_date,
                extra_params={'period': 'D'}  # 日线数据
            )

            # 获取数据源
            if self.data_source_router:
                data_source = self.data_source_router.get_best_data_source('HISTORICAL_KLINE')
            else:
                # 通过插件管理器获取
                context = await self.uni_plugin_manager.create_request_context(query)
                data = await self.uni_plugin_manager.execute_data_request(context)

            if data is None or data.empty:
                logger.info(f"未获取到 {symbol} 的数据 (范围: {start_date} 到 {end_date})")
                return {'records_count': 0}

            # 转换数据格式
            if hasattr(data, 'empty') and data.empty:
                return {'records_count': 0}

            # 数据质量验证
            cleaned_data = self._validate_and_clean_kline_data(data, symbol)
            if cleaned_data.empty:
                logger.warning(f"{symbol} 数据质量验证失败")
                return {'records_count': 0}

            # 存储数据（智能增量存储）
            records_count = await self._store_kline_data_incremental(cleaned_data, symbol, strategy)

            logger.info(f"下载并存储 {symbol} 数据: {records_count} 条")

            return {'records_count': records_count}

        except Exception as e:
            logger.error(f"下载 {symbol} 数据失败: {str(e)}")
            raise

    async def download_incremental_update_all_data(
        self,
        days: int = 7,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        """
        全量智能增量更新所有数据

        Args:
            days: 回溯天数
            progress_callback: 进度回调

        Returns:
            Dict: 更新结果统计
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 获取数据库中的所有股票代码
        try:
            stock_df = await self._get_symbols_from_database()
            symbols = stock_df['code'].tolist() if not stock_df.empty else []
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            symbols = []

        if not symbols:
            logger.warning("数据库中没有找到股票")
            return {
                'success_count': 0,
                'failed_count': 0,
                'skipped_count': 0,
                'total_records': 0,
                'execution_time': 0
            }

        # 智能增量下载
        return await self.download_incremental_data(
            symbols=symbols,
            end_date=end_date,
            strategy=DownloadStrategy.LATEST_ONLY,
            task_name=f"全量增量更新 - {days} 天",
            progress_callback=progress_callback
        )

    async def check_and_fill_data_gaps(
        self,
        symbols: List[str],
        end_date: datetime,
        gap_threshold_days: int = 30
    ) -> Dict[str, Any]:
        """
        检查并填充数据间隙

        Args:
            symbols: 股票代码列表
            end_date: 结束日期
            gap_threshold_days: 最大间隙天数

        Returns:
            Dict: 间隙填充结果
        """
        start_time = datetime.now()
        task_id = self.update_recorder.create_update_task(
            task_name=f"数据间隙填充 - {len(symbols)} 只股票",
            symbols=symbols,
            date_range=(end_date - timedelta(days=gap_threshold_days), end_date),
            update_type=UpdateType.GAP_FILL,
            strategy="gap_fill"
        )

        self.update_recorder.start_task(task_id)

        try:
            success_count = 0
            failed_count = 0
            total_records = 0
            total_gaps_filled = 0

            for symbol in symbols:
                try:
                    if not self.completeness_checker:
                        raise RuntimeError("completeness_checker 未配置")

                    # 检查数据间隙
                    completeness_result = await self.completeness_checker.check_completeness(
                        symbol, end_date - timedelta(days=gap_threshold_days), end_date
                    )

                    if not completeness_result.missing_dates:
                        logger.info(f"未发现 {symbol} 的数据间隙")
                        continue

                    # 填充间隙
                    download_range = (
                        min(completeness_result.missing_dates),
                        max(completeness_result.missing_dates)
                    )

                    raw_data = await self._download_single_symbol_data(
                        symbol, download_range, DownloadStrategy.GAP_FILL
                    )

                    if raw_data is not None and not raw_data.empty:
                        cleaned_data = self._validate_and_clean_kline_data(raw_data, symbol)
                        records_count = await self._store_kline_data_incremental(
                            cleaned_data, symbol, DownloadStrategy.GAP_FILL
                        )

                        total_records += records_count
                        total_gaps_filled += len(completeness_result.missing_dates)
                        success_count += 1

                        logger.info(f"填充 {symbol} 的 {len(completeness_result.missing_dates)} 个间隙")

                except Exception as e:
                    logger.error(f"填充 {symbol} 数据间隙失败: {str(e)}")
                    failed_count += 1

            # 完成任务
            execution_time = (datetime.now() - start_time).total_seconds()
            self.update_recorder.complete_task(task_id, total_records, execution_time)

            return {
                'success_count': success_count,
                'failed_count': failed_count,
                'total_records': total_records,
                'total_gaps_filled': total_gaps_filled,
                'execution_time': execution_time
            }

        except Exception as e:
            logger.error(f"数据间隙填充失败: {str(e)}")
            self.update_recorder.fail_task(task_id, str(e))
            raise

    async def _download_single_symbol_data(
        self,
        symbol: str,
        download_range: Tuple[datetime, datetime],
        strategy: DownloadStrategy
    ) -> pd.DataFrame:
        """
        下载单个符号原始数据（辅助方法）

        Args:
            symbol: 股票符号
            download_range: 下载范围
            strategy: 下载策略

        Returns:
            DataFrame: 原始数据
        """
        start_date, end_date = download_range

        query = StandardQuery(
            symbol=symbol,
            data_type=DataType.HISTORICAL_KLINE,
            asset_type=AssetType.STOCK_A,
            start_date=start_date,
            end_date=end_date,
            extra_params={'period': 'D'}
        )

        if self.data_source_router:
            data_source = self.data_source_router.get_best_data_source('HISTORICAL_KLINE')
            if self.tet_pipeline:
                data = await self.tet_pipeline.process_request(query, data_source)
            else:
                raise RuntimeError("tet_pipeline 未配置")
        else:
            # 通过插件管理器获取
            context = await self.uni_plugin_manager.create_request_context(query)
            data = await self.uni_plugin_manager.execute_data_request(context)

        return data if data is not None else pd.DataFrame()

    async def _get_symbols_from_database(self, asset_type: AssetType = AssetType.STOCK_A) -> pd.DataFrame:
        """从数据库获取股票列表"""
        try:
            db_path = self.asset_db_manager.get_database_path(asset_type)
            query = "SELECT DISTINCT code FROM stock_list WHERE market_filter IS NULL OR market_filter = 'all'"

            result = self.duckdb_operations.execute_query(db_path, query)
            return result if result is not None and not result.empty else pd.DataFrame()

        except Exception as e:
            logger.error(f"从数据库获取股票列表失败: {e}")
            return pd.DataFrame()

    async def _store_kline_data_incremental(
        self,
        data: pd.DataFrame,
        symbol: str,
        strategy: DownloadStrategy
    ) -> int:
        """
        智能增量存储K线数据

        Args:
            data: K线数据
            symbol: 股票符号
            strategy: 下载策略

        Returns:
            int: 存储的记录数
        """
        if data.empty:
            return 0

        # 按日期排序
        data = data.sort_values('datetime')

        # 分块批量插入
        chunk_size = 1000
        total_stored = 0

        for i in range(0, len(data), chunk_size):
            chunk = data.iloc[i:i + chunk_size]

            # 转换为元组列表
            records = []
            for _, row in chunk.iterrows():
                records.append((
                    row['symbol'],
                    row['datetime'],
                    row['open'],
                    row['high'],
                    row['low'],
                    row['close'],
                    row['volume'],
                    row['amount']
                ))

            # 智能冲突解决
            try:
                for record in records:
                    query = """
                    INSERT INTO kline_data_daily
                    (symbol, datetime, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, datetime) DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        volume = excluded.volume,
                        amount = excluded.amount
                    """
                    self.duckdb_operations.execute_query(self.asset_db_manager.get_database_path(AssetType.STOCK_A), query, record)

                total_stored += len(records)

            except Exception as e:
                logger.error(f"批量存储 {symbol} 数据失败: {str(e)}")
                # 尝试单条插入
                for record in records:
                    try:
                        query = """
                        INSERT INTO kline_data_daily
                        (symbol, datetime, open, high, low, close, volume, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(symbol, datetime) DO UPDATE SET
                            open = excluded.open,
                            high = excluded.high,
                            low = excluded.low,
                            close = excluded.close,
                            volume = excluded.volume,
                            amount = excluded.amount
                        """
                        self.duckdb_operations.execute_query(self.asset_db_manager.get_database_path(AssetType.STOCK_A), query, record)
                        total_stored += 1
                    except Exception as inner_e:
                        logger.warning(f"存储 {symbol} 单条记录失败: {str(inner_e)}")
                        continue

        return total_stored

    def _validate_and_clean_kline_data(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """验证和清洗K线数据"""
        try:
            if data.empty:
                return data

            # 必需字段检查
            required_fields = ['open', 'high', 'low', 'close', 'volume']
            missing_fields = [f for f in required_fields if f not in data.columns]
            if missing_fields:
                logger.warning(f"股票 {symbol} K线数据缺少字段: {missing_fields}")
                return pd.DataFrame()

            # 数据类型转换
            for field in required_fields:
                data[field] = pd.to_numeric(data[field], errors='coerce')

            # 异常值过滤
            data = data.dropna(subset=required_fields)
            data = data[(data['high'] >= data['low']) &
                        (data['high'] >= data['open']) &
                        (data['high'] >= data['close']) &
                        (data['low'] <= data['open']) &
                        (data['low'] <= data['close']) &
                        (data['volume'] >= 0)]

            # 添加股票代码
            data['symbol'] = symbol

            return data

        except Exception as e:
            logger.error(f"K线数据验证失败 {symbol}: {e}")
            return pd.DataFrame()

    def _validate_and_clean_stock_list(self, data: pd.DataFrame) -> pd.DataFrame:
        """验证和清洗股票列表数据"""
        try:
            if data.empty:
                return data

            # 必需字段检查
            required_fields = ['code', 'name']
            for field in required_fields:
                if field not in data.columns:
                    logger.warning(f"股票列表缺少字段: {field}")
                    return pd.DataFrame()

            # 去重和清洗
            data = data.drop_duplicates(subset=['code'])
            data = data.dropna(subset=['code', 'name'])

            # 确保必要字段存在
            if 'market' not in data.columns:
                data['market'] = data['code'].str[:2]  # 从代码推断市场
            if 'industry' not in data.columns:
                data['industry'] = '其他'

            return data

        except Exception as e:
            logger.error(f"股票列表数据验证失败: {e}")
            return pd.DataFrame()

    async def _get_latest_data_date(self, symbol: str, period: str, data_category: str, asset_type: AssetType = AssetType.STOCK_A) -> Optional[datetime]:
        """获取最新数据日期"""
        try:
            db_path = self.asset_db_manager.get_database_path(asset_type)
            if not db_path:
                return None

            query = f"""
                SELECT MAX(datetime) as latest_date 
                FROM kline_data_{period.lower()} 
                WHERE symbol = ?
            """

            result = self.duckdb_operations.execute_query(db_path, query, [symbol])
            if not result.empty and result.iloc[0]['latest_date']:
                return pd.to_datetime(result.iloc[0]['latest_date'])

        except Exception as e:
            logger.debug(f"获取最新数据日期失败 {symbol}: {e}")

        return None

    async def _store_kline_data_to_duckdb(self, data: pd.DataFrame, symbol: str, period: str, asset_type: AssetType = AssetType.STOCK_A):
        """存储K线数据到DuckDB"""
        try:
            db_path = self.asset_db_manager.get_database_path(asset_type)
            table_name = f"kline_data_{period.lower()}"

            # 确保表存在
            await self.table_manager.ensure_table_exists(
                db_path, 'kline', 'enhanced_duckdb_downloader', period
            )

            # 插入数据
            result = self.duckdb_operations.insert_dataframe(
                database_path=db_path,
                table_name=table_name,
                dataframe=data,
                conflict_resolution='replace'
            )

            if result.get('success'):
                logger.debug(f"K线数据存储成功: {symbol}, {len(data)} 条")
            else:
                logger.warning(f"K线数据存储失败: {symbol}")

        except Exception as e:
            logger.error(f"存储K线数据失败 {symbol}: {e}")

    async def _store_fundamental_data_to_duckdb(self, data: Any, symbol: str, data_type: str, asset_type: AssetType = AssetType.STOCK_A):
        """存储基本面数据到DuckDB"""
        try:
            db_path = self.asset_db_manager.get_database_path(asset_type)

            if data_type == 'financial_statement':
                table_name = "financial_statements"
            elif data_type == 'announcement':
                table_name = "company_announcements"
            elif data_type == 'analyst_rating':
                table_name = "analyst_ratings"
            else:
                return

            # 确保表存在
            await self.table_manager.ensure_table_exists(
                db_path, data_type, 'enhanced_duckdb_downloader'
            )

            # 转换数据格式
            if isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            df['symbol'] = symbol
            df['update_time'] = datetime.now()

            # 插入数据
            result = self.duckdb_operations.insert_dataframe(
                database_path=db_path,
                table_name=table_name,
                dataframe=df,
                conflict_resolution='replace'
            )

            if result.get('success'):
                logger.debug(f"基本面数据存储成功: {symbol} {data_type}")

        except Exception as e:
            logger.error(f"存储基本面数据失败 {symbol} {data_type}: {e}")

    async def _store_stock_list_to_duckdb(self, data: pd.DataFrame, market: str, asset_type: AssetType = AssetType.STOCK_A):
        """存储股票列表到DuckDB"""
        try:
            db_path = self.asset_db_manager.get_database_path(asset_type)
            table_name = "stock_list"

            # 确保表存在
            await self.table_manager.ensure_table_exists(
                db_path, 'asset_list', 'enhanced_duckdb_downloader'
            )

            # 添加更新时间
            data['update_time'] = datetime.now()
            data['market_filter'] = market

            # 插入数据
            result = self.duckdb_operations.insert_dataframe(
                database_path=db_path,
                table_name=table_name,
                dataframe=data,
                conflict_resolution='replace'
            )

            if result.get('success'):
                logger.debug(f"股票列表存储成功: {len(data)} 只股票")

        except Exception as e:
            logger.error(f"存储股票列表失败: {e}")

    async def get_data_statistics(self) -> Dict[str, Any]:
        """获取数据统计信息"""
        stats = {}

        try:
            for asset_type in AssetType:
                db_path = self.asset_db_manager.get_database_path(asset_type)
                if Path(db_path).exists():
                    db_size = Path(db_path).stat().st_size / (1024 * 1024)  # MB
                    tables_query = "SELECT table_name, estimated_size FROM duckdb_tables()"
                    tables_result = self.duckdb_operations.execute_query(db_path, tables_query)

                    stats[asset_type.value] = {
                        'db_size_mb': round(db_size, 2),
                        'tables': tables_result.to_dict('records') if not tables_result.empty else []
                    }
                else:
                    stats[asset_type.value] = {'db_size_mb': 0, 'tables': []}

        except Exception as e:
            logger.error(f"获取数据统计失败: {e}")

        return stats

    def set_config(self, config: Dict[str, Any]):
        """更新下载配置"""
        self.config.update(config)

        # 更新线程池大小
        if 'max_workers' in config:
            self.executor.shutdown(wait=True)
            self.executor = ThreadPoolExecutor(max_workers=config['max_workers'])

        logger.info(f"下载配置已更新: {config}")

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self.config.copy()

    def get_download_cache_stats(self) -> Dict:
        """获取下载缓存统计"""
        return {
            'cache_size': len(self._download_cache),
            'config': self.get_config()
        }

    def clear_download_cache(self):
        """清空下载缓存"""
        self._download_cache.clear()
        logger.info("下载缓存已清空")

    async def cleanup(self):
        """清理资源"""
        self.executor.shutdown(wait=True)
        self.clear_download_cache()
        logger.info("增强DuckDB数据下载器清理完成")

    async def download_single_symbol_with_breakpoint(self,
                                                     symbol: str,
                                                     data_type: str = "K线数据",
                                                     frequency: str = "日线",
                                                     resume_state: Optional[Any] = None) -> bool:
        """下载单个股票（支持断点续传）"""
        try:
            start_time = datetime.now()

            # 检查是否已经完成
            if resume_state and symbol in resume_state.completed_symbols:
                logger.info(f"跳过已完成股票: {symbol}")
                return True

            # 检查是否失败过（根据策略处理）
            if resume_state and symbol in resume_state.failed_symbols:
                strategy = getattr(resume_state, 'strategy', 'resume_from_failure')
                if strategy == 'full_restart':
                    # 清除失败记录，重新下载
                    if hasattr(resume_state, 'failed_symbols'):
                        resume_state.failed_symbols.remove(symbol)
                elif strategy == 'skip':
                    logger.info(f"跳过失败股票: {symbol}")
                    return False

            logger.info(f"开始下载股票: {symbol} ({data_type}, {frequency})")

            # 获取下载范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)  # 默认下载最近30天

            # 从断点状态获取日期范围
            if resume_state and hasattr(resume_state, 'metadata'):
                metadata = resume_state.metadata
                if 'last_download_date' in metadata:
                    last_date = datetime.fromisoformat(metadata['last_download_date'])
                    start_date = last_date + timedelta(days=1)

            # 下载原始数据
            raw_data = await self._download_single_symbol_data(
                symbol, (start_date, end_date), DownloadStrategy.LATEST_ONLY
            )

            if raw_data is None or raw_data.empty:
                logger.warning(f"未获取到股票数据: {symbol}")
                return False

            # 清洗数据
            cleaned_data = self._validate_and_clean_kline_data(raw_data, symbol)

            # 增量存储数据
            records_count = await self._store_kline_data_incremental(
                cleaned_data, symbol, DownloadStrategy.LATEST_ONLY
            )

            # 更新断点状态
            if resume_state:
                resume_state.completed_symbols.append(symbol)
                resume_state.progress = (len(resume_state.completed_symbols) / len(resume_state.symbols)) * 100
                resume_state.last_updated = datetime.now()

                # 更新元数据
                if hasattr(resume_state, 'metadata'):
                    resume_state.metadata['last_download_date'] = end_date.isoformat()
                    resume_state.metadata['last_download_symbol'] = symbol
                    resume_state.metadata['records_count'] = records_count

            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"下载完成: {symbol}, 记录数: {records_count}, 耗时: {execution_time:.2f}s")

            return True

        except Exception as e:
            logger.error(f"下载股票失败: {symbol}, {e}")

            # 更新断点状态（失败记录）
            if resume_state:
                if symbol not in resume_state.failed_symbols:
                    resume_state.failed_symbols.append(symbol)
                resume_state.last_updated = datetime.now()

            return False


# 全局实例管理
_enhanced_duckdb_downloader: Optional[EnhancedDuckDBDataDownloader] = None


def get_enhanced_duckdb_downloader(uni_plugin_manager: UniPluginDataManager = None) -> EnhancedDuckDBDataDownloader:
    """获取增强DuckDB数据下载器实例"""
    global _enhanced_duckdb_downloader

    if _enhanced_duckdb_downloader is None:
        if uni_plugin_manager is None:
            raise ValueError("首次创建需要提供 uni_plugin_manager")
        _enhanced_duckdb_downloader = EnhancedDuckDBDataDownloader(uni_plugin_manager)

    return _enhanced_duckdb_downloader


def cleanup_enhanced_duckdb_downloader():
    """清理增强DuckDB数据下载器"""
    global _enhanced_duckdb_downloader
    _enhanced_duckdb_downloader = None
