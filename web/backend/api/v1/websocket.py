"""
WebSocket路由
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.websocket_manager import websocket_manager
from web.backend.security.jwt import verify_token


router = APIRouter(prefix="/ws", tags=["WebSocket"])


async def get_current_user_id_from_token(token: str) -> Optional[int]:
    """
    从token获取用户ID
    """
    try:
        payload = verify_token(token)
        if payload:
            return payload.get("user_id")
    except Exception as e:
        print(f"Token验证失败: {e}")
    return None


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token")
):
    """
    WebSocket通知端点
    """
    user_id = await get_current_user_id_from_token(token)
    
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    await websocket_manager.connect(websocket, user_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket错误: {e}")
        websocket_manager.disconnect(websocket)


@router.get("/stats")
async def websocket_stats():
    """
    WebSocket统计信息
    """
    return {
        "active_users": websocket_manager.get_active_users_count(),
        "total_connections": websocket_manager.get_total_connections_count()
    }
