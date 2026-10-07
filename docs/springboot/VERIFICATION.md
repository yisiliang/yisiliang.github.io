# Spring Boot源码手册验证记录

验证日期：2026年10月7日。页面为独立源码导读，网页发布状态由站点发布流程另行核验。

## 固定源码与版本

- Spring Boot3.5.16：`v3.5.16`，commit `0566f6933049aca6bc5ffc6d559fffade9cd2e0c`。
- Spring Boot2.7.18：annotated tag `937c8a98195275d771d2a93eb1b3952f910cfbed`，peeled commit `0c8b382d42db22b92efcf47000d0ff9ef4971629`。
- Spring Framework6.2.19：`v6.2.19`，commit `6214eae8bd02c2ed7ab382bb8d16a9cc6de49522`。Boot3.5.16的gradle.properties声明此Framework版本。
- 用官方GitHub仓库`git ls-remote`核对标签，并浅克隆固定tag，读取真实文件。没有将分支HEAD当成版本依据。
- `source-manifest.json`登记56个片段的原文、仓库、版本、SHA、文件、首尾行与SHA-256。逐段重新读取固定源码并比较：56/56一致；网页代码块也逐段比较。

## 交付规模与静态检查

- 27个实质章节；每章包含问题、字段状态、实际调用链、失败边界和可复现实验。
- 27个内嵌SVG机制图，图标题与marker ID各图唯一，XML可解析。分支分区图明确不表示顺序执行。
- 56段真实源码，全部链接到固定SHA与实际行号。Framework片段明确归属Framework6.2.19。
- HTML所有ID唯一，内部锚点有目标，离线资源自包含，引用下载文件均存在。
- 网页有且仅有1份Umami；离线ZIP的index.html无统计脚本、无CDN依赖。
- 公开正文不包含本地用户路径、临时目录、个人履历或生产连接配置。

## 实际执行的机制实验

教学工程位于`examples/`，使用Spring Boot3.5.16、Maven3.9.11和Java17.0.16执行JUnit：**10个测试全部通过，0失败、0错误、0跳过**。`experiment-results.json`保存机器可读结果。

| 测试 | 实测结果 |
|---|---|
| Duration结构绑定 | `demo.timeout=3s`绑定为Duration.ofSeconds(3) |
| 非法Duration | `demo.timeout=abc`使上下文失败 |
| Jakarta Bean Validation | `demo.retries=0`违反Min(1)，创建失败 |
| MissingBean默认/退让 | 无用户Bean取默认，有用户Bean默认退出 |
| Property条件 | 缺失/false/abc不匹配，TRUE匹配显式havingValue=true |
| 命令行优先级与Runner时序 | cli覆盖文件，Ready事件看到Runner已完成 |
| Runner失败 | IllegalStateException原消息保留，Ready不发布 |
| Profile配置 | dev配置在Runner之前生效 |
| optional缺失导入 | 可选的不存在资源允许启动 |
| MVC切片 | MockMvc经过DispatcherServlet，GET /ping返回pong |

初版实验暴露的两个边界已经进入正文：3.5.16的RuntimeException传播与2.7.18包装行为不同；主配置类显式@Bean不受切片扫描过滤器统一排除。修正工程组织和实际语义断言后，完整测试通过。

执行`mvn -DskipTests package`生成可执行JAR；随后以Java21.0.12.1、`server.port=0`临时启动完整Servlet应用，HTTP实测：`/ping`为200/pong，`/actuator/health`为200/UP，未暴露的`/actuator/beans`为404。向该教学进程发送SIGTERM后退出，日志显示Graceful shutdown complete。此检查不包含长请求排空超时场景。

## 如何复核

```sh
cd examples
mvn test
mvn package
java -jar target/source-lab-1.0.0.jar --server.port=8088
```

首次执行需联网解析Maven依赖。打开网页或离线包直接阅读无需Java或Maven。

维护渲染：在隔离Python环境安装`Markdown==3.11`，执行`python render.py`，再执行`python package.py`更新离线与实验ZIP。源码文本变更时应同步更新manifest和metadata，并再次核对固定源码；渲染器不会替你重新研究版本行为。

## 未执行与限制

- 没有执行上游Boot/Framework全量测试，不宣称所有自动配置都覆盖。
- 没有执行GraalVM Native编译、远程数据库、真实生产流量、平台就绪探针或耗时请求的停机超时实验；这些段落给出步骤和预期。
- 没有运行完整2.7.18实验工程；两版变化来自固定源码对照，3.5.16实验验证不等同于两版所有业务迁移回归通过。
- 本次额外用Chromium实际检查390px和320px手机视口：document.scrollWidth等于视口宽度，无全页横向溢出；顶部控件为104px双行，1440px桌面仍为68px单行。ConfigData搜索状态为1/38；多次搜索前后56个代码块textContent完全一致，源码复制内容不受mark影响。手机/桌面截图已人工检查，站点发布后仍需线上验收。
- 源码外链需要网络，Maven首次解析需要网络；离线阅读正文、图、搜索和主题无需网络。
