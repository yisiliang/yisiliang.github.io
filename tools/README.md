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
