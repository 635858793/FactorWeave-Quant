"""
R106 紧急修复: 截断 right_panel.py 重复内容 + 删除 4 个行业分析死方法
1. 截断到第一个 class RightPanel 结束位置(行 3587)
2. 然后再做 4 方法删除
"""
import ast
import sys
from pathlib import Path

TARGET = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\ui\panels\right_panel.py')
BACKUP = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\ui\panels\right_panel.py.r106.broken')

# 1. 备份当前破坏状态
source = TARGET.read_text(encoding='utf-8')
BACKUP.write_text(source, encoding='utf-8')
print(f"[1] 备份破坏文件到 {BACKUP}")

# 2. 截断到第二个 class RightPanel 之前
lines = source.split('\n')
# 找出所有 class RightPanel 行
class_lines = [i for i, line in enumerate(lines) if line == 'class RightPanel(BasePanel):']
print(f"[2] 找到 class RightPanel 行: {class_lines}")

if len(class_lines) > 1:
    # 截断到第一个 class RightPanel 结束的合理位置
    # 第二个 class RightPanel 之前
    truncate_at = class_lines[1] - 2  # 减 2 是为了删掉前一个空行
    # 找前一个连续的 \n
    while truncate_at > 0 and lines[truncate_at].strip() == '':
        truncate_at -= 1
    truncate_at += 1  # 保留一个空行
    print(f"[3] 截断到行 {truncate_at}")
    new_lines = lines[:truncate_at]
    # 确保文件以 \n 结尾
    if new_lines[-1] != '':
        new_lines.append('')
    new_source = '\n'.join(new_lines)
else:
    new_source = source

print(f"[4] 新文件长度: {len(new_source)} 行 (原 {len(source.split(chr(10)))} 行)")

# 3. 验证
class_count = new_source.count('class RightPanel')
print(f"[5] 'class RightPanel' 出现 {class_count} 次")

# 4. 现在删除 4 个行业分析死方法
method1_idx = new_source.find("def _on_refresh_industry_clicked")
method4_idx = new_source.find("def _update_industry_ui")
print(f"[6] _on_refresh_industry_clicked idx={method1_idx}, _update_industry_ui idx={method4_idx}")

if method1_idx > 0 and method4_idx > 0:
    resize_idx = new_source.find("def resizeEvent", method4_idx)
    print(f"    resizeEvent idx={resize_idx}")

    delete_start = new_source.rfind('\n\n', 0, method1_idx) + 2
    delete_end = new_source.rfind('\n', 0, resize_idx) + 1
    print(f"[7] 删除范围: {delete_start}..{delete_end} ({delete_end-delete_start} 字符)")

    replacement = '''# R106 P0-1 修复 (审计 2026-07-06): 删除行业分析链 4 个死方法
# _on_refresh_industry_clicked / _fetch_industry_data / _reset_industry_loading_flag
# / _update_industry_ui 全部仅服务于 _create_industry_tab 死方法 (0 业务方),
# 与 _create_industry_tab 一起物理删除. 行业分析功能将由 HVD-36 重建.

'''
    new_source = new_source[:delete_start] + replacement + new_source[delete_end:]
    print(f"[8] 删除后文件长度: {len(new_source)} 字符")

# 5. 语法检查
try:
    ast.parse(new_source)
    print("[9] ✅ Python 语法检查通过")
except SyntaxError as e:
    print(f"[9] ❌ 语法错误: {e}")
    sys.exit(1)

# 6. 验证删除
for m in ['_on_refresh_industry_clicked', '_fetch_industry_data', '_reset_industry_loading_flag', '_update_industry_ui']:
    cnt = new_source.count(f'def {m}(')
    status = "✅" if cnt == 0 else f"❌ 仍{cnt}次"
    print(f"    {status} {m}")

# 7. 写回
TARGET.write_text(new_source, encoding='utf-8')
print(f"[10] ✅ 修复完成, 文件已写回: {len(new_source)} 字符, {new_source.count(chr(10))+1} 行")
