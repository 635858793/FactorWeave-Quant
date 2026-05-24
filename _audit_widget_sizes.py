import os

widgets_dir = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets"
files = []
for root, dirs, filenames in os.walk(widgets_dir):
    for fn in filenames:
        if fn.endswith(".py") and "__pycache__" not in root and fn != "__init__.py":
            fp = os.path.join(root, fn)
            files.append((os.path.getsize(fp), fp))

files.sort(reverse=True)
for size, fp in files[:20]:
    rel = fp.replace(widgets_dir, "").lstrip(os.sep).replace("\\", "/")
    print(f"{size:>10,d}  gui/widgets/{rel}")