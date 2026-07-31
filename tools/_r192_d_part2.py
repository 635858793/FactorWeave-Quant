#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R192-D 详细分析 v5 - logger.debug 业务事件升级 + Service 缺 health_check/metrics 扫描"""
import json
import sys
import ast
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui')

# === Part 1: logger.debug 业务事件升级扫描 ===
# 重点: except 块内的 logger.debug
with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_scan.json', encoding='utf-8') as f:
    data = json.load(f)
data = [v for v in data if 'error' not in v]
for v in data:
    v['file'] = v['file'].replace('\\', '/')

# logger.debug in except block
debug_in_except = [v for v in data if v.get('type') == 'R51_LOW_LEVEL' and 'debug' in v.get('methods', [])]
info_in_except = [v for v in data if v.get('type') == 'R51_LOW_LEVEL' and 'info' in v.get('methods', [])]

# === Part 2: Service 缺 health_check/metrics 扫描 ===
services_dir = PROJECT_ROOT / 'core' / 'services'
service_files = list(services_dir.rglob('*.py'))
service_files = [f for f in service_files if '__pycache__' not in f.parts]

def has_method(file_path, method_name):
    """检查文件中是否定义某方法"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return True
    return False

def get_class_name(file_path):
    """获取主类名 (取第一个非内部类)"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # 排除内部类
            if not node.name.startswith('_'):
                return node.name
    return None

services_analysis = []
for f in service_files:
    if f.name == '__init__.py' or f.name == 'base_service.py':
        continue
    class_name = get_class_name(f)
    if not class_name:
        continue
    has_health = has_method(f, 'health_check') or has_method(f, '_do_health_check') or has_method(f, 'is_healthy') or has_method(f, 'perform_health_check')
    has_metrics = has_method(f, 'get_metrics') or has_method(f, 'metrics') or has_method(f, '_get_metrics') or has_method(f, 'collect_metrics')
    services_analysis.append({
        'file': str(f.relative_to(PROJECT_ROOT)).replace('\\', '/'),
        'class': class_name,
        'has_health': has_health,
        'has_metrics': has_metrics,
    })

# 缺 health_check 的 Service
missing_health = [s for s in services_analysis if not s['has_health']]
missing_metrics = [s for s in services_analysis if not s['has_metrics']]

# 整理输出
out = []

out.append("=== Part 1: logger.debug 业务事件升级 (R51 §7.1 #5) ===")
out.append(f"\nlogger.debug in except blocks: {len(debug_in_except)}")
out.append(f"logger.info in except blocks: {len(info_in_except)}")
out.append("\n--- Top 20 logger.debug in except (R190-R191 priority) ---")
priority_files = [
    'core/monitoring/sla_monitor.py',
    'core/services/service_bootstrap.py',
    'core/events/r84_event_helper.py',
    'core/coordinators/event_coordinator.py',
    'core/feature_flags/flag_manager.py',
    'core/importdata/unified_data_import_engine.py',
    'core/ui_integration/smart_data_integration.py',
    'core/events/event_bus.py',
    'core/services/unified_data_manager.py',
    'core/coordinators/main_window_coordinator.py',
]
debug_filtered = [v for v in debug_in_except if v['file'] in priority_files]
for v in debug_filtered[:30]:
    out.append(f"  L{v.get('line'):4d} {v['file']} | {v.get('exception_type')}")

out.append(f"\n=== Part 2: Service 缺 health_check/metrics 扫描 (R143-B 续) ===")
out.append(f"\n总 Service 类数: {len(services_analysis)}")
out.append(f"缺 health_check: {len(missing_health)}")
out.append(f"缺 metrics: {len(missing_metrics)}")

out.append("\n--- 缺 health_check 的 Service (Top 30) ---")
for s in missing_health[:30]:
    out.append(f"  {s['class']:50s} | has_metrics={s['has_metrics']!s:5s} | {s['file']}")

out.append("\n--- 缺 metrics 的 Service (Top 30) ---")
for s in missing_metrics[:30]:
    out.append(f"  {s['class']:50s} | has_health={s['has_health']!s:5s} | {s['file']}")

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_part2.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print("DONE")
