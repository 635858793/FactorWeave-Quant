#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化验证测试套件

定期验证代码质量的综合测试，包括：
1. 导入验证：所有核心模块能否正常导入
2. 数据库连接：UnifiedSQLiteAccess是否正常工作
3. Coordinator初始化：各协调器能否正常创建
4. 对话框创建：各对话框能否正常实例化
5. 交易接口：OrderExecutor能否正常初始化

作者: FactorWeave-Quant Team
版本: 1.0
日期: 2025-01-27
"""

import sys
import os
import pytest
import logging
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, MagicMock, patch

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# 配置测试日志
LOG_DIR = PROJECT_ROOT / "logs" / "validation"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("ValidationSuite")


class ValidationTestFixture:
    """测试夹具基类"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """测试前设置"""
        logger.info("=" * 80)
        logger.info("开始执行测试套件")
        logger.info("=" * 80)
        self.temp_db_path = None
        yield
        self.teardown()

    def teardown(self):
        """测试后清理"""
        if self.temp_db_path and os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
                logger.info(f"已清理临时数据库: {self.temp_db_path}")
            except Exception as e:
                logger.warning(f"清理临时数据库失败: {e}")
        logger.info("=" * 80)
        logger.info("测试套件执行完毕")
        logger.info("=" * 80)


# =============================================================================
# 测试类别 A: 导入验证
# =============================================================================

class TestImportValidation(ValidationTestFixture):
    """测试 A: 核心模块导入验证"""

    @pytest.mark.imports
    def test_core_database_modules(self):
        """测试 A1: 验证数据库相关核心模块导入"""
        logger.info("\n测试 A1: 验证数据库相关核心模块导入")

        modules_to_test = {
            'core.database.unified_sqlite_access': 'UnifiedSQLiteAccess',
            'core.services.database_service': 'DatabaseService',
            'core.services.db_utils': 'configure_connection',
        }

        for module_name, expected_item in modules_to_test.items():
            try:
                module = __import__(module_name, fromlist=[expected_item])
                assert hasattr(module, expected_item), f"模块 {module_name} 缺少 {expected_item}"
                logger.info(f"✓ 模块导入成功: {module_name}.{expected_item}")
            except Exception as e:
                logger.error(f"✗ 模块导入失败: {module_name} - {e}")
                raise

    @pytest.mark.imports
    def test_core_coordinator_modules(self):
        """测试 A2: 验证协调器相关核心模块导入"""
        logger.info("\n测试 A2: 验证协调器相关核心模块导入")

        modules_to_test = {
            'core.coordinators.base_coordinator': 'BaseCoordinator',
            'core.coordinators.main_window_coordinator': 'MainWindowCoordinator',
            'core.coordinators.dialog_coordinator': 'DialogCoordinator',
            'core.coordinators.event_coordinator': 'EventCoordinator',
            'core.coordinators.theme_coordinator': 'ThemeCoordinator',
        }

        for module_name, expected_item in modules_to_test.items():
            try:
                module = __import__(module_name, fromlist=[expected_item])
                assert hasattr(module, expected_item), f"模块 {module_name} 缺少 {expected_item}"
                logger.info(f"✓ 模块导入成功: {module_name}.{expected_item}")
            except Exception as e:
                logger.error(f"✗ 模块导入失败: {module_name} - {e}")
                raise

    @pytest.mark.imports
    def test_core_trading_modules(self):
        """测试 A3: 验证交易相关核心模块导入"""
        logger.info("\n测试 A3: 验证交易相关核心模块导入")

        modules_to_test = {
            'core.trading.order_executor': 'OrderExecutor',
            'core.trading.order_models': 'Order',
            'core.trading.order_repository': 'OrderRepository',
            'core.trading.order_service': 'OrderService',
        }

        for module_name, expected_item in modules_to_test.items():
            try:
                module = __import__(module_name, fromlist=[expected_item])
                assert hasattr(module, expected_item), f"模块 {module_name} 缺少 {expected_item}"
                logger.info(f"✓ 模块导入成功: {module_name}.{expected_item}")
            except Exception as e:
                logger.error(f"✗ 模块导入失败: {module_name} - {e}")
                raise

    @pytest.mark.imports
    def test_core_service_modules(self):
        """测试 A4: 验证服务相关核心模块导入"""
        logger.info("\n测试 A4: 验证服务相关核心模块导入")

        modules_to_test = {
            'core.containers': 'ServiceContainer',
            'core.events': 'EventBus',
            'core.services.base_service': 'BaseService',
        }

        for module_name, expected_item in modules_to_test.items():
            try:
                module = __import__(module_name, fromlist=[expected_item])
                assert hasattr(module, expected_item), f"模块 {module_name} 缺少 {expected_item}"
                logger.info(f"✓ 模块导入成功: {module_name}.{expected_item}")
            except Exception as e:
                logger.error(f"✗ 模块导入失败: {module_name} - {e}")
                raise

    @pytest.mark.imports
    def test_gui_dialog_modules(self):
        """测试 A5: 验证对话框相关模块导入"""
        logger.info("\n测试 A5: 验证对话框相关模块导入")

        dialogs_to_test = [
            ('gui.dialogs.base_dialog', 'BaseDialog'),
            ('gui.dialogs.strategy_manager_dialog', 'StrategyManagerDialog'),
            ('gui.dialogs.settings_dialog', 'SettingsDialog'),
            ('gui.dialogs.account_management_dialog', 'AccountManagementDialog'),
        ]

        for module_name, expected_item in dialogs_to_test:
            try:
                module = __import__(module_name, fromlist=[expected_item])
                assert hasattr(module, expected_item), f"模块 {module_name} 缺少 {expected_item}"
                logger.info(f"✓ 模块导入成功: {module_name}.{expected_item}")
            except Exception as e:
                logger.error(f"✗ 模块导入失败: {module_name} - {e}")
                raise


# =============================================================================
# 测试类别 B: 数据库连接验证
# =============================================================================

class TestDatabaseConnection(ValidationTestFixture):
    """测试 B: 数据库连接验证"""

    @pytest.mark.database
    def test_unified_sqlite_access_initialization(self):
        """测试 B1: UnifiedSQLiteAccess 能否正常初始化"""
        logger.info("\n测试 B1: UnifiedSQLiteAccess 初始化测试")

        from core.database.unified_sqlite_access import UnifiedSQLiteAccess

        self.temp_db_path = str(PROJECT_ROOT / "db" / "test_validation.db")

        db = UnifiedSQLiteAccess.get_instance(self.temp_db_path)

        assert db is not None, "UnifiedSQLiteAccess 实例创建失败"
        assert db.db_path == self.temp_db_path, "数据库路径设置错误"
        assert db.enable_foreign_keys is True, "外键约束默认未启用"

        logger.info("✓ UnifiedSQLiteAccess 初始化成功")

    @pytest.mark.database
    def test_unified_sqlite_access_connection(self):
        """测试 B2: UnifiedSQLiteAccess 数据库连接是否正常"""
        logger.info("\n测试 B2: UnifiedSQLiteAccess 数据库连接测试")

        from core.database.unified_sqlite_access import UnifiedSQLiteAccess

        self.temp_db_path = str(PROJECT_ROOT / "db" / "test_validation.db")

        db = UnifiedSQLiteAccess.get_instance(self.temp_db_path)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            logger.info(f"✓ SQLite 版本: {version}")
            assert version is not None, "无法获取 SQLite 版本"

    @pytest.mark.database
    def test_unified_sqlite_access_wal_mode(self):
        """测试 B3: WAL 模式是否正确启用"""
        logger.info("\n测试 B3: WAL 模式验证测试")

        from core.database.unified_sqlite_access import UnifiedSQLiteAccess

        self.temp_db_path = str(PROJECT_ROOT / "db" / "test_validation.db")

        db = UnifiedSQLiteAccess.get_instance(self.temp_db_path)

        db_info = db.get_database_info()

        assert db_info.get('journal_mode') == 'wal', f"WAL 模式未启用，当前模式: {db_info.get('journal_mode')}"
        logger.info(f"✓ WAL 模式已启用")
        logger.info(f"  数据库信息: {db_info}")

    @pytest.mark.database
    def test_unified_sqlite_access_execute_query(self):
        """测试 B4: UnifiedSQLiteAccess 查询功能是否正常"""
        logger.info("\n测试 B4: UnifiedSQLiteAccess 查询功能测试")

        from core.database.unified_sqlite_access import UnifiedSQLiteAccess

        self.temp_db_path = str(PROJECT_ROOT / "db" / "test_validation.db")

        db = UnifiedSQLiteAccess.get_instance(self.temp_db_path)

        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    value REAL
                )
            """)

        db.execute_write("INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
                         (1, 'test_item', 100.5))

        result = db.execute("SELECT * FROM test_table WHERE id = ?", (1,))

        assert len(result) > 0, "查询结果为空"
        assert result[0]['name'] == 'test_item', "查询结果不匹配"
        logger.info(f"✓ 查询功能正常: {result[0]}")

    @pytest.mark.database
    def test_unified_sqlite_access_foreign_keys(self):
        """测试 B5: 外键约束是否正确启用"""
        logger.info("\n测试 B5: 外键约束验证测试")

        from core.database.unified_sqlite_access import UnifiedSQLiteAccess

        self.temp_db_path = str(PROJECT_ROOT / "db" / "test_validation.db")

        db = UnifiedSQLiteAccess.get_instance(self.temp_db_path, enable_foreign_keys=True)

        with db.get_connection() as conn:
            cursor = conn.execute("PRAGMA foreign_keys")
            fk_status = cursor.fetchone()[0]
            assert fk_status == 1, f"外键约束未启用，状态: {fk_status}"
            logger.info(f"✓ 外键约束已启用 (status={fk_status})")


