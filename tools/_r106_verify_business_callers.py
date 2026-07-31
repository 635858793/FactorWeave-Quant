"""
R106 R+1 round sub-agent A: 跨子目录全项目业务调用方验证
排除: tests/ (R106 基准测试引用), tools/_r106_*.py (R106 实施脚本), 注释
"""
import os
import re

TARGETS_P01 = ['_create_industry_tab', '_on_refresh_industry_clicked',
               '_fetch_industry_data', '_reset_industry_loading_flag', '_update_industry_ui']
TARGETS_P06 = ['_on_asset_selected']
EXCLUDE_DIRS = ['.pytest_cache', '.git', '__pycache__', 'node_modules', 'venv', '.venv']
EXCLUDE_FILES = ['tools/_r106_delete_industry_methods.py',
                 'tools/_r106_recover_truncate.py',
                 'tools/_r106_recover_v2.py',
                 'tools/_r106_verify_subagent_a.py',
                 'tests/test_r106_p0_p1_baseline.py',
                 'tools/audit_dead_code.py']

print("=" * 70)
print("R106 R+1 round: 跨子目录业务调用方验证")
print("排除:", EXCLUDE_DIRS + EXCLUDE_FILES)
print("=" * 70)

results = {}
for target in TARGETS_P01 + TARGETS_P06:
    print(f"\n[Searching] {target}")
    matches = []
    for root, dirs, files in os.walk('.'):
        # Skip excluded dirs
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(root, f).replace('\\', '/')
            # Skip excluded files
            if any(filepath.endswith(exc.replace('\\', '/')) for exc in EXCLUDE_FILES):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as fp:
                    content = fp.read()
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
            # Find all references to the target
            for m in re.finditer(r'\b' + re.escape(target) + r'\b', content):
                line_no = content[:m.start()].count('\n') + 1
                line_content = content.split('\n')[line_no - 1].strip()
                # Exclude comment lines
                if line_content.startswith('#'):
                    continue
                matches.append((filepath, line_no, line_content))
    if matches:
        print(f"  Found {len(matches)} non-comment references:")
        for fp, ln, lc in matches[:10]:
            print(f"    {fp}:{ln}  {lc[:80]}")
        if len(matches) > 10:
            print(f"    ... and {len(matches) - 10} more")
    else:
        print(f"  NO non-comment references found in business code (EXCLUDING tests/tools/comments)")
    results[target] = matches

print()
print("=" * 70)
print("[Final Assessment]")
print("=" * 70)
for target, matches in results.items():
    if matches:
        print(f"  {target}: ⚠ {len(matches)} references (need review)")
        for fp, ln, lc in matches[:5]:
            print(f"      {fp}:{ln}  {lc[:80]}")
    else:
        print(f"  {target}: ✅ 0 业务调用方 (确认安全删除)")
