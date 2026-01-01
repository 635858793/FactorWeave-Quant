import sys
import traceback

try:
    from gui.dialogs.enhanced_strategy_manager_dialog import EnhancedStrategyManagerDialog
    print("导入成功")
except Exception as e:
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {e}")
    traceback.print_exc()
