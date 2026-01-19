#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试订单簿新指标的正确性
测试VWAP、TWAP、买卖压力指数、订单流不平衡度等指标
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from PyQt5.QtWidgets import QApplication
from loguru import logger

from gui.widgets.enhanced_ui.order_book_widget import OrderBookWidget
from core.events.event_bus import EventBus


def test_vwap_calculation():
    """测试VWAP计算"""
    print("\n" + "="*60)
    print("测试1: VWAP计算")
    print("="*60)
    
    # 创建测试数据
    bids = [
        {'price': 100.0, 'volume': 10.0},
        {'price': 99.5, 'volume': 20.0},
        {'price': 99.0, 'volume': 30.0},
        {'price': 98.5, 'volume': 40.0},
        {'price': 98.0, 'volume': 50.0}
    ]
    
    asks = [
        {'price': 101.0, 'volume': 15.0},
        {'price': 101.5, 'volume': 25.0},
        {'price': 102.0, 'volume': 35.0},
        {'price': 102.5, 'volume': 45.0},
        {'price': 103.0, 'volume': 55.0}
    ]
    
    # 计算期望值
    total_value = sum(bid['price'] * bid['volume'] for bid in bids)
    total_value += sum(ask['price'] * ask['volume'] for ask in asks)
    total_volume = sum(bid['volume'] for bid in bids) + sum(ask['volume'] for ask in asks)
    expected_vwap = total_value / total_volume
    
    print(f"买盘数据: {bids}")
    print(f"卖盘数据: {asks}")
    print(f"期望VWAP: {expected_vwap:.4f}")
    
    # 创建OrderBookWidget实例
    app = QApplication(sys.argv)
    event_bus = EventBus()
    widget = OrderBookWidget(event_bus=event_bus)
    
    # 添加历史快照
    for i in range(5):
        snapshot = {
            'timestamp': datetime.now() - timedelta(seconds=60 * i),
            'data': {
                'bids': bids,
                'asks': asks
            }
        }
        widget.historical_snapshots.append(snapshot)
    
    # 计算VWAP
    actual_vwap = widget._calculate_vwap(bids, asks)
    
    print(f"实际VWAP: {actual_vwap:.4f}")
    
    # 验证结果
    if abs(actual_vwap - expected_vwap) < 0.01:
        print("✅ VWAP计算正确")
        return True
    else:
        print(f"❌ VWAP计算错误，差异: {abs(actual_vwap - expected_vwap):.4f}")
        return False


def test_twap_calculation():
    """测试TWAP计算"""
    print("\n" + "="*60)
    print("测试2: TWAP计算")
    print("="*60)
    
    # 创建测试数据
    bids = [
        {'price': 100.0, 'volume': 10.0},
        {'price': 99.5, 'volume': 20.0},
        {'price': 99.0, 'volume': 30.0}
    ]
    
    asks = [
        {'price': 101.0, 'volume': 15.0},
        {'price': 101.5, 'volume': 25.0},
        {'price': 102.0, 'volume': 35.0}
    ]
    
    # 创建OrderBookWidget实例
    app = QApplication(sys.argv)
    event_bus = EventBus()
    widget = OrderBookWidget(event_bus=event_bus)
    
    # 添加历史快照，价格逐渐上涨
    for i in range(5):
        price_offset = i * 0.5
        snapshot_bids = [
            {'price': 100.0 + price_offset, 'volume': 10.0},
            {'price': 99.5 + price_offset, 'volume': 20.0},
            {'price': 99.0 + price_offset, 'volume': 30.0}
        ]
        
        snapshot_asks = [
            {'price': 101.0 + price_offset, 'volume': 15.0},
            {'price': 101.5 + price_offset, 'volume': 25.0},
            {'price': 102.0 + price_offset, 'volume': 35.0}
        ]
        
        snapshot = {
            'timestamp': datetime.now() - timedelta(seconds=60 * (4 - i)),
            'data': {
                'bids': snapshot_bids,
                'asks': snapshot_asks
            }
        }
        widget.historical_snapshots.append(snapshot)
    
    # 计算TWAP
    twap = widget._calculate_twap()
    
    print(f"历史快照数量: {len(widget.historical_snapshots)}")
    print(f"TWAP: {twap:.4f}")
    
    # 验证结果应该在合理范围内
    if 100.0 <= twap <= 102.0:
        print("✅ TWAP计算正确")
        return True
    else:
        print(f"❌ TWAP计算错误，超出合理范围")
        return False


