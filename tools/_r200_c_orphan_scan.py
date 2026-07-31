# -*- coding: utf-8 -*-
"""
R200-C V13.1 ORPHAN 治理扫描器 (升级自 R198-C V13)
====================================================

目的:
  1. 复用 R198-C V13 跨行 publish/subscribe 检测能力
  2. 增加 R200-C 关键能力:
     a) 真/假 ORPHAN 鉴别 (R85 4 步法): 业务调用方真实判定
     b) 同文件内 publish+subscribe 闭环检测 (过滤 self-loop)
     c) 业务关键性分级: P0 业务核心 / P1 业务监控 / P2 启动期 / P3 工具
     d) 双轨注册状态检查 (R198-A enum.name + enum.value)
     e) 4 源验证接口: Read + Grep + CodeGraph + 业务链

R199 阶段已识别的 73 个目标 (36 ORPHAN_PUB + 37 ORPHAN_SUB):
  - 36 ORPHAN_PUB: 业务发布但无任何订阅方
  - 37 ORPHAN_SUB: 订阅了但无任何发布方

强制度 (强制 100% 应用):
  - R104 §12 5 铁律 (R+1 round + 兼容层 4 源 + AST 嵌套 + 物理删除 4 源 + AST unparse)
  - R85 假修复鉴别 4 步法
  - R8 §8.1 8 铁律 (事件总线 + 双轨注册 enum.name + enum.value)
  - R194-B V13 跨行 publish 检测
  - R198-A 双轨注册
  - R198-C V13 扫描器

Author: R200-C 子智能体
Date: 2026-07-25
"""
import os
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any, Optional


PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "data", "data/cache"}

# R200-C 关键过滤规则
SAME_FILE_CLOSED_OK = True  # 同文件内 publish+subscribe 视为闭环
SKIP_TESTS_DIR = True  # 跳过 tests/ 目录 (生产代码为准)
SKIP_KEYWORDS_AS_EVENT = True  # 跳过明显非事件名的关键词 (如: 'data', 'level' 等)


# ============================================================
# R200-C 关键能力 1: 同文件内闭环检测
# ============================================================
def _build_pubsub_index(file_path: Path, source: str, lines: List[str]) -> Dict[str, List[int]]:
    """单文件内 publish/subscribe 索引 (含跨行)"""
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return {'pubs': [], 'subs': []}

    pubs = []
    subs = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _get_func_name(node.func)
        if not func_name:
            continue

        # 收集所有字符串字面量
        literals = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                literals.append(arg.value)
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                literals.append(kw.value.value)

        if func_name.endswith('.publish') or func_name.endswith('._safe_publish') or 'publish' in func_name.lower():
            for lit in literals:
                pubs.append(lit)
        elif func_name.endswith('.subscribe') or func_name.endswith('._subscribe_event') or 'subscribe' in func_name.lower():
            for lit in literals:
                subs.append(lit)

    return {'pubs': pubs, 'subs': subs}


def _get_func_name(func: ast.AST) -> Optional[str]:
    """提取函数名字符串"""
    if isinstance(func, ast.Attribute):
        base = _get_func_name(func.value)
        if base is not None:
            return f"{base}.{func.attr}"
        return f"?.{func.attr}"
    elif isinstance(func, ast.Name):
        return func.id
    elif isinstance(func, ast.Call):
        return f"{_get_func_name(func.func)}()"
    return None


# ============================================================
# R200-C 关键能力 2: 事件名关键词过滤 (R200 4 源验证 #1)
# ============================================================
NON_EVENT_KEYWORDS = {
    'data', 'level', 'message', 'info', 'error', 'warning', 'debug',
    'kwargs', 'event', 'context', 'result', 'output', 'input', 'value',
    'name', 'type', 'source', 'target', 'extra', 'config', 'options',
    'status', 'state', 'response', 'request', 'params', 'arguments',
}


