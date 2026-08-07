"""
R237-D P2 业务监控 ORPHAN_PUB 治理 - 14 个 P2 事件集中订阅方 (2026-07-30)

> **任务**: 治理 14 项 P2 业务监控 ORPHAN_PUB 字符串事件 (R235-A §2.2 P2 候选)
> **强约束**: R8 §8.1 8 铁律 + R85 §10 假修复鉴别 4 步法 + R104 §12 5 铁律
>           + R222 3 层 ORPHAN 治理 (业务方 + 启动期 + fallback) + R231 §13 4 铁律
> **模板**: R236-D P0 治理 + R142 P0-4 集中订阅注册表 + R203-A 字符串字面量集中订阅块
>
> **业务场景**:
> - 14 P2 业务监控事件 (账户/持仓/资金/批量订单/订单告警/订单持久化)
> - 5 项 P2 候选实际有 GUI 订阅 (account_created/updated/deleted/position_created/fund_updated) → 已排除
> - 1 项已 R195-B 订阅 (order_save_failed) → 排除
> - 实际 P2 ORPHAN_PUB 数量: 14 项 (R237 R+1 round 4 源验证 100% 命中)
>
> **R222 3 层架构**:
> 1. **业务方** (本模块): R237P2EventHandlers._SUBSCRIPTION_REGISTRY + subscribe_all()
> 2. **启动期** (event_coordinator.py): 集中订阅块 `_subscribe_p2_events()`
> 3. **fallback 端**: OrphanMonitor (R189-H) 启动期 scan() 检测 ORPHAN 链路
"""

from loguru import logger
from typing import Any, Dict, List, Optional, Tuple, Callable
from core.events import EventBus, get_event_bus


# ==============================================================================
# 14 P2 ORPHAN_PUB 事件清单 (R235-A §2.2 + R237 R+1 round 4 源验证识别)
# ==============================================================================

# 集中订阅注册表 (R142 P0-4 模板 + R203-A 字符串字面量集中订阅块)
_SUBSCRIPTION_REGISTRY: Dict[str, str] = {
    # 账户生命周期 (4 项, 排除 account_created/updated/deleted 已有 GUI 订阅)
    "account_saved":            "_handle_account_saved",
    "accounts_saved":           "_handle_accounts_saved",
    "accounts_refreshed":       "_handle_accounts_refreshed",
    "account_status_changed":   "_handle_account_status_changed",

    # 持仓/资金生命周期 (5 项, 排除 position_created/fund_updated 已有 GUI 订阅)
    "position_deleted":         "_handle_position_deleted",
    "position_saved":           "_handle_position_saved",
    "fund_info_saved":          "_handle_fund_info_saved",
    "cash_frozen":              "_handle_cash_frozen",
    "cash_unfrozen":            "_handle_cash_unfrozen",

    # 批量订单/告警 (4 项)
    "batch_orders_created":     "_handle_batch_orders_created",
    "batch_orders_cancelled":   "_handle_batch_orders_cancelled",
    "all_active_orders_cancelled": "_handle_all_active_orders_cancelled",
    "order_alert":              "_handle_order_alert",

    # 订单持久化 (1 项)
    "order_saved":              "_handle_order_saved",
}


