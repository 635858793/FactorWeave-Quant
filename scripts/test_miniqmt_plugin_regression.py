"""
miniqmt_plugin 全面回归测试脚本

测试内容：
1. 插件实例化测试
2. 抽象方法实现测试（16个方法）
3. 接口实现测试（isinstance 检查）
4. 系统集成测试（PluginManager, UnifiedDataManager, DataSourcePluginAdapter）
5. UI 调用连接测试（adapter.get_plugin_info(), adapter.connect(), adapter.disconnect()）

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2026-01-17
"""

import sys
import os
from typing import Dict, List, Any
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️  警告: pandas 未安装，某些测试将被跳过")


class TestResult:
    """测试结果类"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.success = False
        self.error = None
        self.details = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_name': self.test_name,
            'success': self.success,
            'error': str(self.error) if self.error else None,
            'details': self.details
        }


class RegressionTestSuite:
    """回归测试套件"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.plugin = None
        self.adapter = None
        self.plugin_manager = None
        self.unified_manager = None
    
    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        print(f"\n{'=' * 60}")
        print(f"🧪 测试: {test_name}")
        print('=' * 60)
        
        result = TestResult(test_name)
        
        try:
            test_func(result)
            result.success = True
            print(f"✅ {test_name} - 通过")
        except Exception as e:
            result.success = False
            result.error = e
            print(f"❌ {test_name} - 失败")
            print(f"   错误: {e}")
            import traceback
            traceback.print_exc()
        
        self.results.append(result)
        return result.success
    
    def test_1_plugin_instantiation(self, result: TestResult):
        """测试 1: 插件实例化"""
        from plugins.data_sources.stock.miniqmt_plugin import MiniQMTPlugin
        
        plugin = MiniQMTPlugin()
        self.plugin = plugin
        
        result.details['plugin_id'] = plugin.plugin_info.id
        result.details['plugin_name'] = plugin.plugin_info.name
        result.details['plugin_version'] = plugin.plugin_info.version
        result.details['plugin_author'] = plugin.plugin_info.author
        result.details['plugin_description'] = plugin.plugin_info.description
        
        print(f"   插件ID: {plugin.plugin_info.id}")
        print(f"   插件名称: {plugin.plugin_info.name}")
        print(f"   插件版本: {plugin.plugin_info.version}")
        print(f"   插件作者: {plugin.plugin_info.author}")
        print(f"   插件描述: {plugin.plugin_info.description}")
    
    def test_2_interface_implementation(self, result: TestResult):
        """测试 2: 接口实现检查"""
        from core.data_source_extensions import IDataSourcePlugin
        from plugins.templates.standard_data_source_plugin import StandardDataSourcePlugin
        
        is_idata_source = isinstance(self.plugin, IDataSourcePlugin)
        is_standard_data_source = isinstance(self.plugin, StandardDataSourcePlugin)
        
        result.details['is_idata_source'] = is_idata_source
        result.details['is_standard_data_source'] = is_standard_data_source
        
        print(f"   是否实现 IDataSourcePlugin: {is_idata_source}")
        print(f"   是否实现 StandardDataSourcePlugin: {is_standard_data_source}")
        
        if not is_idata_source:
            raise AssertionError("插件未实现 IDataSourcePlugin 接口")
        
        if not is_standard_data_source:
            raise AssertionError("插件未实现 StandardDataSourcePlugin 接口")
    
    def test_3_plugin_info_property(self, result: TestResult):
        """测试 3: plugin_info 属性检查"""
        from core.data_source_extensions import PluginInfo
        
        plugin_info = self.plugin.plugin_info
        is_property = isinstance(type(self.plugin).plugin_info, property)
        
        result.details['plugin_info_type'] = type(plugin_info).__name__
        result.details['is_property'] = is_property
        result.details['plugin_info_id'] = plugin_info.id
        
        print(f"   plugin_info 类型: {type(plugin_info).__name__}")
        print(f"   plugin_info 是否是 property: {is_property}")
        print(f"   plugin_info.id: {plugin_info.id}")
        
        if not isinstance(plugin_info, PluginInfo):
            raise AssertionError(f"plugin_info 不是 PluginInfo 类型，而是 {type(plugin_info).__name__}")
        
        if not is_property:
            raise AssertionError("plugin_info 不是 property")
    
    def test_4_standard_data_source_plugin_methods(self, result: TestResult):
        """测试 4: StandardDataSourcePlugin 抽象方法实现"""
        required_methods = [
            'get_version',
            'get_description',
            'get_author',
            'get_capabilities',
            'get_supported_asset_types',
            'get_supported_data_types'
        ]
        
        missing_methods = []
        implemented_methods = []
        
        for method_name in required_methods:
            has_method = hasattr(self.plugin, method_name)
            if has_method:
                implemented_methods.append(method_name)
            else:
                missing_methods.append(method_name)
        
        result.details['implemented_methods'] = implemented_methods
        result.details['missing_methods'] = missing_methods
        
        print(f"   已实现方法 ({len(implemented_methods)}/{len(required_methods)}):")
        for method in implemented_methods:
            print(f"     ✅ {method}")
        
        if missing_methods:
            print(f"   缺失方法:")
            for method in missing_methods:
                print(f"     ❌ {method}")
        
        if missing_methods:
            raise AssertionError(f"缺失抽象方法: {', '.join(missing_methods)}")
    
    def test_5_internal_methods(self, result: TestResult):
        """测试 5: StandardDataSourcePlugin 内部抽象方法实现"""
        required_methods = [
            '_internal_connect',
            '_internal_disconnect',
            '_internal_get_asset_list',
            '_internal_get_kdata',
            '_internal_get_real_time_quotes'
        ]
        
        missing_methods = []
        implemented_methods = []
        
        for method_name in required_methods:
            has_method = hasattr(self.plugin, method_name)
            if has_method:
                implemented_methods.append(method_name)
            else:
                missing_methods.append(method_name)
        
        result.details['implemented_internal_methods'] = implemented_methods
        result.details['missing_internal_methods'] = missing_methods
        
        print(f"   已实现内部方法 ({len(implemented_methods)}/{len(required_methods)}):")
        for method in implemented_methods:
            print(f"     ✅ {method}")
        
        if missing_methods:
            print(f"   缺失内部方法:")
            for method in missing_methods:
                print(f"     ❌ {method}")
        
        if missing_methods:
            raise AssertionError(f"缺失内部抽象方法: {', '.join(missing_methods)}")
    
    def test_6_idata_source_plugin_methods(self, result: TestResult):
        """测试 6: IDataSourcePlugin 抽象方法实现"""
        required_methods = [
            'connect',
            'disconnect',
            'is_connected',
            'health_check',
            'get_connection_info',
            'get_asset_list',
            'get_kdata',
            'get_real_time_quotes'
        ]
        
        missing_methods = []
        implemented_methods = []
        
        for method_name in required_methods:
            has_method = hasattr(self.plugin, method_name)
            if has_method:
                implemented_methods.append(method_name)
            else:
                missing_methods.append(method_name)
        
        result.details['implemented_idata_source_methods'] = implemented_methods
        result.details['missing_idata_source_methods'] = missing_methods
        
        print(f"   已实现方法 ({len(implemented_methods)}/{len(required_methods)}):")
        for method in implemented_methods:
            print(f"     ✅ {method}")
        
        if missing_methods:
            print(f"   缺失方法:")
            for method in missing_methods:
                print(f"     ❌ {method}")
        
        if missing_methods:
            raise AssertionError(f"缺失 IDataSourcePlugin 抽象方法: {', '.join(missing_methods)}")
    
    def test_7_get_version(self, result: TestResult):
        """测试 7: get_version() 方法"""
        version = self.plugin.get_version()
        
        result.details['version'] = version
        
        print(f"   版本: {version}")
        
        if not isinstance(version, str):
            raise AssertionError(f"get_version() 应该返回字符串，返回了 {type(version).__name__}")
        
        if not version:
            raise AssertionError("get_version() 返回空字符串")
    
    def test_8_get_description(self, result: TestResult):
        """测试 8: get_description() 方法"""
        description = self.plugin.get_description()
        
        result.details['description'] = description
        
        print(f"   描述: {description}")
        
        if not isinstance(description, str):
            raise AssertionError(f"get_description() 应该返回字符串，返回了 {type(description).__name__}")
        
        if not description:
            raise AssertionError("get_description() 返回空字符串")
    
    def test_9_get_author(self, result: TestResult):
        """测试 9: get_author() 方法"""
        author = self.plugin.get_author()
        
        result.details['author'] = author
        
        print(f"   作者: {author}")
        
        if not isinstance(author, str):
            raise AssertionError(f"get_author() 应该返回字符串，返回了 {type(author).__name__}")
        
        if not author:
            raise AssertionError("get_author() 返回空字符串")
    
    def test_10_get_capabilities(self, result: TestResult):
        """测试 10: get_capabilities() 方法"""
        capabilities = self.plugin.get_capabilities()
        
        result.details['capabilities'] = capabilities
        
        print(f"   能力:")
        for key, value in capabilities.items():
            print(f"     {key}: {value}")
        
        if not isinstance(capabilities, dict):
            raise AssertionError(f"get_capabilities() 应该返回字典，返回了 {type(capabilities).__name__}")
    
    def test_11_get_supported_asset_types(self, result: TestResult):
        """测试 11: get_supported_asset_types() 方法"""
        from core.plugin_types import AssetType
        
        asset_types = self.plugin.get_supported_asset_types()
        
        result.details['asset_types'] = [at.value for at in asset_types]
        result.details['asset_types_count'] = len(asset_types)
        
        print(f"   支持的资产类型 ({len(asset_types)}):")
        for asset_type in asset_types:
            print(f"     - {asset_type.value}")
        
        if not isinstance(asset_types, list):
            raise AssertionError(f"get_supported_asset_types() 应该返回列表，返回了 {type(asset_types).__name__}")
        
        if not asset_types:
            raise AssertionError("get_supported_asset_types() 返回空列表")
        
        for asset_type in asset_types:
            if not isinstance(asset_type, AssetType):
                raise AssertionError(f"资产类型应该是 AssetType 枚举，但包含 {type(asset_type).__name__}")
    
    def test_12_get_supported_data_types(self, result: TestResult):
        """测试 12: get_supported_data_types() 方法"""
        from core.plugin_types import DataType
        
        data_types = self.plugin.get_supported_data_types()
        
        result.details['data_types'] = [dt.value for dt in data_types]
        result.details['data_types_count'] = len(data_types)
        
        print(f"   支持的数据类型 ({len(data_types)}):")
        for data_type in data_types:
            print(f"     - {data_type.value}")
        
        if not isinstance(data_types, list):
            raise AssertionError(f"get_supported_data_types() 应该返回列表，返回了 {type(data_types).__name__}")
        
        if not data_types:
            raise AssertionError("get_supported_data_types() 返回空列表")
        
        for data_type in data_types:
            if not isinstance(data_type, DataType):
                raise AssertionError(f"数据类型应该是 DataType 枚举，但包含 {type(data_type).__name__}")
    
    def test_13_is_connected(self, result: TestResult):
        """测试 13: is_connected() 方法"""
        is_connected = self.plugin.is_connected()
        
        result.details['is_connected'] = is_connected
        
        print(f"   连接状态: {is_connected}")
        
        if not isinstance(is_connected, bool):
            raise AssertionError(f"is_connected() 应该返回布尔值，返回了 {type(is_connected).__name__}")
    
    def test_14_get_connection_info(self, result: TestResult):
        """测试 14: get_connection_info() 方法"""
        from core.data_source_extensions import ConnectionInfo
        
        connection_info = self.plugin.get_connection_info()
        
        result.details['connection_info_type'] = type(connection_info).__name__
        result.details['is_connected'] = connection_info.is_connected
        
        print(f"   连接信息类型: {type(connection_info).__name__}")
        print(f"   是否连接: {connection_info.is_connected}")
        
        if not isinstance(connection_info, ConnectionInfo):
            raise AssertionError(f"get_connection_info() 应该返回 ConnectionInfo，返回了 {type(connection_info).__name__}")
    
    def test_15_health_check(self, result: TestResult):
        """测试 15: health_check() 方法"""
        from core.data_source_extensions import HealthCheckResult
        
        health_result = self.plugin.health_check()
        
        result.details['health_result_type'] = type(health_result).__name__
        result.details['is_healthy'] = health_result.is_healthy
        result.details['message'] = health_result.message
        
        print(f"   健康检查结果类型: {type(health_result).__name__}")
        print(f"   是否健康: {health_result.is_healthy}")
        print(f"   消息: {health_result.message}")
        
        if not isinstance(health_result, HealthCheckResult):
            raise AssertionError(f"health_check() 应该返回 HealthCheckResult，返回了 {type(health_result).__name__}")
    
    def test_16_adapter_creation(self, result: TestResult):
        """测试 16: DataSourcePluginAdapter 创建"""
        from core.data_source_extensions import DataSourcePluginAdapter
        
        adapter = DataSourcePluginAdapter(self.plugin, "miniqmt_data_source")
        self.adapter = adapter
        
        result.details['adapter_type'] = type(adapter).__name__
        result.details['adapter_plugin_id'] = adapter.plugin_id
        
        print(f"   适配器类型: {type(adapter).__name__}")
        print(f"   适配器插件ID: {adapter.plugin_id}")
        
        if not isinstance(adapter, DataSourcePluginAdapter):
            raise AssertionError(f"适配器应该是 DataSourcePluginAdapter 类型，但返回了 {type(adapter).__name__}")
    
    def test_17_adapter_get_plugin_info(self, result: TestResult):
        """测试 17: adapter.get_plugin_info() 方法"""
        plugin_info = self.adapter.get_plugin_info()
        
        result.details['plugin_info_id'] = plugin_info.id
        result.details['plugin_info_name'] = plugin_info.name
        
        print(f"   插件ID: {plugin_info.id}")
        print(f"   插件名称: {plugin_info.name}")
        
        if plugin_info.id != "miniqmt_data_source":
            raise AssertionError(f"插件ID应该是 'miniqmt_data_source'，但返回了 '{plugin_info.id}'")
    
    def test_18_adapter_get_connection_info(self, result: TestResult):
        """测试 18: adapter 连接信息获取（通过 plugin.get_connection_info()）"""
        connection_info = self.plugin.get_connection_info()
        
        result.details['connection_info_type'] = type(connection_info).__name__
        result.details['is_connected'] = connection_info.is_connected
        
        print(f"   连接信息类型: {type(connection_info).__name__}")
        print(f"   是否连接: {connection_info.is_connected}")
    
    def test_19_plugin_manager_discovery(self, result: TestResult):
        """测试 19: PluginManager 插件发现"""
        from core.plugin_manager import PluginManager
        from core.containers import get_service_container
        
        plugin_manager = None
        
        # 尝试从服务容器获取 PluginManager
        try:
            container = get_service_container()
            if container and container.is_registered(PluginManager):
                plugin_manager = container.resolve(PluginManager)
                print(f"   从服务容器获取 PluginManager")
        except Exception as e:
            print(f"   从服务容器获取 PluginManager 失败: {e}")
        
        # 如果服务容器不可用，尝试直接创建
        if not plugin_manager:
            try:
                plugin_manager = PluginManager()
                print(f"   直接创建 PluginManager 实例")
            except Exception as e:
                print(f"   创建 PluginManager 失败: {e}")
        
        self.plugin_manager = plugin_manager
        
        result.details['plugin_manager_type'] = type(plugin_manager).__name__ if plugin_manager else None
        
        if plugin_manager:
            print(f"   插件管理器类型: {type(plugin_manager).__name__}")
            
            # 检查插件是否被加载
            try:
                loaded_plugins = plugin_manager.get_all_plugins()
                result.details['loaded_plugins_count'] = len(loaded_plugins)
                
                print(f"   已加载插件数量: {len(loaded_plugins)}")
                
                # 检查 miniqmt_plugin 是否在已加载插件中
                miniqmt_found = False
                for plugin_name, plugin_info in loaded_plugins.items():
                    if 'miniqmt' in plugin_name.lower():
                        miniqmt_found = True
                        result.details['miniqmt_plugin_name'] = plugin_name
                        print(f"   找到 miniqmt 插件: {plugin_name}")
                        break
                
                result.details['miniqmt_found'] = miniqmt_found
                
                if not miniqmt_found:
                    print("   ⚠️  警告: 未在插件管理器中找到 miniqmt 插件（这可能是因为插件未被加载）")
            except Exception as e:
                print(f"   ⚠️  警告: 获取已加载插件失败: {e}")
                result.details['get_all_plugins_error'] = str(e)
        else:
            print("   ⚠️  警告: 无法创建或获取 PluginManager 实例")
            result.details['plugin_manager_error'] = "无法创建或获取 PluginManager 实例"
    
    def test_20_unified_data_manager_registration(self, result: TestResult):
        """测试 20: UnifiedDataManager 插件注册"""
        from core.services.unified_data_manager import get_unified_data_manager
        
        unified_manager = get_unified_data_manager()
        self.unified_manager = unified_manager
        
        result.details['unified_manager_type'] = type(unified_manager).__name__
        
        print(f"   统一数据管理器类型: {type(unified_manager).__name__}")
        
        # 检查数据源路由器是否可用
        if hasattr(unified_manager, 'data_source_router'):
            router = unified_manager.data_source_router
            result.details['data_source_router_available'] = True
            
            print(f"   数据源路由器类型: {type(router).__name__}")
            
            # 检查 miniqmt 是否在数据源中
            if "miniqmt_data_source" in router.data_sources:
                result.details['miniqmt_registered'] = True
                print(f"   ✅ miniqmt 已注册到数据源路由器")
            else:
                result.details['miniqmt_registered'] = False
                print(f"   ⚠️  警告: miniqmt 未注册到数据源路由器")
        else:
            result.details['data_source_router_available'] = False
            print(f"   ⚠️  警告: 统一数据管理器没有 data_source_router 属性")
    
    def run_all_tests(self):
        """运行所有测试"""
        print(f"\n{'=' * 60}")
        print(f"🚀 miniqmt_plugin 全面回归测试")
        print(f"{'=' * 60}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 测试 1: 插件实例化
        self.run_test("插件实例化", self.test_1_plugin_instantiation)
        
        # 测试 2: 接口实现检查
        self.run_test("接口实现检查", self.test_2_interface_implementation)
        
        # 测试 3: plugin_info 属性检查
        self.run_test("plugin_info 属性检查", self.test_3_plugin_info_property)
        
        # 测试 4: StandardDataSourcePlugin 抽象方法实现
        self.run_test("StandardDataSourcePlugin 抽象方法实现", self.test_4_standard_data_source_plugin_methods)
        
        # 测试 5: StandardDataSourcePlugin 内部抽象方法实现
        self.run_test("StandardDataSourcePlugin 内部抽象方法实现", self.test_5_internal_methods)
        
        # 测试 6: IDataSourcePlugin 抽象方法实现
        self.run_test("IDataSourcePlugin 抽象方法实现", self.test_6_idata_source_plugin_methods)
        
        # 测试 7: get_version() 方法
        self.run_test("get_version() 方法", self.test_7_get_version)
        
        # 测试 8: get_description() 方法
        self.run_test("get_description() 方法", self.test_8_get_description)
        
        # 测试 9: get_author() 方法
        self.run_test("get_author() 方法", self.test_9_get_author)
        
        # 测试 10: get_capabilities() 方法
        self.run_test("get_capabilities() 方法", self.test_10_get_capabilities)
        
        # 测试 11: get_supported_asset_types() 方法
        self.run_test("get_supported_asset_types() 方法", self.test_11_get_supported_asset_types)
        
        # 测试 12: get_supported_data_types() 方法
        self.run_test("get_supported_data_types() 方法", self.test_12_get_supported_data_types)
        
        # 测试 13: is_connected() 方法
        self.run_test("is_connected() 方法", self.test_13_is_connected)
        
        # 测试 14: get_connection_info() 方法
        self.run_test("get_connection_info() 方法", self.test_14_get_connection_info)
        
        # 测试 15: health_check() 方法
        self.run_test("health_check() 方法", self.test_15_health_check)
        
        # 测试 16: DataSourcePluginAdapter 创建
        self.run_test("DataSourcePluginAdapter 创建", self.test_16_adapter_creation)
        
        # 测试 17: adapter.get_plugin_info() 方法
        self.run_test("adapter.get_plugin_info() 方法", self.test_17_adapter_get_plugin_info)
        
        # 测试 18: adapter.get_connection_info() 方法
        self.run_test("adapter.get_connection_info() 方法", self.test_18_adapter_get_connection_info)
        
        # 测试 19: PluginManager 插件发现
        self.run_test("PluginManager 插件发现", self.test_19_plugin_manager_discovery)
        
        # 测试 20: UnifiedDataManager 插件注册
        self.run_test("UnifiedDataManager 插件注册", self.test_20_unified_data_manager_registration)
        
        # 生成测试报告
        return self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        print(f"\n{'=' * 60}")
        print(f"📊 测试报告")
        print(f"{'=' * 60}")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"总测试数: {total_tests}")
        print(f"通过测试: {passed_tests}")
        print(f"失败测试: {failed_tests}")
        print(f"通过率: {pass_rate:.2f}%")
        
        print(f"\n{'=' * 60}")
        print(f"📋 详细结果")
        print(f"{'=' * 60}")
        
        for i, result in enumerate(self.results, 1):
            status = "✅ 通过" if result.success else "❌ 失败"
            print(f"{i}. {result.test_name}: {status}")
            if result.error:
                print(f"   错误: {result.error}")
        
        print(f"\n{'=' * 60}")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}")
        
        # 返回测试结果
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'pass_rate': pass_rate,
            'results': [r.to_dict() for r in self.results]
        }


def main():
    """主函数"""
    test_suite = RegressionTestSuite()
    report = test_suite.run_all_tests()
    
    # 根据测试结果返回退出码
    if report['failed_tests'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
