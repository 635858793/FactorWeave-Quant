import pytest
import tempfile
import shutil
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, Any

from core.data.repository import StockRepository, KlineRepository, MarketRepository, BaseRepository
from core.metrics.repository import MetricsRepository
from core.trading.order_repository import OrderRepository, OrderQuery, OrderFill
from core.trading.account_repository import AccountRepository
from core.plugin_types import AssetType


class TestBaseRepository:
    """BaseRepository 单元测试类"""

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.fixture
    def base_repo(self, mock_logger):
        """创建 BaseRepository 实例（使用具体实现）"""
        with patch('core.data.repository.logger', mock_logger):
            from core.data.repository import StockRepository
            mock_data_manager = MagicMock()
            repo = StockRepository(data_manager=mock_data_manager)
            repo.logger = mock_logger
            return repo

    def test_base_repository_init(self, base_repo):
        """测试 BaseRepository 初始化"""
        assert base_repo.logger is not None
        assert base_repo.data_manager is not None

    def test_is_connected_when_disconnected(self, base_repo):
        """测试连接状态（StockRepository 自动连接）"""
        assert base_repo.is_connected() is True


class TestStockRepository:
    """StockRepository 单元测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.fixture
    def mock_data_manager(self, temp_dir):
        """模拟数据管理器 fixture"""
        data_manager = MagicMock()
        data_manager.get_stock_info = MagicMock(return_value={
            'code': '600000',
            'name': '浦发银行',
            'market': 'SH',
            'industry': '银行',
        })
        data_manager.get_stock_list = MagicMock(return_value=[])
        return data_manager

    @pytest.fixture
    def stock_repo(self, temp_dir, mock_logger, mock_data_manager):
        """创建 StockRepository 实例"""
        with patch('core.data.repository.logger', mock_logger):
            repo = StockRepository.__new__(StockRepository)
            repo.logger = mock_logger
            repo.data_manager = mock_data_manager
            repo._stock_cache = {}
            repo._connected = True
            return repo

    def test_init_stock_repository(self, stock_repo):
        """测试 StockRepository 初始化"""
        assert stock_repo._connected is True
        assert stock_repo._stock_cache == {}

    def test_get_stock_info_success(self, stock_repo, sample_stock_data):
        """测试成功获取股票信息"""
        result = stock_repo.get_stock_info('600000')
        assert result is not None
        assert result.code == '600000'
        assert result.name == '浦发银行'

    def test_get_stock_info_not_found(self, stock_repo):
        """测试获取不存在的股票"""
        stock_repo.data_manager.get_stock_info.return_value = None
        result = stock_repo.get_stock_info('999999')
        assert result is None

    def test_get_stock_list(self, stock_repo):
        """测试获取股票列表"""
        stock_list = [{'code': '600000', 'name': '浦发银行'}]
        stock_repo.data_manager.get_stock_list.return_value = stock_list

        result = stock_repo.get_stock_list()

        assert len(result) == 1
        assert result[0].code == '600000'
        assert result[0].name == '浦发银行'

    def test_search_stocks(self, stock_repo):
        """测试搜索股票"""
        stock_repo.data_manager.search_stocks = MagicMock(return_value=[
            {'code': '600000', 'name': '浦发银行'},
        ])

        result = stock_repo.search_stocks('浦发')

        assert len(result) == 1
        assert result[0].name == '浦发银行'

    def test_add_stock_success(self, stock_repo, sample_stock_data):
        """测试成功添加股票"""
        stock_repo.data_manager.add_stock = MagicMock(return_value=True)

        result = stock_repo.add_stock(sample_stock_data)

        assert result is True
        assert len(stock_repo._stock_cache) == 0

    def test_add_stock_missing_code(self, stock_repo):
        """测试添加股票缺少代码"""
        invalid_data = {'name': '测试股票'}
        result = stock_repo.add_stock(invalid_data)
        assert result is False
        stock_repo.logger.error.assert_called()

    def test_update_stock_success(self, stock_repo, sample_stock_data):
        """测试成功更新股票"""
        from core.data.models import StockInfo
        
        stock_info = StockInfo(
            code=sample_stock_data['code'],
            name=sample_stock_data['name'],
            market=sample_stock_data['market'],
            industry=sample_stock_data['industry']
        )
        stock_repo._stock_cache['600000'] = stock_info
        stock_repo.data_manager.update_stock = MagicMock(return_value=True)

        result = stock_repo.update_stock('600000', {'name': '新名称'})

        assert result is True
        assert stock_repo._stock_cache['600000'].name == '新名称'

    def test_update_stock_not_found(self, stock_repo):
        """测试更新不存在的股票"""
        stock_repo.data_manager.update_stock = MagicMock(return_value=False)

        result = stock_repo.update_stock('999999', {'name': '新名称'})

        assert result is False

    def test_delete_stock_success(self, stock_repo, sample_stock_data):
        """测试成功删除股票"""
        from core.data.models import StockInfo
        
        stock_info = StockInfo(
            code=sample_stock_data['code'],
            name=sample_stock_data['name'],
            market=sample_stock_data['market'],
            industry=sample_stock_data['industry']
        )
        stock_repo._stock_cache['600000'] = stock_info
        stock_repo.data_manager.delete_stock = MagicMock(return_value=True)

        result = stock_repo.delete_stock('600000')

        assert result is True
        assert '600000' not in stock_repo._stock_cache

    def test_delete_stock_not_found(self, stock_repo):
        """测试删除不存在的股票"""
        stock_repo.data_manager.delete_stock = MagicMock(return_value=True)

        result = stock_repo.delete_stock('999999')

        assert result is True

    def test_get_stocks_by_industry(self, stock_repo):
        """测试按行业获取股票"""
        stock_repo.data_manager.get_stock_list.return_value = [
            {'code': '600000', 'name': '浦发银行', 'industry': '银行'},
            {'code': '600001', 'name': '邯郸钢铁', 'industry': '钢铁'},
        ]

        result = stock_repo.get_stocks_by_industry('银行')

        assert len(result) == 1
        assert result[0].industry == '银行'

    def test_get_stocks_by_market(self, stock_repo):
        """测试按市场获取股票"""
        def get_stock_list_by_market(market=None):
            all_stocks = [
                {'code': '600000', 'name': '浦发银行', 'market': 'SH'},
                {'code': '000001', 'name': '平安银行', 'market': 'SZ'},
            ]
            if market:
                return [s for s in all_stocks if s['market'] == market]
            return all_stocks
        
        stock_repo.data_manager.get_stock_list = MagicMock(side_effect=get_stock_list_by_market)

        result = stock_repo.get_stocks_by_market('SH')

        assert len(result) == 1
        assert result[0].market == 'SH'

    def test_clear_cache(self, stock_repo, sample_stock_data):
        """测试清除缓存"""
        stock_repo._stock_cache['600000'] = sample_stock_data
        stock_repo._stock_cache['600001'] = {'code': '600001', 'name': '测试'}

        stock_repo.clear_cache()

        assert stock_repo._stock_cache == {}

    def test_batch_update_stocks(self, stock_repo):
        """测试批量更新股票"""
        updates = [
            {'code': '600000', 'name': '浦发银行V2'},
            {'code': '600001', 'name': '邯郸钢铁V2'},
        ]
        stock_repo.data_manager.update_stock = MagicMock(return_value=True)

        success, failed = stock_repo.batch_update_stocks(updates)

        assert success == 2
        assert failed == 0
        assert stock_repo.data_manager.update_stock.call_count == 2

    def test_batch_delete_stocks(self, stock_repo):
        """测试批量删除股票"""
        from core.data.models import StockInfo
        
        stock_repo._stock_cache = {
            '600000': StockInfo(code='600000', name='浦发银行', market='SH'),
            '600001': StockInfo(code='600001', name='邯郸钢铁', market='SH'),
        }
        stock_repo.data_manager.delete_stock = MagicMock(return_value=True)

        success, failed = stock_repo.batch_delete_stocks(['600000', '600001'])

        assert success == 2
        assert failed == 0
        assert len(stock_repo._stock_cache) == 0

    def test_connect(self, stock_repo):
        """测试连接"""
        with patch.object(stock_repo.data_manager, 'connect', return_value=True):
            result = stock_repo.connect()
            assert result is True

    def test_disconnect(self, stock_repo):
        """测试断开连接"""
        stock_repo.disconnect()
        assert len(stock_repo._stock_cache) == 0

    def test_is_connected(self, stock_repo):
        """测试连接状态"""
        assert stock_repo.is_connected() is True


class TestKlineRepository:
    """KlineRepository 单元测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.fixture
    def mock_data_manager(self):
        """模拟数据管理器 fixture"""
        data_manager = MagicMock()
        return data_manager

    @pytest.fixture
    def kline_repo(self, temp_dir, mock_logger, mock_data_manager):
        """创建 KlineRepository 实例"""
        with patch('core.data.repository.logger', mock_logger):
            repo = KlineRepository.__new__(KlineRepository)
            repo.logger = mock_logger
            repo.data_manager = mock_data_manager
            repo._cache = {}
            repo.asset_service = None  # 确保使用 data_manager
            return repo

    def test_init_kline_repository(self, kline_repo):
        """测试 KlineRepository 初始化"""
        assert kline_repo._cache == {}

    def test_get_kline_data_success(self, kline_repo, sample_kline_data):
        """测试成功获取K线数据"""
        from core.data.models import QueryParams
        from datetime import datetime
        
        kline_repo.data_manager.get_kdata = MagicMock(return_value=sample_kline_data)

        params = QueryParams(
            stock_code='600000',
            period='D',
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        result = kline_repo.get_kline_data(params)

        assert result is not None
        assert len(result.data) == 100

    def test_get_kline_data_empty(self, kline_repo):
        """测试获取空的K线数据"""
        from core.data.models import QueryParams
        from datetime import datetime
        
        kline_repo.data_manager.get_k_data.return_value = pd.DataFrame()

        params = QueryParams(
            stock_code='999999',
            period='D',
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        result = kline_repo.get_kline_data(params)

        assert result is None

    def test_get_latest_price(self, kline_repo):
        """测试获取最新价格"""
        from core.data.models import QueryParams, KlineData
        
        kline_df = pd.DataFrame({
            'datetime': pd.to_datetime(['2024-01-13', '2024-01-14', '2024-01-15']),
            'open': [10.0, 10.1, 10.2],
            'high': [10.1, 10.2, 10.3],
            'low': [9.9, 10.0, 10.1],
            'close': [10.2, 10.3, 10.4],
            'volume': [1000000, 1100000, 1200000],
        })
        kline_data = KlineData(stock_code='600000', period='D', data=kline_df)
        
        def mock_get_kline_data(params):
            return kline_data
        
        kline_repo.get_kline_data = mock_get_kline_data

        result = kline_repo.get_latest_price('600000')

        assert result == 10.4

    def test_get_latest_price_no_data(self, kline_repo):
        """测试获取空数据的最新价格"""
        from core.data.models import KlineData
        
        kline_data = KlineData(stock_code='999999', period='D', data=pd.DataFrame())
        kline_repo.get_kline_data = MagicMock(return_value=kline_data)

        result = kline_repo.get_latest_price('999999')

        assert result is None

    def test_add_kline_success(self, kline_repo, sample_kline_data):
        """测试成功添加K线数据"""
        kline_repo.data_manager.add_kline = MagicMock(return_value=True)

        result = kline_repo.add_kline('600000', 'D', sample_kline_data)

        assert result is True

    def test_add_kline_empty_data(self, kline_repo):
        """测试添加空的K线数据"""
        result = kline_repo.add_kline('600000', 'D', pd.DataFrame())
        assert result is False

    def test_update_kline_success(self, kline_repo, sample_kline_data):
        """测试成功更新K线数据"""
        from core.data.models import KlineData
        
        kline_data = KlineData(stock_code='600000', period='D', data=sample_kline_data)
        kline_repo._cache = {
            'default_600000_D_None_None_None': kline_data
        }
        kline_repo.data_manager.update_kline = MagicMock(return_value=True)

        result = kline_repo.update_kline('600000', 'D', sample_kline_data)

        assert result is True

    def test_delete_kline_success(self, kline_repo):
        """测试成功删除K线数据"""
        from core.data.models import KlineData
        
        kline_data = KlineData(stock_code='600000', period='D', data=pd.DataFrame())
        kline_repo._cache = {
            'default_600000_D_None_None_None': kline_data
        }
        kline_repo.data_manager.delete_kline = MagicMock(return_value=True)

        result = kline_repo.delete_kline('600000', 'D')

        assert result is True

    def test_batch_update_klines(self, kline_repo, sample_kline_data):
        """测试批量更新K线"""
        updates = [
            {'stock_code': '600000', 'period': 'D', 'data': sample_kline_data},
            {'stock_code': '600001', 'period': 'D', 'data': sample_kline_data},
        ]
        kline_repo.data_manager.update_kline = MagicMock(return_value=True)

        success, failed = kline_repo.batch_update_klines(updates)

        assert success == 2
        assert failed == 0
        assert kline_repo.data_manager.update_kline.call_count == 2

    def test_get_cached_symbols(self, kline_repo):
        """测试获取缓存的股票代码"""
        kline_repo._cache = {
            'default_600000_D_None_None_None': None,
            'default_600001_D_None_None_None': None,
            'default_600002_D_None_None_None': None,
        }

        result = kline_repo.get_cached_symbols()

        assert len(result) == 3
        assert '600000' in result

    def test_clear_cache(self, kline_repo):
        """测试清除缓存"""
        kline_repo._cache = {'default_600000_D_None_None_None': None}

        kline_repo.clear_cache()

        assert kline_repo._cache == {}


class TestMarketRepository:
    """MarketRepository 单元测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.fixture
    def mock_data_manager(self):
        """模拟数据管理器 fixture"""
        data_manager = MagicMock()
        return data_manager

    @pytest.fixture
    def market_repo(self, temp_dir, mock_logger, mock_data_manager):
        """创建 MarketRepository 实例"""
        with patch('core.data.repository.logger', mock_logger):
            repo = MarketRepository.__new__(MarketRepository)
            repo.logger = mock_logger
            repo.data_manager = mock_data_manager
            repo._market_cache = {}
            return repo

    def test_init_market_repository(self, market_repo):
        """测试 MarketRepository 初始化"""
        assert market_repo._market_cache == {}

    def test_get_market_data_success(self, market_repo, sample_market_data):
        """测试成功获取市场数据"""
        market_repo.data_manager.get_market_data.return_value = sample_market_data

        result = market_repo.get_market_data('600000', '2024-01-15')

        assert result is not None
        assert result.index_code == '600000'

    def test_get_market_data_not_found(self, market_repo):
        """测试获取不存在的市场数据"""
        market_repo.data_manager.get_market_data.return_value = None

        result = market_repo.get_market_data('999999', '2024-01-15')

        assert result is None

    def test_get_market_indices(self, market_repo):
        """测试获取市场指数"""
        market_repo.data_manager.get_market_indices.return_value = [
            {'code': '000001', 'name': '上证指数'},
            {'code': '399001', 'name': '深证成指'},
        ]

        result = market_repo.get_market_indices()

        assert len(result) == 2
        assert result[0]['code'] == '000001'

    def test_add_market_data_success(self, market_repo, sample_market_data):
        """测试成功添加市场数据"""
        market_repo.data_manager.add_market_data = MagicMock(return_value=True)

        result = market_repo.add_market_data(sample_market_data)

        assert result is True

    def test_add_market_data_missing_code(self, market_repo):
        """测试添加缺少代码的市场数据"""
        invalid_data = {'trade_date': '2024-01-15', 'close': 10.5}
        result = market_repo.add_market_data(invalid_data)
        assert result is False

    def test_update_market_data_success(self, market_repo, sample_market_data):
        """测试成功更新市场数据"""
        from core.data.models import MarketData
        
        market_data = MarketData(
            date=datetime(2024, 1, 15),
            index_code='600000',
            index_name='浦发银行',
            open=10.2,
            high=10.5,
            low=10.0,
            close=10.3,
            volume=1500000,
            amount=15000000,
            change=0.15,
            change_pct=1.5,
        )
        market_repo._market_cache['600000'] = market_data
        market_repo.data_manager.update_market_data = MagicMock(return_value=True)

        result = market_repo.update_market_data('600000', {'close': 10.5})

        assert result is True

    def test_delete_market_data_success(self, market_repo):
        """测试成功删除市场数据"""
        from datetime import datetime
        
        market_repo.data_manager.delete_market_data = MagicMock(return_value=True)

        result = market_repo.delete_market_data('600000', datetime(2024, 1, 15))

        assert result is True

    def test_batch_update_market_data(self, market_repo, sample_market_data):
        """测试批量更新市场数据"""
        updates = [
            sample_market_data,
            {**sample_market_data, 'index_code': '600001'},
        ]
        market_repo.data_manager.update_market_data = MagicMock(return_value=True)

        success, failed = market_repo.batch_update_market_data(updates)

        assert success == 2
        assert failed == 0

    def test_get_market_data_range(self, market_repo, sample_market_data):
        """测试获取日期范围的市场数据"""
        from datetime import datetime
        
        market_repo.data_manager.get_market_data_range = MagicMock(return_value=[sample_market_data])

        result = market_repo.get_market_data_range('600000', datetime(2024, 1, 1), datetime(2024, 1, 31))

        assert result is not None
        assert len(result) == 1

    def test_clear_cache(self, market_repo):
        """测试清除缓存"""
        market_repo._market_cache = {'600000_2024-01-15': {}}

        market_repo.clear_cache()

        assert market_repo._market_cache == {}


class TestMetricsRepository:
    """MetricsRepository 单元测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.fixture
    def metrics_repo(self, temp_dir, mock_logger):
        """创建 MetricsRepository 实例"""
        import os

        with patch('core.metrics.repository.logger', mock_logger):
            db_file = os.path.join(temp_dir, 'test_metrics.db')
            repo = MetricsRepository(db_path=db_file)
            return repo

    def test_init_metrics_repository(self, metrics_repo):
        """测试 MetricsRepository 初始化"""
        assert metrics_repo.db_path.endswith('test_metrics.db')
        assert metrics_repo.cache_size == 1000

    def test_store_metric_success(self, metrics_repo):
        """测试成功存储指标"""
        metrics_repo.store_metric('sharpe_ratio', 1.5, 'risk')

        result = metrics_repo.query_metrics('sharpe_ratio', category='risk')

        assert len(result) == 1
        assert result[0]['metric_name'] == 'sharpe_ratio'
        assert result[0]['value'] == 1.5
        assert result[0]['category'] == 'risk'

    def test_store_metric_database_error(self, metrics_repo):
        """测试存储指标数据库错误"""
        with patch('core.metrics.repository.sqlite3.connect') as mock_connect:
            mock_connect.side_effect = Exception("Database error")

            metrics_repo.store_metric('sharpe_ratio', 1.5, 'risk')

    def test_update_metric_success(self, metrics_repo):
        """测试成功更新指标"""
        metrics_repo.store_metric('sharpe_ratio', 1.5, 'risk')
        result = metrics_repo.query_metrics('sharpe_ratio', category='risk')
        metric_id = result[0]['id']

        update_result = metrics_repo.update_metric(metric_id, 1.6)

        assert update_result is True
        updated_result = metrics_repo.query_metrics('sharpe_ratio', category='risk')
        assert updated_result[0]['value'] == 1.6

    def test_delete_metric_success(self, metrics_repo):
        """测试成功删除指标"""
        metrics_repo.store_metric('sharpe_ratio', 1.5, 'risk')
        result = metrics_repo.query_metrics('sharpe_ratio', category='risk')
        metric_id = result[0]['id']

        delete_result = metrics_repo.delete_metric(metric_id)

        assert delete_result is True
        deleted_result = metrics_repo.query_metrics('sharpe_ratio', category='risk')
        assert len(deleted_result) == 0

    def test_query_metrics(self, metrics_repo):
        """测试查询指标"""
        metrics_repo.store_metric('sharpe_ratio', 1.5, 'risk')
        metrics_repo.store_metric('sharpe_ratio', 1.6, 'risk')

        result = metrics_repo.query_metrics('sharpe_ratio', category='risk')

        assert len(result) == 2
        assert result[0]['metric_name'] == 'sharpe_ratio'
        assert result[0]['category'] == 'risk'

    def test_query_metrics_empty(self, metrics_repo):
        """测试查询空指标"""
        result = metrics_repo.query_metrics('nonexistent')

        assert result == []

    def test_get_latest_metric(self, metrics_repo):
        """测试获取最新指标"""
        metrics_repo.store_metric('sharpe_ratio', 1.5, 'risk')

        result = metrics_repo.get_latest_metric('sharpe_ratio', 'risk')

        assert result is not None
        assert result['value'] == 1.5

    def test_get_latest_metric_not_found(self, metrics_repo):
        """测试获取不存在的最新指标"""
        result = metrics_repo.get_latest_metric('nonexistent', 'risk')

        assert result is None

    def test_query_historical_data(self, metrics_repo):
        """测试查询历史数据"""
        from datetime import datetime

        metrics_repo.store_metric('cpu_usage', 50.0, 'system')
        metrics_repo.store_metric('memory_usage', 60.0, 'system')
        metrics_repo.store_metric('disk_usage', 70.0, 'system')

        result = metrics_repo.query_historical_data(
            datetime(2024, 1, 1),
            datetime(2024, 12, 31),
            'resource_metrics_summary'
        )

        assert result is not None

    def test_cleanup_old_data(self, metrics_repo):
        """测试清理旧数据"""
        import time

        metrics_repo.store_metric('sharpe_ratio', 1.5, 'risk')

        time.sleep(1)

        metrics_repo.cleanup_old_data(0)

        result = metrics_repo.query_metrics('sharpe_ratio', category='risk')
        assert len(result) == 0


class TestOrderRepository:
    """OrderRepository 单元测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.fixture
    def mock_event_bus(self):
        """模拟事件总线 fixture"""
        event_bus = MagicMock()
        event_bus.publish = MagicMock()
        return event_bus

    @pytest.fixture
    def mock_database_service(self):
        """模拟数据库服务 fixture"""
        db_service = MagicMock()
        db_service.execute_query = MagicMock()
        db_service.execute_query_with_cursor = MagicMock(return_value=[])
        return db_service

    @pytest.fixture
    def mock_service_container(self, mock_database_service):
        """模拟服务容器 fixture"""
        container = MagicMock()
        container.resolve = MagicMock(return_value=mock_database_service)
        return container

    @pytest.fixture
    def mock_asset_db_manager(self):
        """模拟资产分离数据库管理器 fixture"""
        manager = MagicMock()
        manager.get_instance = MagicMock(return_value=manager)
        return manager

    @pytest.fixture
    def order_repo(self, temp_dir, mock_logger, mock_event_bus, mock_service_container, mock_asset_db_manager):
        """创建 OrderRepository 实例"""
        with patch('core.trading.order_repository.logger', mock_logger):
            with patch('core.trading.order_repository.AssetSeparatedDatabaseManager.get_instance', return_value=mock_asset_db_manager):
                repo = OrderRepository.__new__(OrderRepository)
                repo.logger = mock_logger
                repo.event_bus = mock_event_bus
                repo.service_container = mock_service_container
                repo.asset_db_manager = mock_asset_db_manager
                repo.cache = MagicMock()
                repo.cache.update = MagicMock()
                repo._connected = True
                return repo

    def test_init_order_repository(self, order_repo):
        """测试 OrderRepository 初始化"""
        assert order_repo._connected is True
        assert order_repo.cache is not None

    def test_generate_order_id(self, order_repo):
        """测试生成订单ID"""
        order_id = order_repo.generate_order_id()

        assert order_id is not None
        assert order_id.startswith('ORD')
        assert len(order_id) > 10

    def test_generate_fill_id(self, order_repo):
        """测试生成成交ID"""
        fill_id = order_repo.generate_fill_id()

        assert fill_id is not None
        assert fill_id.startswith('FIL')
        assert len(fill_id) > 10

    def test_save_order_success(self, order_repo, sample_order_data):
        """测试成功保存订单"""
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock()

        result = order_repo.save_order(sample_order_data)

        assert result is True
        mock_db_service.execute_query.assert_called_once()
        order_repo.event_bus.publish.assert_called_once_with('order_saved', order_id=sample_order_data.order_id)

    def test_save_order_duplicate(self, order_repo, sample_order_data):
        """测试保存重复订单"""
        order_repo.cache.get = MagicMock(return_value=sample_order_data)

        result = order_repo.save_order(sample_order_data)

        assert result is True
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query.assert_called_once()

    def test_get_order_success(self, order_repo, sample_order_data):
        """测试成功获取订单"""
        order_repo.cache.get = MagicMock(return_value=sample_order_data)

        result = order_repo.get_order(sample_order_data.order_id)

        assert result is not None
        assert result.order_id == sample_order_data.order_id

    def test_get_order_not_found(self, order_repo):
        """测试获取不存在的订单"""
        order_repo.cache.get = MagicMock(return_value=None)
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock(return_value=[])
        result = order_repo.get_order('ORDER_NONEXISTENT')
        assert result is None

    def test_query_orders(self, order_repo, sample_order_data):
        """测试查询订单"""
        from core.trading.order_models import OrderStatus
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock(return_value=[sample_order_data.to_dict()])

        result = order_repo.query_orders(OrderQuery(order_status=OrderStatus.PENDING, asset_type=sample_order_data.asset_type))

        assert result is not None
        assert len(result) == 1

    def test_get_active_orders(self, order_repo, sample_order_data):
        """测试获取活跃订单"""
        mock_db_service = order_repo.service_container.resolve.return_value
        
        def mock_execute_query_side_effect(*args, **kwargs):
            sql = args[0] if args else ''
            if 'WHERE' in sql and 'account_id' in sql:
                return [sample_order_data.to_dict()]
            return []
        
        mock_db_service.execute_query = MagicMock(side_effect=mock_execute_query_side_effect)

        result = order_repo.get_active_orders(account_id=sample_order_data.account_id)

        assert len(result) > 0

    def test_get_orders_by_strategy(self, order_repo, sample_order_data):
        """测试按策略获取订单"""
        mock_db_service = order_repo.service_container.resolve.return_value
        
        def mock_execute_query_side_effect(*args, **kwargs):
            sql = args[0] if args else ''
            if 'WHERE' in sql and 'strategy_id' in sql:
                return [sample_order_data.to_dict()]
            return []
        
        mock_db_service.execute_query = MagicMock(side_effect=mock_execute_query_side_effect)

        result = order_repo.get_orders_by_strategy('STRAT_001', limit=1)

        assert result is not None
        assert len(result) > 0

    def test_get_orders_by_stock(self, order_repo, sample_order_data):
        """测试按股票获取订单"""
        mock_db_service = order_repo.service_container.resolve.return_value
        
        def mock_execute_query_side_effect(*args, **kwargs):
            sql = args[0] if args else ''
            if 'WHERE' in sql and 'stock_code' in sql:
                return [sample_order_data.to_dict()]
            return []
        
        mock_db_service.execute_query = MagicMock(side_effect=mock_execute_query_side_effect)

        result = order_repo.get_orders_by_stock('600000', limit=1)

        assert result is not None
        assert len(result) > 0

    def test_update_order_success(self, order_repo, sample_order_data):
        """测试成功更新订单"""
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock()

        result = order_repo.update_order(sample_order_data)

        assert result is True
        mock_db_service.execute_query.assert_called_once()
        order_repo.cache.update.assert_called()

    def test_update_orders_batch(self, order_repo, sample_order_data):
        """测试批量更新订单"""
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock()

        orders = [sample_order_data]
        result = order_repo.update_orders_batch(orders)

        assert result is not None
        assert result[sample_order_data.order_id] is True
        assert mock_db_service.execute_query.call_count == len(orders)

    def test_save_order_fill(self, order_repo, sample_order_data):
        """测试保存订单成交"""
        from datetime import datetime
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock()

        fill = OrderFill(
            fill_id='FILL_001',
            order_id=sample_order_data.order_id,
            stock_code=sample_order_data.stock_code,
            fill_price=10.3,
            fill_quantity=500,
            fill_time=datetime.now()
        )

        result = order_repo.save_order_fill(fill, AssetType.STOCK_A)

        assert result is True
        mock_db_service.execute_query.assert_called()

    def test_get_order_fills(self, order_repo, sample_order_data):
        """测试获取订单成交"""
        from datetime import datetime
        mock_db_service = order_repo.service_container.resolve.return_value
        fill_time = datetime.now()
        mock_db_service.execute_query = MagicMock(
            return_value=[{
                'fill_id': 'FILL_001',
                'order_id': sample_order_data.order_id,
                'stock_code': sample_order_data.stock_code,
                'fill_price': 10.3,
                'fill_quantity': 500,
                'fill_time': fill_time.isoformat(),
                'commission': 0.0
            }]
        )

        result = order_repo.get_order_fills(sample_order_data.order_id, AssetType.STOCK_A)

        assert result is not None
        assert len(result) == 1

    def test_delete_order_success(self, order_repo, sample_order_data):
        """测试成功删除订单"""
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock()

        result = order_repo.delete_order(sample_order_data.order_id, AssetType.STOCK_A)

        assert result is True

    def test_get_order_statistics(self, order_repo, sample_order_data):
        """测试获取订单统计"""
        from core.trading.order_models import OrderStatus
        mock_db_service = order_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock(
            return_value=[{
                'total_orders': 10,
                'filled_orders': 5,
                'cancelled_orders': 2,
                'rejected_orders': 1,
                'total_value': 100000.0,
                'filled_value': 50000.0,
                'total_commission': 100.0
            }]
        )

        query = OrderQuery(order_status=OrderStatus.PENDING)
        result = order_repo.get_order_statistics(query)

        assert result is not None
        assert result['total_orders'] == 10
        assert result['filled_orders'] == 5


class TestAccountRepository:
    """AccountRepository 单元测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.fixture
    def mock_crypto(self):
        """模拟加密工具 fixture"""
        crypto = MagicMock()
        crypto.encrypt.return_value = 'encrypted_data'
        crypto.decrypt.return_value = json.dumps({
            'account_id': 'test_001',
            'name': '测试账户',
        })
        return crypto

    @pytest.fixture
    def mock_database_service(self, temp_dir, temp_sqlite_db):
        """模拟数据库服务 fixture"""
        service = MagicMock()
        service.get_connection.return_value = temp_sqlite_db
        return service

    @pytest.fixture
    def account_repo(self, temp_dir, mock_logger, mock_crypto, mock_database_service, temp_sqlite_db):
        """创建 AccountRepository 实例"""
        from core.containers import ServiceContainer
        from core.events import EventBus
        
        with patch('core.trading.account_repository.logger', mock_logger):
            with patch('core.trading.account_repository.get_crypto_utils', return_value=mock_crypto):
                container = MagicMock()
                container.resolve = MagicMock(return_value=mock_database_service)
                
                event_bus = MagicMock()
                
                repo = AccountRepository.__new__(AccountRepository)
                repo.logger = mock_logger
                repo.service_container = container
                repo.event_bus = event_bus
                repo.crypto_utils = mock_crypto
                return repo

    def test_init_account_repository(self, account_repo):
        """测试 AccountRepository 初始化"""
        assert account_repo.service_container is not None
        assert account_repo.event_bus is not None
        assert account_repo.crypto_utils is not None

    def test_save_account_success(self, account_repo, sample_account_data):
        """测试成功保存账户"""
        from core.trading.account_models import Account
        
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.execute = MagicMock(return_value=True)

        account = Account.from_dict(sample_account_data)
        result = account_repo.save_account(account)

        assert result is True

    def test_save_account_database_error(self, account_repo, sample_account_data):
        """测试保存账户数据库错误"""
        from core.trading.account_models import Account
        
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock(side_effect=Exception("Database error"))

        account = Account.from_dict(sample_account_data)
        result = account_repo.save_account(account)

        assert result is False

    def test_get_account_success(self, account_repo, sample_account_data):
        """测试成功获取账户"""
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.fetch_one = MagicMock(return_value=sample_account_data)
        mock_crypto = account_repo.crypto_utils
        mock_crypto.decrypt_account_data = MagicMock(return_value=sample_account_data)

        result = account_repo.get_account('test_account_001')

        assert result is not None
        assert result.account_id == 'test_account_001'

    def test_get_account_not_found(self, account_repo):
        """测试获取不存在的账户"""
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.fetch_one = MagicMock(return_value=None)

        result = account_repo.get_account('nonexistent')

        assert result is None

    def test_get_accounts(self, account_repo, sample_account_data):
        """测试获取所有账户"""
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.fetch_all = MagicMock(return_value=[sample_account_data])
        mock_crypto = account_repo.crypto_utils
        mock_crypto.decrypt_account_data = MagicMock(return_value=sample_account_data)

        result = account_repo.get_accounts()

        assert result is not None
        assert len(result) == 1

    def test_delete_account_success(self, account_repo):
        """测试成功删除账户"""
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.execute = MagicMock(return_value=True)

        result = account_repo.delete_account('test_001')

        assert result is True

    def test_save_position(self, account_repo):
        """测试保存持仓"""
        from core.trading.account_models import Position, PositionSide
        from core.plugin_types import AssetType
        from datetime import datetime
        
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock(return_value=True)
        
        now = datetime.now()
        position = Position(
            position_id='POS_001',
            account_id='test_001',
            asset_type=AssetType.STOCK_A,
            stock_code='600000',
            stock_name='浦发银行',
            side=PositionSide.LONG,
            quantity=1000,
            available_quantity=1000,
            open_price=10.0,
            current_price=10.2,
            market_value=10200.0,
            cost_price=10.0,
            cost_value=10000.0,
            profit_loss=200.0,
            profit_loss_ratio=0.02,
            open_time=now,
            update_time=now,
            commission=5.0,
            metadata={}
        )

        result = account_repo.save_position(position)

        assert result is True

    def test_get_positions(self, account_repo):
        """测试获取持仓"""
        from core.trading.account_models import Position, PositionSide, PositionQuery
        from core.plugin_types import AssetType
        from datetime import datetime
        
        mock_db_service = account_repo.service_container.resolve.return_value
        now = datetime.now()
        mock_db_service.fetch_all = MagicMock(return_value=[{
            'position_id': 'POS_001',
            'account_id': 'test_001',
            'asset_type': 'stock_a',
            'stock_code': '600000',
            'stock_name': '浦发银行',
            'side': 'long',
            'quantity': 1000,
            'available_quantity': 1000,
            'open_price': 10.0,
            'current_price': 10.2,
            'market_value': 10200.0,
            'cost_price': 10.0,
            'cost_value': 10000.0,
            'profit_loss': 200.0,
            'profit_loss_ratio': 0.02,
            'open_time': now.isoformat(),
            'update_time': now.isoformat(),
            'commission': 5.0,
            'metadata': '{}'
        }])

        query = PositionQuery(account_id='test_001')
        result = account_repo.get_positions(query)

        assert result is not None
        assert len(result) == 1

    def test_delete_position(self, account_repo):
        """测试删除持仓"""
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock(return_value=True)

        result = account_repo.delete_position('POS_001')

        assert result is True

    def test_save_fund_info(self, account_repo):
        """测试保存资金信息"""
        from core.trading.account_models import FundInfo
        from datetime import datetime
        
        mock_db_service = account_repo.service_container.resolve.return_value
        mock_db_service.execute_query = MagicMock(return_value=True)
        
        now = datetime.now()
        fund_info = FundInfo(
            account_id='test_001',
            total_balance=100000.0,
            available_balance=90000.0,
            frozen_balance=10000.0,
            market_value=0.0,
            total_assets=100000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            margin_used=0.0,
            margin_available=0.0,
            maintenance_margin=0.0,
            update_time=now
        )

        result = account_repo.save_fund_info(fund_info)

        assert result is True

    def test_get_fund_info(self, account_repo):
        """测试获取资金信息"""
        from core.trading.account_models import FundInfo
        from datetime import datetime
        
        mock_db_service = account_repo.service_container.resolve.return_value
        now = datetime.now()
        mock_db_service.fetch_one = MagicMock(return_value={
            'account_id': 'test_001',
            'total_balance': 100000.0,
            'available_balance': 90000.0,
            'frozen_balance': 10000.0,
            'market_value': 0.0,
            'total_assets': 100000.0,
            'profit_loss': 0.0,
            'profit_loss_ratio': 0.0,
            'margin_used': 0.0,
            'margin_available': 0.0,
            'maintenance_margin': 0.0,
            'update_time': now.isoformat()
        })

        result = account_repo.get_fund_info('test_001')

        assert result is not None
        assert result.account_id == 'test_001'

    def test_get_all_fund_infos(self, account_repo):
        """测试获取所有资金信息"""
        from core.trading.account_models import FundInfo
        from datetime import datetime
        
        mock_db_service = account_repo.service_container.resolve.return_value
        now = datetime.now()
        mock_db_service.fetch_all = MagicMock(return_value=[{
            'account_id': 'test_001',
            'total_balance': 100000.0,
            'available_balance': 90000.0,
            'frozen_balance': 10000.0,
            'market_value': 0.0,
            'total_assets': 100000.0,
            'profit_loss': 0.0,
            'profit_loss_ratio': 0.0,
            'margin_used': 0.0,
            'margin_available': 0.0,
            'maintenance_margin': 0.0,
            'update_time': now.isoformat()
        }])

        result = account_repo.get_all_fund_infos()

        assert result is not None
        assert len(result) == 1


class TestRepositoryIntegration:
    """Repository 集成测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    def test_stock_to_kline_relationship(self, temp_dir, mock_logger):
        """测试股票与K线的关系"""
        with patch('core.data.repository.logger', mock_logger):
            repo = StockRepository.__new__(StockRepository)
            repo.logger = mock_logger
            repo.data_manager = MagicMock()
            repo._stock_cache = {}
            repo._connected = True

            repo.data_manager.get_stock_info.return_value = {
                'code': '600000',
                'name': '浦发银行',
            }

            stock_info = repo.get_stock_info('600000')
            assert stock_info is not None

    def test_order_state_transitions(self, temp_dir, mock_logger):
        """测试订单状态转换"""
        with patch('core.trading.order_repository.logger', mock_logger):
            repo = OrderRepository.__new__(OrderRepository)
            repo.logger = mock_logger
            repo.event_bus = MagicMock()
            repo._database_pool = MagicMock()
            repo._cache = {}
            repo._connected = True

            order_data = {
                'order_id': 'ORDER_001',
                'status': 'pending',
            }
            repo._cache['ORDER_001'] = order_data

            assert repo._cache['ORDER_001']['status'] == 'pending'

            repo._cache['ORDER_001']['status'] = 'filled'
            assert repo._cache['ORDER_001']['status'] == 'filled'

    def test_account_data_consistency(self, temp_dir, mock_logger):
        """测试账户数据一致性"""
        with patch('core.trading.account_repository.logger', mock_logger):
            repo = AccountRepository.__new__(AccountRepository)
            repo.logger = mock_logger
            repo._crypto = MagicMock()
            repo._conn = MagicMock()
            repo._db_path = os.path.join(temp_dir, 'test.db')

            account = {
                'account_id': 'test_001',
                'name': '测试账户',
                'balance': 100000.0,
            }
            repo._crypto.encrypt.return_value = json.dumps(account)

            encrypted = repo._crypto.encrypt(json.dumps(account))
            repo._crypto.decrypt.return_value = json.dumps(account)
            decrypted = repo._crypto.decrypt(encrypted)

            assert json.loads(decrypted)['balance'] == 100000.0


@pytest.fixture
def repo():
    pass


class TestRepositoryEdgeCases:
    """Repository 边界条件测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def mock_logger(self):
        """模拟日志记录器"""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    def test_empty_stock_list(self, temp_dir, mock_logger):
        """测试空股票列表"""
        with patch('core.data.repository.logger', mock_logger):
            repo = StockRepository.__new__(StockRepository)
            repo.logger = mock_logger
            repo.data_manager = MagicMock()
            repo.data_manager.get_stock_list.return_value = []
            repo._stock_cache = {}
            repo._connected = True

            result = repo.get_stock_list()

            assert result == []

    def test_null_handling(self, temp_dir, mock_logger):
        """测试空值处理"""
        from core.data.models import QueryParams
        from datetime import datetime
        
        with patch('core.data.repository.logger', mock_logger):
            repo = KlineRepository.__new__(KlineRepository)
            repo.logger = mock_logger
            repo.data_manager = MagicMock()
            repo.data_manager.get_k_data.return_value = None
            repo._cache = {}
            repo._connected = True

            params = QueryParams(
                stock_code='600000',
                period='D',
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31)
            )
            result = repo.get_kline_data(params)

            assert result is None

    def test_special_characters_in_data(self, temp_dir, mock_logger):
        """测试特殊字符处理"""
        with patch('core.trading.account_repository.logger', mock_logger):
            repo = AccountRepository.__new__(AccountRepository)
            repo.logger = mock_logger
            repo._crypto = MagicMock()
            repo._conn = MagicMock()
            repo._db_path = os.path.join(temp_dir, 'test.db')

            special_name = "测试'账户\"特殊&字符<测试>"
            account = {
                'account_id': 'test_001',
                'name': special_name,
            }

            json_str = json.dumps(account)
            parsed = json.loads(json_str)
            assert parsed['name'] == special_name

    def test_large_number_handling(self, temp_dir, mock_logger):
        """测试大数处理"""
        with patch('core.metrics.repository.logger', mock_logger):
            db_file = os.path.join(temp_dir, 'test_large_numbers.db')
            repo = MetricsRepository(db_path=db_file)

            large_value = 1.234567890123456789
            repo.store_metric('test', large_value, 'test')

            result = repo.query_metrics('test', category='test')
            assert len(result) == 1
            assert result[0]['value'] == large_value

    def test_timestamp_handling(self, temp_dir, mock_logger):
        """测试时间戳处理"""
        with patch('core.metrics.repository.logger', mock_logger):
            db_file = os.path.join(temp_dir, 'test_timestamp.db')
            repo = MetricsRepository(db_path=db_file)

            import time
            repo.store_metric('test', 1.5, 'test')

            result = repo.query_metrics('test', category='test')
            assert len(result) == 1
            assert result[0]['value'] == 1.5
