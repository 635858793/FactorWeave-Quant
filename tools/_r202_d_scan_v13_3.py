# -*- coding: utf-8 -*-
"""
R202-D V13.3 扫描器: 5 维度增量扫描 + R197-R201 已发现项白名单
==================================================================

目的:
  1. 在 V13.2 基础上升级到 V13.3, 添加 R197-R201 已发现 HVD 候选白名单
  2. 5 维度全项目增量扫描 (排除 R197-R201 已发现 50+ HVD)
  3. 输出新 HVD 候选清单 (>= 6 个, 期望 P0:1 + P1:3 + P2:2)

V13.2 → V13.3 升级点:
  1. R197-R201 已发现 HVD 白名单 (50+ 项, 含物理删除 + 立项)
  2. 5 维度扫描协同: 死代码 + 锁/缓存/事件总线 + 兼容层 + ORPHAN_PUB/SUB + 多账户/AI/性能
  3. 业务关键性分级: P0 业务核心 + P1 业务关键 + P2 启动期 + P3 工具类
  4. R104 §12 5 铁律 100% 应用: R+1 round 验证 + HVD 4 源 + AST 递归 + 物理删除前 4 源 + AST unparse
  5. R202-C HVD-R201-C-NEW-2/3/4 闭环 3 ORPHAN_SUB (2026-07-25 子智能体 C):
     - order_filled 集中 helper (r84_event_helper.publish_order_filled)
     - risk_alert 集中 helper + EventType 枚举 + EventCoordinator._on_risk_alert handler
     - position_update 集中 helper + EventType 枚举 + EventCoordinator._on_position_update handler
     3 个事件加入 R197_R201_EVENTS_WHITELIST, V13.3 扫描器 100% 排除误报.

R197-R201 已发现 HVD 白名单 (50+ 项, 严禁重复立项):
  - R197-D: NEW-01 ~ NEW-12 (12 项)
  - R198-D: NEW-R198-01 ~ NEW-R198-07 + 业务链 HVD 7 项 (14 项)
  - R199-D: NEW-R199-D1-01 ~ D5-02 (9 项)
  - R200 立项: HVD-R200-A-NEW-2/3 + HVD-R200-C-NEW-1 + HVD-R200-D-NEW-1 (4 项立项)
  - R201 立项: HVD-R201-A + HVD-R201-B-NEW-1 + HVD-R201-C-NEW-2/3/4 (5 项立项)
  - 物理删除: initialize_adaptive_pool + Base = DatabaseBase alias (2 项)
  - 业务关键性已分级: P0 业务核心 + P1 业务关键 + P2 启动期 + P3 工具类

Author: R202-D 子智能体
Date: 2026-07-25
强制度:
  - R104 §12 5 铁律
  - R85 假修复鉴别 4 步法
  - R6 §6.1 8 铁律 (死代码)
  - R51 §7.1 5 强约束 (服务注册)
  - R8 §8.1 8 铁律 (事件总线)
  - R9 §9.1 6 铁律 (缓存)
  - R100-F #8 4 锁独立
  - R194-B V12/V13 模式
"""
import os
import ast
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any, Optional
from collections import defaultdict


PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", ".cache", "data/cache"}
OUTPUT_DIR = PROJECT_ROOT / "tools"
OUTPUT_FILE = OUTPUT_DIR / "_r202_d_results.json"
SUMMARY_FILE = OUTPUT_DIR / "_r202_d_summary.json"


