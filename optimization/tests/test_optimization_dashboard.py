#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化仪表板单元测试

测试优化仪表板的各种组件和功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import timedelta
import sqlite3
import tempfile

try:
    from optimization.optimization_dashboard import (
        OptimizationDashboardConfig,
        OptimizationDataManager,
        DatabaseConnectionManager,
        OptimizationExecutor
    )
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"导入失败: {e}")
    IMPORTS_AVAILABLE = False


def run_tests():
    """运行测试"""
    if not IMPORTS_AVAILABLE:
        print("无法导入优化仪表板模块，跳过测试")
        return
    
    print("开始运行测试...")
    
    # 测试配置管理器
    print("\n=== 测试配置管理器 ===")
    test_config_manager()
    
    # 测试数据库连接管理器
    print("\n=== 测试数据库连接管理器 ===")
    test_database_connection_manager()
    
    # 测试数据管理器
    print("\n=== 测试数据管理器 ===")
    test_data_manager()
    
    # 测试优化执行器
    print("\n=== 测试优化执行器 ===")
    test_optimization_executor()
    
    print("\n=== 所有测试完成 ===")


def test_config_manager():
    """测试配置管理器"""
    try:
        config_service = Mock()
        config = OptimizationDashboardConfig(config_service)
        
        # 测试默认配置
        assert config._config['window']['width'] == 1400
        assert config._config['window']['height'] == 900
        assert config._config['cache']['ttl_minutes'] == 5
        print("✓ 默认配置测试通过")
        
        # 测试获取窗口几何信息
        x, y, width, height = config.get_window_geometry()
        assert x == 100
        assert y == 100
        assert width == 1400
        assert height == 900
        print("✓ 窗口几何信息测试通过")
        
        # 测试获取缓存过期时间
        ttl = config.get_cache_ttl()
        assert ttl == timedelta(minutes=5)
        print("✓ 缓存过期时间测试通过")
        
        # 测试获取数据限制
        limits = config.get_data_limits()
        assert limits['history_limit'] == 100
        assert limits['version_limit'] == 50
        assert limits['performance_limit'] == 20
        print("✓ 数据限制测试通过")
        
        # 测试获取优化配置
        opt_config = config.get_optimization_config()
        assert opt_config['max_iterations'] == 30
        assert opt_config['population_size'] == 15
        assert opt_config['performance_threshold'] == 0.7
        assert opt_config['improvement_target'] == 0.1
        print("✓ 优化配置测试通过")
        
    except Exception as e:
        print(f"✗ 配置管理器测试失败: {e}")


def test_database_connection_manager():
    """测试数据库连接管理器"""
    try:
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        db_path = temp_db.name
        
        # 创建测试表
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )
            ''')
            cursor.execute("INSERT INTO test_table (name) VALUES ('test1')")
            cursor.execute("INSERT INTO test_table (name) VALUES ('test2')")
            conn.commit()
        
        connection_manager = DatabaseConnectionManager(
            db_path=db_path,
            max_connections=3
        )
        
        # 测试获取连接
        conn = connection_manager.get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        connection_manager.release_connection(conn)
        print("✓ 获取连接测试通过")
        
        # 测试连接池
        conn1 = connection_manager.get_connection()
        conn2 = connection_manager.get_connection()
        
        assert conn1 is not None
        assert conn2 is not None
        
        connection_manager.release_connection(conn1)
        
        conn3 = connection_manager.get_connection()
        assert conn3 == conn1  # 应该重用连接
        
        connection_manager.release_connection(conn2)
        connection_manager.release_connection(conn3)
        print("✓ 连接池测试通过")
        
        # 测试上下文管理器
        with connection_manager as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_table")
            results = cursor.fetchall()
            assert len(results) == 2
        print("✓ 上下文管理器测试通过")
        
        # 测试关闭所有连接
        connection_manager.close_all()
        assert len(connection_manager._connections) == 0
        assert len(connection_manager._in_use) == 0
        print("✓ 关闭所有连接测试通过")
        
        # 清理
        if os.path.exists(db_path):
            os.unlink(db_path)
        
    except Exception as e:
        print(f"✗ 数据库连接管理器测试失败: {e}")


def test_data_manager():
    """测试数据管理器"""
    try:
        db_manager = Mock()
        pattern_manager = Mock()
        auto_tuner = Mock()
        cache_service = Mock()
        
        cache_service.get.return_value = None
        
        data_manager = OptimizationDataManager(
            db_manager=db_manager,
            pattern_manager=pattern_manager,
            auto_tuner=auto_tuner,
            cache_service=cache_service,
            cache_ttl=timedelta(minutes=5)
        )
        
        # 测试加载形态列表
        mock_pattern = Mock()
        mock_pattern.english_name = "test_pattern"
        mock_pattern.is_active = True
        
        pattern_manager.get_all_patterns.return_value = [mock_pattern]
        
        patterns = data_manager.load_pattern_list()
        
        assert len(patterns) == 1
        assert patterns[0] == "test_pattern"
        assert cache_service.get.called
        assert cache_service.set.called
        print("✓ 加载形态列表测试通过")
        
        # 测试从缓存加载形态列表
        cached_patterns = ["cached_pattern1", "cached_pattern2"]
        cache_service.get.return_value = cached_patterns
        
        patterns = data_manager.load_pattern_list()
        
        assert patterns == cached_patterns
        assert not cache_service.set.called
        print("✓ 从缓存加载形态列表测试通过")
        
        # 测试使缓存失效
        cache_service.get.return_value = None
        data_manager.invalidate_cache('all')
        assert cache_service.delete.called
        print("✓ 使缓存失效测试通过")
        
    except Exception as e:
        print(f"✗ 数据管理器测试失败: {e}")


def test_optimization_executor():
    """测试优化执行器"""
    try:
        auto_tuner = Mock()
        dashboard = Mock()
        
        executor = OptimizationExecutor(
            auto_tuner=auto_tuner,
            dashboard=dashboard
        )
        
        # 测试执行一键优化
        auto_tuner.one_click_optimize.return_value = {
            "summary": {
                "total_tasks": 10,
                "successful_tasks": 8,
                "average_improvement": 15.5
            }
        }
        
        executor.execute_one_click_optimize()
        
        assert auto_tuner.one_click_optimize.called
        print("✓ 执行一键优化测试通过")
        
        # 测试执行智能优化
        auto_tuner.smart_optimize.return_value = {
            "status": "completed",
            "summary": {
                "total_tasks": 5,
                "successful_tasks": 5,
                "average_improvement": 20.0
            }
        }
        
        executor.execute_smart_optimize()
        
        assert auto_tuner.smart_optimize.called
        print("✓ 执行智能优化测试通过")
        
        # 测试智能优化无需优化
        auto_tuner.smart_optimize.return_value = {
            "status": "no_optimization_needed"
        }
        
        executor.execute_smart_optimize()
        
        assert dashboard.log_message.called
        print("✓ 智能优化无需优化测试通过")
        
        # 测试执行单个形态优化
        auto_tuner.optimizer.optimize_algorithm.return_value = {
            "improvement_percentage": 25.5
        }
        
        executor.execute_pattern_optimize("test_pattern")
        
        assert auto_tuner.optimizer.optimize_algorithm.called
        print("✓ 执行单个形态优化测试通过")
        
    except Exception as e:
        print(f"✗ 优化执行器测试失败: {e}")


if __name__ == '__main__':
    print("=== 开始执行测试 ===")
    print(f"IMPORTS_AVAILABLE: {IMPORTS_AVAILABLE}")
    run_tests()
    print("=== 测试执行结束 ===")
