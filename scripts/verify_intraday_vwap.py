"""V-01 盘中实测辅助脚本：真网拉腾讯分时 → 输出 VWAP 验收数据

用法:
    python scripts/verify_intraday_vwap.py [股票代码，默认 600000]

验收标准（与东方财富/同花顺分时图均价线对比）:
    - 三线齐全（分时线/均价线/昨收虚线），VWAP 连续无跳变
    - VWAP 偏差 < 0.1%
    - 停牌/收盘后无崩溃，数据冻结

2026-08-16 为周六非交易日，真机盘中目测无法执行；
本脚本提供数据层验收基准，真机验证流程见 docs/VWAP分时图开发计划.md V-01 章节。
"""
import sys

import numpy as np

from plugins.data_sources.stock.tencent_plugin import TencentIntradayProvider


def main(symbol: str = "600000") -> int:
    df = TencentIntradayProvider.fetch_intraday(symbol)
    if df.empty:
        print(f"[{symbol}] 无分时数据（非交易日或停牌，轮询应静默保持上次渲染）")
        return 1

    price = df['price'].to_numpy(dtype=float)
    vol = df['vol'].to_numpy(dtype=float)
    with np.errstate(divide='ignore', invalid='ignore'):
        vwap = np.where(vol.cumsum() > 0,
                        (price * vol).cumsum() / vol.cumsum(), price)

    prev_close = df.attrs.get('prev_close')
    latest = price[-1]
    print(f"代码: {symbol}  行数: {len(df)}（A股 240 契约，含昨收透传: {'是' if prev_close else '否'}）")
    print(f"昨收: {prev_close}  最新价: {latest}")
    if prev_close:
        print(f"涨跌幅: {(latest / prev_close - 1) * 100:.2f}%")
    print(f"VWAP 末值: {vwap[-1]:.4f}  区间: [{vwap.min():.4f}, {vwap.max():.4f}]")
    print("验收: 与第三方行情软件分时均价线对比，偏差应 < 0.1%")
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:1] or []))
