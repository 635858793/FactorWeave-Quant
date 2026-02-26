"""验证统一缓存架构迁移"""
import sys

print("开始验证统一缓存架构迁移...")

# 测试模块导入
from backtest import get_async_io_manager, get_smart_data_cache, get_unified_cache_service, migrate_to_unified_cache
print("✓ backtest模块导入成功")

from core.services.unified_cache_provider import get_unified_cache_provider, get_smart_cache, get_strategy_cache
print("✓ unified_cache_provider模块导入成功")

from core.adapters.legacy_cache_adapter import SmartDataCacheAdapter, StrategyCacheAdapter, AsyncIOManagerAdapter
print("✓ legacy_cache_adapter模块导入成功")

# 测试缓存服务
provider = get_unified_cache_provider()
cache_service = provider.get_cache_service()
print(f"✓ CacheService获取成功: {cache_service is not None}")

# 测试适配器
smart_cache = get_smart_cache()
print(f"✓ SmartDataCache适配器获取成功: {smart_cache is not None}")

strategy_cache = get_strategy_cache()
print(f"✓ StrategyCache适配器获取成功: {strategy_cache is not None}")

# 测试基本缓存操作
smart_cache.put("test_key", "test_value", ttl=60)
value = smart_cache.get("test_key")
assert value == "test_value", f"缓存读写测试失败: 期望 'test_value', 实际 '{value}'"
print("✓ 缓存读写测试通过")

# 测试命名空间隔离
smart_cache.put("ns_test", "ns_value", ttl=60)
strategy_cache.put("ns_test", "strategy_value", ttl=60)
assert smart_cache.get("ns_test") == "ns_value"
assert strategy_cache.get("ns_test") == "strategy_value"
print("✓ 命名空间隔离测试通过")

# 测试统计信息
stats = smart_cache.get_stats()
print(f"✓ 缓存统计信息: hits={stats.get('hits', 0)}, misses={stats.get('misses', 0)}")

print("\n所有验证通过!")
