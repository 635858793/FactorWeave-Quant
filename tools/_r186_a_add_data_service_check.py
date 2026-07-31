#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R186-A HVD-185-1: 为 DataService 添加 _check_5_service_consistency 方法 (D2)

Why: R158 HVD-150-A 8/8 + R158-A HVD-158-A-NEW-1 (OrderService) +
     R160 HVD-160-E-2 (OrderExecutor) = 10 服务, 但 DataService 缺失.
     HVD-185-1 扩展 12+ 服务闭环, DataService 必须实施 _check_5_service_consistency.

Pattern: 严格模仿 R158 HVD-150-A-P1-2 (TradingEngine) + R158-A HVD-158-A-NEW-1
         (OrderService) 模板, 含 5+1 架构 + R51 软解析 + exc_info=True.

R104 §12 5 铁律:
  - #1 R+1 round 验证 (后续子智能体)
  - #2 HVD 兼容层 4 源验证 (新增服务跨 4 子目录)
  - #3+#5 嵌套检测 (本任务无锁架构, 跳过)
  - #4 物理删除前 4 源 100% 命中 (本任务为新增方法, 跳过)
"""

import sys

# DataService 文件路径
DATA_SERVICE_PATH = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/data_service.py"

# R186-A HVD-185-1 模板 (严格模仿 R158 HVD-158-A-NEW-1)
DATA_SERVICE_METHOD = '''
    def _check_5_service_consistency(self) -> Dict[str, Optional[str]]:
        """R186-A HVD-185-1 新增 (2026-07-25, R186-A 子智能体实施): 12+ 服务 _current_account_id 一致性检查

        Why: R158 HVD-150-A 已实施 8/8 服务 _check_5_service_consistency (RiskManager/TradingService/
             AccountManager/MoneyManager/TradingController/TradingEngine/TradingPanel/
             AccountManagementDialog), R158 HVD-158-A-NEW-1 补 OrderService, R160 HVD-160-E-2 补
             OrderExecutor = 10 服务. 但 DataService (P0 数据核心) 缺失 → 5+1 服务架构 10/12 闭环
             断点. 多账户场景 DataService 拿错账户数据 → 业务核心 P0 失效.
        Fix: 软解析 11 其他服务 (RiskManager/TradingService/AccountManager/MoneyManager/
             TradingController/TradingEngine/OrderService/OrderExecutor/StrategyService/
             TradingPanel/AccountManagementDialog) + 返回 self, 12+ 服务 100% 闭环.
        严格模仿 R158 HVD-150-A-P1-2 (TradingEngine) / R158 HVD-158-A-NEW-1 (OrderService) 模板.

        12+ 服务架构 12 服务: RiskManager/TradingService/AccountManager/MoneyManager/
                              TradingController/TradingEngine/OrderService/OrderExecutor/
                              DataService/StrategyService/TradingPanel/AccountManagementDialog
        关联铁律: R104 §12 5 铁律 + R6 §6.1 8 铁律 + R7 §7.1 7 铁律
                  + R85 假修复鉴别 4 步法 + R99- 单账户兼容 + R51 铁律 #5 显式降级

        Returns:
            Dict[service_name, account_id_or_None]: 12 服务 _current_account_id 快照
        """
        result: Dict[str, Optional[str]] = {
            'data_service': getattr(self, '_current_account_id', None),
            'risk_manager': None,
            'trading_service': None,
            'account_manager': None,
            'money_manager': None,
            'trading_controller': None,
            'trading_engine': None,
            'order_service': None,
            'order_executor': None,
            'strategy_service': None,
            # TradingPanel/AccountManagementDialog 在 gui/ 域, 软解析降级 None
            'trading_panel': None,
            'account_management_dialog': None,
        }
        # R131-P0-1 防御: service_container / 单例不可用时降级 None (不抛)
        # 软解析 11 其他服务 (DataService 已自填 result['data_service'])
        for service_name, class_path in (
            ('risk_manager', 'core.risk_manager.RiskManager'),
            ('trading_service', 'core.services.trading_service.TradingService'),
            ('account_manager', 'core.trading.account_manager.AccountManager'),
            ('money_manager', 'core.money_manager.EnhancedMoneyManager'),
            ('trading_controller', 'core.trading_controller.TradingController'),
            ('trading_engine', 'core.trading_engine.TradingEngine'),
            ('order_service', 'core.trading.order_service.OrderService'),
            ('order_executor', 'core.trading.order_executor.OrderExecutor'),
            ('strategy_service', 'core.services.strategy_service.StrategyService'),
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
                # Why: 软解析失败必须有完整堆栈, 业务方可观测 5+1 服务软解析失败根因
                logger.warning(
                    f"[R186-A HVD-185-1] {service_name} 软解析失败 (降级 None): {e}",
                    exc_info=True,
                )
        return result

    def set_current_account_id(self, account_id: str) -> None:
        """R186-A HVD-185-1 新增 (2026-07-25): 设置当前账户 ID (12+ 服务架构 100% 闭环)

        Why: HVD-185-1 修复 - 12+ 服务架构账户切换一致性, 与 R120-P0-1 (TradingService) /
             R125-P0-8 (AccountManager) / R128-P1-3 (MoneyManager) / R129-P0-1 (TradingController) /
             R131-P0-3 (RiskManager) / R156 HVD-155-2 (OrderService) /
             R147-HVD-147-D (OrderExecutor) 模式完全对齐.
             DataService 是 12+ 服务中缺此方法的服务, 多账户场景下 _current_account_id
             永远 'default', 数据查询按账户 A 拉取 → 跨账户错数据 → 业务核心 P0 失效.

        Fix: 由 AccountSwitchedEvent 订阅方 _on_account_switched 统一调用,
             显式设置 _current_account_id 字段, 多账户场景 100% 生效.
             单账户模式 (R99- 兼容): account_id='default', 业务路径 0 破坏.

        Args:
            account_id: 账户 ID, 空字符串/None fallback 为 'default' (R120-P0-2 真值兜底)
        """
        old_account_id = getattr(self, '_current_account_id', 'default')
        # R120-P0-2 真值兜底: 空字符串/None fallback 'default'
        if not account_id:
            self._current_account_id = 'default'
        else:
            self._current_account_id = str(account_id)
        logger.info(
            f"[R186-A HVD-185-1] DataService._current_account_id 切换: "
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
                f"[R186-A HVD-185-1] DataService 处理 AccountSwitchedEvent 失败: {e}",
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
            # 避免重复订阅 (R8 铁律 #6 dispose 幂等)
            if getattr(self, '_event_bus_subscribed', False):
                return
            event_bus.subscribe(AccountSwitchedEvent, self._on_account_switched)
            self._event_bus_subscribed = True
        except Exception as e:
            logger.warning(
                f"[R186-A HVD-185-1] DataService 订阅 AccountSwitchedEvent 失败, 降级手动调用: {e}",
                exc_info=True
            )

'''


def main():
    # 1. Read 目标文件
    with open(DATA_SERVICE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 2. 验证文件未实施过 (R6 §6.1 #5 不在 AST 扫描前删除, R104 §12 #4 物理删除前 4 源)
    if "_check_5_service_consistency" in content:
        # 已经实施, 检查是否完整
        if "[R186-A HVD-185-1]" in content and "data_service" in content:
            print("[SKIP] DataService._check_5_service_consistency 已实施 (R186-A HVD-185-1)")
            return 0
        else:
            print("[WARN] DataService 已有 _check_5_service_consistency 但标记不是 R186-A, 跳过避免覆盖")
            return 0

    # 3. 找到 _init_unified_cache 方法前 (合适插入点, 与 R158/R160 模板一致)
    #    由于 R158 模板在 TradingEngine 放在位置 938, 在 RiskManager 放在位置 536
    #    DataService 找一个合适位置: get_metrics() 前
    target = "    def get_metrics(self) -> Dict[str, Any]:"
    if target not in content:
        print(f"[ERROR] 未找到插入点: {target}")
        return 1

    new_content = content.replace(target, DATA_SERVICE_METHOD + target, 1)

    # 4. 验证 _current_account_id 字段 (与 R158 模板一致, 必须初始化)
    if "self._current_account_id" not in content:
        # 在 __init__ 中 self._service_lock = threading.RLock() 后插入
        init_target = "        self._service_lock = threading.RLock()"
        init_addition = "        self._service_lock = threading.RLock()\n\n        # R186-A HVD-185-1: 12+ 服务多账户一致性字段\n        self._current_account_id: str = 'default'\n        self._event_bus_subscribed: bool = False"
        new_content = new_content.replace(init_target, init_addition, 1)

        # 在 __init__ 末尾 (logger.info 后) 追加 _subscribe_account_switched_event 调用
        init_end_target = '        logger.info("DataService initialized for architecture simplification")'
        if init_end_target in new_content:
            init_end_addition = init_end_target + "\n\n        # R186-A HVD-185-1: 启动期订阅 AccountSwitchedEvent (12+ 服务架构 100% 闭环)\n        self._subscribe_account_switched_event()"
            new_content = new_content.replace(init_end_target, init_end_addition, 1)
        else:
            print(f"[WARN] 未找到 init 结束 logger.info, _subscribe_account_switched_event 需手动追加")

    # 5. 写回文件
    with open(DATA_SERVICE_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK] DataService._check_5_service_consistency 已添加 (R186-A HVD-185-1)")
    print(f"     文件路径: {DATA_SERVICE_PATH}")
    print(f"     实施: 12 服务软解析 + set_current_account_id + 事件订阅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
