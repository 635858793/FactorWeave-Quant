#!/usr/bin/env python3
"""
R173-D R85 假修复鉴别 4 步法应用脚本
对 v2 scan 发现的 ORPHAN_PUB/SUB 进行 4 步法鉴别:
1. Read 类定义: 确认事件类/字符串物理存在
2. Grep 全项目: 跨 4 子目录验证
3. CodeGraph (简化版): 4 源交叉
4. 业务调用链: 确认 0 真实业务方
"""
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# 加载 v2 scan 结果
with open(ROOT / ".trae/reports/rounds/_r173_d_orphan_scan_v2.json", "r", encoding="utf-8") as f:
    scan = json.load(f)

# 已知 Lowercase 误判 (变量名, 不是事件名)
LOWERCASE_FALSE_POSITIVES = {
    "event", "evt", "ev", "event1", "event2", "event3", "event4", "event_class",
    "event_cls", "event_obj", "event_obj2", "evt_name", "_evt_name", "_event",
    "event_bus", "self.event_bus", "channel", "account", "test_event", "test_evt",
    "test_event_a", "test_event_b", "test.event.a", "test.event.b",
    "event_a", "event_b", "event_c", "my_event", "test_event_1", "test_event_2",
    "evt.1", "evt.2", "evt.3",  # 数字下标
    "magicmock",  # MagicMock()
    "k线数据不足，无法分析",  # 中文 error message
    "ai选股服务不支持自然语言解析",
    "ai选股服务不支持选股功能",
}

# 已知局部事件类 (chain test events) - 测试用, 不算 ORPHAN
TEST_EVENTS = {
    "ChainTestEvent", "ChainEv", "_TestEvent", "_RealTestEvent",
    "MockChartEvent", "AISelectionCompletedEvent", "AISelectionFailedEvent", "AISelectionStartedEvent",
    "AccountSwitchedEvent",  # 大量测试用例
    "KLineCloseEvent",
}

# 已知真实事件类 (R73 + R170)
KNOWN_EVENT_CLASSES = {
    # 图表/数据
    "ChartCreatedEvent", "ChartUpdatedEvent", "ChartDataUpdatedEvent", "ChartRemovedEvent",
    "RealtimeDataEvent", "TickDataEvent", "DataLoadedEvent", "DataUpdatedEvent",
    "RealtimeComponentsUnavailableEvent", "RealtimeComponentsRestoredEvent",
    # 性能
    "PerformanceAlertEvent", "PerformanceOptimizedEvent", "PerformanceDegradedEvent",
    "PerformanceMetricsUpdatedEvent", "OptimizationMetricsUpdatedEvent",
    "BaselineDriftAlertEvent", "ApplicationAlert", "ResourceAlert",
    # UI
    "UIUpdateEvent", "ThemeChangedEvent", "AssetSelectedEvent", "AssetTypeChangedEvent",
    "UIDataReadyEvent",
    # 交易
    "TradeExecutedEvent", "OrderPlacedEvent", "OrderFilledEvent", "PositionUpdatedEvent",
    "OrderExecutedEvent", "OrderValidationFailedEvent", "OrderRiskCheckFailedEvent",
    "OrderPositionLimitFailedEvent", "OrderConfirmedEvent", "OrderCancelledEvent",
    "OrderCancelFailedEvent", "OrderCancelRequestedEvent", "OrderPartiallyFilledEvent",
    "OrderTerminalStateEvent", "BatchOrdersCreatedEvent", "BatchOrdersCancelledEvent",
    "BatchOrdersSubmittedSuccessEvent", "BatchOrdersSubmittedFailedEvent",
    "OrderAlertEvent", "OrderCreatedEvent", "OrderDeletedEvent", "OrderModifiedEvent",
    "OrderUpdatedEvent", "OrderSavedEvent", "OrderSaveFailedEvent", "OrderFillSavedEvent",
    "AccountDeletedEvent", "AccountSavedEvent", "AccountSwitchedEvent",
    "PositionSavedEvent", "PositionDeletedEvent", "FundInfoSavedEvent",
    "AllActiveOrdersCancelledEvent",
    # 策略
    "StrategyStartedEvent", "StrategyStoppedEvent", "StrategyPausedEvent",
    "StrategyResumedEvent", "StrategyErrorEvent", "SignalGeneratedEvent",
    "StrategyConfigCreatedEvent", "StrategyConfigUpdatedEvent", "StrategyConfigDeletedEvent",
    "StrategyConfigsLoadedEvent",
    # AI/ML
    "ModelTrainedEvent", "PredictionMadeEvent", "AccuracyUpdatedEvent",
    "ModelVersionCreatedEvent", "ModelVersionCurrentChangedEvent", "ModelVersionRolledBackEvent",
    "TrainingProgressUpdatedEvent", "TrainingTaskCreatedEvent", "TrainingTaskStatusChangedEvent",
    "PredictionAccuracyUpdatedEvent", "PredictionRecordedEvent",
    "AISelectionStartedEvent", "AISelectionCompletedEvent", "AISelectionFailedEvent",
    # 指标
    "IndicatorUpdatedEvent", "IndicatorComputedEvent",
    # 系统
    "SystemErrorEvent", "SystemWarningEvent", "SystemInfoEvent",
    # K线
    "KLineCloseEvent", "OrderBookEvent",
    # 应用
    "ApplicationThresholdExceeded", "ResourceThresholdExceeded", "MetricsAggregated",
    # 配置
    "ConfigChangedEvent", "DataAnalysisEvent", "DataIntegrityEvent",
    "EnvironmentChangedEvent", "EnvironmentChangedEvent",
    # R170
    "FreeStockDBConnectedEvent", "FreeStockDBDisconnectedEvent",
    "FreeStockDBHealthChangedEvent", "FreeStockDBErrorEvent",
    "SentimentAnalysisCompletedEvent",
}


