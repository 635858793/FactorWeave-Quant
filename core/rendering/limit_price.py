# -*- coding: utf-8 -*-
"""A股涨跌停价格与分类判定（R292 精确判定）。

背景：渲染层原用固定 4.8% 涨跌幅阈值 + 封板（close 贴 high/low）判定涨停/跌停，
会把主板 5~9.9%、双创 10~19.9%、北交 10~29.9% 的普通大阳/大阴线误判为涨停/跌停
（成交价已到涨停价附近但未封板，被 4.8% 阈值一律捕获）。
本模块按板块精确计算涨跌停价（昨收 × (1 ± 幅度) 四舍五入到分），
收盘价等于涨/跌停价 且 收盘封在最高/最低价 才判定——消除误判。

板块幅度（A股，价格精度 0.01）：
- 主板（60/00 前缀）：10%
- 创业板（30/31）：20%
- 科创板（68/69）：20%
- 北交所（43/83/87/88/920）：30%
- ST/*ST（名称含 ST）：5%（渲染层一般无名称 → 按代码板块判定；
  ST 5% 涨停不会命中代码板块的更高幅度价 → 漏判而非误判，安全侧）
- 无涨跌幅限制（上市前 5 日/退市整理等）：无上市天数信息，无法识别，
  按代码板块判定（属已知局限，文档注明）

调用链：优化渲染（optimization/chart_renderer.py）→ WebGPU GPU 路径
（core/webgpu/webgpu_renderer.py _process_candlestick_data_gpu）→ CPU 降级
（_render_cpu_fallback_candlestick）→ 成交量（VolumeDataProcessor）→
fallback 链 Matplotlib（core/webgpu/fallback.py）→ 十字光标浮窗
（gui/widgets/chart_mixins/crosshair_mixin.py）。
"""
import numpy as np

__all__ = ['get_limit_rate', 'classify_limit_up_down', 'is_limit_up_down', 'extract_symbol']


def _round_price(x) -> np.ndarray:
    """四舍五入到分（A股价格精度 0.01），兼容标量/数组。

    Python 内置 round 使用银行家舍入（round-half-even），交易所规则为
    四舍五入，故用 floor(x*100 + 0.5)/100 精确复刻。
    """
    return np.floor(np.asarray(x, dtype=np.float64) * 100.0 + 0.5) / 100.0


def get_limit_rate(symbol='', name='') -> float:
    """返回涨跌停幅度百分比（0 表示无涨跌停/无法判定）。

    Args:
        symbol: 股票代码，支持 '300750' / 'sz300750' / '300750.SZ' /
                'SH600519' 等格式；空串默认按主板 10%。
        name: 股票名称，含 'ST'（不分大小写）时按 5%。
    """
    if name and 'ST' in str(name).upper():
        return 5.0
    digits = ''.join(ch for ch in str(symbol) if ch.isdigit())
    s = digits[-6:] if len(digits) >= 6 else digits
    if s.startswith(('30', '31')):          # 创业板
        return 20.0
    if s.startswith(('68', '69')):          # 科创板
        return 20.0
    if s.startswith(('43', '83', '87', '88', '92')):  # 北交所
        return 30.0
    return 10.0                             # 主板（600/601/603/605/609、000/001/002/003）


def classify_limit_up_down(closes, highs, lows, symbol='', name=''):
    """向量化涨跌停判定（K线/成交量渲染共用）。

    Args:
        closes/highs/lows: 一维 array-like，长度 n，交易日升序序列。
        symbol: 股票代码（用于板块幅度）。
        name: 股票名称（含 ST 时按 5%）。

    Returns:
        (is_limit_up, is_limit_down): 两个 bool 数组，长度 n。
        每根 K 线用前一根收盘价作为昨收；首根无昨收 → 不判定。
    """
    closes = np.asarray(closes, dtype=np.float64)
    highs = np.asarray(highs, dtype=np.float64)
    lows = np.asarray(lows, dtype=np.float64)
    n = len(closes)
    is_limit_up = np.zeros(n, dtype=bool)
    is_limit_down = np.zeros(n, dtype=bool)
    if n < 2:
        return is_limit_up, is_limit_down
    rate = get_limit_rate(symbol, name)
    if rate <= 0:
        return is_limit_up, is_limit_down
    prev = closes[:-1]
    valid = prev > 0
    limit_up_price = _round_price(prev * (1 + rate / 100.0))
    limit_down_price = _round_price(prev * (1 - rate / 100.0))
    tol = 1e-6
    # close 精确等于涨/跌停价 且 收盘封在最高/最低价（封板语义）
    is_limit_up[1:] = valid & (np.abs(closes[1:] - limit_up_price) < tol) \
        & (np.abs(closes[1:] - highs[1:]) < tol)
    is_limit_down[1:] = valid & (np.abs(closes[1:] - limit_down_price) < tol) \
        & (np.abs(closes[1:] - lows[1:]) < tol)
    return is_limit_up, is_limit_down


def is_limit_up_down(prev_close, close, high, low, symbol='', name=''):
    """单点涨跌停判定（十字光标浮窗用）。

    Returns:
        (is_limit_up, is_limit_down): 两个 bool。
    """
    is_limit_up = False
    is_limit_down = False
    if prev_close is not None and prev_close > 0:
        rate = get_limit_rate(symbol, name)
        if rate > 0:
            tol = 1e-6
            is_limit_up = (
                abs(close - _round_price(prev_close * (1 + rate / 100.0))) < tol
                and abs(close - high) < tol)
            is_limit_down = (
                abs(close - _round_price(prev_close * (1 - rate / 100.0))) < tol
                and abs(close - low) < tol)
    return bool(is_limit_up), bool(is_limit_down)


def extract_symbol(data) -> str:
    """从 K 线 DataFrame 提取股票代码（symbol/code 列），无则空串。

    整个序列为同一标的，取首行即可；symbol 列优先于 code 列。
    """
    if data is None:
        return ''
    try:
        for col in ('symbol', 'code'):
            if col in data.columns and len(data) > 0:
                val = data[col].iloc[0]
                if val is not None:
                    return str(val)
    except Exception:
        pass
    return ''
