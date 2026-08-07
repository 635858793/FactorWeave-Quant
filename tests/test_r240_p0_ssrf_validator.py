"""R240-P0: CWE-918 SSRF 5 重防御重建 — url_validator + sink 接入测试

验证 (全部来自 R240-A 子智能体审计 + 主智能体交叉验证):
- url_validator.py 源码已删除 (R236-C 假修复), 仅 pyc 残留 → 需重建
- 6+ 出站 sink 0 校验: plugins/plugin_market.py:323 (download_url SSRF)
  + core/services/external_alert_channels_service.py:299/390 (webhook_url)
  + core/services/distributed_service.py:397/473 + distributed_http_bridge.py:447
  + core/services/tdx_server_discovery.py:131
- TDD: RED → GREEN (新建 core/security/url_validator.py 后通过)
"""
import pytest


@pytest.fixture
def uvs():
    """返回 url_validator 模块 (待实现)"""
    from core.security import url_validator
    return url_validator


# ---------------------------------------------------------------- 1. 功能层
class TestValidateUrlBlocked:
    """应被拒绝的 URL (内网/保留/凭据/非 http)"""

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",                    # 非 http(s) scheme
        "ftp://192.168.1.1/file",                # 非 http(s) scheme
        "http://127.0.0.1:8080/admin",           # 回环 IPv4
        "http://localhost:3000/",                # 回环主机名
        "http://[::1]:8080/",                    # 回环 IPv6
        "http://10.0.0.1/",                      # 私有 A 段
        "http://172.16.0.1/",                    # 私有 B 段
        "http://192.168.1.1/",                   # 私有 C 段
        "http://169.254.169.254/latest/",        # 云元数据 (链路本地)
        "http://0.0.0.0/",                       # 全零
        "http://100.64.0.1/",                    # CGNAT
        "http://224.0.0.1/",                     # 组播
        "http://user:pass@example.com/",         # 内嵌凭据
        "http://example.com:6379/",              # 敏感端口 (Redis)
        "http://example.com:3306/",              # 敏感端口 (MySQL)
        "http://192.168.1.1:443/",               # 内网 IP + https
    ])
    def test_blocked(self, uvs, url):
        ok, reason = uvs.validate_url(url, dns_resolve=False)
        assert ok is False, f"{url} 应被拦截: {reason}"

    def test_blocked_with_dns_resolve(self, uvs, monkeypatch):
        """DNS 解析命中内网也应拦截 (防御 DNS 重绑定)"""
        import socket
        fake_ips = ["127.0.0.1"]  # 域名解析到回环

        def fake_getaddrinfo(host, port, *a, **kw):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in fake_ips]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        ok, reason = uvs.validate_url("http://evil.example.com/", dns_resolve=True)
        assert ok is False, f"DNS 解析到内网应拦截: {reason}"


class TestValidateUrlAccepted:
    """应通过的 URL"""

    def test_public_https(self, uvs):
        ok, reason = uvs.validate_url("https://example.com/plugins/download", dns_resolve=False)
        assert ok is True, f"公网 https 应通过: {reason}"

    def test_public_http_default_port(self, uvs):
        ok, reason = uvs.validate_url("http://example.com/", dns_resolve=False)
        assert ok is True

    def test_public_with_common_port(self, uvs):
        ok, reason = uvs.validate_url("https://cdn.example.com:443/pack.zip", dns_resolve=False)
        assert ok is True


# ---------------------------------------------------------------- 2. 接入层
class TestSinkIntegration:
    """出站 sink 已接入 url 校验"""

    def test_plugin_market_download_url_validated(self, uvs, monkeypatch):
        """plugins/plugin_market.py:323 requests.get(download_url) 必须校验"""
        from plugins import plugin_market as pm
        assert hasattr(pm, "_assert_download_url_safe"), "plugin_market 缺少下载 URL 校验函数"
        # 内网 download_url 必须抛 SSRFBlockedError (插件市场远端可控 → 真实 SSRF 路径)
        with pytest.raises(uvs.SSRFBlockedError):
            pm._assert_download_url_safe("http://192.168.1.66/malicious.zip")
        with pytest.raises(uvs.SSRFBlockedError):
            pm._assert_download_url_safe("http://169.254.169.254/latest/meta-data/")
        with pytest.raises(uvs.SSRFBlockedError):
            pm._assert_download_url_safe("http://localhost/pack.zip")
        # 公网 URL: 模拟 DNS 解析到公网 IP (测试环境无外网 DNS)
        import socket

        def fake_getaddrinfo(host, port, *a, **kw):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        assert pm._assert_download_url_safe("https://cdn.example.com/pack.zip") is True

    def test_external_alert_channels_webhook_validated(self, uvs):
        """core/services/external_alert_channels_service.py:299/390 webhook_url 必须校验"""
        from core.services import external_alert_channels_service as mod
        assert hasattr(mod, "_assert_webhook_url_safe"), "external_alert_channels 缺少 webhook URL 校验函数"
        with pytest.raises(uvs.SSRFBlockedError):
            mod._assert_webhook_url_safe("http://10.0.0.5/hook")
        with pytest.raises(uvs.SSRFBlockedError):
            mod._assert_webhook_url_safe("http://192.168.1.1:8080/alert")
        assert mod._assert_webhook_url_safe("https://hooks.example.com/abc123") is True

    def test_distributed_service_health_checked(self, uvs):
        """core/services/distributed_service.py:397/473 节点健康检查 URL 必须校验"""
        from core.services import distributed_service as mod
        assert hasattr(mod, "_assert_node_url_safe"), "distributed_service 缺少节点 URL 校验函数"
        with pytest.raises(uvs.SSRFBlockedError):
            mod._assert_node_url_safe("http://127.0.0.1:7000/api/v1/health")

    def test_distributed_http_bridge_health_checked(self, uvs):
        """core/services/distributed_http_bridge.py:447 节点健康检查 URL 必须校验"""
        from core.services import distributed_http_bridge as mod
        assert hasattr(mod, "_assert_node_url_safe"), "distributed_http_bridge 缺少节点 URL 校验函数"
        with pytest.raises(uvs.SSRFBlockedError):
            mod._assert_node_url_safe("http://127.0.0.1:7000/api/v1/health")


# ---------------------------------------------------------------- 3. 常量
class TestConstants:
    def test_export(self, uvs):
        assert hasattr(uvs, "SSRFBlockedError")
        assert hasattr(uvs, "validate_url")