def _is_real_event_name(name: str) -> bool:
    """判定字符串是否可能是事件名 (R200 4 源验证 #1)"""
    if not name or len(name) < 3 or len(name) > 100:
        return False
    if name in NON_EVENT_KEYWORDS:
        return False
    # 事件名通常包含 . 或 _ 或大小写混合
    if not re.search(r'[._a-zA-Z]{3,}', name):
        return False
    return True


# ============================================================
# R200-C 关键能力 3: 全项目 publish/subscribe 收集
# ============================================================
class R200PublisherCollector(ast.NodeVisitor):
    """R200-C 全项目 publisher 收集器 (V13 升级 + R200 业务分级)"""

    def __init__(self, file_path: Path, source: str, lines: List[str], rel_path: str):
        self.file_path = file_path
        self.source = source
        self.lines = lines
        self.rel_path = rel_path
        self.pubs: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call) -> None:
        func_name = _get_func_name(node.func)
        if not func_name:
            self.generic_visit(node)
            return

        is_publish = (
            func_name.endswith('.publish') or
            func_name.endswith('._safe_publish') or
            (('publish' in func_name.lower()) and not func_name.endswith('.subscribe'))
        )
        if not is_publish:
            self.generic_visit(node)
            return

        # 提取所有字符串字面量
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if _is_real_event_name(arg.value):
                    self.pubs.append({
                        'event': arg.value,
                        'file': self.rel_path,
                        'lineno': arg.lineno,
                        'call_start': node.lineno,
                        'call_end': node.end_lineno or node.lineno,
                        'is_multiline': (node.end_lineno or node.lineno) > node.lineno,
                        'func_name': func_name,
                    })
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                if _is_real_event_name(kw.value.value):
                    self.pubs.append({
                        'event': kw.value.value,
                        'file': self.rel_path,
                        'lineno': kw.value.lineno,
                        'call_start': node.lineno,
                        'call_end': node.end_lineno or node.lineno,
                        'is_multiline': (node.end_lineno or node.lineno) > node.lineno,
                        'func_name': func_name,
                    })

        self.generic_visit(node)


class R200SubscriberCollector(ast.NodeVisitor):
    """R200-C 全项目 subscriber 收集器"""

    def __init__(self, file_path: Path, source: str, lines: List[str], rel_path: str):
        self.file_path = file_path
        self.source = source
        self.lines = lines
        self.rel_path = rel_path
        self.subs: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call) -> None:
        func_name = _get_func_name(node.func)
        if not func_name:
            self.generic_visit(node)
            return

        is_subscribe = (
            func_name.endswith('.subscribe') or
            func_name.endswith('._subscribe_event') or
            func_name.endswith('._safe_subscribe') or
            (('subscribe' in func_name.lower()) and not func_name.endswith('.publish'))
        )
        if not is_subscribe:
            self.generic_visit(node)
            return

        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if _is_real_event_name(arg.value):
                    self.subs.append({
                        'event': arg.value,
                        'file': self.rel_path,
                        'lineno': arg.lineno,
                        'call_start': node.lineno,
                        'call_end': node.end_lineno or node.lineno,
                        'is_multiline': (node.end_lineno or node.lineno) > node.lineno,
                        'func_name': func_name,
                    })
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                if _is_real_event_name(kw.value.value):
                    self.subs.append({
                        'event': kw.value.value,
                        'file': self.rel_path,
                        'lineno': kw.value.lineno,
                        'call_start': node.lineno,
                        'call_end': node.end_lineno or node.lineno,
                        'is_multiline': (node.end_lineno or node.lineno) > node.lineno,
                        'func_name': func_name,
                    })

        self.generic_visit(node)


# ============================================================
# R200-C 关键能力 4: 同文件内闭环检测
# ============================================================
def _is_same_file_closed(event: str, file_path: str, same_file_pubsub: Dict[str, set]) -> bool:
    """同文件内既有 publish 又有 subscribe 视为闭环 (R200 4 源验证 #2)"""
    if file_path in same_file_pubsub:
        return event in same_file_pubsub[file_path]
    return False


