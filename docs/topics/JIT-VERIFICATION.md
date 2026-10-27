# JIT专题源码与发布检查

检查日期：2026年10月9日。源码基线为OpenJDK8u462-b08，提交`943a5ea328fd2fc8eed0aed4ec9b1957d41f8144`。正文区分Java SE8规范、HotSpot实现和教学示意；源码来源、文件SHA-256与连续行范围见sources.json，版权头见source-notices.txt。

核对了7段固定源码窗口、整文件SHA-256，以及Markdown与HTML中的代码，结果见jit-source-verification.json。窗口覆盖编译提交、volatile加载、Acquire、Release、MemBarVolatile、x86-64后端和uncommon trap入口；局部窗口明确标注，不冒充完整函数。

新增4张预渲染图，全册共21张图、11个专题、66道原理问答。首页新增第11章直达链接，旧章节锚点保留，Markdown下载正文同步。页面沿用共享阅读器的搜索、要点速览、图解放大、复制、阅读进度和主题切换。公开正文、标题与元描述采用技术学习表述；历史URL路径保留。

本专题不提供本机测试工程、运行记录或测量结果。正文代码仅用于解释机制，优化示意和x86后端源码不等于某次运行实际生成的机器指令；排查参数用于说明方法，不作为已验证根因或性能收益的证据。

官方参考：[JLS8§17.3](https://docs.oracle.com/javase/specs/jls/se8/html/jls-17.html#jls-17.3)、[JLS8§17.4](https://docs.oracle.com/javase/specs/jls/se8/html/jls-17.html#jls-17.4)、[HotSpot性能机制](https://docs.oracle.com/javase/8/docs/technotes/guides/vm/performance-enhancements-7.html)、[JDK8诊断参数](https://docs.oracle.com/javase/8/docs/technotes/tools/unix/java.html)。
