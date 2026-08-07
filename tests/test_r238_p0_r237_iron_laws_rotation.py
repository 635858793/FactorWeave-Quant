"""
R238-P0/P0-B TDD 测试: R237 永久铁律落地 + 密钥轮换用户自管理

测试目标:
1. R238-P0: project_rules.md 第十五章已包含 3 条 R237 永久铁律
2. R238-P0-B: secrets_manager.py 已实现 rotate_key API + 90 天周期强制

关联铁律:
- R237 §6.1 工具升级物理文件验证铁律 (MUST)
- R237 §6.2 报告与代码双向同步铁律 (MUST)
- R237 §6.3 跨轮次回归 4 步验证铁律 (MUST)
- R235 §14.1 #5 密钥轮换 90 天周期强制
- R104 §12 #1 R+1 round 二次验证
- R85 §10 假修复鉴别 4 步法
"""

import os
import time
import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent


# ===== R238-P0: R237 永久铁律落地 =====

class TestR238P0IronLaws:
    """R238-P0: project_rules.md 第十五章已包含 3 条 R237 永久铁律."""

    RULES_PATH = ROOT / ".trae" / "rules" / "project_rules.md"

    def test_p0_1_rules_file_exists(self):
        """P0-1: project_rules.md 存在."""
        assert self.RULES_PATH.exists(), "project_rules.md 不存在"

    def test_p0_2_chapter_15_exists(self):
        """P0-2: project_rules.md 已包含第十五章 (R237 永久铁律)."""
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "## 十五、" in content, "第十五章 (R237 永久铁律) 未在 project_rules.md 中找到"

    def test_p0_3_iron_law_1_physical_verification(self):
        """P0-3: 铁律 #1 工具升级物理文件验证已包含."""
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "工具升级物理文件验证" in content, "铁律 #1 工具升级物理文件验证未包含"

    def test_p0_4_iron_law_2_report_bidirectional_sync(self):
        """P0-4: 铁律 #2 报告与代码双向同步已包含."""
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "报告与代码双向同步" in content, "铁律 #2 报告与代码双向同步未包含"

    def test_p0_5_iron_law_3_cross_round_4step(self):
        """P0-5: 铁律 #3 跨轮次回归 4 步验证已包含."""
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "跨轮次回归" in content and "4 步" in content, "铁律 #3 跨轮次回归 4 步验证未包含"

    def test_p0_6_iron_law_1_has_4_subrules(self):
        """P0-6: 铁律 #1 包含 4 条子规则 (Glob 验证 + Read 验证 + collect-only + 禁止自评)."""
        content = self.RULES_PATH.read_text(encoding="utf-8")
        # 必须包含 4 个关键动作词
        markers = ["Glob", "Read", "collect-only", "自评"]
        for m in markers:
            assert m in content, f"铁律 #1 缺少关键标记: {m}"

    def test_p0_7_iron_law_3_has_4_steps(self):
        """P0-7: 铁律 #3 包含 4 步验证流程."""
        content = self.RULES_PATH.read_text(encoding="utf-8")
        # 必须包含 4 步的关键词 (R231 §13.3: 检查合理字符串, 非字面量通配符)
        steps = ["Glob 物理文件验证", "Read 测试文件", "collect-only", "实际跑"]
        for s in steps:
            assert s in content, f"铁律 #3 缺少步骤: {s}"

    def test_p0_8_has_pr_checklist(self):
        """P0-8: 第十五章包含 PR 自检清单."""
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "PR 自检清单" in content, "第十五章缺少 PR 自检清单"

    def test_p0_9_has_historical_accidents(self):
        """P0-9: 第十五章包含引用历史事故 (R236 假修复)."""
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "R236" in content, "第十五章缺少 R236 假修复历史事故引用"


# ===== R238-P0-B: 密钥轮换用户自管理 =====

