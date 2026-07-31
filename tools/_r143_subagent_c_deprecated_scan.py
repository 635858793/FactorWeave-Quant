"""R143 子智能体 C: 52 个 DEPRECATED 详细核验脚本."""
import sys
sys.path.insert(0, '.')
from tools.audit_docstring_deprecated import audit_project, DeprecatedStatus
import json
from collections import Counter

report = audit_project('.')
items = report.deprecated_report.deprecated_items

# 统计 3 状态
status_count = Counter(it.status.value for it in items)
print('=== 3 状态分布 ===')
for s, c in status_count.most_common():
    print(f'  {s}: {c}')

print()
print('=== 52 项详细列表 ===')
for i, it in enumerate(items, 1):
    path = it.file_path.replace('D:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui\\', '').replace('D:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/', '')
    cname = it.class_name or '(module)'
    print(f'{i:2d}. {cname:40s} | {path}:L{it.line:5d} | {it.status.value:30s} | reg={it.is_registered_in_bootstrap} | biz={it.business_caller_count}')

# 额外输出 docstring 摘要
print()
print('=== 52 项 docstring 摘要 ===')
for i, it in enumerate(items, 1):
    path = it.file_path.replace('D:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui\\', '').replace('D:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/', '')
    cname = it.class_name or '(module)'
    excerpt = it.docstring_excerpt[:60].replace('\n', ' ')
    print(f'{i:2d}. {path}:L{it.line:5d} | {cname:30s} | {excerpt}')
