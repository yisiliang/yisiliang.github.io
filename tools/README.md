# 源码节选边界校验

完整函数边界检查覆盖首页目录中所有带固定上游源码链接的文章，使用原有版本，不切换上游基线：

```sh
/tmp/source-excerpts-env/bin/python tools/complete_source_excerpts.py
/tmp/source-excerpts-env/bin/python tools/complete_source_excerpts.py --apply
python3 tools/style_readers.py
```

检查优先使用已打包源码，其余按文章原有提交或版本标签获取并缓存；函数窗口补齐签名、完整分支和结束位置，多函数窗口保留所有函数，字段、枚举和版本配置窗口保持各自用途。网页、Markdown、源码文件、生成器清单和现有离线包同步。`tools/source-completion-report.json`记录补齐范围；再次检查应为0处。更新Java专题的`sources.json`后运行该目录`build.py`与`render-diagrams.py`（从docs启动静态服务器并通过`READER_URL`指定专题地址），随后刷新共享阅读器；Nginx限流专题的窗口定义同时维护在`build.py`。回归边界与空行规则运行`python -m unittest discover -s tools -p 'test_complete_source_excerpts.py'`。

跨目录发布检查运行`python3 tools/audit_articles.py`，覆盖首页收录的全部技术文章及现有离线包；技术机制和固定源码仍须分别核对。离线转换器会把跨教程的相对导航改为网站绝对链接，避免解压后访问不存在的兄弟目录。

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

脚本从函数定义前补回对应原始注释，函数结束后不附带下一个函数的注释或实现。类、字段、方法内部的窗口保留其用途；ThreadLocal的rehash/resize/全表清理是正文明确讨论的连续多方法窗口。函数窗口同时补齐开头与结尾，不因函数较长而截断；注释也保持完整。

`--baseline --apply`可从当前Git提交中的手册重建，使用前确保未提交的正文改动无需保留。`source-excerpt-repair-report.json`记录最近一次有改动的修复清单。每次运行均核对显示的源码与固定源码包、Markdown与网页修改数量、离线ZIP完整性；修复后的再次检查应显示0处改动。

## 源码学习库首页

六大技术领域与第七类“技术专题”记录在`homepage/catalog.json`，样式源文件是`homepage/style.css`。专题分类使用`layout: topics`横跨整行，`topics`数组维护各章节标题与锚点；栏目名称不包含数量，统计由目录自动计算。新增教程时填写真实版本与统计，并运行：

```sh
python3 tools/build_homepage.py
```

脚本生成`docs/index.html`与首页CSS，并拒绝指向尚不存在的教程页面或专题锚点。分类、手册及专题数量从目录计算；CSS链接使用内容摘要作为版本参数，避免新增分类时浏览器沿用旧样式。首页是独立静态页面，不依赖Jekyll主题或客户端框架。

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

首页目录中的12个技术阅读页面均采用技术专题的排版：固定顶栏、左侧章节目录、中央正文、右侧篇内目录与阅读进度。默认整页连续展示全部章节、问答与阅读说明，目录只负责锚点定位；滚动时更新当前章节、篇内目录和全文阅读进度。提供全文搜索、源码复制、SVG图解放大、手机目录抽屉与系统／浅色／深色主题。共享源文件是`reader/style.css`、`reader/controls.js`，在线与现有离线页面均内嵌这些资源；技术专题还保留“要点速览”。

首页与全部技术文章的颜色变量统一维护在`reader/theme.css`，偏好与切换逻辑统一维护在`reader/theme.js`。共用`learning-reader-theme`存储键，切页沿用偏好，已经打开的同源页面通过`storage`事件同步；系统模式随操作系统变化。首页生成器输出带内容摘要的CSS与主题JS，阅读器直接内嵌同一份源码，离线包不需要外部主题资源。修改这两个文件后同时运行`python3 tools/style_readers.py`与`python3 tools/build_homepage.py`。

修改共享样式，或重新生成任一本手册后，运行：

```sh
python3 tools/style_readers.py
python3 tools/validate_source_library.py
python3 docs/nginx/verify.py
python3 docs/nacos/verify.py
```

脚本读取首页目录，使用HTML位置适配器移动原有正文，不重新序列化源码、行号或SVG；保留旧章节与附录锚点，并同步现有离线ZIP、Markdown及本地离线中间页。重复运行只刷新资源，不重复生成结构。对外统一使用学习表述，`reader/learning_words.py`维护用语映射，固定源码不替换。CAP与BASE、Transformer也纳入统一阅读器，交互计算器仍独立运行；应用支持、隐私及历史文章页面保持原有结构。

全目录结构与现有离线包检查：`python3 tools/audit_articles.py`。浏览器回归脚本是`reader/check-browser.js`，在从`docs`启动的静态服务器上用Playwright CLI运行；覆盖11个页面的搜索、旧锚点、复制、图解、主题及计算器。新增或重新生成页面后先运行样式工具，再执行结构与浏览器检查。JVM当前没有完整离线包，技术专题也尚未提供ZIP，工具不会凭空生成它们。

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

Nginx限流专题由`docs/nginx-rate-limiting/article.md`与固定模块源码生成。运行该目录的`build.py`同步HTML、完整Markdown、源码清单和离线ZIP，再运行`verify.py`。专题提供五组本地双Worker代理实验记录；阅读控件使用与共享工具兼容的内嵌资源标识。
