"""R203 阶段计划 - 2 子智能体 + R+1 round 闭环 (2026-07-25)

基于 R202 阶段 6 HVD 立项, 优先实施 R203 P0 任务:
- HVD-R202-D-NEW-01 P0 5 个 order 事件 ORPHAN_PUB 治理
- HVD-R202-D-NEW-02 P0 AdvancedRiskControlService 5 关键方法多账户隔离

后续 R203+ 排期:
- HVD-R202-D-NEW-03 P1 3 个 P1 业务事件 ORPHAN_PUB 治理 (0.4d)
- HVD-R202-D-NEW-04 P1 AI 服务 10 个方法多账户隔离 (0.5d)
- HVD-R202-D-NEW-05 P2 12 个 unregistered Service 类注册治理 (0.5d)
- HVD-R202-D-NEW-06 P2 9 个 compat alias 文档化 (0.4d)
"""
PLAN = {
    "phase": "R203",
    "date": "2026-07-25",
    "method": "superpowers-6.0.3 (brainstorming → codegraph sync → writing-plans → subagent-driven-development → TDD → R+1 round)",
    "codegraph": {
        "synced_at": "R198 阶段已同步 (2786 files / 76351 nodes / 180411 edges / 394.44MB)",
        "r203_resync_needed": False,  # R201-R202 同步异常, 基于 R198 索引继续
        "note": "R201-R202 阶段已确认 R198 索引可用, 同步异常系 Windows 环境, 跳过 sync 继续",
    },
    "sub_agents": [
        {
            "id": "A",
            "name": "HVD-R202-D-NEW-01 P0 5 个 order 事件 ORPHAN_PUB 治理",
            "scope": "5 个 P0 order 事件订阅方闭环: order_save_retry + batch_orders_created + batch_orders_cancelled + all_active_orders_cancelled + order_save_failed_need_unfreeze (publish 已存在 R142 P0-4 helper, 缺订阅方)",
            "hvd": ["HVD-R202-D-NEW-01"],
            "priority": "P0",
            "duration_days": 0.5,
            "key_files": [
                "core/coordinators/event_coordinator.py",
                "core/events/r84_event_helper.py",
                "core/events/types.py",
                "core/events/event_bus.py",
            ],
            "iron_laws": [
                "R104 §12 5 铁律",
                "R8 §8.1 7 铁律 (双轨注册 + 集中 helper + 集中订阅块)",
                "R85 假修复鉴别 4 步法",
                "V13.3 扫描器 (SAME_FILE_CLOSED 误报过滤)",
            ],
            "verification": [
                "Read 订阅方 + helper 函数定义",
                "Grep 跨 4 子目录",
                "CodeGraph 业务调用链 100%",
                "V13.3 扫描器 0 ORPHAN_PUB",
            ],
        },
        {
            "id": "B",
            "name": "HVD-R202-D-NEW-02 P0 AdvancedRiskControlService 5 关键方法多账户隔离",
            "scope": "core/risk/advanced_risk_control_service.py 5 关键方法多账户隔离: get_status + get_current_risk_assessment + get_liquidity_score + get_model_performance + get_metrics (R117-HVD-68 + R147 HVD-143-B 已治理可观测性, 缺 account_id 隔离)",
            "hvd": ["HVD-R202-D-NEW-02"],
            "priority": "P0",
            "duration_days": 0.3,
            "key_files": [
                "core/risk/advanced_risk_control_service.py",
            ],
            "iron_laws": [
                "R104 §12 5 铁律",
                "R104 §13 多账户隔离铁律",
                "R85 假修复鉴别 4 步法",
                "R51 §7.1 5 强约束 (禁止静默失败)",
            ],
            "verification": [
                "Read 方法定义 + 业务调用链",
                "Grep 跨 4 子目录",
                "CodeGraph 业务调用方追踪",
                "业务调用链上下游追溯",
            ],
        },
    ],
    "r_plus_1_round": {
        "main_agent": "主智能体 (本对话)",
        "scope": "2 子智能体修复成果独立 4 源验证 + 全量回归 0 业务中断",
        "verification": [
            "Read 修复位置物理存在",
            "Grep 跨 4 子目录 0 业务中断",
            "CodeGraph 业务调用链 100%",
            "R85 假修复鉴别 4 步法",
            "全量回归 R200+R201+R202+R203+R22 0 业务中断",
        ],
    },
    "deliverables": {
        "tdd_tests": ">= 2 套 (子智能体 A/B 各 1 套)",
        "tools": ">= 1 个 (V13.3 扫描器应用)",
        "hvd": "2 HVD 实施",
        "reports": "3 份 (主 1 + 子 2)",
        "reg_tests": "全量回归 0 业务中断",
    },
}
