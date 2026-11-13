"""Unsplash图片服务（异步 + 进程内缓存）。

原先 `search_photos` 用同步 `requests.get(..., timeout=20)`，而调用它的
`/api/poi/photo` 是 `async def` 路由：一次请求就会把 uvicorn 的事件循环
卡住最多 20 秒。页面打开结果页会并发请求十几个景点图片，实际被串行化，
几十秒到几分钟都有可能，期间其它接口（包括生成行程）全部排队。

这里改成：
1. `httpx.AsyncClient` 异步请求，真正的并发；
2. 超时降到 6 秒，Unsplash 打不通时快速失败，不再拖死整个进程；
3. 进程内 TTL 缓存（6 小时），同一个景点名只查一次；
4. 缓存做了上限，避免长时间运行内存无界增长。
"""

import time
from typing import Optional

import httpx

from ..config import get_settings

# 单次请求超时（秒）。Unsplash 在国内机房经常连不上，宁可快速失败也不能卡住事件循环
TIMEOUT_SECONDS = 6.0

# 图片 URL 基本不变，缓存久一点：6 小时
CACHE_TTL_SECONDS = 6 * 60 * 60

# 缓存条目上限，超过就整体清空（景点名数量有限，实际不会触发）
CACHE_MAX_ENTRIES = 512

_client: Optional[httpx.AsyncClient] = None
_cache: dict[str, tuple[float, Optional[str]]] = {}


def _get_client() -> httpx.AsyncClient:
    """复用同一个 AsyncClient，省掉每次请求的 TCP/TLS 握手。"""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    return _client


class UnsplashService:

    def __init__(self):
        settings = get_settings()
        self.access_key = settings.unsplash_access_key
        self.base_url = settings.unsplash_base_url

    def _cache_get(self, query: str) -> Optional[str]:
        entry = _cache.get(query)
        if entry and entry[0] > time.monotonic():
            return entry[1]
        return None

    def _cache_put(self, query: str, url: Optional[str]) -> None:
        if len(_cache) >= CACHE_MAX_ENTRIES:
            _cache.clear()
        _cache[query] = (time.monotonic() + CACHE_TTL_SECONDS, url)

    async def get_photo_url(self, query: str) -> Optional[str]:
        """按关键词取一张图片 URL，失败返回 None（不抛异常）。"""
        cached = self._cache_get(query)
        if cached is not None:
            return cached

        url = await self._search_photo(query)
        self._cache_put(query, url)
        return url

    async def _search_photo(self, query: str) -> Optional[str]:
        params = {
            "query": query,
            "per_page": 1,
            "client_id": self.access_key,
        }
        try:
            response = await _get_client().get(
                f"{self.base_url}/search/photos", params=params
            )
            response.raise_for_status()
            results = response.json().get("results", [])
        except Exception as exc:
            # 超时/网络不可达都走这里，调用方会拿到 None，前端显示占位图
            print(f"⚠️  Unsplash 请求失败（{type(exc).__name__}）: {exc}")
            return None

        if not results:
            return None
        return results[0].get("urls", {}).get("regular")


_unsplash_service: Optional[UnsplashService] = None


def get_unsplash_service() -> UnsplashService:
    global _unsplash_service
    if _unsplash_service is None:
        _unsplash_service = UnsplashService()
    return _unsplash_service
