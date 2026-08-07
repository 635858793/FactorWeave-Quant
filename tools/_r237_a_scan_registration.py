import re, os
service_dir = 'core/services'
classes = []
for f in os.listdir(service_dir):
    if not f.endswith('.py') or f in ('__init__.py', 'service_bootstrap.py', 'metrics_base.py', 'db_utils.py', 'singleton_protection.py'):
        continue
    path = os.path.join(service_dir, f)
    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
        for i, line in enumerate(fp, 1):
            m = re.match(r'class\s+(\w+(?:Service|Manager|Engine|Provider|Bridge|Factory|Handler))(?:\(|:)', line)
            if m:
                classes.append((m.group(1), f, i))

with open('core/services/service_bootstrap.py', 'r', encoding='utf-8', errors='ignore') as fp:
    bootstrap = fp.read()

output = []
output.append(f'Total classes: {len(classes)}')

registered = set()
for c, f, l in classes:
    if c in bootstrap:
        registered.add(c)
output.append(f'\n=== REGISTERED (in bootstrap) ===')
output.append(f'Total registered: {len(registered)}/{len(classes)}')

output.append(f'\n=== NOT REGISTERED ===')
unregistered = []
for c, f, l in classes:
    if c not in registered:
        unregistered.append((c, f, l))
for c, f, l in unregistered:
    output.append(f'  [NO] {c} ({f}:{l})')
output.append(f'\nTotal NOT registered: {len(unregistered)}')

with open('tools/_r237_a_scan_registration.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(output))
