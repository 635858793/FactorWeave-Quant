#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R195-C AST 锁嵌套验证脚本 v2 (R104 §12 #3 + #5 + R100-F-P1-1 #8 4 锁独立策略)

R195-C 升级点 vs R194-C v1:
1. 业务锁名集合: 28 → 53 个 (R195-C 新增 25 个, 覆盖 R194 未覆盖子目录新发现的锁)
2. P3 类别: 业务隔离 (例如 _account_lock + _user_lock 同方法, 跨业务对象锁嵌套, 业务反模式)
3. 修复 UnicodeEncodeError: 改用 ASCII 兼容输出 (gbk 环境兼容)
4. 新增 --json 输出模式: 供下游工具消费
5. 新增 --summary 模式: 仅输出汇总, 快速巡检
6. 新增锁名覆盖率报告: 显示代码中实际命中的锁名 (供 R196+ round 优化锁名集合)
7. 改进 ast.unparse 验证: 支持行号追踪 (R104 §12 #5 强化)

设计原则 (R104 教训 + R195-C 升级):
- 严禁 ast.walk 扁平化: 必须递归进入 with.body + try.body + if.body + loop.body
- 严禁仅字符串匹配: 必须 ast.unparse 还原方法体后二次验证
- 必须支持 _lock / _xxx_lock / self._yyy_lock 多种锁名模式
- 必须区分 4 类违规: P0 (4 锁独立) + P1 (同锁重入) + P2 (跨实例) + P3 (业务隔离)

执行示例:
  python tools/_r195_c_lock_verify_v2.py core/cache/cache_key_factory.py
  python tools/_r195_c_lock_verify_v2.py core/trading
  python tools/_r195_c_lock_verify_v2.py core/services --summary
  python tools/_r195_c_lock_verify_v2.py core/events --json
"""
import ast
import os
import sys
import json
import argparse
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict


# R100-F-P1-1 #8 (永久规则): 4 锁独立短锁策略
# R195-C 扩展: 28 → 53 个业务锁名 (覆盖 R194-C 未覆盖子目录新发现)
BUSINESS_LOCK_NAMES = {
    # ============================================================
    # EventBus 4 锁 (R100-F-P1-1 #8 实施, R100-F-NEW-P1-4 修复)
    # ============================================================
    '_lock', '_futures_lock', '_stats_lock', '_history_lock',
    # R100-F 实战: EventBus 完整 4 锁独立 (97K QPS 验证)

    # ============================================================
    # Cache/LRU 4 锁 (R192-C-1 实施)
    # ============================================================
    '_lru_lock', '_migration_lock', '_validation_lock',
    # R195-C 实施: cache_key_factory.py 4 锁独立

    # ============================================================
    # 业务方可能使用的锁名前缀 (R195-C 扩展 +25 个)
    # ============================================================
    # 通用业务锁
    '_cache_lock', '_positions_lock', '_account_lock', '_order_lock',
    '_trading_lock', '_data_lock', '_state_lock', '_config_lock',
    '_risk_lock', '_monitor_lock', '_event_lock', '_bus_lock',
    '_pool_lock', '_queue_lock', '_registry_lock', '_subs_lock',
    '_handler_lock', '_subscription_lock', '_coordinator_lock',

    # R195-C 新增 (25 个):
    # 用户/账户隔离相关
    '_user_lock', '_session_lock', '_token_lock', '_auth_lock',
    '_permission_lock', '_role_lock', '_tenant_lock',
    # 数据流相关
    '_stream_lock', '_buffer_lock', '_pipeline_lock', '_batch_lock',
    '_writer_lock', '_reader_lock', '_migration_writer_lock',
    # 网络/连接相关
    '_conn_lock', '_connection_lock', '_socket_lock', '_http_lock',
    '_request_lock', '_response_lock',
    # 监控/指标相关
    '_metrics_lock', '_stats_buffer_lock', '_telemetry_lock',
    '_health_lock', '_alert_lock',
    # 特征/RAG 相关
    '_feature_lock', '_index_lock', '_embed_lock', '_rag_lock',
    # 协调/调度相关
    '_scheduler_lock', '_task_lock', '_worker_lock', '_job_lock',
    '_workflow_lock', '_dispatch_lock',
    # 通知/反馈相关
    '_notify_lock', '_send_lock', '_channel_lock',
    # 持久化/恢复相关
    '_persist_lock', '_snapshot_lock', '_recovery_lock',
    '_checkpoint_lock', '_wal_lock', '_tx_lock',

    # R195-C 二次补充 (从 R195 实测发现):
    # - event_bus.py 实际使用 _coro_lock + _dedup_lock
    # - cache_key_factory.py 实际使用 4 锁独立 (_lru_lock + _migration_lock + _validation_lock + _stats_lock)
    # - 部分子系统使用 _write_lock + _read_lock 替代 _writer_lock + _reader_lock
    # - 隔离区/批处理使用 _batch_lock + _dedup_lock
    '_coro_lock', '_dedup_lock', '_write_lock', '_read_lock',
    '_subscriber_lock', '_dispatcher_lock', '_publish_lock',
    '_buffer_pool_lock', '_replay_lock', '_orphan_lock',

    # FeatureFlagManager 锁
    '_flag_lock', '_change_lock',

    # 数据导入/导出
    '_import_lock', '_export_lock', '_sync_lock', '_load_lock',

    # ============================================================
    # R198-B HVD-195-C-3 新增 (2026-07-25, 子智能体 B 报告):
    # 86 → 107 个业务锁名 (+21 个高频新增, 全部实测扫描确认 >= 2 次出现)
    # 扫描源: core/ 全子目录, 排除 tests/ + __pycache__/
    # 强制度: R104 §12 5 铁律 + R174 §12 AST 严格扫描 + R6 §6.1 8 铁律
    # ============================================================
    # Manager/Service 通用 (高频 10 次)
    '_manager_lock', '_service_lock',
    # DB/Engine 核心 (高频 6/4 次)
    '_db_lock', '_engine_lock',
    # Position/Container (高频 4/3 次)
    '_position_lock', '_container_lock',
    # Init 流程 (高频 3/3 次)
    '_initialization_lock', '_init_lock',
    # Task/Provider/Analysis (高频 2 次)
    '_tasks_lock', '_provider_lock', '_analysis_lock',
    # Global/Listener/Threshold (高频 2 次)
    '_global_lock', '_listener_lock', '_threshold_lock',
    # Flush/Rule/Version (高频 2 次)
    '_flush_lock', '_rule_lock', '_version_lock',
    # Training/Env/Plugin/Arbitrator (高频 2 次)
    '_training_lock', '_env_lock', '_plugin_lock', '_arbitrator_lock',

    # ============================================================
    # ⚠️ 注意: 业务隔离类锁 (R195-C P3 类别)
    # 同方法内 _account_lock + _user_lock 同时持锁 → 业务隔离违规
    # 同方法内 _order_lock + _trading_lock 同时持锁 → 业务边界模糊
    # ============================================================
}

# 业务隔离锁名分组 (R195-C P3 类别, 同组内锁嵌套 = 业务隔离违规)
BUSINESS_ISOLATION_GROUPS = {
    'user_account': {'_user_lock', '_account_lock', '_session_lock', '_auth_lock', '_token_lock', '_permission_lock', '_role_lock', '_tenant_lock'},
    'order_trading': {'_order_lock', '_trading_lock', '_positions_lock', '_account_lock', '_position_lock'},
    'cache_data': {'_cache_lock', '_data_lock', '_lru_lock', '_stream_lock', '_buffer_lock', '_pipeline_lock', '_batch_lock', '_db_lock'},
    'network_io': {'_conn_lock', '_connection_lock', '_socket_lock', '_http_lock', '_request_lock', '_response_lock'},
    'metrics_monitor': {'_metrics_lock', '_stats_buffer_lock', '_telemetry_lock', '_health_lock', '_alert_lock', '_monitor_lock', '_stats_lock', '_history_lock'},
    'persistence': {'_persist_lock', '_snapshot_lock', '_recovery_lock', '_checkpoint_lock', '_wal_lock', '_tx_lock', '_migration_lock', '_migration_writer_lock'},
    'feature_rag': {'_feature_lock', '_index_lock', '_embed_lock', '_rag_lock', '_flag_lock', '_change_lock'},
    'scheduler': {'_scheduler_lock', '_task_lock', '_worker_lock', '_job_lock', '_workflow_lock', '_dispatch_lock', '_coordinator_lock', '_tasks_lock'},
    'notify_channel': {'_notify_lock', '_send_lock', '_channel_lock', '_event_lock', '_bus_lock'},
    'import_export': {'_import_lock', '_export_lock', '_sync_lock', '_load_lock', '_writer_lock', '_reader_lock'},
    # R198-B HVD-195-C-3 新增 (2026-07-25):
    'manager_service': {'_manager_lock', '_service_lock', '_container_lock'},
    'init_lifecycle': {'_initialization_lock', '_init_lock'},
    'core_engine': {'_engine_lock', '_container_lock', '_global_lock'},
    'analysis_strategy': {'_analysis_lock', '_training_lock', '_arbitrator_lock', '_rule_lock'},
    'plugin_env': {'_plugin_lock', '_env_lock', '_version_lock', '_threshold_lock'},
    'io_listeners': {'_listener_lock', '_flush_lock', '_provider_lock'},
}


def get_lock_context_expr(item: ast.withitem) -> Optional[Tuple[str, str]]:
    """从 with item 的 context_expr 提取锁标识 (instance, attr)

    返回:
        (instance_id, attr_name) 如 ("self", "_lock")
        None: 不是我们关心的锁 (非 self.attr 模式)
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

    检测 4 类违规 (R195-C v2):
    1. NESTED_LOCK_4_LOCK_VIOLATION (P0): 同实例 + 不同锁名 = R100-F-P1-1 #8 4 锁独立违规
    2. SAME_LOCK_REENTRY (P1): 同实例 + 同锁名 = RLock 重入 (允许) / Lock 序列化 (违规)
    3. CROSS_INSTANCE_LOCK (P2): 跨实例锁嵌套 (业务反模式)
    4. BUSINESS_ISOLATION_VIOLATION (P3, R195-C 新增): 同组业务隔离锁嵌套 (例如 _account_lock + _user_lock)
    """
    violations = []
    for node in body:
        if isinstance(node, ast.With):
            current_locks = get_with_locks(node.items)
            violations.extend(_check_lock_violations(
                parent_locks, current_locks, node.lineno, node.col_offset,
                depth, method_name, file_path, 'sync',
            ))
            # 递归进入 with.body (R104 §12 #3 强约束: 严禁 ast.walk 扁平化)
            violations.extend(find_nested_locks(
                node.body,
                parent_locks | current_locks,
                depth + 1,
                method_name,
                file_path,
            ))
        elif isinstance(node, ast.AsyncWith):
            current_locks = get_with_locks(node.items)
            violations.extend(_check_lock_violations(
                parent_locks, current_locks, node.lineno, node.col_offset,
                depth, method_name, file_path, 'async',
            ))
            violations.extend(find_nested_locks(
                node.body,
                parent_locks | current_locks,
                depth + 1,
                method_name,
                file_path,
            ))
        elif isinstance(node, ast.Try):
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


def _check_lock_violations(
    parent_locks: Set[Tuple[str, str]],
    current_locks: Set[Tuple[str, str]],
    lineno: int,
    col: int,
    depth: int,
    method_name: str,
    file_path: str,
    ctx_type: str,
) -> List[Dict[str, Any]]:
    """检测单层锁嵌套的 4 类违规 (R195-C v2)"""
    violations = []
    async_suffix = '_ASYNC' if ctx_type == 'async' else ''
    for parent_lock in parent_locks:
        for current_lock in current_locks:
            p_inst, p_attr = parent_lock
            c_inst, c_attr = current_lock
            base = {
                'file': file_path,
                'method': method_name,
                'line': lineno,
                'col': col,
                'depth': depth,
                'parent': f"{p_inst}.{p_attr}",
                'current': f"{c_inst}.{c_attr}",
            }
            # 1. 同实例 + 不同锁名 = P0 (R100-F-P1-1 #8 4 锁独立违规)
            if p_inst == c_inst and p_attr != c_attr:
                violations.append({**base,
                    'type': f'NESTED_LOCK_4_LOCK_VIOLATION{async_suffix}',
                    'severity': 'P0',
                    'rule': 'R100-F-P1-1 #8 4 锁独立策略',
                })
            # 2. 同实例 + 同锁名 = P1 (RLock 重入允许, Lock 序列化违规)
            elif p_inst == c_inst and p_attr == c_attr:
                violations.append({**base,
                    'type': f'SAME_LOCK_REENTRY{async_suffix}',
                    'severity': 'P1',
                    'rule': 'R104 §12 #3 同锁重入 (RLock 允许, Lock 序列化)',
                })
            # 3. 跨实例锁嵌套 = P2
            elif p_inst != c_inst:
                violations.append({**base,
                    'type': f'CROSS_INSTANCE_LOCK{async_suffix}',
                    'severity': 'P2',
                    'rule': 'R104 §12 #3 跨实例锁嵌套',
                })
            # 4. 业务隔离 (R195-C 新增 P3)
            # 同实例 + 不同锁名 + 同属一个业务隔离组 = 业务隔离违规
            if p_inst == c_inst and p_attr != c_attr:
                p_group = _find_business_group(p_attr)
                c_group = _find_business_group(c_attr)
                if p_group and c_group and p_group == c_group:
                    violations.append({**base,
                        'type': f'BUSINESS_ISOLATION_VIOLATION{async_suffix}',
                        'severity': 'P3',
                        'rule': f'R195-C P3 业务隔离 (同组 {p_group} 锁嵌套)',
                        'group': p_group,
                    })
    return violations


def _find_business_group(lock_attr: str) -> Optional[str]:
    """查找锁所属业务隔离组"""
    for group_name, group_locks in BUSINESS_ISOLATION_GROUPS.items():
        if lock_attr in group_locks:
            return group_name
    return None


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
    verified_violations = []
    for v in violations:
        if v.get('method') != method_node.name:
            continue
        parent = v.get('parent', '')
        current = v.get('current', '')
        if parent in unparse_str and current in unparse_str:
            parent_line = -1
            current_line = -1
            for i, line in enumerate(unparse_lines):
                if parent in line and parent_line == -1:
                    parent_line = i
                if current in line and current_line == -1:
                    current_line = i
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
            v['unparse_skip_reason'] = 'parent or current not in unparse'
    return {
        'method': method_node.name,
        'lineno': method_node.lineno,
        'unparse_ok': True,
        'line_count': line_count,
        'verified_violations': verified_violations,
    }


def collect_lock_names_in_file(file_path: str) -> Set[str]:
    """收集文件中实际使用的锁名 (供锁名覆盖率报告)"""
    if not os.path.exists(file_path):
        return set()
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    found_locks = set()
    for node in ast.walk(tree):
        # 锁定义: self._xxx_lock = threading.Lock() / RLock()
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Attribute) and
                    isinstance(target.value, ast.Name) and
                    target.value.id == 'self'):
                    attr = target.attr
                    if attr.endswith('_lock'):
                        found_locks.add(attr)
        # with 语句中的锁使用
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if (isinstance(item.context_expr, ast.Attribute) and
                    isinstance(item.context_expr.value, ast.Name) and
                    item.context_expr.value.id == 'self'):
                    attr = item.context_expr.attr
                    if attr.endswith('_lock'):
                        found_locks.add(attr)
    return found_locks


def analyze_file(file_path: str, return_unparse: bool = False) -> Dict:
    """分析单个 Python 文件的锁架构

    返回:
        {
            'file': file_path,
            'total_methods': int,
            'p0/p1/p2/p3_violations': List[Dict],
            'unparse_verified': bool,
            'lock_names_found': Set[str],
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
    lock_names_found = set()

    # 收集锁名 (用于覆盖率报告)
    lock_names_found = collect_lock_names_in_file(file_path)

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
                unparse_res = verify_method_with_unparse(node, method_violations)
                unparse_results.append(unparse_res)

    p0_violations = [v for v in all_violations if v.get('severity') == 'P0' and v.get('unparse_verified', True)]
    p1_violations = [v for v in all_violations if v.get('severity') == 'P1' and v.get('unparse_verified', True)]
    p2_violations = [v for v in all_violations if v.get('severity') == 'P2' and v.get('unparse_verified', True)]
    p3_violations = [v for v in all_violations if v.get('severity') == 'P3' and v.get('unparse_verified', True)]
    unverified = [v for v in all_violations if not v.get('unparse_verified', True)]

    result = {
        'file': file_path,
        'total_methods': total_methods,
        'total_violations': len(all_violations),
        'p0_violations': p0_violations,
        'p1_violations': p1_violations,
        'p2_violations': p2_violations,
        'p3_violations': p3_violations,
        'unverified': unverified,
        'lock_names_found': sorted(lock_names_found),
    }
    if return_unparse:
        result['unparse_results'] = unparse_results
    return result


def main():
    """主函数: 支持单文件或目录扫描 + JSON 输出 + 汇总模式"""
    # 设置 stdout 为 UTF-8 (修复 R194-C v1 UnicodeEncodeError)
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description='R195-C 锁架构 AST 验证脚本 v2 (R104 §12 #3 + #5 + R100-F-P1-1 #8 4 锁独立策略)',
    )
    parser.add_argument('target', help='单文件或目录路径')
    parser.add_argument('--json', action='store_true', help='输出 JSON 格式 (供下游工具消费)')
    parser.add_argument('--summary', action='store_true', help='仅输出汇总 (快速巡检)')
    parser.add_argument('--coverage', action='store_true', help='输出锁名覆盖率报告 (R195-C 新增)')
    args = parser.parse_args()

    target = args.target

    files_to_analyze = []
    if os.path.isfile(target):
        files_to_analyze = [target]
    elif os.path.isdir(target):
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if f.endswith('.py'):
                    files_to_analyze.append(os.path.join(root, f))
    else:
        print(f"Error: {target} 不存在")
        sys.exit(1)

    # 全局锁名汇总 (供覆盖率报告)
    global_lock_names = set()
    all_results = []

    total_p0 = 0
    total_p1 = 0
    total_p2 = 0
    total_p3 = 0
    total_unverified = 0
    files_with_violations = 0

    for file_path in files_to_analyze:
        result = analyze_file(file_path)
        if 'error' in result:
            if not args.summary:
                print(f"[SKIP] {file_path}: {result['error']}")
            continue

        all_results.append(result)
        global_lock_names.update(result.get('lock_names_found', []))

        p0 = len(result['p0_violations'])
        p1 = len(result['p1_violations'])
        p2 = len(result['p2_violations'])
        p3 = len(result['p3_violations'])
        unverified = len(result['unverified'])

        total_p0 += p0
        total_p1 += p1
        total_p2 += p2
        total_p3 += p3
        total_unverified += unverified

        if p0 + p1 + p2 + p3 > 0:
            files_with_violations += 1

        if not args.summary and not args.json:
            if p0 + p1 + p2 + p3 > 0:
                print(f"[VIOLATION] {file_path}:")
                print(f"  total_methods={result['total_methods']}")
                print(f"  P0: {p0}, P1: {p1}, P2: {p2}, P3: {p3}, unverified: {unverified}")
                for v in result['p0_violations'][:3]:
                    print(f"    P0 L{v['line']} {v['method']}: {v['type']} parent={v['parent']} current={v['current']}")
                if p0 > 3:
                    print(f"    ... ({p0 - 3} more P0)")
                for v in result['p1_violations'][:2]:
                    print(f"    P1 L{v['line']} {v['method']}: {v['type']} parent={v['parent']} current={v['current']}")
                for v in result['p3_violations'][:2]:
                    print(f"    P3 L{v['line']} {v['method']}: {v['type']} group={v.get('group')} parent={v['parent']} current={v['current']}")
            else:
                print(f"[OK] {file_path}: {result['total_methods']} methods, 0 violations")

    if args.json:
        # JSON 输出模式
        output = {
            'target': target,
            'total_files': len(files_to_analyze),
            'files_with_violations': files_with_violations,
            'p0_count': total_p0,
            'p1_count': total_p1,
            'p2_count': total_p2,
            'p3_count': total_p3,
            'unverified_count': total_unverified,
            'business_lock_names_count': len(BUSINESS_LOCK_NAMES),
            'business_lock_names_in_code': sorted(global_lock_names),
            'business_isolation_groups': len(BUSINESS_ISOLATION_GROUPS),
            'files': all_results,
            'pass': (total_p0 + total_p1 + total_p2 + total_p3 == 0),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print()
        print('=== 汇总 ===')
        print(f"扫描路径: {target}")
        print(f"扫描文件数: {len(files_to_analyze)}")
        print(f"违规文件数: {files_with_violations}")
        print(f"P0 (R100-F-P1-1 #8 4 锁独立违规): {total_p0}")
        print(f"P1 (同锁重入): {total_p1}")
        print(f"P2 (跨实例锁嵌套): {total_p2}")
        print(f"P3 (R195-C 新增 业务隔离): {total_p3}")
        print(f"unverified (R104 §12 #5 AST unparse 验证未通过): {total_unverified}")

        if args.coverage:
            print()
            print('=== 锁名覆盖率报告 (R195-C 新增) ===')
            print(f"业务锁名集合: {len(BUSINESS_LOCK_NAMES)} 个")
            print(f"代码中实际命中: {len(global_lock_names)} 个")
            coverage = len(global_lock_names & BUSINESS_LOCK_NAMES) / max(len(global_lock_names), 1) * 100
            print(f"覆盖率: {coverage:.1f}%")
            print(f"代码中锁名列表: {sorted(global_lock_names)}")
            # 未覆盖锁名 (代码中用但不在业务锁名集合 → 提示 R196+ 扩展)
            uncovered = global_lock_names - BUSINESS_LOCK_NAMES
            if uncovered:
                print(f"未覆盖锁名 (R196+ 可扩展): {sorted(uncovered)}")

        if total_p0 == 0 and total_p1 == 0 and total_p2 == 0 and total_p3 == 0:
            print("[PASS] 0 锁架构违规")
        else:
            print("[FAIL] 发现锁架构违规, 详见上方输出")
            sys.exit(1)


if __name__ == "__main__":
    main()
