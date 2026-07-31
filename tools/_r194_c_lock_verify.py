#!/usr/bin/env python3
"""R194-C AST 锁嵌套验证脚本 v2 (R104 §12 #3 + #5 + R100-F-P1-1 #8 4 锁独立策略)

R194-C 升级点 vs R192-C (v1):
1. R104 §12 #3 强约束: AST 检测锁/资源嵌套必须递归进入 with.body (含嵌套 with/try/if/循环)
2. R104 §12 #5 强约束: 锁嵌套检测 必须 ast.unparse 还原方法体后二次验证
3. R100-F-P1-1 #8 (新增铁律 #8): 必须拆分 _lock / _futures_lock / _stats_lock / _history_lock
   为 4 把独立短锁, 禁止在 with self._lock: 块内嵌套其他锁 (任何嵌套)
4. 跨实例锁嵌套检测: parent_instance 不同, current_instance 不同, 但同 RLock 同方法
5. 同实例锁嵌套检测: parent_instance == current_instance, 任何嵌套都是 4 锁独立违规

设计原则 (R104 教训):
- 严禁 ast.walk 扁平化: 必须递归进入 with.body + try.body + if.body + loop.body
- 严禁仅字符串匹配: 必须 ast.unparse 还原方法体后二次验证
- 严禁漏掉单实例同锁嵌套 (例如 with self._lock: 内 with self._lock: 序列化违规)
- 必须支持 _lock / _xxx_lock / self._yyy_lock 多种锁名模式

执行示例:
  python tools/_r194_c_lock_verify.py core/cache/cache_key_factory.py
  python tools/_r194_c_lock_verify.py core/risk/risk_event_subscribers.py
  python tools/_r194_c_lock_verify.py core/feature_flags/flag_manager.py
"""
import ast
import os
import sys
from typing import Dict, List, Set, Tuple, Any, Optional


# R100-F-P1-1 #8 (永久规则): 4 锁独立短锁策略
# 业务关键锁名清单 (跨项目通用)
BUSINESS_LOCK_NAMES = {
    # EventBus 4 锁 (R100-F-P1-1 #8 实施)
    '_lock', '_futures_lock', '_stats_lock', '_history_lock',
    # Cache/LRU 4 锁 (R192-C-1 实施)
    '_lru_lock', '_migration_lock', '_validation_lock',
    # 业务方可能使用的锁名前缀
    '_cache_lock', '_positions_lock', '_account_lock', '_order_lock',
    '_trading_lock', '_data_lock', '_state_lock', '_config_lock',
    '_risk_lock', '_monitor_lock', '_event_lock', '_bus_lock',
    '_pool_lock', '_queue_lock', '_registry_lock', '_subs_lock',
    '_handler_lock', '_subscription_lock', '_coordinator_lock',
    # FeatureFlagManager 锁
    '_flag_lock', '_change_lock', '_history_lock',
}


def get_lock_context_expr(item: ast.withitem) -> Optional[Tuple[str, str]]:
    """从 with item 的 context_expr 提取锁标识 (instance, attr)

    返回:
        (instance_id, attr_name) 如 ("self", "_lock")
        None: 不是我们关心的锁 (非 self.attr 模式)

    支持的 pattern:
    - self._lock
    - self._xxx_lock
    - some_module._lock
    """
    ctx = item.context_expr
    if isinstance(ctx, ast.Attribute):
        if isinstance(ctx.value, ast.Name):
            return (ctx.value.id, ctx.attr)
    return None


def get_with_locks(items: List[ast.withitem]) -> Set[Tuple[str, str]]:
    """提取 with 语句的所有锁"""
    locks = set()
    for item in items:
        lock = get_lock_context_expr(item)
        if lock:
            locks.add(lock)
    return locks


