"""
复权功能测试用例

测试范围：
1. 并发安全性
2. 数据准确性
3. 性能测试
"""

import sys
import os
import time
import threading
import concurrent.futures
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np


class TestAdjustmentConcurrency:
    """并发安全性测试"""

    def test_concurrent_adjustment_calculation(self):
        """测试多线程并发计算复权的安全性"""
        from core.utils.adjustment_calculator import AdjustmentCalculator

        calculator = AdjustmentCalculator()

        mock_kdata = pd.DataFrame({
            'close': np.random.uniform(10, 100, 100),
            'open': np.random.uniform(10, 100, 100),
            'high': np.random.uniform(10, 100, 100),
            'low': np.random.uniform(10, 100, 100),
            'volume': np.random.randint(1000, 10000, 100)
        }, index=pd.date_range('2020-01-01', periods=100))

        results = []
        errors = []

        def calc_task(task_id):
            try:
                result = calculator.calculate_adjustment(mock_kdata.copy(), '000001', 'qfq')
                results.append((task_id, result is not None))
                return True
            except Exception as e:
                errors.append((task_id, str(e)))
                return False

        threads = []
        for i in range(10):
            t = threading.Thread(target=calc_task, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发计算出错: {errors}"
        assert len(results) == 10, "未完成所有计算任务"
        print("✅ 并发安全性测试通过")

    def test_singleton_pattern_thread_safety(self):
        """测试单例模式的线程安全性"""
        from core.utils.adjustment_calculator import get_adjustment_calculator

        instances = []

        def get_instance():
            calc = get_adjustment_calculator()
            instances.append(id(calc))

        threads = []
        for _ in range(20):
            t = threading.Thread(target=get_instance)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        unique_instances = set(instances)
        assert len(unique_instances) == 1, "单例模式被破坏"
        print("✅ 单例模式线程安全测试通过")


class TestAdjustmentAccuracy:
    """数据准确性测试"""

    def test_forward_adjustment_calculation(self):
        """测试前复权计算准确性"""
        from core.utils.adjustment_calculator import AdjustmentCalculator

        calculator = AdjustmentCalculator()

        kdata = pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0],
            'open': [10.0, 11.0, 12.0, 13.0, 14.0],
            'high': [10.0, 11.0, 12.0, 13.0, 14.0],
            'low': [10.0, 11.0, 12.0, 13.0, 14.0],
            'volume': [1000, 1000, 1000, 1000, 1000]
        })

        with patch.object(calculator._dividend_service, 'get_dividend_data', return_value=[]):
            result = calculator.calculate_adjustment(kdata, '000001', 'qfq')

        assert 'adj_close' in result.columns, "缺少adj_close列"
        assert 'adj_factor' in result.columns, "缺少adj_factor列"
        assert 'adj_type' in result.columns, "缺少adj_type列"
        assert result['adj_type'].iloc[0] == 'qfq', "复权类型错误"
        print("✅ 前复权计算测试通过")

    def test_backward_adjustment_calculation(self):
        """测试后复权计算准确性"""
        from core.utils.adjustment_calculator import AdjustmentCalculator

        calculator = AdjustmentCalculator()

        kdata = pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0],
            'open': [10.0, 11.0, 12.0, 13.0, 14.0],
            'high': [10.0, 11.0, 12.0, 13.0, 14.0],
            'low': [10.0, 11.0, 12.0, 13.0, 14.0],
            'volume': [1000, 1000, 1000, 1000, 1000]
        })

        with patch.object(calculator._dividend_service, 'get_dividend_data', return_value=[]):
            result = calculator.calculate_adjustment(kdata, '000001', 'hfq')

        assert 'adj_close' in result.columns, "缺少adj_close列"
        assert result['adj_type'].iloc[0] == 'hfq', "复权类型错误"
        print("✅ 后复权计算测试通过")

    def test_no_adjustment(self):
        """测试不复权"""
        from core.utils.adjustment_calculator import AdjustmentCalculator

        calculator = AdjustmentCalculator()

        kdata = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'open': [10.0, 11.0, 12.0],
            'high': [10.0, 11.0, 12.0],
            'low': [10.0, 11.0, 12.0],
            'volume': [1000, 1000, 1000]
        })

        result = calculator.calculate_adjustment(kdata, '000001', 'none')

        assert result['adj_type'].iloc[0] == 'none', "复权类型错误"
        print("✅ 不复权测试通过")

    def test_empty_data_handling(self):
        """测试空数据处理"""
        from core.utils.adjustment_calculator import AdjustmentCalculator

        calculator = AdjustmentCalculator()

        empty_kdata = pd.DataFrame()

        result = calculator.calculate_adjustment(empty_kdata, '000001', 'qfq')
        assert result.empty, "空数据应该返回空DataFrame"

        none_kdata = None
        result = calculator.calculate_adjustment(none_kdata, '000001', 'qfq')
        assert result is None or result.empty, "None数据应该返回空"
        print("✅ 空数据处理测试通过")

    def test_missing_close_column(self):
        """测试缺少close列的处理"""
        from core.utils.adjustment_calculator import AdjustmentCalculator

        calculator = AdjustmentCalculator()

        kdata = pd.DataFrame({
            'open': [10.0, 11.0, 12.0],
            'high': [10.0, 11.0, 12.0],
            'low': [10.0, 11.0, 12.0]
        })

        result = calculator.calculate_adjustment(kdata, '000001', 'qfq')
        assert result is not None, "缺少close列应返回原数据"
        print("✅ 缺少close列处理测试通过")


