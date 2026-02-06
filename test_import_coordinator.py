#!/usr/bin/env python3
import traceback
import sys

print("Importing MainWindowCoordinator...")
try:
    from core.coordinators import MainWindowCoordinator
    print("✓ MainWindowCoordinator imported successfully")
except Exception as e:
    print(f"✗ MainWindowCoordinator import failed: {e}")
    traceback.print_exc()
    sys.exit(1)
