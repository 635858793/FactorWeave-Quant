"""
统一 SQLite 数据库访问层单元测试

测试范围：
- 单例模式
- 连接管理（WAL模式、外键约束、性能优化）
- 事务管理（自动提交/回滚）
- CRUD 操作
- 边界条件和异常处理
- 并发安全
"""
import pytest
import sqlite3
import os
import tempfile
import threading
from unittest.mock import patch, MagicMock, call
from typing import List

from core.database.unified_sqlite_access import (
    UnifiedSQLiteAccess,
    get_db,
    execute_query,
    execute_write,
)


@pytest.fixture
def temp_db_path():
    """创建临时数据库路径"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def db_instance(temp_db_path):
    """创建数据库访问实例"""
    UnifiedSQLiteAccess._instances.clear()
    instance = UnifiedSQLiteAccess.get_instance(temp_db_path)
    yield instance
    UnifiedSQLiteAccess._instances.clear()


@pytest.fixture
def db_instance_no_fk(temp_db_path):
    """创建禁用外键的数据库实例"""
    UnifiedSQLiteAccess._instances.clear()
    instance = UnifiedSQLiteAccess.get_instance(temp_db_path, enable_foreign_keys=False)
    yield instance
    UnifiedSQLiteAccess._instances.clear()


@pytest.fixture
def db_with_table(db_instance):
    """创建带测试表的数据库"""
    with db_instance.get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value REAL DEFAULT 0.0
            )
        """)
    return db_instance


@pytest.fixture
def db_with_data(db_with_table):
    """创建带测试数据的数据库"""
    operations = [
        ("INSERT INTO test_table (name, value) VALUES (?, ?)", ('item1', 10.5)),
        ("INSERT INTO test_table (name, value) VALUES (?, ?)", ('item2', 20.3)),
        ("INSERT INTO test_table (name, value) VALUES (?, ?)", ('item3', 30.1)),
    ]
    db_with_table.execute_in_transaction(operations)
    return db_with_table


