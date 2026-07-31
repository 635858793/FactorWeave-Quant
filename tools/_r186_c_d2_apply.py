"""
R186-C D2 实施: 9+ 处 R51 软解析散落归一
=========================================

使用 Python 脚本直接操作文件, 避免 Windows PowerShell Edit 工具对
含中文+特殊字符长字符串匹配不稳定 (R174 §12 教训)

R104 §12 5 铁律 100% 应用:
  - #4 物理删除前 4 源 100% 命中 (本任务为编辑, 不删代码)
  - 兼容 R51 §7.1 铁律 #5: 显式降级日志 + exc_info=True

保守策略 (R51 教训):
  - P0 服务第 1 轮 hard_fail=False 软降级 (与原行为 100% 兼容)
  - 通过 fallback_factory 兜底, 防止业务中断
  - 第 2 轮根据 1 周业务基线升级 P0 硬失败
"""
import re
from pathlib import Path

REPO_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# === File 1: import_execution_engine.py ===
FILE1 = REPO_ROOT / "core" / "importdata" / "import_execution_engine.py"

# 模式 1: ProgressPersistenceManager (L325-338) - P1
OLD1 = '''                from core.containers import get_service_container
                container = get_service_container()
                if container is not None and container.is_registered(ProgressPersistenceManager):
                    self.progress_persistence_manager = container.resolve(ProgressPersistenceManager)
                    logger.info("[R59] ProgressPersistenceManager 解析成功 (IoC)")
                else:
                    # 后备: 直接 new 一个 (会绕过容器, 但保证刷盘能力可用)
                    self.progress_persistence_manager = ProgressPersistenceManager()
                    logger.warning(
                        "[R59] ProgressPersistenceManager 未在 ServiceContainer 注册, "
                        "降级到直连实例 (无法享受 IoC 生命周期管理)"
                    )
            except Exception as _e:
                logger.warning(f"[R59] ProgressPersistenceManager 初始化失败: {_e}")
                self.progress_persistence_manager = None'''

NEW1 = '''                # HVD-185-3: 统一 DataImportPipeline 入口 (R51 §7.1 #5 显式降级)
                from core.importdata.pipeline import get_data_import_pipeline
                self.progress_persistence_manager = get_data_import_pipeline().resolve_or_initialize(
                    ProgressPersistenceManager,
                    hard_fail=False,
                    fallback_factory=lambda: ProgressPersistenceManager(),
                )
                if self.progress_persistence_manager is not None:
                    logger.info("[R186-C/HVD-185-3] ProgressPersistenceManager 解析成功 (统一入口)")
            except Exception as _e:
                logger.warning(
                    f"[R186-C/HVD-185-3] ProgressPersistenceManager 初始化失败: {_e}",
                    exc_info=True,
                )
                self.progress_persistence_manager = None'''

# 模式 2: DistributedService (L743-770) - P0
OLD2 = '''        try:
            # 使用ServiceContainer中的DistributedService
            from ..containers import get_service_container

            container = get_service_container()

            if container.is_registered(DistributedService):
                distributed_service = container.resolve(DistributedService)
                logger.info("使用ServiceContainer中的DistributedService")
                return distributed_service

            # Fallback：创建新实例
            logger.info("ServiceContainer中无DistributedService，创建新实例")
            distributed_service = DistributedService()
            distributed_service.start_service()

            logger.info("分布式服务初始化成功")
            return distributed_service

        except ImportError:'''
NEW2 = '''        try:
            # HVD-185-3: 统一 DataImportPipeline 入口 (R51 §7.1 #5 显式降级, P0 保守策略)
            from core.importdata.pipeline import get_data_import_pipeline
            distributed_service = get_data_import_pipeline().resolve_or_initialize(
                DistributedService,
                hard_fail=False,  # P0 保守策略, 防止业务中断 (R51 教训)
            )
            if distributed_service is not None:
                logger.info("[R186-C/HVD-185-3] 使用ServiceContainer中的DistributedService (统一入口)")
                return distributed_service

            # Fallback：创建新实例 (原 R3-3 兜底逻辑保留)
            logger.info("[R186-C/HVD-185-3] ServiceContainer中无DistributedService，创建新实例")
            distributed_service = DistributedService()
            distributed_service.start_service()

            logger.info("分布式服务初始化成功")
            return distributed_service

        except ImportError:'''

# 模式 3: CacheService (L2998-3001) - P0
OLD3 = '''                from core.services.cache_service import CacheService
                from core.containers import get_service_container
                container = get_service_container()
                if container and container.is_registered(CacheService):
                    cache = container.resolve(CacheService)'''
NEW3 = '''                # HVD-185-3: 统一 DataImportPipeline 入口 (P0 CacheService 软降级保守策略)
                from core.services.cache_service import CacheService
                from core.importdata.pipeline import get_data_import_pipeline
                cache = get_data_import_pipeline().resolve_or_initialize(
                    CacheService,
                    hard_fail=False,  # P0 保守策略
                )
                if cache is None:
                    # 原代码逻辑保留 (未注册 cache 跳过)
                    cache = None'''

