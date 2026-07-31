#!/usr/bin/env python3
"""R175 阶段 2: 修复 main_window_coordinator.py 剩余 4 处 R51 #5 违规"""
import pathlib

p = pathlib.Path("core/coordinators/main_window_coordinator.py")
src = p.read_text(encoding="utf-8")

replacements = [
    (
        'logger.warning(f"风险计算器: RiskMetricsCalculator 导入失败 ({import_exc})")',
        'logger.warning(f"风险计算器: RiskMetricsCalculator 导入失败 ({import_exc})", exc_info=True)',
    ),
    (
        'logger.warning(f"R42 _enable_sfe_backend 失败',
        None,  # 多模式匹配
    ),
    (
        'logger.warning(f"[R61] 状态栏 badge 事件订阅失败 (非致命): {e}")',
        'logger.warning(f"[R61] 状态栏 badge 事件订阅失败 (非致命): {e}", exc_info=True)',
    ),
    (
        'logger.warning(f"无法导入OrderBookWidget: {type(e).__name__}: {e}")',
        'logger.warning(f"无法导入OrderBookWidget: {type(e).__name__}: {e}", exc_info=True)',
    ),
]

count = 0
# 直接用 substring replace
patterns = [
    (
        'logger.warning(f"风险计算器: RiskMetricsCalculator 导入失败 ({import_exc})")',
        'logger.warning(f"风险计算器: RiskMetricsCalculator 导入失败 ({import_exc})", exc_info=True)',
    ),
    (
        'logger.warning(f"R42 _enable_sfe_backend 失败(可忽略): {e}")',
        'logger.warning(f"R42 _enable_sfe_backend 失败(可忽略): {e}", exc_info=True)',
    ),
    (
        'logger.warning(f"[R61] 状态栏 badge 事件订阅失败 (非致命): {e}")',
        'logger.warning(f"[R61] 状态栏 badge 事件订阅失败 (非致命): {e}", exc_info=True)',
    ),
    (
        'logger.warning(f"无法导入OrderBookWidget: {type(e).__name__}: {e}")',
        'logger.warning(f"无法导入OrderBookWidget: {type(e).__name__}: {e}", exc_info=True)',
    ),
]
for old, new in patterns:
    if old in src:
        src = src.replace(old, new)
        count += 1
        print(f"OK: {old[:60]}")
    else:
        print(f"MISS: {old[:60]}")

p.write_text(src, encoding="utf-8")
print(f"\nTotal fixed: {count}")
