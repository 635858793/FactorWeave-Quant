"""R235-A: 扫描 event subscribers, 识别 0 订阅方 ORPHAN_PUB 候选"""
import re
import os
import sys
from pathlib import Path

# 已知生产 publish 端提取的事件 (从 _r235_a_events.txt 整理)
PRODUCTION_EVENTS = [
    # (event_name, publish_sources, kind)
    ('KLineCloseEvent', ['core/asset_database_manager.py:1824', 'core/services/unified_data_manager.py:7918'], 'dataclass'),
    ('StockSelectedEvent', ['core/coordinators/main_window_coordinator.py:5371', 'core/ui/panels/right_panel.py:2432'], 'dataclass'),
    ('RealtimeComponentsRestoredEvent', ['core/coordinators/main_window_coordinator.py:6120'], 'dataclass'),
    ('RealtimeComponentsUnavailableEvent', ['core/coordinators/main_window_coordinator.py:6163'], 'dataclass'),
    ('database.type.changed', ['core/database_adapter_factory.py:448', 'core/events/types.py:408,1608'], 'string'),
    ('ErrorEvent', ['core/events/event_bus.py:769', 'core/services/enhanced_realtime_data_manager.py:1615', 'core/services/stock_service.py:286', 'core/trading/account_manager.py:1994'], 'dataclass'),
    ('data.import.complete', ['core/events/event_bus.py:1533', 'core/services/unified_data_manager.py:2893'], 'string'),
    ('order_filled', ['core/events/order_filled_helper.py:214', 'core/trading/interfaces/xtp_pro_trading_interface.py:652'], 'string'),
    ('market.quote_updated', ['core/events/r84_event_helper.py:556'], 'string'),
    ('DataImportEvent', ['core/events/types.py:2022'], 'dataclass'),
    ('MetricsAggregated', ['core/metrics/aggregation_service.py:320'], 'string'),
    ('ApplicationThresholdExceeded', ['core/metrics/aggregation_service.py:506'], 'string'),
    ('plugin_unloaded', ['core/plugin_manager.py:2672'], 'string'),
    ('RiskMonitorEvent', ['core/risk_alert.py:323'], 'dataclass'),
    ('RiskReducePositionEvent', ['core/risk_alert.py:357'], 'dataclass'),
    ('RiskStopTradingEvent', ['core/risk_alert.py:381'], 'dataclass'),
    ('RiskEmergencyLiquidationEvent', ['core/risk_alert.py:402'], 'dataclass'),
    ('data.discrepancy', ['core/routing_mode_dispatcher.py:535'], 'string'),
    ('AISelectionStartedEvent', ['core/services/ai_selection_integration_service.py:895'], 'dataclass'),
    ('AISelectionCompletedEvent', ['core/services/ai_selection_integration_service.py:946'], 'dataclass'),
    ('AISelectionFailedEvent', ['core/services/ai_selection_integration_service.py:1013'], 'dataclass'),
    ('AnalysisCompleteEvent', ['core/services/backtest_result_manager.py:267', 'core/ui/panels/right_panel.py:130', 'gui/widgets/backtest_widget.py:3215'], 'dataclass'),
    ('PerformanceAlertEvent', ['core/services/bettafish_monitoring_service.py:834'], 'dataclass'),
    ('ConfigChangedEvent', ['core/services/config_service.py:645'], 'dataclass'),
    ('DataIntegrityEvent', ['core/services/data_completeness_checker.py:114'], 'dataclass'),
    ('environment.changed', ['core/services/environment_service.py:709'], 'string'),
    ('EnvironmentChangedEvent', ['core/services/environment_service.py:715'], 'dataclass'),
    ('DataAnalysisEvent', ['core/services/incremental_data_analyzer.py:182'], 'dataclass'),
    ('UpdateHistoryEvent', ['core/services/incremental_update_recorder.py:245,278,334,377,420,452'], 'dataclass'),
    ('TrainingTaskCreatedEvent', ['core/services/model_training_service.py:480'], 'dataclass'),
    ('TrainingTaskStatusChangedEvent', ['core/services/model_training_service.py:588'], 'dataclass'),
    ('ModelVersionCreatedEvent', ['core/services/model_training_service.py:657'], 'dataclass'),
    ('ModelVersionCurrentChangedEvent', ['core/services/model_training_service.py:754'], 'dataclass'),
    ('ModelVersionRolledBackEvent', ['core/services/model_training_service.py:874'], 'dataclass'),
    ('TrainingProgressUpdatedEvent', ['core/services/model_training_service.py:1037', 'core/services/training_data_collector.py:225'], 'dataclass'),
    ('performance.metrics_updated', ['core/services/performance_service.py:310'], 'string'),
    ('PredictionRecordedEvent', ['core/services/prediction_tracking_service.py:298'], 'dataclass'),
    ('PredictionAccuracyUpdatedEvent', ['core/services/prediction_tracking_service.py:376'], 'dataclass'),
    ('TradeSignalReceivedEvent', ['core/services/signal_trading_bridge.py:725'], 'dataclass'),
    ('StrategyConfigsLoadedEvent', ['core/services/strategy_service.py:702'], 'dataclass'),
    ('StrategyConfigCreatedEvent', ['core/services/strategy_service.py:961'], 'dataclass'),
    ('StrategyConfigUpdatedEvent', ['core/services/strategy_service.py:1029'], 'dataclass'),
    ('StrategyConfigDeletedEvent', ['core/services/strategy_service.py:1078'], 'dataclass'),
    ('system.optimization.start', ['core/services/system_optimizer.py:635'], 'string'),
    ('system.optimization.complete', ['core/services/system_optimizer.py:665'], 'string'),
    ('system.optimization.error', ['core/services/system_optimizer.py:674'], 'string'),
    ('OrderFilledEvent', ['core/services/trading_service.py:62', 'core/trading/interfaces/ctp_trading_interface.py:1489', 'core/trading/interfaces/miniqmt_trading_interface.py:1019', 'core/trading/interfaces/xtp_pro_trading_interface.py:645', 'core/trading_engine.py:118'], 'dataclass'),
    ('TradeExecutedEvent', ['core/services/trading_service.py:893'], 'dataclass'),
    ('PositionUpdatedEvent', ['core/services/trading_service.py:1026'], 'dataclass'),
    ('xxx', ['core/trading/_event_helpers/account_position_helper.py:9'], 'string'),
    ('account_load_failed', ['core/trading/account_manager.py:244'], 'string'),
    ('AccountLoadFailedEvent', ['core/trading/account_manager.py:248'], 'dataclass'),
    ('accounts_refreshed', ['core/trading/account_manager.py:289'], 'string'),
    ('AccountsRefreshedEvent', ['core/trading/account_manager.py:293'], 'dataclass'),
    ('all_data_synced', ['core/trading/account_manager.py:351'], 'string'),
    ('AllDataSyncedEvent', ['core/trading/account_manager.py:355'], 'dataclass'),
    ('account_created', ['core/trading/account_manager.py:402'], 'string'),
    ('AccountCreatedEvent', ['core/trading/account_manager.py:406'], 'dataclass'),
    ('account_updated', ['core/trading/account_manager.py:451'], 'string'),
    ('AccountUpdatedEvent', ['core/trading/account_manager.py:455'], 'dataclass'),
    ('position_created', ['core/trading/account_manager.py:587'], 'string'),
    ('PositionCreatedEvent', ['core/trading/account_manager.py:591'], 'dataclass'),
    ('position_updated', ['core/trading/account_manager.py:634'], 'string'),
    ('PositionUpdatedEvent', ['core/trading/account_manager.py:642'], 'dataclass'),
    ('PositionUpdatedDbEvent', ['core/trading/account_manager.py:663'], 'dataclass'),
    ('fund_updated', ['core/trading/account_manager.py:791'], 'string'),
    ('FundUpdatedEvent', ['core/trading/account_manager.py:795'], 'dataclass'),
    ('account_status_changed', ['core/trading/account_manager.py:1010,1014'], 'string'),
    ('cash_frozen', ['core/trading/account_manager.py:1207'], 'string'),
    ('CashFrozenEvent', ['core/trading/account_manager.py:1213'], 'dataclass'),
    ('cash_unfrozen', ['core/trading/account_manager.py:1283'], 'string'),
    ('CashUnfrozenEvent', ['core/trading/account_manager.py:1289'], 'dataclass'),
    ('account_saved', ['core/trading/account_repository.py:419'], 'string'),
    ('AccountSavedEvent', ['core/trading/account_repository.py:423'], 'dataclass'),
    ('account_deleted', ['core/trading/account_repository.py:523'], 'string'),
    ('AccountDeletedEvent', ['core/trading/account_repository.py:527'], 'dataclass'),
    ('PositionSavedEvent', ['core/trading/account_repository.py:587'], 'dataclass'),
    ('position_deleted', ['core/trading/account_repository.py:654'], 'string'),
    ('PositionDeletedEvent', ['core/trading/account_repository.py:658'], 'dataclass'),
    ('fund_info_saved', ['core/trading/account_repository.py:698'], 'string'),
    ('FundInfoSavedEvent', ['core/trading/account_repository.py:702'], 'dataclass'),
    ('order_status_changed', ['core/trading/interfaces/ctp_trading_interface.py:1382', 'core/trading/interfaces/xtp_pro_trading_interface.py:521'], 'string'),
    ('cancel_order_rejected', ['core/trading/interfaces/xtp_pro_trading_interface.py:572'], 'string'),
    ('OrderCancelRejectedEvent', ['core/trading/interfaces/xtp_pro_trading_interface.py:577'], 'dataclass'),
    ('xtp_error', ['core/trading/interfaces/xtp_pro_trading_interface.py:690'], 'string'),
    ('trading_interface_circuit_breaker', ['core/trading/order_executor.py:768,1721'], 'string'),
    ('TradingInterfaceCircuitBreakerEvent', ['core/trading/order_executor.py:775,1728'], 'dataclass'),
    ('order.executed', ['core/trading/order_executor.py:1569,2046'], 'string'),
    ('OrderExecutedEvent', ['core/trading/order_executor.py:1582'], 'dataclass'),
    ('order_submitted_success', ['core/trading/order_executor.py:1663,2072'], 'string'),
    ('OrderSubmittedSuccessEvent', ['core/trading/order_executor.py:1672,2081'], 'dataclass'),
    ('OrderSubmittedFailedEvent', ['core/trading/order_executor.py:1756'], 'dataclass'),
    ('batch_orders_submitted_success', ['core/trading/order_executor.py:2146'], 'string'),
    ('BatchOrdersSubmittedSuccessEvent', ['core/trading/order_executor.py:2153'], 'dataclass'),
    ('batch_orders_submitted_failed', ['core/trading/order_executor.py:2166'], 'string'),
    ('BatchOrdersSubmittedFailedEvent', ['core/trading/order_executor.py:2173'], 'dataclass'),
    ('order_terminal_state', ['core/trading/order_executor.py:2349,2861'], 'string'),
    ('OrderTerminalStateEvent', ['core/trading/order_executor.py:2353,2872'], 'dataclass'),
    ('order_cancelled', ['core/trading/order_executor.py:2375'], 'string'),
    ('OrderCancelledEvent', ['core/trading/order_executor.py:2379'], 'dataclass'),
    ('order_cancel_failed', ['core/trading/order_executor.py:2408'], 'string'),
    ('OrderCancelFailedEvent', ['core/trading/order_executor.py:2412'], 'dataclass'),
    ('order_partially_filled', ['core/trading/order_executor.py:2934'], 'string'),
    ('OrderPartiallyFilledEvent', ['core/trading/order_executor.py:2948'], 'dataclass'),
    ('order_alert', ['core/trading/order_monitor.py:416'], 'string'),
    ('OrderAlertEvent', ['core/trading/order_monitor.py:419'], 'dataclass'),
    ('order_save_failed_need_unfreeze', ['core/trading/order_repository.py:298'], 'string'),
    ('order_saved', ['core/trading/order_repository.py:330'], 'string'),
    ('OrderSavedEvent', ['core/trading/order_repository.py:333'], 'dataclass'),
    ('order_save_retry', ['core/trading/order_repository.py:343'], 'string'),
    ('order_save_failed', ['core/trading/order_repository.py:379'], 'string'),
    ('OrderSaveFailedEvent', ['core/trading/order_repository.py:382'], 'dataclass'),
    ('order_updated', ['core/trading/order_repository.py:476', 'core/trading/order_service.py:1990'], 'string'),
    ('OrderUpdatedEvent', ['core/trading/order_repository.py:479'], 'dataclass'),
    ('order_fill_saved', ['core/trading/order_repository.py:766'], 'string'),
    ('OrderFillSavedEvent', ['core/trading/order_repository.py:769'], 'dataclass'),
    ('order_deleted', ['core/trading/order_repository.py:818'], 'string'),
    ('OrderDeletedEvent', ['core/trading/order_repository.py:821'], 'dataclass'),
    ('order.validation_failed', ['core/trading/order_service.py:773'], 'string'),
    ('OrderValidationFailedEvent', ['core/trading/order_service.py:782'], 'dataclass'),
    ('order_created', ['core/trading/order_service.py:1058'], 'string'),
    ('OrderCreatedEvent', ['core/trading/order_service.py:1067'], 'dataclass'),
    ('batch_orders_created', ['core/trading/order_service.py:1242,2267'], 'string'),
    ('BatchOrdersCreatedEvent', ['core/trading/order_service.py:1249,2275'], 'dataclass'),
    ('batch_orders_cancelled', ['core/trading/order_service.py:1766'], 'string'),
    ('BatchOrdersCancelledEvent', ['core/trading/order_service.py:1773'], 'dataclass'),
    ('OrderModifiedEvent', ['core/trading/order_service.py:1997'], 'dataclass'),
    ('all_active_orders_cancelled', ['core/trading/order_service.py:2321'], 'string'),
    ('AllActiveOrdersCancelledEvent', ['core/trading/order_service.py:2328'], 'dataclass'),
    ('SignalGeneratedEvent', ['core/trading_engine.py:856'], 'dataclass'),
    ('OrderRejectedEvent', ['core/trading_engine.py:2375,2504,2544'], 'dataclass'),
    ('MultiScreenToggleEvent', ['core/ui/panels/middle_panel.py:1349,1378'], 'dataclass'),
    ('bettafish.agent.started', ['core/events/r84_event_helper.py:1096'], 'string'),
    ('bettafish.analysis.completed', ['core/events/r84_event_helper.py:1217'], 'string'),
    ('bettafish.analysis.failed', ['core/events/r84_event_helper.py:1254'], 'string'),
]