def find_nested_locks(
    body: List[ast.stmt],
    parent_locks: Set[Tuple[str, str]],
    depth: int = 0,
    method_name: str = "",
    file_path: str = "",
) -> List[Dict[str, Any]]:
    """R104 §12 #3 核心: 递归进入 with.body + try.body + if.body + loop.body 检测锁嵌套

    检测 3 类违规:
    1. SAME_INSTANCE_SAME_LOCK: parent == current, 同实例同锁名 (RLock 死锁/序列化违规)
    2. SAME_INSTANCE_DIFF_LOCK: parent_instance == current_instance, 但 lock_attr 不同
       (R100-F-P1-1 #8 4 锁独立违规, 持锁时间膨胀)
    3. CROSS_INSTANCE: parent_instance != current_instance, 跨实例锁嵌套 (业务反模式)
    """
    violations = []
    for node in body:
        if isinstance(node, ast.With):
            current_locks = get_with_locks(node.items)
            # 嵌套检测 (当前 with 内的锁 vs 上层 with 已有的锁)
            for parent_lock in parent_locks:
                for current_lock in current_locks:
                    p_inst, p_attr = parent_lock
                    c_inst, c_attr = current_lock
                    # R100-F-P1-1 #8 4 锁独立违规: 同实例 + 不同锁名 = 锁嵌套
                    if p_inst == c_inst and p_attr != c_attr:
                        violations.append({
                            'type': 'NESTED_LOCK_4_LOCK_VIOLATION',
                            'file': file_path,
                            'method': method_name,
                            'line': node.lineno,
                            'col': node.col_offset,
                            'depth': depth,
                            'parent': f"{p_inst}.{p_attr}",
                            'current': f"{c_inst}.{c_attr}",
                            'severity': 'P0',
                            'rule': 'R100-F-P1-1 #8 4 锁独立策略',
                        })
                    # 同实例 + 同锁名: RLock 重入允许, 但 Lock 是序列化违规
                    elif p_inst == c_inst and p_attr == c_attr:
                        # RLock 是可重入锁, 不算违规; 但 Lock 是序列化, 算违规
                        # 简化处理: 仅警告 (不计入 P0), 需进一步看锁类型
                        violations.append({
                            'type': 'SAME_LOCK_REENTRY',
                            'file': file_path,
                            'method': method_name,
                            'line': node.lineno,
                            'col': node.col_offset,
                            'depth': depth,
                            'parent': f"{p_inst}.{p_attr}",
                            'current': f"{c_inst}.{c_attr}",
                            'severity': 'P1',
                            'rule': 'R104 §12 #3 同锁重入 (RLock 允许, Lock 序列化)',
                        })
                    # 跨实例锁嵌套
                    elif p_inst != c_inst:
                        violations.append({
                            'type': 'CROSS_INSTANCE_LOCK',
                            'file': file_path,
                            'method': method_name,
                            'line': node.lineno,
                            'col': node.col_offset,
                            'depth': depth,
                            'parent': f"{p_inst}.{p_attr}",
                            'current': f"{c_inst}.{c_attr}",
                            'severity': 'P2',
                            'rule': 'R104 §12 #3 跨实例锁嵌套',
                        })
            # 递归进入 with.body (R104 §12 #3 强约束: 严禁 ast.walk 扁平化)
            violations.extend(find_nested_locks(
                node.body,
                parent_locks | current_locks,
                depth + 1,
                method_name,
                file_path,
            ))
        elif isinstance(node, ast.AsyncWith):
            # AsyncWith 与 With 同结构, 但需异步上下文管理器
            current_locks = get_with_locks(node.items)
            for parent_lock in parent_locks:
                for current_lock in current_locks:
                    p_inst, p_attr = parent_lock
                    c_inst, c_attr = current_lock
                    if p_inst == c_inst and p_attr != c_attr:
                        violations.append({
                            'type': 'NESTED_LOCK_4_LOCK_VIOLATION_ASYNC',
                            'file': file_path,
                            'method': method_name,
                            'line': node.lineno,
                            'col': node.col_offset,
                            'depth': depth,
                            'parent': f"{p_inst}.{p_attr}",
                            'current': f"{c_inst}.{c_attr}",
                            'severity': 'P0',
                            'rule': 'R100-F-P1-1 #8 4 锁独立策略 (AsyncWith)',
                        })
            violations.extend(find_nested_locks(
                node.body,
                parent_locks | current_locks,
                depth + 1,
                method_name,
                file_path,
            ))
        elif isinstance(node, ast.Try):
            # 递归进入 try.body + except handler.body + finally.body
            violations.extend(find_nested_locks(node.body, parent_locks, depth, method_name, file_path))
            for handler in node.handlers:
                violations.extend(find_nested_locks(handler.body, parent_locks, depth, method_name, file_path))
            violations.extend(find_nested_locks(node.finalbody, parent_locks, depth, method_name, file_path))
        elif isinstance(node, ast.If):
            violations.extend(find_nested_locks(node.body, parent_locks, depth, method_name, file_path))
            violations.extend(find_nested_locks(node.orelse, parent_locks, depth, method_name, file_path))
        elif isinstance(node, (ast.For, ast.While)):
            violations.extend(find_nested_locks(node.body, parent_locks, depth, method_name, file_path))
            violations.extend(find_nested_locks(node.orelse, parent_locks, depth, method_name, file_path))
    return violations


