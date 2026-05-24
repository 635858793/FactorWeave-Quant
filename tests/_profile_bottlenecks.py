"""瓶颈剖析：精确定位延迟热点并测试替代方案"""
import time, sys, gc, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
np.random.seed(42)

TIMES = {}

def bench(name, fn, warmup=1, repeat=5):
    gc.collect()
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(repeat):
        gc.collect()
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    avg = np.mean(times)
    TIMES[name] = avg
    return avg

N = 50000

# ============================================================
print("=" * 80)
print("瓶颈剖析：DataFrame → Python 对象 转换")
print("=" * 80)

df = pd.DataFrame({
    'symbol': np.random.choice([f'{c:06d}' for c in range(600000, 602000)], N),
    'open': np.random.uniform(10, 100, N),
    'high': np.random.uniform(10, 100, N),
    'low': np.random.uniform(10, 100, N),
    'close': np.random.uniform(10, 100, N),
    'volume': np.random.uniform(1e6, 1e9, N),
})

# ------------------------------------------------
print("\n--- to_dict('records') 各列开销分析 ---")

# 基线：空列
t_empty = bench("空列 to_dict", lambda: df[[]].to_dict('records'))
print(f"  空列(单列)       : {t_empty:.1f}ms  (baseline)")

# 递增列数
for ncols in [1, 3, 6]:
    cols = ['symbol', 'open', 'high', 'low', 'close', 'volume'][:ncols]
    sub = df[cols]
    t = bench(f"to_dict {ncols}列", lambda: sub.to_dict('records'))
    per_col = (t - t_empty) / max(ncols, 1)
    print(f"  to_dict {ncols}列        : {t:.1f}ms  (+{t-t_empty:.1f}ms, {per_col:.1f}ms/列)")

# ------------------------------------------------
print("\n--- to_dict('records') vs 替代方案 ---")

# 当前方案
t_records = bench("to_dict('records')  6列", lambda: df.to_dict('records'))

# NumPy 数组转换
def to_numpy_records():
    return df.to_numpy().tolist()

t_numpy = bench("to_numpy().tolist() 6列", lambda: to_numpy_records())
print(f"  to_dict('records')   : {t_records:.1f}ms  (当前方案)")
print(f"  to_numpy().tolist()  : {t_numpy:.1f}ms  (比值: {t_numpy/t_records:.2f}x)")

# itertuples
def to_tuples():
    return list(df.itertuples(index=False, name=None))

t_tuples = bench("itertuples 6列", lambda: to_tuples())
print(f"  itertuples (纯tuple) : {t_tuples:.1f}ms  (比值: {t_tuples/t_records:.2f}x)")

# 按列 zip
def to_zip():
    return list(zip(df['symbol'], df['open'], df['high'], df['low'], df['close'], df['volume']))

t_zip = bench("zip(columns) 6列", lambda: to_zip())
print(f"  zip(逐列)            : {t_zip:.1f}ms  (比值: {t_zip/t_records:.2f}x)")

# ============================================================
print("\n" + "=" * 80)
print("瓶颈剖析：日期格式化")
print("=" * 80)

dates = pd.date_range('2024-01-01', periods=N, freq='1min')

# .dt.strftime
t_dt_strftime = bench("Series.dt.strftime", lambda: dates.strftime('%Y-%m-%d'))
print(f"  Series.dt.strftime      : {t_dt_strftime:.1f}ms")

# .dt.strftime 简化格式
t_dt_strf_short = bench("Series.dt.strftime short", lambda: dates.strftime('%Y%m%d'))
print(f"  Series.dt.strftime(short): {t_dt_strf_short:.1f}ms")

# astype(str) + string slicing
def str_slice():
    return dates.astype(str).str[:10]

t_str_slice = bench("astype(str).str[:10]", lambda: str_slice())
print(f"  astype(str).str[:10]    : {t_str_slice:.1f}ms  (比值: {t_str_slice/t_dt_strftime:.2f}x)")

# NumPy datetime64 → 字符串
def numpy_strftime():
    return pd.Index(dates.values).strftime('%Y-%m-%d')

t_np_strf = bench("numpy nat→str", lambda: numpy_strftime())
print(f"  numpy nat→str           : {t_np_strf:.1f}ms  (比值: {t_np_strf/t_dt_strftime:.2f}x)")

# 预计算日期（最优方案：在数据生成时就格式化好）
def preformatted():
    s = pd.Series([d.strftime('%Y-%m-%d') for d in dates[:N]])
    return s

t_pre = bench("预格式化(list comp)", lambda: preformatted())
print(f"  预格式化(list comp)     : {t_pre:.1f}ms  (比值: {t_pre/t_dt_strftime:.2f}x)")