# ============================================================
# R197-R201 已发现 HVD 白名单 (V13.3 关键升级)
# ============================================================
R197_R201_HVD_WHITELIST = {
    # ---------- R197-D: 12 HVD ----------
    "R197-D-NEW-01": "order_filled ORPHAN_PUB 误报 (R196 REGISTERED_EVENT_TYPES 字符串值匹配修复后)",
    "R197-D-NEW-02": "unified_data_quality_monitor.py 兼容层 alias 文档化 (2 个 alias: QualityCheckType, UnifiedQualityReport)",
    "R197-D-NEW-03": "_make_auxiliary_cache_key 6 维度覆盖度 4 源验证 (P2)",
    "R197-D-NEW-04": "EventBus register_event_type 双轨注册强化 + 全项目覆盖率审计 (P1)",
    "R197-D-NEW-05": "测试代码锁嵌套反模式治理 (3 处 P0 违规)",
    "R197-D-NEW-06": "多账户隔离剩余业务追溯 (P1)",
    "R197-D-NEW-07": "AI 服务 40 文件集成度统一扫描 (P1, R195-D 模板复用)",
    "R197-D-NEW-08": "性能监控 133 文件指标覆盖率审计 (P2)",
    "R197-D-NEW-09": "全项目 4674 候选类批量 4 源验证 (P1)",
    "R197-D-NEW-10": "helper publish 模式追踪 (V13 升级, P2)",
    "R197-D-NEW-11": "R196-B P0 修复 4 源验证 (R+1 round, P0)",
    "R197-D-NEW-12": "ORPHAN_SUB 业务方订阅治理 (P1)",

    # ---------- R198-D: 14 HVD ----------
    "R198-D-NEW-R198-01": "模块级函数死代码 4 源验证 (1222 候选, P2)",
    "R198-D-NEW-R198-02": "缓存键工厂使用率 11% 提升 (P1) → R201-D 已实施 70.5%",
    "R198-D-NEW-R198-03": "业务锁名集合 86→100+ 扩展 (119 集合外锁, P2)",
    "R198-D-NEW-R198-04": "兼容层 alias 文档化 (17 候选, P2)",
    "R198-D-NEW-R198-05": "helper publish 模式追踪 (V13 升级, P2)",
    "R198-D-NEW-R198-06": "ORPHAN_PUB 剩余 3 个业务追溯 (P1)",
    "R198-D-NEW-R198-07": "业务方法缺 metric 记录 (取前 5, P2)",
    "R198-D-NEW-01": "order_event_handler register_event_type 覆盖率 (P1)",
    "R198-D-NEW-02": "order_persistence_retry_chain R193-C-D-001 闭环 (P1)",
    "R198-D-NEW-03": "account_multi_account_isolation 100% 覆盖 (P1, R119-C 延伸)",
    "R198-D-NEW-04": "risk_manager_soft_parse_full_audit (P0, R51 教训)",
    "R198-D-NEW-05": "kline_unified_data_manager_get_kdata 缓存键 6 维度 100% 审计 (P1)",
    "R198-D-NEW-06": "event_bus_4_lock_independent_strategy 100% 审计 (P1, R100-F-P1-1 #8)",
    "R198-D-NEW-07": "event_bus_orphan_pub_sub 业务方订阅 (P1)",

    # ---------- R199-D: 9 HVD ----------
    "R199-D-D1-01": "initialize_adaptive_pool 死代码 (P2) → R200-B 已物理删除",
    "R199-D-D2-01": "锁嵌套 29 处违规 (P1) → R200-B 验证为 0 处真嵌套 (误报)",
    "R199-D-D2-02": "4 个字符串事件缺 EventType (P1, 测试代码, R200 立项排除)",
    "R199-D-D2-03": "缓存键工厂使用率 34.9% 偏低 (P2) → R200-D 已实施 51.6%",
    "R199-D-D3-01": "Base = DatabaseBase alias (P2) → R200-B 已物理删除",
    "R199-D-D4-01": "ORPHAN_PUB 36 项业务方订阅治理 (P1) → R200-C 闭环 4 项",
    "R199-D-D4-02": "ORPHAN_SUB 37 项业务方订阅治理 (P1) → R200-C 闭环 2 项",
    "R199-D-D5-01": "多账户隔离 239 处 P0 业务核心 (P0) → R200-A + R201-A 已治理 90 处",
    "R199-D-D5-02": "AI 服务集成 P1 (P1)",

    # ---------- R200 立项: 4 HVD ----------
    "HVD-R200-A-NEW-2": "web/gui 多账户隔离治理 45 处 (P0) → R201-B 已闭环",
    "HVD-R200-A-NEW-3": "剩余 329 处多账户隔离 (P0) → R202-A 待治理",
    "HVD-R200-C-NEW-1": "67 项剩余 ORPHAN 治理 (P1) → R201-C 已闭环 4 项 + V13.2 升级",
    "HVD-R200-D-NEW-1": "缓存键工厂使用率 51.6% 提升 (P1) → R201-D 已实施 70.5%",

    # ---------- R201 立项: 5 HVD ----------
    "HVD-R201-A": "多账户隔离 P0 业务核心 (P0) → R201-A 已闭环 90 处",
    "HVD-R201-B-NEW-1": "6 处 API 端点 account_id 透传 (P0) → R202-B 待治理",
    "HVD-R201-C-NEW-2": "order_filled ORPHAN_SUB 业务方订阅治理 (P1) → R201-C 已闭环",
    "HVD-R201-C-NEW-3": "risk_alert ORPHAN_SUB 业务方订阅治理 (P1) → R201-C 已闭环",
    "HVD-R201-C-NEW-4": "position_update ORPHAN_SUB 业务方订阅治理 (P1) → R201-C 已闭环",

    # ---------- 物理删除 (2 项) ----------
    "DELETED-initialize_adaptive_pool": "core/adaptive_pool_initializer.py:33-106 (76 行) R200-B 物理删除",
    "DELETED-Base_alias": "web/backend/models/__init__.py:9 Base = DatabaseBase R200-B 物理删除",
}

# 文件级白名单 (R200-B 已物理删除 + V13.2 已闭环的事件)
R197_R201_FILE_WHITELIST = {
    "core/adaptive_pool_initializer.py",  # R200-B 删除了 initialize_adaptive_pool
    "core/asset_database_manager.py",   # R199-D 锁嵌套误报
    "core/ai/user_behavior_learner.py", # R199-D 锁嵌套误报
    "core/database/sqlite_extensions.py", # R199-D 锁嵌套误报
    "web/backend/models/__init__.py",   # R200-B 删除了 Base = DatabaseBase alias
}

