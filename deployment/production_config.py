#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Environment Configuration
生产环境配置

本模块提供生产环境的完整配置，包括数据库配置、缓存配置、日志配置、
性能优化配置、安全配置、监控配置等。

配置特性：
1. 环境变量驱动配置
2. 多环境支持（开发、测试、生产）
3. 安全配置管理
4. 性能优化配置
5. 监控和告警配置
6. 容器化部署配置
7. 负载均衡配置
8. 备份和恢复配置
"""

import os
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class Environment(Enum):
    """环境类型枚举"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    # DuckDB配置
    duckdb_path: str = field(default_factory=lambda: os.getenv('DUCKDB_PATH', './data/factorweave.duckdb'))
    duckdb_memory_limit: str = field(default_factory=lambda: os.getenv('DUCKDB_MEMORY_LIMIT', '4GB'))
    duckdb_threads: int = field(default_factory=lambda: int(os.getenv('DUCKDB_THREADS', '4')))
    duckdb_max_memory: str = field(default_factory=lambda: os.getenv('DUCKDB_MAX_MEMORY', '8GB'))

    # 连接池配置
    connection_pool_size: int = field(default_factory=lambda: int(os.getenv('DB_POOL_SIZE', '10')))
    connection_timeout: int = field(default_factory=lambda: int(os.getenv('DB_TIMEOUT', '30')))

    # 备份配置
    backup_enabled: bool = field(default_factory=lambda: os.getenv('DB_BACKUP_ENABLED', 'true').lower() == 'true')
    backup_interval: int = field(default_factory=lambda: int(os.getenv('DB_BACKUP_INTERVAL', '3600')))  # 秒
    backup_retention: int = field(default_factory=lambda: int(os.getenv('DB_BACKUP_RETENTION', '7')))  # 天
    backup_path: str = field(default_factory=lambda: os.getenv('DB_BACKUP_PATH', './backups'))

    def get_duckdb_config(self) -> Dict[str, Any]:
        """获取DuckDB配置字典"""
        return {
            'memory_limit': self.duckdb_memory_limit,
            'threads': self.duckdb_threads,
            'max_memory': self.duckdb_max_memory,
            'enable_progress_bar': False,
            'enable_profiling': os.getenv('DUCKDB_PROFILING', 'false').lower() == 'true',
            'preserve_insertion_order': True
        }


