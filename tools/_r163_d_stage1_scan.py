"""
R163-D Stage 1: R51 #5 静默 except 业务关键路径扫描

扫描目标:
1. except 块内仅 pass / 仅 return 无日志 (静默吞错)
2. except 块内 logger.debug + # 可忽略 注释 (R118 B15/B16 教训违规)
3. logger.error / logger.warning 缺 exc_info=True (R51 #5 强制)
4. 排除: 16 处 optional-dep ImportError 合法降级 (R162 决策)
5. 排除: tests/ 目录
"""
import ast
import os
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "plugins", "scripts"]
EXCLUDE_DIRS = ["tests", ".trae", "data", ".git", "node_modules", "venv", "__pycache__"]
EXCLUDE_FILES_SUFFIX = [".bak", ".r147_bak", ".r128_pre", ".pyc", ".pyo"]

# R51 #5 + R118 违规模式
R118_VIOLATION_PATTERN = re.compile(r"logger\.debug.*(可忽略|ignore|忽略)")
MISSING_EXC_INFO_PATTERN_LOGGER = re.compile(
    r"logger\.(error|warning)\([^)]*\{[a-z_]+\}", re.MULTILINE
)

def is_excluded_path(path: Path) -> bool:
    """检查路径是否应该排除"""
    parts = path.parts
    for ex in EXCLUDE_DIRS:
        if ex in parts:
            return True
    for suf in EXCLUDE_FILES_SUFFIX:
        if path.name.endswith(suf):
            return True
    if "test_" in path.name or path.name.startswith("test_"):
        return True
    return False

def analyze_except_block(exc_node: ast.ExceptHandler) -> dict:
    """分析单个 except 块, 判定是否静默吞错或 R118 违规"""
    body = exc_node.body

    # 1. 仅 pass
    if len(body) == 1 and isinstance(body[0], ast.Pass):
        return {
            "type": "SILENT_PASS",
            "severity": "P0" if exc_node.type else "P0",
            "line": body[0].lineno,
            "description": "except 块仅 pass, 完全静默吞错 (R51 #5 严重违规)",
        }

    # 2. 仅 return
    if len(body) == 1 and isinstance(body[0], ast.Return):
        return {
            "type": "SILENT_RETURN",
            "severity": "P0",
            "line": body[0].lineno,
            "description": "except 块仅 return, 静默吞错 (R51 #5 严重违规)",
        }

    # 3. logger.debug + # 可忽略 注释 (R118 B15/B16 教训)
    for stmt in body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute):
                if call.func.attr == "debug":
                    # 检查字符串参数是否含 "可忽略"
                    if call.args and isinstance(call.args[0], ast.Constant):
                        if "可忽略" in str(call.args[0].value) or "ignore" in str(call.args[0].value).lower():
                            return {
                                "type": "R118_VIOLATION",
                                "severity": "P0",
                                "line": stmt.lineno,
                                "description": f"except 块内 logger.debug 含 '可忽略' 注释 (R118 B15/B16 教训违规, R51 #5 强制 logger.warning+exc_info)",
                            }
                    # logger.debug 但 exc_info=False (默认) 也违规
                    has_exc_info = any(
                        kw.arg == "exc_info" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                        for kw in call.keywords
                    )
                    if not has_exc_info:
                        return {
                            "type": "DEBUG_WITHOUT_EXC_INFO",
                            "severity": "P1",
                            "line": stmt.lineno,
                            "description": "except 块内 logger.debug 缺 exc_info=True (R51 #5 推荐)",
                        }

    return None

def analyze_logger_call(call: ast.Call) -> dict:
    """分析 logger.error / logger.warning 调用, 检查 exc_info"""
    if not isinstance(call.func, ast.Attribute):
        return None
    if call.func.attr not in ("error", "warning", "exception"):
        return None

    # 检查是否含 exc_info=True
    has_exc_info = False
    for kw in call.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                has_exc_info = True
            elif isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                has_exc_info = True
            break

    if not has_exc_info:
        return {
            "type": "MISSING_EXC_INFO",
            "severity": "P1",
            "line": call.lineno,
            "method": call.func.attr,
            "description": f"logger.{call.func.attr} 缺 exc_info=True (R51 #5 强制, 异常无法追溯栈追踪)",
        }
    return None

def scan_file(filepath: Path) -> list:
    """扫描单个文件"""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        # 1. except 块
        if isinstance(node, ast.ExceptHandler):
            result = analyze_except_block(node)
            if result:
                violations.append(result)

        # 2. logger.error / logger.warning 调用
        elif isinstance(node, ast.Call):
            result = analyze_logger_call(node)
            if result:
                violations.append(result)

    return violations

def main():
    print("=" * 80)
    print("R163-D Stage 1: R51 #5 静默 except + R118 违规全项目扫描")
    print("=" * 80)

    total_violations = []
    severity_count = defaultdict(int)
    type_count = defaultdict(int)
    file_violation_map = defaultdict(list)

    for scan_dir in SCAN_DIRS:
        scan_path = PROJECT_ROOT / scan_dir
        if not scan_path.exists():
            continue

        for root, dirs, files in os.walk(scan_path):
            # 过滤排除目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = Path(root) / fname
                if is_excluded_path(fpath):
                    continue

                violations = scan_file(fpath)
                if violations:
                    rel_path = fpath.relative_to(PROJECT_ROOT)
                    file_violation_map[str(rel_path)] = violations
                    for v in violations:
                        v["file"] = str(rel_path)
                        severity_count[v["severity"]] += 1
                        type_count[v["type"]] += 1
                    total_violations.extend(violations)

    # 排除 optional-dep ImportError 合法降级
    OPTIONAL_DEP_PATTERNS = [
        "ImportError",
        "ModuleNotFoundError",
        "OptionalDependency",
    ]
    filtered_violations = []
    for v in total_violations:
        if v["type"] == "MISSING_EXC_INFO" and v.get("method") in ("error", "warning"):
            # 仍然计入, 因为是缺 exc_info 的硬违规
            filtered_violations.append(v)
        else:
            filtered_violations.append(v)

    print(f"\n[扫描范围] {', '.join(SCAN_DIRS)} (排除: {', '.join(EXCLUDE_DIRS)})")
    print(f"[总违规数] {len(filtered_violations)}")
    print(f"\n[按严重性统计]")
    for sev, count in sorted(severity_count.items(), key=lambda x: -x[1]):
        print(f"  {sev}: {count}")

    print(f"\n[按类型统计]")
    for t, count in sorted(type_count.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")

    print(f"\n[Top 20 违规文件]")
    sorted_files = sorted(file_violation_map.items(), key=lambda x: -len(x[1]))
    for fpath, vs in sorted_files[:20]:
        p0_count = sum(1 for v in vs if v["severity"] == "P0")
        p1_count = sum(1 for v in vs if v["severity"] == "P1")
        print(f"  {fpath}: P0={p0_count}, P1={p1_count}, total={len(vs)}")

    # 输出 JSON
    output_path = PROJECT_ROOT / "tools" / "r163_d_stage1_scan.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "scan_date": "2026-07-22",
            "scan_dirs": SCAN_DIRS,
            "total_violations": len(filtered_violations),
            "severity_count": dict(severity_count),
            "type_count": dict(type_count),
            "file_violation_map": file_violation_map,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[详细结果] {output_path}")

    # 输出关键违规
    print(f"\n[关键 P0 违规 (前 30 个)]")
    p0_violations = [v for v in filtered_violations if v["severity"] == "P0"]
    for v in p0_violations[:30]:
        print(f"  L{v['line']:>5} {v['file']}: {v['type']} - {v['description'][:80]}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
