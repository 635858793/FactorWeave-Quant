import re, os
service_dir = 'core/services'
unregistered_classes = [
    'AdvancedRiskControlService', 'AsyncDataImportManager', 'AsyncPluginDiscoveryService',
    'AutomatedRemediationService', 'BondService', 'CloudAPIService', 'DatabaseMonitoringService',
    'DataMaskingService', 'DataService', 'DistributedHTTPBridge', 'DistributedService',
    'DividendDataService', 'DynamicRiskAdjustmentService', 'EnhancedAsyncPluginDiscoveryService',
    'EnhancedPerformanceBridge', 'EnhancedRealtimeDataManager', 'FallbackService',
    'FaultToleranceManager', 'FeatureControlService', 'FundService', 'FundamentalDataManager',
    'IndexService', 'IntegratedSignalAggregatorService', 'LLMConfigService',
    'MacroEconomicDataManager', 'MarketService', 'ModelTrainingService', 'NetworkService',
    'PerformanceBaselineService', 'PluginService', 'ProgressPersistenceManager',
    'RealtimeComputeEngine', 'RoutingRuleManager', 'SectorDataService', 'SecurityService',
    'SystemOptimizerService', 'TdxServerDiscoveryService', 'TensorFlowGPUManager',
    'UnifiedCacheProvider', 'UnifiedChartService', 'UnifiedDataQualityMonitor',
    'LifecycleService', 'DeepAnalysisService', 'BettaFishMonitoringService', 'BettaFishAdvancedMonitoringService',
    'AIExplainabilityService', 'AIPredictionService', 'AnalysisService', 'IndustryService', 'StockService', 'ChartService',
]

# Search across project for usage
project_dirs = ['core', 'gui', 'web', 'tests', 'plugins', 'scripts', 'backtest']
output = []
output.append('=== Unregistered Service usage in business code ===')

for cls in unregistered_classes:
    references = []
    for d in project_dirs:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            if 'venv' in root or '.git' in root or '__pycache__' in root:
                continue
            for f in files:
                if not f.endswith('.py'):
                    continue
                path = os.path.join(root, f)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                        for i, line in enumerate(fp, 1):
                            # Look for business usage (resolve, import, factory)
                            if cls in line and ('resolve' in line or 'import' in line or 'factory' in line or f'get_{cls[0].lower() + cls[1:].replace("Service", "_service")}' in line or f'get_{cls.lower().replace("service", "_service")}' in line):
                                references.append((path, i, line.strip()[:100]))
                except Exception:
                    pass
    if references:
        output.append(f'\n## {cls} ({len(references)} business refs)')
        for p, l, c in references[:5]:
            output.append(f'  {p}:{l}: {c}')
        if len(references) > 5:
            output.append(f'  ... +{len(references)-5} more')

with open('tools/_r237_a_business_refs.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(output))
print('Done. Total lines:', len(output))
