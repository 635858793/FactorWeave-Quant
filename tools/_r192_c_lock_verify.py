#!/usr/bin/env python3
"""R192-C AST unparse 验证脚本 (R104 §12 #5) - v2 重写"""
import ast
import sys


def get_lock_keys(items):
    keys = set()
    for item in items:
        ctx = item.context_expr
        if isinstance(ctx, ast.Attribute):
            if isinstance(ctx.value, ast.Name):
                keys.add((ctx.value.id, ctx.attr))
    return keys


def find_nested(body, parent_locks, depth=0):
    violations = []
    for node in body:
        if isinstance(node, ast.With):
            current_keys = get_lock_keys(node.items)
            parent_instances = {k[0] for k in parent_locks if k[0]}
            current_instances = {k[0] for k in current_keys if k[0]}
            cross = parent_instances & current_instances
            # 跨锁名, 同 instance, 视为 CROSS_LOCK_NESTED
            if cross and current_keys != parent_locks:
                violations.append({
                    "line": node.lineno,
                    "parent": sorted(parent_locks),
                    "current": sorted(current_keys),
                    "depth": depth,
                })
            violations.extend(find_nested(node.body, current_keys | parent_locks, depth + 1))
        elif isinstance(node, ast.Try):
            violations.extend(find_nested(node.body, parent_locks, depth))
            for h in node.handlers:
                violations.extend(find_nested(h.body, parent_locks, depth))
            violations.extend(find_nested(node.finalbody, parent_locks, depth))
        elif isinstance(node, ast.If):
            violations.extend(find_nested(node.body, parent_locks, depth))
            violations.extend(find_nested(node.orelse, parent_locks, depth))
        elif isinstance(node, (ast.For, ast.While)):
            violations.extend(find_nested(node.body, parent_locks, depth))
            violations.extend(find_nested(node.orelse, parent_locks, depth))
    return violations


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "core/cache/cache_key_factory.py"
    with open(target, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)

    print(f"=== R104 12#3 + #5 AST 验证: {target} ===", flush=True)
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            v = find_nested(node.body, set())
            if v:
                print(f"  Method {node.name} (L{node.lineno}):", flush=True)
                for violation in v:
                    print(f"    L{violation['line']}: parent={violation['parent']} current={violation['current']} depth={violation['depth']}", flush=True)
                # AST unparse 验证 (R104 12#5)
                unparse = ast.unparse(node)
                line_count = len(unparse.split("\n"))
                print(f"    AST unparse verify: method body {line_count} lines", flush=True)
                total += len(v)
    print(f"=== Total violations: {total} ===", flush=True)


if __name__ == "__main__":
    main()
