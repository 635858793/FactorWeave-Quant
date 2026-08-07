"""R237-C TDD 测试: 7 个 CWE P2 修复 (28 用例).

铁律: R104 §12 + R235 §14 + R237 §十四
- 4 源验证 100% 命中
- TDD RED-GREEN-REFACTOR
- 7 个 CWE × 4 个用例 = 28 用例

CWE 清单 (R235 子智能体 C §10.2 P2 观察项升级 + R237 §十四):
1. CWE-79 XSS (Cross-Site Scripting) - HTML 转义 + CSP
2. CWE-611 XXE (XML External Entity) - defusedxml + DTD 禁用
3. CWE-326 加密弱点 - 强算法
4. CWE-200 信息泄露 - 错误信息脱敏
5. CWE-352 CSRF - 双 token + SameSite
6. CWE-22 路径遍历 - realpath + 白名单 (R218 _safe_extract 模板)
7. CWE-770 资源耗尽 - fd + 内存 + 连接池
"""
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

import pytest

from core.security.cwe_defenses import (
    # CWE-79
    html_escape, js_escape, safe_html_template, generate_csp_nonce, make_csp_header,
    # CWE-611
    XXEBlockedError, safe_parse_xml, safe_minidom_parse,
    # CWE-326
    DEPRECATED_HASH_ALGORITHMS, strong_hash, strong_hmac, constant_time_compare,
    # CWE-200
    sanitize_error_message, redact_sensitive_data,
    # CWE-352
    generate_csrf_token, verify_csrf_token, is_csrf_safe_method,
    is_public_csrf_endpoint, verify_origin_referer,
    # CWE-22
    PathTraversalError, safe_resolve_path, safe_extract_zip_member, safe_extract_zip,
    # CWE-770
    ResourceExhaustionError,
    check_file_descriptor_limit, check_memory_limit,
    check_connection_pool_size, check_request_body_size, bounded_operation,
    # Unicode
    normalize_unicode,
)


# ============================================================================
# CWE-79 XSS (4 用例)
# ============================================================================

