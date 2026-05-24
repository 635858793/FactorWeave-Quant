"""
executemany 批量写入 vs 逐行 INSERT 基准测试
模拟 stock_service.py batch_update_stock_shares 重构效果
"""
import os
import time
import tempfile
import duckdb


def setup_db():
    db_path = os.path.join(tempfile.gettempdir(), 'hikyuu_bench_executemany.duckdb')
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = duckdb.connect(db_path)
    conn.execute("""
        CREATE TABLE stock_shares (
            stock_code VARCHAR,
            stock_name VARCHAR,
            total_shares DOUBLE,
            circulating_shares DOUBLE,
            total_market_cap DOUBLE,
            circulating_market_cap DOUBLE,
            update_date TIMESTAMP,
            PRIMARY KEY (stock_code, update_date)
        )
    """)
    conn.close()
    return db_path


def gen_records(n):
    from datetime import datetime
    records = []
    for i in range(n):
        records.append({
            'code': f'{600000 + i:06d}',
            'name': f'测试股票{i}',
            'total': 1000000000 + i * 100000,
            'circulating': 800000000 + i * 80000,
            'cap': 15000000000 + i * 1000000,
            'cir_cap': 12000000000 + i * 900000,
        })
    return records


SQL_INSERT = """
    INSERT INTO stock_shares
    (stock_code, stock_name, total_shares, circulating_shares,
     total_market_cap, circulating_market_cap, update_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (stock_code, update_date)
    DO UPDATE SET
        stock_name = excluded.stock_name,
        total_shares = excluded.total_shares,
        circulating_shares = excluded.circulating_shares,
        total_market_cap = excluded.total_market_cap,
        circulating_market_cap = excluded.circulating_market_cap
"""

SQL_CREATE = """
    CREATE TABLE IF NOT EXISTS stock_shares (
        stock_code VARCHAR,
        stock_name VARCHAR,
        total_shares DOUBLE,
        circulating_shares DOUBLE,
        total_market_cap DOUBLE,
        circulating_market_cap DOUBLE,
        update_date TIMESTAMP,
        PRIMARY KEY (stock_code, update_date)
    )
"""


def bench_old_n_inserts(db_path, records):
    """逐行 INSERT — 每次一条 (旧方案)"""
    from datetime import datetime
    update_date = datetime.now()
    conn = duckdb.connect(db_path)
    conn.execute("DELETE FROM stock_shares")
    t0 = time.time()
    for r in records:
        conn.execute(SQL_INSERT, (
            r['code'], r['name'], r['total'], r['circulating'],
            r['cap'], r['cir_cap'], update_date
        ))
    elapsed = time.time() - t0
    conn.close()
    return elapsed


def bench_new_executemany(db_path, records):
    """批量 executemany — 一次提交 (新方案)"""
    from datetime import datetime
    update_date = datetime.now()
    conn = duckdb.connect(db_path)
    conn.execute("DELETE FROM stock_shares")
    batch = [
        (r['code'], r['name'], r['total'], r['circulating'],
         r['cap'], r['cir_cap'], update_date)
        for r in records
    ]
    t0 = time.time()
    conn.executemany(SQL_INSERT, batch)
    elapsed = time.time() - t0
    conn.close()
    return elapsed


def main():
    print("=" * 60)
    print("  executemany vs 逐行 INSERT — stock_shares 基准测试")
    print("=" * 60)

    sizes = [500, 1000, 5000]
    results = []

    for n in sizes:
        db_path = setup_db()
        records = gen_records(n)
        print(f"\n--- {n} 条记录 ---")

        t_old = bench_old_n_inserts(db_path, records)
        t_new = bench_new_executemany(db_path, records)

        speedup = t_old / t_new if t_new > 0 else float('inf')
        pct = (1 - t_new / t_old) * 100 if t_old > 0 else 0

        print(f"  逐行 INSERT:   {t_old:.4f}s ({t_old*1000:.1f}ms)")
        print(f"  executemany:   {t_new:.4f}s ({t_new*1000:.1f}ms)")
        print(f"  加速比:        {speedup:.1f}x ({pct:.0f}%时间节省)")

        results.append({'n': n, 'old': t_old, 'new': t_new, 'speedup': speedup})
        os.remove(db_path)

    print("\n" + "=" * 60)
    print("  汇总")
    print("=" * 60)
    for r in results:
        print(f"  {r['n']:>6} 条 → {r['old']*1000:>8.1f}ms → {r['new']*1000:>8.1f}ms = {r['speedup']:.1f}x")

    all_old = sum(r['old'] for r in results)
    all_new = sum(r['new'] for r in results)
    print(f"  合计 {sum(r['n'] for r in results)} 条 → {all_old*1000:.0f}ms → {all_new*1000:.0f}ms = {all_old/all_new:.1f}x")


if __name__ == '__main__':
    main()