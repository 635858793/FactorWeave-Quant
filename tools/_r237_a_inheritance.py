import re, os
service_dir = 'core/services'
no_dispose_files = [
    'data_masking_service.py', 'database_monitoring_service.py', 'distributed_service.py',
    'fallback_service.py', 'fault_tolerance_manager.py', 'fundamental_data_manager.py',
    'tdx_server_discovery.py', 'dividend_data_service.py', 'feature_control_service.py',
    'enhanced_data_manager.py', 'enhanced_performance_bridge.py', 'llm_config_service.py',
    'integrated_signal_aggregator_service.py', 'deep_analysis_service.py',
    'model_training_service.py', 'cloud_api_service.py', 'funding_rate_analysis_service.py',
    'market_cap_calculator.py', 'unified_cache_provider.py', 'unified_cache_service.py',
    'enhanced_data_quality_monitor.py', 'unified_data_quality_monitor.py',
    'bond_service.py', 'fund_service.py', 'index_service.py',
]

output = []
for f in no_dispose_files:
    path = os.path.join(service_dir, f)
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
        for i, line in enumerate(fp, 1):
            m = re.match(r'class\s+(\w+(?:Service|Manager|Engine|Provider|Bridge|Factory|Handler))(?:\(|:)\s*([\w.,\s\(\)\[\]]*)', line)
            if m:
                output.append(f'{f:48s}:{i:5d}: {line.strip()}')
                break
with open('tools/_r237_a_inheritance.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(output))
