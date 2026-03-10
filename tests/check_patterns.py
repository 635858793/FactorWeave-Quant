import sqlite3
conn = sqlite3.connect('data/factorweave_system.sqlite')
cursor = conn.cursor()
cursor.execute('SELECT name, english_name, confidence_threshold, success_rate FROM pattern_types WHERE english_name IN ("pennant", "expanding_triangle", "flag", "rising_wedge", "falling_wedge")')
rows = cursor.fetchall()
print('Name | English | ConfThresh | SuccessRate')
for r in rows:
    print(f'{r[0]} | {r[1]} | {r[2]} | {r[3]}')
conn.close()
