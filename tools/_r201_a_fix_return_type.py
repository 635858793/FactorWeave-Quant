"""R201-A 修复修复器 v2: 把 -> 移回正确位置"""
import re
from pathlib import Path

ORDER_SERVICE = Path('core/trading/order_service.py')

with open(ORDER_SERVICE, 'r', encoding='utf-8') as f:
    content = f.read()

# 错误模式: ) ->  # R201-A P0 修复: ... (R104 §13 多账户隔离铁律) XXXX:
# 正确模式: ) -> XXXX:  # R201-A P0 修复: ... (R104 §13 多账户隔离铁律)
pattern = re.compile(
    r'\) ->  # R201-A P0 修复: 新增多账户隔离参数 \(R104 §13 多账户隔离铁律\) ([A-Za-z\[\], ]+):'
)

def fix_match(m):
    return_type = m.group(1).strip()
    return f') -> {return_type}:  # R201-A P0 修复: 新增多账户隔离参数 (R104 §13 多账户隔离铁律)'

new_content = pattern.sub(fix_match, content)

# 统计
count = len(pattern.findall(content))
print(f"修复 {count} 处 return type 位置")

with open(ORDER_SERVICE, 'w', encoding='utf-8') as f:
    f.write(new_content)
