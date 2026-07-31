"""R164 紧急修复 v7: 修复 trading_widget.py L900 重复 exc_info"""
from pathlib import Path
p = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\trading_widget.py")
content = p.read_text(encoding='utf-8')

# 修复 L900
old_patterns = [
    '            logger.error(f"清除数据失败: {str(e)}", exc_info=True)", exc_info=True)", exc_info=True)',
    '            logger.error(f"清除数据失败: {str(e)}", exc_info=True)", exc_info=True)',
    '            logger.error(f"清除数据失败: {str(e)}", exc_info=True)',
]
new_pattern = '            logger.error(f"清除数据失败: {str(e)}", exc_info=True)'

for old in old_patterns:
    if old in content:
        # 只替换第一次出现
        content = content.replace(old, new_pattern, 1)
        print(f'[FIX] replaced: {old[:80]}...')
        break

# 修复 L1163 (如果还有问题)
if '            logger.error(f"清除数据失败: {str(e)}' in content and ', exc_info=True)' not in content.split('            logger.error(f"清除数据失败: {str(e)}')[1].split('\n')[0]:
    content = content.replace(
        '            logger.error(f"清除数据失败: {str(e)}',
        '            logger.error(f"清除数据失败: {str(e)}", exc_info=True)',
        1,
    )
    print('[FIX] L1163')

p.write_text(content, encoding='utf-8')
print('Done')
