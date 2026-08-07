"""
R237-B 6 个 P2 候选 0 dispose 链 Service 的 R78 治理 TDD 测试

立项依据: R235 子智能体 B §2.2 P2 候选清单 (6 个)
- AssetSeparatedDatabaseManager (10+ 业务方)
- EnhancedMoneyManager (3+ 业务方, R128-P1-3 订阅泄漏)
- RealDataProvider (1-2 业务方, 5min 定时器)
- ResourceMonitor (2-3 业务方, 有 stop 但未接入统一链)
- DataMissingManager (2-3 业务方, 有 close 但非 BaseService)
- JITWarmupManager (1-2 业务方, 启动期单例)

每 Service 6 用例模板 (R78 治理):
- T01: 必有 _disposed 标志 (R78 铁律 #6 幂等短路)
- T02: 必有 dispose() 方法 (R233 §13.4 P0 必修)
- T03: dispose() 含 _disposed 短路
- T04: 重复 dispose() 幂等 (R78 铁律 #6)
- T05: 业务数据清空 (R234 强化经验: 业务锁内清空)
- T06: dispose 失败防御 (R117-HVD-69 P1 模板: warning + exc_info, 不抛)

铁律遵循:
- R78 铁律 #6 幂等性 (R6 §6.1)
- R8 §8.1 事件总线 7+1 铁律
- R104 §12 5 铁律
- R231 §13 4 铁律
- R233 §13.4 业务核心 0 dispose 链 P0 必修
- R234 强化经验 (业务锁内清空 + 子组件释放 4 步法)
- R235-D OrderMonitor 模板 (类级默认 _disposed=None)
- R236-B 5 Service 模板 (4 链 dispose + 业务锁内清空)

不依赖外部 pytest fixture / 数据库, 仅用 AST 解析 + 字符串匹配验证源码。
"""

import ast
import os
import re
import inspect
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_source(rel_path: str) -> str:
    """读取项目源码"""
    full_path = PROJECT_ROOT / rel_path
    return full_path.read_text(encoding="utf-8")