def test_buy_sell_pressure_calculation():
    """测试买卖压力指数计算"""
    print("\n" + "="*60)
    print("测试3: 买卖压力指数计算")
    print("="*60)
    
    # 创建OrderBookWidget实例
    app = QApplication(sys.argv)
    event_bus = EventBus()
    widget = OrderBookWidget(event_bus=event_bus)
    
    # 测试用例1: 买盘压力
    bids1 = [{'price': 100.0, 'volume': 100.0}]
    asks1 = [{'price': 101.0, 'volume': 50.0}]
    pressure1 = widget._calculate_buy_sell_pressure(bids1, asks1)
    expected1 = (100.0 - 50.0) / (100.0 + 50.0)
    
    print(f"测试用例1: 买盘压力")
    print(f"买盘量: 100.0, 卖盘量: 50.0")
    print(f"期望压力指数: {expected1:.4f}")
    print(f"实际压力指数: {pressure1:.4f}")
    
    if abs(pressure1 - expected1) < 0.01 and pressure1 > 0:
        print("✅ 买盘压力计算正确")
        test1_passed = True
    else:
        print(f"❌ 买盘压力计算错误")
        test1_passed = False
    
    # 测试用例2: 卖盘压力
    bids2 = [{'price': 100.0, 'volume': 50.0}]
    asks2 = [{'price': 101.0, 'volume': 100.0}]
    pressure2 = widget._calculate_buy_sell_pressure(bids2, asks2)
    expected2 = (50.0 - 100.0) / (50.0 + 100.0)
    
    print(f"\n测试用例2: 卖盘压力")
    print(f"买盘量: 50.0, 卖盘量: 100.0")
    print(f"期望压力指数: {expected2:.4f}")
    print(f"实际压力指数: {pressure2:.4f}")
    
    if abs(pressure2 - expected2) < 0.01 and pressure2 < 0:
        print("✅ 卖盘压力计算正确")
        test2_passed = True
    else:
        print(f"❌ 卖盘压力计算错误")
        test2_passed = False
    
    # 测试用例3: 平衡
    bids3 = [{'price': 100.0, 'volume': 100.0}]
    asks3 = [{'price': 101.0, 'volume': 100.0}]
    pressure3 = widget._calculate_buy_sell_pressure(bids3, asks3)
    expected3 = 0.0
    
    print(f"\n测试用例3: 平衡")
    print(f"买盘量: 100.0, 卖盘量: 100.0")
    print(f"期望压力指数: {expected3:.4f}")
    print(f"实际压力指数: {pressure3:.4f}")
    
    if abs(pressure3 - expected3) < 0.01:
        print("✅ 平衡状态计算正确")
        test3_passed = True
    else:
        print(f"❌ 平衡状态计算错误")
        test3_passed = False
    
    return test1_passed and test2_passed and test3_passed


def test_order_flow_imbalance_calculation():
    """测试订单流不平衡度计算"""
    print("\n" + "="*60)
    print("测试4: 订单流不平衡度计算")
    print("="*60)
    
    # 创建OrderBookWidget实例
    app = QApplication(sys.argv)
    event_bus = EventBus()
    widget = OrderBookWidget(event_bus=event_bus)
    
    # 测试用例1: 高不平衡度
    bids1 = [{'price': 100.0, 'volume': 100.0}]
    asks1 = [{'price': 101.0, 'volume': 10.0}]
    imbalance1 = widget._calculate_order_flow_imbalance(bids1, asks1)
    expected1 = abs(100.0 - 10.0) / (100.0 + 10.0)
    
    print(f"测试用例1: 高不平衡度")
    print(f"买盘量: 100.0, 卖盘量: 10.0")
    print(f"期望不平衡度: {expected1:.4f}")
    print(f"实际不平衡度: {imbalance1:.4f}")
    
    if abs(imbalance1 - expected1) < 0.01 and imbalance1 > 0.8:
        print("✅ 高不平衡度计算正确")
        test1_passed = True
    else:
        print(f"❌ 高不平衡度计算错误")
        test1_passed = False
    
    # 测试用例2: 低不平衡度
    bids2 = [{'price': 100.0, 'volume': 100.0}]
    asks2 = [{'price': 101.0, 'volume': 95.0}]
    imbalance2 = widget._calculate_order_flow_imbalance(bids2, asks2)
    expected2 = abs(100.0 - 95.0) / (100.0 + 95.0)
    
    print(f"\n测试用例2: 低不平衡度")
    print(f"买盘量: 100.0, 卖盘量: 95.0")
    print(f"期望不平衡度: {expected2:.4f}")
    print(f"实际不平衡度: {imbalance2:.4f}")
    
    if abs(imbalance2 - expected2) < 0.01 and imbalance2 < 0.1:
        print("✅ 低不平衡度计算正确")
        test2_passed = True
    else:
        print(f"❌ 低不平衡度计算错误")
        test2_passed = False
    
    # 测试用例3: 完全平衡
    bids3 = [{'price': 100.0, 'volume': 100.0}]
    asks3 = [{'price': 101.0, 'volume': 100.0}]
    imbalance3 = widget._calculate_order_flow_imbalance(bids3, asks3)
    expected3 = 0.0
    
    print(f"\n测试用例3: 完全平衡")
    print(f"买盘量: 100.0, 卖盘量: 100.0")
    print(f"期望不平衡度: {expected3:.4f}")
    print(f"实际不平衡度: {imbalance3:.4f}")
    
    if abs(imbalance3 - expected3) < 0.01:
        print("✅ 完全平衡计算正确")
        test3_passed = True
    else:
        print(f"❌ 完全平衡计算错误")
        test3_passed = False
    
    return test1_passed and test2_passed and test3_passed