# 已治理事件 (排除)
GOVERNED = {
    'data.discrepancy', 'data.import.ui_feedback', 'data.masked',
    'performance.alert', 'performance.alert_triggered', 'performance.optimization_completed', 'performance.periodic_report',
    'risk.account_drift',
    'training.task.deleted',
    'security.threat_detected',
    'sla.violation',
    'bettafish.agent.started', 'bettafish.analysis.completed', 'bettafish.analysis.failed',
}

# 已知有 helper + 已被 R84/R108/R140/R142/R187/R188/R189/R200 治理
GOVERNED_BY_HELPER = {
    'data.import.complete', 'order_filled', 'market.quote_updated',
    'service.started', 'service.stopped', 'service.error',
    'service.{name}.initialized', 'service.{name}.initialization_failed',
    'task.status_changed', 'ai.status_updated',
    'order_save_retry', 'batch_orders_created', 'batch_orders_cancelled',
    'all_active_orders_cancelled', 'order_save_failed_need_unfreeze',
    'order_submitted', 'order_rejected', 'theme_changed', 'asset_selected',
    'ui_data_ready', 'ResourceAlert', 'ApplicationAlert', 'TickDataEvent',
    'market.contract_received', 'market.connected', 'market.disconnected',
    'RealtimeDataEvent', 'OrderBookEvent', 'TradeExecutedEvent',
    'strategy.started', 'strategy.stopped',
    'account_saved', 'account_deleted', 'position_saved', 'position_deleted',
    'fund_info_saved', 'order_fill_saved',
    'cash_frozen', 'cash_unfrozen', 'account_load_failed', 'account_status_changed',
    'accounts_refreshed', 'all_data_synced',
    'security.threat_detected', 'orders.batch_confirmed',
    'asset.data_ready', 'data.import.complete',
    'bettafish.agent.started', 'bettafish.agent.stopped',
    'bettafish.analysis.completed', 'bettafish.analysis.failed',
    'bettafish.sentiment.analysis.completed',
    'data_source_switched', 'writer.health_alert', 'sla.violation',
    'risk.account_drift',
}