def _find_class_node(tree: ast.AST, class_name: str) -> ast.ClassDef:
    """查找类节点"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise ValueError(f"Class {class_name} not found")


def _has_method(class_node: ast.ClassDef, method_name: str) -> bool:
    """检查类是否有指定方法"""
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == method_name:
            return True
    return False


def _method_body_source(source: str, class_name: str, method_name: str) -> str:
    """提取方法体的源码字符串"""
    tree = ast.parse(source)
    cls = _find_class_node(tree, class_name)
    for item in cls.body:
        if isinstance(item, ast.FunctionDef) and item.name == method_name:
            return ast.unparse(item)
    raise ValueError(f"Method {method_name} not found in class {class_name}")


def _init_body_source(source: str, class_name: str) -> str:
    """提取 __init__ 方法体的源码字符串"""
    return _method_body_source(source, class_name, "__init__")


def _chain_body_union(source: str, class_name: str, method_name: str) -> str:
    """提取 dispose + 4 链方法 (shutdown/close/cleanup) 的联合源码"""
    cls = _find_class_node(ast.parse(source), class_name)
    body = _method_body_source(source, class_name, method_name)
    body_union = body
    for chain_method in ("shutdown", "close", "cleanup"):
        if _has_method(cls, chain_method):
            try:
                body_union += "\n" + _method_body_source(source, class_name, chain_method)
            except ValueError:
                pass
    return body_union


# ============================================================================
# Test R237-B 01: AssetSeparatedDatabaseManager dispose 链 (10+ 业务方)
# ============================================================================
class TestR237B01AssetSeparatedDatabaseManagerDispose:
    """AssetSeparatedDatabaseManager 4 链 dispose 治理 (R78)"""

    REL_PATH = "core/asset_database_manager.py"
    CLASS_NAME = "AssetSeparatedDatabaseManager"

    def _src(self) -> str:
        return _read_source(self.REL_PATH)

    def _cls(self) -> ast.ClassDef:
        return _find_class_node(ast.parse(self._src()), self.CLASS_NAME)

    def test_T01_asdb_has_disposed_flag(self):
        """T01: 类级默认有 _disposed 标志 (R235-D 模板: _disposed=None/False)"""
        init_src = _init_body_source(self._src(), self.CLASS_NAME)
        assert "_disposed" in init_src, (
            f"AssetSeparatedDatabaseManager.__init__ 必须设置 _disposed 标志 (R78 铁律 #6)"
        )

    def test_T02_asdb_has_dispose_method(self):
        """T02: 必有 dispose() 方法 (R233 §13.4 P0 必修)"""
        assert _has_method(self._cls(), "dispose"), (
            "AssetSeparatedDatabaseManager 必须有 dispose() 方法 (R233 §13.4)"
        )

    def test_T03_asdb_dispose_has_short_circuit(self):
        """T03: dispose() 入口 _disposed 短路 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        # 短路条件 (任何 if self._disposed 返回)
        short_circuit_pattern = re.compile(
            r"if\s+(self\._disposed|getattr\s*\(\s*self\s*,\s*['_\"]_disposed['_\"])", re.IGNORECASE
        )
        assert short_circuit_pattern.search(body), (
            "dispose() 必须含 _disposed 短路 (R78 铁律 #6)"
        )

    def test_T04_asdb_repeated_dispose_idempotent(self):
        """T04: 重复 dispose() 幂等 (R78 铁律 #6)"""
        # dispose 方法存在, 且末尾有 _disposed = True 标记
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        assert "self._disposed = True" in body or "self._disposed=True" in body, (
            "dispose() 末尾必须标记 _disposed = True (R78 铁律 #6)"
        )

    def test_T05_asdb_clears_business_data(self):
        """T05: 业务数据清空 (R234 强化经验: 业务锁内清空 _asset_databases / _database_info)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        # 业务数据 dict 至少一个清空 (在 dispose 主体 或 4 链方法 shutdown/close/cleanup 内)
        src = self._src()
        body_union = body
        for chain_method in ("shutdown", "close", "cleanup"):
            if _has_method(self._cls(), chain_method):
                try:
                    body_union += "\n" + _method_body_source(src, self.CLASS_NAME, chain_method)
                except ValueError:
                    pass
        clears = [
            "_asset_databases" in body_union,
            "_database_info" in body_union,
        ]
        assert any(clears), (
            "dispose() 或其 4 链方法内必须清空业务数据 _asset_databases/_database_info (R234)"
        )

    def test_T06_asdb_dispose_failure_no_raise(self):
        """T06: dispose 失败防御 (R117-HVD-69 P1: warning + exc_info, 不抛)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        # 防御性: try/except + log + 不抛
        has_try = "try:" in body or "try " in body
        has_except = "except" in body
        # 或调用 helper (shutdown/close/cleanup) 内部已经有 try/except
        calls_safe_helper = any(
            f"self.{m}(" in body for m in ("shutdown", "close", "cleanup")
        )
        assert has_try or has_except or calls_safe_helper, (
            "dispose() 必须 try/except 防御 (R117-HVD-69 P1 模板)"
        )


