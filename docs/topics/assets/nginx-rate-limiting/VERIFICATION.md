# Nginx限流专题核验记录

执行日期：2026年10月9日。固定版本：NGINX1.28.0，标签release-1.28.0，提交481d28cb4e04c8096b9b6134856891dc52ecc68f。2026年10月27日迁入独立专题页。

## 源码与内容

- 本地完整模块与 GitHub 官方固定提交的原文件逐字节一致；原文和上游LICENSE保存在 `docs/topics/assets/nginx-rate-limiting/`，随页面提供。
- 10段源码窗口保留原始行号与正文，`source-evidence.json` 记录完整文件与每段窗口的 SHA-256；构建检查核对 HTML 节选、内部锚点、本地资源和数值示例。
- 新Key首个请求、拒绝时不提交候选excess、多zone暂存count和最终记账、时间回退、节点淘汰、配置继承与HTTP阶段均对照固定源码核对。
- 公开文章统一为技术学习与工程实践表述；版本基线与生产选型分开陈述。

## 已执行的本地动态实验

macOS上从固定提交构建二进制，启用http_realip_module，未构建rewrite与gzip模块。使用两个Worker、HTTP/1.1和真实本地HTTP后端，每个场景同步启动7个客户端；本次全部场景客户端发起跨度小于1ms，但不宣称Nginx在严格同一毫秒内完成了所有检查。

原始记录：[lab-results.json](./lab-results.json)。后端时间相对该场景第一个被代理的请求：

|场景|成功/拒绝|后端接收时间，ms|
|---|---|---|
|默认延迟|6次200，1次429|0、100.948、201.232、300.733、401.923、500.537|
|nodelay|6次200，1次429|0、0.505、0.848、1.153、1.563、1.759|
|delay=2|6次200，1次429|0、0.453、0.697、102.080、202.204、302.360|
|dry-run|7次200|0、0.173、0.949、1.900、2.370、2.500、2.660|
|双zone，总量5r/s、burst=3|4次200，3次429|0、200.619、401.824、601.309|

日志记录实际Worker PID、limit状态与request_time；两个Worker均处理了实验请求。dry-run出现PASSED、DELAYED_DRY_RUN和REJECTED_DRY_RUN。

首次运行时，Python实验后端默认连接等待队列较小，突发代理中有一次上游连接重置导致502。将实验后端等待队列设为128后重新运行，以上结果为修正后的完整通过记录。这个修正针对实验装置，不修改Nginx限流行为。

本次未执行生产负载、跨实例协同、HTTP/2/HTTP/3、共享内存耗尽、时钟回退或所有多zone并发交错实验；相应描述来自固定源码或官方文档，不能当作动态实测结论。

## 重建与检查

正文源文件是 `docs/topics/chapters/12.md`，实验文件在 `docs/topics/assets/nginx-rate-limiting/`。页面为独立地址 `/topics/nginx-rate-limiting/`，不再合并进总文章，也不生成 ZIP。

```sh
# 维护环境（只需一次）
python3.12 -m venv /tmp/topics-env
/tmp/topics-env/bin/pip install markdown beautifulsoup4 playwright

# 重建正文与图解
/tmp/topics-env/bin/python docs/topics/build.py
/tmp/topics-env/bin/python docs/topics/render-diagrams.py
python3 tools/build_homepage.py
python3 tools/build_metadata.py

# 本地实验与全站检查
python3 docs/topics/assets/nginx-rate-limiting/run-lab.py --nginx /path/to/nginx --output /tmp/nginx-rate-lab
python3 tools/check_site.py
```

## 已执行的页面检查

- 2026年10月27日拆分后，Playwright 对 27 个地址 × 4 个视口（1440/820/390/320）共 108 次加载：无横向溢出、无脚本错误、无 ZIP 入口；左侧只保留一栏目录，当前篇目录与阅读进度合并在其中。
- 全文搜索、源码复制、图解放大与缩放、手机目录、浅色/深色/系统主题沿用共享阅读器；本页 2 张图与 16 个二级标题均纳入左侧目录。
- 禁用 JavaScript 时正文、问答与图表仍可阅读；实验数据只来自上表记录，不把步骤或预期写成新的实测。
- `tools/check_site.py`、`tools/audit_articles.py`、`tools/validate_source_library.py` 通过；公开 Markdown 与 HTML 内的源码节选一致。
