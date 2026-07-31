# -*- coding: utf-8 -*-
"""
R198-C V13 跨行 publish 检测扫描器
==================================

目的: 升级 V12 扫描器, 识别**跨行** publish 调用 (R195-B 教训:
      `core/trading/account_manager.py:1981-1986` 跨 5 行 publish
      `reconcile_health_alert` → V12 扫描器漏检 → R194-B 报告 P0
      误删, R195-B 4 源验证发现挽救 P0 业务核心)

V12 盲区 (R195-B 100% 命中教训):
  V12 仅识别单行模式:
    1. `bus.publish('event_name', ...)` 单行
    2. `bus.publish(\n    'event_name',\n    data=...\n)` 跨行: 字符串字面量在 L N+1, V12 漏检
    3. `bus.publish(\n    EventType.EVENT_NAME,\n)` 跨行枚举: V12 漏检
    4. `bus.publish("event_name" \\\n  " continued")` 反斜杠续行: V12 漏检
  V12 漏检:
    A. 跨行字符串字面量 (L 1981 'bus.publish('  L 1982 'event_name')
    B. 跨行 keyword args (`data=foo,\n  level=bar`)
    C. 反斜杠续行 (line continuation \)
    D. 多行字符串拼接 (隐式 / 显式)
    E. 嵌套调用跨行 (`bus.publish(handler(event),\n  'fallback')`)

V13 升级 (5 大新模式):
  1. AST NodeVisitor 递归扫描所有 Call 节点
  2. 节点位置: ast.Call.lineno (开始) + ast.Call.end_lineno (结束)
  3. 范围查询: 提取 Call 节点内所有 Constant (str) 节点
  4. 跨行判定: if any(constant.lineno != call.lineno) → 跨行
  5. 物理行连续性验证: lines[call.lineno-1:call.end_lineno] 物理连通

Author: R198-C 子智能体
Date: 2026-07-25
强制度:
  - R104 §12 5 铁律
  - R85 假修复鉴别 4 步法
  - R6 §6.1 8 铁律
  - R8 §8.1 8 铁律 (事件总线)
  - R194-B V12 模式 + V13 升级 (跨行 publish 检测)
  - R195-B reconcile_health_alert 案例补全
"""
import os
import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any, Optional


PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "data", "data/cache"}

# V13 新增: 跨行 publish 检测模式
# 已知跨行 publish 模式 (R195-B reconcile_health_alert 案例):
KNOWN_MULTILINE_PUB_CASES = {
    "reconcile_health_alert": {
        "file": "core/trading/account_manager.py",
        "lines": "1981-1986",
        "method": "_emit_reconcile_health_alert",
        "context": "持仓对账健康告警, P0 业务核心, R195-B 挽救"
    },
}


# ============================================================
# V12 兼容: 单行 publish 检测 (保留)
# ============================================================
def find_direct_publish_v12(file_path: Path, evt: str, lines: List[str]) -> List[Tuple[int, str, str]]:
    """V12 直接发布检测 (单行, 兼容 R194-B)"""
    pubs = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#') and 'publish' not in line:
            continue

        # 模式 1: 字符串字面量 + 直接 .publish() (排除 _safe_publish wrapper, 模式 4 处理)
        if (f"'{evt}'" in line or f'"{evt}"' in line or f"EventType.{evt}" in line):
            if '.publish(' in line and '_safe_publish(' not in line:
                pubs.append((i, 'v12_single_line', line.rstrip()[:200]))

        if f"publish({evt}(" in line or f"publish({evt}.)" in line:
            pubs.append((i, 'v12_dataclass', line.rstrip()[:200]))

        helper = f"publish_{evt}"
        if helper + '(' in line and not line.strip().startswith('def '):
            pubs.append((i, 'v12_helper', line.rstrip()[:200]))

        if f'_safe_publish("{evt}"' in line or f"_safe_publish('{evt}'" in line:
            pubs.append((i, 'v12_safe_helper', line.rstrip()[:200]))

    return pubs


