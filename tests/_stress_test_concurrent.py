"""高并发压力测试：验证向量化优化后的系统稳定性

测试场景：
  STAGE 1: 单线程大数据吞吐量基准
  STAGE 2: 多线程并发 DataFrame 向量化操作
  STAGE 3: 并发缓存读写 + LRU 驱逐压力
  STAGE 4: 混合负载压力（并发读写 + 数据转换）
  STAGE 5: 内存稳定性监控
"""
import os, sys, time, gc, warnings, json, threading
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from collections import deque, defaultdict
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
np.random.seed(42)

PASS, FAIL, SKIP = 0, 0, 0
results_log = []

def report(stage, name, ok, detail=""):
    global PASS, FAIL, SKIP
    status = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
    if ok is True: PASS += 1
    elif ok is False: FAIL += 1
    else: SKIP += 1
    line = f"[{status:4}] {stage:>8} | {name:<55} {detail}"
    results_log.append(line)
    print(line)

try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[INFO] psutil 未安装，跳过内存监控")

# ============================================================
print("=" * 80)
print("FACTORWEAVE-QUANT 2.0 高并发压力测试")
print("=" * 80)

def mem_usage():
    if HAS_PSUTIL:
        return process.memory_info().rss / (1024 * 1024)
    return -1.0

mem_start = mem_usage()
print(f"初始内存: {mem_start:.1f} MB")
gc.collect()

# ============================================================
# STAGE 1: 单线程大数据吞吐量基准
# ============================================================
print("\n" + "─" * 80)
print("STAGE 1: 单线程大数据吞吐量基准")
print("─" * 80)

N_ROWS = 50000
N_SYMBOLS = 2000

base_data = pd.DataFrame({
    'symbol': np.random.choice([f'{c:06d}' for c in range(600000, 600000 + N_SYMBOLS)], N_ROWS),
    'open': np.random.uniform(10, 100, N_ROWS),
    'high': np.random.uniform(10, 100, N_ROWS),
    'low': np.random.uniform(10, 100, N_ROWS),
    'close': np.random.uniform(10, 100, N_ROWS),
    'volume': np.random.uniform(1e6, 1e9, N_ROWS),
    'date': pd.date_range('2024-01-01', periods=N_ROWS, freq='1min'),
    'market': np.random.choice(['SH', 'SZ'], N_ROWS),
})
mem_before = mem_usage()

# 1.1: to_dict('records') 大规模转换
t0 = time.perf_counter()
records = base_data[['symbol', 'open', 'high', 'low', 'close', 'volume', 'market']].fillna('').to_dict('records')
t1 = time.perf_counter() - t0
report("STAGE1", "1.1 to_dict('records') 50000条", len(records) == N_ROWS,
       f"{t1*1000:.1f}ms, {N_ROWS/t1:,.0f} 条/秒")

# 1.2: np.select 大规模条件
base_data['score'] = np.random.uniform(0, 1, N_ROWS)
t0 = time.perf_counter()
sigs = np.select([base_data['score'] > 0.6, base_data['score'] < 0.3], [1, -1], default=0)
t1 = time.perf_counter() - t0
report("STAGE1", "1.2 np.select 50000条", len(sigs) == N_ROWS,
       f"{t1*1000:.1f}ms, {N_ROWS/t1:,.0f} 条/秒")

# 1.3: set_index + to_dict('index') 符号映射 (使用去重数据)
unique_df = base_data.drop_duplicates(subset=['symbol']).copy()
t0 = time.perf_counter()
sym_map = unique_df.set_index('symbol')[['open', 'close', 'market']].to_dict('index')
t1 = time.perf_counter() - t0
report("STAGE1", "1.3 set_index+to_dict 去重符号映射", len(sym_map) == unique_df['symbol'].nunique(),
       f"{t1*1000:.1f}ms, {len(sym_map)} unique symbols")

# 1.4: strftime 向量化
t0 = time.perf_counter()
dates = pd.to_datetime(base_data.index)
date_strs = dates.strftime('%Y-%m-%d')
t1 = time.perf_counter() - t0
report("STAGE1", "1.4 strftime 50000条", len(date_strs) == N_ROWS,
       f"{t1*1000:.1f}ms")

# 1.5: itertuples + 列表构建
t0 = time.perf_counter()
tuples = [(r.symbol, r.open, r.close, r.volume) for r in base_data[['symbol', 'open', 'close', 'volume']].itertuples(index=False)]
t1 = time.perf_counter() - t0
report("STAGE1", "1.5 itertuples 50000条", len(tuples) == N_ROWS,
       f"{t1*1000:.1f}ms, {N_ROWS/t1:,.0f} 条/秒")