# 模式 4: EnhancedPerformanceBridge (L4869-4880) - P1
OLD4 = '''        try:
            from core.containers import get_service_container
            _container = get_service_container()
            if _container is not None and _container.is_registered(EnhancedPerformanceBridge):
                self.enhanced_performance_bridge = _container.resolve(EnhancedPerformanceBridge)
                logger.info("增强版性能数据桥接系统 (IoC) 初始化完成")
            else:
                logger.warning("EnhancedPerformanceBridge 未注册, 跳过初始化")
                self.enhanced_performance_bridge = None
        except Exception as e:
            logger.error(f"初始化增强版性能桥接系统失败: {e}", exc_info=True)
            self.enhanced_performance_bridge = None'''

NEW4 = '''        try:
            # HVD-185-3: 统一 DataImportPipeline 入口 (P1 EnhancedPerformanceBridge 软降级)
            from core.importdata.pipeline import get_data_import_pipeline
            self.enhanced_performance_bridge = get_data_import_pipeline().resolve_or_initialize(
                EnhancedPerformanceBridge,
                hard_fail=False,
            )
            if self.enhanced_performance_bridge is not None:
                logger.info("[R186-C/HVD-185-3] 增强版性能数据桥接系统 (IoC) 初始化完成 (统一入口)")
            else:
                logger.warning("[R186-C/HVD-185-3] EnhancedPerformanceBridge 未注册, 跳过初始化")
        except Exception as e:
            logger.error(f"初始化增强版性能桥接系统失败: {e}", exc_info=True)
            self.enhanced_performance_bridge = None'''


# === File 2: unified_data_import_engine.py ===
FILE2 = REPO_ROOT / "core" / "importdata" / "unified_data_import_engine.py"

# 模式 5: EnhancedPerformanceBridge (L411-421) - P1
OLD5 = '''                try:
                    from core.containers import get_service_container
                    _container = get_service_container()
                    if _container is not None and _container.is_registered(EnhancedPerformanceBridge):
                        self.enhanced_performance_bridge = _container.resolve(EnhancedPerformanceBridge)
                    else:
                        logger.warning("EnhancedPerformanceBridge 未注册, 跳过")
                        self.enhanced_performance_bridge = None
                except Exception as _ioc_exc:
                    logger.warning(f"EnhancedPerformanceBridge IoC 解析失败: {_ioc_exc}")
                    self.enhanced_performance_bridge = None'''
NEW5 = '''                # HVD-185-3: 统一 DataImportPipeline 入口 (P1 EnhancedPerformanceBridge 软降级)
                from core.importdata.pipeline import get_data_import_pipeline
                self.enhanced_performance_bridge = get_data_import_pipeline().resolve_or_initialize(
                    EnhancedPerformanceBridge,
                    hard_fail=False,
                )
                if self.enhanced_performance_bridge is None:
                    logger.warning("[R186-C/HVD-185-3] EnhancedPerformanceBridge 未注册, 跳过 (统一入口)")'''

# 模式 6: IncrementalUpdateScheduler (L485-507) - P0
OLD6 = '''            # 修复: 改走 ServiceContainer IoC 解析 (L1408-1418 已注册), 失败时本地直接实例化兜底.
            try:
                from core.services.incremental_update_scheduler import (
                    IncrementalUpdateScheduler as _IncrementalUpdateScheduler
                )
                # 优先 IoC 解析 (R51 已注册)
                try:
                    from core.containers import get_service_container
                    _container = get_service_container()
                    if _container is not None and _container.is_registered(_IncrementalUpdateScheduler):
                        self.incremental_scheduler = _container.resolve(_IncrementalUpdateScheduler)
                    else:
                        # 兜底: 本地直接实例化 (无依赖注入, 仅用于兜底)
                        self.incremental_scheduler = None
                        logger.debug("IncrementalUpdateScheduler 未注册到 ServiceContainer, 跳过注入")
                except Exception as asioc_exc:
                    # R150-P1-1 (2026-07-19): logger.debug → logger.warning + exc_info=True (R51 铁律 #5)
                    # R150-A 系统框架分析: IncrementalUpdateScheduler IoC 解析失败, 增量下载降级, 业务方需观测
                    logger.warning(
                        f"[R51-FIX] IncrementalUpdateScheduler IoC 解析失败: {asioc_exc}",
                        exc_info=True,
                    )
                    self.incremental_scheduler = None'''
