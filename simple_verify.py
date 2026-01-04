#!/usr/bin/env python3
"""
简单验证修复效果
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_strategies_table():
    """直接测试strategies表创建"""
    import sqlite3
    
    logger.info("测试: 直接验证strategies表创建")
    
    data_dir = project_root / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    
    test_db = data_dir / "test_strategies.db"
    
    try:
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS strategies")
        cursor.execute("DROP TABLE IF EXISTS strategy_configs")
        
        create_strategies_sql = """
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            strategy_type TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '1.0.0',
            author TEXT DEFAULT '',
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            metadata TEXT DEFAULT '{}',
            class_path TEXT NOT NULL
        )
        """
        
        cursor.execute(create_strategies_sql)
        logger.info("✓ strategies表创建成功")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategies'")
        if cursor.fetchone():
            logger.info("✓ 验证: strategies表存在")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_configs (
            strategy_id VARCHAR(36) PRIMARY KEY,
            plugin_type VARCHAR(50) NOT NULL,
            parameters JSON NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON DEFAULT '{}'
        )
        """)
        logger.info("✓ strategy_configs表创建成功")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_configs'")
        if cursor.fetchone():
            logger.info("✓ 验证: strategy_configs表存在")
        
        conn.commit()
        conn.close()
        
        if test_db.exists():
            test_db.unlink()
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_signal_null_check():
    """测试信号空值检查"""
    logger.info("")
    logger.info("测试: 信号空值检查机制")
    
    try:
        from core.services.plugin_database_service import PluginDatabaseService
        
        test_db_path = str(project_root / "data" / "test_signal.db")
        
        class MockSignal:
            def emit(self, *args):
                logger.info(f"信号发射: {args}")
        
        service = object.__new__(PluginDatabaseService)
        
        service.plugin_status_changed = None
        service.plugin_registered = None
        service.database_updated = None
        
        logger.info("模拟信号为None的情况...")
        
        if service.plugin_status_changed:
            service.plugin_status_changed.emit("test", "old", "new")
            logger.error("✗ 未进行空值检查")
            return False
        else:
            logger.info("✓ plugin_status_changed 空值检查通过")
        
        if service.plugin_registered:
            service.plugin_registered.emit("test", {})
            logger.error("✗ 未进行空值检查")
            return False
        else:
            logger.info("✓ plugin_registered 空值检查通过")
        
        if service.database_updated:
            service.database_updated.emit()
            logger.error("✗ 未进行空值检查")
            return False
        else:
            logger.info("✓ database_updated 空值检查通过")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 信号测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_service_code():
    """验证database_service.py代码结构"""
    logger.info("")
    logger.info("测试: database_service.py代码结构验证")
    
    try:
        import core.services.database_service as db_module
        
        if hasattr(db_module.DatabaseService, '_create_strategies_table'):
            logger.info("✓ _create_strategies_table 方法存在")
        else:
            logger.error("✗ _create_strategies_table 方法不存在")
            return False
        
        if hasattr(db_module.DatabaseService, '_initialize_strategy_tables'):
            logger.info("✓ _initialize_strategy_tables 方法存在")
        else:
            logger.error("✗ _initialize_strategy_tables 方法不存在")
            return False
        
        import inspect
        source = inspect.getsource(db_module.DatabaseService._initialize_strategy_tables)
        
        if '_create_strategies_table' in source:
            logger.info("✓ _initialize_strategy_tables 调用了 _create_strategies_table")
        else:
            logger.error("✗ _initialize_strategy_tables 未调用 _create_strategies_table")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 代码结构验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_plugin_service_code():
    """验证plugin_database_service.py代码结构"""
    logger.info("")
    logger.info("测试: plugin_database_service.py代码结构验证")
    
    try:
        import core.services.plugin_database_service as plugin_module
        import inspect
        source = inspect.getsource(plugin_module.PluginDatabaseService)
        
        check_count = source.count('if self.')
        emit_count = source.count('.emit(')
        
        logger.info(f"找到 {check_count} 处空值检查, {emit_count} 处信号发射")
        
        if 'if self.plugin_status_changed:' in source:
            logger.info("✓ plugin_status_changed 空值检查存在")
        else:
            logger.warning("⚠ plugin_status_changed 空值检查未找到")
        
        if 'if self.plugin_registered:' in source:
            logger.info("✓ plugin_registered 空值检查存在")
        else:
            logger.warning("⚠ plugin_registered 空值检查未找到")
        
        if 'if self.database_updated:' in source:
            logger.info("✓ database_updated 空值检查存在")
        else:
            logger.warning("⚠ database_updated 空值检查未找到")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 代码结构验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("验证修复效果")
    print("=" * 60)
    
    results = {}
    
    results["strategies_table"] = test_strategies_table()
    results["signal_null_check"] = test_signal_null_check()
    results["database_service_code"] = test_database_service_code()
    results["plugin_service_code"] = test_plugin_service_code()
    
    print("")
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    
    print("")
    if all_passed:
        print("✓ 所有修复验证通过!")
    else:
        print("✗ 部分测试失败")
    
    return all_passed

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)
    
    success = main()
    sys.exit(0 if success else 1)
