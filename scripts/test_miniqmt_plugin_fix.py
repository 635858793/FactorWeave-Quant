"""
验证 miniqmt_plugin.py 修复后的代码
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.data_sources.stock.miniqmt_plugin import MiniQMTPlugin
from core.data_source_extensions import IDataSourcePlugin
from plugins.templates.standard_data_source_plugin import StandardDataSourcePlugin
from abc import ABC

def test_plugin_instantiation():
    """测试插件实例化"""
    print("=" * 60)
    print("测试 1: 插件实例化")
    print("=" * 60)
    
    try:
        plugin = MiniQMTPlugin()
        print("✅ 插件实例化成功")
        print(f"   插件ID: {plugin.plugin_info.id}")
        print(f"   插件名称: {plugin.plugin_info.name}")
        print(f"   插件版本: {plugin.plugin_info.version}")
        print(f"   插件作者: {plugin.plugin_info.author}")
        print(f"   插件描述: {plugin.plugin_info.description}")
        return plugin
    except Exception as e:
        print(f"❌ 插件实例化失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_interface_implementation(plugin):
    """测试接口实现"""
    print("\n" + "=" * 60)
    print("测试 2: 接口实现检查")
    print("=" * 60)
    
    # 检查是否实现了 IDataSourcePlugin
    is_idata_source = isinstance(plugin, IDataSourcePlugin)
    print(f"✅ 是否实现 IDataSourcePlugin: {is_idata_source}")
    
    # 检查是否实现了 StandardDataSourcePlugin
    is_standard_data_source = isinstance(plugin, StandardDataSourcePlugin)
    print(f"✅ 是否实现 StandardDataSourcePlugin: {is_standard_data_source}")
    
    # 检查 plugin_info 是否是 property
    from core.data_source_extensions import PluginInfo
    plugin_info = plugin.plugin_info
    is_property = isinstance(type(plugin).plugin_info, property)
    print(f"✅ plugin_info 是否是 property: {is_property}")
    print(f"   plugin_info 类型: {type(plugin_info)}")
    print(f"   plugin_info 值: {plugin_info}")
    
    # 检查必需的方法
    required_methods = [
        'connect', 'disconnect', 'is_connected', 'health_check',
        'get_connection_info', 'get_asset_list', 'get_kdata', 'get_real_time_quotes',
        'get_version', 'get_description', 'get_author', 'get_capabilities',
        'get_supported_asset_types', 'get_supported_data_types',
        '_internal_connect', '_internal_disconnect', '_internal_get_asset_list',
        '_internal_get_kdata', '_internal_get_real_time_quotes'
    ]
    
    print("\n必需方法检查:")
    for method_name in required_methods:
        has_method = hasattr(plugin, method_name)
        status = "✅" if has_method else "❌"
        print(f"   {status} {method_name}: {has_method}")

def test_abstract_methods(plugin):
    """测试抽象方法"""
    print("\n" + "=" * 60)
    print("测试 3: 抽象方法实现检查")
    print("=" * 60)
    
    # 检查 StandardDataSourcePlugin 的抽象方法
    standard_abstract_methods = [
        'get_version', 'get_description', 'get_author', 'get_capabilities',
        'get_supported_asset_types', 'get_supported_data_types',
        '_internal_connect', '_internal_disconnect', '_internal_get_asset_list',
        '_internal_get_kdata', '_internal_get_real_time_quotes'
    ]
    
    print("StandardDataSourcePlugin 抽象方法:")
    for method_name in standard_abstract_methods:
        method = getattr(plugin, method_name, None)
        is_implemented = method is not None and callable(method)
        status = "✅" if is_implemented else "❌"
        print(f"   {status} {method_name}: {is_implemented}")
    
    # 检查 IDataSourcePlugin 的抽象方法
    idata_source_abstract_methods = [
        'plugin_info', 'connect', 'disconnect', 'is_connected',
        'get_connection_info', 'health_check', 'get_asset_list',
        'get_kdata', 'get_real_time_quotes'
    ]
    
    print("\nIDataSourcePlugin 抽象方法:")
    for method_name in idata_source_abstract_methods:
        if method_name == 'plugin_info':
            is_property = isinstance(type(plugin).plugin_info, property)
            status = "✅" if is_property else "❌"
            print(f"   {status} {method_name} (property): {is_property}")
        else:
            method = getattr(plugin, method_name, None)
            is_implemented = method is not None and callable(method)
            status = "✅" if is_implemented else "❌"
            print(f"   {status} {method_name}: {is_implemented}")

def test_method_calls(plugin):
    """测试方法调用"""
    print("\n" + "=" * 60)
    print("测试 4: 方法调用测试")
    print("=" * 60)
    
    try:
        # 测试 get_version
        version = plugin.get_version()
        print(f"✅ get_version(): {version}")
        
        # 测试 get_description
        description = plugin.get_description()
        print(f"✅ get_description(): {description}")
        
        # 测试 get_author
        author = plugin.get_author()
        print(f"✅ get_author(): {author}")
        
        # 测试 get_capabilities
        capabilities = plugin.get_capabilities()
        print(f"✅ get_capabilities(): {capabilities}")
        
        # 测试 get_supported_asset_types
        asset_types = plugin.get_supported_asset_types()
        print(f"✅ get_supported_asset_types(): {len(asset_types)} types")
        
        # 测试 get_supported_data_types
        data_types = plugin.get_supported_data_types()
        print(f"✅ get_supported_data_types(): {len(data_types)} types")
        
        # 测试 get_connection_info
        connection_info = plugin.get_connection_info()
        print(f"✅ get_connection_info(): is_connected={connection_info.is_connected}")
        
        # 测试 is_connected
        is_connected = plugin.is_connected()
        print(f"✅ is_connected(): {is_connected}")
        
        # 测试 health_check
        health_result = plugin.health_check()
        print(f"✅ health_check(): is_healthy={health_result.is_healthy}")
        
        # 测试 get_stats
        stats = plugin.get_stats()
        print(f"✅ get_stats(): {stats}")
        
    except Exception as e:
        print(f"❌ 方法调用失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("miniqmt_plugin.py 修复验证")
    print("=" * 60)
    
    plugin = test_plugin_instantiation()
    
    if plugin:
        test_interface_implementation(plugin)
        test_abstract_methods(plugin)
        test_method_calls(plugin)
    
    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
