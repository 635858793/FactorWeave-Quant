#!/usr/bin/env python3
"""R164 HVD-162-C Stage-1 实施脚本 (TDD GREEN 阶段)

任务: 修复 30 P0 业务核心文件 570 处 logger.exc_info 缺失
排除: R145/R161/R162/R163-A 已闭环 19 文件

模式 (复用 R162-B-1 3 模板):
- 模式 A: 业务事件发布失败 → logger.error(f"...", exc_info=True)
- 模式 B: 业务执行失败 → logger.error(f"...", exc_info=True)
- 模式 C: 业务降级 → logger.warning(f"...", exc_info=True)
"""
import re
import sys
from pathlib import Path

ROOT = Path(".").resolve()

# 排除已闭环 19 文件 (R145/R161/R162/R163-A)
EXCLUDED_PATHS = {
    'core/trading_engine.py',  # R145
    'core/order_service.py',  # R161
    'core/importdata/import_execution_engine.py',  # R162
    'core/services/advanced_risk_control_service.py',  # R162
    'core/ctp/ctp_trading_interface.py',  # R162
    'core/xtp/xtp_trading_interface.py',  # R163-A
    'core/xtp/xtp_pro_trading_interface.py',  # R163-A
    'core/oem/oem_trading_interface.py',  # R163-A
    'core/simulator/simulator_trading_interface.py',  # R163-A
    'core/importdata/unified_data_import_engine.py',  # R162
    'core/risk_manager.py',  # R148 + R162 (已升级大部分)
}

# R163-C 报告 P0 业务核心 30 文件清单 (570 处)
P0_FILES = {
    # === TOP 15: 531 处 ===
    'gui/dialogs/order_management_dialog.py': 79,
    'gui/widgets/performance/tabs/risk_control_center_tab.py': 79,
    'gui/widgets/trading_widget.py': 57,
    'core/risk_monitoring/enhanced_risk_monitor.py': 50,
    'gui/dialogs/account_management_dialog.py': 47,
    'gui/widgets/trading_panel.py': 43,
    'core/services/signal_trading_bridge.py': 35,
    'gui/widgets/performance/tabs/trading_execution_monitor_tab.py': 28,
    'core/services/ai_selection_risk_control_service.py': 24,
    'core/agents/risk_agent.py': 23,
    'core/risk_rule_manager.py': 16,
    'gui/widgets/enhanced_ui/order_book_widget.py': 15,
    'core/trading/account_manager.py': 13,
    'core/risk_exporter.py': 11,
    'core/risk/risk_event_subscribers.py': 11,
    # === 16-30: 39 处 ===
    'core/risk_metrics.py': 10,
    'gui/widgets/advanced_risk_control_widget.py': 10,
    'core/performance/professional_risk_metrics.py': 7,
    'gui/widgets/dynamic_risk_adjustment_widget.py': 5,
    'gui/widgets/enhanced_trading_monitor_widget.py': 5,
    'core/risk_alert.py': 4,
    'gui/widgets/bettafish_dashboard/risk_assessment_panel.py': 3,
    'gui/widgets/bettafish_dashboard/trading_signal_panel.py': 3,
    'core/risk_monitoring/sherman_morrison_correlation.py': 2,
    'gui/dialogs/risk_rule_config_dialog.py': 2,
    'core/risk_control.py': 1,
    'core/trading/signal_adapters.py': 1,
    'core/trading/trading_mode.py': 1,
    'gui/dialogs/signal_trading_bridge_dialog.py': 1,
}


def count_exc_info_missing(content: str) -> int:
    """统计代码字符串中 except 块内 logger.error/warning/critical 缺 exc_info 数

    简化算法:
    - 行级扫描: 找到 except 关键字
    - 后续缩进级别内的 logger.* 调用检查 exc_info
    """
    lines = content.split('\n')
    in_except = False
    except_indent = 0
    missing = 0

    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith('#'):
            continue

        # 检测 except 块开始
        if re.match(r'\s*except\s+.*\s*as\s+\w+:', stripped) or re.match(r'\s*except\s*:', stripped):
            in_except = True
            except_indent = len(line) - len(stripped)
            continue

        # 在 except 块内
        if in_except:
            line_indent = len(line) - len(stripped)

            # 块结束: 缩进回到 except 缩进或更少
            if stripped and line_indent <= except_indent:
                in_except = False
                # 重新检查当前行 (可能是新的 except)
                if re.match(r'\s*except\s+.*\s*as\s+\w+:', stripped) or re.match(r'\s*except\s*:', stripped):
                    in_except = True
                    except_indent = line_indent
                continue

            # 检测 logger.error/warning/critical 调用
            m = re.match(r'.*logger\.(error|warning|critical)\s*\(', line)
            if m:
                # 检查当前行是否带 exc_info
                if 'exc_info' not in line:
                    # 继续看后续行 (多行调用)
                    # 简化: 仅看当前行, 因为 90% 是单行
                    missing += 1

    return missing