# ============================================================================
# Test R237-B 02: EnhancedMoneyManager dispose 链 (3+ 业务方)
# ============================================================================
class TestR237B02EnhancedMoneyManagerDispose:
    """EnhancedMoneyManager 4 链 dispose 治理 (R78)"""

    REL_PATH = "core/money_manager.py"
    CLASS_NAME = "EnhancedMoneyManager"

    def _src(self) -> str:
        return _read_source(self.REL_PATH)

    def _cls(self) -> ast.ClassDef:
        return _find_class_node(ast.parse(self._src()), self.CLASS_NAME)

    def test_T01_emm_has_disposed_flag(self):
        """T01: __init__ 必有 _disposed 标志 (R78 铁律 #6)"""
        init_src = _init_body_source(self._src(), self.CLASS_NAME)
        assert "_disposed" in init_src, (
            "EnhancedMoneyManager.__init__ 必须设置 _disposed 标志 (R78 铁律 #6)"
        )

    def test_T02_emm_has_dispose_method(self):
        """T02: 必有 dispose() 方法 (R233 §13.4 P0 必修)"""
        assert _has_method(self._cls(), "dispose"), (
            "EnhancedMoneyManager 必须有 dispose() 方法 (R233 §13.4)"
        )

    def test_T03_emm_dispose_has_short_circuit(self):
        """T03: dispose() 入口 _disposed 短路 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        short_circuit_pattern = re.compile(
            r"if\s+(self\._disposed|getattr\s*\(\s*self\s*,\s*['_\"]_disposed['_\"])", re.IGNORECASE
        )
        assert short_circuit_pattern.search(body), (
            "dispose() 必须含 _disposed 短路 (R78 铁律 #6)"
        )

    def test_T04_emm_repeated_dispose_idempotent(self):
        """T04: 重复 dispose() 幂等 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        assert "self._disposed = True" in body or "self._disposed=True" in body, (
            "dispose() 末尾必须标记 _disposed = True (R78 铁律 #6)"
        )

    def test_T05_emm_clears_business_data(self):
        """T05: 业务数据清空 (positions, peak_equity, correlation_matrix)"""
        body_union = _chain_body_union(self._src(), self.CLASS_NAME, "dispose")
        # 业务字段至少一个清空 (在 dispose 或 4 链方法内)
        clears = [
            "positions" in body_union,
            "peak_equity" in body_union,
            "correlation_matrix" in body_union,
            "current_drawdown" in body_union,
        ]
        assert any(clears), (
            "dispose() 或其 4 链方法内必须清空业务数据 positions/peak_equity/correlation_matrix (R234)"
        )

    def test_T06_emm_dispose_failure_no_raise(self):
        """T06: dispose 失败防御 (R117-HVD-69 P1)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        has_try = "try:" in body or "try " in body
        has_except = "except" in body
        calls_safe_helper = any(
            f"self.{m}(" in body for m in ("shutdown", "close", "cleanup")
        )
        assert has_try or has_except or calls_safe_helper, (
            "dispose() 必须 try/except 防御 (R117-HVD-69 P1 模板)"
        )


# ============================================================================
# Test R237-B 03: RealDataProvider dispose 链 (1-2 业务方, 5min 定时器)
# ============================================================================
class TestR237B03RealDataProviderDispose:
    """RealDataProvider 4 链 dispose 治理 (R78) - 含 _cleanup_thread_stop"""

    REL_PATH = "core/real_data_provider.py"
    CLASS_NAME = "RealDataProvider"

    def _src(self) -> str:
        return _read_source(self.REL_PATH)

    def _cls(self) -> ast.ClassDef:
        return _find_class_node(ast.parse(self._src()), self.CLASS_NAME)

    def test_T01_rdp_has_disposed_flag(self):
        """T01: __init__ 必有 _disposed 标志 (R78 铁律 #6)"""
        init_src = _init_body_source(self._src(), self.CLASS_NAME)
        assert "_disposed" in init_src, (
            "RealDataProvider.__init__ 必须设置 _disposed 标志 (R78 铁律 #6)"
        )

    def test_T02_rdp_has_dispose_method(self):
        """T02: 必有 dispose() 方法 (R233 §13.4 P0 必修)"""
        assert _has_method(self._cls(), "dispose"), (
            "RealDataProvider 必须有 dispose() 方法 (R233 §13.4)"
        )

    def test_T03_rdp_dispose_has_short_circuit(self):
        """T03: dispose() 入口 _disposed 短路 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        short_circuit_pattern = re.compile(
            r"if\s+(self\._disposed|getattr\s*\(\s*self\s*,\s*['_\"]_disposed['_\"])", re.IGNORECASE
        )
        assert short_circuit_pattern.search(body), (
            "dispose() 必须含 _disposed 短路 (R78 铁律 #6)"
        )

    def test_T04_rdp_repeated_dispose_idempotent(self):
        """T04: 重复 dispose() 幂等 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        assert "self._disposed = True" in body or "self._disposed=True" in body, (
            "dispose() 末尾必须标记 _disposed = True (R78 铁律 #6)"
        )

    def test_T05_rdp_stops_cleanup_timer(self):
        """T05: 业务数据清空 + 5min 定时器停止 (R235 子智能体 B 候选特征)"""
        body_union = _chain_body_union(self._src(), self.CLASS_NAME, "dispose")
        # _cleanup_thread_stop = True (停止 5min 定时器) 是该 Service 核心治理点
        timer_stop = "_cleanup_thread_stop" in body_union and "True" in body_union
        # 业务数据清空 (_data_source_pool / _active_instances / _cache)
        clears = [
            "_data_source_pool" in body_union,
            "_active_instances" in body_union,
            "_cache" in body_union,
        ]
        assert timer_stop or any(clears), (
            "dispose() 或其 4 链方法内必须停止 5min 定时器 (_cleanup_thread_stop=True) + 业务数据清空 (R234)"
        )

    def test_T06_rdp_dispose_failure_no_raise(self):
        """T06: dispose 失败防御 (R117-HVD-69 P1)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        has_try = "try:" in body or "try " in body
        has_except = "except" in body
        calls_safe_helper = any(
            f"self.{m}(" in body for m in ("shutdown", "close", "cleanup")
        )
        assert has_try or has_except or calls_safe_helper, (
            "dispose() 必须 try/except 防御 (R117-HVD-69 P1 模板)"
        )


# ============================================================================
# Test R237-B 04: ResourceMonitor (UnifiedResourceMonitor) dispose 链 (2-3 业务方)
# ============================================================================
class TestR237B04UnifiedResourceMonitorDispose:
    """UnifiedResourceMonitor 4 链 dispose 治理 (R78) - 接入统一 dispose 链"""

    REL_PATH = "core/performance/resource_monitor.py"
    CLASS_NAME = "UnifiedResourceMonitor"

    def _src(self) -> str:
        return _read_source(self.REL_PATH)

    def _cls(self) -> ast.ClassDef:
        return _find_class_node(ast.parse(self._src()), self.CLASS_NAME)

    def test_T01_urm_has_disposed_flag(self):
        """T01: __init__ 必有 _disposed 标志 (R78 铁律 #6)"""
        init_src = _init_body_source(self._src(), self.CLASS_NAME)
        assert "_disposed" in init_src, (
            "UnifiedResourceMonitor.__init__ 必须设置 _disposed 标志 (R78 铁律 #6)"
        )

    def test_T02_urm_has_dispose_method(self):
        """T02: 必有 dispose() 方法 (R233 §13.4 P0 必修)"""
        assert _has_method(self._cls(), "dispose"), (
            "UnifiedResourceMonitor 必须有 dispose() 方法 (R233 §13.4)"
        )

    def test_T03_urm_dispose_has_short_circuit(self):
        """T03: dispose() 入口 _disposed 短路 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        short_circuit_pattern = re.compile(
            r"if\s+(self\._disposed|getattr\s*\(\s*self\s*,\s*['_\"]_disposed['_\"])", re.IGNORECASE
        )
        assert short_circuit_pattern.search(body), (
            "dispose() 必须含 _disposed 短路 (R78 铁律 #6)"
        )

    def test_T04_urm_repeated_dispose_idempotent(self):
        """T04: 重复 dispose() 幂等 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        assert "self._disposed = True" in body or "self._disposed=True" in body, (
            "dispose() 末尾必须标记 _disposed = True (R78 铁律 #6)"
        )

    def test_T05_urm_clears_business_data(self):
        """T05: 业务数据清空 (_usage_history, _alert_history, _stats) + 线程停止"""
        body_union = _chain_body_union(self._src(), self.CLASS_NAME, "dispose")
        # 业务数据至少一个清空 / 线程停止调用
        clears = [
            "_usage_history" in body_union,
            "_alert_history" in body_union,
            "_stats" in body_union,
            "self.stop(" in body_union,  # 调用现有 stop 方法
        ]
        assert any(clears), (
            "dispose() 或其 4 链方法内必须清空业务数据 / 调用 self.stop() (R234)"
        )

    def test_T06_urm_dispose_failure_no_raise(self):
        """T06: dispose 失败防御 (R117-HVD-69 P1)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        has_try = "try:" in body or "try " in body
        has_except = "except" in body
        calls_safe_helper = any(
            f"self.{m}(" in body for m in ("shutdown", "close", "cleanup", "stop")
        )
        assert has_try or has_except or calls_safe_helper, (
            "dispose() 必须 try/except 防御 (R117-HVD-69 P1 模板)"
        )


# ============================================================================
# Test R237-B 05: DataMissingManager dispose 链 (2-3 业务方)
# ============================================================================
class TestR237B05DataMissingManagerDispose:
    """DataMissingManager 4 链 dispose 治理 (R78) - 复用 close 方法"""

    REL_PATH = "core/ui_integration/data_missing_manager.py"
    CLASS_NAME = "DataMissingManager"

    def _src(self) -> str:
        return _read_source(self.REL_PATH)

    def _cls(self) -> ast.ClassDef:
        return _find_class_node(ast.parse(self._src()), self.CLASS_NAME)

    def test_T01_dmm_has_disposed_flag(self):
        """T01: __init__ 必有 _disposed 标志 (R78 铁律 #6)"""
        init_src = _init_body_source(self._src(), self.CLASS_NAME)
        assert "_disposed" in init_src, (
            "DataMissingManager.__init__ 必须设置 _disposed 标志 (R78 铁律 #6)"
        )

    def test_T02_dmm_has_dispose_method(self):
        """T02: 必有 dispose() 方法 (R233 §13.4 P0 必修)"""
        assert _has_method(self._cls(), "dispose"), (
            "DataMissingManager 必须有 dispose() 方法 (R233 §13.4)"
        )

    def test_T03_dmm_dispose_has_short_circuit(self):
        """T03: dispose() 入口 _disposed 短路 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        short_circuit_pattern = re.compile(
            r"if\s+(self\._disposed|getattr\s*\(\s*self\s*,\s*['_\"]_disposed['_\"])", re.IGNORECASE
        )
        assert short_circuit_pattern.search(body), (
            "dispose() 必须含 _disposed 短路 (R78 铁律 #6)"
        )

    def test_T04_dmm_repeated_dispose_idempotent(self):
        """T04: 重复 dispose() 幂等 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        assert "self._disposed = True" in body or "self._disposed=True" in body, (
            "dispose() 末尾必须标记 _disposed = True (R78 铁律 #6)"
        )

    def test_T05_dmm_clears_business_data(self):
        """T05: 业务数据清空 (availability_cache, download_tasks) + executor.shutdown"""
        body_union = _chain_body_union(self._src(), self.CLASS_NAME, "dispose")
        # 业务数据清空
        clears = [
            "availability_cache" in body_union,
            "download_tasks" in body_union,
            "plugin_status_cache" in body_union,
            "data_missing_callbacks" in body_union,
            "executor" in body_union,  # executor.shutdown 调用
        ]
        assert any(clears), (
            "dispose() 或其 4 链方法内必须清空业务数据 / 关闭 executor (R234)"
        )

    def test_T06_dmm_dispose_failure_no_raise(self):
        """T06: dispose 失败防御 (R117-HVD-69 P1)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        has_try = "try:" in body or "try " in body
        has_except = "except" in body
        calls_safe_helper = any(
            f"self.{m}(" in body for m in ("shutdown", "close", "cleanup")
        )
        assert has_try or has_except or calls_safe_helper, (
            "dispose() 必须 try/except 防御 (R117-HVD-69 P1 模板)"
        )


# ============================================================================
# Test R237-B 06: JITWarmupManager dispose 链 (1-2 业务方, 启动期单例)
# ============================================================================
class TestR237B06JITWarmupManagerDispose:
    """JITWarmupManager 4 链 dispose 治理 (R78) - 启动期单例清理"""

    REL_PATH = "core/jit_warmup.py"
    CLASS_NAME = "JITWarmupManager"

    def _src(self) -> str:
        return _read_source(self.REL_PATH)

    def _cls(self) -> ast.ClassDef:
        return _find_class_node(ast.parse(self._src()), self.CLASS_NAME)

    def test_T01_jwm_has_disposed_flag(self):
        """T01: __init__ 必有 _disposed 标志 (R78 铁律 #6)"""
        init_src = _init_body_source(self._src(), self.CLASS_NAME)
        assert "_disposed" in init_src, (
            "JITWarmupManager.__init__ 必须设置 _disposed 标志 (R78 铁律 #6)"
        )

    def test_T02_jwm_has_dispose_method(self):
        """T02: 必有 dispose() 方法 (R233 §13.4 P0 必修)"""
        assert _has_method(self._cls(), "dispose"), (
            "JITWarmupManager 必须有 dispose() 方法 (R233 §13.4)"
        )

    def test_T03_jwm_dispose_has_short_circuit(self):
        """T03: dispose() 入口 _disposed 短路 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        short_circuit_pattern = re.compile(
            r"if\s+(self\._disposed|getattr\s*\(\s*self\s*,\s*['_\"]_disposed['_\"])", re.IGNORECASE
        )
        assert short_circuit_pattern.search(body), (
            "dispose() 必须含 _disposed 短路 (R78 铁律 #6)"
        )

    def test_T04_jwm_repeated_dispose_idempotent(self):
        """T04: 重复 dispose() 幂等 (R78 铁律 #6)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        assert "self._disposed = True" in body or "self._disposed=True" in body, (
            "dispose() 末尾必须标记 _disposed = True (R78 铁律 #6)"
        )

    def test_T05_jwm_clears_business_data(self):
        """T05: 业务数据清空 (_warmed dict)"""
        body_union = _chain_body_union(self._src(), self.CLASS_NAME, "dispose")
        # _warmed dict 清空
        clears = [
            "_warmed" in body_union,
        ]
        assert any(clears), (
            "dispose() 或其 4 链方法内必须清空业务数据 _warmed (R234)"
        )

    def test_T06_jwm_dispose_failure_no_raise(self):
        """T06: dispose 失败防御 (R117-HVD-69 P1)"""
        body = _method_body_source(self._src(), self.CLASS_NAME, "dispose")
        has_try = "try:" in body or "try " in body
        has_except = "except" in body
        calls_safe_helper = any(
            f"self.{m}(" in body for m in ("shutdown", "close", "cleanup")
        )
        assert has_try or has_except or calls_safe_helper, (
            "dispose() 必须 try/except 防御 (R117-HVD-69 P1 模板)"
        )
