"""R133 子智能体 D: HVD 候选分类脚本
- 已注册到 service_bootstrap
- 但未继承 BaseService
- 检查业务方
"""
import os
import re

def main():
    # 1. 收集所有 service_bootstrap 注册的 service
    registered = set()
    with open('core/services/service_bootstrap.py', 'r', encoding='utf-8') as f:
        content = f.read()
    # 找所有 factory=lambda: X() 模式
    for m in re.finditer(r'factory=lambda:\s*([A-Za-z_][A-Za-z0-9_]*)\(', content):
        registered.add(m.group(1))
    # 找所有 import ServiceName 别名
    for m in re.finditer(r'_([A-Z][A-Za-z0-9_]+)\s*=\s*', content):
        # 这是下划线 alias, 查找 class
        pass
    print(f'Registered services: {len(registered)}')
    for r in sorted(registered)[:20]:
        print(f'  {r}')

    # 2. 收集所有未继承 BaseService 的 service 类
    not_base = []
    for root, dirs, files in os.walk('core/services'):
        for f in files:
            if f.endswith('.py') and f != '__init__.py':
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                        c = fh.read()
                    if 'BaseService' not in c and 'class ' in c:
                        classes = re.findall(r'^class\s+(\w+)', c, re.M)
                        if classes:
                            not_base.append((fp, classes))
                except: pass

    print(f'\n=== Services without BaseService (potentially HVD candidates) ===')
    for fp, cls in not_base:
        # 提取文件中的主要 class
        main_cls = [c for c in cls if c[0].isupper() and not c.endswith('Error') and not c.endswith('Type') and not c.endswith('Status') and not c.endswith('Config') and not c.endswith('Result') and not c.endswith('Record') and not c.endswith('Metrics') and not c.endswith('Event') and not c.endswith('Plan') and not c.endswith('Task')]
        if not main_cls:
            continue
        main_cls_name = main_cls[0]
        # 检查是否在 service_bootstrap 注册
        is_registered = main_cls_name in registered
        # 检查 docstring 是否含 "未注册"
        has_unregistered_doc = '未注册' in c or 'unregistered' in c.lower()
        print(f'  {fp}: {main_cls_name} registered={is_registered} doc_unreg={has_unregistered_doc}')

if __name__ == '__main__':
    main()
