"""R164 紧急修复 v14: 仅修复已知错误行, 不引入新修改"""
import ast
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui").resolve()

# 每次只检查并报告, 不自动修改
TARGET_FILES = [
    'gui/widgets/trading_widget.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'core/trading/account_manager.py',
]


def get_syntax_error(file_path):
    content = file_path.read_text(encoding='utf-8')
    try:
        ast.parse(content, str(file_path))
        return None
    except SyntaxError as e:
        return e.lineno, e.msg


def main():
    for rel in TARGET_FILES:
        p = ROOT / rel
        err = get_syntax_error(p)
        if err is None:
            print(f'[OK]   {rel}')
            continue
        line_no, msg = err
        lines = p.read_text(encoding='utf-8').split('\n')
        print(f'\n=== {rel} L{line_no} ===')
        for i in range(max(0, line_no-3), min(len(lines), line_no+3)):
            marker = ' >>>' if i+1 == line_no else '    '
            print(f'{marker} L{i+1}: {lines[i][:150]}')


if __name__ == '__main__':
    main()