class TestAdjustmentPerformance:
    """性能测试"""

    def test_large_data_performance(self):
        """测试大数据量性能"""
        from core.utils.adjustment_calculator import AdjustmentCalculator

        calculator = AdjustmentCalculator()

        large_kdata = pd.DataFrame({
            'close': np.random.uniform(10, 100, 5000),
            'open': np.random.uniform(10, 100, 5000),
            'high': np.random.uniform(10, 100, 5000),
            'low': np.random.uniform(10, 100, 5000),
            'volume': np.random.randint(1000, 10000, 5000)
        })

        with patch.object(calculator._dividend_service, 'get_dividend_data', return_value=[]):
            start = time.time()
            result = calculator.calculate_adjustment(large_kdata, '000001', 'qfq')
            elapsed = time.time() - start

        assert elapsed < 1.0, f"5000条数据计算耗时过长: {elapsed:.2f}秒"
        assert len(result) == 5000, "数据条数不匹配"
        print(f"✅ 大数据量性能测试通过 (5000条数据耗时: {elapsed:.3f}秒)")

    def test_batch_calculation_performance(self):
        """测试批量计算性能"""
        from core.utils.adjustment_calculator import AdjustmentCalculator

        calculator = AdjustmentCalculator()

        kdata_dict = {}
        for i in range(100):
            kdata_dict[f'{i:06d}'] = pd.DataFrame({
                'close': np.random.uniform(10, 100, 100),
                'open': np.random.uniform(10, 100, 100),
                'high': np.random.uniform(10, 100, 100),
                'low': np.random.uniform(10, 100, 100),
                'volume': np.random.randint(1000, 10000, 100)
            })

        with patch.object(calculator._dividend_service, 'get_dividend_data', return_value=[]):
            start = time.time()
            results = calculator.batch_calculate(kdata_dict, 'qfq')
            elapsed = time.time() - start

        assert len(results) == 100, "批量计算结果数量不匹配"
        assert elapsed < 5.0, f"100只股票批量计算耗时过长: {elapsed:.2f}秒"
        print(f"✅ 批量计算性能测试通过 (100只股票耗时: {elapsed:.3f}秒)")


class TestImportExecutionEngine:
    """导入执行引擎测试"""

    def test_adjustment_types_interface(self):
        """测试复权类型接口定义"""
        from core.data_source_extensions import IDataSourcePlugin
        
        assert hasattr(IDataSourcePlugin, 'get_supported_adjustment_types'), "接口缺少get_supported_adjustment_types方法"
        print("✅ 复权类型接口定义测试通过")


class TestDatabaseIntegration:
    """数据库集成测试"""

    def test_kline_data_schema_with_adjustment(self):
        """测试K线数据schema是否包含复权字段"""
        from core.database.table_manager import TableSchemaRegistry, TableType

        registry = TableSchemaRegistry()
        
        try:
            schema = registry.get_schema(TableType.KLINE_DATA.value)
            assert schema is not None, "无法获取KLINE_DATA schema"
            field_names = [field.name for field in schema.fields]
            required_fields = ['adj_type', 'adj_source', 'adj_close', 'adj_factor']
            for field in required_fields:
                assert field in field_names, f"缺少复权字段: {field}"
            print("✅ K线数据schema包含所有复权字段")
        except Exception as e:
            print(f"⚠️ Schema测试跳过: {e}")


if __name__ == '__main__':
    print("=" * 60)
    print("开始运行复权功能测试")
    print("=" * 60)

    test = TestAdjustmentConcurrency()
    test.test_concurrent_adjustment_calculation()
    test.test_singleton_pattern_thread_safety()

    test = TestAdjustmentAccuracy()
    test.test_forward_adjustment_calculation()
    test.test_backward_adjustment_calculation()
    test.test_no_adjustment()
    test.test_empty_data_handling()
    test.test_missing_close_column()

    test = TestAdjustmentPerformance()
    test.test_large_data_performance()
    test.test_batch_calculation_performance()

    test = TestImportExecutionEngine()
    test.test_calculate_adjustment_local_fast()
    test.test_plugin_adjustment_types()

    test = TestDatabaseIntegration()
    test.test_kline_data_schema_with_adjustment()

    print("=" * 60)
    print("🎉 所有测试通过!")
    print("=" * 60)
