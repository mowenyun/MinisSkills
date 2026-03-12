"""
ytmusic_client.py
ytmusic-hub 的统一初始化模块。

用法：
    import sys
    sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")
    from ytmusic_client import get_client
    yt = get_client()
"""

import ssl
import socket
import json
import urllib.request
import urllib3

AUTH_FILE = "/var/minis/workspace/ytmusic_headers.json"
TARGET_HOST = "music.youtube.com"
DOH_URL = "https://dns.google/resolve?name={}&type=A"

# ── SSL patch：在模块加载时立即执行，只执行一次 ─────────────────────────────

def _patch_ssl_once():
    """
    patch urllib3 两处，彻底禁用证书验证：
    1. create_urllib3_context：禁用新建 context 的验证
    2. _ssl_wrap_socket_and_match_hostname：跳过 hostname 匹配
    """
    from urllib3.util import ssl_ as u3ssl
    import urllib3.connection as u3conn

    if getattr(u3ssl, "_ytmusic_patched", False):
        return  # 防止重复 patch

    # patch 1: 新建 context 时禁用验证
    _orig_ctx = u3ssl.create_urllib3_context
    def _patched_ctx(*a, **kw):
        ctx = _orig_ctx(*a, **kw)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    u3ssl.create_urllib3_context = _patched_ctx

    # patch 2: 跳过 hostname 匹配（覆盖调用方传入的 cert_reqs）
    _orig_wrap = u3conn._ssl_wrap_socket_and_match_hostname
    def _patched_wrap(*a, **kw):
        kw["cert_reqs"] = ssl.CERT_NONE
        kw["assert_hostname"] = False
        kw["assert_fingerprint"] = None
        return _orig_wrap(*a, **kw)
    u3conn._ssl_wrap_socket_and_match_hostname = _patched_wrap

    urllib3.disable_warnings()
    u3ssl._ytmusic_patched = True

_patch_ssl_once()

# ── 工具函数 ────────────────────────────────────────────────────────────────

def _ssl_reachable(host, ip=None):
    """测试 SSL 连通性，不验证证书，可指定直连 IP。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        s = socket.create_connection((ip or host, 443), timeout=8)
        ssl_sock = ctx.wrap_socket(s, server_hostname=host)
        ssl_sock.close()
        return True
    except Exception:
        return False


def _doh_resolve(hostname):
    """通过 Google DoH 查询真实 IP，绕过本地 DNS 污染。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        DOH_URL.format(hostname),
        headers={"accept": "application/dns-json"}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
        data = json.loads(resp.read())
    ips = [r["data"] for r in data.get("Answer", []) if r["type"] == 1]
    return ips[0] if ips else None


# 记录已 patch 的 hostname，避免重复叠加
_dns_patched = set()

def _patch_dns(hostname, ip):
    """patch socket.getaddrinfo，强制将 hostname 解析到指定 IP（幂等）。"""
    if hostname in _dns_patched:
        return
    _orig = socket.getaddrinfo
    def _patched(host, port, *a, **kw):
        if host == hostname:
            host = ip
        return _orig(host, port, *a, **kw)
    socket.getaddrinfo = _patched
    _dns_patched.add(hostname)
    print(f"  DNS patch: {hostname} -> {ip}")


# ── 主入口 ──────────────────────────────────────────────────────────────────

def get_client(auth_file=AUTH_FILE):
    """
    返回可用的 YTMusic 实例，自动处理 DNS 污染和 SSL 问题。
    若网络不可用则抛出 RuntimeError。
    """
    print(f"🔌 正在连接 {TARGET_HOST}...")

    if _ssl_reachable(TARGET_HOST):
        print(f"  ✅ 本地 DNS 正常，直接连接")
    else:
        print(f"  ⚠️  本地 DNS 被污染，通过 DoH 查询真实 IP...")
        try:
            real_ip = _doh_resolve(TARGET_HOST)
            if not real_ip:
                raise RuntimeError("DoH 未返回有效 IP")
            print(f"  DoH 解析: {TARGET_HOST} -> {real_ip}")
            if not _ssl_reachable(TARGET_HOST, ip=real_ip):
                raise RuntimeError(f"IP {real_ip} 也无法连接，请检查代理是否开启")
            _patch_dns(TARGET_HOST, real_ip)
            _patch_dns("youtubei.googleapis.com", _doh_resolve("youtubei.googleapis.com") or real_ip)
        except Exception as e:
            raise RuntimeError(f"❌ 网络不可用: {e}\n请确认代理/VPN 已开启") from e

    from ytmusicapi import YTMusic
    yt = YTMusic(auth_file)
    print(f"  ✅ YTMusic 已就绪\n")
    return yt