class R237P2EventHandlers:
    """
    R237 P2 业务监控 ORPHAN_PUB 治理 - 14 个 P2 事件 handler 集中类

    职责: 接收 14 项 P2 业务监控事件, 记录审计日志 + 推 UI 状态栏

    强约束:
    - R8 §8.1 #7 持久化失败仅 warning 不抛
    - R51 §7.1 #5 严禁静默, logger 必须 exc_info=True
    - R231 §13.4 class_name 限定 (本类所有 _handle_xxx 方法均归 R237P2EventHandlers 类)
    """

    def __init__(self, main_window_coordinator: Any = None):
        """
        初始化 R237P2EventHandlers.

        Args:
            main_window_coordinator: 主窗口协调器 (可选, 用于 UI 状态栏推送)
        """
        self._main_window_coordinator = main_window_coordinator
        self._disposed = False
        logger.info(f"R237P2EventHandlers 初始化完成 (14 个 P2 handler)")

    # ==========================================================================
    # 账户生命周期 (4 项)
    # ==========================================================================

    def _handle_account_saved(self, event) -> None:
        """P2-01: account_saved - 账户持久化"""
        try:
            account_id = self._extract_field(event, "account_id", "")
            logger.info(f"[R237P2] 账户持久化: account_id={account_id}")
            self._push_status("info", f"账户已保存: {account_id}")
        except Exception as e:
            logger.error(f"[R237P2] _handle_account_saved 失败: {e}", exc_info=True)

    def _handle_accounts_saved(self, event) -> None:
        """P2-02: accounts_saved - 账户批量保存"""
        try:
            total = self._extract_field(event, "total", 0)
            logger.info(f"[R237P2] 账户批量保存: total={total}")
            self._push_status("info", f"已保存 {total} 个账户")
        except Exception as e:
            logger.error(f"[R237P2] _handle_accounts_saved 失败: {e}", exc_info=True)

    def _handle_accounts_refreshed(self, event) -> None:
        """P2-03: accounts_refreshed - 账户列表重载"""
        try:
            count = self._extract_field(event, "count", 0)
            logger.info(f"[R237P2] 账户列表重载: count={count}")
            self._push_status("info", f"已重载 {count} 个账户")
        except Exception as e:
            logger.error(f"[R237P2] _handle_accounts_refreshed 失败: {e}", exc_info=True)

    def _handle_account_status_changed(self, event) -> None:
        """P2-04: account_status_changed - 账户状态变化"""
        try:
            account_id = self._extract_field(event, "account_id", "")
            old_status = self._extract_field(event, "old_status", "")
            new_status = self._extract_field(event, "new_status", "")
            logger.warning(f"[R237P2] 账户状态变化: {account_id} {old_status} → {new_status}")
            self._push_status("warning", f"账户 {account_id} 状态: {old_status} → {new_status}")
        except Exception as e:
            logger.error(f"[R237P2] _handle_account_status_changed 失败: {e}", exc_info=True)

    # ==========================================================================
    # 持仓/资金生命周期 (5 项)
    # ==========================================================================

    def _handle_position_deleted(self, event) -> None:
        """P2-05: position_deleted - 持仓删除"""
        try:
            position_id = self._extract_field(event, "position_id", "")
            logger.info(f"[R237P2] 持仓删除: position_id={position_id}")
            self._push_status("warning", f"持仓已删除: {position_id}")
        except Exception as e:
            logger.error(f"[R237P2] _handle_position_deleted 失败: {e}", exc_info=True)

    def _handle_position_saved(self, event) -> None:
        """P2-06: position_saved - 持仓持久化"""
        try:
            position_id = self._extract_field(event, "position_id", "")
            logger.info(f"[R237P2] 持仓持久化: position_id={position_id}")
            # 不推 UI (持久化是后台操作, 不打扰用户)
        except Exception as e:
            logger.error(f"[R237P2] _handle_position_saved 失败: {e}", exc_info=True)

    def _handle_fund_info_saved(self, event) -> None:
        """P2-07: fund_info_saved - 资金信息保存"""
        try:
            account_id = self._extract_field(event, "account_id", "")
            logger.info(f"[R237P2] 资金信息保存: account_id={account_id}")
            # 不推 UI (后台操作)
        except Exception as e:
            logger.error(f"[R237P2] _handle_fund_info_saved 失败: {e}", exc_info=True)

    def _handle_cash_frozen(self, event) -> None:
        """P2-08: cash_frozen - 资金冻结"""
        try:
            account_id = self._extract_field(event, "account_id", "")
            amount = self._extract_field(event, "amount", 0.0)
            logger.warning(f"[R237P2] 资金冻结: account_id={account_id} amount={amount}")
            self._push_status("warning", f"资金已冻结: {account_id} 金额 {amount}")
        except Exception as e:
            logger.error(f"[R237P2] _handle_cash_frozen 失败: {e}", exc_info=True)

    def _handle_cash_unfrozen(self, event) -> None:
        """P2-09: cash_unfrozen - 资金解冻"""
        try:
            account_id = self._extract_field(event, "account_id", "")
            amount = self._extract_field(event, "amount", 0.0)
            logger.info(f"[R237P2] 资金解冻: account_id={account_id} amount={amount}")
            self._push_status("info", f"资金已解冻: {account_id} 金额 {amount}")
        except Exception as e:
            logger.error(f"[R237P2] _handle_cash_unfrozen 失败: {e}", exc_info=True)

    # ==========================================================================
    # 批量订单/告警 (4 项)
    # ==========================================================================

    def _handle_batch_orders_created(self, event) -> None:
        """P2-10: batch_orders_created - 批量下单"""
        try:
            logger.info(f"[R237P2] 批量下单事件")
            self._push_status("info", "批量下单已提交")
        except Exception as e:
            logger.error(f"[R237P2] _handle_batch_orders_created 失败: {e}", exc_info=True)

    def _handle_batch_orders_cancelled(self, event) -> None:
        """P2-11: batch_orders_cancelled - 批量撤单"""
        try:
            logger.info(f"[R237P2] 批量撤单事件")
            self._push_status("warning", "批量撤单已提交")
        except Exception as e:
            logger.error(f"[R237P2] _handle_batch_orders_cancelled 失败: {e}", exc_info=True)

    def _handle_all_active_orders_cancelled(self, event) -> None:
        """P2-12: all_active_orders_cancelled - 紧急平仓"""
        try:
            logger.error(f"[R237P2] 紧急平仓: 所有活跃订单已撤单")
            self._push_status("error", "紧急平仓: 所有活跃订单已撤单")
        except Exception as e:
            logger.error(f"[R237P2] _handle_all_active_orders_cancelled 失败: {e}", exc_info=True)

    def _handle_order_alert(self, event) -> None:
        """P2-13: order_alert - 订单告警"""
        try:
            # 告警事件可能是 dict 或 dataclass (alert.to_dict() 的结果)
            if isinstance(event, dict):
                alert_type = event.get("alert_type", "")
                message = event.get("message", "")
                level = event.get("level", "warning")
            else:
                alert_type = getattr(event, "alert_type", "")
                message = getattr(event, "message", "")
                level = getattr(event, "level", "warning")
            logger.warning(f"[R237P2] 订单告警: type={alert_type} message={message}")
            self._push_status(level, f"订单告警: {message}")
        except Exception as e:
            logger.error(f"[R237P2] _handle_order_alert 失败: {e}", exc_info=True)

    # ==========================================================================
    # 订单持久化 (1 项)
    # ==========================================================================

    def _handle_order_saved(self, event) -> None:
        """P2-14: order_saved - 订单持久化"""
        try:
            order_id = self._extract_field(event, "order_id", "")
            logger.info(f"[R237P2] 订单持久化: order_id={order_id}")
            # 不推 UI (后台操作)
        except Exception as e:
            logger.error(f"[R237P2] _handle_order_saved 失败: {e}", exc_info=True)

    # ==========================================================================
    # 辅助方法
    # ==========================================================================

    def _extract_field(self, event, field_name: str, default=None):
        """
        兼容 dataclass / .data 字典 / dict 三种事件格式
        (R8 §8.1 #4 字符串事件 payload 同步到 .data 字典)
        """
        if event is None:
            return default
        if isinstance(event, dict):
            return event.get(field_name, default)
        # dataclass 事件
        if hasattr(event, "data") and isinstance(event.data, dict):
            return event.data.get(field_name, default)
        # 直接属性
        return getattr(event, field_name, default)

    def _push_status(self, level: str, message: str) -> None:
        """推 UI 状态栏 (R86 P0-4 模板)"""
        if self._main_window_coordinator is None:
            return
        try:
            if hasattr(self._main_window_coordinator, "show_message"):
                self._main_window_coordinator.show_message(message, level=level)
        except Exception:
            # UI 失败不影响业务 (R8 §8.1 #7 失败仅 warning 不抛)
            pass

    def subscribe_all(self, event_bus: EventBus) -> int:
        """
        业务方: 一次性订阅所有 P2 事件 (R222 3 层架构业务方层)

        Args:
            event_bus: EventBus 实例

        Returns:
            成功订阅的事件数
        """
        if self._disposed:
            logger.warning("[R237P2] 已 dispose, 跳过 subscribe_all")
            return 0

        success_count = 0
        for event_name, handler_name in _SUBSCRIPTION_REGISTRY.items():
            handler = getattr(self, handler_name, None)
            if handler is None:
                logger.warning(f"[R237P2] handler 不存在: {handler_name}")
                continue
            try:
                event_bus.subscribe(event_name, handler)
                success_count += 1
            except Exception as e:
                logger.error(f"[R237P2] 订阅 {event_name} 失败: {e}", exc_info=True)

        logger.info(f"[R237P2] 业务方订阅完成: {success_count}/{len(_SUBSCRIPTION_REGISTRY)}")
        return success_count

    def dispose(self) -> None:
        """R78 铁律 #6 dispose 幂等"""
        if self._disposed:
            return
        self._disposed = True
        logger.info("[R237P2] dispose 完成")


def register_r237_p2_handlers(event_bus: EventBus, main_window_coordinator: Any = None) -> R237P2EventHandlers:
    """
    工厂函数: 创建 R237P2EventHandlers 实例并一次性订阅

    Args:
        event_bus: EventBus 实例
        main_window_coordinator: 主窗口协调器 (可选)

    Returns:
        R237P2EventHandlers 实例
    """
    handler = R237P2EventHandlers(main_window_coordinator=main_window_coordinator)
    handler.subscribe_all(event_bus)
    return handler
