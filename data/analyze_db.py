#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database.unified_sqlite_access import UnifiedSQLiteAccess

db_files = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.sqlite') or f.endswith('.db'):
            db_files.append(os.path.join(root, f))

for db in sorted(set(db_files)):
    print(f'=== {db} ===')
    try:
        db_instance = UnifiedSQLiteAccess.get_instance(db)
        with db_instance.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            for t in tables:
                print(f'  TABLE: {t[0]}')
    except Exception as e:
        print(f'  ERROR: {e}')
    print()