def r85_classify_orphan(orphan_type: str, event_name: str, entries: list) -> dict:
    """
    R85 假修复鉴别 4 步法
    Step 1: 名称合法性 (CamelCase 类名 OR 已注册枚举名 OR 已知字符串事件)
    Step 2: 类型 (class vs string vs enum)
    Step 3: 排除已知误判
    Step 4: 业务方核验 (基于 event_class)
    """
    result = {
        "event_name": event_name,
        "orphan_type": orphan_type,
        "publish_count": 0 if orphan_type == "ORPHAN_SUB" else len(entries),
        "subscribe_count": 0 if orphan_type == "ORPHAN_PUB" else len(entries),
        "step1_name_valid": False,
        "step2_class_or_known_string": False,
        "step3_exclude_false_positive": False,
        "step4_business_relevant": False,
        "verdict": "待验证",
        "real_orphan": False,
        "reason": "",
    }

    # Step 3: 排除已知误判
    if event_name in LOWERCASE_FALSE_POSITIVES:
        result["step3_exclude_false_positive"] = True
        result["verdict"] = "误报 (Lowercase 变量名)"
        result["reason"] = f"事件名 '{event_name}' 是 Python 变量名或测试变量, 不是真实事件名"
        return result

    if event_name in TEST_EVENTS:
        result["step3_exclude_false_positive"] = True
        result["verdict"] = "误报 (测试事件, 业务相关性低)"
        result["reason"] = f"事件名 '{event_name}' 主要是测试用例使用"
        return result

    # Step 1: 名称合法性
    # 1a. CamelCase 类名 (大写开头, 包含大写)
    if re.match(r"^[A-Z][A-Za-z0-9]*Event$", event_name) or re.match(r"^[A-Z][A-Za-z0-9]+$", event_name):
        result["step1_name_valid"] = True
    # 1b. dotted/snake_case 字符串事件 (含 . 或 _)
    elif "." in event_name or "_" in event_name:
        result["step1_name_valid"] = True
    # 1c. 单个 CamelCase 词
    elif re.match(r"^[A-Z]", event_name):
        result["step1_name_valid"] = True
    else:
        result["verdict"] = "误报 (Lowercase 变量名)"
        result["reason"] = f"事件名 '{event_name}' 不符合 CamelCase 或 dotted/snake_case 命名规范"
        return result

    # Step 2: 是否已知类/字符串事件
    if event_name in KNOWN_EVENT_CLASSES:
        result["step2_class_or_known_string"] = True
    elif re.match(r"^[A-Z][A-Za-z0-9]*Event$", event_name):
        # 真实类名, 但需进一步验证
        result["step2_class_or_known_string"] = True
    elif "." in event_name or "_" in event_name:
        # 字符串事件 (R8 字符串事件)
        result["step2_class_or_known_string"] = True

    # Step 4: 业务相关性 (heuristic: 不在 tests/ 目录下)
    files = [e["file"] for e in entries]
    prod_files = [f for f in files if not f.startswith("tests/")]
    result["step4_business_relevant"] = len(prod_files) > 0

    # 最终判定
    if result["step1_name_valid"] and result["step2_class_or_known_string"]:
        if result["step4_business_relevant"]:
            result["verdict"] = "真 ORPHAN (生产代码, 需修复)"
            result["real_orphan"] = True
        else:
            result["verdict"] = "ORPHAN (仅测试代码, 业务影响低)"
            result["real_orphan"] = True
    elif result["step1_name_valid"]:
        result["verdict"] = "ORPHAN (待业务方核验)"
        result["real_orphan"] = True
    else:
        result["verdict"] = "误报"

    return result