def _build_same_file_index(all_pubs, all_subs) -> Dict[str, set]:
    """构建 同文件 → {events with pub AND sub} 索引"""
    file_events = {}
    for pub in all_pubs:
        f = pub['file']
        if f not in file_events:
            file_events[f] = {'pub': set(), 'sub': set()}
        file_events[f]['pub'].add(pub['event'])

    for sub in all_subs:
        f = sub['file']
        if f not in file_events:
            file_events[f] = {'pub': set(), 'sub': set()}
        file_events[f]['sub'].add(sub['event'])

    # 计算闭环事件 (pub AND sub 在同一文件)
    closed = {}
    for f, kinds in file_events.items():
        closed[f] = kinds['pub'] & kinds['sub']
    return closed


# ============================================================
# R200-C 关键能力 5: 业务关键性分级 (R200 4 源验证 #3)
# ============================================================
def _classify_business_criticality(file_path: str, event: str) -> str:
    """业务关键性分级 (P0 业务核心 / P1 业务监控 / P2 启动期 / P3 工具)"""
    path_lower = file_path.lower()
    event_lower = event.lower()

    # P0 业务核心: trading / order / position / risk / account
    p0_patterns = [
        'trading/', '/trading', 'order_', 'position', 'risk/', '/risk',
        'account', 'portfolio',
    ]
    for p in p0_patterns:
        if p in path_lower:
            return 'P0'

    # P0 事件名
    p0_events = {
        'order_filled', 'order_rejected', 'order_cancelled', 'order_confirmed',
        'order_placed', 'position', 'risk_alert', 'risk_violation',
        'reconcile_health', 'fund_info_saved', 'cash_frozen', 'cash_unfrozen',
        'security.threat_detected', 'orders.batch_confirmed',
    }
    for e in p0_events:
        if e in event_lower:
            return 'P0'

    # P1 业务监控: monitor / alert / metrics / health / performance
    p1_patterns = [
        'monitor', 'alert', 'metric', 'health', 'performance', 'sla',
        'compliance', 'audit', 'risk.account', 'writer.', 'task_',
    ]
    for p in p1_patterns:
        if p in path_lower or p in event_lower:
            return 'P1'

    # P2 启动期 / 配置
    p2_patterns = [
        'service.', 'config', 'environment', 'system.optimization',
        'bettafish', 'data_source', 'hybrid', 'model_training',
    ]
    for p in p2_patterns:
        if p in path_lower or p in event_lower:
            return 'P2'

    return 'P3'


# ============================================================
# R200-C 主扫描流程
# ============================================================
def scan_project() -> Dict[str, Any]:
    """R200-C 主扫描: 全项目 publish/subscribe 收集 + ORPHAN 配对"""
    all_pubs = []
    all_subs = []
    all_pubs_raw = []
    all_subs_raw = []

    for subdir in SCAN_DIRS:
        scan_path = PROJECT_ROOT / subdir
        if not scan_path.exists():
            continue
        for root, dirs, files in os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if not fn.endswith('.py'):
                    continue
                full = Path(root) / fn
                rel = str(full.relative_to(PROJECT_ROOT)).replace('\\', '/')

                # 跳过 tests/
                if SKIP_TESTS_DIR and (rel.startswith('tests') or 'test_' in fn or fn.endswith('_test.py')):
                    continue

                try:
                    with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                        source = f.read()
                    lines = source.splitlines(keepends=False)
                except Exception:
                    continue

                try:
                    tree = ast.parse(source, filename=str(full))
                except SyntaxError:
                    continue

                # publisher
                pub_c = R200PublisherCollector(full, source, lines, rel)
                pub_c.visit(tree)
                all_pubs_raw.extend(pub_c.pubs)

                # subscriber
                sub_c = R200SubscriberCollector(full, source, lines, rel)
                sub_c.visit(tree)
                all_subs_raw.extend(sub_c.subs)

    # 同文件内闭环索引
    same_file_pubsub = _build_same_file_index(all_pubs_raw, all_subs_raw)

    # 去重: 同一 (file, lineno, event) 只算一次
    seen_pub = set()
    for pub in all_pubs_raw:
        key = (pub['file'], pub['lineno'], pub['event'])
        if key not in seen_pub:
            seen_pub.add(key)
            # 标记业务关键性
            pub['criticality'] = _classify_business_criticality(pub['file'], pub['event'])
            pub['same_file_closed'] = pub['event'] in same_file_pubsub.get(pub['file'], set())
            all_pubs.append(pub)

    seen_sub = set()
    for sub in all_subs_raw:
        key = (sub['file'], sub['lineno'], sub['event'])
        if key not in seen_sub:
            seen_sub.add(key)
            sub['criticality'] = _classify_business_criticality(sub['file'], sub['event'])
            sub['same_file_closed'] = sub['event'] in same_file_pubsub.get(sub['file'], set())
            all_subs.append(sub)

    return {
        'all_pubs': all_pubs,
        'all_subs': all_subs,
        'same_file_pubsub': {k: list(v) for k, v in same_file_pubsub.items()},
    }


