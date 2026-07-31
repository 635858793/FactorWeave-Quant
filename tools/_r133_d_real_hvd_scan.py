"""R133 子智能体 D: HVD 真候选识别 + 业务方统计 (Grep 跨 5 子目录)"""
import os
import re
import json
import subprocess

def get_registered_classes():
    """从 service_bootstrap.py 提取所有 factory 中的 service 名 (含 _alias)"""
    registered = set()
    with open('core/services/service_bootstrap.py', 'r', encoding='utf-8') as f:
        content = f.read()
    # 模式 1: factory=lambda: X() 或 factory=lambda: _X() 或 factory=lambda: X(args)
    for m in re.finditer(r'factory\s*=\s*lambda\s*:\s*_?([A-Z][A-Za-z0-9_]*)\s*\(', content):
        registered.add(m.group(1))
    # 模式 2: 1) ServiceClass as _AliasClass  / ServiceClass,
    for m in re.finditer(r'_?([A-Z][A-Za-z0-9_]+)\s*,\s*$', content, re.M):
        # 仅在没有 lambda 上下文中
        pass  # 这种太宽泛, 跳过
    # 模式 3: 收集所有 _AliasClass = XClass 形式
    for m in re.finditer(r'from\s+[\w.]+\s+import\s+([A-Z][A-Za-z0-9_]+)\s+as\s+_([A-Z][A-Za-z0-9_]+)', content):
        registered.add(m.group(1))
        registered.add('_' + m.group(2))
    return registered

def get_business_callers(class_name, exclude_self_path):
    """跨 5+ 子目录 Python AST 扫描 class_name 业务调用方"""
    if not class_name:
        return []
    callers = []
    search_dirs = ['core', 'gui', 'plugins', 'web/backend', 'scripts', 'backtest', 'optimization']
    import re
    pattern = re.compile(rf'\b{re.escape(class_name)}\b')
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in ('__pycache__', '.git', '.cache', '.pytest_cache', 'node_modules')]
            for f in files:
                if not f.endswith('.py'):
                    continue
                fp = os.path.join(root, f)
                fp_rel = os.path.relpath(fp, '.')
                if fp_rel == exclude_self_path:
                    continue
                if 'service_bootstrap.py' in fp_rel:
                    continue
                if fp_rel.startswith('tests/') or fp_rel.startswith('test_'):
                    continue
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                    for i, line in enumerate(content.split('\n'), 1):
                        if pattern.search(line):
                            # 排除纯注释/docstring
                            stripped = line.strip()
                            if stripped.startswith('#') or '"""' in line or "'''" in line:
                                continue
                            callers.append(f'{fp_rel}:{i} {stripped[:100]}')
                            if len(callers) >= 20:  # 限速
                                return callers
                except:
                    pass
    return callers

def main():
    registered = get_registered_classes()
    print(f'Total registered: {len(registered)}', flush=True)

    # 收集未继承 BaseService 的 service 类
    candidates = []
    for root, dirs, files in os.walk('core/services'):
        for f in files:
            if f.endswith('.py') and f != '__init__.py':
                fp = os.path.join(root, f)
                fp_rel = os.path.relpath(fp, '.')
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                        c = fh.read()
                    if 'BaseService' in c:
                        continue
                    # 找所有 class 定义
                    classes = re.findall(r'^class\s+(\w+)\s*(?:\(([^)]*)\))?', c, re.M)
                    # 跳过枚举
                    for cn, parents in classes:
                        if cn.startswith('_') or any(x in (parents or '') for x in ['Enum', 'Protocol', 'type']):
                            continue
                        # 跳过 dataclass
                        if 'dataclass' in (parents or ''):
                            continue
                        # 跳过嵌套类
                        if not cn[0].isupper():
                            continue
                        # 只关注 Service/Manager/Engine/Factory/Provider/Bridge/Handler 结尾
                        if not any(cn.endswith(s) for s in ['Service', 'Manager', 'Engine', 'Factory', 'Provider', 'Bridge', 'Handler']):
                            continue
                        candidates.append({
                            'file': fp_rel,
                            'class': cn,
                            'is_registered': cn in registered,
                        })
                except: pass

    # 4 源验证
    real_hvd = []
    for c in candidates:
        c['business_callers'] = get_business_callers(c['class'], c['file'])
        c['business_caller_count'] = len(c['business_callers'])
        # 真 HVD 条件: 已注册 AND 业务方 > 0
        if c['is_registered'] and c['business_caller_count'] > 0:
            real_hvd.append(c)

    # 输出
    print(f'\n=== Real HVD Candidates (registered + business callers > 0) ===\n')
    for c in real_hvd:
        print(f'{c["class"]} ({c["file"]})')
        print(f'  Registered: {c["is_registered"]}, Business callers: {c["business_caller_count"]}')
        for caller in c['business_callers'][:5]:
            print(f'    - {caller}')
        if c['business_caller_count'] > 5:
            print(f'    ... +{c["business_caller_count"]-5} more')
        print()

    # 存 JSON
    with open('.audit_r133_d_real_hvd_candidates.json', 'w', encoding='utf-8') as f:
        json.dump(real_hvd, f, indent=2, ensure_ascii=False)
    print(f'\nTotal real HVD candidates: {len(real_hvd)}', flush=True)

    # 列出 未注册但有业务方 的
    not_reg = [c for c in candidates if not c['is_registered'] and c.get('business_caller_count', 0) > 0]
    print(f'\n=== Unregistered + business callers > 0 (dead code alert) ===')
    for c in not_reg:
        print(f'  {c["class"]} ({c["file"]}) - callers: {c.get("business_caller_count", 0)}')

if __name__ == '__main__':
    main()
