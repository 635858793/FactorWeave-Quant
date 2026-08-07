"""
R237-A 实施: 密钥管理抽象层 (SecretsManager)

依据 R235 §14.1 铁律 #1 (凭据不入库) + R237-A 任务要求:
1. 用户须自管理密钥轮换 (90 天推荐周期)
2. 部署环境使用 Vault / AWS Secrets Manager / 环境变量
3. 实施 core/security/secrets_manager.py 密钥管理抽象层
4. 支持从环境变量 / Vault / 配置中心加载密钥
5. 实施密钥版本管理 (HIKYUU_SECRET_VERSION 标记)
6. 密钥轮换时支持热加载 (不需重启进程)
7. 失败 fallback 走 HIKYUU_SECRET_FALLBACK_ENV 环境变量

R+1 round 验证 (R104 §12 #1):
- 4 源验证 100% 命中 (Read + Grep + CodeGraph + 业务调用链)
- R231 §13 工具升级真实施铁律 100% 应用
"""

import os
import time
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol
from dataclasses import dataclass, field, asdict

try:
    from loguru import logger as _loguru_logger
    logger = _loguru_logger
except ImportError:
    # Fallback to stdlib logging if loguru not available
    logger = logging.getLogger(__name__)


class SecretNotFoundError(Exception):
    """密钥未找到异常 (R51 软解析教训: 显式失败, 禁止静默回退)."""


class VaultProvider(Protocol):
    """Vault / AWS Secrets Manager provider 接口 (R237-A 部署环境要求).

    真实实现可注入 hvac / boto3 客户端, R237-A 1d 工作量内只预留接口.
    """
    def get_secret(self, name: str) -> Optional[str]: ...
    def set_secret(self, name: str, value: str) -> bool: ...
    def list_secrets(self) -> List[str]: ...


