"""R222 根因验证: classmethod descriptor 实际行为"""
from core.database_adapter_factory import DatabaseAdapterFactory

print('=== Test 1: Direct class call ===')
result1 = DatabaseAdapterFactory.dispose()
print(f'Result: {result1}')

DatabaseAdapterFactory.reset_for_testing()
print()

print('=== Test 2: getattr + call (service_bootstrap pattern) ===')
instance = DatabaseAdapterFactory
method = getattr(instance, 'dispose', None)
print(f'method type: {type(method).__name__}')
print(f'callable: {callable(method)}')
try:
    result2 = method()
    print(f'Result: {result2}')
except TypeError as e:
    print(f'TypeError: {e}')

DatabaseAdapterFactory.reset_for_testing()
print()

print('=== Test 3: __dict__ access (raw descriptor) ===')
raw_method = DatabaseAdapterFactory.__dict__.get('dispose')
print(f'raw method type: {type(raw_method).__name__}')
has_func = hasattr(raw_method, '__func__')
print(f'has __func__: {has_func}')
if has_func:
    print(f'__func__: {raw_method.__func__}')
try:
    result3 = raw_method()
    print(f'Result: {result3}')
except TypeError as e:
    print(f'TypeError: {e}')

DatabaseAdapterFactory.reset_for_testing()
print()

print('=== Test 4: Using inspect.getattr_static (raw descriptor without binding) ===')
import inspect
raw_static = inspect.getattr_static(DatabaseAdapterFactory, 'dispose')
print(f'static method type: {type(raw_static).__name__}')
try:
    result4 = raw_static()
    print(f'Result: {result4}')
except TypeError as e:
    print(f'TypeError: {e}')
