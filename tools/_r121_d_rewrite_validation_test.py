"""
R121-D P1 工具脚本: 把 test_comprehensive_validation.py 的顶层执行代码移到 main() 函数
Why: 666 行内容逐行缩进不现实, 用 AST 解析 + 行号定位 + 字符串重写更稳妥.
"""
import ast
import sys
from pathlib import Path

src_path = Path("tests/test_comprehensive_validation.py")
src = src_path.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

# 解析 AST
tree = ast.parse(src)
class_node = None
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "ValidationReport":
        class_node = node
        break

assert class_node is not None, "ValidationReport class not found"

# class 结束行 (1-based) → 0-based index
class_end_lineno = class_node.end_lineno  # e.g., 60 (last line of class)
print(f"ValidationReport class ends at line {class_end_lineno} (0-based: {class_end_lineno - 1})")

# 找到 class 之后的第一个非空行, 那是顶层执行代码开始
# 类结束后的代码 (line 61+) 需要缩进 +4 空格
# 类内代码保持不变 (line 1 - class_end_lineno)

# 策略: 1-based 行号
# - line 1 - class_end_lineno: 保持不变
# - line (class_end_lineno+1) - len(lines): 缩进 +4 空格
# - 末尾: 追加 `if __name__ == "__main__":` 守卫 + 替换 sys.exit() 为 return

# 简化: 我们要做的关键改动:
# 1. 在 class_end_lineno 后插入 def main() -> int:
# 2. 把 class_end_lineno 之后的所有行缩进 +4 (即从原 line 61 开始)
# 3. 把最后的 sys.exit(0 if len(report.failed) == 0 else 1) 替换为 return 0 if len(report.failed) == 0 else 1
# 4. 末尾追加:
#    if __name__ == "__main__":
#        sys.exit(main())

new_lines = []
for i, line in enumerate(lines, start=1):
    if i <= class_end_lineno:
        # class 内 (1-based 1..class_end_lineno): 保持不变
        new_lines.append(line)
    else:
        # class 外 (61+): 缩进 +4 空格
        # 但要跳过文件末尾的空行
        if line.strip() == "":
            new_lines.append(line)  # 空行保持
        else:
            new_lines.append("    " + line)

# 找到最后 sys.exit() 那行, 替换为 return
# 末行: `sys.exit(0 if len(report.failed) == 0 else 1)`
new_content = "".join(new_lines)
new_content = new_content.replace(
    "    sys.exit(0 if len(report.failed) == 0 else 1)\n",
    "    return 0 if len(report.failed) == 0 else 1\n",
    1,  # 只替换第一次
)

# 末尾追加 if __name__ 守卫
new_content += """
if __name__ == "__main__":
    sys.exit(main())
"""

# 写入
src_path.write_text(new_content, encoding="utf-8")
print(f"File rewritten. Total lines: {len(new_content.splitlines())}")

# 验证: 重新解析
try:
    ast.parse(new_content)
    print("AST parse OK - no syntax error")
except SyntaxError as e:
    print(f"AST parse FAIL: {e}")
    sys.exit(1)
