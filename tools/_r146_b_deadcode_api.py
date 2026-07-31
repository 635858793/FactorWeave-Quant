#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R146 B: 死代码审计 - 调用 tools.audit_dead_code API 完整扫描
"""
import os
import sys
import json

# 添加 tools 到 path
sys.path.insert(0, r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools")
sys.path.insert(0, r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 由于 tools 文件夹可能没有 __init__.py, 尝试用 importlib
import importlib.util
spec = importlib.util.spec_from_file_location("audit_dead_code", r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\audit_dead_code.py")
adc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adc)

# 用 DeadCodeAuditor 扫描
auditor = adc.DeadCodeAuditor(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 调用 --find-all-dead 等价方法
print("R146 B 死代码审计: 调用 audit_dead_code.py API")
print("=" * 80)

# 模拟命令行: --find-all-dead
# 实际从 DeadCodeAuditor 找 is_truly_dead modules
dead_modules = []
for module_path, module_name in auditor.all_modules() if hasattr(auditor, 'all_modules') else []:
    result = auditor.analyze_module(module_path)
    if result and result.is_truly_dead:
        dead_modules.append({
            "module": module_name,
            "external_callers": result.external_callers,
            "symbols": result.symbols,
        })

print(f"Found {len(dead_modules)} truly dead modules")
for m in dead_modules[:30]:
    print(f"  - {m['module']} ({len(m['symbols'])} symbols)")
