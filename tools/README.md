# 源码节选边界校验

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
