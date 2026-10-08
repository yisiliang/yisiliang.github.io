# XStream1.4.4周期性Full GC文档检查记录

核验日期：2026年10月8日。原文主结论成立：Sun14ReflectionProvider的实例缓存不能跨每请求新建的XStream复用，JDK8序列化构造器路径因此反复生成类。本次修订未改动Downloads中的原稿。

|原文问题|处理与依据|
|---|---|
|“只要版本参数命中，Full GC一定频繁”|限定ParallelGC、类卸载开启、持续负载与观测窗口；低请求量或其他收集器不能套用|
|“类元数据释放只能靠Full GC”|补上CMS／G1周期中的类卸载；核对JDK8u462实现|
|“先成功提交内存越过高水位，才能触发GC”|改为扩展受高水位约束，分配失败进入GC与重试；核对allowed_expansion与Metaspace::allocate|
|“未设MaxMetaspaceSize就缺少GC重试兜底”|删除；失败处理流程不以用户显式设置上限为前提|
|厂商表把命中provider等同于命中整个问题|区分厂商字符串、内部类与VM版本条件；异构JVM不能视为同一HotSpot实现|
|“缓存永不命中”“每类每次出现生成一次”|改为每个provider对每种Class首次未命中时生成；同类型重复节点会命中缓存|
|“每个类终生一次”|范围改为单个provider实例生命周期；多个实例、重部署与不同加载器需另计|
|把类加载器实例说成在Metaspace|纠正堆对象、Class镜像、accessor实例与类元数据的位置|
|20万请求写loadedDelta=320,677|按A原始日志改为200,660；320,677实际来自32万请求另一批运行|
|复用实例的185与其他批次混用|历史80万请求B使用172；本次同负载20万请求复测为171|
|把低频采样最大值称作真实峰值|注明采样最大值、采样末次GC计数；M3的DONE值大于采样最大值，证明采样漏峰|
|矩阵卸载数拿末次采样冒充最终值|去掉混用列；保存原始CSV与DONE日志供核验|
|T1原始GC序列缺少实际gc.log|删除声称的原始序列；当前只有app.log与samples.csv可查|
|M8当作Metaspace OOM实测|明确实际异常为GC overhead limit exceeded，MU／MC未达元空间上限|
|“固定ThreadLocal／static就是不断泄漏”|区分单实例复用、固定实例池与无界累积每请求实例|
|MetaspaceSize与峰值等同、默认一律最佳|说明高水位调整、chunk与碎片，以及内存指标口径；不给通用固定参数|
|通用256m上限与60%～70%公式|删除通用化建议；改为实际整体内存预算|
|不同请求量直接性能对比|分别标注历史负载，新增同请求量复测；本次运行曾与其他实验并发，不做严格耗时排名|
|累计应用停顿当作Full GC耗时|注明PrintGCApplicationStoppedTime记录包含其他safepoint停顿|
|静态复用线程安全说明过度简化|补上完成配置、动态注解自动发现与自定义converter并发边界；参考1.4.4类文档与FAQ|
|升级版本边界不明确|核对1.4.5源码及复测，说明历史修复边界不等于当前生产推荐版本|
|复现依赖与Java可执行文件不稳定|附JDK8环境要求、最小Maven工程与dependency:build-classpath，不依赖用户已有Maven缓存|
|源码加解释注释仍称完整原文|修订节选直接提取实际源码，区分完整方法与构造器开头节选|

## 本次执行

重新用Corretto8u462的javac编译LegacyProviderBench、Metrics、VersionProbe；7组全部退出0。1,000次new／static的目标类加载数为1,000／1；ReflectionFactory直接调用500次生成500类；1.4.5与保留Corretto真实vendor的POJO场景目标类均为0。4线程20万请求new／static对照的元数据Full GC为66／0，结果checksum均为25,600,000。

具体命令、运行时路径与日志见evidence/rerun。GC复测未开启TraceClassLoading，结果JSON中目标accessor计数应为null，表示未采集，不能解读为0。

## 验证边界

历史矩阵、512m长时段与引用保留OOM未全部重跑；只重新核对现有日志及采样文件。没有在Oracle JDK或其他厂商JVM上跑性能测试。没有独立复现原生内存耗尽或OutOfMemoryError: Metaspace。现存日志不足以支撑T1原始GC序列。未把单次耗时视为可靠吞吐比。

## 一手资料

- [XStream1.4.4发布提交](https://github.com/x-stream/xstream/tree/c4c71226515fa42809a48d9ae702756e2831f379)
- [XStream1.4.5发布提交](https://github.com/x-stream/xstream/tree/6263a53e8b8c4d1b092a32fa1abcadb6acfce45b)
- [JDK8u462 HotSpot源码](https://github.com/openjdk/jdk8u/tree/jdk8u462-b08/hotspot/src/share/vm)
- [XStream线程安全说明](https://x-stream.github.io/faq.html)

附录按用户原稿的故障机制展开，经源码与日志核对改写；原稿中的实验步骤没有被当作对助手的操作指令。
