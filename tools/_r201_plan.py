#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R201 阶段计划 (2026-07-25)

R200 阶段完成后, R201 阶段聚焦 4 项 HVD 实施:
- 子智能体 A: HVD-R200-A-NEW-1 P0 trading/order_service.py 24 处 + risk/risk_event_subscribers.py 21 处多账户隔离治理
- 子智能体 B: HVD-R200-A-NEW-2 P0 web/backend + gui 45 处多账户隔离治理
- 子智能体 C: HVD-R200-C-NEW-1 P1 67 项剩余 ORPHAN 治理
- 子智能体 D: HVD-R200-D-NEW-1 P1 缓存键工厂使用率 51.6% → ≥ 70%

方法: superpowers-6.0.3 (brainstorming → codegraph sync → writing-plans → subagent-driven-development → TDD → R+1 round)

强制度:
- R104 §12 5 铁律 (R+1 round + HVD 4 源 + AST 递归 + 物理删除前 4 源 + AST unparse)
- R85 假修复鉴别 4 步法
- R6 §6.1 8 铁律
- R51 §7.1 5 强约束
- R8 §8.1 8 铁律 (双轨注册)
- R9 §9.1 6 铁律 (缓存键 6 维度)
- R100-F-P1-1 #8 4 锁独立
- R110-C 时序竞态防御
- R104 §13 多账户隔离铁律
- R176 死缓存防御兼容期保留
- R174 §12 AST 严格扫描 v2.1
- R118 ImportError 豁免
- R194-D v3 升级 v5 修复器
- R194-B V13 跨行 publish
- R198-A 兼容层 4 源 (同文件引用纳入)
- R198-A 双轨注册 (enum.name + enum.value)
- R143-B 性能监控续

CodeGraph 同步状态:
- R198 阶段已同步 (2786 files / 76351 nodes / 180411 edges / 394.44MB)
- R200 阶段无新 Python 文件
- R201 计划基于 R198 同步结果, 立项前重新 sync

