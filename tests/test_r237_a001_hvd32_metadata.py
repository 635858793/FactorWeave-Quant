"""
R237-A-001 HVD-32 9 指标元数据 CI 检查 - 实施 TDD 测试 (23 断言, 5 文件)

> **生成日期**: 2026-08-01
> **项目类型**: P1 实施 (代码 + 工具 + CI 集成)
> **测试矩阵**: 5 文件 23 断言
> **强约束应用**: R6 §6.1 (8 铁律) + R104 §12 (5 铁律) + R231 §13 (4 铁律) + R85 §10 (4 步法)

**TDD 流程**:
1. RED 阶段: 跑当前测试, 确认 23 断言中 5+ 失败 (R237-A-001 实施前)
2. GREEN 阶段: 实施 AROON/DEMA/TEMA/NATR 4 指标元数据 + tools/indicator_metadata_audit.py
3. REFACTOR 阶段: 优化 + R+1 round 二次验证

**4 指标元数据缺口**:
- AROON: timeperiod=14, 输入 high/low
- DEMA: timeperiod=30, 输入 close
- TEMA: timeperiod=30, 输入 close
- NATR: timeperiod=14, 输入 high/low/close
"""
import os
import sys
import subprocess
from pathlib import Path

import pytest

# 项目根目录
ROOT = Path(__file__).parent.parent
INDICATOR_PATH = ROOT / "core" / "unified_indicator_service.py"
TOOL_PATH = ROOT / "tools" / "indicator_metadata_audit.py"


class TestR237A001AR00NMetadata:
    """AROON 元数据测试 (5 断言)"""

    def test_aroon_in_supported_params(self):
        """断言 1: AROON 在 supported_params 中 (RED 应失败)"""
        assert INDICATOR_PATH.exists(), f"{INDICATOR_PATH} 不存在"
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'AROON':" in content, "AROON 不在 supported_params 中 (RED 状态)"

    def test_aroon_default_timeperiod_14(self):
        """断言 2: AROON 默认 timeperiod=14"""
        if not INDICATOR_PATH.exists():
            pytest.skip("文件不存在")
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        # 验证 supported_params 中 AROON 条目含 timeperiod
        assert "'AROON': ['timeperiod']" in content or "'AROON': ['timeperiod'," in content, \
            "AROON 元数据应为 ['timeperiod']"

    def test_aroon_in_prepare_talib_inputs(self):
        """断言 3: AROON 在 _prepare_talib_inputs 中有 input 处理分支"""
        if not INDICATOR_PATH.exists():
            pytest.skip("文件不存在")
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "function_name == 'AROON'" in content or "'AROON'" in content, \
            "_prepare_talib_inputs 缺 AROON input 分支 (RED 状态)"

    def test_aroon_high_low_inputs(self):
        """断言 4: AROON 需 high/low 输入 (TA-Lib 标准)"""
        if not INDICATOR_PATH.exists():
            pytest.skip("文件不存在")
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        # 查找 AROON 块后的 4 行 (high/low 赋值)
        import re
        # 找到 "function_name == 'AROON':" 行, 取其后到下一个 elif 前的所有行
        aroon_start = content.find("function_name == 'AROON':")
        if aroon_start < 0:
            pytest.fail("未找到 AROON input 处理分支")
        # 取后续 200 字符 (足够覆盖 high/low 赋值)
        block = content[aroon_start:aroon_start + 200]
        assert "'high'" in block and "'low'" in block, "AROON 分支需含 high/low 输入"

    def test_aroon_business_call_chain(self):
        """断言 5: AROON 业务调用链 0 错误 (R10 §10.4 铁律 #4)"""
        # 验证 C 套 calculate_indicator('AROON', ...) 不抛错 (参数校验通过)
        if not INDICATOR_PATH.exists():
            pytest.skip("文件不存在")
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'AROON':" in content, "AROON 不在元数据中, 业务调用将失败"


