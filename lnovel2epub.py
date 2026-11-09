#!/usr/bin/env python3
"""lnovel2epub —— 把在线小说站上的书抓下来，打包成 EPUB3。

用法：
    python3 lnovel2epub.py 活着                          # 书名：依次在各书源里搜，取第一个命中
    python3 lnovel2epub.py 活着 --list                   # 只列出各书源的搜索结果，不下载
    python3 lnovel2epub.py <书页链接>                    # 认得的站点直接抓
    python3 lnovel2epub.py 3217                          # 纯数字 = lnovel.tw 书号（兼容旧用法）
    python3 lnovel2epub.py 青春豬頭少年 --volume 1       # 多卷书选一卷；--volume 0 = 全部合成一本
    python3 lnovel2epub.py 活着 --source kanunu          # 只用某个书源
    python3 lnovel2epub.py --reindex                     # 重建需要本地索引的书源（努努书坊）
    选项：--out 目录  --simplified 繁转简  --no-images  --json

只依赖 ebooklib + pillow（繁转简额外需要 opencc-python-reimplemented）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re

from sources import BY_NAME, SOURCES, kanunu, lnovel
from sources.common import get_bytes, log


def safe_name(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]", " ", name).strip()
    return re.sub(r"\s+", " ", name) or "未命名"


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


def to_simplified(book: dict) -> dict:
    """繁转简：书名、作者、章节名、正文全部转换，返回新 dict，不改原对象。

    没装 opencc 直接报错退出：静默跳过会产出一本「以为是简体、其实是繁体」的书。
    """
    try:
        import opencc
    except ImportError:
        raise SystemExit("--simplified 需要 opencc：pip install opencc-python-reimplemented")
    cc = opencc.OpenCC("t2s")
    conv = lambda v: cc.convert(v) if isinstance(v, str) else v  # noqa: E731
    out = dict(book)
    out["title"] = conv(book.get("title") or "")
    out["author"] = conv(book.get("author") or "")
    out["chapters"] = [
        {**ch, "title": conv(ch.get("title") or ""), "text": conv(ch.get("text") or "")}
        for ch in book.get("chapters", [])
    ]
    return out


def build(book: dict, out_root: str) -> str:
    from ebooklib import epub

    title = safe_name(book["title"])
    os.makedirs(out_root, exist_ok=True)
    dest = os.path.join(out_root, title)
    os.makedirs(dest, exist_ok=True)
    ref = book.get("referer")

    eb = epub.EpubBook()
    eb.set_identifier(f"{book.get('source', 'lnovel')}-{book['bookId']}")
    eb.set_title(title)
    eb.set_language("zh")
    if book.get("author"):
        eb.add_author(book["author"])

    if book.get("cover"):
        data = get_bytes(book["cover"], ref)
        jpeg = to_jpeg(data) if data else None
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
            data = get_bytes(url, ref)
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


def resolve(target: str, only: str | None) -> tuple[object, str] | list[dict]:
    """链接/书号 → (书源, id)；书名 → 搜索结果列表。"""
    pool = [BY_NAME[only]] if only else SOURCES
    for src in pool:
        bid = src.match(target)
        if bid:
            return src, bid
    if target.isdigit() and (not only or only == lnovel.NAME):
        return lnovel, target
    if re.match(r"https?://", target):
        raise SystemExit(f"不认识这个链接：{target}（支持：{', '.join(s.NAME for s in SOURCES)}）")
    hits = []
    for src in pool:
        try:
            found = src.search(target)
        except Exception as exc:  # noqa: BLE001
            log(f"warn: {src.NAME} 搜索失败：{exc}")
            continue
        log(f"{src.NAME}: {len(found)} 条")
        hits += found
    norm = _normalizer()
    kw = norm(target)
    order = {s.NAME: i for i, s in enumerate(pool)}

    def rank(h):
        t = norm(h["title"])
        return (0 if t == kw else 1 if t.startswith(kw) else 2, len(t), order[h["source"]])
    return sorted(hits, key=rank)


def _normalizer():
    """比较书名用：去空白和书名号；装了 opencc 就统一成简体（「活著」==「活着」）。"""
    try:
        import opencc
        cc = opencc.OpenCC("t2s").convert
    except ImportError:
        cc = lambda s: s  # noqa: E731
    return lambda s: cc(re.sub(r"[\s《》]", "", s))


def main() -> None:
    ap = argparse.ArgumentParser(description="抓在线小说并打包 EPUB（书源：" + " / ".join(s.NAME for s in SOURCES) + "）")
    ap.add_argument("target", nargs="?", help="书名、书页链接，或 lnovel.tw 书号")
    ap.add_argument("--source", choices=list(BY_NAME), help="只用某个书源")
    ap.add_argument("--list", action="store_true", help="只列出搜索结果，不下载")
    ap.add_argument("--pick", type=int, default=1, help="书名搜索时取第几条结果（默认 1）")
    ap.add_argument("--volume", type=int, help="多卷书选第几卷；0 = 全部合成一本")
    ap.add_argument("--reindex", action="store_true", help="重建努努书坊的本地书名索引")
    ap.add_argument("--out", default=os.environ.get("NOVEL_DIR", "./books"), help="落库根目录（默认 ./books）")
    ap.add_argument("--simplified", action="store_true", help="繁体转简体（需要 opencc）")
    ap.add_argument("--no-images", action="store_true", help="跳过插图")
    ap.add_argument("--json", action="store_true", help="只输出结果 JSON")
    a = ap.parse_args()

    if a.reindex:
        kanunu.build_index()
        if not a.target:
            return
    if not a.target:
        ap.error("缺少书名或链接")

    r = resolve(a.target.strip(), a.source)
    if isinstance(r, list):
        if a.list or not r:
            for i, h in enumerate(r, 1):
                print(f"{i}. [{h['source']}] {h['title']}" + (f" — {h['author']}" if h.get("author") else "") + f"  ({h['id']})")
            if not r:
                raise SystemExit(f"各书源都没搜到「{a.target}」。努努书坊的书可以直接给书页链接。")
            return
        if not 1 <= a.pick <= len(r):
            raise SystemExit(f"--pick 超出范围：共 {len(r)} 条")
        h = r[a.pick - 1]
        log(f"选中：[{h['source']}] {h['title']}" + (f"（共 {len(r)} 条，--list 看全部）" if len(r) > 1 else ""))
        src, bid = BY_NAME[h["source"]], h["id"]
    else:
        src, bid = r

    book = src.crawl(bid, with_images=not a.no_images, volume=a.volume)
    if not book["chapters"]:
        raise SystemExit("一章正文都没拿到，不生成空书")
    if a.simplified:
        book = to_simplified(book)
    path = build(book, a.out)
    result = {
        "source": book["source"],
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
        log(f"完成：{result['title']}（{result['source']} · {result['chapters']} 节 / {result['chars']} 字 / "
            f"{result['images']} 图 / {result['size'] // 1024}K）")
        print(os.path.abspath(path))


if __name__ == "__main__":
    main()