# 事件名白名单 (R201-C V13.2 闭环 + R200-C 治理 6 个事件)
R197_R201_EVENTS_WHITELIST = {
    # R200-C 治理 4 ORPHAN_PUB
    "multi_account.drift_detected", "risk.stop_loss.updated",
    "task_submitted", "task_cancelled",
    # R200-C 治理 2 ORPHAN_SUB
    "bettafish.agent.stopped", "data_source_switched",
    # R201-C 治理 1 ORPHAN_PUB
    "order_status_changed",
    # R201-C 治理 3 ORPHAN_SUB
    "order.risk_check_failed", "order.position_limit_failed", "order.confirmed",
    # R195-B 挽救 1 跨行 P0
    "reconcile_health_alert",
    # R202-C HVD-R201-C-NEW-2/3/4 治理 3 ORPHAN_SUB (P1, 2026-07-25 子智能体 C 闭环):
    # - order_filled: EventType.ORDER_FILLED 已存在 (R24 修复, types.py:70), R202-C
    #                 新增集中 helper publish_order_filled (r84_event_helper.py),
    #                 与现有 publish_order_filled_string_once (order_filled_helper.py) 互补.
    # - risk_alert: EventType.RISK_ALERT 新增 (types.py:284, R202-C-NEW-3),
    #               publish_risk_alert 集中 helper + EventCoordinator._on_risk_alert
    #               handler + 启动期 register_event_type 双轨注册.
    # - position_update: EventType.POSITION_UPDATE 新增 (types.py:274, R202-C-NEW-4),
    #                   publish_position_update 集中 helper + EventCoordinator._on_position_update
    #                   handler + 启动期 register_event_type 双轨注册.
    "order_filled", "risk_alert", "position_update",
}


