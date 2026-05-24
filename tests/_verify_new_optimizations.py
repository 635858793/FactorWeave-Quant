"""验证最新5项向量化优化后数据一致性"""
import pandas as pd, numpy as np, time, sys, os

passed = 0
total = 0

# ============================================================
print("=" * 60)
print("TEST 4: chart_service.py iterrows → 向量化 to_dict")
total += 1

np.random.seed(789)
dates = pd.date_range('2024-01-01', periods=1000, freq='D')
kline_old = pd.DataFrame({
    'open': np.random.uniform(10, 100, 1000),
    'high': np.random.uniform(15, 105, 1000),
    'low': np.random.uniform(5, 95, 1000),
    'close': np.random.uniform(10, 100, 1000),
    'volume': np.random.randint(10000, 1000000, 1000),
}, index=dates)

def old_chart(kline_data):
    kline_list = []
    for _, row in kline_data.iterrows():
        if hasattr(row.name, 'strftime'):
            date_str = row.name.strftime('%Y-%m-%d')
        else:
            date_str = str(row.name)[:10]
        kline_list.append({
            'date': date_str,
            'datetime': row.name.strftime('%Y-%m-%d %H:%M:%S') if hasattr(row.name, 'strftime') else str(row.name),
            'open': float(row.get('open', 0)),
            'high': float(row.get('high', 0)),
            'low': float(row.get('low', 0)),
            'close': float(row.get('close', 0)),
            'volume': int(row.get('volume', 0))
        })
    return kline_list

def new_chart(kline_data):
    kline_df = kline_data.copy()
    for col in ['open', 'high', 'low', 'close']:
        if col in kline_df.columns:
            kline_df[col] = kline_df[col].astype(float)
    if 'volume' in kline_df.columns:
        kline_df['volume'] = kline_df['volume'].astype(int)
    idx_dt = pd.to_datetime(kline_df.index)
    kline_df['date'] = idx_dt.strftime('%Y-%m-%d')
    kline_df['datetime'] = idx_dt.strftime('%Y-%m-%d %H:%M:%S')
    return kline_df[['date', 'datetime', 'open', 'high', 'low', 'close', 'volume']].to_dict('records')

t0 = time.perf_counter()
old_r = old_chart(kline_old)
t_old = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
new_r = new_chart(kline_old)
t_new = (time.perf_counter() - t0) * 1000

eq = old_r == new_r
print(f"  Records:         {len(old_r)}")
print(f"  Old iterrows:    {t_old:.2f}ms")
print(f"  New vectorized:  {t_new:.2f}ms")
print(f"  Speedup:         {t_old / t_new:.1f}x")
print(f"  Data consistent: {eq}")
print(f"  Result:          {'PASS' if eq else 'FAIL'}")
if eq: passed += 1

# ============================================================
print()
print("=" * 60)
print("TEST 5: duckdb_downloader iterrows → 向量化 dict(zip)")
total += 1

np.random.seed(111)
result = pd.DataFrame({
    'symbol': [f'{c:06d}' for c in np.random.randint(100000, 999999, 500)],
    'latest_date': pd.to_datetime('2024-01-01') + pd.to_timedelta(np.random.randint(0, 365, 500), unit='D'),
})
result.loc[np.random.choice(500, 50, replace=False), 'latest_date'] = None

def old_duckdb(result):
    return {
        row['symbol']: pd.to_datetime(row['latest_date'])
        for _, row in result.iterrows()
        if pd.notna(row['latest_date'])
    }

def new_duckdb(result):
    filtered = result.dropna(subset=['latest_date'])
    if not filtered.empty:
        dates = pd.to_datetime(filtered['latest_date'])
        return dict(zip(filtered['symbol'], dates))
    return {}

t0 = time.perf_counter()
old_d = old_duckdb(result)
t_old = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
new_d = new_duckdb(result)
t_new = (time.perf_counter() - t0) * 1000

eq = old_d == new_d
print(f"  Records:         {len(old_d)}")
print(f"  Old iterrows:    {t_old:.2f}ms")
print(f"  New vectorized:  {t_new:.2f}ms")
print(f"  Speedup:         {t_old / t_new:.1f}x")
print(f"  Data consistent: {eq}")
print(f"  Result:          {'PASS' if eq else 'FAIL'}")
if eq: passed += 1

# ============================================================
print()
print("=" * 60)
print("TEST 6: signal_generation.py for-range → numpy 向量化")
total += 1

np.random.seed(222)
n_sig = 500
sig_df = pd.DataFrame({
    'close': np.random.uniform(10, 100, n_sig),
    'position': np.zeros(n_sig, dtype=int),
})
min_trade_interval = 5
sig_df['optimized_signal'] = 0
signal_positions = np.random.choice(n_sig, 30, replace=False)
for pos in signal_positions:
    sig_df.iloc[pos, sig_df.columns.get_loc('optimized_signal')] = np.random.choice([-1, 1])

sig_col = sig_df.columns.get_loc('optimized_signal')

def old_signal(result_df, min_trade_interval):
    df = result_df.copy()
    last_trade_idx = -min_trade_interval - 1
    opt_sig_col = df.columns.get_loc('optimized_signal')
    for i in range(len(df)):
        if df.iloc[i, opt_sig_col] != 0:
            if i - last_trade_idx <= min_trade_interval:
                df.iloc[i, opt_sig_col] = 0
            else:
                last_trade_idx = i
    return df

def new_signal(result_df, min_trade_interval):
    df = result_df.copy()
    opt_sig_col = df.columns.get_loc('optimized_signal')
    sig_mask = df.iloc[:, opt_sig_col] != 0
    sig_idxs = np.where(sig_mask)[0]
    if len(sig_idxs) > 0:
        last_trade_idx = -min_trade_interval - 1
        zero_idxs = []
        for idx in sig_idxs:
            if idx - last_trade_idx <= min_trade_interval:
                zero_idxs.append(idx)
            else:
                last_trade_idx = idx
        if zero_idxs:
            df.iloc[zero_idxs, opt_sig_col] = 0
    return df

t0 = time.perf_counter()
odf = old_signal(sig_df, min_trade_interval)
t_old = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
ndf = new_signal(sig_df, min_trade_interval)
t_new = (time.perf_counter() - t0) * 1000

sig_eq = (odf['optimized_signal'].values == ndf['optimized_signal'].values).all()
print(f"  Rows:            {n_sig}, Signals: {len(signal_positions)}")
print(f"  Old for-range:   {t_old:.2f}ms")
print(f"  New numpy:       {t_new:.2f}ms")
print(f"  Speedup:         {t_old / t_new:.1f}x")
print(f"  Signals equal:   {sig_eq}")
print(f"  Result:          {'PASS' if sig_eq else 'FAIL'}")
if sig_eq: passed += 1

# ============================================================
print()
print("=" * 60)
if passed == total:
    print(f"ALL {total} NEW VECTORIZATION TESTS PASSED")
else:
    print(f"{passed}/{total} TESTS PASSED, {total - passed} FAILED")
print("=" * 60)
sys.exit(0 if passed == total else 1)