#!/usr/bin/env python3
"""列出 sentiment_agent.py 剩余违规"""
import sys
sys.path.insert(0, "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
sys.path.insert(0, "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/tests")
from test_r174_hvd_173_d4_top20_r51_compliance import analyze_file
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
fp = PROJECT_ROOT / "core/agents/sentiment_agent.py"
total, missing, violations = analyze_file(fp)
print(f"Total: {total}, Missing: {missing}")
for v in violations:
    print(f"  L{v['line']:5d}  logger.{v['level']:10s} {v['msg']}")
