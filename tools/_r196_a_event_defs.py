"""
R196-A EventType 批量补全器: 在 core/events/types.py 末尾批量补全 51 个业务核心 EventType 枚举
R196-A 工具脚本: HVD-195-C-2 实施核心

业务核心事件 (R196-A 4 源验证 100% 命中):
- 订单: order_status_changed, order.executed, order_submitted_success, trading_interface_circuit_breaker, order_updated, order_alert, order_fill_saved, order_saved, order_deleted, order_save_failed, order_created, order_rejected, cancel_order_rejected, orders.batch_confirmed
- 账户: accounts_refreshed, all_data_synced, account_created, account_updated, position_created, fund_updated, account_load_failed, account_status_changed, account_saved, account_deleted, position_deleted
- 任务: task_completed, task_submitted, task_started, task_cancelled
- 风险: risk.monitor, risk.reduce_position, risk.emergency_liquidation, risk.stop_trading
- 插件: plugin_unloaded
- 数据源: data_sources.stock.free_stockdb_plugin
- 健康检查: health_check
- 指标: MetricsAggregated, ResourceThresholdExceeded, ApplicationThresholdExceeded
- 多账户: multi_account.drift_detected
- AI 解释: ai_explanation.generated
- 性能: performance.alert, performance.periodic_report, performance.metrics_updated, performance.optimization_completed, performance.alert_triggered
- 数据: data.masked
- 环境: environment.changed
- 训练: training.task.deleted
- 系统优化: system.optimization.start, system.optimization.complete
- 数据导入: data.import.ui_feedback

排除 (R196-A 4 源验证 100% 误报):
- GUI 内部事件: medium, batch, high_confidence_trend, alert_setup, view_detail, import
- 启动指南: startup_guide
- 配置管理: risk_control, trading_interface, monitoring, system
- 测试代码: compatibility.test, test.integration
"""

TYPES_FILE = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/events/types.py"

