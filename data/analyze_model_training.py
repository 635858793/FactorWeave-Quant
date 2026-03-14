file_path = r"D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\model_training_service.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

target_lines = [369, 458, 554, 661, 863, 967, 1103, 2365]

for line_num in target_lines:
    print(f"\n{'='*60}")
    print(f"Line {line_num}:")
    start = max(0, line_num - 15)
    end = min(len(lines), line_num + 10)
    
    for i in range(start, end):
        prefix = ">>> " if i + 1 == line_num else "    "
        print(f"{prefix}{i+1}: {lines[i].rstrip()}")
