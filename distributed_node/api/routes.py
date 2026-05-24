"""
FastAPI路由定义

提供节点的HTTP API接口
"""

import psutil
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from loguru import logger

from distributed_node.api.models import (
    TaskRequest, TaskResponse, TaskResult,
    NodeHealth, APIResponse, TaskStatus
)
from distributed_node.task_executor import TaskExecutor
from distributed_node.node_config import get_node_config


# 创建FastAPI应用
app = FastAPI(
    title="Distributed Node API",
    description="分布式计算节点HTTP API",
    version="1.0.0"
)

# 全局任务执行器
_task_executor: TaskExecutor = None
_node_start_time = datetime.now()


def get_task_executor() -> TaskExecutor:
    """获取任务执行器（依赖注入）"""
    global _task_executor
    if _task_executor is None:
        config = get_node_config()
        _task_executor = TaskExecutor(config)
        _task_executor.start_scheduler()
    return _task_executor


async def verify_api_key(x_api_key: str = Header(None)):
    """验证API密钥"""
    config = get_node_config()
    if config.api_key and x_api_key != config.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@app.get("/")
async def root():
    """根路径"""
    config = get_node_config()
    return {
        "service": "Distributed Node API",
        "version": "1.0.0",
        "node_id": config.node_id,
        "node_name": config.node_name,
        "status": "running"
    }


@app.get("/api/v1/health", response_model=NodeHealth)
async def health_check(executor: TaskExecutor = Depends(get_task_executor)):
    """健康检查"""
    config = get_node_config()

    # 获取系统资源使用情况
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    memory_percent = memory.percent

    # 计算运行时间
    uptime = (datetime.now() - _node_start_time).total_seconds()

    # 获取任务统计
    stats = executor.get_statistics()

    # 判断节点状态
    if cpu_percent > config.max_cpu_percent or memory_percent > 90:
        status = "overloaded"
    elif stats["active_tasks"] >= config.max_workers:
        status = "busy"
    else:
        status = "active"

    return NodeHealth(
        node_id=config.node_id,
        node_name=config.node_name,
        status=status,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        active_tasks=stats["active_tasks"],
        completed_tasks=stats["total_executed"],
        failed_tasks=stats["total_failed"],
        uptime_seconds=uptime,
        last_heartbeat=datetime.now(),
        capabilities=config.capabilities or []
    )


@app.post("/api/v1/task/execute", response_model=TaskResponse)
async def execute_task(
    task_request: TaskRequest,
    executor: TaskExecutor = Depends(get_task_executor),
    api_key: str = Depends(verify_api_key)
):
    """
    执行任务

    接收任务请求并异步执行
    """
    try:
        logger.info(f"接收任务请求: {task_request.task_id} (类型: {task_request.task_type.value})")

        # 检查节点负载
        config = get_node_config()
        stats = executor.get_statistics()

        if stats["active_tasks"] >= config.max_workers:
            raise HTTPException(
                status_code=503,
                detail=f"节点繁忙，当前任务数: {stats['active_tasks']}/{config.max_workers}"
            )

        # 异步执行任务（在后台），传递优先级和超时
        import asyncio
        asyncio.create_task(
            executor.execute_task(
                task_request.task_id,
                task_request.task_type,
                task_request.task_data,
                task_request.timeout,
                task_request.priority
            )
        )

        return TaskResponse(
            task_id=task_request.task_id,
            status=TaskStatus.RUNNING,
            message="任务已接收并开始执行",
            started_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/statistics")
async def get_statistics(executor: TaskExecutor = Depends(get_task_executor)):
    """获取节点统计信息"""
    try:
        stats = executor.get_statistics()
        return APIResponse(
            success=True,
            message="获取统计信息成功",
            data=stats
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return APIResponse(
            success=False,
            message=f"获取统计信息失败: {str(e)}",
            data={}
        )


@app.get("/api/v1/task/{task_id}/status", response_model=TaskResult)
async def get_task_status(
    task_id: str,
    executor: TaskExecutor = Depends(get_task_executor)
):
    """查询任务状态"""
    result = executor.get_task_status(task_id)

    if result is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    return result


@app.get("/api/v1/node/stats")
async def get_node_stats(executor: TaskExecutor = Depends(get_task_executor)):
    """获取节点统计信息"""
    config = get_node_config()
    stats = executor.get_statistics()

    return APIResponse(
        success=True,
        message="获取统计信息成功",
        data={
            "node_info": {
                "node_id": config.node_id,
                "node_name": config.node_name,
                "max_workers": config.max_workers,
                "uptime_seconds": (datetime.now() - _node_start_time).total_seconds()
            },
            "task_stats": stats,
            "system_info": {
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                "disk_usage_percent": psutil.disk_usage('/').percent
            }
        }
    )


@app.post("/api/v1/node/shutdown")
async def shutdown_node(api_key: str = Depends(verify_api_key)):
    """关闭节点（需要API密钥）"""
    logger.warning("接收到关闭节点请求")

    # 这里可以添加优雅关闭的逻辑
    import asyncio
    asyncio.create_task(_shutdown())

    return APIResponse(
        success=True,
        message="节点正在关闭...",
        data={"shutdown_in_seconds": 5}
    )


async def _shutdown():
    """延迟关闭"""
    import asyncio
    await asyncio.sleep(5)
    import sys
    sys.exit(0)


# 错误处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "服务器内部错误",
            "error": str(exc)
        }
    )
