"""
R106 P0-1 安全修复脚本 - 精确删除 4 个行业分析链死方法
- 先备份文件
- 然后精确切片删除
- 不使用 source[after_last+1:] 这种危险切片

执行规范: R6 §6.3 + R104 5 铁律
"""
import ast
import sys
from pathlib import Path

TARGET = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\ui\panels\right_panel.py')
BACKUP = TARGET.with_suffix('.py.r106.bak')

# 1. 备份
source = TARGET.read_text(encoding='utf-8')
BACKUP.write_text(source, encoding='utf-8')
print(f"[1] 备份完成: {BACKUP}, 原文件 {len(source)} 字节")

# 2. 检查文件是否被破坏:寻找类定义行数
class_count = source.count('class RightPanel')
print(f"[2] 'class RightPanel' 出现 {class_count} 次 (正常=1)")

# 3. 找到第一个有效 _on_refresh_industry_clicked 位置(应该是类内的)
# 由于文件重复,我们取第一个出现的 _on_refresh_industry_clicked 位置
method1_idx = source.find("def _on_refresh_industry_clicked")
method4_idx = source.find("def _update_industry_ui")
print(f"[3] _on_refresh_industry_clicked idx={method1_idx}, _update_industry_ui idx={method4_idx}")

# 4. 找到 _update_industry_ui 之后的下一个类级别 def (resizeEvent)
# 因为 _update_industry_ui 是 @pyqtSlot 装饰,需要找 "\n    def " 或 "\n    @pyqtSlot"
# 找 @pyqtSlot 之后第一个 def resizeEvent
resize_idx = source.find("def resizeEvent", method4_idx)
print(f"[4] resizeEvent idx={resize_idx}")

assert method1_idx > 0 and method4_idx > 0 and resize_idx > method4_idx

# 5. 关键:向前回溯找 _update_industry_ui 之前的空白行 / @pyqtSlot 装饰
# 完整删除块:method1_idx 之前回溯到上一个 \n\n,然后到 resize_idx 之后回溯到前一个 \n
# 安全做法: 找到 method1_idx 之前的 \n\n,resize_idx 之前的 \n
# 用 method1_idx 之前的连续空行作为起点
delete_start = source.rfind('\n\n', 0, method1_idx) + 2  # +2 跳过 \n\n
# resizeEvent 之前的 \n
delete_end = source.rfind('\n', 0, resize_idx) + 1
print(f"[5] 删除范围: {delete_start}..{delete_end} ({delete_end-delete_start} 字符)")

# 6. 拼接
replacement = '''# R106 P0-1 修复 (审计 2026-07-06): 删除行业分析链 4 个死方法
# _on_refresh_industry_clicked / _fetch_industry_data / _reset_industry_loading_flag
# / _update_industry_ui 全部仅服务于 _create_industry_tab 死方法 (0 业务方),
# 与 _create_industry_tab 一起物理删除. 行业分析功能将由 HVD-36 重建.

'''
new_source = source[:delete_start] + replacement + source[delete_end:]

# 7. 验证
print(f"[6] 新文件长度: {len(new_source)} (原 {len(source)}, 减 {len(source) - len(new_source)})")
TARGET.write_text(new_source, encoding='utf-8')

# 8. 验证删除
verify = TARGET.read_text(encoding='utf-8')
print(f"[7] 验证:")
for m in ['_on_refresh_industry_clicked', '_fetch_industry_data', '_reset_industry_loading_flag', '_update_industry_ui']:
    # 应该是 0 次(如果类内已删除)
    cnt = verify.count(f'def {m}(')
    status = "✅" if cnt == 0 else f"❌ 仍{cnt}次"
    print(f"    {status} {m}")

# 9. 语法检查
try:
    ast.parse(new_source)
    print("[8] ✅ Python 语法检查通过")
except SyntaxError as e:
    print(f"[8] ❌ 语法错误: {e}")
    # 恢复
    TARGET.write_text(source, encoding='utf-8')
    print(f"    已恢复原文件, 备份保留: {BACKUP}")
    sys.exit(1)
