"""快速检查 import_execution_engine.py 实际内容"""
from pathlib import Path

p = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/importdata/import_execution_engine.py")
print(f"文件大小: {p.stat().st_size} 字节")
c = p.read_text(encoding="utf-8")
print(f"行数: {len(c.splitlines())}")
needle = "resolve_or_initialize(ProgressPersistenceManager"
print(f"  '{needle}' 出现: {c.count(needle)} 次")

# 列出所有 resolve_or_initialize 调用
import re
matches = re.findall(r"resolve_or_initialize\([A-Z]\w+", c)
print(f"  resolve_or_initialize 全部调用: {matches}")

# 列出所有 container.is_registered 调用 (业务调用方)
legacy = re.findall(r"container\.is_registered\([A-Z]\w+\)", c)
print(f"  业务调用方 is_registered: {legacy}")
