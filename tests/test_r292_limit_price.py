# -*- coding: utf-8 -*-
"""R292 涨跌停精确判定（TDD）

背景：渲染层原用固定 4.8% 涨跌幅阈值 + 封板判定涨停/跌停，会把主板 5~9.9%、
双创 10~19.9%、北交 10~29.9% 的普通大阳/大阴线误判为涨停/跌停。
本测试验证按板块精确计算涨跌停价（昨收 × (1 ± 幅度) 四舍五入到分）的判定。
"""
import numpy as np
import pandas as pd
import pytest

from core.rendering.limit_price import (
    get_limit_rate,
    classify_limit_up_down,
    is_limit_up_down,
    extract_symbol,
)


class TestGetLimitRate:
    """板块幅度映射"""

    def test_main_board_600(self):
        assert get_limit_rate('600519') == 10.0

    def test_main_board_000(self):
        assert get_limit_rate('000001') == 10.0

    def test_main_board_002(self):
        assert get_limit_rate('002317') == 10.0

    def test_main_board_003(self):
        assert get_limit_rate('003816') == 10.0

    def test_gem_300(self):
        assert get_limit_rate('300750') == 20.0

    def test_gem_301(self):
        assert get_limit_rate('301029') == 20.0

    def test_star_688(self):
        assert get_limit_rate('688001') == 20.0

    def test_star_689(self):
        assert get_limit_rate('689009') == 20.0

    def test_bse_43(self):
        assert get_limit_rate('430047') == 30.0

    def test_bse_83(self):
        assert get_limit_rate('830001') == 30.0

    def test_bse_87(self):
        assert get_limit_rate('870001') == 30.0

    def test_bse_88(self):
        assert get_limit_rate('880001') == 30.0

    def test_bse_92(self):
        assert get_limit_rate('920001') == 30.0

    def test_prefix_sz(self):
        assert get_limit_rate('sz300750') == 20.0

    def test_suffix_dot(self):
        assert get_limit_rate('300750.SZ') == 20.0

    def test_sh_prefix(self):
        assert get_limit_rate('SH600519') == 10.0

    def test_st_name_5pct(self):
        assert get_limit_rate('600001', '*ST广夏') == 5.0

    def test_st_name_lower(self):
        assert get_limit_rate('600001', 'st中安') == 5.0

    def test_empty_default_main(self):
        assert get_limit_rate('') == 10.0


