from loguru import logger
"""
系统集成管理器

负责深度集成系统各个模块，包括：
- 数据存储系统集成
- 字段映射引擎集成
- 工具函数库集成
- 性能监控集成
- 缓存策略集成

作者: FactorWeave-Quant团队
版本: 1.0
"""

import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import json

# 导入核心模块
from ..tet_data_pipeline import TETDataPipeline, StandardQuery, StandardData
from ..data.field_mapping_engine import FieldMappingEngine
from ..database.duckdb_manager import DuckDBConnectionManager
from ..database.sqlite_extensions import SQLiteExtensionManager
from ..database.duckdb_operations import DuckDBOperations
from ..utils.data_calculations import (
    calculate_technical_indicators, calculate_financial_ratios,
    normalize_financial_data, validate_data_quality
)
from ..utils.database_utils import (
    generate_table_name, validate_symbol_format, standardize_market_code
)
from ..plugin_types import DataType, AssetType
from ..data_source_router import DataSourceRouter


class SystemIntegrationManager:
    """
    系统集成管理器

    统一管理和协调系统各个模块的交互，提供高级API接口
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化系统集成管理器

        Args:
            config: 系统配置字典
        """
        self.config = config
        # 核心组件
        self.tet_pipeline: Optional[TETDataPipeline] = None
        self.field_mapping_engine: Optional[FieldMappingEngine] = None
        self.duckdb_manager: Optional[DuckDBConnectionManager] = None
        self.sqlite_manager: Optional[SQLiteExtensionManager] = None
        self.duckdb_operations: Optional[DuckDBOperations] = None

        # 性能监控
        self.performance_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'cache_hit_rate': 0.0,
            'data_quality_score': 0.0
        }

        # 缓存管理
        self.cache = {}
        self.cache_ttl = timedelta(minutes=30)

        # 初始化标志
        self._initialized = False
        
        # 初始化logger
        self.logger = logger.bind(module=self.__class__.__name__)

    async def initialize(self) -> bool:
        """
        初始化系统集成管理器

        Returns:
            初始化是否成功
        """
        try:
            self.logger.info("开始初始化系统集成管理器...")

            # 1. 初始化数据库管理器
            await self._initialize_database_managers()

            # 2. 初始化数据处理管道
            await self._initialize_data_pipeline()

            # 3. 初始化字段映射引擎
            await self._initialize_field_mapping()

            # 4. 验证系统完整性
            if not await self._validate_system_integrity():
                raise Exception("系统完整性验证失败")

            self._initialized = True
            self.logger.info("系统集成管理器初始化完成")
            return True

        except Exception as e:
            self.logger.error(f"系统集成管理器初始化失败: {e}")
            return False

    async def _initialize_database_managers(self):
        """初始化数据库管理器"""
        try:
            # DuckDB管理器
            duckdb_config = self.config.get('duckdb', {})
            self.duckdb_manager = DuckDBConnectionManager(
                db_path=duckdb_config.get('db_path', 'data/factorweave_analytics.duckdb'),
                pool_size=duckdb_config.get('pool_size', 5)
            )

            # 初始化DuckDB
            await asyncio.to_thread(self.duckdb_manager.initialize_database)

            # DuckDB操作管理器
            self.duckdb_operations = DuckDBOperations(self.duckdb_manager)

            # SQLite扩展管理器
            sqlite_config = self.config.get('sqlite', {})
            self.sqlite_manager = SQLiteExtensionManager(
                db_path=sqlite_config.get('db_path', 'data/factorweave_system.sqlite')
            )

            # 初始化SQLite扩展表
            self.sqlite_manager.initialize_tables()

            self.logger.info("数据库管理器初始化完成")

        except Exception as e:
            self.logger.error(f"数据库管理器初始化失败: {e}")
            raise

    async def _initialize_data_pipeline(self):
        """初始化数据处理管道"""
        try:
            # 创建数据源路由器
            router_config = self.config.get('data_source_router', {})
            data_source_router = DataSourceRouter(
                routing_strategy=router_config.get('strategy', 'round_robin'),
                health_check_interval=router_config.get('health_check_interval', 300)
            )

            # 创建TET数据管道
            self.tet_pipeline = TETDataPipeline(data_source_router)

            self.logger.info("数据处理管道初始化完成")

        except Exception as e:
            self.logger.error(f"数据处理管道初始化失败: {e}")
            raise

    async def _initialize_field_mapping(self):
        """初始化字段映射引擎"""
        try:
            # 获取字段映射配置
            field_mappings = self.tet_pipeline.field_mappings if self.tet_pipeline else {}

            # 创建字段映射引擎
            self.field_mapping_engine = FieldMappingEngine(field_mappings)

            # 加载自定义映射规则
            custom_mappings_config = self.config.get('custom_field_mappings', {})
            for data_type_str, mappings in custom_mappings_config.items():
                try:
                    data_type = DataType(data_type_str)
                    self.field_mapping_engine.add_custom_mapping(data_type, mappings)
                except ValueError:
                    self.logger.warning(f"无效的数据类型: {data_type_str}")

            self.logger.info("字段映射引擎初始化完成")

        except Exception as e:
            self.logger.error(f"字段映射引擎初始化失败: {e}")
            raise

    async def _validate_system_integrity(self) -> bool:
        """验证系统完整性"""
        try:
            # 检查核心组件
            if not all([
                self.tet_pipeline,
                self.field_mapping_engine,
                self.duckdb_manager,
                self.sqlite_manager,
                self.duckdb_operations
            ]):
                self.logger.error("核心组件未完全初始化")
                return False

            # 测试数据库连接
            test_conn = self.duckdb_manager.get_connection()
            if not test_conn:
                self.logger.error("DuckDB连接测试失败")
                return False
            self.duckdb_manager.return_connection(test_conn)

            # 测试SQLite连接
            if not self.sqlite_manager.test_connection():
                self.logger.error("SQLite连接测试失败")
                return False

            self.logger.info("系统完整性验证通过")
            return True

        except Exception as e:
            self.logger.error(f"系统完整性验证失败: {e}")
            return False

    async def process_and_store_data(self, query: StandardQuery,
                                     raw_data: Any) -> Dict[str, Any]:
        """
        处理并存储数据的统一接口

        Args:
            query: 标准查询对象
            raw_data: 原始数据

        Returns:
            处理结果字典
        """
        start_time = datetime.now()

        try:
            if not self._initialized:
                raise Exception("系统集成管理器未初始化")

            self.performance_stats['total_requests'] += 1

            # 1. 数据标准化处理
            standardized_data = await self._standardize_data(query, raw_data)

            # 2. 数据质量评估
            quality_report = await self._assess_data_quality(standardized_data, query.data_type)

            # 3. 数据存储
            storage_result = await self._store_data(query, standardized_data, quality_report)

            # 4. 更新性能统计
            processing_time = (datetime.now() - start_time).total_seconds()
            await self._update_performance_stats(processing_time, True, quality_report)

            result = {
                'success': True,
                'processed_records': len(standardized_data) if hasattr(standardized_data, '__len__') else 1,
                'processing_time_seconds': processing_time,
                'data_quality_score': quality_report.get('quality_score', 0.0),
                'storage_result': storage_result,
                'quality_report': quality_report
            }

            self.logger.info(f"数据处理完成: {result['processed_records']} 条记录，耗时 {processing_time:.2f}秒")
            return result

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            await self._update_performance_stats(processing_time, False, {})

            self.logger.error(f"数据处理失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_time_seconds': processing_time
            }

    async def _standardize_data(self, query: StandardQuery, raw_data: Any) -> Any:
        """标准化数据"""
        try:
            # 使用TET管道进行数据标准化
            if hasattr(raw_data, 'to_frame') or hasattr(raw_data, 'columns'):
                # DataFrame数据
                standardized_data = self.tet_pipeline.transform_data(raw_data, query)
            else:
                # 其他类型数据，转换为DataFrame
                import pandas as pd
                if isinstance(raw_data, dict):
                    df = pd.DataFrame([raw_data])
                elif isinstance(raw_data, list):
                    df = pd.DataFrame(raw_data)
                else:
                    raise ValueError(f"不支持的数据类型: {type(raw_data)}")

                standardized_data = self.tet_pipeline.transform_data(df, query)

            # 应用技术指标计算（如果是K线数据）
            if query.data_type == DataType.HISTORICAL_KLINE:
                standardized_data = calculate_technical_indicators(standardized_data)

            # 应用财务比率计算（如果是财务数据）
            elif query.data_type == DataType.FINANCIAL_STATEMENT:
                if not standardized_data.empty:
                    for idx, row_dict in zip(standardized_data.index, standardized_data.to_dict('records')):
                        ratios = calculate_financial_ratios(row_dict)
                        for ratio_name, ratio_value in ratios.items():
                            standardized_data.at[idx, ratio_name] = ratio_value

            return standardized_data

        except Exception as e:
            self.logger.error(f"数据标准化失败: {e}")
            raise

    async def _assess_data_quality(self, data: Any, data_type: DataType) -> Dict[str, Any]:
        """评估数据质量"""
        try:
            # 获取必需字段
            required_fields = self._get_required_fields(data_type)

            # 使用工具函数验证数据质量
            quality_report = validate_data_quality(data, required_fields)

            # 添加数据类型特定的质量检查
            if data_type == DataType.HISTORICAL_KLINE:
                quality_report.update(self._validate_kline_data(data))
            elif data_type == DataType.FINANCIAL_STATEMENT:
                quality_report.update(self._validate_financial_data(data))
            elif data_type == DataType.MACRO_ECONOMIC:
                quality_report.update(self._validate_macro_data(data))

            return quality_report

        except Exception as e:
            self.logger.error(f"数据质量评估失败: {e}")
            return {'quality_score': 0.0, 'issues': [f"质量评估失败: {str(e)}"]}

    async def _store_data(self, query: StandardQuery, data: Any,
                          quality_report: Dict[str, Any]) -> Dict[str, Any]:
        """存储数据"""
        try:
            # 生成表名
            plugin_name = query.extra_params.get('plugin_name', 'default')
            table_name = generate_table_name(plugin_name, query.data_type)

            # 存储到DuckDB
            insert_result = await asyncio.to_thread(
                self.duckdb_operations.batch_insert,
                table_name, data
            )

            # 更新SQLite元数据
            metadata = {
                'plugin_name': plugin_name,
                'data_type': query.data_type.value,
                'table_name': table_name,
                'record_count': len(data) if hasattr(data, '__len__') else 1,
                'last_updated': datetime.now(),
                'data_quality_score': quality_report.get('quality_score', 0.0)
            }

            self.sqlite_manager.update_plugin_table_mapping(
                plugin_name, query.data_type.value, table_name, metadata
            )

            return {
                'table_name': table_name,
                'records_inserted': insert_result.get('records_inserted', 0),
                'insert_success': insert_result.get('success', False)
            }

        except Exception as e:
            self.logger.error(f"数据存储失败: {e}")
            return {
                'table_name': None,
                'records_inserted': 0,
                'insert_success': False,
                'error': str(e)
            }

    def _get_required_fields(self, data_type: DataType) -> List[str]:
        """获取数据类型的必需字段"""
        required_fields_map = {
            DataType.HISTORICAL_KLINE: ['open', 'high', 'low', 'close', 'volume'],
            DataType.REAL_TIME_QUOTE: ['current_price', 'volume'],
            DataType.FINANCIAL_STATEMENT: ['symbol', 'report_date', 'report_type'],
            DataType.MACRO_ECONOMIC: ['indicator_code', 'value', 'data_date']
        }
        return required_fields_map.get(data_type, [])

    def _validate_kline_data(self, data) -> Dict[str, Any]:
        """验证K线数据"""
        issues = []

        try:
            if hasattr(data, 'columns'):
                # 检查OHLC逻辑关系
                if all(col in data.columns for col in ['open', 'high', 'low', 'close']):
                    # 检查 high >= max(open, close) 和 low <= min(open, close)
                    invalid_high = (data['high'] < data[['open', 'close']].max(axis=1)).sum()
                    invalid_low = (data['low'] > data[['open', 'close']].min(axis=1)).sum()

                    if invalid_high > 0:
                        issues.append(f"{invalid_high} 条记录的最高价小于开盘价或收盘价")
                    if invalid_low > 0:
                        issues.append(f"{invalid_low} 条记录的最低价大于开盘价或收盘价")

                # 检查成交量
                if 'volume' in data.columns:
                    negative_volume = (data['volume'] < 0).sum()
                    if negative_volume > 0:
                        issues.append(f"{negative_volume} 条记录的成交量为负数")

        except Exception as e:
            issues.append(f"K线数据验证失败: {str(e)}")

        return {'kline_validation_issues': issues}

    def _validate_financial_data(self, data) -> Dict[str, Any]:
        """验证财务数据"""
        issues = []

        try:
            if hasattr(data, 'columns'):
                # 检查资产负债平衡
                if all(col in data.columns for col in ['total_assets', 'total_liabilities', 'shareholders_equity']):
                    balance_diff = abs(data['total_assets'] - (data['total_liabilities'] + data['shareholders_equity']))
                    significant_diff = (balance_diff > data['total_assets'] * 0.01).sum()  # 1%容差

                    if significant_diff > 0:
                        issues.append(f"{significant_diff} 条记录的资产负债不平衡")

                # 检查负值
                positive_fields = ['total_assets', 'shareholders_equity', 'operating_revenue']
                for field in positive_fields:
                    if field in data.columns:
                        negative_count = (data[field] < 0).sum()
                        if negative_count > 0:
                            issues.append(f"{negative_count} 条记录的 {field} 为负值")

        except Exception as e:
            issues.append(f"财务数据验证失败: {str(e)}")

        return {'financial_validation_issues': issues}

    def _validate_macro_data(self, data) -> Dict[str, Any]:
        """验证宏观经济数据"""
        issues = []

        try:
            if hasattr(data, 'columns'):
                # 检查数值范围合理性
                if 'value' in data.columns:
                    # 检查异常值（使用3σ原则）
                    mean_val = data['value'].mean()
                    std_val = data['value'].std()
                    if std_val > 0:
                        outliers = abs(data['value'] - mean_val) > 3 * std_val
                        outlier_count = outliers.sum()
                        if outlier_count > 0:
                            issues.append(f"{outlier_count} 条记录可能包含异常值")

        except Exception as e:
            issues.append(f"宏观数据验证失败: {str(e)}")

        return {'macro_validation_issues': issues}

    async def _update_performance_stats(self, processing_time: float,
                                        success: bool, quality_report: Dict[str, Any]):
        """更新性能统计"""
        try:
            if success:
                self.performance_stats['successful_requests'] += 1
            else:
                self.performance_stats['failed_requests'] += 1

            # 更新平均响应时间
            total_requests = self.performance_stats['total_requests']
            current_avg = self.performance_stats['avg_response_time']
            self.performance_stats['avg_response_time'] = (
                (current_avg * (total_requests - 1) + processing_time) / total_requests
            )

            # 更新数据质量评分
            quality_score = quality_report.get('quality_score', 0.0)
            current_quality = self.performance_stats['data_quality_score']
            self.performance_stats['data_quality_score'] = (
                (current_quality * (total_requests - 1) + quality_score) / total_requests
            )

        except Exception as e:
            self.logger.error(f"更新性能统计失败: {e}")

    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            status = {
                'initialized': self._initialized,
                'performance_stats': self.performance_stats.copy(),
                'component_status': {
                    'tet_pipeline': self.tet_pipeline is not None,
                    'field_mapping_engine': self.field_mapping_engine is not None,
                    'duckdb_manager': self.duckdb_manager is not None,
                    'sqlite_manager': self.sqlite_manager is not None,
                    'duckdb_operations': self.duckdb_operations is not None
                },
                'database_status': {},
                'cache_status': {
                    'cache_size': len(self.cache),
                    'cache_ttl_minutes': self.cache_ttl.total_seconds() / 60
                }
            }

            # 获取数据库状态
            if self.duckdb_manager:
                status['database_status']['duckdb'] = {
                    'pool_size': self.duckdb_manager.pool_size,
                    'active_connections': len(self.duckdb_manager.connection_pool),
                    'health_status': 'healthy' if self.duckdb_manager.get_connection() else 'unhealthy'
                }

            if self.sqlite_manager:
                status['database_status']['sqlite'] = {
                    'connection_status': 'healthy' if self.sqlite_manager.test_connection() else 'unhealthy'
                }

            return status

        except Exception as e:
            self.logger.error(f"获取系统状态失败: {e}")
            return {'error': str(e)}

    async def cleanup(self):
        """清理资源"""
        try:
            self.logger.info("开始清理系统资源...")

            # 清理数据库连接
            if self.duckdb_manager:
                self.duckdb_manager.close_all_connections()

            # 清理缓存
            self.cache.clear()

            # 重置状态
            self._initialized = False

            self.logger.info("系统资源清理完成")

        except Exception as e:
            self.logger.error(f"系统资源清理失败: {e}")


# 全局系统集成管理器实例
_system_integration_manager: Optional[SystemIntegrationManager] = None


async def get_system_integration_manager(config: Optional[Dict[str, Any]] = None) -> SystemIntegrationManager:
    """
    获取系统集成管理器实例（单例模式）

    Args:
        config: 系统配置（仅在首次调用时需要）

    Returns:
        系统集成管理器实例
    """
    global _system_integration_manager

    if _system_integration_manager is None:
        if config is None:
            raise ValueError("首次调用需要提供系统配置")

        _system_integration_manager = SystemIntegrationManager(config)
        await _system_integration_manager.initialize()

    return _system_integration_manager


async def cleanup_system_integration_manager():
    """清理全局系统集成管理器"""
    global _system_integration_manager

    if _system_integration_manager:
        await _system_integration_manager.cleanup()
        _system_integration_manager = None
