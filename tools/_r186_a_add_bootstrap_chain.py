#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R186-A HVD-185-1: 启动期自动校验串联 (D3)

Why: R184 HVD-182-1 Stage 2 已实施 bootstrap() 末尾串联 health_check_all_services,
     但未串联 12+ 服务一致性检查. HVD-185-1 扩展串联 consistency_check.

Fix: 在 service_bootstrap.py:bootstrap() 末尾, health_check_all_services 串联后,
     立即串联 _check_multi_account_consistency() (新增方法).
     失败仅 warning 不抛 (R51 §7.1 #5 严禁丢失降级日志).
     模仿 R184 HVD-182-1 Stage 2 模式 (L730-745).

R104 §12 5 铁律:
  - #1 R+1 round 验证 (后续子智能体)
  - #2 HVD 兼容层 4 源验证
  - #4 物理删除前 4 源 100% 命中 (本任务为新增, 跳过)
  - #5 锁嵌套 AST unparse (本任务无锁架构, 跳过)
"""

import sys

SERVICE_BOOTSTRAP_PATH = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/service_bootstrap.py"

# R186-A HVD-185-1 启动期自动校验串联块 (插入到 health_check_all_services 之后)
# 模仿 R184 HVD-182-1 Stage 2 (L730-745) 模式
R186_HVD185_1_STAGE_3_CHAIN = '''
            # R186-A HVD-185-1 (2026-07-25): bootstrap 完成后自动串联 12+ 服务一致性检查
            # Why (R185-C 立项): R184 HVD-182-1 Stage 2 已串联 health_check_all_services,
            #      但未串联 12+ 服务 _current_account_id 一致性检查 → 5+1 架构监控盲点.
            # Fix: bootstrap() 末尾 (health_check 之后) 串联 _check_multi_account_consistency()
            #      失败仅 warning 不抛 (R51 §7.1 #5 严禁丢失降级日志, R75-DEV-4 兼容).
            # 业务影响: 启动期自动获得 12+ 服务 account_id 一致性聚合报告, 多账户漂移
            #           自动 CRITICAL 告警 (R8 §8 事件总线同步直发).
            # 验证: tests/test_r186_a_hvd_185_1_consistency.py
            # 报告: .trae/reports/rounds/audit_r186_a_hvd_185_1.md
            try:
                consistency_report = self._check_multi_account_consistency()
                logger.info(
                    f"[R186-A HVD-185-1 Stage 3] bootstrap 启动期一致性检查自动完成: "
                    f"total_services={consistency_report.get('total_services', 0)} "
                    f"is_consistent={consistency_report.get('is_consistent', None)} "
                    f"drift_count={consistency_report.get('drift_count_total', 0)} "
                    f"unique_accounts={len(consistency_report.get('unique_accounts', []))}"
                )
            except Exception as stage3_exc:
                # R51 §7.1 #5 严禁丢失降级日志: warning + exc_info=True
                # Why: 启动期 consistency_check 失败是降级场景, 必须记录 stack trace 但不阻断
                logger.warning(
                    f"[R186-A HVD-185-1 Stage 3] 启动期一致性检查失败 (R51 降级, 不阻断 bootstrap): {stage3_exc}",
                    exc_info=True,
                )

'''


def main():
    with open(SERVICE_BOOTSTRAP_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. 验证未实施过
    if "[R186-A HVD-185-1 Stage 3]" in content:
        print("[SKIP] service_bootstrap.py 已实施 R186-A HVD-185-1 Stage 3 串联")
        return 0

    # 2. 找到 health_check_all_services 串联块结束位置 (R184-A HVD-182-1 Stage 2 末尾)
    # 模式: 在 "Service bootstrap completed successfully" 前插入
    target = '''            logger.info("Service bootstrap completed successfully")'''

    if target not in content:
        print(f"[ERROR] 未找到插入点: {target}")
        return 1

    new_content = content.replace(target, R186_HVD185_1_STAGE_3_CHAIN + target, 1)

    # 3. 添加 _check_multi_account_consistency 方法到 ServiceBootstrap 类
    # 找到 health_check_all_services 方法定义位置
    method_target = "    def health_check_all_services(\n        self,\n        *,\n        include_healthy: bool = True,\n        include_unknown: bool = True,"
    if method_target not in new_content:
        print(f"[ERROR] 未找到 health_check_all_services 方法: {method_target}")
        return 1

    new_method = '''    def _check_multi_account_consistency(self) -> Dict[str, Any]:
        """R186-A HVD-185-1 (2026-07-25): 启动期 12+ 服务多账户一致性检查

        Why: R158 HVD-150-A 实施 8/8 服务 + R158-A HVD-158-A-NEW-1 (OrderService) +
             R160 HVD-160-E-2 (OrderExecutor) + R186-A HVD-185-1 (DataService/StrategyService)
             = 12+ 服务 100% 闭环. 启动期自动串联一致性检查, 监控多账户场景漂移.

        Why 与 health_check 串联: R184 HVD-182-1 Stage 2 已串联 health_check, HVD-185-1
             扩展串联 consistency_check, 二者形成启动期完整服务健康 + 一致性聚合报告.

        关联铁律: R104 §12 5 铁律 + R6 §6.1 8 铁律 + R51 §7.1 5 强约束
                  + R8 §8 事件总线 7 铁律 (CRITICAL 业务事件同步直发)

        Returns:
            Dict: 12+ 服务一致性聚合报告 (R122 HVD-92 Prometheus 集成格式)
        """
        try:
            # 懒加载 MultiAccountConsistencyChecker (R7 §7.1 #1 不在模块顶层注册,
            # 仅作为启动期一致性检查工具, 避免污染 ServiceContainer)
            from core.multi_account.consistency_checker import MultiAccountConsistencyChecker

            # 优先用 ServiceContainer 注入 event_bus, 不可用时降级 None
            event_bus = None
            if self.service_container is not None:
                try:
                    # 尝试从容器取 event_bus (如果有注册)
                    if hasattr(self.service_container, 'resolve'):
                        try:
                            from core.events import EventBus
                            if self.service_container.is_registered(EventBus):
                                event_bus = self.service_container.resolve(EventBus)
                        except Exception:
                            pass
                except Exception:
                    pass

            checker = MultiAccountConsistencyChecker(
                service_container=self.service_container,
                event_bus=event_bus,
            )
            return checker.run_full_check()
        except Exception as e:
            # R51 §7.1 #5 显式降级日志: warning + exc_info=True
            # Why: 启动期一致性检查失败必须记录 stack trace, 但不阻断 bootstrap
            from loguru import logger as _logger
            _logger.warning(
                f"[R186-A HVD-185-1] _check_multi_account_consistency 失败 (R51 降级): {e}",
                exc_info=True,
            )
            return {
                "total_services": 0,
                "is_consistent": None,
                "error": str(e),
            }

'''

    new_content = new_content.replace(method_target, new_method + method_target, 1)

    # 4. 写回文件
    with open(SERVICE_BOOTSTRAP_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK] service_bootstrap.py: bootstrap 启动期一致性检查串联 (R186-A HVD-185-1 Stage 3)")
    print(f"     实施内容:")
    print(f"       1. _check_multi_account_consistency() 方法新增")
    print(f"       2. bootstrap() 末尾串联 (R184-A HVD-182-1 Stage 2 模式)")
    print(f"       3. try/except + exc_info=True 降级 (R51 §7.1 #5)")
    print(f"     文件路径: {SERVICE_BOOTSTRAP_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
