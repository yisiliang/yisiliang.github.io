# JIT专题验证范围

验证日期：2026年10月9日。源码基线为OpenJDK8u462-b08，提交`943a5ea328fd2fc8eed0aed4ec9b1957d41f8144`；通过GitHub标签对象解析取得提交。正文区分Java SE8规范、HotSpot实现、教学示意和本机实验。源码来源、文件SHA-256与连续行范围记录在sources.json，版权头保存在source-notices.txt。

## 源码和发布结构

运行`python verify-jit-sources.py`重新下载固定提交，核对7段源码窗口、整文件SHA-256、Markdown正文和HTML代码，结果见jit-source-verification.json。窗口分别为编译提交、volatile加载、Acquire、Release、MemBarVolatile、x86-64后端及uncommon trap入口。局部窗口在正文明确标注，不冒充完整函数。

图解由本地Mermaid预渲染；读者无需联网渲染。新增4张图，全册共21张图、11个专题、66道原理问答。首页新增第11章直达链接，旧章节锚点保留，Markdown下载正文同步。技术专题目前没有ZIP，未声称新增离线ZIP。页面使用共享阅读器，保留搜索、要点速览、图解放大、复制、阅读进度与主题切换。

公开正文、标题与元描述采用技术学习表述。历史URL路径保留以维持已有链接，路径名称不作为页面文案显示。

## 已执行的本地教学实验

JitLab.java由Amazon Corretto8.462.08.1编译运行，完整版本为`1.8.0_462-b08 / HotSpot25.462-b08`，系统macOS27.0.1，JVM报告架构`aarch64`。这不是x86运行实验，也不宣称Corretto构建与上游OpenJDK源码逐字相同。

各配置执行一次，结果见[jit-lab-results.json](./jit-lab-results.json)：

|样例或对照|实际输出|可支持的结论|
|---|---|---|
|hot / PrintCompilation与PrintInlining|sum=2000001000000, changed=9|保留了可校验结果；日志出现dispatch的level3/4、PlusOne.apply内联和hot的OSR编译|
|hot / LogCompilation|同样的正确结果|运行事件包含unique_concrete_method依赖失败，以及dispatch处带thread标识的class_check uncommon trap；对应事件片段保存在JSON|
|plain-stop / 默认模式|workerAlive=true|本次有限join结束时工作线程仍活着；进程因daemon设置可正常退出|
|plain-stop / -Xint|workerAlive=false|本次解释模式退出，不能据此把原代码认定为正确同步|
|plain-stop / 排除plainWork编译|workerAlive=false|本次针对方法的对照退出；同样只是定位线索|
|volatile-stop|workerAlive=false|本次按volatile停止协议退出，不推导固定调度延迟|
|counter|volatileSplitIncrement=1, atomic=2|栅栏刻意让两线程先读取相同值，确定性展示复合读改写会丢失更新；不是自然count++的失效率测量|
|publish|published=42|一次性volatile发布样例得到预期值；有限实测不能替代HB语义证明|

`javap -c -p`核对了add的`iload_0、iload_1、iadd、ireturn`；两个停止循环均为`getstatic、ifeq、goto`形式。volatile语义来自字段属性和JVM实现，不是新增一条名叫volatile的字节码。

机器码并未采集反汇编，因此普通字段循环的读取外提是允许行为的解释，不作为该次运行实际机器指令的结论。正文x86屏障部分仅根据固定上游后端和Assembler::membar阅读；没有把本机aarch64日志充当x86证据。原日志SHA-256记录在JSON，公开JSON只保存有关事件和结果，不包含本机个人路径或完整环境变量。

## 未执行与不作出的结论

未运行jcstress、JMH、目标机器码反汇编、x86运行对照、多版本压力矩阵或真实生产故障实验。无吞吐与延迟结论，不把有限运行次数当作并发正确性证明。观察到JIT启用与现象相关，不独立证明JIT缺陷；源码分析没有证明每次访问生成固定数量的硬件屏障。

官方参考：[JLS8§17.3](https://docs.oracle.com/javase/specs/jls/se8/html/jls-17.html#jls-17.3)、[JLS8§17.4](https://docs.oracle.com/javase/specs/jls/se8/html/jls-17.html#jls-17.4)、[HotSpot性能机制](https://docs.oracle.com/javase/8/docs/technotes/guides/vm/performance-enhancements-7.html)、[JDK8java诊断参数](https://docs.oracle.com/javase/8/docs/technotes/tools/unix/java.html)。