# ============================================================
print("\n" + "=" * 80)
print("瓶颈剖析：dtype 影响分析")
print("=" * 80)

# float64 vs float32
df_f64 = pd.DataFrame({
    'open': np.random.uniform(10, 100, N).astype(np.float64),
    'close': np.random.uniform(10, 100, N).astype(np.float64),
    'volume': np.random.uniform(1e6, 1e9, N).astype(np.float64),
})
df_f32 = pd.DataFrame({
    'open': np.random.uniform(10, 100, N).astype(np.float32),
    'close': np.random.uniform(10, 100, N).astype(np.float32),
    'volume': np.random.uniform(1e6, 1e9, N).astype(np.float32),
})

t_f64 = bench("float64 3列 to_dict", lambda: df_f64.to_dict('records'))
t_f32 = bench("float32 3列 to_dict", lambda: df_f32.to_dict('records'))
print(f"  float64 3列    : {t_f64:.1f}ms")
print(f"  float32 3列    : {t_f32:.1f}ms  (比值: {t_f32/t_f64:.2f}x)")

# int 列
df_int = pd.DataFrame({
    'volume': np.random.randint(1e6, 1e9, N).astype(np.int64),
})
df_int32 = pd.DataFrame({
    'volume': np.random.randint(1e6, 1e9, N).astype(np.int32),
})
t_i64 = bench("int64 1列 to_dict", lambda: df_int.to_dict('records'))
t_i32 = bench("int32 1列 to_dict", lambda: df_int32.to_dict('records'))
print(f"  int64 1列      : {t_i64:.1f}ms")
print(f"  int32 1列      : {t_i32:.1f}ms  (比值: {t_i32/t_i64:.2f}x)")

# ============================================================
print("\n" + "=" * 80)
print("瓶颈剖析：批量 vs 分块 处理")
print("=" * 80)

CHUNK_SIZE = 5000
N_CHUNKS = N // CHUNK_SIZE

# 一次性处理
t_bulk = bench("批量 50000条", lambda: df.to_dict('records'))

# 分块处理
def chunked():
    results = []
    for i in range(0, N, CHUNK_SIZE):
        chunk = df.iloc[i:i+CHUNK_SIZE].to_dict('records')
        results.extend(chunk)
    return results

t_chunk = bench("分块 5000×10", lambda: chunked())
print(f"  批量 50000条        : {t_bulk:.1f}ms")
print(f"  分块 5000×10      : {t_chunk:.1f}ms  (比值: {t_chunk/t_bulk:.2f}x)")
print(f"  分块效率           : {'更优(可并行)' if t_chunk < t_bulk * 1.1 else '接近'}")

# ============================================================
print("\n" + "=" * 80)
print("瓶颈剖析：set_index + to_dict('index') 深度分析")
print("=" * 80)

sym_unique = df.drop_duplicates(subset=['symbol'])

t_set_idx = bench("set_index+to_dict", lambda: sym_unique.set_index('symbol')[['open', 'close']].to_dict('index'))

def dict_comprehension():
    return {row.symbol: {'open': row.open, 'close': row.close}
            for row in sym_unique.itertuples(index=False)}

t_dict_comp = bench("dict comprehension", lambda: dict_comprehension())
print(f"  set_index+to_dict(index) : {t_set_idx:.1f}ms")
print(f"  dict comprehension(iter) : {t_dict_comp:.1f}ms  (比值: {t_dict_comp/t_set_idx:.2f}x)")

# ============================================================
print("\n" + "=" * 80)
print("瓶颈剖析：信号生成管线逐操作开销")
print("=" * 80)

sig_df = pd.DataFrame({
    'close': np.random.uniform(10, 100, N),
    'volume': np.random.uniform(1e6, 1e9, N),
})

t_ma5 = bench("rolling(5).mean()", lambda: sig_df['close'].rolling(5).mean())
t_ma20 = bench("rolling(20).mean()", lambda: sig_df['close'].rolling(20).mean())
t_pct = bench("pct_change()", lambda: sig_df['close'].pct_change())
t_select = bench("np.select 3-cond", lambda: np.select(
    [sig_df['close'] > sig_df['close'].shift(1) * 1.02,
     sig_df['close'] < sig_df['close'].shift(1) * 0.98],
    [1, -1], default=0))
t_diff = bench("diff()", lambda: sig_df['close'].diff())
t_abs = bench("abs()", lambda: sig_df['close'].diff().abs())

