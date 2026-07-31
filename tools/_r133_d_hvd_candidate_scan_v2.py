"""R133 子智能体 D: HVD 候选分类 v2 - 完整分类
- 已注册到 service_bootstrap
- 但未继承 BaseService
- 检查业务方
"""
import os
import re
import json
import subprocess
from pathlib import Path

def get_registered_services():
    """从 service_bootstrap.py 提取所有注册的服务"""
    registered = set()
    with open('core/services/service_bootstrap.py', 'r', encoding='utf-8') as f:
        content = f.read()
    # factory=lambda: ServiceName() 或 ServiceName = X 模式
    for m in re.finditer(r'factory\s*=\s*lambda\s*:\s*_?([A-Z][A-Za-z0-9_]*)\(', content):
        registered.add(m.group(1))
    for m in re.finditer(r'_([A-Z][A-Za-z0-9_]+)\s*=\s*[A-Z]', content):
        # 收集下划线 alias
        pass
    return registered

def has_base_service_inheritance(fp):
    """检查文件是否有 BaseService 继承"""
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return 'BaseService' in content
    except:
        return False

def get_main_class(fp):
    """获取文件的主类 (通常以 Service/Manager/Engine/Factory 结尾)"""
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree_str = content
        # 找所有 class 定义
        classes = re.findall(r'^class\s+(\w+)\s*(?:\(([^)]*)\))?', tree_str, re.M)
        # 优先: 继承 BaseService 的
        for cname, parents in classes:
            if 'BaseService' in (parents or ''):
                return cname, parents
        # 优先: Service/Manager/Engine 结尾
        for cname, parents in classes:
            if any(cname.endswith(s) for s in ['Service', 'Manager', 'Engine', 'Factory', 'Provider', 'Bridge']):
                return cname, parents
        # 第一个类
        if classes:
            return classes[0][0], classes[0][1]
    except:
        pass
    return None, None

def count_business_callers(class_name):
    """统计 class_name 的业务调用方数量 (Grep core/gui/plugins)"""
    if not class_name:
        return 0
    count = 0
    for d in ['core', 'gui', 'plugins']:
        if not os.path.isdir(d):
            continue
        try:
            r = subprocess.run(
                ['grep', '-rl', class_name, d, '--include=*.py', '--exclude-dir=__pycache__', '--exclude-dir=.git'],
                capture_output=True, text=True, timeout=30
            )
            for line in r.stdout.strip().split('\n'):
                if line and class_name in line:
                    # 排除定义文件
                    if not line.endswith(f'{class_name.lower()}.py'):
                        count += 1
        except:
            pass
    return count

def main():
    registered = get_registered_services()
    print(f'Total registered: {len(registered)}', file=__import__('sys').stderr)

    # 收集未继承 BaseService 的 service 类
    candidates = []
    for root, dirs, files in os.walk('core/services'):
        for f in files:
            if f.endswith('.py') and f != '__init__.py':
                fp = os.path.join(root, f)
                if has_base_service_inheritance(fp):
                    continue
                main_cls, parents = get_main_class(fp)
                if not main_cls:
                    continue
                # 跳过枚举/dataclass
                if any(main_cls.startswith(p) for p in ['_', 'Test', 'Mock']):
                    continue
                # 跳过纯 enum/dataclass (没有 'class' 后跟 '(')
                is_registered = main_cls in registered
                # 跳过嵌套类 (e.g. 'RecoveryAction' 内部类)
                candidates.append({
                    'file': fp,
                    'class': main_cls,
                    'parents': parents or 'object',
                    'is_registered': is_registered,
                })

    # 统计业务方 (限速)
    print(f'Total candidates: {len(candidates)}', file=__import__('sys').stderr)
    for c in candidates[:30]:  # 限速
        c['business_callers'] = count_business_callers(c['class'])

    # 输出
    print(f'\n=== HVD Candidates (未继承 BaseService 的 Service) ===\n')
    print(f'{"Class":<45} {"Registered":<11} {"BusinessCallers":<16} {"Parents":<30}')
    print('-' * 105)
    for c in candidates:
        print(f'{c["class"]:<45} {str(c["is_registered"]):<11} {c.get("business_callers", "N/A"):<16} {c["parents"]:<30}')

    # 4 源验证: 找出 真 HVD 候选 (已注册 + 业务方>0)
    real_hvd = [c for c in candidates if c['is_registered'] and c.get('business_callers', 0) > 0]
    print(f'\n=== Real HVD Candidates (registered + business callers > 0) ===')
    for c in real_hvd:
        print(f'  {c["class"]} (file={c["file"]}, callers={c["business_callers"]})')

    # 存 JSON
    with open('.audit_r133_d_hvd_candidates.json', 'w', encoding='utf-8') as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
