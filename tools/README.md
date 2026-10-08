# 源码节选边界校验

2026年10月8日的8组技术文章复审见[审核记录](../docs/technical-review-2026-10-08.md)。跨目录发布检查运行`python3 tools/audit_articles.py`，覆盖全部8篇及现有离线包；技术机制和固定源码仍须分别核对。离线转换器会把跨教程的相对导航改为网站绝对链接，避免解压后访问不存在的兄弟目录。

`repair_source_excerpts.py`检查JDK、RocketMQ、Redis三本手册的全部源码卡片，使用各手册内已固定版本的原始源码ZIP，不获取或替换上游源码。修复后同步Markdown、网页代码、行号、链接和离线包；正文与图表不变。

运行环境建议Python3.12（tree-sitter0.26与Python3.14存在兼容问题）。首次安装：

```sh
python3.12 -m venv /tmp/source-excerpts-env
/tmp/source-excerpts-env/bin/pip install -r tools/requirements-source-excerpts.txt
npm ci --prefix tools
```

只检查：

```sh
/tmp/source-excerpts-env/bin/python tools/repair_source_excerpts.py
```

应用修复：

```sh
/tmp/source-excerpts-env/bin/python tools/repair_source_excerpts.py --apply
```

脚本从函数定义前补回对应原始注释，函数结束后不附带下一个函数的注释或实现。类、字段、方法内部的窗口保留其用途；ThreadLocal的rehash/resize/全表清理是正文明确讨论的连续多方法窗口。窗口仍可能止于当前函数内部，不额外补全长函数；若截在内部注释中，则补齐该注释。

`--baseline --apply`可从当前Git提交中的手册重建，使用前确保未提交的正文改动无需保留。`source-excerpt-repair-report.json`记录最近一次有改动的修复清单。每次运行均核对显示的源码与固定源码包、Markdown与网页修改数量、离线ZIP完整性；修复后的再次检查应显示0处改动。

## 源码学习库首页

六大分类与已发布教程记录在`homepage/catalog.json`，样式源文件是`homepage/style.css`。新增教程时填写真实版本与统计，并运行：

```sh
python3 tools/build_homepage.py
```

脚本生成`docs/index.html`与首页CSS，并拒绝指向尚不存在的教程页面。首页是独立静态页面，不依赖Jekyll主题或客户端框架。

四本新教程的发布结构检查：

```sh
python3 tools/validate_source_library.py
```

该检查验证页面锚点、本地资源、统计文件、离线包完整性和统计代码边界；源码节选及机制准确性还需各教程的`VERIFICATION.md`与固定源码基线核验。

上游源码窗口保留原始空白以支持逐字核验；`.gitattributes`仅对这些节选及Nacos包含原文的页面放宽对应空白检查。Spring Boot实验的`target/`和Nacos打包中间页不提交。

## 分布式理论文章

`docs/distributed/index.html`与`style.css`维护CAP与BASE图解文章。它是理论与教学案例，不套用源码手册的版本、节选数统计。更新后运行：

```sh
python3 tools/build_distributed_offline.py
python3 tools/build_homepage.py
```

离线包仅包含文章与本地CSS，不含统计脚本；继续阅读链接指向公开网站。首页目录中的理论入口排在Nacos前面，发布时检查目录锚点、手机布局、离线资源及线上HTML。

## 资料页统一阅读样式

首页目录中的8本源码手册采用`distributed`文章的深蓝底色、紫色强调色、衬线标题和左右阅读布局。共享样式与交互源文件在`reader/style.css`、`reader/controls.js`，在线与离线页面均内嵌这些资源。

修改共享样式，或重新生成任一本手册后，运行：

```sh
python3 tools/style_readers.py
python3 tools/validate_source_library.py
python3 docs/nginx/verify.py
python3 docs/nacos/verify.py
```

脚本读取首页目录，保留正文、源码与SVG原文，通过页头和目录布局转换统一8本手册，并同步已有离线ZIP及本地离线中间页。重复执行不会重复添加页头、样式或控件。搜索、复制与图解放大沿用各手册实现；默认深色，明暗偏好在8本手册间共享，手机目录通过“展开目录”显示。SVG保留原有颜色与图例，打印恢复纸面排版。CAP与BASE、Transformer论文解读及应用支持、隐私页面分别维护。目录记录中的`kind: paper`表示独立论文页，共享阅读器脚本跳过这类页面。

## Transformer论文解读

正文、样式与注意力计算器位于`docs/transformer/`，原文基线与验证记录见`VERIFICATION.md`。更新后运行：

```sh
python3 docs/transformer/build_offline.py
python3 docs/transformer/verify.py
python3 tools/build_homepage.py
```

公共页面包含一份Umami，离线包自动剥离统计，保留本地CSS、JS和数值核验脚本。原PDF通过固定版本链接引用。


## JVM附录

XStream附录的编辑入口是`docs/jvm/analysis-xstream-1.4.4-fgc.md`，正文按Oracle JDK8与CMS说明，页面只提供正文Markdown下载。历史检查记录保留在`docs/jvm/xstream-review.md`，不在页面提供入口。原有76节正文保持独立；附录生成器只替换标记区间，并维护附录入口。

```sh
python3 -m pip install -r tools/requirements-jvm-appendix.txt
python3 tools/build_jvm_appendix.py
python3 tools/build_homepage.py
```

`docs/jvm/xstream-lab.zip`作为归档保留最小JDK8实验工程、历史主对照、矩阵采样、复测与SHA256SUMS，不在页面提供下载入口。历史GC数字来自原实验配置，不能改写成CMS实测结果。修改实验结论时同步更新证据包与检查记录；不要把采样最大值当作真实峰值，也不要把未重跑场景写成新实测。

## JDK实战附录

ThreadLocal与多数据源切换复盘位于`docs/jdk-source/analysis-threadlocal-datasource.md`，配图位于`docs/jdk-source/diagrams/appendix-threadlocal/`。更新后运行：

```sh
python3 tools/build_jdk_appendix.py
python3 tools/build_homepage.py
```

渲染依赖沿用`requirements-jvm-appendix.txt`中的Markdown与本目录的highlight.js。生成器仅替换附录标记区，同步完整Markdown手册、内嵌SVG、目录入口和离线ZIP，保留已有JDK源码章节。
