"""
R187-A handle_order_fill 3 阶段拆锁实施脚本 (v2 - AST 精确定位)
================================================================

使用 AST 精确定位 handle_order_fill 内的 _order_lock 块 (R104 §12 #3+#5)
直接用源文件搜索 "with self._order_lock:" 在 L2597 附近定位。
"""
import ast
import sys
from pathlib import Path


FILE_PATH = Path("core/trading/order_executor.py")


def find_handle_order_fill_lock_block_precise() -> tuple[int, int]:
    """AST 精确定位 handle_order_fill 内的 _order_lock 块 (R104 §12 #3+#5)"""
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "OrderExecutor":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "handle_order_fill":
                    for sub in ast.walk(item):
                        if isinstance(sub, ast.With):
                            for with_item in sub.items:
                                if (isinstance(with_item.context_expr, ast.Attribute)
                                        and isinstance(with_item.context_expr.value, ast.Name)
                                        and with_item.context_expr.value.id == "self"
                                        and with_item.context_expr.attr == "_order_lock"):
                                    return sub.lineno, sub.end_lineno
    raise RuntimeError("未找到 handle_order_fill._order_lock 块")


def backup_file() -> Path:
    """备份原文件"""
    backup_path = FILE_PATH.with_suffix(FILE_PATH.suffix + ".bak.r187a")
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(content)
    return backup_path


def generate_replacement_code() -> str:
    """生成 3 阶段拆锁替代代码

    设计:
    - 阶段 1 (锁内 ~25 行): 状态机修改 + publish_args 快照 (snapshot + mutation in lock)
    - 阶段 2 (锁外 ~30 行): 失败埋点 + 持久化回滚 (用 _state_transition_failed flag)
    - 阶段 3 (锁外, 已存在): persist + publish (R90-V CTP 模式)

    关键: 状态机转换 (transition_to) 必须锁内 → 失败处理在锁外用 flag 通信
    """
    return '''            # =================================================================
            # R187-A 3 阶段拆锁 - 阶段 1: 锁内仅做状态机修改 + publish_args 快照
            # =================================================================
            # Why: 原 L2597-2677 持 _order_lock 81 行 → 100+ 成交/秒场景 12+ 线程阻塞
            # Fix: 阶段 1 锁内只做核心 mutation (~25 行) + 失败 flag
            #      阶段 2 锁外做失败埋点 + 持久化回滚 (用 _state_transition_failed flag)
            #      阶段 3 锁外 persist + publish (R90-V CTP 模式, 已存在)
            # 关联铁律:
            #   - R8 §8.1 #2 (publish 锁外) - 阶段 3 publish 在锁外
            #   - R51 #5 (持久化降级) - _persist_order_externalized 失败仅 warning
            #   - R104 §12 #3+#5 (锁嵌套 AST 递归) - 阶段 1 锁内 0 嵌套
            #   - R132-HVD-003 (锁外持久化) - 复用 _persist_order_externalized
            #   - R177 实战模板 (snapshot/decision/mutation)
            with self._order_lock:
                # 阶段 1.1: prev 读取 (快照, 失败回滚用)
                prev_qty = order.filled_quantity
                prev_price = order.filled_price
                prev_status = order.order_status

                # 阶段 1.2: 累加 + 加权平均价 (必须锁内, 修改 order 状态)
                order.filled_quantity += fill_quantity
                if prev_qty > 0:
                    order.filled_price = (order.filled_price * prev_qty + fill_price * fill_quantity) / order.filled_quantity
                else:
                    order.filled_price = fill_price
                order.update_time = datetime.now()

                # 阶段 1.3: 状态机转换 (必须锁内, 失败时设置 flag 锁外处理)
                _state_transition_failed = False
                _state_transition_target = ''
                if order.filled_quantity >= order.order_quantity:
                    if not order.transition_to(OrderStatus.FILLED):
                        _state_transition_failed = True
                        _state_transition_target = OrderStatus.FILLED.value
                else:
                    if not order.transition_to(OrderStatus.PARTIALLY_FILLED):
                        _state_transition_failed = True
                        _state_transition_target = OrderStatus.PARTIALLY_FILLED.value

                # 阶段 1.4: 锁内保存 publish 所需原始字段 (锁外构造 dict, 防锁内代码膨胀)
                # Why: publish_args 字段访问不依赖 order 状态的中间修改, 锁外构造安全
                _publish_is_fully_filled = (order.filled_quantity >= order.order_quantity) and not _state_transition_failed
                if not _current_fill_id:
                    logger.error(f"[NEW-7] fill_id 缺失! order_id={order_id}, 可能导致分笔成交被误去重", exc_info=True)

            # 阶段 1.5: 锁外构造 publish_args dict (字段访问不依赖中间状态, 锁外安全)
            asset_type_value = (order.asset_type.value
                                if getattr(order, 'asset_type', None) is not None
                                else '')
            _publish_args = {
                'order_id': order_id,
                'fill_id': _current_fill_id,
                'stock_code': getattr(order, 'stock_code', ''),
                'filled_price': float(fill_price),
                'filled_quantity': int(fill_quantity),
                'asset_type': asset_type_value,
                'account_id': getattr(order, 'account_id', '') or '',
                'trading_interface': getattr(order, 'trading_interface', 'mock'),
                'signal_id': getattr(order, 'source_signal_id', '') or '',
            }
            _is_fully_filled = _publish_is_fully_filled

            # =================================================================
            # R187-A 3 阶段拆锁 - 阶段 2: 锁外状态机失败回滚 (仅失败时执行)
            # =================================================================
            # Why: 状态机失败的 trace_event + logger + 持久化回滚在锁外执行,
            #      短锁仅做数据回滚 (filled_quantity/price 恢复 prev), 12+ 线程不阻塞.
            # 关联铁律:
            #   - R8 §8.1 #2 (publish 锁外) - 阶段 2 不调 publish
            #   - R51 #5 (持久化降级) - _persist_order_externalized 失败仅 warning
            #   - R159 HVD-158-B (异常埋点可观测) - trace_event 失败 logger.warning exc_info=True
            #   - R174 §12 教训 (异常路径 logger 必须 exc_info=True)
            if _state_transition_failed:
                # 阶段 2.1: trace_event 埋点 (锁外, R90+ T P0-13/14 监控)
                if trace_event is not None:
                    try:
                        trace_event("order.executor.fill_state_fail",
                                    order_id=order_id,
                                    target=_state_transition_target,
                                    persist_fail=False)
                    except Exception as e:
                        logger.warning(
                            f"[R159 HVD-158-B] order.executor.fill_state_fail({_state_transition_target}) "
                            f"trace_event 失败 (可忽略, 不影响主流程): {e}",
                            exc_info=True,
                        )
                # 阶段 2.2: logger.error 状态转换失败 (R174 §12 exc_info=True)
                logger.error(
                    f"成交状态转换失败: {order_id} -> {_state_transition_target}, 回滚成交",
                    exc_info=True,
                )
                # 阶段 2.3: 短锁数据回滚 (filled_quantity/price 恢复到 prev)
                # Why: 避免锁与阶段 1 重叠, 数据回滚只在内存, 持久化在锁外
                with self._order_lock:
                    order.filled_quantity = prev_qty
                    order.filled_price = prev_price
                # 阶段 2.4: 锁外持久化 (R132-HVD-003 模板, _persist_order_externalized)
                # Why: 持久化 5-50ms DB 写入不持 _order_lock, 12+ 线程不阻塞
                self._persist_order_externalized(
                    order,
                    op_name=f"fill_rollback_{_state_transition_target.lower()}",
                    exc_info=True,
                )
                return False

'''