# 排除 (测试 + placeholder + 重复)
EXCLUDE_TEST = True


def search_subscribers(base_dir, event_name):
    """跨 4 子目录 (core/ + gui/ + web/ + tests/) 搜索订阅方"""
    # 搜索模式: 1) .subscribe(EventName)  2) .subscribe("event_name")  3) @bus.subscribe  4) event_type=EventName
    patterns_str = [
        rf'\.subscribe\s*\(\s*["\'](?:{re.escape(event_name)})["\']',  # 'event_name' 直接字符串
        rf'\.subscribe\s*\(\s*EventBus\.',  # EventBus.X
        rf'subscribe\s*\([^,]*event_type\s*=\s*EventBus\.',  # event_type=EventBus.X
    ]
    patterns_class = [
        rf'\.subscribe\s*\(\s*{re.escape(event_name)}\s*\)',  # EventClass 直接传
        rf'\.subscribe\s*\(\s*{re.escape(event_name)}\s*,',  # EventClass 后跟参数
        rf'subscribe\s*\(\s*{re.escape(event_name)}\s*[\),]',
        rf'subscribe\s*\([^,]*event_type\s*=\s*{re.escape(event_name)}\b',
    ]

    hits = []
    search_dirs = ['core', 'gui', 'web', 'tests']
    for d in search_dirs:
        for root, dirs, files in os.walk(os.path.join(base_dir, d)):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', 'node_modules', '.git', 'logs')]
            for f in files:
                if not f.endswith('.py'):
                    continue
                fp = os.path.join(root, f)
                if any(x in fp for x in ['\\tools\\', '\\scripts\\', '_archive', '_r[0-9]+_', '.bak.', '.r']):
                    continue
                try:
                    with open(fp, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                        lines = content.split('\n')
                except Exception:
                    continue
                # 字符串事件搜索
                for line_idx, line in enumerate(lines, 1):
                    # 跳过注释行
                    stripped = line.strip()
                    if stripped.startswith('#'):
                        continue
                    matched = False
                    for pat in patterns_str:
                        if re.search(pat, line):
                            matched = True
                            break
                    if not matched:
                        for pat in patterns_class:
                            if re.search(pat, line):
                                matched = True
                                break
                    if matched:
                        rel = os.path.relpath(fp, base_dir)
                        hits.append((rel, line_idx, line.strip()[:120]))
    return hits


def main():
    base = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui'
    print("=" * 80)
    print(f"R235-A: ORPHAN_PUB 候选扫描 (生产文件, 排除已治理)")
    print("=" * 80)

    # 收集去重后的事件名
    orphan_candidates = []
    for event_name, sources, kind in PRODUCTION_EVENTS:
        if event_name in GOVERNED or event_name in GOVERNED_BY_HELPER:
            continue
        hits = search_subscribers(base, event_name)
        if not hits:
            orphan_candidates.append((event_name, sources, kind, hits))

    print(f"\n=== ORPHAN_PUB 候选 ({len(orphan_candidates)} 个) ===\n")
    for event_name, sources, kind, hits in sorted(orphan_candidates, key=lambda x: x[0]):
        print(f"\n## {event_name} ({kind})")
        print(f"  Publish: {', '.join(sources)}")
        print(f"  Subscribers: 0 (跨 4 子目录搜索)")

    print(f"\n\n=== 总计: {len(orphan_candidates)} ORPHAN_PUB 候选 ===")


if __name__ == '__main__':
    main()
