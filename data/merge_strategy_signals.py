import sqlite3
import os
import shutil
from datetime import datetime

print("=" * 80)
print("P0-2: strategy_signals 数据合并")
print("=" * 80)

src_db = "data/factorweave_system.sqlite"
dst_db = "data/strategy.sqlite"

print(f"\n源数据库: {src_db}")
print(f"目标数据库: {dst_db}")

if not os.path.exists(src_db):
    print(f"❌ 源数据库不存在: {src_db}")
    exit(1)

if not os.path.exists(dst_db):
    print(f"❌ 目标数据库不存在: {dst_db}")
    exit(1)

print("\n[1/4] 备份数据库...")
backup_dir = "data/backups"
os.makedirs(backup_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

src_backup = os.path.join(backup_dir, f"factorweave_system_backup_{timestamp}.sqlite")
dst_backup = os.path.join(backup_dir, f"strategy_backup_{timestamp}.sqlite")

shutil.copy2(src_db, src_backup)
shutil.copy2(dst_db, dst_backup)

print(f"  ✅ 备份完成: {src_backup}")
print(f"  ✅ 备份完成: {dst_backup}")

print("\n[2/4] 检查源数据...")
conn_src = sqlite3.connect(src_db)
cursor_src = conn_src.cursor()

cursor_src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_signals'")
if not cursor_src.fetchone():
    print("  ⚠️ 源数据库中无 strategy_signals 表")
    conn_src.close()
    exit(1)

cursor_src.execute("SELECT COUNT(*) FROM strategy_signals")
src_count = cursor_src.fetchone()[0]
print(f"  源数据: {src_count} 条")

if src_count == 0:
    print("  ⚠️ 无数据需要合并")
    conn_src.close()
    exit(0)

print("\n[3/4] 合并数据到目标数据库...")
conn_dst = sqlite3.connect(dst_db)
cursor_dst = conn_dst.cursor()

cursor_dst.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_signals'")
if not cursor_dst.fetchone():
    print("  ⚠️ 目标数据库中无 strategy_signals 表，创建...")
    cursor_dst.execute("""
        CREATE TABLE IF NOT EXISTS strategy_signals (
            id INTEGER PRIMARY KEY,
            stock_code TEXT,
            signal_type TEXT,
            signal_value REAL,
            confidence REAL,
            strategy_name TEXT,
            parameters TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

cursor_src.execute("PRAGMA table_info(strategy_signals)")
src_columns = [col[1] for col in cursor_src.fetchall()]
print(f"  源表结构: {src_columns}")

cursor_dst.execute("PRAGMA table_info(strategy_signals)")
dst_columns = [col[1] for col in cursor_dst.fetchall()]
print(f"  目标表结构: {dst_columns}")

cursor_src.execute("SELECT * FROM strategy_signals")
rows = cursor_src.fetchall()

if rows:
    placeholders = ','.join(['?'] * len(rows[0]))
    cursor_dst.executemany(f"INSERT OR REPLACE INTO strategy_signals VALUES ({placeholders})", rows)
    conn_dst.commit()
    print(f"  ✅ 成功合并 {len(rows)} 条数据")

conn_src.close()
conn_dst.close()

print("\n[4/4] 验证合并结果...")
conn_src = sqlite3.connect(src_db)
conn_dst = sqlite3.connect(dst_db)

cursor_src = conn_src.cursor()
cursor_dst = conn_dst.cursor()

cursor_src.execute("SELECT COUNT(*) FROM strategy_signals")
src_final = cursor_src.fetchone()[0]

cursor_dst.execute("SELECT COUNT(*) FROM strategy_signals")
dst_final = cursor_dst.fetchone()[0]

print(f"  factorweave_system.sqlite.strategy_signals: {src_final} 条")
print(f"  strategy.sqlite.strategy_signals: {dst_final} 条")

conn_src.close()
conn_dst.close()

print("\n" + "=" * 80)
print("合并完成!")
print("=" * 80)
