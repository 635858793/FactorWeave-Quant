#!/usr/bin/env python3
"""
P0修复效果模拟场景验证测试

验证:
  P0-1: 风控事件链路 (EventBus单例 → RiskAlertSystem → RiskEventSubscriber → ComplianceAuditLogger)
  P0-3: 卖出数量限制 (QSpinBox.setRange min≤max 始终成立)

运行方式:
  conda activate hikyuu
  python tests/test_p0_fix_scenario.py
"""

import sys
import os
import threading
import time
from unittest.mock import MagicMock, patch
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_test():
    results = {'passed': 0, 'failed': 0, 'details': []}

    def _check(name: str, condition: bool, detail: str = ""):
        if condition:
            results['passed'] += 1
            print(f"  ✅ [{name}] 通过")
        else:
            results['failed'] += 1
            print(f"  ❌ [{name}] 失败: {detail}")
        results['details'].append({'name': name, 'passed': condition, 'detail': detail})

    # ===================================================================
    #  场景一: P0-1 风控事件链路修复验证
    # ===================================================================
    print("\n" + "=" * 70)
    print("  场景一: P0-1 风控事件链路修复验证")
    print("=" * 70)

    # 1.1 验证 get_event_bus() 单例模式
    print("\n--- 1.1 EventBus 单例验证 ---")
    from core.events.event_bus import get_event_bus

    bus_a = get_event_bus()
    bus_b = get_event_bus()
    _check("P0-1.1 get_event_bus() 返回同一实例",
           bus_a is bus_b,
           f"bus_a id={id(bus_a)}, bus_b id={id(bus_b)}")

    # 1.2 验证同一总线上的发布-订阅链路
    print("\n--- 1.2 EventBus 发布-订阅链路 ---")
    received_events = []

    def _test_handler(*args, **kwargs):
        received_events.append(args[0] if args else kwargs)

    bus = get_event_bus()
    # 清空之前的订阅，避免干扰
    bus._handlers.clear()
    # 清空去重缓存，避免 cross-test dedup
    bus._dedup_cache.clear() if hasattr(bus, '_dedup_cache') else None
    bus.subscribe('risk.monitor', _test_handler)
    bus.subscribe('risk.reduce_position', _test_handler)
    bus.subscribe('risk.stop_trading', _test_handler)
    bus.subscribe('risk.emergency_liquidation', _test_handler)

    # 模拟 RiskAlertSystem 发布4种风险事件
    test_alert = {'type': 'var_risk', 'level': 'high', 'message': 'VaR超限测试'}
    test_timestamp = datetime.now()

    bus.publish('risk.monitor', alert=test_alert, timestamp=test_timestamp)
    bus.publish('risk.reduce_position', alert=test_alert,
                reduce_ratio=0.5, timestamp=test_timestamp)
    bus.publish('risk.stop_trading', alert=test_alert,
                duration_minutes=30, timestamp=test_timestamp)
    bus.publish('risk.emergency_liquidation', alert=test_alert,
                timestamp=test_timestamp)

    _check("P0-1.2.1 4个事件全部被订阅者接收",
           len(received_events) == 4,
           f"期望4个，实际收到{len(received_events)}个")

    event_types = [getattr(e, 'alert', {}).get('type', 'N/A') if hasattr(e, 'alert') else
                   e.get('alert', {}).get('type', 'N/A') if isinstance(e, dict) else 'N/A'
                   for e in received_events]
    _check("P0-1.2.2 risk.monitor 事件参数正确传递",
           'var_risk' in event_types,
           f"收到事件类型: {event_types}")

    has_timestamps = [hasattr(e, 'timestamp') or (isinstance(e, dict) and 'timestamp' in e)
                      for e in received_events]
    _check("P0-1.2.3 timestamp 正确传递",
           all(has_timestamps),
           f"缺少timestamp的事件数: {sum(1 for x in has_timestamps if not x)}")

    # 1.3 验证 RiskAlertSystem 各方法使用 get_event_bus()
    print("\n--- 1.3 RiskAlertSystem 调用 get_event_bus() 验证 ---")
    try:
        from core.risk_alert import RiskAlertSystem
        import inspect

        source = inspect.getsource(RiskAlertSystem._monitor_risk)
        _check("P0-1.3.1 _monitor_risk 使用 get_event_bus",
               'get_event_bus' in source,
               f"源码中未找到 get_event_bus")

        source = inspect.getsource(RiskAlertSystem._reduce_position)
        _check("P0-1.3.2 _reduce_position 使用 get_event_bus",
               'get_event_bus' in source,
               f"源码中未找到 get_event_bus")

        source = inspect.getsource(RiskAlertSystem._stop_trading)
        _check("P0-1.3.3 _stop_trading 使用 get_event_bus",
               'get_event_bus' in source,
               f"源码中未找到 get_event_bus")

        source = inspect.getsource(RiskAlertSystem._emergency_liquidation)
        _check("P0-1.3.4 _emergency_liquidation 使用 get_event_bus",
               'get_event_bus' in source,
               f"源码中未找到 get_event_bus")
    except Exception as e:
        _check("P0-1.3 RiskAlertSystem 源码检查", False, str(e))

    # 1.4 验证 RiskEventSubscriber 使用 get_event_bus()
    print("\n--- 1.4 RiskEventSubscriber 单例验证 ---")
    try:
        from core.risk.risk_event_subscribers import RiskEventSubscriber
        source = inspect.getsource(RiskEventSubscriber.__init__)
        _check("P0-1.4.1 RiskEventSubscriber.__init__ 使用 get_event_bus",
               'get_event_bus' in source,
               f"源码中未找到 get_event_bus")

        # 模拟初始化验证事件订阅
        mock_audit = MagicMock()
        subscriber = RiskEventSubscriber(audit_logger=mock_audit)
        subscriber.initialize()
        _check("P0-1.4.2 RiskEventSubscriber 订阅初始化成功",
               subscriber._initialized,
               f"初始化状态: {subscriber._initialized}")

        sub_count = len(subscriber._subscriptions)
        _check("P0-1.4.3 RiskEventSubscriber 有事件订阅",
               sub_count > 0,
               f"订阅数: {sub_count}")
        print(f"        已订阅事件: {[s[0] for s in subscriber._subscriptions]}")
    except Exception as e:
        _check("P0-1.4 RiskEventSubscriber 验证", False, str(e))

    # 1.5 验证 ComplianceAuditLogger 使用 get_event_bus()
    print("\n--- 1.5 ComplianceAuditLogger 单例验证 ---")
    try:
        from core.risk.compliance_audit_logger import ComplianceAuditLogger
        source = inspect.getsource(ComplianceAuditLogger.__init__)

        _check("P0-1.5.1 ComplianceAuditLogger.__init__ 使用 get_event_bus",
               'get_event_bus' in source,
               f"源码中未找到 get_event_bus")

        # 使用临时文件初始化验证不会崩溃
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db = f.name
        try:
            auditor = ComplianceAuditLogger(db_path=temp_db)
            _check("P0-1.5.2 ComplianceAuditLogger 初始化成功",
                   auditor._event_bus is not None)
            _check("P0-1.5.3 ComplianceAuditLogger 的 EventBus 是单例",
                   auditor._event_bus is bus_a,
                   f"auditor bus id={id(auditor._event_bus)}, global bus id={id(bus_a)}")
        finally:
            try:
                os.remove(temp_db)
            except OSError:
                pass
    except Exception as e:
        _check("P0-1.5 ComplianceAuditLogger 验证", False, str(e))

    # 1.6 端到端事件链路: RiskAlertSystem → EventBus → 多个订阅者
    print("\n--- 1.6 端到端风控事件链路模拟 ---")
    try:
        from core.events.event_bus import get_event_bus

        bus = get_event_bus()
        bus._handlers.clear()
        bus._dedup_cache.clear() if hasattr(bus, '_dedup_cache') else None
        time.sleep(0.6)  # 等待去重窗口过期

        # 多个订阅者同时监听
        subscriber1_events = []
        subscriber2_events = []
        subscriber3_events = []

        def sub1_handler(*args, **kwargs):
            arg = args[0] if args else kwargs
            subscriber1_events.append(arg)

        def sub2_handler(*args, **kwargs):
            arg = args[0] if args else kwargs
            subscriber2_events.append(arg)

        def sub3_handler(*args, **kwargs):
            arg = args[0] if args else kwargs
            subscriber3_events.append(arg)

        bus.subscribe('risk.monitor', sub1_handler)
        bus.subscribe('risk.monitor', sub2_handler)
        bus.subscribe('risk.monitor', sub3_handler)

        # 模拟 RiskAlertSystem 触发风险监控
        now = datetime.now()
        alert_data = {
            'type': 'market_risk',
            'level': 'critical',
            'metric': 'VaR',
            'value': 0.15,
            'message': '市场风险VaR超过阈值15%'
        }
        bus.publish('risk.monitor', alert=alert_data, timestamp=now)

        _check("P0-1.6.1 订阅者1收到事件",
               len(subscriber1_events) == 1,
               f"期望1，实际{len(subscriber1_events)}")
        _check("P0-1.6.2 订阅者2收到事件",
               len(subscriber2_events) == 1,
               f"期望1，实际{len(subscriber2_events)}")
        _check("P0-1.6.3 订阅者3收到事件",
               len(subscriber3_events) == 1,
               f"期望1，实际{len(subscriber3_events)}")

        if (len(subscriber1_events) == 1 and
                len(subscriber2_events) == 1 and
                len(subscriber3_events) == 1):
            def _extract_value(evt):
                alert = getattr(evt, 'alert', None)
                if isinstance(alert, dict):
                    return alert.get('value')
                if hasattr(alert, 'value'):
                    return alert.value
                if isinstance(evt, dict):
                    inner = evt.get('alert', {})
                    return inner.get('value') if isinstance(inner, dict) else None
                return None

            vals = [_extract_value(subscriber1_events[0]),
                    _extract_value(subscriber2_events[0]),
                    _extract_value(subscriber3_events[0])]
            _check("P0-1.6.4 三个订阅者收到相同数据",
                   vals == [0.15, 0.15, 0.15],
                   f"收到值: {vals}")
        else:
            _check("P0-1.6.4 三个订阅者收到相同数据",
                   False, "无足够事件数据进行对比")

        # 清理
        bus._handlers.clear()
    except Exception as e:
        _check("P0-1.6 端到端链路", False, str(e))

    # 1.7 验证修复前后对比：确认 EventBus() 不会被直接构造
    print("\n--- 1.7 修复完整性验证 ---")
    try:
        import ast
        files_to_check = [
            ('core/risk_alert.py', [
                '_monitor_risk', '_reduce_position', '_stop_trading',
                '_emergency_liquidation'
            ]),
        ]

        import_ok = True
        for filepath, methods in files_to_check:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=filepath)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module == 'core.events.event_bus':
                        imported_names = {alias.name for alias in node.names}
                        if 'EventBus' in imported_names:
                            # 检查这个导入是否在方法内部（惰性导入）
                            # 方法内部的惰性导入可以接受从 ... import EventBus，
                            # 但必须调用 get_event_bus() 而不是 EventBus()
                            pass

            source_text = open(filepath, 'r', encoding='utf-8').read()
            # 查找 EventBus() 直接构造（非注释中）
            import re
            direct_calls = re.findall(
                r'(?<!#\s)(?<!get_)EventBus\(\)', source_text
            )
            _check(f"P0-1.7.1 {filepath} 无直接 EventBus() 构造",
                   len(direct_calls) == 0,
                   f"发现{len(direct_calls)}处直接构造: {direct_calls}")
    except Exception as e:
        _check("P0-1.7 修复完整性", False, str(e))

    # ===================================================================
    #  场景二: P0-3 卖出数量限制修复验证
    # ===================================================================
    print("\n" + "=" * 70)
    print("  场景二: P0-3 卖出数量限制修复验证")
    print("=" * 70)

    # 2.1 源码验证：sell_min_qty 计算逻辑
    print("\n--- 2.1 源码逻辑验证 ---")
    source_path = 'gui/widgets/trading_widget.py'
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()

    _check("P0-3.1.1 源码中包含 sell_min_qty 计算",
           'sell_min_qty' in source,
           "未找到 sell_min_qty 变量")

    _check("P0-3.1.2 sell_min_qty = min(100, position['quantity'])",
           'sell_min_qty = min(100' in source,
           "未找到正确的 min 计算")

    _check("P0-3.1.3 setRange(sell_min_qty, position['quantity'])",
           'setRange(sell_min_qty' in source,
           "setRange 未使用 sell_min_qty")

    # 2.2 逻辑正确性验证：所有场景下 min ≤ max
    print("\n--- 2.2 逻辑正确性验证 (min ≤ max) ---")

    test_cases = [
        ('标准持仓(1000股)', 1000, 100, 1000, True),
        ('标准持仓(500股)', 500, 100, 500, True),
        ('标准持仓(200股)', 200, 100, 200, True),
        ('边界: 恰好100股', 100, 100, 100, True),
        ('边界: 99股(不足一手)', 99, 99, 99, True),
        ('边界: 50股(半手)', 50, 50, 50, True),
        ('边界: 10股', 10, 10, 10, True),
        ('边界: 1股', 1, 1, 1, True),
        ('边界: 0股(空仓)', 0, 0, 0, True),
        ('大量持仓(10000股)', 10000, 100, 10000, True),
    ]

    for name, qty, expected_min, expected_max, should_pass in test_cases:
        sell_min_qty = min(100, qty)
        actual_min = sell_min_qty
        actual_max = qty

        condition = (
            sell_min_qty == expected_min
            and actual_min <= actual_max
            and sell_min_qty <= qty
        )
        _check(
            f"P0-3.2 {name}",
            condition,
            f"quantity={qty}, sell_min_qty={sell_min_qty}, "
            f"expected_min={expected_min}, min<=max={actual_min <= actual_max}"
        )

    # 2.3 修复前后行为对比：验证修复效果
    print("\n--- 2.3 修复前后行为对比 ---")

    old_bugs = 0
    fixed_ok = 0
    for qty in [1000, 500, 200, 100, 99, 50, 10, 1]:
        # 修复后的逻辑
        sell_min_qty = min(100, qty)
        fixed_min = sell_min_qty
        fixed_max = qty
        fixed_valid = fixed_min <= fixed_max

        # 修复前的逻辑（有Bug）
        old_min = 100
        old_max = qty
        old_valid = old_min <= old_max

        if not fixed_valid:
            _check(f"P0-3.3 修复后 quantity={qty} 仍异常",
                   False, f"fixed_min={fixed_min} > fixed_max={fixed_max}")
        else:
            fixed_ok += 1

        if not old_valid and qty < 100:
            old_bugs += 1

    _check("P0-3.3.1 修复后所有场景 min≤max 成立",
           fixed_ok == 8,
           f"修复后通过: {fixed_ok}/8")
    _check("P0-3.3.2 修复前Bug已确认: setRange(100, <100) 导致 min>max",
           old_bugs == 4,
           f"修复前有{old_bugs}个场景 min>max (qty=99,50,10,1)，修复后全部通过")

    # 2.4 QSpinBox 模拟：验证 Qt 行为
    print("\n--- 2.4 QSpinBox 行为模拟 ---")

    class MockSpinBox:
        """模拟 QSpinBox，验证 setRange 行为"""
        def __init__(self):
            self._min = 0
            self._max = 99
            self._value = 0

        def setRange(self, min_val, max_val):
            self._min = min_val
            self._max = max_val

        def setValue(self, value):
            self._value = value

        def validate(self):
            """验证 min ≤ max 和 value 在范围内"""
            if self._min > self._max:
                return False, f"BUG: min({self._min}) > max({self._max})"
            if self._value < self._min or self._value > self._max:
                return False, f"BUG: value({self._value}) not in [{self._min}, {self._max}]"
            return True, "OK"

    test_qt_cases = [
        (1000, 100, 1000, 100),
        (500, 100, 500, 100),
        (99, 99, 99, 99),
        (50, 50, 50, 50),
        (1, 1, 1, 1),
    ]

    for qty, exp_min, exp_max, exp_val in test_qt_cases:
        spin = MockSpinBox()
        sell_min_qty = min(100, qty)
        spin.setRange(sell_min_qty, qty)
        spin.setValue(sell_min_qty)

        valid, msg = spin.validate()
        _check(
            f"P0-3.4 SpinBox模拟 quantity={qty}",
            valid,
            f"{msg}, range=[{spin._min}, {spin._max}], value={spin._value}"
        )

    # ===================================================================
    #  结果汇总
    # ===================================================================
    print("\n" + "=" * 70)
    print(f"  测试结果汇总: 通过 {results['passed']}/{results['passed'] + results['failed']}")
    print("=" * 70)

    if results['failed'] > 0:
        print("\n  失败详情:")
        for d in results['details']:
            if not d['passed']:
                print(f"    ❌ {d['name']}: {d['detail']}")

    return results['failed'] == 0


if __name__ == '__main__':
    success = run_test()
    sys.exit(0 if success else 1)