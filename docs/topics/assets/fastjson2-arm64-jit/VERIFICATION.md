# 文章核验与构建

正文源文件是 `docs/topics/chapters/14-fastjson2-arm64-jit.md`，由 `docs/topics/build.py` 生成独立页面 `/topics/fastjson2-arm64-jit/`。复现源码与原始日志保存在 `docs/topics/assets/fastjson2-arm64-jit/evidence/`，不再打包成 ZIP；页面内可逐项打开 `README.md`、探针源码、日志与 SHA256SUMS。

2026年10月27日，文章从合并专题第14节迁入独立地址，旧 `/fastjson2-arm-jit/` 保留跳转。当前页面使用全站共享阅读器：只有左侧目录，篇内目录与阅读进度合并在左栏；正文 15 个二级标题、2 张图解、45 个静态链接。

```sh
python3.12 -m venv /tmp/topics-env
/tmp/topics-env/bin/pip install markdown beautifulsoup4 playwright
/tmp/topics-env/bin/python docs/topics/build.py
/tmp/topics-env/bin/python docs/topics/render-diagrams.py
python3 tools/build_homepage.py
python3 tools/build_metadata.py
python3 tools/check_site.py
```

后续按作者确认改为第一人称，记录作者亲身遇到问题、排查和验证的过程。最初故障现象与 2026-10-27 的容器版本对照分别叙述，容器实验原始记录在 evidence/。没有声称测试 8u201；没有声称采集到反汇编；没有将不同次数的运行结果作为公平基准。结论的单补丁隔离边界在正文第 7 节保留。

正文对外引用固定的 Fastjson2 2.0.61、OpenJDK 修复提交及 JDK 更新版本标签。补丁的完整检查函数与 operand 定义经本地源码核对。

正文已按“现象 → 线索与猜测 → 对照验证 → 最小复现 → 源码根因与补丁 → 修复边界 → 故障链总结 → 短期 / 长期方案”重新编排，保留第一人称。`-Xcomp` 作为怀疑 JIT 后的主动实验。

## 本次完成的检查

- 迁入独立页面后通过 `tools/check_site.py`：55 个唯一 ID、45 个静态链接，本地资源、页内锚点与 canonical 完整，无右侧目录、无 ZIP 入口。
- evidence/ 的 37 个文件逐项与工作目录一致，SHA256SUMS 可复核；不再提供证据 ZIP。
- 两条正文异常栈与对应原始日志逐字匹配。`-Xcomp` 实测：8u202 首次 JSON.parse 失败、独立探针循环下标 1 读错；8u504 JSON 300 万次、探针 100 万次通过。
- evidence/run.sh 的 shell 语法检查通过。
- 四份复现 Java 源文件编译为 Java 8 字节码通过；从正文单独提取的完整 UnsafeScaleProbe 也编译通过。编译器仅提示目标版本与 Unsafe 内部 API 的常规警告。
- 正文两个完整 OpenJDK 代码窗口与固定提交 3c41cd8e624173834fa7b9ee8ede148c4e5541d0 的文件逐字匹配。
- 2026年10月27日浏览器回归覆盖 27 个地址 × 4 个视口（1440/820/390/320）共 108 次加载：无横向溢出、无脚本错误；本页两张 SVG 均加载成功。
- 全文搜索 `size_fits_all_mem_uses` 可定位到补丁节；要点速览、主题切换、源码复制与图解放大正常；手机目录抽屉可打开并跳转。
- 左侧目录显示当前专题的 15 个二级标题；其他 13 篇专题以链接形式并列，便于跨篇阅读。
- 首页有 14 个专题入口，统一进入 `/topics/` 或对应独立文章；本文不再复制进总文章。
- 发布前重新从作者修改后的 Markdown 构建页面与首页；单页审计、37 个证据文件及 SHA256SUMS 校验、shell 与 JavaScript 语法检查均通过。纳入新增文件后的 diff 检查提示原始 JVM 日志尾部空格及作者 Markdown 末尾空行，保留原始记录与作者原文。
