"""R138 子智能体 C: 修复 ai_selection_risk_control_service.py."""
import ast
from pathlib import Path

fp = Path('core/services/ai_selection_risk_control_service.py')
content = fp.read_text(encoding='utf-8')
lines = content.split('\n')

# L3873 (0-idx 3872) - L3893 (0-idx 3892) 是错误注入的 _do_dispose
# L3894 (0-idx 3893) 是 `            }` 关闭 return dict

# 检查当前内容
for i in range(3870, min(3895, len(lines))):
    print(f'L{i+1} (0-idx {i}): {lines[i][:80]}')

print(f'\nTotal lines: {len(lines)}')

# 删除 3872-3892 (21 行)
if len(lines) > 3893:
    new_lines = lines[:3872] + lines[3893:]
else:
    # 文件结尾附近
    new_lines = lines[:3872]
    # 保留 close }
    if lines[3893:]:
        new_lines = lines[3893:]

new_content = '\n'.join(new_lines)
try:
    ast.parse(new_content)
    print('Syntax OK after fix')
except SyntaxError as e:
    print(f'Syntax error: {e}')
fp.write_text(new_content, encoding='utf-8')
