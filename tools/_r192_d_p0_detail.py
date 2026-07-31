#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R192-D 详细分析 v4 - 列出每个优先级文件的所有 P0 行"""
import json
import sys
import ast
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_scan.json', encoding='utf-8') as f:
    data = json.load(f)
data = [v for v in data if 'error' not in v]
for v in data:
    v['file'] = v['file'].replace('\\', '/')

PROJECT_ROOT = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui'

def get_handler_real_context(file_path, handler_line):
    """分析一个 except handler 的真实上下文"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return 'ERROR', None, None

    # Find the actual except handler
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.lineno == handler_line:
            # 找到父节点: 可能是 Module, FunctionDef, AsyncFunctionDef
            parent_name = None
            parent_node = None
            for parent in ast.walk(tree):
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if parent.lineno <= handler_line <= (parent.end_lineno or 0):
                        # 找到最近的祖先方法
                        if parent_node is None or parent.lineno > parent_node.lineno:
                            parent_node = parent
                            parent_name = parent.name

            body = node.body
            if not body:
                body_type = 'EMPTY'
            elif len(body) == 1 and isinstance(body[0], ast.Pass):
                body_type = 'PASS'
            elif all(isinstance(s, ast.Assign) for s in body):
                body_type = 'ASSIGN'
            else:
                body_type = f'OTHER ({len(body)} stmts)'

            # 决定级别
            if parent_node is None:
                return 'module', None, body_type
            return 'method', parent_name, body_type
    return 'NOT_FOUND', None, None

# Process
out = []
priority = [
    'core/services/ai_selection_risk_control_service.py',
    'core/services/unified_data_manager.py',
    'core/services/service_bootstrap.py',
    'core/coordinators/main_window_coordinator.py',
    'core/services/ai_selection_integration_service.py',
    'core/importdata/intelligent_config_manager.py',
    'core/services/realtime_compute_engine.py',
    'core/services/bettafish_monitoring_service.py',
    'core/services/trading_service.py',
    'core/services/strategy_service.py',
    'core/services/fault_tolerance_manager.py',
    'core/services/ai_prediction_service.py',
    'core/importdata/import_execution_engine.py',
    'core/services/alert_rule_engine.py',
    'core/services/plugin_service.py',
    'core/services/cache_service.py',
    'core/services/model_training_service.py',
    'core/events/event_bus.py',
    'core/monitoring/queue_monitor.py',
    'core/services/base_service.py',
    'core/services/database_service.py',
    'core/services/integrated_signal_aggregator_service.py',
    'core/services/llm_config_service.py',
    'core/services/tdx_server_discovery.py',
    'core/services/performance_service.py',
    'core/services/dynamic_risk_adjustment_service.py',
    'core/services/uni_plugin_data_manager.py',
    'core/services/enhanced_realtime_data_manager.py',
    'core/monitoring/sla_monitor.py',
    'core/services/metrics_base.py',
]

# Focus on P0 violations
p0_data = [v for v in data if v.get('severity') == 'P0' and 'ImportError' not in v.get('exception_type', '')]

for pf in priority:
    file_p0 = [v for v in p0_data if v['file'] == pf]
    if not file_p0:
        continue
    fpath = PROJECT_ROOT + '/' + pf
    out.append(f"\n=== {pf} ({len(file_p0)} P0) ===")
    for v in sorted(file_p0, key=lambda x: x.get('line', 0)):
        ctx, parent, body = get_handler_real_context(fpath, v.get('line', 0))
        out.append(f"  L{v.get('line'):4d} {ctx:6s} {parent or '-':30s} {v.get('exception_type'):20s} body={body}")

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_p0_detail.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print("DONE")
