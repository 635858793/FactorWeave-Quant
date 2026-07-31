"""
R197-A Debug: 验证 R196-B vs R197-A 扫描器差异
"""
import ast
import os
import json
from pathlib import Path
from typing import List, Dict

TARGET_SUBDIRS = [
    "core/ui",
    "core/webgpu",
    "core/importdata",
    "core/advanced_optimization",
]

# R118 ImportError 豁免模式
IMPORT_ERROR_EXEMPT_PATTERNS = [
    "降级", "fallback", "ImportError", "compat", "optional", "未安装",
    "traceback.format_exc", "logger.info", "logger.debug", "# R118",
]

# R196-B vs R197-A 差异对比
def scan_v196_b(file_path: Path) -> List[Dict]:
    """R196-B 扫描器: 只在函数体内找 except 块"""
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    source_lines = source.split("\n")

    def visit_with_except(node):
        if isinstance(node, ast.ExceptHandler):
            for stmt in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if not isinstance(stmt, ast.Call):
                    continue
                if not isinstance(stmt.func, ast.Attribute):
                    continue
                func_name = stmt.func.attr
                if not func_name.startswith(("warning", "error", "critical", "info", "debug")):
                    continue
                if func_name == "exception":
                    continue
                if isinstance(stmt.func.value, ast.Name):
                    if stmt.func.value.id not in {"logger", "_logger", "log"}:
                        continue
                elif isinstance(stmt.func.value, ast.Attribute):
                    if not stmt.func.value.attr.endswith("logger"):
                        continue
                else:
                    continue
                has_exc_info = any(
                    kw.arg == "exc_info" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in stmt.keywords
                )
                if has_exc_info:
                    continue
                line_text = source_lines[stmt.lineno - 1] if stmt.lineno <= len(source_lines) else ""
                if any(pat in line_text for pat in IMPORT_ERROR_EXEMPT_PATTERNS):
                    continue
                violations.append({"file": str(file_path), "line": stmt.lineno, "function": func_name})

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in node.body:
                if isinstance(stmt, ast.Try):
                    for handler in stmt.handlers:
                        visit_with_except(handler)
    return violations


def scan_v197_a(file_path: Path) -> List[Dict]:
    """R197-A 扫描器: 在所有位置找 except 块"""
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    source_lines = source.split("\n")

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Try, ast.TryStar)):
            continue
        for handler in node.handlers:
            if not isinstance(handler, ast.ExceptHandler):
                continue
            for stmt in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
                if not isinstance(stmt, ast.Call):
                    continue
                if not isinstance(stmt.func, ast.Attribute):
                    continue
                func_name = stmt.func.attr
                if not func_name.startswith(("warning", "error", "critical", "info", "debug")):
                    continue
                if func_name == "exception":
                    continue
                if isinstance(stmt.func.value, ast.Name):
                    if stmt.func.value.id not in {"logger", "_logger", "log"}:
                        continue
                elif isinstance(stmt.func.value, ast.Attribute):
                    if not stmt.func.value.attr.endswith("logger"):
                        continue
                else:
                    continue
                has_exc_info = any(
                    kw.arg == "exc_info" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in stmt.keywords
                )
                if has_exc_info:
                    continue
                line_text = source_lines[stmt.lineno - 1] if stmt.lineno <= len(source_lines) else ""
                if any(pat in line_text for pat in IMPORT_ERROR_EXEMPT_PATTERNS):
                    continue
                violations.append({"file": str(file_path), "line": stmt.lineno, "function": func_name})
    return violations


def main():
    project_root = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
    skip_patterns = {"test_", "__pycache__", ".git", "venv", "node_modules", "dist", "build", ".trae"}

    r196_b_total = 0
    r197_a_total = 0
    diffs = []
    for subdir in TARGET_SUBDIRS:
        target_dir = project_root / subdir
        for py_file in target_dir.rglob("*.py"):
            if any(p in str(py_file) for p in skip_patterns):
                continue
            if py_file.name.startswith("test_"):
                continue
            v196 = scan_v196_b(py_file)
            v197 = scan_v197_a(py_file)
            r196_b_total += len(v196)
            r197_a_total += len(v197)
            if len(v196) != len(v197):
                diffs.append({
                    "file": str(py_file),
                    "v196_count": len(v196),
                    "v197_count": len(v197),
                    "v197_extra": sorted([v["line"] for v in v197])[-5:] if len(v197) > len(v196) else []
                })

    print(f"R196-B 总违规: {r196_b_total}")
    print(f"R197-A 总违规: {r197_a_total}")
    print(f"差异: {r197_a_total - r196_b_total}")
    print(f"差异文件: {len(diffs)}")
    for d in diffs[:10]:
        print(f"  {d['file']}: v196={d['v196_count']} v197={d['v197_count']} extra_lines={d['v197_extra']}")


if __name__ == "__main__":
    main()
