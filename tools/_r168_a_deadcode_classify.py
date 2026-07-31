"""R168-A: properly classify business vs test callsites for each candidate service"""
import os
import re

CANDIDATES = [
    'AssetFallbackLoader', 'DataMaskingService', 'PluginDatabaseService',
    'DistributedService', 'FundingRateAnalysisService',
    'RecommendationExplanationGenerator', 'LegacyDataSourceAdapter',
    'SectorFundFlowService', 'AutoMLOptimizer', 'StreamingFeatureEngine',
    'AlertRuleHotLoader', 'FaultToleranceManager', 'LifecycleService',
    'EnvironmentService', 'AlertRuleEngine', 'AlertEventHandler',
    'AlertDeduplicationService', 'MarketCapCalculator', 'UnifiedCacheProvider',
    'PluginHotReloader', 'PluginVersionManager',
    'AssetService', 'SectorDataService',
    'DistributedHTTPBridge', 'EnvironmentService', 'FaultToleranceManager',
    'NotificationService', 'SectorFundFlowService',
    'StrategyStatusMonitor', 'TdxServerDiscoveryService',
    'TensorFlowGPUManager', 'UnifiedChartService', 'UnifiedDataManager',
    'UnifiedDataQualityMonitor', 'UniPluginDataManager',
    'RecommendationModelTrainer', 'PredictionTrackingService',
    'PerformanceBaselineService', 'QualityReportGenerator',
    'RealtimeComputeEngine', 'RecommendationExplanationGenerator',
    'SmartRecommendationEngine', 'SystemOptimizerService',
    'AIExplainabilityService', 'AIPredictionService',
    'AISelectionBacktestService', 'AISelectionIntegrationService',
    'AISelectionRiskControlService', 'AIStockSelectorService',
    'AutoTrainingPipeline', 'BacktestResultManager', 'TradingService',
    'TrainingDataCollector',
    'PluginService', 'NetworkService', 'SecurityService',
    'AnalysisService', 'IndustryService', 'CacheService', 'DataService',
    'ChartService', 'ConfigService', 'DatabaseService',
    'StockService', 'FundService', 'BondService', 'IndexService',
    'MarketService', 'ExtensionService', 'NotificationService',
    'ExternalAlertManager', 'BettaFishErrorHandler', 'ErrorHandler',
    'MacroEconomicDataManager', 'FundamentalDataManager', 'GPUAccelerationManager',
    'HybridRecommendationEngine', 'IntegratedSignalAggregatorService',
    'TradingConfirmationService', 'BettaFishMonitoringService',
    'BettaFishAdvancedMonitoringService', 'BettaFishMonitoringIntegration',
    'DatabaseMonitoringService', 'AnnouncementParser', 'AssetService',
    'DividendDataService', 'DataCompletenessChecker',
    'EnhancedRealtimeDataManager', 'EnhancedDataQualityMonitor',
    'EnhancedDataManager', 'EnhancedDuckDBDataDownloader',
    'EnhancedPerformanceBridge', 'IncrementalDataAnalyzer',
    'IncrementalUpdateRecorder', 'IncrementalUpdateScheduler',
    'IndicatorDependencyManager', 'LLMConfigService',
    'ModelExplainer', 'ModelTrainingService',
    'NewStockFetcher', 'PerformanceDataBridge',
    'PluginService', 'SectorDataService',
    'ServiceHealthMonitor', 'StrategyService',
    'StrategyPluginPool', 'TaskScheduler',
    'ScheduledTaskExecutor', 'ProgressPersistenceManager',
    'ExternalAlertConfigPersistence', 'ExternalAlertChannelsService',
    'NotificationService', 'RealtimeComputeEngine',
    'SmartRecommendationEngine', 'SystemOptimizerService',
    'BettaFishMonitoringIntegration', 'BettaFishMonitoringService',
    'BettaFishAdvancedMonitoringService', 'QualityRuleEngine',
    'UnifiedCacheProvider', 'AsyncPluginDiscoveryWorker',
    'AsyncPluginDiscoveryService', 'DynamicRiskAdjustmentEngine',
    'DynamicRiskAdjustmentService', 'AdvancedRiskControlService',
    'DependencyType', 'ServiceState',
]

# Get class -> file mapping
def find_class_file(classname):
    for root, dirs, fs in os.walk('.'):
        if any(skip in root for skip in ['__pycache__', '.git', 'node_modules', '.pytest_cache', '.cache', 'data/cache', 'data/databases']):
            continue
        for fn in fs:
            if not fn.endswith('.py'):
                continue
            if 'bak' in fn or '.r128' in fn or '.r161' in fn:
                continue
            fp = os.path.join(root, fn)
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Look for `class ClassName(` or `class ClassName:`
                if re.search(rf'^class\s+{re.escape(classname)}\b', content, re.MULTILINE):
                    return fp.replace('\\', '/')
            except (UnicodeDecodeError, OSError):
                pass
    return None


for cls in CANDIDATES:
    self_file = find_class_file(cls)
    files = []
    for root, dirs, fs in os.walk('.'):
        if any(skip in root for skip in ['__pycache__', '.git', 'node_modules', '.pytest_cache', '.cache', 'data/cache', 'data/databases']):
            continue
        for fn in fs:
            if not fn.endswith('.py'):
                continue
            if 'bak' in fn or '.r128' in fn or '.r161' in fn:
                continue
            fp = os.path.join(root, fn)
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                if cls in content:
                    files.append(fp.replace('\\', '/'))
            except (UnicodeDecodeError, OSError):
                pass
    if not files:
        continue
    # Categorize
    self_only = [f for f in files if f == self_file]
    bootstrap = [f for f in files if f.endswith('service_bootstrap.py')]
    tests = [f for f in files if '/tests/' in f]
    tools = [f for f in files if '/tools/' in f or f.startswith('./_')]
    business = [f for f in files if f not in self_only + bootstrap + tests + tools]
    if len(files) >= 2 or cls in ('PluginHotReloader', 'PluginVersionManager', 'RecommendationExplanationGenerator'):
        print(f'\n{cls}: total={len(files)} self={len(self_only)} bootstrap={len(bootstrap)} tests={len(tests)} tools={len(tools)} BUSINESS={len(business)}')
        for f in business[:5]:
            print(f'  [B] {f}')
        for f in tools[:3]:
            print(f'  [T] {f}')
