#!/usr/bin/env python3
"""统计 4 个高优先级 GUI 文件的 exc_info 缺失数 (R164-A-续期 预备)"""
import re
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

TARGETS = {
    "gui/widgets/trading_widget.py": 25,
    "gui/widgets/performance/tabs/risk_control_center_tab.py": 23,
    "gui/widgets/performance/tabs/trading_execution_monitor_tab.py": 21,
    "gui/widgets/enhanced_ui/order_book_widget.py": 17,
}


def count_missing_exc_info(content: str) -> int:
    """统计 exc_info 缺失的 logger.error/warning/critical 调用 (R51 #5 强约束)

    规则:
    1. 找到所有 except Exception as e: 后的代码块
    2. 找到块内所有 logger.error/warning/critical 调用
    3. 检查是否带 exc_info=True
    4. 排除 logger.exception() (自带 traceback)
    """
    missing = 0
    missing_details = []
    lines = content.split('\n')

    in_except = False
    except_indent = 0
    except_block = []
    except_line = 0

    for i, line in enumerate(lines, 1):
        # 检测 except 行
        if re.match(r'\s*except\s+.*\s+as\s+\w+.*:', line):
            in_except = True
            except_indent = len(line) - len(line.lstrip())
            except_block = []
            except_line = i
            continue
        # 检测 except 块结束 (缩进回到 except 之前)
        if in_except:
            if line.strip() == '' or line.startswith(' ' * (except_indent + 1)) or line.startswith('\t'):
                except_block.append((i, line))
            else:
                # 块结束, 统计
                missing_in_block, details = _analyze_except_block(except_block)
                missing += missing_in_block
                missing_details.extend(details)
                in_except = False
                except_block = []

    # 处理末尾 except 块
    if in_except and except_block:
        missing_in_block, details = _analyze_except_block(except_block)
        missing += missing_in_block
        missing_details.extend(details)

    return missing, missing_details


def _analyze_except_block(except_block):
    """分析一个 except 块内的 logger.error/warning/critical 调用"""
    missing = 0
    details = []
    for line_no, line in except_block:
        # 匹配 logger.error/warning/critical (排除 logger.exception)
        m = re.search(r'logger\.(error|warning|critical)\s*\(', line)
        if m and 'exception' not in line:
            # 检查是否带 exc_info
            if 'exc_info' not in line:
                missing += 1
                details.append((line_no, line.strip()[:100]))
    return missing, details


for rel_path, expected in TARGETS.items():
    full_path = ROOT / rel_path
    if not full_path.exists():
        print(f"[X] {rel_path}: 文件不存在")
        continue
    content = full_path.read_text(encoding='utf-8')
    actual, details = count_missing_exc_info(content)
    status = "OK" if actual == 0 else f"待修复 {actual} 处 (预期 {expected})"
    print(f"\n[{status}] {rel_path}: {actual} missing")
    if details:
        print(f"  样例缺失 (前 5):")
        for line_no, line in details[:5]:
            print(f"    L{line_no}: {line}")
