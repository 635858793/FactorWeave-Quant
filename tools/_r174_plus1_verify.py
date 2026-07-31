"""R174 阶段 1 R+1 round 物理验证脚本 (R104 §12 铁律 #1)

执行: python tools/_r174_plus1_verify.py
"""
import ast
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    print("=" * 80)
    print("R174 阶段 1 R+1 round 物理验证 (R104 §12 铁律 #1 + R85 假修复鉴别 4 步法)")
    print("=" * 80)

    # 验证 1: types.py 5 EventType 枚举
    print("\n[R+1 round 验证 1] 5 EventType 枚举 (core/events/types.py)")
    types_path = PROJECT_ROOT / "core" / "events" / "types.py"
    source = types_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    expected_enums = {
        "FREE_STOCKDB_CONNECTED": "free_stockdb.connected",
        "FREE_STOCKDB_DISCONNECTED": "free_stockdb.disconnected",
        "FREE_STOCKDB_HEALTH_CHANGED": "free_stockdb.health.changed",
        "FREE_STOCKDB_ERROR": "free_stockdb.error",
        "BETTAFISH_SENTIMENT_ANALYSIS_COMPLETED": "bettafish.sentiment.analysis.completed",
    }
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "EventType":
            for member in node.body:
                if isinstance(member, ast.Assign) and isinstance(member.value, ast.Constant):
                    for target in member.targets:
                        if isinstance(target, ast.Name) and target.id in expected_enums:
                            found[target.id] = (member.value.value, target.lineno)
    for enum_name, (dotted_value, lineno) in found.items():
        print(f"  L{lineno} {enum_name} = {dotted_value!r}")
    print(f"  总计: {len(found)}/5 枚举 {'PASS' if len(found) == 5 else 'FAIL'}")

    # 验证 2: types.py 5 BaseEvent 子类
    print("\n[R+1 round 验证 2] 5 BaseEvent 子类 (core/events/types.py)")
    expected_classes = [
        "FreeStockDBConnectedEvent",
        "FreeStockDBDisconnectedEvent",
        "FreeStockDBHealthChangedEvent",
        "FreeStockDBErrorEvent",
        "SentimentAnalysisCompletedEvent",
    ]
    found_classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in expected_classes:
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseEvent":
                    found_classes.append((node.name, node.lineno))
    for cls_name, lineno in found_classes:
        print(f"  L{lineno} {cls_name}(BaseEvent)")
    print(f"  总计: {len(found_classes)}/5 BaseEvent 子类 {'PASS' if len(found_classes) == 5 else 'FAIL'}")

    # 验证 3: event_helper.py ImportError 修复 (用 AST 检测实际 import 语句)
    print("\n[R+1 round 验证 3] event_helper.py ImportError 修复")
    helper_path = PROJECT_ROOT / "plugins" / "data_sources" / "stock" / "free_stockdb" / "event_helper.py"
    helper_source = helper_path.read_text(encoding="utf-8")
    helper_tree = ast.parse(helper_source)
    has_bad_import = False
    has_good_import = False
    for node in ast.walk(helper_tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "core.events.event_types":
                has_bad_import = True
                print(f"  L{node.lineno} 仍从 core.events.event_types 导入 (FAIL)")
            if node.module == "core.events.types":
                for alias in node.names:
                    if alias.name in ("EventType", "register_event_type"):
                        has_good_import = True
    if not has_bad_import:
        print("  [OK] 已移除 core.events.event_types 导入")
    if has_good_import:
        print("  [OK] 已使用 core.events.types 标准路径")
    print(f"  ImportError 修复: {'PASS' if (not has_bad_import and has_good_import) else 'FAIL'}")

    # 验证 4: order_fill_saved 订阅 + handler
    print("\n[R+1 round 验证 4] order_fill_saved 订阅 + handler (core/risk/risk_event_subscribers.py)")
    sub_path = PROJECT_ROOT / "core" / "risk" / "risk_event_subscribers.py"
    sub_source = sub_path.read_text(encoding="utf-8")
    sub_tree = ast.parse(sub_source)
    has_subscribe = False
    has_handler = False
    # 检测订阅 (AST: 字符串字面量 'order_fill_saved' 在任何位置出现, 与变量名 order_fill_saved 一起)
    for node in ast.walk(sub_tree):
        if isinstance(node, ast.Constant) and node.value == "order_fill_saved":
            has_subscribe = True
            print(f"  L{node.lineno} 字符串字面量 'order_fill_saved' (订阅证据)")
            break
    # 检测 handler
    for node in ast.walk(sub_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_order_fill_saved":
            has_handler = True
            print(f"  L{node.lineno} _handle_order_fill_saved handler 已实装")
    print(f"  order_fill_saved 订阅+handler: {'PASS' if (has_subscribe and has_handler) else 'FAIL'}")

    # 验证 5: free_stockdb.connected/disconnected 订阅 + handler
    print("\n[R+1 round 验证 5] free_stockdb.connected/disconnected 订阅 (gui/widgets/data_source_status_widget.py)")
    widget_path = PROJECT_ROOT / "gui" / "widgets" / "data_source_status_widget.py"
    widget_source = widget_path.read_text(encoding="utf-8")
    widget_tree = ast.parse(widget_source)
    has_connected_subscribe = False
    has_disconnected_subscribe = False
    has_connected_handler = False
    has_disconnected_handler = False
    for node in ast.walk(widget_tree):
        if isinstance(node, ast.Constant):
            if node.value == "free_stockdb.connected":
                has_connected_subscribe = True
                print(f"  L{node.lineno} 字符串字面量 'free_stockdb.connected' (订阅证据)")
            if node.value == "free_stockdb.disconnected":
                has_disconnected_subscribe = True
                print(f"  L{node.lineno} 字符串字面量 'free_stockdb.disconnected' (订阅证据)")
    for node in ast.walk(widget_tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == "_on_free_stockdb_connected":
                has_connected_handler = True
                print(f"  L{node.lineno} _on_free_stockdb_connected handler 已实装")
            if node.name == "_on_free_stockdb_disconnected":
                has_disconnected_handler = True
                print(f"  L{node.lineno} _on_free_stockdb_disconnected handler 已实装")
    print(
        f"  free_stockdb.connected 订阅+handler: "
        f"{'PASS' if (has_connected_subscribe and has_connected_handler) else 'FAIL'}"
    )
    print(
        f"  free_stockdb.disconnected 订阅+handler: "
        f"{'PASS' if (has_disconnected_subscribe and has_disconnected_handler) else 'FAIL'}"
    )

    # 验证 6: bettafish.sentiment 订阅 (R173 已实装, 保留验证)
    print("\n[R+1 round 验证 6] bettafish.sentiment.analysis.completed 订阅 (R173 已实装)")
    has_bettafish_subscribe = False
    has_bettafish_handler = False
    for node in ast.walk(sub_tree):
        if isinstance(node, ast.Constant) and node.value == "bettafish.sentiment.analysis.completed":
            has_bettafish_subscribe = True
            print(f"  L{node.lineno} 字符串字面量 'bettafish.sentiment.analysis.completed' (订阅证据)")
            break
    for node in ast.walk(sub_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_bettafish_sentiment_analysis_completed":
            has_bettafish_handler = True
            print(f"  L{node.lineno} _handle_bettafish_sentiment_analysis_completed handler 已实装 (R173)")
    print(
        f"  bettafish 订阅+handler: {'PASS' if (has_bettafish_subscribe and has_bettafish_handler) else 'FAIL'}"
    )

    # 验证 7: 实际 import 测试
    print("\n[R+1 round 验证 7] 实际 import 测试")
    try:
        from core.events.types import (
            EventType,
            FreeStockDBConnectedEvent,
            FreeStockDBDisconnectedEvent,
            FreeStockDBHealthChangedEvent,
            FreeStockDBErrorEvent,
            SentimentAnalysisCompletedEvent,
        )
        print("  [OK] 5 BaseEvent 子类可导入")
        print(f"  [OK] EventType.FREE_STOCKDB_CONNECTED = {EventType.FREE_STOCKDB_CONNECTED.value!r}")
    except ImportError as e:
        print(f"  [FAIL] Import 测试失败: {e}")

    print()
    print("=" * 80)
    print("R+1 round 物理验证完成 (R104 §12 铁律 #1 100% 应用)")
    print("=" * 80)


if __name__ == "__main__":
    main()
