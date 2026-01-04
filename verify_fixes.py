#!/usr/bin/env python3
"""
验证数据库初始化和信号机制修复效果
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
import sqlite3

def test_database_initialization():
    """测试数据库初始化修复效果"""
    logger.info("=" * 60)
    logger.info("测试1: 数据库初始化修复验证")
    logger.info("=" * 60)
    
    try:
        import traceback
        traceback_info = traceback.format_exc()
        logger.debug(f"导入堆栈: {traceback_info}")
        
        from core.services.database_service import DatabaseService
        from core.containers import get_service_container
        
        logger.info("正在初始化数据库服务...")
        container = get_service_container()
        db_service = container.get_service("DatabaseService")
        
        if db_service is None:
            db_service = DatabaseService(container)
            container.register_service(db_service)
        
        logger.info("正在调用 _initialize_strategy_tables...")
        db_service._initialize_strategy_tables()
        
        logger.info("验证 strategies 表是否存在...")
        strategy_db_path = os.path.join(project_root, "data", "strategy_system.sqlite")
        
        if not os.path.exists(strategy_db_path):
            strategy_db_path = os.path.join(project_root, "data", "factorweave_system.sqlite")
        
        if os.path.exists(strategy_db_path):
            conn = sqlite3.connect(strategy_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategies'")
            result = cursor.fetchone()
            
            if result:
                logger.info("✓ strategies 表已成功创建!")
                
                cursor.execute("SELECT COUNT(*) FROM strategies")
                count = cursor.fetchone()[0]
                logger.info(f"  - 表中记录数: {count}")
            else:
                logger.error("✗ strategies 表未找到!")
                return False
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_configs'")
            result = cursor.fetchone()
            
            if result:
                logger.info("✓ strategy_configs 表存在")
            else:
                logger.error("✗ strategy_configs 表未找到!")
                return False
            
            conn.close()
            return True
        else:
            logger.error(f"✗ 数据库文件不存在: {strategy_db_path}")
            return False
            
    except Exception as e:
        logger.error(f"数据库初始化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_signal_mechanism():
    """测试信号机制修复效果"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试2: PyQt5信号机制修复验证")
    logger.info("=" * 60)
    
    try:
        from core.services.plugin_database_service import PluginDatabaseService
        
        logger.info("正在创建 PluginDatabaseService 实例...")
        test_db_path = os.path.join(project_root, "data", "test_plugin_system.sqlite")
        plugin_service = PluginDatabaseService(test_db_path)
        
        logger.info("检查信号初始化状态...")
        logger.info(f"  - plugin_status_changed: {'有效' if plugin_service.plugin_status_changed else 'None (预期)'}")
        logger.info(f"  - plugin_registered: {'有效' if plugin_service.plugin_registered else 'None (预期)'}")
        logger.info(f"  - database_updated: {'有效' if plugin_service.database_updated else 'None (预期)'}")
        
        from db.models.plugin_models import PluginStatus
        
        logger.info("测试信号发射 (带空值检查)...")
        test_plugin_name = "test_signal_plugin"
        
        try:
            plugin_service.update_plugin_status(
                test_plugin_name, 
                PluginStatus.LOADED,
                reason="测试信号机制",
                error_message=""
            )
            logger.info("✓ update_plugin_status 信号发射成功 (无空指针异常)")
        except AttributeError as e:
            logger.error(f"✗ 信号发射失败: {e}")
            return False
        
        try:
            plugin_service.save_plugin_config_json(
                test_plugin_name, 
                {"test_key": "test_value"},
                config_type='user'
            )
            logger.info("✓ save_plugin_config_json 信号发射成功 (无空指针异常)")
        except AttributeError as e:
            logger.error(f"✗ 信号发射失败: {e}")
            return False
        
        logger.info("✓ 所有信号机制测试通过!")
        return True
        
    except Exception as e:
        logger.error(f"信号机制测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    logger.remove()
    logger.add(sys.stderr, level="DEBUG", format="{time:HH:mm:ss} | {level} | {message}", colorize=True)
    
    logger.info("=" * 60)
    logger.info("验证数据库初始化和信号机制修复效果")
    logger.info("=" * 60)
    
    results = {}
    
    results["database_init"] = test_database_initialization()
    results["signal_mechanism"] = test_signal_mechanism()
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        logger.info(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    
    logger.info("")
    if all_passed:
        logger.info("✓ 所有修复验证通过!")
    else:
        logger.error("✗ 部分测试失败，请检查上述日志")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
