#!/usr/bin/env python3
"""R180-B 子智能体 B: Top 20 业务关键文件 违规清单 dump"""
import sys
sys.path.insert(0, r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools')
from _r180_c_exc_info_scanner_v2 import audit_exc_info_compliance

TARGETS = [
    'core/database/duckdb_manager.py',
    'core/services/stock_service.py',
    'core/services/industry_service.py',
    'core/services/strategy_service.py',
    'core/agents/technical_agent.py',
    'core/agents/fusion_engine.py',
    'core/agents/risk_agent.py',
    'core/services/database_service.py',
    'core/services/sector_fund_flow_service.py',
    'core/services/network_service.py',
]

ALL_RESULTS = {}
for fp in TARGETS:
    r = audit_exc_info_compliance(fp)
    ALL_RESULTS[fp] = r
    print('=' * 80)
    print(f'FILE: {fp}')
    print(f'  except blocks: {r["total_except_blocks"]}')
    print(f'  logger in except: {r["logger_in_except"]}')
    print(f'  with exc_info: {r["logger_with_exc_info"]}')
    print(f'  without exc_info: {r["logger_without_exc_info"]}')
    if r['logger_in_except'] > 0:
        compliance = r['logger_with_exc_info'] / r['logger_in_except'] * 100
        print(f'  compliance: {compliance:.1f}%')
    print(f'  VIOLATIONS ({len(r["violations"])}):')
    for v in r['violations']:
        line = v['source_line'][:110]
        chain = v['method_chain'][:60]
        print(f'    L{v["lineno"]:>4} [{v["func_name"]:>8}] {chain:<60}')
        print(f'           {line}')

print('=' * 80)
print('SUMMARY')
print('=' * 80)
total_v = sum(r['logger_without_exc_info'] for r in ALL_RESULTS.values())
total_le = sum(r['logger_in_except'] for r in ALL_RESULTS.values())
total_we = sum(r['logger_with_exc_info'] for r in ALL_RESULTS.values())
print(f'  Total files: {len(ALL_RESULTS)}')
print(f'  Total logger in except: {total_le}')
print(f'  Total with exc_info: {total_we}')
print(f'  Total without exc_info (violations): {total_v}')
if total_le > 0:
    print(f'  Overall compliance: {total_we/total_le*100:.1f}%')
