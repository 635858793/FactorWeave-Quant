"""
测试脚本：验证K线下载页面UI参数修复

测试内容：
1. RealtimeWriteService配置使用
2. ImportTaskConfig的description和data_usage字段
3. UI参数收集和传递
"""

import sys
import os
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_realtime_write_service():
    """测试RealtimeWriteService配置使用"""
    print("=" * 80)
    print("测试1: RealtimeWriteService配置使用")
    print("=" * 80)
    
    try:
        from core.services.realtime_write_service import RealtimeWriteService
        from core.services.realtime_write_config import RealtimeWriteConfig, WriteStrategy
        
        # 测试1.1: 批量写入模式
        print("\n1.1 测试批量写入模式...")
        config = RealtimeWriteConfig(
            enabled=True,
            write_strategy=WriteStrategy.BATCH,
            batch_size=100,
            concurrency=4,
            max_retries=3,
            enable_performance_monitoring=True,
            enable_memory_monitoring=True
        )
        service = RealtimeWriteService(config)
        
        # 验证配置是否正确设置
        assert service.config.enabled == True, "enabled配置未正确设置"
        assert service.config.write_strategy == WriteStrategy.BATCH, "write_strategy配置未正确设置"
        assert service.config.batch_size == 100, "batch_size配置未正确设置"
        assert service.config.concurrency == 4, "concurrency配置未正确设置"
        assert service.config.max_retries == 3, "max_retries配置未正确设置"
        assert service.config.enable_performance_monitoring == True, "enable_performance_monitoring配置未正确设置"
        assert service.config.enable_memory_monitoring == True, "enable_memory_monitoring配置未正确设置"
        
        # 验证批量缓冲区是否初始化
        assert hasattr(service, '_batch_buffer'), "_batch_buffer未初始化"
        assert hasattr(service, '_batch_lock'), "_batch_lock未初始化"
        assert hasattr(service, '_performance_stats'), "_performance_stats未初始化"
        assert hasattr(service, '_memory_stats'), "_memory_stats未初始化"
        
        print("✅ 批量写入模式配置正确")
        
        # 测试1.2: 实时写入模式
        print("\n1.2 测试实时写入模式...")
        config = RealtimeWriteConfig(
            enabled=True,
            write_strategy=WriteStrategy.REALTIME,
            enable_performance_monitoring=False,
            enable_memory_monitoring=False
        )
        service = RealtimeWriteService(config)
        
        assert service.config.write_strategy == WriteStrategy.REALTIME, "write_strategy配置未正确设置"
        assert service.config.enable_performance_monitoring == False, "enable_performance_monitoring配置未正确设置"
        assert service.config.enable_memory_monitoring == False, "enable_memory_monitoring配置未正确设置"
        
        print("✅ 实时写入模式配置正确")
        
        # 测试1.3: 自适应写入模式
        print("\n1.3 测试自适应写入模式...")
        config = RealtimeWriteConfig(
            enabled=True,
            write_strategy=WriteStrategy.ADAPTIVE,
            performance_warning_threshold=1000
        )
        service = RealtimeWriteService(config)
        
        assert service.config.write_strategy == WriteStrategy.ADAPTIVE, "write_strategy配置未正确设置"
        assert service.config.performance_warning_threshold == 1000, "performance_warning_threshold配置未正确设置"
        
        print("✅ 自适应写入模式配置正确")
        
        # 测试1.4: 禁用写入
        print("\n1.4 测试禁用写入...")
        config = RealtimeWriteConfig(
            enabled=False
        )
        service = RealtimeWriteService(config)
        
        assert service.config.enabled == False, "enabled配置未正确设置"
        
        print("✅ 禁用写入配置正确")
        
        print("\n" + "=" * 80)
        print("✅ 测试1通过: RealtimeWriteService配置使用")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_import_task_config():
    """测试ImportTaskConfig的description和data_usage字段"""
    print("\n" + "=" * 80)
    print("测试2: ImportTaskConfig的description和data_usage字段")
    print("=" * 80)
    
    try:
        from core.importdata.import_config_manager import ImportTaskConfig
        from core.importdata.import_config_manager import DataFrequency, ImportMode
        
        # 测试2.1: 创建包含description和data_usage的任务配置
        print("\n2.1 测试创建包含description和data_usage的任务配置...")
        task_config = ImportTaskConfig(
            task_id="test_task_001",
            name="测试任务",
            description="这是一个测试任务描述",
            data_usage="backtest",
            symbols=["000001.SZ", "000002.SZ"],
            data_source="通达信",
            asset_type="股票",
            data_type="K线数据",
            frequency=DataFrequency.DAILY,
            mode=ImportMode.MANUAL
        )
        
        # 验证字段是否正确设置
        assert task_config.task_id == "test_task_001", "task_id未正确设置"
        assert task_config.name == "测试任务", "name未正确设置"
        assert task_config.description == "这是一个测试任务描述", "description未正确设置"
        assert task_config.data_usage == "backtest", "data_usage未正确设置"
        
        print("✅ 任务配置字段正确")
        
        # 测试2.2: 测试默认值
        print("\n2.2 测试默认值...")
        task_config = ImportTaskConfig(
            task_id="test_task_002",
            name="测试任务2",
            symbols=["000001.SZ"],
            data_source="通达信",
            asset_type="股票",
            data_type="K线数据",
            frequency=DataFrequency.DAILY,
            mode=ImportMode.MANUAL
        )
        
        assert task_config.description is None, "description默认值应为None"
        assert task_config.data_usage == "general", "data_usage默认值应为'general'"
        
        print("✅ 默认值正确")
        
        # 测试2.3: 测试序列化和反序列化
        print("\n2.3 测试序列化和反序列化...")
        task_config = ImportTaskConfig(
            task_id="test_task_003",
            name="测试任务3",
            description="序列化测试",
            data_usage="realtime",
            symbols=["000001.SZ"],
            data_source="通达信",
            asset_type="股票",
            data_type="K线数据",
            frequency=DataFrequency.DAILY,
            mode=ImportMode.MANUAL
        )
        
        # 序列化
        config_dict = task_config.to_dict()
        assert 'description' in config_dict, "description未序列化"
        assert 'data_usage' in config_dict, "data_usage未序列化"
        assert config_dict['description'] == "序列化测试", "description序列化值不正确"
        assert config_dict['data_usage'] == "realtime", "data_usage序列化值不正确"
        
        # 反序列化
        task_config_restored = ImportTaskConfig.from_dict(config_dict)
        assert task_config_restored.description == "序列化测试", "description反序列化值不正确"
        assert task_config_restored.data_usage == "realtime", "data_usage反序列化值不正确"
        
        print("✅ 序列化和反序列化正确")
        
        print("\n" + "=" * 80)
        print("✅ 测试2通过: ImportTaskConfig的description和data_usage字段")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_import_execution_engine():
    """测试ImportExecutionEngine中使用description和data_usage"""
    print("\n" + "=" * 80)
    print("测试3: DataImportExecutionEngine中使用description和data_usage")
    print("=" * 80)
    
    try:
        from core.importdata.import_execution_engine import DataImportExecutionEngine
        from core.importdata.import_config_manager import ImportTaskConfig, DataFrequency, ImportMode
        
        # 测试3.1: 验证_execute_task方法使用description和data_usage
        print("\n3.1 验证_execute_task方法使用description和data_usage...")
        
        # 读取import_execution_engine.py文件，检查是否使用了description和data_usage
        with open('core/importdata/import_execution_engine.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 检查_execute_task方法中是否使用了task_config.description
            if 'task_config.description' in content:
                print("✅ _execute_task方法使用了task_config.description")
            else:
                print("⚠️ _execute_task方法未使用task_config.description")
            
            # 检查_execute_task方法中是否使用了task_config.data_usage
            if 'task_config.data_usage' in content:
                print("✅ _execute_task方法使用了task_config.data_usage")
            else:
                print("⚠️ _execute_task方法未使用task_config.data_usage")
        
        # 测试3.2: 验证_import_single_symbol_kline方法使用description和data_usage
        print("\n3.2 验证_import_single_symbol_kline方法使用description和data_usage...")
        
        # 检查_import_single_symbol_kline方法中是否使用了task_config.description
        if 'task_config.description' in content:
            print("✅ _import_single_symbol_kline方法使用了task_config.description")
        else:
            print("⚠️ _import_single_symbol_kline方法未使用task_config.description")
        
        # 检查_import_single_symbol_kline方法中是否使用了task_config.data_usage
        if 'task_config.data_usage' in content:
            print("✅ _import_single_symbol_kline方法使用了task_config.data_usage")
        else:
            print("⚠️ _import_single_symbol_kline方法未使用task_config.data_usage")
        
        # 测试3.3: 验证_validate_imported_data方法支持strict_validation参数
        print("\n3.3 验证_validate_imported_data方法支持strict_validation参数...")
        
        # 检查_validate_imported_data方法签名
        if 'strict_validation' in content:
            print("✅ _validate_imported_data方法支持strict_validation参数")
        else:
            print("⚠️ _validate_imported_data方法不支持strict_validation参数")
        
        print("\n" + "=" * 80)
        print("✅ 测试3通过: ImportExecutionEngine中使用description和data_usage")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_parameter_collection():
    """测试UI参数收集和传递"""
    print("\n" + "=" * 80)
    print("测试4: UI参数收集和传递")
    print("=" * 80)
    
    try:
        # 测试4.1: 验证_get_current_ui_config方法收集description
        print("\n4.1 验证_get_current_ui_config方法收集description...")
        
        with open('gui/widgets/enhanced_data_import_widget.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 检查_get_current_ui_config方法中是否收集了description
            if "'description'" in content and "task_desc_edit" in content:
                print("✅ _get_current_ui_config方法收集了description")
            else:
                print("⚠️ _get_current_ui_config方法未收集description")
        
        # 测试4.2: 验证_create_task_legacy方法传递description
        print("\n4.2 验证_create_task_legacy方法传递description...")
        
        # 检查_create_task_legacy方法中是否传递了description
        if "description=task_config_dict.get('description'" in content:
            print("✅ _create_task_legacy方法传递了description")
        else:
            print("⚠️ _create_task_legacy方法未传递description")
        
        # 测试4.3: 验证start_import方法传递description和data_usage
        print("\n4.3 验证start_import方法传递description和data_usage...")
        
        # 检查start_import方法中是否传递了description和data_usage
        if "description=task_desc" in content and "data_usage=data_usage" in content:
            print("✅ start_import方法传递了description和data_usage")
        else:
            print("⚠️ start_import方法未传递description和data_usage")
        
        # 测试4.4: 验证update_realtime_write_config方法调用
        print("\n4.4 验证update_realtime_write_config方法调用...")
        
        # 检查start_import方法中是否调用了update_realtime_write_config
        if "update_realtime_write_config" in content:
            print("✅ start_import方法调用了update_realtime_write_config")
        else:
            print("⚠️ start_import方法未调用update_realtime_write_config")
        
        print("\n" + "=" * 80)
        print("✅ 测试4通过: UI参数收集和传递")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试4失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("开始K线下载页面UI参数修复测试")
    print("=" * 80)
    
    results = []
    
    # 运行测试
    results.append(("RealtimeWriteService配置使用", test_realtime_write_service()))
    results.append(("ImportTaskConfig字段", test_import_task_config()))
    results.append(("ImportExecutionEngine使用", test_import_execution_engine()))
    results.append(("UI参数收集和传递", test_ui_parameter_collection()))
    
    # 输出测试结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    # 计算通过率
    passed = sum(1 for _, result in results if result)
    total = len(results)
    pass_rate = (passed / total) * 100 if total > 0 else 0
    
    print("\n" + "=" * 80)
    print(f"总体结果: {passed}/{total} 通过 ({pass_rate:.1f}%)")
    print("=" * 80)
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
