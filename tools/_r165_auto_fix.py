#!/usr/bin/env python3
"""R165 自动修复 trading_widget.py 和 enhanced_risk_monitor.py 的 IndentationError + SyntaxError

策略:
1. 读取文件
2. 用 ast 找到 except handler 块的缩进
3. 把 4 空格缩进的 logger 调用改成 8 空格
4. 处理 f-string 未闭合
5. 写回文件
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def fix_trading_widget():
    """修复 trading_widget.py"""
    file_path = ROOT / "gui/widgets/trading_widget.py"
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    fixed_count = 0
    for i, line in enumerate(lines):
        # 模式: 4 空格缩进的 logger 调用
        m = re.match(r'^    (logger\.\w+\(.*)$', line)
        if not m:
            continue
        # 看上一行是否 except
        if i == 0:
            continue
        prev = lines[i-1]
        if not re.match(r'^\s+except\s+', prev):
            continue
        # 修复: 改为 8 空格
        lines[i] = '        ' + m.group(1)
        fixed_count += 1
        # 修复可能未闭合的 f-string
        if '{str(e}' in lines[i] and '{str(e})' in lines[i]:
            lines[i] = lines[i].replace('{str(e})', '{str(e)}')
        if lines[i].count('"') % 2 == 1:
            lines[i] = lines[i] + '"' if lines[i].count('"') == 1 else lines[i] + ")"

    new_content = '\n'.join(lines)
    file_path.write_text(new_content, encoding='utf-8')
    return fixed_count


def fix_enhanced_risk_monitor():
    """修复 enhanced_risk_monitor.py"""
    file_path = ROOT / "core/risk_monitoring/enhanced_risk_monitor.py"
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    fixed_count = 0
    for i, line in enumerate(lines):
        m = re.match(r'^    (logger\.\w+\(.*)$', line)
        if not m:
            continue
        if i == 0:
            continue
        prev = lines[i-1]
        if not re.match(r'^\s+except\s+', prev):
            continue
        lines[i] = '        ' + m.group(1)
        fixed_count += 1
        if '{str(e}' in lines[i] and '{str(e})' in lines[i]:
            lines[i] = lines[i].replace('{str(e})', '{str(e)}')

    new_content = '\n'.join(lines)
    file_path.write_text(new_content, encoding='utf-8')
    return fixed_count


def verify_syntax(file_path: Path) -> bool:
    try:
        ast.parse(file_path.read_text(encoding='utf-8'))
        return True
    except (SyntaxError, IndentationError) as e:
        print(f"  [REMAINING ERROR] {e.lineno}: {e.msg}")
        return False


def main():
    print("=" * 80)
    print("R165 自动修复 4 文件 SyntaxError/IndentationError")
    print("=" * 80)

    # 1. trading_widget.py
    print("\n[1/2] trading_widget.py:")
    n = fix_trading_widget()
    print(f"  修复 {n} 行 (4→8 空格缩进)")
    ok = verify_syntax(ROOT / "gui/widgets/trading_widget.py")
    print(f"  语法验证: {'✅ OK' if ok else '❌ FAIL'}")

    # 2. enhanced_risk_monitor.py
    print("\n[2/2] enhanced_risk_monitor.py:")
    n = fix_enhanced_risk_monitor()
    print(f"  修复 {n} 行 (4→8 空格缩进)")
    ok = verify_syntax(ROOT / "core/risk_monitoring/enhanced_risk_monitor.py")
    print(f"  语法验证: {'✅ OK' if ok else '❌ FAIL'}")


if __name__ == '__main__':
    main()
