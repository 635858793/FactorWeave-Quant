#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FactorWeave-Quant 迁移前系统健康检查

该模块提供传统数据源迁移前的全面系统健康检查功能，包括：
- 核心组件状态检查
- 数据源连接验证
- 系统资源评估
- 依赖项完整性检查
- 迁移前置条件验证

作者: FactorWeave-Quant Migration Team
日期: 2025-09-20
"""

import os
import sys
import json
import time
import psutil
import threading
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import importlib
import subprocess

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from core.loguru_interface import get_logger
    from core.plugin_center import PluginCenter
    from core.tet_router_engine import TETRouterEngine
    from core.services.unified_data_manager import UnifiedDataManager, get_unified_data_manager
    from core.services.uni_plugin_data_manager import UniPluginDataManager
    from core.data_standardization_engine import DataStandardizationEngine
    from core.asset_database_manager import AssetSeparatedDatabaseManager
    from core.enums import HealthStatus
except ImportError as e:
    # 备用日志记录
    import logging
    logging.basicConfig(level=logging.INFO)

    def get_logger(name):
        return logging.getLogger(name)

    # 模拟类，避免导入错误
    class MockComponent:
        def __init__t__(self):
            pass
            pass

class CheckCategory(Enum):
    """检查类别枚举"""
    SYSTEM_RESOURCES = "system_resources"
    CORE_COMPONENTS = "core_components"
    DATA_SOURCES = "data_sources"
    DATABASE = "database"
    NETWORK = "network"
    DEPENDENCIES = "dependencies"
    CONFIGURATION = "configuration"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    check_id: str
    name: str
    category: CheckCategory
    status: HealthStatus
    message: str
    details: Dict[str, Any] = None
    recommendations: List[str] = None
    timestamp: datetime.datetime = None
    duration: float = 0.0

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.recommendations is None:
            self.recommendations = []
        if self.timestamp is None:
            self.timestamp = datetime.datetime.now()


class PreMigrationHealthChecker:
    """迁移前健康检查器"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化健康检查器

        Args:
            config: 检查配置
        """
        self.logger = get_logger("PreMigrationHealthChecker")

        # 默认配置
        self.config = {
            "min_free_memory_gb": 2.0,
            "min_free_disk_gb": 10.0,
            "max_cpu_usage_percent": 80.0,
            "network_timeout_seconds": 10,
            "database_timeout_seconds": 30,
            "skip_network_checks": False,
            "skip_performance_checks": False,
            "required_python_version": "3.8",
            "required_packages": [
                "pandas", "numpy", "loguru", "psutil",
                "requests", "sqlite3", "duckdb"
            ]
        }

        if config:
            self.config.update(config)

        # 检查结果存储
        self.check_results: List[HealthCheckResult] = []
        self.overall_status = HealthStatus.UNKNOWN

        # 组件实例
        self.components = {}

        self.logger.info("迁移前健康检查器初始化完成")

    def run_all_checks(self) -> Tuple[HealthStatus, List[HealthCheckResult]]:
        """运行所有健康检查"""
        self.logger.info("开始执行迁移前健康检查...")
        start_time = time.time()

        self.check_results = []

        # 按类别执行检查
        check_methods = [
            self._check_system_resources,
            self._check_python_environment,
            self._check_required_packages,
            self._check_core_components,
            self._check_data_sources,
            self._check_database_connections,
            self._check_network_connectivity,
            self._check_file_permissions,
            self._check_configuration_validity,
            self._check_migration_prerequisites
        ]

        for check_method in check_methods:
            try:
                results = check_method()
                if isinstance(results, list):
                    self.check_results.extend(results)
                else:
                    self.check_results.append(results)
            except Exception as e:
                error_result = HealthCheckResult(
                    check_id=f"error_{check_method.__name__}",
                    name=f"检查方法错误: {check_method.__name__}",
                    category=CheckCategory.SYSTEM_RESOURCES,
                    status=HealthStatus.CRITICAL,
                    message=f"执行检查时发生错误: {str(e)}",
                    details={"exception": str(e)}
                )
                self.check_results.append(error_result)
                self.logger.error(f"健康检查方法 {check_method.__name__} 执行失败: {e}")

        # 计算总体状态
        self.overall_status = self._calculate_overall_status()

        duration = time.time() - start_time
        self.logger.info(f"健康检查完成，总体状态: {self.overall_status.value}，耗时: {duration:.2f}秒")

        return self.overall_status, self.check_results

    def _check_system_resources(self) -> List[HealthCheckResult]:
        """检查系统资源"""
        results = []

        # 内存检查
        try:
            memory = psutil.virtual_memory()
            free_memory_gb = memory.available / (1024**3)

            if free_memory_gb >= self.config["min_free_memory_gb"]:
                status = HealthStatus.HEALTHY
                message = f"可用内存充足: {free_memory_gb:.2f} GB"
            elif free_memory_gb >= self.config["min_free_memory_gb"] * 0.5:
                status = HealthStatus.WARNING
                message = f"可用内存较少: {free_memory_gb:.2f} GB"
            else:
                status = HealthStatus.CRITICAL
                message = f"可用内存不足: {free_memory_gb:.2f} GB"

            results.append(HealthCheckResult(
                check_id="memory_check",
                name="内存检查",
                category=CheckCategory.SYSTEM_RESOURCES,
                status=status,
                message=message,
                details={
                    "total_gb": memory.total / (1024**3),
                    "available_gb": free_memory_gb,
                    "usage_percent": memory.percent
                },
                recommendations=["释放内存空间"] if status != HealthStatus.HEALTHY else []
            ))
        except Exception as e:
            results.append(HealthCheckResult(
                check_id="memory_check",
                name="内存检查",
                category=CheckCategory.SYSTEM_RESOURCES,
                status=HealthStatus.UNKNOWN,
                message=f"无法获取内存信息: {e}"
            ))

        # 磁盘空间检查
        try:
            disk = psutil.disk_usage(str(project_root))
            free_disk_gb = disk.free / (1024**3)

            if free_disk_gb >= self.config["min_free_disk_gb"]:
                status = HealthStatus.HEALTHY
                message = f"磁盘空间充足: {free_disk_gb:.2f} GB"
            elif free_disk_gb >= self.config["min_free_disk_gb"] * 0.5:
                status = HealthStatus.WARNING
                message = f"磁盘空间较少: {free_disk_gb:.2f} GB"
            else:
                status = HealthStatus.CRITICAL
                message = f"磁盘空间不足: {free_disk_gb:.2f} GB"

            results.append(HealthCheckResult(
                check_id="disk_check",
                name="磁盘空间检查",
                category=CheckCategory.SYSTEM_RESOURCES,
                status=status,
                message=message,
                details={
                    "total_gb": disk.total / (1024**3),
                    "free_gb": free_disk_gb,
                    "usage_percent": (disk.used / disk.total) * 100
                },
                recommendations=["清理磁盘空间"] if status != HealthStatus.HEALTHY else []
            ))
        except Exception as e:
            results.append(HealthCheckResult(
                check_id="disk_check",
                name="磁盘空间检查",
                category=CheckCategory.SYSTEM_RESOURCES,
                status=HealthStatus.UNKNOWN,
                message=f"无法获取磁盘信息: {e}"
            ))

        # CPU使用率检查
        if not self.config.get("skip_performance_checks", False):
            try:
                cpu_percent = psutil.cpu_percent(interval=1)

                if cpu_percent <= self.config["max_cpu_usage_percent"]:
                    status = HealthStatus.HEALTHY
                    message = f"CPU使用率正常: {cpu_percent:.1f}%"
                elif cpu_percent <= self.config["max_cpu_usage_percent"] * 1.2:
                    status = HealthStatus.WARNING
                    message = f"CPU使用率较高: {cpu_percent:.1f}%"
                else:
                    status = HealthStatus.CRITICAL
                    message = f"CPU使用率过高: {cpu_percent:.1f}%"

                results.append(HealthCheckResult(
                    check_id="cpu_check",
                    name="CPU使用率检查",
                    category=CheckCategory.SYSTEM_RESOURCES,
                    status=status,
                    message=message,
                    details={
                        "cpu_percent": cpu_percent,
                        "cpu_count": psutil.cpu_count()
                    },
                    recommendations=["等待CPU使用率降低后再进行迁移"] if status != HealthStatus.HEALTHY else []
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    check_id="cpu_check",
                    name="CPU使用率检查",
                    category=CheckCategory.SYSTEM_RESOURCES,
                    status=HealthStatus.UNKNOWN,
                    message=f"无法获取CPU信息: {e}"
                ))

        return results

    def _check_python_environment(self) -> HealthCheckResult:
        """检查Python环境"""
        try:
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            required_version = self.config["required_python_version"]

            # 简单版本比较
            current_parts = [int(x) for x in python_version.split('.')]
            required_parts = [int(x) for x in required_version.split('.')]

            version_ok = current_parts >= required_parts

            if version_ok:
                status = HealthStatus.HEALTHY
                message = f"Python版本符合要求: {python_version}"
            else:
                status = HealthStatus.CRITICAL
                message = f"Python版本过低: {python_version}，要求: {required_version}"

            return HealthCheckResult(
                check_id="python_version",
                name="Python版本检查",
                category=CheckCategory.DEPENDENCIES,
                status=status,
                message=message,
                details={
                    "current_version": python_version,
                    "required_version": required_version,
                    "executable": sys.executable
                },
                recommendations=[f"升级Python到{required_version}或更高版本"] if not version_ok else []
            )
        except Exception as e:
            return HealthCheckResult(
                check_id="python_version",
                name="Python版本检查",
                category=CheckCategory.DEPENDENCIES,
                status=HealthStatus.UNKNOWN,
                message=f"无法检查Python版本: {e}"
            )

    def _check_required_packages(self) -> List[HealthCheckResult]:
        """检查必需的Python包"""
        results = []

        for package in self.config["required_packages"]:
            try:
                importlib.import_module(package)
                results.append(HealthCheckResult(
                    check_id=f"package_{package}",
                    name=f"包检查: {package}",
                    category=CheckCategory.DEPENDENCIES,
                    status=HealthStatus.HEALTHY,
                    message=f"包 {package} 已安装"
                ))
            except ImportError:
                results.append(HealthCheckResult(
                    check_id=f"package_{package}",
                    name=f"包检查: {package}",
                    category=CheckCategory.DEPENDENCIES,
                    status=HealthStatus.CRITICAL,
                    message=f"缺少必需的包: {package}",
                    recommendations=[f"安装包: pip install {package}"]
                ))

        return results

    def _check_core_components(self) -> List[HealthCheckResult]:
        """检查核心组件"""
        results = []

        # 检查核心组件类
        components_to_check = [
            ("PluginCenter", "插件中心"),
            ("TETRouterEngine", "TET路由引擎"),
            ("UnifiedDataManager", "统一数据管理器"),
            ("UniPluginDataManager", "插件数据管理器"),
            ("DataQualityRiskManager", "数据质量风险管理器"),
            ("DataStandardizationEngine", "数据标准化引擎"),
            ("AssetSeparatedDatabaseManager", "资产分离数据库管理器")
        ]

        for component_name, display_name in components_to_check:
            try:
                # 尝试实例化组件
                if component_name == "PluginCenter":
                    component = PluginCenter()
                elif component_name == "TETRouterEngine":
                    component = TETRouterEngine()
                elif component_name == "UnifiedDataManager":
                    component = get_unified_data_manager()
                elif component_name == "UniPluginDataManager":
                    # TODO: 使用依赖注入获取UniPluginDataManager实例

                    component = None  # 需要从服务容器获取
                elif component_name == "DataQualityRiskManager":
                    component = None
                elif component_name == "DataStandardizationEngine":
                    component = DataStandardizationEngine()
                elif component_name == "AssetSeparatedDatabaseManager":
                    component = AssetSeparatedDatabaseManager()
                else:
                    component = None

                if component is not None:
                    self.components[component_name] = component

                    results.append(HealthCheckResult(
                        check_id=f"component_{component_name.lower()}",
                        name=f"{display_name}检查",
                        category=CheckCategory.CORE_COMPONENTS,
                        status=HealthStatus.HEALTHY,
                        message=f"{display_name}初始化成功"
                    ))
                else:
                    results.append(HealthCheckResult(
                        check_id=f"component_{component_name.lower()}",
                        name=f"{display_name}检查",
                        category=CheckCategory.CORE_COMPONENTS,
                        status=HealthStatus.WARNING,
                        message=f"{display_name}无法实例化"
                    ))

            except Exception as e:
                results.append(HealthCheckResult(
                    check_id=f"component_{component_name.lower()}",
                    name=f"{display_name}检查",
                    category=CheckCategory.CORE_COMPONENTS,
                    status=HealthStatus.CRITICAL,
                    message=f"{display_name}初始化失败: {str(e)}",
                    details={"exception": str(e)},
                    recommendations=[f"检查{display_name}的依赖和配置"]
                ))

        return results

    def _check_data_sources(self) -> List[HealthCheckResult]:
        """检查数据源状态"""
        results = []

        # 检查传统数据源
        traditional_sources = [
            ("eastmoney", "东方财富"),
            ("sina", "新浪财经"),
            ("tonghuashun", "同花顺")
        ]

        for source_id, source_name in traditional_sources:
            try:
                # 尝试导入数据源模块
                module_name = f"core.{source_id}_source"
                source_module = importlib.import_module(module_name)

                # 检查数据源类是否存在
                class_name = f"{source_id.capitalize()}Source"
                if hasattr(source_module, class_name):
                    source_class = getattr(source_module, class_name)

                    # 尝试实例化
                    source_instance = source_class()

                    # 测试连接（如果有connect方法）
                    if hasattr(source_instance, 'connect'):
                        connected = source_instance.connect()
                        if connected:
                            status = HealthStatus.HEALTHY
                            message = f"{source_name}数据源连接正常"
                        else:
                            status = HealthStatus.WARNING
                            message = f"{source_name}数据源连接失败"
                    else:
                        status = HealthStatus.HEALTHY
                        message = f"{source_name}数据源类可用"
                else:
                    status = HealthStatus.CRITICAL
                    message = f"{source_name}数据源类不存在"

                results.append(HealthCheckResult(
                    check_id=f"datasource_{source_id}",
                    name=f"{source_name}数据源检查",
                    category=CheckCategory.DATA_SOURCES,
                    status=status,
                    message=message
                ))

            except ImportError as e:
                results.append(HealthCheckResult(
                    check_id=f"datasource_{source_id}",
                    name=f"{source_name}数据源检查",
                    category=CheckCategory.DATA_SOURCES,
                    status=HealthStatus.CRITICAL,
                    message=f"{source_name}数据源模块导入失败: {str(e)}",
                    recommendations=[f"检查{source_name}数据源模块是否存在"]
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    check_id=f"datasource_{source_id}",
                    name=f"{source_name}数据源检查",
                    category=CheckCategory.DATA_SOURCES,
                    status=HealthStatus.WARNING,
                    message=f"{source_name}数据源检查异常: {str(e)}"
                ))

        return results

    def _check_database_connections(self) -> List[HealthCheckResult]:
        """检查数据库连接"""
        results = []

        # 检查SQLite数据库
        sqlite_files = list(project_root.glob("**/*.db")) + list(project_root.glob("**/*.sqlite"))

        for db_file in sqlite_files[:5]:  # 只检查前5个数据库文件
            try:
                import sqlite3
                conn = sqlite3.connect(str(db_file), timeout=self.config["database_timeout_seconds"])
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                conn.close()

                results.append(HealthCheckResult(
                    check_id=f"sqlite_{db_file.stem}",
                    name=f"SQLite数据库检查: {db_file.name}",
                    category=CheckCategory.DATABASE,
                    status=HealthStatus.HEALTHY,
                    message=f"SQLite数据库 {db_file.name} 连接正常"
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    check_id=f"sqlite_{db_file.stem}",
                    name=f"SQLite数据库检查: {db_file.name}",
                    category=CheckCategory.DATABASE,
                    status=HealthStatus.WARNING,
                    message=f"SQLite数据库 {db_file.name} 连接失败: {str(e)}"
                ))

        # 检查DuckDB数据库
        try:
            import duckdb
            duckdb_files = list(project_root.glob("**/*.duckdb"))

            for db_file in duckdb_files[:3]:  # 只检查前3个DuckDB文件
                try:
                    conn = duckdb.connect(str(db_file))
                    conn.execute("SELECT 1")
                    conn.close()

                    results.append(HealthCheckResult(
                        check_id=f"duckdb_{db_file.stem}",
                        name=f"DuckDB数据库检查: {db_file.name}",
                        category=CheckCategory.DATABASE,
                        status=HealthStatus.HEALTHY,
                        message=f"DuckDB数据库 {db_file.name} 连接正常"
                    ))
                except Exception as e:
                    results.append(HealthCheckResult(
                        check_id=f"duckdb_{db_file.stem}",
                        name=f"DuckDB数据库检查: {db_file.name}",
                        category=CheckCategory.DATABASE,
                        status=HealthStatus.WARNING,
                        message=f"DuckDB数据库 {db_file.name} 连接失败: {str(e)}"
                    ))
        except ImportError:
            results.append(HealthCheckResult(
                check_id="duckdb_import",
                name="DuckDB模块检查",
                category=CheckCategory.DATABASE,
                status=HealthStatus.CRITICAL,
                message="DuckDB模块未安装",
                recommendations=["安装DuckDB: pip install duckdb"]
            ))

        return results

    def _check_network_connectivity(self) -> List[HealthCheckResult]:
        """检查网络连接"""
        results = []

        if self.config.get("skip_network_checks", False):
            results.append(HealthCheckResult(
                check_id="network_skip",
                name="网络检查",
                category=CheckCategory.NETWORK,
                status=HealthStatus.HEALTHY,
                message="网络检查已跳过"
            ))
            return results

        # 测试网络连接
        test_urls = [
            ("http://www.baidu.com", "百度"),
            ("https://finance.sina.com.cn", "新浪财经"),
            ("http://quote.eastmoney.com", "东方财富")
        ]

        for url, name in test_urls:
            try:
                import requests
                response = requests.get(url, timeout=self.config["network_timeout_seconds"])

                if response.status_code == 200:
                    status = HealthStatus.HEALTHY
                    message = f"{name}网络连接正常"
                else:
                    status = HealthStatus.WARNING
                    message = f"{name}网络连接异常: HTTP {response.status_code}"

                results.append(HealthCheckResult(
                    check_id=f"network_{name.lower()}",
                    name=f"{name}网络检查",
                    category=CheckCategory.NETWORK,
                    status=status,
                    message=message,
                    details={"url": url, "status_code": response.status_code}
                ))

            except Exception as e:
                results.append(HealthCheckResult(
                    check_id=f"network_{name.lower()}",
                    name=f"{name}网络检查",
                    category=CheckCategory.NETWORK,
                    status=HealthStatus.WARNING,
                    message=f"{name}网络连接失败: {str(e)}",
                    recommendations=["检查网络连接和防火墙设置"]
                ))

        return results

    def _check_file_permissions(self) -> List[HealthCheckResult]:
        """检查文件权限"""
        results = []

        # 检查关键目录的读写权限
        critical_dirs = [
            project_root / "core",
            project_root / "config",
            project_root / "logs",
            project_root / "db",
            project_root / "backups"
        ]

        for dir_path in critical_dirs:
            if dir_path.exists():
                try:
                    # 测试读权限
                    list(dir_path.iterdir())

                    # 测试写权限
                    test_file = dir_path / ".permission_test"
                    test_file.write_text("test")
                    test_file.unlink()

                    results.append(HealthCheckResult(
                        check_id=f"permission_{dir_path.name}",
                        name=f"目录权限检查: {dir_path.name}",
                        category=CheckCategory.SYSTEM_RESOURCES,
                        status=HealthStatus.HEALTHY,
                        message=f"目录 {dir_path.name} 权限正常"
                    ))
                except Exception as e:
                    results.append(HealthCheckResult(
                        check_id=f"permission_{dir_path.name}",
                        name=f"目录权限检查: {dir_path.name}",
                        category=CheckCategory.SYSTEM_RESOURCES,
                        status=HealthStatus.CRITICAL,
                        message=f"目录 {dir_path.name} 权限不足: {str(e)}",
                        recommendations=[f"检查目录 {dir_path} 的读写权限"]
                    ))
            else:
                results.append(HealthCheckResult(
                    check_id=f"permission_{dir_path.name}",
                    name=f"目录权限检查: {dir_path.name}",
                    category=CheckCategory.SYSTEM_RESOURCES,
                    status=HealthStatus.WARNING,
                    message=f"目录 {dir_path.name} 不存在"
                ))

        return results

    def _check_configuration_validity(self) -> List[HealthCheckResult]:
        """检查配置有效性"""
        results = []

        # 检查配置文件
        config_files = [
            project_root / "config" / "config.json",
            project_root / "config" / "app_config.json",
            project_root / "pytest.ini"
        ]

        for config_file in config_files:
            if config_file.exists():
                try:
                    if config_file.suffix == '.json':
                        with open(config_file, 'r', encoding='utf-8') as f:
                            json.load(f)

                    results.append(HealthCheckResult(
                        check_id=f"config_{config_file.stem}",
                        name=f"配置文件检查: {config_file.name}",
                        category=CheckCategory.CONFIGURATION,
                        status=HealthStatus.HEALTHY,
                        message=f"配置文件 {config_file.name} 格式正确"
                    ))
                except Exception as e:
                    results.append(HealthCheckResult(
                        check_id=f"config_{config_file.stem}",
                        name=f"配置文件检查: {config_file.name}",
                        category=CheckCategory.CONFIGURATION,
                        status=HealthStatus.CRITICAL,
                        message=f"配置文件 {config_file.name} 格式错误: {str(e)}",
                        recommendations=[f"修复配置文件 {config_file.name} 的格式错误"]
                    ))

        return results

    def _check_migration_prerequisites(self) -> List[HealthCheckResult]:
        """检查迁移前置条件"""
        results = []

        # 检查是否有正在运行的迁移
        migration_lock_file = project_root / "migration.lock"
        if migration_lock_file.exists():
            results.append(HealthCheckResult(
                check_id="migration_lock",
                name="迁移锁检查",
                category=CheckCategory.CONFIGURATION,
                status=HealthStatus.CRITICAL,
                message="检测到迁移锁文件，可能有正在进行的迁移",
                recommendations=["等待当前迁移完成或删除锁文件"]
            ))
        else:
            results.append(HealthCheckResult(
                check_id="migration_lock",
                name="迁移锁检查",
                category=CheckCategory.CONFIGURATION,
                status=HealthStatus.HEALTHY,
                message="没有检测到迁移锁文件"
            ))

        # 检查备份目录
        backup_dir = project_root / "backups"
        if backup_dir.exists():
            backup_count = len(list(backup_dir.glob("*")))
            results.append(HealthCheckResult(
                check_id="backup_dir",
                name="备份目录检查",
                category=CheckCategory.CONFIGURATION,
                status=HealthStatus.HEALTHY,
                message=f"备份目录存在，包含 {backup_count} 个备份",
                details={"backup_count": backup_count}
            ))
        else:
            results.append(HealthCheckResult(
                check_id="backup_dir",
                name="备份目录检查",
                category=CheckCategory.CONFIGURATION,
                status=HealthStatus.WARNING,
                message="备份目录不存在",
                recommendations=["创建备份目录"]
            ))

        return results

    def _calculate_overall_status(self) -> HealthStatus:
        """计算总体健康状态"""
        if not self.check_results:
            return HealthStatus.UNKNOWN

        # 统计各状态数量
        status_counts = {status: 0 for status in HealthStatus}
        for result in self.check_results:
            status_counts[result.status] += 1

        # 决策逻辑
        if status_counts[HealthStatus.CRITICAL] > 0:
            return HealthStatus.CRITICAL
        elif status_counts[HealthStatus.WARNING] > status_counts[HealthStatus.HEALTHY] / 2:
            return HealthStatus.WARNING
        elif status_counts[HealthStatus.HEALTHY] > 0:
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN

    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康检查摘要"""
        if not self.check_results:
            return {"status": "no_checks_run"}

        # 按类别统计
        category_stats = {}
        for category in CheckCategory:
            category_results = [r for r in self.check_results if r.category == category]
            if category_results:
                status_counts = {status: 0 for status in HealthStatus}
                for result in category_results:
                    status_counts[result.status] += 1

                category_stats[category.value] = {
                    "total": len(category_results),
                    "healthy": status_counts[HealthStatus.HEALTHY],
                    "warning": status_counts[HealthStatus.WARNING],
                    "critical": status_counts[HealthStatus.CRITICAL],
                    "unknown": status_counts[HealthStatus.UNKNOWN]
                }

        # 总体统计
        total_stats = {status: 0 for status in HealthStatus}
        for result in self.check_results:
            total_stats[result.status] += 1

        # 关键问题
        critical_issues = [r for r in self.check_results if r.status == HealthStatus.CRITICAL]
        warning_issues = [r for r in self.check_results if r.status == HealthStatus.WARNING]

        return {
            "overall_status": self.overall_status.value,
            "total_checks": len(self.check_results),
            "summary": {
                "healthy": total_stats[HealthStatus.HEALTHY],
                "warning": total_stats[HealthStatus.WARNING],
                "critical": total_stats[HealthStatus.CRITICAL],
                "unknown": total_stats[HealthStatus.UNKNOWN]
            },
            "by_category": category_stats,
            "critical_issues": len(critical_issues),
            "warning_issues": len(warning_issues),
            "migration_ready": self.overall_status in [HealthStatus.HEALTHY, HealthStatus.WARNING]
        }

    def get_recommendations(self) -> List[str]:
        """获取修复建议"""
        recommendations = []

        for result in self.check_results:
            if result.status in [HealthStatus.CRITICAL, HealthStatus.WARNING]:
                recommendations.extend(result.recommendations)

        # 去重
        return list(set(recommendations))

    def save_report(self, file_path: str = None) -> str:
        """保存健康检查报告"""
        if not file_path:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = project_root / "logs" / f"health_check_report_{timestamp}.json"

        report_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "overall_status": self.overall_status.value,
            "summary": self.get_health_summary(),
            "recommendations": self.get_recommendations(),
            "detailed_results": [
                {
                    "check_id": result.check_id,
                    "name": result.name,
                    "category": result.category.value,
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details,
                    "recommendations": result.recommendations,
                    "timestamp": result.timestamp.isoformat(),
                    "duration": result.duration
                }
                for result in self.check_results
            ]
        }

        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"健康检查报告已保存: {file_path}")
        return str(file_path)


def run_health_check(config: Dict[str, Any] = None) -> Tuple[HealthStatus, str]:
    """运行健康检查的便捷函数"""
    checker = PreMigrationHealthChecker(config)
    overall_status, results = checker.run_all_checks()
    report_file = checker.save_report()

    return overall_status, report_file


if __name__ == "__main__":
    # 测试代码
    print("开始执行迁移前健康检查...")

    checker = PreMigrationHealthChecker()
    overall_status, results = checker.run_all_checks()

    print(f"\n总体健康状态: {overall_status.value}")
    print(f"检查项目数: {len(results)}")

    # 显示摘要
    summary = checker.get_health_summary()
    print(f"\n健康检查摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # 显示建议
    recommendations = checker.get_recommendations()
    if recommendations:
        print(f"\n修复建议:")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")

    # 保存报告
    report_file = checker.save_report()
    print(f"\n详细报告已保存到: {report_file}")

    # 显示是否可以进行迁移
    if summary["migration_ready"]:
        print("\n系统状态良好，可以进行迁移")
    else:
        print("\n[ERROR] 系统存在关键问题，建议修复后再进行迁移")
