#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database.unified_sqlite_access import UnifiedSQLiteAccess

print("=" * 80)
print("一、数据库文件统计")
print("=" * 80)

sqlite_files = set()
duckdb_files = set()
other_files = set()

for root, dirs, files in os.walk('.'):
    for f in files:
        full_path = os.path.join(root, f)
        if f.endswith('.sqlite'):
            sqlite_files.add(full_path)
        elif f.endswith('.duckdb'):
            duckdb_files.add(full_path)
        elif f.endswith('.db') and 'performance_baselines' not in full_path:
            other_files.add(full_path)

print(f"SQLite文件数: {len(sqlite_files)}")
print(f"DuckDB文件数: {len(duckdb_files)}")
print(f"其他db文件数: {len(other_files)}")

print("\n" + "=" * 80)
print("二、SQLite数据库详细分析")
print("=" * 80)

def analyze_sqlite(db_path):
    print(f"\n=== {db_path} ===")
    try:
        db = UnifiedSQLiteAccess.get_instance(db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            print(f"表数量: {len(tables)}")
            
            for t in tables:
                cursor.execute(f"SELECT COUNT(*) FROM \"{t}\"")
                count = cursor.fetchone()[0]
                print(f"  - {t}: {count} 条记录")
        return True
    except Exception as e:
        print(f"  错误: {e}")
        return False

for db in sorted(sqlite_files):
    analyze_sqlite(db)

print("\n" + "=" * 80)
print("三、DuckDB数据库详细分析")
print("=" * 80)

def analyze_duckdb(db_path):
    print(f"\n=== {db_path} ===")
    try:
        import duckdb
        conn = duckdb.connect(db_path, read_only=True)
        cursor = conn.cursor()
        
        cursor.execute("SHOW TABLES")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"表数量: {len(tables)}")
        
        for t in tables[:10]:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                count = cursor.fetchone()[0]
                print(f"  - {t}: {count} 条记录")
            except Exception:
                print(f"  - {t}: 查询失败")
        
        if len(tables) > 10:
            print(f"  ... 还有 {len(tables) - 10} 个表")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  错误: {e}")
        return False

for db in sorted(duckdb_files):
    analyze_duckdb(db)

print("\n" + "=" * 80)
print("四、数据库文件问题检查")
print("=" * 80)

def check_db_issues():
    issues = []
    
    for db in sqlite_files:
        if not os.path.exists(db):
            issues.append(f"文件不存在: {db}")
        elif os.path.getsize(db) == 0:
            issues.append(f"空文件: {db}")
    
    for db in duckdb_files:
        if not os.path.exists(db):
            issues.append(f"文件不存在: {db}")
        elif os.path.getsize(db) == 0:
            issues.append(f"空文件: {db}")
    
    return issues

issues = check_db_issues()
if issues:
    print("发现以下问题:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("未发现明显问题")

print("\n" + "=" * 80)
print("五、数据库表重复检查")
print("=" * 80)

all_tables = {}
for db in sqlite_files:
    try:
        db_instance = UnifiedSQLiteAccess.get_instance(db)
        with db_instance.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            for t in tables:
                if t not in all_tables:
                    all_tables[t] = []
                all_tables[t].append(db)
    except Exception:
        pass

duplicates = {t: dbs for t, dbs in all_tables.items() if len(dbs) > 1}
if duplicates:
    print("发现重复表名:")
    for t, dbs in sorted(duplicates.items()):
        print(f"  - {t}:")
        for db in dbs:
            print(f"      {db}")
else:
    print("未发现重复表名")
