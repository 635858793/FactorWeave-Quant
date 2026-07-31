#!/usr/bin/env python3
"""R174 子智能体 B: 业务调用链 + 服务注册审计工具 - v2 修正别名映射"""
import re
import os
import sys

def main():
    with open('core/services/service_bootstrap.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Build alias map: `_XClassName` -> `OriginalClassName`
    alias_map = {}
    for m in re.finditer(r'from\s+(\S+)\s+import\s+\(?\s*([^)]+?)\s*\)?', content):
        module = m.group(1)
        names = m.group(2)
        for name in re.split(r'[,\n]', names):
            name = name.strip()
            if not name or name.startswith('#'):
                continue
            m2 = re.match(r'(\w+)\s+as\s+(\w+)', name)
            if m2:
                alias_map[m2.group(2)] = m2.group(1)

    # 2. Find all registered class names
    registered = set()
    for m in re.finditer(r'(?:register(?:_factory|_instance)?|_is_service_registered|is_registered)\s*\(\s*([A-Z]\w*)\b', content):
        name = m.group(1)
        # Map alias back to original
        if name in alias_map:
            registered.add(alias_map[name])
        else:
            registered.add(name)

    # 3. Find all classes in core/ inheriting from BaseService
    all_classes = {}
    for root, dirs, files in os.walk('core'):
        if any(x in root for x in ['__pycache__', '.git', 'node_modules', '.venv', 'venv']):
            continue
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8') as fp:
                    file_content = fp.read()
            except Exception:
                continue
            for m in re.finditer(r'class\s+(\w+)\s*\(\s*([^)]*)\)', file_content):
                cls_name = m.group(1)
                parents = m.group(2)
                if any(b in parents for b in ['BaseService', 'AsyncBaseService', 'ConfigurableService']):
                    if cls_name in ('BaseService', 'AsyncBaseService', 'ConfigurableService', 'CacheableService', 'AsyncConfigurableService'):
                        continue
                    all_classes[cls_name] = (path, parents[:80])

    # 4. Skip classes (helpers, deprecated, sub-agents, etc.)
    SKIP = {
        'BaseService', 'AsyncBaseService', 'CacheableService', 'ConfigurableService',
        'ConfigurableServiceBase', 'AsyncConfigurableService',
        # Internal helpers within other services (not standalone)
        'DataQualityMonitor',  # internal class in enhanced_data_manager.py
        'FailureDetector',  # internal of fault_tolerance_manager
        'BettaFishErrorHandler',  # internal of error_handling_service
        'ErrorHandler',  # internal of error_handling_service
        # R119 marked as dead code (0 业务方), R120 物理删除候选
        'RecoveryEngine', 'QualityRuleEngine', 'RecommendationFusionEngine',
        'ResultComparisonAnalyzer', 'SimpleDuckDBManager', 'TETDataProvider',
        # Sub-agents managed by BettaFishAgent internally
        'SentimentAnalysisAgent', 'NewsAnalysisAgent', 'RiskAssessmentAgent', 'TechnicalAnalysisAgent',
        # Legacy / fallback
        'AssetFallbackLoader',
        # Event handlers (not services)
        'AlertEventHandler',
    }

    # 5. Categorize
    registered_list = []
    not_registered = []
    for n, (p, par) in sorted(all_classes.items()):
        if n in SKIP:
            continue
        if n in registered:
            registered_list.append((n, p))
        else:
            not_registered.append((n, p, par))

    print(f'总类数: {len(all_classes)}, 已注册(去重+排除): {len(registered_list)}, 未注册(P0/P1 候选): {len(not_registered)}')
    print()
    print('=== [P0/P1 候选] 未注册 Service (重点审计) ===')
    for n, p, par in not_registered:
        print(f'  [X] {n}: {p}')
        print(f'      parents: {par}')

    print()
    print('=== [V] 已注册 Service (确认) ===')
    for n, p in registered_list:
        print(f'  [V] {n}: {p}')

    # Coverage stats
    print()
    print(f'注册覆盖率: {len(registered_list)} / ({len(registered_list)} + {len(not_registered)}) = {100.0 * len(registered_list) / (len(registered_list) + len(not_registered)):.1f}%')


if __name__ == '__main__':
    main()
