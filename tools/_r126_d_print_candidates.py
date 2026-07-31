"""R126 Step 2: 打印 BaseService 继承覆盖率 + 候选清单."""

import json
import sys
from pathlib import Path

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\.audit_r126_d_baseservice.json', encoding='utf-8-sig') as f:
    data = json.load(f)

info = data['r126_step2']
print(f"=== R126 BaseService 覆盖率扫描结果 ===")
print(f"服务文件总数: {info['total_service_files']}")
print(f"Service-like 类总数: {info['total_service_classes']}")
print(f"已继承 BaseService: {info['subclassed_classes']}")
print(f"已有 lifecycle 方法: {info['lifecycle_impls']}")
print(f"Pydantic BaseModel 排除: {info['pydantic_excluded']}")
print(f"当前覆盖率: {info['coverage_percent']}%")
print(f"待继承候选数: {info['pending_candidates_count']}")
print()
print("=== 50 个待继承候选 (按文件排序) ===")
for i, c in enumerate(info['pending_candidates'], 1):
    has_life = "✓ 已有" if c['has_lifecycle_methods'] else "✗ 缺失"
    fname = Path(c['file']).name
    print(f"{i:3d}. {c['name']:40s} {fname:50s} L{c['lineno']:4d} lifecycle: {has_life}")
