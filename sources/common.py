"""各书源共用的网络与文本工具。"""
from __future__ import annotations

import html as htmllib
import os
import re
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _opener() -> urllib.request.OpenerDirector:
    # 遵循 HTTPS_PROXY / HTTP_PROXY 环境变量（urllib 默认行为）
    return urllib.request.build_opener()


def fetch(url: str, referer: str | None = None, retries: int = 3, timeout: int = 30) -> bytes:
    """GET，失败重试（单章偶发半包会让整本少一节）。"""
    last: Exception | None = None
    op = _opener()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer or url})
            with op.open(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            last = exc
        except Exception as exc:  # noqa: BLE001
            last = exc
        if attempt < retries - 1:
            time.sleep(2 + attempt * 2)
    raise RuntimeError(f"请求失败 {url}: {last}")


def get(url: str, referer: str | None = None, encoding: str = "utf-8") -> str:
    return fetch(url, referer).decode(encoding, "ignore")


def get_bytes(url: str, referer: str | None = None) -> bytes | None:
    try:
        return fetch(url, referer, retries=2)
    except Exception:  # noqa: BLE001
        return None


def clean(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment)
    text = re.sub(r"<[^>]+>", "", text)
    text = htmllib.unescape(text).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def paragraphs(fragment: str) -> str:
    """<br> / <p> 分段的 HTML → 以空行分隔的段落文本。"""
    parts = re.split(r"(?:<br\s*/?>\s*){1,}|</p>\s*<p[^>]*>", fragment)
    out = [clean(p).strip("　 ") for p in parts]
    return "\n\n".join(p for p in out if p)


def cache_dir() -> str:
    d = os.environ.get("NOVEL_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "lnovel2epub")
    os.makedirs(d, exist_ok=True)
    return d