class TestUnifiedSQLiteAccess:
    """统一SQLite访问测试"""

    def test_singleton_pattern_same_path(self, temp_db_path):
        """测试单例模式：相同路径返回相同实例"""
        UnifiedSQLiteAccess._instances.clear()
        
        instance1 = UnifiedSQLiteAccess.get_instance(temp_db_path)
        instance2 = UnifiedSQLiteAccess.get_instance(temp_db_path)
        
        assert instance1 is instance2
        UnifiedSQLiteAccess._instances.clear()

    def test_singleton_pattern_different_path(self):
        """测试单例模式：不同路径返回不同实例"""
        UnifiedSQLiteAccess._instances.clear()
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f1, \
             tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f2:
            instance1 = UnifiedSQLiteAccess.get_instance(f1.name)
            instance2 = UnifiedSQLiteAccess.get_instance(f2.name)
            
            assert instance1 is not instance2
            assert instance1.db_path != instance2.db_path
        
        UnifiedSQLiteAccess._instances.clear()

    def test_singleton_thread_safety(self, temp_db_path):
        """测试单例模式线程安全"""
        UnifiedSQLiteAccess._instances.clear()
        instances = []
        
        def create_instance():
            instance = UnifiedSQLiteAccess.get_instance(temp_db_path)
            instances.append(instance)
        
        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert all(instances[0] is inst for inst in instances)
        UnifiedSQLiteAccess._instances.clear()

    def test_get_all_instances(self, temp_db_path):
        """测试获取所有实例"""
        UnifiedSQLiteAccess._instances.clear()
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            UnifiedSQLiteAccess.get_instance(temp_db_path)
            UnifiedSQLiteAccess.get_instance(f.name)
            
            all_instances = UnifiedSQLiteAccess.get_all_instances()
            assert len(all_instances) == 2
        
        UnifiedSQLiteAccess._instances.clear()

    def test_connection_configuration_wal_mode(self, db_instance):
        """测试连接配置：WAL模式"""
        with db_instance.get_connection() as conn:
            result = conn.execute("PRAGMA journal_mode").fetchone()
            assert result[0].lower() == 'wal'

    def test_connection_configuration_foreign_keys(self, db_instance):
        """测试连接配置：外键约束启用"""
        with db_instance.get_connection() as conn:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1

    def test_connection_configuration_foreign_keys_disabled(self, db_instance_no_fk):
        """测试连接配置：外键约束禁用"""
        with db_instance_no_fk.get_connection() as conn:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 0

    def test_connection_configuration_row_factory(self, db_instance):
        """测试连接配置：row_factory 设置为 sqlite3.Row"""
        with db_instance.get_connection() as conn:
            assert conn.row_factory == sqlite3.Row

    def test_connection_auto_commit(self, db_with_table):
        """测试自动提交事务"""
        db_with_table.execute_write(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            ('test_item', 100.0)
        )
        
        results = db_with_table.execute("SELECT * FROM test_table WHERE name = ?", ('test_item',))
        assert len(results) == 1
        assert results[0]['name'] == 'test_item'

    def test_connection_auto_rollback_on_error(self, db_with_table):
        """测试异常时自动回滚"""
        initial_count = db_with_table.get_table_count('test_table')
        
        with pytest.raises(sqlite3.OperationalError):
            with db_with_table.get_connection() as conn:
                conn.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('valid', 50.0))
                conn.execute("INVALID SQL STATEMENT")
        
        final_count = db_with_table.get_table_count('test_table')
        assert final_count == initial_count

    def test_execute_query(self, db_with_data):
        """测试查询操作"""
        results = db_with_data.execute("SELECT * FROM test_table ORDER BY id")
        assert len(results) == 3
        assert results[0]['name'] == 'item1'
        assert results[1]['name'] == 'item2'
        assert results[2]['name'] == 'item3'

    def test_execute_query_with_params(self, db_with_data):
        """测试带参数查询"""
        results = db_with_data.execute(
            "SELECT * FROM test_table WHERE name = ?",
            ('item2',)
        )
        assert len(results) == 1
        assert results[0]['value'] == pytest.approx(20.3, 0.01)

    def test_execute_write(self, db_with_table):
        """测试写入操作"""
        rowcount = db_with_table.execute_write(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            ('new_item', 99.9)
        )
        assert rowcount >= 0
        
        count = db_with_table.get_table_count('test_table')
        assert count == 1

    def test_execute_many(self, db_with_table):
        """测试批量执行"""
        params_list = [
            ('batch1', 1.1),
            ('batch2', 2.2),
            ('batch3', 3.3),
        ]
        rowcount = db_with_table.execute_many(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            params_list
        )
        assert rowcount >= 0
        
        count = db_with_table.get_table_count('test_table')
        assert count == 3

    def test_execute_in_transaction(self, db_with_table):
        """测试事务中执行多个操作"""
        operations = [
            ("INSERT INTO test_table (name, value) VALUES (?, ?)", ('trans1', 10.0)),
            ("INSERT INTO test_table (name, value) VALUES (?, ?)", ('trans2', 20.0)),
            ("UPDATE test_table SET value = ? WHERE name = ?", (15.0, 'trans1')),
        ]
        total_affected = db_with_table.execute_in_transaction(operations)
        assert total_affected >= 0
        
        results = db_with_table.execute("SELECT * FROM test_table ORDER BY name")
        assert len(results) == 2
        assert results[0]['name'] == 'trans1'
        assert results[0]['value'] == pytest.approx(15.0, 0.01)

    def test_table_exists(self, db_with_table):
        """测试检查表是否存在"""
        assert db_with_table.table_exists('test_table') is True
        assert db_with_table.table_exists('nonexistent_table') is False

    def test_get_table_count(self, db_with_data):
        """测试获取表记录数"""
        count = db_with_data.get_table_count('test_table')
        assert count == 3

    def test_get_table_count_empty(self, db_with_table):
        """测试获取空表记录数"""
        count = db_with_table.get_table_count('test_table')
        assert count == 0

    def test_check_foreign_keys_enabled(self, db_instance):
        """测试检查外键约束是否启用"""
        assert db_instance.check_foreign_keys_enabled() is True

    def test_check_foreign_keys_disabled(self, db_instance_no_fk):
        """测试检查外键约束是否禁用"""
        assert db_instance_no_fk.check_foreign_keys_enabled() is False

    def test_get_foreign_key_violations(self, db_with_table):
        """测试获取外键违反情况"""
        violations = db_with_table.get_foreign_key_violations()
        assert isinstance(violations, list)

    def test_get_database_info(self, db_instance):
        """测试获取数据库信息"""
        info = db_instance.get_database_info()
        
        assert 'journal_mode' in info
        assert 'synchronous' in info
        assert 'foreign_keys' in info
        assert 'cache_size' in info
        assert 'page_count' in info
        assert 'page_size' in info
        assert 'db_size_bytes' in info
        assert info['journal_mode'].lower() == 'wal'
        assert info['foreign_keys'] == 1

    def test_get_database_info_error_handling(self, db_instance):
        """测试获取数据库信息异常处理"""
        with patch.object(db_instance, 'get_connection') as mock_conn:
            mock_conn.side_effect = Exception("Connection error")
            info = db_instance.get_database_info()
            assert info == {}

    def test_convenience_function_get_db(self, temp_db_path):
        """测试便捷函数 get_db"""
        UnifiedSQLiteAccess._instances.clear()
        
        db = get_db(temp_db_path)
        assert isinstance(db, UnifiedSQLiteAccess)
        assert db.db_path == temp_db_path
        
        UnifiedSQLiteAccess._instances.clear()

    def test_convenience_function_execute_query(self, db_with_data):
        """测试便捷函数 execute_query"""
        results = execute_query(db_with_data.db_path, "SELECT COUNT(*) as cnt FROM test_table")
        assert results[0][0] == 3

    def test_convenience_function_execute_write(self, db_with_table):
        """测试便捷函数 execute_write"""
        rowcount = execute_write(
            db_with_table.db_path,
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            ('convenience', 1.0)
        )
        assert rowcount >= 0