# ============================================================
# V13.3 扫描器 5 维度
# ============================================================
class V13_3_Scanner:
    """V13.3 扫描器: 5 维度增量扫描"""

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.results = {
            "metadata": {
                "scanner_version": "V13.3",
                "scan_date": "2026-07-25",
                "scanner_name": "R202-D",
                "iron_laws": [
                    "R104 §12 5 铁律", "R85 假修复鉴别 4 步法",
                    "R6 §6.1 8 铁律", "R51 §7.1 5 强约束",
                    "R8 §8.1 8 铁律", "R9 §9.1 6 铁律",
                    "R100-F #8 4 锁独立",
                ],
            },
            "whitelist": {
                "hvd_count": len(R197_R201_HVD_WHITELIST),
                "file_count": len(R197_R201_FILE_WHITELIST),
                "event_count": len(R197_R201_EVENTS_WHITELIST),
            },
            "dim_1_dead_code": [],
            "dim_2_lock_cache_eventbus": [],
            "dim_3_compat_layer": [],
            "dim_4_orphan_pub_sub": [],
            "dim_5_multi_account_ai_perf": [],
            "summary": {},
        }
        self.scan_start = time.time()

    def scan_all(self) -> Dict[str, Any]:
        """执行 5 维度扫描"""
        print(f"[*] R202-D V13.3 扫描启动 - {time.time() - self.scan_start:.1f}s")
        print(f"[*] 白名单: {len(R197_R201_HVD_WHITELIST)} HVD + {len(R197_R201_FILE_WHITELIST)} 文件 + {len(R197_R201_EVENTS_WHITELIST)} 事件")

        # 维度 1: 死代码扫描
        print("[1/5] 维度 1: 死代码扫描...")
        self.results["dim_1_dead_code"] = self._scan_dead_code()

        # 维度 2: 锁/缓存/事件总线
        print("[2/5] 维度 2: 锁/缓存/事件总线扫描...")
        self.results["dim_2_lock_cache_eventbus"] = self._scan_lock_cache_eventbus()

        # 维度 3: 兼容层
        print("[3/5] 维度 3: 兼容层 alias/wrapper 扫描...")
        self.results["dim_3_compat_layer"] = self._scan_compat_layer()

        # 维度 4: ORPHAN_PUB/SUB
        print("[4/5] 维度 4: ORPHAN_PUB/SUB V13 扫描...")
        self.results["dim_4_orphan_pub_sub"] = self._scan_orphan_pub_sub()

        # 维度 5: 多账户/AI/性能
        print("[5/5] 维度 5: 多账户/AI/性能扫描...")
        self.results["dim_5_multi_account_ai_perf"] = self._scan_multi_account_ai_perf()

        # 汇总
        self._summarize()
        return self.results

    # ============================================================
    # 维度 1: 死代码扫描
    # ============================================================
    def _scan_dead_code(self) -> List[Dict[str, Any]]:
        """维度 1: 死代码扫描 (R6 §6.1 8 铁律 + 排除白名单)"""
        candidates = []

        # 1.1 扫描未在 service_bootstrap 注册的 Service 类
        for subdir in SCAN_DIRS:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if rel in R197_R201_FILE_WHITELIST:
                        continue
                    if "test_" in fn or fn.endswith("_test.py"):
                        continue
                    if rel.startswith("tests/"):
                        continue

                    # 检测 class 继承 BaseService 但未注册
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            source = f.read()
                        tree = ast.parse(source, filename=str(full))
                    except (SyntaxError, UnicodeDecodeError):
                        continue

                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            # 跳过兼容层类名
                            if any(suffix in node.name for suffix in
                                   ["Unified", "Enhanced", "Legacy", "Base", "Abstract",
                                    "V1", "V2", "V3", "Compat", "CompatLayer"]):
                                continue
                            # 检测 BaseService 子类
                            for base in node.bases:
                                base_name = ""
                                if isinstance(base, ast.Name):
                                    base_name = base.id
                                elif isinstance(base, ast.Attribute):
                                    base_name = base.attr
                                if "Service" in base_name and "Base" in base_name:
                                    # 进一步检测是否在 service_bootstrap 注册
                                    if not self._is_registered(node.name):
                                        candidates.append({
                                            "file": rel,
                                            "line": node.lineno,
                                            "class_name": node.name,
                                            "base_class": base_name,
                                            "type": "unregistered_service",
                                            "candidate_priority": "P2",  # 启动期 Service 未注册
                                        })
                                    break

        # 1.2 扫描未使用的模块级公共函数
        module_level_funcs = self._scan_unused_module_funcs()
        candidates.extend(module_level_funcs[:5])  # 取前 5

        return candidates[:20]  # 限流

    def _is_registered(self, class_name: str) -> bool:
        """检测 Service 类是否在 service_bootstrap.py 注册"""
        bootstrap_path = PROJECT_ROOT / "core" / "services" / "service_bootstrap.py"
        if not bootstrap_path.exists():
            return True
        try:
            with open(bootstrap_path, 'r', encoding='utf-8', errors='ignore') as f:
                bootstrap_src = f.read()
        except Exception:
            return True
        return class_name in bootstrap_src

    def _scan_unused_module_funcs(self) -> List[Dict[str, Any]]:
        """扫描未使用的模块级公共函数 (基于 R6 §6.1 4 源验证简化版)"""
        candidates = []
        # 已知候选: R198-D 提到 R197-D 已扫过 1222 候选
        # R202 增量: 关注新出现的模块级函数, 跨子目录
        for subdir in ["core/managers", "core/coordinators", "core/services"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if rel in R197_R201_FILE_WHITELIST:
                        continue
                    if "test_" in fn or fn.endswith("_test.py"):
                        continue

                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            source = f.read()
                        tree = ast.parse(source, filename=str(full))
                    except (SyntaxError, UnicodeDecodeError):
                        continue

                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if not node.name.startswith("_") and node.col_offset == 0:
                                # 公共模块级函数, 检查是否被调用
                                if not self._is_func_called(node.name, rel):
                                    candidates.append({
                                        "file": rel,
                                        "line": node.lineno,
                                        "func_name": node.name,
                                        "type": "unused_module_func",
                                        "candidate_priority": "P2",
                                    })
        return candidates

    def _is_func_called(self, func_name: str, origin_file: str) -> bool:
        """简化版: 检查函数是否被其他文件调用"""
        for subdir in SCAN_DIRS:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if rel == origin_file:
                        continue
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                    if func_name in content:
                        return True
        return False

    # ============================================================
    # 维度 2: 锁/缓存/事件总线
    # ============================================================
    def _scan_lock_cache_eventbus(self) -> List[Dict[str, Any]]:
        """维度 2: 锁嵌套 + 缓存键 6 维度 + 事件总线双轨注册"""
        candidates = []

        # 2.1 锁嵌套检测 (R104 §12 #3 AST 递归 with.body)
        candidates.extend(self._scan_lock_nesting())

        # 2.2 缓存键 6 维度检测
        candidates.extend(self._scan_cache_key_6d())

        # 2.3 事件总线双轨注册
        candidates.extend(self._scan_event_dual_track())

        return candidates[:20]

    def _scan_lock_nesting(self) -> List[Dict[str, Any]]:
        """锁嵌套检测 (AST 递归 with.body)"""
        candidates = []
        # 业务锁名集合 (复用 R198-D K1)
        business_locks = {
            "_lock", "_positions_lock", "_account_lock", "_order_lock",
            "_cache_lock", "_risk_lock", "_user_lock", "_futures_lock",
            "_stats_lock", "_history_lock", "_registry_lock", "_auth_lock",
            "_permission_lock", "_role_lock", "_session_lock", "_trade_lock",
            "_portfolio_lock", "_balance_lock", "_position_lock", "_config_lock",
        }
        # 已排除 R199-D 误报 29 处
        excluded_files = {
            "core/asset_database_manager.py",
            "core/ai/user_behavior_learner.py",
            "core/database/sqlite_extensions.py",
            "tests/test_r27_stress_batch_cancel_race.py",
        }

        for subdir in ["core", "gui", "web"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if rel in excluded_files or rel in R197_R201_FILE_WHITELIST:
                        continue
                    if "test_" in fn or rel.startswith("tests/"):
                        continue

                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            source = f.read()
                        tree = ast.parse(source, filename=str(full))
                    except (SyntaxError, UnicodeDecodeError):
                        continue

                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            nested = self._detect_nested_lock_in_method(node, business_locks)
                            for n in nested:
                                candidates.append({
                                    "file": rel,
                                    "method": node.name,
                                    "line": n["line"],
                                    "parent_lock": n["parent"],
                                    "child_lock": n["child"],
                                    "type": "lock_nesting",
                                    "candidate_priority": "P1",
                                })
        return candidates

    def _detect_nested_lock_in_method(self, func_node, business_locks) -> List[Dict[str, Any]]:
        """AST 递归 with.body 检测锁嵌套"""
        nested = []
        def visit_block(stmts, parent_locks):
            current_locks = set(parent_locks)
            for stmt in stmts:
                if isinstance(stmt, ast.With):
                    new_locks = set(current_locks)
                    for item in stmt.items:
                        if isinstance(item.context_expr, ast.Attribute):
                            if isinstance(item.context_expr.value, ast.Name):
                                if item.context_expr.value.id == "self":
                                    lock_name = item.context_expr.attr
                                    if lock_name in business_locks:
                                        if lock_name in current_locks:
                                            nested.append({
                                                "line": stmt.lineno,
                                                "parent": lock_name,
                                                "child": lock_name,
                                            })
                                        new_locks.add(lock_name)
                    visit_block(stmt.body, new_locks)
                elif isinstance(stmt, ast.Try):
                    visit_block(stmt.body, current_locks)
                    for handler in stmt.handlers:
                        visit_block(handler.body, current_locks)
                elif isinstance(stmt, (ast.If, ast.For, ast.While)):
                    visit_block(stmt.body, current_locks)
                    if isinstance(stmt, ast.If):
                        visit_block(stmt.orelse, current_locks)
        visit_block(func_node.body, set())
        return nested

    def _scan_cache_key_6d(self) -> List[Dict[str, Any]]:
        """缓存键 6 维度检测 (排除白名单)"""
        candidates = []
        # R198-D 已知 _make_auxiliary_cache_key 6 维度已部分覆盖
        # R202 增量: 找非工厂方法的 f-string 缓存键 (排除 R201-D 4 子目录已修复)
        r201_d_excluded_files = {
            "core/agents/news_agent.py",
            "core/agents/risk_agent.py",
            "core/agents/technical_agent.py",
            "core/importdata/import_execution_engine.py",
            "core/performance/professional_risk_metrics.py",
            "core/performance/unified_monitor.py",
            "core/services/service_bootstrap.py",
            "core/services/bond_service.py",
            "core/services/fund_service.py",
            "core/services/index_service.py",
            "core/services/stock_service.py",
            "core/services/indicator_dependency_manager.py",
        }
        # 已知的工厂方法签名 (R201-D 已实施, 内部的 f-string 是合法实现)
        known_factory_funcs = {
            "_make_business_cache_key", "_make_auxiliary_cache_key",
            "_make_indicator_cache_key", "_make_var_cache_key",
            "_make_tab_data_cache_key", "_make_service_health_key",
            "_make_kdata_cache_key", "_make_task_cache_key",
            "_make_config_cache_key", "_make_quality_cache_key",
            "make_cache_key", "make_6d_cache_key", "_make_6d_cache_key",
        }

        # 检测 f"xxx_v2_xxx" 模式 (缓存键硬编码)
        pattern = re.compile(r'f["\'][^"\']*_v2_[^"\']*["\']')
        for subdir in ["core"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if rel in r201_d_excluded_files or rel in R197_R201_FILE_WHITELIST:
                        continue
                    if "test_" in fn or rel.startswith("tests/"):
                        continue

                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue

                    # 排除已知工厂方法内部的 f-string
                    # 检测是否在工厂方法体内
                    lines = content.splitlines()
                    factory_lines = set()
                    try:
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if node.name in known_factory_funcs:
                                    for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                                        factory_lines.add(ln)
                    except Exception:
                        pass

                    # 仅统计工厂方法外的 f-string
                    real_matches = 0
                    real_samples = []
                    for m in pattern.finditer(content):
                        line_num = content[:m.start()].count("\n") + 1
                        if line_num not in factory_lines:
                            real_matches += 1
                            if len(real_samples) < 3:
                                real_samples.append(m.group(0)[:80])

                    if real_matches > 0:
                        candidates.append({
                            "file": rel,
                            "fstring_count": real_matches,
                            "samples": real_samples,
                            "type": "cache_key_fstring_outside_factory",
                            "candidate_priority": "P2",
                        })
        return candidates

    def _scan_event_dual_track(self) -> List[Dict[str, Any]]:
        """事件总线双轨注册检测 (R8 §8.1 #1)"""
        candidates = []
        # 排除 R198-D-NEW-04 已治理 + R201-C 已治理
        # R202 增量: 找未在 EventType 枚举中注册的字符串事件
        types_path = PROJECT_ROOT / "core" / "events" / "types.py"
        if not types_path.exists():
            return candidates
        try:
            with open(types_path, 'r', encoding='utf-8', errors='ignore') as f:
                types_src = f.read()
        except Exception:
            return candidates

        # 提取 EventType 枚举成员
        enum_members = set()
        try:
            tree = ast.parse(types_src)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "EventType":
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Name):
                                    enum_members.add(target.id)
        except Exception:
            return candidates

        # 扫描全项目 bus.publish('event_name', ...) 字符串事件
        pub_pattern = re.compile(r"""(?:publish|_safe_publish)\s*\(\s*['"]([a-zA-Z][a-zA-Z0-9_.]*)['"]""")
        unregistered = defaultdict(int)
        for subdir in ["core", "gui"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if "test_" in fn or rel.startswith("tests/"):
                        continue
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                    for m in pub_pattern.finditer(content):
                        evt = m.group(1)
                        if "." in evt and evt not in R197_R201_EVENTS_WHITELIST:
                            # 业务事件 . 分隔, 不在 EventType 枚举中
                            parts = evt.upper().split(".")
                            if not any(p in enum_members for p in parts):
                                unregistered[evt] += 1
        # 输出 Top 10
        sorted_unreg = sorted(unregistered.items(), key=lambda x: -x[1])[:10]
        for evt, count in sorted_unreg:
            if count >= 2:  # 至少 2 处才立项
                candidates.append({
                    "event": evt,
                    "publish_count": count,
                    "type": "string_event_unregistered",
                    "candidate_priority": "P2",
                })
        return candidates

    # ============================================================
    # 维度 3: 兼容层 alias/wrapper
    # ============================================================
    def _scan_compat_layer(self) -> List[Dict[str, Any]]:
        """维度 3: 兼容层 alias/wrapper 4 源验证 (排除白名单)"""
        candidates = []
        # 检测类级 alias: `AliasName = TargetClass`
        # 检测模块级 wrapper 函数
        alias_pattern = re.compile(r"^([A-Z][a-zA-Z0-9_]*)\s*=\s*([A-Z][a-zA-Z0-9_]*)\s*$", re.MULTILINE)
        for subdir in ["core", "web", "gui"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if rel in R197_R201_FILE_WHITELIST:
                        continue
                    if "test_" in fn or rel.startswith("tests/"):
                        continue
                    if any(suffix in rel for suffix in ["models/__init__.py", "services/__init__.py"]):
                        # __init__.py 中的 alias 是公共导出, 跳过
                        continue
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                    for m in alias_pattern.finditer(content):
                        alias_name, target = m.group(1), m.group(2)
                        if alias_name == target:
                            continue
                        if any(suffix in target for suffix in ["Unified", "Enhanced", "Legacy", "Base", "Abstract"]):
                            candidates.append({
                                "file": rel,
                                "line": content[:m.start()].count("\n") + 1,
                                "alias_name": alias_name,
                                "target_name": target,
                                "type": "compat_alias",
                                "candidate_priority": "P2",
                            })
        return candidates[:10]

    # ============================================================
    # 维度 4: ORPHAN_PUB/SUB (V13 模式)
    # ============================================================
    def _scan_orphan_pub_sub(self) -> List[Dict[str, Any]]:
        """维度 4: ORPHAN_PUB/SUB V13 扫描 (排除 R201-C 闭环 4+3 + R200-C 闭环 4+2)"""
        candidates = []
        pub_pattern = re.compile(r"""(?:publish|_safe_publish)\s*\(\s*['"]([a-zA-Z][a-zA-Z0-9_.]*)['"]""")
        sub_pattern = re.compile(r"""(?:subscribe|_subscribe_event)\s*\(\s*['"]([a-zA-Z][a-zA-Z0-9_.]*)['"]""")
        # R203-A 升级 (2026-07-26, 子智能体 A): 增加 for 循环字符串字面量订阅块模式识别
        # Why: R203-A 实施 L702-718 for 循环模式, 字符串字面量在元组 ('event_name', handler) 中,
        #      后续 _subscribe_event(_var, _var) 用变量. 原有 sub_pattern 仅识别直接 _subscribe_event('literal', ...)
        #      模式, 无法识别 for 循环.
        # Fix: 增加 tuple_literal_sub_pattern 匹配 ('event_name', self._on_xxx) 字符串字面量元组.
        # 强制度: R8 §8.1 #3 集中 helper 配对 + R203-A HVD 实施规范.
        tuple_literal_sub_pattern = re.compile(r"""\(\s*['"]([a-zA-Z][a-zA-Z0-9_.]*)['"]\s*,\s*self\._on_[a-zA-Z_]+""")

        pub_events = defaultdict(list)
        sub_events = defaultdict(list)

        for subdir in ["core", "gui", "web"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if "test_" in fn or rel.startswith("tests/"):
                        continue
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                    for i, line in enumerate(content.splitlines(), 1):
                        for m in pub_pattern.finditer(line):
                            evt = m.group(1)
                            if evt not in R197_R201_EVENTS_WHITELIST:
                                pub_events[evt].append((rel, i))
                        for m in sub_pattern.finditer(line):
                            evt = m.group(1)
                            if evt not in R197_R201_EVENTS_WHITELIST:
                                sub_events[evt].append((rel, i))
                        # R203-A 升级: 识别 for 循环字符串字面量订阅块
                        for m in tuple_literal_sub_pattern.finditer(line):
                            evt = m.group(1)
                            if evt not in R197_R201_EVENTS_WHITELIST:
                                sub_events[evt].append((rel, i))

        # ORPHAN_PUB: publish 但无 subscribe
        for evt, pubs in pub_events.items():
            if evt not in sub_events and len(pubs) >= 1:
                # 排除字段名误报
                if evt in {"order_id", "fill_id", "asset_type", "account_id", "new_status",
                           "no_change", "ctp", "miniqmt", "xtp_pro", "started", "stopped",
                           "paused", "resumed", "rejected", "closed", "connect", "normal",
                           "kline", "form_checkbox", "COMPLETED", "FAILED", "RUNNING",
                           "PREDICTING", "BettaFishAgent", "BettaFishFusionModel",
                           "AIExplainabilityService", "AISelectionIntegrationService",
                           "retrain", "shutdown_all", "warning", "OrderBookEvent",
                           "TradeExecutedEvent", "TickDataEvent"}:
                    continue
                # 业务关键性分级
                priority = "P2"
                # P0 业务核心: 订单持久化 + 对账 + 风控 + 资金 (R142 P0-4 修复订单)
                if any(kw in evt.lower() for kw in ["order_save", "batch_orders", "active_orders", "order_save_failed"]):
                    priority = "P0"
                elif any(kw in evt.lower() for kw in ["reconcile", "drift", "critical", "alert", "threat"]):
                    priority = "P0"
                elif any(kw in evt.lower() for kw in ["order", "trade", "risk", "position", "account", "batch_confirmed", "quote_updated"]):
                    priority = "P1"
                candidates.append({
                    "event": evt,
                    "publish_count": len(pubs),
                    "publish_locations": pubs[:3],
                    "type": "ORPHAN_PUB",
                    "candidate_priority": priority,
                })
        # ORPHAN_SUB: subscribe 但无 publish
        for evt, subs in sub_events.items():
            if evt not in pub_events and len(subs) >= 1:
                if evt in {"warning", "error", "info", "debug"}:
                    continue
                priority = "P2"
                if any(kw in evt.lower() for kw in ["order", "trade", "risk", "position", "account"]):
                    priority = "P1"
                candidates.append({
                    "event": evt,
                    "subscribe_count": len(subs),
                    "subscribe_locations": subs[:3],
                    "type": "ORPHAN_SUB",
                    "candidate_priority": priority,
                })
        return candidates[:20]

    # ============================================================
    # 维度 5: 多账户/AI/性能
    # ============================================================
    def _scan_multi_account_ai_perf(self) -> List[Dict[str, Any]]:
        """维度 5: 多账户/AI/性能 增量扫描"""
        candidates = []

        # 5.1 多账户隔离 (R200-A 已闭环 90 处, R200-A-NEW-3 待 329 处)
        # R202-D 增量: 找新增的多账户隔离薄弱点
        candidates.extend(self._scan_multi_account_isolation())

        # 5.2 AI agent 软解析 (R51 §7.1 #5 教训)
        candidates.extend(self._scan_ai_soft_parse())

        # 5.3 性能关键路径无 metric 记录
        candidates.extend(self._scan_perf_metric())

        return candidates[:20]

    def _scan_multi_account_isolation(self) -> List[Dict[str, Any]]:
        """多账户隔离扫描 (排除 R200-A/R201-A/R201-B 已治理 90+45+6=141 处)"""
        candidates = []
        # 已知治理位置 (R200-A + R201-A + R201-B)
        treated_files = {
            "core/trading_engine.py", "core/services/trading_confirmation_service.py",
            "core/services/trading_service.py", "core/services/account_service.py",
            "core/services/portfolio_service.py", "web/backend/services/order_service.py",
            "gui/dialogs/account_management_dialog.py", "web/backend/api/v1/orders.py",
        }
        # 检测业务关键方法缺 account_id 参数 (但有 self.context 或 _current_account_id)
        pattern = re.compile(r"def\s+(get_|create_|update_|delete_|fetch_|list_|query_)([a-z_]+)\s*\(")
        # P0 业务核心服务 (R104 §13 多账户隔离铁律)
        p0_services = {
            "advanced_risk_control_service.py",   # 风控核心
            "trading_confirmation_service.py",     # 订单确认
            "order_service.py",                    # 订单服务
            "position_manager.py",                 # 持仓管理
        }
        for subdir in ["core/services", "core/managers", "web/backend/services"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if rel in treated_files or rel in R197_R201_FILE_WHITELIST:
                        continue
                    if "test_" in fn or rel.startswith("tests/"):
                        continue
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                    # 找 get_/create_/update_/delete_/fetch_/list_/query_ 方法
                    for m in pattern.finditer(content):
                        method_name = m.group(0).split("(")[0].replace("def ", "").strip()
                        # 检查方法体内是否提到 account_id
                        method_start = m.end()
                        # 简化: 找下一个 def 或类结束
                        next_def = content.find("\n    def ", method_start)
                        if next_def == -1:
                            next_def = method_start + 500
                        method_body = content[method_start:next_def]
                        if "account_id" not in method_body and "user_id" not in method_body:
                            # 业务关键性分级
                            fn_lower = fn.lower()
                            if any(p0 in fn_lower for p0 in p0_services):
                                priority = "P0"  # P0 业务核心
                            else:
                                priority = "P1"
                            candidates.append({
                                "file": rel,
                                "method": method_name,
                                "type": "multi_account_isolation_weak",
                                "candidate_priority": priority,
                            })
        return candidates[:15]

    def _scan_ai_soft_parse(self) -> List[Dict[str, Any]]:
        """AI agent 软解析扫描 (R51 §7.1 #5 强约束)"""
        candidates = []
        # 检测 service_container.get(AIxxxService, default=None) 软解析
        pattern = re.compile(r"service_container\.get\([^,]+,\s*default\s*=\s*None\)")
        for subdir in ["core"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if "test_" in fn or rel.startswith("tests/"):
                        continue
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                    matches = pattern.findall(content)
                    if matches:
                        candidates.append({
                            "file": rel,
                            "soft_parse_count": len(matches),
                            "samples": matches[:3],
                            "type": "ai_soft_parse",
                            "candidate_priority": "P0",  # R51 教训 P0 业务核心
                        })
        return candidates

    def _scan_perf_metric(self) -> List[Dict[str, Any]]:
        """性能关键路径无 metric 记录"""
        candidates = []
        # 找 trading/risk/position 业务关键方法但无 metric 记录
        critical_funcs = ["submit_order", "fill_order", "reject_order", "calculate_risk",
                         "update_position", "check_position_limit", "evaluate_position",
                         "validate_order", "confirm_order", "execute_buy", "execute_sell"]
        for subdir in ["core/services", "core/trading", "core/risk"]:
            scan_path = PROJECT_ROOT / subdir
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    full = Path(root) / fn
                    rel = str(full.relative_to(PROJECT_ROOT))
                    if "test_" in fn or rel.startswith("tests/"):
                        continue
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                    for func in critical_funcs:
                        # 找 def func_name( 行
                        def_pattern = re.compile(rf"def\s+{func}\s*\(")
                        for m in def_pattern.finditer(content):
                            method_start = m.end()
                            next_def = content.find("\n    def ", method_start)
                            if next_def == -1:
                                next_def = method_start + 800
                            method_body = content[method_start:next_def]
                            if ("metric" not in method_body.lower() and
                                "counter" not in method_body.lower() and
                                "histogram" not in method_body.lower() and
                                "duration" not in method_body.lower()):
                                candidates.append({
                                    "file": rel,
                                    "method": func,
                                    "type": "perf_metric_missing",
                                    "candidate_priority": "P2",
                                })
        return candidates[:10]

    # ============================================================
    # 汇总
    # ============================================================
    def _summarize(self):
        """汇总 5 维度扫描结果"""
        all_candidates = []
        for dim in ["dim_1_dead_code", "dim_2_lock_cache_eventbus",
                    "dim_3_compat_layer", "dim_4_orphan_pub_sub",
                    "dim_5_multi_account_ai_perf"]:
            all_candidates.extend(self.results[dim])

        # 按优先级分级
        p0 = [c for c in all_candidates if c.get("candidate_priority") == "P0"]
        p1 = [c for c in all_candidates if c.get("candidate_priority") == "P1"]
        p2 = [c for c in all_candidates if c.get("candidate_priority") == "P2"]
        p3 = [c for c in all_candidates if c.get("candidate_priority") == "P3"]

        # 按类型分组
        by_type = defaultdict(int)
        for c in all_candidates:
            by_type[c.get("type", "unknown")] += 1

        self.results["summary"] = {
            "total_candidates": len(all_candidates),
            "by_priority": {
                "P0": len(p0),
                "P1": len(p1),
                "P2": len(p2),
                "P3": len(p3),
            },
            "by_type": dict(by_type),
            "scan_duration_sec": round(time.time() - self.scan_start, 2),
            "target_met": {
                "P0": ">= 1" + (" ✅" if len(p0) >= 1 else " ❌"),
                "P1": ">= 3" + (" ✅" if len(p1) >= 3 else " ❌"),
                "P2": ">= 2" + (" ✅" if len(p2) >= 2 else " ❌"),
                "total": ">= 6" + (" ✅" if len(all_candidates) >= 6 else " ❌"),
            },
        }


def main():
    scanner = V13_3_Scanner()
    results = scanner.scan_all()

    # 保存结果
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(results["summary"], f, ensure_ascii=False, indent=2)

    print(f"\n[*] 扫描完成,耗时 {results['summary']['scan_duration_sec']}s")
    print(f"[*] 候选总数: {results['summary']['total_candidates']}")
    print(f"[*] 优先级分布: P0={results['summary']['by_priority']['P0']} "
          f"P1={results['summary']['by_priority']['P1']} "
          f"P2={results['summary']['by_priority']['P2']}")
    print(f"[*] 目标达成: {results['summary']['target_met']}")
    print(f"[*] 输出文件: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