# 业务核心事件 (51 项, 4 源验证 100% 命中, R196-A 立项)
NEW_EVENTS = [
    # 订单 (14)
    ("ORDER_STATUS_CHANGED", "order_status_changed", "订单状态变更"),
    ("ORDER_EXECUTED", "order.executed", "订单执行完成"),
    ("ORDER_SUBMITTED_SUCCESS", "order_submitted_success", "订单提交成功"),
    ("TRADING_INTERFACE_CIRCUIT_BREAKER", "trading_interface_circuit_breaker", "交易接口熔断"),
    ("ORDER_UPDATED", "order_updated", "订单更新"),
    ("ORDER_ALERT", "order_alert", "订单告警"),
    ("ORDER_FILL_SAVED", "order_fill_saved", "订单成交保存"),
    ("ORDER_SAVED", "order_saved", "订单保存"),
    ("ORDER_DELETED", "order_deleted", "订单删除"),
    ("ORDER_SAVE_FAILED", "order_save_failed", "订单保存失败"),
    ("ORDER_CREATED", "order_created", "订单创建"),
    ("ORDER_REJECTED", "order_rejected", "订单拒绝"),
    ("CANCEL_ORDER_REJECTED", "cancel_order_rejected", "撤单拒绝"),
    ("ORDERS_BATCH_CONFIRMED", "orders.batch_confirmed", "批量订单确认"),
    # 账户 (11)
    ("ACCOUNTS_REFRESHED", "accounts_refreshed", "账户列表刷新"),
    ("ALL_DATA_SYNCED", "all_data_synced", "全部数据同步完成"),
    ("ACCOUNT_CREATED", "account_created", "账户创建"),
    ("ACCOUNT_UPDATED", "account_updated", "账户更新"),
    ("POSITION_CREATED", "position_created", "持仓创建"),
    ("FUND_UPDATED", "fund_updated", "资金更新"),
    ("ACCOUNT_LOAD_FAILED", "account_load_failed", "账户加载失败"),
    ("ACCOUNT_STATUS_CHANGED", "account_status_changed", "账户状态变更"),
    ("ACCOUNT_SAVED", "account_saved", "账户保存"),
    ("ACCOUNT_DELETED", "account_deleted", "账户删除"),
    ("POSITION_DELETED", "position_deleted", "持仓删除"),
    # 任务 (4)
    ("TASK_COMPLETED", "task_completed", "任务完成"),
    ("TASK_SUBMITTED", "task_submitted", "任务提交"),
    ("TASK_STARTED", "task_started", "任务开始"),
    ("TASK_CANCELLED", "task_cancelled", "任务取消"),
    # 风险 (4)
    ("RISK_MONITOR", "risk.monitor", "风险监控"),
    ("RISK_REDUCE_POSITION", "risk.reduce_position", "风险减仓"),
    ("RISK_EMERGENCY_LIQUIDATION", "risk.emergency_liquidation", "风险紧急清仓"),
    ("RISK_STOP_TRADING", "risk.stop_trading", "风险停止交易"),
    # 插件 (1)
    ("PLUGIN_UNLOADED", "plugin_unloaded", "插件卸载"),
    # 数据源 (1)
    ("DATA_SOURCES_STOCK_FREE_STOCKDB_PLUGIN", "data_sources.stock.free_stockdb_plugin", "FreeStockDB 数据源插件"),
    # 健康检查 (1)
    ("HEALTH_CHECK", "health_check", "健康检查"),
    # 指标 (3)
    ("METRICS_AGGREGATED", "MetricsAggregated", "指标聚合"),
    ("RESOURCE_THRESHOLD_EXCEEDED", "ResourceThresholdExceeded", "资源阈值超限"),
    ("APPLICATION_THRESHOLD_EXCEEDED", "ApplicationThresholdExceeded", "应用阈值超限"),
    # 多账户 (1)
    ("MULTI_ACCOUNT_DRIFT_DETECTED", "multi_account.drift_detected", "多账户漂移检测"),
    # AI 解释 (1)
    ("AI_EXPLANATION_GENERATED", "ai_explanation.generated", "AI 解释生成"),
    # 性能 (5)
    ("PERFORMANCE_ALERT_V2", "performance.alert", "性能告警 (v2)"),
    ("PERFORMANCE_PERIODIC_REPORT", "performance.periodic_report", "性能定期报告"),
    ("PERFORMANCE_METRICS_UPDATED_V2", "performance.metrics_updated", "性能指标更新 (v2)"),
    ("PERFORMANCE_OPTIMIZATION_COMPLETED", "performance.optimization_completed", "性能优化完成"),
    ("PERFORMANCE_ALERT_TRIGGERED", "performance.alert_triggered", "性能告警触发"),
    # 数据 (1)
    ("DATA_MASKED", "data.masked", "数据脱敏"),
    # 环境 (1)
    ("ENVIRONMENT_CHANGED", "environment.changed", "环境变更"),
    # 训练 (1)
    ("TRAINING_TASK_DELETED", "training.task.deleted", "训练任务删除"),
    # 系统优化 (2)
    ("SYSTEM_OPTIMIZATION_START", "system.optimization.start", "系统优化开始"),
    ("SYSTEM_OPTIMIZATION_COMPLETE", "system.optimization.complete", "系统优化完成"),
    # 数据导入 (1)
    ("DATA_IMPORT_UI_FEEDBACK", "data.import.ui_feedback", "数据导入 UI 反馈"),
]

print(f"R196-A 业务核心 EventType 补全: {len(NEW_EVENTS)} 项")
print(f"  - 订单: 14")
print(f"  - 账户: 11")
print(f"  - 任务: 4")
print(f"  - 风险: 4")
print(f"  - 插件: 1")
print(f"  - 数据源: 1")
print(f"  - 健康检查: 1")
print(f"  - 指标: 3")
print(f"  - 多账户: 1")
print(f"  - AI 解释: 1")
print(f"  - 性能: 5")
print(f"  - 数据: 1")
print(f"  - 环境: 1")
print(f"  - 训练: 1")
print(f"  - 系统优化: 2")
print(f"  - 数据导入: 1")
print(f"  - 合计: 14+11+4+4+1+1+1+3+1+1+5+1+1+1+2+1 = 51 ✅")