def fix_file_exc_info(file_path: Path) -> tuple:
    """修复文件内的 exc_info 缺失, 返回 (fixed_count, total_calls)"""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return 0, 0

    original_content = content
    fixed_count = 0
    total_calls = 0

    # 找到 except 块内的 logger.error/warning/critical 调用
    # 模式: indent + except ... as e: 之后, 同一/后续缩进内的 logger.X(...) 调用
    lines = content.split('\n')
    new_lines = []
    i = 0
    in_except = False
    except_indent = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        line_indent = len(line) - len(stripped)

        # 检测 except 块开始
        if re.match(r'\s*except\s+.*\s*as\s+\w+:', stripped) or re.match(r'\s*except\s*:', stripped):
            in_except = True
            except_indent = line_indent
            new_lines.append(line)
            i += 1
            continue

        # 检查是否还在 except 块内
        if in_except and stripped and line_indent <= except_indent:
            in_except = False

        # 在 except 块内的 logger 调用
        if in_except:
            # 找 logger.error/warning/critical 调用
            m = re.match(r'(.*?logger\.(error|warning|critical)\s*\()([^)]*?)(\))', line)
            if m:
                total_calls += 1
                prefix = m.group(1)
                method = m.group(2)
                args = m.group(3)
                suffix = m.group(4)

                # 检查 args 是否已含 exc_info
                if 'exc_info' not in args and 'exc_info' not in line:
                    # 添加 exc_info=True
                    # 处理 args 末尾是否有逗号
                    args_stripped = args.rstrip()
                    if args_stripped.endswith(','):
                        new_args = args_stripped + ' exc_info=True'
                    else:
                        new_args = args_stripped + ', exc_info=True'
                    new_line = f"{prefix}{new_args}{suffix}"
                    new_lines.append(new_line)
                    fixed_count += 1
                    i += 1
                    continue

        new_lines.append(line)
        i += 1

    if fixed_count > 0:
        new_content = '\n'.join(new_lines)
        # 仅在确实修改时写回
        if new_content != original_content:
            file_path.write_text(new_content, encoding='utf-8')

    return fixed_count, total_calls


def main():
    print("=" * 70)
    print("R164 HVD-162-C Stage-1 实施: P0 业务核心 exc_info 升级")
    print("=" * 70)
    print()

    # Phase 1: 扫描基线
    print("【Phase 1: 基线扫描】")
    total_missing = 0
    file_baseline = {}
    for rel_path, expected in P0_FILES.items():
        full_path = ROOT / rel_path
        if not full_path.exists():
            print(f"  ⚠️  文件不存在: {rel_path}")
            continue
        if rel_path in EXCLUDED_PATHS:
            print(f"  ⏭️  排除: {rel_path}")
            continue
        content = full_path.read_text(encoding='utf-8')
        missing = count_exc_info_missing(content)
        file_baseline[rel_path] = (missing, expected)
        total_missing += missing
        if missing > 0:
            print(f"  📍 {rel_path}: {missing} 处 (R163-C 预期 {expected})")

    print(f"\n  总 missing: {total_missing}")
    print(f"  R163-C 预期: 570")
    print()

    # Phase 2: 批量修复
    print("【Phase 2: 批量修复 (TDD GREEN)】")
    total_fixed = 0
    files_fixed = 0
    for rel_path in P0_FILES:
        if rel_path in EXCLUDED_PATHS:
            continue
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue
        fixed, total = fix_file_exc_info(full_path)
        if fixed > 0:
            print(f"  ✅ {rel_path}: 修复 {fixed}/{total}")
            total_fixed += fixed
            files_fixed += 1
        else:
            print(f"  ✓  {rel_path}: 无需修复")

    print(f"\n  总修复: {total_fixed} 处 (在 {files_fixed} 文件)")
    print()

    # Phase 3: 验证
    print("【Phase 3: 验证 (TDD 闭环)】")
    total_remaining = 0
    for rel_path, expected in P0_FILES.items():
        if rel_path in EXCLUDED_PATHS:
            continue
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue
        content = full_path.read_text(encoding='utf-8')
        remaining = count_exc_info_missing(content)
        if remaining > 0:
            total_remaining += remaining
            print(f"  ❌ {rel_path}: 仍缺 {remaining} 处")

    print(f"\n  剩余 missing: {total_remaining}")
    print(f"  修复率: {(1 - total_remaining / max(total_missing, 1)) * 100:.1f}%")
    print()
    print("=" * 70)
    if total_remaining == 0:
        print("🎉 R164 HVD-162-C Stage-1 TDD GREEN 通过!")
    else:
        print(f"⚠️  R164 HVD-162-C Stage-1 仍需修复 {total_remaining} 处")
    print("=" * 70)

    return total_remaining


if __name__ == '__main__':
    remaining = main()
    sys.exit(0 if remaining == 0 else 1)
