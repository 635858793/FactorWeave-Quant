#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import os

db_files = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.sqlite') or f.endswith('.db'):
            db_files.append(os.path.join(root, f))

for db in sorted(set(db_files)):
    print(f'=== {db} ===')
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for t in tables:
            print(f'  TABLE: {t[0]}')
        conn.close()
    except Exception as e:
        print(f'  ERROR: {e}')
    print()
