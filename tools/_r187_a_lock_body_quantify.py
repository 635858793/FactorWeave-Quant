"""
R187-A handle_order_fill 锁内代码量化工具
验证 R186-B 报告的 81 行锁内代码确实存在
并量化每阶段的子操作归属
"""
import ast
import sys
from typing import List, Dict, Tuple, Optional


def find_lock_blocks_in_method(
    file_path: str,
    method_name: str,
    target_lock: str = "_order_lock",
) -> List[Dict]:
    """查找方法内所有 target_lock 块的位置与子操作归属"""
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
        lines = source.split('\n')

    tree = ast.parse(source)
    results = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    method_end = item.end_lineno
                    method_start = item.lineno
                    # 找所有 with self._order_lock 块
                    for child in ast.walk(item):
                        if isinstance(child, ast.With):
                            for with_item in child.items:
                                if (isinstance(with_item.context_expr, ast.Attribute)
                                        and isinstance(with_item.context_expr.value, ast.Name)
                                        and with_item.context_expr.value.id == "self"
                                        and with_item.context_expr.attr == target_lock):
                                    start_line = child.lineno
                                    end_line = child.end_lineno
                                    body_lines = end_line - start_line + 1
                                    results.append({
                                        "class": node.name,
                                        "method": item.name,
                                        "method_start": method_start,
                                        "method_end": method_end,
                                        "lock_start": start_line,
                                        "lock_end": end_line,
                                        "lock_body_lines": body_lines,
                                    })
    return results


def classify_lock_body_suboperations(
    file_path: str,
    method_name: str,
    lock_start: int,
    lock_end: int,
) -> Dict:
    """分类锁内子操作 (状态机 / 持久化 / 事件 / 通知)"""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    categories = {
        "state_machine": [],   # 状态机转换
        "snapshot": [],        # publish_args 快照
        "trace_event": [],     # 埋点
        "logger": [],          # 日志
        "persist": [],         # 持久化 (在锁内)
        "publish": [],         # 事件发布 (在锁内)
        "return": [],          # 提前 return
    }

    for i in range(lock_start - 1, lock_end):
        if i >= len(lines):
            break
        line = lines[i]
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue

        if "transition_to" in line:
            categories["state_machine"].append((i + 1, line_stripped[:100]))
        if "filled_quantity" in line or "filled_price" in line or "_publish_args" in line:
            categories["snapshot"].append((i + 1, line_stripped[:100]))
        if "trace_event" in line:
            categories["trace_event"].append((i + 1, line_stripped[:100]))
        if "logger." in line:
            categories["logger"].append((i + 1, line_stripped[:100]))
        if "update_order" in line or "save_order_fill" in line or "_persist_order" in line:
            categories["persist"].append((i + 1, line_stripped[:100]))
        if "event_bus.publish" in line:
            categories["publish"].append((i + 1, line_stripped[:100]))
        if "return" in line and "return False" in line:
            categories["return"].append((i + 1, line_stripped[:100]))

    return categories


def main():
    file_path = "core/trading/order_executor.py"
    method_name = "handle_order_fill"

    results = find_lock_blocks_in_method(file_path, method_name)
    if not results:
        print("❌ 未找到 handle_order_fill 内的 _order_lock 块")
        return 1

    print(f"\n{'='*70}")
    print(f"R187-A handle_order_fill 锁内代码量化报告")
    print(f"{'='*70}\n")

    for r in results:
        print(f"类: {r['class']}")
        print(f"方法: {r['method']} (L{r['method_start']}-{r['method_end']}, 共 {r['method_end']-r['method_start']+1} 行)")
        print(f"\n锁块位置: L{r['lock_start']}-{r['lock_end']}")
        print(f"锁内代码行数: {r['lock_body_lines']} 行")
        if r['lock_body_lines'] > 30:
            print(f"  ⚠️  锁内代码行数 {r['lock_body_lines']} > 30 行阈值, 需要 3 阶段拆锁")
        print()

        # 量化子操作
        cats = classify_lock_body_suboperations(file_path, method_name, r['lock_start'], r['lock_end'])
        print("锁内子操作分类:")
        for cat, items in cats.items():
            if items:
                print(f"  [{cat}]: {len(items)} 项")
                for line_no, text in items[:3]:
                    print(f"    L{line_no}: {text}")
                if len(items) > 3:
                    print(f"    ... (共 {len(items)} 项)")
        print()

    # 业务关键判断
    print(f"{'='*70}")
    print("业务关键判断:")
    print(f"  1. 锁内事件 publish: {len(cats['publish'])} (应为 0, R8 §8.1 #2 强约束)")
    print(f"  2. 锁内持久化调用: {len(cats['persist'])} (状态机回滚时不可避免, 但应最小化)")
    print(f"  3. 锁内状态机转换: {len(cats['state_machine'])} (核心业务, 应在锁内)")
    print(f"  4. 锁内快照准备: {len(cats['snapshot'])} (R90-V CTP 模式, 应在锁内)")
    print(f"  5. 锁内提前 return: {len(cats['return'])} (回滚时不可避免)")
    print(f"  6. 锁内 trace_event 埋点: {len(cats['trace_event'])} (R90+ N P0-2 监控)")
    print(f"  7. 锁内 logger 调用: {len(cats['logger'])} (异常路径 + SLOW-LOCK 监控)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
