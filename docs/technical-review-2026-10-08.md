---
layout: default
title: 8组技术文章复审记录
---

# 8组技术文章复审记录

审核日期：2026年10月8日。范围为`mysql`、`nginx`、`springboot`、`nacos`、`distributed`、`transformer`、`jvm`、`jdk-source`。

整体主干可以继续使用，但“源码原文存在”不等于“引用属于正文所讲路径”，也不等于简化解释成立。本轮修正10处错误、表述边界或交付问题，补充4类机制反例。修订直接落到原章节，同步现有Markdown、作者数据、源码清单与离线包。

本轮覆盖各目录的阅读结构与高风险机制：事务/恢复、异步进度、状态确认、版本比较、GC与并发语义；并逐字检查下列固定源码窗口。它不是逐句形式化证明，也没有执行所有附带实验。未发现新问题的段落保留原文，不能把这一结论理解为“全书已经零错误”。

## 分组结论

|目录|本轮结论与修改|当前验证边界|
|---|---|---|
|MySQL|MVCC、读视图、redo/binlog、组提交与恢复主干未发现新的关键错误；补充纯gap锁兼容与插入意向锁边界|30段节选逐字匹配8.4.0；未启动MySQL或执行SQL|
|NGINX|请求、事件循环和重试主干未发现新的关键错误；修正Cookie缓存概括，区分读缓存与存响应两个开关|24段节选逐字匹配1.28.0；未运行NGINX集成实验|
|Spring Boot|修正Servlet章节误用Reactive同名类；修正Ready图示的流量承诺|56段节选匹配3.5.16、2.7.18、Framework6.2.19；未重跑历史Maven或服务器实验|
|Nacos|注册/Distro/持久实例/配置存储主干未发现新的关键错误；补充MD5比较的ABA反例|43段节选匹配3.2.4/2.5.4；未运行Server、SDK或集群故障实验|
|CAP与BASE|定义、不可区分性证明、Delayed-t与outbox故障窗口未发现本轮可确认的新错误，正文保留|对照原12页论文模型和证明；业务流程是教学方案|
|Transformer|Q/K/V、因果mask、多头、训练与生成主干未发现新的关键错误；补充原始嵌入缩放及权重共享|固定arXiv v5；数值脚本复算通过；没有训练完整模型|
|JVM|确认6处错误或过度简化，重点在卡表、TLAB、CMS、SPI及顺序一致性|核对JLS8与固定HotSpot8代码；本轮没有Java/GC动态实验|
|JDK源码|180张源码卡片核验通过；补充InheritableThreadLocal在线程池中的边界；修复离线包的跨目录导航|固定OpenJDK8u SHA；没有全量并发压力测试|

MySQL/NGINX/Spring Boot/Nacos/JDK合计333段固定源码窗口。JVM中的教学伪代码及XStream附录不混入这个“逐字源码”计数。

## 已修正的问题