def find_direct_subscribe_v12(file_path: Path, evt: str, lines: List[str]) -> List[Tuple[int, str, str]]:
    """V12 直接订阅检测 (单行, 兼容 R194-B)"""
    subs = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#') and 'subscribe' not in line:
            continue

        if (f"'{evt}'" in line or f'"{evt}"' in line):
            if '.subscribe(' in line or '_subscribe_event(' in line:
                subs.append((i, 'v12_single_line', line.rstrip()[:200]))

        if f"subscribe({evt}(" in line or f"subscribe({evt}.)" in line:
            subs.append((i, 'v12_dataclass', line.rstrip()[:200]))

    return subs


# ============================================================
# V13 新增: AST 跨行 publish 检测
# ============================================================
class MultilinePublishDetector(ast.NodeVisitor):
    """V13 跨行 publish 检测器

    算法:
    1. AST 遍历所有 Call 节点
    2. 判定是否为 publish 调用: func.attr in ('publish', '_safe_publish')
       或 func.id 含 'publish' (helper)
    3. 收集 Call 内所有 Constant (str) 节点
    4. 跨行判定: call.end_lineno > call.lineno AND 任意 const.lineno != call.lineno
    5. 物理行连续性验证: lines[call.lineno-1:call.end_lineno] 物理连通
    """

    def __init__(self, file_path: Path, source: str, lines: List[str]):
        self.file_path = file_path
        self.source = source
        self.lines = lines
        self.multiline_pubs: List[Dict[str, Any]] = []
        self.all_pubs: List[Dict[str, Any]] = []  # 包含单行 + 跨行

    def visit_Call(self, node: ast.Call) -> None:
        """访问每个 Call 节点, 判定是否为 publish 调用"""
        func_name = self._get_func_name(node.func)
        if not func_name:
            # 继续递归子节点
            self.generic_visit(node)
            return

        # 判定 publish 调用
        is_publish = (
            func_name.endswith('.publish') or
            func_name.endswith('._safe_publish') or
            'publish' in func_name.lower()
        )
        if not is_publish:
            self.generic_visit(node)
            return

        # 收集所有字符串字面量 (事件名候选)
        string_literals = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                string_literals.append({
                    'value': arg.value,
                    'lineno': arg.lineno,
                    'col_offset': arg.col_offset,
                })
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                string_literals.append({
                    'value': kw.value.value,
                    'lineno': kw.value.lineno,
                    'col_offset': kw.value.col_offset,
                    'kw': kw.arg,
                })

        # 跨行判定
        call_start = node.lineno
        call_end = node.end_lineno or node.lineno
        is_multiline = (call_end > call_start)

        # 提取物理行
        if call_start <= len(self.lines) and call_end <= len(self.lines):
            physical_lines = self.lines[call_start - 1:call_end]
            physical_text = "\n".join(physical_lines)
        else:
            physical_text = ""

        # 物理连通性: 反斜杠续行
        has_continuation = any('\\' in line for line in physical_lines[:-1])

        record = {
            'file': str(self.file_path),
            'call_start': call_start,
            'call_end': call_end,
            'func_name': func_name,
            'is_multiline': is_multiline,
            'has_continuation': has_continuation,
            'string_literals': string_literals,
            'physical_text': physical_text[:500],  # 限长
        }

        self.all_pubs.append(record)

        if is_multiline or has_continuation:
            self.multiline_pubs.append(record)

        # 继续递归 (处理嵌套调用)
        self.generic_visit(node)

    def _get_func_name(self, func: ast.AST) -> Optional[str]:
        """提取函数名字符串"""
        if isinstance(func, ast.Attribute):
            # obj.method 形式
            base = self._get_func_name(func.value)
            if base is not None:
                return f"{base}.{func.attr}"
            return f"?.{func.attr}"
        elif isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Call):
            # 链式调用: foo()()
            return f"{self._get_func_name(func.func)}()"
        return None


