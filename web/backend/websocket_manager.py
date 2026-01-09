"""
WebSocket管理器
"""

from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from datetime import datetime


class ConnectionManager:
    """
    WebSocket连接管理器
    """
    
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.user_connections: Dict[WebSocket, int] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """
        连接WebSocket
        """
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        self.user_connections[websocket] = user_id
        
        print(f"WebSocket连接成功: user_id={user_id}")
    
    def disconnect(self, websocket: WebSocket):
        """
        断开WebSocket连接
        """
        user_id = self.user_connections.get(websocket)
        
        if user_id and user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        if websocket in self.user_connections:
            del self.user_connections[websocket]
        
        print(f"WebSocket断开连接: user_id={user_id}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """
        发送个人消息
        """
        if user_id in self.active_connections:
            disconnected = set()
            
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"发送消息失败: {e}")
                    disconnected.add(connection)
            
            for connection in disconnected:
                self.disconnect(connection)
    
    async def broadcast(self, message: dict):
        """
        广播消息给所有连接
        """
        disconnected = set()
        
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"广播消息失败: {e}")
                    disconnected.add(connection)
        
        for connection in disconnected:
            self.disconnect(connection)
    
    async def send_notification(
        self,
        user_id: int,
        notification: dict
    ):
        """
        发送通知
        """
        message = {
            "type": "notification",
            "data": notification,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.send_personal_message(message, user_id)
    
    async def send_system_message(self, message: str):
        """
        发送系统消息
        """
        message = {
            "type": "system",
            "data": {
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.broadcast(message)
    
    def get_active_users_count(self) -> int:
        """
        获取活跃用户数
        """
        return len(self.active_connections)
    
    def get_total_connections_count(self) -> int:
        """
        获取总连接数
        """
        return len(self.user_connections)


websocket_manager = ConnectionManager()
