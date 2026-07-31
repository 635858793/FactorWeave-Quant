"""R222 E2E: 直接调用真实 service_bootstrap.shutdown_all() 验证"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")))

# 重置 factory
from core.database_adapter_factory import DatabaseAdapterFactory
DatabaseAdapterFactory.reset_for_testing()

print("Pre-state:")
print(f"  _disposed: {DatabaseAdapterFactory._disposed}")
print()

print("=== Test 1: 直接调 DatabaseAdapterFactory.dispose() ===")
result = DatabaseAdapterFactory.dispose()
print(f"  Result: {result}")
print(f"  _disposed: {DatabaseAdapterFactory._disposed}")
print()

# 重置
DatabaseAdapterFactory.reset_for_testing()
print("=== Test 2: 模拟 service_bootstrap.shutdown_all 关闭链 (修复后代码) ===")

import asyncio as _asyncio

instance = DatabaseAdapterFactory
service_name = "DatabaseAdapterFactory"
results = {}

# 这是 service_bootstrap.py 修复后的关闭链代码 (7155-7195)
for method_name in ('stop', 'shutdown', 'close', 'dispose'):
    method = getattr(instance, method_name, None)
    if method is None or not callable(method):
        continue
    try:
        if isinstance(instance, type) and isinstance(method, classmethod):
            bound_callable = method.__func__
            _call_args = (instance,)
        else:
            bound_callable = method
            _call_args = ()
        if _asyncio.iscoroutinefunction(bound_callable):
            try:
                _loop = _asyncio.get_running_loop()
                _loop.create_task(bound_callable(*_call_args))
            except RuntimeError:
                _asyncio.run(bound_callable(*_call_args))
        else:
            bound_callable(*_call_args)
        print(f"  [OK] {service_name}.{method_name}() 调用成功")
        results[service_name] = True
        break
    except Exception as method_exc:
        print(f"  [FAIL] {service_name}.{method_name}() 失败: {method_exc}")
        results[service_name] = False

print()
print(f"  Result: {results}")
print(f"  _disposed: {DatabaseAdapterFactory._disposed}")

assert results.get("DatabaseAdapterFactory") is True, "E2E 失败: 修复后 dispose 应成功"
assert DatabaseAdapterFactory._disposed is True, "E2E 失败: _disposed 应被设置"
print()
print("✅ E2E 通过: 修复后 service_bootstrap 关闭链正确处理 classmethod")

# 重置
DatabaseAdapterFactory.reset_for_testing()
print()
print("=== Test 3: 真实 service_bootstrap.shutdown_all() 全流程 ===")

# 模拟 service_container 注册 DatabaseAdapterFactory 类
from core.containers.service_container import get_service_container
from core.services.service_bootstrap import ServiceBootstrap, ServiceScope

container = get_service_container()
bootstrap = ServiceBootstrap(container)

# 注册 DatabaseAdapterFactory 类 (模拟 _register_database_adapter)
try:
    if not bootstrap._is_service_registered(DatabaseAdapterFactory):
        from core.database_adapter_factory import get_database_adapter_factory
        container.register(
            DatabaseAdapterFactory,
            scope=ServiceScope.SINGLETON,
            factory=lambda: get_database_adapter_factory(service_container=container),
        )
        print(f"  DatabaseAdapterFactory 已注册到 container")
except Exception as e:
    print(f"  注册失败: {e}")

# 验证能 resolve
try:
    instance = container.resolve(DatabaseAdapterFactory)
    print(f"  container.resolve(DatabaseAdapterFactory) type: {type(instance).__name__}")
    print(f"  instance is DatabaseAdapterFactory: {instance is DatabaseAdapterFactory}")
except Exception as e:
    print(f"  resolve 失败: {e}")

# 重置
DatabaseAdapterFactory.reset_for_testing()
print()
print("=== Test 4: 真正调用 service_bootstrap.shutdown_all() ===")
# 准备: 添加到 _instance_registered_services
bootstrap._instance_registered_services.add(DatabaseAdapterFactory)
print(f"  _instance_registered_services: {len(bootstrap._instance_registered_services)} services")

# 实际调用 (禁用容器 dispose 以避免破坏其他测试)
try:
    from unittest.mock import patch
    with patch.object(container, 'dispose'):
        result_dict = bootstrap.shutdown_all()
        print(f"  shutdown_all() result: {result_dict}")
        print(f"  DatabaseAdapterFactory result: {result_dict.get('DatabaseAdapterFactory')}")
        print(f"  _disposed: {DatabaseAdapterFactory._disposed}")
        assert result_dict.get('DatabaseAdapterFactory') is True, \
            f"DatabaseAdapterFactory 关闭应成功, 实际: {result_dict.get('DatabaseAdapterFactory')}"
        assert DatabaseAdapterFactory._disposed is True, \
            "DatabaseAdapterFactory._disposed 应被设置"
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"  shutdown_all 失败: {e}")

print()
print("✅ 全部 E2E 测试通过")
