"""
性能基准服务模块

提供性能基准测试、指标收集、存储和比较功能。
"""

import json
import os
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import statistics
import sqlite3

from loguru import logger

from ..services.base_service import BaseService
from ..events import EventBus, get_event_bus
from ..containers import get_service_container


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceBenchmark:
    """性能基准"""
    id: str
    name: str
    description: str
    timestamp: datetime
    duration_seconds: float
    metrics: List[PerformanceMetric]
    system_info: Dict[str, Any]
    success: bool
    error_message: Optional[str] = None


@dataclass
class PerformanceComparison:
    """性能比较结果"""
    baseline_id: str
    current_id: str
    improvements: List[str]
    regressions: List[str]
    metric_changes: Dict[str, Dict[str, float]]  # metric_name -> {old_value, new_value, change_percent}


class PerformanceBaselineService(BaseService):
    """
    性能基准服务

    提供系统性能基准测试、指标收集、存储和历史比较功能。
    """

    def __init__(self, event_bus: Optional[EventBus] = None, storage_path: str = "performance_baselines"):
        """
        初始化性能基准服务

        Args:
            event_bus: 事件总线
            storage_path: 基准数据存储路径
        """
        super().__init__(event_bus)

        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(exist_ok=True)

        # 数据库存储
        self._db_path = self._storage_path / "performance_baselines.db"
        self._init_database()

        # 当前基准数据
        self._current_benchmark: Optional[PerformanceBenchmark] = None
        self._baseline_benchmark: Optional[PerformanceBenchmark] = None

        # 监控状态
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._metrics_lock = threading.RLock()

        # 实时指标收集
        self._realtime_metrics: Dict[str, List[PerformanceMetric]] = {}
        self._metrics_window_size = 100  # 保留最近100个指标

        logger.info(f"Performance baseline service initialized with storage: {self._storage_path}")

    def initialize(self) -> None:
        """初始化服务"""
        if self._initialized:
            return

        try:
            # 加载最新基准
            self._load_latest_baseline()

            self._initialized = True
            logger.info("Performance baseline service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize performance baseline service: {e}")
            raise

    def _init_database(self) -> None:
        """初始化SQLite数据库"""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS benchmarks (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        timestamp TEXT NOT NULL,
                        duration_seconds REAL NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        system_info TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        benchmark_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        value REAL NOT NULL,
                        unit TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        metadata TEXT,
                        FOREIGN KEY (benchmark_id) REFERENCES benchmarks (id)
                    )
                ''')

                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_metrics_benchmark_id 
                    ON metrics (benchmark_id)
                ''')

                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_metrics_name 
                    ON metrics (name)
                ''')

            logger.info("Performance baseline database initialized")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def start_baseline_collection(self, name: str, description: str = "") -> str:
        """
        开始性能基准收集

        Args:
            name: 基准名称
            description: 基准描述

        Returns:
            基准ID
        """
        if self._current_benchmark:
            logger.warning("Baseline collection already in progress")
            return self._current_benchmark.id

        benchmark_id = f"baseline_{int(time.time())}_{name}"

        self._current_benchmark = PerformanceBenchmark(
            id=benchmark_id,
            name=name,
            description=description,
            timestamp=datetime.now(),
            duration_seconds=0.0,
            metrics=[],
            system_info=self._collect_system_info(),
            success=False
        )

        logger.info(f"Started baseline collection: {name} (ID: {benchmark_id})")
        return benchmark_id

    def collect_startup_metrics(self) -> List[PerformanceMetric]:
        """收集启动性能指标"""
        metrics = []

        try:
            # 获取服务容器
            container = get_service_container()

            # 收集服务初始化时间
            if hasattr(container, 'get_initialization_times'):
                init_times = container.get_initialization_times()
                for service_type, init_time in init_times.items():
                    metrics.append(PerformanceMetric(
                        name=f"service_init_time_{service_type.__name__}",
                        value=init_time * 1000,  # 转换为毫秒
                        unit="ms",
                        metadata={"service": service_type.__name__}
                    ))

            # 收集总启动时间（从进程开始计算）
            process = psutil.Process()
            startup_time = time.time() - process.create_time()
            metrics.append(PerformanceMetric(
                name="total_startup_time",
                value=startup_time,
                unit="seconds"
            ))

            # 收集内存使用
            memory_info = process.memory_info()
            metrics.append(PerformanceMetric(
                name="startup_memory_rss",
                value=memory_info.rss / 1024 / 1024,  # MB
                unit="MB"
            ))

            metrics.append(PerformanceMetric(
                name="startup_memory_vms",
                value=memory_info.vms / 1024 / 1024,  # MB
                unit="MB"
            ))

        except Exception as e:
            logger.error(f"Error collecting startup metrics: {e}")
            metrics.append(PerformanceMetric(
                name="startup_metrics_error",
                value=1.0,
                unit="count",
                metadata={"error": str(e)}
            ))

        return metrics

    def collect_service_resolution_metrics(self) -> List[PerformanceMetric]:
        """收集服务解析性能指标"""
        metrics = []

        try:
            container = get_service_container()

            # 测试常用服务的解析时间
            test_services = [
                'ConfigService',
                'UnifiedDataManager',
                'PluginManager'
            ]

            for service_name in test_services:
                try:
                    start_time = time.time()
                    # 这里需要根据实际的服务注册情况来解析
                    # 暂时使用简单的检查
                    resolution_time = time.time() - start_time

                    metrics.append(PerformanceMetric(
                        name=f"service_resolution_time_{service_name}",
                        value=resolution_time * 1000,  # 毫秒
                        unit="ms",
                        metadata={"service": service_name}
                    ))

                except Exception as e:
                    metrics.append(PerformanceMetric(
                        name=f"service_resolution_error_{service_name}",
                        value=1.0,
                        unit="count",
                        metadata={"service": service_name, "error": str(e)}
                    ))

        except Exception as e:
            logger.error(f"Error collecting service resolution metrics: {e}")

        return metrics

    def collect_memory_metrics(self) -> List[PerformanceMetric]:
        """收集内存使用指标"""
        metrics = []

        try:
            process = psutil.Process()

            # 内存信息
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            metrics.extend([
                PerformanceMetric(
                    name="memory_rss",
                    value=memory_info.rss / 1024 / 1024,
                    unit="MB"
                ),
                PerformanceMetric(
                    name="memory_vms",
                    value=memory_info.vms / 1024 / 1024,
                    unit="MB"
                ),
                PerformanceMetric(
                    name="memory_percent",
                    value=memory_percent,
                    unit="percent"
                )
            ])

            # 系统内存信息
            system_memory = psutil.virtual_memory()
            metrics.extend([
                PerformanceMetric(
                    name="system_memory_total",
                    value=system_memory.total / 1024 / 1024 / 1024,
                    unit="GB"
                ),
                PerformanceMetric(
                    name="system_memory_available",
                    value=system_memory.available / 1024 / 1024 / 1024,
                    unit="GB"
                ),
                PerformanceMetric(
                    name="system_memory_used_percent",
                    value=system_memory.percent,
                    unit="percent"
                )
            ])

        except Exception as e:
            logger.error(f"Error collecting memory metrics: {e}")
            metrics.append(PerformanceMetric(
                name="memory_metrics_error",
                value=1.0,
                unit="count",
                metadata={"error": str(e)}
            ))

        return metrics

    def collect_cpu_metrics(self) -> List[PerformanceMetric]:
        """收集CPU使用指标"""
        metrics = []

        try:
            process = psutil.Process()

            # CPU使用率（需要等待一小段时间来计算）
            cpu_percent = process.cpu_percent(interval=0.1)

            metrics.extend([
                PerformanceMetric(
                    name="cpu_percent",
                    value=cpu_percent,
                    unit="percent"
                ),
                PerformanceMetric(
                    name="cpu_count",
                    value=psutil.cpu_count(),
                    unit="count"
                ),
                PerformanceMetric(
                    name="cpu_count_logical",
                    value=psutil.cpu_count(logical=True),
                    unit="count"
                )
            ])

            # 系统CPU信息
            system_cpu_percent = psutil.cpu_percent(interval=0.1)
            metrics.append(PerformanceMetric(
                name="system_cpu_percent",
                value=system_cpu_percent,
                unit="percent"
            ))

        except Exception as e:
            logger.error(f"Error collecting CPU metrics: {e}")
            metrics.append(PerformanceMetric(
                name="cpu_metrics_error",
                value=1.0,
                unit="count",
                metadata={"error": str(e)}
            ))

        return metrics

    def finish_baseline_collection(self, success: bool = True, error_message: Optional[str] = None) -> Optional[PerformanceBenchmark]:
        """
        完成基准收集

        Args:
            success: 是否成功
            error_message: 错误信息

        Returns:
            完成的基准测试结果
        """
        if not self._current_benchmark:
            logger.warning("No baseline collection in progress")
            return None

        # 计算持续时间
        self._current_benchmark.duration_seconds = (
            datetime.now() - self._current_benchmark.timestamp
        ).total_seconds()

        self._current_benchmark.success = success
        self._current_benchmark.error_message = error_message

        # 收集所有指标
        all_metrics = []
        all_metrics.extend(self.collect_startup_metrics())
        all_metrics.extend(self.collect_service_resolution_metrics())
        all_metrics.extend(self.collect_memory_metrics())
        all_metrics.extend(self.collect_cpu_metrics())

        self._current_benchmark.metrics = all_metrics

        # 保存到数据库
        self._save_benchmark(self._current_benchmark)

        # 设置为当前基准
        completed_benchmark = self._current_benchmark
        self._current_benchmark = None

        logger.info(
            f"Baseline collection completed: {completed_benchmark.name} "
            f"({len(all_metrics)} metrics, {completed_benchmark.duration_seconds:.2f}s)"
        )

        return completed_benchmark

    def run_comprehensive_benchmark(self, name: str, description: str = "") -> PerformanceBenchmark:
        """
        运行综合性能基准测试

        Args:
            name: 基准名称
            description: 基准描述

        Returns:
            基准测试结果
        """
        logger.info(f"Starting comprehensive benchmark: {name}")

        try:
            # 开始收集
            benchmark_id = self.start_baseline_collection(name, description)

            # 等待一段时间确保所有服务都已初始化
            time.sleep(1)

            # 完成收集
            benchmark = self.finish_baseline_collection(success=True)

            return benchmark

        except Exception as e:
            logger.error(f"Comprehensive benchmark failed: {e}")
            return self.finish_baseline_collection(success=False, error_message=str(e))

    def _collect_system_info(self) -> Dict[str, Any]:
        """收集系统信息"""
        try:
            return {
                'platform': os.name,
                'cpu_count': psutil.cpu_count(),
                'cpu_count_logical': psutil.cpu_count(logical=True),
                'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
                'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error collecting system info: {e}")
            return {'error': str(e)}

    def _save_benchmark(self, benchmark: PerformanceBenchmark) -> None:
        """保存基准到数据库"""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                # 保存基准记录
                conn.execute('''
                    INSERT INTO benchmarks 
                    (id, name, description, timestamp, duration_seconds, success, error_message, system_info)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    benchmark.id,
                    benchmark.name,
                    benchmark.description,
                    benchmark.timestamp.isoformat(),
                    benchmark.duration_seconds,
                    benchmark.success,
                    benchmark.error_message,
                    json.dumps(benchmark.system_info)
                ))

                # 保存指标
                for metric in benchmark.metrics:
                    conn.execute('''
                        INSERT INTO metrics 
                        (benchmark_id, name, value, unit, timestamp, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        benchmark.id,
                        metric.name,
                        metric.value,
                        metric.unit,
                        metric.timestamp.isoformat(),
                        json.dumps(metric.metadata)
                    ))

                conn.commit()

            logger.info(f"Benchmark {benchmark.id} saved to database")

        except Exception as e:
            logger.error(f"Failed to save benchmark {benchmark.id}: {e}")

    def _load_latest_baseline(self) -> None:
        """加载最新的基准"""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute('''
                    SELECT id, name, description, timestamp, duration_seconds, success, error_message, system_info
                    FROM benchmarks 
                    WHERE success = 1
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ''')

                row = cursor.fetchone()
                if row:
                    benchmark_id = row[0]

                    # 加载指标
                    metrics_cursor = conn.execute('''
                        SELECT name, value, unit, timestamp, metadata
                        FROM metrics 
                        WHERE benchmark_id = ?
                    ''', (benchmark_id,))

                    metrics = []
                    for metric_row in metrics_cursor.fetchall():
                        metrics.append(PerformanceMetric(
                            name=metric_row[0],
                            value=metric_row[1],
                            unit=metric_row[2],
                            timestamp=datetime.fromisoformat(metric_row[3]),
                            metadata=json.loads(metric_row[4]) if metric_row[4] else {}
                        ))

                    self._baseline_benchmark = PerformanceBenchmark(
                        id=row[0],
                        name=row[1],
                        description=row[2],
                        timestamp=datetime.fromisoformat(row[3]),
                        duration_seconds=row[4],
                        success=bool(row[5]),
                        error_message=row[6],
                        system_info=json.loads(row[7]) if row[7] else {},
                        metrics=metrics
                    )

                    logger.info(f"Loaded baseline: {self._baseline_benchmark.name}")

        except Exception as e:
            logger.error(f"Failed to load latest baseline: {e}")

    def compare_with_baseline(self, current_benchmark: PerformanceBenchmark) -> PerformanceComparison:
        """
        与基准进行比较

        Args:
            current_benchmark: 当前基准测试结果

        Returns:
            比较结果
        """
        if not self._baseline_benchmark:
            logger.warning("No baseline available for comparison")
            return PerformanceComparison(
                baseline_id="none",
                current_id=current_benchmark.id,
                improvements=[],
                regressions=[],
                metric_changes={}
            )

        improvements = []
        regressions = []
        metric_changes = {}

        # 创建指标映射
        baseline_metrics = {m.name: m.value for m in self._baseline_benchmark.metrics}
        current_metrics = {m.name: m.value for m in current_benchmark.metrics}

        # 比较共同指标
        for metric_name in set(baseline_metrics.keys()) & set(current_metrics.keys()):
            baseline_value = baseline_metrics[metric_name]
            current_value = current_metrics[metric_name]

            if baseline_value != 0:
                change_percent = ((current_value - baseline_value) / baseline_value) * 100
            else:
                change_percent = 0.0

            metric_changes[metric_name] = {
                'baseline_value': baseline_value,
                'current_value': current_value,
                'change_percent': change_percent
            }

            # 判断改进或回退（针对特定指标）
            if 'time' in metric_name.lower() or 'duration' in metric_name.lower():
                # 时间类指标：减少是改进
                if change_percent < -5:  # 改进超过5%
                    improvements.append(f"{metric_name}: {change_percent:.1f}% faster")
                elif change_percent > 5:  # 回退超过5%
                    regressions.append(f"{metric_name}: {change_percent:.1f}% slower")
            elif 'memory' in metric_name.lower():
                # 内存类指标：减少是改进
                if change_percent < -5:
                    improvements.append(f"{metric_name}: {change_percent:.1f}% less memory")
                elif change_percent > 5:
                    regressions.append(f"{metric_name}: {change_percent:.1f}% more memory")
            elif 'cpu' in metric_name.lower():
                # CPU类指标：减少是改进
                if change_percent < -5:
                    improvements.append(f"{metric_name}: {change_percent:.1f}% less CPU")
                elif change_percent > 5:
                    regressions.append(f"{metric_name}: {change_percent:.1f}% more CPU")

        return PerformanceComparison(
            baseline_id=self._baseline_benchmark.id,
            current_id=current_benchmark.id,
            improvements=improvements,
            regressions=regressions,
            metric_changes=metric_changes
        )

    def get_benchmark_history(self, limit: int = 10) -> List[PerformanceBenchmark]:
        """
        获取基准测试历史

        Args:
            limit: 返回数量限制

        Returns:
            历史基准测试列表
        """
        history = []

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute('''
                    SELECT id, name, description, timestamp, duration_seconds, success, error_message, system_info
                    FROM benchmarks 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))

                for row in cursor.fetchall():
                    benchmark = PerformanceBenchmark(
                        id=row[0],
                        name=row[1],
                        description=row[2],
                        timestamp=datetime.fromisoformat(row[3]),
                        duration_seconds=row[4],
                        success=bool(row[5]),
                        error_message=row[6],
                        system_info=json.loads(row[7]) if row[7] else {},
                        metrics=[]  # 不加载详细指标以提高性能
                    )
                    history.append(benchmark)

        except Exception as e:
            logger.error(f"Failed to get benchmark history: {e}")

        return history

    def generate_performance_report(self, benchmark: PerformanceBenchmark) -> str:
        """
        生成性能报告

        Args:
            benchmark: 基准测试结果

        Returns:
            性能报告文本
        """
        report = []
        report.append(f"# Performance Report: {benchmark.name}")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Benchmark ID: {benchmark.id}")
        report.append(f"Duration: {benchmark.duration_seconds:.2f} seconds")
        report.append(f"Success: {'✓' if benchmark.success else '❌'}")

        if benchmark.error_message:
            report.append(f"Error: {benchmark.error_message}")

        report.append("\n## System Information")
        for key, value in benchmark.system_info.items():
            report.append(f"- {key}: {value}")

        report.append("\n## Performance Metrics")

        # 按类别分组指标
        categories = {
            'Startup': [m for m in benchmark.metrics if 'startup' in m.name],
            'Memory': [m for m in benchmark.metrics if 'memory' in m.name],
            'CPU': [m for m in benchmark.metrics if 'cpu' in m.name],
            'Service': [m for m in benchmark.metrics if 'service' in m.name],
            'Other': []
        }

        # 其他指标
        categorized_metrics = set()
        for cat_metrics in categories.values():
            categorized_metrics.update(cat_metrics)

        categories['Other'] = [m for m in benchmark.metrics if m not in categorized_metrics]

        for category, metrics in categories.items():
            if metrics:
                report.append(f"\n### {category} Metrics")
                for metric in sorted(metrics, key=lambda m: m.name):
                    report.append(f"- {metric.name}: {metric.value:.2f} {metric.unit}")

        # 基准比较
        if self._baseline_benchmark:
            comparison = self.compare_with_baseline(benchmark)

            report.append("\n## Comparison with Baseline")
            report.append(f"Baseline: {self._baseline_benchmark.name} ({self._baseline_benchmark.id})")

            if comparison.improvements:
                report.append("\n### Improvements ✓")
                for improvement in comparison.improvements:
                    report.append(f"- {improvement}")

            if comparison.regressions:
                report.append("\n### Regressions ❌")
                for regression in comparison.regressions:
                    report.append(f"- {regression}")

            if not comparison.improvements and not comparison.regressions:
                report.append("- No significant changes detected")

        return "\n".join(report)

    def set_as_baseline(self, benchmark_id: str) -> bool:
        """
        设置指定基准为新的基线

        Args:
            benchmark_id: 基准ID

        Returns:
            是否成功
        """
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute('''
                    SELECT id, name, description, timestamp, duration_seconds, success, error_message, system_info
                    FROM benchmarks 
                    WHERE id = ? AND success = 1
                ''', (benchmark_id,))

                row = cursor.fetchone()
                if not row:
                    logger.error(f"Benchmark {benchmark_id} not found or not successful")
                    return False

                # 加载指标
                metrics_cursor = conn.execute('''
                    SELECT name, value, unit, timestamp, metadata
                    FROM metrics 
                    WHERE benchmark_id = ?
                ''', (benchmark_id,))

                metrics = []
                for metric_row in metrics_cursor.fetchall():
                    metrics.append(PerformanceMetric(
                        name=metric_row[0],
                        value=metric_row[1],
                        unit=metric_row[2],
                        timestamp=datetime.fromisoformat(metric_row[3]),
                        metadata=json.loads(metric_row[4]) if metric_row[4] else {}
                    ))

                self._baseline_benchmark = PerformanceBenchmark(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    timestamp=datetime.fromisoformat(row[3]),
                    duration_seconds=row[4],
                    success=bool(row[5]),
                    error_message=row[6],
                    system_info=json.loads(row[7]) if row[7] else {},
                    metrics=metrics
                )

                logger.info(f"Set benchmark {benchmark_id} as new baseline")
                return True

        except Exception as e:
            logger.error(f"Failed to set baseline {benchmark_id}: {e}")
            return False

    def dispose(self) -> None:
        """释放服务资源"""
        self.stop_monitoring()
        super().dispose()
        logger.info("Performance baseline service disposed")


# 全局实例
_performance_baseline_service: Optional[PerformanceBaselineService] = None
_service_lock = threading.Lock()


def get_performance_baseline_service() -> PerformanceBaselineService:
    """获取全局性能基准服务实例"""
    global _performance_baseline_service
    if _performance_baseline_service is None:
        with _service_lock:
            if _performance_baseline_service is None:
                _performance_baseline_service = PerformanceBaselineService()
    return _performance_baseline_service
