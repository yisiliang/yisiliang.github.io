# 构建与验收范围

## 2026-10-27 技术专题拆分、单侧栏与站点元数据

技术专题从一篇合并长文拆成 14 篇独立文章，统一放在 `/topics/<slug>/`，目录页是 `/topics/`。每篇有自己的正文、目录、搜索、要点速览和图解；新增专题只需增加一份 Markdown 和一条 `topics.json` 记录，不再合并进总页。旧地址 `/java-architect-interview/`、`/fastjson2-arm-jit/`、`/nginx-rate-limiting/`、`/jvm-memory-oom/` 保留为跳转页，旧的 `#c1`–`#c14` 锚点映射到对应新文章。

阅读器改为单侧栏：左侧合并章节树、当前篇内目录和阅读进度，右侧目录已移除，正文区域加宽。11 本手册与 14 篇专题共用同一套内嵌的 `theme.css`、`style.css`、`controls.js`、`theme.js`。

ZIP 下载全部退役：离线包、源码包与证据包已从仓库和页面移除，每篇只保留 Markdown 正文下载与验证记录。旧目录中的专题正文、图片、实验文件与源码窗口已迁入 `docs/topics/chapters/`、`docs/topics/assets/` 与 `docs/topics/sources.json`。

公开内容页统一补齐 `description`、`canonical`、Open Graph、Twitter Card、favicon，并生成 `sitemap.xml`、`robots.txt`、默认分享图和 `404.html`。首页、11 本手册、专题目录和 14 篇专题共 27 个页面纳入检查。

内容规模：14 篇专题、66 道三层问答、117 个代码块、48 张图解（21 张 Mermaid 预渲染 SVG + 27 张随文 SVG）。

构建顺序：

```sh
/tmp/topics-env/bin/python docs/topics/build.py
/tmp/topics-env/bin/python docs/topics/render-diagrams.py
python3 tools/style_readers.py
python3 tools/build_homepage.py
python3 tools/build_metadata.py
python3 tools/check_site.py
```

本轮验收：

- `tools/check_site.py`：47 个 HTML 页面、27 个公开内容页；0 个失效链接、0 个失效锚点、0 个重复 ID、0 个 ZIP 入口、0 个元数据缺口、0 个右侧栏残留、sitemap 目标全部存在。
- `tools/audit_articles.py` 与 `tools/validate_source_library.py` 通过。
- `docs/nginx/verify.py`、`docs/nacos/verify.py`、`docs/mysql/verify.py`、`docs/langgraph/verify.py`、`docs/transformer/verify.py` 通过。
- Playwright 浏览器回归覆盖 27 个地址 × 4 个宽度（1440/820/390/320），共 108 次加载：无右侧栏、无横向溢出、无 ZIP 入口、无脚本错误，左栏目录初始化正常；搜索、要点速览、主题与图解放大沿用原实现。
- 21 张 Mermaid 图在构建时预渲染，读者端不加载 Mermaid；源码窗口与固定提交的逐字核对仍以各手册的 `VERIFICATION.md` 为准。

本轮未执行：Nacos 服务集群、RocketMQ 故障注入、MySQL 主从切换等真实服务端实验；相关章节仍区分“已执行”与“仅步骤/预期”。

## 历史记录（拆分前）

本目录的排版作为全站技术学习文章的共同基准。2026年10月9日统一学习用语与阅读器，共享源文件位于tools/reader；运行tools/style_readers.py后页面内嵌资源，原有章节与知识点锚点不变。首页第七类“技术专题”直接提供十一章链接，栏目名称不固定数量；不更新sitemap/RSS。仓库GitHub Pages从master:/docs构建（legacy Jekyll），本目录不使用Front Matter，index.html是直接复制的静态HTML。页面显式载入现有Umami网站记录脚本；没有访问权限控制。

