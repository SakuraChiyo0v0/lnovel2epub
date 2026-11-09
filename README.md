# lnovel2epub

把在线小说站上的书抓下来，打包成 EPUB3。

给「我自己有阅读器 / NAS 书库」的人用：一条命令一本书，按书名就能找，带封面和插图。

```bash
python3 lnovel2epub.py 活着
# → ./books/活着/活着.epub
```

## 它能做什么

- **按书名找书**：依次在各书源里搜，书名完全一致的排最前；`--list` 看全部结果，`--pick N` 换一条
- **给链接直接抓**：认得的书页链接不用搜
- **多卷书分卷出**：`--volume N` 一卷一本，`--volume 0` 合成一本
- **插图**：正文里只有图没有字的「插图」节会单独下载并内嵌
- **图片格式**：WebP 等统一转码成 JPEG（老阅读器认不出改了扩展名的 WebP）
- **重试**：每章请求重试三次，避免偶发半包让整本少一节
- 可选繁转简、跳过插图、只输出 JSON

## 书源

| `--source` | 内容 | 语言 | 找书方式 |
|-|-|-|-|
| `8novel` | 日本轻小说，分卷较全 | 繁体 | 站内搜索 |
| `lnovel` | 日本轻小说 | 繁体 | 只认书号 / 链接 |
| `kanunu` | 出版读物：国内外文学、推理、科幻、武侠等 | 简体 | 本地索引（见下） |

书源实现都在 `sources/` 下，一个文件一个站，接口是 `match / search / crawl` 三个函数。
站点改版会让对应书源失效，其它书源不受影响。

### 本地索引

`kanunu` 站内没有搜索，第一次按书名找书时会先建一份书名索引（约 1 万本，抓 1,800 多个目录页，十分钟左右），
存在 `$NOVEL_CACHE`（默认 `~/.cache/lnovel2epub`），7 天内复用。`--reindex` 手动重建。
有少数书不在任何目录页里，索引搜不到时直接给书页链接即可。

## 安装

```bash
pip install -r requirements.txt          # ebooklib + pillow
pip install opencc-python-reimplemented  # 可选：繁转简；装了之后按书名搜索也会繁简通配
```

Python 3.10+。需要代理时设 `HTTPS_PROXY` / `HTTP_PROXY`。

## 用法

```bash
# 按书名
python3 lnovel2epub.py 活着
python3 lnovel2epub.py 十宗罪 --list          # 只看搜索结果
python3 lnovel2epub.py 十宗罪 --pick 2        # 取第 2 条
python3 lnovel2epub.py 活着 --source kanunu   # 只在某个书源里找

# 按链接 / 书号
python3 lnovel2epub.py <书页链接>
python3 lnovel2epub.py 3217                   # 纯数字 = lnovel 书号

# 多卷书
python3 lnovel2epub.py <多卷书链接>            # 会列出所有卷，提示用 --volume
python3 lnovel2epub.py <多卷书链接> --volume 2
python3 lnovel2epub.py <多卷书链接> --volume 0 # 全部合成一本

# 其它
python3 lnovel2epub.py 活着 --out ~/novels     # 落库目录（默认 ./books，或 $NOVEL_DIR）
python3 lnovel2epub.py <繁体书> --simplified   # 书名、作者、章节名、正文一起转简体
python3 lnovel2epub.py 活着 --no-images
python3 lnovel2epub.py 活着 --json             # 脚本调用：只输出结果 JSON
python3 lnovel2epub.py --reindex               # 重建本地索引
```

输出结构：

```
books/
└── 活着/
    └── 活着.epub
```

## 已知限制

- 插图有没有取决于站上收录；简体出版读物一般没有插图和封面
- 繁体书源出的是繁体原文，要简体用 `--simplified`
- 某些站的正文地址藏在混淆过的脚本里，站点改写法后对应书源要跟着改；报错会说明是哪一项认不出

## 免责声明

本工具只做格式转换，**不存储、不托管任何书籍内容**；抓取的内容版权归原作者与出版方所有。
请仅用于个人学习与离线阅读，支持正版。因使用本工具产生的任何后果由使用者自行承担。

## License

MIT
