import re, os

# Business-critical services that need dispose check
critical_services = [
    'bond_service.py',
    'fund_service.py',
    'index_service.py',
    'market_service.py',
    'network_service.py',
    'security_service.py',
    'data_service.py',
    'plugin_service.py',
    'data_masking_service.py',
    'database_monitoring_service.py',
    'distributed_service.py',
    'distributed_http_bridge.py',
    'fallback_service.py',
    'fault_tolerance_manager.py',
    'macro_economic_data_manager.py',
    'fundamental_data_manager.py',
    'tdx_server_discovery.py',
    'tensorflow_gpu_manager.py',
    'sector_data_service.py',
    'sector_fund_flow_service.py',
    'dividend_data_service.py',
    'realtime_compute_engine.py',
    'realtime_compute_engine.py',
    'unified_chart_service.py',
    'routing_rule_manager.py',
    'feature_control_service.py',
    'progress_persistence_manager.py',
    'lifecycle_service.py',
    'notification_service.py',
    'strategy_service.py',
    'trading_service.py',
    'cache_service.py',
    'database_service.py',
    'enhanced_data_manager.py',
    'unified_data_manager.py',
    'bettafish_monitoring_service.py',
    'bettafish_advanced_monitoring_service.py',
    'enhanced_performance_bridge.py',
    'enhanced_realtime_data_manager.py',
    'llm_config_service.py',
    'integrated_signal_aggregator_service.py',
    'deep_analysis_service.py',
    'model_training_service.py',
    'analysis_service.py',
    'industry_service.py',
    'stock_service.py',
    'chart_service.py',
    'alert_deduplication_service.py',
    'alert_rule_engine.py',
    'ai_explainability_service.py',
    'ai_prediction_service.py',
    'extension_service.py',
    'environment_service.py',
    'cloud_api_service.py',
    'funding_rate_analysis_service.py',
    'funding_rate_analysis_service.py',
    'market_cap_calculator.py',
    'performance_baseline_service.py',
    'performance_service.py',
    'unified_cache_provider.py',
    'unified_cache_service.py',
    'unified_data_quality_monitor.py',
]

service_dir = 'core/services'
output = []
output.append('=== Dispose Chain Audit (R233 §13.4 强约束) ===')
output.append('Service | dispose | shutdown | close | cleanup | _do_dispose | on_dispose')

for f in critical_services:
    path = os.path.join(service_dir, f)
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
        content = fp.read()
    has_dispose = 'def dispose' in content or 'def _do_dispose' in content
    has_shutdown = 'def shutdown' in content
    has_close = 'def close' in content
    has_cleanup = 'def cleanup' in content
    has_on_dispose = 'def on_dispose' in content
    has_undo_dispose = '_do_dispose' in content
    status = '🟢' if (has_dispose or has_shutdown or has_close or has_cleanup) else '🔴'
    output.append(f'{status} {f:48s} | {has_dispose} | {has_shutdown} | {has_close} | {has_cleanup} | {has_undo_dispose} | {has_on_dispose}')

with open('tools/_r237_a_dispose_audit.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(output))
