from loguru import logger
#!/usr/bin/env python3
"""
FactorWeave-Quant系统优化器服务

基于新架构的系统优化器，提供自动分析和优化功能，清理冗余文件，提升性能
"""

import os
import sys
import gc
import asyncio
import shutil
from pathlib import Path
from typing import List, Dict, Any, Set, Optional, Callable
import ast
import importlib.util
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

# 核心模块导入
from core.services.base_service import AsyncBaseService
from core.config import ConfigManager
from core.events import EventBus
from core.performance.unified_monitor import UnifiedPerformanceMonitor

from utils.manager_factory import get_config_manager

logger = logger.bind(module=__name__)


class OptimizationLevel(Enum):
    """优化级别"""
    LIGHT = "light"      # 轻度优化：只清理缓存
    MEDIUM = "medium"    # 中度优化：清理缓存 + 临时文件
    DEEP = "deep"        # 深度优化：全面优化
    CUSTOM = "custom"    # 自定义优化


@dataclass
class OptimizationConfig:
    """优化配置"""
    level: OptimizationLevel = OptimizationLevel.MEDIUM
    clean_cache: bool = True
    clean_temp_files: bool = True
    clean_logs: bool = True
    optimize_imports: bool = True
    optimize_memory: bool = True
    analyze_dependencies: bool = True
    backup_before_optimize: bool = True
    log_retention_days: int = 30
    max_file_size_mb: int = 100
    exclude_patterns: List[str] = None
    include_patterns: List[str] = None

    def __post_init__(self):
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                '__pycache__',
                '.git',
                '.pytest_cache',
                'node_modules',
                '.vscode',
                '.idea',
                '*.pyc',
                '*.pyo',
                '*.pyd',
                '.DS_Store',
                'Thumbs.db'
            ]
        if self.include_patterns is None:
            self.include_patterns = ['*.py', '*.json', '*.yaml', '*.yml']


@dataclass
class OptimizationResult:
    """优化结果"""
    start_time: datetime
    end_time: datetime
    level: OptimizationLevel
    total_files_scanned: int = 0
    files_cleaned: int = 0
    files_optimized: int = 0
    bytes_freed: int = 0
    errors: List[str] = None
    warnings: List[str] = None
    performance_improvement: float = 0.0

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    @property
    def duration(self) -> timedelta:
        return self.end_time - self.start_time

    @property
    def success_rate(self) -> float:
        if self.total_files_scanned == 0:
            return 0.0
        return (self.total_files_scanned - len(self.errors)) / self.total_files_scanned


