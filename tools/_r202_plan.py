"""R202 阶段计划 - 4 子智能体 + R+1 round 闭环 (2026-07-25)

基于 R201 阶段 12 HVD 立项, 实施 R202 阶段 (3.0d) 主要任务.
"""
PLAN = {
    "phase": "R202",
    "date": "2026-07-25",
    "method": "superpowers-6.0.3 (brainstorming → codegraph sync → writing-plans → subagent-driven-development → TDD → R+1 round)",
    "codegraph": {
        "synced_at": "R198 阶段已同步 (2786 files / 76351 nodes / 180411 edges / 394.44MB)",
        "r202_resync_needed": False,  # 已知 R199-R201 同步异常, 基于 R198 索引继续
        "note": "R201 阶段已确认 R198 索引可用, 同步异常系 Windows 环境, 跳过 sync 继续",
    },
    "sub_agents": [
        {
            "id": "A",
            "name": "HVD-R200-A-NEW-3 P0 剩余 329 处多账户隔离治理分批",
            "scope": "core/services/ + core/risk/ + core/trading/ + core/managers/ + core/coordinators/ 剩余 329 处业务关键方法 account_id 隔离治理 (R201 闭环 90 处, R201-B 立项 329 处)",
            "hvd": ["HVD-R200-A-NEW-3"],
            "priority": "P0",
            "duration_days": 2.0,
            "key_files": [
                "core/services/account_service.py",
                "core/services/portfolio_service.py",
                "core/risk/risk_manager.py",
                "core/risk/position_sizer.py",
                "core/trading/order_manager.py",
                "core/managers/account_manager.py",
                "core/coordinators/trading_coordinator.py",
            ],
            "iron_laws": [
                "R104 §12 5 铁律",
                "R104 §13 多账户隔离铁律",
                "R85 假修复鉴别 4 步法",
                "R51 §7.1 5 强约束",
            ],
            "verification": [
                "Read 方法定义物理存在",
                "Grep 跨 4 子目录",
                "CodeGraph 业务调用方追踪",
                "业务调用链上下游追溯",
                "R+1 round 全量回归 0 业务中断",
            ],
        },
        {
            "id": "B",
            "name": "HVD-R201-B-NEW-1 P0 6 处 API 端点 account_id 透传",
            "scope": "web/backend/routes/ 6 处 API 端点 (account/list + positions/list + orders/list + trades/list + portfolio/get + risk/check) 透传 account_id 参数 + 显式校验",
            "hvd": ["HVD-R201-B-NEW-1"],
            "priority": "P0",
            "duration_days": 0.5,
            "key_files": [
                "web/backend/routes/account.py",
                "web/backend/routes/positions.py",
                "web/backend/routes/orders.py",
                "web/backend/routes/trades.py",
                "web/backend/routes/portfolio.py",
                "web/backend/routes/risk.py",
            ],
            "iron_laws": [
                "R104 §12 5 铁律",
                "R104 §13 多账户隔离铁律",
                "R85 假修复鉴别 4 步法",
                "API 端点参数透传契约 (R201-B 立项)",
            ],
            "verification": [
                "Read 路由函数签名 + 显式校验",
                "Grep API 调用方",
                "CodeGraph 跨 web 业务调用链",
                "业务调用链上下游追溯",
            ],
        },
        {
            "id": "C",
            "name": "HVD-R201-C-NEW-2/3/4 P1 3 项 ORPHAN_SUB 业务方订阅治理",
            "scope": "core/coordinators/ 3 项 ORPHAN_SUB 业务方订阅: order_filled (P1) + risk_alert (P1) + position_update (P1)",
            "hvd": ["HVD-R201-C-NEW-2", "HVD-R201-C-NEW-3", "HVD-R201-C-NEW-4"],
            "priority": "P1",
            "duration_days": 0.5,
            "key_files": [
                "core/coordinators/event_coordinator.py",
                "core/events/r84_event_helper.py",
            ],
            "iron_laws": [
                "R104 §12 5 铁律",
                "R8 §8.1 7 铁律 (双轨注册 + 集中 helper)",
                "R85 假修复鉴别 4 步法",
                "V13.2 扫描器升级 (SAME_FILE_CLOSED 误报过滤)",
            ],
            "verification": [
                "Read 订阅方 + helper 函数定义",
                "Grep 跨 4 子目录",
                "CodeGraph 业务调用链",
                "V13.2 扫描器 0 ORPHAN_SUB",
            ],
        },
        {
            "id": "D",
            "name": "全项目增量扫描 + 跨 5 维度发现新 HVD 候选",
            "scope": "5 维度全项目扫描: 死代码 + 锁/缓存/事件总线 + 兼容层 + ORPHAN_PUB/SUB + 多账户/AI/性能",
            "hvd": ["HVD-R202-D-NEW-1~N"],
            "priority": "P1",
            "duration_days": 1.0,
            "key_files": [
                "core/ 全项目",
                "tests/ 全项目",
                "web/ + gui/ 跨子目录",
            ],
            "iron_laws": [
                "R104 §12 5 铁律",
                "R6 §6.1 8 铁律 (死代码)",
                "R85 假修复鉴别 4 步法",
                "V13.2 扫描器 (5 维度)",
            ],
            "verification": [
                "5 维度全项目 AST 扫描",
                "Read + Grep 4 源验证",
                "CodeGraph 跨子目录业务调用链",
                "HVD 立项清单 + 优先级分级",
            ],
        },
    ],
    "r_plus_1_round": {
        "main_agent": "主智能体 (本对话)",
        "scope": "4 子智能体修复成果独立 4 源验证 + 全量回归 0 业务中断",
        "verification": [
            "Read 修复位置物理存在",
            "Grep 跨 4 子目录 0 业务中断",
            "CodeGraph 业务调用链 100%",
            "R85 假修复鉴别 4 步法",
        ],
    },
    "deliverables": {
        "tdd_tests": ">= 4 套 (子智能体 A/B/C/D 各 1 套)",
        "tools": ">= 3 个 (V13.2 扫描器升级 + AST 验证脚本 + 报告生成)",
        "hvd": ">= 4 HVD 实施 + >= 8 HVD 立项 (R203+)",
        "reports": "5 份 (主 1 + 子 4)",
        "reg_tests": "全量回归 0 业务中断",
    },
}