def test_edge_cases():
    """测试边界情况"""
    print("\n" + "="*60)
    print("测试5: 边界情况")
    print("="*60)
    
    # 创建OrderBookWidget实例
    app = QApplication(sys.argv)
    event_bus = EventBus()
    widget = OrderBookWidget(event_bus=event_bus)
    
    # 测试用例1: 空数据
    empty_bids = []
    empty_asks = []
    
    vwap_empty = widget._calculate_vwap(empty_bids, empty_asks)
    twap_empty = widget._calculate_twap()
    pressure_empty = widget._calculate_buy_sell_pressure(empty_bids, empty_asks)
    imbalance_empty = widget._calculate_order_flow_imbalance(empty_bids, empty_asks)
    
    print(f"测试用例1: 空数据")
    print(f"VWAP: {vwap_empty:.4f}")
    print(f"TWAP: {twap_empty:.4f}")
    print(f"买卖压力指数: {pressure_empty:.4f}")
    print(f"订单流不平衡度: {imbalance_empty:.4f}")
    
    if (vwap_empty == 0.0 and twap_empty == 0.0 and 
        pressure_empty == 0.0 and imbalance_empty == 0.0):
        print("✅ 空数据处理正确")
        test1_passed = True
    else:
        print("❌ 空数据处理错误")
        test1_passed = False
    
    # 测试用例2: 零成交量
    zero_bids = [{'price': 100.0, 'volume': 0.0}]
    zero_asks = [{'price': 101.0, 'volume': 0.0}]
    
    vwap_zero = widget._calculate_vwap(zero_bids, zero_asks)
    pressure_zero = widget._calculate_buy_sell_pressure(zero_bids, zero_asks)
    imbalance_zero = widget._calculate_order_flow_imbalance(zero_bids, zero_asks)
    
    print(f"\n测试用例2: 零成交量")
    print(f"VWAP: {vwap_zero:.4f}")
    print(f"买卖压力指数: {pressure_zero:.4f}")
    print(f"订单流不平衡度: {imbalance_zero:.4f}")
    
    if vwap_zero == 0.0 and pressure_zero == 0.0 and imbalance_zero == 0.0:
        print("✅ 零成交量处理正确")
        test2_passed = True
    else:
        print("❌ 零成交量处理错误")
        test2_passed = False
    
    return test1_passed and test2_passed


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("订单簿新指标测试")
    print("="*60)
    
    # 运行所有测试
    results = []
    
    results.append(("VWAP计算", test_vwap_calculation()))
    results.append(("TWAP计算", test_twap_calculation()))
    results.append(("买卖压力指数计算", test_buy_sell_pressure_calculation()))
    results.append(("订单流不平衡度计算", test_order_flow_imbalance_calculation()))
    results.append(("边界情况处理", test_edge_cases()))
    
    # 打印测试结果汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
    
    # 计算通过率
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    pass_rate = (passed_count / total_count) * 100
    
    print(f"\n通过率: {pass_rate:.1f}% ({passed_count}/{total_count})")
    
    if passed_count == total_count:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
