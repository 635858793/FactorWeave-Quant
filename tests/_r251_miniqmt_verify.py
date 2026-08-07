"""R251 miniqmt 频率映射 mock 验证

环境无 xtquant C 扩展，无法真实调用 xtdata.get_market_data，
故 mock 一个 FakeXtdata 记录 period 参数并返回构造的 DataFrame，
验证系统频率 ('D'/'W'/'M'/'5min'/'60m' 等) 被正确转换为 xtquant period
('1d'/'1w'/'1M'/'5m'/'60m') 后再传给 xtdata。
"""
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.data_sources.stock.miniqmt_plugin import MiniQMTPlugin


class FakeXtdata:
    """mock xtdata：记录 get_market_data 的 period 参数并返回构造的 DataFrame"""

    def __init__(self):
        self.calls = []  # 记录每次调用的 kwargs

    def get_market_data(self, stock_list=None, period=None, start_time=None,
                        end_time=None, count=None, field_list=None,
                        dividend_type=None, fill_data=True):
        self.calls.append({
            "stock_list": stock_list,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "count": count,
        })
        # 构造一个迷你 DataFrame，模拟 xtdata 返回格式
        index = pd.date_range("2026-08-01", periods=3, freq="D")
        return pd.DataFrame({
            "time": [t for t in index],
            "open": [10.0, 10.2, 10.1],
            "high": [10.5, 10.4, 10.6],
            "low": [9.9, 10.0, 10.0],
            "close": [10.3, 10.1, 10.5],
            "volume": [1000, 1200, 1100],
        })


passed = 0


def main():
    failures = []

    def check(label, freq, expected_period, method="get_kdata"):
        global passed
        plugin = MiniQMTPlugin()
        fake = FakeXtdata()
        plugin._xtdata = fake

        if method == "get_kdata":
            df = plugin.get_kdata("000001.SZ", freq=freq,
                                  start_date="20260801", end_date="20260804")
        else:
            df = plugin.get_kline_data("000001.SZ", period=freq,
                                       start_time="20260801", end_time="20260804")

        ok_period = len(fake.calls) == 1 and fake.calls[0]["period"] == expected_period
        ok_data = df is not None and len(df) == 3 and "close" in df.columns
        if ok_period and ok_data:
            global passed
            passed += 1
            print(f"[PASS] {method}({freq}) -> period={fake.calls[0]['period']}, 返回 {len(df)} 条")
        else:
            got = fake.calls[0]["period"] if fake.calls else None
            failures.append(f"[FAIL] {method}({freq}): 期望 period={expected_period}, 实际={got}, "
                            f"data_ok={ok_data}")
            print(failures[-1])

    # 核心修复验证：系统日/周/月频率 -> xtquant 格式
    check("D", "D", "1d")
    check("W", "W", "1w")
    check("M", "M", "1M")
    # 分钟长格式 -> xtquant 格式
    check("5min", "5min", "5m")
    check("60m", "60m", "60m")
    check("1H", "1H", "60m")
    # 幂等性：已是 xtquant 格式的取值应原样透传
    check("1m", "1m", "1m")
    check("1d", "1d", "1d")
    check("1w", "1w", "1w")
    check("1M", "1M", "1M")
    # 未知格式原样透传
    check("unknown", "XYZ", "XYZ")
    # 另一 K 线入口同步修复
    check("kline-D", "D", "1d", method="get_kline_data")
    check("kline-5min", "5min", "5m", method="get_kline_data")

    print(f"\n总计: {passed} PASS / {passed + len(failures)} 用例")
    if failures:
        print("\n".join(failures))
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
