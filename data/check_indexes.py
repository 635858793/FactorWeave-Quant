import sqlite3
import os

db_files = [
    "data/factorweave_system.sqlite",
    "data/strategy.sqlite",
    "data/tradeaccount.sqlite"
]

for db_path in db_files:
    if not os.path.exists(db_path):
        print(f"❌ {db_path} 不存在")
        continue
    
    print(f"\n{'='*60}")
    print(f"数据库: {db_path}")
    print('='*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = cursor.fetchall()
    
    if indexes:
        print(f"索引数量: {len(indexes)}")
        for idx in indexes[:10]:
            print(f"  - {idx[0]}")
        if len(indexes) > 10:
            print(f"  ... 还有 {len(indexes)-10} 个")
    else:
        print("⚠️ 无索引")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"表数量: {len(tables)}")
    
    conn.close()
