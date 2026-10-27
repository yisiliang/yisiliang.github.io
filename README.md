# 源码之下，系统之上

[打开源码学习库](https://yisiliang.github.io/)

从源码出发，理解系统。首页保留语言与运行时、应用框架、数据库、缓存与消息、网络与分布式系统、AI与大模型六大领域，并新增第七类“技术专题”，按问题串起源码原理与架构实践；MyBatis属于应用框架。

|分类|已发布手册|
|---|---|
|语言与运行时|[JDK](https://yisiliang.github.io/jdk-source/) · [JVM](https://yisiliang.github.io/jvm/)|
|应用框架|[Spring Boot3.5.16 / 2.7.18对照](https://yisiliang.github.io/springboot/)|
|数据库|[MySQL8.4.0](https://yisiliang.github.io/mysql/)|
|缓存与消息|[Redis](https://yisiliang.github.io/redis/) · [RocketMQ](https://yisiliang.github.io/rocketmq/)|
|网络与分布式系统|[NGINX1.28.0](https://yisiliang.github.io/nginx/) · [CAP与BASE](https://yisiliang.github.io/distributed/) · [Nacos3.2.4 / 2.5.4对照](https://yisiliang.github.io/nacos/)|
|AI与大模型|[Transformer：《Attention Is All You Need》通俗解读](https://yisiliang.github.io/transformer/)、[LangGraph：核心机制、源码解析与工程实践](https://yisiliang.github.io/langgraph/)|
|技术专题|[Java核心技术与架构实践（13个专题）](https://yisiliang.github.io/java-architect-interview/)|

技术专题覆盖Java并发、集合、JVM内存与故障排查、Spring事务、数据库、RocketMQ、Redis、分布式事务、系统稳定性与JIT即时编译，并新增Nginx限流专题与JVM内存、OOM排查专题。首页在专题标题与说明下直接列出13个专题入口。Java专题包含66道三层问答、原有图解与新增Nginx/JVM主题，并支持要点速览和90分钟回顾路线。

第12专题“Nginx限流原理与工程实践”固定NGINX1.28.0，解释excess、rate、burst、nodelay、delay、共享状态、多zone记账、可信代理与跨实例配额边界；包含源码窗口、图解、本地实验和离线阅读包。

CAP与BASE文章从网络分区推导理论边界，并通过订单与积分案例解释可靠消息、幂等、重试、补偿与对账，提供离线阅读包，并附Gilbert与Lynch原论文精读：定理1的执行构造、推论1.1、定理2及Delayed-t恢复约束，均标注PDF页码。

Transformer文章固定arXiv:1706.03762v5，通过16节深入解读、4张图解与交互计算器串起Q/K/V、多头、位置编码、Encoder—Decoder和训练推理，并分析创新点、计算与显存取舍、梯度学习、GPT预训练及2017—2022年走向ChatGPT的演进，附可重新计算的教学矩阵与离线包。

JVM附录[XStream1.4.4与CMS回收压力](https://yisiliang.github.io/jvm/#appendix-xstream)按Oracle JDK8与CMS展开，解释实例级构造器缓存、反射类生成、元空间高水位，以及复用实例和升级版本的作用。

JDK附录[ThreadLocal状态残留与偶发SQL异常](https://yisiliang.github.io/jdk-source/#appendix-threadlocal-datasource)通过六张流程图还原单例DAO留下选库状态、后续非单例DAO读取残留值的过程，解释线程复用、调用顺序和报错后状态恢复带来的排查难点。

源码教程固定上游标签与完整提交，提供真实节选、机制图、正文推导、验证记录和离线包。实验记录区分已执行与仅提供步骤/预期；学习基线不等于最新生产版本。

首页目录维护与发布检查见[tools/README.md](tools/README.md)。Support、Privacy Policy和历史技术文章保留原地址，不在首页展示。

新增故障复盘：[从 Fastjson2 解析异常追到 ARM64 JIT 编译缺陷](docs/fastjson2-arm-jit/article.md)。通过 ARM64 Linux 容器、独立 Unsafe 探针与 BellSoft 8u292 / 8u302 对照，将 Fastjson2 2.0.61 的解析异常对应到 JDK-8267689，附实验代码与日志。该独立文章列于首页“技术专题”，Java 核心技术手册仍保留原有 13 个专题。

JIT专题从热点识别、分层编译、OSR与去优化展开，串联JMM、volatile发布、CAS及C2内存屏障，附固定OpenJDK源码窗口和机制图解：[JIT即时编译、JMM与内存屏障](https://yisiliang.github.io/java-architect-interview/#c11)。

第13专题“JVM内存结构与OOM排查实战”以HotSpot JDK8为主要基线，覆盖Heap、Metaspace、Direct Memory、线程与容器RSS、常见OOM、诊断命令和故障案例，包含23张SVG图解及应急清单。

LangGraph手册固定1.2.16与提交`41c9c22fdc83d68a2859d0c9a2b627c8615a792f`，通过16章、5张图解、9段完整函数源码与10组本地实验，解释状态合并、Pregel调度、条件路由、Checkpoint、人工审核、重试与业务幂等，附SQLite跨进程恢复实验和离线包。构建与复核方法见`docs/langgraph/VERIFICATION.md`。
