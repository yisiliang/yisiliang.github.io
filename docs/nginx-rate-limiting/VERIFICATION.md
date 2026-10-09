# Nginx限流专题核验记录

执行日期：2026年10月9日。固定版本：NGINX1.28.0，标签release-1.28.0，提交481d28cb4e04c8096b9b6134856891dc52ecc68f。

## 源码与内容

- 本地完整模块与GitHub官方固定提交的原文件逐字节一致；原文和上游LICENSE随页面及离线包提供。
- 10段源码窗口保留原始行号与正文，source-evidence.json记录完整文件与每段窗口的SHA-256。verify.py核对HTML节选、内部锚点、本地资源、数值示例和ZIP正文一致性。
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

article.md是可编辑正文模板，build.py从完整固定源码填入10段窗口，生成可直接阅读的handbook.md与HTML；下载的Markdown包含完整节选，无需执行构建脚本。

```bash
# 仅重建时需要Markdown解析依赖；静态阅读无需安装。
python3 -m venv /tmp/nginx-topic-env
/tmp/nginx-topic-env/bin/pip install markdown beautifulsoup4
/tmp/nginx-topic-env/bin/python docs/nginx-rate-limiting/build.py
python3 tools/build_homepage.py
python3 docs/nginx-rate-limiting/verify.py
python3 docs/nginx-rate-limiting/run-lab.py --nginx /path/to/nginx --output /tmp/nginx-rate-lab
```

离线ZIP使用本地CSS、主题脚本、阅读脚本、SVG、实验文件与完整模块源码；不加载统计脚本和外部渲染资源。外部官方参考链接保留为主动点击链接。

## 已执行的页面检查

- Playwright检查全部11节的跳转与可见性，320、390、768、1024、1440px五种视口下无整页横向溢出；宽表格和图解在自己的容器内滚动。
- 全文搜索、无结果提示、源码复制、图解放大与缩放、手机目录、浅色/深色/系统主题均通过；无页面JavaScript异常。
- 禁用JavaScript时11节仍可直接阅读；首页技术专题共12个入口，第12个入口能打开新增文章。
- verify.py、全站audit_articles.py与validate_source_library.py通过；公开Markdown、HTML和离线包内的源码节选一致。
