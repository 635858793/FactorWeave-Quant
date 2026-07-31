"""R168-A Service metrics/health_check coverage analysis"""
import os
import re
import json
from pathlib import Path

base = Path('core/services')
files = [f for f in base.glob('*.py') if not f.name.startswith('_') and 'bak' not in f.name and '.r128_pre' not in f.name]

service_classes = []
for f in files:
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
        for m in re.finditer(r'^class\s+(\w+)\(([\w\.\,\s]*)\):', content, re.MULTILINE):
            cls_name = m.group(1)
            parents = m.group(2)
            if any(p in parents for p in ['BaseService', 'AsyncBaseService', 'CacheableService', 'ConfigurableService']):
                has_get_metrics = bool(re.search(r'def\s+get_metrics\s*\(', content))
                has_health_check = bool(re.search(r'def\s+_do_health_check\s*\(', content))
                has_initialize = bool(re.search(r'def\s+_do_initialize\s*\(', content))
                service_classes.append({
                    'file': f.name,
                    'class': cls_name,
                    'parents': parents.strip(),
                    'has_get_metrics': has_get_metrics,
                    'has_health_check': has_health_check,
                    'has_initialize': has_initialize,
                })

print(f'Total Service classes: {len(service_classes)}')
print('---')
print('With get_metrics override:')
for s in service_classes:
    if s['has_get_metrics']:
        print(f"  {s['file']}: {s['class']}")
print('---')
print('Without get_metrics override:')
for s in service_classes:
    if not s['has_get_metrics']:
        print(f"  {s['file']}: {s['class']} (parent={s['parents']})")
print('---')
print('Without _do_health_check:')
for s in service_classes:
    if not s['has_health_check']:
        print(f"  {s['file']}: {s['class']}")
print('---')
print('Without _do_initialize:')
for s in service_classes:
    if not s['has_initialize']:
        print(f"  {s['file']}: {s['class']}")