# ============================================================
# V13 跨行 subscribe 检测 (与 publish 对称)
# ============================================================
class MultilineSubscribeDetector(ast.NodeVisitor):
    """V13 跨行 subscribe 检测器 (与 publish 对称)"""

    def __init__(self, file_path: Path, source: str, lines: List[str]):
        self.file_path = file_path
        self.source = source
        self.lines = lines
        self.multiline_subs: List[Dict[str, Any]] = []
        self.all_subs: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call) -> None:
        func_name = self._get_func_name(node.func)
        if not func_name:
            self.generic_visit(node)
            return

        is_subscribe = (
            func_name.endswith('.subscribe') or
            func_name.endswith('._subscribe_event') or
            'subscribe' in func_name.lower()
        )
        if not is_subscribe:
            self.generic_visit(node)
            return

        string_literals = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                string_literals.append({
                    'value': arg.value,
                    'lineno': arg.lineno,
                })
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                string_literals.append({
                    'value': kw.value.value,
                    'lineno': kw.value.lineno,
                })

        call_start = node.lineno
        call_end = node.end_lineno or node.lineno
        is_multiline = (call_end > call_start)

        if call_start <= len(self.lines) and call_end <= len(self.lines):
            physical_lines = self.lines[call_start - 1:call_end]
            physical_text = "\n".join(physical_lines)
        else:
            physical_text = ""

        has_continuation = any('\\' in line for line in physical_lines[:-1])

        record = {
            'file': str(self.file_path),
            'call_start': call_start,
            'call_end': call_end,
            'func_name': func_name,
            'is_multiline': is_multiline,
            'has_continuation': has_continuation,
            'string_literals': string_literals,
            'physical_text': physical_text[:500],
        }

        self.all_subs.append(record)

        if is_multiline or has_continuation:
            self.multiline_subs.append(record)

        self.generic_visit(node)

    def _get_func_name(self, func: ast.AST) -> Optional[str]:
        if isinstance(func, ast.Attribute):
            base = self._get_func_name(func.value)
            if base is not None:
                return f"{base}.{func.attr}"
            return f"?.{func.attr}"
        elif isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Call):
            return f"{self._get_func_name(func.func)}()"
        return None


# ============================================================
# V13 完整事件扫描
# ============================================================
def scan_event_v13(evt: str) -> Dict[str, Any]:
    """V13 完整扫描单事件: V12 单行 + V13 跨行 + 集中式订阅"""
    pub_v12_total = 0
    pub_v13_multiline = []
    sub_v12_total = 0
    sub_v13_multiline = []

    pub_prods = []
    sub_prods = []

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
                rel = str(full.relative_to(PROJECT_ROOT))

                try:
                    with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                        source = f.read()
                    lines = source.splitlines(keepends=False)
                except Exception:
                    continue

                # V12 单行 publish/subscribe (排除 tests/, 与 V13 一致)
                if not rel.startswith("tests") and "test_" not in fn and not fn.endswith("_test.py"):
                    pubs_v12 = find_direct_publish_v12(full, evt, lines)
                    subs_v12 = find_direct_subscribe_v12(full, evt, lines)
                    pub_v12_total += len(pubs_v12)
                    sub_v12_total += len(subs_v12)
                    for ln, kind, s in pubs_v12:
                        pub_prods.append((rel, ln, kind, s))
                    for ln, kind, s in subs_v12:
                        sub_prods.append((rel, ln, kind, s))

                # V13 跨行 AST 检测
                try:
                    tree = ast.parse(source, filename=str(full))
                except SyntaxError:
                    continue

                pub_detector = MultilinePublishDetector(full, source, lines)
                pub_detector.visit(tree)
                sub_detector = MultilineSubscribeDetector(full, source, lines)
                sub_detector.visit(tree)

                for pub in pub_detector.multiline_pubs:
                    # 事件名匹配
                    matched = any(
                        lit['value'] == evt
                        for lit in pub['string_literals']
                    )
                    if matched and not rel.startswith("tests"):
                        pub_v13_multiline.append({
                            'file': rel,
                            'lines': f"{pub['call_start']}-{pub['call_end']}",
                            'func_name': pub['func_name'],
                            'has_continuation': pub['has_continuation'],
                            'physical_text': pub['physical_text'],
                        })

                for sub in sub_detector.multiline_subs:
                    matched = any(
                        lit['value'] == evt
                        for lit in sub['string_literals']
                    )
                    if matched and not rel.startswith("tests"):
                        sub_v13_multiline.append({
                            'file': rel,
                            'lines': f"{sub['call_start']}-{sub['call_end']}",
                            'func_name': sub['func_name'],
                            'has_continuation': sub['has_continuation'],
                            'physical_text': sub['physical_text'],
                        })

    return {
        "evt": evt,
        "pub_v12_total": pub_v12_total,
        "sub_v12_total": sub_v12_total,
        "pub_v13_multiline": pub_v13_multiline,
        "sub_v13_multiline": sub_v13_multiline,
        "pub_prods": pub_prods,
        "sub_prods": sub_prods,
    }


