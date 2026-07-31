"""
R173-P0-2/P0-3 批量修复脚本: 41 处 logger.warning(, exc_info=True) 笔误
=================================================================
处理对象:
- core/trading/account_manager.py: 20 处
- core/services/signal_trading_bridge.py: 21 处

Pattern 修复:
    错:   logger.warning(, exc_info=True)
            f"...",
            f"...", exc_info=True,
        )
    正:   logger.warning(
            f"...",
            f"...", exc_info=True,
        )

L299 已由 Edit 修复, 跳过。
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# 待修复文件
TARGET_FILES = [
    PROJECT_ROOT / "core" / "trading" / "account_manager.py",
    PROJECT_ROOT / "core" / "services" / "signal_trading_bridge.py",
]


def fix_account_manager_typo(source: str) -> tuple[str, int]:
    """修复 account_manager.py 的 logger.warning(, exc_info=True) 笔误

    Pattern:
        except Exception as XXX:
            # 注释
                                logger.warning(, exc_info=True)
                f"...", exc_info=True,
            )

    修复后:
        except Exception as XXX:
            # 注释
            logger.warning(
                f"...", exc_info=True,
            )
    """
    fixed_count = 0
    lines = source.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 检测笔误行: 行末以 logger.warning(, exc_info=True) 结尾 (任意缩进)
        if re.search(r'logger\.warning\(\s*,\s*exc_info\s*=\s*True\s*\)\s*$', line):
            # 检查下一行是否以 f-string 开头 (修复关键)
            if i + 1 < len(lines) and re.search(r'^\s+f["\']', lines[i + 1]):
                # 提取当前行的缩进
                indent_match = re.match(r'^(\s*)', line)
                current_indent = indent_match.group(1) if indent_match else ''

                # 把笔误行替换为正确的 logger.warning( 起始
                new_lines.append(f"{current_indent}logger.warning(")
                i += 1
                # 继续合并接下来的 f-string 行直到找到闭括号 )
                # 找到 f-string 块结束 (匹配 ")" 闭括号)
                paren_depth = 1
                while i < len(lines):
                    f_line = lines[i]
                    # 简化处理: 直接保留 f-string 块直到遇到以 ), 或 "  结尾
                    new_lines.append(f_line)
                    # 检测 f-string 块结束 (行包含 ) 或 ), exc_info=True, 或 ), 单独)
                    if re.search(r'^\s*\)\s*$', f_line) or re.search(r'^\s*\)\s*,?\s*$', f_line):
                        i += 1
                        break
                    i += 1
                fixed_count += 1
                continue
        new_lines.append(line)
        i += 1
    return '\n'.join(new_lines), fixed_count


def fix_logger_error_indent(source: str) -> tuple[str, int]:
    """修复 logger.error 缩进错误 (except 块外, 缩进不足)

    Pattern:
        except Exception as e:
    logger.error(..., exc_info=True)  # 缺缩进
            return ...

    修复后:
        except Exception as e:
            logger.error(..., exc_info=True)  # 4 空格
            return ...
    """
    fixed_count = 0
    lines = source.split('\n')
    new_lines = []
    for i, line in enumerate(lines):
        # 检测缩进错误的 logger.error 行 (缩进 < 4 但应该是 8-12)
        m = re.match(r'^(\s+)logger\.error\(', line)
        if m:
            current_indent = m.group(1)
            if len(current_indent) < 4:
                # 检查前一行是否是 except Exception as e:
                if i > 0 and re.match(r'^\s*except\s+Exception\s+as\s+\w+:', lines[i - 1]):
                    # 修复缩进: 改为 8 空格 (方法内 except 块的标准缩进)
                    new_line = '        ' + line.lstrip()
                    new_lines.append(new_line)
                    fixed_count += 1
                    continue
        new_lines.append(line)
    return '\n'.join(new_lines), fixed_count


def main():
    total_fixed = 0
    for f in TARGET_FILES:
        if not f.exists():
            print(f"  ❌ 文件不存在: {f}")
            continue

        source = f.read_text(encoding="utf-8")
        original = source

        # 步骤 1: 修复 logger.warning(, exc_info=True) 笔误
        source, count1 = fix_account_manager_typo(source)
        print(f"  {f.name}: 修复 logger.warning(, exc_info=True) 笔误 {count1} 处")

        # 步骤 2: 修复 logger.error 缩进错误
        source, count2 = fix_logger_error_indent(source)
        print(f"  {f.name}: 修复 logger.error 缩进错误 {count2} 处")

        if source != original:
            f.write_text(source, encoding="utf-8")
            print(f"  [OK] {f.name}: 写入修改 ({count1 + count2} 处)")
            total_fixed += count1 + count2
        else:
            print(f"  [SKIP] {f.name}: 无修改")

    print(f"\n总修复: {total_fixed} 处")


if __name__ == "__main__":
    main()
