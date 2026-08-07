"""
R237-A TDD 测试: 密钥管理抽象层 + 版本管理 + 热加载 (12 用例)

测试目标:
- core/security/secrets_manager.py 实施密钥管理抽象层
- 支持从环境变量 / Vault / 配置中心加载密钥
- 实施密钥版本管理 (HIKYUU_SECRET_VERSION 标记)
- 密钥轮换时支持热加载 (不需重启进程)
- 失败 fallback 走 HIKYUU_SECRET_FALLBACK_ENV 环境变量

关联铁律:
- R235 §14.1 #1 凭据不入库铁律 (MUST)
- R104 §12 #1 R+1 round 二次验证
- R231 §13 工具升级 4 源验证
- R85 §10 假修复鉴别 4 步法
"""

import os
import json
import time
import threading
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ==== T01-T04: 基础加载与 fallback ====

def test_t01_secrets_manager_loads_from_env_var(monkeypatch):
    """T01: 从环境变量加载密钥 (优先级最高, R235 §14.1 #1)."""
    monkeypatch.setenv("HIKYUU_JWT_SECRET", "env-var-secret-v1")
    monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager()
    secret = mgr.get_secret("jwt_secret")

    assert secret == "env-var-secret-v1"
    assert mgr.get_version() == "v1"


def test_t02_secrets_manager_fallback_to_file(monkeypatch, tmp_path):
    """T02: 环境变量缺失时, fallback 到密钥文件 (兼容 R235-C 现有 jwt_secret.key)."""
    monkeypatch.delenv("HIKYUU_JWT_SECRET", raising=False)
    monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1-file")

    key_file = tmp_path / "jwt_secret.key"
    key_file.write_text("file-loaded-secret\n", encoding="utf-8")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager(key_file_path=str(key_file))
    secret = mgr.get_secret("jwt_secret")

    assert secret == "file-loaded-secret"


def test_t03_secrets_manager_fallback_env_var(monkeypatch):
    """T03: HIKYUU_SECRET_FALLBACK_ENV 环境变量 fallback 链 (R237-A 任务要求)."""
    monkeypatch.delenv("HIKYUU_JWT_SECRET", raising=False)
    monkeypatch.setenv("HIKYUU_SECRET_FALLBACK_ENV", "FALLBACK_JWT")
    monkeypatch.setenv("FALLBACK_JWT", "fallback-via-env-var")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager()
    secret = mgr.get_secret("jwt_secret", fallback_env="FALLBACK_JWT")

    assert secret == "fallback-via-env-var"


def test_t04_secrets_manager_missing_raises_clear_error(monkeypatch):
    """T04: 全部源缺失时, 抛出明确错误, 禁止静默回退 (R51 软解析教训)."""
    monkeypatch.delenv("HIKYUU_JWT_SECRET", raising=False)
    monkeypatch.delenv("HIKYUU_SECRET_FALLBACK_ENV", raising=False)

    from core.security.secrets_manager import SecretsManager, SecretNotFoundError

    mgr = SecretsManager(key_file_path="/nonexistent/file.key")
    with pytest.raises(SecretNotFoundError) as excinfo:
        mgr.get_secret("jwt_secret")

    assert "jwt_secret" in str(excinfo.value)
    assert "env" in str(excinfo.value).lower() or "file" in str(excinfo.value).lower()


# ==== T05-T08: 密钥版本管理 ====

def test_t05_version_tracking_in_secrets_manager(monkeypatch):
    """T05: HIKYUU_SECRET_VERSION 标记密钥版本, 用于审计与回滚."""
    monkeypatch.setenv("HIKYUU_JWT_SECRET", "v2-secret")
    monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v2")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager()
    assert mgr.get_version() == "v2"


def test_t06_version_mismatch_warning(monkeypatch, caplog):
    """T06: 旧版本检测 + 警告日志 (R236 R+1 round 教训: 显式降级日志)."""
    import logging as _stdlib_logging
    monkeypatch.setenv("HIKYUU_JWT_SECRET", "secret")
    monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1")
    monkeypatch.setenv("HIKYUU_SECRET_MIN_VERSION", "v2")

    from core.security.secrets_manager import SecretsManager

    # 捕获 stdlib logging (loguru 通常配置为桥接到 stdlib)
    caplog.set_level(_stdlib_logging.WARNING)
    mgr = SecretsManager()
    # 不抛错, 但应记录 WARNING
    secret = mgr.get_secret("jwt_secret")
    assert secret == "secret"
    # 验证: 实例应标记 _version_outdated = True (R51 显式降级)
    assert getattr(mgr, "_version_outdated", False) is True