def verify_method_with_unparse(method_node: ast.FunctionDef, violations: List[Dict]) -> Dict:
    """R104 §12 #5 核心: AST unparse 还原方法体, 二次验证锁路径

    二次验证:
    1. unparse 字符串中是否真有 parent_lock 字符串 (排除 false positive)
    2. unparse 字符串中是否真有 current_lock 字符串
    3. parent_lock 出现在 current_lock 之前 (行号序)
    """
    try:
        unparse_str = ast.unparse(method_node)
    except Exception as e:
        return {
            'method': method_node.name,
            'lineno': method_node.lineno,
            'unparse_ok': False,
            'error': str(e),
        }

    unparse_lines = unparse_str.split('\n')
    line_count = len(unparse_lines)
    # 二次验证 violations
    verified_violations = []
    for v in violations:
        if v.get('method') != method_node.name:
            continue
        parent = v.get('parent', '')
        current = v.get('current', '')
        # unparse 字符串中必须出现 parent 和 current
        if parent in unparse_str and current in unparse_str:
            # 找 parent 在 unparse 字符串中的行
            parent_line = -1
            current_line = -1
            for i, line in enumerate(unparse_lines):
                if parent in line and parent_line == -1:
                    parent_line = i
                if current in line and current_line == -1:
                    current_line = i
            # parent 必须在 current 之前
            if parent_line != -1 and current_line != -1 and parent_line <= current_line:
                v['unparse_verified'] = True
                v['unparse_parent_line'] = parent_line
                v['unparse_current_line'] = current_line
                verified_violations.append(v)
            else:
                v['unparse_verified'] = False
                v['unparse_skip_reason'] = f'parent_line={parent_line} > current_line={current_line}'
        else:
            v['unparse_verified'] = False
            v['unparse_skip_reason'] = f'parent or current not in unparse'
    return {
        'method': method_node.name,
        'lineno': method_node.lineno,
        'unparse_ok': True,
        'line_count': line_count,
        'verified_violations': verified_violations,
    }


def analyze_file(file_path: str) -> Dict:
    """分析单个 Python 文件的锁架构

    返回:
        {
            'file': file_path,
            'total_methods': int,
            'methods_with_violations': int,
            'p0_violations': List[Dict],
            'p1_violations': List[Dict],
            'p2_violations': List[Dict],
            'unparse_verified': bool,
        }
    """
    if not os.path.exists(file_path):
        return {'file': file_path, 'error': 'file not found'}

    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {'file': file_path, 'error': f'syntax error: {e}'}

    all_violations = []
    unparse_results = []
    total_methods = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total_methods += 1
            method_violations = find_nested_locks(
                node.body,
                set(),
                0,
                node.name,
                file_path,
            )
            if method_violations:
                all_violations.extend(method_violations)
                # R104 §12 #5: AST unparse 二次验证
                unparse_res = verify_method_with_unparse(node, method_violations)
                unparse_results.append(unparse_res)

    p0_violations = [v for v in all_violations if v.get('severity') == 'P0' and v.get('unparse_verified', True)]
    p1_violations = [v for v in all_violations if v.get('severity') == 'P1' and v.get('unparse_verified', True)]
    p2_violations = [v for v in all_violations if v.get('severity') == 'P2' and v.get('unparse_verified', True)]
    unverified = [v for v in all_violations if not v.get('unparse_verified', True)]

    return {
        'file': file_path,
        'total_methods': total_methods,
        'total_violations': len(all_violations),
        'methods_with_violations': len(unparse_results),
        'p0_violations': p0_violations,
        'p1_violations': p1_violations,
        'p2_violations': p2_violations,
        'unverified': unverified,
        'unparse_results': unparse_results,
    }


