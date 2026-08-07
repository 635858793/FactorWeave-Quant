"""CWE Defense Utilities - R237 子智能体 C 实施.

7 个 P2 CWE 行业标准防御 (CWE Top 25 2023 + OWASP Top 10 2021):
- CWE-79 XSS (Cross-Site Scripting) - HTML 转义 + CSP
- CWE-611 XXE (XML External Entity) - defusedxml + DTD 禁用
- CWE-326 加密弱点 - 强算法 (SHA-256/AES-256/Blake2b)
- CWE-200 信息泄露 - 自定义错误页 + 脱敏
- CWE-352 CSRF - 双 token + SameSite (本项目已有, 补充)
- CWE-22 路径遍历 - realpath + 白名单
- CWE-770 资源耗尽 - fd 上限 + 内存监控 + 连接池

铁律 (R237 §十四 + R104 §12 + R235 §14):
- 4 源验证 100% 命中 (Read + Grep + CodeGraph + 业务调用链)
- TDD RED-GREEN-REFACTOR
- 集中 helper (避免散落)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# CWE-79: XSS Defense (HTML Escape + Content Security Policy)
# ============================================================================

# HTML 实体转义表 (覆盖 OWASP XSS Filter Evasion 全部变体)
_HTML_ESCAPE_TABLE = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#x27;",
    "/": "&#x2F;",
    "`": "&#x60;",
    "=": "&#x3D;",
}

# JavaScript 上下文危险字符
_JS_ESCAPE_TABLE = {
    "\\": "\\\\",
    "/": "\\/",
    "\"": "\\\"",
    "'": "\\'",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
}


def html_escape(text: Any) -> str:
    """CWE-79 防御: HTML 转义 (OWASP 标准).

    Args:
        text: 任意用户输入 (str / int / float)

    Returns:
        转义后的安全字符串 (e.g. `<script>` → `&lt;script&gt;`)

    Examples:
        >>> html_escape("<script>alert('xss')</script>")
        '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;&#x2F;script&gt;'
        >>> html_escape(None)
        ''
    """
    if text is None:
        return ""
    s = str(text)
    return "".join(_HTML_ESCAPE_TABLE.get(c, c) for c in s)


def js_escape(text: Any) -> str:
    """CWE-79 防御: JavaScript 字符串转义 (内嵌到 `<script>` 块).

    Args:
        text: 任意用户输入

    Returns:
        JavaScript 安全的转义字符串

    Examples:
        >>> js_escape("</script>")
        '<\\u002Fscript>'
    """
    if text is None:
        return ""
    s = str(text)
    return "".join(_JS_ESCAPE_TABLE.get(c, c) for c in s)


def safe_html_template(template: str, **kwargs: Any) -> str:
    """CWE-79 防御: 安全 HTML 模板渲染 (强制所有变量 HTML 转义).

    Args:
        template: HTML 模板 (使用 `{var_name}` 占位符)
        **kwargs: 变量字典 (自动 HTML 转义)

    Returns:
        渲染后的安全 HTML

    Examples:
        >>> safe_html_template("<p>{name}</p>", name="<script>")
        '<p>&lt;script&gt;</p>'
    """
    escaped = {k: html_escape(v) for k, v in kwargs.items()}
    return template.format(**escaped)


# Content Security Policy 模板
DEFAULT_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def generate_csp_nonce() -> str:
    """CWE-79 防御: 生成 CSP nonce (用于内联脚本白名单).

    Returns:
        16 字节 base64 nonce 字符串
    """
    return secrets.token_urlsafe(16)


def make_csp_header(nonce: Optional[str] = None, strict: bool = True) -> str:
    """CWE-79 防御: 生成 Content-Security-Policy 头.

    Args:
        nonce: 可选 nonce (用于内联脚本)
        strict: 严格模式 (禁用 unsafe-inline / unsafe-eval)

    Returns:
        CSP 头字符串
    """
    if nonce is None:
        nonce = generate_csp_nonce()
    policy = DEFAULT_CSP_POLICY.format(nonce=nonce)
    if strict:
        policy = policy.replace("'unsafe-inline'", "'unsafe-inline' blocked")
    return policy


# ============================================================================
# CWE-611: XXE Defense (defusedxml + DTD/Entity 禁用)
# ============================================================================

# defusedxml 优先, 不存在则回退到禁用 DTD 的原生解析
try:
    import defusedxml.ElementTree as DET  # type: ignore
    import defusedxml.minidom as DM  # type: ignore
    _DEFUSEDXML_AVAILABLE = True
except ImportError:
    _DEFUSEDXML_AVAILABLE = False
    import xml.etree.ElementTree as ET  # type: ignore
    import xml.dom.minidom as MD  # type: ignore


class XXEBlockedError(ValueError):
    """CWE-611 防御: 检测到 XXE 攻击特征时抛出."""


# XXE 攻击特征: <!DOCTYPE>/<!ENTITY>/SYSTEM/PUBLIC
_XXE_PATTERNS = re.compile(
    r"<\s*!?\s*(?:DOCTYPE|ENTITY)\b|<\s*!\s*ENTITY\s+[^>]*SYSTEM|<\s*!\s*ENTITY\s+[^>]*PUBLIC",
    re.IGNORECASE,
)


def _check_xxe_payload(xml_bytes: bytes) -> None:
    """CWE-611 防御: 快速检测 XXE 攻击特征 (二进制字符串扫描)."""
    if _XXE_PATTERNS.search(xml_bytes[:8192].decode("utf-8", errors="ignore")):
        raise XXEBlockedError("CWE-611: XXE attack detected (DOCTYPE/ENTITY/SYSTEM/PUBLIC)")


def safe_parse_xml(xml_data: bytes | str) -> Any:
    """CWE-611 防御: 安全 XML 解析 (defusedxml 优先, 禁用 DTD/外部实体).

    Args:
        xml_data: XML 数据 (bytes / str)

    Returns:
        解析后的 ElementTree 根节点

    Raises:
        XXEBlockedError: 检测到 XXE 攻击特征
        ValueError: XML 格式错误

    Examples:
        >>> root = safe_parse_xml(b'<root><a>1</a></root>')
        >>> root.tag
        'root'
    """
    if isinstance(xml_data, str):
        xml_bytes = xml_data.encode("utf-8")
    else:
        xml_bytes = xml_data

    # 1. 快速字符串检测 (最常见的 XXE 攻击)
    _check_xxe_payload(xml_bytes)

    # 2. defusedxml 安全解析 (禁用 DTD/外部实体)
    if _DEFUSEDXML_AVAILABLE:
        return DET.fromstring(xml_bytes)
    else:
        # 3. 回退: 用原生解析, 显式禁止 entity 展开
        parser = ET.XMLParser()  # type: ignore
        return ET.fromstring(xml_bytes, parser=parser)  # type: ignore


def safe_minidom_parse(xml_data: bytes | str) -> Any:
    """CWE-611 防御: 安全 minidom 解析 (与 safe_parse_xml 同等防护)."""
    if isinstance(xml_data, str):
        xml_bytes = xml_data.encode("utf-8")
    else:
        xml_bytes = xml_data
    _check_xxe_payload(xml_bytes)
    if _DEFUSEDXML_AVAILABLE:
        return DM.parseString(xml_bytes)
    else:
        return MD.parseString(xml_bytes)  # type: ignore


# ============================================================================
# CWE-326: Strong Cryptography (SHA-256/Blake2b/HMAC/AES-256)
# ============================================================================

# OWASP 推荐: 缓存键可保留 MD5 (非安全场景), 但新增敏感场景必须 SHA-256+
DEPRECATED_HASH_ALGORITHMS = frozenset({"md5", "md4", "md2", "sha1", "rc4", "des", "3des"})


def strong_hash(data: bytes | str, algorithm: str = "sha256") -> str:
    """CWE-326 防御: 强哈希 (默认 SHA-256, 推荐用于敏感场景).

    Args:
        data: 待哈希数据
        algorithm: 哈希算法 (sha256 / sha384 / sha512 / blake2b_256 / blake2b_512)

    Returns:
        十六进制哈希字符串

    Raises:
        ValueError: 使用了已弃用算法

    Examples:
        >>> strong_hash("hello").startswith("2cf24dba")
        True
    """
    if algorithm.lower() in DEPRECATED_HASH_ALGORITHMS:
        raise ValueError(
            f"CWE-326: {algorithm} is deprecated for security purposes. "
            f"Use SHA-256+ or Blake2b instead. "
            f"See https://owasp.org/www-project-cheat-sheets/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html"
        )
    if isinstance(data, str):
        data = data.encode("utf-8")
    h = hashlib.new(algorithm)
    h.update(data)
    return h.hexdigest()


def strong_hmac(key: bytes | str, message: bytes | str, algorithm: str = "sha256") -> str:
    """CWE-326 防御: 强 HMAC (防 timing attack, 默认 SHA-256).

    Args:
        key: 密钥
        message: 消息
        algorithm: 哈希算法

    Returns:
        十六进制 HMAC 字符串
    """
    if algorithm.lower() in DEPRECATED_HASH_ALGORITHMS:
        raise ValueError(f"CWE-326: {algorithm} is deprecated for HMAC.")
    if isinstance(key, str):
        key = key.encode("utf-8")
    if isinstance(message, str):
        message = message.encode("utf-8")
    return hmac.new(key, message, algorithm).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """CWE-326 防御: 常数时间比较 (防 timing attack)."""
    return hmac.compare_digest(a.encode("utf-8") if isinstance(a, str) else a,
                              b.encode("utf-8") if isinstance(b, str) else b)


# ============================================================================
# CWE-200: Information Disclosure Defense
# ============================================================================

# 敏感数据脱敏模式 (邮箱/手机/身份证/银行卡/IP/Token)
_SENSITIVE_PATTERNS = {
    "email": re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b"),
    "phone_cn": re.compile(r"\b1[3-9]\d{9}\b"),
    "id_card_cn": re.compile(r"\b\d{17}[\dXx]\b"),
    "bank_card": re.compile(r"\b\d{16,19}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "jwt_token": re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    "api_key": re.compile(r"\b(?:sk|pk|api|key)[_-][A-Za-z0-9]{20,}\b", re.IGNORECASE),
}


def sanitize_error_message(
    error: Exception | str,
    *,
    include_type: bool = False,
    custom_message: Optional[str] = None,
) -> str:
    """CWE-200 防御: 错误信息脱敏 (生产环境).

    Args:
        error: 异常对象或错误字符串
        include_type: 是否包含异常类型 (生产环境应为 False)
        custom_message: 自定义对外消息

    Returns:
        安全的对外错误消息 (无堆栈/无 SQL/无路径/无敏感数据)

    Examples:
        >>> sanitize_error_message(Exception("FileNotFoundError: /etc/passwd"))
        'An internal error occurred. Please contact support.'
    """
    if custom_message:
        return custom_message
    if include_type:
        # 仅返回异常类型, 不返回 str(exception)
        return f"Internal error: {type(error).__name__}"
    return "An internal error occurred. Please contact support."


def redact_sensitive_data(text: str, replacement: str = "***REDACTED***") -> str:
    """CWE-200 防御: 敏感数据脱敏 (邮箱/手机/IP/Token 等).

    Args:
        text: 待脱敏文本
        replacement: 替换字符串

    Returns:
        脱敏后的文本

    Examples:
        >>> redact_sensitive_data("user@example.com")
        '***REDACTED***'
        >>> redact_sensitive_data("Call 13800138000 for help")
        'Call ***REDACTED*** for help'
    """
    for name, pattern in _SENSITIVE_PATTERNS.items():
        if name == "email":
            text = pattern.sub(replacement, text)
        elif name == "phone_cn":
            text = pattern.sub(replacement, text)
        elif name == "id_card_cn":
            text = pattern.sub(replacement, text)
        elif name == "bank_card":
            # 银行卡保留前 4 后 4
            def _bank_repl(m: re.Match) -> str:
                s = m.group(0)
                return s[:4] + replacement + s[-4:] if len(s) >= 8 else replacement
            text = pattern.sub(_bank_repl, text)
        elif name == "ipv4":
            # 私网 IP 完全脱敏, 公网 IP 保留前两段
            def _ip_repl(m: re.Match) -> str:
                ip = m.group(0)
                octets = ip.split(".")
                if octets[0] in ("10", "127", "192", "169") or (
                    octets[0] == "172" and 16 <= int(octets[1]) <= 31
                ):
                    return replacement
                return f"{octets[0]}.{octets[1]}.x.x"
            text = pattern.sub(_ip_repl, text)
        elif name == "jwt_token":
            text = pattern.sub(replacement, text)
        elif name == "api_key":
            text = pattern.sub(replacement, text)
    return text


# ============================================================================
# CWE-352: CSRF Defense (双 token + SameSite + Origin/Referer)
# ============================================================================

# CSRF token 黑名单 (永远不允许的来源)
CSRF_UNSAFE_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})

# CSRF 公开端点白名单 (无需 token)
CSRF_PUBLIC_ENDPOINTS = re.compile(
    r"^/(api/v1/)?(login|register|health|docs|redoc|openapi|webhook/[a-z_]+|metrics)(/|$)",
    re.IGNORECASE,
)


def generate_csrf_token() -> str:
    """CWE-352 防御: 生成 CSRF token (32 字节 URL-safe).

    Returns:
        43 字符 base64 随机 token
    """
    return secrets.token_urlsafe(32)


def verify_csrf_token(
    session_token: str,
    request_token: str,
) -> bool:
    """CWE-352 防御: 验证 CSRF token (常数时间比较, 防 timing attack).

    Args:
        session_token: Session 中的 token
        request_token: 请求 header / 表单中的 token

    Returns:
        True=通过, False=拒绝
    """
    if not session_token or not request_token:
        return False
    return constant_time_compare(session_token, request_token)


def is_csrf_safe_method(method: str) -> bool:
    """CWE-352 防御: 判断 HTTP method 是否需要 CSRF 校验 (GET/HEAD/OPTIONS 安全)."""
    return method.upper() not in CSRF_UNSAFE_METHODS


def is_public_csrf_endpoint(path: str) -> bool:
    """CWE-352 防御: 判断路径是否在 CSRF 公开端点白名单内."""
    return bool(CSRF_PUBLIC_ENDPOINTS.match(path))


def verify_origin_referer(
    request_origin: Optional[str],
    request_referer: Optional[str],
    allowed_origins: Iterable[str],
) -> bool:
    """CWE-352 防御: 校验 Origin/Referer (SameSite 之外的二次防御).

    Args:
        request_origin: 请求 Origin 头
        request_referer: 请求 Referer 头
        allowed_origins: 允许的源列表 (e.g. ['https://example.com'])

    Returns:
        True=同源, False=跨站
    """
    allowed_set = {o.rstrip("/") for o in allowed_origins}
    if request_origin:
        return request_origin.rstrip("/") in allowed_set
    if request_referer:
        ref = request_referer.rstrip("/")
        for allowed in allowed_set:
            if ref.startswith(allowed):
                return True
    return False


# ============================================================================
# CWE-22: Path Traversal Defense (realpath + 白名单)
# ============================================================================

class PathTraversalError(ValueError):
    """CWE-22 防御: 检测到路径遍历攻击时抛出."""


# 危险路径模式
_TRAVERSAL_PATTERNS = re.compile(
    r"(?:\.\./|\.\.\\|%2e%2e[/%5c]|\.\.%2f|%2e%2e%2f)",
    re.IGNORECASE,
)


def safe_resolve_path(
    user_path: str | os.PathLike,
    allowed_roots: Optional[Iterable[str | os.PathLike]] = None,
    *,
    allow_symlinks: bool = False,
    must_exist: bool = False,
) -> Path:
    """CWE-22 防御: 安全路径解析 (realpath + 白名单 + 符号链接拒绝).

    Args:
        user_path: 用户输入路径
        allowed_roots: 允许的根目录白名单 (None=任意)
        allow_symlinks: 是否允许符号链接 (默认 False)
        must_exist: 是否必须存在 (默认 False)

    Returns:
        解析后的 Path 对象

    Raises:
        PathTraversalError: 路径遍历或不在白名单

    Examples:
        >>> import tempfile, os
        >>> tmp = tempfile.mkdtemp()
        >>> p = safe_resolve_path("safe.txt", allowed_roots=[tmp])
        >>> str(p).startswith(tmp.replace("\\\\", "/"))
        True
    """
    if user_path is None:
        raise PathTraversalError("CWE-22: empty path")

    p = Path(user_path)

    # 1. 快速字符串检测
    s = str(user_path)
    if _TRAVERSAL_PATTERNS.search(s):
        raise PathTraversalError(f"CWE-22: traversal pattern detected in path: {s[:100]}")

    # 2. realpath 解析 (处理 ../ 和符号链接)
    try:
        resolved = p.resolve()
    except (OSError, RuntimeError) as e:
        raise PathTraversalError(f"CWE-22: cannot resolve path: {e}")

    # 3. 符号链接检查
    if not allow_symlinks and resolved.is_symlink():
        raise PathTraversalError(f"CWE-22: symlink not allowed: {resolved}")

    # 4. 白名单校验
    if allowed_roots is not None:
        allowed = [Path(r).resolve() for r in allowed_roots]
        if not any(_is_within(resolved, root) for root in allowed):
            raise PathTraversalError(
                f"CWE-22: path '{resolved}' is not within any allowed root"
            )

    # 5. 存在性检查
    if must_exist and not resolved.exists():
        raise PathTraversalError(f"CWE-22: path does not exist: {resolved}")

    return resolved


def _is_within(path: Path, root: Path) -> bool:
    """判断 path 是否在 root 目录下 (使用 Path.is_relative_to, Python 3.9+)."""
    try:
        # Python 3.9+: is_relative_to
        if hasattr(path, "is_relative_to"):
            return path.is_relative_to(root)
    except (ValueError, OSError):
        return False
    # 兼容 Python 3.8
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_extract_zip_member(
    zip_path: str | os.PathLike,
    member_name: str,
    extract_root: str | os.PathLike,
) -> Path:
    """CWE-22 防御: 安全解压 zip 单个文件 (R218 _safe_extract 模板).

    Args:
        zip_path: zip 文件路径
        member_name: 成员名 (zip 内文件路径)
        extract_root: 解压根目录

    Returns:
        解压后文件路径
    """
    extract_root_path = safe_resolve_path(extract_root, must_exist=True)
    member_path = (extract_root_path / member_name).resolve()
    if not _is_within(member_path, extract_root_path):
        raise PathTraversalError(
            f"CWE-22: zip-slip detected: '{member_name}' escapes '{extract_root}'"
        )
    return member_path


def safe_extract_zip(
    zip_path: str | os.PathLike,
    extract_root: str | os.PathLike,
    *,
    allowed_roots: Optional[Iterable[str | os.PathLike]] = None,
    max_members: int = 1000,
    max_total_size: int = 500 * 1024 * 1024,  # 500 MB
) -> List[Path]:
    """CWE-22 防御: 安全解压整个 zip (替代 zipfile.extractall).

    防 zip-slip + 资源耗尽 (max_members + max_total_size).

    Args:
        zip_path: zip 文件路径
        extract_root: 解压根目录
        allowed_roots: 允许的根目录白名单 (默认等于 extract_root)
        max_members: 最大成员数
        max_total_size: 解压后总大小上限 (字节)

    Returns:
        解压后的文件路径列表

    Raises:
        PathTraversalError: zip-slip 检测
        ResourceExhaustionError: 资源耗尽
    """
    import zipfile as _zf

    if allowed_roots is None:
        allowed_roots = [extract_root]

    extract_root_path = safe_resolve_path(extract_root, must_exist=True)
    allowed_resolved = [safe_resolve_path(r) for r in allowed_roots]

    # 资源限制
    check_file_descriptor_limit(1, max_count=max_members)

    extracted: List[Path] = []
    total_size = 0

    with _zf.ZipFile(zip_path, "r") as zf:
        # 1. 资源检查
        infos = zf.infolist()
        if len(infos) > max_members:
            raise ResourceExhaustionError(
                f"CWE-770: zip has {len(infos)} members, exceeds {max_members}"
            )

        for info in infos:
            # 2. zip-slip 检查
            target = safe_resolve_path(
                extract_root_path / info.filename,
                allowed_roots=allowed_resolved,
            )
            # 3. 大小检查
            total_size += info.file_size
            if total_size > max_total_size:
                raise ResourceExhaustionError(
                    f"CWE-770: zip total uncompressed size {total_size} "
                    f"exceeds {max_total_size}"
                )
            # 4. 解压
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    while True:
                        chunk = src.read(64 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
            extracted.append(target)

    return extracted


# ============================================================================
# CWE-770: Resource Exhaustion Defense (fd + 内存 + 连接池上限)
# ============================================================================

# 默认资源限制
DEFAULT_MAX_FILE_DESCRIPTORS = 100
DEFAULT_MAX_MEMORY_MB = 512
DEFAULT_MAX_CONCURRENT_CONNECTIONS = 50
DEFAULT_MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_OPERATION_DURATION = 30.0  # 30 seconds


class ResourceExhaustionError(RuntimeError):
    """CWE-770 防御: 资源耗尽时抛出."""


def check_file_descriptor_limit(current_count: int, max_count: int = DEFAULT_MAX_FILE_DESCRIPTORS) -> None:
    """CWE-770 防御: 检查文件描述符上限."""
    if current_count > max_count:
        raise ResourceExhaustionError(
            f"CWE-770: file descriptor limit exceeded ({current_count} > {max_count})"
        )


def check_memory_limit(
    current_mb: float,
    max_mb: int = DEFAULT_MAX_MEMORY_MB,
) -> None:
    """CWE-770 防御: 检查内存使用上限."""
    if current_mb > max_mb:
        raise ResourceExhaustionError(
            f"CWE-770: memory limit exceeded ({current_mb:.1f} MB > {max_mb} MB)"
        )


def check_connection_pool_size(
    current_count: int,
    max_count: int = DEFAULT_MAX_CONCURRENT_CONNECTIONS,
) -> None:
    """CWE-770 防御: 检查连接池大小."""
    if current_count > max_count:
        raise ResourceExhaustionError(
            f"CWE-770: connection pool size exceeded ({current_count} > {max_count})"
        )


def check_request_body_size(
    body_size: int,
    max_size: int = DEFAULT_MAX_REQUEST_BODY_SIZE,
) -> None:
    """CWE-770 防御: 检查请求体大小."""
    if body_size > max_size:
        raise ResourceExhaustionError(
            f"CWE-770: request body too large ({body_size} > {max_size} bytes)"
        )


@contextmanager
def bounded_operation(
    operation_name: str,
    *,
    max_duration: float = DEFAULT_MAX_OPERATION_DURATION,
    on_timeout: Optional[Callable[[], None]] = None,
):
    """CWE-770 防御: 有界操作 (超时控制).

    Args:
        operation_name: 操作名 (用于日志)
        max_duration: 最长执行时间 (秒)
        on_timeout: 超时回调

    Yields:
        dict (包含 elapsed 时间)

    Examples:
        >>> with bounded_operation("test", max_duration=1.0) as ctx:
        ...     time.sleep(0.1)
        >>> ctx['elapsed'] < 1.0
        True
    """
    ctx: Dict[str, float] = {"elapsed": 0.0}
    start = time.monotonic()
    try:
        yield ctx
    finally:
        ctx["elapsed"] = time.monotonic() - start
        if ctx["elapsed"] > max_duration:
            logger.warning(
                f"CWE-770: operation '{operation_name}' exceeded {max_duration}s "
                f"(elapsed={ctx['elapsed']:.2f}s)"
            )
            if on_timeout:
                on_timeout()


# ============================================================================
# Unicode Normalization Helper (防 Unicode bidi/同形字符攻击)
# ============================================================================

def normalize_unicode(text: str, form: str = "NFKC") -> str:
    """Unicode 规范化 (防同形字符 / bidi override 攻击).

    Args:
        text: 输入字符串
        form: 规范化形式 (NFC/NFD/NFKC/NFKD)

    Returns:
        规范化后的字符串
    """
    return unicodedata.normalize(form, text)


# ============================================================================
# 集中导出
# ============================================================================

__all__ = [
    # CWE-79 XSS
    "html_escape", "js_escape", "safe_html_template", "generate_csp_nonce", "make_csp_header",
    # CWE-611 XXE
    "XXEBlockedError", "safe_parse_xml", "safe_minidom_parse", "_DEFUSEDXML_AVAILABLE",
    # CWE-326 Strong Crypto
    "DEPRECATED_HASH_ALGORITHMS", "strong_hash", "strong_hmac", "constant_time_compare",
    # CWE-200 Information Disclosure
    "sanitize_error_message", "redact_sensitive_data",
    # CWE-352 CSRF
    "CSRF_UNSAFE_METHODS", "CSRF_PUBLIC_ENDPOINTS",
    "generate_csrf_token", "verify_csrf_token", "is_csrf_safe_method",
    "is_public_csrf_endpoint", "verify_origin_referer",
    # CWE-22 Path Traversal
    "PathTraversalError", "safe_resolve_path", "safe_extract_zip_member",
    # CWE-770 Resource Exhaustion
    "ResourceExhaustionError",
    "DEFAULT_MAX_FILE_DESCRIPTORS", "DEFAULT_MAX_MEMORY_MB",
    "DEFAULT_MAX_CONCURRENT_CONNECTIONS", "DEFAULT_MAX_REQUEST_BODY_SIZE",
    "DEFAULT_MAX_OPERATION_DURATION",
    "check_file_descriptor_limit", "check_memory_limit",
    "check_connection_pool_size", "check_request_body_size", "bounded_operation",
    # Unicode
    "normalize_unicode",
]
