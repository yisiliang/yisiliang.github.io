# 站点维护指南

GitHub Pages 从 `master:/docs` 发布。站点是静态 HTML，没有运行时后端；构建脚本只在本地维护时使用。

## 目录

|路径|用途|
|---|---|
|`docs/index.html`|首页，由 `tools/homepage/catalog.json` 生成|
|`docs/topics/`|技术专题：`build.py`、`topics.json`、`chapters/`、`assets/`、`vendor/`|
|`docs/topics/<slug>/index.html`|每篇专题的独立页面，构建产物|
|`docs/topics/<slug>/article.md`|同篇 Markdown 正文，作为下载入口|
|`docs/<book>/index.html`|11 本手册的阅读页|
|`tools/reader/`|共享阅读器：`theme.css`、`style.css`、`controls.js`、`theme.js`|
|`tools/build_homepage.py`|生成首页与 `assets/homepage/`|
|`tools/build_metadata.py`|注入 description/canonical/OG，生成 sitemap、robots、favicon、分享图|
|`tools/check_site.py`|发布前全站检查|
|`tools/audit_articles.py`|逐本手册检查本地链接、锚点、重复 ID|
|`tools/validate_source_library.py`|四本源码手册的结构检查|

## 技术专题

每篇专题是一份 Markdown 加一条 `topics.json` 记录，不再合并进总页。

```sh
# 维护环境（只需一次）
python3.12 -m venv /tmp/topics-env
/tmp/topics-env/bin/pip install markdown beautifulsoup4 playwright

# 新增或修改专题后
/tmp/topics-env/bin/python docs/topics/build.py
/tmp/topics-env/bin/python docs/topics/render-diagrams.py
python3 tools/build_homepage.py
python3 tools/build_metadata.py
```

`build.py` 读取 `chapters/*.md`，按 `topics.json` 的 `n`、`slug`、`title`、`summary`、`source`、`quick` 生成 14 个独立页面、`/topics/` 目录页和旧地址跳转页。新增一篇时：

1. 在 `docs/topics/chapters/` 放一份以 `# 标题` 开头的 Markdown；
2. 在 `docs/topics/topics.json` 追加一条记录，`quick` 写 3–5 条要点；
3. 运行上面的四条命令。

`anchors.json` 保存每篇 `cN-sM` 标题锚点，改名时保留旧值可以避免旧链接失效。目录页的旧地址 `/java-architect-interview/` 会把 `#c1`–`#c14` 映射到 `/topics/<slug>/`。

`render-diagrams.py` 用本地 Chrome 把 Mermaid 预渲染成 SVG，读者端不加载 Mermaid。可通过 `CHROMIUM_EXECUTABLE` 指定浏览器路径。渲染结果记录在 `diagram-validation.json`。

## 阅读器改造

11 本手册与 14 篇专题共用一套内嵌的 `theme.css + style.css + controls.js + theme.js`。目录只有左侧一栏：章节树、当前篇内目录与阅读进度合并显示；右侧目录已移除，正文区域加宽。

改动共享样式或脚本后：

```sh
python3 tools/style_readers.py     # 刷新 11 本手册，保留源码与锚点
/tmp/topics-env/bin/python docs/topics/build.py
/tmp/topics-env/bin/python docs/topics/render-diagrams.py
python3 tools/build_homepage.py
python3 tools/build_metadata.py
```

`style_readers.py` 会移除旧的右侧目录、空 ZIP 下载项和重复分隔符，再内嵌最新资源。手册自己的 `build.py` 仍负责各自正文，顺序是“手册生成器 → style_readers → 首页 → metadata”。

## 元数据

`tools/build_metadata.py` 覆盖首页、11 本手册、专题目录和 14 篇专题，共 27 个公开内容页：

- `description`、`canonical`、Open Graph、Twitter Card；
- `/favicon.svg`、`/favicon-32.png`、`/apple-touch-icon.png`；
- `/assets/og-default.png` 默认分享图；
- `sitemap.xml`、`robots.txt`；
- `404.html`。

分享图与 PNG favicon 需要 Pillow；缺少 Pillow 时脚本仍会注入元数据，只跳过图片生成。元数据块以 `<!-- social-meta:start -->` 标记，重复运行会替换而不是叠加。

## 检查

```sh
python3 tools/check_site.py             # 链接、锚点、重复 ID、单侧栏、元数据、sitemap
python3 tools/audit_articles.py         # 逐本手册的本地链接与锚点
python3 tools/validate_source_library.py
python3 docs/nginx/verify.py
python3 docs/nacos/verify.py
python3 docs/mysql/verify.py
python3 docs/langgraph/verify.py
python3 docs/transformer/verify.py
python3 tools/check_browser.py
```

`check_site.py` 是发布前的总检查，失败会返回非零退出码。浏览器回归用 `python3 tools/check_browser.py`：脚本自动启动静态服务器，覆盖 27 个地址 × 4 个视口，检查单侧栏、横向溢出、脚本错误、搜索、复制、主题、要点速览、手机抽屉与禁用 JavaScript，需要 Playwright 和本地 Chrome。

## 已退役

- 所有 ZIP 离线包、源码包和证据包已删除，页面不再提供 ZIP 下载，只保留 Markdown 与验证记录；
- `/java-architect-interview/` 的总文章已拆分为 `/topics/<slug>/`，旧地址保留跳转；
- `docs/nginx-rate-limiting/`、`docs/jvm-memory-oom/`、`docs/fastjson2-arm-jit/` 的正文、图片与实验文件已迁入 `docs/topics/`，旧目录只保留跳转页；
- `tools/build_distributed_offline.py`、`docs/transformer/build_offline.py`、`docs/springboot/package.py` 等只用于打包 ZIP 的脚本已删除；
- 依赖源码 ZIP 的 `repair_source_excerpts.py` 及其回归测试已删除。

手写源码窗口、许可证与验证记录仍在 `docs/topics/sources.json`、`source-notes.json`、`source-notices.txt` 与 `licenses/`。固定源码的逐字核验仍以各手册的 `VERIFICATION.md` 为准。
