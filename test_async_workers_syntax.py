#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试async_workers文件语法
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_async_workers_syntax():
    """测试async_workers文件语法"""
    print("=" * 80)
    print("测试async_workers文件语法")
    print("=" * 80)

    try:
        print("1. 编译async_workers.py文件...")
        import py_compile
        py_compile.compile('gui/widgets/performance/workers/async_workers.py', doraise=True)
        print("✓ async_workers.py文件编译成功")

        print("2. 导入async_workers模块（不导入PyQt5）...")
        import ast
        with open('gui/widgets/performance/workers/async_workers.py', 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        print("✓ async_workers.py文件语法检查通过")

        print("✓ 所有测试通过")
        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_async_workers_syntax()
    print(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)