import json
from pathlib import Path

with open('tools/_r197_a_p0_scan.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

target_files_lines = {
    'database_writer.py': [107, 329, 367],
    'unified_data_import_engine.py': [211],
    'webgpu_renderer.py': [153],
    'memory_manager.py': [206, 232],
    'pipeline_optimizer.py': [191],
    'intelligent_cache.py': [308, 419],
    'thread_monitor.py': [248],
    'base_panel.py': [186, 472],
}
for v in data['p0_violations_for_fix']:
    fn = v['file'].split('\\')[-1]
    for f, lns in target_files_lines.items():
        if f == fn and v['line'] in lns:
            print(f'{fn}:L{v["line"]} - {v["function"]}(...) - {v["snippet"][:80]}')
            break
