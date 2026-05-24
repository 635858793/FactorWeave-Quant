"""
10万行 CSV 导入基准测试
对比：旧方案(pd.read_csv + ALTER TABLE + iterrows INSERT) vs 新方案(DuckDB read_csv_auto)
"""
import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_CSV = os.path.join(os.path.dirname(__file__), '_stress_100k.csv')
TABLE_NAME = 'stress_test_benchmark'


def get_test_db_path():
    return os.path.join(tempfile.gettempdir(), 'hikyuu_bench_test.duckdb')


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def run_old_approach(file_path, db_path):
    """模拟旧方案: pd.read_csv → ALTER TABLE 逐列 → iterrows 逐行 INSERT"""
    import duckdb
    import pandas as pd

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = duckdb.connect(db_path)
    total_start = time.time()

    # 1. pandas 读取
    t0 = time.time()
    df = pd.read_csv(file_path)
    t_read = time.time() - t0
    columns = df.columns.tolist()
    col_count = len(columns)

    # 2. 创建表
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} (idx INTEGER)")

    # 3. ALTER TABLE 逐列
    t_alter_start = time.time()
    for col in columns:
        col_safe = col.replace(' ', '_').replace('(', '').replace(')', '').replace('"', '""')
        try:
            conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN IF NOT EXISTS \"{col_safe}\" TEXT")
        except Exception:
            pass
    t_alter = time.time() - t_alter_start

    # 4. iterrows 逐行 INSERT
    t_insert_start = time.time()
    placeholder_str = ','.join(['?' for _ in range(col_count + 1)])
    for i, row in df.iterrows():
        params = [i] + [str(v) if pd.notna(v) else None for v in row.values]
        conn.execute(f"INSERT INTO {TABLE_NAME} VALUES ({placeholder_str})", params)
    t_insert = time.time() - t_insert_start

    total_time = time.time() - total_start
    row_count = conn.execute(f"SELECT COUNT(*) AS cnt FROM {TABLE_NAME}").fetchone()[0]
    conn.close()

    return {
        'approach': 'OLD (pd.read_csv + ALTER + iterrows)',
        'total_time': total_time,
        'read_time': t_read,
        'alter_time': t_alter,
        'insert_time': t_insert,
        'row_count': row_count,
        'inserts': len(df),
        'ops_per_sec': len(df) / t_insert if t_insert > 0 else 0,
    }


def run_new_approach(file_path, db_path):
    """模拟新方案: DuckDB read_csv_auto 单条 SQL"""
    import duckdb

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = duckdb.connect(db_path)
    total_start = time.time()

    safe_path = file_path.replace("'", "''")

    # 单条 SQL: CREATE OR REPLACE TABLE AS SELECT FROM read_csv_auto
    t0 = time.time()
    conn.execute(f"""
        CREATE OR REPLACE TABLE {TABLE_NAME} AS
        SELECT row_number() OVER () - 1 AS idx, *
        FROM read_csv_auto('{safe_path}', header=true, all_varchar=false)
    """)
    t_exec = time.time() - t0

    total_time = time.time() - total_start
    row_count = conn.execute(f"SELECT COUNT(*) AS cnt FROM {TABLE_NAME}").fetchone()[0]

    # 验证列完整性
    cols_result = conn.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{TABLE_NAME}'")
    cols = [r[0] for r in cols_result.fetchall()]

    conn.close()

    return {
        'approach': 'NEW (DuckDB read_csv_auto)',
        'total_time': total_time,
        'exec_time': t_exec,
        'row_count': row_count,
        'col_count': len(cols),
        'columns': cols,
    }


def validate_integrity(db_path_old, db_path_new):
    """验证新旧方案导入数据一致性"""
    import duckdb

    conn_old = duckdb.connect(db_path_old)
    conn_new = duckdb.connect(db_path_new)

    count_old = conn_old.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    count_new = conn_new.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]

    conn_old.close()
    conn_new.close()

    return {
        'old_rows': count_old,
        'new_rows': count_new,
        'match': count_old == count_new,
    }


