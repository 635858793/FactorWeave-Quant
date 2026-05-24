import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database.unified_sqlite_access import UnifiedSQLiteAccess

print("=" * 80)
print("P1-2: 修复 TEXT 存数字问题")
print("=" * 80)

db_path = "data/strategy.sqlite"

print(f"\n数据库: {db_path}")

if not os.path.exists(db_path):
    print(f"数据库不存在: {db_path}")
    exit(1)

db = UnifiedSQLiteAccess.get_instance(db_path)

print("\n[1/3] 查找 TEXT 存数字的问题字段...")

with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]

issues_found = []

for table in tables:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = cursor.fetchall()
        
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            
            if col_type == 'TEXT':
                cursor.execute(f"""
                    SELECT COUNT(*) FROM "{table}" 
                    WHERE "{col_name}" IS NOT NULL 
                    AND typeof("{col_name}") = 'text' 
                    AND "{col_name}" GLOB '[0-9]*'
                """)
                count = cursor.fetchone()[0]
                
                if count > 0:
                    issues_found.append((table, col_name, count))
                    print(f"  警告: {table}.{col_name}: {count} 条TEXT存数字")

print(f"\n发现问题: {len(issues_found)} 处")

if not issues_found:
    print("无需修复")
    exit(0)

print("\n[2/3] 修复 TEXT 存数字问题...")

for table, col_name, count in issues_found:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info('{table}')")
            columns = cursor.fetchall()
            
            col_names = [c[1] for c in columns]
            
            cursor.execute(f"SELECT * FROM '{table}' LIMIT 1")
            sample = cursor.fetchone()
            
            if sample is None:
                print(f"  跳过: {table}.{col_name}: 空表，跳过")
                continue
            
            new_col_name = f"{col_name}_new"
            
            cursor.execute(f"ALTER TABLE '{table}' ADD COLUMN '{new_col_name}' INTEGER")
            
            cursor.execute(f"""
                UPDATE "{table}" 
                SET "{new_col_name}" = CAST("{col_name}" AS INTEGER)
                WHERE "{col_name}" IS NOT NULL 
                AND typeof("{col_name}") = 'text' 
                AND "{col_name}" GLOB '[0-9]*'
            """)
            
            cursor.execute(f"ALTER TABLE '{table}' DROP COLUMN '{col_name}'")
            
            cursor.execute(f"ALTER TABLE '{table}' RENAME COLUMN '{new_col_name}' TO '{col_name}'")
        
        print(f"  成功: {table}.{col_name}: 已修复 {count} 条")
        
    except Exception as e:
        print(f"  失败: {table}.{col_name}: 修复失败 - {e}")

print("\n[3/3] 验证修复结果...")

with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]

still_issues = 0

for table in tables:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = cursor.fetchall()
        
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            
            if col_type == 'TEXT':
                cursor.execute(f"""
                    SELECT COUNT(*) FROM "{table}" 
                    WHERE "{col_name}" IS NOT NULL 
                    AND typeof("{col_name}") = 'text' 
                    AND "{col_name}" GLOB '[0-9]*'
                """)
                count = cursor.fetchone()[0]
                
                if count > 0:
                    still_issues += 1
                    print(f"  警告: {table}.{col_name}: 仍有 {count} 条")

if still_issues == 0:
    print("\n所有 TEXT 存数字问题已修复!")
else:
    print(f"\n仍有 {still_issues} 处问题未修复")

print("\n" + "=" * 80)
print("修复完成!")
print("=" * 80)
