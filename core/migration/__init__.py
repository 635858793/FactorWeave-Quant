"""
FactorWeave-Quant 数据源迁移模块

提供传统数据源迁移的工具和接口，包括：
- 依赖关系分析
- 迁移监控和日志记录
- 资产类型迁移

注意：传统数据源已迁移到TET+Plugin架构，此模块主要用于历史依赖检查和迁移监控。
"""

try:
    from .dependency_analyzer import (
        DependencyAnalyzer,
        DependencyType,
        ImpactLevel,
        DependencyReference,
        FileAnalysisResult,
        DependencyGraph,
        analyze_project_dependencies,
    )
except Exception:
    DependencyAnalyzer = None
    DependencyType = None
    ImpactLevel = None
    DependencyReference = None
    FileAnalysisResult = None
    DependencyGraph = None
    analyze_project_dependencies = None

try:
    from .migration_monitor import (
        MigrationMonitor,
        MigrationPhase,
        MigrationStatus,
        TaskStatus,
        MigrationTask,
        MigrationEvent,
        get_migration_monitor,
        initialize_migration_monitor,
        log_migration_info,
        log_migration_warning,
        log_migration_error,
    )
except Exception:
    MigrationMonitor = None
    MigrationPhase = None
    MigrationStatus = None
    TaskStatus = None
    MigrationTask = None
    MigrationEvent = None
    get_migration_monitor = None
    initialize_migration_monitor = None
    log_migration_info = None
    log_migration_warning = None
    log_migration_error = None

__all__ = [
    'DependencyAnalyzer',
    'DependencyType',
    'ImpactLevel',
    'DependencyReference',
    'FileAnalysisResult',
    'DependencyGraph',
    'analyze_project_dependencies',
    'MigrationMonitor',
    'MigrationPhase',
    'MigrationStatus',
    'TaskStatus',
    'MigrationTask',
    'MigrationEvent',
    'get_migration_monitor',
    'initialize_migration_monitor',
    'log_migration_info',
    'log_migration_warning',
    'log_migration_error',
]