"""R128 子智能体 B: 验证修复后状态.

R104 §12 5 铁律 + R6 §6.1 8 铁律 + R85 假修复鉴别 4 步法
"""
import ast
import sys
import json
from pathlib import Path

TARGET_FILES = [
    'core/services/unified_data_manager.py',
    'core/services/ai_selection_integration_service.py',
    'core/services/dynamic_risk_adjustment_service.py',
    'core/strategy/strategy_engine.py',
    'core/trading/order_service.py',
    'core/trading/account_manager.py',
]

LOGGER_METHODS = {'error', 'warning', 'warn', 'info', 'debug', 'exception', 'critical', 'trace'}


def _is_logger_call(node):
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in LOGGER_METHODS:
        return False
    return True


def _has_exc_info(node):
    for kw in node.keywords:
        if kw.arg == 'exc_info':
            return True
    return False


def scan_file(file_path):
    src = Path(file_path).read_text(encoding='utf-8')
    tree = ast.parse(src)  # 验证 AST 解析
    total = 0
    missing = 0
    lines = src.splitlines()
    violations = []

    def _walk(node):
        nonlocal total, missing
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ExceptHandler):
                if child.body:
                    for stmt in child.body:
                        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                            if _is_logger_call(stmt.value):
                                total += 1
                                if not _has_exc_info(stmt.value):
                                    missing += 1
                                    line_no = stmt.value.lineno
                                    violations.append({
                                        'line': line_no,
                                        'method': stmt.value.func.attr,
                                        'content': lines[line_no - 1].strip()[:200],
                                    })
                        _walk(stmt)
            elif isinstance(child, ast.Try):
                _walk(child)
            else:
                _walk(child)

    _walk(tree)
    return total, missing, violations, src


if __name__ == '__main__':
    print("=" * 80)
    print("R128 子智能体 B: 修复后验证")
    print("=" * 80)

    results = {}
    for f in TARGET_FILES:
        try:
            total, missing, violations, src = scan_file(f)
            exc_info_count = src.count('exc_info=True')
            results[f] = {
                'total_logger_in_except': total,
                'missing_exc_info': missing,
                'total_exc_info': exc_info_count,
                'syntax_ok': True,
            }
            print(f"\n[{f}]")
            print(f"  AST parse: OK")
            print(f"  except 块内 logger 调用: {total}")
            print(f"  缺 exc_info=True: {missing}")
            print(f"  全文件 exc_info=True 总数: {exc_info_count}")
            if missing > 0:
                print(f"  ⚠️ 残留违规: {missing}")
                for v in violations[:3]:
                    print(f"    L{v['line']:>5} logger.{v['method']:>8} | {v['content'][:120]}")
        except SyntaxError as e:
            results[f] = {'syntax_error': f'{e.msg} at L{e.lineno}'}
            print(f"\n[{f}]")
            print(f"  ❌ SyntaxError: {e.msg} at L{e.lineno}")

    # 汇总
    print()
    print("=" * 80)
    total_missing = sum(r.get('missing_exc_info', 0) for r in results.values())
    total_logger = sum(r.get('total_logger_in_except', 0) for r in results.values())
    total_ei = sum(r.get('total_exc_info', 0) for r in results.values())
    syntax_errors = [f for f, r in results.items() if 'syntax_error' in r]

    print(f"汇总:")
    print(f"  6 文件 except 块内 logger 调用总数: {total_logger}")
    print(f"  6 文件 exc_info=True 总数: {total_ei}")
    print(f"  6 文件残留违规: {total_missing}")
    print(f"  语法错误文件: {len(syntax_errors)}")
    if total_missing == 0 and len(syntax_errors) == 0:
        print(f"  ✅ GREEN 状态达成: 0 残留, 0 语法错误")
    print("=" * 80)

    # 写入 JSON
    with open('d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/_r128_b_post_fix_verify.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细验证已写入 _r128_b_post_fix_verify.json")

    sys.exit(0 if total_missing == 0 and len(syntax_errors) == 0 else 1)