十一个专题、66道三层问答、21张Mermaid图、源码连续节选和模拟故障。官方源码下载记录见sources.json，补充联网记录见research-checks.json。所有事故均为教学模拟，原有十章未实际运行Java、数据库、Redis、RocketMQ故障实验；JIT专题只展示源码机制与教学片段，不声称有真实生产测量。

读者不需要 npm、Python、Node.js 或后端。源码高亮使用本地 Prism；Mermaid 在构建时渲染成 SVG，正文和图表禁用 JavaScript 仍可阅读。运行时只有 Umami 使用外部请求，阻断它不影响核心功能。许可证在 licenses/ 与 vendor/，源码声明在 source-notices.txt。

维护时安装markdown、beautifulsoup4、playwright（仅维护环境）；运行build.py后，从仓库docs目录启动8000端口静态服务器，再运行render-diagrams.py，最后对本目录调用tools/style_readers.py中的transform应用共享阅读器，再运行verify.py。浏览器优先使用CHROMIUM_EXECUTABLE指定路径，否则检测Linux Chromium或macOS Google Chrome，再使用Playwright默认浏览器。部署产物不调用这些脚本。验证截图保存在output/playwright，验证结果见validation-results.json与diagram-validation.json。

发布仅需提交本目录，沿用已有 GitHub Pages 设置。公开地址为 https://yisiliang.github.io/java-architect-interview/。

2026-10-08 阅读改写：重写十章讲解与 60 道回答，口述部分直接给出完整回答；案例分段说明现象、检查与验证。source-notes.json 保存每段源码的阅读说明，anchors.json 保留 200 个原有知识点锚点。问题标题直接作为折叠按钮。样式和脚本资源按内容摘要附版本参数，避免正文更新后浏览器仍使用旧资源。

2026-10-09 RocketMQ存储协作补充：在原专题c7内增加完整存储协作章节（c7-s22），沿CommitLog追加、Reput派发、CQ去重、队列读取、哈希索引、Half内部队列和崩溃恢复说明状态变化与失败边界。新增15段RocketMQ4.9.8官方连续源码节选、2张构建时预渲染流程图，并核对5.3.4的并发Reput与RocksDB CQ实现。storage-source-verification.json记录新增节选的行号、整文件SHA256与原文核验范围；所有旧知识点锚点保留，正文使用技术学习用语。

本次通过全站文章静态发布审计、原有锚点比对、新增源码原文/SHA256/行号及HTML一致性检查，以及十章目录、搜索、复制、主题、要点速览、320/390/820px布局、禁用JavaScript和阻断外部请求下的浏览器验收。验证器等待hash导航完成后再断言当前章节。本次未执行RocketMQ进程故障、掉电或损坏磁盘实验；恢复结论来自固定版本源码分析。

图解放大时为克隆SVG改写ID，同时同步改写内嵌CSS选择器、marker/use与无障碍引用，避免Mermaid节点失去样式而变成黑块。共享controls.js与本手册的app.js、内嵌阅读器保持一致；逐一检查本页17张图放大后的节点fill/stroke与原图相同、全页ID唯一，且缩放按钮生效。

构建时SVG命名空间改写使用一次性ID映射，避免根ID与marker ID的前缀关系触发重复替换。所有图表的url(#...)引用和放大弹窗中的箭头标记均核对到存在的ID，确保禁用JavaScript时原图也保留流程方向。

2026年10月9日新增第11章JIT即时编译、JMM与内存屏障：固定OpenJDK8u462-b08提交，7段原始源码窗口、4张预渲染图、6道原理问答。重新生成正文、首页入口、章节统计并核验原锚点；JIT源码和发布检查范围见JIT-VERIFICATION.md。90分钟路线仍覆盖原十章，另列15分钟JIT扩展阅读。

JIT合并后验收通过11章搜索与要点速览、21张图的箭头引用和放大样式、320/390/820px布局、禁用JavaScript、阻断全部外部请求，以及7段固定源码的原文/行号/摘要和生成正文一致性。
