# 构建与验收范围

本目录的排版作为全站技术学习文章的共同基准。2026年10月9日统一学习用语与阅读器，共享源文件位于tools/reader；运行tools/style_readers.py后页面内嵌资源，原有章节与知识点锚点不变。首页第七类“技术专题”直接提供十章链接，栏目名称不固定数量；不更新sitemap/RSS。仓库GitHub Pages从master:/docs构建（legacy Jekyll），本目录不使用Front Matter，index.html是直接复制的静态HTML。页面显式载入现有Umami网站记录脚本；没有访问权限控制。

十个专题、60道三层问答、17张Mermaid图、源码连续节选和模拟故障。官方源码下载记录见sources.json，补充联网记录见research-checks.json。所有事故均为教学模拟，未实际运行Java、数据库、Redis、RocketMQ故障实验，不声称有真实生产测量。

读者不需要 npm、Python、Node.js 或后端。源码高亮使用本地 Prism；Mermaid 在构建时渲染成 SVG，正文和图表禁用 JavaScript 仍可阅读。运行时只有 Umami 使用外部请求，阻断它不影响核心功能。许可证在 licenses/ 与 vendor/，源码声明在 source-notices.txt。

维护时安装markdown、beautifulsoup4、playwright（仅维护环境）；运行build.py后，从仓库docs目录启动8000端口静态服务器，再运行render-diagrams.py，最后对本目录调用tools/style_readers.py中的transform应用共享阅读器，再运行verify.py。浏览器优先使用CHROMIUM_EXECUTABLE指定路径，否则检测Linux Chromium或macOS Google Chrome，再使用Playwright默认浏览器。部署产物不调用这些脚本。验证截图保存在output/playwright，验证结果见validation-results.json与diagram-validation.json。

发布仅需提交本目录，沿用已有 GitHub Pages 设置。公开地址为 https://yisiliang.github.io/java-architect-interview/。

2026-10-08 阅读改写：重写十章讲解与 60 道回答，口述部分直接给出完整回答；案例分段说明现象、检查与验证。source-notes.json 保存每段源码的阅读说明，anchors.json 保留 200 个原有知识点锚点。问题标题直接作为折叠按钮。样式和脚本资源按内容摘要附版本参数，避免正文更新后浏览器仍使用旧资源。

2026-10-09 RocketMQ存储协作补充：在原专题c7内增加完整存储协作章节（c7-s22），沿CommitLog追加、Reput派发、CQ去重、队列读取、哈希索引、Half内部队列和崩溃恢复说明状态变化与失败边界。新增15段RocketMQ4.9.8官方连续源码节选、2张构建时预渲染流程图，并核对5.3.4的并发Reput与RocksDB CQ实现。storage-source-verification.json记录新增节选的行号、整文件SHA256与原文核验范围；所有旧知识点锚点保留，正文使用技术学习用语。

本次通过全站文章静态发布审计、原有锚点比对、新增源码原文/SHA256/行号及HTML一致性检查，以及十章目录、搜索、复制、主题、要点速览、320/390/820px布局、禁用JavaScript和阻断外部请求下的浏览器验收。验证器等待hash导航完成后再断言当前章节。本次未执行RocketMQ进程故障、掉电或损坏磁盘实验；恢复结论来自固定版本源码分析。

图解放大时为克隆SVG改写ID，同时同步改写内嵌CSS选择器、marker/use与无障碍引用，避免Mermaid节点失去样式而变成黑块。共享controls.js与本手册的app.js、内嵌阅读器保持一致；逐一检查本页17张图放大后的节点fill/stroke与原图相同、全页ID唯一，且缩放按钮生效。
