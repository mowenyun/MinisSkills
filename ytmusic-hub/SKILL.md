---
name: ytmusic-hub
description: 使用 Python + ytmusicapi 读写 YouTube Music 数据的技能，通过 browser_use get_cookies 自动获取 Cookie 完成认证，无需手动复制。支持获取歌单列表、收藏歌曲、歌单详情，创建/编辑/删除歌单，搜索歌曲并添加到歌单，获取推荐、图表、歌词等。当用户提到"YouTube Music"、"YT Music"、"ytmusic"、"ytmusic-hub"、"获取 YouTube 歌单"、"创建 YouTube Music 歌单"、"我的收藏歌曲"、"YTM 歌单"，或任何需要以编程方式读写 YouTube Music 数据的场景，必须触发本技能。
---

# ytmusic-hub

使用 `ytmusicapi` 库操作 YouTube Music，通过浏览器 Cookie 认证，支持歌单管理、搜索、收藏等全部功能。

---

## 环境准备

### 安装依赖
```bash
pip install ytmusicapi
```

### 认证文件路径
```
/var/minis/workspace/ytmusic_headers.json
```

---

## 认证流程（每次使用前执行）

认证分两步：**获取 Cookie** → **生成认证文件**。

### Step 1：获取 Cookie

用 `browser_use` 打开 YouTube Music 并获取 Cookie：

```python
# browser_use navigate: https://music.youtube.com
# browser_use get_cookies -> 保存到 env 文件
```

确认页面已登录（右上角显示头像/用户名），然后 `get_cookies` 获取全部 Cookie，记录 env 文件路径。

### Step 2：生成认证文件

加载 env 文件后运行认证脚本：

```bash
. /var/minis/offloads/env_cookies_youtube_com_xxx.sh
python3 /var/minis/skills/ytmusic-hub/scripts/setup_auth.py
```

脚本会自动从环境变量读取所有 Cookie，生成带 SAPISIDHASH 的认证文件到 `/var/minis/workspace/ytmusic_headers.json`。

### Step 3：初始化 YTMusic 客户端

使用统一初始化模块，自动处理 DNS 污染和 SSL 证书问题：

```python
import sys
sys.path.insert(0, "/var/minis/skills/ytmusic-hub/scripts")
from ytmusic_client import get_client

yt = get_client()
```

`get_client()` 会自动：
1. patch urllib3 SSL context（绕过 iSH 证书问题）
2. 检测本地 DNS 是否被污染
3. 若污染，通过 Google DoH (`dns.google`) 查询真实 IP，patch socket 强制走正确 IP
4. 返回可用的 YTMusic 实例，失败则抛出含原因的异常

---

## 功能 API 参考

### 📋 歌单管理

```python
# 获取我的所有歌单
playlists = yt.get_library_playlists(limit=25)
# 返回: [{playlistId, title, count, ...}, ...]

# 获取歌单详细内容（包含所有曲目）
playlist = yt.get_playlist(playlistId, limit=100)
# 返回: {title, description, trackCount, tracks: [{videoId, title, artists, ...}]}

# 创建新歌单
playlistId = yt.create_playlist(
    title="歌单名称",
    description="歌单描述",
    privacy_status="PRIVATE"  # PUBLIC / PRIVATE / UNLISTED
)

# 编辑歌单信息
yt.edit_playlist(playlistId, title="新名称", description="新描述")

# 删除歌单
yt.delete_playlist(playlistId)

# 添加歌曲到歌单（videoId 列表）
yt.add_playlist_items(playlistId, videoIds=["videoId1", "videoId2"])

# 从歌单移除歌曲
# 先获取 setVideoId（歌单内的唯一标识，不同于 videoId）
tracks = yt.get_playlist(playlistId)["tracks"]
yt.remove_playlist_items(playlistId, tracks=[
    {"videoId": t["videoId"], "setVideoId": t["setVideoId"]}
    for t in tracks if t["title"] == "目标歌曲"
])
```

### ❤️ 收藏与资料库

