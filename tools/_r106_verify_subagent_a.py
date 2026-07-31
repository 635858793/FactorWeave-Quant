"""
R106 R+1 round independent sub-agent A verification script
"""
import ast
import sys

# Read source
with open('core/ui/panels/right_panel.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Parse AST
tree = ast.parse(source)

# Find all FunctionDef
all_funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
all_classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

# Targets to verify
targets_p01 = ['_create_industry_tab', '_on_refresh_industry_clicked',
               '_fetch_industry_data', '_reset_industry_loading_flag', '_update_industry_ui']
targets_p06 = ['_on_asset_selected']
targets_p03 = ['self.analysis_service', 'from core.services.analysis_service']

print("=" * 70)
print("R106 R+1 round sub-agent A verification")
print("=" * 70)

# Check targets in source (string match)
print("\n[P0-1] 5 method definitions removed:")
for m in targets_p01:
    in_funcs = m in all_funcs
    in_source = f"def {m}(" in source
    status = "FAIL" if (in_funcs or in_source) else "OK"
    print(f"  {m}: AST={in_funcs}, source_def={in_source} -> {status}")

print("\n[P0-6] _on_asset_selected removed:")
m = '_on_asset_selected'
in_funcs = m in all_funcs
in_source = f"def {m}(" in source
status = "FAIL" if (in_funcs or in_source) else "OK"
print(f"  {m}: AST={in_funcs}, source_def={in_source} -> {status}")

print("\n[P0-1] industry_* widget references removed:")
for pattern in ["add_widget('industry_", "get_widget('industry_"]:
    count = source.count(pattern)
    status = "FAIL" if count > 0 else "OK"
    print(f"  {pattern!r}: count={count} -> {status}")

print("\n[P0-3] self.analysis_service / AnalysisService import removed:")
for pattern in targets_p03:
    count = source.count(pattern)
    status = "FAIL" if count > 0 else "OK"
    print(f"  {pattern!r}: count={count} -> {status}")

print("\n[P0-6] subscribe/unsubscribe AssetSelectedEvent removed:")
for pattern in ["subscribe(AssetSelectedEvent", "unsubscribe(AssetSelectedEvent"]:
    count = source.count(pattern)
    status = "FAIL" if count > 0 else "OK"
    print(f"  {pattern!r}: count={count} -> {status}")

print("\n[P0-7] _create_signal_tab / _create_backtest_tab in conditional block:")
# Find line with `if not PROFESSIONAL_TABS_AVAILABLE:`
lines = source.split('\n')
cond_line_idx = None
for i, line in enumerate(lines):
    if 'if not PROFESSIONAL_TABS_AVAILABLE' in line:
        cond_line_idx = i
        break
if cond_line_idx is not None:
    # Find next non-indented line
    for j in range(cond_line_idx + 1, min(cond_line_idx + 20, len(lines))):
        if lines[j].strip() and not lines[j].startswith(' ') and not lines[j].startswith('#'):
            break
    block = '\n'.join(lines[cond_line_idx:j])
    has_signal = '_create_signal_tab' in block
    has_backtest = '_create_backtest_tab' in block
    has_basic_tabs = '_has_basic_tabs = True' in block
    print(f"  _create_signal_tab in block: {has_signal}")
    print(f"  _create_backtest_tab in block: {has_backtest}")
    print(f"  _has_basic_tabs = True in block: {has_basic_tabs}")

print("\n[P0-8] _perf_refresh_timer.stop() in _do_dispose:")
# Find _do_dispose method body
dispose_start = source.find('def _do_dispose')
next_def = source.find('\n    def ', dispose_start + 1)
if next_def == -1:
    next_def = len(source)
dispose_body = source[dispose_start:next_def]
has_stop = '_perf_refresh_timer.stop()' in dispose_body
print(f"  _perf_refresh_timer.stop() in _do_dispose: {has_stop}")

print("\n[Summary]")
all_p01_clean = all(m not in all_funcs and f"def {m}(" not in source for m in targets_p01)
all_p06_clean = all(m not in all_funcs and f"def {m}(" not in source for m in targets_p06)
p03_clean = all(source.count(p) == 0 for p in targets_p03)
widget_clean = source.count("add_widget('industry_") == 0 and source.count("get_widget('industry_") == 0
event_clean = source.count("subscribe(AssetSelectedEvent") == 0 and source.count("unsubscribe(AssetSelectedEvent") == 0

print(f"  P0-1 5 methods removed: {all_p01_clean}")
print(f"  P0-1 8 add_widget + 4 get_widget cleared: {widget_clean}")
print(f"  P0-3 self.analysis_service / import removed: {p03_clean}")
print(f"  P0-6 _on_asset_selected + subscribe/unsubscribe removed: {all_p06_clean and event_clean}")
print(f"  P0-7 conditional block: {has_signal and has_backtest and has_basic_tabs}")
print(f"  P0-8 _perf_refresh_timer.stop() in _do_dispose: {has_stop}")

print()
all_pass = all_p01_clean and widget_clean and p03_clean and all_p06_clean and event_clean and has_signal and has_backtest and has_basic_tabs and has_stop
print(f"[ALL CHECKS] {'PASS' if all_pass else 'FAIL'}")
sys.exit(0 if all_pass else 1)
