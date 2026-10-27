# 文章核验与构建

正文是 article.md；build.py 生成 index.html 与复现证据 ZIP，内嵌网站共享 reader 资源，不更新其他阅读页面。

```sh
python3 -m venv /tmp/fastjson-article-env
/tmp/fastjson-article-env/bin/pip install markdown beautifulsoup4
/tmp/fastjson-article-env/bin/python docs/fastjson2-arm-jit/build.py
python3 tools/build_homepage.py
python3 tools/audit_articles.py
```

后续按作者确认改为第一人称，记录作者亲身遇到问题、排查和验证的过程。最初故障现象与 2026-10-27 的容器版本对照分别叙述，容器实验原始记录在 evidence/。没有声称测试 8u201；没有声称采集到反汇编；没有将不同次数的运行结果作为公平基准。结论的单补丁隔离边界在正文第 7 节保留。

正文对外引用固定的 Fastjson2 2.0.61、OpenJDK 修复提交及 JDK 更新版本标签。补丁的完整检查函数与 operand 定义经本地源码核对。

正文已按“现象 → 线索与猜测 → 对照验证 → 最小复现 → 源码根因与补丁 → 修复边界 → 故障链总结 → 短期 / 长期方案”重新编排，保留第一人称。`-Xcomp` 作为怀疑 JIT 后的主动实验。

## 本次完成的检查

- 新文章通过 tools/audit_articles.py 的单页校验：60 个唯一 ID、41 个静态链接，本地资源和页内锚点完整。
- evidence ZIP 的 37 个文件逐项与工作目录一致，ZIP 完整性检查通过。
- 两条正文异常栈与对应原始日志逐字匹配。`-Xcomp` 实测：8u202 首次 JSON.parse 失败、独立探针循环下标 1 读错；8u504 JSON 300 万次、探针 100 万次通过。
- evidence/run.sh 的 shell 语法检查通过。
- 四份复现 Java 源文件编译为 Java 8 字节码通过；从正文单独提取的完整 UnsafeScaleProbe 也编译通过。编译器仅提示目标版本与 Unsafe 内部 API 的常规警告。
- 正文两个完整 OpenJDK 代码窗口与固定提交 3c41cd8e624173834fa7b9ee8ede148c4e5541d0 的文件逐字匹配。
- 浏览器实测桌面 1710px、手机 401px：文档没有横向溢出，两张 SVG 均加载成功。
- 全文搜索 size_fits_all_mem_uses 得到 2 处匹配，搜索结果可跳转到补丁节并关闭搜索框。
- 图解放大正常；手机目录抽屉可打开，选择版本边界节后跳转并关闭。
- 按作者要求，左侧仅显示 10 个一级目录；右侧固定显示全文一级与二级标题。此前浏览器验证过全文目录跳转与高亮；本轮重排后静态检查为 10 个一级标题、11 个二级标题，共 21 项。本轮没有重新进行浏览器交互验收。
- 共享 reader 控件通过 data-toc-scope="document" 支持全文目录，本文启用；没有该属性的页面保留原逻辑，未重新生成其他阅读页面。
- 首页有 14 个专题入口，新增入口可到达本文。原 Java 核心技术手册仍为 13 个专题。
- 发布前重新从作者修改后的 article.md 构建页面与首页；单页审计、37 个证据文件及 SHA256SUMS 校验、shell 与 JavaScript 语法检查均通过。纳入新增文件后的 diff 检查提示原始 JVM 日志尾部空格及作者 Markdown 末尾空行，保留原始记录与作者原文。

全目录逐页校验另有两项既有问题，均不属于本次新增文件：Nacos 的离线 ZIP 中 offline.html 与本地文件不一致；java-architect-interview 页面引用的 lab-nginx.conf 在当前检出中缺失。本次保留原状，不将全站检查表述为全部通过。
