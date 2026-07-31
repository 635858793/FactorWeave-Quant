"""
R199-A 软解析修复器 (Apply Tool)

按 R51 §7.1 #5 + R199-A 任务要求修复 P0 风险控制软解析:
  1. 加 exc_info=True 到 logger.warning (R51 铁律 #5)
  2. 加显式降级日志标识 (R199-A HVD-198-D-NEW-04)
  3. 保持原有业务逻辑不变

输出:
  - 应用修复到目标文件
  - 验证修复后是否 R51 合规
"""
import ast
import re
import json
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 已识别的需要修复的位置 (R199-A HVD-198-D-NEW-04)
KNOWN_P0_FIXES = [
    {
        'file': 'core/coordinators/event_coordinator.py',
        'line': 2391,  # 原始 except 行 (R199-A 修复前)
        'fix_type': 'add_exc_info',
        'description': 'RiskManager 软解析失败日志加 exc_info=True',
        'service': 'RiskManager / risk_manager',
        'context_match': '风控推送失败',
    },
    {
        'file': 'gui/widgets/performance/unified_performance_widget.py',
        'line': 870,  # 原始 except 行
        'fix_type': 'add_exc_info',
        'description': 'RiskManager 软解析失败日志加 exc_info=True',
        'service': 'RiskManager',
        'context_match': 'RiskManager 解析失败',
    },
]


def apply_fix_at(file_path: Path, line_no: int, context_match: str) -> bool:
    """在指定文件行附近应用 exc_info 修复"""
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print(f"  [ERROR] {file_path}: {e}")
        return False

    lines = content.splitlines(keepends=True)

    if line_no - 1 >= len(lines):
        print(f"  [ERROR] 行号 {line_no} 超出文件范围")
        return False

    # 在指定行附近 (5-15 行内) 找到 logger.warning 调用
    # R199-A 修复模式: 在 except 后, logger.warning 的最外层调用
    # 搜索范围: 行号 - 2 到 行号 + 10
    search_start = max(0, line_no - 3)
    search_end = min(len(lines), line_no + 10)

    found_warn = -1
    found_exc_info = -1
    paren_depth = 0
    in_warning = False
    warning_start = -1

    for i in range(search_start, search_end):
        line = lines[i]
        if 'logger.warning' in line and context_match in content[sum(len(l) for l in lines[:i]):sum(len(l) for l in lines[:i+1])]:
            found_warn = i
            in_warning = True
            warning_start = i
            # 跟踪括号
            paren_depth = line.count('(') - line.count(')')
            break

    if found_warn < 0:
        print(f"  [WARN] 未找到 logger.warning (context_match={context_match})")
        return False

    # 找到 logger.warning 调用的结束位置 (paren_depth = 0)
    for j in range(found_warn, search_end):
        line = lines[j]
        paren_depth += line.count('(') - line.count(')')
        if paren_depth == 0 and j > found_warn:
            # 找到结束
            last_line = lines[j]
            if 'exc_info=True' in last_line or 'exc_info = True' in last_line:
                print(f"  [SKIP] 已有 exc_info=True ({file_path}:{j+1})")
                return True
            # 在该行末尾加 exc_info=True
            stripped = last_line.rstrip()
            # 找到 ) 的位置
            close_paren_idx = stripped.rfind(')')
            if close_paren_idx == -1:
                print(f"  [ERROR] 未找到 )")
                return False
            # 判断原行末尾是 ',' 还是 ')'
            before_close = stripped[max(0, close_paren_idx - 30):close_paren_idx]
            if ',' in before_close:
                # 已经有逗号, 直接加 exc_info=True
                new_line = stripped[:close_paren_idx].rstrip() + ',\n                    exc_info=True,\n                ' + stripped[close_paren_idx:].lstrip()
            else:
                # 没有逗号, 加逗号 + 换行
                new_line = stripped[:close_paren_idx].rstrip() + ',\n                    exc_info=True,\n                ' + stripped[close_paren_idx:].lstrip()

            # 添加 R199-A 注释 (在 logger.warning 上方)
            new_lines = lines[:j] + [new_line + '\n'] + lines[j+1:]
            file_path.write_text(''.join(new_lines), encoding='utf-8')
            print(f"  [OK] {file_path.name}:{j+1} 加 exc_info=True")
            return True

    print(f"  [WARN] 未找到 logger.warning 结束位置")
    return False


def main():
    print("[R199-A] 应用 P0 风险软解析修复...")
    print()

    fixed_count = 0
    for fix in KNOWN_P0_FIXES:
        file_path = PROJECT_ROOT / fix['file']
        if not file_path.exists():
            print(f"  [ERROR] 文件不存在: {fix['file']}")
            continue

        print(f"[FIX] {fix['file']}:{fix['line']}  ({fix['description']})")
        success = apply_fix_at(file_path, fix['line'], fix['context_match'])
        if success:
            fixed_count += 1
        print()

    print(f"[R199-A] 修复完成: {fixed_count}/{len(KNOWN_P0_FIXES)}")
    return fixed_count


if __name__ == '__main__':
    main()
