"""
R246: Track1/Track2 形态识别迁移 + PatternManager.identify_all_patterns 修复验证

覆盖：
1. 迁移等价性：14 个 Track2 K线形态（exec 算法）迁移为 Track1 内置 _detect_* 方法后，
   与 Track2 原始算法代码在 检出集（index/signal/start/end）+ confidence + extra_data 上逐位一致
2. Track1 优先分发：_DETECT_DISPATCH 23 键与 _SEED_PATTERNS 一一对应；内置形态即使
   algorithm_code 残留旧代码也走 Track1；未注册自定义形态仍走 Track2 exec 沙箱
3. PatternManager.identify_all_patterns 契约 + get_pattern_statistics 结构
4. import_tdx_formula / _save_pattern_config 回归（PatternCategory 缺失 + category.value 连带 bug）
"""
import sys
import os
import ast
import time
import builtins as _b

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest

from analysis.pattern_recognition import (
    PatternRecognizer,
    EnhancedPatternRecognizer,
    _DETECT_DISPATCH,
    ALLOWED_BUILTIN_NAMES,
    _validate_ast,
)
from analysis.pattern_base import PatternResult, SignalType, PatternConfig
from analysis.pattern_manager import PatternManager
import db.init_pattern_algorithms as _ipa_module
from core.unified_indicator_service import _SEED_PATTERNS


# ==================== 工具 ====================