print(f"  rolling(5).mean()  : {t_ma5:.2f}ms")
print(f"  rolling(20).mean() : {t_ma20:.2f}ms")
print(f"  pct_change()       : {t_pct:.2f}ms")
print(f"  np.select(3条件)   : {t_select:.2f}ms")
print(f"  diff()             : {t_diff:.2f}ms")
print(f"  abs()              : {t_abs:.2f}ms")

# ============================================================
print("\n" + "=" * 80)
print("瓶颈剖析：并发场景下的 GIL 争用")
print("=" * 80)

from concurrent.futures import ThreadPoolExecutor

def cpu_heavy(seed):
    np.random.seed(seed)
    n = 3000
    local = pd.DataFrame({
        'open': np.random.uniform(10, 100, n),
        'close': np.random.uniform(10, 100, n),
    })
    local['ma5'] = local['close'].rolling(5).mean()
    local['signal'] = np.select(
        [local['close'] > local['open'] * 1.02,
         local['close'] < local['open'] * 0.98],
        [1, -1], default=0)
    return local.to_dict('records')

# 单线程
t_serial = bench("单线程 10×3000条", lambda: [cpu_heavy(i) for i in range(10)], repeat=3)

# 4线程
def parallel_4():
    with ThreadPoolExecutor(max_workers=4) as e:
        list(e.map(cpu_heavy, range(10)))
t_par4 = bench("4线程 10×3000条", lambda: parallel_4(), repeat=3)

# 8线程
def parallel_8():
    with ThreadPoolExecutor(max_workers=8) as e:
        list(e.map(cpu_heavy, range(10)))
t_par8 = bench("8线程 10×3000条", lambda: parallel_8(), repeat=3)

print(f"  单线程 (10×3000)  : {t_serial:.1f}ms")
print(f"  4线程  (10×3000)  : {t_par4:.1f}ms  (加速比: {t_serial/t_par4:.2f}x)")
print(f"  8线程  (10×3000)  : {t_par8:.1f}ms  (加速比: {t_serial/t_par8:.2f}x)")

# ============================================================
print("\n" + "=" * 80)
print("瓶颈剖析汇总 & 优化建议")
print("=" * 80)

# 计算每个操作的相对权重
names = [
    "to_dict('records') 6列", "itertuples 6列", "zip(columns) 6列",
    "Series.dt.strftime", "astype(str).str[:10]",
    "float64 3列 to_dict", "float32 3列 to_dict",
    "dict comprehension", "set_index+to_dict"
]
vals = {n: TIMES[n] for n in names}

print(f"\n{'操作':<35} {'耗时(ms)':>10} {'相对耗时':>10} {'瓶颈等级':>10}")
print("-" * 68)

max_t = max(vals.values())
for name, t in sorted(vals.items(), key=lambda x: x[1], reverse=True):
    rel = t / max_t * 100
    if rel > 80:
        level = "🔴 严重"
    elif rel > 40:
        level = "🟡 中等"
    elif rel > 10:
        level = "🟢 轻微"
    else:
        level = "⚪ 可忽略"
    print(f"{name:<35} {t:>8.1f}ms {rel:>9.0f}% {level:>10}")

print(f"\n优化建议：")
print(f"  1. to_dict('records') 是最大瓶颈，占绝对主导地位")
if TIMES.get("float64 3列 to_dict", 0) > 0 and TIMES.get("float32 3列 to_dict", 0) > 0:
    f64 = TIMES["float64 3列 to_dict"]
    f32 = TIMES["float32 3列 to_dict"]
    if f32 / f64 < 0.95:
        print(f"     → 考虑 float32 替代 float64（节省 {((1-f32/f64)*100):.0f}%）")
if TIMES.get("astype(str).str[:10]", 0) > 0:
    strf = TIMES.get("Series.dt.strftime", 0)
    alt = TIMES["astype(str).str[:10]"]
    if alt / strf < 0.9:
        print(f"     → strftime 可用 astype(str).str[:10] 替代（节省 {((1-alt/strf)*100):.0f}%）")
print(f"  2. 图表数据可考虑分块传输（WebSocket 流式推送），避免单次 to_dict 阻塞")

ser = TIMES.get("单线程 10×3000条", 0)
par = TIMES.get("4线程 10×3000条", 0)
if ser > 0 and par > 0 and ser / par < 1.5:
    print(f"  3. 并发加速比有限（{ser/par:.1f}x），DataFrame 操作受 GIL 限制")
    print(f"     → 重度计算考虑 ProcessPoolExecutor 或外部进程")
else:
    print(f"  3. 并发加速比良好（{ser/par:.1f}x），多线程可以为 IO 密集型操作提供帮助")

print(f"\n✅ 瓶颈剖析完成")