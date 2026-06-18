"""
@file        market_intel/scraper.py
@description 市場資訊爬蟲：關鍵字搜尋 + 網頁內容抓取
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0

支援資料來源：
- 政府電子採購網（關鍵字搜尋標案公告）
- 衛福部/社會局/長照相關政策公告
- 產業新聞（Google News / RSS）
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 預設監控關鍵字（可從 system_params 覆寫）
DEFAULT_KEYWORDS = [
    "復康巴士", "沐浴車", "福祉車", "輪椅升降機",
    "長照", "無障礙", "輔具補助", "身障",
    "標案", "採購公告",
]

SEARCH_SOURCES = {
    "news": {
        "label": "產業新聞",
        "url": "https://serpapi.com/search",
    },
}

TIMEOUT = 30


class SearchResult:
    """單筆搜尋結果"""

    def __init__(self, title: str, url: str, snippet: str, source: str, relevance: str = "medium"):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source
        self.relevance = relevance

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "relevance": self.relevance,
        }


async def fetch_page_content(url: str) -> str:
    """抓取網頁內容，回傳純文字（過濾 JS/JSON/CSS）"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            resp.raise_for_status()
            text = resp.text
            # 移除 HTML 標籤
            import re
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            # 移除 JavaScript 變數宣告和 JSON 資料
            text = re.sub(r'window\.[a-zA-Z_$][\w$]*\s*=\s*[^;]+;', '', text)
            text = re.sub(r'var\s+\w+\s*=\s*[^;]+;', '', text)
            text = re.sub(r'function\s+\w+\s*\([^)]*\)\s*\{[^}]*\}', '', text)
            # 合併空白
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:2000]  # 取前 2000 字
    except Exception as e:
        logger.warning("Fetch %s failed: %s", url, e)
        return ""


async def search(keywords: list[str] | None = None, num_results: int = 5) -> list[SearchResult]:
    """搜尋市場資訊

    目前使用 websearch 工具查詢，未來可加入政府採購網 API。
    """
    kw = keywords or DEFAULT_KEYWORDS
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for keyword in kw[:3]:  # 最多查 3 個關鍵字
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": keyword,
                        "hl": "zh-TW",
                        "gl": "tw",
                        "num": num_results,
                        "api_key": "__missing__",  # 由環境變數提供
                    },
                )
                # 如果 SerpAPI 沒設定，fallback 到簡單搜尋
                if resp.status_code != 200:
                    logger.warning("SerpAPI failed (%s), using fallback", resp.status_code)
                    # 使用 Google 新聞 RSS
                    fallback_results = await _search_fallback(keyword, num_results)
                    results.extend(fallback_results)
                else:
                    data = resp.json()
                    for item in data.get("organic_results", []):
                        url = item.get("link", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            results.append(SearchResult(
                                title=item.get("title", ""),
                                url=url,
                                snippet=item.get("snippet", ""),
                                source="web",
                            ))
        except Exception as e:
            logger.warning("Search keyword '%s' failed: %s", keyword, e)

    return results


async def _search_fallback(keyword: str, num: int) -> list[SearchResult]:
    """SerpAPI 不可用時的 fallback 搜尋 — 使用 DuckDuckGo HTML 搜尋（取得真實文章網址）"""
    results: list[SearchResult] = []
    try:
        import urllib.parse
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": keyword},
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            )
            if resp.status_code == 200:
                import re
                html = resp.text
                # 從 DuckDuckGo 結果中提取真實 URL（解開 uddg 跳轉）和標題
                titles = re.findall(r'class="result__title"[^>]*>(.*?)</(?:a|div)', html, re.DOTALL)
                links = re.findall(r'class="result__url"[^>]*href="([^"]+)"', html)
                snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)', html, re.DOTALL)

                # 備用：從 result__a 提取連結
                if not links:
                    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)

                for i in range(min(num, len(links))):
                    url = links[i]
                    if "uddg=" in url:
                        from urllib.parse import parse_qs, urlparse
                        qs = parse_qs(urlparse(url).query)
                        url = qs.get("uddg", [""])[0]
                    title = ""
                    if i < len(titles):
                        title = re.sub(r'<[^>]+>', '', titles[i]).strip()
                    snippet = ""
                    if i < len(snippets):
                        snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                    if url and url not in {r.url for r in results}:
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet[:300] if snippet else "",
                            source="news",
                        ))
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s", e)

    # 如果 DuckDuckGo 沒結果，fallback 到 Google News RSS
    if not results:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(
                    "https://news.google.com/rss/search",
                    params={"q": keyword, "hl": "zh-TW", "gl": "TW"},
                )
                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text)
                    entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
                    for item in entries[:num]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "") or item.findtext("summary", "")
                        if link and link not in {r.url for r in results}:
                            results.append(SearchResult(
                                title=title,
                                url=link,
                                snippet=desc[:300] if desc else "",
                                source="news",
                            ))
        except Exception as e:
            logger.warning("Google News RSS fallback failed: %s", e)

    return results
