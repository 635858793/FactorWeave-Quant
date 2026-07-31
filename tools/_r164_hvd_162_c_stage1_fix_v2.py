#!/usr/bin/env python3
"""R164 HVD-162-C Stage-1 实施脚本 v2 (增强多行支持)

TDD GREEN 阶段 - 修复 30 P0 业务核心文件 logger.exc_info 缺失
v2 改进: 处理多行 logger.warning/error/critical 调用
"""
import re
import sys
from pathlib import Path

ROOT = Path(".").resolve()

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
    'core/risk_manager.py',  # R148 + R162
}

P0_FILES = {
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
    """统计 exc_info 缺失 (支持多行 logger 调用)"""
    # 按 except 块扫描
    lines = content.split('\n')
    in_except = False
    except_indent = 0
    missing = 0

    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped:
            continue

        # 检测 except 块开始
        if re.match(r'\s*except\s+.*\s*as\s+\w+\s*:', stripped) or re.match(r'\s*except\s*:', stripped):
            in_except = True
            except_indent = len(line) - len(stripped)
            continue

        if in_except and stripped:
            line_indent = len(line) - len(stripped)
            if line_indent <= except_indent:
                in_except = False
                # 可能是新 except
                if re.match(r'\s*except\s+.*\s*as\s+\w+\s*:', stripped) or re.match(r'\s*except\s*:', stripped):
                    in_except = True
                    except_indent = line_indent
                continue

        if in_except:
            # 找 logger.error/warning/critical 调用 (单行或多行开始)
            m = re.search(r'logger\.(error|warning|critical)\s*\(', line)
            if m:
                # 检查整个 logger 调用是否带 exc_info
                # 找到匹配的 )
                start_pos = m.end()
                paren_count = 1
                pos = start_pos
                while pos < len(line) and paren_count > 0:
                    ch = line[pos]
                    if ch == '(':
                        paren_count += 1
                    elif ch == ')':
                        paren_count -= 1
                    pos += 1
                if paren_count == 0:
                    # 单行调用
                    call_content = line[m.start():pos]
                    if 'exc_info' not in call_content:
                        missing += 1
                else:
                    # 多行调用, 累计直到匹配 )
                    full_call = line[m.start():]
                    paren_count_acc = paren_count
                    scan_idx = idx + 1
                    while scan_idx < len(lines) and paren_count_acc > 0:
                        next_line = lines[scan_idx]
                        for ch in next_line:
                            if ch == '(':
                                paren_count_acc += 1
                            elif ch == ')':
                                paren_count_acc -= 1
                                if paren_count_acc == 0:
                                    break
                        full_call += '\n' + next_line
                        scan_idx += 1
                    if 'exc_info' not in full_call:
                        missing += 1

    return missing


def fix_file_exc_info(file_path: Path) -> tuple:
    """修复文件内的 exc_info 缺失 (支持多行调用), 返回 (fixed_count, total_calls)"""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return 0, 0

    lines = content.split('\n')
    in_except = False
    except_indent = 0
    new_lines = list(lines)  # 复制以保留原始
    fixed_count = 0
    total_calls = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        line_indent = len(line) - len(stripped) if stripped else 0

        # 检测 except 块
        if re.match(r'\s*except\s+.*\s*as\s+\w+\s*:', stripped) or re.match(r'\s*except\s*:', stripped):
            in_except = True
            except_indent = line_indent
            i += 1
            continue

        if in_except and stripped and line_indent <= except_indent:
            in_except = False
            if re.match(r'\s*except\s+.*\s*as\s+\w+\s*:', stripped) or re.match(r'\s*except\s*:', stripped):
                in_except = True
                except_indent = line_indent
            i += 1
            continue

        if in_except:
            m = re.search(r'logger\.(error|warning|critical)\s*\(', line)
            if m:
                total_calls += 1
                # 找匹配的 )
                start_pos = m.end()
                paren_count = 1
                pos = start_pos
                while pos < len(line) and paren_count > 0:
                    ch = line[pos]
                    if ch == '(':
                        paren_count += 1
                    elif ch == ')':
                        paren_count -= 1
                    pos += 1

                if paren_count == 0:
                    # 单行
                    call_content = line[m.start():pos]
                    if 'exc_info' not in call_content:
                        # 在 ) 之前插入 exc_info=True
                        before = line[:pos-1].rstrip()
                        after = line[pos-1:]
                        # 处理逗号
                        if before.rstrip().endswith(','):
                            new_line = before + ' exc_info=True' + after
                        elif before.rstrip().endswith('('):
                            new_line = before + 'exc_info=True' + after
                        else:
                            new_line = before + ', exc_info=True' + after
                        new_lines[i] = new_line
                        fixed_count += 1
                else:
                    # 多行
                    # 累积所有行
                    call_parts = [line[m.start():]]
                    paren_count_acc = paren_count
                    scan_idx = i + 1
                    end_line_idx = i
                    while scan_idx < len(lines) and paren_count_acc > 0:
                        next_line = lines[scan_idx]
                        call_parts.append(next_line)
                        for ch_pos, ch in enumerate(next_line):
                            if ch == '(':
                                paren_count_acc += 1
                            elif ch == ')':
                                paren_count_acc -= 1
                                if paren_count_acc == 0:
                                    end_line_idx = scan_idx
                                    # 标记结束位置
                                    break
                        scan_idx += 1

                    full_call = '\n'.join(call_parts)
                    if 'exc_info' not in full_call:
                        # 找到最后一个非空行 (在 ) 之前的)
                        # 在 ) 之前一行添加 exc_info=True
                        # 简单方法: 在最后一行 ) 之前插入
                        last_line = call_parts[-1]
                        # 找 ) 位置
                        close_pos = last_line.rfind(')')
                        if close_pos > 0:
                            # 找匹配第几个 ) - 是调用结束的那个
                            # 简化: 找最后一个非空字符串, 然后插入
                            before = last_line[:close_pos].rstrip()
                            # 检查是否已经以 , 结尾
                            if before.rstrip().endswith(','):
                                new_last = before + ' exc_info=True' + last_line[close_pos:]
                            else:
                                new_last = before + ', exc_info=True' + last_line[close_pos:]
                            call_parts[-1] = new_last
                            # 替换行
                            for j, part in enumerate(call_parts):
                                new_lines[i + j] = part
                            fixed_count += 1
        i += 1

    if fixed_count > 0:
        new_content = '\n'.join(new_lines)
        file_path.write_text(new_content, encoding='utf-8')

    return fixed_count, total_calls


def main():
    print("=" * 70)
    print("R164 HVD-162-C Stage-1 实施 v2: 多行 logger.exc_info 升级")
    print("=" * 70)
    print()

    # Phase 1: 扫描基线
    print("【Phase 1: 基线扫描 (修复后)】")
    total_missing = 0
    for rel_path in P0_FILES:
        if rel_path in EXCLUDED_PATHS:
            continue
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue
        content = full_path.read_text(encoding='utf-8')
        missing = count_exc_info_missing(content)
        if missing > 0:
            print(f"  📍 {rel_path}: {missing} 处")
            total_missing += missing

    print(f"\n  当前 missing: {total_missing}")
    print()

    if total_missing == 0:
        print("🎉 全部已修复!")
        return 0

    # Phase 2: 批量修复
    print("【Phase 2: 批量修复 (TDD GREEN)】")
    total_fixed = 0
    for rel_path in P0_FILES:
        if rel_path in EXCLUDED_PATHS:
            continue
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue
        fixed, total = fix_file_exc_info(full_path)
        if fixed > 0:
            print(f"  ✅ {rel_path}: 修复 {fixed}")
            total_fixed += fixed

    print(f"\n  本轮修复: {total_fixed}")
    print()

    # Phase 3: 验证
    print("【Phase 3: 验证 (TDD 闭环)】")
    total_remaining = 0
    for rel_path in P0_FILES:
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

    print(f"\n  最终 remaining: {total_remaining}")
    print()
    print("=" * 70)
    if total_remaining == 0:
        print("🎉 R164 HVD-162-C Stage-1 TDD GREEN 通过!")
    else:
        print(f"⚠️  R164 仍需修复 {total_remaining} 处")
    print("=" * 70)
    return total_remaining


if __name__ == '__main__':
    remaining = main()
    sys.exit(0 if remaining == 0 else 1)
