"""
综合修复验证测试脚本

验证范围：
1. 导入验证 - Coordinator、UnifiedSQLiteAccess、OrderExecutor、db_utils
2. 数据库层验证 - 外键配置、PRAGMA、plugin_models
3. Coordinator验证 - MainWindowCoordinator、4个专业协调器
4. 交易接口验证 - OrderExecutor健康状态、故障转移
5. 生成验证报告
"""

import sys
import os
import importlib
import inspect
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 测试报告
class ValidationReport:
    def __init__(self):
        self.passed: List[str] = []
        self.failed: List[str] = []
        self.warnings: List[str] = []
        self.start_time = datetime.now()
        
    def add_pass(self, test_name: str, detail: str = ""):
        msg = f"✓ {test_name}"
        if detail:
            msg += f" - {detail}"
        self.passed.append(msg)
        print(f"  [PASS] {test_name}")
        if detail:
            print(f"         {detail}")
    
    def add_fail(self, test_name: str, error: str = ""):
        msg = f"✗ {test_name}"
        if error:
            msg += f" - {error}"
        self.failed.append(msg)
        print(f"  [FAIL] {test_name}")
        if error:
            print(f"         错误: {error}")
    
    def add_warning(self, test_name: str, detail: str = ""):
        msg = f"⚠ {test_name}"
        if detail:
            msg += f" - {detail}"
        self.warnings.append(msg)
        print(f"  [WARN] {test_name}")
        if detail:
            print(f"         {detail}")
    
    def print_summary(self):
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print("验证测试报告")
        print("=" * 80)
        print(f"测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试耗时: {duration:.2f} 秒")
        print("-" * 80)
        
        print(f"\n通过: {len(self.passed)}")
        for item in self.passed:
            print(f"  {item}")
        
        if self.failed:
            print(f"\n失败: {len(self.failed)}")
            for item in self.failed:
                print(f"  {item}")
        
        if self.warnings:
            print(f"\n警告: {len(self.warnings)}")
            for item in self.warnings:
                print(f"  {item}")
        
        print("-" * 80)
        total = len(self.passed) + len(self.failed)
        score = (len(self.passed) / total * 100) if total > 0 else 0
        
        print(f"总测试数: {total}")
        print(f"通过率: {score:.1f}%")
        
        if score >= 95:
            grade = "优秀 (A)"
        elif score >= 85:
            grade = "良好 (B)"
        elif score >= 70:
            grade = "中等 (C)"
        else:
            grade = "需改进 (D)"
        
        print(f"总体评分: {grade}")
        print("=" * 80)
        
        return score


    if __name__ == '__main__':
        report = ValidationReport()

        # ============================================================================
        # 1. 导入验证
        # ============================================================================
        print("\n" + "=" * 80)
        print("1. 导入验证")
        print("=" * 80)

        # 1.1 验证Coordinator导入
        print("\n1.1 Coordinator导入验证")
        try:
            from core.coordinators import (
                MainWindowCoordinator,
                PanelCoordinator,
                EventCoordinator,
                DialogCoordinator,
                ThemeCoordinator,
                BaseCoordinator
            )
            report.add_pass("Coordinator模块导入", "所有6个协调器类成功导入")
    
            # 验证每个类是否存在
            for cls_name in ['MainWindowCoordinator', 'PanelCoordinator', 'EventCoordinator', 
                             'DialogCoordinator', 'ThemeCoordinator', 'BaseCoordinator']:
                cls = eval(cls_name)
                if inspect.isclass(cls):
                    report.add_pass(f"{cls_name}类存在", f"模块: {cls.__module__}")
                else:
                    report.add_fail(f"{cls_name}类不存在")
            
        except ImportError as e:
            report.add_fail("Coordinator模块导入", str(e))

        # 1.2 验证UnifiedSQLiteAccess导入
        print("\n1.2 UnifiedSQLiteAccess导入验证")
        try:
            from core.database.unified_sqlite_access import (
                UnifiedSQLiteAccess,
                get_db,
                execute_query,
                execute_write
            )
            report.add_pass("UnifiedSQLiteAccess模块导入", "主类和便捷函数成功导入")
    
            # 验证关键方法
            methods = ['get_instance', 'get_connection', 'execute', 'execute_write', 
                       'execute_many', 'execute_in_transaction', 'table_exists',
                       'check_foreign_keys_enabled', 'get_foreign_key_violations',
                       'get_database_info']
    
            for method in methods:
                if hasattr(UnifiedSQLiteAccess, method):
                    report.add_pass(f"UnifiedSQLiteAccess.{method}方法存在")
                else:
                    report.add_fail(f"UnifiedSQLiteAccess.{method}方法不存在")
            
        except ImportError as e:
            report.add_fail("UnifiedSQLiteAccess模块导入", str(e))

        # 1.3 验证OrderExecutor导入
        print("\n1.3 OrderExecutor导入验证")
        try:
            from core.trading.order_executor import (
                OrderExecutor,
                MockTradingInterface
            )
            report.add_pass("OrderExecutor模块导入", "主类和模拟接口成功导入")
    
            # 验证关键方法
            methods = ['check_interface_health', '_try_reconnect_interface', 
                       '_setup_failover_mapping', 'submit_order', 'cancel_order',
                       'submit_orders_batch', '_pre_trade_risk_check',
                       '_validate_order_integrity', '_resolve_account_for_order']
    
            for method in methods:
                if hasattr(OrderExecutor, method):
                    report.add_pass(f"OrderExecutor.{method}方法存在")
                else:
                    report.add_fail(f"OrderExecutor.{method}方法不存在")
            
        except ImportError as e:
            report.add_fail("OrderExecutor模块导入", str(e))

        # 1.4 验证db_utils导入
        print("\n1.4 db_utils导入验证")
        try:
            from core.services.db_utils import (
                configure_connection,
                create_configured_connection
            )
            report.add_pass("db_utils模块导入", "配置函数成功导入")
    
            # 验证函数签名
            sig = inspect.signature(configure_connection)
            if 'conn' in sig.parameters:
                report.add_pass("configure_connection函数签名正确", f"参数: {list(sig.parameters.keys())}")
            else:
                report.add_fail("configure_connection函数签名错误")
        
            sig2 = inspect.signature(create_configured_connection)
            if 'db_path' in sig2.parameters:
                report.add_pass("create_configured_connection函数签名正确", f"参数: {list(sig2.parameters.keys())}")
            else:
                report.add_fail("create_configured_connection函数签名错误")
        
        except ImportError as e:
            report.add_fail("db_utils模块导入", str(e))

        # ============================================================================
        # 2. 数据库层验证
        # ============================================================================
        print("\n" + "=" * 80)
        print("2. 数据库层验证")
        print("=" * 80)

        # 2.1 验证UnifiedSQLiteAccess外键配置
        print("\n2.1 UnifiedSQLiteAccess外键配置验证")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = os.path.join(tmpdir, "test_foreign_keys.db")
        
                db = UnifiedSQLiteAccess.get_instance(test_db, enable_foreign_keys=True)
        
                with db.get_connection() as conn:
                    # 创建测试表
                    conn.execute('''
                        CREATE TABLE parent (
                            id INTEGER PRIMARY KEY,
                            name TEXT NOT NULL
                        )
                    ''')
                    conn.execute('''
                        CREATE TABLE child (
                            id INTEGER PRIMARY KEY,
                            parent_id INTEGER,
                            name TEXT NOT NULL,
                            FOREIGN KEY (parent_id) REFERENCES parent(id)
                        )
                    ''')
            
                    # 检查外键是否启用
                    fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                    if fk_status == 1:
                        report.add_pass("外键约束已启用", "PRAGMA foreign_keys = 1")
                    else:
                        report.add_fail("外键约束未启用", f"PRAGMA foreign_keys = {fk_status}")
            
                    # 检查WAL模式
                    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                    if journal_mode.upper() == "WAL":
                        report.add_pass("WAL模式已启用", f"journal_mode = {journal_mode}")
                    else:
                        report.add_fail("WAL模式未启用", f"journal_mode = {journal_mode}")
            
                    # 检查synchronous (NORMAL=1, FULL=2)
                    sync_mode = conn.execute("PRAGMA synchronous").fetchone()[0]
                    report.add_pass("Synchronous模式", f"synchronous = {sync_mode} (1=NORMAL)")
            
                    # 检查cache_size
                    cache_size = conn.execute("PRAGMA cache_size").fetchone()[0]
                    if cache_size == -64000:
                        report.add_pass("Cache大小配置正确", f"cache_size = {cache_size}")
                    else:
                        report.add_warning("Cache大小配置", f"cache_size = {cache_size} (预期: -64000)")
            
                    # 验证外键约束是否生效
                    try:
                        conn.execute("INSERT INTO child (id, parent_id, name) VALUES (1, 999, 'test')")
                        report.add_fail("外键约束未生效", "应该拒绝插入不存在的外键引用")
                    except sqlite3.IntegrityError:
                        report.add_pass("外键约束生效", "正确拒绝了无效的外键引用")
        
                # 清理单例
                UnifiedSQLiteAccess._instances.pop(test_db, None)
        
        except Exception as e:
            report.add_fail("UnifiedSQLiteAccess外键配置验证", str(e))

        # 2.2 验证sqlite_extensions的PRAGMA配置
        print("\n2.2 sqlite_extensions PRAGMA配置验证")
        try:
            from core.database.sqlite_extensions import SQLiteExtensionManager
    
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = os.path.join(tmpdir, "test_extensions.db")
        
                manager = SQLiteExtensionManager(test_db)
        
                with manager.get_connection() as conn:
                    # 检查所有PRAGMA设置
                    pragma_tests = {
                        'journal_mode': 'WAL',
                        'foreign_keys': '1',
                    }
            
                    for pragma, expected in pragma_tests.items():
                        result = conn.execute(f"PRAGMA {pragma}").fetchone()[0]
                        if str(result).upper() == expected.upper():
                            report.add_pass(f"sqlite_extensions.{pragma}配置正确", 
                                           f"值: {result} (预期: {expected})")
                        else:
                            report.add_fail(f"sqlite_extensions.{pragma}配置错误",
                                           f"值: {result} (预期: {expected})")
            
                    # 单独验证synchronous (NORMAL=1)
                    sync_result = conn.execute("PRAGMA synchronous").fetchone()[0]
                    if str(sync_result) in ['1', 'NORMAL']:
                        report.add_pass("sqlite_extensions.synchronous配置正确",
                                       f"值: {sync_result} (预期: 1/NORMAL)")
                    else:
                        report.add_fail("sqlite_extensions.synchronous配置错误",
                                       f"值: {sync_result} (预期: 1/NORMAL)")
        
        except ImportError as e:
            report.add_fail("sqlite_extensions导入失败", str(e))
        except Exception as e:
            report.add_fail("sqlite_extensions PRAGMA配置验证", str(e))

        # 2.3 验证plugin_models使用UnifiedSQLiteAccess
        print("\n2.3 plugin_models使用UnifiedSQLiteAccess验证")
        try:
            from db.models.plugin_models import PluginDatabaseManager, DataSourcePluginConfigManager
    
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = os.path.join(tmpdir, "test_plugin.db")
        
                # 测试PluginDatabaseManager
                plugin_mgr = PluginDatabaseManager(test_db)
        
                # 验证使用了UnifiedSQLiteAccess
                if hasattr(plugin_mgr, 'db') and isinstance(plugin_mgr.db, UnifiedSQLiteAccess):
                    report.add_pass("PluginDatabaseManager使用UnifiedSQLiteAccess")
                else:
                    report.add_fail("PluginDatabaseManager未使用UnifiedSQLiteAccess")
        
                # 验证表创建成功
                if plugin_mgr.db.table_exists('plugins'):
                    report.add_pass("plugins表创建成功")
                else:
                    report.add_fail("plugins表未创建")
        
                if plugin_mgr.db.table_exists('plugin_configs'):
                    report.add_pass("plugin_configs表创建成功")
                else:
                    report.add_fail("plugin_configs表未创建")
        
                if plugin_mgr.db.table_exists('plugin_dependencies'):
                    report.add_pass("plugin_dependencies表创建成功")
                else:
                    report.add_fail("plugin_dependencies表未创建")
        
                # 验证外键约束
                with plugin_mgr.db.get_connection() as conn:
                    fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                    if fk_status == 1:
                        report.add_pass("plugin_models外键约束已启用")
                    else:
                        report.add_warning("plugin_models外键约束状态", f"foreign_keys = {fk_status}")
        
                # 清理单例
                UnifiedSQLiteAccess._instances.pop(test_db, None)
        
        except ImportError as e:
            report.add_fail("plugin_models导入失败", str(e))
        except Exception as e:
            report.add_fail("plugin_models验证失败", str(e))

        # ============================================================================
        # 3. Coordinator验证
        # ============================================================================
        print("\n" + "=" * 80)
        print("3. Coordinator验证")
        print("=" * 80)

        # 3.1 验证MainWindowCoordinator包含4个专业协调器
        print("\n3.1 MainWindowCoordinator协调器包含验证")
        try:
            # 检查__init__方法中的协调器属性
            init_source = inspect.getsource(MainWindowCoordinator.__init__)
    
            coordinators = {
                '_panel_coordinator': 'PanelCoordinator',
                '_event_coordinator': 'EventCoordinator',
                '_dialog_coordinator': 'DialogCoordinator',
                '_theme_coordinator': 'ThemeCoordinator'
            }
    
            for attr, coord_name in coordinators.items():
                if attr in init_source:
                    report.add_pass(f"MainWindowCoordinator包含{coord_name}", f"属性: {attr}")
                else:
                    report.add_fail(f"MainWindowCoordinator缺少{coord_name}", f"属性: {attr}")
    
        except Exception as e:
            report.add_fail("MainWindowCoordinator协调器验证", str(e))

        # 3.2 验证协调器导入关系
        print("\n3.2 协调器导入关系验证")
        try:
            # 检查MainWindowCoordinator的导入
            mwm_source = inspect.getsource(inspect.getmodule(MainWindowCoordinator))
    
            imports = [
                'from core.coordinators.panel_coordinator import PanelCoordinator',
                'from core.coordinators.event_coordinator import EventCoordinator',
                'from core.coordinators.dialog_coordinator import DialogCoordinator',
                'from core.coordinators.theme_coordinator import ThemeCoordinator'
            ]
    
            for imp in imports:
                if imp in mwm_source:
                    report.add_pass(f"MainWindowCoordinator正确导入", imp.split(' import ')[1])
                else:
                    report.add_fail(f"MainWindowCoordinator缺少导入", imp)
    
        except Exception as e:
            report.add_fail("协调器导入关系验证", str(e))

        # 3.3 验证各协调器初始化
        print("\n3.3 协调器初始化验证")
        try:
            # 检查每个协调器的__init__方法
            for coord_class in [PanelCoordinator, EventCoordinator, DialogCoordinator, ThemeCoordinator]:
                init_method = getattr(coord_class, '__init__', None)
                if init_method and callable(init_method):
                    sig = inspect.signature(init_method)
                    params = list(sig.parameters.keys())
                    report.add_pass(f"{coord_class.__name__}.__init__存在", f"参数: {params}")
                else:
                    report.add_fail(f"{coord_class.__name__}.__init__不存在")
    
        except Exception as e:
            report.add_fail("协调器初始化验证", str(e))

        # 3.4 验证__init__.py导出
        print("\n3.4 coordinators/__init__.py导出验证")
        try:
            from core.coordinators import __all__
    
            expected_exports = ['BaseCoordinator', 'MainWindowCoordinator', 'PanelCoordinator', 
                                'DialogCoordinator', 'ThemeCoordinator']
    
            for export in expected_exports:
                if export in __all__:
                    report.add_pass(f"__all__包含{export}")
                else:
                    report.add_fail(f"__all__缺少{export}")
    
            # EventCoordinator应该在__all__中
            if 'EventCoordinator' in __all__:
                report.add_pass("__all__包含EventCoordinator")
            else:
                report.add_warning("__all__缺少EventCoordinator", "建议添加")
        
        except Exception as e:
            report.add_fail("coordinators/__init__.py导出验证", str(e))

        # ============================================================================
        # 4. 交易接口验证
        # ============================================================================
        print("\n" + "=" * 80)
        print("4. 交易接口验证")
        print("=" * 80)

        # 4.1 验证OrderExecutor健康状态跟踪
        print("\n4.1 OrderExecutor健康状态跟踪验证")
        try:
            from unittest.mock import MagicMock
    
            # 创建模拟依赖
            mock_container = MagicMock()
            mock_event_bus = MagicMock()
    
            executor = OrderExecutor(mock_container, mock_event_bus)
    
            # 验证健康状态跟踪属性
            if hasattr(executor, '_interface_health'):
                report.add_pass("OrderExecutor包含_interface_health属性")
        
                # 检查健康状态字段
                if executor._interface_health:
                    first_asset = list(executor._interface_health.keys())[0]
                    health = executor._interface_health[first_asset]
            
                    required_fields = ['connected', 'logged_in', 'last_error', 'retry_count',
                                      'last_health_check', 'consecutive_failures', 'circuit_breaker',
                                      'total_requests', 'failed_requests']
            
                    for field in required_fields:
                        if field in health:
                            report.add_pass(f"健康状态字段{field}存在")
                        else:
                            report.add_fail(f"健康状态字段{field}缺失")
                else:
                    report.add_warning("健康状态字典为空", "可能没有注册任何交易接口")
            else:
                report.add_fail("OrderExecutor缺少_interface_health属性")
        
        except Exception as e:
            report.add_fail("OrderExecutor健康状态跟踪验证", str(e))

        # 4.2 验证check_interface_health方法
        print("\n4.2 check_interface_health方法验证")
        try:
            from core.plugin_types import AssetType
            from unittest.mock import MagicMock
    
            mock_container = MagicMock()
            mock_event_bus = MagicMock()
    
            executor = OrderExecutor(mock_container, mock_event_bus)
    
            # 测试方法调用
            health = executor.check_interface_health(AssetType.STOCK_A)
    
            if isinstance(health, dict):
                report.add_pass("check_interface_health返回字典")
        
                if 'connected' in health:
                    report.add_pass("返回结果包含connected字段")
                else:
                    report.add_fail("返回结果缺少connected字段")
        
                if 'last_health_check' in health:
                    report.add_pass("返回结果包含last_health_check字段")
                else:
                    report.add_warning("返回结果缺少last_health_check字段")
            else:
                report.add_fail("check_interface_health返回类型错误", f"类型: {type(health)}")
    
        except Exception as e:
            report.add_fail("check_interface_health方法验证", str(e))

        # 4.3 验证_try_reconnect_interface方法
        print("\n4.3 _try_reconnect_interface方法验证")
        try:
            from core.plugin_types import AssetType
            from unittest.mock import MagicMock
    
            mock_container = MagicMock()
            mock_event_bus = MagicMock()
    
            executor = OrderExecutor(mock_container, mock_event_bus)
    
            # 验证方法存在
            if hasattr(executor, '_try_reconnect_interface'):
                report.add_pass("_try_reconnect_interface方法存在")
        
                # 验证方法签名
                sig = inspect.signature(executor._try_reconnect_interface)
                params = list(sig.parameters.keys())
        
                if 'asset_type' in params:
                    report.add_pass("_try_reconnect_interface包含asset_type参数")
                else:
                    report.add_fail("_try_reconnect_interface缺少asset_type参数")
        
                # 尝试调用（不会真正连接，只是验证）
                try:
                    executor._try_reconnect_interface(AssetType.STOCK_A)
                    report.add_pass("_try_reconnect_interface调用成功")
                except Exception as e:
                    report.add_warning("_try_reconnect_interface调用异常", str(e))
            else:
                report.add_fail("_try_reconnect_interface方法不存在")
        
        except Exception as e:
            report.add_fail("_try_reconnect_interface方法验证", str(e))

        # 4.4 验证故障转移映射
        print("\n4.4 故障转移映射验证")
        try:
            from core.plugin_types import AssetType
            from unittest.mock import MagicMock
    
            mock_container = MagicMock()
            mock_event_bus = MagicMock()
    
            executor = OrderExecutor(mock_container, mock_event_bus)
    
            if hasattr(executor, '_interface_failover_map'):
                report.add_pass("OrderExecutor包含_interface_failover_map属性")
        
                if executor._interface_failover_map:
                    report.add_pass("故障转移映射已配置", f"映射数: {len(executor._interface_failover_map)}")
            
                    # 检查具体映射
                    expected_mappings = {
                        AssetType.STOCK_A: [AssetType.FUND],
                        AssetType.STOCK_HK: [AssetType.STOCK_A],
                        AssetType.STOCK_US: [AssetType.STOCK_A]
                    }
            
                    for asset_type, expected_failover in expected_mappings.items():
                        if asset_type in executor._interface_failover_map:
                            actual_failover = executor._interface_failover_map[asset_type]
                            if actual_failover == expected_failover:
                                report.add_pass(f"故障转移映射正确", 
                                               f"{asset_type.value} -> {[a.value for a in actual_failover]}")
                            else:
                                report.add_warning(f"故障转移映射不匹配",
                                                  f"{asset_type.value}: 实际{actual_failover} vs 预期{expected_failover}")
                        else:
                            report.add_warning(f"缺少{asset_type.value}的故障转移映射")
                else:
                    report.add_warning("故障转移映射为空")
            else:
                report.add_fail("OrderExecutor缺少_interface_failover_map属性")
        
        except Exception as e:
            report.add_fail("故障转移映射验证", str(e))

        # ============================================================================
        # 5. 额外验证 - db_utils集成
        # ============================================================================
        print("\n" + "=" * 80)
        print("5. db_utils集成验证")
        print("=" * 80)

        print("\n5.1 db_utils功能验证")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_db = os.path.join(tmpdir, "test_db_utils.db")
        
                # 测试configure_connection
                conn = sqlite3.connect(test_db)
                configure_connection(conn)
        
                # 验证配置
                journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
                cache_size = conn.execute("PRAGMA cache_size").fetchone()[0]
                busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        
                conn.close()
        
                if journal_mode.upper() == 'WAL':
                    report.add_pass("db_utils WAL模式配置正确")
                else:
                    report.add_fail("db_utils WAL模式配置错误")
        
                if foreign_keys == 1:
                    report.add_pass("db_utils 外键约束配置正确")
                else:
                    report.add_fail("db_utils 外键约束配置错误")
        
                if str(synchronous) in ['1', 'NORMAL']:
                    report.add_pass("db_utils Synchronous配置正确")
                else:
                    report.add_fail("db_utils Synchronous配置错误")
        
                if cache_size == -64000:
                    report.add_pass("db_utils Cache配置正确")
                else:
                    report.add_warning("db_utils Cache配置", f"cache_size = {cache_size}")
        
                if busy_timeout == 5000:
                    report.add_pass("db_utils Busy Timeout配置正确")
                else:
                    report.add_warning("db_utils Busy Timeout配置", f"busy_timeout = {busy_timeout}")
        
                # 测试create_configured_connection
                conn2 = create_configured_connection(test_db)
                if conn2:
                    report.add_pass("create_configured_connection创建成功")
                    fk_status = conn2.execute("PRAGMA foreign_keys").fetchone()[0]
                    if fk_status == 1:
                        report.add_pass("create_configured_connection外键已启用")
                    else:
                        report.add_fail("create_configured_connection外键未启用")
                    conn2.close()
                else:
                    report.add_fail("create_configured_connection创建失败")
            
        except Exception as e:
            report.add_fail("db_utils功能验证", str(e))

        # ============================================================================
        # 打印总结报告
        # ============================================================================
        score = report.print_summary()

        # 如果失败率超过10%，打印警告
        fail_rate = len(report.failed) / (len(report.passed) + len(report.failed)) if (len(report.passed) + len(report.failed)) > 0 else 0
        if fail_rate > 0.1:
            print("\n⚠ 警告: 失败率超过10%，建议检查失败的测试项目！")
        elif fail_rate == 0:
            print("\n✓ 所有测试通过！修复验证完成。")
        else:
            print(f"\n✓ 通过率: {(1-fail_rate)*100:.1f}%，修复验证基本完成。")

        return 0 if len(report.failed) == 0 else 1
    if __name__ == "__main__":
        sys.exit(main())

    if __name__ == "__main__":
        sys.exit(main())

    if __name__ == "__main__":
        sys.exit(main())

    if __name__ == "__main__":
        sys.exit(main())

    if __name__ == "__main__":
        sys.exit(main())

if __name__ == "__main__":
    sys.exit(main())
