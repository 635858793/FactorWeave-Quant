#!/usr/bin/env python3
"""诊断脚本: 列出 plugins/ 下所有被 _find_plugin_class 误判的文件"""
import sys
from pathlib import Path

sys.path.insert(0, '.')

# Quiet down logs
import logging
logging.disable(logging.CRITICAL)

import importlib.util
from core.plugin_manager import PluginManager
pm = PluginManager(plugin_dir='plugins')

plugins_dir = Path('plugins')
all_files = sorted(plugins_dir.rglob('*.py'))

# Files that are NOT plugins (interface / base / config / templates)
non_plugin_patterns = [
    'plugin_interface.py',
    'plugin_market.py',
    'loguru_plugin_logger.py',
    'sentiment_data_source_interface.py',
    'base_sentiment_plugin.py',
    'config_base.py',
    'config_base_loguru.py',
    'templates/',
    'examples/',
    'data_injectors/',
    'development/',
    '__init__.py',
    'standard_data_source_plugin.py',  # 模板
    'hikyuu_indicators_plugin.py.hikyuu_backup',  # 备份
]

# Categorize files
interface_base_files = []
concrete_plugin_files = []
excluded_pattern_files = []

for f in all_files:
    rel = str(f.relative_to(plugins_dir))
    if 'templates' in rel or 'examples' in rel or '__pycache__' in rel:
        excluded_pattern_files.append(rel)
        continue
    if f.name.startswith('__'):
        continue
    if any(pattern in rel for pattern in non_plugin_patterns):
        interface_base_files.append(rel)
        continue
    concrete_plugin_files.append(rel)

print(f"=== 分类 ===")
print(f"  Interface/Base 配置文件: {len(interface_base_files)}")
print(f"  Concrete Plugin 文件: {len(concrete_plugin_files)}")
print(f"  Templates/Examples/Cache: {len(excluded_pattern_files)}")
print()

print("=== Interface/Base 配置文件 (应跳过) ===")
for f in interface_base_files:
    print(f"  {f}")
print()

print("=== Concrete Plugin 文件 (应能加载) ===")
for f in concrete_plugin_files:
    # Try to load
    spec = importlib.util.spec_from_file_location('test_module', f'plugins/{f}')
    if spec is None or spec.loader is None:
        print(f"  [SPEC FAIL] {f}")
        continue
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"  [IMPORT FAIL] {f}: {e}")
        continue
    plugin_class = pm._find_plugin_class(module)
    if plugin_class is None:
        # Find classes in module
        class_names = [name for name in dir(module) if isinstance(getattr(module, name, None), type)]
        print(f"  [NO PLUGIN CLASS] {f} - classes: {class_names[:3]}")
    else:
        print(f"  [OK] {f} -> {plugin_class.__name__}")