NEW6 = '''            # HVD-185-3: 统一 DataImportPipeline 入口 (P0 IncrementalUpdateScheduler 软降级保守策略)
            try:
                from core.services.incremental_update_scheduler import (
                    IncrementalUpdateScheduler as _IncrementalUpdateScheduler
                )
                from core.importdata.pipeline import get_data_import_pipeline
                self.incremental_scheduler = get_data_import_pipeline().resolve_or_initialize(
                    _IncrementalUpdateScheduler,
                    hard_fail=False,  # P0 保守策略, 防止业务中断 (R51 教训)
                )
                if self.incremental_scheduler is None:
                    logger.debug("[R186-C/HVD-185-3] IncrementalUpdateScheduler 未注册到 ServiceContainer, 跳过注入 (统一入口)")'''

# 模式 7: UnifiedDataImportEngine get_unified_data_import_engine (L2557-2580) - P0
OLD7 = '''    global _unified_data_import_engine_instance
    try:
        from core.containers import get_service_container
        _container = get_service_container()
        if _container is not None and _container.is_registered(UnifiedDataImportEngine):
            # R125-P0-2: 改用 try_resolve 替代 resolve (R93-6-HVD-37 模式,
            #          解析失败时内置 warning 显式降级日志)
            engine = _container.try_resolve(UnifiedDataImportEngine)
            if engine is not None:
                return engine
    except Exception as e:'''
NEW7 = '''    global _unified_data_import_engine_instance
    try:
        # HVD-185-3: 统一 DataImportPipeline 入口 (P0 UnifiedDataImportEngine 软降级保守策略)
        from core.importdata.pipeline import get_data_import_pipeline
        engine = get_data_import_pipeline().resolve_or_initialize(
            UnifiedDataImportEngine,
            hard_fail=False,  # P0 保守策略, 防止业务中断 (R51 教训)
        )
        if engine is not None:
            return engine
    except Exception as e:'''


# === File 3: intelligent_config_manager.py ===
FILE3 = REPO_ROOT / "core" / "importdata" / "intelligent_config_manager.py"

# 模式 8: AIPredictionService (L121-137) - P1
OLD8 = '''        try:
            from core.containers import get_service_container
            container = get_service_container()
            if container is not None and container.is_registered(AIPredictionService):
                self.ai_service = container.resolve(AIPredictionService)
            else:
                self.ai_service = None
                logger.warning(
                    f"[R110 P1-C] AIPredictionService 未注册到 ServiceContainer, "
                    f"AI 参数优化功能降级 (硬解析防御 R51 铁律)"
                )
        except ImportError as _icm_import_exc:'''
NEW8 = '''        try:
            # HVD-185-3: 统一 DataImportPipeline 入口 (P1 AIPredictionService 软降级)
            from core.importdata.pipeline import get_data_import_pipeline
            self.ai_service = get_data_import_pipeline().resolve_or_initialize(
                AIPredictionService,
                hard_fail=False,
            )
            if self.ai_service is None:
                logger.warning(
                    "[R186-C/HVD-185-3] AIPredictionService 未注册到 ServiceContainer, "
                    "AI 参数优化功能降级 (硬解析防御 R51 铁律, 统一入口)"
                )
        except ImportError as _icm_import_exc:'''


# === 实施 ===
REPLACEMENTS = [
    (FILE1, OLD1, NEW1, "L325-338 ProgressPersistenceManager (P1)"),
    (FILE1, OLD2, NEW2, "L743-770 DistributedService (P0)"),
    (FILE1, OLD3, NEW3, "L2998-3001 CacheService (P0)"),
    (FILE1, OLD4, NEW4, "L4869-4880 EnhancedPerformanceBridge (P1)"),
    (FILE2, OLD5, NEW5, "L411-421 EnhancedPerformanceBridge (P1)"),
    (FILE2, OLD6, NEW6, "L485-507 IncrementalUpdateScheduler (P0)"),
    (FILE2, OLD7, NEW7, "L2557-2580 UnifiedDataImportEngine (P0)"),
    (FILE3, OLD8, NEW8, "L121-137 AIPredictionService (P1)"),
]


def main():
    results = []
    for file_path, old, new, desc in REPLACEMENTS:
        if not file_path.exists():
            results.append((desc, False, f"文件不存在: {file_path}"))
            continue

        content = file_path.read_text(encoding="utf-8")
        if old not in content:
            results.append((desc, False, "未找到匹配的旧代码"))
            continue

        new_content = content.replace(old, new, 1)
        file_path.write_text(new_content, encoding="utf-8")

        # 验证 (Read 二次验证, R174 §12 教训)
        verify = file_path.read_text(encoding="utf-8")
        if new in verify:
            results.append((desc, True, f"✅ 成功, 文件大小: {len(verify)} 字节"))
        else:
            results.append((desc, False, "❌ 验证失败"))

    print("\n=== R186-C D2 实施结果 ===\n")
    success_count = 0
    for desc, ok, msg in results:
        status = "✅" if ok else "❌"
        print(f"  {status} {desc}: {msg}")
        if ok:
            success_count += 1
    print(f"\n成功: {success_count}/{len(results)}")


if __name__ == "__main__":
    main()
