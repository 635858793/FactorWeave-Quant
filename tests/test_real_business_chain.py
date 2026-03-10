#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实业务调用链性能验证测试
深度分析系统框架与功能结合业务调用链
"""

import sys
sys.path.insert(0, '.')

import time
import threading
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import MagicMock, patch
import json


def test_p0_1_real_business_chain():
    """P0-1 真实业务调用链验证：持仓同步机制"""
    print('=' * 70)
    print('P0-1: 真实业务调用链性能验证 - 持仓同步机制')
    print('=' * 70)
    print('\n业务调用链分析:')
    print('  1. 账户创建 → 2. 持仓更新事件触发 → 3. 调度同步任务 → 4. 执行同步 → 5. 更新内存')
    print()
    
    try:
        from core.trading.account_manager import AccountManager
        from core.containers import ServiceContainer
        from core.events import EventBus, Event, EventType
        
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False)
        
        manager = AccountManager.__new__(AccountManager)
        manager.service_container = service_container
        manager.event_bus = event_bus
        manager._accounts = {}
        manager._positions = {}
        manager._fund_infos = {}
        manager._account_lock = threading.RLock()
        manager._position_lock = threading.RLock()
        manager._fund_info_lock = threading.RLock()
        manager._last_sync_times = {}
        manager._sync_lock = threading.Lock()
        manager._min_sync_interval = 5
        manager._pending_sync_accounts = set()
        manager._sync_timer = None
        manager._realtime_sync_enabled = False
        manager.repository = MagicMock()
        manager.sync_account_positions = MagicMock()
        
        manager._setup_position_sync_handlers()
        
        print('【测试1】单账户持仓同步调用链性能')
        iterations = 1000
        start_time = time.perf_counter()
        
        for i in range(iterations):
            manager._schedule_position_sync('account_test_001')
        
        elapsed = time.perf_counter() - start_time
        avg_time = (elapsed / iterations) * 1000
        
        print(f'  - 执行 {iterations} 次同步调度')
        print(f'  - 总耗时: {elapsed:.4f}秒')
        print(f'  - 平均耗时: {avg_time:.4f}ms/次')
        print(f'  - 吞吐量: {iterations/elapsed:.0f}次/秒')
        
        status = '✅ 通过' if avg_time < 1.0 else '❌ 需优化'
        print(f'  - 状态: {status}')
        print()
        
        print('【测试2】多账户并发持仓同步调用链性能')
        account_ids = [f'account_{i}' for i in range(10)]
        iterations = 500
        
        start_time = time.perf_counter()
        
        for i in range(iterations):
            for account_id in account_ids:
                manager._schedule_position_sync(account_id)
        
        total_ops = iterations * len(account_ids)
        elapsed = time.perf_counter() - start_time
        avg_time = (elapsed / total_ops) * 1000
        
        print(f'  - 账户数: {len(account_ids)}')
        print(f'  - 总操作数: {total_ops}')
        print(f'  - 总耗时: {elapsed:.4f}秒')
        print(f'  - 平均耗时: {avg_time:.4f}ms/次')
        print(f'  - 吞吐量: {total_ops/elapsed:.0f}次/秒')
        
        status = '✅ 通过' if avg_time < 1.0 else '❌ 需优化'
        print(f'  - 状态: {status}')
        print()
        
        print('【测试3】节流机制验证')
        manager._last_sync_times['account_throttle'] = time.time() - 1
        
        start_time = time.perf_counter()
        
        for i in range(100):
            manager._schedule_position_sync('account_throttle')
        
        elapsed = time.perf_counter() - start_time
        
        print(f'  - 100次节流请求执行耗时: {elapsed:.4f}秒')
        print(f'  - 预期: 由于节流机制，应几乎无开销')
        
        status = '✅ 通过' if elapsed < 0.1 else '❌ 节流失效'
        print(f'  - 状态: {status}')
        print()
        
        return avg_time
        
    except Exception as e:
        print(f'❌ 测试失败: {e}')
        import traceback
        traceback.print_exc()
        return None


def test_p0_2_real_business_chain():
    """P0-2 真实业务调用链验证：风控检查响应"""
    print('=' * 70)
    print('P0-2: 真实业务调用链性能验证 - 风控检查响应')
    print('=' * 70)
    print('\n业务调用链分析:')
    print('  1. 策略生成信号 → 2. 创建订单 → 3. 风控预检查 → 4. 通过/拦截 → 5. 成交执行')
    print()
    
    try:
        from core.trading.order_executor import OrderExecutor
        from core.trading.order_models import Order, OrderType, OrderStatus, OrderCategory
        from core.plugin_types import AssetType
        
        executor = OrderExecutor.__new__(OrderExecutor)
        executor.service_container = MagicMock()
        executor.event_bus = MagicMock()
        
        order = Order(
            order_id='TEST_001',
            strategy_id='test_strategy',
            asset_type=AssetType.STOCK_A,
            stock_code='600000',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id='default'
        )
        
        print('【测试1】单次风控检查调用链性能')
        iterations = 5000
        start_time = time.perf_counter()
        
        for i in range(iterations):
            result = executor._pre_trade_risk_check(order)
        
        elapsed = time.perf_counter() - start_time
        avg_time = (elapsed / iterations) * 1000
        
        print(f'  - 执行 {iterations} 次风控检查')
        print(f'  - 总耗时: {elapsed:.4f}秒')
        print(f'  - 平均耗时: {avg_time:.4f}ms/次')
        print(f'  - 吞吐量: {iterations/elapsed:.0f}次/秒')
        
        status = '✅ 通过' if avg_time < 1.0 else '❌ 需优化'
        print(f'  - 状态: {status}')
        print()
        
        print('【测试2】批量订单风控检查调用链性能')
        orders = []
        for i in range(100):
            o = Order(
                order_id=f'BATCH_{i}',
                strategy_id='batch_strategy',
                asset_type=AssetType.STOCK_A,
                stock_code=f'{600000 + i}',
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i * 0.1,
                order_quantity=100 + i * 10,
                order_status=OrderStatus.PENDING,
                create_time=datetime.now(),
                update_time=datetime.now(),
                account_id='default'
            )
            orders.append(o)
        
        start_time = time.perf_counter()
        
        for order in orders:
            for _ in range(50):
                result = executor._pre_trade_risk_check(order)
        
        total_ops = len(orders) * 50
        elapsed = time.perf_counter() - start_time
        avg_time = (elapsed / total_ops) * 1000
        
        print(f'  - 订单数: {len(orders)}')
        print(f'  - 每订单检查次数: 50')
        print(f'  - 总操作数: {total_ops}')
        print(f'  - 总耗时: {elapsed:.4f}秒')
        print(f'  - 平均耗时: {avg_time:.4f}ms/次')
        
        status = '✅ 通过' if avg_time < 1.0 else '❌ 需优化'
        print(f'  - 状态: {status}')
        print()
        
        print('【测试3】风控模块导入开销验证')
        import importlib
        
        start_time = time.perf_counter()
        
        for i in range(100):
            try:
                from core.risk_monitoring.enhanced_risk_monitor import EnhancedRiskMonitor
            except ImportError:
                pass
        
        elapsed = time.perf_counter() - start_time
        
        print(f'  - 100次模块导入耗时: {elapsed:.4f}秒')
        print(f'  - 说明: 首次导入有开销，后续应被缓存')
        
        print()
        
        return avg_time
        
    except Exception as e:
        print(f'❌ 测试失败: {e}')
        import traceback
        traceback.print_exc()
        return None


def test_p0_3_real_business_chain():
    """P0-3 真实业务调用链验证：VWAP成交模型"""
    print('=' * 70)
    print('P0-3: 真实业务调用链性能验证 - VWAP成交模型')
    print('=' * 70)
    print('\n业务调用链分析:')
    print('  1. 回测初始化 → 2. 加载K线数据 → 3. 信号生成 → 4. VWAP价格计算 → 5. 成交记录')
    print()
    
    try:
        from backtest.unified_backtest_engine import UnifiedBacktestEngine
        
        engine = UnifiedBacktestEngine()
        
        print('【测试1】完整回测调用链性能（VWAP模型）')
        
        for size in [1000, 5000, 10000]:
            dates = pd.date_range('2024-01-01', periods=size, freq='min')
            data = pd.DataFrame({
                'open': np.random.uniform(9.5, 10.5, size),
                'close': np.random.uniform(9.5, 10.5, size),
                'high': np.random.uniform(10.0, 10.8, size),
                'low': np.random.uniform(9.2, 10.0, size),
                'volume': np.random.randint(100000, 1000000, size),
                'signal': np.random.choice([1, 0, -1], size, p=[0.1, 0.8, 0.1])
            }, index=dates)
            
            start_time = time.perf_counter()
            
            result = engine.run_backtest(
                data=data,
                signal_col='signal',
                price_col='close',
                initial_capital=100000,
                execution_model='vwap'
            )
            
            elapsed = time.perf_counter() - start_time
            throughput = size / elapsed
            
            print(f'  - 数据量: {size:>5}条')
            print(f'  - 耗时: {elapsed:.4f}秒')
            print(f'  - 吞吐量: {throughput:.0f}条/秒')
            
            status = '✅ 通过' if throughput > 1000 else '❌ 需优化'
            print(f'  - 状态: {status}')
            print()
        
        print('【测试2】VWAP价格计算函数独立性能')
        
        dates = pd.date_range('2024-01-01', periods=1000, freq='D')
        data = pd.DataFrame({
            'close': [10.0 + i * 0.01 for i in range(1000)],
            'high': [10.2 + i * 0.01 for i in range(1000)],
            'low': [9.8 + i * 0.01 for i in range(1000)],
            'volume': [1000000] * 1000,
            'signal': [1 if i % 5 == 0 else (-1 if i % 5 == 3 else 0) for i in range(1000)]
        }, index=dates)
        
        iterations = 50000
        start_time = time.perf_counter()
        
        for i in range(iterations):
            idx = i % 1000
            price = engine._calculate_vwap_price(data, idx, 10.0, True, 0.001)
        
        elapsed = time.perf_counter() - start_time
        avg_time = (elapsed / iterations) * 1000
        
        print(f'  - 执行 {iterations} 次VWAP价格计算')
        print(f'  - 总耗时: {elapsed:.4f}秒')
        print(f'  - 平均耗时: {avg_time:.4f}ms/次')
        print(f'  - 吞吐量: {iterations/elapsed:.0f}次/秒')
        
        status = '✅ 通过' if avg_time < 0.5 else '❌ 需优化'
        print(f'  - 状态: {status}')
        print()
        
        print('【测试3】三种成交模型对比')
        
        models = ['fixed', 'vwap', 'random']
        
        for model in models:
            iterations = 10000
            start_time = time.perf_counter()
            
            for i in range(iterations):
                idx = i % 1000
                if model == 'fixed':
                    price = engine._calculate_execution_price(data, idx, 10.0, True, 0.001)
                elif model == 'vwap':
                    price = engine._calculate_vwap_price(data, idx, 10.0, True, 0.001)
                else:
                    price = engine._calculate_random_price(data, idx, 10.0, True, 0.001)
            
            elapsed = time.perf_counter() - start_time
            avg_time = (elapsed / iterations) * 1000
            
            print(f'  - {model.upper():>6}: {avg_time:.4f}ms/次')
        
        print()
        
        return avg_time
        
    except Exception as e:
        print(f'❌ 测试失败: {e}')
        import traceback
        traceback.print_exc()
        return None


def analyze_system_framework():
    """分析系统框架与业务调用链"""
    print('=' * 70)
    print('系统框架与业务调用链分析')
    print('=' * 70)
    
    print('\n【P0-1 持仓同步机制】')
    print('  调用链: AccountManager → EventBus → _schedule_position_sync')
    print('  关键路径: 事件触发 → 节流判断 → Timer调度 → 同步执行')
    print('  性能要点:')
    print('    - time.time() vs datetime.now(): time.time()快约30%')
    print('    - 节流机制: 避免高频同步请求')
    print('    - Timer对象: 可考虑线程池优化')
    
    print('\n【P0-2 风控检查响应】')
    print('  调用链: OrderExecutor._pre_trade_risk_check → EnhancedRiskMonitor')
    print('  关键路径: 订单创建 → 风控检查 → 规则匹配 → 决策返回')
    print('  性能要点:')
    print('    - 模块导入: try-except保护，失败不影响主流程')
    print('    - 服务解析: 可使用缓存减少解析开销')
    print('    - 规则匹配: 考虑LRU缓存')
    
    print('\n【P0-3 VWAP成交模型】')
    print('  调用链: run_backtest → _calculate_vwap_price → 成交记录')
    print('  关键路径: K线数据 → 信号触发 → VWAP计算 → 价格成交')
    print('  性能要点:')
    print('    - random预导入: 避免循环内导入开销')
    print('    - DataFrame访问: 考虑向量化优化')
    print('    - numpy计算: 可使用numba JIT加速')
    
    print()


def identify_issues_and_optimize():
    """识别问题并优化"""
    print('=' * 70)
    print('问题识别与优化建议')
    print('=' * 70)
    
    issues = [
        {
            'module': 'P0-1',
            'issue': 'Timer对象创建有开销',
            'suggestion': '使用线程池或批量处理',
            'priority': '中'
        },
        {
            'module': 'P0-2',
            'issue': '服务解析可能有重复开销',
            'suggestion': '缓存已解析的服务实例',
            'priority': '低'
        },
        {
            'module': 'P0-3',
            'issue': 'DataFrame.iloc访问有开销',
            'suggestion': '使用numpy数组直接访问',
            'priority': '中'
        }
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f'\n{i}. {issue["module"]} - {issue["issue"]}')
        print(f'   优化建议: {issue["suggestion"]}')
        print(f'   优先级: {issue["priority"]}')
    
    print()


if __name__ == '__main__':
    print('\n' + '=' * 70)
    print('真实业务调用链性能验证测试')
    print('深度分析系统框架与功能结合业务调用链')
    print('=' * 70 + '\n')
    
    analyze_system_framework()
    
    p0_1_result = test_p0_1_real_business_chain()
    p0_2_result = test_p0_2_real_business_chain()
    p0_3_result = test_p0_3_real_business_chain()
    
    identify_issues_and_optimize()
    
    print('=' * 70)
    print('验证总结')
    print('=' * 70)
    print(f'P0-1 持仓同步: {p0_1_result:.4f}ms/次' if p0_1_result else 'P0-1: 测试失败')
    print(f'P0-2 风控检查: {p0_2_result:.4f}ms/次' if p0_2_result else 'P0-2: 测试失败')
    print(f'P0-3 VWAP模型: {p0_3_result:.4f}ms/次' if p0_3_result else 'P0-3: 测试失败')
    print('=' * 70)
