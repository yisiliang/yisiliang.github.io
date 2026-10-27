# LangGraph手册验证记录

> 说明：本记录写于 ZIP 离线包退役前。相关 ZIP 已于 2026-10-27 删除，页面现只提供 Markdown 正文下载；原始核验结论仍然有效。

核验日期：2026年10月19日。

## 固定基线

- LangGraph：1.2.16，GitHub提交`41c9c22fdc83d68a2859d0c9a2b627c8615a792f`。
- Python：3.13；完整实际运行版本见`lab-results.json`。
- Checkpoint、SQLite与其他依赖精确版本见`examples/requirements.lock`；该锁文件来自本机实验环境，其他操作系统的二进制包可用性需另行确认。
- 网页生成器：Markdown3.10.2与仓库`tools/node_modules`中的highlight.js11.11.1。
- 固定源码节选包含9个完整函数：LastValue.update、_is_field_binop、BinaryOperatorAggregate.update、StateGraph.compile、CompiledStateGraph.attach_edge、PregelLoop.tick、apply_writes、interrupt、run_with_retry。`source-evidence.json`记录完整路径、行号、SHA-256与固定提交URL。上游MIT许可证保存在`UPSTREAM-LICENSE.txt`。

## 重建与校验

```sh
python3.13 -m venv /tmp/langgraph-guide-env
/tmp/langgraph-guide-env/bin/python -m pip install -r docs/langgraph/examples/requirements.lock
npm ci --prefix tools
/tmp/langgraph-guide-env/bin/python docs/langgraph/build.py --run-labs
/tmp/langgraph-guide-env/bin/python docs/langgraph/verify.py
python3 tools/build_homepage.py
python3 tools/audit_articles.py
```

首次抽取源码或复核上游时，下载上面的固定提交，使用：

```sh
/tmp/langgraph-guide-env/bin/python docs/langgraph/build.py --source /path/to/langgraph --run-labs
/tmp/langgraph-guide-env/bin/python docs/langgraph/verify.py --source /path/to/langgraph
```

`build.py`从章节Markdown生成全文Markdown和网页，共享站内阅读器样式与控件，离线包移除统计脚本并改写跨教程导航。Python AST定位到函数结束，不截断分支，也不带入下一个函数。

## 实验范围

`examples/lab.py`的9组场景及断言已实际执行：最小图、并行合并与冲突、消息ID替换、动态Send、审批通过/拒绝/输入无效、重试次数、pending writes恢复、循环超限、updates事件。

`examples/sqlite_restart.py`在两个独立Python子进程间使用同一SQLite文件恢复中断，验证进程退出后仍可批准待审任务；不代表数据库容灾验证。

所有示例使用合成材料与确定性函数，无API Key、真实模型、追踪平台和业务系统。未验证模型准确率、子图专项行为、真实业务提交、多实例并发、PostgreSQL容灾或各类断电窗口。

## 页面验收

页面结构、离线资源、源码一致性与浏览器交互在发布前复核。浏览器覆盖目录、搜索、复制、图解、主题、手机抽屉、阅读进度和无JavaScript阅读；检查320、390、768、1024、1440像素布局。发布后等待GitHub Pages构建完成，再比较线上HTML与本地内容。

### 本次检查结果

- 10组编排实验通过，9段源码与GitHub固定提交原文逐字一致。
- LangGraph独立结构与离线包检查通过；浏览器搜索、复制、目录、图解缩放、三种主题、手机抽屉、进度及无JavaScript阅读全部通过，未发现页面脚本异常；320—1440像素检查无横向溢出。
- 首页第06类展示Transformer与LangGraph，已检查桌面与手机布局；手册正文和5张图解已视觉检查。
- 全站结构回归发现两个既有问题：Nacos离线包内`offline.html`与本地被忽略的中间文件不同；旧技术专题引用缺失的`./lab-nginx.conf`。全站浏览器回归还在旧技术专题的“正文全部展开”检查处失败。对应Nacos页面、ZIP与旧技术专题页面均与本次工作前HEAD完全一致，未在本次LangGraph变更中改动；其余已完成的结构检查通过。这些既有失败不计作LangGraph验收通过项。
