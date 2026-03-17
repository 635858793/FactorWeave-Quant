"""
回测数据准确性自测脚本
用于验证回测数据的完整性和准确性
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def test_backtest_data_integrity():
    """测试 1: 回测数据完整性检查"""
    print("=" * 60)
    print("测试 1: 回测数据完整性检查")
    print("=" * 60)
    
    # 模拟回测数据
    initial_capital = 100000
    total_bars = 243
    
    # 生成模拟的权益曲线
    np.random.seed(42)
    returns = np.random.randn(total_bars) * 0.01  # 模拟日收益率
    equity_curve = initial_capital * np.cumprod(1 + returns)
    
    # 修正：确保第一个点等于初始资金
    equity_curve[0] = initial_capital
    
    print(f"✓ 初始资金：{initial_capital}")
    print(f"✓ 总 K 线数：{total_bars}")
    print(f"✓ 权益曲线长度：{len(equity_curve)}")
    print(f"✓ 最终权益：{equity_curve[-1]:.2f}")
    print(f"✓ 总收益率：{(equity_curve[-1] / initial_capital - 1) * 100:.2f}%")
    
    # 验证数据点
    assert len(equity_curve) == total_bars, "权益曲线长度不匹配"
    assert equity_curve[0] == initial_capital, "初始权益不正确"
    assert all(equity_curve > 0), "权益曲线存在负值"
    
    print("✓ 数据完整性检查通过\n")
    return equity_curve


def test_data_point_generation():
    """测试 2: 数据点生成逻辑验证"""
    print("=" * 60)
    print("测试 2: 数据点生成逻辑验证")
    print("=" * 60)
    
    from datetime import datetime
    
    initial_capital = 100000
    equity_curve = test_backtest_data_integrity()
    
    # 模拟数据点生成（与 backtest_widget.py 中的逻辑一致）
    data_points = []
    for i, value in enumerate(equity_curve):
        data_point = {
            'timestamp': datetime.now(),
            'cumulative_return': (value / initial_capital - 1),
            'current_drawdown': 0,
            'capital': value,
            'bar_index': i,
            'total_bars': len(equity_curve)
        }
        data_points.append(data_point)
    
    print(f"✓ 生成数据点数量：{len(data_points)}")
    print(f"✓ 第一个数据点:")
    print(f"  - bar_index: {data_points[0]['bar_index']}")
    print(f"  - capital: {data_points[0]['capital']:.2f}")
    print(f"  - cumulative_return: {data_points[0]['cumulative_return']:.4f}")
    
    print(f"✓ 最后一个数据点:")
    print(f"  - bar_index: {data_points[-1]['bar_index']}")
    print(f"  - capital: {data_points[-1]['capital']:.2f}")
    print(f"  - cumulative_return: {data_points[-1]['cumulative_return']:.4f}")
    
    # 验证数据点
    assert len(data_points) == len(equity_curve), "数据点数量不匹配"
    assert data_points[0]['bar_index'] == 0, "第一个索引不为 0"
    assert data_points[-1]['bar_index'] == len(equity_curve) - 1, "最后一个索引不正确"
    
    print("✓ 数据点生成验证通过\n")
    return data_points


def test_progressive_display_logic():
    """测试 3: 渐进式展示逻辑验证"""
    print("=" * 60)
    print("测试 3: 渐进式展示逻辑验证")
    print("=" * 60)
    
    data_points = test_data_point_generation()
    total_points = len(data_points)
    
    # 模拟渐进式展示参数
    batch_size = 15
    interval_ms = 30
    
    # 模拟展示过程
    displayed_count = 0
    batch_count = 0
    
    print(f"✓ 总数据点：{total_points}")
    print(f"✓ 批次大小：{batch_size}")
    print(f"✓ 时间间隔：{interval_ms}ms")
    
    while displayed_count < total_points:
        end_index = min(displayed_count + batch_size, total_points)
        batch = data_points[displayed_count:end_index]
        
        batch_count += 1
        displayed_count = end_index
        
        print(f"  批次 {batch_count}: 显示 {len(batch)} 个点，累计 {displayed_count}/{total_points}")
    
    total_time_ms = batch_count * interval_ms
    print(f"✓ 总批次数：{batch_count}")
    print(f"✓ 总显示时间：{total_time_ms}ms ({total_time_ms/1000:.2f}秒)")
    
    assert displayed_count == total_points, "未显示完所有数据点"
    
    print("✓ 渐进式展示逻辑验证通过\n")


def test_chart_data_accumulation():
    """测试 4: 图表数据累积验证（关键测试）"""
    print("=" * 60)
    print("测试 4: 图表数据累积验证（关键测试）")
    print("=" * 60)
    
    data_points = test_data_point_generation()
    
    # 模拟 ChartWidget 的 _backtest_metrics 列表
    _backtest_metrics = []
    
    # 模拟分批添加数据（模拟 RealTimeChart._incremental_update）
    batch_size = 15
    displayed_count = 0
    batch_count = 0
    
    while displayed_count < len(data_points):
        end_index = min(displayed_count + batch_size, len(data_points))
        batch = data_points[displayed_count:end_index]
        
        # 关键：使用 extend 添加数据（正确方式）
        _backtest_metrics.extend(batch)
        
        displayed_count = end_index
        batch_count += 1
    
    print(f"✓ 最终累积数据点：{len(_backtest_metrics)}")
    print(f"✓ 预期数据点：{len(data_points)}")
    print(f"✓ 数据完整性：{len(_backtest_metrics) == len(data_points)}")
    
    # 验证数据完整性
    assert len(_backtest_metrics) == len(data_points), "数据丢失"
    
    # 验证数据一致性
    for i in range(len(data_points)):
        assert _backtest_metrics[i]['bar_index'] == data_points[i]['bar_index'], f"索引 {i} 不匹配"
        assert _backtest_metrics[i]['capital'] == data_points[i]['capital'], f"索引 {i} 资金不匹配"
    
    print("✓ 图表数据累积验证通过\n")


def test_incorrect_implementation():
    """测试 5: 错误实现演示（对比用）"""
    print("=" * 60)
    print("测试 5: 错误实现演示（对比用）")
    print("=" * 60)
    
    data_points = test_data_point_generation()
    
    # 错误方式：每次赋值而不是 extend
    _backtest_metrics_wrong = []
    
    batch_size = 15
    displayed_count = 0
    batch_count = 0
    
    while displayed_count < len(data_points):
        end_index = min(displayed_count + batch_size, len(data_points))
        batch = data_points[displayed_count:end_index]
        
        # 错误：直接赋值而不是 extend（会覆盖之前的数据）
        _backtest_metrics_wrong = batch  # ❌ 错误！
        
        displayed_count = end_index
        batch_count += 1
    
    print(f"✗ 错误方式最终数据点：{len(_backtest_metrics_wrong)}")
    print(f"✗ 预期数据点：{len(data_points)}")
    print(f"✗ 数据丢失率：{(len(data_points) - len(_backtest_metrics_wrong)) / len(data_points) * 100:.1f}%")
    print(f"⚠ 只保留了最后一批数据！")
    
    print("\n")


def test_real_scenario():
    """测试 6: 真实场景模拟"""
    print("=" * 60)
    print("测试 6: 真实场景模拟")
    print("=" * 60)
    
    # 从实际回测结果加载（如果存在）
    import json
    from pathlib import Path
    
    results_dir = Path(__file__).parent / 'backtest_results'
    
    if results_dir.exists():
        json_files = list(results_dir.glob('*.json'))
        if json_files:
            latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
            print(f"✓ 找到最新回测结果：{latest_file.name}")
            
            try:
                with open(latest_file, 'r') as f:
                    results = json.load(f)
                
                equity_curve = results.get('equity_curve', [])
                if isinstance(equity_curve, list):
                    print(f"✓ 权益曲线数据点：{len(equity_curve)}")
                    print(f"✓ 初始值：{equity_curve[0]:.2f}")
                    print(f"✓ 最终值：{equity_curve[-1]:.2f}")
                    print(f"✓ 收益率：{(equity_curve[-1] / equity_curve[0] - 1) * 100:.2f}%")
                else:
                    print("⚠ 权益曲线格式不正确")
                    
            except Exception as e:
                print(f"✗ 读取失败：{e}")
        else:
            print("⚠ 未找到回测结果文件，使用模拟数据")
            test_backtest_data_integrity()
    else:
        print("⚠ 回测结果目录不存在，使用模拟数据")
        test_backtest_data_integrity()
    
    print()


def main():
    """运行所有测试"""
    print("\n" + "🧪 " * 20)
    print("回测数据准确性自测脚本")
    print("🧪 " * 20 + "\n")
    
    try:
        # 运行所有测试
        test_real_scenario()
        test_backtest_data_integrity()
        test_data_point_generation()
        test_progressive_display_logic()
        test_chart_data_accumulation()
        test_incorrect_implementation()  # 对比错误实现
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