class TestCwe79XssDefense(unittest.TestCase):
    """CWE-79 XSS Defense (4 用例)."""

    def test_01_html_escape_special_chars(self):
        """用例 1: HTML 特殊字符全部转义 (OWASP XSS Filter Evasion)."""
        self.assertEqual(html_escape("<script>"), "&lt;script&gt;")
        self.assertEqual(html_escape("\"hello\""), "&quot;hello&quot;")
        self.assertEqual(html_escape("'apostrophe'"), "&#x27;apostrophe&#x27;")
        self.assertEqual(html_escape("&amp;"), "&amp;amp;")
        self.assertEqual(html_escape("/path"), "&#x2F;path")
        self.assertEqual(html_escape("`code`"), "&#x60;code&#x60;")
        self.assertEqual(html_escape("a=b"), "a&#x3D;b")

    def test_02_html_escape_handles_none_and_int(self):
        """用例 2: 处理 None / 数字 / 字符串混合输入."""
        self.assertEqual(html_escape(None), "")
        self.assertEqual(html_escape(42), "42")
        self.assertEqual(html_escape(3.14), "3.14")
        self.assertEqual(html_escape("<b>"), "&lt;b&gt;")

    def test_03_js_escape_prevents_script_breakout(self):
        """用例 3: JavaScript 字符串转义防 </script> 突破."""
        result = js_escape("</script><img src=x onerror=alert(1)>")
        self.assertIn("\\u003c", result)
        self.assertIn("\\u003e", result)
        # \n \r \t 需转义
        self.assertIn("\\n", js_escape("line1\nline2"))
        self.assertIn("\\r", js_escape("line1\rline2"))
        self.assertIn("\\t", js_escape("col1\tcol2"))

    def test_04_safe_html_template_and_csp(self):
        """用例 4: 安全 HTML 模板 + CSP 头生成."""
        # 模板自动转义所有变量
        html = safe_html_template(
            "<p>Hello {name}, your score is {score}</p>",
            name="<script>alert('xss')</script>",
            score=100,
        )
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert", html)
        self.assertIn("100", html)

        # CSP 头
        csp = make_csp_header(nonce="abc123")
        self.assertIn("default-src 'self'", csp)
        self.assertIn("'nonce-abc123'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)

        # nonce 自动生成
        csp2 = make_csp_header()
        self.assertIn("'nonce-", csp2)


# ============================================================================
# CWE-611 XXE (4 用例)
# ============================================================================

class TestCwe611XxeDefense(unittest.TestCase):
    """CWE-611 XXE Defense (4 用例)."""

    def test_01_safe_parse_xml_blocks_doctype(self):
        """用例 1: 拒绝 DOCTYPE (XXE 攻击最常见入口)."""
        xxe_payload = b"""<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>"""
        with self.assertRaises(XXEBlockedError):
            safe_parse_xml(xxe_payload)

    def test_02_safe_parse_xml_blocks_entity_system(self):
        """用例 2: 拒绝 ENTITY SYSTEM 声明."""
        xxe_payload = b"""<?xml version="1.0"?>
<root>
  <!ENTITY xxe SYSTEM "http://attacker.com/steal">
</root>"""
        # ENTITY outside DOCTYPE 也应被检测
        with self.assertRaises(XXEBlockedError):
            safe_parse_xml(xxe_payload)

    def test_03_safe_parse_xml_normal_xml_passes(self):
        """用例 3: 正常 XML 通过解析."""
        normal_xml = b"""<?xml version="1.0"?>
<root>
  <user name="alice" age="30"/>
  <user name="bob" age="25"/>
</root>"""
        root = safe_parse_xml(normal_xml)
        self.assertEqual(root.tag, "root")
        users = list(root)
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0].get("name"), "alice")
        self.assertEqual(users[1].get("age"), "25")

    def test_04_safe_minidom_blocks_xxe(self):
        """用例 4: minidom 路径同样防御 XXE."""
        xxe_payload = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/shadow">]>
