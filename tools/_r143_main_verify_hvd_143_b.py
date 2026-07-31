#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R143 主智能体 R+1 round 独立验证脚本 - HVD-143-B"""
import re
from pathlib import Path

project_root = Path('core')
service_files = []
for f in project_root.rglob('*.py'):
    if '__pycache__' in str(f) or 'test' in str(f).lower():
        continue
    try:
        content = f.read_text(encoding='utf-8')
    except Exception:
        continue
    classes = re.findall(r'class\s+(\w+(?:Service|Manager|Engine|Provider|Bridge|Handler))\s*[:\(]', content)
    if classes:
        for cls in classes:
            has_metrics = '_metrics' in content or 'def.*metric' in content.lower()
            has_health = 'def.*health' in content.lower() or 'health_check' in content.lower()
            has_status = 'is_healthy' in content or 'get_status' in content or 'health_check' in content
            service_files.append({
                'file': str(f),
                'class': cls,
                'has_metrics': has_metrics,
                'has_health': has_health,
                'has_status': has_status,
            })

print(f'Total service-like classes: {len(service_files)}')
no_metrics = [s for s in service_files if not s['has_metrics']]
no_health = [s for s in service_files if not s['has_health']]
no_status = [s for s in service_files if not s['has_status']]
no_any = [s for s in service_files if not (s['has_metrics'] or s['has_health'] or s['has_status'])]
print(f'  no metrics: {len(no_metrics)}')
print(f'  no health: {len(no_health)}')
print(f'  no status: {len(no_status)}')
print(f'  no metrics AND no health AND no status: {len(no_any)}')
print()
print('Top 20 services without any observability:')
for s in no_any[:20]:
    print(f'  {s["class"]} @ {s["file"]}')