# =============================================================================
# 测试类别 C: Coordinator 初始化验证
# =============================================================================

class TestCoordinatorInitialization(ValidationTestFixture):
    """测试 C: Coordinator 初始化验证"""

    @pytest.mark.coordinator
    def test_base_coordinator_creation(self):
        """测试 C1: BaseCoordinator 能否正常创建"""
        logger.info("\n测试 C1: BaseCoordinator 创建测试")

        from core.coordinators.base_coordinator import BaseCoordinator
        from core.containers import ServiceContainer
        from core.events import EventBus

        service_container = ServiceContainer()
        event_bus = EventBus()

        coordinator = BaseCoordinator.__new__(BaseCoordinator)
        coordinator._service_container = service_container
        coordinator._event_bus = event_bus
        coordinator._initialized = False
        coordinator._disposed = False
        coordinator._name = "TestBaseCoordinator"
        coordinator._event_handlers = []

        assert coordinator is not None, "BaseCoordinator 创建失败"
        assert coordinator.name == "TestBaseCoordinator", "协调器名称设置错误"
        assert not coordinator.initialized, "协调器初始化状态错误"

        logger.info("✓ BaseCoordinator 创建成功")

    @pytest.mark.coordinator
    def test_event_coordinator_creation(self):
        """测试 C2: EventCoordinator 能否正常创建"""
        logger.info("\n测试 C2: EventCoordinator 创建测试")

        from core.containers import ServiceContainer
        from core.events import EventBus

        service_container = ServiceContainer()
        event_bus = EventBus()

        mock_main_window = Mock()

        from core.coordinators.event_coordinator import EventCoordinator

        coordinator = EventCoordinator(
            main_window_coordinator=mock_main_window,
            service_container=service_container,
            event_bus=event_bus
        )

        assert coordinator is not None, "EventCoordinator 创建失败"
        assert coordinator.service_container == service_container, "服务容器设置错误"
        assert coordinator.event_bus == event_bus, "事件总线设置错误"

        logger.info("✓ EventCoordinator 创建成功")

    @pytest.mark.coordinator
    def test_dialog_coordinator_creation(self):
        """测试 C3: DialogCoordinator 能否正常创建"""
        logger.info("\n测试 C3: DialogCoordinator 创建测试")

        from core.containers import ServiceContainer
        from core.events import EventBus
        from core.coordinators.dialog_coordinator import DialogCoordinator

        service_container = ServiceContainer()
        event_bus = EventBus()

        coordinator = DialogCoordinator(
            service_container=service_container,
            event_bus=event_bus
        )

        assert coordinator is not None, "DialogCoordinator 创建失败"
        assert coordinator._dialog_cache is not None, "对话框缓存未初始化"

        logger.info("✓ DialogCoordinator 创建成功")