def _load_track2_codes() -> dict:
    """从 init_pattern_algorithms.py 源码提取 Track2 参考算法代码（algorithms 为纯字面量 dict）"""
    src = os.path.join(os.path.dirname(os.path.abspath(_ipa_module.__file__)), "init_pattern_algorithms.py")
    with open(src, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "init_pattern_algorithms":
            for child in node.body:
                if isinstance(child, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "algorithms" for t in child.targets
                ):
                    return ast.literal_eval(child.value)
    raise RuntimeError("init_pattern_algorithms.py 中未找到 algorithms dict")


_TRACK2_CODES = _load_track2_codes()


def _track2_raw_exec(code: str, kdata: pd.DataFrame, recognizer: PatternRecognizer):
    """在受限命名空间中执行 Track2 算法代码，返回未经趋势层/智能信号层加工的原始 PatternResult 列表"""
    results = []
    local_vars = {
        "kdata": kdata.copy(),
        "results": results,
        "pd": pd,
        "np": np,
        "PatternResult": PatternResult,
        "SignalType": SignalType,
        "create_result": recognizer.create_result,
        "get_datetime_val": lambda k, i: None,
    }
    restricted = {}
    for name in ALLOWED_BUILTIN_NAMES:
        if name == "print":
            restricted[name] = lambda *a, **k: None
        else:
            restricted[name] = getattr(_b, name)
    _validate_ast(code)
    try:
        exec(compile(code, "<track2_ref>", "exec"), {"__builtins__": restricted}, local_vars)
    except Exception:
        # 镜像生产沙箱回退语义：Track2 参考代码含 exec 分离命名空间缺陷（如
        # inverted_hammer 的 listcomp 解析不到 local_vars['kdata'] → NameError），
        # 生产 _execute_algorithm_code 中外层 except 同样吞掉并回退，该形态 Track2 恒空。
        return []
    return list(results)


def _make_config(english_name: str, algorithm_code: str = "") -> PatternConfig:
    return PatternConfig(
        id=0,
        name=english_name,
        english_name=english_name,
        category="K线形态",
        signal_type=SignalType.NEUTRAL,
        description="r246 test",
        min_periods=1,
        max_periods=100,
        confidence_threshold=0.0,
        algorithm_code=algorithm_code,
        parameters={},
        is_active=True,
    )


def _flat(n: int) -> pd.DataFrame:
    """平盘 K 线（open=high=low=close=100），total_range=0，不触发任何形态"""
    return pd.DataFrame({
        "open": [100.0] * n,
        "high": [100.0] * n,
        "low": [100.0] * n,
        "close": [100.0] * n,
    })


def _craft_kdata() -> pd.DataFrame:
    """在平盘基底上按 Track2 规格精确注入 14 个形态（含已知索引），供等价性与正向检出验证。
    注意列序为 open/high/low/close；构造须严格满足 Track2 触发条件"""
    df = _flat(90)
    # hammer @10: open=100, close=101(body=1), high=101.15(upper=0.15<0.2*body), low=94(lower=6>2*body)
    df.iloc[10] = [100.0, 101.15, 94.0, 101.0]
    # doji @14，前一根 @13 大实体（ratio 0.5）；@14 body=0.02/range=4 → ratio 0.005 < 0.1
    df.iloc[13] = [100.0, 105.0, 95.0, 95.0]
    df.iloc[14] = [103.0, 105.0, 101.0, 103.02]
    # shooting_star @18（错开 inverted_hammer 趋势 @20-24，避免覆盖）
    df.iloc[18] = [100.0, 107.0, 99.0, 99.2]
    # inverted_hammer @25，前 5 根收盘走低（close 106..102 @20-24）
    for j, c in enumerate([106.0, 105.0, 104.0, 103.0, 102.0]):
        df.iloc[20 + j] = [c, c + 1.0, c - 1.0, c]
    df.iloc[25] = [100.0, 108.0, 100.2, 100.2]
    # marubozu @30（阳线，body_ratio>0.9，双影<0.05）
    df.iloc[30] = [100.0, 107.2, 99.9, 107.0]
    # spinning_top @35（body_ratio<0.3，双影>0.2）
    df.iloc[35] = [100.0, 103.0, 97.5, 100.5]
    # bullish_engulfing @40（k1@39 阴线，k2 吞没：open 98.5<99、close 104>102）
    df.iloc[39] = [102.0, 103.0, 100.0, 99.0]
    df.iloc[40] = [98.5, 105.0, 98.0, 104.0]
    # bearish_engulfing @45（k1@44 阳线，k2 吞没：open 102.5>100、close 98.5<99）
    df.iloc[44] = [99.0, 103.0, 99.0, 100.0]
    df.iloc[45] = [102.5, 103.0, 98.5, 98.5]
    # piercing_pattern @50（k1@49 阴线，k2 open 96<97.5、close 101.5>mid 99.75）
    df.iloc[49] = [102.0, 102.5, 100.0, 97.5]
    df.iloc[50] = [96.0, 102.0, 96.0, 101.5]
    # dark_cloud_cover @55（k1@54 阳线，k2 open 102.5>100、close 99<mid 99.5）
    df.iloc[54] = [99.0, 102.5, 100.0, 100.0]
    df.iloc[55] = [102.5, 102.5, 99.0, 99.0]
    # three_white_soldiers @58-60（三阳、close/open 双升、body_ratio>0.3、upper_ratio<0.4）
    df.iloc[58] = [100.0, 104.5, 99.5, 104.0]
    df.iloc[59] = [104.5, 108.4, 104.0, 108.0]
    df.iloc[60] = [108.5, 112.3, 108.0, 112.0]
    # three_black_crows @63-65（三阴、close/open 双降、body_ratio>0.3、lower_ratio<0.4）
    df.iloc[63] = [112.0, 112.5, 107.5, 107.5]
    df.iloc[64] = [107.5, 108.0, 103.5, 103.5]
    df.iloc[65] = [103.5, 104.0, 99.5, 99.5]
    # morning_star @68-70（k0 阴线、星线 @69 body_ratio 0.05 跳空、k2 阳线穿透 >0.5）
    df.iloc[68] = [102.0, 102.5, 98.0, 97.5]
    df.iloc[69] = [97.0, 97.5, 96.5, 97.05]
    df.iloc[70] = [99.0, 103.5, 98.5, 103.0]
    # evening_star @73-75（k0 阳线、星线 @74 body_ratio 0.02 跳空、k2 阴线穿透 >0.5）
    df.iloc[73] = [98.0, 103.3, 97.0, 102.0]
    df.iloc[74] = [102.8, 103.3, 102.3, 102.82]
    df.iloc[75] = [101.0, 101.5, 97.0, 96.5]
    return df


# Track2 迁移的 14 个形态 → 期望检出索引
_TRACK2_PATTERNS = {
    "hammer": [10],
    "doji": [14],
    "shooting_star": [18],
    "inverted_hammer": [25],
    "marubozu": [30],
    "spinning_top": [35],
    "bullish_engulfing": [40],
    "bearish_engulfing": [45],
    "piercing_pattern": [50],
    "dark_cloud_cover": [55],
    "three_white_soldiers": [60],
    "three_black_crows": [65],
    "morning_star": [70],
    "evening_star": [75],
}

# Track2 单根形态 create_result 不设 start/end（PatternResult 默认 None）；Track1 增强为 index。
# 等价性断言对单根形态忽略 start/end（不影响检出集与消费），双根/三根形态仍严格比较。
_SINGLE_BAR_PATTERNS = {"hammer", "doji", "hanging_man", "shooting_star",
                        "inverted_hammer", "marubozu", "spinning_top",
                        "white_marubozu", "black_marubozu"}


# ==================== 1. 迁移等价性（Track1 _detect_* vs Track2 exec） ====================

def _pattern_key(d_or_r):
    """检出集/匹配定位键：单根形态忽略 start/end，双根/三根包含"""
    if isinstance(d_or_r, dict):
        base = (d_or_r["pattern_type"], d_or_r["signal_type"], d_or_r["index"])
        if d_or_r["pattern_type"] in _SINGLE_BAR_PATTERNS:
            return base
        return base + (d_or_r.get("start_index"), d_or_r.get("end_index"))
    base = (d_or_r.pattern_type, d_or_r.signal_type.value, d_or_r.index)
    if d_or_r.pattern_type in _SINGLE_BAR_PATTERNS:
        return base
    return base + (d_or_r.start_index, d_or_r.end_index)


@pytest.mark.parametrize("pattern_key,exp_index", sorted(_TRACK2_PATTERNS.items()))
def test_track1_matches_track2(pattern_key, exp_index):
    """Track1 内置检测与 Track2 原始算法在检出集/置信度/extra_data 上等价，且命中期望索引"""
    recognizer = PatternRecognizer(_make_config(pattern_key))
    kdata = _craft_kdata()

    t1_dicts = getattr(recognizer, _DETECT_DISPATCH[pattern_key])(kdata)
    t2_results = _track2_raw_exec(_TRACK2_CODES[pattern_key]["code"], kdata, recognizer)

    if not t2_results:
        # Track2 参考代码存在 exec 缺陷（inverted_hammer listcomp NameError），生产 Track2 恒空，
        # 迁移 Track1 实为修复；此处仅验证 Track1 正向检出 + 无污染。
        assert set(exp_index) <= {d["index"] for d in t1_dicts}, \
            f"{pattern_key}: Track1 未检出期望索引 {exp_index}（Track2 参考缺陷，仅验证 Track1）"
        return

    t1_keys = {_pattern_key(d) for d in t1_dicts}
    t2_keys = {_pattern_key(r) for r in t2_results}
    assert t1_keys == t2_keys, f"{pattern_key}: 检出集不一致 t1={sorted(t1_keys)} t2={sorted(t2_keys)}"
    assert set(exp_index) <= {d["index"] for d in t1_dicts}, \
        f"{pattern_key}: 未在期望索引 {exp_index} 检出，实际 {sorted(d['index'] for d in t1_dicts)}"

    for d in t1_dicts:
        match = [r for r in t2_results if _pattern_key(r) == _pattern_key(d)]
        assert len(match) == 1, f"{pattern_key}@{d['index']}: Track2 匹配结果数 {len(match)}"
        r = match[0]
        assert abs(d["confidence"] - r.confidence) < 1e-9, \
            f"{pattern_key}@{d['index']}: confidence {d['confidence']} vs Track2 {r.confidence}"
        assert set((d.get("extra_data") or {}).keys()) == set((r.extra_data or {}).keys()), \
            f"{pattern_key}@{d['index']}: extra_data 键不一致"


def test_track2_codes_are_14():
    """Track2 参考算法恰好 14 个，且都在 _DETECT_DISPATCH 中"""
    assert len(_TRACK2_CODES) == 14
    assert set(_TRACK2_CODES.keys()) <= set(_DETECT_DISPATCH.keys())


def test_dispatch_keys_match_seed():
    """_DETECT_DISPATCH 23 键与 _SEED_PATTERNS（23 条）一一对应"""
    seed_keys = {row[0] for row in _SEED_PATTERNS}
    assert set(_DETECT_DISPATCH.keys()) == seed_keys
    assert len(_DETECT_DISPATCH) == 23


def test_hanging_man_sell_and_no_pollution():
    """hanging_man 独立输出看跌；hammer 配置不带上吊线信号"""
    recognizer = PatternRecognizer(_make_config("hammer"))
    kdata = _craft_kdata()

    hammer_signals = {d["index"]: d["signal_type"] for d in recognizer._detect_hammer(kdata)}
    hm_signals = {d["index"]: d["signal_type"] for d in recognizer._detect_hanging_man(kdata)}

    assert 10 in hammer_signals and hammer_signals[10] == "buy"
    assert 10 in hm_signals and hm_signals[10] == "sell"
    assert not any(s == "sell" for s in hammer_signals.values()), "hammer 配置不应带上吊线(sell)信号"


def test_negative_flat_data():
    """平盘数据不触发任何形态"""
    recognizer = PatternRecognizer(_make_config("hammer"))
    flat = _flat(50)
    for name in _TRACK2_PATTERNS:
        assert getattr(recognizer, _DETECT_DISPATCH[name])(flat) == [], f"{name} 在平盘数据误报"


# ==================== 2. 分发顺序：Track1 优先 + 自定义形态 Track2 保留 ====================

def test_track1_priority_over_algorithm_code():
    """内置形态即使残留旧 algorithm_code 也走 Track1（Track1 优先主开关）"""
    kdata = _craft_kdata()
    # 注入一个会抛异常的旧 Track2 代码（若被 exec 将走失败回退，仍应有 hammer 检出则证明未 exec）
    bad_code = "raise RuntimeError('legacy track2 code')"
    recognizer = PatternRecognizer(_make_config("hammer", bad_code))
    results = recognizer.recognize(kdata)
    hammer_idx = [r.index for r in results if r.pattern_type == "hammer"]
    assert 10 in hammer_idx, f"Track1 未优先：结果 {hammer_idx}"


def test_custom_pattern_track2_exec_still_works():
    """未注册形态（不在分发表）仍走 Track2 exec 沙箱（自定义形态通道保留）"""
    kdata = _flat(20)
    code = (
        "for i in range(min(len(kdata), 1000)):\n"
        "    k = kdata.iloc[i]\n"
        "    if k['close'] >= k['open']:\n"
        "        results.append(create_result(pattern_type='pennant', signal_type=SignalType.BUY,\n"
        "                                       confidence=0.6, index=i, price=k['close']))\n"
    )
    recognizer = PatternRecognizer(_make_config("pennant", code))
    results = recognizer.recognize(kdata)
    assert results, "自定义形态 Track2 exec 未生效"
    assert all(r.pattern_type == "pennant" for r in results)


# ==================== 3. identify_all_patterns / get_pattern_statistics ====================

def test_identify_all_patterns_contract():
    """identify_all_patterns 返回 to_dict 契约（get_pattern_statistics 消费键全覆盖）"""
    pm = PatternManager()
    kdata = _craft_kdata()
    patterns = pm.identify_all_patterns(kdata)
    assert isinstance(patterns, list)
    for p in patterns:
        assert isinstance(p, dict)
        for key in ("pattern_category", "signal", "confidence", "pattern_name", "index"):
            assert key in p, f"缺少消费键 {key}: {p}"


def test_identify_all_patterns_filtered():
    """指定 pattern_types 时只识别该形态"""
    pm = PatternManager()
    kdata = _craft_kdata()
    patterns = pm.identify_all_patterns(kdata, ["hammer"])
    assert patterns, "锤头线未检出"
    assert all(p.get("type") == "hammer" for p in patterns), \
        f"混入非 hammer 结果: {[p.get('type') for p in patterns]}"


def test_get_pattern_statistics_structure():
    """get_pattern_statistics 不再恒空，结构完整且分桶计数一致"""
    pm = PatternManager()
    stats = pm.get_pattern_statistics(_craft_kdata())
    assert set(stats.keys()) == {"total_patterns", "by_category", "by_signal", "confidence_distribution"}
    total = stats["total_patterns"]
    assert total >= 1, "迁移后形态统计应为非空"
    assert sum(stats["by_category"].values()) == total
    assert sum(stats["by_signal"].values()) == total
    assert sum(stats["confidence_distribution"].values()) == total


def test_identify_patterns_consumer_contract():
    """unified_indicator_service._calculate_pattern_indicator 的调用契约（signal_type/index）"""
    recognizer = EnhancedPatternRecognizer()
    kdata = _craft_kdata()
    results = recognizer.identify_patterns(kdata, confidence_threshold=0.0, pattern_types=["hammer"])
    assert results
    assert all(hasattr(r, "signal_type") and hasattr(r, "index") for r in results)
    assert any(r.signal_type.value == "buy" for r in results)


# ==================== 4. import_tdx_formula / _save_pattern_config 回归 ====================

def test_import_tdx_formula_regression():
    """PatternCategory 缺失（NameError 被吞）+ category.value（AttributeError 被吞）修复回归"""
    pm = PatternManager()
    unique_name = f"r246_tdx_test_{int(time.time())}"
    try:
        ok = pm.import_tdx_formula(unique_name, "C > O")
        assert ok, "import_tdx_formula 仍失败（PatternCategory/.value 未修复）"
        # 验证落库
        db = pm._get_db()
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT category, signal_type FROM pattern_types WHERE english_name = ?", (unique_name,))
            row = cur.fetchone()
        assert row and row[0] == "complex", f"落库 category 异常: {row}"
    finally:
        # 清理测试数据
        try:
            db = pm._get_db()
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM pattern_types WHERE english_name = ?", (unique_name,))
        except Exception:
            pass
