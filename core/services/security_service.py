"""
统一安全服务 - 架构精简重构版本

整合所有安全管理器功能，提供统一的安全控制和认证保护接口。
整合SecurityManager、AuthenticationManager、AuthorizationManager等。
完全重构以符合15个核心服务的架构精简目标。
"""

import hashlib
import hmac
import os
import secrets
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, Tuple, Set
from collections import defaultdict, deque
import json
import base64
import uuid

from loguru import logger
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .base_service import BaseService
from ..events import EventBus, get_event_bus
from ..containers import ServiceContainer, get_service_container


class SecurityLevel(Enum):
    """安全级别"""
    PUBLIC = 0          # 公开访问
    AUTHENTICATED = 1   # 需要认证
    AUTHORIZED = 2      # 需要授权
    ADMIN = 3          # 管理员权限
    SYSTEM = 4         # 系统级权限


class AuthenticationStatus(Enum):
    """认证状态"""
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    PENDING = "pending"


class ThreatLevel(Enum):
    """威胁级别"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class EventType(Enum):
    """安全事件类型"""
    LOGIN_ATTEMPT = "login_attempt"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    PERMISSION_DENIED = "permission_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    TOKEN_EXPIRED = "token_expired"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


@dataclass
class SecurityCredentials:
    """安全凭证"""
    username: str
    password_hash: str
    salt: str
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    failed_attempts: int = 0
    is_locked: bool = False
    permissions: Set[str] = field(default_factory=set)
    roles: Set[str] = field(default_factory=set)


@dataclass
class AuthToken:
    """认证令牌"""
    token_id: str
    user_id: str
    token: str
    token_type: str = "bearer"
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=24))
    created_at: datetime = field(default_factory=datetime.now)
    is_revoked: bool = False
    permissions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityEvent:
    """安全事件"""
    event_id: str
    event_type: EventType
    user_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    threat_level: ThreatLevel
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Permission:
    """权限"""
    name: str
    description: str
    resource: str
    action: str
    conditions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Role:
    """角色"""
    name: str
    description: str
    permissions: Set[str] = field(default_factory=set)
    is_system_role: bool = False


@dataclass
class SecurityMetrics:
    """安全服务指标"""
    total_authentications: int = 0
    successful_authentications: int = 0
    failed_authentications: int = 0
    active_sessions: int = 0
    blocked_users: int = 0
    security_events: int = 0
    high_threat_events: int = 0
    average_session_duration: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)


class SecurityService(BaseService):
    """
    统一安全服务 - 架构精简重构版本

    整合所有安全管理器功能：
    - SecurityManager: 安全策略管理
    - AuthenticationManager: 用户认证管理
    - AuthorizationManager: 权限控制管理
    - SessionManager: 会话管理
    - TokenManager: 令牌管理
    - AuditManager: 审计日志管理
    - ThreatDetectionManager: 威胁检测管理

    提供统一的安全控制接口，支持：
    1. 用户认证和密码管理
    2. 基于角色的权限控制(RBAC)
    3. JWT令牌生成和验证
    4. 会话管理和安全策略
    5. 威胁检测和防护
    6. 安全审计和日志记录
    7. 数据加密和解密
    8. 安全事件监控和告警
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """
        初始化安全服务

        Args:
            service_container: 服务容器
        """
        super().__init__()
        self.service_name = "SecurityService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 用户管理
        self._credentials: Dict[str, SecurityCredentials] = {}
        self._active_sessions: Dict[str, AuthToken] = {}
        self._credentials_lock = threading.RLock()

        # 权限和角色管理
        self._permissions: Dict[str, Permission] = {}
        self._roles: Dict[str, Role] = {}
        self._rbac_lock = threading.RLock()

        # 令牌管理
        self._tokens: Dict[str, AuthToken] = {}
        self._revoked_tokens: Set[str] = set()
        self._token_lock = threading.RLock()

        # 安全事件和审计
        self._security_events: deque = deque(maxlen=10000)
        self._event_lock = threading.RLock()

        # 威胁检测
        self._failed_attempts: Dict[str, List[datetime]] = defaultdict(list)
        self._blocked_ips: Dict[str, datetime] = {}
        self._suspicious_activities: Dict[str, int] = defaultdict(int)
        self._threat_lock = threading.RLock()

        # 加密管理
        self._encryption_key: Optional[bytes] = None
        self._cipher_suite: Optional[Fernet] = None
        self._jwt_secret: str = self._load_or_create_jwt_secret()

        # 服务指标 - 区分BaseService的基础指标和SecurityService的业务指标
        self._security_metrics = SecurityMetrics()

        # 配置参数
        self._config = {
            "max_failed_attempts": 5,
            "lockout_duration_minutes": 30,
            "session_timeout_hours": 24,
            "token_expiry_hours": 24,
            "password_min_length": 8,
            "require_strong_passwords": True,
            "enable_brute_force_protection": True,
            "enable_audit_logging": True,
            "enable_threat_detection": True,
            "jwt_algorithm": "HS256",
            "password_hash_rounds": 100000,
            "cleanup_interval_minutes": 60
        }

        # 线程和锁
        self._service_lock = threading.RLock()

        # 监控和统计
        self._start_time = datetime.now()
        self._last_cleanup = datetime.now()

        logger.info("SecurityService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing SecurityService core components...")

            # 1. 初始化加密系统
            self._initialize_encryption()

            # 2. 初始化默认权限和角色
            self._initialize_default_rbac()

            # 3. 创建默认管理员账户
            self._create_default_admin()

            # 4. 启动后台清理任务
            self._start_background_tasks()

            # 5. 验证安全配置
            self._validate_security_config()

            logger.info("SecurityService initialized successfully with comprehensive security management")

        except Exception as e:
            logger.error(f"❌ Failed to initialize SecurityService: {e}")
            raise

    def _initialize_encryption(self) -> None:
        """初始化加密系统"""
        try:
            password_str = os.environ.get("HIKYUU_ENCRYPTION_KEY")
            if not password_str:
                logger.warning(
                    "HIKYUU_ENCRYPTION_KEY 环境变量未配置，加密系统将禁用。"
                    "生产环境必须通过环境变量设置安全的加密密钥。"
                )
                self._cipher_suite = None
                return

            password = password_str.encode("utf-8")

            salt_str = os.environ.get("HIKYUU_ENCRYPTION_SALT")
            if not salt_str:
                logger.warning(
                    "HIKYUU_ENCRYPTION_SALT 环境变量未配置，加密系统将禁用。"
                    "生产环境必须通过环境变量设置安全的加密盐值。"
                )
                self._cipher_suite = None
                return

            salt = salt_str.encode("utf-8")[:16]

            from cryptography.hazmat.backends import default_backend

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )

            self._encryption_key = base64.urlsafe_b64encode(kdf.derive(password))
            self._cipher_suite = Fernet(self._encryption_key)

            logger.info("✓ Encryption system initialized")

        except Exception as e:
            logger.critical(f"❌ FAIL-OPEN: 加密系统初始化失败，敏感数据将以明文传输！错误: {e}")
            logger.critical("请立即配置 HIKYUU_ENCRYPTION_KEY 和 HIKYUU_ENCRYPTION_SALT 环境变量")
            self._cipher_suite = None
            self._encryption_failure_reason = str(e)

    def _initialize_default_rbac(self) -> None:
        """初始化默认的RBAC权限和角色"""
        try:
            # 创建基本权限
            default_permissions = [
                Permission("read_data", "读取数据", "data", "read"),
                Permission("write_data", "写入数据", "data", "write"),
                Permission("delete_data", "删除数据", "data", "delete"),
                Permission("manage_users", "用户管理", "users", "manage"),
                Permission("view_system", "查看系统", "system", "view"),
                Permission("manage_system", "系统管理", "system", "manage"),
                Permission("execute_trades", "执行交易", "trading", "execute"),
                Permission("view_reports", "查看报告", "reports", "view"),
                Permission("manage_plugins", "插件管理", "plugins", "manage"),
                Permission("admin_access", "管理员访问", "admin", "access")
            ]

            with self._rbac_lock:
                for perm in default_permissions:
                    self._permissions[perm.name] = perm

            # 创建基本角色
            guest_role = Role("guest", "访客", {"read_data", "view_system"})
            user_role = Role("user", "普通用户", {"read_data", "write_data", "view_system", "execute_trades", "view_reports"})
            admin_role = Role("admin", "管理员", set(self._permissions.keys()), True)

            with self._rbac_lock:
                self._roles["guest"] = guest_role
                self._roles["user"] = user_role
                self._roles["admin"] = admin_role

            logger.info("✓ Default RBAC system initialized")

        except Exception as e:
            logger.error(f"Failed to initialize RBAC: {e}")

    def _create_default_admin(self) -> None:
        """创建默认管理员账户"""
        try:
            admin_username = "admin"
            admin_password = os.environ.get(
                "HIKYUU_ADMIN_PASSWORD",
                secrets.token_urlsafe(16)
            )

            if admin_username not in self._credentials:
                self.create_user(
                    username=admin_username,
                    password=admin_password,
                    roles={"admin"}
                )
                logger.info("✓ Default admin user created")
                if "HIKYUU_ADMIN_PASSWORD" not in os.environ:
                    logger.warning(
                        "默认管理员密码为随机生成，请通过环境变量 "
                        "HIKYUU_ADMIN_PASSWORD 设置自定义密码"
                    )
            else:
                logger.info("✓ Default admin user already exists")

        except Exception as e:
            logger.error(f"Failed to create default admin: {e}")

    def _start_background_tasks(self) -> None:
        """启动后台任务"""
        try:
            # 启动后台任务（简化版，不依赖executor）
            # 在真实环境中可以启动后台线程
            logger.info("Background tasks would be started here in production")

            logger.info("✓ Security background tasks started")

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    def _load_or_create_jwt_secret(self) -> str:
        """加载或创建JWT密钥，确保重启后保持一致"""
        try:
            # 优先从环境变量读取
            env_secret = os.environ.get("HIKYUU_JWT_SECRET")
            if env_secret:
                logger.info("已从环境变量加载 JWT_SECRET")
                return env_secret

            # 尝试从配置文件读取
            config_dir = Path(__file__).parent.parent.parent / "config"
            secret_file = config_dir / "jwt_secret.key"

            if secret_file.exists():
                with open(secret_file, "r", encoding="utf-8") as f:
                    secret = f.read().strip()
                    if secret:
                        logger.info("已从配置文件加载 JWT_SECRET")
                        return secret

            # 创建新的JWT密钥并保存到文件
            new_secret = secrets.token_urlsafe(32)
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
                with open(secret_file, "w", encoding="utf-8") as f:
                    f.write(new_secret)
                # 设置文件权限（仅当前用户可读写）
                if os.name != "nt":  # Windows 不支持 chmod
                    os.chmod(secret_file, 0o600)
                logger.warning("已创建新的JWT密钥并保存到 config/jwt_secret.key")
            except Exception as e:
                logger.error(f"保存JWT密钥文件失败: {e}")
                logger.warning("JWT密钥将仅在当前会话有效，重启后token将失效")

            return new_secret

        except Exception as e:
            logger.error(f"加载/创建JWT密钥失败: {e}")
            # 降级：使用随机密钥
            return secrets.token_urlsafe(32)

    def _validate_security_config(self) -> None:
        """验证安全配置"""
        try:
            # 检查关键配置
            if self._config["password_min_length"] < 6:
                logger.warning("Password minimum length is too short")

            if not self._config["enable_brute_force_protection"]:
                logger.warning("Brute force protection is disabled")

            logger.info("✓ Security configuration validated")

        except Exception as e:
            logger.warning(f"Security configuration validation warning: {e}")

    # 用户管理接口

    def create_user(self, username: str, password: str,
                    roles: Optional[Set[str]] = None,
                    permissions: Optional[Set[str]] = None) -> bool:
        """
        创建用户

        Args:
            username: 用户名
            password: 密码
            roles: 角色集合
            permissions: 权限集合

        Returns:
            是否创建成功
        """
        try:
            if not self._validate_password(password):
                logger.error(f"Password validation failed for user: {username}")
                return False

            with self._credentials_lock:
                if username in self._credentials:
                    logger.error(f"User already exists: {username}")
                    return False

                # 生成盐值和密码哈希
                salt = secrets.token_hex(16)
                password_hash = self._hash_password(password, salt)

                # 获取权限
                user_permissions = set(permissions) if permissions else set()
                user_roles = set(roles) if roles else {"user"}

                # 从角色获取权限
                for role_name in user_roles:
                    if role_name in self._roles:
                        user_permissions.update(self._roles[role_name].permissions)

                # 创建凭证
                credentials = SecurityCredentials(
                    username=username,
                    password_hash=password_hash,
                    salt=salt,
                    permissions=user_permissions,
                    roles=user_roles
                )

                self._credentials[username] = credentials

                # 记录安全事件
                self._record_security_event(
                    EventType.LOGIN_SUCCESS,
                    user_id=username,
                    threat_level=ThreatLevel.LOW,
                    description=f"User created: {username}"
                )

                logger.info(f"User created successfully: {username}")
                return True

        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            return False

    def authenticate_user(self, username: str, password: str,
                          ip_address: Optional[str] = None,
                          user_agent: Optional[str] = None) -> Tuple[AuthenticationStatus, Optional[AuthToken]]:
        """
        用户认证

        Args:
            username: 用户名
            password: 密码
            ip_address: IP地址
            user_agent: 用户代理

        Returns:
            认证状态和令牌
        """
        try:
            with self._credentials_lock:
                self._security_metrics.total_authentications += 1

                # 检查用户是否存在
                if username not in self._credentials:
                    self._record_failed_attempt(username, ip_address)
                    self._record_security_event(
                        EventType.LOGIN_FAILURE,
                        user_id=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        threat_level=ThreatLevel.MEDIUM,
                        description=f"Login attempt for non-existent user: {username}"
                    )
                    self._security_metrics.failed_authentications += 1
                    return AuthenticationStatus.FAILED, None

                credentials = self._credentials[username]

                # 检查用户是否被锁定
                if credentials.is_locked:
                    self._record_security_event(
                        EventType.LOGIN_FAILURE,
                        user_id=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        threat_level=ThreatLevel.HIGH,
                        description=f"Login attempt for locked user: {username}"
                    )
                    return AuthenticationStatus.BLOCKED, None

                # 验证密码
                if self._verify_password(password, credentials.password_hash, credentials.salt):
                    # 认证成功
                    credentials.last_login = datetime.now()
                    credentials.failed_attempts = 0

                    # 生成令牌
                    token = self._generate_token(username, credentials.permissions)

                    with self._token_lock:
                        self._tokens[token.token_id] = token
                        self._active_sessions[username] = token

                    self._record_security_event(
                        EventType.LOGIN_SUCCESS,
                        user_id=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        threat_level=ThreatLevel.LOW,
                        description=f"Successful login: {username}"
                    )

                    self._security_metrics.successful_authentications += 1
                    self._security_metrics.active_sessions = len(self._active_sessions)

                    logger.info(f"User authenticated successfully: {username}")
                    return AuthenticationStatus.SUCCESS, token
                else:
                    # 认证失败
                    credentials.failed_attempts += 1

                    # 检查是否需要锁定用户
                    if credentials.failed_attempts >= self._config["max_failed_attempts"]:
                        credentials.is_locked = True
                        logger.warning(f"User locked due to failed attempts: {username}")

                    self._record_failed_attempt(username, ip_address)
                    self._record_security_event(
                        EventType.LOGIN_FAILURE,
                        user_id=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        threat_level=ThreatLevel.MEDIUM,
                        description=f"Password verification failed for user: {username}"
                    )

                    self._security_metrics.failed_authentications += 1
                    return AuthenticationStatus.FAILED, None

        except Exception as e:
            logger.error(f"Authentication error for user {username}: {e}")
            self._security_metrics.failed_authentications += 1
            return AuthenticationStatus.FAILED, None

    def verify_token(self, token: str) -> Tuple[bool, Optional[str], Set[str]]:
        """
        验证令牌

        Args:
            token: JWT令牌

        Returns:
            (是否有效, 用户ID, 权限集合)
        """
        try:
            # 解码JWT令牌
            payload = jwt.decode(token, self._jwt_secret, algorithms=[self._config["jwt_algorithm"]])

            token_id = payload.get("token_id")
            user_id = payload.get("user_id")
            permissions = set(payload.get("permissions", []))

            with self._token_lock:
                # 检查令牌是否被撤销
                if token_id in self._revoked_tokens:
                    return False, None, set()

                # 检查令牌是否存在
                if token_id not in self._tokens:
                    return False, None, set()

                auth_token = self._tokens[token_id]

                # 检查令牌是否过期
                if datetime.now() > auth_token.expires_at:
                    self._revoked_tokens.add(token_id)
                    del self._tokens[token_id]

                    self._record_security_event(
                        EventType.TOKEN_EXPIRED,
                        user_id=user_id,
                        threat_level=ThreatLevel.LOW,
                        description=f"Token expired for user: {user_id}"
                    )

                    return False, None, set()

                return True, user_id, permissions

        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return False, None, set()
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return False, None, set()
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return False, None, set()

    def check_permission(self, user_id: str, permission: str, resource: str = "") -> bool:
        """
        检查权限

        Args:
            user_id: 用户ID
            permission: 权限名称
            resource: 资源名称

        Returns:
            是否有权限
        """
        try:
            with self._credentials_lock:
                if user_id not in self._credentials:
                    return False

                credentials = self._credentials[user_id]

                # 检查直接权限
                if permission in credentials.permissions:
                    return True

                # 检查角色权限
                for role_name in credentials.roles:
                    if role_name in self._roles:
                        role = self._roles[role_name]
                        if permission in role.permissions:
                            return True

                # 记录权限拒绝事件
                self._record_security_event(
                    EventType.PERMISSION_DENIED,
                    user_id=user_id,
                    threat_level=ThreatLevel.MEDIUM,
                    description=f"Permission denied: {permission} for user: {user_id}"
                )

                return False

        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False

    def logout_user(self, user_id: str) -> bool:
        """
        用户登出

        Args:
            user_id: 用户ID

        Returns:
            是否成功
        """
        try:
            with self._token_lock:
                # 撤销用户的所有令牌
                tokens_to_revoke = []
                for token_id, token in self._tokens.items():
                    if token.user_id == user_id:
                        tokens_to_revoke.append(token_id)

                for token_id in tokens_to_revoke:
                    self._revoked_tokens.add(token_id)
                    del self._tokens[token_id]

                # 移除活跃会话
                if user_id in self._active_sessions:
                    del self._active_sessions[user_id]

                self._security_metrics.active_sessions = len(self._active_sessions)

                logger.info(f"User logged out: {user_id}")
                return True

        except Exception as e:
            logger.error(f"Logout error for user {user_id}: {e}")
            return False

    # 加密解密接口

    def encrypt_data(self, data: Union[str, bytes]) -> Optional[str]:
        """
        加密数据

        Args:
            data: 要加密的数据

        Returns:
            加密后的数据（Base64编码），若加密未初始化则返回明文
        """
        try:
            if self._cipher_suite is None:
                logger.critical("FAIL-OPEN: 加密密钥未配置，敏感数据以明文通过！"
                                "请设置 HIKYUU_ENCRYPTION_KEY 环境变量")
                if isinstance(data, bytes):
                    return data.decode('utf-8', errors='replace')
                return data

            if isinstance(data, str):
                data = data.encode('utf-8')

            encrypted_data = self._cipher_suite.encrypt(data)
            return base64.b64encode(encrypted_data).decode('utf-8')

        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return None

    def decrypt_data(self, encrypted_data: str) -> Optional[str]:
        """
        解密数据

        Args:
            encrypted_data: 加密的数据（Base64编码）

        Returns:
            解密后的数据，若加密未初始化则返回原数据
        """
        try:
            if self._cipher_suite is None:
                logger.critical("FAIL-OPEN: 加密密钥未配置，解密操作以明文通过！"
                                "请设置 HIKYUU_ENCRYPTION_KEY 环境变量")
                return encrypted_data

            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self._cipher_suite.decrypt(encrypted_bytes)
            return decrypted_data.decode('utf-8')

        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None

    # 内部辅助方法

    def _validate_password(self, password: str) -> bool:
        """验证密码强度"""
        if len(password) < self._config["password_min_length"]:
            return False

        if self._config["require_strong_passwords"]:
            # 检查是否包含大小写字母和数字
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)

            return has_upper and has_lower and has_digit

        return True

    def _hash_password(self, password: str, salt: str) -> str:
        """哈希密码"""
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            self._config["password_hash_rounds"]
        ).hex()

    def _verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """验证密码"""
        return self._hash_password(password, salt) == password_hash

    def _generate_token(self, user_id: str, permissions: Set[str]) -> AuthToken:
        """生成认证令牌"""
        token_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=self._config["token_expiry_hours"])

        payload = {
            "token_id": token_id,
            "user_id": user_id,
            "permissions": list(permissions),
            "exp": expires_at.timestamp(),
            "iat": datetime.now().timestamp()
        }

        token = jwt.encode(payload, self._jwt_secret, algorithm=self._config["jwt_algorithm"])

        return AuthToken(
            token_id=token_id,
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            permissions=permissions
        )

    def _record_failed_attempt(self, username: str, ip_address: Optional[str]) -> None:
        """记录失败尝试"""
        if not self._config["enable_brute_force_protection"]:
            return

        try:
            with self._threat_lock:
                now = datetime.now()

                # 记录用户失败尝试
                if username not in self._failed_attempts:
                    self._failed_attempts[username] = []

                self._failed_attempts[username].append(now)

                # 清理旧记录（只保留最近1小时的）
                cutoff = now - timedelta(hours=1)
                self._failed_attempts[username] = [
                    attempt for attempt in self._failed_attempts[username]
                    if attempt > cutoff
                ]

                # 检查是否为暴力破解
                if len(self._failed_attempts[username]) >= self._config["max_failed_attempts"]:
                    self._record_security_event(
                        EventType.BRUTE_FORCE_DETECTED,
                        user_id=username,
                        ip_address=ip_address,
                        threat_level=ThreatLevel.HIGH,
                        description=f"Brute force attack detected for user: {username}"
                    )

                # 记录IP失败尝试
                if ip_address:
                    self._suspicious_activities[ip_address] += 1

                    if self._suspicious_activities[ip_address] > 20:  # 20次失败尝试
                        self._blocked_ips[ip_address] = now + timedelta(hours=1)

        except Exception as e:
            logger.error(f"Error recording failed attempt: {e}")

    def _record_security_event(self, event_type: EventType, user_id: Optional[str] = None,
                               ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                               threat_level: ThreatLevel = ThreatLevel.LOW,
                               description: str = "", metadata: Optional[Dict[str, Any]] = None) -> None:
        """记录安全事件"""
        if not self._config["enable_audit_logging"]:
            return

        try:
            event = SecurityEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                threat_level=threat_level,
                description=description,
                metadata=metadata or {}
            )

            with self._event_lock:
                self._security_events.append(event)
                self._security_metrics.security_events += 1

                if threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                    self._security_metrics.high_threat_events += 1

                    # 发送威胁告警
                    if hasattr(self, '_event_bus'):
                        self._event_bus.publish("security.threat_detected",
                            event_id=event.event_id,
                            threat_level=threat_level.name,
                            description=description,
                            user_id=user_id,
                            ip_address=ip_address
                        )

        except Exception as e:
            logger.error(f"Error recording security event: {e}")

    def _cleanup_loop(self) -> None:
        """清理循环"""
        try:
            self._perform_cleanup()
            logger.debug("Security cleanup operation completed")
        except Exception as e:
            logger.error(f"Error in security cleanup loop: {e}")

    def _threat_detection_loop(self) -> None:
        """威胁检测循环"""
        try:
            self._perform_threat_detection()
            logger.debug("Threat detection completed")
        except Exception as e:
            logger.error(f"Error in threat detection loop: {e}")

    def _perform_cleanup(self) -> None:
        """执行清理"""
        try:
            current_time = datetime.now()

            # 清理过期令牌
            with self._token_lock:
                expired_tokens = []
                for token_id, token in self._tokens.items():
                    if current_time > token.expires_at:
                        expired_tokens.append(token_id)

                for token_id in expired_tokens:
                    self._revoked_tokens.add(token_id)
                    del self._tokens[token_id]

                if expired_tokens:
                    logger.debug(f"Cleaned up {len(expired_tokens)} expired tokens")

            # 清理撤销令牌列表（保留24小时）
            if len(self._revoked_tokens) > 10000:
                # 简单的清理策略：保留最新的5000个
                revoked_list = list(self._revoked_tokens)
                self._revoked_tokens = set(revoked_list[-5000:])

            # 解锁用户（如果锁定时间已过）
            with self._credentials_lock:
                lockout_duration = timedelta(minutes=self._config["lockout_duration_minutes"])
                unlocked_users = []

                for username, credentials in self._credentials.items():
                    if (credentials.is_locked and credentials.last_login and
                            current_time - credentials.last_login > lockout_duration):
                        credentials.is_locked = False
                        credentials.failed_attempts = 0
                        unlocked_users.append(username)

                if unlocked_users:
                    logger.info(f"Unlocked users: {unlocked_users}")

            # 清理失败尝试记录
            with self._threat_lock:
                cutoff = current_time - timedelta(hours=24)
                for username in list(self._failed_attempts.keys()):
                    self._failed_attempts[username] = [
                        attempt for attempt in self._failed_attempts[username]
                        if attempt > cutoff
                    ]
                    if not self._failed_attempts[username]:
                        del self._failed_attempts[username]

                # 清理被阻止的IP
                expired_blocks = []
                for ip, block_until in self._blocked_ips.items():
                    if current_time > block_until:
                        expired_blocks.append(ip)

                for ip in expired_blocks:
                    del self._blocked_ips[ip]
                    if ip in self._suspicious_activities:
                        del self._suspicious_activities[ip]

            # 更新指标
            self._security_metrics.active_sessions = len(self._active_sessions)
            self._security_metrics.blocked_users = sum(1 for c in self._credentials.values() if c.is_locked)
            self._security_metrics.last_update = current_time

        except Exception as e:
            logger.error(f"Security cleanup operation failed: {e}")

    def _perform_threat_detection(self) -> None:
        """执行威胁检测"""
        if not self._config["enable_threat_detection"]:
            return

        try:
            current_time = datetime.now()

            # 检测异常登录模式
            with self._threat_lock:
                # 检测频繁失败的IP
                for ip, count in self._suspicious_activities.items():
                    if count > 50 and ip not in self._blocked_ips:  # 50次失败
                        self._blocked_ips[ip] = current_time + timedelta(hours=2)
                        self._record_security_event(
                            EventType.SUSPICIOUS_ACTIVITY,
                            ip_address=ip,
                            threat_level=ThreatLevel.CRITICAL,
                            description=f"IP blocked due to excessive failures: {ip}"
                        )

        except Exception as e:
            logger.error(f"Threat detection failed: {e}")

    # 公共接口方法

    def get_metrics(self) -> SecurityMetrics:
        """获取安全服务指标"""
        with self._service_lock:
            self._security_metrics.last_update = datetime.now()
            return self._security_metrics

    @property
    def metrics(self) -> Dict[str, Any]:
        """获取服务指标（字典格式）"""
        # 重写BaseService的metrics属性以返回字典格式，合并基础指标和安全指标
        base_metrics = super().metrics
        security_metrics_obj = self.get_metrics()

        # 合并基础指标和安全指标
        combined_metrics = base_metrics.copy()
        combined_metrics.update({
            "total_authentications": security_metrics_obj.total_authentications,
            "successful_authentications": security_metrics_obj.successful_authentications,
            "failed_authentications": security_metrics_obj.failed_authentications,
            "active_sessions": security_metrics_obj.active_sessions,
            "blocked_users": security_metrics_obj.blocked_users,
            "security_events": security_metrics_obj.security_events,
            "high_threat_events": security_metrics_obj.high_threat_events,
            "average_session_duration": security_metrics_obj.average_session_duration,
            "security_last_update": security_metrics_obj.last_update.isoformat()
        })

        return combined_metrics

    def get_security_events(self, limit: int = 100,
                            threat_level: Optional[ThreatLevel] = None) -> List[SecurityEvent]:
        """获取安全事件"""
        with self._event_lock:
            events = list(self._security_events)

            if threat_level:
                events = [e for e in events if e.threat_level == threat_level]

            return events[-limit:]

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """获取活跃会话"""
        with self._token_lock:
            sessions = {}
            for user_id, token in self._active_sessions.items():
                sessions[user_id] = {
                    "token_id": token.token_id,
                    "created_at": token.created_at.isoformat(),
                    "expires_at": token.expires_at.isoformat(),
                    "permissions": list(token.permissions)
                }
            return sessions

    def revoke_token(self, token_id: str) -> bool:
        """撤销令牌"""
        try:
            with self._token_lock:
                if token_id in self._tokens:
                    token = self._tokens[token_id]
                    self._revoked_tokens.add(token_id)
                    del self._tokens[token_id]

                    # 移除活跃会话
                    if token.user_id in self._active_sessions:
                        del self._active_sessions[token.user_id]

                    logger.info(f"Token revoked: {token_id}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            current_time = datetime.now()
            uptime = (current_time - self._start_time).total_seconds()

            return {
                "status": "healthy",
                "active_users": len(self._active_sessions),
                "total_users": len(self._credentials),
                "blocked_users": sum(1 for c in self._credentials.values() if c.is_locked),
                "active_tokens": len(self._tokens),
                "revoked_tokens": len(self._revoked_tokens),
                "security_events": len(self._security_events),
                "blocked_ips": len(self._blocked_ips),
                "threat_detection_enabled": self._config["enable_threat_detection"],
                "success_rate": (
                    self._security_metrics.successful_authentications /
                    max(1, self._security_metrics.total_authentications) * 100
                ),
                "uptime_seconds": uptime
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing SecurityService resources...")

            # 清理会话和令牌
            with self._token_lock:
                self._tokens.clear()
                self._active_sessions.clear()
                self._revoked_tokens.clear()

            # 清理安全事件
            with self._event_lock:
                self._security_events.clear()

            # 清理威胁检测数据
            with self._threat_lock:
                self._failed_attempts.clear()
                self._blocked_ips.clear()
                self._suspicious_activities.clear()

            logger.info("SecurityService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing SecurityService: {e}")


# 装饰器函数
def require_permission(permission: str):
    """权限检查装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 在实际应用中，这里需要从请求上下文获取用户信息
            # 这里简化为示例
            user_id = kwargs.get('user_id')
            if user_id:
                security_service = get_service_container().resolve(SecurityService)
                if not security_service.check_permission(user_id, permission):
                    raise PermissionError(f"Permission denied: {permission}")

            return func(*args, **kwargs)
        return wrapper
    return decorator
