"""R138 子智能体 C: 修复 gpu_acceleration_manager.py + ai_selection_risk_control_service.py."""
import ast
from pathlib import Path

# 修复 gpu_acceleration_manager.py
fp1 = Path('core/services/gpu_acceleration_manager.py')
content = fp1.read_text(encoding='utf-8')
lines = content.split('\n')

# L475 (0-idx 474) - L489 (0-idx 488) 是错误注入的 _do_health_check
# 删除 474-488 (15 行)
# 但要看 L489-L490 是什么
print(f'L474 (0-idx 473): {lines[473]}')
print(f'L475 (0-idx 474): {lines[474]}')
print(f'L489 (0-idx 488): {lines[488]}')
print(f'L490 (0-idx 489): {lines[489]}')

# 删除 474-488
new_lines = lines[:474] + lines[489:]
new_content = '\n'.join(new_lines)
try:
    ast.parse(new_content)
    print('Syntax OK after fix')
except SyntaxError as e:
    print(f'Syntax error: {e}')
fp1.write_text(new_content, encoding='utf-8')

# 修复 ai_selection_risk_control_service.py
print('\n--- ai_selection_risk_control_service.py ---')
fp2 = Path('core/services/ai_selection_risk_control_service.py')
content = fp2.read_text(encoding='utf-8')
lines = content.split('\n')

# L3873 (0-idx 3872) - L3893 (0-idx 3892) 是错误注入的 _do_dispose
# L3894 (0-idx 3893) 是 `            }` 关闭 return dict
print(f'L3872 (0-idx 3871): {lines[3871]}')
print(f'L3873 (0-idx 3872): {lines[3872]}')
print(f'L3893 (0-idx 3892): {lines[3892]}')
print(f'L3894 (0-idx 3893): {lines[3893]}')
print(f'L3895 (0-idx 3894): {lines[3894]}')

# 删除 3872-3892 (21 行), 保留 L3894 `}` 关闭 return dict
new_lines = lines[:3872] + lines[3893:]
new_content = '\n'.join(new_lines)
try:
    ast.parse(new_content)
    print('Syntax OK after fix')
except SyntaxError as e:
    print(f'Syntax error: {e}')
fp2.write_text(new_content, encoding='utf-8')
