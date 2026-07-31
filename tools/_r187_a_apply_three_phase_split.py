"""
R187-A handle_order_fill 3 阶段拆锁实施脚本
=============================================

设计: 3 阶段拆锁 (R177 实战模板 + R90-V CTP 模式 + R186-B 报告约束)

阶段 1 (锁内 ~10 行): state_machine_locked_phase
  - 累加 filled_quantity + 平均价 + update_time
  - 执行 transition_to (FILLED / PARTIALLY_FILLED)
  - 失败时设置 _state_transition_failed = True
  - 准备 _publish_args 快照 (防撕裂)

锁释放 (短锁 ~10-15 行)

阶段 2 (锁外): rollback_phase (仅失败时执行)
  - trace_event fill_state_fail (FILLED / PARTIALLY_FILLED)
  - logger.error 状态转换失败
  - 锁内回滚 filled_quantity/price (短锁 ~5 行)
  - _persist_order_externalized 锁外持久化
  - return False

阶段 3 (锁外, 已存在): persist + publish
  - update_order (锁外)
  - save_order_fill (锁外)
  - event_bus.publish (锁外)
  - _unfreeze_order_funds (锁外)

预期效果:
  - 锁内代码: 81 行 → ~25 行 (-69%)
  - 业务关键事件 publish 仍锁外 (R8 §8.1 #2 100% 满足)
  - 持久化失败仅 warning (R51 铁律 #5)
  - 异常路径 logger 必须 exc_info=True (R174 §12 教训)
  - 状态机失败回滚分两段: 数据回滚(短锁) + 持久化(锁外)
"""
import re
import sys
from pathlib import Path


# 文件路径
FILE_PATH = Path("core/trading/order_executor.py")


def read_file_lines() -> list[str]:
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        return f.readlines()


def write_file_lines(lines: list[str]) -> None:
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def backup_file() -> Path:
    """备份原文件"""
    backup_path = FILE_PATH.with_suffix(FILE_PATH.suffix + ".bak.r187a")
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(content)
    return backup_path


def find_lock_block_range(lines: list[str]) -> tuple[int, int]:
    """查找 handle_order_fill 内 _order_lock 块的范围 (start_line, end_line, 1-based)"""
    in_method = False
    method_indent = None
    lock_indent = None
    lock_start = None
    lock_end = None

    for i, line in enumerate(lines):
        # 找方法定义
        if "def handle_order_fill(" in line:
            in_method = True
            method_indent = len(line) - len(line.lstrip())
            continue
        if in_method and "def " in line and "def handle_order_fill(" not in line:
            # 下一个方法
            break
        if in_method and "with self._order_lock:" in line:
            lock_start = i + 1  # 1-based
            lock_indent = len(line) - len(line.lstrip())
            # 找锁块结束 (回到与 lock_indent 同级的 dedent)
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                next_indent = len(next_line) - len(next_line.lstrip())
                # 锁块结束条件: 缩进回到 lock_indent 或更小, 且非空行/注释
                if next_line.strip() and not next_line.strip().startswith("#"):
                    if next_indent <= lock_indent:
                        lock_end = j  # 锁块结束 (上一行是最后一行, 1-based j+1-1=j)
                        break
            if lock_end is None:
                lock_end = len(lines)
            return lock_start, lock_end

    raise RuntimeError("未找到 handle_order_fill._order_lock 块")


