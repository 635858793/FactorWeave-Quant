"""R128 子智能体 B 深度分析: 找出 7 文件中所有假修复模式."""
import ast
import re
import json
import sys
from pathlib import Path

# 7 个目标文件
TARGET_FILES = [
    ('core/services/unified_data_manager.py', 13),
    ('core/services/ai_selection_integration_service.py', 19),
    ('core/services/dynamic_risk_adjustment_service.py', 8),
    ('core/strategy/strategy_engine.py', 14),
    ('core/trading/order_service.py', 18),
    ('core/trading/account_manager.py', 2),
]


def analyze_file(file_path, expected_count):
    """深度分析文件: 找出真修复 vs 假修复."""
    src = Path(file_path).read_text(encoding='utf-8')
    lines = src.splitlines()

    # 用 AST 解析每个函数/方法
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {
            'file': file_path,
            'syntax_error': f'{e.msg} at L{e.lineno}',
            'expected_count': expected_count,
        }

    # 找出所有 R145-F 标记行
    marker_lines = []
    for i, line in enumerate(lines, 1):
        if 'R145-F' in line:
            marker_lines.append((i, line))

    # 分析每行的实际状态
    issues = []
    for ln, content in marker_lines:
        # 提取 logger 调用部分
        # 模式: logger.XXX(...)  # R145-F 批量修复
        # 或:   # Fix: ...  # R145-F 批量修复
        if re.search(r'logger\.\w+\([^)]*exc_info=True\s*\)', content):
            # logger 调用且 exc_info=True 闭合
            issues.append({
                'line': ln,
                'content': content,
                'status': 'OK',
                'note': 'logger 调用, exc_info=True 闭合'
            })
        elif re.search(r'#\s*Fix:', content) and 'exc_info=True' in content:
            # 注释行, 含 exc_info=True
            issues.append({
                'line': ln,
                'content': content,
                'status': 'COMMENT_LINE',
                'note': '纯注释行, 含 exc_info=True 描述'
            })
        elif re.search(r'#\s*R115 HVD-63', content) and 'exc_info=True' in content:
            # R115 HVD-63 注释行
            issues.append({
                'line': ln,
                'content': content,
                'status': 'COMMENT_LINE',
                'note': 'R115 HVD-63 注释行, 含 exc_info=True 描述'
            })
        else:
            issues.append({
                'line': ln,
                'content': content,
                'status': 'UNKNOWN',
                'note': '未识别模式'
            })

    # 统计
    status_count = {}
    for issue in issues:
        status_count[issue['status']] = status_count.get(issue['status'], 0) + 1

    return {
        'file': file_path,
        'expected_count': expected_count,
        'actual_count': len(marker_lines),
        'issues': issues,
        'status_count': status_count,
    }


if __name__ == '__main__':
    print("=" * 80)
    print("R128 子智能体 B 深度分析: 7 文件 R145-F 假修复模式")
    print("=" * 80)

    results = []
    for f, expected in TARGET_FILES:
        result = analyze_file(f, expected)
        results.append(result)
        if 'syntax_error' in result:
            print(f"\n[{f}] 语法错误: {result['syntax_error']}")
        else:
            print(f"\n[{f}]")
            print(f"  预期: {expected} 处, 实际: {result['actual_count']} 处 (# R145-F 标记)")
            print(f"  状态分布: {result['status_count']}")
            print(f"  状态详情:")
            for issue in result['issues']:
                print(f"    L{issue['line']:>5} [{issue['status']:>15}] {issue['content'][:120]}")

    # 汇总
    print()
    print("=" * 80)
    print("汇总")
    print("=" * 80)
    total_expected = sum(r['expected_count'] for r in results if 'syntax_error' not in r)
    total_actual = sum(r['actual_count'] for r in results if 'syntax_error' not in r)
    print(f"预期总假修复: {total_expected} 处")
    print(f"实际 # R145-F 标记: {total_actual} 处")
    print(f"差异: {total_actual - total_expected} 处 (含注释行标记, 非假修复)")

    # 写入 JSON
    with open('d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/_r128_b_deep_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细分析已写入 _r128_b_deep_analysis.json")
