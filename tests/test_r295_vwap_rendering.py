"""
R295-VWAP: 分时图均价线计算单元测试（rendering_mixin._compute_intraday_series）

VWAP 渲染链路（已实现，R294）:
    rendering_mixin.py L106-136   _compute_intraday_series  均价线计算 (纯静态方法, 无 GUI)
    rendering_mixin.py L314-343   分时图分支                 分时线 + 黄色均价线 + 昨收虚线 + 成交量
    middle_panel.py  L1648-1704   _refresh_intraday_realtime (R295 轮询) → L1614-1646 类1min K线 → update_chart
本文件补齐该链路计算核心的单元测试覆盖（此前无任何测试引用 _compute_intraday_series）。
"""
import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit

# conftest.py L51 将 'gui.widgets' mock 进 sys.modules（阻断真实包导入），
# 与 test_r295_intraday_chart.py 同模式：pop 后真实导入（子模块 mock 仍保留，安全）。
import os  # noqa: E402
import sys  # noqa: E402
import importlib.util  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

sys.modules.pop('gui.widgets', None)  # noqa: E402

from gui.widgets.chart_mixins.rendering_mixin import RenderingMixin  # noqa: E402


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _load_module_from_file(mod_name, file_path):
    """按文件路径加载模块（参照 test_r293_minute_axis.py 同名单函数最小实现）"""
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestComputeIntradaySeries:
    """分时图 VWAP 均价线计算"""

    @staticmethod
    def _kline(closes, vols, datetimes=None):
        df = pd.DataFrame({
            'open': closes, 'high': closes, 'low': closes,
            'close': closes, 'volume': vols,
        })
        if datetimes is not None:
            df['datetime'] = pd.to_datetime(datetimes)
        return df

    def test_vwap_weighted_average(self):
        """VWAP = Σ(close×volume)/Σvolume 精确值"""
        df = self._kline([10.0, 11.0, 12.0], [100, 200, 300],
                         ['2026-08-14 09:31', '2026-08-14 09:32', '2026-08-14 09:33'])
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert len(intra) == 3
        assert prev_close is not None
        assert avg.iloc[0] == pytest.approx(10.0)
        # (10*100 + 11*200) / (100+200) = 3200/300
        assert avg.iloc[1] == pytest.approx(3200.0 / 300.0)
        # (3200 + 12*300) / (300+300) = 6800/600
        assert avg.iloc[2] == pytest.approx(6800.0 / 600.0)
        assert len(avg) == len(df)

    def test_zero_volume_keeps_running_average(self):
        """某分钟 volume=0 → 分子分母不变，均价保持前值"""
        df = self._kline([10.0, 11.0, 12.0], [100, 0, 200],
                         ['2026-08-14 09:31', '2026-08-14 09:32', '2026-08-14 09:33'])
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert avg.iloc[1] == pytest.approx(10.0)          # 11*0 不增权
        assert avg.iloc[2] == pytest.approx((1000 + 12 * 200) / 300.0)  # 3400/300

    def test_first_row_zero_volume_degrades_to_close(self):
        """首行 volume=0 → cum_vol=0 退化分支取 close 均价"""
        df = self._kline([10.0, 11.0], [0, 100],
                         ['2026-08-14 09:31', '2026-08-14 09:32'])
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert avg.iloc[0] == pytest.approx(10.0)   # np.where(cum_vol>0) → close
        assert avg.iloc[1] == pytest.approx(11.0)   # (0 + 11*100)/100

    def test_last_trading_day_filter_and_prev_close(self):
        """datetime 过滤最新交易日；昨收 = 前一日最后一根收盘"""
        closes = [10.0, 10.5, 10.0, 11.0, 12.0]
        vols = [100, 100, 100, 200, 300]
        dts = ['2026-08-13 10:00', '2026-08-13 14:30',
               '2026-08-14 09:31', '2026-08-14 09:32', '2026-08-14 09:33']
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(
            self._kline(closes, vols, dts))
        assert len(intra) == 3
        assert prev_close == pytest.approx(10.5)
        assert avg.iloc[-1] == pytest.approx(6800.0 / 600.0)

    def test_no_datetime_column_uses_all_rows(self):
        """无 datetime 列 → 全量计算；昨收退化取首行 open"""
        df = self._kline([10.0, 11.0], [100, 100])
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert len(intra) == 2
        assert prev_close == pytest.approx(10.0)
        assert avg.iloc[-1] == pytest.approx(10.5)

    def test_empty_dataframe(self):
        """空 DataFrame → intra 空、prev_close None（不抛异常）"""
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert len(intra) == 0
        assert prev_close is None

    def test_r295_intraday_kline_pipeline_input(self):
        """R295 轮询链路产物（_convert_intraday_to_kline 输出列 [datetime,open,high,low,close,volume]）→ VWAP 正确"""
        price = [10.0, 11.0, 12.0]
        vol = [100, 200, 300]
        df = self._kline(price, vol,
                         ['2026-08-14 09:31', '2026-08-14 09:32', '2026-08-14 09:33'])
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert avg.iloc[-1] == pytest.approx(6800.0 / 600.0)
        # 渲染契约: 均价线索引与 intra 对齐（render_line 用 x_intra=np.arange(len(intra)) 绘制）
        assert list(avg.index) == list(intra.index)

    def test_prev_close_column_priority(self):
        """V-03 契约: 带 prev_close 列（类1min K线，每行同值）→ 昨收直接取该列，而非退化 open[0]"""
        df = self._kline([10.0, 11.0, 12.0], [100, 200, 300],
                         ['2026-08-14 09:31', '2026-08-14 09:32', '2026-08-14 09:33'])
        df['prev_close'] = 9.18
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert prev_close == pytest.approx(9.18)   # 而非退化 open[0]=10.0

    def test_prev_close_column_beats_history_close(self):
        """多日数据 + prev_close 列 → 列值优先于历史 close 推算（跳过历史/退化逻辑）"""
        closes = [10.0, 10.5, 11.0, 12.0, 13.0]
        vols = [100, 100, 100, 200, 300]
        dts = ['2026-08-13 10:00', '2026-08-13 14:30',
               '2026-08-14 09:31', '2026-08-14 09:32', '2026-08-14 09:33']
        df = self._kline(closes, vols, dts)
        df['prev_close'] = 9.5
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert len(intra) == 3                       # 最新交易日过滤仍生效
        assert prev_close == pytest.approx(9.5)      # 列优先，而非历史 close=10.5

    def test_no_prev_close_column_falls_back_to_open(self):
        """无 prev_close 列 → 回退原逻辑（当日数据退化 open[0]，回归）"""
        df = self._kline([10.0, 11.0, 12.0], [100, 200, 300],
                         ['2026-08-14 09:31', '2026-08-14 09:32', '2026-08-14 09:33'])
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert prev_close == pytest.approx(10.0)

    def test_prev_close_column_all_nan_falls_back(self):
        """prev_close 列全 NaN → 回退历史 close / open[0]（不抛异常）"""
        df = self._kline([10.0, 11.0], [100, 100],
                         ['2026-08-14 09:31', '2026-08-14 09:32'])
        df['prev_close'] = [float('nan'), float('nan')]
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert prev_close == pytest.approx(10.0)


