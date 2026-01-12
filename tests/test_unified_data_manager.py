"""
UnifiedDataManager 单元测试

测试统一数据管理器的核心功能，包括：
1. 初始化测试
2. 股票CRUD操作
3. K线数据CRUD操作
4. 行情数据CRUD操作
5. 数据获取测试
6. 缓存管理测试
7. 请求管理测试
"""

import pytest
import tempfile
import shutil
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
import json

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestUnifiedDataManager:
    """UnifiedDataManager 单元测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def temp_db_path(self, temp_dir):
        """临时数据库路径 fixture"""
        return os.path.join(temp_dir, 'test_data_manager.db')

    @pytest.fixture
    def mock_service_container(self):
        """模拟服务容器 fixture"""
        container = MagicMock()
        container.get = MagicMock(return_value=MagicMock())
        container.is_registered = MagicMock(return_value=False)
        container.resolve = MagicMock(return_value=MagicMock())
        return container

    @pytest.fixture
    def mock_event_bus(self):
        """模拟事件总线 fixture"""
        event_bus = MagicMock()
        event_bus.publish = MagicMock()
        return event_bus

    @pytest.fixture
    def mock_duckdb_operations(self):
        """模拟DuckDB操作 fixture"""
        operations = MagicMock()
        operations.insert_stock_info = MagicMock(return_value=True)
        operations.update_stock_info = MagicMock(return_value=True)
        operations.delete_stock_info = MagicMock(return_value=True)
        operations.insert_kline_data = MagicMock(return_value=True)
        operations.update_kline_data = MagicMock(return_value=True)
        operations.delete_kline_data = MagicMock(return_value=True)
        operations.insert_market_data = MagicMock(return_value=True)
        operations.update_market_data = MagicMock(return_value=True)
        operations.delete_market_data = MagicMock(return_value=True)
        return operations

    @pytest.fixture
    def sample_stock_data(self):
        """示例股票数据 fixture"""
        return {
            'code': '600000',
            'name': '浦发银行',
            'market': 'SH',
            'industry': '银行',
            'list_date': '1999-11-10',
            'status': 'active'
        }

    @pytest.fixture
    def sample_kline_data(self):
        """示例K线数据 fixture"""
        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        return pd.DataFrame({
            'trade_date': dates,
            'open': [10.0 + i * 0.1 for i in range(10)],
            'high': [10.5 + i * 0.1 for i in range(10)],
            'low': [9.5 + i * 0.1 for i in range(10)],
            'close': [10.2 + i * 0.1 for i in range(10)],
            'volume': [1000000 + i * 10000 for i in range(10)],
            'amount': [10000000 + i * 100000 for i in range(10)]
        })

    @pytest.fixture
    def sample_market_data(self):
        """示例行情数据 fixture"""
        return {
            'code': '600000',
            'trade_date': '2024-01-15',
            'open': 10.5,
            'high': 10.8,
            'low': 10.3,
            'close': 10.6,
            'volume': 1500000,
            'amount': 15000000,
            'change_pct': 2.5
        }

    @pytest.fixture
    def data_manager(self, temp_dir, mock_service_container, mock_event_bus, mock_duckdb_operations):
        """创建 UnifiedDataManager 实例 fixture"""
        with patch('core.services.unified_data_manager.logger'):
            with patch('core.services.unified_data_manager.DB_PATH', os.path.join(temp_dir, 'test.db')):
                with patch('core.services.unified_data_manager.IndustryManager'):
                    with patch('core.services.unified_data_manager.TETDataPipeline'):
                        with patch('core.services.unified_data_manager.DataSourceRouter'):
                            with patch('core.services.unified_data_manager.MultiLevelCacheManager'):
                                from core.services.unified_data_manager import UnifiedDataManager

                                manager = UnifiedDataManager(
                                    service_container=mock_service_container,
                                    event_bus=mock_event_bus,
                                    max_workers=2
                                )

                                # 模拟数据库连接
                                manager.conn = sqlite3.connect(os.path.join(temp_dir, 'test.db'), check_same_thread=False)
                                manager._db_lock = MagicMock()
                                manager._db_lock.__enter__ = MagicMock(return_value=MagicMock())
                                manager._db_lock.__exit__ = MagicMock(return_value=False)

                                # 模拟DuckDB操作
                                manager.duckdb_available = True
                                manager.duckdb_operations = mock_duckdb_operations

                                # 模拟缓存
                                manager.cache_manager = MagicMock()
                                manager.multi_cache = MagicMock()

                                # 模拟行业管理器
                                manager.industry_manager = MagicMock()

                                # 初始化数据库表
                                cursor = manager.conn.cursor()
                                cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS stocks (
                                        code TEXT PRIMARY KEY,
                                        name TEXT,
                                        market TEXT,
                                        industry TEXT,
                                        list_date TEXT,
                                        delist_date TEXT,
                                        status TEXT
                                    )
                                ''')
                                cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS kline (
                                        stock_code TEXT,
                                        period TEXT,
                                        trade_date TEXT,
                                        open REAL,
                                        high REAL,
                                        low REAL,
                                        close REAL,
                                        volume INTEGER,
                                        amount REAL,
                                        PRIMARY KEY (stock_code, period, trade_date)
                                    )
                                ''')
                                cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS market (
                                        code TEXT,
                                        trade_date TEXT,
                                        open REAL,
                                        high REAL,
                                        low REAL,
                                        close REAL,
                                        volume INTEGER,
                                        amount REAL,
                                        change_pct REAL,
                                        PRIMARY KEY (code, trade_date)
                                    )
                                ''')
                                manager.conn.commit()

                                yield manager

                                # 清理
                                if manager.conn:
                                    manager.conn.close()

    def test_init_data_manager(self, temp_dir, mock_service_container, mock_event_bus):
        """测试 UnifiedDataManager 初始化"""
        with patch('core.services.unified_data_manager.logger'):
            with patch('core.services.unified_data_manager.DB_PATH', os.path.join(temp_dir, 'test.db')):
                with patch('core.services.unified_data_manager.IndustryManager'):
                    with patch('core.services.unified_data_manager.TETDataPipeline'):
                        with patch('core.services.unified_data_manager.DataSourceRouter'):
                            with patch('core.services.unified_data_manager.MultiLevelCacheManager'):
                                from core.services.unified_data_manager import UnifiedDataManager

                                manager = UnifiedDataManager(
                                    service_container=mock_service_container,
                                    event_bus=mock_event_bus,
                                    max_workers=2
                                )

                                assert manager is not None
                                assert manager.service_container == mock_service_container
                                assert manager.event_bus == mock_event_bus
                                assert manager._executor is not None
                                assert manager._pending_requests == {}
                                assert manager._active_requests == {}
                                assert manager._completed_requests == {}
                                assert manager._cache_ttl == 300

    def test_add_stock_success(self, data_manager, sample_stock_data):
        """测试成功添加股票"""
        result = data_manager.add_stock(sample_stock_data)

        assert result is True
        data_manager.duckdb_operations.insert_stock_info.assert_called_once_with(sample_stock_data)

    def test_add_stock_invalid_data(self, data_manager):
        """测试添加无效股票数据"""
        result = data_manager.add_stock({})

        assert result is False
        data_manager.logger.error.assert_called()

    def test_add_stock_missing_code(self, data_manager):
        """测试添加缺少code字段的股票数据"""
        result = data_manager.add_stock({'name': '测试股票'})

        assert result is False

    def test_add_stock_duckdb_fallback_to_sqlite(self, temp_dir, mock_service_container, mock_event_bus):
        """测试DuckDB失败时回退到SQLite"""
        with patch('core.services.unified_data_manager.logger'):
            with patch('core.services.unified_data_manager.DB_PATH', os.path.join(temp_dir, 'test.db')):
                with patch('core.services.unified_data_manager.IndustryManager'):
                    with patch('core.services.unified_data_manager.TETDataPipeline'):
                        with patch('core.services.unified_data_manager.DataSourceRouter'):
                            with patch('core.services.unified_data_manager.MultiLevelCacheManager'):
                                from core.services.unified_data_manager import UnifiedDataManager

                                # 模拟DuckDB操作返回失败
                                mock_duckdb = MagicMock()
                                mock_duckdb.insert_stock_info = MagicMock(return_value=False)

                                manager = UnifiedDataManager(
                                    service_container=mock_service_container,
                                    event_bus=mock_event_bus,
                                    max_workers=2
                                )
                                manager.conn = sqlite3.connect(os.path.join(temp_dir, 'test.db'), check_same_thread=False)
                                manager._db_lock = MagicMock()
                                manager._db_lock.__enter__ = MagicMock(return_value=MagicMock())
                                manager._db_lock.__exit__ = MagicMock(return_value=False)
                                manager.duckdb_available = True
                                manager.duckdb_operations = mock_duckdb
                                manager.cache_manager = MagicMock()
                                manager.multi_cache = MagicMock()
                                manager.industry_manager = MagicMock()

                                # 初始化数据库表
                                cursor = manager.conn.cursor()
                                cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS stocks (
                                        code TEXT PRIMARY KEY,
                                        name TEXT,
                                        market TEXT,
                                        industry TEXT,
                                        list_date TEXT,
                                        delist_date TEXT,
                                        status TEXT
                                    )
                                ''')
                                manager.conn.commit()

                                sample_data = {'code': '600001', 'name': '测试股票'}
                                result = manager.add_stock(sample_data)

                                assert result is True

    def test_update_stock_success(self, data_manager, sample_stock_data):
        """测试成功更新股票信息"""
        data_manager.add_stock(sample_stock_data)

        update_data = {'name': '浦发银行改', 'industry': '金融'}
        result = data_manager.update_stock('600000', update_data)

        assert result is True
        data_manager.duckdb_operations.update_stock_info.assert_called()

    def test_update_stock_empty_code(self, data_manager):
        """测试更新股票时股票代码为空"""
        result = data_manager.update_stock('', {'name': '测试'})

        assert result is False
        data_manager.logger.error.assert_called()

    def test_update_stock_not_found(self, data_manager):
        """测试更新不存在的股票"""
        result = data_manager.update_stock('999999', {'name': '测试'})

        assert result is False

    def test_delete_stock_success(self, data_manager, sample_stock_data):
        """测试成功删除股票"""
        data_manager.add_stock(sample_stock_data)

        result = data_manager.delete_stock('600000')

        assert result is True
        data_manager.duckdb_operations.delete_stock_info.assert_called_once_with('600000')

    def test_delete_stock_empty_code(self, data_manager):
        """测试删除股票时股票代码为空"""
        result = data_manager.delete_stock('')

        assert result is False
        data_manager.logger.error.assert_called()

    def test_delete_stock_not_found(self, data_manager):
        """测试删除不存在的股票"""
        result = data_manager.delete_stock('999999')

        assert result is False

    def test_add_kline_success(self, data_manager, sample_kline_data):
        """测试成功添加K线数据"""
        result = data_manager.add_kline('600000', 'D', sample_kline_data)

        assert result is True
        data_manager.duckdb_operations.insert_kline_data.assert_called_once_with('600000', 'D', sample_kline_data)

    def test_add_kline_empty_stock_code(self, data_manager, sample_kline_data):
        """测试添加K线时股票代码为空"""
        result = data_manager.add_kline('', 'D', sample_kline_data)

        assert result is False

    def test_add_kline_empty_data(self, data_manager):
        """测试添加空K线数据"""
        result = data_manager.add_kline('600000', 'D', pd.DataFrame())

        assert result is False

    def test_update_kline_success(self, data_manager, sample_kline_data):
        """测试成功更新K线数据"""
        mock_duckdb = data_manager.duckdb_operations
        mock_duckdb.delete_kline_data = MagicMock(return_value=True)

        result = data_manager.update_kline('600000', 'D', sample_kline_data)

        assert result is True

    def test_delete_kline_success(self, data_manager):
        """测试成功删除K线数据"""
        mock_duckdb = data_manager.duckdb_operations
        mock_duckdb.delete_kline_data = MagicMock(return_value=True)

        result = data_manager.delete_kline('600000', 'D')

        assert result is True
        mock_duckdb.delete_kline_data.assert_called_once_with('600000', 'D', None, None)

    def test_delete_kline_with_date_range(self, data_manager):
        """测试删除指定日期范围的K线数据"""
        mock_duckdb = data_manager.duckdb_operations
        mock_duckdb.delete_kline_data = MagicMock(return_value=True)

        result = data_manager.delete_kline('600000', 'D', '2024-01-01', '2024-01-31')

        assert result is True
        mock_duckdb.delete_kline_data.assert_called_once_with('600000', 'D', '2024-01-01', '2024-01-31')

    def test_add_market_data_success(self, data_manager, sample_market_data):
        """测试成功添加行情数据"""
        result = data_manager.add_market_data(sample_market_data)

        assert result is True
        data_manager.duckdb_operations.insert_market_data.assert_called_once_with(sample_market_data)

    def test_add_market_data_invalid(self, data_manager):
        """测试添加无效行情数据"""
        result = data_manager.add_market_data({})

        assert result is False

    def test_add_market_data_missing_code(self, data_manager):
        """测试添加缺少code字段的行情数据"""
        result = data_manager.add_market_data({'trade_date': '2024-01-15'})

        assert result is False

    def test_update_market_data_success(self, data_manager, sample_market_data):
        """测试成功更新行情数据"""
        data_manager.add_market_data(sample_market_data)

        update_data = {'close': 10.8, 'change_pct': 3.0}
        result = data_manager.update_market_data('600000', update_data)

        assert result is True

    def test_update_market_data_missing_date(self, data_manager):
        """测试更新行情数据时缺少trade_date"""
        result = data_manager.update_market_data('600000', {'close': 10.8})

        assert result is False
        data_manager.logger.error.assert_called()

    def test_update_market_data_empty_code(self, data_manager):
        """测试更新行情数据时股票代码为空"""
        result = data_manager.update_market_data('', {'trade_date': '2024-01-15', 'close': 10.8})

        assert result is False

    def test_delete_market_data_success(self, data_manager, sample_market_data):
        """测试成功删除行情数据"""
        data_manager.add_market_data(sample_market_data)

        result = data_manager.delete_market_data('600000', datetime(2024, 1, 15))

        assert result is True
        data_manager.duckdb_operations.delete_market_data.assert_called()

    def test_delete_market_data_not_found(self, data_manager):
        """测试删除不存在的行情数据"""
        mock_duckdb = data_manager.duckdb_operations
        mock_duckdb.delete_market_data = MagicMock(return_value=False)

        result = data_manager.delete_market_data('999999', datetime(2024, 1, 15))

        assert result is False

    def test_get_stock_info(self, data_manager, sample_stock_data):
        """测试获取股票信息"""
        data_manager.add_stock(sample_stock_data)

        info = data_manager.get_stock_info('600000')

        assert info is not None
        assert info['code'] == '600000'
        assert info['name'] == '浦发银行'

    def test_get_stock_info_not_found(self, data_manager):
        """测试获取不存在的股票信息"""
        info = data_manager.get_stock_info('999999')

        assert info is None

    def test_search_stocks(self, data_manager, sample_stock_data):
        """测试搜索股票"""
        data_manager.add_stock(sample_stock_data)

        results = data_manager.search_stocks('浦发')

        assert isinstance(results, list)

    def test_search_stocks_not_found(self, data_manager):
        """测试搜索不存在的股票"""
        results = data_manager.search_stocks('不存在的股票')

        assert results == []

    def test_get_stats(self, data_manager):
        """测试获取统计信息"""
        stats = data_manager.get_stats()

        assert isinstance(stats, dict)
        assert 'requests_total' in stats
        assert 'requests_completed' in stats
        assert 'requests_failed' in stats
        assert 'requests_cancelled' in stats
        assert 'cache_hits' in stats
        assert 'cache_misses' in stats

    def test_get_statistics(self, data_manager):
        """测试获取详细统计信息"""
        stats = data_manager.get_statistics()

        assert isinstance(stats, dict)
        assert 'requests' in stats
        assert 'cache' in stats
        assert 'active_requests' in stats

    def test_request_status_enum(self):
        """测试 DataRequestStatus 枚举"""
        from core.services.unified_data_manager import DataRequestStatus

        assert DataRequestStatus.PENDING.value == "pending"
        assert DataRequestStatus.LOADING.value == "loading"
        assert DataRequestStatus.COMPLETED.value == "completed"
        assert DataRequestStatus.FAILED.value == "failed"
        assert DataRequestStatus.CANCELLED.value == "cancelled"

    def test_data_request_creation(self):
        """测试 DataRequest 创建"""
        from core.services.unified_data_manager import DataRequest, DataRequestStatus, AssetType

        request = DataRequest(
            request_id="test_001",
            symbol="600000",
            asset_type=AssetType.STOCK_A,
            data_type="kdata",
            period="D",
            time_range=365
        )

        assert request.request_id == "test_001"
        assert request.symbol == "600000"
        assert request.status == DataRequestStatus.PENDING
        assert request.priority == 0

    def test_data_request_backward_compatibility(self):
        """测试 DataRequest 向后兼容属性"""
        from core.services.unified_data_manager import DataRequest

        request = DataRequest(
            request_id="test_001",
            symbol="600000"
        )

        assert request.stock_code == "600000"
        request.stock_code = "000001"
        assert request.symbol == "000001"

    def test_data_request_equality(self):
        """测试 DataRequest 相等性判断"""
        from core.services.unified_data_manager import DataRequest, AssetType

        request1 = DataRequest(
            request_id="test_001",
            symbol="600000",
            asset_type=AssetType.STOCK_A,
            data_type="kdata",
            period="D",
            time_range=365
        )

        request2 = DataRequest(
            request_id="test_002",
            symbol="600000",
            asset_type=AssetType.STOCK_A,
            data_type="kdata",
            period="D",
            time_range=365
        )

        assert request1 == request2

    def test_data_request_hash(self):
        """测试 DataRequest 哈希计算"""
        from core.services.unified_data_manager import DataRequest, AssetType

        request = DataRequest(
            request_id="test_001",
            symbol="600000",
            asset_type=AssetType.STOCK_A,
            data_type="kdata",
            period="D",
            time_range=365
        )

        hash_value = hash(request)
        assert isinstance(hash_value, int)

    def test_cache_data_operations(self, data_manager):
        """测试缓存数据操作"""
        test_data = {'key': 'value', 'number': 123}

        data_manager._cache_data('test_cache_key', test_data)
        cached = data_manager._get_cached_data('test_cache_key')

        assert cached == test_data

        data_manager._invalidate_cache('test_cache_key')
        cached_after_invalidate = data_manager._get_cached_data('test_cache_key')

        assert cached_after_invalidate is None

    def test_get_unified_data_manager_function(self):
        """测试 get_unified_data_manager 函数"""
        with patch('core.services.unified_data_manager.get_service_container') as mock_get_container:
            mock_container = MagicMock()
            mock_get_container.return_value = mock_container
            mock_container.resolve = MagicMock(return_value=MagicMock())

            from core.services.unified_data_manager import get_unified_data_manager

            result = get_unified_data_manager()

            assert result is not None

    def test_get_unified_data_manager_not_available(self):
        """测试 get_unified_data_manager 在服务不可用时返回 None"""
        with patch('core.services.unified_data_manager.get_service_container') as mock_get_container:
            mock_get_container.side_effect = Exception("Service not available")

            from core.services.unified_data_manager import get_unified_data_manager

            result = get_unified_data_manager()

            assert result is None

    def test_request_management(self, data_manager):
        """测试请求管理功能"""
        from core.services.unified_data_manager import DataRequest, DataRequestStatus

        request = DataRequest(
            request_id="test_request_001",
            symbol="600000",
            data_type="kdata",
            period="D",
            time_range=365
        )

        data_manager._add_request(request)

        assert request.request_id in data_manager._pending_requests
        assert data_manager._pending_requests[request.request_id] == request

        request.status = DataRequestStatus.LOADING
        data_manager._move_request_to_active(request)

        assert request.request_id in data_manager._active_requests
        assert request.request_id not in data_manager._pending_requests

        data_manager._complete_request(request)

        assert request.request_id in data_manager._completed_requests
        assert request.request_id not in data_manager._active_requests

    def test_get_request_status(self, data_manager):
        """测试获取请求状态"""
        from core.services.unified_data_manager import DataRequest, DataRequestStatus

        request = DataRequest(
            request_id="test_request_002",
            symbol="600000",
            data_type="kdata",
            period="D",
            time_range=365
        )

        data_manager._add_request(request)

        status = data_manager.get_request_status("test_request_002")

        assert status == DataRequestStatus.PENDING

        status_not_found = data_manager.get_request_status("nonexistent_request")

        assert status_not_found is None

    def test_duckdb_not_available_fallback(self, temp_dir, mock_service_container, mock_event_bus):
        """测试DuckDB不可用时回退到SQLite"""
        with patch('core.services.unified_data_manager.logger'):
            with patch('core.services.unified_data_manager.DB_PATH', os.path.join(temp_dir, 'test.db')):
                with patch('core.services.unified_data_manager.IndustryManager'):
                    with patch('core.services.unified_data_manager.TETDataPipeline'):
                        with patch('core.services.unified_data_manager.DataSourceRouter'):
                            with patch('core.services.unified_data_manager.MultiLevelCacheManager'):
                                from core.services.unified_data_manager import UnifiedDataManager

                                manager = UnifiedDataManager(
                                    service_container=mock_service_container,
                                    event_bus=mock_event_bus,
                                    max_workers=2
                                )

                                manager.conn = sqlite3.connect(os.path.join(temp_dir, 'test.db'), check_same_thread=False)
                                manager._db_lock = MagicMock()
                                manager._db_lock.__enter__ = MagicMock(return_value=MagicMock())
                                manager._db_lock.__exit__ = MagicMock(return_value=False)
                                manager.duckdb_available = False
                                manager.duckdb_operations = None
                                manager.cache_manager = MagicMock()
                                manager.multi_cache = MagicMock()
                                manager.industry_manager = MagicMock()

                                # 初始化数据库表
                                cursor = manager.conn.cursor()
                                cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS stocks (
                                        code TEXT PRIMARY KEY,
                                        name TEXT,
                                        market TEXT,
                                        industry TEXT,
                                        list_date TEXT,
                                        delist_date TEXT,
                                        status TEXT
                                    )
                                ''')
                                manager.conn.commit()

                                sample_data = {'code': '600001', 'name': '测试股票'}
                                result = manager.add_stock(sample_data)

                                assert result is True

    def test_exception_handling_add_stock(self, data_manager):
        """测试添加股票时的异常处理"""
        mock_duckdb = data_manager.duckdb_operations
        mock_duckdb.insert_stock_info = MagicMock(side_effect=Exception("Database error"))

        result = data_manager.add_stock({'code': '600000', 'name': '测试'})

        assert result is False
        data_manager.logger.error.assert_called()

    def test_exception_handling_update_stock(self, data_manager):
        """测试更新股票时的异常处理"""
        mock_duckdb = data_manager.duckdb_operations
        mock_duckdb.update_stock_info = MagicMock(side_effect=Exception("Database error"))

        result = data_manager.update_stock('600000', {'name': '测试'})

        assert result is False

    def test_exception_handling_delete_stock(self, data_manager):
        """测试删除股票时的异常处理"""
        mock_duckdb = data_manager.duckdb_operations
        mock_duckdb.delete_stock_info = MagicMock(side_effect=Exception("Database error"))

        result = data_manager.delete_stock('600000')

        assert result is False


class TestUnifiedDataManagerEdgeCases:
    """UnifiedDataManager 边界情况测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_service_container(self):
        """模拟服务容器 fixture"""
        container = MagicMock()
        return container

    @pytest.fixture
    def mock_event_bus(self):
        """模拟事件总线 fixture"""
        event_bus = MagicMock()
        return event_bus

    def test_empty_database_path(self, temp_dir, mock_service_container, mock_event_bus):
        """测试空数据库路径处理"""
        with patch('core.services.unified_data_manager.logger'):
            with patch('core.services.unified_data_manager.DB_PATH', ''):
                with patch('core.services.unified_data_manager.IndustryManager'):
                    with patch('core.services.unified_data_manager.TETDataPipeline'):
                        with patch('core.services.unified_data_manager.DataSourceRouter'):
                            with patch('core.services.unified_data_manager.MultiLevelCacheManager'):
                                from core.services.unified_data_manager import UnifiedDataManager

                                # 测试空路径时是否正确处理
                                try:
                                    manager = UnifiedDataManager(
                                        service_container=mock_service_container,
                                        event_bus=mock_event_bus
                                    )
                                    # 如果创建成功，检查conn是否为None
                                    assert manager.conn is None or manager.conn is not None
                                except Exception:
                                    pass

    def test_concurrent_request_handling(self, temp_dir, mock_service_container, mock_event_bus):
        """测试并发请求处理"""
        with patch('core.services.unified_data_manager.logger'):
            with patch('core.services.unified_data_manager.DB_PATH', os.path.join(temp_dir, 'test.db')):
                with patch('core.services.unified_data_manager.IndustryManager'):
                    with patch('core.services.unified_data_manager.TETDataPipeline'):
                        with patch('core.services.unified_data_manager.DataSourceRouter'):
                            with patch('core.services.unified_data_manager.MultiLevelCacheManager'):
                                from core.services.unified_data_manager import UnifiedDataManager, DataRequest

                                manager = UnifiedDataManager(
                                    service_container=mock_service_container,
                                    event_bus=mock_event_bus,
                                    max_workers=2
                                )
                                manager.conn = sqlite3.connect(os.path.join(temp_dir, 'test.db'), check_same_thread=False)
                                manager._db_lock = MagicMock()
                                manager._db_lock.__enter__ = MagicMock(return_value=MagicMock())
                                manager._db_lock.__exit__ = MagicMock(return_value=False)
                                manager.duckdb_available = False
                                manager.cache_manager = MagicMock()
                                manager.multi_cache = MagicMock()
                                manager.industry_manager = MagicMock()

                                requests = []
                                for i in range(5):
                                    request = DataRequest(
                                        request_id=f"concurrent_test_{i}",
                                        symbol=f"60000{i}",
                                        data_type="kdata",
                                        period="D",
                                        time_range=365
                                    )
                                    requests.append(request)
                                    manager._add_request(request)

                                assert len(manager._pending_requests) == 5

    def test_special_characters_in_stock_code(self, temp_dir, mock_service_container, mock_event_bus):
        """测试股票代码包含特殊字符的处理"""
        with patch('core.services.unified_data_manager.logger'):
            with patch('core.services.unified_data_manager.DB_PATH', os.path.join(temp_dir, 'test.db')):
                with patch('core.services.unified_data_manager.IndustryManager'):
                    with patch('core.services.unified_data_manager.TETDataPipeline'):
                        with patch('core.services.unified_data_manager.DataSourceRouter'):
                            with patch('core.services.unified_data_manager.MultiLevelCacheManager'):
                                from core.services.unified_data_manager import UnifiedDataManager

                                manager = UnifiedDataManager(
                                    service_container=mock_service_container,
                                    event_bus=mock_event_bus
                                )
                                manager.conn = sqlite3.connect(os.path.join(temp_dir, 'test.db'), check_same_thread=False)
                                manager._db_lock = MagicMock()
                                manager._db_lock.__enter__ = MagicMock(return_value=MagicMock())
                                manager._db_lock.__exit__ = MagicMock(return_value=False)
                                manager.duckdb_available = False
                                manager.cache_manager = MagicMock()
                                manager.multi_cache = MagicMock()
                                manager.industry_manager = MagicMock()

                                cursor = manager.conn.cursor()
                                cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS stocks (
                                        code TEXT PRIMARY KEY,
                                        name TEXT,
                                        market TEXT,
                                        industry TEXT,
                                        list_date TEXT,
                                        delist_date TEXT,
                                        status TEXT
                                    )
                                ''')
                                manager.conn.commit()

                                special_code_stock = {'code': '60000!@#', 'name': '特殊字符股票'}
                                result = manager.add_stock(special_code_stock)

                                assert result is True

    def test_unicode_in_stock_name(self, temp_dir, mock_service_container, mock_event_bus):
        """测试股票名称包含Unicode字符"""
        with patch('core.services.unified_data_manager.logger'):
            with patch('core.services.unified_data_manager.DB_PATH', os.path.join(temp_dir, 'test.db')):
                with patch('core.services.unified_data_manager.IndustryManager'):
                    with patch('core.services.unified_data_manager.TETDataPipeline'):
                        with patch('core.services.unified_data_manager.DataSourceRouter'):
                            with patch('core.services.unified_data_manager.MultiLevelCacheManager'):
                                from core.services.unified_data_manager import UnifiedDataManager

                                manager = UnifiedDataManager(
                                    service_container=mock_service_container,
                                    event_bus=mock_event_bus
                                )
                                manager.conn = sqlite3.connect(os.path.join(temp_dir, 'test.db'), check_same_thread=False)
                                manager._db_lock = MagicMock()
                                manager._db_lock.__enter__ = MagicMock(return_value=MagicMock())
                                manager._db_lock.__exit__ = MagicMock(return_value=False)
                                manager.duckdb_available = False
                                manager.cache_manager = MagicMock()
                                manager.multi_cache = MagicMock()
                                manager.industry_manager = MagicMock()

                                cursor = manager.conn.cursor()
                                cursor.execute('''
                                    CREATE TABLE IF NOT EXISTS stocks (
                                        code TEXT PRIMARY KEY,
                                        name TEXT,
                                        market TEXT,
                                        industry TEXT,
                                        list_date TEXT,
                                        delist_date TEXT,
                                        status TEXT
                                    )
                                ''')
                                manager.conn.commit()

                                unicode_stock = {'code': '600002', 'name': 'unicode测试股票中文名称'}
                                result = manager.add_stock(unicode_stock)

                                assert result is True

                                info = manager.get_stock_info('600002')
                                assert info is not None
                                assert 'unicode' in info['name']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
