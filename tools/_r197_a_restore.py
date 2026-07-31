"""从备份恢复文件"""
import shutil
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 恢复所有 .r197a.* 备份
for backup in PROJECT_ROOT.rglob("*.r197a.*"):
    if backup.is_file():
        # 恢复: 文件名去掉 .r197a.* 后缀
        original = backup.parent / backup.name.split(".r197a.")[0]
        shutil.copy2(backup, original)
        print(f"Restored: {original.name}")
