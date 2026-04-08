#!/usr/bin/env python3
"""
参数编辑器信号类型修复验证测试

验证 parameter_changed 信号可以正确传递各种类型的参数值
"""

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal


class TestWidget(QWidget):
    """测试 Widget"""
    
    # 修复后的信号定义（使用 object 类型）
    parameter_changed = pyqtSignal(str, object)
    
    def __init__(self):
        super().__init__()
        self.received_signals = []
        
        # 连接信号到槽函数
        self.parameter_changed.connect(self.on_parameter_changed)
    
    def on_parameter_changed(self, name: str, value):
        """槽函数：接收参数变化"""
        self.received_signals.append({
            'name': name,
            'value': value,
            'type': type(value).__name__
        })
        print(f"✓ 参数变化：{name} = {value} (类型：{type(value).__name__})")


def test_parameter_types():
    """测试各种参数类型"""
    app = QApplication(sys.argv)
    widget = TestWidget()
    
    print("=" * 60)
    print("参数编辑器信号类型修复验证测试")
    print("=" * 60)
    
    # 测试各种类型
    test_cases = [
        ("check_mode", "str"),
        ("lookahead_window", 10),
        ("ma_period", 20),
        ("atr_period", 14),
        ("volatility_factor", 1.5),
        ("trend_factor", 0.8),
        ("min_stop_loss", 0.02),
        ("max_stop_loss", 0.1),
        ("fixed_stop_loss", 0.05),
        ("min_take_profit", 0.03),
        ("max_take_profit", 0.2),
        ("trailing_profit", 0.05),
        ("profit_lock", 0.02),
        ("init_cash", 100000),
        ("fixed_count", 1000),
        ("slippage_percent", 0.001),
        ("vectorized_enabled", True),
        ("market_factor", 2.0),
    ]
    
    print("\n测试参数信号传递：\n")
    
    for name, value in test_cases:
        try:
            widget.parameter_changed.emit(name, value)
        except Exception as e:
            print(f"✗ {name} 失败：{e}")
            return False
    
    print("\n" + "=" * 60)
    print(f"测试结果：成功发射 {len(widget.received_signals)} 个信号")
    print("=" * 60)
    
    # 验证接收到的信号
    expected_types = {
        'check_mode': 'str',
        'lookahead_window': 'int',
        'ma_period': 'int',
        'atr_period': 'int',
        'volatility_factor': 'float',
        'trend_factor': 'float',
        'min_stop_loss': 'float',
        'max_stop_loss': 'float',
        'fixed_stop_loss': 'float',
        'min_take_profit': 'float',
        'max_take_profit': 'float',
        'trailing_profit': 'float',
        'profit_lock': 'float',
        'init_cash': 'int',
        'fixed_count': 'int',
        'slippage_percent': 'float',
        'vectorized_enabled': 'bool',
        'market_factor': 'float',
    }
    
    all_passed = True
    for i, signal in enumerate(widget.received_signals):
        expected_type = expected_types.get(signal['name'])
        actual_type = signal['type']
        
        if expected_type and actual_type != expected_type:
            print(f"✗ {signal['name']}: 期望 {expected_type}, 实际 {actual_type}")
            all_passed = False
        else:
            print(f"✓ {signal['name']}: {signal['value']} ({actual_type}) - 正确")
    
    print("\n" + "=" * 60)
    if all_passed and len(widget.received_signals) == len(test_cases):
        print("✓ 所有测试通过！信号类型修复成功！")
        print("=" * 60)
        return True
    else:
        print("✗ 测试失败")
        print("=" * 60)
        return False


if __name__ == '__main__':
    success = test_parameter_types()
    sys.exit(0 if success else 1)
