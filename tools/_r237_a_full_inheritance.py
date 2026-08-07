import re, os
service_dir = 'core/services'
output = []
output.append('=== Service Class Inheritance (R233 §13.4 强约束) ===')
output.append('File:Line:Class:Parent | dispose_inherited')

for f in os.listdir(service_dir):
    if not f.endswith('.py') or f in ('__init__.py', 'service_bootstrap.py', 'metrics_base.py', 'db_utils.py', 'singleton_protection.py', 'base_service.py'):
        continue
    path = os.path.join(service_dir, f)
    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
        for i, line in enumerate(fp, 1):
            m = re.match(r'class\s+(\w+(?:Service|Manager|Engine|Provider|Bridge|Factory|Handler))(?:\(([\w.,\s\(\)\[\]]*?)\))?:', line)
            if m:
                cls = m.group(1)
                parent = m.group(2) or 'NO_PARENT'
                has_dispose_inh = any(p in parent for p in ['BaseService', 'CacheableService', 'ConfigurableService', 'AsyncBaseService'])
                has_own_dispose = False
                with open(path, 'r', encoding='utf-8', errors='ignore') as fp2:
                    content = fp2.read()
                    if 'def dispose' in content or 'def _do_dispose' in content or 'def shutdown' in content or 'def close' in content or 'def cleanup' in content:
                        has_own_dispose = True
                status = '🟢' if (has_dispose_inh or has_own_dispose) else '🔴'
                output.append(f'{status} {f:48s}:{i:5d} {cls:30s} : ({parent.strip()}) own_dispose={has_own_dispose}')

with open('tools/_r237_a_full_inheritance.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(output))
