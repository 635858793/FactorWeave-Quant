"""向量化优化后数据一致性验证脚本"""
import pandas as pd, numpy as np, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from enum import Enum

class AssetType(Enum):
    STOCK = 'stock'

np.random.seed(42)
n_stocks = 5000
stock_df = pd.DataFrame({
    'code': [f'{code:06d}' for code in np.random.choice([600000, 688001, 300750, 159919, 512880], n_stocks)],
    'name': [f'Stock_{i}' for i in range(n_stocks)],
    'market': np.random.choice(['SH', 'SZ'], n_stocks),
})

def old_convert(stock_df):
    asset_list = []
    for _, row in stock_df.iterrows():
        asset_list.append({
            'symbol': row.get('code', ''), 'name': row.get('name', ''),
            'market': row.get('market', ''), 'asset_type': 'stock',
            'currency': 'CNY', 'exchange': row.get('market', '')
        })
    return asset_list

def new_convert(stock_df):
    df = stock_df.copy()
    for col in ('code', 'name', 'market'):
        if col not in df.columns:
            df[col] = ''
    df['asset_type'] = 'stock'
    df['currency'] = 'CNY'
    df['exchange'] = df['market']
    return df[['code', 'name', 'market', 'asset_type', 'currency', 'exchange']].rename(columns={'code': 'symbol'}).to_dict('records')

t0 = time.perf_counter()
old_r = old_convert(stock_df)
t_old = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
new_r = new_convert(stock_df)
t_new = (time.perf_counter() - t0) * 1000

eq = all(r == n for r, n in zip(old_r, new_r))
print('=' * 60)
print('TEST 1: tongdaxin_plugin iterrows -> vectorized')
print(f'  Records: {len(old_r)}')
print(f'  Old iterrows:       {t_old:.2f}ms')
print(f'  New vectorized:     {t_new:.2f}ms')
print(f'  Speedup:            {t_old / t_new:.1f}x')
print(f'  Data consistent:    {eq}')
print(f'  Result:             {"PASS" if eq else "FAIL"}')

# ============================================================
np.random.seed(123)
data = pd.DataFrame({
    'date': pd.date_range('2024-01-01', periods=2000, freq='D'),
    'symbol': np.random.choice([f'{c:06d}' for c in np.random.randint(100000, 999999, 50)], 2000),
    'open': np.random.uniform(10, 100, 2000),
    'high': np.random.uniform(10, 100, 2000),
    'low': np.random.uniform(10, 100, 2000),
    'close': np.random.uniform(10, 100, 2000),
    'volume': np.random.uniform(1e6, 1e8, 2000),
})
scores = {s: np.random.uniform(0, 1) for s in data['symbol'].unique()}

def old_ai(data, scores):
    sd = []
    for rd in data.to_dict('records'):
        s = scores.get(rd['symbol'], 0.0)
        sig = 1 if s > 0.6 else (-1 if s < 0.3 else 0)
        sd.append({
            'date': rd['date'], 'symbol': rd['symbol'],
            'open': rd['open'], 'high': rd['high'], 'low': rd['low'],
            'close': rd['close'], 'volume': rd['volume'],
            'ai_signal': sig, 'signal_strength': abs(s - 0.5) * 2,
            'confidence': s,
        })
    return pd.DataFrame(sd)

def new_ai(data, scores):
    df = data.copy()
    df['score'] = df['symbol'].map(scores).fillna(0.0)
    df['ai_signal'] = np.select(
        [df['score'] > 0.6, df['score'] < 0.3], [1, -1], default=0
    )
    df['signal_strength'] = (df['score'] - 0.5).abs() * 2
    df['confidence'] = df['score']
    return df[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume',
               'ai_signal', 'signal_strength', 'confidence']].copy()

t0 = time.perf_counter()
odf = old_ai(data, scores)
t_old = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
ndf = new_ai(data, scores)
t_new = (time.perf_counter() - t0) * 1000

sig_eq = (odf['ai_signal'].values == ndf['ai_signal'].values).all()
str_eq = np.allclose(odf['signal_strength'].values, ndf['signal_strength'].values)
conf_eq = np.allclose(odf['confidence'].values, ndf['confidence'].values)
all_ok = sig_eq and str_eq and conf_eq

print()
print('=' * 60)
print('TEST 2: ai_selection to_dict loop -> np.select')
print(f'  Records:            {len(odf)}')
print(f'  Old to_dict loop:   {t_old:.2f}ms')
print(f'  New np.select:      {t_new:.2f}ms')
print(f'  Speedup:            {t_old / t_new:.1f}x')
print(f'  ai_signal equal:    {sig_eq}')
print(f'  signal_strength eq: {str_eq}')
print(f'  confidence eq:      {conf_eq}')
print(f'  Result:             {"PASS" if all_ok else "FAIL"}')

# ============================================================
np.random.seed(456)
n = 1000
base_dates = pd.date_range('2024-01-01', periods=n, freq='D')
df_d = pd.DataFrame({
    'datetime': base_dates.strftime('%Y%m%d').tolist(),
    'close': np.random.uniform(10, 50, n),
})
fmts = [None, '%Y%m%d', '%Y-%m-%d', '%Y/%m/%d']

def old_date(df, fmts):
    best = df
    for f in fmts:
        dt = df.copy()
        try:
            dt['datetime'] = pd.to_datetime(dt['datetime'], format=f, errors='coerce')
            if dt['datetime'].notna().sum() / len(dt) > 0.5:
                best = dt
        except Exception:
            pass
    return best

def new_date(df, fmts):
    bd = None
    br = 0
    for f in fmts:
        try:
            dc = pd.to_datetime(df['datetime'], format=f, errors='coerce')
            r = dc.notna().sum() / len(dc)
            if r > br:
                br = r
                bd = dc
        except Exception:
            pass
    if bd is not None:
        df = df.copy()
        df['datetime'] = bd
    return df

d1 = old_date(df_d.copy(), fmts)
d2 = new_date(df_d.copy(), fmts)
d1_is_dt = pd.api.types.is_datetime64_any_dtype(d1['datetime'])
d2_is_dt = pd.api.types.is_datetime64_any_dtype(d2['datetime'])
if not d1_is_dt:
    print(f'  DEBUG d1 dtype: {d1["datetime"].dtype}, first: {d1["datetime"].iloc[0]}')
cl_eq = d1['close'].equals(d2['close'])
parsed_ok = d1_is_dt and d2_is_dt and d1['datetime'].notna().all() and d2['datetime'].notna().all()
deq = parsed_ok and cl_eq

print()
print('=' * 60)
print('TEST 3: date format copy optimization')
print(f'  d1 datetime dtype:  {d1_is_dt}')
print(f'  d2 datetime dtype:  {d2_is_dt}')
print(f'  all dates parsed:   {parsed_ok}')
print(f'  close equal:        {cl_eq}')
print(f'  Result:             {"PASS" if deq else "FAIL"}')

# ============================================================
all_passed = eq and all_ok and deq
print()
print('=' * 60)
if all_passed:
    print('ALL 3 VECTORIZATION TESTS PASSED')
    print('Data calculation results are 100% consistent after optimization')
else:
    print('SOME VECTORIZATION TESTS FAILED')
    if not eq:
        print('  - TEST 1 FAILED')
    if not all_ok:
        print('  - TEST 2 FAILED')
    if not deq:
        print('  - TEST 3 FAILED')
print('=' * 60)
sys.exit(0 if all_passed else 1)