# ============================================================
# V13 全项目 publish 扫描 (不指定事件)
# ============================================================
def scan_all_publishes_v13() -> List[Dict[str, Any]]:
    """V13 扫描全项目所有 publish 调用 (含单行 + 跨行)

    Returns:
        List of dict: {file, call_start, call_end, func_name, is_multiline,
                       has_continuation, event_name, event_lineno}
    """
    all_pubs = []

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
                rel = str(full.relative_to(PROJECT_ROOT))

                # 跳过测试
                if rel.startswith("tests") or "test_" in fn or fn.endswith("_test.py"):
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

                detector = MultilinePublishDetector(full, source, lines)
                detector.visit(tree)

                for pub in detector.all_pubs:
                    # 提取事件名 (第一个字符串字面量)
                    event_name = None
                    event_lineno = None
                    for lit in pub['string_literals']:
                        if 'event' not in lit.get('kw', '').lower() if lit.get('kw') else True:
                            event_name = lit['value']
                            event_lineno = lit['lineno']
                            break

                    all_pubs.append({
                        'file': rel,
                        'call_start': pub['call_start'],
                        'call_end': pub['call_end'],
                        'func_name': pub['func_name'],
                        'is_multiline': pub['is_multiline'],
                        'has_continuation': pub['has_continuation'],
                        'event_name': event_name,
                        'event_lineno': event_lineno,
                    })

    return all_pubs


def scan_all_subscribes_v13() -> List[Dict[str, Any]]:
    """V13 扫描全项目所有 subscribe 调用 (含单行 + 跨行)"""
    all_subs = []

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
                rel = str(full.relative_to(PROJECT_ROOT))

                if rel.startswith("tests") or "test_" in fn or fn.endswith("_test.py"):
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

                detector = MultilineSubscribeDetector(full, source, lines)
                detector.visit(tree)

                for sub in detector.all_subs:
                    event_name = None
                    event_lineno = None
                    for lit in sub['string_literals']:
                        if not lit.get('kw') or lit.get('kw') not in ('data', 'message', 'level', 'event_type'):
                            event_name = lit['value']
                            event_lineno = lit['lineno']
                            break

                    all_subs.append({
                        'file': rel,
                        'call_start': sub['call_start'],
                        'call_end': sub['call_end'],
                        'func_name': sub['func_name'],
                        'is_multiline': sub['is_multiline'],
                        'has_continuation': sub['has_continuation'],
                        'event_name': event_name,
                        'event_lineno': event_lineno,
                    })

    return all_subs


# ============================================================
# ORPHAN 配对 (R195-B 教训)
# ============================================================
def compute_orphan_pairs(all_pubs, all_subs):
    """计算 ORPHAN_PUB (publish 无 subscribe) + ORPHAN_SUB (subscribe 无 publish)"""
    pub_events = {}
    for pub in all_pubs:
        if pub['event_name']:
            evt = pub['event_name']
            if evt not in pub_events:
                pub_events[evt] = []
            pub_events[evt].append(pub)

    sub_events = {}
    for sub in all_subs:
        if sub['event_name']:
            evt = sub['event_name']
            if evt not in sub_events:
                sub_events[evt] = []
            sub_events[evt].append(sub)

    orphan_pubs = []
    for evt, pubs in pub_events.items():
        if evt not in sub_events:
            orphan_pubs.append({
                'event': evt,
                'pub_count': len(pubs),
                'pubs': pubs[:5],
            })

    orphan_subs = []
    for evt, subs in sub_events.items():
        if evt not in pub_events:
            orphan_subs.append({
                'event': evt,
                'sub_count': len(subs),
                'subs': subs[:5],
            })

    closed = []
    for evt in set(pub_events.keys()) & set(sub_events.keys()):
        closed.append({
            'event': evt,
            'pub_count': len(pub_events[evt]),
            'sub_count': len(sub_events[evt]),
        })

    return orphan_pubs, orphan_subs, closed


