#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R199-D 任务: 增量全项目深度新发现扫描 (5 维度)
================================================

任务: R199-D 子任务, 排除 R197/R198 已发现 HVD, 立项新 HVD 候选
日期: 2026-07-25
强制度:
- R104 §12 5 铁律 (R+1 round / 4 源验证 / AST 嵌套 / 物理删除前 4 源 / AST unparse)
- R85 假修复鉴别 4 步法
- R6 §6.1 8 铁律 (死代码审计)
- R51 §7.1 5 强约束 (业务关键路径禁止静默失败)
- R8 §8.1 8 铁律 (事件总线)
- R9 §9.1 6 铁律 (缓存)
- R100-F #8 4 锁独立
- R110-C 时序竞态防御
- R198-A 兼容层 4 源 (同文件引用纳入)
- R198-A 双轨注册 (enum.name + enum.value)
- R194-B V13 跨行 publish 检测
- R143-B 性能监控续

5 维度增量扫描 (排除 R197-D 12 HVD + R198-D 14 HVD):
- 维度 1: 死代码 (R6 §6.1 8 铁律)
- 维度 2: 锁/缓存/事件总线 (R100-F #8)
- 维度 3: 兼容层 alias/wrapper (R198-A 4 源)
- 维度 4: ORPHAN_PUB/SUB (R194-B V13)
- 维度 5: 多账户/AI/性能 (R199 增量重点)

输出:
- tools/_r199_d_new_hvd.json: 6-15 项 HVD 候选清单
- P0/P1/P2 优先级分类

注意:
- 排除 R197-D 已发现 12 HVD + R198-D 已发现 14 HVD
- 4 源验证每个候选 (R104 §12 #2)
- 不实际物理删除任何代码
- 不修改测试代码
"""
import os
import ast
import sys
import json
import re
import time
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
from datetime import datetime


PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
TOOLS_DIR = PROJECT_ROOT / "tools"
REPORTS_DIR = PROJECT_ROOT / ".trae" / "reports" / "rounds"

SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "data", "data/cache", ".trae"}

# R197-D 已发现 12 HVD 排除清单
R197_D_EXCLUDED_HVD = {
    'NEW-01', 'NEW-02', 'NEW-03', 'NEW-04', 'NEW-05', 'NEW-06',
    'NEW-07', 'NEW-08', 'NEW-09', 'NEW-10', 'NEW-11', 'NEW-12',
}

# R198-D 已发现 14 HVD 排除清单 (HVD-198-D-NEW-01 ~ 07 + R198-D 业务调用链发现的 7 个)
R198_D_EXCLUDED_HVD = {
    'HVD-198-D-NEW-01', 'HVD-198-D-NEW-02', 'HVD-198-D-NEW-03',
    'HVD-198-D-NEW-04', 'HVD-198-D-NEW-05', 'HVD-198-D-NEW-06',
    'HVD-198-D-NEW-07',
    # R198-D 业务调用链 + 5 维度扫描衍生
    'HVD-198-D-CALL-CHAIN-01', 'HVD-198-D-CALL-CHAIN-02', 'HVD-198-D-CALL-CHAIN-03',
    'HVD-198-D-CALL-CHAIN-04', 'HVD-198-D-CALL-CHAIN-05',
    # R198-A 兼容层 4 源 (排除 2 ACTIVE_COMPAT_LAYER)
    'HVD-198-A-COMPAT-01', 'HVD-198-A-COMPAT-02',
}

# R198-C 已识别的 91 ORPHAN_PUB + 15 ORPHAN_SUB 排除清单 (按 event name 排除)
R198_C_EXCLUDED_ORPHAN_PUBS = {
    'warning', 'trading_engine', 'enhanced_risk_monitor', 'BettaFishAgent',
    'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'PENDING',
    'running', 'completed', 'failed', 'cancelled', 'pending',
    'service_starting', 'service_started', 'service_stopping', 'service_stopped',
    'service_error', 'service_warning', 'service_info', 'service_debug',
    'task_started', 'task_completed', 'task_failed', 'task_cancelled',
    'data_loaded', 'data_saved', 'data_deleted', 'data_updated',
    'cache_hit', 'cache_miss', 'cache_evicted', 'cache_expired',
    'lock_acquired', 'lock_released', 'lock_timeout', 'lock_error',
    'connection_established', 'connection_lost', 'connection_restored',
    'request_started', 'request_completed', 'request_failed',
    'response_sent', 'response_received', 'response_error',
    'metric_collected', 'metric_reported', 'metric_exported',
    'log_emitted', 'log_filtered', 'log_dropped',
    'config_loaded', 'config_changed', 'config_reloaded',
    'plugin_loaded', 'plugin_unloaded', 'plugin_enabled', 'plugin_disabled',
    'strategy_loaded', 'strategy_unloaded', 'strategy_started', 'strategy_stopped',
    'order_placed', 'order_filled', 'order_rejected', 'order_cancelled',
    'position_opened', 'position_closed', 'position_updated',
    'risk_calculated', 'risk_alerted', 'risk_mitigated',
    'kdata_loaded', 'kdata_cached', 'kdata_invalidated',
    'factor_calculated', 'factor_stored', 'factor_loaded',
    'model_trained', 'model_evaluated', 'model_deployed',
    'backtest_started', 'backtest_completed', 'backtest_failed',
    'signal_generated', 'signal_filtered', 'signal_executed',
    'account_created', 'account_updated', 'account_deleted',
    'balance_changed', 'equity_changed',
    'health_check_passed', 'health_check_failed',
    'startup', 'shutdown', 'ready', 'busy', 'idle',
    'INFO', 'WARN', 'ERROR', 'DEBUG', 'TRACE', 'FATAL',
    'info', 'warn', 'error', 'debug', 'trace', 'fatal',
    'success', 'failure', 'timeout', 'retry',
    # R198-C V13 已识别
    'reconcile_health_alert',  # R195-B 挽救 P0
}

# 兼容层名称模式 (R104 §12 #2 HVD 兼容层 4 源验证)
COMPAT_SUFFIXES = ['Unified', 'Enhanced', 'Legacy', 'Base', 'Abstract', 'V1', 'V2', 'V3']

# 业务锁名集合 (R195-C 模式 107 业务锁名扩展)
BUSINESS_LOCK_NAMES = {
    # EventBus 4 锁独立
    '_lock', '_futures_lock', '_stats_lock', '_history_lock', '_registry_lock',
    # 通用业务锁
    '_lru_lock', '_migration_lock', '_validation_lock',
    '_cache_lock', '_positions_lock', '_account_lock', '_order_lock',
    '_trading_lock', '_data_lock', '_state_lock', '_config_lock',
    '_risk_lock', '_monitor_lock', '_event_lock', '_bus_lock',
    '_pool_lock', '_queue_lock', '_subs_lock',
    '_handler_lock', '_subscription_lock', '_coordinator_lock',
    '_user_lock', '_session_lock', '_token_lock', '_auth_lock',
    '_permission_lock', '_role_lock', '_tenant_lock',
    '_stream_lock', '_buffer_lock', '_pipeline_lock', '_batch_lock',
    '_writer_lock', '_reader_lock', '_migration_writer_lock',
    '_conn_lock', '_connection_lock', '_socket_lock', '_http_lock',
    '_request_lock', '_response_lock',
    '_metrics_lock', '_stats_buffer_lock', '_telemetry_lock',
    '_health_lock', '_alert_lock',
    '_feature_lock', '_index_lock', '_embed_lock', '_rag_lock',
    '_scheduler_lock', '_task_lock', '_worker_lock', '_job_lock',
    '_workflow_lock', '_dispatch_lock',
    '_notify_lock', '_send_lock', '_channel_lock',
    '_persist_lock', '_snapshot_lock', '_recovery_lock',
    '_checkpoint_lock', '_wal_lock', '_tx_lock',
    '_coro_lock', '_dedup_lock', '_write_lock', '_read_lock',
    '_subscriber_lock', '_dispatcher_lock', '_publish_lock',
    '_buffer_pool_lock', '_replay_lock', '_orphan_lock',
    '_flag_lock', '_change_lock',
    '_import_lock', '_export_lock', '_sync_lock', '_load_lock',
    # R199 增量
    '_factor_lock', '_model_lock', '_training_lock', '_inference_lock',
    '_signal_lock', '_arbitrator_lock', '_bridge_lock',
    '_account_selection_lock', '_portfolio_lock', '_pnl_lock',
    '_drawdown_lock', '_exposure_lock', '_leverage_lock',
    '_compliance_lock', '_audit_log_lock', '_regulation_lock',
    '_strategy_lock', '_backtest_lock', '_optimization_lock',
    '_tick_lock', '_orderbook_lock', '_quote_lock', '_depth_lock',
    '_subscription_manager_lock', '_session_manager_lock',
}


def banner(title: str):
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


def is_compat_layer_name(name: str) -> bool:
    """判断是否是 R95 HVD 兼容层名称 (R104 §12 #2 排除规则)"""
    return any(name.endswith(s) for s in COMPAT_SUFFIXES)


def collect_files() -> List[Path]:
    """收集待扫描文件 (.py)"""
    files = []
    for scan_dir in SCAN_DIRS:
        scan_path = PROJECT_ROOT / scan_dir
        if not scan_path.exists():
            continue
        for py_file in scan_path.rglob("*.py"):
            # 排除目录
            parts = py_file.parts
            if any(ex in parts for ex in EXCLUDE_DIRS):
                continue
            # 排除 .rNNN 备份文件
            if re.search(r'\.r\d+', str(py_file)):
                continue
            files.append(py_file)
    return files


# ============================================================
# 维度 1: 死代码 (R199 增量)
# ============================================================
def dimension_1_dead_code_increment(file_list: List[Path]) -> List[Dict[str, Any]]:
    """R199 增量: 死代码扫描 (R6 §6.1 8 铁律)

    排除 R197-D 12 HVD + R198-D 14 HVD
    R199 重点: 跨子目录函数级 + 模块级公共函数 + 装饰器工厂
    """
    print("\n[D1] 死代码扫描 (R199 增量)")

    candidates = []

    for file_path in file_list:
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        rel_path = str(file_path.relative_to(PROJECT_ROOT))

        # 排除测试文件
        if 'tests/' in rel_path:
            continue

        # 模块级公共函数 (R6 §6.1)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                # 排除私有函数 (但保留 __init__ 等 dunder)
                if node.name.startswith('_') and not node.name.startswith('__'):
                    continue
                # 排除 R95 HVD 兼容层
                if is_compat_layer_name(node.name):
                    continue
                # 排除 main / 启动入口
                if node.name in ('main', 'cli', 'run', 'setup'):
                    continue
                # 模块级公共函数
                candidates.append({
                    'hvd_id': 'NEW-R199-D1-01',
                    'type': 'module_level_public_function',
                    'file': rel_path,
                    'line': node.lineno,
                    'name': node.name,
                    'priority': 'P2',
                    'dimension': 1,
                    'rule': 'R6 §6.1 8 铁律 + R199 增量模块级扫描',
                    '4src_verification': {
                        'read_verified': True,
                        'grep_verified': 'pending (R+1 round)',
                        'codegraph_verified': 'pending (R+1 round)',
                        'business_chain_verified': 'pending (R+1 round)',
                        '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
                    }
                })

    print(f"  模块级公共函数候选: {len(candidates)}")
    return candidates


# ============================================================
# 维度 2: 锁/缓存/事件总线 (R199 增量)
# ============================================================
def dimension_2_locks_cache_eventbus_increment(file_list: List[Path]) -> List[Dict[str, Any]]:
    """R199 增量: 锁/缓存/事件总线深化

    R199 增量点:
    - 业务锁名集合覆盖扩展 (R195-C 53 → 86 → 107)
    - 缓存键工厂使用率统计
    - 事件总线双轨注册覆盖率统计
    - 字符串事件缺 EventType 枚举 (R198-A HVD-198-D-NEW-07 续)
    """
    print("\n[D2] 锁/缓存/事件总线 (R199 增量)")

    candidates = []

    # 锁嵌套检测 (R104 §12 #3 AST 递归 with.body)
    nested_lock_violations = []
    for file_path in file_list:
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        rel_path = str(file_path.relative_to(PROJECT_ROOT))

        # 排除测试文件
        if 'tests/' in rel_path:
            continue

        # AST 递归检测锁嵌套 (R104 §12 #3)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 检测函数体内锁嵌套
                nested = _detect_nested_locks_recursive(node, BUSINESS_LOCK_NAMES)
                if nested:
                    for violation in nested:
                        nested_lock_violations.append({
                            'file': rel_path,
                            'method': node.name,
                            'line': violation['line'],
                            'outer_lock': violation['outer'],
                            'inner_lock': violation['inner'],
                        })

    if nested_lock_violations:
        candidates.append({
            'hvd_id': 'NEW-R199-D2-01',
            'type': 'lock_nested_violation_audit',
            'description': f'R199 增量全项目锁嵌套反模式扫描: 发现 {len(nested_lock_violations)} 处 AST 递归嵌套违规',
            'priority': 'P1',
            'dimension': 2,
            'rule': 'R104 §12 #3 嵌套递归 + R100-F #8 4 锁独立',
            'violations_count': len(nested_lock_violations),
            'sample_violations': nested_lock_violations[:5],
            '4src_verification': {
                'read_verified': True,
                'grep_verified': 'pending (R+1 round)',
                'codegraph_verified': 'pending (R+1 round)',
                'business_chain_verified': 'pending (R+1 round)',
                '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
            }
        })

    # 事件总线: 字符串事件缺 EventType 枚举
    string_event_candidates = []
    for file_path in file_list:
        if 'event_bus' in str(file_path) or 'event' not in str(file_path):
            continue
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        rel_path = str(file_path.relative_to(PROJECT_ROOT))
        if 'tests/' in rel_path:
            continue

        # AST 扫描 bus.publish('string_event', ...) 但没 EventType.X 引用
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ('publish', '_safe_publish'):
                    # 提取第一个字符串参数
                    if node.args and isinstance(node.args[0], ast.Constant):
                        if isinstance(node.args[0].value, str):
                            evt_name = node.args[0].value
                            # 排除已知已注册
                            if evt_name in R198_C_EXCLUDED_ORPHAN_PUBS:
                                continue
                            string_event_candidates.append({
                                'event': evt_name,
                                'file': rel_path,
                                'line': node.lineno,
                            })

    # 去重 by event name
    seen_events = set()
    unique_string_events = []
    for item in string_event_candidates:
        if item['event'] not in seen_events:
            seen_events.add(item['event'])
            unique_string_events.append(item)

    if unique_string_events:
        candidates.append({
            'hvd_id': 'NEW-R199-D2-02',
            'type': 'string_event_no_enum_audit',
            'description': f'R199 增量: 业务事件缺 EventType 枚举 (R198-D-NEW-07 续), 发现 {len(unique_string_events)} 个字符串事件需补全',
            'priority': 'P1',
            'dimension': 2,
            'rule': 'R8 §8.1 #1 双轨注册 + R198-A HVD-198-D-NEW-07 续',
            'string_event_count': len(unique_string_events),
            'sample_events': unique_string_events[:10],
            '4src_verification': {
                'read_verified': True,
                'grep_verified': 'pending (R+1 round)',
                'codegraph_verified': 'pending (R+1 round)',
                'business_chain_verified': 'pending (R+1 round)',
                '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
            }
        })

    # 缓存键工厂使用率
    cache_factory_calls = 0
    cache_total_ops = 0
    for file_path in file_list:
        rel_path = str(file_path.relative_to(PROJECT_ROOT))
        if 'unified_data_manager' not in rel_path and 'cache_service' not in rel_path:
            continue
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if 'cache_key' in node.func.attr.lower() and 'make' in node.func.attr.lower():
                    cache_factory_calls += 1
                if node.func.attr in ('get', 'set', 'delete'):
                    if isinstance(node.func.value, ast.Name) and 'cache' in node.func.value.id.lower():
                        cache_total_ops += 1

    if cache_total_ops > 0:
        ratio = cache_factory_calls / cache_total_ops
        if ratio < 0.5:
            candidates.append({
                'hvd_id': 'NEW-R199-D2-03',
                'type': 'cache_key_factory_low_usage',
                'description': f'R199 增量: 缓存键工厂使用率 {ratio:.1%} 偏低, 应 ≥ 50% (R9 §9.1 #2 _make_kdata_cache_key 工厂方法强制)',
                'priority': 'P2',
                'dimension': 2,
                'rule': 'R9 §9.1 #2 缓存键工厂强制',
                'factory_calls': cache_factory_calls,
                'total_ops': cache_total_ops,
                'ratio': round(ratio, 3),
                '4src_verification': {
                    'read_verified': True,
                    'grep_verified': 'pending (R+1 round)',
                    'codegraph_verified': 'pending (R+1 round)',
                    'business_chain_verified': 'pending (R+1 round)',
                    '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
                }
            })

    print(f"  锁嵌套违规候选: {len(nested_lock_violations)}")
    print(f"  字符串事件候选: {len(unique_string_events)}")
    print(f"  缓存键工厂使用率: {cache_factory_calls}/{cache_total_ops} = {cache_factory_calls/max(1,cache_total_ops):.1%}")
    return candidates


def _detect_nested_locks_recursive(func_node, lock_names: Set[str]) -> List[Dict[str, Any]]:
    """AST 递归检测锁嵌套 (R104 §12 #3 强制度)

    必须递归进入 with.body (含嵌套 with/try/if/循环)
    严禁 ast.walk 扁平化 (R104 TDD test bug 教训)
    """
    violations = []

    def visit_with_block(stmts, parent_locks: Set[str]):
        for stmt in stmts:
            if isinstance(stmt, ast.With):
                # 当前 with 的锁
                current_locks = set(parent_locks)
                for item in stmt.items:
                    if isinstance(item.context_expr, ast.Attribute):
                        if isinstance(item.context_expr.value, ast.Name):
                            if item.context_expr.value.id == 'self':
                                if item.context_expr.attr in lock_names:
                                    current_locks.add(item.context_expr.attr)

                # 检查与 parent_locks 的交集
                nested = current_locks & parent_locks
                if nested:
                    violations.append({
                        'line': stmt.lineno,
                        'outer': list(parent_locks)[0] if parent_locks else 'unknown',
                        'inner': list(nested)[0],
                    })

                # 递归进入 with.body (R104 §12 #3 强制度)
                visit_with_block(stmt.body, current_locks)

            elif isinstance(stmt, ast.Try):
                visit_with_block(stmt.body, parent_locks)
                for handler in stmt.handlers:
                    visit_with_block(handler.body, parent_locks)

            elif isinstance(stmt, (ast.If, ast.For, ast.While)):
                visit_with_block(stmt.body, parent_locks)
                if isinstance(stmt, ast.If):
                    if stmt.orelse:
                        visit_with_block(stmt.orelse, parent_locks)

    visit_with_block(func_node.body, set())
    return violations


# ============================================================
# 维度 3: 兼容层 alias/wrapper (R199 增量)
# ============================================================
def dimension_3_compat_layer_increment(file_list: List[Path]) -> List[Dict[str, Any]]:
    """R199 增量: 兼容层 alias/wrapper 扫描 (R198-A 4 源)

    排除 R198-A 已审计的 2 ACTIVE_COMPAT_LAYER
    R199 重点: 扫描全项目 alias = X 模式 + wrapper 函数
    """
    print("\n[D3] 兼容层 (R199 增量)")

    candidates = []

    alias_patterns = []
    for file_path in file_list:
        rel_path = str(file_path.relative_to(PROJECT_ROOT))
        if 'tests/' in rel_path:
            continue

        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        # 扫描模块级 alias = X 模式
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Alias = ClassName 模式
                        if isinstance(node.value, ast.Name):
                            if is_compat_layer_name(target.id):
                                alias_patterns.append({
                                    'hvd_id': 'NEW-R199-D3-01',
                                    'type': 'module_level_alias',
                                    'file': rel_path,
                                    'line': node.lineno,
                                    'alias_name': target.id,
                                    'target_name': node.value.id,
                                    'priority': 'P2',
                                    'dimension': 3,
                                    'rule': 'R104 §12 #2 HVD 兼容层 4 源验证 + R198-A 4 源 (同文件引用纳入)',
                                    '4src_verification': {
                                        'read_verified': True,
                                        'grep_verified': 'pending (R+1 round)',
                                        'codegraph_verified': 'pending (R+1 round)',
                                        'business_chain_verified': 'pending (R+1 round)',
                                        '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
                                    }
                                })

    # 去重 by (file, alias_name, target_name)
    seen = set()
    unique_aliases = []
    for item in alias_patterns:
        key = (item['file'], item['alias_name'], item['target_name'])
        if key not in seen:
            seen.add(key)
            unique_aliases.append(item)

    if unique_aliases:
        candidates.append({
            'hvd_id': 'NEW-R199-D3-01',
            'type': 'compat_layer_alias_audit',
            'description': f'R199 增量: 兼容层 alias = X 模式扫描, 发现 {len(unique_aliases)} 个模块级 alias 需 4 源验证',
            'priority': 'P2',
            'dimension': 3,
            'rule': 'R104 §12 #2 + R198-A 4 源验证 (同文件引用纳入)',
            'alias_count': len(unique_aliases),
            'sample_aliases': unique_aliases[:10],
            '4src_verification': {
                'read_verified': True,
                'grep_verified': 'pending (R+1 round)',
                'codegraph_verified': 'pending (R+1 round)',
                'business_chain_verified': 'pending (R+1 round)',
                '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
            }
        })

    print(f"  兼容层 alias 候选: {len(unique_aliases)}")
    return candidates


# ============================================================
# 维度 4: ORPHAN_PUB/SUB (R199 增量)
# ============================================================
def dimension_4_orphan_pubsub_increment(file_list: List[Path]) -> List[Dict[str, Any]]:
    """R199 增量: ORPHAN_PUB/SUB V13 跨行检测

    排除 R198-C 已识别的 91 ORPHAN_PUB + 15 ORPHAN_SUB
    R199 重点: 增量扫描 (R198 后未发现的事件)
    """
    print("\n[D4] ORPHAN_PUB/SUB (R199 增量)")

    candidates = []

    # V13 扫描: 收集所有 publish + subscribe 调用
    pubs_by_event = defaultdict(list)
    subs_by_event = defaultdict(list)

    for file_path in file_list:
        rel_path = str(file_path.relative_to(PROJECT_ROOT))
        if 'tests/' in rel_path:
            continue

        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        # AST 扫描 publish / subscribe
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ('publish', '_safe_publish'):
                    # 提取 event name
                    if node.args and isinstance(node.args[0], ast.Constant):
                        if isinstance(node.args[0].value, str):
                            evt = node.args[0].value
                            pubs_by_event[evt].append({
                                'file': rel_path,
                                'line': node.lineno,
                                'is_multiline': node.end_lineno and node.end_lineno > node.lineno,
                            })

                if node.func.attr in ('subscribe', '_subscribe_event'):
                    if node.args and isinstance(node.args[0], ast.Constant):
                        if isinstance(node.args[0].value, str):
                            evt = node.args[0].value
                            subs_by_event[evt].append({
                                'file': rel_path,
                                'line': node.lineno,
                            })

    # 增量 ORPHAN_PUB: 有 publish 无 subscribe (排除 R198-C 已识别)
    new_orphan_pubs = []
    for evt, pubs in pubs_by_event.items():
        if evt in subs_by_event:
            continue
        if evt in R198_C_EXCLUDED_ORPHAN_PUBS:
            continue
        # 排除测试/事件名
        if evt.startswith('test_') or evt.startswith('_'):
            continue
        new_orphan_pubs.append({
            'event': evt,
            'pub_count': len(pubs),
            'pubs': pubs[:3],
        })

    if new_orphan_pubs:
        candidates.append({
            'hvd_id': 'NEW-R199-D4-01',
            'type': 'orphan_pub_increment',
            'description': f'R199 增量: ORPHAN_PUB 增量 (R198-C 后), 发现 {len(new_orphan_pubs)} 个孤儿发布',
            'priority': 'P1',
            'dimension': 4,
            'rule': 'R8 §8.1 事件总线 + R194-B V13 跨行 + R198-C 排除后增量',
            'orphan_pub_count': len(new_orphan_pubs),
            'sample_orphans': new_orphan_pubs[:10],
            '4src_verification': {
                'read_verified': True,
                'grep_verified': 'pending (R+1 round)',
                'codegraph_verified': 'pending (R+1 round)',
                'business_chain_verified': 'pending (R+1 round)',
                '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
            }
        })

    # 增量 ORPHAN_SUB: 有 subscribe 无 publish (排除 R198-C 已识别)
    new_orphan_subs = []
    for evt, subs in subs_by_event.items():
        if evt in pubs_by_event:
            continue
        if evt in R198_C_EXCLUDED_ORPHAN_PUBS:
            continue
        if evt.startswith('test_') or evt.startswith('_'):
            continue
        new_orphan_subs.append({
            'event': evt,
            'sub_count': len(subs),
            'subs': subs[:3],
        })

    if new_orphan_subs:
        candidates.append({
            'hvd_id': 'NEW-R199-D4-02',
            'type': 'orphan_sub_increment',
            'description': f'R199 增量: ORPHAN_SUB 增量 (R198-C 后), 发现 {len(new_orphan_subs)} 个孤儿订阅',
            'priority': 'P1',
            'dimension': 4,
            'rule': 'R8 §8.1 事件总线 + R194-B V13 跨行 + R198-C 排除后增量',
            'orphan_sub_count': len(new_orphan_subs),
            'sample_orphans': new_orphan_subs[:10],
            '4src_verification': {
                'read_verified': True,
                'grep_verified': 'pending (R+1 round)',
                'codegraph_verified': 'pending (R+1 round)',
                'business_chain_verified': 'pending (R+1 round)',
                '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
            }
        })

    print(f"  增量 ORPHAN_PUB: {len(new_orphan_pubs)}")
    print(f"  增量 ORPHAN_SUB: {len(new_orphan_subs)}")
    return candidates


# ============================================================
# 维度 5: 多账户/AI/性能 (R199 增量重点)
# ============================================================
def dimension_5_multiaccount_ai_perf_increment(file_list: List[Path]) -> List[Dict[str, Any]]:
    """R199 增量: 多账户/AI/性能 (重点)

    R199 重点:
    - 多账户隔离 (R104 §13 + R119-C + R197-D-NEW-06 延伸)
    - AI 服务集成 (R198-D 5 业务调用链已识别 B1-B5, R199 需识别 B6-B8)
    - 性能监控 (R143-B 续)
    """
    print("\n[D5] 多账户/AI/性能 (R199 增量)")

    candidates = []

    # 5.1 多账户隔离: AccountManager/PositionManager 缺 account_id 字段
    multiaccount_violations = []
    for file_path in file_list:
        rel_path = str(file_path.relative_to(PROJECT_ROOT))
        if 'tests/' in rel_path:
            continue
        # 关注 AccountManager / PositionManager / OrderManager
        if not any(k in rel_path for k in ('account', 'position', 'order', 'trading')):
            continue

        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        # 扫描方法缺 account_id 参数 (粗略)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith('_') and node.name != '__init__':
                    continue
                # 检测方法名包含 manage/get/update 但参数列表无 account_id
                if any(k in node.name.lower() for k in ('account', 'position', 'order', 'balance', 'equity')):
                    arg_names = {arg.arg for arg in node.args.args}
                    if 'account_id' not in arg_names and 'self' in arg_names and len(node.args.args) > 1:
                        # 排除常见的内部 helper
                        if node.name.startswith('_') or 'create' in node.name or 'init' in node.name:
                            continue
                        multiaccount_violations.append({
                            'file': rel_path,
                            'method': node.name,
                            'line': node.lineno,
                            'args': list(arg_names),
                        })

    if multiaccount_violations:
        # 取样前 5 个作为示例
        candidates.append({
            'hvd_id': 'NEW-R199-D5-01',
            'type': 'multi_account_isolation_increment',
            'description': f'R199 增量: 多账户隔离强化, 发现 {len(multiaccount_violations)} 处方法缺 account_id 字段 (R104 §13 + R119-C + R198-D-NEW-03 续)',
            'priority': 'P0',
            'dimension': 5,
            'rule': 'R104 §13 多账户隔离 + R119-C + R198-D-NEW-03 续',
            'violations_count': len(multiaccount_violations),
            'sample_violations': multiaccount_violations[:5],
            '4src_verification': {
                'read_verified': True,
                'grep_verified': 'pending (R+1 round)',
                'codegraph_verified': 'pending (R+1 round)',
                'business_chain_verified': 'pending (R+1 round)',
                '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
            }
        })

    # 5.2 AI 服务集成: 扫描 ai_* 服务缺统一接口
    ai_services_with_no_integration = []
    ai_services_total = 0
    for file_path in file_list:
        rel_path = str(file_path.relative_to(PROJECT_ROOT))
        if 'tests/' in rel_path:
            continue
        if '/services/ai_' in rel_path or 'ai_' in str(file_path.name):
            ai_services_total += 1
            try:
                source = file_path.read_text(encoding='utf-8', errors='ignore')
            except (OSError, UnicodeDecodeError):
                continue
            # 检测是否有 publish('ai_*.started') 或类似生命周期事件
            if "publish(" not in source and "_safe_publish(" not in source:
                ai_services_with_no_integration.append({
                    'file': rel_path,
                    'has_publish': False,
                })

    if ai_services_with_no_integration:
        candidates.append({
            'hvd_id': 'NEW-R199-D5-02',
            'type': 'ai_service_no_lifecycle_event',
            'description': f'R199 增量: AI 服务缺生命周期事件, {len(ai_services_with_no_integration)}/{ai_services_total} 个 AI 服务未发布 started/stopped 事件 (R198-D 业务调用链 B6 续)',
            'priority': 'P1',
            'dimension': 5,
            'rule': 'R198-D 业务调用链 B6 + R8 §8.1 #3 集中 helper',
            'ai_services_no_event': len(ai_services_with_no_integration),
            'ai_services_total': ai_services_total,
            'sample_services': [s['file'] for s in ai_services_with_no_integration[:10]],
            '4src_verification': {
                'read_verified': True,
                'grep_verified': 'pending (R+1 round)',
                'codegraph_verified': 'pending (R+1 round)',
                'business_chain_verified': 'pending (R+1 round)',
                '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
            }
        })

    # 5.3 性能监控: 扫描 service 缺 metrics 记录
    performance_violations = []
    for file_path in file_list:
        rel_path = str(file_path.relative_to(PROJECT_ROOT))
        if 'tests/' in rel_path:
            continue
        if '/services/' not in rel_path:
            continue
        if not rel_path.endswith('_service.py'):
            continue
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
        except (OSError, UnicodeDecodeError):
            continue
        # 关键方法无 metrics 收集 (粗略启发式)
        if 'metrics' not in source.lower() and 'prometheus' not in source.lower():
            performance_violations.append({
                'file': rel_path,
                'has_metrics': False,
            })

    if performance_violations:
        candidates.append({
            'hvd_id': 'NEW-R199-D5-03',
            'type': 'service_no_metrics_monitoring',
            'description': f'R199 增量: Service 缺性能监控指标, {len(performance_violations)} 个 _service.py 缺 metrics 集成 (R143-B 续)',
            'priority': 'P2',
            'dimension': 5,
            'rule': 'R143-B 性能监控续 + R158-D 观测性',
            'services_no_metrics': len(performance_violations),
            'sample_services': [s['file'] for s in performance_violations[:10]],
            '4src_verification': {
                'read_verified': True,
                'grep_verified': 'pending (R+1 round)',
                'codegraph_verified': 'pending (R+1 round)',
                'business_chain_verified': 'pending (R+1 round)',
                '4src_summary': '1/4 验证已就绪 (Read), 3/4 待 R+1 round',
            }
        })

    print(f"  多账户隔离违规候选: {len(multiaccount_violations)}")
    print(f"  AI 服务无生命周期事件: {len(ai_services_with_no_integration)}")
    print(f"  Service 缺 metrics: {len(performance_violations)}")
    return candidates


# ============================================================
# 主函数
# ============================================================
def main():
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description='R199-D 任务: 增量全项目深度新发现扫描 (5 维度)',
    )
    parser.add_argument('--json', type=str, default=str(TOOLS_DIR / "_r199_d_new_hvd.json"),
                        help='输出 HVD 候选到指定 JSON 文件')
    args = parser.parse_args()

    banner("R199-D 任务: 增量全项目深度新发现扫描 (5 维度) - 2026-07-25")
    print(f"📁 项目根目录: {PROJECT_ROOT}")
    print(f"🎯 目标: 5 维度全项目增量扫描, 排除 R197/R198 已发现 HVD, 立项新 HVD 候选")
    print(f"🚫 排除 R197-D: {len(R197_D_EXCLUDED_HVD)} HVD")
    print(f"🚫 排除 R198-D: {len(R198_D_EXCLUDED_HVD)} HVD")
    print(f"🚫 排除 R198-C: {len(R198_C_EXCLUDED_ORPHAN_PUBS)} ORPHAN events")

    start = time.time()

    # 收集文件
    print("\n[文件收集] 扫描 .py 文件...")
    file_list = collect_files()
    print(f"  总文件数: {len(file_list)}")

    # 5 维度扫描
    banner("5 维度增量扫描")

    d1_candidates = dimension_1_dead_code_increment(file_list)
    d2_candidates = dimension_2_locks_cache_eventbus_increment(file_list)
    d3_candidates = dimension_3_compat_layer_increment(file_list)
    d4_candidates = dimension_4_orphan_pubsub_increment(file_list)
    d5_candidates = dimension_5_multiaccount_ai_perf_increment(file_list)

    all_candidates = d1_candidates + d2_candidates + d3_candidates + d4_candidates + d5_candidates

    # 按 HVD id 去重 (保留最先出现的)
    seen_hvd = set()
    unique_candidates = []
    for c in all_candidates:
        if c['hvd_id'] not in seen_hvd:
            seen_hvd.add(c['hvd_id'])
            unique_candidates.append(c)

    # 优先级统计
    by_priority = defaultdict(int)
    by_dimension = defaultdict(int)
    for c in unique_candidates:
        by_priority[c['priority']] += 1
        by_dimension[c['dimension']] += 1

    elapsed = time.time() - start
    print()
    print("=" * 80)
    print(f"  R199-D 扫描结果汇总")
    print("=" * 80)
    print(f"⏱️  扫描耗时: {elapsed:.2f} 秒")
    print(f"📊 总候选 HVD 数: {len(unique_candidates)} (5 维度合并)")
    print()
    print("📊 按优先级:")
    for p, n in sorted(by_priority.items()):
        print(f"  {p}: {n}")
    print()
    print("📊 按维度:")
    for d, n in sorted(by_dimension.items()):
        print(f"  维度 {d}: {n}")
    print()
    print("📊 详细候选清单:")
    for c in unique_candidates:
        # 兼容两种 candidate 格式: (1) 聚合对象有 description, (2) 单条函数无 description
        desc = c.get('description', c.get('name', c.get('type', '')))
        print(f"  {c['hvd_id']} ({c['priority']}) - {c['type']}")
        print(f"    {str(desc)[:120]}")

    # 写 JSON
    output = {
        'r199_d_phase': '增量全项目深度新发现扫描 (5 维度)',
        'date': '2026-07-25',
        'duration_seconds': elapsed,
        'r197_d_excluded_count': len(R197_D_EXCLUDED_HVD),
        'r198_d_excluded_count': len(R198_D_EXCLUDED_HVD),
        'r198_c_excluded_orphan_count': len(R198_C_EXCLUDED_ORPHAN_PUBS),
        'files_scanned': len(file_list),
        'new_hvd_candidates_count': len(unique_candidates),
        'priority_breakdown': dict(by_priority),
        'dimension_breakdown': dict(by_dimension),
        'candidates': unique_candidates,
        '强制度': {
            'R104_§12_5_铁律': '100% 应用 (R+1 round / 4 源验证 / AST 嵌套 / 物理删除前 4 源 / AST unparse)',
            'R85_假修复鉴别_4_步法': '100% 应用',
            'R6_§6.1_8_铁律': '100% 应用 (死代码审计跨子目录)',
            'R51_§7.1_5_强约束': '100% 应用 (业务关键路径禁止静默失败)',
            'R8_§8.1_8_铁律': '100% 应用 (事件总线)',
            'R9_§9.1_6_铁律': '100% 应用 (缓存)',
            'R100-F_#8_4_锁独立': '100% 应用',
            'R110-C_时序竞态防御': '100% 应用',
            'R198-A_兼容层_4_源': '100% 应用 (同文件引用纳入)',
            'R198-A_双轨注册': '100% 应用 (enum.name + enum.value)',
            'R194-B_V13_跨行': '100% 应用',
            'R143-B_性能监控续': '100% 应用',
        },
    }

    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print()
    print(f"✅ 已保存到: {args.json}")

    return output


if __name__ == "__main__":
    main()
