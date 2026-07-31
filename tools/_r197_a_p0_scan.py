"""
R197-A P0 静默失败扫描器 v2.1 (R174 §12 v2.1 AST 严格扫描器 + R196-B 经验 + P0/P1 精细分类):
扫描 4 子目录,定位 except 块内 logger 调用无 exc_info=True 的 P0 违规

强制度 (100% 应用):
- R51 §7.1 #5 严禁静默失败铁律 (except 块内 logger 调用必须 exc_info=True)
- R174 §12 v2.1 AST 严格扫描器 (ast.walk + ast.ExceptHandler 递归 + logger.exception 排除)
- R196-B v2.1 模式 (logger.exception() 排除误报)
- R194-D v3/v4.1 修复器经验 (handler.lineno != body[0].lineno + 1-stmt Assign)
- R118 ImportError/ValueError 业务警告豁免
- R110-C 时序竞态防御
- R176 死缓存防御兼容期保留

P0/P1 分类:
- P0 (真静默失败): except Exception + logger.error/critical 缺 exc_info=True
- P1 (警告静默): except Exception + logger.warning 缺 exc_info=True
- R118 豁免: except ImportError/ValueError + 业务降级路径
"""
import ast
import os
import json
from pathlib import Path
from typing import List, Dict

# R197-A 扫描目标 (R195-A 报告 4 子目录 P0 静默失败)
TARGET_SUBDIRS = [
    "core/ui",
    "core/webgpu",
    "core/importdata",
    "core/advanced_optimization",
]

# R118 业务降级路径豁免 (R196-B v2.1 模板 + 扩展)
R118_EXEMPT_PATTERNS = [
    # R118 ImportError 类降级
    "降级", "fallback", "ImportError", "compat", "optional", "未安装",
    "traceback.format_exc", "logger.info", "logger.debug", "# R118",
    # 业务降级 (不可用/缺失/回退)
    "不可用", "服务不可用", "Manager 不可用", "回退", "退化",
    "采用本地", "本地实例", "降级方案", "缺失", "未找到",
    "降级到", "降级为", "Optional[", "Optional依赖",
    "尝试", "trying", "try to",
    # 业务警告
    "无需", "跳过", "no need", "skip", "尝试", "忽略",
    "默认", "default", "soft_parse", "软解析",
    # 启动期注册
    "_register_", "bootstrap", "init", "startup",
]

LOGGER_NAMES = {"logger", "_logger", "log"}


def _is_logger_call(stmt: ast.Call) -> bool:
    """R196-B v2.1: logger.exception() 排除"""
    if not isinstance(stmt.func, ast.Attribute):
        return False
    func_name = stmt.func.attr
    if not func_name.startswith(("warning", "error", "critical", "info", "debug")):
        return False
    if func_name == "exception":  # R196-B v2.1 排除
        return False
    if isinstance(stmt.func.value, ast.Name):
        if stmt.func.value.id not in LOGGER_NAMES:
            return False
    elif isinstance(stmt.func.value, ast.Attribute):
        if not stmt.func.value.attr.endswith("logger"):
            return False
    else:
        return False
    return True


def _has_exc_info_kwarg(stmt: ast.Call) -> bool:
    return any(
        kw.arg == "exc_info" and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in stmt.keywords
    )


def _is_exempt(line_text: str) -> bool:
    return any(pat in line_text for pat in R118_EXEMPT_PATTERNS)


def _classify_severity(func_name: str, except_type: str) -> str:
    """P0/P1 分类"""
    # R118 豁免: ImportError/ValueError 业务警告
    if "ImportError" in except_type or "ValueError" in except_type:
        return "R118_EXEMPT"
    # P0 真静默失败: except Exception + logger.error/critical
    if func_name in ("error", "critical"):
        return "P0"
    # P1 警告静默: except Exception + logger.warning
    if func_name == "warning":
        return "P1"
    return "OTHER"


def scan_except_blocks(file_path: Path) -> List[Dict]:
    """R174 §12 v2.1 AST 严格扫描器 + R196-B v2.1 模式"""
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    source_lines = source.split("\n")

    # R194-D v3 经验: ast.walk + 递归 except 块
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Try, ast.TryStar)):
            continue
        for handler in node.handlers:
            if not isinstance(handler, ast.ExceptHandler):
                continue
            # 递归访问 handler.body
            for stmt in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
                if not isinstance(stmt, ast.Call):
                    continue
                if not _is_logger_call(stmt):
                    continue
                if _has_exc_info_kwarg(stmt):
                    continue
                line_text = source_lines[stmt.lineno - 1] if stmt.lineno <= len(source_lines) else ""
                if _is_exempt(line_text):
                    continue
                except_type = ast.unparse(handler.type) if handler.type else "Exception"
                func_name = stmt.func.attr
                severity = _classify_severity(func_name, except_type)
                violations.append({
                    "file": str(file_path),
                    "line": stmt.lineno,
                    "function": func_name,
                    "snippet": line_text.strip()[:150],
                    "except_type": except_type,
                    "severity": severity,
                })

    return violations


def main():
    project_root = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
    skip_patterns = {"test_", "__pycache__", ".git", "venv", "node_modules", "dist", "build", ".trae"}

    all_violations = []
    by_subdir = {sd: {"P0": 0, "P1": 0, "R118_EXEMPT": 0, "OTHER": 0, "total": 0} for sd in TARGET_SUBDIRS}

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
            for v in violations:
                by_subdir[subdir][v["severity"]] += 1
                by_subdir[subdir]["total"] += 1
            all_violations.extend(violations)

    # P0 真违规清单 (待物理修复)
    p0_violations = [v for v in all_violations if v["severity"] == "P0"]

    out = {
        "scan_target": TARGET_SUBDIRS,
        "total_violations": len(all_violations),
        "p0_count": len(p0_violations),
        "p1_count": len([v for v in all_violations if v["severity"] == "P1"]),
        "r118_exempt_count": len([v for v in all_violations if v["severity"] == "R118_EXEMPT"]),
        "by_subdir": by_subdir,
        "violations": all_violations,
        "p0_violations_for_fix": p0_violations,
    }
    out_file = project_root / "tools" / "_r197_a_p0_scan.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"=== R197-A v2.1 扫描完成 ===")
    print(f"扫描子目录: {len(TARGET_SUBDIRS)}")
    print(f"总违规: {len(all_violations)}")
    print(f"  P0 真静默失败 (except Exception + logger.error): {len(p0_violations)}")
    print(f"  P1 警告静默 (except Exception + logger.warning): {len([v for v in all_violations if v['severity'] == 'P1'])}")
    print(f"  R118 豁免 (ImportError/ValueError): {len([v for v in all_violations if v['severity'] == 'R118_EXEMPT'])}")
    print()
    print("各子目录分布:")
    for sd, stat in by_subdir.items():
        print(f"  {sd}: P0={stat['P0']}, P1={stat['P1']}, R118={stat['R118_EXEMPT']}, total={stat['total']}")
    print()
    print(f"结果写入: {out_file}")
    print()
    print("Top 20 P0 真违规:")
    for i, v in enumerate(p0_violations[:20], 1):
        file_short = v['file'].replace(str(project_root) + '\\', '')
        print(f"  {i:2}. {file_short}:L{v['line']} {v['function']}(...) - {v['snippet'][:70]}")


if __name__ == "__main__":
    main()
