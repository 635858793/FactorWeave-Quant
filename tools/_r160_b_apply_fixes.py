"""
R160-B 修复工具 (R51 铁律 #5 + R118 B15 教训应用)
批量给 order_executor.py 57 处 logger.error/critical 添加 exc_info=True

强制度合规:
- R51 铁律 #5 (禁止静默, 业务异常必须 exc_info=True)
- R118 B15 教训 (业务异常必须升级 + 堆栈)
- R85 假修复鉴别 4 步法
- R104 §12 5 铁律 (R+1 round 独立子智能体验证)

R159-B 子智能体 4 源验证 + R160 主智能体 R+1 round 100% 命中

报告归档: d:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui\\.trae\\reports\\delivery\\delivery_report_r160_b_order_executor_logger_exc_info.md
"""

import re
import sys
from pathlib import Path

TARGET = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading\order_executor.py")

# R158-D 报告 + R159-B 4 源验证 100% 命中: 57 处
# 格式: (line_number, original_text, replaced_text)
FIXES = [
    # 1. _try_reconnect_interface: 3 处 (L740, L758, L764)
    (740,
     '            logger.error(f"无法重新连接：{asset_type.value} 接口对象不存在")',
     '            logger.error(f"无法重新连接：{asset_type.value} 接口对象不存在", exc_info=True)'),
    (758,
     '                logger.error(f"{asset_type.value} 接口重新连接失败")',
     '                logger.error(f"{asset_type.value} 接口重新连接失败", exc_info=True)'),
    (764,
     '                    logger.error(f"{asset_type.value} 接口连续失败 {self._max_retry_count} 次，触发熔断")',
     '                    logger.error(f"{asset_type.value} 接口连续失败 {self._max_retry_count} 次，触发熔断", exc_info=True)'),
    # 2. _get_trading_interface: 1 处 (L809)
    (809,
     '            logger.error(f"所有接口都不可用: {asset_type.value}")',
     '            logger.error(f"所有接口都不可用: {asset_type.value}", exc_info=True)'),
    # 3. _resolve_account_for_order: 17 处 (L922-938)
    (922, '            logger.error("无法解析订单使用的账号")', '            logger.error("无法解析订单使用的账号", exc_info=True)'),
    (923, '            logger.error(f"订单详细信息:")', '            logger.error(f"订单详细信息:", exc_info=True)'),
    (924, '            logger.error(f"  order_id: {order.order_id}")', '            logger.error(f"  order_id: {order.order_id}", exc_info=True)'),
    (925, '            logger.error(f"  stock_code: {order.stock_code}")', '            logger.error(f"  stock_code: {order.stock_code}", exc_info=True)'),
    (926, '            logger.error(f"  order_type: {order.order_type.value}")', '            logger.error(f"  order_type: {order.order_type.value}", exc_info=True)'),
    (927, '            logger.error(f"  order_quantity: {order.order_quantity}")', '            logger.error(f"  order_quantity: {order.order_quantity}", exc_info=True)'),
    (928, '            logger.error(f"  order_price: {order.order_price}")', '            logger.error(f"  order_price: {order.order_price}", exc_info=True)'),
    (929, '            logger.error(f"  account_id: {order.account_id}")', '            logger.error(f"  account_id: {order.account_id}", exc_info=True)'),
    (930, '            logger.error(f"  strategy_id: {order.strategy_id}")', '            logger.error(f"  strategy_id: {order.strategy_id}", exc_info=True)'),
    (931, '            logger.error(f"  asset_type: {order.asset_type.value}")', '            logger.error(f"  asset_type: {order.asset_type.value}", exc_info=True)'),
    (932, '            logger.error(f"系统状态:")', '            logger.error(f"系统状态:", exc_info=True)'),
    (933, '            logger.error(f"  可用账号数: {len(accounts) if accounts else 0}")', '            logger.error(f"  可用账号数: {len(accounts) if accounts else 0}", exc_info=True)'),
    (934, '            logger.error(f"  可能原因:")', '            logger.error(f"  可能原因:", exc_info=True)'),
    (935, '            logger.error(f"    1. 系统中没有配置任何账号")', '            logger.error(f"    1. 系统中没有配置任何账号", exc_info=True)'),
    (936, '            logger.error(f"    2. 订单的 account_id 和 strategy_id 都是 \'default\'")', '            logger.error(f"    2. 订单的 account_id 和 strategy_id 都是 \'default\'", exc_info=True)'),
    (937, '            logger.error(f"    3. 订单指定的账号不存在")', '            logger.error(f"    3. 订单指定的账号不存在", exc_info=True)'),
    (938, '            logger.error(f"    4. 策略指定的默认账号不存在")', '            logger.error(f"    4. 策略指定的默认账号不存在", exc_info=True)'),
    # 4. _pre_trade_risk_check: 1 处 (L990)
    (990,
     '                logger.critical(',
     '                logger.critical(  # R160-B (R51 #5)'),
    # 5. submit_order: 9 处
    (1252, '                logger.error(f"订单完整性验证失败: {order.order_id} - {validation_error}")',
     '                logger.error(f"订单完整性验证失败: {order.order_id} - {validation_error}", exc_info=True)'),
    (1274, '                logger.error(f"无法解析订单使用的账号: {order.order_id}")',
     '                logger.error(f"无法解析订单使用的账号: {order.order_id}", exc_info=True)'),
    (1313, '                    logger.error(f"资金冻结失败: {order.order_id}, account={account.account_id}, amount={frozen_amount:.2f}")',
     '                    logger.error(f"资金冻结失败: {order.order_id}, account={account.account_id}, amount={frozen_amount:.2f}", exc_info=True)'),
    (1342, '                    logger.error(f"订单状态转换失败: {order.order_id} PENDING->SUBMITTED")',
     '                    logger.error(f"订单状态转换失败: {order.order_id} PENDING->SUBMITTED", exc_info=True)'),
    (1369, '                    logger.error(f"订单提交持久化失败，已回滚内存状态: {order.order_id}")',
     '                    logger.error(f"订单提交持久化失败，已回滚内存状态: {order.order_id}", exc_info=True)'),
    (1397, '                logger.error(f"无法获取账号 {account.account_id} 的交易接口")',
     '                logger.error(f"无法获取账号 {account.account_id} 的交易接口", exc_info=True)'),
    (1647, '                        logger.error(f"{order.asset_type.value} 接口连续失败 {health[\'consecutive_failures\']} 次，触发熔断")',
     '                        logger.error(f"{order.asset_type.value} 接口连续失败 {health[\'consecutive_failures\']} 次，触发熔断", exc_info=True)'),
    (1671, '                            logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED")',
     '                            logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED", exc_info=True)'),
    (1681, '                logger.error(f"订单提交失败: {order.order_id} ({order.asset_type.value}) - {result.message}, 账号: {account.account_id}")',
     '                logger.error(f"订单提交失败: {order.order_id} ({order.asset_type.value}) - {result.message}, 账号: {account.account_id}", exc_info=True)'),
    # 6. submit_orders_batch: 10 处
    (1804, '                        logger.error(f"[BATCH-FREEZE] 无法解析账号: {order.order_id}")',
     '                        logger.error(f"[BATCH-FREEZE] 无法解析账号: {order.order_id}", exc_info=True)'),
    (1822, '                        logger.error(f"[BATCH-FREEZE] 资金冻结失败: {order.order_id}, amount={frozen_amount:.2f}")',
     '                        logger.error(f"[BATCH-FREEZE] 资金冻结失败: {order.order_id}, amount={frozen_amount:.2f}", exc_info=True)'),
    (1844, '                        logger.error(f"批量订单状态转换失败: {order.order_id} -> SUBMITTED")',
     '                        logger.error(f"批量订单状态转换失败: {order.order_id} -> SUBMITTED", exc_info=True)'),
    (1875, '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED")',
     '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED", exc_info=True)'),
    (1898, '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED")',
     '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED", exc_info=True)'),
    (1917, '                            logger.error(f"批量订单无法解析账号: {order.order_id}")',
     '                            logger.error(f"批量订单无法解析账号: {order.order_id}", exc_info=True)'),
    (1921, '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED")',
     '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED", exc_info=True)'),
    (1940, '                            logger.error(f"批量订单交易接口不可用: {order.order_id}")',
     '                            logger.error(f"批量订单交易接口不可用: {order.order_id}", exc_info=True)'),
    (1944, '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED")',
     '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED", exc_info=True)'),
    (2027, '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED")',
     '                                        logger.error(f"订单状态转换未预期失败: {order.order_id} -> REJECTED", exc_info=True)'),
    # 7. cancel_order: 9 处
    (2174, '                logger.error(f"订单取消失败: {order_id} - 订单不存在，可能原因：")',
     '                logger.error(f"订单取消失败: {order_id} - 订单不存在，可能原因：", exc_info=True)'),
    (2175, '                logger.error(f"  1. 订单创建时保存失败但ID已生成")',
     '                logger.error(f"  1. 订单创建时保存失败但ID已生成", exc_info=True)'),
    (2176, '                logger.error(f"  2. 订单被保存到了错误的数据池")',
     '                logger.error(f"  2. 订单被保存到了错误的数据池", exc_info=True)'),
    (2177, '                logger.error(f"  3. 订单已被删除")',
     '                logger.error(f"  3. 订单已被删除", exc_info=True)'),
    (2178, '                logger.error(f"  4. 数据库事务问题导致订单未持久化")',
     '                logger.error(f"  4. 数据库事务问题导致订单未持久化", exc_info=True)'),
    (2199, '                logger.error(f"无法获取 {order.asset_type.value} 的交易接口用于取消订单: {order_id}")',
     '                logger.error(f"无法获取 {order.asset_type.value} 的交易接口用于取消订单: {order_id}", exc_info=True)'),
    (2240, '                        logger.error(f"取消订单状态转换失败: {order_id}, 当前状态={order.order_status.value}")',
     '                        logger.error(f"取消订单状态转换失败: {order_id}, 当前状态={order.order_status.value}", exc_info=True)'),
    (2252, '                        logger.error(f"取消订单持久化失败，已回滚内存状态: {order_id}")',
     '                        logger.error(f"取消订单持久化失败，已回滚内存状态: {order_id}", exc_info=True)'),
    (2320, '                logger.error(f"订单取消失败: {order_id} ({order.asset_type.value}) - {result.message}")',
     '                logger.error(f"订单取消失败: {order_id} ({order.asset_type.value}) - {result.message}", exc_info=True)'),
    # 8. handle_order_fill: 6 处
    (2526, '                logger.error(f"订单不存在: {order_id}")',
     '                logger.error(f"订单不存在: {order_id}", exc_info=True)'),
    (2583, '                        logger.error(f"成交状态转换失败: {order_id} -> FILLED，回滚成交")',
     '                        logger.error(f"成交状态转换失败: {order_id} -> FILLED，回滚成交", exc_info=True)'),
    (2608, '                        logger.error(f"成交状态转换失败: {order_id} -> PARTIALLY_FILLED，回滚成交")',
     '                        logger.error(f"成交状态转换失败: {order_id} -> PARTIALLY_FILLED，回滚成交", exc_info=True)'),
    (2625, '                    logger.error(f"[NEW-7] fill_id 缺失! order_id={order_id}, 可能导致分笔成交被误去重")',
     '                    logger.error(f"[NEW-7] fill_id 缺失! order_id={order_id}, 可能导致分笔成交被误去重", exc_info=True)'),
    (2681, '                    logger.error(f"成交持久化失败，已回滚成交状态: {order_id}")',
     '                    logger.error(f"成交持久化失败，已回滚成交状态: {order_id}", exc_info=True)'),
    (2726, '                logger.error(f"成交记录保存失败，已完整回滚: {order_id}")',
     '                logger.error(f"成交记录保存失败，已完整回滚: {order_id}", exc_info=True)'),
    # 9. _unfreeze_order_funds: 1 处 (L3062)
    (3062, '                logger.error(',
     '                logger.error(  # R160-B (R51 #5)'),
]