class TestClassifyLimitUpDown:
    """向量化涨跌停判定"""

    def _df_like(self, prev, vals, symbol='600519', high_extra=0.0, low_extra=0.0):
        closes = [prev] + vals
        highs = [v + high_extra for v in closes]
        lows = [v - low_extra for v in closes]
        return (np.array(closes), np.array(highs), np.array(lows))

    def test_main_board_limit_up(self):
        closes, highs, lows = self._df_like(10.00, [11.00])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert lu[1] and not ld[1] and not lu[0]

    def test_main_board_big_up_not_limit(self):
        # 涨 6% 普通大阳线：旧 4.8% 阈值 + 封板会误判涨停
        closes, highs, lows = self._df_like(10.00, [10.60])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert not lu[1] and not ld[1]

    def test_main_board_9pct_not_limit(self):
        # 涨 9.9% 仍未涨停（涨停价 11.00）
        closes, highs, lows = self._df_like(10.00, [10.99])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert not lu[1]

    def test_gem_limit_up_20(self):
        closes, highs, lows = self._df_like(10.00, [12.00], '300750')
        lu, ld = classify_limit_up_down(closes, highs, lows, '300750')
        assert lu[1]

    def test_gem_10pct_not_limit(self):
        # 双创涨 10% 不是涨停（旧阈值误判）
        closes, highs, lows = self._df_like(10.00, [11.00], '300750')
        lu, ld = classify_limit_up_down(closes, highs, lows, '300750')
        assert not lu[1]

    def test_main_board_limit_down(self):
        closes, highs, lows = self._df_like(10.00, [9.00])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert ld[1] and not lu[1]

    def test_main_board_big_down_not_limit(self):
        # 跌 8% 普通大阴线
        closes, highs, lows = self._df_like(10.00, [9.20])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert not ld[1]

    def test_round_price_precision(self):
        # 昨收 13.57 → 涨停价 四舍五入 round(13.57*1.1) = 14.93
        closes, highs, lows = self._df_like(13.57, [14.93])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert lu[1]

    def test_first_bar_never_limit(self):
        closes, highs, lows = self._df_like(10.00, [11.00, 12.10])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert not lu[0] and not ld[0]

    def test_bse_limit_30(self):
        closes, highs, lows = self._df_like(10.00, [13.00], '830001')
        lu, ld = classify_limit_up_down(closes, highs, lows, '830001')
        assert lu[1]

    def test_st_limit_5(self):
        closes, highs, lows = self._df_like(10.00, [10.50], '600001')
        lu, ld = classify_limit_up_down(closes, highs, lows, '600001', '*ST广夏')
        assert lu[1]

    def test_st_main_board_no_name_not_limit(self):
        # 无名称时 ST 5% 涨停按主板 10% 判定 → 漏判（安全侧，不误判）
        closes, highs, lows = self._df_like(10.00, [10.50], '600001')
        lu, ld = classify_limit_up_down(closes, highs, lows, '600001')
        assert not lu[1]

    def test_limit_up_price_but_not_sealed(self):
        # close 等于涨停价但最高价更高（盘中开板）→ 不判涨停（封板语义）
        closes = np.array([10.00, 11.00])
        highs = np.array([10.00, 11.20])
        lows = np.array([10.00, 10.80])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert not lu[1]

    def test_single_bar(self):
        lu, ld = classify_limit_up_down(
            np.array([10.0]), np.array([10.0]), np.array([10.0]), '600519')
        assert not lu[0] and not ld[0]

    def test_empty_input(self):
        lu, ld = classify_limit_up_down(
            np.array([]), np.array([]), np.array([]), '600519')
        assert len(lu) == 0 and len(ld) == 0

    def test_consecutive_limit_ups(self):
        # 连续涨停：10.00 → 11.00 → 12.10（11.00×1.1=12.10）
        closes = np.array([10.00, 11.00, 12.10])
        highs = np.array([10.00, 11.00, 12.10])
        lows = np.array([10.00, 11.00, 12.10])
        lu, ld = classify_limit_up_down(closes, highs, lows, '600519')
        assert lu[1] and lu[2]


class TestIsLimitUpDown:
    """单点判定（十字光标浮窗）"""

    def test_limit_up_single(self):
        up, down = is_limit_up_down(10.00, 11.00, 11.00, 10.00, '600519')
        assert up and not down

    def test_big_up_not_limit(self):
        up, down = is_limit_up_down(10.00, 10.60, 10.60, 10.50, '600519')
        assert not up and not down

    def test_limit_down_single(self):
        up, down = is_limit_up_down(10.00, 9.00, 9.00, 9.00, '600519')
        assert down and not up

    def test_zero_prev(self):
        up, down = is_limit_up_down(0, 1.1, 1.1, 1.0, '600519')
        assert not up and not down

    def test_none_prev(self):
        up, down = is_limit_up_down(None, 11.0, 11.0, 10.0, '600519')
        assert not up and not down

    def test_gem_limit(self):
        up, down = is_limit_up_down(10.00, 12.00, 12.00, 10.00, '300750')
        assert up and not down


class TestExtractSymbol:
    """从 DataFrame 提取 symbol"""

    def test_symbol_col(self):
        df = pd.DataFrame({'symbol': ['300750'], 'close': [1.0]})
        assert extract_symbol(df) == '300750'

    def test_code_col(self):
        df = pd.DataFrame({'code': ['600519'], 'close': [1.0]})
        assert extract_symbol(df) == '600519'

    def test_symbol_priority_over_code(self):
        df = pd.DataFrame({'symbol': ['300750'], 'code': ['600519'], 'close': [1.0]})
        assert extract_symbol(df) == '300750'

    def test_none(self):
        assert extract_symbol(None) == ''

    def test_empty_df(self):
        assert extract_symbol(pd.DataFrame({'close': []})) == ''

    def test_multi_row_takes_first(self):
        df = pd.DataFrame({'symbol': ['300750', '300750'], 'close': [1.0, 2.0]})
        assert extract_symbol(df) == '300750'
