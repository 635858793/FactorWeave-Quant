"""
R174 全项目扫描: 找所有有 SyntaxError 的 Python 文件
"""
import ast
import sys
from pathlib import Path


def find_broken_files(root_dir: str) -> list:
    """找出所有无法 AST 解析的 Python 文件"""
    broken = []
    root = Path(root_dir)
    for py_file in root.rglob('*.py'):
        # 跳过虚拟环境/构建目录
        skip_parts = {'__pycache__', '.venv', 'venv', 'node_modules', 'dist', 'build', '.git', 'site-packages'}
        if any(part in skip_parts for part in py_file.parts):
            continue
        try:
            ast.parse(py_file.read_text(encoding='utf-8', errors='replace'))
        except SyntaxError as e:
            broken.append((str(py_file), e.lineno, e.msg))
        except Exception as e:
            broken.append((str(py_file), 0, f'{type(e).__name__}: {e}'))
    return broken


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui'
    print(f"Scanning {target}...")
    broken = find_broken_files(target)
    print(f"Found {len(broken)} broken files:")
    for path, lineno, msg in broken:
        print(f"  L{lineno}: {path}: {msg}")
