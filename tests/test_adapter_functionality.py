"""
简单的功能测试 - 验证适配器功能
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.cache import Cache
from core.adapters.legacy_cache_adapter import create_legacy_cache_adapter
from core.interfaces.cache import CacheLevel


async def test_adapter_basic_operations():
    """测试适配器基本操作"""
    print("测试适配器基本操作...")
    
    # 创建原始缓存
    original_cache = Cache(cache_dir=".test_cache_basic", backend="diskcache")
    
    # 创建适配器
    adapter = create_legacy_cache_adapter(original_cache, async_mode=False, level=CacheLevel.L3_DISK)
    
    try:
        # 测试set和get
        print("  测试set和get...")
        await adapter.set("test_key", "test_value", ttl=3600)
        value = await adapter.get("test_key")
        assert value == "test_value", f"Expected 'test_value', got {value}"
        print("  ✓ set和get测试通过")
        
        # 测试exists
        print("  测试exists...")
        exists = await adapter.exists("test_key")
        assert exists == True, f"Expected True, got {exists}"
        print("  ✓ exists测试通过")
        
        # 测试delete
        print("  测试delete...")
        await adapter.delete("test_key")
        exists = await adapter.exists("test_key")
        assert exists == False, f"Expected False, got {exists}"
        print("  ✓ delete测试通过")
        
        # 测试批量操作
        print("  测试批量操作...")
        items = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3"
        }
        count = await adapter.set_many(items, ttl=3600)
        assert count == 3, f"Expected 3, got {count}"
        
        values = await adapter.get_many(["key1", "key2", "key3"])
        assert len(values) == 3, f"Expected 3, got {len(values)}"
        print("  ✓ 批量操作测试通过")
        
        # 测试统计信息
        print("  测试统计信息...")
        stats = await adapter.get_stats()
        print(f"    Hits: {stats.hits}, Misses: {stats.misses}, Sets: {stats.sets}")
        print("  ✓ 统计信息测试通过")
        
        # 测试clear
        print("  测试clear...")
        await adapter.clear()
        stats = await adapter.get_stats()
        assert stats.current_size == 0, f"Expected 0, got {stats.current_size}"
        print("  ✓ clear测试通过")
        
        print("✓ 适配器基本操作测试通过\n")
        
    finally:
        # 关闭缓存连接
        if hasattr(original_cache, 'cache') and hasattr(original_cache.cache, 'close'):
            original_cache.cache.close()


async def main():
    """主测试函数"""
    print("=" * 60)
    print("开始功能测试")
    print("=" * 60 + "\n")
    
    try:
        await test_adapter_basic_operations()
        
        print("=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 清理测试缓存
        import shutil
        for cache_dir in [".test_cache_basic"]:
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                print(f"清理测试缓存: {cache_dir}")


if __name__ == "__main__":
    asyncio.run(main())