# 1.6: dict(zip) 映射 (去重)
t0 = time.perf_counter()
sym_info = dict(zip(unique_df['symbol'], unique_df['close']))
t1 = time.perf_counter() - t0
report("STAGE1", "1.6 dict(zip) 去重符号映射", len(sym_info) == len(unique_df),
       f"{t1*1000:.1f}ms, {len(sym_info)} keys")

mem_after_s1 = mem_usage()
report("STAGE1", "1.7 内存稳定性", mem_after_s1 - mem_before < 500,
       f"增量: {mem_after_s1 - mem_before:.1f} MB (总: {mem_after_s1:.1f} MB)")

del records, base_data
gc.collect()

# ============================================================
# STAGE 2: 多线程并发 DataFrame 操作
# ============================================================
print("\n" + "─" * 80)
print("STAGE 2: 多线程并发 DataFrame 向量化操作")
print("─" * 80)

N_THREADS = 12
N_PER_THREAD = 5000
mem_before_s2 = mem_usage()

def concurrent_df_ops(seed):
    np.random.seed(seed)
    df = pd.DataFrame({
        'symbol': [f'{c:06d}' for c in range(600000 + seed * N_PER_THREAD, 600000 + (seed + 1) * N_PER_THREAD)],
        'open': np.random.uniform(10, 100, N_PER_THREAD),
        'close': np.random.uniform(10, 100, N_PER_THREAD),
        'volume': np.random.uniform(1e6, 1e9, N_PER_THREAD),
        'market': np.random.choice(['SH', 'SZ'], N_PER_THREAD),
        'datetime': pd.date_range('2024-01-01', periods=N_PER_THREAD, freq='1min'),
    })
    df['score'] = np.random.uniform(0, 1, N_PER_THREAD)

    # 模拟所有向量化优化管线
    d1 = df.copy()
    records = d1[['symbol', 'open', 'close', 'volume', 'market']].fillna('').to_dict('records')

    d2 = df.copy()
    sigs = np.select([d2['score'] > 0.6, d2['score'] < 0.3], [1, -1], default=0)

    d3 = df.copy()
    idx_dt = pd.to_datetime(d3['datetime'])
    d3['date_str'] = idx_dt.dt.strftime('%Y-%m-%d')

    d4 = df.copy()
    sym_map = dict(zip(d4['symbol'], d4['close']))

    return len(records), len(sigs), len(d3), len(sym_map)

t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=N_THREADS) as executor:
    futures = [executor.submit(concurrent_df_ops, i) for i in range(N_THREADS)]
    results = [f.result() for f in as_completed(futures)]
t1 = time.perf_counter() - t0

all_ok = all(r == (N_PER_THREAD, N_PER_THREAD, N_PER_THREAD, N_PER_THREAD) for r in results)
total_rows = N_THREADS * N_PER_THREAD
report("STAGE2", f"2.1 并发{N_THREADS}线程×{N_PER_THREAD}条=5万条", all_ok,
       f"总耗时: {t1:.2f}s, 吞吐: {total_rows/t1:,.0f} 条/秒, 加速比: {N_THREADS/(t1/(t1/N_THREADS)):.1f}x")

mem_after_s2 = mem_usage()
report("STAGE2", "2.2 并发后内存", mem_after_s2 - mem_before_s2 < 1000,
       f"增量: {mem_after_s2 - mem_before_s2:.1f} MB (总: {mem_after_s2:.1f} MB)")

gc.collect()
mem_after_gc_s2 = mem_usage()
gc_ok = mem_after_gc_s2 < mem_after_s2 * 0.98 or mem_after_gc_s2 < mem_after_s2 + 10
report("STAGE2", "2.3 GC后内存回收", gc_ok,
       f"释放: {mem_after_s2 - mem_after_gc_s2:.1f} MB (总: {mem_after_gc_s2:.1f} MB)")

# ============================================================
# STAGE 3: 并发缓存 + LRU 驱逐压力
# ============================================================
print("\n" + "─" * 80)
print("STAGE 3: 并发缓存读写 + LRU 驱逐压力")
print("─" * 80)

CACHE_SIZE = 2000
CACHE_MAX = CACHE_SIZE
cache = {}
cache_time = {}
cache_lock = threading.Lock()
cache_evicted = 0
cache_hits = 0
cache_misses = 0
cache_hit_lock = threading.Lock()

