#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R194-D 改进修复脚本 v2 直接写入日志"""
import sys
import os
sys.path.insert(0, r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools")
from pathlib import Path

# 重定向 stdout 到文件
PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
LOG_FILE = PROJECT_ROOT / "_r194_d_v2_run.log"
LOG = open(LOG_FILE, "w", encoding="utf-8")

# 替换 print
import builtins
_original_print = builtins.print
def log_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    _original_print(msg)
    LOG.write(msg + "\n")
    LOG.flush()
builtins.print = log_print

# 现在导入
from _r194_d_fix_silent_v2 import main, fix_file

# 替换 R194_TARGETS
import _r194_d_fix_silent_v2 as mod
mod.R194_TARGETS = [
    "core/services/ai_selection_risk_control_service.py",
    "core/services/unified_data_manager.py",
    "core/services/service_bootstrap.py",
    "core/coordinators/main_window_coordinator.py",
    "core/services/ai_selection_integration_service.py",
    "core/services/trading_service.py",
    "core/events/event_bus.py",
    "core/monitoring/queue_monitor.py",
    "core/monitoring/cache_degradation_exporter.py",
    "core/risk_manager.py",
]

# 直接运行
print("=" * 80)
print("R194-D 改进修复 v2 - 第二轮运行")
print("=" * 80)
grand_p0 = 0
grand_err = 0
for rp in mod.R194_TARGETS:
    fp = PROJECT_ROOT / rp
    if not fp.exists():
        print(f"[MISSING] {rp}")
        continue
    print(f"\n--- {rp} ---")
    p0, p1, err = fix_file(fp)
    grand_p0 += p0
    grand_err += err
    print(f"  P0 修复: {p0} | 语法错误: {err}")

print(f"\n{'=' * 80}")
print(f"总计: P0={grand_p0}, 语法错误={grand_err}")
print("=" * 80)

LOG.close()
