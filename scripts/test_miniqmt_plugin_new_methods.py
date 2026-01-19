"""
测试 miniqmt_plugin 的新增方法

测试内容：
1. get_plugin_info() 方法
2. initialize() 方法

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2026-01-18
"""

import sys
import os
from typing import Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

def test_get_plugin_info():
    """测试 get_plugin_info() 方法"""
    print("\n" + "=" * 60)
    print("🧪 测试: get_plugin_info() 方法")
    print("=" * 60)
    
    try:
        from plugins.data_sources.stock.miniqmt_plugin import MiniQMTPlugin
        
        plugin = MiniQMTPlugin()
        
        # 测试 get_plugin_info() 方法
        plugin_info = plugin.get_plugin_info()
        
        print(f"   插件ID: {plugin_info.id}")
        print(f"   插件名称: {plugin_info.name}")
        print(f"   插件版本: {plugin_info.version}")
        print(f"   插件作者: {plugin_info.author}")
        print(f"   插件描述: {plugin_info.description}")
        print(f"   支持的资产类型: {[at.value if hasattr(at, 'value') else str(at) for at in plugin_info.supported_asset_types]}")
        print(f"   支持的数据类型: {[dt.value if hasattr(dt, 'value') else str(dt) for dt in plugin_info.supported_data_types]}")
        print(f"   插件能力: {plugin_info.capabilities}")
        
        # 验证返回值
        assert plugin_info.id == "miniqmt_data_source", f"插件ID应该是 'miniqmt_data_source'，但返回了 '{plugin_info.id}'"
        assert plugin_info.name == "miniQMT数据源", f"插件名称应该是 'miniQMT数据源'，但返回了 '{plugin_info.name}'"
        assert plugin_info.version == "1.0.0", f"插件版本应该是 '1.0.0'，但返回了 '{plugin_info.version}'"
        assert plugin_info.author == "FactorWeave-Quant团队", f"插件作者应该是 'FactorWeave-Quant团队'，但返回了 '{plugin_info.author}'"
        
        print("\n✅ get_plugin_info() 方法测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ get_plugin_info() 方法测试失败")
        print(f"   错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_initialize():
    """测试 initialize() 方法"""
    print("\n" + "=" * 60)
    print("🧪 测试: initialize() 方法")
    print("=" * 60)
    
    try:
        from plugins.data_sources.stock.miniqmt_plugin import MiniQMTPlugin
        
        plugin = MiniQMTPlugin()
        
        # 测试无参数初始化
        print("   测试无参数初始化...")
        result = plugin.initialize()
        
        if not result:
            print("   ⚠️  警告: initialize() 返回 False（可能是因为 xtquant 未安装）")
        else:
            print("   ✅ initialize() 返回 True")
        
        # 测试带参数初始化
        print("\n   测试带参数初始化...")
        config = {
            'ip': '192.168.1.100',
            'port': 58610,
            'session_id': 123,
            'enable_cache': False,
            'cache_ttl': 120
        }
        
        plugin2 = MiniQMTPlugin()
        result2 = plugin2.initialize(config)
        
        if not result2:
            print("   ⚠️  警告: initialize(config) 返回 False（可能是因为 xtquant 未安装）")
        else:
            print("   ✅ initialize(config) 返回 True")
            print(f"   配置已更新: IP={plugin2.config.ip}, Port={plugin2.config.port}")
        
        # 验证配置是否正确更新
        assert plugin2.config.ip == '192.168.1.100', f"IP 应该是 '192.168.1.100'，但返回了 '{plugin2.config.ip}'"
        assert plugin2.config.port == 58610, f"Port 应该是 58610，但返回了 {plugin2.config.port}"
        assert plugin2.config.session_id == 123, f"Session ID 应该是 123，但返回了 {plugin2.config.session_id}"
        assert plugin2.config.enable_cache == False, f"Enable Cache 应该是 False，但返回了 {plugin2.config.enable_cache}"
        assert plugin2.config.cache_ttl == 120, f"Cache TTL 应该是 120，但返回了 {plugin2.config.cache_ttl}"
        
        print("\n✅ initialize() 方法测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ initialize() 方法测试失败")
        print(f"   错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🚀 miniqmt_plugin 新增方法测试")
    print("=" * 60)
    
    # 测试 get_plugin_info() 方法
    test1_passed = test_get_plugin_info()
    
    # 测试 initialize() 方法
    test2_passed = test_initialize()
    
    # 生成测试报告
    print("\n" + "=" * 60)
    print("📊 测试报告")
    print("=" * 60)
    
    total_tests = 2
    passed_tests = sum([test1_passed, test2_passed])
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {failed_tests}")
    print(f"通过率: {pass_rate:.2f}%")
    
    print("\n" + "=" * 60)
    print("结束时间: 2026-01-18 13:17:00")
    print("=" * 60)
    
    # 根据测试结果返回退出码
    if failed_tests > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
