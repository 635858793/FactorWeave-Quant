"""详细诊断 import_execution_engine.py"""
from pathlib import Path

p = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/importdata/import_execution_engine.py")
c = p.read_text(encoding="utf-8")
print(f"文件大小: {p.stat().st_size} 字节")
print(f"行数: {len(c.splitlines())}")

# 搜索关键字符串
for needle in [
    "HVD-185-3",
    "R186-C",
    "DataImportPipeline",
    "get_data_import_pipeline",
    "resolve_or_initialize",
    "container.is_registered",
    "ProgressPersistenceManager",
]:
    count = c.count(needle)
    print(f"  '{needle}': {count} 次")

# 显示 L320-345 内容
lines = c.splitlines()
for i, line in enumerate(lines[320:345], start=321):
    print(f"L{i}: {line[:120]}")
