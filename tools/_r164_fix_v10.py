"""R164 紧急修复 v10: 修复 L1194 (使用 chr(10) 避免转义)"""
from pathlib import Path
p = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\trading_widget.py")
content = p.read_text(encoding='utf-8')
# 使用 Unicode escape 避免 PS 转义问题
old_str = '                    logger.error(f"\u5206\u6790\u5f02\u5e38: {str(e)}'
new_str = '                    logger.error(f"\u5206\u6790\u5f02\u5e38: {str(e)}", exc_info=True)'
if old_str in content:
    content = content.replace(old_str, new_str, 1)
    p.write_text(content, encoding='utf-8')
    print('[FIX] L1194')
else:
    print('[NOT FOUND]')
    # 查找实际内容
    for i, line in enumerate(content.split('\n')):
        if '\u5206\u6790\u5f02\u5e38' in line:
            print(f'  L{i+1}: {repr(line)}')