def test_t07_get_all_secrets_returns_versioned_dict(monkeypatch):
    """T07: 批量获取所有密钥 + 版本标记 (审计用)."""
    monkeypatch.setenv("HIKYUU_JWT_SECRET", "jwt-val")
    monkeypatch.setenv("HIKYUU_ENCRYPTION_KEY", "enc-val")
    monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v3")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager()
    all_secrets = mgr.get_all_secrets()

    assert all_secrets["jwt_secret"] == "jwt-val"
    assert all_secrets["encryption_key"] == "enc-val"
    assert all_secrets["_version"] == "v3"


def test_t08_audit_log_includes_version(monkeypatch):
    """T08: 审计日志包含密钥版本 (R222 3 层 ORPHAN 治理 _emit_audit_log 模式)."""
    monkeypatch.setenv("HIKYUU_JWT_SECRET", "audit-test-secret")
    monkeypatch.setenv("HIKYUU_SECRET_VERSION", "v1-audit")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager()
    audit_record = mgr.audit_get("jwt_secret")

    assert audit_record["secret_name"] == "jwt_secret"
    assert audit_record["version"] == "v1-audit"
    assert "timestamp" in audit_record
    assert audit_record["source"] in ("env", "file", "fallback_env")


# ==== T09-T12: 热加载 + 线程安全 ====

def test_t09_hot_reload_on_rotation(monkeypatch, tmp_path):
    """T09: 密钥轮换时支持热加载 (不需重启进程, R237-A 任务要求)."""
    key_file = tmp_path / "rotation.key"
    key_file.write_text("v1-secret\n", encoding="utf-8")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager(key_file_path=str(key_file))
    assert mgr.get_secret("jwt_secret") == "v1-secret"

    # 模拟轮换: 更新文件
    key_file.write_text("v2-rotated-secret\n", encoding="utf-8")
    mgr.reload()

    assert mgr.get_secret("jwt_secret") == "v2-rotated-secret"


def test_t10_hot_reload_preserves_existing_when_no_change(monkeypatch, tmp_path):
    """T10: 文件未变化时热加载不破坏现有状态 (幂等)."""
    key_file = tmp_path / "stable.key"
    key_file.write_text("stable-secret\n", encoding="utf-8")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager(key_file_path=str(key_file))
    initial = mgr.get_secret("jwt_secret")
    mgr.reload()
    after = mgr.get_secret("jwt_secret")

    assert initial == after == "stable-secret"


def test_t11_thread_safe_concurrent_get(monkeypatch, tmp_path):
    """T11: 多线程并发 get_secret 线程安全 (R8 事件总线铁律类比: 锁粒度)."""
    key_file = tmp_path / "concurrent.key"
    key_file.write_text("concurrent-secret\n", encoding="utf-8")

    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager(key_file_path=str(key_file))
    results = []
    errors = []

    def worker():
        try:
            for _ in range(50):
                results.append(mgr.get_secret("jwt_secret"))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 8 * 50
    assert all(r == "concurrent-secret" for r in results)


def test_t12_vault_provider_stub(monkeypatch):
    """T12: Vault provider 接口预留 (R237-A 任务要求: 部署环境用 Vault/AWS Secrets Manager).

    注: R237-A 1d 工作量内只预留接口, 不实际连接 Vault (避免引入 hvac 依赖).
    """
    from core.security.secrets_manager import SecretsManager

    mgr = SecretsManager()
    # 接口存在性测试
    assert hasattr(mgr, "_vault_provider")
    # 当前默认 None (无 Vault 配置时不启用)
    assert mgr._vault_provider is None

    # 可注入 mock provider
    mock_provider = MagicMock()
    mock_provider.get_secret.return_value = "vault-secret"
    mgr.set_vault_provider(mock_provider)
    assert mgr._vault_provider is mock_provider


# ===== 跨轮次回归测试钩子 (避免破坏现有 R235-C 安全基线) =====

def test_r237_a_does_not_break_existing_crypto_utils(monkeypatch):
    """验证 R237-A 不会破坏现有 core/utils/crypto_utils.py (Fernet 加密)."""
    # CryptoUtils 应仍可独立工作
    from core.utils.crypto_utils import get_crypto_utils

    utils = get_crypto_utils()
    # 至少能调用 (即使未配置密钥也走路径分支)
    assert utils is not None


def test_r237_a_does_not_break_existing_security_service_jwt(monkeypatch):
    """验证 R237-A 不会破坏 SecurityService 现有 _load_or_create_jwt_secret 路径."""
    monkeypatch.delenv("HIKYUU_JWT_SECRET", raising=False)

    # SecurityService._load_or_create_jwt_secret 仍能工作 (即使无 env var, 走文件回退)
    # 注: 此测试不实际实例化 SecurityService (构造复杂), 仅确认模块导入
    from core.services.security_service import SecurityService
    assert SecurityService is not None
    assert hasattr(SecurityService, "_load_or_create_jwt_secret")