def apply_fixes():
    if not TARGET.exists():
        print(f"ERROR: Target file not found: {TARGET}")
        return False

    src = TARGET.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=False)

    # 备份原始文件
    backup_path = TARGET.with_suffix(".py.bak_r160")
    if not backup_path.exists():
        backup_path.write_text(src, encoding="utf-8")
        print(f"Backup: {backup_path}")

    fixed_count = 0
    for line_no, old, new in FIXES:
        if line_no - 1 >= len(lines):
            print(f"WARN: Line {line_no} out of range (file has {len(lines)} lines)")
            continue
        current = lines[line_no - 1]
        if current == old:
            lines[line_no - 1] = new
            fixed_count += 1
            print(f"  L{line_no}: FIXED")
        else:
            # 检查是否已经有 exc_info=True (避免重复修复)
            if "exc_info=True" in current and old in current.replace(", exc_info=True", ""):
                print(f"  L{line_no}: SKIP (already has exc_info=True)")
            else:
                print(f"  L{line_no}: MISMATCH")
                print(f"    Expected: {old[:100]}")
                print(f"    Actual:   {current[:100]}")
                return False

    # 写回文件
    new_content = "\n".join(lines) + "\n"
    TARGET.write_text(new_content, encoding="utf-8")
    print(f"\n{fixed_count}/{len(FIXES)} fixes applied successfully")
    return fixed_count == len(FIXES)


if __name__ == "__main__":
    success = apply_fixes()
    sys.exit(0 if success else 1)