def generate_phase1_replacement() -> str:
    """生成阶段 1 (锁内) 替代代码"""
    return '''            # R187-A 3 阶段拆锁 - 阶段 1: 锁内仅做状态机修改 + publish_args 快照
            # Why: 原 L2597-2677 81 行持锁 → 100+ 成交/秒场景 12+ 线程阻塞
            # Fix: 阶段 1 锁内只做核心 mutation (~10 行) + 失败 flag; 阶段 2 锁外做
            #      埋点 + 持久化回滚; 阶段 3 锁外 persist + publish (R177 模板).
            # 关联铁律: R8 §8.1 #2 (publish 锁外) + R51 #5 (持久化降级) +
            #          R104 §12 #3+#5 (锁嵌套 AST 递归) + R132-HVD-003 (锁外持久化).
            with self._order_lock:
                # 阶段 1.1: 累加 + 平均价 (必须锁内, 修改 order 状态)
                prev_qty = order.filled_quantity
                prev_price = order.filled_price
                prev_status = order.order_status
                order.filled_quantity += fill_quantity
                if prev_qty > 0:
                    order.filled_price = (order.filled_price * prev_qty + fill_price * fill_quantity) / order.filled_quantity
                else:
                    order.filled_price = fill_price
                order.update_time = datetime.now()

                # 阶段 1.2: 状态机转换 (必须锁内, 决定 _is_fully_filled)
                # 失败时设置 _state_transition_failed 标志, 锁外做埋点 + 持久化回滚
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

                # 阶段 1.3: publish_args 快照 (必须锁内, 防锁外读到不一致状态)
                _is_fully_filled = (order.filled_quantity >= order.order_quantity) and not _state_transition_failed
                asset_type_value = (order.asset_type.value
                                    if getattr(order, 'asset_type', None) is not None
                                    else '')
                if not _current_fill_id:
                    logger.error(f"[NEW-7] fill_id 缺失! order_id={order_id}, 可能导致分笔成交被误去重", exc_info=True)
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

            # R187-A 3 阶段拆锁 - 阶段 2: 锁外状态机失败回滚
            # Why: 状态机失败时的 trace_event + logger + 持久化回滚逻辑不持有 order_lock,
            #      失败回滚路径独立短锁写 prev 状态, 12+ 线程不阻塞.
            if _state_transition_failed:
                # 阶段 2.1: trace_event 埋点 (锁外, R90+ T P0-13/14)
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
                logger.error(
                    f"成交状态转换失败: {order_id} -> {_state_transition_target}, 回滚成交",
                    exc_info=True,
                )
                # 阶段 2.2: 短锁数据回滚 (filled_quantity/price 恢复到 prev)
                with self._order_lock:
                    order.filled_quantity = prev_qty
                    order.filled_price = prev_price
                # 阶段 2.3: 锁外持久化 (R132-HVD-003 模板, _persist_order_externalized)
                self._persist_order_externalized(
                    order,
                    op_name=f"fill_rollback_{_state_transition_target.lower()}",
                    exc_info=True,
                )
                return False

'''


def main():
    lines = read_file_lines()
    print(f"原文件: {FILE_PATH} 共 {len(lines)} 行")

    # 1. 备份
    backup_path = backup_file()
    print(f"备份: {backup_path}")

    # 2. 查找锁块范围
    lock_start, lock_end = find_lock_block_range(lines)
    print(f"锁块范围: L{lock_start}-{lock_end} (共 {lock_end - lock_start + 1} 行)")

    # 3. 校验当前锁块行数 == 81
    if lock_end - lock_start + 1 != 81:
        print(f"⚠️  警告: 锁块行数 {lock_end - lock_start + 1} != 81 (R186-B 报告基线)")
        print(f"  继续执行 (可能 R186-B 报告后已有微调)")

    # 4. 生成阶段 1+2 替代代码
    new_code = generate_phase1_replacement()
    new_lines = new_code.split('\n')

    # 5. 替换 (锁块 L2597-2677 → 新代码)
    # 关键: lines[lock_start-1:lock_end] 替换为 new_lines
    replaced_lines = lines[:lock_start - 1] + [line + '\n' for line in new_lines] + lines[lock_end:]

    # 6. 写回文件
    write_file_lines(replaced_lines)
    print(f"已写入: 锁内 81 行 → {len(new_lines)} 行 (阶段 1: 锁内 + 阶段 2: 锁外)")

    # 7. 验证
    print("\n验证: 重新读取并查找锁块...")
    verify_lines = read_file_lines()
    try:
        new_lock_start, new_lock_end = find_lock_block_range(verify_lines)
        new_lock_body = new_lock_end - new_lock_start + 1
        print(f"新锁块范围: L{new_lock_start}-{new_lock_end} (共 {new_lock_body} 行)")
        if new_lock_body <= 30:
            print(f"✅ 锁内代码: 81 → {new_lock_body} 行 (-{81 - new_lock_body} 行, -{int((81 - new_lock_body) / 81 * 100)}%)")
            print(f"✅ R187-A 3 阶段拆锁目标达成 (< 30 行)")
        else:
            print(f"❌ 锁内代码仍 {new_lock_body} 行, 未达成 < 30 行目标")
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
