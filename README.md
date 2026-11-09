# lnovel2epub

把 [lnovel.tw（輕小說百科）](https://lnovel.tw) 上的轻小说正文抓下来，打包成 EPUB3。

给「我自己有阅读器 / NAS 书库」的人用：一条命令一本书，带封面和插图。

```bash
python3 lnovel2epub.py 3217
# → ./books/我永遠不會忘記，燦爛一瞬間的你/我永遠不會忘記，燦爛一瞬間的你.epub
```

## 它能做什么

- 输入书号或书籍页链接，输出一本完整的 EPUB3
- 正文按站上的目录分节，段落按空行还原
- **封面**：优先 `og:image`，没有就按 `alt == 书名` 找图；缩略图会换成同图的大尺寸
- **插图**：轻小说的「插畫」是独立一节、正文里只有 `<img>` 没有 `<p>`，会单独下载并内嵌
- **图片格式**：站上常是 WebP 但扩展名写 `.jpg`，老阅读器会当坏图，这里统一转码成 JPEG
- **重试**：单章偶发半包会让整本少一节，每章请求重试三次
- 可选繁转简、跳过插图、只输出 JSON（见下）

## 安装

```bash
pip install -r requirements.txt          # ebooklib + pillow
pip install opencc-python-reimplemented  # 可选：繁转简
```

Python 3.10+。

## 用法

```bash
# 书号或链接都行
python3 lnovel2epub.py 3217
python3 lnovel2epub.py https://lnovel.tw/books-3217

# 指定落库目录（默认 ./books）
python3 lnovel2epub.py 3217 --out ~/novels

# 繁体转简体（书名、作者、章节名、正文一起转；没装 opencc 会直接报错）
python3 lnovel2epub.py 3217 --simplified

# 只要文字，不要插图
python3 lnovel2epub.py 3217 --no-images

# 脚本调用：只输出结果 JSON
python3 lnovel2epub.py 3217 --json
```

输出结构：

```
books/
└── 我永遠不會忘記，燦爛一瞬間的你/
    ├── 我永遠不會忘記，燦爛一瞬間的你.epub
    └── lnovel_3217.json          # 原始抓取结果，方便二次处理
```

## 它会处理什么

- **分节**：按站上的目录结构切，`<article>` 里的 `<p>` 按空行还原成段落
- **插图**：轻小说的「插畫」是独立一节、正文里只有 `<img>` 没有 `<p>`；这里会单独下载并内嵌
- **封面**：优先 `og:image`，没有就按 `alt == 书名` 找图；站上缩略图 `xxx.jpg.small.webp` 会换成同图的大尺寸 `xxx.jpg`
- **WebP → JPEG**：站上图片常是 WebP 但扩展名写 `.jpg`，老阅读器会当坏图，这里统一转码
- **重试**：单章偶发半包会让整本少一节（实测 17 节变 16），每章请求重试三次

## 已知限制

- 只有 **繁体中文**（台版录入）；简体靠 `--simplified` 本地转换
- 插图有没有取决于站上收录：实测同作者四本里两本 0 图
- 封面最大 270×360（站上给的上限）
- 站点改版会让解析失效——`<article class="card mb-4">` 这个选择器是当前的唯一依赖点

## 免责声明

本工具只做格式转换，**不存储、不托管任何书籍内容**；抓取的内容版权归原作者与出版方所有。
请仅用于个人学习与离线阅读，支持正版。因使用本工具产生的任何后果由使用者自行承担。

## License

MIT