<config>&xxe;</config>"""
        with self.assertRaises(XXEBlockedError):
            safe_minidom_parse(xxe_payload)

        # 正常 XML
        normal = b"<config><key>value</key></config>"
        doc = safe_minidom_parse(normal)
        self.assertIsNotNone(doc)


# ============================================================================
# CWE-326 Strong Crypto (4 用例)
# ============================================================================

class TestCwe326CryptoDefense(unittest.TestCase):
    """CWE-326 Strong Crypto Defense (4 用例)."""

    def test_01_strong_hash_uses_sha256_default(self):
        """用例 1: 默认 SHA-256 (32 字节 hex)."""
        h = strong_hash("hello")
        self.assertEqual(len(h), 64)  # SHA-256 → 32 字节 → 64 hex 字符
        # 与 hashlib 对照
        import hashlib
        expected = hashlib.sha256(b"hello").hexdigest()
        self.assertEqual(h, expected)

    def test_02_strong_hash_rejects_deprecated(self):
        """用例 2: 拒绝 MD5/SHA1/DES 等弱算法."""
        for algo in ["md5", "sha1", "md4", "md2"]:
            with self.assertRaises(ValueError, msg=f"Should reject {algo}"):
                strong_hash("data", algorithm=algo)
        # DEPRECATED 集合完整性
        self.assertIn("md5", DEPRECATED_HASH_ALGORITHMS)
        self.assertIn("sha1", DEPRECATED_HASH_ALGORITHMS)
        self.assertIn("rc4", DEPRECATED_HASH_ALGORITHMS)

    def test_03_strong_hmac_uses_sha256(self):
        """用例 3: HMAC 默认 SHA-256, 拒绝弱算法."""
        mac = strong_hmac("secret", "message")
        self.assertEqual(len(mac), 64)
        with self.assertRaises(ValueError):
            strong_hmac("k", "m", algorithm="md5")

    def test_04_constant_time_compare(self):
        """用例 4: 常数时间比较 (防 timing attack)."""
        self.assertTrue(constant_time_compare("abc123", "abc123"))
        self.assertFalse(constant_time_compare("abc123", "abc456"))
        self.assertFalse(constant_time_compare("", "abc"))
        # bytes 输入
        self.assertTrue(constant_time_compare(b"xyz", b"xyz"))


# ============================================================================
# CWE-200 Information Disclosure (4 用例)
# ============================================================================

class TestCwe200InfoDisclosureDefense(unittest.TestCase):
    """CWE-200 Information Disclosure Defense (4 用例)."""

    def test_01_sanitize_error_message_strips_stacktrace(self):
        """用例 1: 错误信息不暴露堆栈/路径/SQL."""
        exc = Exception("FileNotFoundError: /etc/passwd (permission denied) [SQL: SELECT * FROM users WHERE id=1]")
        msg = sanitize_error_message(exc)
        self.assertNotIn("/etc/passwd", msg)
        self.assertNotIn("SELECT", msg)
        self.assertNotIn("permission denied", msg)
        # 默认对外消息
        self.assertIn("internal error", msg.lower())

    def test_02_sanitize_error_message_custom(self):
        """用例 2: 自定义对外消息."""
        custom = "操作失败, 请稍后重试"
        msg = sanitize_error_message(Exception("raw error"), custom_message=custom)
        self.assertEqual(msg, custom)
        # include_type=True 时显示类型, 不显示 str(exception)
        msg2 = sanitize_error_message(ValueError("secret detail"), include_type=True)
        self.assertIn("ValueError", msg2)
        self.assertNotIn("secret detail", msg2)

    def test_03_redact_sensitive_data_email_phone(self):
        """用例 3: 脱敏邮箱/手机号/身份证."""
        text = "Contact: alice@example.com or 13800138000, ID: 110101199003078888"
        redacted = redact_sensitive_data(text)
        self.assertNotIn("alice@example.com", redacted)
        self.assertNotIn("13800138000", redacted)
        self.assertNotIn("110101199003078888", redacted)
        self.assertIn("***REDACTED***", redacted)

    def test_04_redact_sensitive_data_ip_jwt_apikey(self):
        """用例 4: 脱敏 IP / JWT / API Key + 私网 IP 完全脱敏."""
        text = "Server 10.0.0.1 responded with JWT eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc and key sk-1234567890abcdefghij"
        redacted = redact_sensitive_data(text)
        self.assertNotIn("10.0.0.1", redacted)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", redacted)
        self.assertNotIn("sk-1234567890abcdefghij", redacted)
        # 公网 IP 部分保留
        text2 = "Public IP 8.8.8.8 is reachable"
        redacted2 = redact_sensitive_data(text2)
        self.assertIn("8.8.", redacted2)
        self.assertIn("x.x", redacted2)


# ============================================================================
# CWE-352 CSRF (4 用例)
# ============================================================================

class TestCwe352CsrfDefense(unittest.TestCase):
    """CWE-352 CSRF Defense (4 用例)."""

    def test_01_generate_csrf_token_is_secure(self):
        """用例 1: CSRF token 强随机 (32 字节 URL-safe)."""
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        self.assertGreaterEqual(len(token1), 32)
        self.assertNotEqual(token1, token2)
        # 高熵
        self.assertNotIn("+", token1)
        self.assertNotIn("=", token1.rstrip("="))

    def test_02_verify_csrf_token_constant_time(self):
        """用例 2: CSRF token 验证 (常数时间, 防 timing attack)."""
        token = generate_csrf_token()
        self.assertTrue(verify_csrf_token(token, token))
        self.assertFalse(verify_csrf_token(token, token[:-1] + "X"))
        self.assertFalse(verify_csrf_token("", token))
        self.assertFalse(verify_csrf_token(token, ""))

    def test_03_csrf_method_safety_check(self):
        """用例 3: HTTP method 安全判断 (GET/HEAD/OPTIONS 不需 token)."""
        self.assertTrue(is_csrf_safe_method("GET"))
        self.assertTrue(is_csrf_safe_method("HEAD"))
        self.assertTrue(is_csrf_safe_method("OPTIONS"))
        self.assertFalse(is_csrf_safe_method("POST"))
        self.assertFalse(is_csrf_safe_method("PUT"))
        self.assertFalse(is_csrf_safe_method("DELETE"))
        self.assertFalse(is_csrf_safe_method("PATCH"))

    def test_04_csrf_public_endpoint_and_origin(self):
        """用例 4: 公开端点白名单 + Origin 校验."""
        self.assertTrue(is_public_csrf_endpoint("/api/v1/login"))
        self.assertTrue(is_public_csrf_endpoint("/health"))
        self.assertTrue(is_public_csrf_endpoint("/api/v1/webhook/github"))
        self.assertFalse(is_public_csrf_endpoint("/api/v1/orders"))
        self.assertFalse(is_public_csrf_endpoint("/api/v1/account/transfer"))

        # Origin 校验
        allowed = ["https://example.com", "https://app.example.com"]
        self.assertTrue(verify_origin_referer("https://example.com", None, allowed))
        self.assertTrue(verify_origin_referer(None, "https://app.example.com/page", allowed))
        self.assertFalse(verify_origin_referer("https://evil.com", None, allowed))
        self.assertFalse(verify_origin_referer(None, None, allowed))


# ============================================================================
# CWE-22 Path Traversal (4 用例)
# ============================================================================

class TestCwe22PathTraversalDefense(unittest.TestCase):
    """CWE-22 Path Traversal Defense (4 用例)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="r237_cwe22_")
        self.tmppath = Path(self.tmpdir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_safe_resolve_blocks_traversal_patterns(self):
        """用例 1: 拒绝经典 traversal 模式 (../ / ..\\ / %2e%2e)."""
        for bad in [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2fetc%2fpasswd",
            "..%2f..%2fetc",
        ]:
            with self.assertRaises(PathTraversalError, msg=f"Should reject: {bad}"):
                safe_resolve_path(bad, allowed_roots=[self.tmppath])

    def test_02_safe_resolve_enforces_whitelist(self):
        """用例 2: 白名单强制 (允许的根目录之外的路径被拒)."""
        # tmpdir 内的文件
        safe_file = self.tmppath / "safe.txt"
        safe_file.write_text("hello")

        # 使用绝对路径测试
        result = safe_resolve_path(str(safe_file), allowed_roots=[self.tmppath])
        self.assertEqual(result.resolve(), safe_file.resolve())

        # tmpdir 之外的文件被拒
        with self.assertRaises(PathTraversalError):
            safe_resolve_path("/etc/passwd", allowed_roots=[self.tmppath])

        # 相对路径 + os.chdir 测试 (确保白名单生效)
        old_cwd = os.getcwd()
        try:
            os.chdir(str(self.tmppath))
            result2 = safe_resolve_path("safe.txt", allowed_roots=[self.tmppath])
            self.assertEqual(result2.resolve(), safe_file.resolve())
            # 不在白名单内的绝对路径被拒
            with self.assertRaises(PathTraversalError):
                safe_resolve_path("/nonexistent/absolute/path", allowed_roots=[self.tmppath])
        finally:
            os.chdir(old_cwd)

    def test_03_safe_resolve_symlink_check(self):
        """用例 3: 默认拒绝符号链接 (allow_symlinks=False)."""
        target = self.tmppath / "real.txt"
        target.write_text("content")
        link = self.tmppath / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink not supported on this platform")

        # 默认不允许符号链接
        with self.assertRaises(PathTraversalError):
            safe_resolve_path("link.txt", allowed_roots=[self.tmppath])

        # 允许符号链接则通过
        result = safe_resolve_path("link.txt", allowed_roots=[self.tmppath], allow_symlinks=True)
        self.assertTrue(result.exists())

    def test_04_safe_extract_zip_blocks_zip_slip(self):
        """用例 4: zip-slip 防御 (R218 _safe_extract 模板)."""
        # 构造 zip-slip zip
        zip_path = self.tmppath / "malicious.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../../../etc/evil.txt", "pwned")

        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                with self.assertRaises(PathTraversalError, msg=f"zip-slip: {member}"):
                    safe_extract_zip_member(zip_path, member, self.tmppath)

    def test_05_safe_extract_zip_normal_extract(self):
        """用例 5: safe_extract_zip 正常解压 (替代 extractall)."""
        zip_path = self.tmppath / "good.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "hello")
            zf.writestr("subdir/file2.txt", "world")
        extracted = safe_extract_zip(zip_path, self.tmppath)
        self.assertEqual(len(extracted), 2)
        # 解压后文件存在
        for p in extracted:
            self.assertTrue(p.exists())