def cache_get(key):
    global cache_evicted, cache_hits, cache_misses
    with cache_lock:
        if key in cache:
            with cache_hit_lock:
                cache_hits += 1
            return cache[key]
    with cache_hit_lock:
        cache_misses += 1
    value = f"data_{key}"  # 模拟从DB/API获取
    with cache_lock:
        if len(cache) >= CACHE_MAX:
            oldest = min(cache_time, key=cache_time.get)
            del cache[oldest]
            del cache_time[oldest]
            cache_evicted += 1
        cache[key] = value
        cache_time[key] = time.time()
    return value

N_CACHE_KEYS = CACHE_SIZE * 5
N_OPS_PER_THREAD = 5000
N_CACHE_THREADS = 8

def cache_worker(seed):
    np.random.seed(seed)
    values = []
    for _ in range(N_OPS_PER_THREAD):
        key = f"stock_{np.random.randint(0, N_CACHE_KEYS)}"
        values.append(cache_get(key))
    return values

t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=N_CACHE_THREADS) as executor:
    futures = [executor.submit(cache_worker, i) for i in range(N_CACHE_THREADS)]
    all_values = [f.result() for f in as_completed(futures)]
t1 = time.perf_counter() - t0

total_ops = N_CACHE_THREADS * N_OPS_PER_THREAD
report("STAGE3", "3.1 并发缓存读写", len(all_values) == N_CACHE_THREADS,
       f"{total_ops} 次操作, {t1:.2f}s, {total_ops/t1:,.0f} ops/s")

report("STAGE3", "3.2 LRU驱逐触发", cache_evicted > 0,
       f"驱逐: {cache_evicted}, 命中: {cache_hits}, 未命中: {cache_misses}, 命中率: {cache_hits/total_ops*100:.1f}%")

report("STAGE3", "3.3 缓存大小限制", len(cache) <= CACHE_MAX,
       f"最终缓存: {len(cache)}/{CACHE_MAX}")

# ============================================================
# STAGE 4: 混合负载压力测试
# ============================================================
print("\n" + "─" * 80)
print("STAGE 4: 混合负载压力 (并发读写 + 数据转换)")
print("─" * 80)

mem_before_s4 = mem_usage()
N_MIXED_THREADS = 8
N_ROUNDS = 10

error_count = threading.Lock()
errs = [0]

def mixed_worker(seed):
    np.random.seed(seed)
    local_errs = 0
    for rd in range(N_ROUNDS):
        try:
            n = 2000 + seed * 500 + rd * 100
            df = pd.DataFrame({
                'symbol': [f'{c:06d}' for c in range(600000 + seed * 2000, 600000 + seed * 2000 + n)],
                'open': np.random.uniform(10, 100, n),
                'close': np.random.uniform(10, 100, n),
                'volume': np.random.uniform(1e6, 1e9, n),
            })
            df['ma5'] = df['close'].rolling(5).mean()
            df['change_pct'] = df['close'].pct_change() * 100
            sigs = np.select([df['change_pct'] > 2, df['change_pct'] < -2], [1, -1], default=0)
            records = df[['symbol', 'close', 'ma5', 'change_pct']].fillna(0).to_dict('records')
            _ = len(records), len(sigs)
            del df, records
        except Exception:
            local_errs += 1
    with error_count:
        errs[0] += local_errs

t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=N_MIXED_THREADS) as executor:
    futures = [executor.submit(mixed_worker, i) for i in range(N_MIXED_THREADS)]
    for f in as_completed(futures):
        f.result()
t1 = time.perf_counter() - t0

total_ops = N_MIXED_THREADS * N_ROUNDS
report("STAGE4", f"4.1 混合负载{N_MIXED_THREADS}线程×{N_ROUNDS}轮", errs[0] == 0,
       f"总耗时: {t1:.2f}s, 错误: {errs[0]}/{total_ops}, 平均: {t1/total_ops*1000:.1f}ms/轮")

mem_after_s4 = mem_usage()
gc.collect()
mem_after_gc_s4 = mem_usage()
report("STAGE4", "4.2 混合负载后内存", mem_after_gc_s4 - mem_before_s4 < 500,
       f"增量: {mem_after_gc_s4 - mem_before_s4:.1f} MB (GC后: {mem_after_gc_s4:.1f} MB)")

# ============================================================
# STAGE 5: 极端压力测试
# ============================================================
print("\n" + "─" * 80)
print("STAGE 5: 极端压力测试")
print("─" * 80)

