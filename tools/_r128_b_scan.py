"""R128 子智能体 B 任务执行: R145-F 假修复批量修复 - 语法核验 + TDD."""
import ast
import sys
import re
import json
from pathlib import Path

# 7 个目标文件
TARGET_FILES = [
    'core/services/unified_data_manager.py',
    'core/services/ai_selection_integration_service.py',
    'core/services/dynamic_risk_adjustment_service.py',
    'core/strategy/strategy_engine.py',
    'core/trading/order_service.py',
    'core/trading/account_manager.py',
]


def step1_ast_parse_check():
    """Step 1: AST 解析检查所有 7 文件."""
    print("=" * 80)
    print("Step 1: AST 解析检查 - 验证 7 文件是否真正存在语法错误")
    print("=" * 80)

    results = {}
    for f in TARGET_FILES:
        try:
            src = Path(f).read_text(encoding='utf-8')
            ast.parse(src)
            print(f"OK  {f}: parse OK")
            results[f] = 'OK'
        except SyntaxError as e:
            print(f"ERR {f}: {e.msg} at line {e.lineno}")
            # 打印问题行
            lines = src.splitlines()
            for ln in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
                marker = ">>>" if ln == e.lineno - 1 else "   "
                print(f"    {marker} {ln+1}: {lines[ln].rstrip()}")
            results[f] = f'SYNTAX_ERROR_LINE_{e.lineno}'
        except Exception as e:
            print(f"EXC {f}: {e}")
            results[f] = f'EXC_{type(e).__name__}'

    return results


def step2_search_fake_fix_pattern():
    """Step 2: 搜索 R145-F 假修复模式.

    错误: exc_info=True  # 注释)  (注释含 ), 导致函数调用未闭合)
    正确: exc_info=True)  # 注释  (注释移到调用外)
    """
    print()
    print("=" * 80)
    print("Step 2: 搜索 R145-F 假修复模式 (exc_info=True  # 注释) 模式)")
    print("=" * 80)

    # 匹配 "exc_info=True  # 注释内容)  # R145-F" 模式
    # 即: exc_info=True 后跟注释, 注释里有 ), 然后是 # R145-F 标记
    # 修复后应该是: exc_info=True)  # 注释内容  # R145-F 标记
    pattern_fake = re.compile(
        r'(exc_info=True)\s+#\s*([^)]*\))\s+(#\s*R145-F[^"\n]*)',
        re.MULTILINE
    )

    results = {}
    for f in TARGET_FILES:
        src = Path(f).read_text(encoding='utf-8')
        matches = list(pattern_fake.finditer(src))
        if matches:
            print(f"\n{f}: 发现 {len(matches)} 处假修复")
            for i, m in enumerate(matches):
                line_num = src[:m.start()].count('\n') + 1
                print(f"  [{i+1}] L{line_num}: {m.group(0)[:120]}...")
                print(f"      应改为: {m.group(1)})  # {m.group(2)} {m.group(3)}")
            results[f] = matches
        else:
            print(f"{f}: 0 处假修复")
            results[f] = []

    return results


def step3_search_exc_info_paren_pattern():
    """Step 3: 搜索另一种假修复模式 - exc_info 关键字前有 ) 但前一个括号未闭."""
    print()
    print("=" * 80)
    print("Step 3: 搜索 R145 修复痕迹 (含 # R145-F 标记的所有行)")
    print("=" * 80)

    # 找出所有含 # R145-F 标记的行
    pattern_marker = re.compile(r'#\s*R145-F', re.MULTILINE)

    results = {}
    for f in TARGET_FILES:
        src = Path(f).read_text(encoding='utf-8')
        lines = src.splitlines()
        marker_lines = []
        for i, line in enumerate(lines, 1):
            if 'R145-F' in line:
                marker_lines.append((i, line))
        results[f] = marker_lines
        print(f"\n{f}: {len(marker_lines)} 处含 # R145-F 标记")
        for ln, content in marker_lines:
            print(f"  L{ln}: {content[:140]}")

    return results


if __name__ == '__main__':
    # Step 1: AST 解析
    r1 = step1_ast_parse_check()
    # Step 2: 搜索假修复模式
    r2 = step2_search_fake_fix_pattern()
    # Step 3: 搜索 R145-F 标记
    r3 = step3_search_exc_info_paren_pattern()

    # 输出汇总
    print()
    print("=" * 80)
    print("汇总: 各文件标记数 vs 假修复数")
    print("=" * 80)
    for f in TARGET_FILES:
        markers = len(r3[f])
        fakes = len(r2[f])
        print(f"{f}: markers={markers}, fake_fixes={fakes}")