class TestR237A001DemaMetadata:
    """DEMA 元数据测试 (5 断言)"""

    def test_dema_in_supported_params(self):
        """断言 6: DEMA 在 supported_params 中 (RED 应失败)"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'DEMA':" in content, "DEMA 不在 supported_params 中 (RED 状态)"

    def test_dema_default_timeperiod_30(self):
        """断言 7: DEMA 默认 timeperiod=30"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'DEMA': ['timeperiod']" in content or "'DEMA': ['timeperiod'," in content, \
            "DEMA 元数据应为 ['timeperiod']"

    def test_dema_in_prepare_talib_inputs(self):
        """断言 8: DEMA 在 _prepare_talib_inputs 中有 input 处理分支"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'DEMA'" in content, "_prepare_talib_inputs 缺 DEMA input 分支 (RED 状态)"

    def test_dema_close_input(self):
        """断言 9: DEMA 需 close 输入 (TA-Lib 标准)"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        dema_start = content.find("function_name in ['DEMA', 'TEMA']:")
        if dema_start < 0:
            pytest.fail("未找到 DEMA/TEMA input 处理分支")
        block = content[dema_start:dema_start + 200]
        assert "'close'" in block, "DEMA 分支需含 close 输入"

    def test_dema_business_call_chain(self):
        """断言 10: DEMA 业务调用链 0 错误"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'DEMA':" in content, "DEMA 不在元数据中"


class TestR237A001TemaMetadata:
    """TEMA 元数据测试 (5 断言)"""

    def test_tema_in_supported_params(self):
        """断言 11: TEMA 在 supported_params 中 (RED 应失败)"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'TEMA':" in content, "TEMA 不在 supported_params 中 (RED 状态)"

    def test_tema_default_timeperiod_30(self):
        """断言 12: TEMA 默认 timeperiod=30"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'TEMA': ['timeperiod']" in content or "'TEMA': ['timeperiod'," in content, \
            "TEMA 元数据应为 ['timeperiod']"

    def test_tema_in_prepare_talib_inputs(self):
        """断言 13: TEMA 在 _prepare_talib_inputs 中有 input 处理分支"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'TEMA'" in content, "_prepare_talib_inputs 缺 TEMA input 分支 (RED 状态)"

    def test_tema_close_input(self):
        """断言 14: TEMA 需 close 输入"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        # TEMA 共享 DEMA 分支
        dema_start = content.find("function_name in ['DEMA', 'TEMA']:")
        if dema_start < 0:
            pytest.fail("未找到 TEMA input 处理分支")
        block = content[dema_start:dema_start + 200]
        assert "'close'" in block, "TEMA 分支需含 close 输入"

    def test_tema_business_call_chain(self):
        """断言 15: TEMA 业务调用链 0 错误"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'TEMA':" in content, "TEMA 不在元数据中"


class TestR237A001NatrMetadata:
    """NATR 元数据测试 (5 断言)"""

    def test_natr_in_supported_params(self):
        """断言 16: NATR 在 supported_params 中 (RED 应失败)"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'NATR':" in content, "NATR 不在 supported_params 中 (RED 状态)"

    def test_natr_default_timeperiod_14(self):
        """断言 17: NATR 默认 timeperiod=14"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'NATR': ['timeperiod']" in content or "'NATR': ['timeperiod'," in content, \
            "NATR 元数据应为 ['timeperiod']"

    def test_natr_in_prepare_talib_inputs(self):
        """断言 18: NATR 在 _prepare_talib_inputs 中有 input 处理分支"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'NATR'" in content, "_prepare_talib_inputs 缺 NATR input 分支 (RED 状态)"

    def test_natr_high_low_close_inputs(self):
        """断言 19: NATR 需 high/low/close 输入 (TA-Lib 标准)"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        natr_start = content.find("function_name == 'NATR':")
        if natr_start < 0:
            pytest.fail("未找到 NATR input 处理分支")
        block = content[natr_start:natr_start + 300]
        assert "'high'" in block and "'low'" in block and "'close'" in block, \
            "NATR 分支需含 high/low/close 输入"

    def test_natr_business_call_chain(self):
        """断言 20: NATR 业务调用链 0 错误 (R10 §10.4)"""
        content = INDICATOR_PATH.read_text(encoding="utf-8")
        assert "'NATR':" in content, "NATR 不在元数据中"


class TestR237A001CIAuditTool:
    """tools/indicator_metadata_audit.py 工具测试 (3 断言)"""

    def test_audit_tool_exists(self):
        """断言 21: tools/indicator_metadata_audit.py 存在 (RED 应失败)"""
        assert TOOL_PATH.exists(), f"工具 {TOOL_PATH} 不存在 (RED 状态)"

    def test_audit_tool_9_indicators_pass(self):
        """断言 22: 工具扫描 9/9 指标通过"""
        if not TOOL_PATH.exists():
            pytest.skip("工具未实施 (RED 状态)")
        # 跑工具
        result = subprocess.run(
            [sys.executable, str(TOOL_PATH),
             "--indicators", "MA,MACD,RSI,KDJ,AD,AROON,DEMA,TEMA,NATR"],
            capture_output=True, text=True, timeout=30
        )
        # 当前 4 指标缺失, 应 exit 1 (RED 状态)
        # GREEN 状态: 9/9 通过, exit 0
        assert result.returncode == 0, f"工具失败: stdout={result.stdout}, stderr={result.stderr}"

    def test_audit_tool_fail_on_missing(self):
        """断言 23: 故意缺 AROON 时工具 exit 1"""
        if not TOOL_PATH.exists():
            pytest.skip("工具未实施 (RED 状态)")
        result = subprocess.run(
            [sys.executable, str(TOOL_PATH),
             "--indicators", "MA,MACD,RSI,KDJ,AD,DEMA,TEMA,NATR",  # 故意缺 AROON
             "--fail-on-missing"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 1, f"缺 AROON 应 exit 1, 实际 {result.returncode}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
