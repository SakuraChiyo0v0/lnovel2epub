"""努努书坊（kanunu8）：简体出版读物（国内外文学、推理、科幻、武侠……）。页面是 GBK。

站内没有搜索，所以按书名找要先建本地索引（`--reindex`）：
  ① 29 个分类页 + 专题页上列出的书
  ② 作家总目（/files/writer/ 共 10 页）→ 每个作家页上的书
有些书只出现在作家页里（比如《活着》），所以两步都要。索引存在缓存目录，7 天内复用。
索引里查不到的书，直接给书页链接也能抓。

书页有两种排版：新版 <div class="mulu-list"> 分卷，老版 <table> 里一行 <td><strong>卷名</strong>。
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from .common import cache_dir, clean, get, log, paragraphs

NAME = "kanunu"
BASE = "https://www.kanunu8.com"
ENC = "gb18030"
URL_RE = re.compile(r"kanunu8\.com(/(?:book\d*|wuxia|tuili)/[\w]+/?(?:index\.html)?)")
BOOK_RE = re.compile(r"""href=["'](?:https?://www\.kanunu8\.com)?(/book\d*/[\w]+/(?:index\.html)?)["'][^>]*>(.*?)</a>""", re.S)
INDEX_TTL = 7 * 86400


def match(target: str) -> str | None:
    m = URL_RE.search(target)
    return re.sub(r"index\.html$", "", m.group(1)) if m else None


def _get(path: str) -> str:
    return get(BASE + path, BASE + "/", ENC)


def _title(t: str) -> str:
    return clean(t).strip("《》 ")


def _index_path() -> str:
    return os.path.join(cache_dir(), "kanunu-index.json")


def build_index() -> dict:
    t0 = time.time()
    books: dict[str, dict] = {}

    def add(path, label, author=""):
        path = re.sub(r"index\.html$", "", path)
        label = _title(label)
        if not label or path in books:
            return
        a, _, t = label.partition(":") if ":" in label else label.partition("：")
        if t and not author and len(a) <= 12:
            author, label = a.strip(), t.strip()
        books[path] = {"title": label.strip("《》 "), "author": author}

    genres = _get("/genres.html")
    cats = sorted(set(re.findall(r'href="(?:https://www\.kanunu8\.com)?(/(?:files/[\w./]+|wuxia/|tuili/))"', genres)))
    cats = [c for c in cats if "writer" not in c] + ["/zt/"]
    writers: dict[str, str] = {}
    for p in range(1, 11):
        page = _get("/files/writer/" + ("" if p == 1 else f"18-{p}.html"))
        for h, t in re.findall(r"""href=['"]((?:/zj/\d+|/files/writer/\d+)\.html)['"][^>]*>([^<]+)</a>""", page):
            writers[h] = re.sub(r"(作品全?集).*$", "", t.split(":")[-1].split("：")[-1]).strip()

    def scan(path):
        try:
            return path, _get(path)
        except Exception as exc:  # noqa: BLE001
            log(f"warn: 索引跳过 {path}: {exc}")
            return path, ""

    with ThreadPoolExecutor(4) as ex:
        for path, page in ex.map(scan, cats):
            for h, t in BOOK_RE.findall(page):
                add(h, t)
        for path, page in ex.map(scan, list(writers)):
            for h, t in BOOK_RE.findall(page):
                add(h, t, writers[path])

    idx = {"built": time.time(), "books": books}
    with open(_index_path(), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False)
    log(f"努努书坊索引：{len(books)} 本（{len(cats)} 个分类 + {len(writers)} 个作家页，{time.time() - t0:.0f}s）")
    return idx


def load_index(rebuild: bool = False) -> dict:
    p = _index_path()
    if not rebuild and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            idx = json.load(f)
        if time.time() - idx.get("built", 0) < INDEX_TTL:
            return idx
    return build_index()


def search(keyword: str, rebuild: bool = False) -> list[dict]:
    idx = load_index(rebuild)
    kw = keyword.replace(" ", "")
    hits = [{"source": NAME, "id": path, "title": b["title"], "author": b["author"]}
            for path, b in idx["books"].items() if kw in b["title"].replace(" ", "")]
    # 书名完全相等的排前面，其次按书名长度
    hits.sort(key=lambda h: (h["title"] != keyword, len(h["title"])))
    return hits


def _toc(page: str) -> list[tuple[str, list[tuple[str, str]]]]:
    vols: list[tuple[str, list[tuple[str, str]]]] = []
    if "mulu-list" in page:
        for vname, block in re.findall(r'<div class="mulu-title">\s*<h2[^>]*>(.*?)</h\d>\s*</div>\s*<div class="mulu-list">(.*?)</div>', page, re.S):
            eps = re.findall(r"""<a href=["'](\d+\.html)["']>(.*?)</a>""", block)
            if eps:
                vols.append((clean(vname), [(h, clean(n)) for h, n in eps]))
        return vols
    # 老版：表格里卷名行 + 章节行交替
    cur = ("正文", [])
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        eps = re.findall(r"""<a href=["'](\d+\.html)["'][^>]*>(.*?)</a>""", row)
        if eps:
            cur[1].extend((h, clean(n)) for h, n in eps)
            continue
        head = re.search(r"<strong>(.*?)</strong>", row, re.S)
        if head and "colspan" in row and not re.search(r"作品集|内容简介", row):
            if cur[1]:
                vols.append(cur)
            cur = (clean(head.group(1)), [])
    if cur[1]:
        vols.append(cur)
    return vols


def _body(page: str) -> str:
    m = re.search(r'<div class="neirong" id="neirong">(.*?)</div>', page, re.S)
    if m:
        return paragraphs(m.group(1))
    # 老版：正文在 <td width="820"> 里的 <p>
    m = re.search(r'<td width="820"[^>]*>(.*?)</td>', page, re.S)
    seg = m.group(1) if m else " ".join(re.findall(r"<p>(.*?)</p>", page, re.S))
    return paragraphs(seg)


def crawl(path: str, with_images: bool = True, volume: int | None = None) -> dict:
    if not path.endswith("/") and not path.endswith(".html"):
        path += "/"
    book_url = BASE + path
    base = book_url.rsplit("/", 1)[0] + "/"
    page = get(book_url, BASE + "/", ENC)
    title = ""
    m = re.search(r'<div class="catalog">\s*<h1>(.*?)</h1>', page, re.S) or re.search(r"<title>(.*?)</title>", page, re.S)
    if m:
        title = re.split(r" - | by |全集|在线阅读", clean(m.group(1)))[0].strip()
    author = ""
    m = re.search(r'<div class="info">作者：(.*?)</div>', page) or re.search(r"作者：\s*([^<\s]{1,20})", page)
    if m:
        author = clean(m.group(1))
    if not author:
        m = re.search(r"<title>.*? - (\S{1,12}) - 小说在线阅读", page) or re.search(r"<title>.*? by (\S{1,12}) -", page)
        author = m.group(1) if m else ""

    vols = _toc(page)
    if not vols:
        raise RuntimeError(f"努努书坊书页上没找到目录：{book_url}")
    if volume:
        if not 1 <= volume <= len(vols):
            raise SystemExit(f"--volume 超出范围：共 {len(vols)} 卷")
        vols = [vols[volume - 1]]
        title = f"{title} {vols[0][0]}"
    multi = len(vols) > 1

    eps = [(h, n, v) for v, items in vols for h, n in items]
    chapters = []
    for i, (href, name, vname) in enumerate(eps, 1):
        text = _body(get(base + href, book_url, ENC))
        label = f"{vname} {name}" if multi and vname != "正文" else name
        chapters.append({"title": label, "text": text, "images": []})
        log(f"[{i}/{len(eps)}] {label} {len(text)} 字")

    return {"source": NAME, "bookId": "kanunu" + re.sub(r"\W+", "-", path).rstrip("-") + (f"-v{volume}" if volume else ""),
            "title": title, "author": author, "cover": "", "referer": book_url, "chapters": chapters}