class TestIntradayRenderSmoke:
    """V-03 分时图渲染冒烟：分时线 + 均价线（主题色）+ VWAP 角标 + K线分支不画均价"""

    @classmethod
    def setup_class(cls):
        try:
            cls.render_mod = _load_module_from_file(
                'gui.widgets.chart_mixins.rendering_mixin',
                os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins',
                             'rendering_mixin.py'))
            cls.utility_mod = _load_module_from_file(
                'gui.widgets.chart_mixins.utility_mixin',
                os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins',
                             'utility_mixin.py'))
        except Exception as e:  # matplotlib/PyQt5 无头导入失败等
            pytest.skip(f"rendering_mixin 无头加载失败，跳过分时图渲染冒烟测试: {e}")

    def _make_widget(self, style=None):
        class _ChartWidget(self.render_mod.RenderingMixin, self.utility_mod.UtilityMixin):
            pass
        w = _ChartWidget.__new__(_ChartWidget)
        w.current_kdata = None
        w._full_kdata = None
        w.price_ax = MagicMock()
        w.volume_ax = MagicMock()
        w.indicator_ax = MagicMock()
        w.renderer = MagicMock()
        w.theme_manager = MagicMock()
        w.theme_manager.get_theme_colors.return_value = {
            'chart_text': '#222b45', 'chart_background': '#ffffff'}
        w.active_indicators = []
        w.error_occurred = MagicMock()
        w.canvas = MagicMock()
        w._render_indicators = MagicMock()
        w._optimize_display = MagicMock()
        w.close_loading_dialog = MagicMock()
        w._invalidate_crosshair_background = MagicMock()
        w.show_no_data = MagicMock()
        w._safe_format_date = MagicMock(return_value='08-14 10:00')
        w.current_stock = '600519'
        if style is None:
            style = {'avg_color': '#00ff00'}
        w._get_chart_style = MagicMock(return_value=style)
        return w

    @staticmethod
    def _intraday_df():
        """3 行当日 1min 分时数据（close 递增；VWAP 末值 = 6800/600 ≈ 11.3333）"""
        return pd.DataFrame({
            'datetime': pd.to_datetime(
                ['2026-08-14 09:31', '2026-08-14 09:32', '2026-08-14 09:33']),
            'open': [10.0, 11.0, 12.0],
            'high': [10.0, 11.0, 12.0],
            'low': [10.0, 11.0, 12.0],
            'close': [10.0, 11.0, 12.0],
            'volume': [100, 200, 300],
        })

    def test_intraday_render_draws_price_and_avg_lines(self):
        """分时图渲染：render_line 恰好 2 次（分时线 close + 均价线），均价线末值 == VWAP"""
        w = self._make_widget()
        w.update_chart({'kdata': self._intraday_df(), 'chart_type': '分时图'})
        assert len(w.renderer.render_line.call_args_list) == 2
        price_series = w.renderer.render_line.call_args_list[0].args[1]
        avg_series = w.renderer.render_line.call_args_list[1].args[1]
        assert price_series.iloc[-1] == pytest.approx(12.0)
        assert avg_series.iloc[-1] == pytest.approx(6800.0 / 600.0)

    def test_avg_line_color_from_style(self):
        """V-04: 均价线颜色取自 style['avg_color']（主题键 avg_line → '#00ff00'）"""
        w = self._make_widget(style={'avg_color': '#00ff00'})
        w.update_chart({'kdata': self._intraday_df(), 'chart_type': '分时图'})
        avg_style = w.renderer.render_line.call_args_list[1].args[2]
        assert avg_style['color'] == '#00ff00'

    def test_avg_line_color_default_gold(self):
        """style 无 avg_color → 缺省 #ffd700（向后兼容）"""
        w = self._make_widget(style={})
        w.update_chart({'kdata': self._intraday_df(), 'chart_type': '分时图'})
        avg_style = w.renderer.render_line.call_args_list[1].args[2]
        assert avg_style['color'] == '#ffd700'

    def test_vwap_label_text_rendered(self):
        """V-05: price_ax.text 至少一次调用含 '均价' 前缀（最新 VWAP 角标）"""
        w = self._make_widget()
        w.update_chart({'kdata': self._intraday_df(), 'chart_type': '分时图'})
        labels = [str(c.args[2]) for c in w.price_ax.text.call_args_list
                  if len(c.args) >= 3]
        assert any(lbl.startswith('均价') for lbl in labels)

    def test_kline_chart_type_does_not_draw_avg(self):
        """K线图分支：走 render_candlesticks，不画均价线（render_line 0 次）"""
        w = self._make_widget()
        w.update_chart({'kdata': self._intraday_df(), 'chart_type': 'K线图'})
        w.renderer.render_candlesticks.assert_called_once()
        w.renderer.render_line.assert_not_called()

    @staticmethod
    def _full_session_df():
        """盘中全量 A股 240 点（09:31-11:30 + 13:01-15:00）：price 随机游走 + vol 波动"""
        from datetime import datetime as _dt, time as _tm
        rng = np.random.default_rng(42)
        times, price, vol = [], [], []
        p = 10.0
        for hh in range(9, 16):
            for mm in range(0, 60):
                if hh == 9:
                    if mm < 31:
                        continue  # 09:30 开盘前
                elif hh == 11:
                    if mm > 30:
                        continue  # 11:31 午休
                elif hh == 12:
                    continue  # 午休
                elif hh == 13:
                    if mm == 0:
                        continue  # 13:00 非标准点（A股 240 契约从 13:01 起）
                elif hh == 15:
                    if mm > 0:
                        continue  # 收盘后
                times.append(_dt(2026, 8, 14, hh, mm))
                p = round(p + rng.normal(0, 0.02), 2)
                price.append(p)
                vol.append(float(rng.integers(50, 800)))
        df = pd.DataFrame({'datetime': pd.to_datetime(times),
                           'open': price, 'high': price, 'low': price,
                           'close': price, 'volume': vol})
        return df

    def test_full_session_240_points_render_and_vwap(self):
        """V-01 盘中模拟：240 点全量渲染 → 分时线+均价线各 1 次，均价线末值 == 独立重算 VWAP"""
        w = self._make_widget()
        df = self._full_session_df()
        assert len(df) == 240
        w.update_chart({'kdata': df, 'chart_type': '分时图'})
        assert len(w.renderer.render_line.call_args_list) == 2
        avg_series = w.renderer.render_line.call_args_list[1].args[1]
        cl = df['close'].to_numpy(dtype=float)
        vol = df['volume'].to_numpy(dtype=float)
        expected = (cl * vol).cumsum() / vol.cumsum()
        assert avg_series.iloc[-1] == pytest.approx(expected[-1])
        # 均价线全程单调稳定（VWAP 介于 min/max 收盘之间）
        assert avg_series.min() >= df['close'].min()
        assert avg_series.max() <= df['close'].max()

    def test_full_session_vwap_matches_independent_calculation(self):
        """V-01 交叉验证：_compute_intraday_series 的 VWAP 与 (price×vol 独立公式) 逐点一致"""
        df = self._full_session_df()
        intra, prev_close, avg = RenderingMixin._compute_intraday_series(df)
        assert prev_close == pytest.approx(df['open'].iloc[0])  # 无历史/无列 → open[0] 退化
        cl = df['close'].to_numpy(dtype=float)
        vol = df['volume'].to_numpy(dtype=float)
        expected = np.where(vol.cumsum() > 0,
                            (cl * vol).cumsum() / vol.cumsum(), cl)
        np.testing.assert_allclose(avg.to_numpy(), expected, rtol=1e-9)
