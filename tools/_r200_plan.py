#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R200 计划: 4 子智能体 + R+1 round, 2026-07-25

R200 主要任务 (基于 R199 立项的 9 项 HVD 中需实施的 6 项):
- A: HVD-R199-D5-01 P0 多账户隔离治理 239 处 (1.5d) - 关键 P0 业务核心
- B: HVD-R199-D2-01 + D1-01 + D3-01 P1+P2 锁/死代码/兼容层 (1.5d)
- C: HVD-R199-D4-01/02 P1 ORPHAN_PUB 36 + ORPHAN_SUB 37 补全 (1.5d)
- D: HVD-R199-D2-03 P2 缓存键工厂使用率提升 (0.5d)
- R+1 round: 主智能体 4 源验证 (0.2d)

强制度:
- R104 §12 5 铁律 (R+1 round + HVD 兼容层 4 源 + AST 嵌套 + 物理删除前 4 源 + AST unparse)
- R85 假修复鉴别 4 步法
- R6 §6.1 8 铁律
- R51 §7.1 5 强约束 (业务关键路径禁止静默失败 + 显式降级日志)
- R51 教训: AdvancedRiskControlService 用 service_container.get() 软解析 → 动态风控退化为静态阈值 (R51 事故)
- R8 §8.1 8 铁律 (双轨注册 enum.name + enum.value)
- R9 §9.1 6 铁律 (缓存键 6 维度)
- R100-F #8 4 锁独立
- R110-C 时序竞态防御
- R176 死缓存防御兼容期保留
- R174 §12 AST 严格扫描 v2.1
- R118 ImportError 豁免
- R194-D v3 升级 v5 修复器经验
- R194-B V13 跨行 publish 检测
- R198-A 兼容层 4 源验证 (同文件引用纳入)
- R198-A 双轨注册 (enum.name + enum.value)
- R143-B 性能监控续
- R104 §13 多账户隔离铁律 (HVD-R199-D5-01 P0)
"""
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
TOOLS_DIR = PROJECT_ROOT / "tools"


def main():
    plan = {
        "phase": "R200",
        "date": "2026-07-25",
        "method": "superpowers-6.0.3 (brainstorming → codegraph sync → writing-plans → subagent-driven-development → TDD → R+1 round)",
        "codegraph": {
            "synced_at": "R198 阶段已同步 (2786 files / 76351 nodes / 180411 edges / 394.44MB)",
            "r200_resync_needed": False,
            "note": "R200 计划基于 R198 同步结果, R199 阶段无新 Python 文件, 无需 resync",
        },
        "sub_agents": [
            {
                "id": "A",
                "name": "HVD-R199-D5-01 P0 多账户隔离治理 239 处",
                "scope": "全项目 account_id 隔离强化 + R104 §13 + R119-C + R198-D-NEW-03 续",
                "hvd": ["HVD-R199-D5-01"],
                "priority": "P0",
                "duration_days": 1.5,
                "key_files": [
                    "core/trading_engine.py",
                    "core/services/trading_confirmation_service.py",
                    "core/risk/",
                    "core/portfolio/",
                    "core/account/",
                ],
            },
            {
                "id": "B",
                "name": "HVD-R199-D2-01 + D1-01 + D3-01 P1+P2 锁/死代码/兼容层治理",
                "scope": "R199-D 立项 1 P1 锁嵌套 + 1 P2 死代码 + 1 P2 兼容层 (3 项 HVD)",
                "hvd": [
                    "HVD-R199-D2-01",
                    "HVD-R199-D1-01",
                    "HVD-R199-D3-01",
                ],
                "priority": "P1+P2",
                "duration_days": 1.5,
            },
            {
                "id": "C",
                "name": "HVD-R199-D4-01/02 P1 ORPHAN_PUB 36 + ORPHAN_SUB 37 补全",
                "scope": "R199-D 立项 2 项 P1 ORPHAN 治理 (跨行 publish + V13 检测 + 双轨注册)",
                "hvd": ["HVD-R199-D4-01", "HVD-R199-D4-02"],
                "priority": "P1",
                "duration_days": 1.5,
            },
            {
                "id": "D",
                "name": "HVD-R199-D2-03 P2 缓存键工厂使用率提升",
                "scope": "R199-D 立项 1 项 P2 缓存键工厂使用率 34.9% → ≥ 50%",
                "hvd": ["HVD-R199-D2-03"],
                "priority": "P2",
                "duration_days": 0.5,
            },
        ],
        "r_plus_1_round": {
            "role": "主智能体",
            "tasks": [
                "Read 验证 4 子智能体修复物理存在",
                "Grep 验证业务调用方",
                "CodeGraph 验证业务链",
                "类检查验证方法签名",
            ],
        },
        "expected_outcomes": {
            "p0_multi_account_fixes": "目标 100+ 多账户隔离强化 (1.5d 子智能体 A)",
            "p1_hvd_completed": "目标 6 项 HVD 100% 闭环 (1 P0 + 3 P1 + 3 P2 = 7 项 HVD)",
            "tdd_passes": "目标 100% (TDD 强制)",
            "regression_passes": "目标 100% (R200 + R199 + R198 + R197 + R196 + R195 + R194)",
        },
    }

    plan_file = TOOLS_DIR / "_r200_plan.json"
    plan_file.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[OK] R200 计划已保存: {plan_file}")

    print()
    print("R200 子任务分配:")
    for sa in plan["sub_agents"]:
        print(f"  子智能体 {sa['id']}: {sa['name']}")
        print(f"    范围: {sa['scope']}")
        print(f"    HVD: {sa['hvd']}")
        print(f"    优先级: {sa['priority']}, 工作量: {sa['duration_days']}d")
        print()

    print("R200 强制度: R104 §12 + R85 4 步法 + R51 §7.1 (关键路径) + R8 + R9 + R100-F + R110-C + R174 + R118 + R194-D v3 + V13 + R198-A 兼容层 4 源 + R198-A 双轨注册 + R104 §13 多账户隔离 + R143-B 性能监控")


if __name__ == "__main__":
    main()
