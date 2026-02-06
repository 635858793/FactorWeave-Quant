#!/usr/bin/env python3
import traceback
import sys

print("Step 1: Importing basic modules...")
try:
    from utils.exception_handler import setup_exception_handler
    from utils.warning_suppressor import suppress_warnings
    print("✓ Utils imported")
except Exception as e:
    print(f"✗ Utils import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\nStep 2: Importing core modules...")
try:
    from core.coordinators import MainWindowCoordinator
    print("✓ MainWindowCoordinator imported")
except Exception as e:
    print(f"✗ MainWindowCoordinator import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from core.events import EventBus, get_event_bus
    print("✓ EventBus imported")
except Exception as e:
    print(f"✗ EventBus import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from core.containers import ServiceContainer, get_service_container
    print("✓ ServiceContainer imported")
except Exception as e:
    print(f"✗ ServiceContainer import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from core.services.service_bootstrap import bootstrap_services
    print("✓ bootstrap_services imported")
except Exception as e:
    print(f"✗ bootstrap_services import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from core.graceful_shutdown import shutdown_manager
    print("✓ shutdown_manager imported")
except Exception as e:
    print(f"✗ shutdown_manager import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\nStep 3: Importing Qt modules...")
try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QIcon
    from qasync import QEventLoop
    print("✓ Qt modules imported")
except Exception as e:
    print(f"✗ Qt import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\nStep 4: Importing optimization modules...")
try:
    from optimization.webgpu_chart_renderer import get_webgpu_chart_renderer
    print("✓ webgpu_chart_renderer imported")
except Exception as e:
    print(f"✗ webgpu_chart_renderer import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\nStep 5: Importing main...")
try:
    import main
    print("✓ Main imported successfully")
except Exception as e:
    print(f"✗ Main import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All imports successful!")
