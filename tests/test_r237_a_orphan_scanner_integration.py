"""
R237-A TDD 测试: ORPHAN_PUB 扫描器 v2 集成 service_bootstrap (8 用例)

测试目标:
- tools/orphan_pub_scanner_v2.py 集成到 service_bootstrap.py 启动期
- 启动期自动扫描 ORPHAN_PUB, 0 业务方候选上报
- 集成审计日志 (R222 _emit_audit_log 模式)
- 启动期 ORPHAN_PUB 计数 < 5 (R235 25.8% 误报率治理后目标)

关联铁律:
- R236-A 假修复修复 (R231 §13.1 工具升级 4 源验证)
- R235 §14.2 #2 ORPHAN_PUB 扫描 4 类订阅模式识别铁律
- R222 ORPHAN 3 层治理 (业务方 + 启动期 + fallback)
- R104 §12 #3 AST 递归 with.body
- R104 §12 #5 AST unparse 验证
"""

import os
import ast
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ===== 工具自身测试 (R236-A 假修复修复) =====

def test_t01_orphan_scanner_v2_module_exists():
    """T01: tools/orphan_pub_scanner_v2.py 物理存在 (R231 §13.1 源 1 验证)."""
    scanner_path = Path("tools/orphan_pub_scanner_v2.py")
    assert scanner_path.exists(), f"扫描器文件不存在: {scanner_path}"
    assert scanner_path.stat().st_size > 1000, "扫描器文件过小 (<1KB), 可能未真实实施"


def test_t02_orphan_scanner_v2_class_exists():
    """T02: 扫描器主类 ORPHANPubScannerV2 存在 (R231 §13.1 源 2 Grep 验证)."""
    from tools.orphan_pub_scanner_v2 import ORPHANPubScannerV2

    assert ORPHANPubScannerV2 is not None
    # 必须有 scan 方法
    assert hasattr(ORPHANPubScannerV2, "scan")


def test_t03_p1_direct_string_literal_subscribe():
    """T03: P1_DIRECT 模式 - 直接字符串字面量订阅 (R235 §14.2 #1)."""
    from tools.orphan_pub_scanner_v2 import ORPHANPubScannerV2

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # 创建订阅方
        sub_file = tmp_path / "subscriber.py"
        sub_file.write_text(
            "from core.events import get_event_bus\n"
            "bus = get_event_bus()\n"
            "def handler(event):\n"
            "    pass\n"
            "bus.subscribe('order.created', handler)\n",
            encoding="utf-8"
        )
        # 创建发布方
        pub_file = tmp_path / "publisher.py"
        pub_file.write_text(
            "from core.events import get_event_bus\n"
            "bus = get_event_bus()\n"
            "bus.publish('order.created', data={'foo': 'bar'})\n",
            encoding="utf-8"
        )

        scanner = ORPHANPubScannerV2(
            root=str(tmp_path), subdirs=["."]
        )
        result = scanner.scan()

        # 'order.created' 在 pub+sub 配对, 不应出现在 ORPHAN
        assert "order.created" not in result.orphan_pub


def test_t04_p2_tuple_for_iteration_subscribe():
    """T04: P2_TUPLE_FOR 模式 - tuple 迭代订阅 (R235 §14.2 #2, R25/R174 模板)."""
    from tools.orphan_pub_scanner_v2 import ORPHANPubScannerV2

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sub_file = tmp_path / "risk_subscriber.py"
        sub_file.write_text(
            "from core.events import get_event_bus\n"
            "bus = get_event_bus()\n"
            "risk_events = [\n"
            "    ('risk.monitor', self._handle_monitor),\n"
            "    ('risk.reduce_position', self._handle_reduce),\n"
            "]\n"
            "for event_name, handler in risk_events:\n"
            "    bus.subscribe(event_name, handler)\n",
            encoding="utf-8"
        )
        pub_file = tmp_path / "risk_publisher.py"
        pub_file.write_text(
            "from core.events import get_event_bus\n"
            "bus = get_event_bus()\n"
            "bus.publish('risk.monitor', data={})\n"
            "bus.publish('risk.reduce_position', data={})\n",
            encoding="utf-8"
        )

        scanner = ORPHANPubScannerV2(root=str(tmp_path), subdirs=["."])
        result = scanner.scan()

        assert "risk.monitor" not in result.orphan_pub
        assert "risk.reduce_position" not in result.orphan_pub