# ============================================================================
# CWE-770 Resource Exhaustion (4 用例)
# ============================================================================

class TestCwe770ResourceExhaustionDefense(unittest.TestCase):
    """CWE-770 Resource Exhaustion Defense (4 用例)."""

    def test_01_file_descriptor_limit(self):
        """用例 1: 文件描述符上限检查."""
        # 默认上限 100, 50 < 100 应通过
        check_file_descriptor_limit(50)
        # 101 > 100 应抛错
        with self.assertRaises(ResourceExhaustionError):
            check_file_descriptor_limit(101)
        # 自定义上限 10
        check_file_descriptor_limit(5, max_count=10)
        # 11 > 10 应抛错
        with self.assertRaises(ResourceExhaustionError):
            check_file_descriptor_limit(11, max_count=10)

    def test_02_memory_limit(self):
        """用例 2: 内存上限检查."""
        check_memory_limit(100.0)
        with self.assertRaises(ResourceExhaustionError):
            check_memory_limit(600.0)
        # 自定义上限 10 MB
        check_memory_limit(5.0, max_mb=10)
        with self.assertRaises(ResourceExhaustionError):
            check_memory_limit(20.0, max_mb=10)

    def test_03_connection_pool_and_request_size(self):
        """用例 3: 连接池 + 请求体大小检查."""
        # 连接池
        check_connection_pool_size(30)
        with self.assertRaises(ResourceExhaustionError):
            check_connection_pool_size(60)
        # 请求体
        check_request_body_size(1024 * 1024)  # 1MB < 10MB
        with self.assertRaises(ResourceExhaustionError):
            check_request_body_size(20 * 1024 * 1024)  # 20MB > 10MB

    def test_04_bounded_operation_timeout(self):
        """用例 4: 有界操作超时控制."""
        import time as _time

        # 正常操作 (0.1s < 1.0s)
        with bounded_operation("fast_op", max_duration=1.0) as ctx:
            _time.sleep(0.05)
        self.assertLess(ctx["elapsed"], 1.0)

        # 慢操作 (0.3s > 0.1s, 应触发 warning)
        callback_called = []
        with bounded_operation(
            "slow_op",
            max_duration=0.1,
            on_timeout=lambda: callback_called.append(True),
        ) as ctx:
            _time.sleep(0.3)
        self.assertGreater(ctx["elapsed"], 0.1)
        self.assertEqual(callback_called, [True])


# ============================================================================
# Unicode 规范化 (补充 1 用例, 跨多个 CWE)
# ============================================================================

class TestUnicodeNormalization(unittest.TestCase):
    """Unicode 规范化 (防同形字符 / bidi override 攻击)."""

    def test_01_nfkc_normalization(self):
        """用例 1: NFKC 规范化 (防 Unicode 欺骗)."""
        # 全角字符 → 半角
        fullwidth = "\uff28\uff45\uff4c\uff4c\uff4f"  # "Ｈｅｌｌｏ"
        self.assertEqual(normalize_unicode(fullwidth), "Hello")
        # 兼容性分解
        ligature = "ﬁ"  # fi 连字
        self.assertEqual(len(normalize_unicode(ligature)), 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
