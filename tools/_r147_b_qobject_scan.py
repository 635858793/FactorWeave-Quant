"""
R147 HVD-147-B 立项评估工具: 扫描所有 QObject Service.

为什么需要这个工具:
  - R147-B 报告说"10 个 QObject Service"但实际只找到 6 个
  - R147-D 漏报 3 个 vs 实际 4 个
  - 立项前必须 4 源验证 + 完整 AST 扫描, 不能只信报告

R104 §12 铁律 #3 (AST 递归 with.body) + 铁律 #5 (AST unparse)
"""
import ast
import sys
from pathlib import Path
from collections import defaultdict


def scan_qobject_classes(root_dir: Path):
    """扫描 root_dir 下所有 .py 文件, 找出继承 QObject 的类."""
    qobject_classes = []
    for py_file in root_dir.rglob('*.py'):
        if any(part in str(py_file) for part in ['site-packages', 'venv', '__pycache__', '.pytest_cache']):
            continue
        try:
            source = py_file.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # 检查基类
                for base in node.bases:
                    base_name = None
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr

                    if base_name == 'QObject':
                        qobject_classes.append({
                            'file': str(py_file.relative_to(root_dir)),
                            'line': node.lineno,
                            'class_name': node.name,
                        })
                        break
    return qobject_classes


def main():
    project_root = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
    root = project_root / "core"
    qobject_classes = scan_qobject_classes(root)

    # 按文件分组
    by_file = defaultdict(list)
    for cls in qobject_classes:
        by_file[cls['file']].append(cls)

    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append(f"R147-B HVD-147-B Assessment: QObject Service full list in core/")
    output_lines.append(f"Root: {root}")
    output_lines.append(f"Total: {len(qobject_classes)} QObject classes")
    output_lines.append("=" * 80)

    for file, classes in sorted(by_file.items()):
        output_lines.append(f"\n[{file}]")
        for cls in classes:
            is_service = cls['class_name'].endswith('Service') or 'Service' in cls['class_name']
            tag = "[SERVICE]" if is_service else "[BUSINESS]"
            output_lines.append(f"  L{cls['line']}: {cls['class_name']} {tag}")

    service_qobjects = [c for c in qobject_classes
                        if c['class_name'].endswith('Service')
                        or 'Scheduler' in c['class_name']
                        or 'Executor' in c['class_name']
                        or 'Monitor' in c['class_name']]
    output_lines.append(f"\n\n=== QObject Service candidates ({len(service_qobjects)}) ===")
    for c in sorted(service_qobjects, key=lambda x: x['file']):
        output_lines.append(f"  {c['file']}:L{c['line']}  {c['class_name']}")

    # 写文件 (ASCII 安全)
    output = '\n'.join(output_lines)
    Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/.trae/reports/rounds/.r147_b_qobject_scan.txt").write_text(
        output, encoding='utf-8'
    )
    print(f"Written to .trae/reports/rounds/.r147_b_qobject_scan.txt ({len(output)} bytes)")


if __name__ == '__main__':
    main()
