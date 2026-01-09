"""
WebSocket和错误边界功能测试
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.main import app
from web.backend.websocket_manager import websocket_manager


client = TestClient(app)


def test_websocket_stats_endpoint():
    """
    测试WebSocket统计端点
    """
    print("=== 测试WebSocket统计端点 ===")
    
    response = client.get("/api/v1/ws/stats")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "active_users" in data
    assert "total_connections" in data
    assert isinstance(data["active_users"], int)
    assert isinstance(data["total_connections"], int)
    
    print(f"✓ WebSocket统计: {data}")


def test_connection_manager_methods():
    """
    测试连接管理器方法
    """
    print("\n=== 测试连接管理器方法 ===")
    
    # 测试获取活跃用户数
    active_count = websocket_manager.get_active_users_count()
    assert isinstance(active_count, int)
    print(f"✓ 活跃用户数: {active_count}")
    
    # 测试获取总连接数
    total_count = websocket_manager.get_total_connections_count()
    assert isinstance(total_count, int)
    print(f"✓ 总连接数: {total_count}")


def test_websocket_manager_structure():
    """
    测试WebSocket管理器结构
    """
    print("\n=== 测试WebSocket管理器结构 ===")
    
    # 检查管理器是否有必要的方法
    assert hasattr(websocket_manager, 'connect')
    assert hasattr(websocket_manager, 'disconnect')
    assert hasattr(websocket_manager, 'send_personal_message')
    assert hasattr(websocket_manager, 'broadcast')
    assert hasattr(websocket_manager, 'send_notification')
    assert hasattr(websocket_manager, 'send_system_message')
    assert hasattr(websocket_manager, 'get_active_users_count')
    assert hasattr(websocket_manager, 'get_total_connections_count')
    
    # 检查连接字典
    assert hasattr(websocket_manager, 'active_connections')
    assert hasattr(websocket_manager, 'user_connections')
    
    print("✓ WebSocket管理器结构正确")


def test_websocket_manager_initialization():
    """
    测试WebSocket管理器初始化
    """
    print("\n=== 测试WebSocket管理器初始化 ===")
    
    # 检查初始状态
    assert websocket_manager.active_connections == {}
    assert websocket_manager.user_connections == {}
    
    print("✓ WebSocket管理器初始化正确")


if __name__ == "__main__":
    print("开始测试WebSocket和错误边界功能...\n")
    
    try:
        test_websocket_stats_endpoint()
        test_connection_manager_methods()
        test_websocket_manager_structure()
        test_websocket_manager_initialization()
        
        print("\n" + "="*50)
        print("✓ 所有测试通过！")
        print("="*50)
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        sys.exit(1)
