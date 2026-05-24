import os
base = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets"
for f in ['backtest_widget.py','trading_widget.py','chart_widget.py','chart_renderer.py','chart_rendering_manager.py']:
    fp = os.path.join(base, f)
    if os.path.exists(fp):
        with open(fp, encoding='utf-8', errors='ignore') as fh:
            lines = sum(1 for _ in fh)
        print(f"{f}: {lines} lines, {os.path.getsize(fp):,d} bytes")
    else:
        print(f"{f}: NOT FOUND")