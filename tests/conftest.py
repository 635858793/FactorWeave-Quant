import sys
import os
from unittest.mock import MagicMock

# R256-P2: 测试专用占位符密钥 (仅测试进程, 不污染 .env; 参照 web/backend/config/settings.py:146-171 双闸)
# ENCRYPTION_KEY 由 Fernet.generate_key() 生成 (32-byte url-safe base64, 已实测 Fernet() 可解析)
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-r256-0123456789abcdef')
os.environ.setdefault('ENCRYPTION_KEY', 'gPvOPsE3pSmGEU9mC7r2AHrVToBWYgCbqFsxSUJiz_M=')

os.environ.setdefault('MPLBACKEND', 'Agg')

_QT_MOCK_MODULES = [
    'matplotlib.backends.backend_qt',
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_qt5agg',
]

_GUI_MOCK_MODULES = [
    # R258-P0: 移除 'gui' / 'gui.utils' / 'gui.utils.responsive_helper' 三行 ——
    # 实证 responsive_helper.py:27-31 无 QApplication 时安全返回 1.0 (offscreen 安全),
    # gui/__init__.py 为惰性 __getattr__ 导入 (gui/__init__.py:13-23), gui/utils/__init__.py 为空。
    # mock 顶层包会阻断真实子模块导入 (mock 无 __path__), 导致响应式工具不可测且
    # r25x 系列文件 collection 阶段 pop mock 后行为不一致 (R258 交叉验证实证)。
    # R261-c5: 移除 'gui.dialogs' 顶层 mock —— BaseDialog 构造路径不触碰
    # QApplication/desktop (base_dialog.py:133-144 构造, desktop 仅 showEvent:249 触发),
    # 允许真实子模块导入以支持真实 GUI 实例化测试 (tests/gui/test_base_dialog_real.py)。
    # 以下子模块经 R261-c5 独立进程实证存在硬问题, 保留/回退 mock:
    #  - strategy_manager_dialog: 模块级重依赖 (core.services.*/gui.components.*), 未纳入真实测试
    #  - intelligent_model_selection_dialog: 模块级硬导入 gui.widgets.intelligent_model_selection.* (L27-29)
    #  - plugin_manager_dialog_unified: PluginManagerDialogUnified 构造创建并 start QTimer (L582-590)
    #  - ai_prediction_config_dialog / account_management_dialog / distributed_node_monitor_dialog /
    #    distributed_service_monitor_dialog: 模块级 import 缺陷 (NameError: BaseDialog/QDialog 未定义)
    #  - data_management_dialog_unified / webgpu_status_dialog / indicator_selection_dialog /
    #    system_optimizer_dialog / quality_report_dialog / model_training_dialog:
    #    导入/实例化触发 Qt 硬崩溃 (0xC0000005/0xC0000409)
    #  - llm_config_dialog: 默认构造抛 AttributeError (llm_config_service 为 None)
    'gui.dialogs.strategy_manager_dialog',
    'gui.dialogs.intelligent_model_selection_dialog',
    'gui.dialogs.plugin_manager_dialog_unified',
    'gui.dialogs.ai_prediction_config_dialog',
    'gui.dialogs.account_management_dialog',
    'gui.dialogs.distributed_node_monitor_dialog',
    'gui.dialogs.distributed_service_monitor_dialog',
    'gui.dialogs.data_management_dialog_unified',
    'gui.dialogs.webgpu_status_dialog',
    'gui.dialogs.indicator_selection_dialog',
    'gui.dialogs.system_optimizer_dialog',
    'gui.dialogs.quality_report_dialog',
    'gui.dialogs.model_training_dialog',
    'gui.dialogs.llm_config_dialog',
    'gui.widgets',
    'gui.widgets.backtest_widget',
    'gui.widgets.trading_panel',
    'gui.widgets.enhanced_ui',
    'gui.widgets.enhanced_ui.order_book_widget',
    'gui.widgets.enhanced_ui.level2_data_panel',
    'gui.widgets.performance',
    'gui.widgets.performance.tabs',
    'core.ui',
    'core.ui.panels',
    'core.ui.panels.base_panel',
    'core.ui.panels.left_panel',
    'core.ui.panels.middle_panel',
    'core.ui.panels.right_panel',
    'core.ui.panels.bottom_panel',
    'core.ui.widgets',
    'core.coordinators.main_window_coordinator',
]

