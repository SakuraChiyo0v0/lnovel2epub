"""lnovel.tw（輕小說百科）：繁体台版日轻。章节页是静态 HTML，正文在 <article class="card mb-4">。

没有可用的站内搜索，只接受书号或书页链接。
"""
from __future__ import annotations

import re

from .common import clean, get, log

NAME = "lnovel"
BASE = "https://lnovel.tw"
URL_RE = re.compile(r"lnovel\.tw/books-(\d+)")


def match(target: str) -> str | None:
    m = URL_RE.search(target)
    return m.group(1) if m else None


def search(keyword: str) -> list[dict]:
    return []


def _cover(page: str, title: str) -> str:
    """封面：优先 og:image；否则按 alt==书名 找 <img>（属性顺序不固定，逐标签解析）。"""
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', page)
    cover = m.group(1) if m else ""
    if not cover:
        for tag in re.findall(r"<img[^>]*>", page):
            alt = re.search(r'alt="([^"]*)"', tag)
            src = re.search(r'src="([^"]+)"', tag)
            if alt and src and alt.group(1).strip() == title:
                cover = src.group(1)
                break
    if cover.startswith("/"):
        cover = BASE + cover
    # 缩略图 .jpg.small.webp → 同图的 .jpg（270×360）
    if cover.endswith(".small.webp"):
        base = cover[: -len(".small.webp")]
        if not re.search(r"\.(jpg|jpeg|png|webp)$", base, re.I):
            base += ".jpg"
        cover = base
    return cover


def crawl(book_id: str, with_images: bool = True, volume: int | None = None) -> dict:
    page = get(f"{BASE}/books-{book_id}", BASE + "/")
    title = clean(re.search(r"<title>(.*?)</title>", page, re.S).group(1)).split(" - ")[0]
    author = ""
    m = re.search(r"作者[\s\S]{0,120}?>\s*([^<\s][^<]{0,30})", page)
    if m:
        author = clean(m.group(1))

    links: list[tuple[str, str]] = []
    for href, name in re.findall(r'href="(/chapters-\d+)"[^>]*>(.*?)</a>', page, re.S):
        if href not in [h for h, _ in links]:
            links.append((href, clean(name) or f"第{len(links) + 1}节"))

    chapters = []
    for i, (href, name) in enumerate(links, 1):
        ch_html = get(BASE + href, f"{BASE}/books-{book_id}")
        art = re.search(r'<article class="card mb-4">(.*?)</article>', ch_html, re.S)
        if not art:
            log(f"warn: {href} 没有正文容器，跳过")
            continue
        body = art.group(1)
        paras = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
        text = "\n\n".join(p for p in paras if p)
        # 插图：「插畫」是独立一节，正文里只有 <img> 没有 <p>，只取 <p> 会整节丢
        images = []
        if with_images:
            images = [s if s.startswith("http") else BASE + s
                      for s in re.findall(r'<img[^>]*src="([^"]+)"', body) if "/uploads/" in s]
        chapters.append({"title": name, "text": text, "images": images})
        log(f"[{i}/{len(links)}] {name} {len(text)} 字{' · ' + str(len(images)) + ' 图' if images else ''}")

    return {"source": NAME, "bookId": book_id, "title": title, "author": author,
            "cover": _cover(page, title), "referer": BASE + "/", "chapters": chapters}
