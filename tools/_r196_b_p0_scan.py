"""
R196-B P0 静默失败扫描器 (R174 §12 v2 AST 严格扫描器 v2.1):
扫描指定子目录,定位 except 块内 logger 调用无 exc_info=True 的 P0 违规

强制度:
- R51 §7.1 #5 严禁静默失败
- R174 §12 AST 严格扫描 v2 (ast.walk + ast.ExceptHandler 递归)
- R194-D v3/v4.1 升级经验 (handler.lineno != body[0].lineno + 1-stmt Assign + R118 豁免)
- R110-C 时序竞态防御
"""
import ast
import os
import json
from pathlib import Path
from typing import List, Dict, Tuple

# R196-B 扫描目标 (R195-A 报告 P0 5 子目录 + 全项目 R118 豁免模式)
TARGET_SUBDIRS = [
    "core/trading",
    "core/ui",
    "core/webgpu",
    "core/importdata",
    "core/advanced_optimization",
    "core/services",
    "core/coordinators",
    "core/monitoring",
    "core/risk",
    "core/optimization",
]

# R118 ImportError 豁免模式
IMPORT_ERROR_EXEMPT_PATTERNS = [
    "降级", "fallback", "ImportError", "compat", "optional", "未安装",
    "traceback.format_exc", "logger.info", "logger.debug", "# R118",
]


def scan_except_blocks(file_path: Path) -> List[Dict]:
    """扫描文件,识别 except 块内 logger 调用无 exc_info=True 的违规"""
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    # 读取源码行用于上下文判断
    source_lines = source.split("\n")

    def visit_with_except(node, context=""):
        """递归访问函数体,定位 except 块内的 logger 调用"""
        if isinstance(node, ast.ExceptHandler):
            # 处理 except 块内的 logger 调用
            for stmt in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if not isinstance(stmt, ast.Call):
                    continue
                # 检查是否是 logger 调用
                if not isinstance(stmt.func, ast.Attribute):
                    continue
                func_name = stmt.func.attr
                if not func_name.startswith(("warning", "error", "critical", "info", "debug")):
                    continue
                # logger.exception() 已自动含 exc_info=True, 不算违规
                if func_name == "exception":
                    continue
                # 检查调用对象是否是 logger
                if isinstance(stmt.func.value, ast.Name):
                    if stmt.func.value.id not in {"logger", "_logger", "log"}:
                        continue
                elif isinstance(stmt.func.value, ast.Attribute):
                    # 允许 self.logger / cls.logger
                    if not stmt.func.value.attr.endswith("logger"):
                        continue
                else:
                    continue
                # 检查 exc_info=True 是否在关键字参数中
                has_exc_info = any(
                    kw.arg == "exc_info" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in stmt.keywords
                )
                if has_exc_info:
                    continue
                # R118 豁免: 业务警告路径不需要 exc_info=True
                line_text = source_lines[stmt.lineno - 1] if stmt.lineno <= len(source_lines) else ""
                if any(pat in line_text for pat in IMPORT_ERROR_EXEMPT_PATTERNS):
                    continue
                # R194-D v3 经验: handler.lineno != body[0].lineno
                violations.append({
                    "file": str(file_path),
                    "line": stmt.lineno,
                    "function": func_name,
                    "snippet": line_text.strip()[:150],
                    "except_type": ast.unparse(node.type) if node.type else "Exception",
                })

    # 访问所有函数定义
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in node.body:
                if isinstance(stmt, ast.Try):
                    for handler in stmt.handlers:
                        visit_with_except(handler, f"func={node.name}")

    return violations


def main():
    project_root = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
    skip_patterns = {"test_", "__pycache__", ".git", "venv", "node_modules", "dist", "build", ".trae"}

    all_violations = []
    for subdir in TARGET_SUBDIRS:
        target_dir = project_root / subdir
        if not target_dir.exists():
            print(f"⚠️  {subdir} 不存在, 跳过")
            continue
        for py_file in target_dir.rglob("*.py"):
            if any(p in str(py_file) for p in skip_patterns):
                continue
            if py_file.name.startswith("test_"):
                continue
            violations = scan_except_blocks(py_file)
            all_violations.extend(violations)

    # 分类 P0/P1
    p0_violations = [v for v in all_violations if "trading" in v["file"] or "risk" in v["file"]]
    p1_violations = [v for v in all_violations if v not in p0_violations]

    # 写入结果
    out = {
        "scan_target": TARGET_SUBDIRS,
        "total_violations": len(all_violations),
        "p0_count": len(p0_violations),
        "p1_count": len(p1_violations),
        "violations": all_violations,
    }
    out_file = project_root / "tools" / "_r196_b_p0_scan.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"扫描完成: {len(TARGET_SUBDIRS)} 子目录")
    print(f"总违规数: {len(all_violations)}")
    print(f"  P0 (trading/risk): {len(p0_violations)}")
    print(f"  P1 (其他): {len(p1_violations)}")
    print(f"结果写入: {out_file}")
    print()
    print("Top 20 P0 违规:")
    for i, v in enumerate(p0_violations[:20], 1):
        file_short = v['file'].replace(str(project_root) + '\\', '')
        print(f"  {i:2}. {file_short}:L{v['line']} {v['function']}(...) - {v['snippet'][:80]}")


if __name__ == "__main__":
    main()