for _mod in _QT_MOCK_MODULES + _GUI_MOCK_MODULES:
    if _mod not in sys.modules:
        _mock = MagicMock()
        _mock.__name__ = _mod
        _mock.__file__ = f'<mock:{_mod}>'
        sys.modules[_mod] = _mock

import pytest
import tempfile
import shutil
from unittest.mock import patch
from typing import Generator, Dict, Any
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope='session')
def temp_dir():
    """临时目录 fixture"""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture(scope='session')
def mock_config(temp_dir) -> Dict[str, Any]:
    """模拟配置 fixture"""
    return {
        'database': {
            'path': temp_dir,
            'duckdb_path': os.path.join(temp_dir, 'market_data.duckdb'),
            'sqlite_path': os.path.join(temp_dir, 'hikyuu.db'),
        },
        'trading': {
            'default_account': 'test_account',
            'risk_level': 'medium',
        },
        'logging': {
            'level': 'DEBUG',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        },
    }


@pytest.fixture
def mock_service_container():
    """模拟服务容器 fixture"""
    container = MagicMock()
    container.resolve = MagicMock(return_value=MagicMock())
    return container


@pytest.fixture
def mock_event_bus():
    """模拟事件总线 fixture"""
    event_bus = MagicMock()
    event_bus.publish = MagicMock()
    event_bus.subscribe = MagicMock()
    event_bus.unsubscribe = MagicMock()
    return event_bus


@pytest.fixture
def sample_account_data() -> Dict[str, Any]:
    """示例账户数据 fixture"""
    return {
        'account_id': 'test_account_001',
        'account_name': '测试账户',
        'account_type': 'simulated',
        'status': 'active',
        'balance': 100000.0,
        'available_balance': 100000.0,
        'frozen_balance': 0.0,
        'market_value': 0.0,
        'total_assets': 100000.0,
        'profit_loss': 0.0,
        'profit_loss_ratio': 0.0,
        'create_time': datetime.now().isoformat(),
        'update_time': datetime.now().isoformat(),
        'user_id': 'test_user',
    }


@pytest.fixture
def sample_stock_data() -> Dict[str, Any]:
    """示例股票数据 fixture"""
    return {
        'code': '600000',
        'name': '浦发银行',
        'market': 'SH',
        'industry': '银行',
        'list_date': '1999-11-10',
        'status': 'active',
    }


