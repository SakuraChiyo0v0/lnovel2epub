"""书源注册表。每个书源模块提供：

    NAME                       书源名（--source 用）
    match(target) -> id|None   认不认这个链接
    search(keyword) -> [ {source, id, title, author?} ]
    crawl(id, with_images, volume) -> book dict

按书名找书时按 SOURCES 的顺序依次搜索。
"""
from . import eightnovel, kanunu, lnovel

SOURCES = [eightnovel, lnovel, kanunu]
BY_NAME = {s.NAME: s for s in SOURCES}
