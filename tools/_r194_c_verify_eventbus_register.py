"""R194-C 验证 R193-C-D-001 实施的 EventType 枚举在 EventBus 启动期注册情况"""
import logging
import sys
logging.disable(logging.CRITICAL)
from core.events.types import EventType
from core.events.event_bus import EventBus

bus = EventBus(async_execution=False, max_workers=1)
result_lines = []
result_lines.append('=== R194-C 验证: R193-C-D-001 实施的 3 个新 EventType 枚举已注册 ===')
# 注意: _register_builtin_event_types 用 EventType.__members__.items() 遍历的是大写名 (如 'ORDER_SAVE_RETRY')
# 而非 .value (如 'order_save_retry'), source='builtin_enum'
for et in [EventType.ORDER_SAVE_RETRY, EventType.ORDER_SAVE_FAILED_NEED_UNFREEZE, EventType.ALL_ACTIVE_ORDERS_CANCELLED]:
    in_reg_enum = (et.name, 'builtin_enum') in bus._event_type_registry  # 用大写名检查
    in_reg_value = (et.value, 'builtin_enum') in bus._event_type_registry  # 用 value 检查 (兼容)
    result_lines.append(f'  {et.name} (name={et.name}, value={et.value}) builtin_enum: name_match={in_reg_enum}, value_match={in_reg_value}')
result_lines.append(f'总注册类型数: {len(bus._event_type_registry)}')
result_lines.append(f'总 EventType 枚举数: {len(EventType.__members__)}')

result = '\n'.join(result_lines)
with open('_r194_c_eventbus_register.txt', 'w', encoding='utf-8') as f:
    f.write(result + '\n')
sys.exit(0)