class SystemOptimizerService(AsyncBaseService):
    """系统优化器服务"""

    def __init__(self,
                 config_manager: Optional[ConfigManager] = None,
                 performance_monitor: Optional[UnifiedPerformanceMonitor] = None,
                 event_bus: Optional[EventBus] = None):
        """
        初始化系统优化器服务

        Args:
            config_manager: 配置管理器
            performance_monitor: 性能监控器
            event_bus: 事件总线
        """
        super().__init__(event_bus)
        self._config_manager = config_manager
        self._performance_monitor = performance_monitor
        try:
            from core.services.unified_cache_provider import get_unified_cache_provider
            self._cache = get_unified_cache_provider().get_cache_service()
        except ImportError:
            self._cache = None

        self._project_root = Path(".")
        self._optimization_config = OptimizationConfig()
        self._current_result: Optional[OptimizationResult] = None
        self._optimization_history: List[OptimizationResult] = []

        # 回调函数
        self._progress_callback: Optional[Callable[[str, float], None]] = None
        self._status_callback: Optional[Callable[[str], None]] = None

    async def _do_initialize_async(self) -> None:
        """异步初始化服务"""
        try:
            # 延迟初始化依赖项
            if self._config_manager is None:
                self._config_manager = get_config_manager()
            if self._performance_monitor is None:
                self._performance_monitor = get_performance_monitor()

            # 加载配置
            await self._load_configuration()

            # 初始化项目根目录
            self._project_root = Path(
                self._config_manager.get('project.root_path', '.'))

            # 确保日志目录存在
            logs_dir = self._project_root / 'logs'
            logs_dir.mkdir(exist_ok=True)

            # 注册事件监听器
            self._register_event_listeners()

            logger.info(f"系统优化器服务初始化完成，项目根目录: {self._project_root}")

        except Exception as e:
            logger.error(f"系统优化器服务初始化失败: {e}")
            raise

    async def _do_dispose_async(self) -> None:
        """异步清理服务资源"""
        try:
            # 保存优化历史
            await self._save_optimization_history()

            if self._cache:
                self._cache.clear_namespace("system_optimizer")

            logger.info("系统优化器服务已清理")

        except Exception as e:
            logger.error(f"系统优化器服务清理失败: {e}")

    async def _load_configuration(self) -> None:
        """加载配置"""
        try:
            config_dict = self._config_manager.get('optimization', {})

            # 更新优化配置
            if config_dict:
                for key, value in config_dict.items():
                    if hasattr(self._optimization_config, key):
                        setattr(self._optimization_config, key, value)

            logger.info("优化配置加载完成")

        except Exception as e:
            logger.warning(f"加载优化配置失败，使用默认配置: {e}")

    def _register_event_listeners(self) -> None:
        """注册事件监听器"""
        self.event_bus.subscribe(
            'system.optimization.start', self._on_optimization_start)
        self.event_bus.subscribe(
            'system.optimization.complete', self._on_optimization_complete)
        self.event_bus.subscribe(
            'system.optimization.error', self._on_optimization_error)

    def _on_optimization_start(self, event_data) -> None:
        """优化开始事件处理"""
        logger.info("系统优化开始")
        if self._status_callback:
            self._status_callback("优化开始")

    def _on_optimization_complete(self, event_data) -> None:
        """优化完成事件处理"""
        result = getattr(event_data, 'result', None)
        if result:
            self._optimization_history.append(result)
            logger.info(f"系统优化完成，耗时: {result.duration}")
            if self._status_callback:
                self._status_callback("优化完成")

    def _on_optimization_error(self, event_data) -> None:
        """优化错误事件处理"""
        error = getattr(event_data, 'error', '未知错误')
        logger.error(f"系统优化失败: {error}")
        if self._status_callback:
            self._status_callback(f"优化失败: {error}")

    def set_progress_callback(self, callback: Callable[[str, float], None]) -> None:
        """设置进度回调函数"""
        self._progress_callback = callback

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """设置状态回调函数"""
        self._status_callback = callback

    def update_optimization_config(self, config: OptimizationConfig) -> None:
        """更新优化配置"""
        self._optimization_config = config
        logger.info(f"优化配置已更新: {config.level}")

    @property
    def optimization_config(self) -> OptimizationConfig:
        """获取优化配置"""
        return self._optimization_config

    @property
    def optimization_history(self) -> List[OptimizationResult]:
        """获取优化历史"""
        return self._optimization_history.copy()

    @property
    def current_result(self) -> Optional[OptimizationResult]:
        """获取当前优化结果"""
        return self._current_result

    async def analyze_system(self) -> Dict[str, Any]:
        """分析系统状态"""
        self._ensure_not_disposed()

        with self._performance_monitor.measure_time("system_analysis"):
            logger.info("开始系统状态分析...")

            if self._progress_callback:
                self._progress_callback("正在分析系统...", 0.0)

            analysis = {
                'scan_time': datetime.now(),
                'total_files': 0,
                'python_files': 0,
                'large_files': [],
                'empty_files': [],
                'cache_files': [],
                'log_files': [],
                'temp_files': [],
                'duplicate_files': [],
                'import_analysis': {
                    'duplicate_imports': [],
                    'unused_imports': [],
                    'circular_imports': []
                },
                'dependency_analysis': {
                    'missing_dependencies': [],
                    'outdated_dependencies': [],
                    'unused_dependencies': []
                },
                'performance_issues': [],
                'security_issues': []
            }

            try:
                total_files = list(self._project_root.rglob('*'))
                analysis['total_files'] = len(
                    [f for f in total_files if f.is_file()])

                processed = 0
                for file_path in total_files:
                    if not file_path.is_file() or self._should_ignore(file_path):
                        continue

                    processed += 1
                    if self._progress_callback and processed % 100 == 0:
                        progress = processed / len(total_files)
                        self._progress_callback(
                            f"分析文件: {file_path.name}", progress)

                    await self._analyze_file(file_path, analysis)

                # 分析依赖关系
                await self._analyze_dependencies(analysis)

                # 分析性能问题
                await self._analyze_performance_issues(analysis)

                # 分析安全问题
                await self._analyze_security_issues(analysis)

                logger.info(f"系统分析完成: {analysis['total_files']}个文件")
                return analysis

            except Exception as e:
                logger.error(f"系统分析失败: {e}")
                raise

    async def _analyze_file(self, file_path: Path, analysis: Dict[str, Any]) -> None:
        """分析单个文件"""
        try:
            file_size = file_path.stat().st_size

            # 检查大文件
            if file_size > self._optimization_config.max_file_size_mb * 1024 * 1024:
                analysis['large_files'].append({
                    'path': str(file_path),
                    'size_mb': file_size / (1024 * 1024)
                })

            # 检查空文件
            if file_size == 0:
                analysis['empty_files'].append(str(file_path))

            # 分类文件
            if file_path.suffix == '.py':
                analysis['python_files'] += 1
                await self._analyze_python_file(file_path, analysis)
            elif any(pattern in str(file_path).lower() for pattern in ['cache', 'tmp', 'temp']):
                analysis['cache_files'].append(str(file_path))
            elif file_path.suffix in ['.log', '.out'] or 'log' in file_path.name.lower():
                analysis['log_files'].append(str(file_path))
            elif file_path.suffix in ['.tmp', '.temp', '.bak'] or file_path.name.startswith('~'):
                analysis['temp_files'].append(str(file_path))

        except Exception as e:
            logger.warning(f"分析文件失败 {file_path}: {e}")

    async def _analyze_python_file(self, file_path: Path, analysis: Dict[str, Any]) -> None:
        """分析Python文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析AST
            tree = ast.parse(content)

            # 分析导入
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")

            # 检查重复导入
            seen_imports = set()
            for imp in imports:
                if imp in seen_imports:
                    analysis['import_analysis']['duplicate_imports'].append({
                        'file': str(file_path),
                        'import': imp
                    })
                seen_imports.add(imp)

            # 检查潜在的性能问题
            await self._check_performance_issues(file_path, tree, analysis)

        except Exception as e:
            logger.warning(f"分析Python文件失败 {file_path}: {e}")

    async def _analyze_dependencies(self, analysis: Dict[str, Any]) -> None:
        """分析依赖关系"""
        try:
            # 检查requirements.txt
            req_file = self._project_root / 'requirements.txt'
            if req_file.exists():
                with open(req_file, 'r', encoding='utf-8') as f:
                    requirements = f.read().splitlines()

                # 分析依赖
                for req in requirements:
                    if req.strip() and not req.startswith('#'):
                        # 这里可以添加更复杂的依赖分析逻辑
                        pass

        except Exception as e:
            logger.warning(f"依赖分析失败: {e}")

    async def _analyze_performance_issues(self, analysis: Dict[str, Any]) -> None:
        """分析性能问题"""
        try:
            # 检查大文件
            for large_file in analysis['large_files']:
                if large_file['size_mb'] > 50:  # 大于50MB
                    analysis['performance_issues'].append({
                        'type': 'large_file',
                        'file': large_file['path'],
                        'description': f"文件过大: {large_file['size_mb']:.2f}MB"
                    })

            # 检查重复导入
            if analysis['import_analysis']['duplicate_imports']:
                analysis['performance_issues'].append({
                    'type': 'duplicate_imports',
                    'count': len(analysis['import_analysis']['duplicate_imports']),
                    'description': "存在重复导入，可能影响启动性能"
                })

        except Exception as e:
            logger.warning(f"性能问题分析失败: {e}")

    async def _analyze_security_issues(self, analysis: Dict[str, Any]) -> None:
        """分析安全问题"""
        try:
            # 检查敏感文件
            sensitive_patterns = ['.env', 'password', 'secret', 'key', 'token']

            for file_path in self._project_root.rglob('*'):
                if file_path.is_file():
                    file_name_lower = file_path.name.lower()
                    if any(pattern in file_name_lower for pattern in sensitive_patterns):
                        analysis['security_issues'].append({
                            'type': 'sensitive_file',
                            'file': str(file_path),
                            'description': "可能包含敏感信息的文件"
                        })

        except Exception as e:
            logger.warning(f"安全问题分析失败: {e}")

    async def _check_performance_issues(self, file_path: Path, tree: ast.AST, analysis: Dict[str, Any]) -> None:
        """检查代码性能问题"""
        try:
            # 检查循环中的重复计算
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.While)):
                    # 这里可以添加更复杂的性能检查逻辑
                    pass

        except Exception as e:
            logger.warning(f"性能问题检查失败 {file_path}: {e}")

    async def optimize_system(self, level: OptimizationLevel = None) -> OptimizationResult:
        """优化系统"""
        self._ensure_not_disposed()

        level = level or self._optimization_config.level
        start_time = datetime.now()

        # 创建优化结果
        self._current_result = OptimizationResult(
            start_time=start_time,
            end_time=start_time,  # 临时设置
            level=level
        )

        try:
            # 发送优化开始事件
            self.event_bus.publish('system.optimization.start',
                                   level=level,
                                   config=asdict(self._optimization_config)
                                   )

            logger.info(f"开始系统优化，级别: {level}")

            with self._performance_monitor.measure_time("system_optimization"):
                # 备份（如果需要）
                if self._optimization_config.backup_before_optimize:
                    await self._create_backup()

                # 根据级别执行不同的优化
                if level == OptimizationLevel.LIGHT:
                    await self._light_optimization()
                elif level == OptimizationLevel.MEDIUM:
                    await self._medium_optimization()
                elif level == OptimizationLevel.DEEP:
                    await self._deep_optimization()
                else:  # CUSTOM
                    await self._custom_optimization()

                # 内存优化
                if self._optimization_config.optimize_memory:
                    await self._optimize_memory()

                # 更新结果
                self._current_result.end_time = datetime.now()

                # 发送优化完成事件
                self.event_bus.publish('system.optimization.complete',
                                       result=self._current_result
                                       )

                logger.info(f"系统优化完成，耗时: {self._current_result.duration}")
                return self._current_result

        except Exception as e:
            # 发送优化错误事件
            self.event_bus.publish('system.optimization.error',
                                   error=str(e),
                                   level=level
                                   )

            self._current_result.errors.append(str(e))
            self._current_result.end_time = datetime.now()

            logger.error(f"系统优化失败: {e}")
            self._exception_handler.handle_exception(e, "system_optimization")
            raise

    async def _create_backup(self) -> None:
        """创建备份"""
        try:
            backup_dir = self._project_root / 'backups' / \
                f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 备份重要文件
            important_files = ['requirements.txt',
                               'setup.py', 'config.json', 'settings.json']
            for file_name in important_files:
                src_file = self._project_root / file_name
                if src_file.exists():
                    shutil.copy2(src_file, backup_dir / file_name)

            logger.info(f"备份创建完成: {backup_dir}")

        except Exception as e:
            logger.warning(f"创建备份失败: {e}")

    async def _light_optimization(self) -> None:
        """轻度优化"""
        if self._progress_callback:
            self._progress_callback("执行轻度优化...", 0.0)

        # 只清理缓存
        await self._clean_cache_files()

        if self._progress_callback:
            self._progress_callback("轻度优化完成", 1.0)

    async def _medium_optimization(self) -> None:
        """中度优化"""
        if self._progress_callback:
            self._progress_callback("执行中度优化...", 0.0)

        # 清理缓存和临时文件
        await self._clean_cache_files()
        if self._progress_callback:
            self._progress_callback("缓存清理完成", 0.3)

        await self._clean_temp_files()
        if self._progress_callback:
            self._progress_callback("临时文件清理完成", 0.6)

        await self._clean_old_logs()
        if self._progress_callback:
            self._progress_callback("中度优化完成", 1.0)

    async def _deep_optimization(self) -> None:
        """深度优化"""
        if self._progress_callback:
            self._progress_callback("执行深度优化...", 0.0)

        # 执行全面优化
        await self._clean_cache_files()
        if self._progress_callback:
            self._progress_callback("缓存清理完成", 0.2)

        await self._clean_temp_files()
        if self._progress_callback:
            self._progress_callback("临时文件清理完成", 0.4)

        await self._clean_old_logs()
        if self._progress_callback:
            self._progress_callback("日志清理完成", 0.6)

        await self._optimize_imports()
        if self._progress_callback:
            self._progress_callback("导入优化完成", 0.8)

        await self._optimize_code_structure()
        if self._progress_callback:
            self._progress_callback("深度优化完成", 1.0)

    async def _custom_optimization(self) -> None:
        """自定义优化"""
        if self._progress_callback:
            self._progress_callback("执行自定义优化...", 0.0)

        tasks = []
        progress_step = 0.0
        total_tasks = 0

        # 根据配置决定执行哪些优化
        if self._optimization_config.clean_cache:
            tasks.append(self._clean_cache_files())
            total_tasks += 1

        if self._optimization_config.clean_temp_files:
            tasks.append(self._clean_temp_files())
            total_tasks += 1

        if self._optimization_config.clean_logs:
            tasks.append(self._clean_old_logs())
            total_tasks += 1

        if self._optimization_config.optimize_imports:
            tasks.append(self._optimize_imports())
            total_tasks += 1

        # 执行任务
        for i, task in enumerate(tasks):
            await task
            progress_step = (i + 1) / total_tasks
            if self._progress_callback:
                self._progress_callback(f"自定义优化进度", progress_step)

        if self._progress_callback:
            self._progress_callback("自定义优化完成", 1.0)

    async def _clean_cache_files(self) -> int:
        """清理缓存文件"""
        logger.info("开始清理缓存文件...")

        cleaned_count = 0
        bytes_freed = 0
        cache_patterns = ['__pycache__',
                          '.pytest_cache', '.cache', '.mypy_cache']

        for pattern in cache_patterns:
            for cache_dir in self._project_root.rglob(pattern):
                if cache_dir.is_dir():
                    try:
                        # 计算目录大小
                        dir_size = sum(
                            f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())

                        shutil.rmtree(cache_dir)
                        cleaned_count += 1
                        bytes_freed += dir_size

                        logger.info(f"删除缓存目录: {cache_dir}")

                    except Exception as e:
                        logger.error(f"删除缓存目录失败 {cache_dir}: {e}")
                        self._current_result.errors.append(f"删除缓存目录失败: {e}")

        # 清理.pyc文件
        for pyc_file in self._project_root.rglob('*.pyc'):
            try:
                file_size = pyc_file.stat().st_size
                pyc_file.unlink()
                cleaned_count += 1
                bytes_freed += file_size

            except Exception as e:
                logger.error(f"删除.pyc文件失败 {pyc_file}: {e}")
                self._current_result.errors.append(f"删除.pyc文件失败: {e}")

        self._current_result.files_cleaned += cleaned_count
        self._current_result.bytes_freed += bytes_freed

        logger.info(
            f"缓存文件清理完成，删除了 {cleaned_count} 个文件/目录，释放 {bytes_freed / 1024 / 1024:.2f} MB")
        return cleaned_count

    async def _clean_temp_files(self) -> int:
        """清理临时文件"""
        logger.info("开始清理临时文件...")

        cleaned_count = 0
        bytes_freed = 0
        temp_patterns = ['*.tmp', '*.temp', '*.bak', '~*', '*.swp', '*.swo']

        for pattern in temp_patterns:
            for temp_file in self._project_root.rglob(pattern):
                if temp_file.is_file():
                    try:
                        file_size = temp_file.stat().st_size
                        temp_file.unlink()
                        cleaned_count += 1
                        bytes_freed += file_size

                        logger.info(f"删除临时文件: {temp_file}")

                    except Exception as e:
                        logger.error(f"删除临时文件失败 {temp_file}: {e}")
                        self._current_result.errors.append(f"删除临时文件失败: {e}")

        self._current_result.files_cleaned += cleaned_count
        self._current_result.bytes_freed += bytes_freed

        logger.info(
            f"临时文件清理完成，删除了 {cleaned_count} 个文件，释放 {bytes_freed / 1024 / 1024:.2f} MB")
        return cleaned_count

    async def _clean_old_logs(self) -> int:
        """清理旧日志文件"""
        logger.info(
            f"开始清理 {self._optimization_config.log_retention_days} 天前的日志文件...")

        cleaned_count = 0
        bytes_freed = 0
        cutoff_time = datetime.now().timestamp() - \
            (self._optimization_config.log_retention_days * 24 * 60 * 60)

        logs_dir = self._project_root / 'logs'
        if logs_dir.exists():
            for log_file in logs_dir.rglob('*.log'):
                try:
                    if log_file.stat().st_mtime < cutoff_time:
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        cleaned_count += 1
                        bytes_freed += file_size

                        logger.info(f"删除旧日志文件: {log_file}")

                except Exception as e:
                    logger.error(f"删除日志文件失败 {log_file}: {e}")
                    self._current_result.errors.append(f"删除日志文件失败: {e}")

        self._current_result.files_cleaned += cleaned_count
        self._current_result.bytes_freed += bytes_freed

        logger.info(
            f"日志清理完成，删除了 {cleaned_count} 个文件，释放 {bytes_freed / 1024 / 1024:.2f} MB")
        return cleaned_count

    async def _optimize_imports(self) -> int:
        """优化导入语句"""
        logger.info("开始优化导入语句...")

        optimized_count = 0

        for py_file in self._project_root.rglob('*.py'):
            if self._should_ignore(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 简单的导入优化：移除重复的导入
                lines = content.split('\n')
                seen_imports = set()
                optimized_lines = []

                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith(('import ', 'from ')):
                        if stripped not in seen_imports:
                            seen_imports.add(stripped)
                            optimized_lines.append(line)
                        else:
                            logger.info(f"移除重复导入: {stripped} in {py_file}")
                            optimized_count += 1
                    else:
                        optimized_lines.append(line)

                # 如果有优化，写回文件
                if len(optimized_lines) < len(lines):
                    with open(py_file, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(optimized_lines))
                    self._current_result.files_optimized += 1

            except Exception as e:
                logger.error(f"优化导入失败 {py_file}: {e}")
                self._current_result.errors.append(f"优化导入失败: {e}")

        logger.info(f"导入优化完成，优化了 {optimized_count} 个重复导入")
        return optimized_count

    async def _optimize_code_structure(self) -> None:
        """优化代码结构"""
        logger.info("开始优化代码结构...")

        try:
            # 获取所有Python文件
            python_files = list(self._project_root.rglob("*.py"))
            
            # 分析并优化每个Python文件
            for i, file_path in enumerate(python_files):
                if self._progress_callback:
                    progress = (i + 1) / len(python_files)
                    self._progress_callback(f"分析文件: {file_path.name}", progress * 0.9)
                
                await self._analyze_and_optimize_file(file_path)
            
            # 如果需要，生成代码结构报告
            if self._progress_callback:
                self._progress_callback("代码结构优化完成", 1.0)
                
            logger.info("代码结构优化完成")

        except Exception as e:
            logger.error(f"代码结构优化失败: {e}")
            self._current_result.errors.append(f"代码结构优化失败: {e}")
    
    async def _analyze_and_optimize_file(self, file_path: Path) -> None:
        """分析并优化单个Python文件"""
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 解析AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                logger.warning(f"文件 {file_path} 存在语法错误，跳过优化: {e}")
                return
                
            # 初始化分析结果
            analysis = {
                'long_functions': [],
                'deeply_nested_blocks': [],
                'large_classes': [],
                'repeated_code_blocks': [],
                'potential_optimizations': []
            }
            
            # 分析AST并收集问题
            await self._analyze_ast(tree, file_path, analysis)
            
            # 如果发现可优化的问题，记录到结果中
            if analysis['long_functions']:
                self._current_result.warnings.append(f"{file_path}: 发现 {len(analysis['long_functions'])} 个长函数")
                self._current_result.files_optimized += 1
                
            if analysis['deeply_nested_blocks']:
                self._current_result.warnings.append(f"{file_path}: 发现 {len(analysis['deeply_nested_blocks'])} 个深度嵌套代码块")
                
            if analysis['large_classes']:
                self._current_result.warnings.append(f"{file_path}: 发现 {len(analysis['large_classes'])} 个大型类")
                
            if analysis['potential_optimizations']:
                self._current_result.warnings.append(f"{file_path}: 建议 {len(analysis['potential_optimizations'])} 项代码优化")
                
        except Exception as e:
            logger.warning(f"分析文件 {file_path} 失败: {e}")
            self._current_result.errors.append(f"分析文件 {file_path} 失败: {e}")
    
    async def _analyze_ast(self, tree: ast.AST, file_path: Path, analysis: Dict[str, Any]) -> None:
        """分析AST并收集潜在问题"""
        try:
            # 遍历所有节点
            for node in ast.walk(tree):
                # 分析函数
                if isinstance(node, ast.FunctionDef):
                    await self._analyze_function(node, file_path, analysis)
                    
                # 分析类
                elif isinstance(node, ast.ClassDef):
                    await self._analyze_class(node, file_path, analysis)
                    
                # 分析代码块嵌套深度
                elif isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                    await self._check_nesting_depth(node, file_path, analysis)
                    
        except Exception as e:
            logger.warning(f"AST分析失败 {file_path}: {e}")
    
    async def _analyze_function(self, func_node: ast.FunctionDef, file_path: Path, analysis: Dict[str, Any]) -> None:
        """分析函数结构"""
        try:
            # 检查函数长度（行数）
            if hasattr(func_node, 'end_lineno') and func_node.end_lineno:
                func_length = func_node.end_lineno - func_node.lineno
            else:
                # 粗略估算函数长度
                func_length = 50  # 默认值，可能需要更精确的计算
                
            if func_length > 50:  # 超过50行的函数
                analysis['long_functions'].append({
                    'file': str(file_path),
                    'name': func_node.name,
                    'start_line': func_node.lineno,
                    'length': func_length,
                    'suggestion': '考虑将长函数拆分为更小的函数'
                })
                analysis['potential_optimizations'].append(f"拆分函数 {func_node.name}")
                
            # 检查函数参数数量
            if len(func_node.args.args) > 5:
                analysis['potential_optimizations'].append(f"函数 {func_node.name} 参数过多，考虑使用配置对象或字典")
                
        except Exception as e:
            logger.warning(f"分析函数失败 {func_node.name}: {e}")
    
    async def _analyze_class(self, class_node: ast.ClassDef, file_path: Path, analysis: Dict[str, Any]) -> None:
        """分析类结构"""
        try:
            # 计算类中的方法数量
            methods = [node for node in class_node.body if isinstance(node, ast.FunctionDef)]
            if len(methods) > 20:  # 超过20个方法的类
                analysis['large_classes'].append({
                    'file': str(file_path),
                    'name': class_node.name,
                    'method_count': len(methods),
                    'suggestion': '考虑将大型类拆分为多个更小的类'
                })
                analysis['potential_optimizations'].append(f"拆分类 {class_node.name}")
                
        except Exception as e:
            logger.warning(f"分析类失败 {class_node.name}: {e}")
    
    async def _check_nesting_depth(self, node: ast.AST, file_path: Path, analysis: Dict[str, Any]) -> None:
        """检查代码块嵌套深度"""
        try:
            # 计算节点的嵌套深度
            depth = self._calculate_node_depth(node)
            if depth > 4:  # 超过4层嵌套
                analysis['deeply_nested_blocks'].append({
                    'file': str(file_path),
                    'line': node.lineno,
                    'depth': depth,
                    'suggestion': '考虑重构深度嵌套的代码以提高可读性'
                })
                
        except Exception as e:
            logger.warning(f"检查嵌套深度失败: {e}")
    
    def _calculate_node_depth(self, node: ast.AST, depth: int = 0) -> int:
        """计算AST节点的嵌套深度"""
        max_child_depth = depth
        
        # 遍历所有子节点
        for child in ast.iter_child_nodes(node):
            child_depth = self._calculate_node_depth(child, depth + 1)
            max_child_depth = max(max_child_depth, child_depth)
            
        return max_child_depth

    async def _optimize_memory(self) -> None:
        """优化内存使用"""
        logger.info("开始内存优化...")

        try:
            # 强制垃圾回收
            collected = gc.collect()
            logger.info(f"垃圾回收完成，回收了 {collected} 个对象")

            # 清理导入缓存
            if hasattr(sys, 'modules'):
                modules_to_remove = []
                for module_name in sys.modules:
                    if module_name.startswith('__pycache__'):
                        modules_to_remove.append(module_name)

                for module_name in modules_to_remove:
                    del sys.modules[module_name]

                logger.info(f"清理了 {len(modules_to_remove)} 个缓存模块")

            if self._cache:
                self._cache.clear_namespace("system_optimizer")

        except Exception as e:
            logger.error(f"内存优化失败: {e}")
            self._current_result.errors.append(f"内存优化失败: {e}")

    def _should_ignore(self, path: Path) -> bool:
        """检查是否应该忽略该路径"""
        path_str = str(path)

        # 检查排除模式
        for pattern in self._optimization_config.exclude_patterns:
            if pattern in path_str:
                return True

        # 检查包含模式
        if self._optimization_config.include_patterns:
            for pattern in self._optimization_config.include_patterns:
                if pattern.replace('*', '') in path_str:
                    return False
            return True

        return False

    async def generate_report(self) -> str:
        """生成优化报告"""
        if not self._current_result:
            return "没有可用的优化结果"

        result = self._current_result

        report = f"""