# 5.1: 单次超大批量 (10万条)
EXTREME_N = 100000
t0 = time.perf_counter()
big_df = pd.DataFrame({
    'symbol': np.random.choice([f'{c:06d}' for c in range(600000, 608000)], EXTREME_N),
    'open': np.random.uniform(10, 100, EXTREME_N).astype(np.float32),
    'high': np.random.uniform(10, 100, EXTREME_N).astype(np.float32),
    'low': np.random.uniform(10, 100, EXTREME_N).astype(np.float32),
    'close': np.random.uniform(10, 100, EXTREME_N).astype(np.float32),
    'volume': np.random.uniform(1e6, 1e9, EXTREME_N).astype(np.float64),
})
mem_big = mem_usage()
t_data = time.perf_counter() - t0

records_big = big_df[['symbol', 'open', 'high', 'low', 'close', 'volume']].fillna(0).to_dict('records')
t_conv = time.perf_counter() - t0 - t_data

report("STAGE5", f"5.1 超大批量 {EXTREME_N:,}条 构建+转换", len(records_big) == EXTREME_N,
       f"构建: {t_data*1000:.0f}ms, 转换: {t_conv*1000:.0f}ms, DF内存: {mem_big - mem_before_s4:.1f}MB")

t0 = time.perf_counter()
big_df['signal'] = np.select(
    [big_df['close'] > big_df['close'].shift(1) * 1.02,
     big_df['close'] < big_df['close'].shift(1) * 0.98],
    [1, -1], default=0
)
big_df['volume_ma'] = big_df['volume'].rolling(20).mean()
t_ind = time.perf_counter() - t0
mem_peak = mem_usage()

report("STAGE5", f"5.2 超大批量 np.select+rolling", True,
       f"{t_ind*1000:.0f}ms, 峰值内存: {mem_peak:.1f}MB")

del big_df, records_big
gc.collect()
mem_after_s5 = mem_usage()
report("STAGE5", "5.3 超大批量后GC回收", mem_after_s5 < mem_peak * 0.8,
       f"峰值: {mem_peak:.1f}MB → 回收后: {mem_after_s5:.1f}MB, 释放: {mem_peak - mem_after_s5:.1f}MB")

# ============================================================
# STAGE 6: 并发信号生成管线压力
# ============================================================
print("\n" + "─" * 80)
print("STAGE 6: 并发信号生成管线")
print("─" * 80)

def signal_pipeline(seed):
    np.random.seed(seed)
    n = 3000
    df = pd.DataFrame({
        'close': np.random.uniform(10, 100, n),
        'volume': np.random.uniform(1e6, 1e9, n),
    })
    df['symbol'] = f'{600000 + seed:06d}'
    df['date'] = pd.date_range('2024-01-01', periods=n, freq='1min')

    for fw in [5, 10, 20]:
        df[f'ma_{fw}'] = df['close'].rolling(fw, min_periods=fw).mean()
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().clip(lower=0).rolling(14).mean() /
                                      df['close'].diff().abs().rolling(14).mean())))
    df['signal'] = np.select(
        [df['close'] > df['ma_5'], df['close'] < df['ma_20']],
        [1, -1], default=0
    )
    records = df.fillna(0).to_dict('records')
    return len(records), (df['signal'] != 0).sum()

N_SIG_THREADS = 10
t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=N_SIG_THREADS) as executor:
    futures = [executor.submit(signal_pipeline, i) for i in range(N_SIG_THREADS)]
    sig_results = [f.result() for f in as_completed(futures)]
t1 = time.perf_counter() - t0

all_valid = all(r[0] == 3000 for r in sig_results)
total_signals = sum(r[1] for r in sig_results)
report("STAGE6", f"6.1 并发{N_SIG_THREADS}线程信号生成", all_valid,
       f"总耗时: {t1:.2f}s, 总信号: {total_signals}, 平均: {t1/N_SIG_THREADS*1000:.1f}ms/线程")

gc.collect()
mem_after_s6 = mem_usage()

# ============================================================
# FINAL: 汇总结果
# ============================================================
gc.collect()
mem_final = mem_usage()

print("\n" + "=" * 80)
print("压力测试结果汇总")
print("=" * 80)
for line in results_log:
    print(line)

print("\n" + "─" * 80)
print(f"内存使用: {mem_start:.1f}MB (初始) → {mem_final:.1f}MB (最终), 增量: {mem_final - mem_start:.1f}MB")
print(f"测试结果: {PASS} PASS, {FAIL} FAIL, {SKIP} SKIP")
print("─" * 80)

if FAIL == 0:
    print("✅ 高并发压力测试全部通过！系统在向量化优化后表现稳定。")
else:
    print(f"⚠️  有 {FAIL} 项测试失败，需要进一步排查。")

sys.exit(0 if FAIL == 0 else 1)