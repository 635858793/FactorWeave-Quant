#!/usr/bin/env python3
"""R175-B R51 §7.1 #5 精细版: 只检测 except 块内 logger.warning/error 缺 exc_info"""
import os
import ast
import json

BUSINESS_CRITICAL_PATHS = [
    'core/events/event_bus.py',
    'core/trading_engine.py',
    'core/trading/order_executor.py',
    'core/trading/order_service.py',
    'core/trading/account_manager.py',
    'core/trading/order_monitor.py',
    'core/services/advanced_risk_control_service.py',
    'core/services/dynamic_risk_adjustment_service.py',
    'core/risk_rule_manager.py',
    'core/agents/bettafish_agent.py',
    'core/agents/sentiment_agent.py',
    'core/agents/news_agent.py',
    'core/agents/technical_agent.py',
    'core/agents/risk_agent.py',
    'core/services/ai_selection_integration_service.py',
    'core/services/hybrid_recommendation_engine.py',
    'core/services/service_bootstrap.py',
    'core/coordinators/event_coordinator.py',
    'core/coordinators/main_window_coordinator.py',
    'core/importdata/import_execution_engine.py',
]


def find_except_logger_violations(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        return [], str(e)
    violations = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [], f'SyntaxError: {e}'

    def visit(node, in_except=False):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ExceptHandler):
                # 进入 except 块, 递归标记
                for stmt in child.body:
                    visit(stmt, in_except=True)
            elif isinstance(child, (ast.Try, ast.If, ast.For, ast.While, ast.With)):
                # 子结构: 保留 in_except
                visit(child, in_except)
            elif isinstance(child, ast.Call) and in_except:
                func = child.func
                if isinstance(func, ast.Attribute) and func.attr in ('warning', 'error'):
                    if isinstance(func.value, ast.Name) and 'logger' in func.value.id.lower():
                        has_exc_info = any(kw.arg == 'exc_info' for kw in child.keywords)
                        if not has_exc_info:
                            line_no = child.lineno
                            lines = source.split('\n')
                            line_content = lines[line_no - 1].strip() if line_no <= len(lines) else ''
                            violations.append({
                                'line': line_no,
                                'level': func.attr,
                                'text': line_content[:150],
                            })
            else:
                # 递归到下一层
                if hasattr(child, 'body') and isinstance(getattr(child, 'body', None), list):
                    visit(child, in_except)

    visit(tree, in_except=False)
    return violations, None


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    summary = {}
    total = 0
    file_count = 0
    error_files = []

    for rel_path in BUSINESS_CRITICAL_PATHS:
        full_path = os.path.join(root, rel_path.replace('/', os.sep))
        if not os.path.exists(full_path):
            error_files.append((rel_path, 'not found'))
            continue
        file_count += 1
        violations, err = find_except_logger_violations(full_path)
        if err:
            error_files.append((rel_path, err))
            continue
        summary[rel_path] = violations
        total += len(violations)

    result = {
        'total_violations': total,
        'file_count': file_count,
        'error_files': error_files,
        'per_file': summary,
    }
    out_path = os.path.join(root, '.audit_r175_b_except_logger.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'Saved to {out_path}')
    print(f'Total except-block violations: {total}, Files scanned: {file_count}')
    for p, v in sorted(summary.items()):
        if v:
            print(f'  {p}: {len(v)} violations')


if __name__ == '__main__':
    main()