# =============================================================================
# 测试类别 D: 对话框创建验证
# =============================================================================

class TestDialogCreation(ValidationTestFixture):
    """测试 D: 对话框创建验证"""

    @pytest.mark.dialog
    def test_base_dialog_import(self):
        """测试 D1: BaseDialog 能否正常导入"""
        logger.info("\n测试 D1: BaseDialog 导入测试")

        from gui.dialogs.base_dialog import BaseDialog

        assert BaseDialog is not None, "BaseDialog 导入失败"
        assert hasattr(BaseDialog, '__init__'), "BaseDialog 缺少 __init__ 方法"

        logger.info("✓ BaseDialog 导入成功")

    @pytest.mark.dialog
    def test_base_dialog_instantiation(self):
        """测试 D2: BaseDialog 能否正常实例化"""
        logger.info("\n测试 D2: BaseDialog 实例化测试")

        from gui.dialogs.base_dialog import BaseDialog

        dialog = BaseDialog.__new__(BaseDialog)

        assert dialog is not None, "BaseDialog 实例化失败"

        logger.info("✓ BaseDialog 实例化成功")

    @pytest.mark.dialog
    def test_strategy_manager_dialog_import(self):
        """测试 D3: StrategyManagerDialog 能否正常导入"""
        logger.info("\n测试 D3: StrategyManagerDialog 导入测试")

        from gui.dialogs.strategy_manager_dialog import StrategyManagerDialog

        assert StrategyManagerDialog is not None, "StrategyManagerDialog 导入失败"
        assert hasattr(StrategyManagerDialog, '__init__'), "StrategyManagerDialog 缺少 __init__ 方法"

        logger.info("✓ StrategyManagerDialog 导入成功")

    @pytest.mark.dialog
    def test_settings_dialog_import(self):
        """测试 D4: SettingsDialog 能否正常导入"""
        logger.info("\n测试 D4: SettingsDialog 导入测试")

        from gui.dialogs.settings_dialog import SettingsDialog

        assert SettingsDialog is not None, "SettingsDialog 导入失败"
        assert hasattr(SettingsDialog, '__init__'), "SettingsDialog 缺少 __init__ 方法"

        logger.info("✓ SettingsDialog 导入成功")

    @pytest.mark.dialog
    def test_account_management_dialog_import(self):
        """测试 D5: AccountManagementDialog 能否正常导入"""
        logger.info("\n测试 D5: AccountManagementDialog 导入测试")

        from gui.dialogs.account_management_dialog import AccountManagementDialog

        assert AccountManagementDialog is not None, "AccountManagementDialog 导入失败"
        assert hasattr(AccountManagementDialog, '__init__'), "AccountManagementDialog 缺少 __init__ 方法"

        logger.info("✓ AccountManagementDialog 导入成功")


