# Spring Boot源码实验室

Java17+、Maven3.6.3+。首次执行需联网解析依赖；手册离线阅读不需要这些依赖。

```sh
mvn test
mvn package
java -jar target/source-lab-1.0.0.jar --server.port=8088
curl http://127.0.0.1:8088/ping
curl http://127.0.0.1:8088/actuator/health
```

10个JUnit测试覆盖Duration绑定、绑定/约束失败、MissingBean退让、Property值条件、命令行优先级、Runner/Ready顺序、Runner失败、Profile、optional导入和MVC切片。验收状态见上级VERIFICATION.md。

Native实验另需GraalVM，可执行`mvn -Pnative native:compile`；普通JVM测试不证明Native通过。教学工程采用Apache License2.0，许可见上级apache-license.txt。
