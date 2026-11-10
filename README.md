# lnovel2epub

把在线小说站上的书抓下来，打包成 EPUB3。

一条命令一本书：给书名能搜，给链接能直接抓，出来的 `.epub` 带目录、封面和插图，放进任何阅读器或书库都能读。

```bash
python3 lnovel2epub.py 活着
# → ./books/活着/活着.epub
```

## 它能做什么

- **按书名找书**：依次在各书源里搜。书名完全一致的排最前；`--list` 看全部结果，`--pick N` 换一条
- **给链接直接抓**：认得的书页链接不用搜
- **多卷书**：`--volume N` 一卷一本，`--volume 0` 合成一本。卷数超过一本又没指定时，会先把各卷列出来让你选
- **插图**：正文里只有图、没有字的「插图」节会单独下载并内嵌
- **图片格式**：WebP 等统一转成 JPEG —— 只改扩展名的 WebP，老阅读器照样打不开
- **重试**：每章请求重试三次，偶尔半包不会让整本少一节
- **理性失败**：一章正文都没拿到就直接报错，不会给你一本空书；正文 404 的那一节跳过并告警，不悄悄少一节
- 可选：整本繁转简、跳过插图、只输出 JSON

一本书打包成标准 EPUB3：有目录（nav + NCX）、一章一节，作者和封面写进元数据，插图按节内嵌。

## 书源

| `--source` | 内容 | 语言 | 找书方式 |
|-|-|-|-|
| `8novel` | 日本轻小说，分卷较全，有插图 | 繁体 | 站内搜索 |
| `lnovel` | 日本轻小说 | 繁体 | 只认书号 / 链接 |
| `kanunu` | 出版读物：国内外文学、推理、科幻、武侠等 | 简体 | 本地索引（见下） |

文件名和输出都**只显示书名**，不点名站点。三个书源都在 `sources/` 下，一个文件一个站，接口只有三个函数：

```python
NAME                        # 书源名，--source 用
match(target)  -> id | None # 认不认这个链接 / 书号
search(keyword)-> [ {...} ] # 按书名搜
crawl(id, with_images, volume) -> book dict
```

站点改版会让对应书源失效，报错会说明是哪一项认不出；其它书源不受影响。加一个新站 = 加一个文件 + 在 `sources/__init__.py` 注册。

### 本地索引（kanunu）

这个站没有站内搜索，所以第一次按书名找书时会先建一份书名索引：扫分类页、专题页和作家总目，
去重后约 1 万本，耗时十分钟左右。索引存在 `$NOVEL_CACHE`（默认 `~/.cache/lnovel2epub`），7 天内复用，
`--reindex` 手动重建。

少数书只在作家页里出现（比如《活着》），索引同样收得进来。确实搜不到时，直接把书页链接丢给它就行。

## 安装

```bash
pip install -r requirements.txt          # ebooklib + pillow
pip install opencc-python-reimplemented  # 可选，见下
```

Python 3.10+。需要代理时设 `HTTPS_PROXY` / `HTTP_PROXY`。

装了 opencc 有两个用处：`--simplified` 能整本繁转简；按书名搜索时繁简通配（搜「活着」能找到《活著》）。
**没装 opencc 时 `--simplified` 会直接报错退出**，而不是默默给你一本「看起来是简体、其实是繁体」的书。

## 用法

```bash
# 按书名
python3 lnovel2epub.py 活着
python3 lnovel2epub.py 十宗罪 --list          # 只看搜索结果，不下载
python3 lnovel2epub.py 十宗罪 --pick 2        # 取第 2 条
python3 lnovel2epub.py 活着 --source kanunu   # 只在某个书源里找

# 按链接 / 书号
python3 lnovel2epub.py <书页链接>
python3 lnovel2epub.py 3217                   # 纯数字 = lnovel 书号

# 多卷书
python3 lnovel2epub.py <多卷书链接>            # 不带 --volume 时先列出所有卷
python3 lnovel2epub.py <多卷书链接> --volume 2
python3 lnovel2epub.py <多卷书链接> --volume 0 # 全部合成一本

# 其它
python3 lnovel2epub.py 活着 --out ~/novels     # 落库目录（默认 ./books，或 $NOVEL_DIR）
python3 lnovel2epub.py <繁体书> --simplified   # 书名、作者、章节名、正文一起转简体
python3 lnovel2epub.py 活着 --no-images
python3 lnovel2epub.py 活着 --json             # 脚本调用：只输出结果 JSON
python3 lnovel2epub.py --reindex               # 重建本地索引
```

`--json` 的输出：

```json
{"source": "kanunu", "title": "活着", "author": "余华", "chapters": 11,
 "chars": 91600, "images": 0, "path": "/abs/books/活着/活着.epub", "size": 123456}
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
- 正文地址藏在混淆脚本里的站，站点改写法后对应书源要跟着改
- 索引只对 `kanunu` 生效；另外两个书源是实时搜，不用建索引

## 免责声明

本工具只做格式转换，**不存储、不托管任何书籍内容**；抓取的内容版权归原作者与出版方所有。
请仅用于个人学习与离线阅读，支持正版。因使用本工具产生的任何后果由使用者自行承担。

## License

MIT
