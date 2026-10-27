# Fastjson2 / ARM64 C2 复现与证据

实验日期：2026-10-27。所有原始日志来自 ARM64 Mac 上 Colima/VZ 的原生 ARM64 Linux 容器。

本文已测试 BellSoft OpenJDK 8u202-b08、8u292-b10、8u302-b08，以及 Temurin 8u504-b01。没有测试 8u201。目标信创 CPU / JDK 发行商可能不同。

## 在自己的 ARM64 Linux 上复现

本目录保留三个用途的探针及辅助源码：

- UnsafeScaleProbe.java：无 Fastjson 依赖，定位 char 索引缩放错误；期望值按小端构造。
- LongReadProbe.java：char[] / byte[] 的 getLongLE 独立校验。
- JsonOnlyProbe.java：固定 String 的纯 JSON 解析对照，依赖 FastjsonProbe.repeat 辅助方法。
- FastjsonProbe.java：初始组合校验与样例构造。

不含第三方 JRE 或 JAR。下载 Fastjson2 2.0.61：

```sh
curl -fL https://repo.maven.apache.org/maven2/com/alibaba/fastjson2/fastjson2/2.0.61/fastjson2-2.0.61.jar -o fastjson2-2.0.61.jar
sha256sum fastjson2-2.0.61.jar
```

预期 JAR SHA256：`f3ad16c4cd2529d542b7cb7b91284e3001d1494c8391f3fab235804877bc8fa5`。

使用目标机器的 Java 和 javac：

```sh
sh run.sh /path/to/java /path/to/javac
```

也可用 PATH 中的 Java：

```sh
sh run.sh
```

run.sh 将结果写入新建的 runs-* 目录，不覆盖本文留存的 logs。出现退出码 1 是探针检测到错误的可能结果，应查看具体日志，不要将它误认为实验框架执行成功的标志。

Java 8 javac 可直接编译；其他编译器能否访问 sun.misc.Unsafe 取决于所用版本。本文测试使用相同 Java 8 字节码；新加入的独立探针使用 javac 21 -source 8 -target 8 编译。

## 实测结论

| 版本 / 模式 | 结果 |
| --- | --- |
| 8u202 默认 JIT | char[] 读取不匹配；纯 JSON 三个独立进程均失败 |
| 8u202 -Xint | 纯 JSON 30 万次通过 |
| 8u202 exclude getLongLE | 纯 JSON 300 万次通过 |
| 8u202 仅 C1 | 纯 JSON 300 万次通过 |
| BellSoft 8u292 默认 JIT | 地址缩放探针、char[] 校验和 JSON 解析均失败 |
| BellSoft 8u302 默认 JIT | 地址缩放探针 100 万次、char[] 校验 1000 万次、JSON 300 万次通过 |
| Temurin 8u504 默认 JIT | 前期 JSON 累计 3900 万次通过；新增独立探针和 JSON 对照也通过 |

补充主动编译对照（同日执行，日志在 logs/xcomp/）：8u202 使用 -Xcomp 后，在 JsonOnlyProbe 建立参考结果的首次 JSON.parse 调用中失败，尚未进入循环；独立地址探针在循环下标 1 读错。8u504 的 -Xcomp JSON 解析 300 万次、地址探针 100 万次均通过。完整参数和退出码保存在 logs/xcomp/results.json。

logs 是挑选保留的原始日志，records 包含官方 JBS 响应、修复提交元数据与运行结果。8u202 的排除组、C1、Xint 日志与默认组测试次数不同，不应直接比较其耗时。

hsdis 没有安装。print 日志可以证明 C1/C2 编译，但没有本次直接捕获的汇编指令文本。
没有自行重新构建仅增删 JDK-8267689 的 JVM，所以结论来自源码机制、官方记录和版本边界实验，不是单补丁二进制隔离实验。

## 上游来源

- https://github.com/openjdk/jdk8u/commit/3c41cd8e624173834fa7b9ee8ede148c4e5541d0
- https://bugs.openjdk.org/browse/JDK-8267689
- https://docs.bell-sw.com/liberica-jdk/8u302b8/general/release-notes/
- https://github.com/bell-sw/Liberica/releases/tag/8u202
- https://github.com/bell-sw/Liberica/releases/tag/8u292+10
- https://github.com/bell-sw/Liberica/releases/tag/8u302+8

SHA256SUMS 校验本证据包中的文件内容，不代表额外验证了 JRE 厂商签名。
