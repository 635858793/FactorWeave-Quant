"""R222 根因深度诊断"""
import inspect
from core.database_adapter_factory import DatabaseAdapterFactory

DatabaseAdapterFactory.reset_for_testing()

instance = DatabaseAdapterFactory
method = getattr(instance, 'dispose', None)

print('=== getattr path (current service_bootstrap) ===')
print(f'type: {type(method).__name__}')
print(f'is classmethod: {isinstance(method, classmethod)}')
print(f'has __func__: {hasattr(method, "__func__")}')
print(f'has __self__: {hasattr(method, "__self__")}')
if hasattr(method, '__self__'):
    print(f'__self__: {method.__self__}')
if hasattr(method, '__func__'):
    print(f'__func__: {method.__func__}')
    print(f'__func__ type: {type(method.__func__).__name__}')

# Try calling __func__() without args
print()
print('=== Test: method.__func__() ===')
try:
    result = method.__func__()
    print(f'Result: {result}')
except TypeError as e:
    print(f'TypeError: {e}')

# Try calling __func__(instance)
print()
print('=== Test: method.__func__(instance) ===')
try:
    result = method.__func__(instance)
    print(f'Result: {result}')
except TypeError as e:
    print(f'TypeError: {e}')

print()
print('=== inspect.getattr_static path ===')
DatabaseAdapterFactory.reset_for_testing()
static_method = inspect.getattr_static(DatabaseAdapterFactory, 'dispose')
print(f'type: {type(static_method).__name__}')
print(f'is classmethod: {isinstance(static_method, classmethod)}')
print(f'has __func__: {hasattr(static_method, "__func__")}')
if hasattr(static_method, '__func__'):
    print(f'__func__: {static_method.__func__}')
    print(f'__func__ type: {type(static_method.__func__).__name__}')

# Try calling static_method() directly
print()
print('=== Test: static_method() ===')
try:
    result = static_method()
    print(f'Result: {result}')
except TypeError as e:
    print(f'TypeError: {e}')

# Try calling static_method.__func__(instance)
print()
print('=== Test: static_method.__func__(instance) ===')
try:
    result = static_method.__func__(instance)
    print(f'Result: {result}')
except TypeError as e:
    print(f'TypeError: {e}')