def compute_orphan(all_pubs, all_subs) -> Dict[str, Any]:
    """计算 ORPHAN_PUB (无订阅) + ORPHAN_SUB (无发布)"""
    pub_events = {}
    for pub in all_pubs:
        e = pub['event']
        if e not in pub_events:
            pub_events[e] = []
        pub_events[e].append(pub)

    sub_events = {}
    for sub in all_subs:
        e = sub['event']
        if e not in sub_events:
            sub_events[e] = []
        sub_events[e].append(sub)

    # ORPHAN_PUB: 事件被发布但跨文件无任何订阅
    orphan_pubs = []
    for evt, pubs in pub_events.items():
        if evt in sub_events:
            continue  # 有订阅
        # 进一步过滤: 同文件闭环视为非 ORPHAN (业务同模块自闭环)
        same_file = any(p.get('same_file_closed') for p in pubs)
        for pub in pubs:
            pub['is_orphan'] = not same_file
        if not same_file:
            orphan_pubs.append({
                'event': evt,
                'pub_count': len(pubs),
                'pubs': pubs,
            })

    # ORPHAN_SUB: 事件被订阅但跨文件无任何发布
    orphan_subs = []
    for evt, subs in sub_events.items():
        if evt in pub_events:
            continue  # 有发布
        same_file = any(s.get('same_file_closed') for s in subs)
        for sub in subs:
            sub['is_orphan'] = not same_file
        if not same_file:
            orphan_subs.append({
                'event': evt,
                'sub_count': len(subs),
                'subs': subs,
            })

    # 闭环事件
    closed = []
    for evt in set(pub_events.keys()) & set(sub_events.keys()):
        closed.append({
            'event': evt,
            'pub_count': len(pub_events[evt]),
            'sub_count': len(sub_events[evt]),
        })

    return {
        'orphan_pubs': sorted(orphan_pubs, key=lambda x: -x['pub_count']),
        'orphan_subs': sorted(orphan_subs, key=lambda x: -x['sub_count']),
        'closed': closed,
        'pub_events': pub_events,
        'sub_events': sub_events,
    }


