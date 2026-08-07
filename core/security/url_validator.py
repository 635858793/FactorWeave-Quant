"""
URL 安全校验器 (R240-P0, 2026-08-02)

CWE-918 SSRF 5 重防御 (R236-C 假修复重建):
1. scheme 白名单: 仅 http/https
2. 禁止 URL 内嵌凭据 (userinfo)
3. host 为 IP 字面量 → 内网/回环/链路本地/保留/组播/全零/CGNAT 黑名单
4. host 为域名 → DNS 解析后解析 IP 二次校验 (fail-closed, 防 DNS 重绑定)
5. 敏感端口拒绝 (数据库/消息队列/管理端口)

接入点 (审计确认的 6+ 出站 sink):
- plugins/plugin_market.py:323 download_url (远端可控 → 真实 SSRF 路径)
- core/services/external_alert_channels_service.py:299/390 webhook_url
- core/services/distributed_service.py:397/473 节点健康检查
- core/services/distributed_http_bridge.py:447 节点健康检查
- core/services/tdx_server_discovery.py:131 行情服务器探测

设计: 返回 (ok, reason) 二元组, 业务层用 assert_safe_url 抛 SSRFBlockedError.
DNS 解析失败默认 fail-closed (返回不安全) — SSRF 防御宁可误杀不可漏网.
"""
import ipaddress
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

from loguru import logger

# scheme 白名单
_ALLOWED_SCHEMES = ("http", "https")

# 敏感端口 (数据库/消息队列/管理/内部服务)
_BLOCKED_PORTS = frozenset({
    21, 22, 23, 25, 110, 135, 139, 143, 445, 873,
    1433, 1521, 3306, 3389, 5432, 5900, 6379,
    11211, 27017, 5000, 7000, 8000, 8080, 9000,
})

# 私有/保留网段黑名单 (IPv4)
_PRIVATE_NETWORKS_IPV4 = tuple(
    ipaddress.ip_network(net) for net in (
        "0.0.0.0/8",          # 全零
        "10.0.0.0/8",         # 私有 A
        "100.64.0.0/10",      # CGNAT
        "127.0.0.0/8",        # 回环
        "169.254.0.0/16",     # 链路本地 (云元数据)
        "172.16.0.0/12",      # 私有 B
        "192.0.0.0/24",       # IETF 协议分配
        "192.168.0.0/16",     # 私有 C
        "198.18.0.0/15",      # 基准测试
        "224.0.0.0/4",        # 组播
        "240.0.0.0/4",        # 保留
        "255.255.255.255/32", # 广播
    )
)

# 本地保留主机名 (DNS 不可依赖时也要拦截)
_LOCAL_HOSTNAMES = frozenset({
    "localhost", "localhost.localdomain", "localhost6",
    "ip6-localhost", "ip6-loopback", "broadcasthost",
})


class SSRFBlockedError(Exception):
    """URL 被 SSRF 防御拦截"""


def _is_blocked_ip(ip: ipaddress._BaseAddress, mode: str = "strict") -> bool:
    """IP 是否命中黑名单 (内网/回环/链路本地/保留/组播)

    mode:
      - strict: 全部拦截 (含 RFC1918 私有段) — 不可信外部输入默认
      - lan_ok: 允许 RFC1918 私有段 (分布式集群节点常部署于内网),
                仍拦截回环/链路本地/组播/保留/未指定
    """
    if ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_reserved or ip.is_unspecified:
        return True
    if mode == "lan_ok":
        return False
    if ip.is_private:
        return True
    if isinstance(ip, ipaddress.IPv4Address):
        return any(ip in net for net in _PRIVATE_NETWORKS_IPV4)
    return False


def validate_url(url: str, *, dns_resolve: bool = True, mode: str = "strict") -> Tuple[bool, str]:
    """
    校验 URL 是否安全 (SSRF 5 重防御)

    Args:
        url: 待校验 URL
        dns_resolve: 域名是否执行 DNS 解析校验 (默认 True, fail-closed)
        mode: "strict" (默认, 全黑名单) 或 "lan_ok" (允许内网, 用于分布式集群)

    Returns:
        (True, "") 或 (False, reason)
    """
    if not url or not isinstance(url, str):
        return False, "URL 为空或类型非法"

    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        return False, f"URL 解析失败: {e}"

    # 1. scheme 白名单
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False, f"scheme 非法: {parsed.scheme!r} (仅允许 http/https)"

    # 2. 禁止内嵌凭据
    if parsed.username or parsed.password:
        return False, "URL 禁止内嵌凭据 (userinfo)"

    host = parsed.hostname
    if not host:
        return False, "URL 缺少 host"

    # 本地保留主机名黑名单 (不依赖 DNS)
    if host.lower() in _LOCAL_HOSTNAMES or host.lower().endswith(".local"):
        return False, f"主机名 {host} 为本地保留主机名"

    # 5. 敏感端口拒绝 (仅在显式端口时)
    if parsed.port is not None and parsed.port in _BLOCKED_PORTS:
        return False, f"端口 {parsed.port} 为敏感端口, 已拒绝"

    # 3/4. host 解析校验
    try:
        ip = ipaddress.ip_address(host)
        # IP 字面量 → 直接黑名单
        if _is_blocked_ip(ip, mode=mode):
            return False, f"目标 IP {host} 为内网/保留地址"
        return True, ""
    except ValueError:
        # 域名 → 语法检查 + (可选) DNS 二次校验
        if not dns_resolve:
            return True, ""
        return _check_dns(host, mode=mode)


def _check_dns(host: str, mode: str = "strict") -> Tuple[bool, str]:
    """域名 DNS 解析后二次校验 (fail-closed)"""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # 解析失败 → fail-closed (SSRF 防御宁可误杀)
        return False, f"域名 {host} DNS 解析失败 (fail-closed)"

    if not infos:
        return False, f"域名 {host} 无解析结果 (fail-closed)"

    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_ip(ip, mode=mode):
            return False, f"域名 {host} 解析到内网/保留地址 {addr} (可能 DNS 重绑定)"

    return True, ""


def assert_safe_url(url: str, *, dns_resolve: bool = True, mode: str = "strict") -> str:
    """
    校验 URL, 不安全抛 SSRFBlockedError, 安全返回原 URL (供 sink 接入)
    """
    ok, reason = validate_url(url, dns_resolve=dns_resolve, mode=mode)
    if not ok:
        logger.warning(f"[SSRF] 拦截不安全 URL: {reason} — {url}")
        raise SSRFBlockedError(reason)
    return url


__all__ = ["SSRFBlockedError", "validate_url", "assert_safe_url"]
