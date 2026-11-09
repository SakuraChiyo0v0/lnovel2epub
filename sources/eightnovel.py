"""8novel（無限輕小說）：繁体日轻，收录多、分卷齐。

正文不在 HTML 里：阅读页有一段混淆过的脚本，用 `$.get(unescape(<表达式>))` 拉 `/txt/1/<书号>/<章号><5 位>.html`。
变量名每次刷新都会变，所以这里**不认名字、按结构求值**：先收集脚本里的 `var x=...;` 定义，
再把表达式按顶层 `+` 拆开逐项求值。只认三种项：字符串字面量、变量、`A[A.length-B].substr(C * D % E, F)`。
"""
from __future__ import annotations

import re
import urllib.parse

from .common import clean, get, log, paragraphs

NAME = "8novel"
BASE = "https://www.8novel.com"
IMG_BASE = "https://img9.8novel.com"
URL_RE = re.compile(r"8novel\.com/(?:novelbooks|read)/(\d+)")


def match(target: str) -> str | None:
    m = URL_RE.search(target)
    return m.group(1) if m else None


def search(keyword: str) -> list[dict]:
    page = get(f"{BASE}/search/?key={urllib.parse.quote(keyword)}", BASE + "/")
    out, seen = [], set()
    for bid, title in re.findall(r"href='/novelbooks/(\d+)'\s+title='([^']+)'", page):
        if bid not in seen:
            seen.add(bid)
            out.append({"source": NAME, "id": bid, "title": title})
    return out


# ---------- 混淆脚本求值 ----------

def _split_top(expr: str) -> list[str]:
    out, depth, quote, cur = [], 0, None, ""
    for ch in expr:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "+" and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return out


def _vars(script: str) -> dict:
    env: dict = {}
    for name, val in re.findall(r"var (\w+)=(.*?);(?=var |if\(|\$\.|for\(|u=|\w+=|$)", script):
        v = val.strip()
        m = re.fullmatch(r'"([^"]*)"\.split\(\'(.)\'\)', v)
        if m:
            env[name] = m.group(1).split(m.group(2))
        elif re.fullmatch(r"-?\d+", v):
            env[name] = int(v)
        elif re.fullmatch(r"'[^']*'|\"[^\"]*\"", v):
            env[name] = v[1:-1]
    return env


def _term(t: str, env: dict) -> str:
    if t.startswith("(typeof("):  # (typeof(td)!='undefined'?td:'') —— 站点前缀，恒为空
        return ""
    if t[:1] in "'\"":
        return t[1:-1]
    if re.fullmatch(r"-?\d+", t):
        return t
    m = re.fullmatch(r"(\w+)\[(\w+)\.length-(\w+)\]\.substr\((\w+) \* (\w+) % (\w+), (\w+)\)", t)
    if m:
        arr, _, one, a, b, c, d = m.groups()
        val = lambda x: int(env[x]) if x in env else int(x)  # noqa: E731
        s = env[arr][len(env[arr]) - val(one)]
        start = val(a) * val(b) % val(c)
        return s[start:start + val(d)]
    if t in env:
        return str(env[t])
    raise RuntimeError(f"8novel 正文地址公式里有认不出的项：{t}（站点可能改了混淆写法）")


class _Reader:
    def __init__(self, script: str):
        self.script = script
        self.env = _vars(script)
        self.cid_var = re.search(r"var (\w+)=u\.indexOf\('\?'\)>0\?u\.split", script).group(1)
        self.expr = re.search(r"\$\.get\(unescape\((.*?)\),function", script, re.S).group(1)
        lists = [v for v in self.env.values() if isinstance(v, list)]
        ids = next(v for v in lists if v and all(x.isdigit() for x in v))
        self.ids = ids[:-1]  # 最后一项是取校验码用的长串
        self.names = next((v for v in lists if len(v) == len(self.ids) and not all(x.isdigit() for x in v)),
                          [f"第{i + 1}节" for i in range(len(self.ids))])

    def url(self, cid: str) -> str:
        env = dict(self.env, **{self.cid_var: cid})
        return BASE + urllib.parse.unquote("".join(_term(t, env) for t in _split_top(self.expr)))


def _reader(bid: str, first: str) -> _Reader:
    page = get(f"{BASE}/read/{bid}/?{first}", f"{BASE}/novelbooks/{bid}/")
    script = next((s for s in re.findall(r"<script[^>]*>(.*?)</script>", page, re.S) if "$.get(unescape(" in s), None)
    if not script:
        raise RuntimeError("8novel 阅读页里没找到正文加载脚本（站点可能改版）")
    return _Reader(script)


