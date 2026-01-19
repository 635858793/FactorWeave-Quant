#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB连接池配置管理

支持：
1. 连接池参数配置
2. DuckDB优化参数配置
3. 自动化优化集成
4. 配置热重载

作者: AI Assistant
日期: 2025-10-12
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from loguru import logger


@dataclass
class ConnectionPoolConfig:
    """连接池配置"""
    pool_size: int = 15
    max_overflow: int = 100
    timeout: float = 30.0
    pool_recycle: int = 3600
    use_lifo: bool = True

    # 验证范围
    MIN_POOL_SIZE = 1
    MAX_POOL_SIZE = 50
    MIN_OVERFLOW = 0
    MAX_OVERFLOW = 100
    MIN_TIMEOUT = 1.0
    MAX_TIMEOUT = 300.0
    MIN_RECYCLE = 60
    MAX_RECYCLE = 86400

    def validate(self) -> tuple[bool, str]:
        """验证配置"""
        if not (self.MIN_POOL_SIZE <= self.pool_size <= self.MAX_POOL_SIZE):
            return False, f"pool_size必须在{self.MIN_POOL_SIZE}-{self.MAX_POOL_SIZE}之间"

        if not (self.MIN_OVERFLOW <= self.max_overflow <= self.MAX_OVERFLOW):
            return False, f"max_overflow必须在{self.MIN_OVERFLOW}-{self.MAX_OVERFLOW}之间"

        if not (self.MIN_TIMEOUT <= self.timeout <= self.MAX_TIMEOUT):
            return False, f"timeout必须在{self.MIN_TIMEOUT}-{self.MAX_TIMEOUT}秒之间"

        if not (self.MIN_RECYCLE <= self.pool_recycle <= self.MAX_RECYCLE):
            return False, f"pool_recycle必须在{self.MIN_RECYCLE}-{self.MAX_RECYCLE}秒之间"

        return True, "配置有效"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in asdict(self).items() if not k.startswith('MIN_') and not k.startswith('MAX_')}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionPoolConfig':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class DuckDBOptimizationConfig:
    """DuckDB优化配置"""
    memory_limit_gb: Optional[float] = None  # None表示自动
    threads: Optional[int] = None  # None表示自动
    enable_object_cache: bool = True
    enable_progress_bar: bool = False
    temp_directory: Optional[str] = None
    max_memory_percent: float = 0.7  # 默认70%

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DuckDBOptimizationConfig':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class ConnectionPoolConfigManager:
    """连接池配置管理器"""

    def __init__(self, config_service):
        """
        Args:
            config_service: ConfigService实例
        """
        self.config_service = config_service
        self._ensure_default_config()

    def _ensure_default_config(self):
        """确保默认配置存在"""
        if not self.config_service.get('connection_pool'):
            default_config = {
                "connection_pool": ConnectionPoolConfig().to_dict(),
                "connection_pool_scenarios": {
                    "realtime": {"timeout": 5.0},
                    "monitoring": {"timeout": 10.0},
                    "normal": {"timeout": 30.0},
                    "batch": {"timeout": 60.0},
                    "analytics": {"timeout": 120.0}
                },
                "duckdb_optimization": DuckDBOptimizationConfig().to_dict(),
                "auto_optimization": {
                    "enabled": True,
                    "workload_type": "olap"  # olap/oltp/mixed
                }
            }

            for key, value in default_config.items():
                self.config_service.set(key, value)

            logger.info("✅ 连接池默认配置已初始化")

    def load_pool_config(self) -> ConnectionPoolConfig:
        """加载连接池配置"""
        config_dict = self.config_service.get('connection_pool')
        if config_dict:
            return ConnectionPoolConfig.from_dict(config_dict)
        return ConnectionPoolConfig()

    def save_pool_config(self, config: ConnectionPoolConfig) -> bool:
        """保存连接池配置"""
        valid, msg = config.validate()
        if not valid:
            raise ValueError(msg)

        self.config_service.set('connection_pool', config.to_dict())
        logger.info(f"✅ 连接池配置已保存: {config}")
        return True

    def load_optimization_config(self) -> DuckDBOptimizationConfig:
        """加载优化配置"""
        config_dict = self.config_service.get('duckdb_optimization')
        if config_dict:
            return DuckDBOptimizationConfig.from_dict(config_dict)
        return DuckDBOptimizationConfig()

    def save_optimization_config(self, config: DuckDBOptimizationConfig) -> bool:
        """保存优化配置"""
        self.config_service.set('duckdb_optimization', config.to_dict())
        logger.info(f"✅ DuckDB优化配置已保存: {config}")
        return True

    def is_auto_optimization_enabled(self) -> bool:
        """是否启用自动优化"""
        auto_config = self.config_service.get('auto_optimization', {})
        return auto_config.get('enabled', True)

    def get_workload_type(self) -> str:
        """获取工作负载类型"""
        auto_config = self.config_service.get('auto_optimization', {})
        return auto_config.get('workload_type', 'olap')

    def set_auto_optimization(self, enabled: bool, workload_type: str = None) -> bool:
        """设置自动优化"""
        auto_config = self.config_service.get('auto_optimization', {})
        auto_config['enabled'] = enabled
        if workload_type:
            auto_config['workload_type'] = workload_type

        self.config_service.set('auto_optimization', auto_config)
        logger.info(f"✅ 自动优化设置已更新: enabled={enabled}, workload_type={auto_config['workload_type']}")
        return True

    def get_scenario_timeout(self, scenario: str) -> float:
        """获取场景超时配置"""
        scenarios = self.config_service.get('connection_pool_scenarios', {})
        return scenarios.get(scenario, {}).get('timeout', 30.0)

    def load_adaptive_config(self) -> Dict[str, Any]:
        """加载自适应连接池配置（全局默认）"""
        config_dict = self.config_service.get('adaptive_connection_pool', {})
        if not config_dict:
            # 返回默认配置
            return {
                'enabled': True,
                'min_pool_size': 3,
                'max_pool_size': 50,
                'scale_up_usage_threshold': 0.8,
                'scale_down_usage_threshold': 0.3,
                'scale_up_overflow_threshold': 0.5,
                'metrics_window_seconds': 60,
                'cooldown_seconds': 60,
                'collection_interval': 10,
                'scale_up_factor': 1.5,
                'scale_down_factor': 0.8
            }
        return config_dict

    def load_adaptive_pool_config(self, pool_name: str) -> Dict[str, Any]:
        """加载指定连接池的自适应配置"""
        per_pool_config = self.config_service.get('adaptive_pool_per_pool', {})
        
        if pool_name in per_pool_config:
            pool_config = per_pool_config[pool_name]
            if pool_config.get('enabled', False):
                return pool_config
            else:
                return {'enabled': False}
        
        return {'enabled': False}

    def save_adaptive_config(self, config: Dict[str, Any]) -> bool:
        """保存自适应连接池配置（全局默认）"""
        self.config_service.set('adaptive_connection_pool', config)
        logger.info(f"✅ 自适应连接池配置已保存")
        return True

    def save_adaptive_pool_config(self, pool_name: str, config: Dict[str, Any]) -> bool:
        """保存指定连接池的自适应配置"""
        per_pool_config = self.config_service.get('adaptive_pool_per_pool', {})
        
        if pool_name not in per_pool_config:
            per_pool_config[pool_name] = {}
        
        per_pool_config[pool_name] = config
        self.config_service.set('adaptive_pool_per_pool', per_pool_config)
        logger.info(f"✅ 连接池 {pool_name} 的自适应配置已保存")
        return True

    def is_adaptive_pool_enabled(self, pool_name: str) -> bool:
        """检查指定连接池是否启用自适应"""
        per_pool_config = self.config_service.get('adaptive_pool_per_pool', {})
        
        if pool_name in per_pool_config:
            return per_pool_config[pool_name].get('enabled', False)
        
        return False

    def is_adaptive_enabled(self) -> bool:
        """检查全局是否启用自适应管理（向后兼容）"""
        adaptive_config = self.config_service.get('adaptive_connection_pool', {})
        return adaptive_config.get('enabled', True)
