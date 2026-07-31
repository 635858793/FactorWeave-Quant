#!/usr/bin/env python3
"""
R159-B HVD-158-B 静默 except 业务埋点失败扫描器
扫描: 业务核心文件 (order_service.py, order_executor.py, order_monitor.py 等)
  1. except 块中 logger.warning/error/critical 缺 exc_info=True
  2. except 块静默 (无 logger 调用, 仅 pass/return/continue)
"""
import ast
import sys
from pathlib import Path

TARGET_FILES = [
    "core/trading/order_service.py",
    "core/trading/order_executor.py",
    "core/trading/order_monitor.py",
    "core/trading_engine.py",
    "core/services/trading_service.py",
    "core/services/advanced_risk_control_service.py",
    "core/events/event_bus.py",
    "core/services/service_bootstrap.py",
]

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


class SilentExceptVisitor(ast.NodeVisitor):
    """扫描 except 块中的 logger 调用, 标记缺 exc_info=True"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.issues = []  # [(lineno, kind, message)]

    def visit_Try(self, node: ast.Try):
        for handler in node.handlers:
            if not handler.body:
                continue
            # 1. 检查是否有 logger.warning/error/critical
            has_logger = False
            logger_no_exc = []
            for stmt in handler.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    func = call.func
                    if isinstance(func, ast.Attribute):
                        # logger.warning(...), logger.error(...), etc.
                        if (isinstance(func.value, ast.Name) and
                                func.value.id == "logger" and
                                func.attr in ("warning", "error", "critical", "exception")):
                            has_logger = True
                            # 检查是否有 exc_info=True
                            has_exc = any(
                                kw.arg == "exc_info" and
                                isinstance(kw.value, ast.Constant) and
                                kw.value.value is True
                                for kw in call.keywords
                            )
                            if not has_exc:
                                logger_no_exc.append((stmt.lineno, func.attr, ast.unparse(stmt).strip()[:80]))

            # 2. 静默 except: 仅 pass/return/continue
            is_silent = False
            silent_lines = []
            for stmt in handler.body:
                if isinstance(stmt, ast.Pass):
                    is_silent = True
                    silent_lines.append(stmt.lineno)
                elif isinstance(stmt, ast.Return):
                    # 如果整个 except 块只有 return, 算静默
                    if len(handler.body) == 1:
                        is_silent = True
                        silent_lines.append(stmt.lineno)
                elif isinstance(stmt, ast.Continue):
                    is_silent = True
                    silent_lines.append(stmt.lineno)

            if is_silent:
                self.issues.append((
                    handler.lineno,
                    "SILENT_EXCEPT",
                    f"静默 except 块 (无 logger 调用): lines={silent_lines}"
                ))

            for lineno, kind, msg in logger_no_exc:
                self.issues.append((
                    lineno,
                    "LOGGER_NO_EXC_INFO",
                    f"logger.{kind} 缺 exc_info=True: {msg}"
                ))

        self.generic_visit(node)


def scan_file(filepath: Path) -> list:
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return [("FILE_READ_ERROR", str(e))]
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [("SYNTAX_ERROR", str(e))]

    visitor = SilentExceptVisitor(str(filepath))
    visitor.visit(tree)
    return visitor.issues


def main():
    print("=" * 80)
    print("R159-B HVD-158-B 静默 except 业务埋点失败扫描器")
    print("=" * 80)
    print()

    all_issues = {}
    for rel in TARGET_FILES:
        path = PROJECT_ROOT / rel
        if not path.exists():
            print(f"[SKIP] {rel} (不存在)")
            continue
        issues = scan_file(path)
        all_issues[rel] = issues
        silent = [i for i in issues if i[1] == "SILENT_EXCEPT"]
        no_exc = [i for i in issues if i[1] == "LOGGER_NO_EXC_INFO"]
        print(f"## {rel}")
        print(f"   静默 except: {len(silent)} 处")
        print(f"   logger 缺 exc_info: {len(no_exc)} 处")
        for lineno, kind, msg in issues:
            print(f"   L{lineno} [{kind}]: {msg[:100]}")
        print()

    # 总计
    total_silent = sum(len([i for i in issues if i[1] == "SILENT_EXCEPT"]) for issues in all_issues.values())
    total_no_exc = sum(len([i for i in issues if i[1] == "LOGGER_NO_EXC_INFO"]) for issues in all_issues.values())
    print("=" * 80)
    print(f"总计: 静默 except {total_silent} 处, logger 缺 exc_info {total_no_exc} 处")
    print("=" * 80)


if __name__ == "__main__":
    main()