|编号|位置与原问题|修正及证据|
|---|---|---|
|1|JVM§12.2.1：把0写为干净、非0写为脏|固定HotSpot8为`clean_card=-1`、`dirty_card=0`，还有其他状态；[CardTableModRefBS枚举](https://github.com/openjdk/jdk8u/blob/943a5ea328fd2fc8eed0aed4ec9b1957d41f8144/hotspot/src/share/vm/memory/cardTableModRefBS.hpp#L56-L74)|
|2|JVM§5.7：TLAB放不下对象时“退回Eden”|区分保留TLAB并共享分配、退役TLAB与填充尾部；不把尾部描述成立即可再分配空间；[make_parsable](https://github.com/openjdk/jdk8u/blob/943a5ea328fd2fc8eed0aed4ec9b1957d41f8144/hotspot/src/share/vm/memory/threadLocalAllocBuffer.cpp#L111-L134)|
|3|JVM§16.2：CMS初始标记只说根直接关联对象|补充年轻代作为老年代标记的根来源；[checkpointRootsInitialWork](https://github.com/openjdk/jdk8u/blob/943a5ea328fd2fc8eed0aed4ec9b1957d41f8144/hotspot/src/share/vm/gc_implementation/concurrentMarkSweep/concurrentMarkSweepGeneration.cpp#L3749-L3771)|
|4|JVM§16.8：把CMSScavengeBeforeRemark的Young GC归入可中断预清理|改为最终标记入口在条件满足时执行，并说明可能增加暂停成本；[checkpointRootsFinal](https://github.com/openjdk/jdk8u/blob/943a5ea328fd2fc8eed0aed4ec9b1957d41f8144/hotspot/src/share/vm/gc_implementation/concurrentMarkSweep/concurrentMarkSweepGeneration.cpp#L5035-L5071)|
|5|JVM§27.3：顺序一致性被概括为“所有操作原子且立即可见”|改为总顺序、程序顺序和读值规则；不把i++当原子动作，补上正确同步程序的保证；[JLS8§17.4.3](https://docs.oracle.com/javase/specs/jls/se8/html/jls-17.html#jls-17.4.3)、[§17.4.5](https://docs.oracle.com/javase/specs/jls/se8/html/jls-17.html#jls-17.4.5)|
|6|JVM§8.3：SPI写成“父加载器委托子加载器”|说明SPI显式选择TCCL等加载器；不等于改变默认loadClass算法，并保留DriverManager调用方可见性边界；[ServiceLoader](https://github.com/openjdk/jdk8u/blob/943a5ea328fd2fc8eed0aed4ec9b1957d41f8144/jdk/src/share/classes/java/util/ServiceLoader.java)、[DriverManager](https://github.com/openjdk/jdk8u/blob/943a5ea328fd2fc8eed0aed4ec9b1957d41f8144/jdk/src/share/classes/java/sql/DriverManager.java)|
|7|Spring Boot§14：Servlet链引用Reactive的WebServerStartStopLifecycle|改为`web/servlet/context`下的类，节选明确含`ServletWebServerInitializedEvent`；正文、行号、SHA256和归属清单同步；[正确源码](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/web/servlet/context/WebServerStartStopLifecycle.java#L42-L48)|
|8|Spring Boot§2图：“ready：允许接流量”|改为“发布就绪状态”；端口可更早监听，平台必须接入探针才能控制流量。原§20已经有此边界，现在图文一致；[事件源码](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/event/EventPublishingRunListener.java#L100-L111)|
|9|NGINX§22：Cookie、Set-Cookie等并列而未解释各自效果|明确请求Cookie不会自动绕过缓存或进入默认key，响应Set-Cookie默认禁止保存；区分cache_bypass与no_cache；[官方配置语义](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache_bypass)、[固定上游缓存路径](https://github.com/nginx/nginx/blob/481d28cb4e04c8096b9b6134856891dc52ecc68f/src/http/ngx_http_upstream.c)|
|10|JDK离线包：主页及JVM链接指向`../`、`../jvm/`|改为网站绝对链接，离线正文与图仍自包含；在共享离线转换器中补上规则，后续重建也能修正|

## 已补充的机制反例

- **MySQL§19**：纯gap S/X锁可以共存，不能照搬记录锁的兼容表解释；插入意向要结合具体位置和范围锁。[官方锁说明](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html)。
- **Nacos§20**：MD5比较当前内容，A→B→A后旧MD5仍可能通过条件，不能识别全部修改历史。该反例从内容比较条件推导，不宣称实测Server并发；源码入口为[ConfigInfoMapper](https://github.com/alibaba/nacos/blob/2c587c04891d532df1544ae95b906b677ac8eeff/plugin/datasource/src/main/java/com/alibaba/nacos/plugin/datasource/mapper/ConfigInfoMapper.java)。
- **Transformer§2**：完整2017配置还有嵌入缩放√d_model和嵌入/词表输出权重共享；行向量记法下输出使用Eᵀ。手算矩阵保留原值并标明省略这些设置。[固定v5§3.4](https://arxiv.org/html/1706.03762v5#S3.SS4)。
- **JDK§14.8**：InheritableThreadLocal在线程创建时继承，不随每次线程池任务提交自动重取上下文；默认不深复制值。补充显式传递、执行线程清理/恢复边界。[Thread.init](https://github.com/openjdk/jdk8u/blob/943a5ea328fd2fc8eed0aed4ec9b1957d41f8144/jdk/src/share/classes/java/lang/Thread.java#L419-L422)。

## 可重复检查与维护

新增`tools/audit_articles.py`覆盖全部8个目录，检查ID/锚点、本地文件、7个现有离线ZIP的完整性、正文一致性、资源新旧一致性与离线网络依赖。比较正文时允许导航和下载链接文案不同；源码逐字验证仍由各手册验证器与固定checkout承担，不能用这个发布检查替代机制审核。

```sh
python3 tools/audit_articles.py
python3 tools/validate_source_library.py
python3 docs/mysql/verify.py /path/to/mysql-8.4.0
python3 docs/nginx/verify.py /path/to/nginx-1.28.0
python3 docs/nacos/verify.py --source3 /path/to/nacos-3.2.4 --source2 /path/to/nacos-2.5.4
python3 docs/transformer/verify.py
/path/to/python3.12 tools/repair_source_excerpts.py
```

Spring Boot本轮另外将56项manifest逐项与三套固定SHA源码比较，Markdown与manifest一致，Servlet节选修正后重新渲染并打包。MySQL、NGINX、Nacos、JDK现有包同步更新；Transformer重新构建。JVM当前只维护公开HTML与附录材料，没有独立全书Markdown/离线包，不能沿用旧记录声称本轮同步了这些不存在的文件。

Playwright检查全部8页在1440px桌面和390px手机视口下的布局，16组结果均没有整页横向溢出。另检查JVM与Spring Boot截图；修复JVM摘要中直接显示的Markdown加粗标记。浏览器校验验证呈现与尺寸，不把它当作服务器运行或机制实测。

后续优化按收益排序：

1. **把实验设计变成带环境信息的实测记录**：MySQL两会话锁与2PC恢复、NGINX缓存/重试/慢消费者、Nacos断链恢复/CAS/快照优先；需要可丢弃实例或集群。本轮保留“未执行”，不填预期数字作实测。
2. **减少JVM重复内容**：第0–59节摘要与第60–75节补强存在重复。本轮已看到旧摘要仍遗漏补强中的约束；以后可合并同一主题，并保留原锚点跳转，减少两处维护导致的漂移。
3. **统一源码文章的构建入口**：Spring Boot/Nacos已有声明式材料；MySQL/NGINX当前仓库缺完整正文生成器。本轮保留既有HTML做精确更新，后续宜把生成流程纳入仓库，避免依赖临时脚本。
4. **继续保持版本隔离**：固定学习源码与生产补丁选型分开；现代JDK、滚动NGINX文档及不同Nacos部署模式单独判断。本轮没有把教程升级成“最新版本”。

本轮没有发现新的关键问题的CAP与Transformer主干，也没有因此删去原文已有的前提、限制和论文内部数据差异说明。