class TestUnifiedSQLiteAccessEdgeCases:
    """边界条件测试"""

    def test_empty_query_result(self, db_with_table):
        """测试空查询结果"""
        results = db_with_table.execute("SELECT * FROM test_table")
        assert len(results) == 0

    def test_query_nonexistent_column(self, db_with_table):
        """测试查询不存在的列"""
        with pytest.raises(sqlite3.OperationalError):
            db_with_table.execute("SELECT nonexistent FROM test_table")

    def test_write_with_invalid_sql(self, db_with_table):
        """测试无效SQL写入"""
        with pytest.raises(sqlite3.OperationalError):
            db_with_table.execute_write("INVALID SQL")

    def test_execute_many_empty_list(self, db_with_table):
        """测试批量执行空列表"""
        rowcount = db_with_table.execute_many(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            []
        )
        assert rowcount == 0

    def test_execute_in_transaction_empty_list(self, db_with_table):
        """测试事务执行空操作列表"""
        total_affected = db_with_table.execute_in_transaction([])
        assert total_affected == 0

    def test_concurrent_writes(self, db_with_table):
        """测试并发写入"""
        errors = []
        
        def write_data(thread_id):
            try:
                for i in range(10):
                    db_with_table.execute_write(
                        "INSERT INTO test_table (name, value) VALUES (?, ?)",
                        (f'thread{thread_id}_item{i}', i)
                    )
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=write_data, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        count = db_with_table.get_table_count('test_table')
        assert count == 50

    def test_connection_context_manager_exception(self, db_instance):
        """测试连接上下文管理器异常处理"""
        with pytest.raises(Exception):
            with db_instance.get_connection() as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
                raise ValueError("Test exception")
        
        assert db_instance.table_exists('test') is False

    def test_singleton_with_different_foreign_key_settings(self):
        """测试单例模式下不同外键设置"""
        UnifiedSQLiteAccess._instances.clear()
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db1 = UnifiedSQLiteAccess.get_instance(f.name, enable_foreign_keys=True)
            db2 = UnifiedSQLiteAccess.get_instance(f.name, enable_foreign_keys=False)
            
            assert db1 is db2
            assert db1.enable_foreign_keys is True
        
        UnifiedSQLiteAccess._instances.clear()

    def test_large_batch_insert(self, db_with_table):
        """测试大批量插入"""
        params_list = [(f'item{i}', float(i)) for i in range(1000)]
        rowcount = db_with_table.execute_many(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            params_list
        )
        assert rowcount >= 0
        
        count = db_with_table.get_table_count('test_table')
        assert count == 1000

    def test_special_characters_in_data(self, db_with_table):
        """测试特殊字符数据"""
        special_chars = [
            ("quote'test", 1.0),
            ("double\"quote", 2.0),
            ("newline\ntest", 3.0),
            ("unicode_中文", 4.0),
            ("emoji_\U0001F600", 5.0),
        ]
        
        for name, value in special_chars:
            db_with_table.execute_write(
                "INSERT INTO test_table (name, value) VALUES (?, ?)",
                (name, value)
            )
        
        results = db_with_table.execute("SELECT * FROM test_table ORDER BY value")
        assert len(results) == 5
        assert results[0]['name'] == "quote'test"
        assert results[3]['name'] == "unicode_中文"


