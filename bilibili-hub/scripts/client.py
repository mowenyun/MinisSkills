"""
Bilibili API Client — 基于 bilibili-api-python 的异步封装。

改造来源：jackwener/bilibili-cli
https://github.com/jackwener/bilibili-cli/blob/main/bili_cli/client.py

主要改动：
- 移除 browser-cookie3 / click / rich / PyYAML / qrcode 依赖
- 认证改为直接传入 Cookie dict，不做浏览器自动提取
- 移除 QR 登录、formatter 等 CLI 层代码
- 保留全部 API 方法，统一用 asyncio.run() 提供同步接口
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

import aiohttp
from bilibili_api import comment, dynamic, favorite_list, homepage, hot, rank, search, user, video
from bilibili_api.exceptions import (
    ApiException,
    CredentialNoBiliJctException,
    CredentialNoSessdataException,
    NetworkException,
    ResponseCodeException,
    ResponseException,
)
from bilibili_api.utils.network import Credential

from .exceptions import (
    AuthenticationError,
    BiliError,
    InvalidBvidError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

_BVID_RE = re.compile(r"\bBV[0-9A-Za-z]{10}\b")


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def extract_bvid(url_or_bvid: str) -> str:
    """从 URL 或字符串中提取 BV 号。"""
    match = _BVID_RE.search(url_or_bvid)
    if match:
        return match.group(0)
    raise InvalidBvidError(f"无法提取 BV 号: {url_or_bvid}")


def make_credential(cookies: dict[str, str]) -> Credential:
    """从 Cookie dict 构建 bilibili-api Credential 对象。"""
    return Credential(
        sessdata=cookies.get("SESSDATA", ""),
        bili_jct=cookies.get("bili_jct", ""),
        ac_time_value=cookies.get("ac_time_value", ""),
        buvid3=cookies.get("buvid3", ""),
        buvid4=cookies.get("buvid4", ""),
        dedeuserid=cookies.get("DedeUserID", ""),
    )


def _map_error(action: str, exc: Exception) -> BiliError:
    if isinstance(exc, BiliError):
        return exc
    if isinstance(exc, (CredentialNoSessdataException, CredentialNoBiliJctException)):
        return AuthenticationError(f"{action}: {exc}")
    if isinstance(exc, ResponseCodeException):
        code = getattr(exc, "code", None)
        if code in {-101, -111}:   return AuthenticationError(f"{action}: {exc}")
        if code in {-404, 62002}:  return NotFoundError(f"{action}: {exc}")
        if code in {-412, 412}:    return RateLimitError(f"{action}: {exc}")
        return BiliError(f"{action}: [{code}] {exc}")
    if isinstance(exc, (NetworkException, ResponseException, aiohttp.ClientError, asyncio.TimeoutError)):
        return NetworkError(f"{action}: {exc}")
    if isinstance(exc, ApiException):
        return BiliError(f"{action}: {exc}")
    return BiliError(f"{action}: {exc}")


async def _call(action: str, awaitable):
    try:
        return await awaitable
    except Exception as exc:
        raise _map_error(action, exc) from exc


def _run(coro):
    """在同步环境中运行异步协程。"""
    return asyncio.run(coro)


# ─── 视频 ─────────────────────────────────────────────────────────────────────

async def _get_video_info(bvid: str, cred: Credential | None = None) -> dict:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("获取视频信息", v.get_info())

async def _get_video_subtitle(bvid: str, cred: Credential | None = None) -> tuple[str, list]:
    v = video.Video(bvid=bvid, credential=cred)
    pages = await _call("获取视频分P", v.get_pages())
    if not pages:
        return "", []
    cid = pages[0].get("cid")
    if not cid:
        return "", []
    player_info = await _call("获取播放器信息", v.get_player_info(cid=cid))
    subtitle_info = player_info.get("subtitle", {})
    if not subtitle_info or not subtitle_info.get("subtitles"):
        return "", []
    subtitle_list = subtitle_info["subtitles"]
    subtitle_url = None
    for sub in subtitle_list:
        if "zh" in sub.get("lan", "").lower():
            subtitle_url = sub.get("subtitle_url", "")
            break
    if not subtitle_url and subtitle_list:
        subtitle_url = subtitle_list[0].get("subtitle_url", "")
    if not subtitle_url:
        return "", []
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(subtitle_url) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
    except Exception as e:
        raise NetworkError(f"下载字幕失败: {e}") from e
    if "body" in data:
        raw = data["body"]
        return "\n".join(item.get("content", "") for item in raw), raw
    return "", []

async def _get_video_comments(bvid: str, cred: Credential | None = None) -> list:
    v = video.Video(bvid=bvid, credential=cred)
    info = await _call("获取视频信息", v.get_info())
    aid = info.get("aid")
    if not aid:
        return []
    c = comment.Comment(oid=aid, type=comment.CommentResourceType.VIDEO, credential=cred)
    result = await _call("获取评论", c.get_comments())
    return result.get("replies") or []

async def _get_related_videos(bvid: str, cred: Credential | None = None) -> list:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("获取相关视频", v.get_related())

async def _get_ai_summary(bvid: str, cred: Credential | None = None) -> str:
    v = video.Video(bvid=bvid, credential=cred)
    try:
        pages = await _call("获取视频分P", v.get_pages())
        if not pages:
            return ""
        cid = pages[0].get("cid")
        result = await _call("获取 AI 总结", v.get_ai_conclusion(cid=cid, credential=cred))
        return result.get("model_result", {}).get("summary", "") or ""
    except Exception:
        return ""

# ─── 用户 ─────────────────────────────────────────────────────────────────────

async def _get_user_info(uid: int, cred: Credential | None = None) -> dict:
    u = user.User(uid=uid, credential=cred)
    return await _call("获取用户信息", u.get_user_info())

async def _get_user_relation(uid: int, cred: Credential | None = None) -> dict:
    u = user.User(uid=uid, credential=cred)
    return await _call("获取用户关系", u.get_relation_info())

async def _get_self_info(cred: Credential) -> dict:
    return await _call("获取自身信息", user.get_self_info(cred))

async def _get_user_videos(uid: int, count: int = 10, cred: Credential | None = None) -> list:
    u = user.User(uid=uid, credential=cred)
    results = []
    page = 1
    while len(results) < count:
        batch = await _call("获取用户视频", u.get_videos(pn=page))
        items = batch.get("list", {}).get("vlist", [])
        if not items:
            break
        results.extend(items)
        page += 1
        if len(items) < 30:
            break
    return results[:count]

# ─── 搜索 ─────────────────────────────────────────────────────────────────────

async def _search_users(keyword: str, page: int = 1) -> list:
    result = await _call("搜索用户", search.search_by_type(
        keyword, search_type=search.SearchObjectType.USER, page=page,
    ))
    return result.get("result", []) or []

async def _search_videos(keyword: str, page: int = 1, count: int = 20) -> list:
    result = await _call("搜索视频", search.search_by_type(
        keyword, search_type=search.SearchObjectType.VIDEO, page=page,
    ))
    return (result.get("result", []) or [])[:count]

# ─── 发现 ─────────────────────────────────────────────────────────────────────

async def _get_hot(page: int = 1, count: int = 20) -> list:
    result = await _call("获取热门", hot.get_hot_videos(pn=page, ps=count))
    return result.get("list", []) or []

async def _get_rank(day: int = 3, count: int = 100) -> list:
    result = await _call("获取排行榜", rank.get_hot_videos(day=day))
    return (result.get("list", []) or [])[:count]

async def _get_feed(offset: int = 0, cred: Credential | None = None) -> dict:
    result = await _call("获取动态 Feed", dynamic.get_dynamic_page_UPs_info(credential=cred, offset=offset))
    return result

async def _get_my_dynamics(uid: int, offset: int = 0, cred: Credential | None = None) -> dict:
    u = user.User(uid=uid, credential=cred)
    return await _call("获取我的动态", u.get_dynamics(offset=offset))

async def _post_dynamic(text: str, cred: Credential) -> dict:
    if not text.strip():
        raise BiliError("发布动态: 文本不能为空")
    info = dynamic.BuildDynamic.empty().add_text(text.strip())
    return await _call("发布动态", dynamic.send_dynamic(info=info, credential=cred))

async def _delete_dynamic(dynamic_id: int, cred: Credential) -> dict:
    d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=cred)
    return await _call("删除动态", d.delete())

# ─── 收藏 ─────────────────────────────────────────────────────────────────────

async def _get_favorite_folders(uid: int, cred: Credential | None = None) -> list:
    result = await _call("获取收藏夹", favorite_list.get_video_favorite_list(uid=uid, credential=cred))
    return result.get("list", []) or []

async def _get_favorite_videos(folder_id: int, page: int = 1, count: int = 20, cred: Credential | None = None) -> list:
    result = await _call("获取收藏视频", favorite_list.get_video_favorite_list_content(
        media_id=folder_id, page=page, credential=cred,
    ))
    return (result.get("medias", []) or [])[:count]

async def _get_following(uid: int, page: int = 1, cred: Credential | None = None) -> list:
    u = user.User(uid=uid, credential=cred)
    result = await _call("获取关注列表", u.get_followings(pn=page))
    return result.get("list", []) or []

async def _get_watch_later(cred: Credential) -> list:
    result = await _call("获取稍后再看", favorite_list.get_video_toview_list(credential=cred))
    return result.get("list", []) or []

async def _get_history(cred: Credential) -> list:
    u = user.User(uid=0, credential=cred)
    result = await _call("获取历史记录", u.get_history())
    return result.get("list", []) or []

# ─── 互动 ─────────────────────────────────────────────────────────────────────

async def _like_video(bvid: str, cred: Credential, undo: bool = False) -> dict:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("点赞", v.like(status=not undo))

async def _coin_video(bvid: str, cred: Credential, num: int = 1) -> dict:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("投币", v.pay_coin(num=num))

async def _triple_video(bvid: str, cred: Credential) -> dict:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("一键三连", v.triple())

async def _unfollow_user(uid: int, cred: Credential) -> dict:
    u = user.User(uid=uid, credential=cred)
    return await _call("取消关注", u.modify_relation(relation=user.RelationType.UNSUBSCRIBE))


# ═══════════════════════════════════════════════════════════════════════════════
# BiliClient — 同步封装，对外暴露的主类
# ═══════════════════════════════════════════════════════════════════════════════

class BiliClient:
    """
    哔哩哔哩 API 客户端。

    Cookie 直接通过构造函数传入，支持两种方式：

    方式一：dict 传入
        cookies = {"SESSDATA": "...", "bili_jct": "...", "DedeUserID": "..."}
        client = BiliClient(cookies)

    方式二：从环境变量读取
        client = BiliClient.from_env()
        # 需要设置：BILI_SESSDATA, BILI_JCT, BILI_USERID

    Cookie 获取方式（browser_use 自动获取，见 SKILL.md）：
        1. browser_use navigate → https://www.bilibili.com
        2. browser_use get_cookies → 获取 SESSDATA / bili_jct / DedeUserID
        3. 加载 offload env 文件注入环境变量
    """

    def __init__(self, cookies: dict[str, str] | None = None):
        self._cred: Credential | None = None
        if cookies:
            if not cookies.get("SESSDATA"):
                raise ValueError("cookies 必须包含 'SESSDATA' 字段")
            self._cred = make_credential(cookies)

    @classmethod
    def from_env(cls) -> "BiliClient":
        """从环境变量构建客户端。需要 BILI_SESSDATA / BILI_JCT / BILI_USERID。"""
        sessdata = os.environ.get("BILI_SESSDATA", "")
        if not sessdata:
            raise ValueError("环境变量 BILI_SESSDATA 未设置")
        return cls({
            "SESSDATA":   sessdata,
            "bili_jct":   os.environ.get("BILI_JCT", ""),
            "DedeUserID": os.environ.get("BILI_USERID", ""),
            "buvid3":     os.environ.get("BILI_BUVID3", ""),
        })

    def _auth(self, require_write: bool = False) -> Credential:
        """获取认证凭证，未登录时抛出 AuthenticationError。"""
        if not self._cred or not self._cred.sessdata:
            raise AuthenticationError("未登录，请先传入 Cookie")
        if require_write and not self._cred.bili_jct:
            raise AuthenticationError("写操作需要 bili_jct Cookie")
        return self._cred

    # ── 账号 ──────────────────────────────────────────────────────────────

    def whoami(self) -> dict:
        """获取当前登录用户信息。"""
        return _run(_get_self_info(self._auth()))

    # ── 视频 ──────────────────────────────────────────────────────────────

    def get_video(
        self,
        bvid: str,
        *,
        subtitle: bool = False,
        subtitle_timeline: bool = False,
        ai_summary: bool = False,
        comments: bool = False,
        related: bool = False,
    ) -> dict:
        """
        获取视频详情。

        bvid: BV 号或包含 BV 号的 URL
        subtitle: 是否获取字幕（纯文本）
        subtitle_timeline: 是否获取带时间轴字幕
        ai_summary: 是否获取 AI 总结（需登录）
        comments: 是否获取热门评论
        related: 是否获取相关视频
        """
        bvid = extract_bvid(bvid)
        cred = self._cred

        async def _fetch():
            info = await _get_video_info(bvid, cred)
            sub_text, sub_raw = "", []
            if subtitle or subtitle_timeline:
                sub_text, sub_raw = await _get_video_subtitle(bvid, cred)
            ai = await _get_ai_summary(bvid, cred) if ai_summary else ""
            cmts = await _get_video_comments(bvid, cred) if comments else []
            rels = await _get_related_videos(bvid, cred) if related else []
            return info, sub_text, sub_raw, ai, cmts, rels

        info, sub_text, sub_raw, ai, cmts, rels = _run(_fetch())

        from .payloads import normalize_video_command_payload
        return normalize_video_command_payload(
            info,
            subtitle_text=sub_text,
            subtitle_items=sub_raw if subtitle_timeline else None,
            ai_summary=ai,
            comments=cmts,
            related=rels,
        )

    # ── 用户 ──────────────────────────────────────────────────────────────

    def get_user(self, uid: int) -> dict:
        """获取用户主页信息。"""
        async def _fetch():
            info = await _get_user_info(uid, self._cred)
            rel  = await _get_user_relation(uid, self._cred)
            return info, rel
        info, rel = _run(_fetch())
        from .payloads import normalize_user, normalize_relation
        return {"user": normalize_user(info), "relation": normalize_relation(rel)}

    def get_user_videos(self, uid: int, count: int = 20) -> list:
        """获取用户发布的视频列表。"""
        from .payloads import normalize_video_summary
        items = _run(_get_user_videos(uid, count, self._cred))
        return [normalize_video_summary(v) for v in items]

    # ── 搜索 ──────────────────────────────────────────────────────────────

    def search_users(self, keyword: str, page: int = 1) -> list:
        """搜索用户。"""
        from .payloads import normalize_search_user
        items = _run(_search_users(keyword, page))
        return [normalize_search_user(u) for u in items]

    def search_videos(self, keyword: str, page: int = 1, count: int = 20) -> list:
        """搜索视频。"""
        from .payloads import normalize_search_video
        items = _run(_search_videos(keyword, page, count))
        return [normalize_search_video(v) for v in items]

    # ── 发现 ──────────────────────────────────────────────────────────────

    def get_hot(self, page: int = 1, count: int = 20) -> list:
        """获取热门视频。"""
        from .payloads import normalize_video_summary
        items = _run(_get_hot(page, count))
        return [normalize_video_summary(v) for v in items]

    def get_rank(self, day: int = 3, count: int = 50) -> list:
        """获取全站排行榜。day: 1/3/7"""
        from .payloads import normalize_video_summary
        items = _run(_get_rank(day, count))
        return [normalize_video_summary(v) for v in items]

    def get_feed(self, offset: int = 0) -> dict:
        """获取关注动态 Feed（需登录）。"""
        return _run(_get_feed(offset, self._auth()))

    def get_my_dynamics(self, offset: int = 0) -> list:
        """获取我发布的动态（需登录）。"""
        from .payloads import normalize_dynamic_item
        cred = self._auth()
        info = _run(_get_self_info(cred))
        uid  = int(info.get("mid", 0))
        result = _run(_get_my_dynamics(uid, offset, cred))
        items = result.get("items", []) or []
        return [normalize_dynamic_item(i) for i in items]

    def post_dynamic(self, text: str) -> dict:
        """发布文字动态（需登录）。"""
        return _run(_post_dynamic(text, self._auth(require_write=True)))

    def delete_dynamic(self, dynamic_id: int) -> dict:
        """删除动态（需登录）。"""
        return _run(_delete_dynamic(dynamic_id, self._auth(require_write=True)))

    # ── 收藏 ──────────────────────────────────────────────────────────────

    def get_favorites(self, folder_id: int | None = None, page: int = 1, count: int = 20) -> list | dict:
        """
        获取收藏夹。
        - folder_id=None: 返回收藏夹列表
        - folder_id=<id>: 返回该收藏夹内的视频
        """
        cred = self._auth()
        if folder_id is None:
            info = _run(_get_self_info(cred))
            uid  = int(info.get("mid", 0))
            from .payloads import normalize_favorite_folder
            items = _run(_get_favorite_folders(uid, cred))
            return [normalize_favorite_folder(f) for f in items]
        from .payloads import normalize_favorite_media
        items = _run(_get_favorite_videos(folder_id, page, count, cred))
        return [normalize_favorite_media(v) for v in items]

    def get_following(self, page: int = 1) -> list:
        """获取关注列表（需登录）。"""
        cred = self._auth()
        info = _run(_get_self_info(cred))
        uid  = int(info.get("mid", 0))
        from .payloads import normalize_following_user
        items = _run(_get_following(uid, page, cred))
        return [normalize_following_user(u) for u in items]

    def get_watch_later(self) -> list:
        """获取稍后再看列表（需登录）。"""
        from .payloads import normalize_watch_later_item
        items = _run(_get_watch_later(self._auth()))
        return [normalize_watch_later_item(v) for v in items]

    def get_history(self) -> list:
        """获取观看历史（需登录）。"""
        from .payloads import normalize_history_item
        items = _run(_get_history(self._auth()))
        return [normalize_history_item(v) for v in items]

    # ── 互动 ──────────────────────────────────────────────────────────────

    def like(self, bvid: str, undo: bool = False) -> dict:
        """点赞 / 取消点赞。"""
        from .payloads import action_result
        bvid = extract_bvid(bvid)
        _run(_like_video(bvid, self._auth(require_write=True), undo=undo))
        return action_result("like" if not undo else "unlike", bvid=bvid)

    def coin(self, bvid: str, num: int = 1) -> dict:
        """投币（1 或 2 枚）。"""
        from .payloads import action_result
        bvid = extract_bvid(bvid)
        _run(_coin_video(bvid, self._auth(require_write=True), num=num))
        return action_result("coin", bvid=bvid, num=num)

    def triple(self, bvid: str) -> dict:
        """一键三连（点赞 + 投币 + 收藏）。"""
        from .payloads import action_result
        bvid = extract_bvid(bvid)
        _run(_triple_video(bvid, self._auth(require_write=True)))
        return action_result("triple", bvid=bvid)

    def unfollow(self, uid: int) -> dict:
        """取消关注用户。"""
        from .payloads import action_result
        _run(_unfollow_user(uid, self._auth(require_write=True)))
        return action_result("unfollow", uid=uid)
