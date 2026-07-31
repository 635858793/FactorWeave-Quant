"""R164 紧急修复 v13: 全面修复所有日志调用错误"""
import re
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui").resolve()

TARGET_FILES = [
    'gui/widgets/trading_widget.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'core/trading/account_manager.py',
]


def fix_all_log_calls(content: str) -> str:
    """应用所有已知修复模式"""
    original = content

    # 模式 A: f-string 包含 (exc_info=True) 字符串但实际缺 exc_info 关键字参数
    # 修复: logger.error(f"xxx (exc_info=True)") -> logger.error("xxx (exc_info=True)", exc_info=True)
    content = re.sub(
        r'logger\.(error|warning|critical)\(f"([^"]*?)\(exc_info=True\)"\)',
        r'logger.\1(f"\2(exc_info=True)", exc_info=True)',
        content,
    )

    # 模式 B: logger.error(f"xxx{exc_info=True) 缺右括号
    # 修复: 添加 )", exc_info=True)
    content = re.sub(
        r'logger\.(error|warning|critical)\(f"([^"]*?)\{([^}]*?),\s*exc_info=True\)$',
        r'logger.\1(f"\2{\3}", exc_info=True)',
        content,
        flags=re.MULTILINE,
    )

    # 模式 C: logger.error(f"xxx{str(e) 缺 }", exc_info=True)
    # 这种错误模式: 行以 logger.error(f" 开头, 不含完整闭合
    lines = content.split('\n')
    new_lines = []
    for i, line in enumerate(lines):
        # 匹配: 行以 logger.xxx( 开头但 rstrip() 后括号不平衡
        stripped = line.rstrip()
        if re.match(r'\s*logger\.(error|warning|critical)\(', stripped):
            open_count = stripped.count('(') - stripped.count(')')
            # 在 f-string 内, 还要考虑 { } 平衡
            # 简单判断: 如果行不以 ), 结尾且包含 ( 但 ) 少于 (
            if open_count > 0 and not stripped.endswith(')'):
                # 加上 )", exc_info=True) 或类似
                # 但 f-string 内可能 { 比 } 多
                brace_open = stripped.count('{') - stripped.count('}')
                if brace_open > 0:
                    # f-string 未闭合
                    # 简单修复: 加 )", exc_info=True) 重新平衡
                    if stripped.endswith('"'):
                        line = line + ', exc_info=True)'
                    else:
                        line = line + '")' if not stripped.endswith('"') else line
                else:
                    if not stripped.endswith(')'):
                        line = line + ', exc_info=True)'
        new_lines.append(line)
    content = '\n'.join(new_lines)

    return content


def fix_orphaned_lines(content: str) -> str:
    """修复孤立行: 仅包含 ', exc_info=True,' 或 ', exc_info=True)' 等"""
    lines = content.split('\n')
    new_lines = []
    skip_next_blank = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in (', exc_info=True', ', exc_info=True,', ', exc_info=True)', 'exc_info=True'):
            # 孤立行, 应合并到上一行
            if new_lines:
                prev = new_lines[-1].rstrip()
                if prev.endswith(','):
                    new_lines[-1] = prev + ' exc_info=True)'
                elif prev.endswith('('):
                    new_lines[-1] = prev + 'exc_info=True)'
                else:
                    new_lines[-1] = prev + ', exc_info=True)' if not prev.endswith('exc_info=True)') else prev
            continue
        new_lines.append(line)
    return '\n'.join(new_lines)


def fix_indentation(content: str) -> str:
    """修复缩进问题: logger 应该在 except 块内缩进"""
    # 模式: except ... :\n[空白]?logger\. -> except ... :\n    logger\.
    content = re.sub(
        r'(except[^\n]*:\n)([ \t]*)logger\.',
        r'\1    logger.',
        content,
    )
    # 模式: with ... :\n[空白]?logger\. -> with ... :\n        logger\.
    # 但不要修改已经正确缩进的
    return content


def main():
    print("=" * 60)
    print("R164 紧急修复 v13: 全面修复")
    print("=" * 60)
    import ast
    for rel in TARGET_FILES:
        p = ROOT / rel
        if not p.exists():
            print(f'[SKIP] {rel}')
            continue
        content = p.read_text(encoding='utf-8')

        # 多次迭代修复, 每次都尝试编译
        for iteration in range(10):
            try:
                ast.parse(content, str(p))
                break
            except SyntaxError:
                # 尝试修复
                content = fix_all_log_calls(content)
                content = fix_orphaned_lines(content)
                content = fix_indentation(content)
                p.write_text(content, encoding='utf-8')

        try:
            ast.parse(content, str(p))
            print(f'[OK]   {rel}')
        except SyntaxError as e:
            print(f'[FAIL] {rel}: line {e.lineno}: {e.msg}')


if __name__ == '__main__':
    main()
