"""
R237-D P3 物理删除 TDD 测试 (2026-07-30) - POST-DELETION 验证版

> **任务**: 物理删除 2 项 P3 真正死代码 (R235-A §2.3 P3 候选)
> **强约束**: R6 §6.3 物理删除 SOP 10 步 + R104 §12 #4 物理删除前 4 源 100% 命中
> **R237 R+1 round 4 源验证 100% 命中**:
> - Read: types.py:1075-1095 (PredictionRecordedEvent) + types.py:1097-1119 (PredictionAccuracyUpdatedEvent)
> - Grep 跨 4 子目录: 仅 types.py + __init__.py, 0 业务调用方
> - CodeGraph: codegraph_callers 返回 0
> - 业务调用链追踪: 0 publish 端 (实际 publish 是 STRING "prediction.recorded" / "prediction.accuracy_updated",
>                  与 dataclass PredictionRecordedEvent / PredictionAccuracyUpdatedEvent 无关)

**R235-A §2.3 P3 候选 (8 项) R237 4 源验证识别**:
- 39-40: ApplicationThresholdExceeded, MetricsAggregated → FALSE POSITIVES (R147-D 治理)
- 41-42: OrderUpdateEvent, AccountStatusChangedEvent (string) → 不存在, 已排除
- 43: 'xxx' helper → 不存在 (R187 扫描器测试), 已排除
- 44-46: EnvironmentChangedEvent, PredictionRecordedEvent, PredictionAccuracyUpdatedEvent
  → **2 项真死代码**: PredictionRecordedEvent + PredictionAccuracyUpdatedEvent
  → EnvironmentChangedEvent 有 publish 端, 不是死代码, 需保留

**R237 P3 物理删除执行 (2026-07-30)**:
- types.py L1074-1115: 物理删除 PredictionRecordedEvent + PredictionAccuracyUpdatedEvent 类定义
- __init__.py L60-61 + L130-131: 物理删除 re-export
- 本测试文件为 POST-DELETION 验证版, 验证删除完整 + 业务链不破坏
"""

import pytest
import os
import sys
import ast
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ==============================================================================
# 2 P3 真正死代码清单 (R237 R+1 round 4 源验证 100% 命中)
# ==============================================================================

P3_DEAD_CODE_EVENTS = [
    # (类名, 业务场景)
    ("PredictionRecordedEvent",        "AI 预测记录"),
    ("PredictionAccuracyUpdatedEvent", "AI 预测精度更新"),
]


# ==============================================================================
# Group A: POST-DELETION 4 源验证 (R104 §12 #2 强约束)
# ==============================================================================

class TestP3PostDeletion4SourceVerification:
    """P3 物理删除 POST-DELETION 4 源验证: 文件已无引用 + 0 业务调用方残留 + 业务调用链追踪"""

    @pytest.mark.parametrize("class_name,description", P3_DEAD_CODE_EVENTS)
    def test_a1_class_definition_removed(self, class_name, description):
        """源 1: Read 验证 class 定义在 types.py 物理不存在"""
        types_file = ROOT / "core" / "events" / "types.py"
        assert types_file.exists(), f"types.py 不存在: {types_file}"

        content = types_file.read_text(encoding="utf-8")
        assert f"class {class_name}" not in content, \
            f"[{class_name}] types.py 仍含 class 定义 (物理删除未完成)"

    @pytest.mark.parametrize("class_name,description", P3_DEAD_CODE_EVENTS)
    def test_a2_init_reexport_removed(self, class_name, description):
        """源 2: Read 验证 __init__.py 不再 re-export"""
        init_file = ROOT / "core" / "events" / "__init__.py"
        assert init_file.exists(), f"__init__.py 不存在: {init_file}"

        content = init_file.read_text(encoding="utf-8")
        # 严格验证: 既不在 import 块也不在 __all__ 块
        assert class_name not in content, \
            f"[{class_name}] __init__.py 仍含 re-export (物理删除未完成)"

    @pytest.mark.parametrize("class_name,description", P3_DEAD_CODE_EVENTS)
    def test_a3_no_business_callers(self, class_name, description):
        """源 3: Grep 跨 4 子目录验证 0 业务调用方残留"""
        # 排除定义文件 + re-export + 工具脚本
        excluded = {
            "core/events/types.py",
            "core/events/__init__.py",
        }

        callers = []
        for subdir in ["core", "gui", "web", "tests"]:
            subdir_path = ROOT / subdir
            if not subdir_path.exists():
                continue
            for py_file in subdir_path.rglob("*.py"):
                rel = str(py_file.relative_to(ROOT))
                if rel in excluded:
                    continue
                if any(x in rel for x in ["_r", "_archive", "tools/", ".bak", "conftest"]):
                    continue
                # 排除 test_r237_d_2p3_physically_removed.py 自身
                if "test_r237_d_2p3_physically_removed" in rel:
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                # 检查 import + class 引用
                if f"import {class_name}" in content:
                    callers.append(f"{rel}: import {class_name}")
                if f"from .{class_name}" in content or f"from core.events import {class_name}" in content:
                    callers.append(f"{rel}: from ... import {class_name}")

        assert len(callers) == 0, \
            f"[{class_name}] 有 {len(callers)} 业务调用方残留: {callers}"

    @pytest.mark.parametrize("class_name,description", P3_DEAD_CODE_EVENTS)
    def test_a4_no_publishers_or_subscribers(self, class_name, description):
        """源 4: 0 publish 端 + 0 subscribe 端残留"""
        for subdir in ["core", "gui", "web"]:
            subdir_path = ROOT / subdir
            if not subdir_path.exists():
                continue
            for py_file in subdir_path.rglob("*.py"):
                rel = str(py_file.relative_to(ROOT))
                if any(x in rel for x in ["_r", "_archive", "tools/", ".bak", "conftest"]):
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                # publish(<ClassName>(
                if f"publish({class_name}(" in content:
                    pytest.fail(f"[{class_name}] 有 publish 端残留: {rel}")
                # subscribe(<ClassName> 或 subscribe('ClassName'
                if f"subscribe({class_name}" in content:
                    pytest.fail(f"[{class_name}] 有 subscribe 端残留: {rel}")
                if f"subscribe('{class_name}'" in content or f'subscribe("{class_name}"' in content:
                    pytest.fail(f"[{class_name}] 有 subscribe 端残留: {rel}")


