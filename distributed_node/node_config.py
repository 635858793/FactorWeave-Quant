"""
分布式节点配置管理

提供节点的配置加载、验证和管理功能
"""

import os
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


@dataclass
class NodeConfig:
    """节点配置"""
    # 节点标识
    node_id: str = ""  # 自动生成UUID
    node_name: str = "Distributed Node"

    # 网络配置
    host: str = "0.0.0.0"
    port: int = 8900
    api_key: Optional[str] = None  # API认证密钥

    # 主控节点配置
    master_host: str = "localhost"
    master_port: int = 8888
    auto_register: bool = True  # 启动时自动注册到主控

    # 性能配置
    max_workers: int = 4  # 最大并发任务数
    task_timeout: int = 300  # 任务超时时间（秒）
    heartbeat_interval: int = 10  # 心跳间隔（秒）

    # 资源限制
    max_memory_mb: int = 4096  # 最大内存使用（MB）
    max_cpu_percent: float = 80.0  # 最大CPU使用率（%）

    # 日志配置
    log_level: str = "INFO"
    log_file: str = "logs/node.log"

    # 数据目录
    data_dir: str = "data/node_data"
    cache_dir: str = "cache/node_cache"

    # 节点能力配置（支持的任务类型）
    capabilities: list = None  # 支持的功能列表，None表示自动检测

    def __post_init__(self):
        """初始化后处理"""
        if not self.node_id:
            import uuid
            self.node_id = str(uuid.uuid4())[:8]

        # 如果未指定能力，自动检测
        if self.capabilities is None:
            self.capabilities = self._detect_capabilities()

    def _detect_capabilities(self) -> list:
        """
        自动检测节点支持的功能

        注意：分布式节点与主程序一起部署，共享相同代码库
        因此直接检测本地模块即可
        """
        capabilities = []

        # 基础功能（所有节点都支持）
        capabilities.append("data_fetch")  # 数据获取
        capabilities.append("data_process")  # 数据处理

        # 检测分析能力
        try:
            import pandas as pd
            import numpy as np
            capabilities.append("analysis")  # 技术分析
            capabilities.append("indicator_calc")  # 指标计算
        except ImportError:
            pass

        # 检测回测能力（检测系统内置回测引擎）
        try:
            from backtest import UnifiedBacktestEngine
            capabilities.append("backtest")
            capabilities.append("backtest_builtin")
            logger.debug("检测到系统内置回测引擎 (UnifiedBacktestEngine)")
        except ImportError:
            logger.debug("未检测到系统内置回测引擎")

        # 检测优化能力
        try:
            from scipy import optimize
            capabilities.append("optimization")  # 参数优化
            capabilities.append("genetic_algorithm")  # 遗传算法
        except ImportError:
            pass

        # 检测机器学习能力
        try:
            import sklearn
            capabilities.append("machine_learning")  # 机器学习
            capabilities.append("model_training")  # 模型训练
        except ImportError:
            pass

        # 检测深度学习能力
        try:
            import torch
            capabilities.append("deep_learning")  # 深度学习
            capabilities.append("neural_network")  # 神经网络
        except ImportError:
            try:
                import tensorflow
                capabilities.append("deep_learning")
                capabilities.append("neural_network")
            except ImportError:
                pass

        # 检测GPU加速能力
        try:
            import torch
            if torch.cuda.is_available():
                capabilities.append("gpu_acceleration")  # GPU加速
                capabilities.append("cuda_compute")  # CUDA计算
        except Exception:
            pass

        # 检测数据导入能力
        try:
            import akshare
            capabilities.append("data_import")  # 数据导入
            capabilities.append("stock_data")  # 股票数据
        except ImportError:
            pass

        # 检测数据库能力
        try:
            import duckdb
            capabilities.append("duckdb_storage")  # DuckDB存储
        except ImportError:
            pass

        try:
            import sqlite3
            capabilities.append("sqlite_storage")  # SQLite存储
        except ImportError:
            pass

        logger.info(f"节点能力检测完成，支持功能: {capabilities}")
        return capabilities

    @classmethod
    def load_from_file(cls, config_file: str) -> 'NodeConfig':
        """从文件加载配置"""
        config_path = Path(config_file)
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"从文件加载配置: {config_file}")
                return cls(**data)
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                return cls()
        else:
            logger.warning(f"配置文件不存在: {config_file}，使用默认配置")
            return cls()

    @classmethod
    def load_from_env(cls) -> 'NodeConfig':
        """从环境变量加载配置"""
        return cls(
            node_id=os.getenv('NODE_ID', ''),
            node_name=os.getenv('NODE_NAME', 'Distributed Node'),
            host=os.getenv('NODE_HOST', '0.0.0.0'),
            port=int(os.getenv('NODE_PORT', '8900')),
            api_key=os.getenv('NODE_API_KEY'),
            master_host=os.getenv('MASTER_HOST', 'localhost'),
            master_port=int(os.getenv('MASTER_PORT', '8888')),
            auto_register=os.getenv('AUTO_REGISTER', 'true').lower() == 'true',
            max_workers=int(os.getenv('MAX_WORKERS', '4')),
            task_timeout=int(os.getenv('TASK_TIMEOUT', '300')),
            heartbeat_interval=int(os.getenv('HEARTBEAT_INTERVAL', '10')),
            max_memory_mb=int(os.getenv('MAX_MEMORY_MB', '4096')),
            max_cpu_percent=float(os.getenv('MAX_CPU_PERCENT', '80.0')),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file=os.getenv('LOG_FILE', 'logs/node.log'),
            data_dir=os.getenv('DATA_DIR', 'data/node_data'),
            cache_dir=os.getenv('CACHE_DIR', 'cache/node_cache'),
        )

    def save_to_file(self, config_file: str):
        """保存配置到文件"""
        config_path = Path(config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存到: {config_file}")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


# 全局配置实例
_global_config: Optional[NodeConfig] = None


def get_node_config() -> NodeConfig:
    """获取全局节点配置"""
    global _global_config
    if _global_config is None:
        # 优先从文件加载，其次环境变量
        config_file = os.getenv('NODE_CONFIG_FILE', 'distributed_node/node_config.json')
        if Path(config_file).exists():
            _global_config = NodeConfig.load_from_file(config_file)
        else:
            _global_config = NodeConfig.load_from_env()
    return _global_config


def set_node_config(config: NodeConfig):
    """设置全局节点配置"""
    global _global_config
    _global_config = config
