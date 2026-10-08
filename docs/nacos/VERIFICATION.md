# Nacos手册核验记录

核验日期：2026年10月7日。

## 固定来源

- Nacos3.2.4：`2c587c04891d532df1544ae95b906b677ac8eeff`。
- Nacos2.5.4：`55a99b1c186f81a53976e1a323ae29feb47d3aaf`。
- 官方仓库：[alibaba/nacos](https://github.com/alibaba/nacos)。已读取两版发布页，并以固定checkout实际内容为源码依据。
- 共28个实质章节、17幅SVG机制图、43个源码窗口，逐文件路径/版本/SHA/行号/节选SHA256记录于`source-manifest.json`。

## 已执行

1. 两个checkout的`git rev-parse HEAD`与以上固定提交一致。
2. 43个节选逐字对照相应原文件的行号窗口；生成HTML解码后的源码正文再次与节选摘要比较，避免高亮渲染改写源码。
3. `verify.py`检查章节、图与节选数量，HTML唯一ID/锚点、相对资源存在性、SVG完整XML及唯一title/desc/marker引用。
4. 公开HTML恰好一份Umami，离线HTML及ZIP内HTML没有统计脚本；公开HTML不含本机路径。
5. ZIP CRC、许可/NOTICE原文、相对链接与资源检查；ZIP入口为无统计的`index.html`，CSS、代码高亮与脚本均内联，无需CDN才能阅读。
6. `examples/md5-cas-model.py`通过：旧MD5写入拒绝，ACK先于正文更新。该脚本只验证教学模型，不验证Nacos运行行为。
7. 父级已在实际浏览器复查桌面与390px手机首屏；无全页横向溢出，源码窗口与表格/图解使用各自滚动容器。

复核命令（源码路径由复核者明确传入，不写进公开HTML）：

```sh
python3 verify.py --source3 SOURCE_CHECKOUT_3_2_4 --source2 SOURCE_CHECKOUT_2_5_4
python3 examples/md5-cas-model.py
```

若只拿到离线包，可直接运行`python3 verify.py`核对本包摘要、HTML、锚点和资源；要逐字对照上游，必须提供两个固定源码checkout。离线包中的verify脚本将检查当前文件，ZIP本身不存在时不做ZIP递归验证。

## 确认的版本与边界

- 3.2.4服务端Java17；Client与Maintainer Client为Java8基线。根POM的Spring Boot实际为3.5.14。
- 2.5.4已使用gRPC与Client/Distro架构，不写成3.2首次引入。
- Service身份由namespace/group/name决定，ephemeral不是另一身份键；同名服务类型冲突需拒绝。
- 临时实例Distro、持久实例CP、外部MySQL与嵌入式分布式数据库分别解释，不作全系统统一Raft或全局线性一致承诺。
- 配置提示ACK先于正文获取、监听回调及应用生效；NO_RIGHT权限错误不会被snapshot兜底吞掉。
- MCP/A2A索引与正文各有发布调用；Prompt/Skill有不同AiResource、版本与存储模型，不把AI Registry写成模型推理引擎。
- 3.2.4JRaft认证存在持久强制锁存；进入强制状态后不依赖混合旧版本滚动降级。弃用AI API与私网MCP导入按官方3.2.4范围单独迁移。

## 未执行与交付限制

- 没有构建整个Nacos、启动服务集群或运行上游Java测试。
- 没有执行真实SDK断链、Distro网络分区、JRaft多数派故障、数据库故障、AI发布或滚动升级实验。
- 各章实验均标为未执行；`examples/README.md`提供隔离环境步骤与观察点。
- 本记录只证明源码与静态交付一致性，不证明上述运行时性能、恢复时间或兼容性；页面部署状态由父级统一验收。

## 许可

`apache-license.txt`为上游LICENSE完整原文，`nacos-notice.txt`为上游NOTICE原文；节选版权及编排说明见`source-notices.txt`。未修改源码正文，未打包完整源码树。Java高亮为本包自有着色，无第三方脚本依赖。

主任务浏览器验收：桌面与390px手机页面可读，无全页横向溢出；41段初始源码及最终43段均以两版checkout独立核验。offline.html为打包中间文件，不作为公开页面提交；核验器也支持直接读取ZIP中的离线HTML。

## 2026年10月8日复审

本轮用3.2.4/2.5.4 checkout逐字核对43段源码；补充MD5内容比较的ABA边界。未运行Server、Java SDK、数据库或集群故障实验。
