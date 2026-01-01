try:
    from gui.dialogs.enhanced_strategy_manager_dialog_v2 import SensitivityAnalysisDialog, StrategyComparisonDialog, ParameterScanDialog
    print('所有对话框导入成功！')
except Exception as e:
    print(f'错误: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