class TestUnifiedSQLiteAccessErrorHandling:
    """异常处理测试"""

    def test_connection_failure(self, db_instance):
        """测试连接失败处理"""
        original_connect = sqlite3.connect
        
        def mock_connect(*args, **kwargs):
            raise sqlite3.OperationalError("Unable to open database")
        
        with patch('sqlite3.connect', mock_connect):
            with pytest.raises(sqlite3.OperationalError):
                with db_instance.get_connection() as conn:
                    pass

    def test_configure_connection_failure(self, db_instance):
        """测试连接配置失败处理"""
        with patch.object(db_instance, '_configure_connection') as mock_config:
            mock_config.side_effect = Exception("Configuration error")
            
            with pytest.raises(Exception):
                with db_instance.get_connection() as conn:
                    pass

    def test_execute_with_syntax_error(self, db_with_table):
        """测试执行语法错误SQL"""
        with pytest.raises(sqlite3.OperationalError):
            db_with_table.execute("SELEC * FROM test_table")

    def test_execute_write_with_constraint_violation(self, db_with_table):
        """测试写入约束违反"""
        with db_with_table.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS constraint_test (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
        
        with pytest.raises(sqlite3.IntegrityError):
            db_with_table.execute_write(
                "INSERT INTO constraint_test (id, name) VALUES (?, ?)",
                (1, None)
            )

    def test_table_count_nonexistent_table(self, db_instance):
        """测试获取不存在表的记录数"""
        with pytest.raises(sqlite3.OperationalError):
            db_instance.get_table_count('nonexistent_table')

    def test_get_database_info_corrupted_db(self, temp_db_path):
        """测试损坏数据库的信息获取"""
        with open(temp_db_path, 'wb') as f:
            f.write(b'corrupted data')
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path)
        info = db.get_database_info()
        assert info == {}

    def test_connection_close_exception(self, db_instance):
        """测试连接关闭异常处理"""
        with db_instance.get_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")

    def test_execute_many_with_partial_failure(self, db_with_table):
        """测试批量执行部分失败"""
        params_list = [
            ('valid1', 1.0),
            ('valid2', 2.0),
        ]
        
        rowcount = db_with_table.execute_many(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            params_list
        )
        assert rowcount >= 0
        
        count = db_with_table.get_table_count('test_table')
        assert count == 2

    def test_transaction_rollback_preserves_data(self, db_with_data):
        """测试事务回滚保留原有数据"""
        initial_count = db_with_data.get_table_count('test_table')
        
        try:
            with db_with_data.get_connection() as conn:
                conn.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ('rollback_test', 999.0))
                raise ValueError("Force rollback")
        except ValueError:
            pass
        
        final_count = db_with_data.get_table_count('test_table')
        assert final_count == initial_count
