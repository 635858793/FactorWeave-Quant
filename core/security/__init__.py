"""core.security 子包 - R237 实施.

包含:
- secrets_manager: 密钥管理抽象层 (R237-A + R235 §14.1 铁律 #1)
- cwe_defenses: 7 个 CWE P2 防御工具 (R237-C)
- url_validator: CWE-918 SSRF 5 重防御 (R240-P0 重建)

铁律: R104 §12 + R235 §14 + R237 §十四
"""
from .secrets_manager import (
    SecretsManager,
    SecretNotFoundError,
    VaultProvider,
    SecretAuditRecord,
    get_secrets_manager,
    reset_secrets_manager,
)
from .url_validator import (
    SSRFBlockedError,
    validate_url,
    assert_safe_url,
)
from .cwe_defenses import (
    # CWE-79 XSS
    html_escape, js_escape, safe_html_template, generate_csp_nonce, make_csp_header,
    # CWE-611 XXE
    XXEBlockedError, safe_parse_xml, safe_minidom_parse,
    # CWE-326 Strong Crypto
    DEPRECATED_HASH_ALGORITHMS, strong_hash, strong_hmac, constant_time_compare,
    # CWE-200 Information Disclosure
    sanitize_error_message, redact_sensitive_data,
    # CWE-352 CSRF
    generate_csrf_token, verify_csrf_token, is_csrf_safe_method,
    is_public_csrf_endpoint, verify_origin_referer,
    # CWE-22 Path Traversal
    PathTraversalError, safe_resolve_path, safe_extract_zip_member, safe_extract_zip,
    # CWE-770 Resource Exhaustion
    ResourceExhaustionError,
    check_file_descriptor_limit, check_memory_limit,
    check_connection_pool_size, check_request_body_size, bounded_operation,
    # Unicode
    normalize_unicode,
)

__all__ = [
    # R237-A secrets_manager
    "SecretsManager", "SecretNotFoundError", "VaultProvider", "SecretAuditRecord",
    "get_secrets_manager", "reset_secrets_manager",
    # R240-P0 url_validator
    "SSRFBlockedError", "validate_url", "assert_safe_url",
    # R237-C cwe_defenses
    "html_escape", "js_escape", "safe_html_template", "generate_csp_nonce", "make_csp_header",
    "XXEBlockedError", "safe_parse_xml", "safe_minidom_parse",
    "DEPRECATED_HASH_ALGORITHMS", "strong_hash", "strong_hmac", "constant_time_compare",
    "sanitize_error_message", "redact_sensitive_data",
    "generate_csrf_token", "verify_csrf_token", "is_csrf_safe_method",
    "is_public_csrf_endpoint", "verify_origin_referer",
    "PathTraversalError", "safe_resolve_path", "safe_extract_zip_member", "safe_extract_zip",
    "ResourceExhaustionError",
    "check_file_descriptor_limit", "check_memory_limit",
    "check_connection_pool_size", "check_request_body_size", "bounded_operation",
    "normalize_unicode",
]
