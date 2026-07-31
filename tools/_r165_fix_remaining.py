#!/usr/bin/env python3
"""R165 终极修复 - 找出 enhanced_risk_monitor.py 1 missing + 修 R162 假修复 9 missing"""
import ast
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def find_missing(file_path: Path) -> list:
    """找到文件内所有 exc_info 缺失的 logger 调用"""
    if not file_path.exists():
        return []
    try:
        content = file_path.read_text(encoding='utf-8')
        tree = ast.parse(content)
    except (SyntaxError, IndentationError) as e:
        return [(0, f"语法错误: {e}")]

    missing = []
    lines = content.split('\n')
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not (isinstance(child.func, ast.Attribute)
                    and child.func.attr in ('error', 'warning', 'critical')
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == 'logger'):
                continue
            if not any(kw.arg == 'exc_info' for kw in child.keywords):
                line_no = child.lineno
                line_text = lines[line_no - 1] if line_no <= len(lines) else ''
                missing.append((line_no, line_text.strip()[:100]))
    return missing


def fix_file(file_path: Path) -> int:
    """为所有 logger.error/warning/critical 调用添加 exc_info=True

    策略: 找到每个 logger 调用, 在右括号前加 , exc_info=True
    """
    content = file_path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(content)
    except (SyntaxError, IndentationError) as e:
        print(f"  语法错误, 跳过: {e}")
        return 0

    # 收集所有需要修改的 Call 节点
    modifications = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not (isinstance(child.func, ast.Attribute)
                    and child.func.attr in ('error', 'warning', 'critical')
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == 'logger'):
                continue
            if any(kw.arg == 'exc_info' for kw in child.keywords):
                continue
            # 找到此调用的结束位置 (右括号)
            # child.end_col_offset 是右括号 +1 的位置
            # 我们需要在右括号前插入 , exc_info=True
            modifications.append({
                'lineno': child.lineno,
                'end_col': child.end_col_offset,
                'has_paren': True,
            })

    # 按 lineno 倒序修改,避免偏移
    lines = content.split('\n')
    # 简单处理: 找到每行 logger 调用的右括号, 在前面加
    fixed = 0
    for mod in modifications:
        ln = mod['lineno']
        if ln > len(lines):
            continue
        line = lines[ln - 1]
        # 找到 logger 调用的右括号 (最右的 ')'  且 后面没有其他内容)
        # 简单: 在行末加 , exc_info=True (如果有 ')' 结尾) 或不处理
        # 实际上 line 可能多行,所以这是不准确的
        # 改用: 找到最后一个 ')' 位置
        last_paren = line.rfind(')')
        if last_paren == -1:
            continue
        # 检查 ', exc_info' 是否已存在
        if ', exc_info' in line:
            continue
        # 插入
        new_line = line[:last_paren] + ', exc_info=True' + line[last_paren:]
        lines[ln - 1] = new_line
        fixed += 1

    new_content = '\n'.join(lines)
    file_path.write_text(new_content, encoding='utf-8')
    return fixed


def main():
    files = [
        "core/risk_monitoring/enhanced_risk_monitor.py",
        "core/trading/account_repository.py",
        "core/trading/order_event_handlers.py",
    ]
    for rel in files:
        fp = ROOT / rel
        print(f"\n=== {rel} ===")
        missing = find_missing(fp)
        if not missing:
            print(f"  无 missing")
            continue
        print(f"  发现 {len(missing)} missing:")
        for ln, txt in missing:
            print(f"    L{ln}: {txt}")
        # 修复
        fixed = fix_file(fp)
        print(f"  修复 {fixed} 行")
        # 再次验证
        missing2 = find_missing(fp)
        print(f"  修复后剩余: {len(missing2)} missing")


if __name__ == '__main__':
    main()