@pytest.fixture
def sample_kline_data() -> pd.DataFrame:
    """示例K线数据 fixture"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    return pd.DataFrame({
        'trade_date': dates,
        'open': [10.0 + i * 0.1 for i in range(100)],
        'high': [10.5 + i * 0.1 for i in range(100)],
        'low': [9.5 + i * 0.1 for i in range(100)],
        'close': [10.2 + i * 0.1 for i in range(100)],
        'volume': [1000000 + i * 1000 for i in range(100)],
        'amount': [10000000 + i * 10000 for i in range(100)],
    })


@pytest.fixture
def sample_market_data() -> Dict[str, Any]:
    """示例行情数据 fixture"""
    return {
        'date': datetime(2024, 1, 15),
        'index_code': '600000',
        'index_name': '浦发银行',
        'open': 10.2,
        'high': 10.5,
        'low': 10.0,
        'close': 10.3,
        'volume': 1500000,
        'amount': 15000000,
        'change': 0.15,
        'change_pct': 1.5,
    }


@pytest.fixture
def sample_order_data():
    """示例订单数据 fixture"""
    from core.trading.order_models import Order, OrderType, OrderCategory, OrderStatus
    from core.plugin_types import AssetType
    
    now = datetime.now()
    return Order(
        order_id='ORDER_20240115_001',
        strategy_id='STRAT_001',
        asset_type=AssetType.STOCK_A,
        stock_code='600000',
        order_type=OrderType.BUY,
        order_category=OrderCategory.LIMIT,
        order_price=10.2,
        order_quantity=1000,
        order_status=OrderStatus.PENDING,
        create_time=now,
        update_time=now,
        user_id='test_user',
        account_id='test_account_001',
    )


@pytest.fixture
def temp_sqlite_db(temp_dir):
    """临时 SQLite 数据库 fixture"""
    db_path = os.path.join(temp_dir, 'test_db.sqlite')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            name TEXT,
            account_type TEXT,
            capital REAL,
            status TEXT,
            data TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            code TEXT PRIMARY KEY,
            name TEXT,
            market TEXT,
            industry TEXT,
            list_date TEXT,
            status TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            period TEXT,
            trade_date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            amount REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            trade_date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            amount REAL,
            change_pct REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            value REAL,
            timestamp INTEGER,
            metadata TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            account_id TEXT,
            symbol TEXT,
            side TEXT,
            order_type TEXT,
            price REAL,
            quantity INTEGER,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_duckdb_operations():
    """模拟 DuckDB 操作 fixture"""
    operations = MagicMock()
    operations.insert_stock_info = MagicMock(return_value=True)
    operations.update_stock_info = MagicMock(return_value=True)
    operations.delete_stock_info = MagicMock(return_value=True)
    operations.insert_kline_data = MagicMock(return_value=True)
    operations.delete_kline_data = MagicMock(return_value=True)
    operations.insert_market_data = MagicMock(return_value=True)
    operations.update_market_data = MagicMock(return_value=True)
    operations.delete_market_data = MagicMock(return_value=True)
    return operations


@pytest.fixture
def sample_risk_metrics() -> Dict[str, Any]:
    """示例风险指标 fixture"""
    return {
        'sharpe_ratio': 1.5,
        'max_drawdown': 0.15,
        'volatility': 0.2,
        'beta': 1.1,
        'alpha': 0.05,
        'var_95': 0.02,
        'sortino_ratio': 2.0,
    }


@pytest.fixture
def mock_logger():
    """模拟日志记录器 fixture"""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    return logger


@pytest.fixture
def app_config():
    """应用配置 fixture"""
    return {
        'app_name': 'Hikyuu UI Test',
        'version': '1.0.0',
        'debug': True,
        'log_level': 'DEBUG',
    }


def pytest_configure(config):
    """Pytest 配置钩子"""
    config.addinivalue_line(
        'markers', 'slow: marks tests as slow (deselect with \'-m "not slow"\')'
    )
    config.addinivalue_line(
        'markers', 'integration: marks tests as integration tests'
    )


def pytest_collection_modifyitems(config, items):
    """测试项目修改钩子"""
    for item in items:
        if 'slow' in item.name.lower():
            item.add_marker(pytest.mark.slow)
        if 'integration' in item.name.lower():
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def mock_crypto_utils():
    """模拟加密工具 fixture"""
    with patch('core.utils.crypto_utils.CryptoUtils') as mock:
        mock.encrypt = MagicMock(return_value='encrypted_data')
        mock.decrypt = MagicMock(return_value='{"key": "value"}')
        mock.generate_key = MagicMock(return_value='test_key_32_bytes_long_')
        yield mock


@pytest.fixture
def mock_database_service(temp_sqlite_db):
    """模拟数据库服务 fixture"""
    service = MagicMock()
    service.get_connection = MagicMock(return_value=temp_sqlite_db)
    service.execute_query = MagicMock(return_value=[])
    service.execute_update = MagicMock(return_value=1)
    return service


@pytest.fixture
def cleanup_temp_files(temp_dir):
    """清理临时文件 fixture"""
    yield
    for file in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception:
            pass


def pytest_runtest_setup(item):
    """每个测试前设置"""
    pass


def pytest_runtest_teardown(item, nextitem):
    """每个测试后清理"""
    pass


@pytest.fixture(scope='module')
def test_module():
    """测试模块 fixture"""
    class TestModule:
        def __init__(self):
            self.setup_complete = False
            self.test_data = {}

        def setup(self):
            self.setup_complete = True

        def add_test_data(self, key, value):
            self.test_data[key] = value

        def get_test_data(self, key):
            return self.test_data.get(key)

    module = TestModule()
    yield module
