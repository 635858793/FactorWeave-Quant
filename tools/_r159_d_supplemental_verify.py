"""R159 补充验证: R51 软解析精准扫描 + HVD-155-3-CALL 精确搜索"""
import re
import ast
from pathlib import Path

PROJECT_ROOT = Path('.')

print("=" * 80)
print("R159 补充验证 1: R51 软解析精准扫描 (仅 except 块内 logger 缺 exc_info)")
print("=" * 80)

# 精准 R51 软解析扫描 (仅 except 块内)
r51_violations_strict = []
total_except_loggers = 0
for search_dir in ['core', 'gui', 'web/backend']:
    dir_path = PROJECT_ROOT / search_dir
    if not dir_path.exists():
        continue
    for py_file in dir_path.rglob('*.py'):
        if any(skip in py_file.parts for skip in ['.git', '__pycache__', '.pytest_cache']):
            continue
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            file_lines = content.split('\n')
        except Exception:
            continue

        # 简单 AST 解析
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # 找 except 块内所有 logger 调用
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        func = sub.func
                        if (isinstance(func, ast.Attribute) and
                            isinstance(func.value, ast.Name) and
                            func.value.id == 'logger' and
                            func.attr in ('error', 'warning')):
                            total_except_loggers += 1
                            # 检查该调用是否含 exc_info
                            has_exc_info = any(
                                kw.arg == 'exc_info' for kw in sub.keywords
                            )
                            if not has_exc_info:
                                r51_violations_strict.append({
                                    'file': str(py_file.relative_to(PROJECT_ROOT)),
                                    'line': sub.lineno,
                                    'logger_type': func.attr,
                                })

print(f"  [全项目 except 块内 logger.error/warning 总数]: {total_except_loggers}")
print(f"  [R51 软解析违规 (except 块内 logger 缺 exc_info=True)]: {len(r51_violations_strict)} 处")
if r51_violations_strict[:20]:
    print(f"    前 20 处:")
    for v in r51_violations_strict[:20]:
        print(f"      {v['file']}:{v['line']} ({v['logger_type']})")

# 按文件分组
from collections import Counter
file_counter = Counter(v['file'] for v in r51_violations_strict)
print(f"  [违规文件 Top 10]:")
for f, c in file_counter.most_common(10):
    print(f"    {f}: {c} 处")


print("\n" + "=" * 80)
print("R159 补充验证 2: HVD-155-3-CALL trading_engine 精确搜索 (account_id 透传)")
print("=" * 80)
with open('core/trading_engine.py', 'r', encoding='utf-8') as f:
    te_source = f.read()
te_lines = te_source.split('\n')

# 找所有 account_id 引用
account_id_lines = []
for i, l in enumerate(te_lines, 1):
    if 'account_id=' in l:
        account_id_lines.append((i, l.strip()[:120]))

print(f"  [account_id= 引用总数]: {len(account_id_lines)} 处")
for line_no, content in account_id_lines[:30]:
    print(f"    L{line_no}: {content}")


print("\n" + "=" * 80)
print("R159 补充验证 3: R137-IMP-5/6 4 源验证深挖 (R158-C 实证)")
print("=" * 80)

# 类别 9: R137-IMP-5: account_management_dialog.py 18 处 R51 漏洞全量 sweep
acc_dialog_path = 'gui/dialogs/account_management_dialog.py'
try:
    with open(acc_dialog_path, 'r', encoding='utf-8') as f:
        acc_dialog_source = f.read()
    acc_tree = ast.parse(acc_dialog_source)

    # 精准 except 块内 logger 漏 exc_info
    acc_except_loggers_no_exc = 0
    acc_except_loggers_total = 0
    for node in ast.walk(acc_tree):
        if isinstance(node, ast.ExceptHandler):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    func = sub.func
                    if (isinstance(func, ast.Attribute) and
                        isinstance(func.value, ast.Name) and
                        func.value.id == 'logger' and
                        func.attr in ('error', 'warning', 'debug')):
                        acc_except_loggers_total += 1
                        has_exc_info = any(kw.arg == 'exc_info' for kw in sub.keywords)
                        if not has_exc_info:
                            acc_except_loggers_no_exc += 1
                            print(f"    [R51 漏洞] L{sub.lineno}: {acc_dialog_source.split(chr(10))[sub.lineno-1].strip()[:100]}")
    print(f"  [account_management_dialog.py except 块内 logger]: {acc_except_loggers_total} 处")
    print(f"  [account_management_dialog.py 漏 exc_info=True]: {acc_except_loggers_no_exc} 处 (R158-C 报告 18 处, 差异可能是 logger.debug 也算)")
except FileNotFoundError:
    print(f"  [{acc_dialog_path}]: NOT FOUND")


print("\n" + "=" * 80)
print("R159 补充验证 4: R51 软解析 (logger.debug 屏蔽违反 R51 #5) 验证")
print("=" * 80)
# 验证 R51 铁律 #5: logger.debug 屏蔽严重异常 (R51-DIALOG-SWEEP-2 L352)
# 简单搜索 logger.debug in except handler
print(f"  [全项目 except 块内 logger.debug 总数]:")
debug_in_except = 0
for search_dir in ['core', 'gui', 'web/backend']:
    dir_path = PROJECT_ROOT / search_dir
    if not dir_path.exists():
        continue
    for py_file in dir_path.rglob('*.py'):
        if any(skip in py_file.parts for skip in ['.git', '__pycache__', '.pytest_cache']):
            continue
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(content)
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        func = sub.func
                        if (isinstance(func, ast.Attribute) and
                            isinstance(func.value, ast.Name) and
                            func.value.id == 'logger' and
                            func.attr == 'debug'):
                            debug_in_except += 1
print(f"    计数: {debug_in_except} 处")


print("\n" + "=" * 80)
print("R159 补充验证 5: HVD-157-NEW-1-EXT (Layer 6) 验证")
print("=" * 80)
arcs_path = 'core/services/advanced_risk_control_service.py'
try:
    with open(arcs_path, 'r', encoding='utf-8') as f:
        arcs_source = f.read()
    # 找 risk_metrics_payload 字段
    rmp_lines = [i + 1 for i, l in enumerate(arcs_source.split('\n'))
                 if 'risk_metrics_payload' in l]
    print(f"  [AdvancedRiskControlService risk_metrics_payload 引用]: {len(rmp_lines)} 处")
    # 找 account_id 字段
    acct_id_in_payload = 'risk_metrics_payload' in arcs_source and 'account_id' in arcs_source
    # 检查 L1085-1095 实际内容
    arcs_lines = arcs_source.split('\n')
    print(f"  [L1085-1095 实际内容]:")
    for i in range(1084, min(1096, len(arcs_lines))):
        print(f"    L{i+1}: {arcs_lines[i].rstrip()[:120]}")
except FileNotFoundError:
    print(f"  [{arcs_path}]: NOT FOUND")


print("\n" + "=" * 80)
print("R159 补充验证完成")
print("=" * 80)
