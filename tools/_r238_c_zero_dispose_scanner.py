"""R238 C 子智能体: 0 dispose 链 Service 扫描工具."""
import os
import re
import sys
from pathlib import Path

CORE_SERVICES = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services")
BASE_SERVICE_CLASSES = r"class\s+(\w+)\s*\(.*?(BaseService|AsyncBaseService|ConfigurableService|CacheableService)"


def scan_file(py_file: Path):
    """扫描单文件, 返回候选 Service 字典列表."""
    text = py_file.read_text(encoding="utf-8", errors="ignore")
    results = []
    # 找出所有继承 BaseService/AsyncBaseService/ConfigurableService/CacheableService 的类
    for m in re.finditer(BASE_SERVICE_CLASSES, text):
        class_name = m.group(1)
        # 找该类的 dispose 方法
        # 简单策略: 类内 def dispose(self
        class_start = m.end()
        # 找下一个 class 定义 (此类的结束)
        next_class = re.search(r"^class\s+\w+", text[class_start:], re.MULTILINE)
        class_end = class_start + next_class.start() if next_class else len(text)
        class_body = text[class_start:class_end]
        has_dispose = bool(re.search(r"def\s+dispose\s*\(", class_body))
        has_shutdown = bool(re.search(r"def\s+shutdown\s*\(", class_body))
        has_close = bool(re.search(r"def\s+close\s*\(", class_body))
        has_cleanup = bool(re.search(r"def\s+cleanup\s*\(", class_body))
        # 找出类定义的行号
        line_no = text[: m.start()].count("\n") + 1
        results.append({
            "file": str(py_file),
            "class": class_name,
            "line": line_no,
            "has_dispose": has_dispose,
            "has_shutdown": has_shutdown,
            "has_close": has_close,
            "has_cleanup": has_cleanup,
        })
    return results


def main():
    candidates = []
    for py in sorted(CORE_SERVICES.glob("*.py")):
        if py.name in ("base_service.py", "__init__.py"):
            continue
        for item in scan_file(py):
            candidates.append(item)
    # 过滤: 0 dispose 链候选
    print(f"Total Service classes scanned: {len(candidates)}")
    print()
    print("=== 0 Dispose 链候选 (4 链全缺) ===")
    no_dispose = [c for c in candidates if not c["has_dispose"] and not c["has_shutdown"]]
    for c in no_dispose:
        chain = "D={0} S={1} C={2} K={3}".format(
            int(c["has_dispose"]),
            int(c["has_shutdown"]),
            int(c["has_close"]),
            int(c["has_cleanup"]),
        )
        print(f"  {c['class']:45s} {c['file']}:{c['line']} [{chain}]")
    print(f"\nTotal 0 dispose 候选: {len(no_dispose)}")
    print()
    print("=== 只有 dispose 缺 shutdown 的候选 ===")
    only_dispose = [c for c in candidates if c["has_dispose"] and not c["has_shutdown"]]
    for c in only_dispose:
        chain = "D={0} S={1} C={2} K={3}".format(
            int(c["has_dispose"]),
            int(c["has_shutdown"]),
            int(c["has_close"]),
            int(c["has_cleanup"]),
        )
        print(f"  {c['class']:45s} {c['file']}:{c['line']} [{chain}]")
    print(f"\nTotal dispose-only 候选: {len(only_dispose)}")
    print()
    print("=== 4 链全部齐备 ===")
    full_chain = [c for c in candidates if c["has_dispose"] and c["has_shutdown"] and c["has_close"] and c["has_cleanup"]]
    for c in full_chain:
        print(f"  {c['class']:45s} {c['file']}:{c['line']}")
    print(f"\nTotal 4-chain 完整: {len(full_chain)}")


if __name__ == "__main__":
    main()
