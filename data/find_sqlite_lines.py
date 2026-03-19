import re

file_path = r"D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\model_training_service.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

for i, line in enumerate(lines):
    if 'sqlite3.connect(str(db_path))' in line:
        print(f"Line {i+1}: {line.strip()}")