FactorWeave-Quant系统优化报告
==================

优化时间: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {result.end_time.strftime('%Y-%m-%d %H:%M:%S')}
持续时间: {result.duration.total_seconds():.2f} 秒
优化级别: {result.level.value}
成功率: {result.success_rate:.2%}

优化结果:
- 扫描文件数: {result.total_files_scanned}
- 清理文件数: {result.files_cleaned}
- 优化文件数: {result.files_optimized}
- 释放空间: {result.bytes_freed / 1024 / 1024:.2f} MB
- 性能提升: {result.performance_improvement:.2%}

"""

        if result.errors:
            report += f"\n错误列表 ({len(result.errors)}个):\n"
            for error in result.errors[:10]:  # 只显示前10个错误
                report += f"- {error}\n"
            if len(result.errors) > 10:
                report += f"... 还有 {len(result.errors) - 10} 个错误\n"

        if result.warnings:
            report += f"\n警告列表 ({len(result.warnings)}个):\n"
            for warning in result.warnings[:10]:  # 只显示前10个警告
                report += f"- {warning}\n"
            if len(result.warnings) > 10:
                report += f"... 还有 {len(result.warnings) - 10} 个警告\n"

        # 性能统计
        perf_stats = self._performance_monitor.get_stats()
        if 'operations' in perf_stats:
            report += "\n性能统计:\n"
            for operation, stats in perf_stats['operations'].items():
                if 'system' in operation:
                    report += f"- {operation}: {stats['avg_time']:.3f}s (平均)\n"

        return report

    async def _save_optimization_history(self) -> None:
        """保存优化历史"""
        try:
            history_file = self._project_root / 'logs' / 'optimization_history.json'
            history_data = [asdict(result)
                            for result in self._optimization_history]

            import json
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2,
                          ensure_ascii=False, default=str)

            logger.info(f"优化历史已保存到: {history_file}")

        except Exception as e:
            logger.error(f"保存优化历史失败: {e}")

    async def get_optimization_suggestions(self) -> List[str]:
        """获取优化建议"""
        suggestions = []

        try:
            # 分析系统状态
            analysis = await self.analyze_system()

            # 基于分析结果提供建议
            if analysis['large_files']:
                suggestions.append(
                    f"发现 {len(analysis['large_files'])} 个大文件，建议检查是否可以压缩或删除")

            if analysis['import_analysis']['duplicate_imports']:
                suggestions.append("发现重复导入，建议运行导入优化")

            if analysis['cache_files']:
                suggestions.append(
                    f"发现 {len(analysis['cache_files'])} 个缓存文件，建议清理")

            if analysis['temp_files']:
                suggestions.append(
                    f"发现 {len(analysis['temp_files'])} 个临时文件，建议清理")

            if analysis['performance_issues']:
                suggestions.append(
                    f"发现 {len(analysis['performance_issues'])} 个性能问题，建议深度优化")

            if analysis['security_issues']:
                suggestions.append(
                    f"发现 {len(analysis['security_issues'])} 个安全问题，建议检查")

            if not suggestions:
                suggestions.append("系统状态良好，暂无优化建议")

        except Exception as e:
            logger.error(f"获取优化建议失败: {e}")
            suggestions.append("无法获取优化建议，请检查系统状态")

        return suggestions

    async def run_full_optimization(self, level: OptimizationLevel = OptimizationLevel.MEDIUM) -> OptimizationResult:
        """运行完整的系统优化"""
        self._ensure_not_disposed()

        logger.info(f"开始完整系统优化，级别: {level}")

        try:
            # 1. 系统分析
            analysis = await self.analyze_system()

            # 2. 执行优化
            result = await self.optimize_system(level)
            result.total_files_scanned = analysis['total_files']

            # 3. 生成报告
            report = await self.generate_report()

            # 4. 保存报告
            report_file = self._project_root / 'logs' / \
                f'optimization_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)

            logger.info(f"完整系统优化完成，报告已保存到: {report_file}")
            return result

        except Exception as e:
            logger.error(f"完整系统优化失败: {e}")
            raise


# 全局实例
_system_optimizer_service: Optional[SystemOptimizerService] = None


def get_system_optimizer_service() -> SystemOptimizerService:
    """获取系统优化器服务实例"""
    global _system_optimizer_service
    if _system_optimizer_service is None:
        _system_optimizer_service = SystemOptimizerService()
    return _system_optimizer_service


def set_system_optimizer_service(service: SystemOptimizerService) -> None:
    """设置系统优化器服务实例"""
    global _system_optimizer_service
    _system_optimizer_service = service


async def main():
    """主函数"""
    logger.info("FactorWeave-Quant 系统优化器服务")
    logger.info("====================")

    # 创建并初始化优化器服务
    optimizer_service = SystemOptimizerService()

    try:
        await optimizer_service.initialize_async()

        # 设置进度回调
        def progress_callback(message: str, progress: float):
            logger.info(f"进度: {progress:.1%} - {message}")

        def status_callback(status: str):
            logger.info(f"状态: {status}")

        optimizer_service.set_progress_callback(progress_callback)
        optimizer_service.set_status_callback(status_callback)

        # 获取优化建议
        suggestions = await optimizer_service.get_optimization_suggestions()
        logger.info("\n优化建议:")
        for suggestion in suggestions:
            logger.info(f"- {suggestion}")

        # 运行完整优化
        result = await optimizer_service.run_full_optimization()

        # 生成报告
        report = await optimizer_service.generate_report()
        logger.info("\n优化报告:")
        logger.info(report)

    except Exception as e:
        logger.info(f"优化失败: {e}")

    finally:
        await optimizer_service.dispose_async()

if __name__ == "__main__":
    asyncio.run(main())
