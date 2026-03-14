file_path = r"D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\asset_database_manager.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

target_line = 662

print(f"方法: _get_database_path (Line {target_line})")
print("=" * 60)

for i in range(target_line - 1, min(target_line + 40, len(lines))):
    print(lines[i].rstrip())