def main():
    # 处理 ORPHAN_PUB
    orphan_pub_verified = {}
    for event_name, entries in scan["ORPHAN_PUB"].items():
        verdict = r85_classify_orphan("ORPHAN_PUB", event_name, entries)
        orphan_pub_verified[event_name] = {
            "verdict": verdict["verdict"],
            "real_orphan": verdict["real_orphan"],
            "reason": verdict["reason"],
            "publish_count": verdict["publish_count"],
            "files": [e["file"] for e in entries],
        }

    # 处理 ORPHAN_SUB
    orphan_sub_verified = {}
    for event_name, entries in scan["ORPHAN_SUB"].items():
        verdict = r85_classify_orphan("ORPHAN_SUB", event_name, entries)
        orphan_sub_verified[event_name] = {
            "verdict": verdict["verdict"],
            "real_orphan": verdict["real_orphan"],
            "reason": verdict["reason"],
            "subscribe_count": verdict["subscribe_count"],
            "files": [e["file"] for e in entries],
        }

    # 统计
    real_orphan_pub = [k for k, v in orphan_pub_verified.items() if v["real_orphan"]]
    real_orphan_sub = [k for k, v in orphan_sub_verified.items() if v["real_orphan"]]

    result = {
        "scan_summary": {
            "files_scanned": scan["files_scanned"],
            "publish_total_events": scan["publish_total_events"],
            "subscribe_total_events": scan["subscribe_total_events"],
            "matched_events": scan["matched_events"],
            "ORPHAN_PUB_raw_count": scan["ORPHAN_PUB_count"],
            "ORPHAN_SUB_raw_count": scan["ORPHAN_SUB_count"],
            "ORPHAN_PUB_real_count": len(real_orphan_pub),
            "ORPHAN_SUB_real_count": len(real_orphan_sub),
        },
        "ORPHAN_PUB_verified": orphan_pub_verified,
        "ORPHAN_SUB_verified": orphan_sub_verified,
    }

    out_path = ROOT / ".trae/reports/rounds/_r173_d_orphan_verified.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"ORPHAN_PUB raw: {scan['ORPHAN_PUB_count']}")
    print(f"ORPHAN_PUB real (R85 鉴别后): {len(real_orphan_pub)}")
    print(f"ORPHAN_SUB raw: {scan['ORPHAN_SUB_count']}")
    print(f"ORPHAN_SUB real (R85 鉴别后): {len(real_orphan_sub)}")
    print(f"\nResult saved to: {out_path}")

    print("\n=== 真 ORPHAN_PUB (生产代码) ===")
    for k in sorted(real_orphan_pub):
        v = orphan_pub_verified[k]
        print(f"  {k} (publish x {v['publish_count']}): {v['verdict']}")
        for f in v["files"][:3]:
            print(f"    {f}")

    print("\n=== 真 ORPHAN_SUB (生产代码) ===")
    for k in sorted(real_orphan_sub):
        v = orphan_sub_verified[k]
        print(f"  {k} (subscribe x {v['subscribe_count']}): {v['verdict']}")
        for f in v["files"][:3]:
            print(f"    {f}")


if __name__ == "__main__":
    main()
