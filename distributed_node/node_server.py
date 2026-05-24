"""
分布式节点服务器主程序

启动FastAPI服务器并提供节点功能
"""

import sys
import uvicorn
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from distributed_node.api.routes import app
from distributed_node.node_config import get_node_config, set_node_config, NodeConfig


def register_with_master(config: NodeConfig) -> bool:
    """
    向主控节点注册当前Worker节点

    Args:
        config: 节点配置

    Returns:
        注册是否成功
    """
    if not config.auto_register:
        logger.info("自动注册已禁用，跳过向主控注册")
        return False

    try:
        import requests
        import socket

        master_url = f"http://{config.master_host}:{config.master_port}/api/v1/nodes/register"

        node_info = {
            "node_id": config.node_id,
            "node_name": config.node_name,
            "host": socket.gethostbyname(socket.gethostname()),
            "port": config.port,
            "max_workers": config.max_workers,
            "capabilities": config.capabilities or [],
            "status": "active"
        }

        headers = {}
        if config.api_key:
            headers["X-API-Key"] = config.api_key

        logger.info(f"正在向主控节点注册: {master_url}")
        logger.info(f"节点信息: {node_info}")

        response = requests.post(
            master_url,
            json=node_info,
            headers=headers,
            timeout=10
        )

        if response.status_code in (200, 201):
            logger.info(f"向主控节点注册成功: {config.node_name} ({config.node_id})")
            return True
        elif response.status_code == 409:
            logger.warning(f"节点已存在于主控: {config.node_name}")
            return True
        else:
            logger.warning(f"向主控节点注册失败: HTTP {response.status_code} - {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        logger.warning(f"无法连接到主控节点 {config.master_host}:{config.master_port}，跳过注册")
        return False
    except requests.exceptions.Timeout:
        logger.warning(f"向主控节点注册超时 {config.master_host}:{config.master_port}")
        return False
    except Exception as e:
        logger.error(f"向主控节点注册异常: {e}")
        return False


def setup_logging(config: NodeConfig):
    """设置日志"""
    log_file = Path(config.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 配置loguru
    logger.remove()  # 移除默认处理器
    
    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=config.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # 添加文件输出
    logger.add(
        config.log_file,
        level=config.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8"
    )
    
    logger.info(f"日志系统初始化完成，级别: {config.log_level}")


def create_directories(config: NodeConfig):
    """创建必要的目录"""
    dirs = [
        Path(config.data_dir),
        Path(config.cache_dir),
        Path(config.log_file).parent
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"创建目录: {dir_path}")


def start_server(config: NodeConfig = None, debug: bool = False):
    """
    启动节点服务器
    
    Args:
        config: 节点配置，如果为None则自动加载
        debug: 调试模式
    """
    # 加载配置
    if config is None:
        config = get_node_config()
    else:
        set_node_config(config)
    
    # 设置日志
    setup_logging(config)
    
    # 创建目录
    create_directories(config)
    
    # 打印配置信息
    logger.info("="*80)
    logger.info("分布式节点服务器启动")
    logger.info("="*80)
    logger.info(f"节点ID: {config.node_id}")
    logger.info(f"节点名称: {config.node_name}")
    logger.info(f"监听地址: {config.host}:{config.port}")
    logger.info(f"主控节点: {config.master_host}:{config.master_port}")
    logger.info(f"最大工作线程: {config.max_workers}")
    logger.info(f"任务超时: {config.task_timeout}秒")
    logger.info(f"API认证: {'启用' if config.api_key else '禁用'}")
    logger.info("="*80)
    
    # 自动向主控节点注册
    register_with_master(config)
    
    # 启动FastAPI服务器
    try:
        uvicorn.run(
            app,
            host=config.host,
            port=config.port,
            log_level=config.log_level.lower(),
            access_log=True,
            reload=debug
        )
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        raise
    finally:
        logger.info("服务器已关闭")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="分布式节点服务器")
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--host", type=str, help="监听地址")
    parser.add_argument("--port", type=int, help="监听端口")
    parser.add_argument("--node-name", type=str, help="节点名称")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日志级别")
    
    args = parser.parse_args()
    
    # 加载配置
    if args.config:
        config = NodeConfig.load_from_file(args.config)
    else:
        config = get_node_config()
    
    # 命令行参数覆盖
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.node_name:
        config.node_name = args.node_name
    if args.log_level:
        config.log_level = args.log_level
    
    # 启动服务器
    start_server(config, debug=args.debug)