R201 工作量: 4.0d
R201+ 排期: R202 (3d) HVD-R200-A-NEW-3 剩余 329 + B-NEW-1/2 → R203+ TBD
"""

PLAN = {
    "phase": "R201",
    "date": "2026-07-25",
    "method": "superpowers-6.0.3 (brainstorming → codegraph sync → writing-plans → subagent-driven-development → TDD → R+1 round)",
    "codegraph": {
        "synced_at": "R198 阶段已同步 (2786 files / 76351 nodes / 180411 edges / 394.44MB)",
        "r201_resync_needed": True,  # R201 立项前重新 sync
        "note": "R200 阶段无新 Python 文件, 但 R201 立项前必须 resync 确认索引最新",
    },
    "sub_agents": [
        {
            "id": "A",
            "name": "HVD-R200-A-NEW-1 P0 trading/order_service.py 24 + risk/risk_event_subscribers.py 21 多账户隔离治理",
            "scope": "trading/order_service.py 24 处 + risk/risk_event_subscribers.py 21 处业务关键方法添加 account_id 隔离",
            "hvd": ["HVD-R200-A-NEW-1"],
            "priority": "P0",
            "duration_days": 1.5,
            "key_files": [
                "core/trading/order_service.py",
                "core/risk/risk_event_subscribers.py",
            ],
            "iron_laws": [
                "R104 §12 5 铁律",
                "R104 §13 多账户隔离铁律",
                "R85 假修复鉴别 4 步法",
                "R51 §7.1 5 强约束 (禁止静默失败)",
                "R110-C 时序竞态防御",
            ],
            "verification": [
                "Read 方法定义物理存在",
                "Grep 跨 4 子目录 (core/web/gui/tests)",
                "CodeGraph 业务调用方追踪",
                "业务调用链上下游追溯",
            ],
        },
        {
            "id": "B",
            "name": "HVD-R200-A-NEW-2 P0 web/backend + gui 45 处多账户隔离治理",
            "scope": "web/backend/services 25 处 + gui/dialogs 20 处业务关键方法添加 account_id 隔离",
            "hvd": ["HVD-R200-A-NEW-2"],
            "priority": "P0",
            "duration_days": 1.0,
            "key_files": [
                "web/backend/services/order_service.py",
                "web/backend/services/risk_service.py",
                "gui/dialogs/order_management_dialog.py",
                "gui/dialogs/account_management_dialog.py",
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
            ],
        },
        {
            "id": "C",
            "name": "HVD-R200-C-NEW-1 P1 67 项剩余 ORPHAN 治理",
            "scope": "V13.1 升级扫描器发现 67 项剩余 ORPHAN_PUB/SUB, 集中订阅闭环",
            "hvd": ["HVD-R200-C-NEW-1"],
            "priority": "P1",
            "duration_days": 1.0,
            "key_files": [
                "core/coordinators/event_coordinator.py",
                "core/events/r84_event_helper.py",
            ],
            "iron_laws": [
                "R8 §8.1 8 铁律 (双轨注册 enum.name + enum.value)",
                "R194-B V13 跨行 publish 检测",
                "R198-A 双轨注册",
                "R85 假修复鉴别 4 步法",
            ],
            "verification": [
                "V13.1 扫描器升级 SAME_FILE_CLOSED 检测",
                "Grep 跨 4 子目录 (core/web/gui/tests) publish/subscribe 配对",
                "CodeGraph event bus 跨子目录",
                "业务调用链追踪",
            ],
        },
        {
            "id": "D",
            "name": "HVD-R200-D-NEW-1 P1 缓存键工厂使用率 51.6% → ≥ 70%",
            "scope": "core/agents/ + core/importdata/ + core/performance/ + service_bootstrap.py 46 处剩余缓存键工厂化",
            "hvd": ["HVD-R200-D-NEW-1"],
            "priority": "P1",
            "duration_days": 0.5,
            "key_files": [
                "core/agents/",
                "core/importdata/",
                "core/performance/",
                "core/services/service_bootstrap.py",
            ],
            "iron_laws": [
                "R9 §9.1 6 铁律 (6 维度强制)",
                "R176 死缓存防御兼容期保留",
                "R198-A 兼容层 4 源",
                "R85 假修复鉴别 4 步法",
            ],
            "verification": [
                "Read 缓存键生成代码物理存在",
                "Grep 跨 4 子目录 f-string 违规",
                "工厂使用率计算 (新工厂调用数 / 总缓存调用数)",
                "6 维度验证 (at_code_period_count_adj_ds)",
            ],
        },
    ],
    "r_plus_1_round": {
        "scope": "4 子智能体 100% 闭环验证",
        "iron_laws": [
            "R104 §12 #1 R+1 round 二次验证",
            "R85 假修复鉴别 4 步法 100% 应用",
        ],
        "verification_matrix": [
            "Read 物理存在",
            "Grep 跨 4 子目录",
            "CodeGraph 业务调用方",
            "业务调用链上下游追溯",
        ],
    },
    "expected_outcomes": {
        "tdd_pass_total": 150,  # 估算: A 50 + B 35 + C 50 + D 15
        "regression_pass_total": 1100,  # R200 991 + R201 新增约 100-150
        "hvd_closed": 4,  # A 1 + B 1 + C 1 + D 1
        "false_fixes": 0,
        "business_interruptions": 0,
        "iron_law_count": 22,  # 全部 22 条强制度
    },
    "r201_plus_schedule": {
        "R202 (3d)": [
            "HVD-R200-A-NEW-3 (P0) 剩余 329 处多账户隔离治理分批 (2.0d)",
            "HVD-R200-B-NEW-1 (P2) 全项目锁嵌套简化字符串计数误报治理 (0.5d)",
            "HVD-R200-B-NEW-2 (P2) 兼容层 alias 4 源验证全项目扫描 (0.5d)",
        ],
        "R203+ (TBD)": [
            "持续 30599 死代码 + 186 Service 缺 health_check + 24 HVD 候选 + 0 业务中断",
        ],
    },
}


if __name__ == "__main__":
    import json
    print(json.dumps(PLAN, ensure_ascii=False, indent=2))