# ---------- 水印 ----------
# 正文里每隔几十段插一整段「⑧ΝОνЕ┕。Сοм」：数字 8 + novel + 点 + com，每个字母随机换成
# 全角 / 希腊 / 西里尔的同形字。先折叠成 ASCII 再整段匹配，只删整段，不碰正文里的英文。
_FOLD = str.maketrans({
    "⑧": "8", "⑻": "8", "８": "8",
    "Ν": "N", "Н": "N", "ｎ": "n", "Ｎ": "N",
    "Ο": "O", "О": "O", "ο": "o", "о": "o", "σ": "o", "Ｏ": "O", "ｏ": "o",
    "ν": "v", "ｖ": "v", "Ｖ": "V",
    "Ε": "E", "Е": "E", "Ё": "E", "ヨ": "E", "Ｅ": "E", "ｅ": "e",
    "┕": "L", "┗": "L", "└": "L", "ｌ": "l", "Ｌ": "L",
    "。": ".", "．": ".", "·": ".",
    "С": "C", "с": "c", "Ｃ": "C", "ｃ": "c",
    "м": "m", "М": "M", "ｍ": "m", "Ｍ": "M",
})
_WATERMARK = re.compile(r"8\s*n\s*o\s*v\s*e?\s*l?\s*\.\s*c\s*o\s*m", re.I)  # 字母偶尔会漏一个


def _strip_watermark(text: str) -> str:
    keep = [p for p in text.split("\n\n") if not (len(p) <= 20 and _WATERMARK.fullmatch(p.translate(_FOLD).strip()))]
    return "\n\n".join(keep)


# ---------- 抓取 ----------

def crawl(book_id: str, with_images: bool = True, volume: int | None = None) -> dict:
    book_url = f"{BASE}/novelbooks/{book_id}/"
    page = get(book_url, BASE + "/")
    meta = lambda k: (re.search(rf'<meta property="og:{k}" content="([^"]*)"', page) or [None, ""])[1]  # noqa: E731
    title = clean(meta("novel:book_name") or meta("title"))
    author = clean(meta("novel:author"))
    cover = meta("image")

    # 书页按卷分组：<div class="row m-0 folder" ...><h3 class="px-2">第一卷</font>...<ul>...章节...</ul>
    vols = []
    for vname, block in re.findall(r'<h3 class="px-2">(.*?)</font>.*?<ul[^>]*>(.*?)</ul>', page, re.S):
        eps = re.findall(rf"href='/read/{book_id}/\?(\d+)'>(.*?)</a>", block)
        vols.append((clean(vname), [(cid, clean(n)) for cid, n in eps]))
    if not vols:
        raise RuntimeError("8novel 书页上没找到目录")

    if len(vols) > 1 and volume is None:
        listing = "；".join(f"{i}. {v[0]}（{len(v[1])} 节）" for i, v in enumerate(vols, 1))
        raise SystemExit(f"《{title}》共 {len(vols)} 卷，请用 --volume N 选一卷（或 --volume 0 合成一本）：{listing}")
    if volume:
        if not 1 <= volume <= len(vols):
            raise SystemExit(f"--volume 超出范围：共 {len(vols)} 卷")
        picked = [vols[volume - 1]]
    else:
        picked = vols

    first = picked[0][1][0][0]
    rd = _reader(book_id, first)
    full_names = dict(zip(rd.ids, rd.names))

    chapters = []
    eps = [(cid, n, vname) for vname, items in picked for cid, n in items]
    for i, (cid, name, vname) in enumerate(eps, 1):
        raw = get(rd.url(cid), f"{BASE}/read/{book_id}/?{cid}")
        if "<title>404." in raw:
            log(f"warn: 第 {i} 节 {name} 正文 404，跳过")
            continue
        images = []
        if with_images:
            images = [s if s.startswith("http") else IMG_BASE + s
                      for s in re.findall(r'<img[^>]+src="([^"]+)"', raw)]
        text = _strip_watermark(paragraphs(raw))
        # 多卷合本时章节名带卷名，避免「第一章」重名
        full = full_names.get(cid) or f"{vname} {name}"
        if volume or len(vols) == 1:
            label = name
            # 有的书 book 页的章节名本身就带「第N卷 副标题」，去掉
            m = re.match(rf"{re.escape(vname)}\s+\S+\s+(.+)", full)
            if m and name == full:
                label = m.group(1)
        else:
            label = full
        chapters.append({"title": label, "text": text, "images": images})
        log(f"[{i}/{len(eps)}] {label} {len(text)} 字{' · ' + str(len(images)) + ' 图' if images else ''}")

    if volume:
        vname = picked[0][0]
        # 卷名取自全名里「第N卷 <副标题>」那段，没有就用「第N卷」
        sub = re.match(rf"{re.escape(vname)}\s+(\S+)", full_names.get(first, ""))
        title = f"{title} {vname}" + (f" {sub.group(1)}" if sub and sub.group(1) not in title else "")
    return {"source": NAME, "bookId": book_id + (f"-v{volume}" if volume else ""), "title": title,
            "author": author, "cover": cover, "referer": book_url, "chapters": chapters}