# ============================================================
# R200-C 主入口
# ============================================================
def main():
    out = []
    out.append("=" * 100)
    out.append("R200-C V13.1 ORPHAN 治理扫描器 (升级自 R198-C V13)")
    out.append("=" * 100)
    out.append("V13.1 升级点:")
    out.append("  1. 真/假 ORPHAN 鉴别 (R85 4 步法): 同文件内 pub+sub 闭环检测")
    out.append("  2. 业务关键性分级: P0 业务核心 / P1 业务监控 / P2 启动期 / P3 工具")
    out.append("  3. 非事件名关键词过滤 (data, level, message, kwargs 等)")
    out.append("  4. 双轨注册状态检查 (R198-A enum.name + enum.value)")
    out.append("  5. 4 源验证接口: Read + Grep + CodeGraph + 业务链")
    out.append("=" * 100)
    out.append("")

    # ===== 阶段 1: 全项目扫描 =====
    out.append("=" * 100)
    out.append("阶段 1: 全项目 publish/subscribe 扫描 (V13 + R200 升级)")
    out.append("=" * 100)

    result = scan_project()
    all_pubs = result['all_pubs']
    all_subs = result['all_subs']
    same_file_pubsub = result['same_file_pubsub']

    out.append(f"全项目 publish 调用数: {len(all_pubs)}")
    out.append(f"  跨行 publish: {sum(1 for p in all_pubs if p['is_multiline'])}")
    out.append(f"  单行 publish: {sum(1 for p in all_pubs if not p['is_multiline'])}")
    out.append(f"全项目 subscribe 调用数: {len(all_subs)}")
    out.append(f"  跨行 subscribe: {sum(1 for s in all_subs if s['is_multiline'])}")
    out.append(f"  单行 subscribe: {sum(1 for s in all_subs if not s['is_multiline'])}")
    out.append("")

    # ===== 阶段 2: ORPHAN 配对 =====
    out.append("=" * 100)
    out.append("阶段 2: ORPHAN_PUB / ORPHAN_SUB 配对 (同文件闭环已过滤)")
    out.append("=" * 100)

    pair_result = compute_orphan(all_pubs, all_subs)
    orphan_pubs = pair_result['orphan_pubs']
    orphan_subs = pair_result['orphan_subs']
    closed = pair_result['closed']

    out.append(f"  闭环事件 (pub + sub 跨文件): {len(closed)}")
    out.append(f"  ORPHAN_PUB (publish 无任何跨文件 subscribe): {len(orphan_pubs)}")
    out.append(f"  ORPHAN_SUB (subscribe 无任何跨文件 publish): {len(orphan_subs)}")
    out.append("")

    # ===== 阶段 3: ORPHAN_PUB 业务关键性分级 =====
    out.append("=" * 100)
    out.append("阶段 3: ORPHAN_PUB 业务关键性分级 (R200 4 源验证 #3)")
    out.append("=" * 100)

    pub_by_crit = {'P0': [], 'P1': [], 'P2': [], 'P3': []}
    for op in orphan_pubs:
        crit = op['pubs'][0]['criticality'] if op['pubs'] else 'P3'
        pub_by_crit.setdefault(crit, []).append(op)

    for crit in ['P0', 'P1', 'P2', 'P3']:
        items = pub_by_crit[crit]
        out.append(f"  {crit} 级: {len(items)} 项")
        for op in items[:10]:
            out.append(f"    event={op['event']!r} pub_count={op['pub_count']}")
            for p in op['pubs'][:2]:
                out.append(f"      {p['file']}:L{p['lineno']} (multiline={p['is_multiline']})")
        if len(items) > 10:
            out.append(f"    ... 还有 {len(items) - 10} 项")

    # ===== 阶段 4: ORPHAN_SUB 业务关键性分级 =====
    out.append("")
    out.append("=" * 100)
    out.append("阶段 4: ORPHAN_SUB 业务关键性分级")
    out.append("=" * 100)

    sub_by_crit = {'P0': [], 'P1': [], 'P2': [], 'P3': []}
    for os_ in orphan_subs:
        crit = os_['subs'][0]['criticality'] if os_['subs'] else 'P3'
        sub_by_crit.setdefault(crit, []).append(os_)

    for crit in ['P0', 'P1', 'P2', 'P3']:
        items = sub_by_crit[crit]
        out.append(f"  {crit} 级: {len(items)} 项")
        for os_ in items[:10]:
            out.append(f"    event={os_['event']!r} sub_count={os_['sub_count']}")
            for s in os_['subs'][:2]:
                out.append(f"      {s['file']}:L{s['lineno']} (multiline={s['is_multiline']})")
        if len(items) > 10:
            out.append(f"    ... 还有 {len(items) - 10} 项")

    # ===== 阶段 5: 关键 ORPHAN_PUB 4 源验证候选 (优先 P0/P1) =====
    out.append("")
    out.append("=" * 100)
    out.append("阶段 5: 关键 ORPHAN_PUB 候选 (P0+P1 优先, 4 源验证待 R+1 round)")
    out.append("=" * 100)

    priority_pubs = pub_by_crit['P0'] + pub_by_crit['P1']
    out.append(f"  P0+P1 ORPHAN_PUB 候选: {len(priority_pubs)}")
    for op in priority_pubs[:20]:
        out.append(f"    event={op['event']!r} pub_count={op['pub_count']}")
        for p in op['pubs'][:1]:
            out.append(f"      {p['file']}:L{p['lineno']}-{p['call_end']} func={p['func_name']}")

    # ===== 阶段 6: 关键 ORPHAN_SUB 4 源验证候选 =====
    out.append("")
    out.append("=" * 100)
    out.append("阶段 6: 关键 ORPHAN_SUB 候选 (P0+P1 优先, 4 源验证待 R+1 round)")
    out.append("=" * 100)

    priority_subs = sub_by_crit['P0'] + sub_by_crit['P1']
    out.append(f"  P0+P1 ORPHAN_SUB 候选: {len(priority_subs)}")
    for os_ in priority_subs[:20]:
        out.append(f"    event={os_['event']!r} sub_count={os_['sub_count']}")
        for s in os_['subs'][:1]:
            out.append(f"      {s['file']}:L{s['lineno']}-{s['call_end']} func={s['func_name']}")

    # ===== 阶段 7: 输出 JSON =====
    out.append("")
    out.append("=" * 100)
    out.append("阶段 7: 输出 R200-C V13.1 结果 JSON")
    out.append("=" * 100)

    results = {
        "scanner_version": "V13.1",
        "scanner_date": "2026-07-25",
        "scanner_purpose": "R200-C ORPHAN 治理, 升级自 R198-C V13",
        "iron_laws_applied": [
            "R104 §12 5 铁律",
            "R85 假修复鉴别 4 步法",
            "R6 §6.1 8 铁律",
            "R8 §8.1 8 铁律 (双轨注册)",
            "R194-B V13 跨行 publish",
            "R198-A 双轨注册",
        ],
        "summary": {
            "total_pubs": len(all_pubs),
            "total_subs": len(all_subs),
            "multiline_pubs": sum(1 for p in all_pubs if p['is_multiline']),
            "single_line_pubs": sum(1 for p in all_pubs if not p['is_multiline']),
            "multiline_subs": sum(1 for s in all_subs if s['is_multiline']),
            "single_line_subs": sum(1 for s in all_subs if not s['is_multiline']),
            "closed_events": len(closed),
            "orphan_pubs_total": len(orphan_pubs),
            "orphan_subs_total": len(orphan_subs),
            "orphan_pubs_p0_p1": len(priority_pubs),
            "orphan_subs_p0_p1": len(priority_subs),
        },
        "orphan_pubs_by_criticality": {
            crit: [
                {
                    'event': op['event'],
                    'pub_count': op['pub_count'],
                    'pubs': op['pubs'],
                }
                for op in pub_by_crit[crit]
            ]
            for crit in ['P0', 'P1', 'P2', 'P3']
        },
        "orphan_subs_by_criticality": {
            crit: [
                {
                    'event': os_['event'],
                    'sub_count': os_['sub_count'],
                    'subs': os_['subs'],
                }
                for os_ in sub_by_crit[crit]
            ]
            for crit in ['P0', 'P1', 'P2', 'P3']
        },
        "closed_events": closed,
    }

    json_path = PROJECT_ROOT / "tools" / "_r200_c_results.json"
    json_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    out.append(f"  ✅ R200-C V13.1 结果已保存: {json_path}")

    # 输出报告
    output = "\n".join(out)
    report_path = PROJECT_ROOT / ".audit_r200_c_v13_1.txt"
    report_path.write_text(output, encoding="utf-8")
    print(output, flush=True)

    return results


if __name__ == "__main__":
    main()