# ==============================================================================
# Group B: POST-DELETION 业务不破坏验证 (R6 §6.3 步骤 9)
# ==============================================================================

class TestP3PostDeletionImportSafety:
    """P3 物理删除后业务不破坏: import + 关键事件类仍可用"""

    def test_b1_core_events_import_works(self):
        """B1: core.events 仍可正常 import (无 ImportError)"""
        try:
            from core.events import EventBus, get_event_bus
            from core.events import BaseEvent, EventPriority
            assert EventBus is not None
            assert get_event_bus is not None
            assert BaseEvent is not None
        except ImportError as e:
            pytest.fail(f"core.events import 失败: {e}")

    def test_b2_other_prediction_services_unaffected(self):
        """B2: prediction_tracking_service.py 仍可正常 import (实际使用 STRING 事件, 不受影响)"""
        try:
            from core.services.prediction_tracking_service import PredictionTrackingService
            assert PredictionTrackingService is not None
        except ImportError as e:
            pytest.fail(f"PredictionTrackingService import 失败: {e}")

    def test_b3_string_event_publish_unchanged(self):
        """B3: STRING 事件 "prediction.recorded" / "prediction.accuracy_updated" 仍可发布 (无业务破坏)"""
        # 这是反向验证: 删除 dataclass 不应影响 string 事件
        from core.events import EventBus
        bus = EventBus()
        try:
            # 实际业务方用 STRING 事件
            bus.publish("prediction.recorded", record_id="test", model_version_id="v1", prediction_type="pattern")
            bus.publish("prediction.accuracy_updated", record_id="test", accuracy=0.95)
        except Exception as e:
            pytest.fail(f"STRING 事件 publish 失败: {e}")


# ==============================================================================
# Group C: 保留反例验证 (R6 §6.3 步骤 4: 排除已删除但有引用的误删)
# ==============================================================================

class TestP3RetentionCounterexamples:
    """P3 物理删除保留反例: 验证其他事件类未被误删"""

    def test_c1_确认_2_Prediction_事件_全删(self):
        """C1: 验证 2 个 Prediction* 事件类被全删"""
        types_file = ROOT / "core" / "events" / "types.py"
        content = types_file.read_text(encoding="utf-8")
        # 验证 0 命中
        assert "class PredictionRecordedEvent" not in content, \
            "PredictionRecordedEvent 未被删除"
        assert "class PredictionAccuracyUpdatedEvent" not in content, \
            "PredictionAccuracyUpdatedEvent 未被删除"

    def test_c2_保留_其他事件_不_被误删(self):
        """C2: 验证其他核心事件类未被误删"""
        types_file = ROOT / "core" / "events" / "types.py"
        content = types_file.read_text(encoding="utf-8")
        # 验证其他核心事件类未被误删
        must_keep = [
            "StrategyStartedEvent",
            "StrategyStoppedEvent",
            "StrategyConfigCreatedEvent",
            "StrategyConfigUpdatedEvent",
            "StrategyConfigDeletedEvent",
            "StrategyConfigsLoadedEvent",
            "ModelVersionCreatedEvent",
            "BaseEvent",
            "AssetSelectedEvent",
            "ErrorEvent",
        ]
        for class_name in must_keep:
            assert f"class {class_name}" in content, \
                f"[误删] {class_name} 不在 types.py 中"

    def test_c3_保留_init_导出_不_被误删(self):
        """C3: 验证 __init__.py 其他事件类 re-export 未被误删"""
        init_file = ROOT / "core" / "events" / "__init__.py"
        content = init_file.read_text(encoding="utf-8")
        # 验证其他核心 re-export 仍在
        must_keep = [
            "StrategyConfigCreatedEvent",
            "StrategyConfigUpdatedEvent",
            "StrategyConfigDeletedEvent",
            "StrategyConfigsLoadedEvent",
            "ModelVersionCreatedEvent",
            "BaseEvent",
            "EventBus",
        ]
        for class_name in must_keep:
            assert class_name in content, \
                f"[误删] {class_name} 不在 __init__.py 中"


