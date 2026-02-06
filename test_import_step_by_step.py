#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐步测试导入链
"""

import sys
import traceback

def test_import_step_by_step():
    """逐步测试导入"""
    print("=" * 80)
    print("逐步测试导入链")
    print("=" * 80)

    try:
        print("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        print("✓ Qt模块导入成功")

        print("2. 创建QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication创建成功")

        print("3. 导入loguru...")
        from loguru import logger
        print("✓ loguru导入成功")

        print("4. 导入numpy...")
        import numpy as np
        print("✓ numpy导入成功")

        print("5. 导入pandas...")
        import pandas as pd
        print("✓ pandas导入成功")

        print("6. 导入matplotlib...")
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        print("✓ matplotlib导入成功")

        print("7. 导入collections...")
        from collections import defaultdict, deque
        print("✓ collections导入成功")

        print("8. 导入dataclasses...")
        from dataclasses import dataclass, field
        print("✓ dataclasses导入成功")

        print("9. 导入enum...")
        from enum import Enum, auto
        print("✓ enum导入成功")

        print("10. 导入concurrent.futures...")
        from concurrent.futures import ThreadPoolExecutor
        print("✓ concurrent.futures导入成功")

        print("11. 导入contextlib...")
        from contextlib import contextmanager
        print("✓ contextlib导入成功")

        print("12. 导入statistics...")
        import statistics
        print("✓ statistics导入成功")

        print("13. 导入random...")
        import random
        print("✓ random导入成功")

        print("14. 导入time...")
        import time
        print("✓ time导入成功")

        print("15. 导入threading...")
        import threading
        print("✓ threading导入成功")

        print("16. 导入os...")
        import os
        print("✓ os导入成功")

        print("17. 导入json...")
        import json
        print("✓ json导入成功")

        print("18. 导入hashlib...")
        import hashlib
        print("✓ hashlib导入成功")

        print("19. 导入warnings...")
        import warnings
        print("✓ warnings导入成功")

        print("20. 导入tracemalloc...")
        import tracemalloc
        print("✓ tracemalloc导入成功")

        print("21. 导入typing...")
        from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple
        print("✓ typing导入成功")

        print("22. 导入datetime...")
        from datetime import datetime, timedelta
        print("✓ datetime导入成功")

        print("23. 导入pathlib...")
        from pathlib import Path
        print("✓ pathlib导入成功")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_import_step_by_step()
    sys.exit(0 if success else 1)