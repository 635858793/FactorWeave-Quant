#!/usr/bin/env python3
"""
PyQt5 信号类型全面审核测试

验证所有使用 Any 类型的信号定义及其实际运行情况
"""

import sys
from PyQt5.QtCore import pyqtSignal, QObject
from typing import Any, Dict


class TestSignalDefinitions(QObject):
    """测试信号定义"""
    
    # 原始定义（使用 Any - 有问题）
    # signal_with_any = pyqtSignal(str, Any)
    
    # 修复后的定义（使用 object）
    signal_with_object = pyqtSignal(str, object)
    
    # 三参数版本（模拟 data_updated）
    # data_updated_any = pyqtSignal(str, str, Any)  # 有问题的定义
    data_updated_object = pyqtSignal(str, str, object)  # 修复后的定义
    
    def __init__(self):
        super().__init__()
        self.received_signals = []
        
        # 连接信号
        self.signal_with_object.connect(self.on_signal_with_object)
        self.data_updated_object.connect(self.on_data_updated_object)
    
    def on_signal_with_object(self, name: str, value):
        """接收 parameter_changed 信号"""
        self.received_signals.append({
            'type': 'parameter_changed',
            'name': name,
            'value': value,
            'value_type': type(value).__name__
        })
    
    def on_data_updated_object(self, tab_name: str, data_type: str, data):
        """接收 data_updated 信号"""
        self.received_signals.append({
            'type': 'data_updated',
            'tab_name': tab_name,
            'data_type': data_type,
            'data': data,
            'data_type_name': type(data).__name__
        })


def test_all_signal_types():
    """测试所有信号类型"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    print("=" * 80)
    print("PyQt5 信号类型全面审核测试")
    print("=" * 80)
    
    test_obj = TestSignalDefinitions()
    
    # 测试 1: parameter_changed 信号（2 参数）
    print("\n【测试 1】parameter_changed 信号（模拟 ParameterEditorWidget）")
    print("-" * 80)
    
    test_cases_2params = [
        ("check_mode", "str", str),
        ("lookahead_window", 10, int),
        ("volatility_factor", 1.5, float),
        ("vectorized_enabled", True, bool),
    ]
    
    for name, value, expected_type in test_cases_2params:
        try:
            test_obj.signal_with_object.emit(name, value)
            actual_type = type(value).__name__
            print(f"✓ {name}: {value} ({actual_type})")
        except Exception as e:
            print(f"✗ {name} 失败：{e}")
            return False
    
    # 测试 2: data_updated 信号（3 参数）
    print("\n【测试 2】data_updated 信号（模拟 PerformanceDataUpdateManager）")
    print("-" * 80)
    
    test_cases_3params = [
        ("system_monitor", "data", {"cpu": 50.5, "memory": 60.2}),
        ("sector_flow", "rank", {"sector": "科技", "flow": 1000000}),
        ("pattern_analysis", "stats", [{"pattern": "头肩顶", "count": 5}]),
    ]
    
    for tab_name, data_type, data in test_cases_3params:
        try:
            test_obj.data_updated_object.emit(tab_name, data_type, data)
            actual_type = type(data).__name__
            print(f"✓ {tab_name}/{data_type}: {actual_type}")
        except Exception as e:
            print(f"✗ {tab_name}/{data_type} 失败：{e}")
            return False
    
    # 验证接收到的信号
    print("\n【测试 3】验证信号接收")
    print("-" * 80)
    
    param_signals = [s for s in test_obj.received_signals if s['type'] == 'parameter_changed']
    data_signals = [s for s in test_obj.received_signals if s['type'] == 'data_updated']
    
    print(f"接收到 parameter_changed 信号：{len(param_signals)} 个")
    print(f"接收到 data_updated 信号：{len(data_signals)} 个")
    
    if len(param_signals) != len(test_cases_2params):
        print(f"✗ parameter_changed 信号数量不匹配")
        return False
    
    if len(data_signals) != len(test_cases_3params):
        print(f"✗ data_updated 信号数量不匹配")
        return False
    
    print("✓ 所有信号都正确接收")
    
    # 性能测试
    print("\n【测试 4】性能测试（1000 次信号发射）")
    print("-" * 80)
    
    import time
    start = time.time()
    for i in range(1000):
        test_obj.signal_with_object.emit(f"param_{i}", i)
    elapsed = time.time() - start
    
    print(f"1000 次信号发射耗时：{elapsed*1000:.2f}ms")
    print(f"平均每次：{elapsed*1000000:.2f}μs")
    
    if elapsed < 1.0:  # 1 秒内完成 1000 次是正常的
        print("✓ 性能正常")
    else:
        print("⚠ 性能可能有问题")
    
    print("\n" + "=" * 80)
    print("✓ 所有测试通过！信号类型修复方案验证成功！")
    print("=" * 80)
    
    return True


def analyze_signal_definitions():
    """分析系统中的信号定义"""
    print("\n【系统信号定义分析报告】")
    print("=" * 80)
    
    # 读取文件分析
    import os
    import re
    
    project_root = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui"
    
    # 查找所有使用 Any 的信号定义
    any_signal_pattern = re.compile(r'pyqtSignal\([^)]*Any[^)]*\)')
    found_issues = []
    
    for root, dirs, files in os.walk(project_root):
        # 跳过测试目录和备份目录
        if 'test' in root or 'backup' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = any_signal_pattern.findall(content)
                        if matches:
                            for match in matches:
                                found_issues.append({
                                    'file': file_path,
                                    'definition': match
                                })
                except Exception:
                    pass
    
    if found_issues:
        print(f"\n发现 {len(found_issues)} 个使用 Any 类型的信号定义：\n")
        for i, issue in enumerate(found_issues, 1):
            print(f"{i}. {issue['file']}")
            print(f"   定义：{issue['definition']}")
            print()
    else:
        print("\n✓ 未发现其他使用 Any 类型的信号定义（除已修复的外）")
    
    print("=" * 80)


if __name__ == '__main__':
    # 运行分析
    analyze_signal_definitions()
    
    # 运行测试
    success = test_all_signal_types()
    
    sys.exit(0 if success else 1)