@dataclass
class CacheConfig:
    """缓存配置"""
    # L1内存缓存
    l1_enabled: bool = field(default_factory=lambda: os.getenv('CACHE_L1_ENABLED', 'true').lower() == 'true')
    l1_strategy: str = field(default_factory=lambda: os.getenv('CACHE_L1_STRATEGY', 'adaptive'))
    l1_max_size: int = field(default_factory=lambda: int(os.getenv('CACHE_L1_MAX_SIZE', '10000')))

    # L2磁盘缓存
    l2_enabled: bool = field(default_factory=lambda: os.getenv('CACHE_L2_ENABLED', 'true').lower() == 'true')
    l2_cache_dir: str = field(default_factory=lambda: os.getenv('CACHE_L2_DIR', './cache'))
    l2_max_size_mb: int = field(default_factory=lambda: int(os.getenv('CACHE_L2_MAX_SIZE_MB', '2048')))

    # L3分布式缓存（Redis）
    l3_enabled: bool = field(default_factory=lambda: os.getenv('CACHE_L3_ENABLED', 'false').lower() == 'true')
    redis_host: str = field(default_factory=lambda: os.getenv('REDIS_HOST', 'localhost'))
    redis_port: int = field(default_factory=lambda: int(os.getenv('REDIS_PORT', '6379')))
    redis_password: Optional[str] = field(default_factory=lambda: os.getenv('REDIS_PASSWORD'))
    redis_db: int = field(default_factory=lambda: int(os.getenv('REDIS_DB', '0')))
    redis_key_prefix: str = field(default_factory=lambda: os.getenv('REDIS_KEY_PREFIX', 'factorweave:'))
    redis_default_ttl: int = field(default_factory=lambda: int(os.getenv('REDIS_DEFAULT_TTL', '3600')))

    # 缓存监控
    monitoring_enabled: bool = field(default_factory=lambda: os.getenv('CACHE_MONITORING_ENABLED', 'true').lower() == 'true')
    hit_rate_threshold: float = field(default_factory=lambda: float(os.getenv('CACHE_HIT_RATE_THRESHOLD', '0.7')))
    memory_usage_threshold: float = field(default_factory=lambda: float(os.getenv('CACHE_MEMORY_THRESHOLD', '0.9')))

    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置字典"""
        config = {
            'l1_memory': {
                'enabled': self.l1_enabled,
                'strategy': self.l1_strategy,
                'max_size': self.l1_max_size
            },
            'l2_disk': {
                'enabled': self.l2_enabled,
                'cache_dir': self.l2_cache_dir,
                'max_size_mb': self.l2_max_size_mb
            },
            'l3_distributed': {
                'enabled': self.l3_enabled
            }
        }

        if self.l3_enabled:
            redis_config = {
                'host': self.redis_host,
                'port': self.redis_port,
                'data': self.redis_db,
                'key_prefix': self.redis_key_prefix,
                'default_ttl': self.redis_default_ttl,
                'decode_responses': True,
                'socket_timeout': 5,
                'socket_connect_timeout': 5,
                'retry_on_timeout': True,
                'health_check_interval': 30
            }

            if self.redis_password:
                redis_config['password'] = self.redis_password

            config['l3_distributed']['redis'] = redis_config

        return config


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))
    format: str = field(default_factory=lambda: os.getenv('LOG_FORMAT',
                                                          '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>'))

    # 文件日志
    file_enabled: bool = field(default_factory=lambda: os.getenv('LOG_FILE_ENABLED', 'true').lower() == 'true')
    file_path: str = field(default_factory=lambda: os.getenv('LOG_FILE_PATH', './logs/factorweave.log'))
    file_rotation: str = field(default_factory=lambda: os.getenv('LOG_FILE_ROTATION', '100 MB'))
    file_retention: str = field(default_factory=lambda: os.getenv('LOG_FILE_RETENTION', '30 days'))
    file_compression: str = field(default_factory=lambda: os.getenv('LOG_FILE_COMPRESSION', 'gz'))

    # 控制台日志
    console_enabled: bool = field(default_factory=lambda: os.getenv('LOG_CONSOLE_ENABLED', 'true').lower() == 'true')

    # 结构化日志
    json_enabled: bool = field(default_factory=lambda: os.getenv('LOG_JSON_ENABLED', 'false').lower() == 'true')

    # 性能日志
    performance_enabled: bool = field(default_factory=lambda: os.getenv('LOG_PERFORMANCE_ENABLED', 'true').lower() == 'true')
    slow_query_threshold: float = field(default_factory=lambda: float(os.getenv('LOG_SLOW_QUERY_THRESHOLD', '1.0')))

    def get_loguru_config(self) -> List[Dict[str, Any]]:
        """获取Loguru配置"""
        handlers = []

        if self.console_enabled:
            console_handler = {
                "sink": "sys.stdout",
                "level": self.level,
                "format": self.format,
                "colorize": True
            }
            handlers.append(console_handler)

        if self.file_enabled:
            file_handler = {
                "sink": self.file_path,
                "level": self.level,
                "format": self.format,
                "rotation": self.file_rotation,
                "retention": self.file_retention,
                "compression": self.file_compression,
                "enqueue": True
            }
            handlers.append(file_handler)

        if self.json_enabled:
            json_handler = {
                "sink": self.file_path.replace('.log', '_json.log'),
                "level": self.level,
                "serialize": True,
                "rotation": self.file_rotation,
                "retention": self.file_retention,
                "compression": self.file_compression
            }
            handlers.append(json_handler)

        return handlers


@dataclass
class PerformanceConfig:
    """性能配置"""
    # 线程池配置
    max_workers: int = field(default_factory=lambda: int(os.getenv('MAX_WORKERS', '8')))
    thread_pool_size: int = field(default_factory=lambda: int(os.getenv('THREAD_POOL_SIZE', '16')))

    # 异步配置
    async_enabled: bool = field(default_factory=lambda: os.getenv('ASYNC_ENABLED', 'true').lower() == 'true')
    event_loop_policy: str = field(default_factory=lambda: os.getenv('EVENT_LOOP_POLICY', 'asyncio'))

    # 内存配置
    memory_limit_mb: int = field(default_factory=lambda: int(os.getenv('MEMORY_LIMIT_MB', '4096')))
    gc_threshold: int = field(default_factory=lambda: int(os.getenv('GC_THRESHOLD', '1000')))

    # 数据处理配置
    batch_size: int = field(default_factory=lambda: int(os.getenv('BATCH_SIZE', '1000')))
    chunk_size: int = field(default_factory=lambda: int(os.getenv('CHUNK_SIZE', '10000')))

    # 网络配置
    request_timeout: int = field(default_factory=lambda: int(os.getenv('REQUEST_TIMEOUT', '30')))
    connection_pool_size: int = field(default_factory=lambda: int(os.getenv('CONNECTION_POOL_SIZE', '100')))

    # 缓存预热
    cache_warmup_enabled: bool = field(default_factory=lambda: os.getenv('CACHE_WARMUP_ENABLED', 'true').lower() == 'true')
    warmup_data_size: int = field(default_factory=lambda: int(os.getenv('WARMUP_DATA_SIZE', '10000')))


@dataclass
class SecurityConfig:
    """安全配置"""
    # API安全
    api_key_required: bool = field(default_factory=lambda: os.getenv('API_KEY_REQUIRED', 'false').lower() == 'true')
    api_key: Optional[str] = field(default_factory=lambda: os.getenv('API_KEY'))

    # 数据加密
    encryption_enabled: bool = field(default_factory=lambda: os.getenv('ENCRYPTION_ENABLED', 'false').lower() == 'true')
    encryption_key: Optional[str] = field(default_factory=lambda: os.getenv('ENCRYPTION_KEY'))

    # 访问控制
    allowed_hosts: List[str] = field(default_factory=lambda:
                                     os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(','))
    cors_enabled: bool = field(default_factory=lambda: os.getenv('CORS_ENABLED', 'true').lower() == 'true')
    cors_origins: List[str] = field(default_factory=lambda:
                                    os.getenv('CORS_ORIGINS', '*').split(','))

    # 速率限制
    rate_limit_enabled: bool = field(default_factory=lambda: os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true')
    rate_limit_requests: int = field(default_factory=lambda: int(os.getenv('RATE_LIMIT_REQUESTS', '1000')))
    rate_limit_window: int = field(default_factory=lambda: int(os.getenv('RATE_LIMIT_WINDOW', '3600')))

    # SSL/TLS
    ssl_enabled: bool = field(default_factory=lambda: os.getenv('SSL_ENABLED', 'false').lower() == 'true')
    ssl_cert_path: Optional[str] = field(default_factory=lambda: os.getenv('SSL_CERT_PATH'))
    ssl_key_path: Optional[str] = field(default_factory=lambda: os.getenv('SSL_KEY_PATH'))


@dataclass
class MonitoringConfig:
    """监控配置"""
    # 健康检查
    health_check_enabled: bool = field(default_factory=lambda: os.getenv('HEALTH_CHECK_ENABLED', 'true').lower() == 'true')
    health_check_interval: int = field(default_factory=lambda: int(os.getenv('HEALTH_CHECK_INTERVAL', '60')))

    # 性能监控
    metrics_enabled: bool = field(default_factory=lambda: os.getenv('METRICS_ENABLED', 'true').lower() == 'true')
    metrics_port: int = field(default_factory=lambda: int(os.getenv('METRICS_PORT', '9090')))

    # Prometheus集成
    prometheus_enabled: bool = field(default_factory=lambda: os.getenv('PROMETHEUS_ENABLED', 'false').lower() == 'true')
    prometheus_endpoint: str = field(default_factory=lambda: os.getenv('PROMETHEUS_ENDPOINT', '/metrics'))

    # 告警配置
    alerting_enabled: bool = field(default_factory=lambda: os.getenv('ALERTING_ENABLED', 'true').lower() == 'true')
    alert_webhook_url: Optional[str] = field(default_factory=lambda: os.getenv('ALERT_WEBHOOK_URL'))

    # 系统监控阈值
    cpu_threshold: float = field(default_factory=lambda: float(os.getenv('CPU_THRESHOLD', '80.0')))
    memory_threshold: float = field(default_factory=lambda: float(os.getenv('MEMORY_THRESHOLD', '85.0')))
    disk_threshold: float = field(default_factory=lambda: float(os.getenv('DISK_THRESHOLD', '90.0')))

    # 业务监控阈值
    error_rate_threshold: float = field(default_factory=lambda: float(os.getenv('ERROR_RATE_THRESHOLD', '5.0')))
    response_time_threshold: float = field(default_factory=lambda: float(os.getenv('RESPONSE_TIME_THRESHOLD', '2.0')))


@dataclass
class UIConfig:
    """UI配置"""
    # 服务器配置
    host: str = field(default_factory=lambda: os.getenv('UI_HOST', '0.0.0.0'))
    port: int = field(default_factory=lambda: int(os.getenv('UI_PORT', '8080')))
    debug: bool = field(default_factory=lambda: os.getenv('UI_DEBUG', 'false').lower() == 'true')

    # 主题配置
    theme: str = field(default_factory=lambda: os.getenv('UI_THEME', 'dark'))
    language: str = field(default_factory=lambda: os.getenv('UI_LANGUAGE', 'zh_CN'))

    # 性能配置
    enable_compression: bool = field(default_factory=lambda: os.getenv('UI_COMPRESSION', 'true').lower() == 'true')
    cache_static_files: bool = field(default_factory=lambda: os.getenv('UI_CACHE_STATIC', 'true').lower() == 'true')

    # 功能开关
    enable_realtime: bool = field(default_factory=lambda: os.getenv('UI_ENABLE_REALTIME', 'true').lower() == 'true')
    enable_advanced_charts: bool = field(default_factory=lambda: os.getenv('UI_ENABLE_ADVANCED_CHARTS', 'true').lower() == 'true')
    enable_data_export: bool = field(default_factory=lambda: os.getenv('UI_ENABLE_DATA_EXPORT', 'true').lower() == 'true')


@dataclass
class PluginConfig:
    """插件配置"""
    # 插件目录
    plugin_dirs: List[str] = field(default_factory=lambda:
                                   os.getenv('PLUGIN_DIRS', './plugins').split(','))

    # 插件加载
    auto_load: bool = field(default_factory=lambda: os.getenv('PLUGIN_AUTO_LOAD', 'true').lower() == 'true')
    load_timeout: int = field(default_factory=lambda: int(os.getenv('PLUGIN_LOAD_TIMEOUT', '30')))

    # 插件安全
    sandbox_enabled: bool = field(default_factory=lambda: os.getenv('PLUGIN_SANDBOX', 'true').lower() == 'true')
    allowed_modules: List[str] = field(default_factory=lambda:
                                       os.getenv('PLUGIN_ALLOWED_MODULES', 'pandas,numpy,requests').split(','))

    # 插件性能
    max_memory_mb: int = field(default_factory=lambda: int(os.getenv('PLUGIN_MAX_MEMORY_MB', '512')))
    max_execution_time: int = field(default_factory=lambda: int(os.getenv('PLUGIN_MAX_EXECUTION_TIME', '60')))


class ProductionConfig:
    """生产环境配置管理器"""

    def __init__(self, environment: Environment = Environment.PRODUCTION):
        self.environment = environment
        self.database = DatabaseConfig()
        self.cache = CacheConfig()
        self.logging = LoggingConfig()
        self.performance = PerformanceConfig()
        self.security = SecurityConfig()
        self.monitoring = MonitoringConfig()
        self.ui = UIConfig()
        self.plugin = PluginConfig()

        # 根据环境调整配置
        self._adjust_for_environment()

        logger.info(f"生产环境配置初始化完成，环境: {environment.value}")

    def _adjust_for_environment(self):
        """根据环境调整配置"""
        if self.environment == Environment.DEVELOPMENT:
            # 开发环境配置调整
            self.logging.level = 'DEBUG'
            self.ui.debug = True
            self.security.api_key_required = False
            self.cache.l3_enabled = False
            self.monitoring.prometheus_enabled = False
            self.monitoring.alerting_enabled = False

        elif self.environment == Environment.TESTING:
            # 测试环境配置调整
            self.logging.level = 'DEBUG'
            self.database.duckdb_path = ':memory:'
            self.cache.l2_enabled = False
            self.cache.l3_enabled = False
            self.monitoring.alerting_enabled = False

        elif self.environment == Environment.STAGING:
            # 预发布环境配置调整
            self.logging.level = 'INFO'
            self.security.api_key_required = True
            self.monitoring.alerting_enabled = True

        elif self.environment == Environment.PRODUCTION:
            # 生产环境配置调整
            self.logging.level = 'WARNING'
            self.ui.debug = False
            self.security.api_key_required = True
            self.security.encryption_enabled = True
            self.monitoring.prometheus_enabled = True
            self.monitoring.alerting_enabled = True

    def get_complete_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return {
            'environment': self.environment.value,
            'database': self.database.__dict__,
            'cache': self.cache.get_cache_config(),
            'logging': {
                'level': self.logging.level,
                'handlers': self.logging.get_loguru_config(),
                'performance_enabled': self.logging.performance_enabled,
                'slow_query_threshold': self.logging.slow_query_threshold
            },
            'performance': self.performance.__dict__,
            'security': self.security.__dict__,
            'monitoring': self.monitoring.__dict__,
            'ui': self.ui.__dict__,
            'plugin': self.plugin.__dict__
        }

    def validate_config(self) -> List[str]:
        """验证配置"""
        errors = []

        # 验证数据库配置
        if not self.database.duckdb_path:
            errors.append("数据库路径不能为空")

        # 验证缓存配置
        if self.cache.l3_enabled and not self.cache.redis_host:
            errors.append("启用Redis缓存时必须配置Redis主机")

        # 验证安全配置
        if self.security.api_key_required and not self.security.api_key:
            errors.append("启用API密钥验证时必须配置API密钥")

        if self.security.encryption_enabled and not self.security.encryption_key:
            errors.append("启用加密时必须配置加密密钥")

        if self.security.ssl_enabled and (not self.security.ssl_cert_path or not self.security.ssl_key_path):
            errors.append("启用SSL时必须配置证书和密钥路径")

        # 验证监控配置
        if self.monitoring.alerting_enabled and not self.monitoring.alert_webhook_url:
            errors.append("启用告警时必须配置Webhook URL")

        # 验证目录存在性
        directories_to_check = [
            self.cache.l2_cache_dir,
            self.database.backup_path,
            Path(self.logging.file_path).parent
        ]

        for directory in directories_to_check:
            dir_path = Path(directory)
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"无法创建目录 {directory}: {e}")

        return errors

    def save_config(self, file_path: str):
        """保存配置到文件"""
        config_data = self.get_complete_config()

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"配置已保存到: {file_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            raise

    @classmethod
    def load_config(cls, file_path: str) -> 'ProductionConfig':
        """从文件加载配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            environment = Environment(config_data.get('environment', 'production'))
            config = cls(environment)

            # 更新配置（这里简化处理，实际可能需要更复杂的合并逻辑）
            logger.info(f"配置已从文件加载: {file_path}")
            return config

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise

    def setup_logging(self):
        """设置日志配置"""
        try:
            from loguru import logger as loguru_logger

            print("DEBUG: 开始设置日志配置...")

            # 移除默认处理器
            print("DEBUG: 移除默认处理器...")
            loguru_logger.remove()
            print("DEBUG: 处理器移除完成")

            # 获取日志配置
            loguru_config = self.logging.get_loguru_config()
            print(f"DEBUG: 获取到 {len(loguru_config)} 个日志处理器配置")

            # 添加配置的处理器
            for i, handler_config in enumerate(loguru_config):
                print(f"DEBUG: 添加处理器 {i}: {handler_config.get('sink', 'unknown')}")
                loguru_logger.add(**handler_config)
                print(f"DEBUG: 处理器 {i} 添加完成")

            print("DEBUG: 日志配置完成")

        except Exception as e:
            print(f"ERROR: 设置日志配置失败: {e}")
            import traceback
            traceback.print_exc()

            # 如果没有loguru，使用标准logging
            import logging

            logging.basicConfig(
                level=getattr(logging, self.logging.level),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

            if self.logging.file_enabled:
                file_handler = logging.FileHandler(self.logging.file_path)
                file_handler.setLevel(getattr(logging, self.logging.level))
                logging.getLogger().addHandler(file_handler)

    def get_environment_info(self) -> Dict[str, Any]:
        """获取环境信息"""
        import platform
        import sys

        return {
            'environment': self.environment.value,
            'python_version': sys.version,
            'platform': platform.platform(),
            'architecture': platform.architecture(),
            'processor': platform.processor(),
            'hostname': platform.node(),
            'config_validation': len(self.validate_config()) == 0
        }


def create_production_config(environment: str = None) -> ProductionConfig:
    """创建生产环境配置"""
    if environment:
        env = Environment(environment.lower())
    else:
        env_str = os.getenv('ENVIRONMENT', 'production').lower()
        env = Environment(env_str)

    return ProductionConfig(env)


def main():
    """主函数 - 用于配置验证和生成"""
    import argparse

    parser = argparse.ArgumentParser(description='FactorWeave-Quant 生产环境配置管理')
    parser.add_argument('--env', choices=['development', 'testing', 'staging', 'production'],
                        default='production', help='环境类型')
    parser.add_argument('--validate', action='store_true', help='验证配置')
    parser.add_argument('--save', type=str, help='保存配置到文件')
    parser.add_argument('--load', type=str, help='从文件加载配置')
    parser.add_argument('--info', action='store_true', help='显示环境信息')

    args = parser.parse_args()

    try:
        if args.load:
            config = ProductionConfig.load_config(args.load)
        else:
            config = create_production_config(args.env)

        if args.validate:
            errors = config.validate_config()
            if errors:
                print("配置验证失败:")
                for error in errors:
                    print(f"  - {error}")
                return 1
            else:
                print("配置验证通过")

        if args.save:
            config.save_config(args.save)
            print(f"配置已保存到: {args.save}")

        if args.info:
            info = config.get_environment_info()
            print("环境信息:")
            for key, value in info.items():
                print(f"  {key}: {value}")

        return 0

    except Exception as e:
        print(f"配置管理失败: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