class TestR238P0BKeyRotation:
    """R238-P0-B: secrets_manager.py 已实现 rotate_key API + 90 天周期强制."""

    def test_p0b_1_rotate_key_method_exists(self):
        """P0B-1: SecretsManager 有 rotate_key 方法."""
        from core.security.secrets_manager import SecretsManager
        assert hasattr(SecretsManager, "rotate_key"), "SecretsManager 缺少 rotate_key 方法"

    def test_p0b_2_rotate_key_updates_secret(self, monkeypatch):
        """P0B-2: rotate_key 能更新密钥值."""
        monkeypatch.setenv("HIKYUU_JWT_SECRET", "old-secret")
        monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1")

        from core.security.secrets_manager import SecretsManager

        mgr = SecretsManager()
        val_before = mgr.get_secret("jwt_secret")
        assert val_before == "old-secret"

        mgr.rotate_key("jwt_secret", "new-secret-v2", new_version="v2")
        val_after = mgr.get_secret("jwt_secret")
        assert val_after == "new-secret-v2"

    def test_p0b_3_rotate_key_updates_version(self, monkeypatch):
        """P0B-3: rotate_key 后版本号更新."""
        monkeypatch.setenv("HIKYUU_JWT_SECRET", "old-secret")
        monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1")

        from core.security.secrets_manager import SecretsManager

        mgr = SecretsManager()
        mgr.rotate_key("jwt_secret", "new-secret", new_version="v2")

        assert mgr.get_version() == "v2"

    def test_p0b_4_rotate_key_records_audit(self, monkeypatch):
        """P0B-4: rotate_key 操作记录到审计日志."""
        monkeypatch.setenv("HIKYUU_JWT_SECRET", "old-secret")
        monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1")

        from core.security.secrets_manager import SecretsManager

        mgr = SecretsManager()
        mgr.rotate_key("jwt_secret", "rotated-secret", new_version="v2")

        audit_log = mgr.get_audit_log(limit=10)
        # 找最近一次 rotate 审计记录
        rotation_records = [r for r in audit_log if r.get("secret_name") == "jwt_secret" and "rotate" in r.get("action", "")]
        assert len(rotation_records) >= 1, "rotate_key 未记录审计日志"
        assert rotation_records[0]["success"], "rotate_key 审计记录未标记成功"

    def test_p0b_5_rotate_key_without_version(self, monkeypatch):
        """P0B-5: 不传 new_version 时, 自动生成版本."""
        monkeypatch.setenv("HIKYUU_JWT_SECRET", "old-secret")
        monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1")

        from core.security.secrets_manager import SecretsManager

        mgr = SecretsManager()
        mgr.rotate_key("jwt_secret", "auto-version-secret")

        # 版本应自动更新 (带时间戳)
        version = mgr.get_version()
        assert version != "v1", "rotate_key 未自动更新版本"

    def test_p0b_6_rotation_reminder_exists(self, monkeypatch):
        """P0B-6: SecretsManager 有 rotation_reminder 方法 (90 天周期检查)."""
        from core.security.secrets_manager import SecretsManager
        assert hasattr(SecretsManager, "get_rotation_reminder"), "SecretsManager 缺少 get_rotation_reminder 方法"

    def test_p0b_7_rotation_reminder_returns_days_remaining(self, monkeypatch):
        """P0B-7: get_rotation_reminder 返回剩余天数."""
        monkeypatch.setenv("HIKYUU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1")

        from core.security.secrets_manager import SecretsManager, SecretNotFoundError

        mgr = SecretsManager()
        # 刚轮换, 剩余天数应接近 90
        mgr.rotate_key("jwt_secret", "new-secret", new_version="v2")

        reminder = mgr.get_rotation_reminder("jwt_secret")
        assert "days_remaining" in reminder, "get_rotation_reminder 返回缺少 days_remaining"
        assert reminder["days_remaining"] > 80, f"刚轮换后剩余天数应 > 80, 实际 {reminder['days_remaining']}"

    def test_p0b_8_rotation_reminder_warns_expired(self, monkeypatch):
        """P0B-8: 超过 90 天未轮换时, 返回警告."""
        monkeypatch.setenv("HIKYUU_JWT_SECRET", "old-secret")
        monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1")

        from core.security.secrets_manager import SecretsManager

        mgr = SecretsManager()
        # 手动设置过期轮换时间
        mgr._last_rotation["jwt_secret"] = (datetime.utcnow() - timedelta(days=100)).isoformat()

        reminder = mgr.get_rotation_reminder("jwt_secret")
        assert reminder["days_remaining"] < 0, "过期轮换应返回负天数"
        assert reminder.get("overdue", False), "过期轮换应标记 overdue=True"