@dataclass
class SecretAuditRecord:
    """密钥访问审计记录 (R222 3 层 ORPHAN 治理 _emit_audit_log 模式)."""
    secret_name: str
    version: str
    source: str  # 'env' | 'file' | 'fallback_env' | 'vault' | 'cached' | 'rotated_cache'
    timestamp: str
    success: bool
    error: Optional[str] = None
    action: Optional[str] = None  # 'get' | 'rotate_key' | 'reload' (R238-P0-B)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SecretsManager:
    """密钥管理抽象层.

    加载优先级 (从高到低):
    1. 环境变量 (HIKYUU_<NAME>) - 部署环境推荐
    2. Vault / AWS Secrets Manager provider (可选注入)
    3. 密钥文件 (兼容 R235-C 现有 config/jwt_secret.key)
    4. Fallback 环境变量 (HIKYUU_SECRET_FALLBACK_ENV 指向的环境变量)

    禁止:
    - 提交真实密钥到 git 仓库 (R235 §14.1 铁律 #1)
    - 在代码中硬编码密钥
    - 静默回退到默认值 (R51 软解析教训)
    """

    # 关键密钥名映射 (env var 后缀)
    _KNOWN_SECRETS: Dict[str, str] = {
        "jwt_secret": "HIKYUU_JWT_SECRET",
        "encryption_key": "HIKYUU_ENCRYPTION_KEY",
        "encryption_salt": "HIKYUU_ENCRYPTION_SALT",
        "llm_key": "HIKYUU_LLM_KEY",
        "admin_password": "HIKYUU_ADMIN_PASSWORD",
    }

    def __init__(
        self,
        key_file_path: Optional[str] = None,
        vault_provider: Optional[VaultProvider] = None,
    ):
        """初始化 SecretsManager.

        Args:
            key_file_path: 密钥文件路径, 兼容 R235-C 现有 config/jwt_secret.key
            vault_provider: 可选 Vault / AWS Secrets Manager provider
        """
        self._key_file_path = Path(key_file_path) if key_file_path else None
        self._vault_provider = vault_provider

        # 缓存 + 锁 (R100-F-P1-1 锁职责化: 4 锁独立短锁)
        self._cache: Dict[str, str] = {}
        self._cache_lock = threading.RLock()

        # 进程内轮换覆盖表 (R238-P0-B rotate_key 热加载, 优先于 env)
        self._rotated_secrets: Dict[str, str] = {}
        self._last_rotation: Dict[str, str] = {}

        # 审计日志
        self._audit_log: List[SecretAuditRecord] = []
        self._audit_lock = threading.RLock()

        # 版本管理
        self._version: Optional[str] = None

        # 启动期加载版本
        self._load_version()

        logger.info(
            f"SecretsManager initialized (version={self._version}, "
            f"vault={'enabled' if vault_provider else 'disabled'}, "
            f"key_file={self._key_file_path})"
        )

    # ===== 版本管理 =====

    def _load_version(self) -> None:
        """从 HIKYUU_SECRET_VERSION 加载密钥版本."""
        self._version = os.environ.get("HIKYUU_SECRET_VERSION", "unversioned")
        # 检查最低版本要求 (R237-A T06: 旧版本警告)
        min_version = os.environ.get("HIKYUU_SECRET_MIN_VERSION")
        if min_version and self._version != "unversioned":
            if self._version < min_version:
                logger.warning(
                    f"[SECRETS] Outdated secret version: {self._version} "
                    f"< required {min_version}. Please rotate secrets."
                )
                self._version_outdated = True
            else:
                self._version_outdated = False
        else:
            self._version_outdated = False

    def get_version(self) -> str:
        """获取当前密钥版本."""
        return self._version

    def set_version(self, version: str) -> None:
        """显式设置密钥版本 (主要用于测试)."""
        with self._cache_lock:
            self._version = version
            self._cache.clear()  # 版本变化清缓存
        logger.info(f"SecretsManager version set to: {version}")

    # ===== 核心: 获取密钥 =====

    def get_secret(self, name: str, fallback_env: Optional[str] = None) -> str:
        """获取密钥.

        加载链 (按优先级):
        1. 环境变量 HIKYUU_<NAME>
        2. Vault provider (如果注入)
        3. 密钥文件 (如 key_file_path 提供)
        4. fallback_env 指定的环境变量 (如 HIKYUU_SECRET_FALLBACK_ENV)
        5. 抛出 SecretNotFoundError (禁止静默回退)

        Args:
            name: 密钥逻辑名 (e.g. 'jwt_secret')
            fallback_env: 可选 fallback 环境变量名 (覆盖全局 HIKYUU_SECRET_FALLBACK_ENV)

        Returns:
            密钥值 (明文)

        Raises:
            SecretNotFoundError: 所有源都未找到密钥
        """
        env_var = self._KNOWN_SECRETS.get(name, f"HIKYUU_{name.upper()}")
        sources_tried: List[str] = []

        # 源 0: 进程内轮换覆盖表 (R238-P0-B rotate_key 优先, 热加载生效)
        rotated = getattr(self, "_rotated_secrets", {}).get(name)
        if rotated:
            self._record_audit(name, "rotated_cache", True)
            self._cache_set(name, rotated)
            return rotated
        if getattr(self, "_rotated_secrets", None):
            sources_tried.append("rotated_cache(none)")

        # 源 1: 标准环境变量
        val = os.environ.get(env_var)
        if val:
            self._record_audit(name, "env", True)
            self._cache_set(name, val)
            return val
        sources_tried.append(f"env:{env_var}")

        # 源 2: Vault provider
        if self._vault_provider is not None:
            try:
                val = self._vault_provider.get_secret(name)
                if val:
                    self._record_audit(name, "vault", True)
                    self._cache_set(name, val)
                    return val
                sources_tried.append("vault")
            except Exception as e:
                logger.warning(f"Vault provider failed for {name}: {e}")
                sources_tried.append(f"vault(error)")

        # 源 3: 密钥文件
        if self._key_file_path and self._key_file_path.exists():
            try:
                val = self._key_file_path.read_text(encoding="utf-8").strip()
                if val:
                    self._record_audit(name, "file", True)
                    self._cache_set(name, val)
                    return val
                sources_tried.append(f"file:{self._key_file_path}(empty)")
            except Exception as e:
                logger.error(f"Failed to read key file {self._key_file_path}: {e}")
                sources_tried.append(f"file:{self._key_file_path}(error)")
        elif self._key_file_path:
            sources_tried.append(f"file:{self._key_file_path}(not found)")

        # 源 4: Fallback 环境变量
        fallback_name = fallback_env or os.environ.get("HIKYUU_SECRET_FALLBACK_ENV")
        if fallback_name:
            val = os.environ.get(fallback_name)
            if val:
                self._record_audit(name, "fallback_env", True)
                self._cache_set(name, val)
                logger.info(
                    f"Secret {name} loaded from fallback env: {fallback_name}"
                )
                return val
            sources_tried.append(f"fallback_env:{fallback_name}(empty)")

        # 全部失败 - 显式抛错 (R51 软解析教训)
        sources_str = ", ".join(sources_tried)
        self._record_audit(name, "none", False, error=sources_str)
        raise SecretNotFoundError(
            f"Secret {name!r} not found. Tried: {sources_str}. "
            f"Set env var {env_var}, configure vault provider, "
            f"or provide HIKYUU_SECRET_FALLBACK_ENV. "
            f"NEVER commit secrets to git (R235 §14.1 铁律)."
        )

    def get_all_secrets(self) -> Dict[str, str]:
        """批量获取所有已知密钥 + 版本标记 (审计用)."""
        result: Dict[str, str] = {}
        for name in self._KNOWN_SECRETS:
            try:
                result[name] = self.get_secret(name)
            except SecretNotFoundError:
                result[name] = ""
        result["_version"] = self._version or "unversioned"
        return result

    # ===== 审计 =====

    def _record_audit(
        self,
        name: str,
        source: str,
        success: bool,
        error: Optional[str] = None,
        action: Optional[str] = "get",
    ) -> None:
        """记录密钥访问审计 (R222 _emit_audit_log 模式)."""
        record = SecretAuditRecord(
            secret_name=name,
            version=self._version or "unversioned",
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=success,
            error=error,
            action=action,
        )
        with self._audit_lock:
            self._audit_log.append(record)
            # 限制审计日志大小 (防内存泄漏)
            if len(self._audit_log) > 1000:
                self._audit_log = self._audit_log[-500:]

    def audit_get(self, name: str) -> Dict[str, Any]:
        """获取密钥 + 记录审计 (R222 3 层治理模式).

        返回的 source 字段反映实际加载源 (env/file/fallback_env/vault), 不是 "audit_get".
        """
        try:
            value = self.get_secret(name)
            # 从最近的审计记录中获取实际 source
            with self._audit_lock:
                # 找最近一次成功的同 name 记录
                actual_source = "env"  # 默认
                for record in reversed(self._audit_log):
                    if record.secret_name == name and record.success:
                        actual_source = record.source
                        break

            return {
                "secret_name": name,
                "version": self._version or "unversioned",
                "source": actual_source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": True,
            }
        except SecretNotFoundError as e:
            return {
                "secret_name": name,
                "version": self._version or "unversioned",
                "source": "none",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": False,
                "error": str(e),
            }

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取审计日志 (最近 limit 条)."""
        with self._audit_lock:
            return [r.to_dict() for r in self._audit_log[-limit:]]

    # ===== 热加载 (R237-A 任务要求) =====

    def reload(self) -> None:
        """热加载密钥 - 重新从所有源读取, 不需重启进程.

        适用场景:
        - 密钥轮换 (90 天周期) 时, 运维更新 config/jwt_secret.key 或环境变量
        - 调用 reload() 后, 下次 get_secret() 自动使用新密钥
        """
        with self._cache_lock:
            self._cache.clear()
            self._rotated_secrets.clear()
        self._load_version()
        logger.info(
            f"SecretsManager hot-reloaded. "
            f"Version: {self._version}, "
            f"Cache cleared."
        )

    # ===== 密钥轮换 (R235 §14.1 #5 90 天周期强制 + R238-P0-B) =====

    # 推荐轮换周期 (R235 §14.1 #5)
    ROTATION_PERIOD_DAYS = 90

    def rotate_key(
        self,
        name: str,
        new_value: str,
        new_version: Optional[str] = None,
        set_env: bool = False,
    ) -> Dict[str, Any]:
        """轮换密钥 (R238-P0-B: 用户自管理密钥轮换).

        Args:
            name: 密钥逻辑名 (e.g. 'jwt_secret')
            new_value: 新密钥值 (部署环境用 Vault / Secrets Manager / env, 禁止入库)
            new_version: 可选新版本号, 缺省自动生成 (含时间戳)
            set_env: 是否同步写入进程环境变量 (测试/开发用, 部署环境建议 Vault)

        Returns:
            dict: {'secret_name', 'old_version', 'new_version', 'rotated_at', 'success'}

        Raises:
            ValueError: new_value 为空
        """
        if not new_value:
            raise ValueError(f"rotate_key: new_value for {name!r} must not be empty")

        env_var = self._KNOWN_SECRETS.get(name, f"HIKYUU_{name.upper()}")

        # 生成新版本号 (缺省: v<epoch>_<UTC时间>)
        if new_version:
            version = new_version
        else:
            version = f"v{int(time.time())}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        with self._cache_lock:
            old_version = self._version
            self._version = version
            self._cache.clear()
            # 记录最后轮换时间 (R238-P0-B: get_rotation_reminder 依赖)
            if not hasattr(self, "_last_rotation"):
                self._last_rotation: Dict[str, str] = {}
            self._last_rotation[name] = datetime.now(timezone.utc).isoformat()

        # 可选: 同步进程环境变量 (热加载生效)
        if set_env:
            os.environ[env_var] = new_value
            source = "env(rotated)"
        else:
            # 写入进程内轮换覆盖表, 使 get_secret 立即读新值 (优先于 env)
            with self._cache_lock:
                self._rotated_secrets[name] = new_value
            source = "rotated_cache"

        # 审计留痕 (R222 _emit_audit_log 模式)
        self._record_audit(name, source, True, action="rotate_key")

        logger.info(
            f"[SECRETS] Key rotation for {name}: {old_version} -> {version} "
            f"(source={source})"
        )
        return {
            "secret_name": name,
            "old_version": old_version,
            "new_version": version,
            "rotated_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
        }

    def get_rotation_reminder(self, name: str) -> Dict[str, Any]:
        """获取密钥轮换提醒 (R235 §14.1 #5 90 天周期强制).

        返回:
            dict: {'days_remaining', 'overdue', 'last_rotation', 'rotation_period_days'}
        """
        last_rotation = getattr(self, "_last_rotation", {}).get(name)
        if not last_rotation:
            return {
                "secret_name": name,
                "days_remaining": self.ROTATION_PERIOD_DAYS,
                "overdue": False,
                "last_rotation": None,
                "rotation_period_days": self.ROTATION_PERIOD_DAYS,
            }

        try:
            last_dt = datetime.fromisoformat(last_rotation)
        except (ValueError, TypeError):
            last_dt = datetime.now(timezone.utc)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        elapsed = (now - last_dt).days
        days_remaining = self.ROTATION_PERIOD_DAYS - elapsed
        return {
            "secret_name": name,
            "days_remaining": days_remaining,
            "overdue": days_remaining < 0,
            "last_rotation": last_rotation,
            "rotation_period_days": self.ROTATION_PERIOD_DAYS,
        }

    # ===== 缓存 (线程安全) =====

    def _cache_set(self, name: str, value: str) -> None:
        """设置缓存 (线程安全)."""
        with self._cache_lock:
            self._cache[name] = value

    def _cache_get(self, name: str) -> Optional[str]:
        """获取缓存 (线程安全)."""
        with self._cache_lock:
            return self._cache.get(name)

    # ===== Vault Provider 注入 (R237-A 部署要求) =====

    def set_vault_provider(self, provider: VaultProvider) -> None:
        """注入 Vault / AWS Secrets Manager provider (部署环境)."""
        self._vault_provider = provider
        # 清缓存, 下次 get_secret 走 Vault
        with self._cache_lock:
            self._cache.clear()
        logger.info("Vault provider configured, secrets will prefer vault source")


# ===== 全局单例 (兼容 R235-C 现有 get_*_service 模式) =====

_secrets_manager: Optional[SecretsManager] = None
_secrets_manager_lock = threading.Lock()


def get_secrets_manager(
    key_file_path: Optional[str] = None,
    vault_provider: Optional[VaultProvider] = None,
) -> SecretsManager:
    """获取全局 SecretsManager 单例 (R7 §7.1 服务注册铁律 #2)."""
    global _secrets_manager
    with _secrets_manager_lock:
        if _secrets_manager is None:
            _secrets_manager = SecretsManager(
                key_file_path=key_file_path,
                vault_provider=vault_provider,
            )
        return _secrets_manager


def reset_secrets_manager() -> None:
    """重置单例 (仅测试用)."""
    global _secrets_manager
    with _secrets_manager_lock:
        _secrets_manager = None
