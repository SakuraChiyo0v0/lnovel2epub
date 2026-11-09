#!/usr/bin/env python3
"""lnovel2epub —— 从 lnovel.tw（輕小說百科）抓取轻小说正文，打包成 EPUB3。

用法：
    python3 lnovel2epub.py 3217                     # 书号
    python3 lnovel2epub.py https://lnovel.tw/books-3217
    python3 lnovel2epub.py 3217 --out ~/books       # 落库根目录（默认 ./books）
    python3 lnovel2epub.py 3217 --simplified        # 繁转简（需要 opencc）
    python3 lnovel2epub.py 3217 --no-images         # 跳过插图

只依赖 ebooklib + pillow（繁转简额外需要 opencc-python-reimplemented）。
"""
from __future__ import annotations

import argparse
import html as htmllib
import io
import json
import os
import re
import sys
import time
import urllib.request

BASE = "https://lnovel.tw"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
EXTS = (".jpg", ".jpeg", ".png", ".webp")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def get(url: str, retries: int = 3) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE + "/"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries - 1:
                time.sleep(2 + attempt * 2)
    raise RuntimeError(f"请求失败 {url}: {last}")


def get_bytes(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE + "/"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return None


def clean(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment)
    text = re.sub(r"<[^>]+>", "", text)
    text = htmllib.unescape(text).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def safe_name(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]", " ", name).strip()
    return re.sub(r"\s+", " ", name) or "未命名"


def find_cover(page: str, title: str) -> str:
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


def crawl(book_id: str, with_images: bool = True) -> dict:
    page = get(f"{BASE}/books-{book_id}")
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
        ch_html = get(BASE + href)
        art = re.search(r'<article class="card mb-4">(.*?)</article>', ch_html, re.S)
        if not art:
            log(f"warn: {href} 没有正文容器，跳过")
            continue
        body = art.group(1)
        paras = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
        text = "\n\n".join(p for p in paras if p)
        images: list[str] = []
        if with_images:
            for src in re.findall(r'<img[^>]*src="([^"]+)"', body):
                if "/uploads/" in src:
                    images.append(src if src.startswith("http") else BASE + src)
        chapters.append({"title": name, "text": text, "images": images})
        log(f"[{i}/{len(links)}] {name} {len(text)} 字{' · ' + str(len(images)) + ' 图' if images else ''}")

    return {
        "bookId": book_id,
        "title": title,
        "author": author,
        "cover": find_cover(page, title),
        "chapters": chapters,
    }


def to_jpeg(data: bytes) -> bytes | None:
    """WebP/其它格式统一转 JPEG：文件名写 .jpg 骗不过老阅读器。"""
    if data[:2] == b"\xff\xd8":
        return data
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None


def build(book: dict, out_root: str, simplified: bool = False) -> str:
    from ebooklib import epub

    title = safe_name(book["title"])
    if simplified:
        try:
            import opencc

            cc = opencc.OpenCC("t2s")
            title = safe_name(cc.convert(title))
        except ImportError:
            log("warn: 没装 opencc-python-reimplemented，跳过繁转简")

    if not os.path.isdir(out_root):
        os.makedirs(out_root, exist_ok=True)
    dest = os.path.join(out_root, title)
    os.makedirs(dest, exist_ok=True)

    eb = epub.EpubBook()
    eb.set_identifier(f"lnovel-{book['bookId']}")
    eb.set_title(title)
    eb.set_language("zh")
    if book.get("author"):
        eb.add_author(book["author"])

    cover = book.get("cover") or ""
    if cover:
        data = get_bytes(cover)
        if data:
            jpeg = to_jpeg(data)
            if jpeg:
                eb.set_cover("cover.jpg", jpeg)

    items = []
    for idx, ch in enumerate(book["chapters"], 1):
        name = safe_name(ch["title"])
        paragraphs = [p.strip() for p in (ch.get("text") or "").split("\n") if p.strip()]
        images = ch.get("images") or []
        if not paragraphs and not images:
            continue
        html = [f"<h2>{name}</h2>"]
        html += [f"<p>{p}</p>" for p in paragraphs]
        for j, url in enumerate(images, 1):
            data = get_bytes(url)
            jpeg = to_jpeg(data) if data else None
            if not jpeg:
                continue
            fname = f"i{idx:03d}_{j}.jpg"
            eb.add_item(epub.EpubItem(uid=fname, file_name=f"images/{fname}",
                                      media_type="image/jpeg", content=jpeg))
            html.append(f'<div style="text-align:center;margin:1em 0"><img src="images/{fname}" alt="{name}"/></div>')
        item = epub.EpubHtml(title=name, file_name=f"ch{idx:03d}.xhtml", lang="zh")
        item.content = "<html><body>" + "".join(html) + "</body></html>"
        eb.add_item(item)
        items.append(item)

    eb.toc = tuple(items)
    eb.add_item(epub.EpubNcx())
    eb.add_item(epub.EpubNav())
    eb.spine = ["nav", *items]

    path = os.path.join(dest, f"{title}.epub")
    epub.write_epub(path, eb)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="抓 lnovel.tw 轻小说并打包 EPUB")
    ap.add_argument("target", help="书号或 https://lnovel.tw/books-<id>")
    ap.add_argument("--out", default=os.environ.get("NOVEL_DIR", "./books"), help="落库根目录（默认 ./books）")
    ap.add_argument("--simplified", action="store_true", help="繁体转简体（需要 opencc）")
    ap.add_argument("--no-images", action="store_true", help="跳过插图")
    ap.add_argument("--json", action="store_true", help="只输出结果 JSON")
    a = ap.parse_args()

    m = re.search(r"(\d+)", a.target)
    if not m:
        raise SystemExit(f"解析不出书号：{a.target}")
    book_id = m.group(1)

    book = crawl(book_id, with_images=not a.no_images)
    path = build(book, a.out, simplified=a.simplified)
    result = {
        "title": book["title"],
        "author": book.get("author") or None,
        "chapters": len(book["chapters"]),
        "chars": sum(len(c["text"]) for c in book["chapters"]),
        "images": sum(len(c.get("images") or []) for c in book["chapters"]),
        "path": os.path.abspath(path),
        "size": os.path.getsize(path),
    }
    if a.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        log(f"完成：{result['title']}（{result['chapters']} 节 / {result['chars']} 字 / "
            f"{result['images']} 图 / {result['size'] // 1024}K）")
        print(os.path.abspath(path))


if __name__ == "__main__":
    main()