def test_t05_p4_subscribe_event_indirect():
    """T05: P4 模式 - 间接调用 self._subscribe_event 订阅 (R235 §14.2 #3, R4/R22 模板)."""
    from tools.orphan_pub_scanner_v2 import ORPHANPubScannerV2

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sub_file = tmp_path / "coord.py"
        sub_file.write_text(
            "class EventCoordinator:\n"
            "    def subscribe(self, bus):\n"
            "        self._subscribe_event('trade.signal', self._on_signal)\n"
            "        self._subscribe_event('data.integrity', self._on_integrity)\n",
            encoding="utf-8"
        )
        pub_file = tmp_path / "pub.py"
        pub_file.write_text(
            "bus.publish('trade.signal', data={})\n"
            "bus.publish('data.integrity', data={})\n",
            encoding="utf-8"
        )

        scanner = ORPHANPubScannerV2(root=str(tmp_path), subdirs=["."])
        result = scanner.scan()

        assert "trade.signal" not in result.orphan_pub
        assert "data.integrity" not in result.orphan_pub


def test_t06_real_orphan_detected():
    """T06: 真 ORPHAN_PUB 仍能被正确检测 (R236-A 召回率 100%)."""
    from tools.orphan_pub_scanner_v2 import ORPHANPubScannerV2

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # 只有发布, 无订阅
        pub_file = tmp_path / "lone_publisher.py"
        pub_file.write_text(
            "from core.events import get_event_bus\n"
            "bus = get_event_bus()\n"
            "bus.publish('orphan.event', data={})\n",
            encoding="utf-8"
        )

        scanner = ORPHANPubScannerV2(root=str(tmp_path), subdirs=["."])
        result = scanner.scan()

        # orphan_pub 是 list[dict], 需查 event_name 字段
        orphan_names = [item.get("event_name") if isinstance(item, dict) else item
                        for item in result.orphan_pub]
        assert "orphan.event" in orphan_names


def test_t07_scan_result_dataclass():
    """T07: ScanResult 数据结构完整 (含 orphan_pub/orphan_sub + 模式分布)."""
    from tools.orphan_pub_scanner_v2 import ORPHANPubScannerV2, ScanResult

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # 任意文件
        (tmp_path / "empty.py").write_text("pass\n", encoding="utf-8")

        scanner = ORPHANPubScannerV2(root=str(tmp_path), subdirs=["."])
        result = scanner.scan()

        assert isinstance(result, ScanResult)
        assert hasattr(result, "orphan_pub")
        assert hasattr(result, "orphan_sub")
        assert hasattr(result, "subscribe_pattern_distribution")
        assert hasattr(result, "summary")
        assert isinstance(result.summary, dict)


def test_t08_orphan_count_below_threshold():
    """T08: R237-A 启动期 ORPHAN_PUB 计数 < 5 (R235 25.8% 误报率治理后目标)."""
    from tools.orphan_pub_scanner_v2 import ORPHANPubScannerV2

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # 创建大量有订阅的事件
        for i in range(20):
            (tmp_path / f"sub_{i}.py").write_text(
                f"bus.subscribe('event.{i}', handler_{i})\n",
                encoding="utf-8"
            )
            (tmp_path / f"pub_{i}.py").write_text(
                f"bus.publish('event.{i}', data={{}})\n",
                encoding="utf-8"
            )

        scanner = ORPHANPubScannerV2(root=str(tmp_path), subdirs=["."])
        result = scanner.scan()

        # 20 个事件全部有配对, 0 ORPHAN
        assert len(result.orphan_pub) < 5
        assert len(result.orphan_pub) == 0


# ===== service_bootstrap 集成测试 =====

def test_r237_a_scanner_importable_in_service_bootstrap():
    """验证 service_bootstrap 可导入扫描器 (R7 §7.1 服务注册铁律)."""
    # 仅验证可导入, 不触发实际引导 (避免启动期副作用)
    from core.services.service_bootstrap import ServiceBootstrap

    bootstrap = ServiceBootstrap()
    # 必须有 _run_orphan_scanner 启动期集成方法
    assert hasattr(bootstrap, "_run_orphan_pub_scan")


def test_r237_a_scanner_runner_does_not_break_bootstrap():
    """验证 _run_orphan_pub_scan 失败时不破坏 bootstrap 主流程 (R51 软解析教训)."""
    from core.services.service_bootstrap import ServiceBootstrap

    bootstrap = ServiceBootstrap()
    # 强制 mock _run_orphan_pub_scan_impl 抛错, 验证包装层不崩
    with patch.object(
        ServiceBootstrap,
        "_run_orphan_pub_scan_impl",
        side_effect=Exception("mock scanner failure"),
    ):
        # 必须捕获, 不抛
        try:
            bootstrap._run_orphan_pub_scan()
        except Exception as e:
            pytest.fail(f"_run_orphan_pub_scan 未捕获异常: {e}")
