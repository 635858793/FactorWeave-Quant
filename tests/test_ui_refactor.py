import sys
import io

old_stdout = sys.stdout
old_stderr = sys.stderr

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

app = QApplication(sys.argv)

print("Testing matplotlib initialization...", flush=True)

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    print("[PASS] Matplotlib initialized successfully", flush=True)
except Exception as e:
    print(f"[FAIL] Matplotlib initialization failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Testing dialog import...", flush=True)
try:
    from gui.dialogs.enhanced_strategy_manager_dialog import EnhancedStrategyManagerDialog
    print("[PASS] Import successful", flush=True)
except Exception as e:
    print(f"[FAIL] Import failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Creating dialog...", flush=True)
try:
    dialog = EnhancedStrategyManagerDialog()
    print("[PASS] Dialog created successfully", flush=True)
except Exception as e:
    print(f"[FAIL] Dialog creation failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("All tests passed!", flush=True)
