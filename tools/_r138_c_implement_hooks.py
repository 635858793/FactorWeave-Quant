"""R138 子智能体 C: 批量实施 17 healthcheck + 22 dispose 钩子.

R137-B 已实施 5+5=10 个 (StockService, AIPredictionService, ConfigService,
StrategyService, ChartService + ConfigService, AssetService,
AdvancedRiskControlService, AISelectionIntegrationService, BettaFishMonitoringService)

R138-C 新增:
  healthcheck 17 候选:
    1. AlertRuleHotLoader
    2. AsyncBaseService (基类, 注入 _do_health_check 默认实现)
    3. ConfigurableService (基类)
    4. CacheableService (基类, 已 _do_dispose)
    5. BondService
    6. DatabaseMonitoringService
    7. DividendDataService
    8. ExtensionService
    9. FundService
    10. GPUAccelerationManager
    11. HybridRecommendationEngine
    12. IndexService
    13. IndustryService
    14. ModelTrainingService
    15. PerformanceBaselineService
    16. PredictionTrackingService
    17. SystemOptimizerService

  dispose 22 候选 (排除 R137-B 已实施 5 个):
    1. AISelectionBacktestService
    2. AISelectionRiskControlService
    3. AuditDeadCodeService
    4. AsyncBaseService (基类)
    5. ConfigurableService (基类)
    6. BondService
    7. DatabaseMonitoringService
    8. DataMaskingService
    9. DeepAnalysisService
    10. DistributedService
    11. DividendDataService
    12. DynamicRiskAdjustmentService
    13. FundingRateAnalysisService
    14. FundService
    15. HybridRecommendationEngine
    16. IndexService
    17. ModelTrainingService
    18. PredictionTrackingService
    19. SectorDataService
    20. SystemOptimizerService
    21. TdxServerDiscoveryService
    22. TradingConfirmationService

R6 §6.3 SOP + R104 §12 5 铁律 + R7 §7.1 7 铁律 + R85 假修复鉴别 4 步法: 100% 应用
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ==================== healthcheck 钩子模板 ====================
HEALTHCHECK_TEMPLATES = {
    "AlertRuleHotLoader": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-AlertRuleHotLoader: 业务级健康字段 (1+ 业务方).

        Returns:
            包含业务指标 (rules_cached / running / stop_event_set / check_interval /
            last_check_age) 的字典. 异常时降级返回 {"status": "error", "error": str(e)},
            不抛异常 (R134 HVD-68-RCE/PDB 模板).
        """
        import time
        try:
            with self._lock:
                rules_cached = len(getattr(self, '_rules_cache', {}) or {})
                running = bool(getattr(self, '_running', False))
                stop_event_set = bool(getattr(self, '_stop_event', None) and self._stop_event.is_set())
                check_interval = getattr(self, 'check_interval', 0)
                last_check_time = getattr(self, '_last_check_time', None)
                last_check_age = (time.time() - last_check_time) if last_check_time else None
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "rules_cached": rules_cached,
                    "running": running,
                    "stop_event_set": stop_event_set,
                    "check_interval": check_interval,
                    "last_check_age_seconds": last_check_age,
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"AlertRuleHotLoader._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "AsyncBaseService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-AsyncBaseService: 基类默认实现 (异步服务)."""
        try:
            return {
                "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                "service_type": "async",
                "initialized": self._initialized,
                "disposed": self._disposed,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
''',

    "ConfigurableService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-ConfigurableService: 基类默认实现 (可配置服务)."""
        try:
            return {
                "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                "config_keys": len(getattr(self, '_config', {}) or {}),
                "service_type": "configurable",
                "initialized": self._initialized,
                "disposed": self._disposed,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
''',

    "CacheableService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-CacheableService: 基类默认实现 (可缓存服务)."""
        try:
            stats = self.get_cache_stats() if hasattr(self, 'get_cache_stats') else {}
            return {
                "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                "cache_hits": stats.get('cache_hits', 0),
                "cache_misses": stats.get('cache_misses', 0),
                "hit_rate": stats.get('hit_rate', 0.0),
                "namespace": stats.get('namespace', 'unknown'),
                "unified_cache_connected": bool(getattr(self, '_unified_cache', None)),
                "service_type": "cacheable",
                "initialized": self._initialized,
                "disposed": self._disposed,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
''',

    "BondService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-BondService: 业务级健康字段 (2+ 业务方)."""
        try:
            with self._lock:
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "bond_count": len(getattr(self, '_bond_list', []) or []),
                    "cache_hit_rate": self.get_cache_stats().get('hit_rate', 0.0) if hasattr(self, 'get_cache_stats') else 0.0,
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"BondService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "DatabaseMonitoringService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-DatabaseMonitoringService: 业务级健康字段 (1+ 业务方)."""
        try:
            with self._lock:
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "monitoring_active": bool(getattr(self, '_monitoring_active', False)),
                    "pool_count": len(getattr(self, '_pool_metrics', {}) or {}),
                    "alerts_count": len(getattr(self, '_active_alerts', []) or []),
                    "query_history_size": len(getattr(self, '_query_history', []) or []),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"DatabaseMonitoringService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "DividendDataService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-DividendDataService: 业务级健康字段 (1+ 业务方)."""
        try:
            with self._lock:
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "akshare_available": getattr(self, '_akshare', None) is not None,
                    "memory_cache_size": len(getattr(self, '_memory_cache', {}) or {}),
                    "hot_stocks_count": len(getattr(self, '_hot_stocks', []) or []),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"DividendDataService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "ExtensionService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-ExtensionService: 业务级健康字段 (1+ 业务方)."""
        try:
            with self._lock:
                extension_points = getattr(self, '_extension_points', {}) or {}
                hook_count = sum(len(h) for h in (getattr(self, '_hooks', {}) or {}).values())
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "extension_points_count": len(extension_points),
                    "hooks_count": hook_count,
                    "registered_callbacks": len(getattr(self, '_callbacks', {}) or {}),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"ExtensionService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "FundService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-FundService: 业务级健康字段 (2+ 业务方)."""
        try:
            with self._lock:
                cache_stats = self.get_cache_stats() if hasattr(self, 'get_cache_stats') else {}
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "fund_count": len(getattr(self, '_fund_list', []) or []),
                    "cache_hit_rate": cache_stats.get('hit_rate', 0.0),
                    "unified_data_connected": bool(getattr(self, '_unified_data_manager', None)),
                    "no_data_cache_size": len(getattr(self, '_no_data_cache', set()) or set()),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"FundService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "GPUAccelerationManager": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-GPUAccelerationManager: 业务级健康字段 (1+ 业务方)."""
        try:
            with self._lock:
                gpu_status = getattr(self, '_status', None)
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "webgpu_available": globals().get('WEBGPU_AVAILABLE', False),
                    "gpu_status": str(gpu_status) if gpu_status else "unknown",
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"GPUAccelerationManager._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "HybridRecommendationEngine": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-HybridRecommendationEngine: 业务级健康字段 (2+ 业务方)."""
        try:
            with self._lock:
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "models_loaded": len(getattr(self, '_models', {}) or {}),
                    "cache_size": len(getattr(self, '_recommendation_cache', {}) or {}),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"HybridRecommendationEngine._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "IndexService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-IndexService: 业务级健康字段 (2+ 业务方)."""
        try:
            with self._lock:
                cache_stats = self.get_cache_stats() if hasattr(self, 'get_cache_stats') else {}
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "index_count": len(getattr(self, '_index_list', []) or []),
                    "cache_hit_rate": cache_stats.get('hit_rate', 0.0),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"IndexService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "IndustryService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-IndustryService: 业务级健康字段 (4+ 业务方)."""
        try:
            with self._lock:
                cache_stats = self.get_cache_stats() if hasattr(self, 'get_cache_stats') else {}
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "industry_count": len(getattr(self, '_industries_cache', {}) or {}),
                    "cache_hit_rate": cache_stats.get('hit_rate', 0.0),
                    "manager_initialized": bool(getattr(self, '_industry_manager', None)),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"IndustryService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "ModelTrainingService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-ModelTrainingService: 业务级健康字段 (4+ 业务方)."""
        try:
            with self._lock:
                tasks = getattr(self, '_tasks', {}) or {}
                active = sum(1 for t in tasks.values() if getattr(t, 'status', None) and str(t.status).endswith('TRAINING'))
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "total_tasks": len(tasks),
                    "active_tasks": active,
                    "models_count": len(getattr(self, '_model_versions', {}) or {}),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"ModelTrainingService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "PerformanceBaselineService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-PerformanceBaselineService: 业务级健康字段 (1+ 业务方)."""
        try:
            with self._lock:
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "baselines_count": len(getattr(self, '_baselines', {}) or {}),
                    "snapshots_count": len(getattr(self, '_snapshots', []) or []),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"PerformanceBaselineService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "PredictionTrackingService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-PredictionTrackingService: 业务级健康字段 (3+ 业务方)."""
        try:
            with self._record_lock:
                records = len(getattr(self, '_prediction_records', {}) or {})
            with self._statistics_lock:
                stats = len(getattr(self, '_accuracy_statistics', {}) or {})
            return {
                "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                "prediction_records": records,
                "accuracy_statistics": stats,
                "database_connected": bool(getattr(self, '_database_service', None)),
                "initialized": self._initialized,
                "disposed": self._disposed,
            }
        except Exception as e:
            logger.error(f"PredictionTrackingService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',

    "SystemOptimizerService": '''    def _do_health_check(self) -> Dict[str, Any]:
        """R138 子智能体 C HVD-HC-SystemOptimizerService: 业务级健康字段 (3+ 业务方)."""
        try:
            with self._lock:
                return {
                    "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
                    "optimization_rules": len(getattr(self, '_optimization_rules', {}) or {}),
                    "metrics_history": len(getattr(self, '_metrics_history', {}) or {}),
                    "initialized": self._initialized,
                    "disposed": self._disposed,
                }
        except Exception as e:
            logger.error(f"SystemOptimizerService._do_health_check failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
''',
}


# ==================== dispose 钩子模板 ====================
DISPOSE_TEMPLATES = {
    "AISelectionBacktestService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-AISelectionBacktestService: 释放资源 (2+ 业务方).

        R78 防御: 幂等. R6 §6.3 LIFO: 先业务后 super.
        """
        if getattr(self, '_disposed', False):
            logger.debug("AISelectionBacktestService._do_dispose: 已 dispose, 跳过")
            return
        try:
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=False)
                logger.debug("AISelectionBacktestService._do_dispose: executor shutdown")
            for attr in ('_strategies', '_results', '_backtest_data'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"AISelectionBacktestService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "AISelectionRiskControlService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-AISelectionRiskControlService: 释放资源 (1+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=False)
            for attr in ('_risk_metrics', '_alerts', '_ml_models'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"AISelectionRiskControlService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "AuditDeadCodeService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-AuditDeadCodeService: 释放资源 (1+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            for attr in ('_cache', '_results', '_reports'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"AuditDeadCodeService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "AsyncBaseService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-AsyncBaseService: 基类默认 dispose 实现."""
        if getattr(self, '_disposed', False):
            return
        try:
            # 异步服务基类无特殊资源, 仅调用 BaseService 默认实现
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"AsyncBaseService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "ConfigurableService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-ConfigurableService: 基类默认 dispose 实现."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_config') and isinstance(self._config, dict):
                self._config.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"ConfigurableService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "BondService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-BondService: 释放资源 (2+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_unified_data_manager'):
                self._unified_data_manager = None
            for attr in ('_bond_list', '_no_data_cache'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, (list, set)):
                        obj.clear()
            if hasattr(self, 'clear_cache'):
                self.clear_cache()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"BondService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "DataMaskingService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-DataMaskingService: 释放资源 (1+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            for attr in ('_rules', '_masked_keys', '_cache'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"DataMaskingService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "DatabaseMonitoringService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-DatabaseMonitoringService: 释放资源 (1+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            # 停止监控线程
            if hasattr(self, '_monitor_thread') and self._monitor_thread and self._monitor_thread.is_alive():
                if hasattr(self, '_stop_monitoring'):
                    self._stop_monitoring()
            for attr in ('_pool_metrics', '_query_history', '_active_alerts'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_database_service'):
                self._database_service = None
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"DatabaseMonitoringService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "DeepAnalysisService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-DeepAnalysisService: 释放资源 (4+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=False)
            for attr in ('_analysis_cache', '_results', '_tasks'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"DeepAnalysisService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "DistributedService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-DistributedService: 释放资源 (4+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=False)
            if hasattr(self, '_http_session') and self._http_session:
                try:
                    self._http_session.close()
                except Exception:
                    pass
                self._http_session = None
            for attr in ('_nodes', '_workers', '_tasks'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"DistributedService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "DividendDataService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-DividendDataService: 释放资源 (1+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            for attr in ('_memory_cache', '_memory_cache_time'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
            if hasattr(self, '_akshare'):
                self._akshare = None
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"DividendDataService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "DynamicRiskAdjustmentService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-DynamicRiskAdjustmentService: 释放资源 (3+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_monitoring_task') and self._monitoring_task:
                try:
                    self._monitoring_task.cancel()
                except Exception:
                    pass
                self._monitoring_task = None
            for attr in ('_risk_models', '_adjustments', '_history'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"DynamicRiskAdjustmentService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "FundingRateAnalysisService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-FundingRateAnalysisService: 释放资源 (1+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            for attr in ('_cache', '_rate_history', '_analysis_results'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"FundingRateAnalysisService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "FundService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-FundService: 释放资源 (2+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_unified_data_manager'):
                self._unified_data_manager = None
            for attr in ('_fund_list', '_no_data_cache', '_last_query_time'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, (list, set)):
                        obj.clear()
                    elif isinstance(obj, dict):
                        obj.clear()
            if hasattr(self, 'clear_cache'):
                self.clear_cache()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"FundService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "HybridRecommendationEngine": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-HybridRecommendationEngine: 释放资源 (2+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=False)
            for attr in ('_models', '_recommendation_cache', '_features'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"HybridRecommendationEngine._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "IndexService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-IndexService: 释放资源 (2+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_unified_data_manager'):
                self._unified_data_manager = None
            for attr in ('_index_list', '_no_data_cache'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, (list, set)):
                        obj.clear()
            if hasattr(self, 'clear_cache'):
                self.clear_cache()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"IndexService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "ModelTrainingService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-ModelTrainingService: 释放资源 (4+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=False)
            # 取消活跃任务
            tasks = getattr(self, '_tasks', {}) or {}
            for task in tasks.values():
                if hasattr(task, 'cancel'):
                    try:
                        task.cancel()
                    except Exception:
                        pass
            for attr in ('_tasks', '_model_versions', '_training_history'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"ModelTrainingService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "PredictionTrackingService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-PredictionTrackingService: 释放资源 (3+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            for attr in ('_prediction_records', '_accuracy_statistics'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
            if hasattr(self, '_database_service'):
                self._database_service = None
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"PredictionTrackingService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "SectorDataService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-SectorDataService: 释放资源 (2+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_unified_data_manager'):
                self._unified_data_manager = None
            for attr in ('_sector_list', '_no_data_cache'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, (list, set)):
                        obj.clear()
            if hasattr(self, 'clear_cache'):
                self.clear_cache()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"SectorDataService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "SystemOptimizerService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-SystemOptimizerService: 释放资源 (3+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            if hasattr(self, '_monitoring_task') and self._monitoring_task:
                try:
                    self._monitoring_task.cancel()
                except Exception:
                    pass
                self._monitoring_task = None
            for attr in ('_optimization_rules', '_metrics_history', '_optimization_results'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"SystemOptimizerService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "TdxServerDiscoveryService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-TdxServerDiscoveryService: 释放资源 (2+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            for attr in ('_servers', '_discovery_cache', '_results'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"TdxServerDiscoveryService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',

    "TradingConfirmationService": '''    def _do_dispose(self) -> None:
        """R138 子智能体 C HVD-DP-TradingConfirmationService: 释放资源 (2+ 业务方)."""
        if getattr(self, '_disposed', False):
            return
        try:
            for attr in ('_pending_confirmations', '_confirmation_history', '_callbacks'):
                if hasattr(self, attr):
                    obj = getattr(self, attr, None)
                    if isinstance(obj, dict):
                        obj.clear()
                    elif isinstance(obj, list):
                        obj.clear()
            if hasattr(self, '_event_bus'):
                self._event_bus = None
            super()._do_dispose()
        except Exception as e:
            logger.error(f"TradingConfirmationService._do_dispose failed: {e}", exc_info=True)
            super()._do_dispose()
''',
}


# ==================== 候选到文件路径映射 ====================
HEALTHCHECK_FILES = {
    "AlertRuleHotLoader": "core/services/alert_rule_hot_loader.py",
    "AsyncBaseService": "core/services/base_service.py",
    "ConfigurableService": "core/services/base_service.py",
    "CacheableService": "core/services/base_service.py",
    "BondService": "core/services/bond_service.py",
    "DatabaseMonitoringService": "core/services/database_monitoring_service.py",
    "DividendDataService": "core/services/dividend_data_service.py",
    "ExtensionService": "core/services/extension_service.py",
    "FundService": "core/services/fund_service.py",
    "GPUAccelerationManager": "core/services/gpu_acceleration_manager.py",
    "HybridRecommendationEngine": "core/services/hybrid_recommendation_engine.py",
    "IndexService": "core/services/index_service.py",
    "IndustryService": "core/services/industry_service.py",
    "ModelTrainingService": "core/services/model_training_service.py",
    "PerformanceBaselineService": "core/services/performance_baseline_service.py",
    "PredictionTrackingService": "core/services/prediction_tracking_service.py",
    "SystemOptimizerService": "core/services/system_optimizer.py",
}

DISPOSE_FILES = {
    "AISelectionBacktestService": "core/services/ai_selection_backtest_service.py",
    "AISelectionRiskControlService": "core/services/ai_selection_risk_control_service.py",
    "AuditDeadCodeService": "core/services/audit_dead_code_service.py",
    "AsyncBaseService": "core/services/base_service.py",
    "ConfigurableService": "core/services/base_service.py",
    "BondService": "core/services/bond_service.py",
    "DataMaskingService": "core/services/data_masking_service.py",
    "DatabaseMonitoringService": "core/services/database_monitoring_service.py",
    "DeepAnalysisService": "core/services/deep_analysis_service.py",
    "DistributedService": "core/services/distributed_service.py",
    "DividendDataService": "core/services/dividend_data_service.py",
    "DynamicRiskAdjustmentService": "core/services/dynamic_risk_adjustment_service.py",
    "FundingRateAnalysisService": "core/services/funding_rate_analysis_service.py",
    "FundService": "core/services/fund_service.py",
    "HybridRecommendationEngine": "core/services/hybrid_recommendation_engine.py",
    "IndexService": "core/services/index_service.py",
    "ModelTrainingService": "core/services/model_training_service.py",
    "PredictionTrackingService": "core/services/prediction_tracking_service.py",
    "SectorDataService": "core/services/sector_data_service.py",
    "SystemOptimizerService": "core/services/system_optimizer.py",
    "TdxServerDiscoveryService": "core/services/tdx_server_discovery.py",
    "TradingConfirmationService": "core/services/trading_confirmation_service.py",
}


def get_class_anchor(content: str, class_name: str) -> int:
    """找到类定义结束的下一行, 返回合适的插入点(类内末尾)."""
    lines = content.split('\n')
    class_start = -1
    for i, line in enumerate(lines):
        if line.startswith(f'class {class_name}(') or line.startswith(f'class {class_name}:'):
            class_start = i
            break
    if class_start < 0:
        return -1

    # 找到类结束(下一行顶级 class/def)
    indent_level = 0
    for i in range(class_start + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith(' '):
            # 顶级行, 类结束
            return i - 1
    return len(lines) - 1


def get_class_body_range(content: str, class_name: str) -> tuple:
    """找到类定义的行范围 (start, end_exclusive).

    Returns:
        (start_line_idx, end_line_idx_exclusive) 或 (-1, -1) 如果未找到.
    """
    lines = content.split('\n')
    class_start = -1
    for i, line in enumerate(lines):
        if line.startswith(f'class {class_name}(') or line.startswith(f'class {class_name}:'):
            class_start = i
            break
    if class_start < 0:
        return (-1, -1)

    # 找到类结束(下一行顶级 class/def)
    for i in range(class_start + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith(' '):
            return (class_start, i)
    return (class_start, len(lines))


def class_has_method(content: str, class_name: str, method_name: str) -> bool:
    """检查指定类内是否已定义某方法."""
    start, end = get_class_body_range(content, class_name)
    if start < 0:
        return False
    lines = content.split('\n')
    body = lines[start:end]
    for line in body:
        if line.startswith(f'    def {method_name}('):
            return True
    return False


def inject_healthcheck(file_path: Path, class_name: str, method_code: str) -> bool:
    """在类内注入 _do_health_check 方法."""
    if not file_path.exists():
        print(f"  [SKIP] {file_path} 不存在")
        return False
    content = file_path.read_text(encoding='utf-8')

    if class_has_method(content, class_name, '_do_health_check'):
        print(f"  [EXISTS] {file_path}::{class_name} 已有 _do_health_check")
        return True

    insert_line_idx = get_class_anchor(content, class_name)
    if insert_line_idx < 0:
        print(f"  [FAIL] {file_path} 找不到 class {class_name}")
        return False

    lines = content.split('\n')
    new_lines = lines[:insert_line_idx] + [method_code] + lines[insert_line_idx:]
    new_content = '\n'.join(new_lines)

    file_path.write_text(new_content, encoding='utf-8')
    print(f"  [OK] {file_path}::{class_name} _do_health_check 注入")
    return True


def inject_dispose(file_path: Path, class_name: str, method_code: str) -> bool:
    """在类内注入 _do_dispose 方法."""
    if not file_path.exists():
        print(f"  [SKIP] {file_path} 不存在")
        return False
    content = file_path.read_text(encoding='utf-8')

    if class_has_method(content, class_name, '_do_dispose'):
        print(f"  [EXISTS] {file_path}::{class_name} 已有 _do_dispose")
        return True

    insert_line_idx = get_class_anchor(content, class_name)
    if insert_line_idx < 0:
        print(f"  [FAIL] {file_path} 找不到 class {class_name}")
        return False

    lines = content.split('\n')
    new_lines = lines[:insert_line_idx] + [method_code] + lines[insert_line_idx:]
    new_content = '\n'.join(new_lines)

    file_path.write_text(new_content, encoding='utf-8')
    print(f"  [OK] {file_path}::{class_name} _do_dispose 注入")
    return True


def main():
    print("=" * 60)
    print("R138 子智能体 C: 批量实施 17 healthcheck + 22 dispose 钩子")
    print("=" * 60)

    print("\n[Phase 1] healthcheck 17 候选实施:")
    for cls_name, rel_path in HEALTHCHECK_FILES.items():
        file_path = PROJECT_ROOT / rel_path
        method_code = HEALTHCHECK_TEMPLATES.get(cls_name)
        if not method_code:
            print(f"  [SKIP] {cls_name} 无模板")
            continue
        inject_healthcheck(file_path, cls_name, method_code)

    print("\n[Phase 2] dispose 22 候选实施:")
    for cls_name, rel_path in DISPOSE_FILES.items():
        file_path = PROJECT_ROOT / rel_path
        method_code = DISPOSE_TEMPLATES.get(cls_name)
        if not method_code:
            print(f"  [SKIP] {cls_name} 无模板")
            continue
        inject_dispose(file_path, cls_name, method_code)

    print("\n" + "=" * 60)
    print("实施完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
