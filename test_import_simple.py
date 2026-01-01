import sys
sys.path.insert(0, '.')

try:
    import gui.dialogs.enhanced_strategy_manager_dialog
    print("导入成功")
except ImportError as e:
    print(f"ImportError: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