def main():
    if not os.path.exists(TEST_CSV):
        print(f"\n[ERROR] 测试文件不存在: {TEST_CSV}")
        print("请先运行: python tests/_gen_100k_csv.py")
        return

    csv_size_mb = os.path.getsize(TEST_CSV) / 1024 / 1024
    print_header(f"CSV 导入 10万行基准测试")
    print(f"  文件: {TEST_CSV}")
    print(f"  大小: {csv_size_mb:.1f} MB")

    # === 旧方案 ===
    print_header("方案A: 旧方案 (pd.read_csv + ALTER + iterrows INSERT)")
    db_old = os.path.join(tempfile.gettempdir(), 'hikyuu_bench_old.duckdb')
    result_old = run_old_approach(TEST_CSV, db_old)
    print(f"  读CSV耗时:       {result_old['read_time']:.3f}s")
    print(f"  ALTER TABLE耗时: {result_old['alter_time']:.3f}s")
    print(f"  INSERT耗时:      {result_old['insert_time']:.3f}s ({result_old['inserts']}行, {result_old['ops_per_sec']:.0f} ops/s)")
    print(f"  总耗时:          {result_old['total_time']:.3f}s")
    print(f"  导入行数:        {result_old['row_count']}")

    # === 新方案 ===
    print_header("方案B: 新方案 (DuckDB read_csv_auto 单条SQL)")
    db_new = os.path.join(tempfile.gettempdir(), 'hikyuu_bench_new.duckdb')
    result_new = run_new_approach(TEST_CSV, db_new)
    print(f"  执行耗时:        {result_new['exec_time']:.3f}s")
    print(f"  总耗时:          {result_new['total_time']:.3f}s")
    print(f"  导入行数:        {result_new['row_count']}")
    print(f"  列数:            {result_new['col_count']}")
    print(f"  列名:            {result_new['columns'][:5]}...")

    # === 对比 ===
    integrity = validate_integrity(db_old, db_new)
    speedup = result_old['total_time'] / result_new['total_time'] if result_new['total_time'] > 0 else float('inf')

    print_header("对比结果")
    print(f"  行数一致性:      {'PASS' if integrity['match'] else 'FAIL'} (old={integrity['old_rows']}, new={integrity['new_rows']})")
    print(f"  旧方案总耗时:    {result_old['total_time']:.3f}s")
    print(f"  新方案总耗时:    {result_new['total_time']:.3f}s")
    print(f"  加速比:          {speedup:.1f}x")
    print(f"  节省时间:        {result_old['total_time'] - result_new['total_time']:.3f}s")

    # === 多次运行取平均 ===
    print_header("稳定性验证 (新方案 5次运行)")
    times = []
    for lap in range(5):
        db_lap = os.path.join(tempfile.gettempdir(), f'hikyuu_bench_lap{lap}.duckdb')
        r = run_new_approach(TEST_CSV, db_lap)
        times.append(r['total_time'])
        print(f"  第{lap+1}次: {r['total_time']:.3f}s  ({r['row_count']}行)")
        if os.path.exists(db_lap):
            os.remove(db_lap)

    if len(times) >= 2:
        avg = sum(times) / len(times)
        min_t = min(times)
        max_t = max(times)
        print(f"\n  平均: {avg:.3f}s | 最快: {min_t:.3f}s | 最慢: {max_t:.3f}s | 波动: {max_t-min_t:.3f}s")

    # 清理
    for f in [db_old, db_new] + [
        os.path.join(tempfile.gettempdir(), f'hikyuu_bench_lap{i}.duckdb')
        for i in range(5)
    ]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

    print_header("测试完成")
    if integrity['match']:
        print("  [PASS] 数据完整性验证通过，新旧方案行数一致")
    else:
        print("  [FAIL] 数据行数不一致，请检查")

    print(f"  [SPEED] DuckDB read_csv_auto 加速比: {speedup:.1f}x")


if __name__ == '__main__':
    main()