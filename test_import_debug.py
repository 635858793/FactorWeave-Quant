#!/usr/bin/env python3
import sys
import os

# 禁用异步日志以避免干扰
os.environ['LOGURU_ASYNC_MODE'] = 'false'

print("Importing MainWindowCoordinator...")

try:
    import faulthandler
    faulthandler.enable()
except:
    pass

try:
    from core.coordinators import MainWindowCoordinator
    print("✓ MainWindowCoordinator imported successfully")
except SystemExit as e:
    print(f"✗ SystemExit: {e.code}")
    sys.exit(e.code)
except KeyboardInterrupt:
    print("✗ KeyboardInterrupt")
    sys.exit(1)
except Exception as e:
    print(f"✗ Exception: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    print("Import attempt completed")
