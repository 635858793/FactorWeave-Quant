"""
R173-P0-2 智能缩进修复 v2: AST 解析 + 自动检测 + 修复
=============================================================
针对 account_manager.py / signal_trading_bridge.py 中的
"logger.warning( 缩进过深" 模式 (R145-F 批量升级时引入)

策略:
1. 逐行扫描
2. 检测 logger.warning(/logger.error( 缩进 < 8 空格
3. 找到该行前面的 except Exception ...: 行, 取其缩进 + 4
4. 自动调整 logger 行的缩进
"""
import re
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

TARGET_FILES = [
    PROJECT_ROOT / "core" / "trading" / "account_manager.py",
    PROJECT_ROOT / "core" / "services" / "signal_trading_bridge.py",
]


def fix_indent_wrong(source: str) -> tuple[str, int]:
    """修复 logger.xxx( 缩进错误的笔误 (R173-P0-2 模式)

    Pattern:
        except Exception as e:    ← 缩进 = X
        logger.error(...)         ← 当前缩进 = < X+4 (错)
            return ...

    修复:
        except Exception as e:    ← 缩进 = X
            logger.error(...)     ← 缩进 = X+4
            return ...
    """
    fixed_count = 0
    lines = source.split('\n')
    new_lines = []
    except_indent_stack = []  # 维护 except 块的缩进栈

    for i, line in enumerate(lines):
        # 检测 except ...: 行
        m_except = re.match(r'^(\s*)except\s+\S+', line)
        if m_except:
            except_indent = len(m_except.group(1))
            except_indent_stack.append(except_indent)
            new_lines.append(line)
            continue

        # 检测 logger.xxx( 行, 检查缩进
        m_logger = re.match(r'^(\s+)(logger\.(?:warning|error|info|debug)\()', line)
        if m_logger and except_indent_stack:
            current_indent = len(m_logger.group(1))
            expected_except = except_indent_stack[-1]
            expected_indent = expected_except + 4  # except 块内 logger 应有 except+4 缩进

            # 如果缩进错误 (太浅, 比如 0/4)
            if current_indent < expected_indent:
                # 修复缩进
                stripped = line.lstrip()
                new_line = ' ' * expected_indent + stripped
                new_lines.append(new_line)
                fixed_count += 1
                continue

        # 检测 return/break/continue/raise 结束块
        if re.match(r'^\s*(return|break|continue|raise)\b', line):
            pass  # 不弹出 except_indent_stack

        # 检测函数/类定义, 清空栈
        if re.match(r'^(class |def )', line):
            except_indent_stack = []

        new_lines.append(line)

    return '\n'.join(new_lines), fixed_count


def main():
    total_fixed = 0
    for f in TARGET_FILES:
        if not f.exists():
            print(f"  [SKIP] 文件不存在: {f}")
            continue

        source = f.read_text(encoding="utf-8")
        original = source

        source, count = fix_indent_wrong(source)
        print(f"  {f.name}: 修复 logger 缩进错误 {count} 处")

        if source != original:
            f.write_text(source, encoding="utf-8")
            print(f"  [OK] {f.name}: 写入修改")
            total_fixed += count
        else:
            print(f"  [SKIP] {f.name}: 无修改")

    print(f"\n总修复: {total_fixed} 处")


if __name__ == "__main__":
    main()
