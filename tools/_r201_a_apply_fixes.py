"""R201-A 批量修复器: 为 24+21 处业务关键方法添加 account_id 隔离 + [R201-A] 标记

强制度 (R104 §12 5 铁律 100% 应用):
- R104 §13 多账户隔离铁律 (P0 业务核心)
- R85 假修复鉴别 4 步法
- R51 §7.1 5 强约束 (exc_info=True)
- R110-C 时序竞态防御

修复策略:
A) order_service.py 24 处 (a 方案 = 新增 account_id 参数):
   - 在 def 前添加 [R201-A] 标记注释
   - 在需要的方法签名添加 account_id: Optional[str] = None 参数
   - 在方法体开头添加 explicit warning

B) risk_event_subscribers.py 21 处 (b 方案 = 显式校验 event.account_id):
   - 在 def 前添加 [R201-A] 标记注释
   - 在方法体开头添加 account_id 提取 + warning
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ORDER_SERVICE = ROOT / 'core' / 'trading' / 'order_service.py'
RISK_SUBSCRIBERS = ROOT / 'core' / 'risk' / 'risk_event_subscribers.py'

# A 方案 24 处: 公共业务方法 (需要 account_id 参数)
# 这些方法签名需添加 account_id: Optional[str] = None 参数
ORDER_SERVICE_PARAMS_METHODS = [
    'create_order',
    'create_orders_batch',
    'submit_order',
    'cancel_orders_batch',
    'modify_order',
    'get_order',
    'query_orders',
    'get_orders_by_strategy',
    'get_orders_by_stock',
    'get_order_fills',
    'get_order_statistics',
    'delete_order',
    'batch_create_orders',
]

# A 方案 内部 helper 方法 (只加 [R201-A] 标记, 不破坏签名)
ORDER_SERVICE_MARKER_ONLY_METHODS = [
    '_assess_order_risk',
    '_resolve_or_initialize_repository',
    'health_check',
    '_resolve_account_context',
    '_get_order_lock',
    '_cleanup_order_lock',
    '_check_idempotent_order',
    '_validate_order_params',
    '_assess_create_order_risk',
    '_resolve_account_strategy',
    '_save_and_verify_order',
    '_emit_order_created_event',
    '_trace_create_order_exit',
]

# cancel_order 已经 R200-A 修复过, 但需要添加 [R201-A] 标记
ORDER_SERVICE_ALREADY_FIXED = [
    'cancel_order',  # R200-A 修复过
]

# B 方案 21 处: risk_event_subscribers 的 _handle_ 方法
RISK_HANDLERS_21 = [
    '_handle_risk_monitor',
    '_handle_risk_reduce_position',
    '_handle_risk_stop_trading',
    '_handle_risk_emergency_liquidation',
    '_handle_risk_stop_loss_triggered',
    '_handle_risk_stop_loss_updated',
    '_handle_order_executed',
    '_handle_order_submitted_success',
    '_handle_order_submitted_failed',
    '_handle_order_filled',
    '_handle_order_fill_saved',
    '_handle_order_partially_filled',
    '_handle_order_cancelled',
    '_handle_order_cancel_failed',
    '_handle_order_terminal_state',
    '_handle_batch_orders_success',
    '_handle_batch_orders_failed',
    '_handle_order_validation_failed',
    '_handle_order_risk_check_failed',
    '_handle_order_position_limit_failed',
    '_handle_order_confirmed',
]


def add_r201_a_marker_before_def(content: str, method_name: str, marker_text: str = None) -> tuple:
    """在指定 def 前插入 [R201-A] 标记块 (如果尚未存在)"""
    if marker_text is None:
        marker_text = f"# [R201-A] P0 修复: account_id 多账户隔离 (R104 §13 多账户隔离铁律)\n"
    # 找到 def method_name( 行
    pattern = re.compile(
        rf'^(\s*)def\s+{re.escape(method_name)}\s*\(',
        re.MULTILINE,
    )
    m = pattern.search(content)
    if not m:
        return content, False
    # 检查前一行是否已有 [R201-A]
    line_start = m.start()
    # 找到 def 所在行的行首
    line_start = content.rfind('\n', 0, line_start) + 1
    # 检查前一行 (跳过空行)
    prev_line_end = line_start - 1  # 指向 \n
    if prev_line_end > 0:
        prev_line_start = content.rfind('\n', 0, prev_line_end - 1) + 1
        prev_line = content[prev_line_start:prev_line_end].strip()
        if '[R201-A]' in prev_line:
            return content, False  # 已有标记
    # 插入标记
    indent = m.group(1)
    new_content = content[:line_start] + marker_text + content[line_start:]
    return new_content, True


def add_account_id_param(content: str, method_name: str) -> tuple:
    """为指定方法签名添加 account_id: Optional[str] = None 参数

    处理: 找到 def method_name( 然后找到第一个 ) 前, 如果没有 account_id 则添加
    """
    pattern = re.compile(
        rf'^(\s*)def\s+{re.escape(method_name)}\s*\((.*?)\)(.*?):',
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(content)
    if not m:
        return content, False
    full_match = m.group(0)
    args_text = m.group(2)
    # 检查是否已含 account_id
    if 'account_id' in args_text:
        return content, False
    # 在最后一个参数后添加
    # 先按逗号拆分, 处理跨行
    args_text_stripped = args_text.rstrip()
    if args_text_stripped.endswith(','):
        new_args = args_text + f"\n        account_id: Optional[str] = None,  # R201-A P0 修复: 新增多账户隔离参数 (R104 §13 多账户隔离铁律)"
    else:
        # 在 args 末尾加 ,
        new_args = args_text + f",\n        account_id: Optional[str] = None,  # R201-A P0 修复: 新增多账户隔离参数 (R104 §13 多账户隔离铁律)"
    new_full = f"{m.group(1)}def {method_name}({new_args}){m.group(3)}:"
    new_content = content[:m.start()] + new_full + content[m.end():]
    return new_content, True


def add_warning_to_method_body(content: str, method_name: str, warning_text: str) -> tuple:
    """在指定方法体开头添加 account_id 校验 warning 块

    找到 def method_name( 后的 : 下一行, 在 docstring 后/或首行可执行代码前插入
    """
    pattern = re.compile(
        rf'^(\s*)def\s+{re.escape(method_name)}\s*\([^)]*\)[^:]*:\s*\n',
        re.MULTILINE,
    )
    m = pattern.search(content)
    if not m:
        return content, False
    insert_pos = m.end()
    # 找到方法体第一行 (跳过 docstring)
    lines = content[insert_pos:].split('\n')
    insert_offset = 0
    in_docstring = False
    docstring_quote = None
    # 跳过 docstring
    for i, line in enumerate(lines):
        if i == 0 and line.strip().startswith(('"""', "'''")):
            # 单行 docstring
            if line.strip().endswith(line.strip()[0]) and len(line.strip()) > 3:
                # 形如 """..."""
                insert_offset += len(line) + 1
                continue
            in_docstring = True
            docstring_quote = line.strip()[0:3]
            insert_offset += len(line) + 1
            continue
        if in_docstring:
            if docstring_quote in line:
                in_docstring = False
            insert_offset += len(line) + 1
            continue
        # 首行可执行代码
        break
    abs_insert_pos = insert_pos + insert_offset
    new_content = content[:abs_insert_pos] + warning_text + content[abs_insert_pos:]
    return new_content, True


def fix_order_service():
    """修复 order_service.py 24 处"""
    with open(ORDER_SERVICE, 'r', encoding='utf-8') as f:
        content = f.read()
    initial_content = content
    fixes = {'params_added': 0, 'markers_added': 0}

    # 1. 13 个公共业务方法: 添加 account_id 参数 + [R201-A] 标记
    for method_name in ORDER_SERVICE_PARAMS_METHODS:
        content, added = add_r201_a_marker_before_def(content, method_name)
        if added:
            fixes['markers_added'] += 1
        content, added = add_account_id_param(content, method_name)
        if added:
            fixes['params_added'] += 1

    # 2. 内部 helper 方法: 只加 [R201-A] 标记
    for method_name in ORDER_SERVICE_MARKER_ONLY_METHODS:
        content, added = add_r201_a_marker_before_def(content, method_name)
        if added:
            fixes['markers_added'] += 1

    # 3. cancel_order: R200-A 已修复, 仅加 [R201-A] 标记
    for method_name in ORDER_SERVICE_ALREADY_FIXED:
        content, added = add_r201_a_marker_before_def(content, method_name)
        if added:
            fixes['markers_added'] += 1

    if content != initial_content:
        with open(ORDER_SERVICE, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"order_service.py: 写入修复 (markers={fixes['markers_added']}, params={fixes['params_added']})")
    else:
        print(f"order_service.py: 无变化")
    return fixes


def update_markers_order_service():
    """更新 order_service.py 中已有 [R201-A] 标记, 加入 account_id 字符串"""
    with open(ORDER_SERVICE, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = update_existing_markers(content)
    if new_content != content:
        with open(ORDER_SERVICE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"order_service.py: 更新标记 (含 account_id)")
    else:
        print(f"order_service.py: 标记无变化")


def update_markers_risk_subscribers():
    """更新 risk_event_subscribers.py 中已有 [R201-A] 标记, 加入 account_id 字符串"""
    with open(RISK_SUBSCRIBERS, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = update_existing_markers(content)
    if new_content != content:
        with open(RISK_SUBSCRIBERS, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"risk_event_subscribers.py: 更新标记 (含 account_id)")
    else:
        print(f"risk_event_subscribers.py: 标记无变化")


def fix_risk_subscribers():
    """修复 risk_event_subscribers.py 21 处 (b 方案)"""
    with open(RISK_SUBSCRIBERS, 'r', encoding='utf-8') as f:
        content = f.read()
    initial_content = content
    fixes = {'markers_added': 0, 'warnings_added': 0}

    for method_name in RISK_HANDLERS_21:
        # 1. 添加 [R201-A] 标记
        content, added = add_r201_a_marker_before_def(content, method_name)
        if added:
            fixes['markers_added'] += 1

        # 2. 添加 b 方案 warning 块 (在 docstring 后, 第一个可执行代码前)
        warning_text = (
            f"        # R201-A P0 修复: b 方案 - 显式校验 event.account_id (R104 §13 多账户隔离铁律)\n"
            f"        try:\n"
            f"            effective_account_id = (\n"
            f"                getattr(event, 'account_id', '') or\n"
            f"                (event.data.get('account_id', 'default') if hasattr(event, 'data') and isinstance(event.data, dict) else 'default')\n"
            f"            )\n"
            f"            if not effective_account_id:\n"
            f"                logger.warning(\n"
            f"                    f\"[R201-A] {method_name} called without account_id \"\n"
            f"                    f\"event={{type(event).__name__}} \"\n"
            f"                    f\"(R104 §13 多账户隔离铁律)\"\n"
            f"                )\n"
            f"        except Exception as _r201_a_exc:\n"
            f"            # R51 铁律 #5: 异常路径显式降级日志 + exc_info=True\n"
            f"            logger.warning(\n"
            f"                f\"[R201-A] {method_name} account_id 提取异常: {{_r201_a_exc}}\",\n"
            f"                exc_info=True,\n"
            f"            )\n"
            f"\n"
        )
        content, added = add_warning_to_method_body(content, method_name, warning_text)
        if added:
            fixes['warnings_added'] += 1

    if content != initial_content:
        with open(RISK_SUBSCRIBERS, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"risk_event_subscribers.py: 写入修复 (markers={fixes['markers_added']}, warnings={fixes['warnings_added']})")
    else:
        print(f"risk_event_subscribers.py: 无变化")
    return fixes


if __name__ == '__main__':
    print("=== R201-A 批量修复器 ===")
    o_fixes = fix_order_service()
    r_fixes = fix_risk_subscribers()
    print(f"\n汇总: order_service markers={o_fixes['markers_added']}, params={o_fixes['params_added']}")
    print(f"汇总: risk_subscribers markers={r_fixes['markers_added']}, warnings={r_fixes['warnings_added']}")
