"""
R173-P0-3 智能脚本: 修复 signal_trading_bridge.py 21 处 logger.warning( 行首 0 缩进
=================================================================
Pattern:
    except Exception as e:
        # 注释
logger.warning(                    ← 0 缩进
            f"...", exc_info=True,
        )
        logger.debug(                ← 16 缩进 (在 except 块内)

修复:
    except Exception as e:
        # 注释
        logger.warning(              ← 8 缩进 (在 except 块内)
            f"...", exc_info=True,
        )
        logger.debug(
"""
import re
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

TARGET_FILE = PROJECT_ROOT / "core" / "services" / "signal_trading_bridge.py"


def fix_line_start_indent(source: str) -> tuple[str, int]:
    """修复 logger.warning( 行首 0 缩进 (但下面 f-string 在 except 块内)
    """
    fixed_count = 0
    lines = source.split('\n')
    new_lines = []

    for i, line in enumerate(lines):
        # 检测行首 0 缩进的 logger.warning(
        m = re.match(r'^logger\.(warning|error|info|debug)\(', line)
        if m:
            # 检查下一行是否在 except 块内 (缩进 > 0, 包含 f-string)
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # 找下一行 f-string 缩进
                f_match = re.match(r'^(\s+)f["\']', next_line)
                if f_match:
                    f_indent = len(f_match.group(1))
                    # f-string 缩进应 >= 12 (try/except 块内)
                    if f_indent >= 12:
                        # logger 缩进应为 f_indent - 12 + 4 = f_indent - 8
                        target_indent = f_indent - 12 + 8
                        if target_indent < 0:
                            target_indent = 4
                        # 修复 logger 行
                        new_line = ' ' * target_indent + line.lstrip()
                        new_lines.append(new_line)
                        fixed_count += 1
                        continue
        new_lines.append(line)

    return '\n'.join(new_lines), fixed_count


def main():
    if not TARGET_FILE.exists():
        print(f"  [SKIP] 文件不存在: {TARGET_FILE}")
        return

    source = TARGET_FILE.read_text(encoding="utf-8")
    original = source

    source, count = fix_line_start_indent(source)
    print(f"  signal_trading_bridge.py: 修复行首 logger 缩进 {count} 处")

    if source != original:
        TARGET_FILE.write_text(source, encoding="utf-8")
        print(f"  [OK] 写入修改")
    else:
        print(f"  [SKIP] 无修改")


if __name__ == "__main__":
    main()
