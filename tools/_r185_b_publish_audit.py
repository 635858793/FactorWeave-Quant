"""
R185-B 业务方迁移分析: 统计 bus.publish() 散落点
"""
from pathlib import Path
import re

ROOT = Path(".")
DIRS_SKIP = {".pytest_cache", "__pycache__", ".git", "_archive", "node_modules", "venv", ".venv"}

# 统计所有 .py 文件 (排除缓存/git/archive)
py_files = []
for p in ROOT.rglob("*.py"):
    if not any(d in p.parts for d in DIRS_SKIP):
        py_files.append(p)

print(f"Total Python files: {len(py_files)}")

# 1) bus.publish(...) 总数
bus_publish_count = 0
bus_publish_files = {}
for f in py_files:
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    matches = re.findall(r"\bbus\.publish\s*\(", content)
    if matches:
        bus_publish_count += len(matches)
        bus_publish_files[str(f)] = len(matches)

print(f"\n[1] bus.publish(...) 总数: {bus_publish_count}")
print(f"    涉及文件数: {len(bus_publish_files)}")

# 2) self._bus.publish / self.bus.publish
self_bus_count = 0
for f in py_files:
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    matches = re.findall(r"self\._?bus\.publish\s*\(", content)
    self_bus_count += len(matches)

print(f"\n[2] self._bus.publish / self.bus.publish 总数: {self_bus_count}")

# 3) get_event_bus().publish()
geb_count = 0
for f in py_files:
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    matches = re.findall(r"get_event_bus\(\)\.publish\s*\(", content)
    geb_count += len(matches)

print(f"\n[3] get_event_bus().publish() 总数: {geb_count}")

# 4) r84 helper 复用数 (已用 _safe_publish 包装)
r84_helper_count = 0
for f in py_files:
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    matches = re.findall(r"publish_\w+\s*\(", content)
    r84_helper_count += len(matches)

print(f"\n[4] publish_xxx() helper 复用总数: {r84_helper_count}")

# 5) r84 helper 定义数
r84_file = ROOT / "core" / "events" / "r84_event_helper.py"
if r84_file.exists():
    content = r84_file.read_text(encoding="utf-8")
    helpers = re.findall(r"^def (publish_\w+)", content, re.MULTILINE)
    print(f"\n[5] r84_event_helper.py 中 publish_xxx helper 定义数: {len(helpers)}")
    print(f"    Helper 列表: {helpers[:10]}{'...' if len(helpers) > 10 else ''}")

# 6) 估算 241→80 收敛 (R184-C 立项)
total_scattered = bus_publish_count + self_bus_count + geb_count
print(f"\n[6] 散落 publish() 调用点估计: {total_scattered}")
print(f"    R184-C 立项: 241 散落 → 80 收敛 (66.8% 减少)")
print(f"    当前实测散落: {total_scattered} → 收敛目标 80")
