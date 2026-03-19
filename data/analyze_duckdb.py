#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

db_files = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.duckdb') or f.endswith('.duckdb.wal'):
            db_files.append(os.path.join(root, f))

db_files = sorted(set([f for f in db_files if not f.endswith('.wal')]))

for db in db_files:
    print(f'=== {db} ===')
    try:
        import duckdb
        conn = duckdb.connect(db, read_only=True)
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        for t in tables:
            print(f'  TABLE: {t[0]}')
        conn.close()
    except Exception as e:
        print(f'  ERROR: {e}')
    print()