def main():
    """主函数: 支持单文件或目录扫描"""
    if len(sys.argv) < 2:
        print("用法: python _r194_c_lock_verify.py <file_or_dir>")
        print("示例: python _r194_c_lock_verify.py core/cache/cache_key_factory.py")
        sys.exit(1)

    target = sys.argv[1]

    files_to_analyze = []
    if os.path.isfile(target):
        files_to_analyze = [target]
    elif os.path.isdir(target):
        for root, dirs, files in os.walk(target):
            # 跳过 __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if f.endswith('.py'):
                    files_to_analyze.append(os.path.join(root, f))
    else:
        print(f"Error: {target} 不存在")
        sys.exit(1)

    print(f"=== R194-C 锁架构 AST 验证 (R104 §12 #3 + #5 + R100-F-P1-1 #8) ===")
    print(f"扫描路径: {target}")
    print(f"文件数: {len(files_to_analyze)}")
    print(f"业务锁名集合: {len(BUSINESS_LOCK_NAMES)} 个")
    print()

    total_p0 = 0
    total_p1 = 0
    total_p2 = 0
    total_unverified = 0
    files_with_violations = 0

    for file_path in files_to_analyze:
        result = analyze_file(file_path)
        if 'error' in result:
            print(f"[SKIP] {file_path}: {result['error']}")
            continue

        p0 = len(result['p0_violations'])
        p1 = len(result['p1_violations'])
        p2 = len(result['p2_violations'])
        unverified = len(result['unverified'])

        total_p0 += p0
        total_p1 += p1
        total_p2 += p2
        total_unverified += unverified

        if p0 + p1 + p2 > 0:
            files_with_violations += 1
            print(f"[VIOLATION] {file_path}:")
            print(f"  total_methods={result['total_methods']}, methods_with_violations={result['methods_with_violations']}")
            print(f"  P0: {p0}, P1: {p1}, P2: {p2}, unverified: {unverified}")
            for v in result['p0_violations'][:3]:
                print(f"    P0 L{v['line']} {v['method']}: {v['type']} parent={v['parent']} current={v['current']}")
            if p0 > 3:
                print(f"    ... ({p0 - 3} more P0)")
            for v in result['p1_violations'][:2]:
                print(f"    P1 L{v['line']} {v['method']}: {v['type']} parent={v['parent']} current={v['current']}")
        else:
            print(f"[OK] {file_path}: {result['total_methods']} methods, 0 violations")

    print()
    print(f"=== 汇总 ===")
    print(f"扫描文件数: {len(files_to_analyze)}")
    print(f"违规文件数: {files_with_violations}")
    print(f"P0 (R100-F-P1-1 #8 4 锁独立违规): {total_p0}")
    print(f"P1 (同锁重入): {total_p1}")
    print(f"P2 (跨实例锁嵌套): {total_p2}")
    print(f"unverified (R104 §12 #5 AST unparse 验证未通过): {total_unverified}")

    if total_p0 == 0 and total_p1 == 0 and total_p2 == 0:
        print("✅ PASS: 0 锁架构违规")
    else:
        print("❌ FAIL: 发现锁架构违规, 详见上方输出")


if __name__ == "__main__":
    main()
