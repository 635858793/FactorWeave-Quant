import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database.unified_sqlite_access import UnifiedSQLiteAccess

db_files = [
    "data/factorweave_system.sqlite",
    "data/strategy.sqlite",
    "data/tradeaccount.sqlite"
]

for db_path in db_files:
    if not os.path.exists(db_path):
        print(f"数据库 {db_path} 不存在")
        continue
    
    print(f"\n{'='*60}")
    print(f"数据库: {db_path}")
    print('='*60)
    
    db = UnifiedSQLiteAccess.get_instance(db_path)
    
    with db.get_connection() as conn:
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
            print("无索引")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"表数量: {len(tables)}")
