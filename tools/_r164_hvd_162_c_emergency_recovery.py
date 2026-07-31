#!/usr/bin/env python3
"""R164 紧急恢复脚本: 修复 v1/v2 脚本破坏的 f-string 语法

R162 教训应用: 误判 50 处基于已撤销, 必须 TDD 验证

恢复模式:
1. f-string 内错误: {str(e, exc_info=True) → {str(e)}
   原始: logger.error(f"...{str(e)}")
   错误: logger.error(f"...{str(e, exc_info=True)
   恢复: logger.error(f"...{str(e)}", exc_info=True)

2. 多行调用双重 exc_info: ...\n, exc_info=True) → ...
   原始: logger.warning(\n    f"...",\n    f"...",\n)
   错误: logger.warning(\n    f"...",\n    f"...",\n, exc_info=True)
   恢复: logger.warning(\n    f"...",\n    f"...",\n, exc_info=True)
   实际只需要一个 exc_info=True, 重复需要清理

3. 缩进破坏: 多行 logger 调用因在 except 块中识别为新 except 关键字
   原始: except Exception as e:\n    logger.warning(\n        f"..."\n    )
   错误: except Exception as e:\nlogger.warning(\n    f"..."\n, exc_info=True)
"""
import re
from pathlib import Path

ROOT = Path(".")

# 受影响的 7 文件 (R164 v1/v2 误修复)
AFFECTED_FILES = [
    'gui/widgets/trading_widget.py',
    'core/agents/risk_agent.py',
    'core/risk_exporter.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'core/risk/risk_event_subscribers.py',
    'core/trading/account_manager.py',
    'core/services/signal_trading_bridge.py',
    'core/services/ai_selection_risk_control_service.py',
    'core/risk_monitoring/sherman_morrison_correlation.py',
]


def fix_broken_fstring(content: str) -> tuple:
    """修复 f-string 内错误插入的 exc_info=True

    模式: f"...{xxx, exc_info=True) ...stuff..., exc_info=True)
    应该: f"...{xxx}) ...stuff..., exc_info=True)

    实际上需要分两步:
    1. 修复 f-string 内的错误语法
    2. 已经在 logger.* 调用末尾添加了 , exc_info=True), 检查重复
    """
    fixed_count = 0

    # Step 1: 修复 f-string 内错误的 exc_info=True 插入
    # 模式: {var, exc_info=True) 或 {var, exc_info=True}
    # 简化为: {var}, 然后 logger.* 末尾加 , exc_info=True
    pattern_fstring = re.compile(r'\{(\w+(?:\([^)]*\))?), exc_info=True\)', re.MULTILINE)

    def replace_fstring(m):
        return f'{{{m.group(1)}}}'

    new_content = pattern_fstring.sub(replace_fstring, content)
    fixed_count += len(pattern_fstring.findall(content))

    return new_content, fixed_count


def fix_duplicate_exc_info(content: str) -> tuple:
    """修复重复的 exc_info=True

    模式 1: 在 logger.* 调用内已经正确添加, 但有 v2 错误的额外添加
    实际上 v2 修复后, 可能出现:
    logger.error(f"...") , exc_info=True)  ← 多余的 )
    """
    # 不需要处理, 因为前面的 f-string 修复会自动让语法正确
    return content, 0


def fix_indent_broken_except(content: str) -> tuple:
    """修复缩进被破坏的 except 块

    模式: except Exception as e:\nlogger.warning(...
    应该: except Exception as e:\n    logger.warning(...
    """
    # 找到 except 关键字后跟 logger 调用但没有缩进的情况
    fixed_count = 0
    lines = content.split('\n')
    new_lines = []

    for i, line in enumerate(lines):
        # 检测 except 后第 i+1 行直接是 logger 调用 (无缩进)
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            if re.match(r'except\s+.*\s*as\s+\w+\s*:', line) and re.match(r'logger\.', next_line):
                # next_line 需要加 except 缩进
                # except 通常 4 空格缩进 (在 method 内)
                indent = '    '
                if next_line and not next_line.startswith(' '):
                    lines[i + 1] = indent + next_line
                    fixed_count += 1

        new_lines.append(line)

    return '\n'.join(new_lines), fixed_count


def main():
    print("=" * 70)
    print("R164 紧急恢复: 修复 v1/v2 脚本破坏的 f-string 语法")
    print("=" * 70)
    print()

    total_fixed = 0
    for rel_path in AFFECTED_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            print(f"  ⚠️  文件不存在: {rel_path}")
            continue

        original = full_path.read_text(encoding='utf-8')
        content = original

        # Step 1: 修复 f-string 内错误
        content, c1 = fix_broken_fstring(content)
        # Step 2: 修复缩进
        content, c2 = fix_indent_broken_except(content)

        if c1 + c2 > 0:
            full_path.write_text(content, encoding='utf-8')
            print(f"  ✅ {rel_path}: 修复 {c1 + c2} 处 (f-string={c1}, indent={c2})")
            total_fixed += c1 + c2
        else:
            print(f"  ✓  {rel_path}: 无需修复")

    print(f"\n  总修复: {total_fixed} 处")
    print()

    # 验证
    print("【验证: AST 语法检查】")
    import ast
    errors = 0
    for rel_path in AFFECTED_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue
        try:
            ast.parse(full_path.read_text(encoding='utf-8'))
            print(f"  ✅ {rel_path}: 语法 OK")
        except SyntaxError as e:
            errors += 1
            print(f"  ❌ {rel_path}: 语法错误 L{e.lineno}: {e.msg}")

    print()
    print("=" * 70)
    if errors == 0:
        print("🎉 紧急恢复完成, 全部语法 OK!")
    else:
        print(f"⚠️  仍有 {errors} 个文件语法错误")
    print("=" * 70)
    return errors


if __name__ == '__main__':
    import sys
    errors = main()
    sys.exit(0 if errors == 0 else 1)