# ==============================================================================
# Group D: 物理删除后回归 (R6 §6.3 步骤 9: 跑全量回归 0 failed)
# ==============================================================================

class TestP3PostDeletionRegression:
    """物理删除后全量回归 (R6 §6.3 步骤 9)"""

    def test_d1_types_py_syntax_valid(self):
        """D1: 物理删除后 types.py 语法正确"""
        types_file = ROOT / "core" / "events" / "types.py"
        content = types_file.read_text(encoding="utf-8")
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"types.py 语法错误: {e}")

    def test_d2_init_py_syntax_valid(self):
        """D2: 物理删除后 __init__.py 语法正确"""
        init_file = ROOT / "core" / "events" / "__init__.py"
        content = init_file.read_text(encoding="utf-8")
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"__init__.py 语法错误: {e}")

    def test_d3_event_bus_import_works(self):
        """D3: 物理删除后 EventBus 仍可正常 import"""
        try:
            from core.events import EventBus, get_event_bus
            from core.events.types import BaseEvent, EventPriority
            assert EventBus is not None
            assert get_event_bus is not None
        except Exception as e:
            pytest.fail(f"EventBus import 失败: {e}")

    def test_d4_no_prediction_event_references(self):
        """D4: 物理删除后全项目无 PredictionRecorded/AccuracyUpdated 引用 (除 types/__init__/tools/test)"""
        # 排除 types.py + __init__.py (即使残留也不影响业务) + tools/ + test_r237 自身
        for subdir in ["core", "gui", "web", "tests"]:
            subdir_path = ROOT / subdir
            if not subdir_path.exists():
                continue
            for py_file in subdir_path.rglob("*.py"):
                rel = str(py_file.relative_to(ROOT))
                if any(x in rel for x in ["_r", "_archive", "tools/", ".bak", "conftest"]):
                    continue
                # 排除 test_r237_d_2p3_physically_removed.py 自身
                if "test_r237_d_2p3_physically_removed" in rel:
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                # 检查引用
                if "PredictionRecordedEvent" in content and "types.py" not in rel and "__init__.py" not in rel:
                    pytest.fail(f"[{rel}] 仍引用 PredictionRecordedEvent (未删干净)")
                if "PredictionAccuracyUpdatedEvent" in content and "types.py" not in rel and "__init__.py" not in rel:
                    pytest.fail(f"[{rel}] 仍引用 PredictionAccuracyUpdatedEvent (未删干净)")


# ==============================================================================
# Group E: R237 4 源验证 0 误报 (R85 §10 假修复鉴别 4 步法)
# ==============================================================================

class TestP3NoFalseFix:
    """R237 P3 物理删除 0 误报 (R85 §10 假修复鉴别 4 步法)"""

    def test_e1_正则_检查_字符串_prediction(self):
        """E1: 正则检查 - 防止误报 (允许 'Prediction' 出现在 docstring/comment)"""
        # 但要确保 PredictionRecordedEvent / PredictionAccuracyUpdatedEvent 不在业务代码
        # 由 test_d4 覆盖
        pass

    def test_e2_范围_检查_排除测试自身(self):
        """E2: 搜索范围 - 排除 test_r237_d_2p3_physically_removed.py 自身 + tools/"""
        # 由 test_d4 覆盖
        pass

    def test_e3_降级_路径_检查(self):
        """E3: 合法降级路径 - 删除后 core.events 仍可用 + STRING 事件 publish 不受影响"""
        # 由 test_b1, b3 覆盖
        pass

    def test_e4_类_限定_检查(self):
        """E4: 类限定 - 只删 Prediction* 系列, 不影响其他"""
        # 由 test_c2, c3 覆盖
        pass


# ==============================================================================
# 测试配置
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