```python
# 获取收藏歌曲（Liked Songs）
liked = yt.get_liked_songs(limit=100)
tracks = liked["tracks"]  # [{videoId, title, artists, album, ...}]

# 获取资料库歌曲
songs = yt.get_library_songs(limit=25)

# 获取资料库专辑
albums = yt.get_library_albums(limit=25)

# 获取资料库艺术家
artists = yt.get_library_artists(limit=25)

# 点赞/取消点赞歌曲
yt.rate_song(videoId, "LIKE")     # LIKE / DISLIKE / INDIFFERENT
```

### 🔍 搜索

```python
# 搜索（返回混合结果）
results = yt.search("周杰伦 夜曲")

# 按类型搜索
songs   = yt.search("周杰伦", filter="songs")    # 歌曲
videos  = yt.search("周杰伦", filter="videos")   # 视频
albums  = yt.search("周杰伦", filter="albums")   # 专辑
artists = yt.search("周杰伦", filter="artists")  # 艺术家

# 获取 videoId（用于添加到歌单）
videoId = songs[0]["videoId"]
```

### 🎵 浏览与推荐

```python
# 首页推荐
home = yt.get_home()

# 全球/地区排行榜
charts = yt.get_charts(country="HK")  # TW / CN / US / JP 等

# 心情歌单分类
moods = yt.get_mood_categories()
mood_playlists = yt.get_mood_playlists(params=moods["Moods & moments"][0]["params"])

# 获取歌词
watchPlaylist = yt.get_watch_playlist(videoId="videoId")
lyricsId = watchPlaylist.get("lyrics")
if lyricsId:
    lyrics = yt.get_lyrics(lyricsId)
    print(lyrics["lyrics"])
```

### 🎤 艺术家与专辑

```python
# 获取艺术家信息
artist = yt.get_artist(channelId)

# 获取专辑
album = yt.get_album(browseId)

# 获取用户主页
user = yt.get_user(channelId)
user_playlists = yt.get_user_playlists(channelId, params)
```

---

## 常见工作流示例

### 工作流 A：搜索歌曲并加入指定歌单

```python
# 1. 搜索
results = yt.search("告五人 爱人错过", filter="songs")
videoId = results[0]["videoId"]
title = results[0]["title"]
print(f"找到: {title} ({videoId})")

# 2. 获取歌单列表，让用户选择
playlists = yt.get_library_playlists()
for i, pl in enumerate(playlists):
    print(f"{i+1}. {pl['title']} [{pl['playlistId']}]")

# 3. 添加
yt.add_playlist_items(playlistId, videoIds=[videoId])
print(f"✅ 已添加到歌单")
```

### 工作流 B：创建新歌单并批量添加收藏歌曲

```python
# 1. 创建歌单
new_id = yt.create_playlist("我的精选", "从收藏中挑选", "PRIVATE")

# 2. 获取收藏
liked = yt.get_liked_songs(limit=50)
video_ids = [t["videoId"] for t in liked["tracks"][:20]]

# 3. 批量添加（每次最多50首）
yt.add_playlist_items(new_id, videoIds=video_ids)
print(f"✅ 已创建歌单并添加 {len(video_ids)} 首歌")
```

### 工作流 C：导出歌单为 Markdown

```python
playlist = yt.get_playlist(playlistId, limit=200)
lines = [f"# {playlist['title']}", f"> {playlist.get('description','')}", ""]
for i, t in enumerate(playlist["tracks"], 1):
    artists = ", ".join(a["name"] for a in t.get("artists", []))
    lines.append(f"{i}. **{t['title']}** — {artists}")
print("\n".join(lines))
```

---

## 注意事项

- **Cookie 有效期**：通常数天到数周，失效后重新执行认证流程即可
- **认证文件安全**：`ytmusic_headers.json` 包含登录凭据，不要分享
- **API 限制**：ytmusicapi 是非官方库，大量操作可能触发 Google 风控，建议适量使用
- **网络要求**：需要能访问 `music.youtube.com`（需代理），iSH 的 SSL patch 已内置在初始化模板中
- **videoId vs setVideoId**：从歌单移除歌曲时必须用 `setVideoId`（歌曲在该歌单内的唯一 ID），不能用 `videoId`