def main():
    print(f"R187-A handle_order_fill 3 阶段拆锁 v2 (AST 精确定位)")
    print(f"文件: {FILE_PATH}\n")

    # 1. 备份
    backup_path = backup_file()
    print(f"备份: {backup_path}")

    # 2. AST 精确定位
    lock_start, lock_end = find_handle_order_fill_lock_block_precise()
    print(f"原锁块: L{lock_start}-{lock_end} (共 {lock_end - lock_start + 1} 行)")

    # 3. 验证锁块行数 == 81
    if lock_end - lock_start + 1 != 81:
        print(f"⚠️  锁块行数 {lock_end - lock_start + 1} != 81 (R186-B 报告基线)")
        print(f"  仍继续 (可能 R186-B 报告后已有微调)")

    # 4. 读取并替换
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split('\n')

    new_code = generate_replacement_code()
    new_lines = new_code.split('\n')

    # 关键: 0-indexed: lines[lock_start-1 : lock_end] 是 1-based L{lock_start}-L{lock_end} 内容
    # 替换: lines[lock_start-1:lock_end] = new_lines
    replaced_lines = lines[:lock_start - 1] + new_lines + lines[lock_end:]

    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write('\n'.join(replaced_lines))

    # 5. 验证
    print(f"已写入: 新代码 {len(new_lines)} 行 (阶段 1: 锁内 + 阶段 2: 锁外)")

    # 6. AST 解析验证
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            new_source = f.read()
        ast.parse(new_source)
        print("✅ AST 解析通过 (Python 语法正确)")
    except SyntaxError as e:
        print(f"❌ AST 解析失败: {e}")
        # 回滚
        with open(backup_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print("已回滚到备份")
        return 1

    # 7. 重新查找锁块, 验证 < 30 行
    new_lock_start, new_lock_end = find_handle_order_fill_lock_block_precise()
    new_lock_body = new_lock_end - new_lock_start + 1
    print(f"\n新锁块: L{new_lock_start}-{new_lock_end} (共 {new_lock_body} 行)")

    if new_lock_body <= 30:
        print(f"✅ 锁内代码: {lock_end - lock_start + 1} → {new_lock_body} 行 (-{lock_end - lock_start + 1 - new_lock_body} 行, -{int((lock_end - lock_start + 1 - new_lock_body) / (lock_end - lock_start + 1) * 100)}%)")
        print(f"✅ R187-A 3 阶段拆锁目标达成 (锁内 < 30 行)")
    else:
        print(f"❌ 锁内代码仍 {new_lock_body} 行, 未达成 < 30 行目标")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
