#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入链，找出性能监控系统自动启动的原因
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 开始测试导入链 ===")

# 测试1: 导入 core.trading.interfaces
try:
    print("\n1. 导入 core.trading.interfaces...")
    from core.trading import xtp_pro_trading_interface
    print("✓ core.trading.interfaces 导入成功")
except Exception as e:
    print(f"✗ core.trading.interfaces 导入失败: {e}")

print("\n=== 测试完成 ===")
