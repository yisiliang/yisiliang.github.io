# 实验记录与复现实验

已执行：`python3 examples/md5-cas-model.py`。这个标准库模型说明旧MD5的CAS为何拒绝，以及ACK为什么先于正文更新。它没有运行Nacos，不验证真实SQL并发、gRPC、Distro或JRaft，不能替代下面的集成实验。

## 真实SDK实验：版本对照与观察清单

准备隔离的Nacos3.2.4三节点集群、独立测试namespace，客户端分别用2.5.4及3.2.4。不要在生产制造断链、分区或存储故障。每项保留SDK版本、服务器SHA、配置模式、时间戳、connectionId及内容MD5；凭据不写进日志。以下实验未执行。

|步骤|操作|观察点|判断边界|
|---|---|---|---|
|1|同namespace和group注册一个临时实例，并订阅它|ConnectionManager登记→Client创建→实例关系→publisher/subscriber索引|连接在线与实例注册是两阶段|
|2|修改metadata，再注销实例|客户端ServiceInfo、diff和InstancesChangeEvent|协议ACK不是业务负载均衡刷新确认|
|3|保留SDK到A连通，暂时阻断A到其他节点|各节点Client快照和revision|临时命名Distro允许传播窗口，不作全局线性一致承诺|
|4|恢复节点间通信|校验和CHANGE任务，快照缺席关系的删除|修复应该按Client单元观察|
|5|发布一份配置，两个发布者读同一MD5后CAS|第一个成功，第二个资源冲突|重新读取并合并，不能无条件覆盖|
|6|客户端断连时连续发布两次，再恢复|CacheData标脏、批量MD5对账、query正文、Listener|期待最终版本，不要求每个中间版本回调|
|7|准备snapshot和不同failover文件|实际返回来源、过滤/解密链|人工接管与自动快照不是同一种缓存|
|8|使用无权限用户请求配置|NO_RIGHT原样抛出|不能靠snapshot绕过授权错误|
|9|仅在可丢弃三节点环境做持久实例注册并失去多数派|CP提交错误与SDK端超时|节点端口存活不代表持久写可用|
|10|比较外部MySQL和嵌入式分布式部署|ConfigInfoPersistService实现、DB状态机组|两种持久化路径分别判定|
|11|独立Console发布与查询，以不同主体访问|Console身份转发与Server资源权限|页面能打开不等于SDK链路正常|
|12|Prompt草稿→提交→上线→按label读取；Skill按manifest下载|meta可见性、version状态、storage文件|草稿写入不等于在线可读|

## 源码断点位置

- 命名注册：`InstanceRequestHandler.registerInstance`、`EphemeralClientOperationServiceImpl.registerInstance`。
- 断链：`ConnectionManager.unregister`、`ConnectionBasedClientManager.clientDisconnected`、`NamingGrpcRedoService.onDisConnect`。
- Distro：`DistroClientDataProcessor.upgradeClient`、`DistroLoadDataTask.loadAllDataSnapshotFromRemote`。
- 配置：`ConfigOperationService.publishConfig`、`ConfigCacheService.dumpWithMd5`、`ClientWorker.handleConfigChangeNotifyRequest`、`refreshContentAndCheck`。
- CP：`PersistentClientOperationServiceImpl.onApply`、`JRaftServer.commit`、`DistributedDatabaseOperateImpl.update`。
- AI：`McpServerOperationService.createMcpServer`、`PromptOperationServiceImpl.queryPrompt`、`SkillOperationServiceImpl.querySkill`。

JRaft认证升级验证必须另建专门集群。检查所有节点的server identity和能力状态后再升级，强制状态锁存后不要使用混合旧版本滚动降级作为实验清理方案。