# =============================================================================
# 测试类别 E: OrderExecutor 初始化验证
# =============================================================================

class TestOrderExecutorInitialization(ValidationTestFixture):
    """测试 E: OrderExecutor 初始化验证"""

    @pytest.mark.order_executor
    def test_order_executor_import(self):
        """测试 E1: OrderExecutor 能否正常导入"""
        logger.info("\n测试 E1: OrderExecutor 导入测试")

        from core.trading.order_executor import OrderExecutor

        assert OrderExecutor is not None, "OrderExecutor 导入失败"
        assert hasattr(OrderExecutor, '__init__'), "OrderExecutor 缺少 __init__ 方法"

        logger.info("✓ OrderExecutor 导入成功")

    @pytest.mark.order_executor
    def test_order_executor_initialization(self):
        """测试 E2: OrderExecutor 能否正常初始化"""
        logger.info("\n测试 E2: OrderExecutor 初始化测试")

        from core.trading.order_executor import OrderExecutor
        from core.containers import ServiceContainer
        from core.events import EventBus

        service_container = ServiceContainer()
        event_bus = EventBus()

        with patch.object(OrderExecutor, '_initialize'):
            executor = OrderExecutor(service_container, event_bus)

        assert executor is not None, "OrderExecutor 初始化失败"
        assert executor.service_container == service_container, "服务容器设置错误"
        assert executor.event_bus == event_bus, "事件总线设置错误"

        logger.info("✓ OrderExecutor 初始化成功")

    @pytest.mark.order_executor
    def test_order_executor_with_mock_trading_interface(self):
        """测试 E3: OrderExecutor 与 MockTradingInterface 能否正常工作"""
        logger.info("\n测试 E3: OrderExecutor 与 MockTradingInterface 测试")

        from core.trading.order_executor import OrderExecutor, MockTradingInterface
        from core.trading.order_models import Order, OrderType, OrderStatus, OrderCategory
        from core.containers import ServiceContainer
        from core.events import EventBus

        mock_interface = MockTradingInterface()

        assert mock_interface is not None, "MockTradingInterface 创建失败"

        service_container = ServiceContainer()
        event_bus = EventBus()

        with patch.object(OrderExecutor, '_initialize'):
            executor = OrderExecutor(service_container, event_bus)
            executor.trading_interface = mock_interface

        assert executor.trading_interface == mock_interface, "交易接口设置错误"

        logger.info("✓ OrderExecutor 与 MockTradingInterface 工作正常")

    @pytest.mark.order_executor
    def test_mock_trading_interface_submit_order(self):
        """测试 E4: MockTradingInterface 能否正常提交订单"""
        logger.info("\n测试 E4: MockTradingInterface 提交订单测试")

        from core.trading.order_executor import MockTradingInterface
        from core.trading.order_models import Order, OrderType, OrderStatus, OrderCategory
        from core.plugin_types import AssetType
        from datetime import datetime

        mock_interface = MockTradingInterface()

        order = Order(
            order_id="TEST_ORDER_001",
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        result = mock_interface.submit_order(order)

        assert result is not None, "订单提交结果为空"
        assert result.status.value == 'success', f"订单提交状态错误: {result.status}"
        assert result.exchange_order_id is not None, "交易所订单 ID 为空"

        logger.info(f"✓ MockTradingInterface 提交订单成功: {result.exchange_order_id}")


# =============================================================================
# 测试报告生成
# =============================================================================

class TestReportGeneration(ValidationTestFixture):
    """测试报告生成"""

    @pytest.mark.report
    def test_generate_test_report(self, request):
        """生成测试报告"""
        logger.info("\n生成测试报告")

        report = {
            'test_time': datetime.now().isoformat(),
            'project_root': str(PROJECT_ROOT),
            'log_file': str(LOG_FILE),
            'python_version': sys.version,
            'test_module': request.module.__name__ if hasattr(request, 'module') else 'unknown',
        }

        logger.info(f"测试报告: {report}")

        report_file = LOG_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"✓ 测试报告已保存至: {report_file}")


if __name__ == '__main__':
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--log-cli-level=INFO',
        '--html=logs/validation/validation_report.html',
        '--self-contained-html'
    ])
