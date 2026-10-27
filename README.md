# 源码之下，系统之上

[打开源码学习库](https://yisiliang.github.io/)

从源码出发，理解系统。首页保留语言与运行时、应用框架、数据库、缓存与消息、网络与分布式系统、AI与大模型六大领域，以及第七类“技术专题”。技术专题现在是 **14 篇独立长文**，不再合并成一个总页；每篇都有自己的目录、搜索、要点速览和图解。

|分类|已发布手册|
|---|---|
|语言与运行时|[JDK](https://yisiliang.github.io/jdk-source/) · [JVM](https://yisiliang.github.io/jvm/)|
|应用框架|[Spring Boot3.5.16 / 2.7.18对照](https://yisiliang.github.io/springboot/)|
|数据库|[MySQL8.4.0](https://yisiliang.github.io/mysql/)|
|缓存与消息|[Redis](https://yisiliang.github.io/redis/) · [RocketMQ](https://yisiliang.github.io/rocketmq/)|
|网络与分布式系统|[NGINX1.28.0](https://yisiliang.github.io/nginx/) · [CAP与BASE](https://yisiliang.github.io/distributed/) · [Nacos3.2.4 / 2.5.4对照](https://yisiliang.github.io/nacos/)|
|AI与大模型|[Transformer：《Attention Is All You Need》通俗解读](https://yisiliang.github.io/transformer/) · [LangGraph：核心机制、源码解析与工程实践](https://yisiliang.github.io/langgraph/)|
|技术专题|[技术专题目录（14篇）](https://yisiliang.github.io/topics/)|

## 技术专题

专题入口是 [yisiliang.github.io/topics/](https://yisiliang.github.io/topics/)，每篇一个独立地址：

|#|专题|地址|
|---|---|---|
|01|Java 并发编程与锁机制|[/topics/java-concurrency/](https://yisiliang.github.io/topics/java-concurrency/)|
|02|HashMap 与 ConcurrentHashMap|[/topics/hashmap-concurrenthashmap/](https://yisiliang.github.io/topics/hashmap-concurrenthashmap/)|
|03|JVM 内存管理、CMS 与 G1|[/topics/jvm-memory-cms-g1/](https://yisiliang.github.io/topics/jvm-memory-cms-g1/)|
|04|JVM OOM 与生产故障排查|[/topics/jvm-oom-troubleshooting/](https://yisiliang.github.io/topics/jvm-oom-troubleshooting/)|
|05|Spring 核心原理与事务|[/topics/spring-core-transactions/](https://yisiliang.github.io/topics/spring-core-transactions/)|
|06|数据库事务、MVCC 与性能优化|[/topics/database-transactions-mvcc/](https://yisiliang.github.io/topics/database-transactions-mvcc/)|
|07|RocketMQ 消息队列|[/topics/rocketmq/](https://yisiliang.github.io/topics/rocketmq/)|
|08|Redis 与分布式缓存|[/topics/redis-cache/](https://yisiliang.github.io/topics/redis-cache/)|
|09|分布式事务与数据一致性|[/topics/distributed-transactions/](https://yisiliang.github.io/topics/distributed-transactions/)|
|10|微服务、高并发与系统稳定性|[/topics/microservices-stability/](https://yisiliang.github.io/topics/microservices-stability/)|
|11|JIT即时编译、JMM与内存屏障|[/topics/jit-jmm-memory-barriers/](https://yisiliang.github.io/topics/jit-jmm-memory-barriers/)|
|12|Nginx限流原理与工程实践|[/topics/nginx-rate-limiting/](https://yisiliang.github.io/topics/nginx-rate-limiting/)|
|13|JVM内存结构与OOM排查实战|[/topics/jvm-memory-structure-oom/](https://yisiliang.github.io/topics/jvm-memory-structure-oom/)|
|14|从 Fastjson2 解析异常追到 ARM64 JIT 编译缺陷|[/topics/fastjson2-arm64-jit/](https://yisiliang.github.io/topics/fastjson2-arm64-jit/)|

14 篇合计 66 道三层问答、48 张图解。旧地址 `/java-architect-interview/`、`/fastjson2-arm-jit/`、`/nginx-rate-limiting/`、`/jvm-memory-oom/` 保留为跳转页，旧的 `#c1`–`#c14` 锚点也会映射到对应新文章。

新增专题不再合并进总页：在 `docs/topics/chapters/` 放一份以 `# 标题` 开头的 Markdown，在 `docs/topics/topics.json` 增加一条记录，然后依次运行 `docs/topics/build.py`、`docs/topics/render-diagrams.py`、`tools/build_homepage.py`、`tools/build_metadata.py` 即可。

## 阅读器

全部 25 个阅读页面（11 本手册 + 14 篇专题）共用一套版式：固定顶栏、**只有左侧目录**（章节树、篇内目录与阅读进度合并在一起）、中央正文、全文搜索、源码复制、图解放大、要点速览和系统／浅色／深色主题。右侧目录已移除，正文区域相应加宽。

源码教程固定上游标签与完整提交，提供真实节选、机制图、正文推导、验证记录和 Markdown 下载。实验记录区分已执行与仅提供步骤/预期；学习基线不等于最新生产版本。可下载的手册与专题提供 Markdown 正文，不再提供 ZIP 离线包。

## 元数据与发布

`tools/build_metadata.py` 统一为公开内容页补齐 `description`、`canonical`、Open Graph、Twitter Card、favicon，并生成 `sitemap.xml`、`robots.txt`、默认分享图和 `404.html`。首页、手册页与专题页的 canonical 都指向各自的固定地址。

首页目录维护与发布检查见 [tools/README.md](tools/README.md)。Support、Privacy Policy 和历史技术文章保留原地址，不在首页展示；这些页面不参与本次版式与元数据改造。

## 其他内容

JVM 附录 [XStream1.4.4与CMS回收压力](https://yisiliang.github.io/jvm/#appendix-xstream) 按 Oracle JDK8 与 CMS 展开，解释实例级构造器缓存、反射类生成、元空间高水位，以及复用实例和升级版本的作用。

JDK 附录 [ThreadLocal状态残留与偶发SQL异常](https://yisiliang.github.io/jdk-source/#appendix-threadlocal-datasource) 通过六张流程图还原单例DAO留下选库状态、后续非单例DAO读取残留值的过程，解释线程复用、调用顺序和报错后状态恢复带来的排查难点。

第 12 专题固定 NGINX1.28.0，解释 excess、rate、burst、nodelay、delay、共享状态、多 zone 记账、可信代理与跨实例配额边界；第 13 专题以 HotSpot JDK8 为基线覆盖 Heap、Metaspace、Direct Memory、线程与容器 RSS；第 14 专题通过 ARM64 Linux 容器、独立 Unsafe 探针与 BellSoft 8u292 / 8u302 对照，把 Fastjson2 2.0.61 的解析异常对应到 JDK-8267689。

CAP 与 BASE 文章从网络分区推导理论边界，并通过订单与积分案例解释可靠消息、幂等、重试、补偿与对账，附 Gilbert 与 Lynch 原论文精读，均标注 PDF 页码。

Transformer 文章固定 arXiv:1706.03762v5，通过 16 节深入解读、4 张图解与交互计算器串起 Q/K/V、多头、位置编码、Encoder—Decoder 和训练推理，附可重新计算的教学矩阵。

LangGraph 手册固定 1.2.16 与提交 `41c9c22fdc83d68a2859d0c9a2b627c8615a792f`，通过 16 章、5 张图解、9 段完整函数源码与 10 组本地实验，解释状态合并、Pregel 调度、条件路由、Checkpoint、人工审核、重试与业务幂等。构建与复核方法见 `docs/langgraph/VERIFICATION.md`。
