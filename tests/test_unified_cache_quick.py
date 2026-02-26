"""验证统一缓存架构迁移"""
import sys

print("开始验证统一缓存架构迁移...")

from core.services.cache_service import CacheService
print("✓ CacheService导入成功")

from core.services.unified_cache_provider import get_unified_cache_provider
print("✓ unified_cache_provider模块导入成功")

from core.adapters.legacy_cache_adapter import SmartDataCacheAdapter, StrategyCacheAdapter, AsyncIOManagerAdapter
print("✓ legacy_cache_adapter模块导入成功")

from backtest import get_async_io_manager, get_smart_data_cache
print("✓ backtest模块导入成功")

provider = get_unified_cache_provider()
cache = provider.get_cache_service()
print(f"✓ CacheService初始化: {cache is not None}")

cache.set("test_key", "test_value", namespace="test")
value = cache.get("test_key", namespace="test")
assert value == "test_value", f"缓存读写测试失败: 期望 'test_value', 实际 '{value}'"
print("✓ 缓存读写测试通过")

smart_cache = get_smart_data_cache()
print(f"✓ SmartDataCache适配器: {smart_cache is not None}")

async_io = get_async_io_manager()
print(f"✓ AsyncIOManager适配器: {async_io is not None}")

print("\n所有验证通过!")
