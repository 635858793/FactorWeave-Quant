"""R180 C 子智能体: 详细分析 UDM 15 处违规"""
import sys
sys.path.insert(0, 'tools')
from _r180_c_exc_info_scanner_v2 import audit_exc_info_compliance

result = audit_exc_info_compliance('core/services/unified_data_manager.py')
print(f'违规总数: {len(result["violations"])}')
print('=' * 100)
for v in result['violations']:
    print(f'L{v["lineno"]:>5} [{v["func_name"]}] except {v["except_type"]:<35} {v["method_chain"]}')
    print(f'      -> {v["source_line"][:120]}')