# ============================================================
# 主入口
# ============================================================
def main():
    out = []
    out.append("=" * 100)
    out.append("R198-C V13 跨行 publish 检测扫描器 (升级自 V12)")
    out.append("=" * 100)
    out.append("V13 升级点:")
    out.append("  1. AST NodeVisitor 递归扫描所有 Call 节点")
    out.append("  2. 节点位置: ast.Call.lineno (开始) + ast.Call.end_lineno (结束)")
    out.append("  3. 范围查询: 提取 Call 节点内所有 Constant (str) 节点")
    out.append("  4. 跨行判定: call.end_lineno > call.lineno")
    out.append("  5. 物理行连续性验证: 反斜杠续行 \\ 识别")
    out.append("  6. V12 兼容: 单行模式保留 (R194-B 100% 兼容)")
    out.append("=" * 100)
    out.append("")

    # ===== 阶段 1: R195-B 已知案例补全 (TDD) =====
    out.append("=" * 100)
    out.append("阶段 1: R195-B 已知案例补全验证 (TDD)")
    out.append("=" * 100)

    known_case_evt = "reconcile_health_alert"
    result_known = scan_event_v13(known_case_evt)

    out.append(f"事件: {known_case_evt}")
    out.append(f"  V12 单行 publish: {result_known['pub_v12_total']}")
    out.append(f"  V13 跨行 publish: {len(result_known['pub_v13_multiline'])}")
    out.append(f"  V12 单行 subscribe: {result_known['sub_v12_total']}")
    out.append(f"  V13 跨行 subscribe: {len(result_known['sub_v13_multiline'])}")

    if result_known['pub_v13_multiline']:
        for p in result_known['pub_v13_multiline']:
            out.append(f"  [V13 命中] 跨行 publish: {p['file']} L{p['lines']} ({p['func_name']})")
            out.append(f"    物理文本:\n{p['physical_text']}")

    if result_known['sub_v13_multiline']:
        for s in result_known['sub_v13_multiline']:
            out.append(f"  [V13 命中] 跨行 subscribe: {s['file']} L{s['lines']} ({s['func_name']})")

    # 验证: V12 vs V13
    v12_miss = (result_known['pub_v12_total'] == 0 and len(result_known['pub_v13_multiline']) > 0)
    if v12_miss:
        out.append(f"  ✅ V13 补全 R195-B 案例: V12 漏检 → V13 命中 (跨行 publish)")
    elif result_known['pub_v12_total'] > 0:
        out.append(f"  ✅ V12 已覆盖单行 publish (无跨行)")
    out.append("")

    # ===== 阶段 2: 全项目 V13 publish 扫描 =====
    out.append("=" * 100)
    out.append("阶段 2: 全项目 V13 publish 扫描 (排除 tests/)")
    out.append("=" * 100)

    all_pubs = scan_all_publishes_v13()
    multiline_pubs = [p for p in all_pubs if p['is_multiline'] or p['has_continuation']]

    out.append(f"全项目 publish 总数: {len(all_pubs)}")
    out.append(f"  跨行 publish: {len(multiline_pubs)}")
    out.append(f"  单行 publish: {len(all_pubs) - len(multiline_pubs)}")

    out.append("")
    out.append("=== 跨行 publish 明细 (V13 新发现) ===")
    for pub in multiline_pubs[:30]:
        out.append(f"  {pub['file']}:L{pub['call_start']}-{pub['call_end']} "
                   f"event={pub['event_name']!r} func={pub['func_name']} "
                   f"continuation={pub['has_continuation']}")

    if len(multiline_pubs) > 30:
        out.append(f"  ... 还有 {len(multiline_pubs) - 30} 项")

    # ===== 阶段 3: 全项目 V13 subscribe 扫描 =====
    out.append("")
    out.append("=" * 100)
    out.append("阶段 3: 全项目 V13 subscribe 扫描 (排除 tests/)")
    out.append("=" * 100)

    all_subs = scan_all_subscribes_v13()
    multiline_subs = [s for s in all_subs if s['is_multiline'] or s['has_continuation']]

    out.append(f"全项目 subscribe 总数: {len(all_subs)}")
    out.append(f"  跨行 subscribe: {len(multiline_subs)}")
    out.append(f"  单行 subscribe: {len(all_subs) - len(multiline_subs)}")

    out.append("")
    out.append("=== 跨行 subscribe 明细 (V13 新发现) ===")
    for sub in multiline_subs[:30]:
        out.append(f"  {sub['file']}:L{sub['call_start']}-{sub['call_end']} "
                   f"event={sub['event_name']!r} func={sub['func_name']}")

    # ===== 阶段 4: ORPHAN 配对 =====
    out.append("")
    out.append("=" * 100)
    out.append("阶段 4: ORPHAN_PUB / ORPHAN_SUB 配对")
    out.append("=" * 100)

    orphan_pubs, orphan_subs, closed = compute_orphan_pairs(all_pubs, all_subs)

    out.append(f"  闭环事件 (pub + sub): {len(closed)}")
    out.append(f"  ORPHAN_PUB (publish 无 subscribe): {len(orphan_pubs)}")
    out.append(f"  ORPHAN_SUB (subscribe 无 publish): {len(orphan_subs)}")

    out.append("")
    out.append("=== ORPHAN_PUB 明细 (V13 候选) ===")
    for op in orphan_pubs[:20]:
        out.append(f"  event={op['event']!r} pub_count={op['pub_count']}")
        for p in op['pubs'][:2]:
            out.append(f"    {p['file']}:L{p['call_start']}-{p['call_end']} (multiline={p['is_multiline']})")

    out.append("")
    out.append("=== ORPHAN_SUB 明细 (V13 候选) ===")
    for os_ in orphan_subs[:20]:
        out.append(f"  event={os_['event']!r} sub_count={os_['sub_count']}")
        for s in os_['subs'][:2]:
            out.append(f"    {s['file']}:L{s['call_start']}-{s['call_end']}")

    # ===== 阶段 5: 输出 JSON =====
    out.append("")
    out.append("=" * 100)
    out.append("阶段 5: 输出 V13 结果 JSON")
    out.append("=" * 100)

    results = {
        "scanner_version": "V13",
        "scanner_date": "2026-07-25",
        "scanner_purpose": "跨行 publish 检测, R195-B reconcile_health_alert 教训",
        "iron_laws_applied": ["R104 §12 5 铁律", "R85 假修复鉴别 4 步法", "R6 §6.1 8 铁律", "R8 §8.1 8 铁律"],
        "summary": {
            "total_publishes": len(all_pubs),
            "multiline_publishes": len(multiline_pubs),
            "single_line_publishes": len(all_pubs) - len(multiline_pubs),
            "total_subscribes": len(all_subs),
            "multiline_subscribes": len(multiline_subs),
            "single_line_subscribes": len(all_subs) - len(multiline_subs),
            "closed_events": len(closed),
            "orphan_pubs": len(orphan_pubs),
            "orphan_subs": len(orphan_subs),
        },
        "known_case_verification": {
            "reconcile_health_alert": {
                "v12_single_pub": result_known['pub_v12_total'],
                "v13_multiline_pub": len(result_known['pub_v13_multiline']),
                "v12_single_sub": result_known['sub_v12_total'],
                "v13_multiline_sub": len(result_known['sub_v13_multiline']),
                "v12_missed": v12_miss,
                "v13_hit": len(result_known['pub_v13_multiline']) > 0,
            },
        },
        "multiline_publishes": multiline_pubs,
        "multiline_subscribes": multiline_subs,
        "orphan_pubs": orphan_pubs,
        "orphan_subs": orphan_subs,
    }

    json_path = PROJECT_ROOT / "tools" / "_r198_c_v13_results.json"
    json_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    out.append(f"  ✅ V13 结果已保存: {json_path}")

    # 配对 JSON
    pairs = {
        "scanner_version": "V13",
        "date": "2026-07-25",
        "total_pubs": len(all_pubs),
        "total_subs": len(all_subs),
        "closed_count": len(closed),
        "orphan_pub_count": len(orphan_pubs),
        "orphan_sub_count": len(orphan_subs),
        "orphan_pubs": orphan_pubs,
        "orphan_subs": orphan_subs,
    }
    pair_path = PROJECT_ROOT / "tools" / "_r198_c_orphan_pair.json"
    pair_path.write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    out.append(f"  ✅ ORPHAN 配对已保存: {pair_path}")

    # 输出报告
    output = "\n".join(out)
    report_path = PROJECT_ROOT / ".audit_r198_c_v13.txt"
    report_path.write_text(output, encoding="utf-8")
    print(output, flush=True)

    return results


if __name__ == "__main__":
    main()
