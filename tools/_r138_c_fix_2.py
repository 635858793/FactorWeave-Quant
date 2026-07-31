"""R138 子智能体 C: 修复 extension_service.py dispose 方法."""
from pathlib import Path

fp = Path('core/services/extension_service.py')
content = fp.read_text(encoding='utf-8')
lines = content.split('\n')

# 现状:
# L496:         except Exception as e:
# L497:     def _do_health_check(self) -> Dict[str, Any]:  <- 错误注入
# L498-L513:    _do_health_check 方法体
# L514: (空行)
# L515:             logger.error(f"Error disposing ExtensionService: {e}", exc_info=True)  <- 应在 L497

# 目标:
# L496:         except Exception as e:
# L497:             logger.error(f"Error disposing ExtensionService: {e}", exc_info=True)  <- 移到这里
# L498: (空行)
# L499:     def _do_health_check(self) -> Dict[str, Any]:  <- 重新注入

# 操作:
# 1. 删除 L497-L513 (0-indexed: 496-512)
# 2. 保留 L515 不变(会自动上移)

# 先看 L515
print(f'L515 (0-idx 514): {lines[514]}')
print(f'L496 (0-idx 495): {lines[495]}')
print(f'L497 (0-idx 496): {lines[496]}')
print(f'L513 (0-idx 512): {lines[512]}')
print(f'L514 (0-idx 513): {lines[513]}')

# 删除 0-idx 496-512 (17 行)
new_lines = lines[:496] + lines[513:]
new_content = '\n'.join(new_lines)
fp.write_text(new_content, encoding='utf-8')

# 验证
import ast
try:
    ast.parse(new_content)
    print('Syntax OK')
except SyntaxError as e:
    print(f'Syntax error: {e}')
