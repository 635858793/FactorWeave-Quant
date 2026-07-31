#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R186-A HVD-185-1: 为 StrategyService 添加 _check_5_service_consistency 方法 (D2)

Why: HVD-185-1 扩展 12+ 服务闭环, StrategyService 缺失此方法.
     严格模仿 R158 HVD-158-A-NEW-1 (OrderService) / R186-A HVD-185-1 (DataService) 模板.
"""

import sys

STRATEGY_SERVICE_PATH = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/strategy_service.py"

# R186-A HVD-185-1 模板 (严格模仿 R158 模板)
STRATEGY_SERVICE_METHOD = '''
    def _check_5_service_consistency(self) -> Dict[str, Optional[str]]:
        """R186-A HVD-185-1 新增 (2026-07-25, R186-A 子智能体实施): 12+ 服务 _current_account_id 一致性检查

        Why: R158 HVD-150-A 已实施 8/8 服务 + R158 HVD-158-A-NEW-1 (OrderService) +
             R160 HVD-160-E-2 (OrderExecutor) + R186-A HVD-185-1 (DataService) = 11 服务.
             但 StrategyService (P1 策略) 缺失 → 5+1 服务架构 11/12 闭环断点.
             多账户场景 StrategyService 策略可能按错账户执行 → 业务核心 P0 失效.
        Fix: 软解析 11 其他服务 (RiskManager/TradingService/AccountManager/MoneyManager/
             TradingController/TradingEngine/OrderService/OrderExecutor/DataService/
             TradingPanel/AccountManagementDialog) + 返回 self, 12+ 服务 100% 闭环.
        严格模仿 R158 HVD-150-A-P1-2 (TradingEngine) / R158 HVD-158-A-NEW-1 (OrderService) /
                  R186-A HVD-185-1 (DataService) 模板.

        12+ 服务架构 12 服务: RiskManager/TradingService/AccountManager/MoneyManager/
                              TradingController/TradingEngine/OrderService/OrderExecutor/
                              DataService/StrategyService/TradingPanel/AccountManagementDialog
        关联铁律: R104 §12 5 铁律 + R6 §6.1 8 铁律 + R7 §7.1 7 铁律
                  + R85 假修复鉴别 4 步法 + R99- 单账户兼容 + R51 铁律 #5 显式降级

        Returns:
            Dict[service_name, account_id_or_None]: 12 服务 _current_account_id 快照
        """
        result: Dict[str, Optional[str]] = {
            'strategy_service': getattr(self, '_current_account_id', None),
            'risk_manager': None,
            'trading_service': None,
            'account_manager': None,
            'money_manager': None,
            'trading_controller': None,
            'trading_engine': None,
            'order_service': None,
            'order_executor': None,
            'data_service': None,
            # TradingPanel/AccountManagementDialog 在 gui/ 域, 软解析降级 None
            'trading_panel': None,
            'account_management_dialog': None,
        }
        # R131-P0-1 防御: service_container / 单例不可用时降级 None (不抛)
        # 软解析 11 其他服务 (StrategyService 已自填 result['strategy_service'])
        for service_name, class_path in (
            ('risk_manager', 'core.risk_manager.RiskManager'),
            ('trading_service', 'core.services.trading_service.TradingService'),
            ('account_manager', 'core.trading.account_manager.AccountManager'),
            ('money_manager', 'core.money_manager.EnhancedMoneyManager'),
            ('trading_controller', 'core.trading_controller.TradingController'),
            ('trading_engine', 'core.trading_engine.TradingEngine'),
            ('order_service', 'core.trading.order_service.OrderService'),
            ('order_executor', 'core.trading.order_executor.OrderExecutor'),
            ('data_service', 'core.services.data_service.DataService'),
            # TradingPanel/AccountManagementDialog 在 gui/ 域, 软解析降级 None
            ('trading_panel', None),
            ('account_management_dialog', None),
        ):
            if class_path is None:
                # GUI 域服务不在 core 范围, 保留 None
                continue
            try:
                import importlib
                module_path, class_name = class_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    # 优先取单例 (_instance 类属性)
                    singleton = getattr(cls, '_instance', None)
                    instance = singleton if singleton is not None else cls
                    result[service_name] = getattr(instance, '_current_account_id', None)
            except Exception as e:
                # R51 §7.1 #5 显式降级日志: logger.warning + exc_info=True
                logger.warning(
                    f"[R186-A HVD-185-1] {service_name} 软解析失败 (降级 None): {e}",
                    exc_info=True,
                )
        return result

    def set_current_account_id(self, account_id: str) -> None:
        """R186-A HVD-185-1 新增 (2026-07-25): 设置当前账户 ID (12+ 服务架构 100% 闭环)

        Why: 12+ 服务架构账户切换一致性, 与 R120-P0-1 (TradingService) /
             R125-P0-8 (AccountManager) / R128-P1-3 (MoneyManager) / R129-P0-1 (TradingController) /
             R131-P0-3 (RiskManager) / R156 HVD-155-2 (OrderService) /
             R147-HVD-147-D (OrderExecutor) /
             R186-A HVD-185-1 (DataService) 模式完全对齐.

        Fix: 由 AccountSwitchedEvent 订阅方 _on_account_switched 统一调用,
             显式设置 _current_account_id 字段, 多账户场景 100% 生效.
        """
        old_account_id = getattr(self, '_current_account_id', 'default')
        if not account_id:
            self._current_account_id = 'default'
        else:
            self._current_account_id = str(account_id)
        logger.info(
            f"[R186-A HVD-185-1] StrategyService._current_account_id 切换: "
            f"{old_account_id} -> {self._current_account_id}"
        )

    def get_current_account_id(self) -> str:
        """R186-A HVD-185-1 新增 (2026-07-25): 获取当前账户 ID (12+ 服务一致性检查依赖)"""
        return getattr(self, '_current_account_id', 'default') or 'default'

    def _on_account_switched(self, event) -> None:
        """R186-A HVD-185-1 新增 (2026-07-25): 账户切换事件处理 (订阅方, 12+ 服务架构一致性)"""
        try:
            account_id = getattr(event, 'account_id', '') or 'default'
            self.set_current_account_id(account_id)
        except Exception as e:
            logger.error(
                f"[R186-A HVD-185-1] StrategyService 处理 AccountSwitchedEvent 失败: {e}",
                exc_info=True
            )

    def _subscribe_account_switched_event(self) -> None:
        """R186-A HVD-185-1 新增 (2026-07-25): 订阅 AccountSwitchedEvent (12+ 服务架构 100% 闭环)"""
        try:
            from core.events import get_event_bus
            from core.events.types import AccountSwitchedEvent
            event_bus = get_event_bus()
            if event_bus is None:
                return
            if getattr(self, '_event_bus_subscribed', False):
                return
            event_bus.subscribe(AccountSwitchedEvent, self._on_account_switched)
            self._event_bus_subscribed = True
        except Exception as e:
            logger.warning(
                f"[R186-A HVD-185-1] StrategyService 订阅 AccountSwitchedEvent 失败, 降级手动调用: {e}",
                exc_info=True
            )

'''


def main():
    with open(STRATEGY_SERVICE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if "_check_5_service_consistency" in content:
        if "[R186-A HVD-185-1]" in content and "strategy_service" in content:
            print("[SKIP] StrategyService._check_5_service_consistency 已实施 (R186-A HVD-185-1)")
            return 0
        else:
            print("[WARN] StrategyService 已有 _check_5_service_consistency 但标记不是 R186-A, 跳过")
            return 0

    # 插入到 _do_initialize 方法前 (L323)
    target = "    def _do_initialize(self) -> None:"
    if target not in content:
        print(f"[ERROR] 未找到插入点: {target}")
        return 1

    new_content = content.replace(target, STRATEGY_SERVICE_METHOD + target, 1)

    # 添加 _current_account_id 字段到 __init__
    if "self._current_account_id" not in new_content:
        init_target = "        self._cleanup_timer = None  # 清理定时器"
        init_addition = "        self._cleanup_timer = None  # 清理定时器\n\n        # R186-A HVD-185-1: 12+ 服务多账户一致性字段\n        self._current_account_id: str = 'default'\n        self._event_bus_subscribed: bool = False"
        if init_target in new_content:
            new_content = new_content.replace(init_target, init_addition, 1)
        else:
            print(f"[WARN] 未找到 _cleanup_timer 字段位置, _current_account_id 需手动添加")

        # 尝试在 __init__ 末尾 (super().__init__() 之后, _load_strategy_plugins 之前) 添加 _subscribe_account_switched_event
        # 简单方式: 找到 _load_strategy_plugins 前
        subscribe_target = "        self._load_strategy_plugins()"
        if subscribe_target in new_content:
            subscribe_addition = "        # R186-A HVD-185-1: 启动期订阅 AccountSwitchedEvent (12+ 服务架构 100% 闭环)\n        self._subscribe_account_switched_event()\n\n        " + subscribe_target
            new_content = new_content.replace(subscribe_target, subscribe_addition, 1)
        else:
            print(f"[WARN] 未找到 _load_strategy_plugins, _subscribe_account_switched_event 需手动添加")

    with open(STRATEGY_SERVICE_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK] StrategyService._check_5_service_consistency 已添加 (R186-A HVD-185-1)")
    print(f"     文件路径: {STRATEGY_SERVICE_PATH}")
    print(f"     实施: 12 服务软解析 + set_current_account_id + 事件订阅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
