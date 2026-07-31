"""R126 Step 1-2: AST 扫描 core/services/ BaseService 继承覆盖率统计."""

import ast
import json
import sys
from pathlib import Path
from collections import defaultdict

BASE_SERVICE_NAMES = {'BaseService', 'AsyncBaseService', 'ConfigurableService', 'CacheableService'}


def collect_bases(base: ast.expr) -> set:
    """提取类 base 的所有名称 (含 Attribute)."""
    names = set()
    if isinstance(base, ast.Name):
        names.add(base.id)
    elif isinstance(base, ast.Attribute):
        names.add(base.attr)
    return names


def is_baseservice_subclass(class_node: ast.ClassDef) -> tuple:
    """检查类是否继承 BaseService 4 选 1."""
    for base in class_node.bases:
        names = collect_bases(base)
        for n in names:
            if n in BASE_SERVICE_NAMES:
                return True, n
    return False, ""


def is_service_class(class_node: ast.ClassDef) -> bool:
    """类名暗示 Service/Manager/Engine/Provider/Handler/Controller/Bridge/Monitor/Fetcher/Pool/Adapter/Worker."""
    keywords = (
        'Service', 'Manager', 'Engine', 'Provider', 'Handler', 'Controller',
        'Bridge', 'Monitor', 'Fetcher', 'Pool', 'Adapter', 'Worker',
        'Loader', 'Resolver', 'Calculator', 'Recorder', 'Collector',
        'Detector', 'Analyzer', 'Generator', 'Trainer', 'Optimizer',
    )
    return any(class_node.name.endswith(k) for k in keywords)


def is_pydantic_model(class_node: ast.ClassDef) -> bool:
    """检查类是否继承 BaseModel (pydantic)."""
    for base in class_node.bases:
        names = collect_bases(base)
        if 'BaseModel' in names:
            return True
    return False


def has_initialize_or_dispose(class_node: ast.ClassDef) -> bool:
    """类是否已实现 initialize/dispose/_do_initialize/_do_dispose/_do_health_check."""
    target_methods = {'initialize', 'dispose', '_do_initialize', '_do_dispose',
                      '_do_health_check', 'initialize_async', 'dispose_async'}
    for stmt in class_node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name in target_methods:
                return True
    return False


def analyze_file(file_path: Path) -> dict:
    """分析单个文件, 返回类继承信息."""
    try:
        source = file_path.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(source)
    except Exception as e:
        return {'error': str(e), 'classes': []}

    file_info = {
        'file': str(file_path),
        'classes': [],
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            is_subclass, base_name = is_baseservice_subclass(node)
            service_like = is_service_class(node)
            is_pydantic = is_pydantic_model(node)

            file_info['classes'].append({
                'name': node.name,
                'lineno': node.lineno,
                'is_baseservice_subclass': is_subclass,
                'base_service_name': base_name,
                'is_service_like': service_like,
                'is_pydantic': is_pydantic,
                'has_lifecycle_methods': has_initialize_or_dispose(node),
            })

    return file_info


def main():
    services_dir = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services')
    py_files = sorted(services_dir.glob('*.py'))
    # 排除 base_service.py 自身
    py_files = [f for f in py_files if f.name != 'base_service.py']

    all_results = []
    for f in py_files:
        info = analyze_file(f)
        all_results.append(info)

    # 统计
    total_service_classes = 0
    subclassed_classes = 0
    pending_candidates = []  # Service-like 但未继承 BaseService
    pydantic_excluded = 0
    lifecycle_impls = 0

    for info in all_results:
        for cls in info['classes']:
            if cls['is_pydantic']:
                pydantic_excluded += 1
                continue
            if not cls['is_service_like']:
                continue
            total_service_classes += 1
            if cls['is_baseservice_subclass']:
                subclassed_classes += 1
                if cls['has_lifecycle_methods']:
                    lifecycle_impls += 1
            else:
                pending_candidates.append({
                    'name': cls['name'],
                    'file': info['file'],
                    'lineno': cls['lineno'],
                    'has_lifecycle_methods': cls['has_lifecycle_methods'],
                })

    coverage = subclassed_classes / total_service_classes * 100 if total_service_classes > 0 else 0

    report = {
        'r126_step2': {
            'total_service_files': len(py_files),
            'total_service_classes': total_service_classes,
            'subclassed_classes': subclassed_classes,
            'pydantic_excluded': pydantic_excluded,
            'lifecycle_impls': lifecycle_impls,
            'coverage_percent': round(coverage, 2),
            'pending_candidates_count': len(pending_candidates),
            'pending_candidates': pending_candidates,
        }
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == '__main__':
    main()
