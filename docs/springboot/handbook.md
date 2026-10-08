# Spring Boot源码学习：从启动约定到容器状态

> 源码之下，系统之上。固定Spring Boot3.5.16主线、2.7.18对照；Spring Framework6.2.19解释容器与MVC边界。先沿启动旅程理解状态，再用真实调用链验证。

[下载完整离线版](./springboot-offline.zip) · [下载实验工程](./springboot-examples.zip) · [源码许可](./apache-license.txt) · [归属与节选清单](./source-notices.txt) · [验证记录](./VERIFICATION.md)

本文不是官方文档，也不是Spring Boot全部源码的逐行翻译。图中的概念框是机制模型，带行号代码才是固定源码原文；省略的上下文请点固定SHA链接读取。本文把“源码直接可见”“官方迁移背景”“作者分析”和“实验预期”区分开：源码说明这两个版本如何工作，不自动证明所有部署环境都相同。

## 固定版本与阅读路径

| 项目 | 标签 | 固定commit | 用途 |
|---|---|---|---|
| Spring Boot | v3.5.16 | 0566f6933049aca6bc5ffc6d559fffade9cd2e0c | 主要解释 |
| Spring Boot | v2.7.18 | 0c8b382d42db22b92efcf47000d0ff9ef4971629 | 2.x比较基线 |
| Spring Framework | v6.2.19 | 6214eae8bd02c2ed7ab382bb8d16a9cc6de49522 | Boot主线BOM管理的容器/MVC版本 |

2.7.18是选定对照，不代表每个2.x版本；3.5.16也不等于每个3.x版本。本页不使用“最新”作为版本论据。Java17要求来自该标签的system-requirements文档，Servlet包名、候选导入、构造绑定等差异直接来自两版源码。

先读第1–6章，建立启动与配置顺序；第7–12章解释候选如何变成定义；第13–18章进入容器、Web与绑定；第19–23章理解运行管理、AOT、测试和迁移；第24–27章用数据源、关闭和实验复述整条链。每章按“问题→状态→调用链→失败边界→实验”组织；实验允许边读边做，不执行也能按状态推演理解。

不要把三个完成点混淆：**候选名单出现**不等于**BeanDefinition登记**，后者又不等于**Bean实例创建成功**。同样，服务器端口已经监听不等于Runner完成，也不等于部署平台已经认可Readiness。

[官方Boot3.0迁移指南](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide)解释升级背景；[3.5.16系统要求源码](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-docs/src/docs/antora/modules/ROOT/pages/system-requirements.adoc)与[依赖版本属性](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/gradle.properties)提供版本事实。


<h2 id="chapter-01">01. 先画责任边界：Boot编排，Framework执行</h2>

### 问题与设计动机

为什么读完SpringApplication仍不能解释Bean实例化？Boot解决的是应用如何以约定启动：选上下文、准备环境、加载配置、接入WebServer并发布运行事件。它把这些能力接到Spring容器，容器内部的定义解析、依赖注入、后置处理器和生命周期仍由Spring Framework实现。把两层混为一谈，会把失败发生的阶段说错。

### 字段、状态与不变量

Boot的SpringApplication持有primarySources、initializers、listeners和启动属性；Framework的AbstractApplicationContext持有beanFactory、active状态和事件广播器。Environment是两层之间共享的配置视图，BeanDefinition是配置解析的产物，Bean实例则是后续实例化的产物。三者不能互相替代。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-1"><title id="diagram-title-1">先画责任边界：Boot编排，Framework执行：关键状态推进</title><defs><marker id="arrow-1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-1)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">main：约定启动</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">Boot：准备环境/上下文</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Framework：解析定义/实例</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">Boot：Runner与就绪</text></svg><figcaption>图1 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

业务main→SpringApplication.run→prepareEnvironment→prepareContext→refreshContext→AbstractApplicationContext.refresh。refresh中的invokeBeanFactoryPostProcessors负责执行配置类解析，registerBeanPostProcessors负责把实例拦截器准备好，onRefresh让Boot的Servlet上下文创建WebServer。

[真实源码 · SpringApplication.java:301–314 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L301-L314)

```java
	public ConfigurableApplicationContext run(String... args) {
		Startup startup = Startup.create();
		if (this.properties.isRegisterShutdownHook()) {
			SpringApplication.shutdownHook.enableShutdownHookAddition();
		}
		DefaultBootstrapContext bootstrapContext = createBootstrapContext();
		ConfigurableApplicationContext context = null;
		configureHeadlessProperty();
		SpringApplicationRunListeners listeners = getRunListeners(args);
		listeners.starting(bootstrapContext, this.mainApplicationClass);
		try {
			ApplicationArguments applicationArguments = new DefaultApplicationArguments(args);
			ConfigurableEnvironment environment = prepareEnvironment(listeners, bootstrapContext, applicationArguments);
			Banner printedBanner = printBanner(environment);
```

[真实源码 · AbstractApplicationContext.java:588–612 · 6.2.19](https://github.com/spring-projects/spring-framework/blob/6214eae8bd02c2ed7ab382bb8d16a9cc6de49522/spring-context/src/main/java/org/springframework/context/support/AbstractApplicationContext.java#L588-L612)

```java
	public void refresh() throws BeansException, IllegalStateException {
		this.startupShutdownLock.lock();
		try {
			this.startupShutdownThread = Thread.currentThread();

			StartupStep contextRefresh = this.applicationStartup.start("spring.context.refresh");

			// Prepare this context for refreshing.
			prepareRefresh();

			// Tell the subclass to refresh the internal bean factory.
			ConfigurableListableBeanFactory beanFactory = obtainFreshBeanFactory();

			// Prepare the bean factory for use in this context.
			prepareBeanFactory(beanFactory);

			try {
				// Allows post-processing of the bean factory in context subclasses.
				postProcessBeanFactory(beanFactory);

				StartupStep beanPostProcess = this.applicationStartup.start("spring.context.beans.post-process");
				// Invoke factory processors registered as beans in the context.
				invokeBeanFactoryPostProcessors(beanFactory);
				// Register bean processors that intercept bean creation.
				registerBeanPostProcessors(beanFactory);
```

### 分支与失败边界

一个缺依赖的Bean可能在Framework创建实例时失败，然后被Boot的失败处理包装、分析并关闭上下文。不能因最终日志由Boot打印，就把根因归到自动配置。MVC请求分派也应继续进入Framework的DispatcherServlet，而非停在Boot的WebMvcAutoConfiguration。

### 可复现实验与观察点

先在调试器对SpringApplication.run、AbstractApplicationContext.refresh、AbstractAutowireCapableBeanFactory.initializeBean各设断点。启动第27章样例；每次停下记录当前方法、beanName及上下文active状态。预期先进入Boot，再进入Framework，Bean初始化过程中不会重复执行整条Boot启动链。

<h2 id="chapter-02">02. 启动全过程：成功不是一个瞬间</h2>

### 问题与设计动机

启动包含多个完成点。Environment完成时Bean尚未创建；refresh完成时多数非懒加载单例已初始化，嵌入式服务器也完成生命周期启动；Runner完成后才发布ready。将“Started”日志等同于业务可接流量，会忽略Runner初始化缓存、预热或校验失败的窗口。

### 字段、状态与不变量

run里的context最初为null，随后创建；Startup记录启动耗时；listeners从starting到environmentPrepared、contextPrepared、contextLoaded、started、ready逐段通知。BootstrapContext提供早期对象共享，之后close(context)交接到真正的ApplicationContext。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-2"><title id="diagram-title-2">启动全过程：成功不是一个瞬间：关键状态推进</title><defs><marker id="arrow-2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-2)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">环境完成：无业务Bean</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">refresh完成：服务器已启动</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Runner成功：预热完成</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">ready：发布就绪状态</text></svg><figcaption>图2 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

run创建DefaultBootstrapContext→listeners.starting→DefaultApplicationArguments→prepareEnvironment→printBanner→createApplicationContext→prepareContext→refreshContext→afterRefresh→listeners.started→callRunners→context.isRunning检查→listeners.ready→返回context。注意ready在第二个try块，关闭了上下文的Runner会使其跳过。

[真实源码 · SpringApplication.java:301–339 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L301-L339)

```java
	public ConfigurableApplicationContext run(String... args) {
		Startup startup = Startup.create();
		if (this.properties.isRegisterShutdownHook()) {
			SpringApplication.shutdownHook.enableShutdownHookAddition();
		}
		DefaultBootstrapContext bootstrapContext = createBootstrapContext();
		ConfigurableApplicationContext context = null;
		configureHeadlessProperty();
		SpringApplicationRunListeners listeners = getRunListeners(args);
		listeners.starting(bootstrapContext, this.mainApplicationClass);
		try {
			ApplicationArguments applicationArguments = new DefaultApplicationArguments(args);
			ConfigurableEnvironment environment = prepareEnvironment(listeners, bootstrapContext, applicationArguments);
			Banner printedBanner = printBanner(environment);
			context = createApplicationContext();
			context.setApplicationStartup(this.applicationStartup);
			prepareContext(bootstrapContext, context, environment, listeners, applicationArguments, printedBanner);
			refreshContext(context);
			afterRefresh(context, applicationArguments);
			startup.started();
			if (this.properties.isLogStartupInfo()) {
				new StartupInfoLogger(this.mainApplicationClass, environment).logStarted(getApplicationLog(), startup);
			}
			listeners.started(context, startup.timeTakenToStarted());
			callRunners(context, applicationArguments);
		}
		catch (Throwable ex) {
			throw handleRunFailure(context, ex, listeners);
		}
		try {
			if (context.isRunning()) {
				listeners.ready(context, startup.ready());
			}
		}
		catch (Throwable ex) {
			throw handleRunFailure(context, ex, null);
		}
		return context;
	}
```

### 分支与失败边界

准备环境就失败时context仍为null；refresh或Runner失败时handleRunFailure可拿到context并关闭资源。Runner主动关闭上下文与抛异常不同：前者可能使ready跳过但返回已关闭context；后者走失败链。应用监听器执行过慢也会延长启动，因为这条编排不是无条件异步。端口可在Runner之前监听；只有部署平台消费Readiness探针并按结果路由，才能阻挡未就绪流量。Ready事件本身不执行网络隔离。

### 可复现实验与观察点

将样例的ApplicationRunner加入Thread.sleep(3000)，监听ApplicationStartedEvent与ApplicationReadyEvent输出时间。预期两事件相差约3秒。再在Runner抛IllegalStateException，预期Started可能出现而Ready不出现，进程启动失败。此实验是教学步骤，本次未启动真实服务器。

<h2 id="chapter-03">03. WebApplicationType与上下文选择</h2>

### 问题与设计动机

同一套run既能启动命令行、Servlet也能启动Reactive应用，因此必须先决定上下文种类。决定因素不是类名里有没有Application，也不是项目用了异步API，而是关键类是否存在及显式配置。Servlet和Reactive都在类路径时，源码有清楚的偏向。

### 字段、状态与不变量

WebApplicationType只有NONE、SERVLET、REACTIVE。SERVLET_INDICATOR_CLASSES在3.5.16检查jakarta.servlet.Servlet与ConfigurableWebApplicationContext；WEBMVC_INDICATOR_CLASS是DispatcherServlet。SpringApplicationProperties持有最终webApplicationType，Environment绑定spring.main属性后可能覆盖初始推断。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-3"><title id="diagram-title-3">WebApplicationType与上下文选择：分支条件对照</title><defs><marker id="arrow-3" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 条件分支</text><text x="41" y="74" fill="#20324d" font-size="15">WebFlux有、MVC无：Reactive</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 条件分支</text><text x="436" y="74" fill="#20324d" font-size="15">MVC也有：继续Servlet检查</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 条件分支</text><text x="41" y="179" fill="#20324d" font-size="15">Servlet指标齐：Servlet</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 条件分支</text><text x="436" y="179" fill="#20324d" font-size="15">缺指标：NONE</text></svg><figcaption>图3 · 分支分区，四格不表示顺序执行</figcaption></figure>

### 沿真实调用链推演

构造SpringApplication时推断类路径→prepareEnvironment绑定spring.main→deduceEnvironmentClass→ApplicationContextFactory.create按最终类型选择上下文。在WebFlux存在且MVC和Jersey都不存在时选REACTIVE；否则Servlet指标有任一缺失就NONE；齐全才SERVLET。

[真实源码 · WebApplicationType.java:60–72 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/WebApplicationType.java#L60-L72)

```java
	static WebApplicationType deduceFromClasspath() {
		if (ClassUtils.isPresent(WEBFLUX_INDICATOR_CLASS, null) && !ClassUtils.isPresent(WEBMVC_INDICATOR_CLASS, null)
				&& !ClassUtils.isPresent(JERSEY_INDICATOR_CLASS, null)) {
			return WebApplicationType.REACTIVE;
		}
		for (String className : SERVLET_INDICATOR_CLASSES) {
			if (!ClassUtils.isPresent(className, null)) {
				return WebApplicationType.NONE;
			}
		}
		return WebApplicationType.SERVLET;
	}

```

[真实源码 · WebApplicationType.java:48–49 · 2.7.18](https://github.com/spring-projects/spring-boot/blob/0c8b382d42db22b92efcf47000d0ff9ef4971629/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/WebApplicationType.java#L48-L49)

```java
	private static final String[] SERVLET_INDICATOR_CLASSES = { "javax.servlet.Servlet",
			"org.springframework.web.context.ConfigurableWebApplicationContext" };
```

### 分支与失败边界

误加spring-boot-starter-web可能使WebFlux项目选到Servlet。反过来强制SERVLET但没有ServletWebServerFactory会启动失败，而不是自动降级到NONE。关闭Web类型适合批处理，但Web控制器与服务器相关条件也会退场。

### 两版对照的依据

2.7.18的Servlet指标是javax.servlet.Servlet；3.5.16改成jakarta.servlet.Servlet。推断算法的核心结构保留，包名迁移并不意味着算法变成“Reactive优先”。

### 可复现实验与观察点

使用样例运行--spring.main.web-application-type=none，观察没有端口监听；删除参数再运行应启动Servlet。若引入starter-webflux但保留starter-web，断点deduceFromClasspath检查MVC指标仍在，预期SERVLET。

<h2 id="chapter-04">04. Environment：优先级是有序源，不是覆盖文件</h2>

### 问题与设计动机

同一个demo.message可能来自默认值、文件、环境变量或命令行。Boot没有先把这些全部合并成一个最终Map；它保存多个PropertySource，读取时按顺序查找第一个非null值。因此排障要同时问“哪些源存在”与“它们的顺序是什么”。

### 字段、状态与不变量

MutablePropertySources维护有序列表；SimpleCommandLinePropertySource处理--key=value；defaultProperties由DefaultPropertiesPropertySource放到低优先级。Framework的PropertySourcesPropertyResolver保存propertySources并在getProperty循环查找。配置名归一化/环境变量适配与值转换则是另一层职责。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-4"><title id="diagram-title-4">Environment：优先级是有序源，不是覆盖文件：关键状态推进</title><defs><marker id="arrow-4" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-4)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">命令行命中：立即返回</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">未命中→系统/环境</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">再查ConfigData</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">默认值兜底</text></svg><figcaption>图4 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

prepareEnvironment→configureEnvironment→configurePropertySources：默认源addOrMerge，命令行源addFirst；environmentPrepared阶段加入ConfigData；默认源moveToEnd。Framework getProperty从前向后找命中的源并转换类型。这里给出的常见优先级是命令行＞系统属性＞系统环境＞ConfigData＞程序默认值，Servlet/JNDI/JSON/测试注入会插入额外源，不能把简表当完整所有场景表。

[真实源码 · SpringApplication.java:507–527 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L507-L527)

```java
	protected void configurePropertySources(ConfigurableEnvironment environment, String[] args) {
		MutablePropertySources sources = environment.getPropertySources();
		if (!CollectionUtils.isEmpty(this.defaultProperties)) {
			DefaultPropertiesPropertySource.addOrMerge(this.defaultProperties, sources);
		}
		if (this.addCommandLineProperties && args.length > 0) {
			String name = CommandLinePropertySource.COMMAND_LINE_PROPERTY_SOURCE_NAME;
			if (sources.contains(name)) {
				PropertySource<?> source = sources.get(name);
				CompositePropertySource composite = new CompositePropertySource(name);
				composite
					.addPropertySource(new SimpleCommandLinePropertySource("springApplicationCommandLineArgs", args));
				composite.addPropertySource(source);
				sources.replace(name, composite);
			}
			else {
				sources.addFirst(new SimpleCommandLinePropertySource(args));
			}
		}
		environment.getPropertySources().addLast(new ApplicationInfoPropertySource(this.mainApplicationClass));
	}
```

[真实源码 · PropertySourcesPropertyResolver.java:78–98 · 6.2.19](https://github.com/spring-projects/spring-framework/blob/6214eae8bd02c2ed7ab382bb8d16a9cc6de49522/spring-core/src/main/java/org/springframework/core/env/PropertySourcesPropertyResolver.java#L78-L98)

```java
	protected <T> T getProperty(String key, Class<T> targetValueType, boolean resolveNestedPlaceholders) {
		if (this.propertySources != null) {
			for (PropertySource<?> propertySource : this.propertySources) {
				if (logger.isTraceEnabled()) {
					logger.trace("Searching for key '" + key + "' in PropertySource '" +
							propertySource.getName() + "'");
				}
				Object value = propertySource.getProperty(key);
				if (value != null) {
					if (resolveNestedPlaceholders) {
						if (value instanceof String string) {
							value = resolveNestedPlaceholders(string);
						}
						else if ((value instanceof CharSequence cs) && (String.class.equals(targetValueType) ||
								CharSequence.class.equals(targetValueType))) {
							value = resolveNestedPlaceholders(cs.toString());
						}
					}
					logKeyFound(key, propertySource, value);
					return convertValueIfNecessary(value, targetValueType);
				}
```

### 分支与失败边界

@PropertySource配置类要等refresh解析后才加入，对早期logging.*和spring.main.*可能太晚。addCommandLineProperties=false会取消命令行插入；测试属性源可能排在生产参数之前。所谓“外部文件优先”也要看location分组、profile和import，不能只比较文件路径。

### 可复现实验与观察点

样例application.properties写demo.message=file，运行DEMO_MESSAGE=env java -Ddemo.message=sys -jar target/source-lab-1.0.0.jar --demo.message=cli，Runner应打印cli。依次删除cli、-D、环境变量，再观察sys→env→file；每一步打印environment.getPropertySources()的名称。

<h2 id="chapter-05">05. ConfigData：为什么先无Profile再有Profile</h2>

### 问题与设计动机

application-dev.properties是否应被读取，取决于active profiles；active profiles本身又可能定义在普通配置中。这是一个依赖关系，所以ConfigData分阶段处理。它不是扫目录之后无脑按文件名拼接。先收集初始导入，再建立激活上下文，处理非Profile贡献，最后使用已确定Profile补充加载。

### 字段、状态与不变量

ConfigDataEnvironment的contributors描述候选来源及激活状态；ConfigDataActivationContext保存cloud platform与Profiles。ConfigDataImporter跟踪loaded资源、loadedLocations和optionalLocations，避免同一资源被反复导入。BinderOption.FAIL_ON_BIND_TO_INACTIVE_SOURCE防止从未激活贡献里偷取决定性配置。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-5"><title id="diagram-title-5">ConfigData：为什么先无Profile再有Profile：关键状态推进</title><defs><marker id="arrow-5" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-5)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">初始贡献：尚无激活上下文</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">普通文档：确定Profiles</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Profile文档：按激活筛选</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">活跃源：应用到Environment</text></svg><figcaption>图5 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

ConfigDataEnvironmentPostProcessor.postProcessEnvironment→getConfigDataEnvironment→processAndApply→processInitial→createActivationContext→processWithoutProfiles→withProfiles→processWithProfiles→applyToEnvironment。最终才将活跃贡献的PropertySource放入实际Environment。

[真实源码 · ConfigDataEnvironment.java:234–246 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/config/ConfigDataEnvironment.java#L234-L246)

```java
	void processAndApply() {
		ConfigDataImporter importer = new ConfigDataImporter(this.logFactory, this.notFoundAction, this.resolvers,
				this.loaders);
		registerBootstrapBinder(this.contributors, null, DENY_INACTIVE_BINDING);
		ConfigDataEnvironmentContributors contributors = processInitial(this.contributors, importer);
		ConfigDataActivationContext activationContext = createActivationContext(
				contributors.getBinder(null, BinderOption.FAIL_ON_BIND_TO_INACTIVE_SOURCE));
		contributors = processWithoutProfiles(contributors, importer, activationContext);
		activationContext = withProfiles(contributors, activationContext);
		contributors = processWithProfiles(contributors, importer, activationContext);
		applyToEnvironment(contributors, activationContext, importer.getLoadedLocations(),
				importer.getOptionalLocations());
	}
```

[真实源码 · ConfigDataEnvironmentPostProcessor.java:88–97 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/config/ConfigDataEnvironmentPostProcessor.java#L88-L97)

```java
	public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
		postProcessEnvironment(environment, application.getResourceLoader(), application.getAdditionalProfiles());
	}

	void postProcessEnvironment(ConfigurableEnvironment environment, ResourceLoader resourceLoader,
			Collection<String> additionalProfiles) {
		this.logger.trace("Post-processing environment to add config data");
		resourceLoader = (resourceLoader != null) ? resourceLoader : new DefaultResourceLoader();
		getConfigDataEnvironment(environment, resourceLoader, additionalProfiles).processAndApply();
	}
```

### 分支与失败边界

非活跃文档里的值不能拿来影响自身激活条件。Profile特定文档不能随意声明spring.profiles.active/include形成自我激活；源码通过InvalidConfigDataPropertyException等分支阻止无效配置。用spring.config.location替换默认位置与additional-location追加默认位置，是不同语义。

### 两版对照的依据

ConfigData在2.4时代已经出现，2.7.18也有processAndApply与分阶段Profile处理；不能把spring.config.import说成3.x才引入。

### 可复现实验与观察点

在application.properties写spring.profiles.active=dev和demo.message=base，application-dev.properties写demo.message=dev，预期打印dev。将active声明移入spring.config.activate.on-profile=dev控制的文档并检查启动错误。打开logging.level.org.springframework.boot.context.config=TRACE观察分阶段处理。

<h2 id="chapter-06">06. ConfigData导入：Location、Resource与可选失败</h2>

### 问题与设计动机

配置导入需要支持file、classpath、configtree及插件扩展。抽象分成LocationResolver与Loader：前者把位置变成可加载资源，后者把资源变成ConfigData。这让“定位失败”与“读取失败”有不同诊断，也让Profile资源解析与基础资源解析可以复用协议。

### 字段、状态与不变量

ConfigDataLocation携带optional语义；ConfigDataResource是资源身份；ConfigDataResolutionResult携带解析结果。Importer的loaded集合按资源去重，optionalLocations记录缺失可忽略的位置。扩展通过早期BootstrapContext获得所需服务，不能依赖尚不存在的普通业务Bean。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-6"><title id="diagram-title-6">ConfigData导入：Location、Resource与可选失败：关键状态推进</title><defs><marker id="arrow-6" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-6)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">Location：协议/optional</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">Resolver：定位Resource</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Loader：读取PropertySource</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">去重记账→贡献树</text></svg><figcaption>图6 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

resolveAndLoad读取activationContext profiles→resolve遍历locations→resolvers解析→load调用loaders→记账并返回Map。IO异常转换成IllegalStateException附带导入位置；缺失资源由ConfigDataNotFoundAction与optional分支判定是否抛出。

[真实源码 · ConfigDataImporter.java:81–92 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/config/ConfigDataImporter.java#L81-L92)

```java
	Map<ConfigDataResolutionResult, ConfigData> resolveAndLoad(ConfigDataActivationContext activationContext,
			ConfigDataLocationResolverContext locationResolverContext, ConfigDataLoaderContext loaderContext,
			List<ConfigDataLocation> locations) {
		try {
			Profiles profiles = (activationContext != null) ? activationContext.getProfiles() : null;
			List<ConfigDataResolutionResult> resolved = resolve(locationResolverContext, profiles, locations);
			return load(loaderContext, resolved);
		}
		catch (IOException ex) {
			throw new IllegalStateException("IO error on loading imports from " + locations, ex);
		}
	}
```

[真实源码 · ConfigDataImporter.java:51–55 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/config/ConfigDataImporter.java#L51-L55)

```java
	private final Set<ConfigDataResource> loaded = new HashSet<>();

	private final Set<ConfigDataLocation> loadedLocations = new HashSet<>();

	private final Set<ConfigDataLocation> optionalLocations = new HashSet<>();
```

### 分支与失败边界

optional:只声明允许资源不存在，并不保证语法错误、认证失败或任意IOException都被吞掉。重复资源按身份去重也不等于任意字符串地址都能识别同一个远程内容。实现自定义Loader时必须定义资源equals/hashCode，否则导入重复判断可能失效。

### 可复现实验与观察点

给样例传--spring.config.import=file:./missing.properties，预期因缺失配置启动失败；改为optional:file:./missing.properties，预期继续启动。再创建一个非法YAML文档并optional导入，观察解析错误仍失败。删除参数恢复默认配置，避免实验文件污染后续。

<h2 id="chapter-07">07. 自动配置候选：从注解走到imports资源</h2>

### 问题与设计动机

@SpringBootApplication包含@EnableAutoConfiguration，但候选类不是靠扫描整个第三方包找到的。自动配置是第三方显式登记的候选清单，常规组件扫描只处理业务指定包。这个区分解释了为什么一个jar在类路径上，仍可能完全没有参与自动配置。

### 字段、状态与不变量

AutoConfigurationImportSelector保存autoConfigurationAnnotation与ClassLoader；ImportCandidates定位META-INF/spring/<注解全名>.imports并逐行读取、去注释、去空白。候选是类名字符串，先拿名单再筛选，不等于所有类立即实例化。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-7"><title id="diagram-title-7">自动配置候选：从注解走到imports资源：关键状态推进</title><defs><marker id="arrow-7" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-7)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">业务注解：启用选择器</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">多个jar的imports：汇总</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">类名候选：尚无Bean</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">过滤/排序后进入解析</text></svg><figcaption>图7 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

@EnableAutoConfiguration的@Import→DeferredImportSelector→getAutoConfigurationEntry→getCandidateConfigurations→ImportCandidates.load→ClassLoader.getResources遍历多个jar→读取类名。候选随后去重、排除、过滤，再进入配置解析。

[真实源码 · AutoConfigurationImportSelector.java:195–206 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/AutoConfigurationImportSelector.java#L195-L206)

```java
	protected List<String> getCandidateConfigurations(AnnotationMetadata metadata, AnnotationAttributes attributes) {
		ImportCandidates importCandidates = ImportCandidates.load(this.autoConfigurationAnnotation,
				getBeanClassLoader());
		List<String> configurations = importCandidates.getCandidates();
		Assert.state(!CollectionUtils.isEmpty(configurations),
				"No auto configuration classes found in " + "META-INF/spring/"
						+ this.autoConfigurationAnnotation.getName() + ".imports. If you "
						+ "are using a custom packaging, make sure that file is correct.");
		return configurations;
	}

	private void checkExcludedClasses(List<String> configurations, Set<String> exclusions) {
```

[真实源码 · ImportCandidates.java:108–124 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/annotation/ImportCandidates.java#L108-L124)

```java
	private static List<String> readCandidateConfigurations(URL url) {
		try (BufferedReader reader = new BufferedReader(
				new InputStreamReader(new UrlResource(url).getInputStream(), StandardCharsets.UTF_8))) {
			List<String> candidates = new ArrayList<>();
			String line;
			while ((line = reader.readLine()) != null) {
				line = stripComment(line);
				line = line.trim();
				if (line.isEmpty()) {
					continue;
				}
				candidates.add(line);
			}
			return candidates;
		}
		catch (IOException ex) {
			throw new IllegalArgumentException("Unable to load configurations from location [" + url + "]", ex);
```

### 分支与失败边界

Shade或自定义打包若覆盖而非合并imports资源，会丢第三方候选。候选非空只证明找到了清单；类不存在或缺传递依赖仍可能在后续失败。不要通过扩大@ComponentScan去“修复”丢失的自动配置注册，这会绕开预期处理时序。

### 两版对照的依据

2.7.18同时调用SpringFactoriesLoader.loadFactoryNames与ImportCandidates.load；3.5.16候选注册读取imports。spring.factories仍服务其他扩展，例如FailureAnalyzer和EnvironmentPostProcessor，不能从自动配置迁移推断整个文件被移除。

### 可复现实验与观察点

解压一个starter相关autoconfigure jar，检查META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports。创建本章自定义自动配置后，分别把它登记到imports与只登记到spring.factories；在3.5.16下预期只有imports路径使它被自动导入。

<h2 id="chapter-08">08. 候选筛选：排除和条件的两个层次</h2>

### 问题与设计动机

候选清单很大，加载所有配置类再判断昂贵且可能触发缺类错误。选择器首先做名字级去重/排除及ImportFilter批量筛选；Framework解析配置时再执行注解条件。两层条件共同决定结果，名单过滤通过不等于@Bean必然注册。

### 字段、状态与不变量

AutoConfigurationEntry保存configurations与exclusions；ConfigurationClassFilter保存filters与autoConfigurationMetadata。条件结果是ConditionOutcome，包含match布尔值与解释信息，报告按source归档。排除集合可以来自注解exclude、excludeName或spring.autoconfigure.exclude。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-8"><title id="diagram-title-8">候选筛选：排除和条件的两个层次：关键状态推进</title><defs><marker id="arrow-8" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-8)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">清单：所有候选</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">去重/显式排除</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">元数据过滤：缺类退出</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">配置/方法条件：最终定义</text></svg><figcaption>图8 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

getAutoConfigurationEntry：isEnabled→attributes→候选→removeDuplicates→getExclusions→checkExcludedClasses→removeAll→getConfigurationClassFilter.filter→fireAutoConfigurationImportEvents。后续Framework配置解析仍评估ConfigurationCondition及@Bean方法上的条件。

[真实源码 · AutoConfigurationImportSelector.java:137–151 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/AutoConfigurationImportSelector.java#L137-L151)

```java
	protected AutoConfigurationEntry getAutoConfigurationEntry(AnnotationMetadata annotationMetadata) {
		if (!isEnabled(annotationMetadata)) {
			return EMPTY_ENTRY;
		}
		AnnotationAttributes attributes = getAttributes(annotationMetadata);
		List<String> configurations = getCandidateConfigurations(annotationMetadata, attributes);
		configurations = removeDuplicates(configurations);
		Set<String> exclusions = getExclusions(annotationMetadata, attributes);
		checkExcludedClasses(configurations, exclusions);
		configurations.removeAll(exclusions);
		configurations = getConfigurationClassFilter().filter(configurations);
		fireAutoConfigurationImportEvents(configurations, exclusions);
		return new AutoConfigurationEntry(configurations, exclusions);
	}

```

### 分支与失败边界

排除存在但不属于自动配置候选的类会触发invalid excludes检查；拼错一个不存在的类名与排除存在的普通配置类不是同一分支。配置类整体条件通过，内部@Bean仍可因MissingBean或Property条件不匹配而缺失。

### 可复现实验与观察点

运行样例--debug，找到Positive matches与Negative matches。用--spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration排除MVC默认配置，比较报告；把exclude改为一个存在的普通业务配置类，预期得到无效排除诊断。

<h2 id="chapter-09">09. OnClassCondition：元数据与加载隔离</h2>

### 问题与设计动机

如果可选依赖不存在，首先要避免JVM在读方法签名时就解析它。类条件用字符串/ASM元数据判断类是否存在，过滤掉不满足条件的配置；但这不保证放在任意位置的@ConditionalOnClass都能阻止JVM提前加载签名类型。设计starter时要把可选依赖隔离在嵌套配置类。

### 字段、状态与不变量

OnClassCondition对候选返回ConditionOutcome数组，null结果表示这层没有否定它；真正类存在性判断使用指定ClassLoader。autoConfigurationMetadata保存处理器生成的条件类型信息，批量判断避免每个候选都进行完整配置解析。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-9"><title id="diagram-title-9">OnClassCondition：元数据与加载隔离：关键状态推进</title><defs><marker id="arrow-9" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-9)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">候选类名：未加载</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">元数据：所需类型名</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">ClassLoader存在性判断</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">缺类→noMatch；有类→继续</text></svg><figcaption>图9 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

ConfigurationClassFilter→OnClassCondition.getOutcomes→按处理器数选择单线程或一个后台线程→StandardOutcomesResolver检查required classes→缺类返回noMatch。Framework阶段getMatchOutcome再读取实际注解属性。该并行是候选检查优化，不能据此声称Bean创建全部并行。

[真实源码 · OnClassCondition.java:47–60 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/condition/OnClassCondition.java#L47-L60)

```java
	protected final ConditionOutcome[] getOutcomes(String[] autoConfigurationClasses,
			AutoConfigurationMetadata autoConfigurationMetadata) {
		// Split the work and perform half in a background thread if more than one
		// processor is available. Using a single additional thread seems to offer the
		// best performance. More threads make things worse.
		if (autoConfigurationClasses.length > 1 && Runtime.getRuntime().availableProcessors() > 1) {
			return resolveOutcomesThreaded(autoConfigurationClasses, autoConfigurationMetadata);
		}
		else {
			OutcomesResolver outcomesResolver = new StandardOutcomesResolver(autoConfigurationClasses, 0,
					autoConfigurationClasses.length, autoConfigurationMetadata, getBeanClassLoader());
			return outcomesResolver.resolveOutcomes();
		}
	}
```

### 分支与失败边界

在@Bean方法直接返回OptionalLibrary类型，即便方法带条件也可能过早触发类解析。稳妥结构是在单独@Configuration上加@ConditionalOnClass，把可选Bean方法放进去。类“存在”也不保证二进制版本兼容，NoSuchMethodError是另一个问题。

### 可复现实验与观察点

用spring-boot-test的ApplicationContextRunner配合FilteredClassLoader隐藏一个可选库类型，再载入对应自动配置。预期相关Bean不存在且报告显示缺类；移除过滤后恢复。此测试只验证类条件，不验证远程服务是否可用。

<h2 id="chapter-10">10. OnBeanCondition：退让与解析时序</h2>

### 问题与设计动机

自动配置通常提供默认实现，用户自己定义同类型Bean时默认实现应退让。@ConditionalOnMissingBean不是运行时每次调用都检查，也不是启动结束后扫描一次所有实例，而是在REGISTER_BEAN阶段根据当时可见的定义/类型判断。因此排序与搜索范围是语义的一部分。

### 字段、状态与不变量

OnBeanCondition的Spec保存names、types、annotations、search strategy及ignored类型；MatchResult区分匹配与未匹配。Bean条件会考虑候选定义、FactoryBean类型及默认候选等细节；BeanDefinition的返回类型如果过度泛化，会削弱可判断性。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-10"><title id="diagram-title-10">OnBeanCondition：退让与解析时序：分支条件对照</title><defs><marker id="arrow-10" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 条件分支</text><text x="41" y="74" fill="#20324d" font-size="15">用户BeanDefinition先登记</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 条件分支</text><text x="436" y="74" fill="#20324d" font-size="15">REGISTER_BEAN查询类型</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 条件分支</text><text x="41" y="179" fill="#20324d" font-size="15">已存在：默认Bean退让</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 条件分支</text><text x="436" y="179" fill="#20324d" font-size="15">不存在：登记默认实现</text></svg><figcaption>图10 · 分支分区，四格不表示顺序执行</figcaption></figure>

### 沿真实调用链推演

Framework解析配置→OnBeanCondition.getConfigurationPhase返回REGISTER_BEAN→getMatchOutcome处理ConditionalOnBean、SingleCandidate、MissingBean→查询BeanFactory可见候选→匹配结果决定是否登记BeanDefinition。默认配置放在用户配置之后，减少“未来Bean尚不可见”的问题。

[真实源码 · OnBeanCondition.java:88–90 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/condition/OnBeanCondition.java#L88-L90)

```java
	public ConfigurationPhase getConfigurationPhase() {
		return ConfigurationPhase.REGISTER_BEAN;
	}
```

[真实源码 · OnBeanCondition.java:123–145 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/condition/OnBeanCondition.java#L123-L145)

```java
	public ConditionOutcome getMatchOutcome(ConditionContext context, AnnotatedTypeMetadata metadata) {
		ConditionOutcome matchOutcome = ConditionOutcome.match();
		MergedAnnotations annotations = metadata.getAnnotations();
		if (annotations.isPresent(ConditionalOnBean.class)) {
			Spec<ConditionalOnBean> spec = new Spec<>(context, metadata, annotations, ConditionalOnBean.class);
			matchOutcome = evaluateConditionalOnBean(spec, matchOutcome.getConditionMessage());
			if (!matchOutcome.isMatch()) {
				return matchOutcome;
			}
		}
		if (metadata.isAnnotated(ConditionalOnSingleCandidate.class.getName())) {
			Spec<ConditionalOnSingleCandidate> spec = new SingleCandidateSpec(context, metadata,
					metadata.getAnnotations());
			matchOutcome = evaluateConditionalOnSingleCandidate(spec, matchOutcome.getConditionMessage());
			if (!matchOutcome.isMatch()) {
				return matchOutcome;
			}
		}
		if (metadata.isAnnotated(ConditionalOnMissingBean.class.getName())) {
			Spec<ConditionalOnMissingBean> spec = new Spec<>(context, metadata, annotations,
					ConditionalOnMissingBean.class);
			matchOutcome = evaluateConditionalOnMissingBean(spec, matchOutcome.getConditionMessage());
			if (!matchOutcome.isMatch()) {
```

### 分支与失败边界

给@Bean返回Object而实际new某接口实现，条件阶段可能无法像你预期那样推断类型。多个同类型候选时SingleCandidate涉及primary/default候选判断；MissingBean不是“任意同名实例覆盖”。启用allow-bean-definition-overriding也不会改变条件匹配的基本含义。

### 可复现实验与观察点

编写ApplicationContextRunner加载一个带@ConditionalOnMissingBean(Greeting.class)的自动配置。无用户配置应得到默认Greeting；withUserConfiguration提供Greeting后应得到用户实例且默认Bean名不存在。断点getConfigurationPhase证实不是请求到来时才评估。

<h2 id="chapter-11">11. OnPropertyCondition：false、缺失和havingValue</h2>

### 问题与设计动机

一个开关在未配置时是否启用，是API契约。@ConditionalOnProperty默认匹配“存在且不等于false”的字符串，而不自动执行你想象的业务布尔转换；havingValue指定后进行大小写不敏感比较，缺失则由matchIfMissing决定。读取条件表比凭名字猜更可靠。

### 字段、状态与不变量

Spec保存prefix、names、havingValue、matchIfMissing。collectProperties分别收集missing和nonMatching，多个names要求都满足。prefix会规范到带分隔符形式；PropertyResolver负责实际值来源，因此本条件服从Environment顺序。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-11"><title id="diagram-title-11">OnPropertyCondition：false、缺失和havingValue：分支条件对照</title><defs><marker id="arrow-11" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 条件分支</text><text x="41" y="74" fill="#20324d" font-size="15">属性不存在：看matchIfMissing</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 条件分支</text><text x="436" y="74" fill="#20324d" font-size="15">存在：比较havingValue</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 条件分支</text><text x="41" y="179" fill="#20324d" font-size="15">未指定havingValue：排除false</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 条件分支</text><text x="436" y="179" fill="#20324d" font-size="15">任一失败→配置不登记</text></svg><figcaption>图11 · 分支分区，四格不表示顺序执行</figcaption></figure>

### 沿真实调用链推演

getMatchOutcome→确定annotation Spec→collectProperties→containsProperty→isMatch(value,havingValue)；缺失且matchIfMissing=false进入missing，存在但不符合值进入nonMatching；两者都空才match。条件结果携带具体哪些属性失败的说明。

[真实源码 · OnPropertyCondition.java:156–171 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/condition/OnPropertyCondition.java#L156-L171)

```java
		private void collectProperties(PropertyResolver resolver, List<String> missing, List<String> nonMatching) {
			for (String name : this.names) {
				String key = this.prefix + name;
				if (resolver.containsProperty(key)) {
					if (!isMatch(resolver.getProperty(key), this.havingValue)) {
						nonMatching.add(name);
					}
				}
				else {
					if (!this.matchIfMissing) {
						missing.add(name);
					}
				}
			}
		}

```

[真实源码 · OnPropertyCondition.java:172–177 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/condition/OnPropertyCondition.java#L172-L177)

```java
		private boolean isMatch(String value, String requiredValue) {
			if (StringUtils.hasLength(requiredValue)) {
				return requiredValue.equalsIgnoreCase(value);
			}
			return !"false".equalsIgnoreCase(value);
		}
```

### 分支与失败边界

没指定havingValue时demo.enabled=abc仍可能匹配；所以真正布尔配置应明确契约或使用布尔条件注解。集合索引如demo.list[0]不是demo.list本身存在的普遍保证，Property条件不适合判断集合是否非空。多个name是AND，不是OR。

### 可复现实验与观察点

自定义自动配置用@ConditionalOnProperty(prefix="demo",name="enabled",havingValue="true",matchIfMissing=false)。分别用withPropertyValues测缺失、false、TRUE、abc，预期只有TRUE匹配；删havingValue后abc可匹配。将结果与源码isMatch逐项对照。

<h2 id="chapter-12">12. 自动配置排序：定义顺序与实例顺序分开</h2>

### 问题与设计动机

B的MissingBean条件必须看到A提供的定义，于是候选配置需要确定顺序。但排序不是Bean实例化调度表，也不保证外部服务启动顺序。实例的依赖关系、DependsOn和生命周期phase由Framework处理。理解这个区分可以避免把AutoConfigureAfter当业务初始化屏障。

### 字段、状态与不变量

AutoConfigurationSorter先建立AutoConfigurationClasses元数据索引；顺序由order数值及before/after依赖关系共同决定。AutoConfigurationGroup收集各选择器条目后统一排序，避免某一局部imports清单顺序误导全局结果。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-12"><title id="diagram-title-12">自动配置排序：定义顺序与实例顺序分开：关键状态推进</title><defs><marker id="arrow-12" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-12)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">候选去重：稳定名单</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">order排序：数值优先</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">before/after：关系约束</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">定义顺序≠实例启动屏障</text></svg><figcaption>图12 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

AutoConfigurationGroup.selectImports→合并exclusions→sortAutoConfigurations→AutoConfigurationSorter.getInPriorityOrder：先字母序稳定化，再order值，再尊重AutoConfigureBefore/After。配置类解析按该结果推进，随后Bean实例化仍按容器依赖规则执行。

[真实源码 · AutoConfigurationSorter.java:62–79 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/AutoConfigurationSorter.java#L62-L79)

```java
	List<String> getInPriorityOrder(Collection<String> classNames) {
		// Initially sort alphabetically
		List<String> alphabeticallyOrderedClassNames = new ArrayList<>(classNames);
		Collections.sort(alphabeticallyOrderedClassNames);
		// Then sort by order
		AutoConfigurationClasses classes = new AutoConfigurationClasses(this.metadataReaderFactory,
				this.autoConfigurationMetadata, alphabeticallyOrderedClassNames);
		List<String> orderedClassNames = new ArrayList<>(classNames);
		Collections.sort(orderedClassNames);
		orderedClassNames.sort((o1, o2) -> {
			int i1 = classes.get(o1).getOrder();
			int i2 = classes.get(o2).getOrder();
			return Integer.compare(i1, i2);
		});
		// Then respect @AutoConfigureBefore @AutoConfigureAfter
		orderedClassNames = sortByAnnotation(classes, orderedClassNames);
		return orderedClassNames;
	}
```

### 分支与失败边界

相互before/after形成循环会导致排序失败，属于配置依赖图错误。即使A配置在B之前，A里的懒加载Bean也可能直到业务调用才实例化。若B必须使用A实例，应声明真实构造依赖，而不是仅排序配置。

### 可复现实验与观察点

创建A、B两个@AutoConfiguration，在B中用ConditionalOnBean(AService.class)，先不声明after，再给B添加@AutoConfiguration(after=A.class)。用ApplicationContextRunner记录是否登记B；最后将AService设@Lazy并观察排序不等于立即初始化。

<h2 id="chapter-13">13. Bean生命周期：从定义到初始化与代理</h2>

### 问题与设计动机

自动配置完成后得到的是定义，生命周期把定义变成可用对象。实例化、依赖填充、Aware回调、before initialization、初始化回调、after initialization不是同一个阶段。AOP代理通常在后置处理器阶段产生，Boot并不自己重写所有Bean创建。

### 字段、状态与不变量

AbstractAutowireCapableBeanFactory.initializeBean局部wrappedBean可以从原始实例变成后置处理器返回的包装对象；RootBeanDefinition记录初始化方法等元数据。Boot的prepareContext设置allowCircularReferences/allowBeanDefinitionOverriding及懒初始化处理器，影响Framework策略而非替代它。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-13"><title id="diagram-title-13">Bean生命周期：从定义到初始化与代理：关键状态推进</title><defs><marker id="arrow-13" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-13)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">BeanDefinition：配方</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">实例化/填充：原始对象</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Aware/初始化：回调</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">after初始化：可能返回代理</text></svg><figcaption>图13 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

Framework createBean→doCreateBean→createBeanInstance→populateBean→initializeBean→invokeAwareMethods→applyBeanPostProcessorsBeforeInitialization→invokeInitMethods→applyBeanPostProcessorsAfterInitialization→返回wrappedBean。ConfigurationProperties绑定就在before initialization阶段之一。

[真实源码 · AbstractAutowireCapableBeanFactory.java:1811–1831 · 6.2.19](https://github.com/spring-projects/spring-framework/blob/6214eae8bd02c2ed7ab382bb8d16a9cc6de49522/spring-beans/src/main/java/org/springframework/beans/factory/support/AbstractAutowireCapableBeanFactory.java#L1811-L1831)

```java
	protected Object initializeBean(String beanName, Object bean, @Nullable RootBeanDefinition mbd) {
		invokeAwareMethods(beanName, bean);

		Object wrappedBean = bean;
		if (mbd == null || !mbd.isSynthetic()) {
			wrappedBean = applyBeanPostProcessorsBeforeInitialization(wrappedBean, beanName);
		}

		try {
			invokeInitMethods(beanName, wrappedBean, mbd);
		}
		catch (Throwable ex) {
			throw new BeanCreationException(
					(mbd != null ? mbd.getResourceDescription() : null), beanName, ex.getMessage(), ex);
		}
		if (mbd == null || !mbd.isSynthetic()) {
			wrappedBean = applyBeanPostProcessorsAfterInitialization(wrappedBean, beanName);
		}

		return wrappedBean;
	}
```

[真实源码 · SpringApplication.java:397–404 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L397-L404)

```java
		if (beanFactory instanceof AbstractAutowireCapableBeanFactory autowireCapableBeanFactory) {
			autowireCapableBeanFactory.setAllowCircularReferences(this.properties.isAllowCircularReferences());
			if (beanFactory instanceof DefaultListableBeanFactory listableBeanFactory) {
				listableBeanFactory.setAllowBeanDefinitionOverriding(this.properties.isAllowBeanDefinitionOverriding());
			}
		}
		if (this.properties.isLazyInitialization()) {
			context.addBeanFactoryPostProcessor(new LazyInitializationBeanFactoryPostProcessor());
```

### 分支与失败边界

构造循环无法仅靠早期引用解决；setter循环也受allowCircularReferences、作用域、代理等限制。初始化方法抛异常包装BeanCreationException并使非懒单例启动失败。懒加载只把失败推迟到首次访问，不等于修复依赖。循环引用默认禁用已在2.6时代发生，不能归为3.x专属改变。

### 可复现实验与观察点

样例加入实现BeanNameAware与InitializingBean的组件及自定义BeanPostProcessor，输出beanName和阶段；构造器→Aware→before→afterPropertiesSet→after是应观察的关键顺序。再在afterPropertiesSet抛错，定位BeanCreationException的根cause。

<h2 id="chapter-14">14. Servlet上下文：创建服务器与启动服务器</h2>

### 问题与设计动机

容器refresh需要创建WebServer，也需要让Servlet注册到ServletContext；真正对外启动则通过SmartLifecycle交接。将getWebServer当成唯一启动点，会忽略后面的WebServerStartStopLifecycle与初始化事件。外部WAR容器已有ServletContext时还走另一条路径。

### 字段、状态与不变量

ServletWebServerApplicationContext的webServer字段最初null，servletContext可能来自外部容器。createWebServer仅在两者都null时找ServletWebServerFactory，创建webServer并注册webServerGracefulShutdown与webServerStartStop单例。已有servletContext则执行selfInitializer而不创建嵌入式服务器。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-14"><title id="diagram-title-14">Servlet上下文：创建服务器与启动服务器：关键状态推进</title><defs><marker id="arrow-14" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-14)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">无ServletContext：嵌入式路径</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">factory.getWebServer：构建对象</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Lifecycle.start：开放连接</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">有ServletContext：外部WAR注册</text></svg><figcaption>图14 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

Framework refresh.onRefresh→Boot createWebServer→getWebServerFactory→factory.getWebServer(getSelfInitializer)→注册生命周期Bean；Framework finishRefresh启动LifecycleProcessor→WebServerStartStopLifecycle.start→webServer.start→发布ServletWebServerInitializedEvent。

[真实源码 · ServletWebServerApplicationContext.java:186–208 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/web/servlet/context/ServletWebServerApplicationContext.java#L186-L208)

```java
	private void createWebServer() {
		WebServer webServer = this.webServer;
		ServletContext servletContext = getServletContext();
		if (webServer == null && servletContext == null) {
			StartupStep createWebServer = getApplicationStartup().start("spring.boot.webserver.create");
			ServletWebServerFactory factory = getWebServerFactory();
			createWebServer.tag("factory", factory.getClass().toString());
			this.webServer = factory.getWebServer(getSelfInitializer());
			createWebServer.end();
			getBeanFactory().registerSingleton("webServerGracefulShutdown",
					new WebServerGracefulShutdownLifecycle(this.webServer));
			getBeanFactory().registerSingleton("webServerStartStop",
					new WebServerStartStopLifecycle(this, this.webServer));
		}
		else if (servletContext != null) {
			try {
				getSelfInitializer().onStartup(servletContext);
			}
			catch (ServletException ex) {
				throw new ApplicationContextException("Cannot initialize servlet context", ex);
			}
		}
		initPropertySources();
```

[真实源码 · WebServerStartStopLifecycle.java:42–48 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/web/servlet/context/WebServerStartStopLifecycle.java#L42-L48)

```java
	@Override
	public void start() {
		this.webServer.start();
		this.running = true;
		this.applicationContext
			.publishEvent(new ServletWebServerInitializedEvent(this.webServer, this.applicationContext));
	}
```

### 分支与失败边界

getWebServerFactory要求当前上下文恰当的工厂候选：零个或多个都不是自动任选一个。端口冲突可能在服务器初始化/启动路径抛异常，由onRefresh或生命周期链传播到启动失败。WebServerInitialized只说明服务器初始化事件，Runner仍可能失败。

### 可复现实验与观察点

运行样例--server.port=0，监听ServletWebServerInitializedEvent输出getWebServer().getPort()，应得到实际随机端口；再强制一个被占用端口，查看失败分析。对createWebServer与WebServerStartStopLifecycle.start设断点，确认两个完成点顺序。

<h2 id="chapter-15">15. Tomcat工厂与Servlet注册：适配器的责任</h2>

### 问题与设计动机

Boot把server.port、连接器定制、上下文设置和ServletContextInitializer组装为嵌入式Tomcat。它提供可替换工厂和Customizer，Tomcat自身负责Socket、请求解析与Servlet调度。研究Boot时追到工厂边界，研究连接调度时再进入Tomcat仓库。

### 字段、状态与不变量

TomcatServletWebServerFactory持有protocol、baseDirectory、additionalTomcatConnectors等；Tomcat内部有Server、Service、Engine、Host、Context。ServletContextInitializerBeans维护initializers映射与sortedList，把Servlet/Filter/Listener Bean适配成注册对象。seen集合避免重复适配注册。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-15"><title id="diagram-title-15">Tomcat工厂与Servlet注册：适配器的责任：关键状态推进</title><defs><marker id="arrow-15" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-15)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">Boot属性/Customizer</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">Tomcat树与Connector</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Initializer排序/去重</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">ServletContext注册映射</text></svg><figcaption>图15 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

getWebServer→new Tomcat→设置baseDir→创建Connector→customizeConnector→设置Host/Engine→prepareContext→getTomcatWebServer；Context初始化时selfInitialize→getServletContextInitializerBeans→按order执行onStartup，在ServletContext登记Servlet、Filter与Listener。

[真实源码 · TomcatServletWebServerFactory.java:196–217 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/web/embedded/tomcat/TomcatServletWebServerFactory.java#L196-L217)

```java
	public WebServer getWebServer(ServletContextInitializer... initializers) {
		if (this.disableMBeanRegistry) {
			Registry.disableRegistry();
		}
		Tomcat tomcat = new Tomcat();
		File baseDir = (this.baseDirectory != null) ? this.baseDirectory : createTempDir("tomcat");
		tomcat.setBaseDir(baseDir.getAbsolutePath());
		for (LifecycleListener listener : getDefaultServerLifecycleListeners()) {
			tomcat.getServer().addLifecycleListener(listener);
		}
		Connector connector = new Connector(this.protocol);
		connector.setThrowOnFailure(true);
		tomcat.getService().addConnector(connector);
		customizeConnector(connector);
		tomcat.setConnector(connector);
		registerConnectorExecutor(tomcat, connector);
		tomcat.getHost().setAutoDeploy(false);
		configureEngine(tomcat.getEngine());
		for (Connector additionalConnector : this.additionalTomcatConnectors) {
			tomcat.getService().addConnector(additionalConnector);
			registerConnectorExecutor(tomcat, additionalConnector);
		}
```

[真实源码 · ServletContextInitializerBeans.java:95–101 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/web/servlet/ServletContextInitializerBeans.java#L95-L101)

```java
		addServletContextInitializerBeans(beanFactory);
		addAdaptableBeans(beanFactory);
		this.sortedList = this.initializers.values()
			.stream()
			.flatMap((value) -> value.stream().sorted(AnnotationAwareOrderComparator.INSTANCE))
			.toList();
		logMappings(this.initializers);
```

### 分支与失败边界

单独声明Servlet Bean可能自动适配，但明确ServletRegistrationBean可以设置映射与顺序；显式注册后不能再期待重复注册同一实例。Filter顺序影响请求经过的链条，不能靠文件名推断。端口、协议或SSL错误可能由Tomcat底层报错，Boot负责传播与诊断。

### 可复现实验与观察点

样例添加一个FilterRegistrationBean，映射/*、order=1，在doFilter前后打印并访问/ping；再加order=2的过滤器，预期前置为1→2，后置为2→1。定义ServletRegistrationBean映射/raw，确认它绕开MVC控制器但仍进入Servlet过滤链。

<h2 id="chapter-16">16. MVC：Boot提供默认值，DispatcherServlet处理请求</h2>

### 问题与设计动机

Boot的MVC自动配置提供转换器、静态资源、格式化、视图等默认组合。一次HTTP请求如何找Handler、适配调用、处理异常，仍在Framework的DispatcherServlet。加@EnableWebMvc通常意味着自己接管MVC配置，原因可从MissingBean条件直接看见。

### 字段、状态与不变量

WebMvcAutoConfiguration要求SERVLET环境、Servlet/DispatcherServlet/WebMvcConfigurer存在，以及没有WebMvcConfigurationSupport Bean。DispatcherServlet持有handlerMappings、handlerAdapters、handlerExceptionResolvers等策略；doDispatch里的mappedHandler与mv记录本次请求状态。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-16"><title id="diagram-title-16">MVC：Boot提供默认值，DispatcherServlet处理请求：关键状态推进</title><defs><marker id="arrow-16" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-16)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">HTTP请求：Servlet进入</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">HandlerMapping：找到处理器</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">HandlerAdapter：参数/调用</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">异常解析/视图或响应体</text></svg><figcaption>图16 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

Boot自动配置登记MVC支持Bean→DispatcherServlet初始化策略→doDispatch checkMultipart→getHandler→getHandlerAdapter→拦截器preHandle→HandlerAdapter.handle→异步判定或postHandle→processDispatchResult→异常解析/渲染→afterCompletion。控制器参数转换不由Boot的启动run直接执行。

[真实源码 · WebMvcAutoConfiguration.java:146–151 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/web/servlet/WebMvcAutoConfiguration.java#L146-L151)

```java
@ConditionalOnWebApplication(type = Type.SERVLET)
@ConditionalOnClass({ Servlet.class, DispatcherServlet.class, WebMvcConfigurer.class })
@ConditionalOnMissingBean(WebMvcConfigurationSupport.class)
@AutoConfigureOrder(Ordered.HIGHEST_PRECEDENCE + 10)
@ImportRuntimeHints(WebResourcesRuntimeHints.class)
public class WebMvcAutoConfiguration {
```

[真实源码 · DispatcherServlet.java:1049–1072 · 6.2.19](https://github.com/spring-projects/spring-framework/blob/6214eae8bd02c2ed7ab382bb8d16a9cc6de49522/spring-webmvc/src/main/java/org/springframework/web/servlet/DispatcherServlet.java#L1049-L1072)

```java
	protected void doDispatch(HttpServletRequest request, HttpServletResponse response) throws Exception {
		HttpServletRequest processedRequest = request;
		HandlerExecutionChain mappedHandler = null;
		boolean multipartRequestParsed = false;

		WebAsyncManager asyncManager = WebAsyncUtils.getAsyncManager(request);

		try {
			ModelAndView mv = null;
			Exception dispatchException = null;

			try {
				processedRequest = checkMultipart(request);
				multipartRequestParsed = (processedRequest != request);

				// Determine handler for the current request.
				mappedHandler = getHandler(processedRequest);
				if (mappedHandler == null) {
					noHandlerFound(processedRequest, response);
					return;
				}

				// Determine handler adapter for the current request.
				HandlerAdapter ha = getHandlerAdapter(mappedHandler.getHandler());
```

### 分支与失败边界

没找到Handler走noHandlerFound；找到但没合适Adapter是另一种配置错误；转换失败与控制器抛错由异常解析器链处理。@EnableWebMvc导入WebMvcConfigurationSupport相关配置后，Boot MVC自动配置退让，而不是仅“增加一个注解功能”。静态资源404也不能先假设控制器未扫描。

### 可复现实验与观察点

样例/ping返回字符串；加入WebMvcConfigurer自定义拦截器，预期保留Boot默认行为。然后临时加@EnableWebMvc并--debug，观察WebMvcAutoConfiguration不再匹配；比较静态资源与消息转换器配置，再移除注解。

<h2 id="chapter-17">17. Binder：源名称、目标类型和错误策略</h2>

### 问题与设计动机

@Value偏向一个键的表达式求值，@ConfigurationProperties偏向结构化对象绑定。Binder必须同时知道配置名、目标类型、当前绑定上下文与处理器，才能处理Duration、嵌套对象、Map/List及错误。宽松名称匹配是来源适配能力，不意味着任意拼写都能成功。

### 字段、状态与不变量

Binder保存ConfigurationPropertySources、placeholdersResolver、conversionService和dataObjectBinders；Bindable携带ResolvableType、注解及已有值；Context跟踪当前深度与来源；BindHandler可在onStart/onSuccess/onFailure/onFinish中改变策略。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-17"><title id="diagram-title-17">Binder：源名称、目标类型和错误策略：分支条件对照</title><defs><marker id="arrow-17" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 条件分支</text><text x="41" y="74" fill="#20324d" font-size="15">名称demo + Bindable类型</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 条件分支</text><text x="436" y="74" fill="#20324d" font-size="15">PropertySource适配/查找</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 条件分支</text><text x="41" y="179" fill="#20324d" font-size="15">直接值/聚合/对象分派</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 条件分支</text><text x="436" y="179" fill="#20324d" font-size="15">Handler处理成功或错误</text></svg><figcaption>图17 · 分支分区，四格不表示顺序执行</figcaption></figure>

### 沿真实调用链推演

bind→新Context→handler.onStart→bindObject：直接属性命中则转换，聚合目标交AggregateBinder，否则bindDataObject选择JavaBean或值对象Binder→handleBindResult→onSuccess及必要类型转换；异常→handleBindError→handler.onFailure。

[真实源码 · Binder.java:348–364 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/properties/bind/Binder.java#L348-L364)

```java
	private <T> T bind(ConfigurationPropertyName name, Bindable<T> target, BindHandler handler, Context context,
			boolean allowRecursiveBinding, boolean create) {
		try (ConfigurationPropertyCaching.CacheOverride cacheOverride = this.configurationPropertyCaching.override()) {
			try {
				Bindable<T> replacementTarget = handler.onStart(name, target, context);
				if (replacementTarget == null) {
					return handleBindResult(name, target, handler, context, null, create);
				}
				target = replacementTarget;
				Object bound = bindObject(name, target, handler, context, allowRecursiveBinding);
				return handleBindResult(name, target, handler, context, bound, create);
			}
			catch (Exception ex) {
				return handleBindError(name, target, handler, context, ex);
			}
		}
	}
```

### 分支与失败边界

List覆盖与Map按键合并有不同规则，不要说“所有集合逐项叠加”。转换错误不会自动回退低优先级来源：高优先级已命中的非法值通常使绑定失败。@ConfigurationProperties(ignoreInvalidFields=true)会改变错误策略，应清楚其可能留下默认值的后果。

### 可复现实验与观察点

第27章record DemoProperties中Duration timeout默认来自demo.timeout=2s。传--demo.timeout=abc，预期启动绑定失败并报告配置键与来源；传--demo.timeout=PT3S，预期可转换。对Binder.bindObject设断点观察目标是Duration还是完整record。

<h2 id="chapter-18">18. ConfigurationProperties生命周期、构造绑定与校验</h2>

### 问题与设计动机

可变JavaBean需要先创建再填充；不可变record必须用配置值调用构造器。这两条路径不能同时套在同一个普通@Component Bean上。绑定后应在应用接流量前验证约束，否则无效重试次数、超时或URL会进入业务。

### 字段、状态与不变量

BindMethod区分JAVA_BEAN与VALUE_OBJECT；ConfigurationPropertiesBindingPostProcessor跳过已构造绑定的value object，对常规Bean在before initialization时绑定。ConfigurationPropertiesBinder根据注解创建BindHandler，并可追加ValidationBindHandler、IgnoreErrorsBindHandler及UnboundElementsBindHandler。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-18"><title id="diagram-title-18">ConfigurationProperties生命周期、构造绑定与校验：关键状态推进</title><defs><marker id="arrow-18" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-18)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">JavaBean：先创建后绑定</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">Value Object：绑定后构造</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">ValidationBindHandler：验证</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">失败→阻断启动</text></svg><figcaption>图18 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

通过ConfigurationPropertiesScan或EnableConfigurationProperties登记类型→值对象由对应Bean注册/实例供应路径bindOrCreate；常规Bean经过postProcessBeforeInitialization→ConfigurationPropertiesBean.get→ConfigurationPropertiesBinder.bind→Binder与校验Handler。错误包装ConfigurationPropertiesBindException，携带Bean信息。

[真实源码 · ConfigurationPropertiesBindingPostProcessor.java:77–86 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/properties/ConfigurationPropertiesBindingPostProcessor.java#L77-L86)

```java
	public Object postProcessBeforeInitialization(Object bean, String beanName) throws BeansException {
		if (!hasBoundValueObject(beanName)) {
			bind(ConfigurationPropertiesBean.get(this.applicationContext, bean, beanName));
		}
		return bean;
	}

	private boolean hasBoundValueObject(String beanName) {
		return BindMethod.VALUE_OBJECT.equals(BindMethodAttribute.get(this.registry, beanName));
	}
```

[真实源码 · ConfigurationPropertiesBinder.java:90–95 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/properties/ConfigurationPropertiesBinder.java#L90-L95)

```java
	BindResult<?> bind(ConfigurationPropertiesBean propertiesBean) {
		Bindable<?> target = propertiesBean.asBindTarget();
		ConfigurationProperties annotation = propertiesBean.getAnnotation();
		BindHandler bindHandler = getBindHandler(target, annotation);
		return getBinder().bind(annotation.prefix(), target, bindHandler);
	}
```

[真实源码 · ConstructorBinding.java:34–38 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/properties/bind/ConstructorBinding.java#L34-L38)

```java
@Target({ ElementType.CONSTRUCTOR, ElementType.ANNOTATION_TYPE })
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface ConstructorBinding {

```

[真实源码 · ConstructorBinding.java:42–46 · 2.7.18](https://github.com/spring-projects/spring-boot/blob/0c8b382d42db22b92efcf47000d0ff9ef4971629/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/properties/ConstructorBinding.java#L42-L46)

```java
@Target({ ElementType.TYPE, ElementType.CONSTRUCTOR })
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface ConstructorBinding {

```

### 分支与失败边界

3.x单个参数化构造器通常可推断构造绑定，多个构造器则需明确选择；@ConstructorBinding不是用于把任何@Component改成值对象。3.x注解在context.properties.bind包并针对构造器，2.7.18在context.properties包且可标记类型。@Validated需实际验证实现，例如starter-validation，只有注解而没有Provider不能假定校验已执行。

### 可复现实验与观察点

样例record标记@Validated，给int retries加@Min(1)，pom引入starter-validation；--demo.retries=0应失败，--demo.retries=2应成功。把record改成普通@Component并保留构造绑定意图，观察普通Bean构造依赖与属性绑定之间的冲突，再恢复扫描注册。

<h2 id="chapter-19">19. Actuator：发现、可用性、暴露与鉴权是四个问题</h2>

### 问题与设计动机

“有Actuator依赖”不代表所有管理接口都可HTTP访问。端点先被发现并转换为操作模型，再受访问/启用与暴露策略过滤，最后由Web适配层映射；认证授权通常由Spring Security配置负责。将404当作安全证明，或把暴露当作认证，都容易误判。

### 字段、状态与不变量

EndpointDiscoverer缓存endpoints；EndpointBean保存id、Bean与操作；createEndpointBeans按EndpointId建LinkedHashMap并检查重复。3.5.x端点访问属性与最大允许访问限制形成端点可用性边界；WebEndpointDiscoverer及暴露过滤器控制哪些端点进入HTTP映射。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-19"><title id="diagram-title-19">Actuator：发现、可用性、暴露与鉴权是四个问题：关键状态推进</title><defs><marker id="arrow-19" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-19)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">Bean发现：EndpointId唯一</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">访问策略：是否有操作</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Web暴露：是否映射HTTP</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">Security：谁能调用</text></svg><figcaption>图19 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

getEndpoints→discoverEndpoints→createEndpointBeans→addExtensionBeans→convertToEndpoints→过滤操作/端点→Web端点映射→请求鉴权→调用操作。health、metrics、conditions与beans不是同一种成本，尤其条件报告和Bean信息不能无区别公开。

[真实源码 · EndpointDiscoverer.java:151–167 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-actuator/src/main/java/org/springframework/boot/actuate/endpoint/annotation/EndpointDiscoverer.java#L151-L167)

```java
	private Collection<E> discoverEndpoints() {
		Collection<EndpointBean> endpointBeans = createEndpointBeans();
		addExtensionBeans(endpointBeans);
		return convertToEndpoints(endpointBeans);
	}

	private Collection<EndpointBean> createEndpointBeans() {
		Map<EndpointId, EndpointBean> byId = new LinkedHashMap<>();
		String[] beanNames = BeanFactoryUtils.beanNamesForAnnotationIncludingAncestors(this.applicationContext,
				Endpoint.class);
		for (String beanName : beanNames) {
			if (!ScopedProxyUtils.isScopedTarget(beanName)) {
				EndpointBean endpointBean = createEndpointBean(beanName);
				EndpointBean previous = byId.putIfAbsent(endpointBean.getId(), endpointBean);
				Assert.state(previous == null, () -> "Found two endpoints with the id '" + endpointBean.getId() + "': '"
						+ endpointBean.getBeanName() + "' and '" + previous.getBeanName() + "'");
			}
```

### 分支与失败边界

重复id直接Assert失败；显式暴露不自动创建被访问策略禁用的端点。management.server.port不同会影响管理上下文与端口路由。health成功也不证明所有业务依赖与数据正确；探针聚合要看具体HealthIndicator/group。

### 可复现实验与观察点

样例只暴露health,info,conditions。访问/actuator/health应有结果，/actuator/beans预期404。临时增加beans暴露再检查变化；若加入Security，应验证未登录与登录分别返回什么。本样例供本机学习，不建议将管理端口直接公开。

<h2 id="chapter-20">20. Runner与可用性：存活不等于就绪</h2>

### 问题与设计动机

系统可能已经启动线程和端口，业务仍在加载索引。Liveness回答进程内部是否处于可继续工作的状态，Readiness回答是否适合接受新请求。Boot先发布started与CORRECT，Runner执行后才ready与ACCEPTING_TRAFFIC，为预热过程留出明确状态。

### 字段、状态与不变量

ApplicationAvailabilityBean的events按AvailabilityState类型保存最后事件；两个状态可以独立变化。SpringApplication从BeanFactory收集Runner实例，利用排序器与Bean工厂来源信息排序。Runner是启动时同步执行的回调，不是常驻后台线程接口。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-20"><title id="diagram-title-20">Runner与可用性：存活不等于就绪：关键状态推进</title><defs><marker id="arrow-20" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-20)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">refresh完成：CORRECT</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">Runner预热：未Ready</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">全部Runner成功</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">ACCEPTING_TRAFFIC</text></svg><figcaption>图20 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

refresh完成→EventPublishingRunListener.started发布ApplicationStartedEvent与LivenessState.CORRECT→callRunners收集并排序ApplicationRunner/CommandLineRunner→ready发布ApplicationReadyEvent与ReadinessState.ACCEPTING_TRAFFIC。外部探针适配可将这些状态映射为健康结果。

[真实源码 · EventPublishingRunListener.java:102–112 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/event/EventPublishingRunListener.java#L102-L112)

```java
	public void started(ConfigurableApplicationContext context, Duration timeTaken) {
		context.publishEvent(new ApplicationStartedEvent(this.application, this.args, context, timeTaken));
		AvailabilityChangeEvent.publish(context, LivenessState.CORRECT);
	}

	@Override
	public void ready(ConfigurableApplicationContext context, Duration timeTaken) {
		context.publishEvent(new ApplicationReadyEvent(this.application, this.args, context, timeTaken));
		AvailabilityChangeEvent.publish(context, ReadinessState.ACCEPTING_TRAFFIC);
	}

```

[真实源码 · ApplicationAvailabilityBean.java:74–80 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/availability/ApplicationAvailabilityBean.java#L74-L80)

```java
	public void onApplicationEvent(AvailabilityChangeEvent<?> event) {
		Class<? extends AvailabilityState> type = getStateType(event.getState());
		if (this.logger.isDebugEnabled()) {
			this.logger.debug(getLogMessage(type, event));
		}
		this.events.put(type, event);
	}
```

[真实源码 · SpringApplication.java:763–775 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L763-L775)

```java
	private void callRunners(ConfigurableApplicationContext context, ApplicationArguments args) {
		ConfigurableListableBeanFactory beanFactory = context.getBeanFactory();
		String[] beanNames = beanFactory.getBeanNamesForType(Runner.class);
		Map<Runner, String> instancesToBeanNames = new IdentityHashMap<>();
		for (String beanName : beanNames) {
			instancesToBeanNames.put(beanFactory.getBean(beanName, Runner.class), beanName);
		}
		Comparator<Object> comparator = getOrderComparator(beanFactory)
			.withSourceProvider(new FactoryAwareOrderSourceProvider(beanFactory, instancesToBeanNames));
		instancesToBeanNames.keySet().stream().sorted(comparator).forEach((runner) -> callRunner(runner, args));
	}

	private OrderComparator getOrderComparator(ConfigurableListableBeanFactory beanFactory) {
```

[真实源码 · SpringApplication.java:793–798 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L793-L798)

```java
	private <R extends Runner> void callRunner(Class<R> type, Runner runner, ThrowingConsumer<R> call) {
		call.throwing(
				(message, ex) -> new IllegalStateException("Failed to execute " + ClassUtils.getShortName(type), ex))
			.accept((R) runner);
	}

```

[真实源码 · SpringApplication.java:754–761 · 2.7.18](https://github.com/spring-projects/spring-boot/blob/0c8b382d42db22b92efcf47000d0ff9ef4971629/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L754-L761)

```java
	private void callRunner(ApplicationRunner runner, ApplicationArguments args) {
		try {
			(runner).run(args);
		}
		catch (Exception ex) {
			throw new IllegalStateException("Failed to execute ApplicationRunner", ex);
		}
	}
```

[真实源码 · ThrowingConsumer.java:58–69 · 6.2.19](https://github.com/spring-projects/spring-framework/blob/6214eae8bd02c2ed7ab382bb8d16a9cc6de49522/spring-core/src/main/java/org/springframework/util/function/ThrowingConsumer.java#L58-L69)

```java
	default void accept(T t, BiFunction<String, Exception, RuntimeException> exceptionWrapper) {
		try {
			acceptWithException(t);
		}
		catch (RuntimeException ex) {
			throw ex;
		}
		catch (Exception ex) {
			throw exceptionWrapper.apply(ex.getMessage(), ex);
		}
	}

```

### 分支与失败边界

HTTP端口可监听而Readiness尚未接受流量；如果负载均衡器忽略就绪探针，仍可能把请求送来。长Runner阻塞后续Runner及ready；Runner失败会关闭上下文。Liveness通常不应因外部数据库短暂不可用而触发无限重启，具体依赖放在哪个健康组要按业务恢复策略设计。

### 两版对照的依据

实测教学Runner抛IllegalStateException时，3.5.16向调用者重新抛出该RuntimeException，消息仍是原始teaching failure；2.7.18的callRunner直接catch(Exception)并统一包装Failed to execute ApplicationRunner。3.5.16采用Framework ThrowingConsumer，RuntimeException原样传播，checked Exception才调用包装器。Ready不发布这一结果仍然相同，测试不要只硬编码旧错误消息。

### 可复现实验与观察点

样例添加一个3秒Runner，再监听AvailabilityChangeEvent输出状态类型及值。预期CORRECT先出现，3秒后ACCEPTING_TRAFFIC；改成失败Runner，不应出现ACCEPTING_TRAFFIC。对外流量是否被阻挡取决于部署平台探针设置，单机日志不证明负载均衡已遵守它。

<h2 id="chapter-21">21. 日志与FailureAnalyzer：早期初始化和诊断链</h2>

### 问题与设计动机

日志必须在Bean创建前工作，否则配置解析失败时没有可用诊断。LoggingApplicationListener先beforeInitialize抑制不合适输出，Environment准备后再按logging配置初始化。FailureAnalyzer则把异常转成描述与建议；它提升可读性，但不能替代根异常。

### 字段、状态与不变量

LoggingApplicationListener持有loggingSystem、logFile和loggerGroups；环境事件到来时才能读完整日志配置。FailureAnalyzers保存按工厂加载的analyzers；FailureAnalysis包括description/action/cause，FailureAnalysisReporter负责输出。分析器自身异常被记录并继续尝试下一个。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-21"><title id="diagram-title-21">日志与FailureAnalyzer：早期初始化和诊断链：关键状态推进</title><defs><marker id="arrow-21" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-21)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">starting：日志占位初始化</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">Environment：完整日志配置</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">异常：分析器链</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">结构化建议或通用堆栈</text></svg><figcaption>图21 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

ApplicationStartingEvent→LoggingSystem.get.beforeInitialize→ApplicationEnvironmentPreparedEvent→initialize(environment)；启动异常→SpringApplication.handleRunFailure→SpringBootExceptionReporter.reportException→FailureAnalyzers.analyze按序首个非null→reporters.report→必要时通用异常日志。

[真实源码 · LoggingApplicationListener.java:218–238 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/context/logging/LoggingApplicationListener.java#L218-L238)

```java
	public void onApplicationEvent(ApplicationEvent event) {
		if (event instanceof ApplicationStartingEvent startingEvent) {
			onApplicationStartingEvent(startingEvent);
		}
		else if (event instanceof ApplicationEnvironmentPreparedEvent environmentPreparedEvent) {
			onApplicationEnvironmentPreparedEvent(environmentPreparedEvent);
		}
		else if (event instanceof ApplicationPreparedEvent preparedEvent) {
			onApplicationPreparedEvent(preparedEvent);
		}
		else if (event instanceof ContextClosedEvent contextClosedEvent) {
			onContextClosedEvent(contextClosedEvent);
		}
		else if (event instanceof ApplicationFailedEvent) {
			onApplicationFailedEvent();
		}
	}

	private void onApplicationStartingEvent(ApplicationStartingEvent event) {
		this.loggingSystem = LoggingSystem.get(event.getSpringApplication().getClassLoader());
		this.loggingSystem.beforeInitialize();
```

[真实源码 · FailureAnalyzers.java:85–100 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/diagnostics/FailureAnalyzers.java#L85-L100)

```java
	private FailureAnalysis analyze(Throwable failure, List<FailureAnalyzer> analyzers) {
		for (FailureAnalyzer analyzer : analyzers) {
			try {
				FailureAnalysis analysis = analyzer.analyze(failure);
				if (analysis != null) {
					return analysis;
				}
			}
			catch (Throwable ex) {
				logger.trace(LogMessage.format("FailureAnalyzer %s failed", analyzer), ex);
			}
		}
		return null;
	}

	private boolean report(FailureAnalysis analysis) {
```

### 分支与失败边界

@PropertySource上的logging.level可能晚于日志初始化。FailureAnalyzer返回null意味着不负责该异常，不是“没有错误”。分析器提供的建议要和根cause核对，例如端口冲突、循环依赖、配置绑定错误有不同触发点。--debug条件报告解释配置决策，不等于开启所有业务DEBUG日志。

### 可复现实验与观察点

运行样例--logging.level.org.springframework.boot.context.config=TRACE观察早期配置解析；再以--demo.timeout=abc制造绑定失败，记录FailureAnalysis中的属性、值、来源与建议。对比Runner自定义异常没有专用分析器时的通用堆栈，确认二者诊断层次不同。

<h2 id="chapter-22">22. AOT与Native：构建期固定结构的代价</h2>

### 问题与设计动机

Native编译需要提前知道反射、资源与代理用法；Boot3整合AOT处理，用构建时可分析的应用上下文生成初始化代码与运行提示。它不是在生产第一次请求时再编译，也不意味着所有动态条件能在Native运行时任意改变。

### 字段、状态与不变量

SpringApplicationAotProcessor保存applicationArgs，继承Framework ContextAotProcessor。AotProcessorHook截获启动过程，获取为AOT准备的GenericApplicationContext；运行时AotDetector.useGeneratedArtifacts决定加载生成初始化器，主类名后缀__ApplicationContextInitializer必须存在。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-22"><title id="diagram-title-22">AOT与Native：构建期固定结构的代价：关键状态推进</title><defs><marker id="arrow-22" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-22)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">构建：准备上下文/条件</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">生成初始化代码与Hints</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">Native编译：闭世界</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">运行：装配已生成结构</text></svg><figcaption>图22 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

AOT构建入口→prepareApplicationContext→反射调用应用main→AotProcessorHook在准备好的上下文处交接→Framework ContextAotProcessor分析生成源/资源/类→Native编译；运行时SpringApplication.addAotGeneratedInitializerIfNecessary→加载生成初始化器，跳过常规source load分支。

[真实源码 · SpringApplicationAotProcessor.java:59–71 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplicationAotProcessor.java#L59-L71)

```java
	protected GenericApplicationContext prepareApplicationContext(Class<?> application) {
		return new AotProcessorHook(application).run(() -> {
			Method mainMethod = getMainMethod(application);
			mainMethod.setAccessible(true);
			if (mainMethod.getParameterCount() == 0) {
				ReflectionUtils.invokeMethod(mainMethod, null);
			}
			else {
				ReflectionUtils.invokeMethod(mainMethod, null, new Object[] { this.applicationArgs });
			}
			return Void.class;
		});
	}
```

[真实源码 · SpringApplication.java:419–432 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L419-L432)

```java
	private void addAotGeneratedInitializerIfNecessary(List<ApplicationContextInitializer<?>> initializers) {
		if (AotDetector.useGeneratedArtifacts()) {
			List<ApplicationContextInitializer<?>> aotInitializers = new ArrayList<>(
					initializers.stream().filter(AotApplicationContextInitializer.class::isInstance).toList());
			if (aotInitializers.isEmpty()) {
				String initializerClassName = this.mainApplicationClass.getName() + "__ApplicationContextInitializer";
				if (!ClassUtils.isPresent(initializerClassName, getClassLoader())) {
					throw new AotInitializerNotFoundException(this.mainApplicationClass, initializerClassName);
				}
				aotInitializers.add(AotApplicationContextInitializer.forInitializerClasses(initializerClassName));
			}
			initializers.removeAll(aotInitializers);
			initializers.addAll(0, aotInitializers);
		}
```

### 分支与失败边界

反射调用未登记Hints可能在Native运行时失败；条件决定的Bean图在构建期固定，运行时改变profile或影响Bean存在性的配置不能假设重建图。正常Bean属性值仍有运行时绑定场景，但结构与值要分开判断。构建main中的副作用也可能被执行，要避免在主方法无条件写生产资源。

### 两版对照的依据

3.5.16的AOT处理入口@since 3.0.0；2.7.18主线不包含该Boot3集成入口，2.x使用Spring Native实验项目的历史路径不能直接当成3.x内置机制。

### 可复现实验与观察点

在受支持的GraalVM环境执行mvn -Pnative native:compile，再运行产物并检查/ping。比较target/spring-aot/main/sources中的生成初始化器；故意添加反射读取一个未登记类型的路径，观察并补RuntimeHintsRegistrar。本次未编译Native，实验依赖GraalVM与native插件配置。

<h2 id="chapter-23">23. 测试切片：受控容器比缩小@SpringBootTest更明确</h2>

### 问题与设计动机

控制器测试通常只需MVC相关Bean，数据库测试只需数据访问设施。切片通过关闭通用自动配置、限制类型扫描并导入特定自动配置组合减少范围。它不是简单在完整容器里让部分Bean懒加载，所以切片成功不能证明整个应用依赖都正确。

### 字段、状态与不变量

@WebMvcTest组合BootstrapWith、OverrideAutoConfiguration(enabled=false)、TypeExcludeFilters、AutoConfigureWebMvc与AutoConfigureMockMvc。SpringBootTestContextBootstrapper则选择Boot ContextLoader，搜索SpringBootConfiguration并处理WebEnvironment。测试Context缓存属于Framework测试设施，缓存键受配置/属性等影响。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-23"><title id="diagram-title-23">测试切片：受控容器比缩小@SpringBootTest更明确：分支条件对照</title><defs><marker id="arrow-23" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 条件分支</text><text x="41" y="74" fill="#20324d" font-size="15">WebMvcTest：MVC范围</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 条件分支</text><text x="436" y="74" fill="#20324d" font-size="15">ExcludeFilter：剔除业务服务</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 条件分支</text><text x="41" y="179" fill="#20324d" font-size="15">MockMvc：Servlet内调用</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 条件分支</text><text x="436" y="179" fill="#20324d" font-size="15">SpringBootTest：整应用/真实端口可选</text></svg><figcaption>图23 · 分支分区，四格不表示顺序执行</figcaption></figure>

### 沿真实调用链推演

JUnit扩展→TestContextBootstrapper→合并上下文配置→切片TypeExcludeFilter限制扫描→ImportAutoConfiguration选择切片候选→ContextLoader加载→MockMvc调用DispatcherServlet但不启动真实端口。RANDOM_PORT模式@SpringBootTest则启动真实服务器，并不等同于MockMvc。

[真实源码 · WebMvcTest.java:101–109 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-test-autoconfigure/src/main/java/org/springframework/boot/test/autoconfigure/web/servlet/WebMvcTest.java#L101-L109)

```java
@BootstrapWith(WebMvcTestContextBootstrapper.class)
@ExtendWith(SpringExtension.class)
@OverrideAutoConfiguration(enabled = false)
@TypeExcludeFilters(WebMvcTypeExcludeFilter.class)
@AutoConfigureCache
@AutoConfigureWebMvc
@AutoConfigureMockMvc
@ImportAutoConfiguration
public @interface WebMvcTest {
```

[真实源码 · SpringBootTestContextBootstrapper.java:144–147 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-test/src/main/java/org/springframework/boot/test/context/SpringBootTestContextBootstrapper.java#L144-L147)

```java
	protected Class<? extends ContextLoader> getDefaultContextLoaderClass(Class<?> testClass) {
		return SpringBootContextLoader.class;
	}

```

### 分支与失败边界

控制器依赖业务Service而切片未提供时会缺Bean，需要测试替身或显式Import。@Transactional测试回滚只覆盖同线程/相应事务边界，RANDOM_PORT服务端请求在其他线程执行，不能假定被测试线程事务回滚。Security配置存在时MockMvc请求也可能401/403，而非控制器没映射。 本次实验曾把依赖DemoProperties的@Bean Runner放在主配置类，@WebMvcTest仍解析该@Bean，却没有提供业务属性对象，实际出现缺Bean。随后把Runner移成独立@Component，让切片扫描排除它，MVC测试通过。这说明TypeExcludeFilter并非对所有显式@Bean的全局开关。

### 可复现实验与观察点

为/ping写@WebMvcTest(PingController.class)测试，断言GET /ping响应；实际样例控制器为单独的PingController类。若为控制器加入GreetingService依赖，先观察缺Bean，再用Framework的@MockitoBean提供替身。另写RANDOM_PORT集成测试验证端口与HTTP链，分别说明其覆盖边界。

<h2 id="chapter-24">24. 2.7.18→3.5.16：迁移证据与责任归属</h2>

### 问题与设计动机

迁移需要区分Boot约定、Framework行为与第三方二进制接口。只把pom版本改成3.x会同时换Java基线、Servlet/JPA/Validation命名空间以及依赖版本。先在2.7线上清掉弃用API并建立行为测试，再切Java17+、Jakarta和新自动配置资源，更容易定位失败。

### 字段、状态与不变量

3.5.16 gradle.properties固定Framework6.2.19，2.7.18固定5.3.31；这两版不代表所有2.x和3.x小版本。Boot3运行最低Java17是上游system-requirements文档明示；Servlet指标源码从javax改jakarta；构造绑定注解位置/Target与候选注册代码存在直接差异。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-24"><title id="diagram-title-24">2.7.18→3.5.16：迁移证据与责任归属：分支条件对照</title><defs><marker id="arrow-24" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 条件分支</text><text x="41" y="74" fill="#20324d" font-size="15">Java8时代基线→Java17+</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 条件分支</text><text x="436" y="74" fill="#20324d" font-size="15">javax Servlet→jakarta Servlet</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 条件分支</text><text x="41" y="179" fill="#20324d" font-size="15">factories+imports→imports</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 条件分支</text><text x="436" y="179" fill="#20324d" font-size="15">Framework5.3→6.2依赖集</text></svg><figcaption>图24 · 分支分区，四格不表示顺序执行</figcaption></figure>

### 沿真实调用链推演

构建工具解析Boot BOM→固定依赖集→javac/运行JVM基线→ClassLoader加载Jakarta API→自动配置候选读取imports→Framework6解析Bean/MVC→Boot生命周期。每一层都应单独核验：NoClassDefFoundError偏向命名空间/缺依赖，NoSuchMethodError偏向版本混装，Bean条件不匹配偏向候选/环境。

[真实源码 · AutoConfigurationImportSelector.java:181–190 · 2.7.18](https://github.com/spring-projects/spring-boot/blob/0c8b382d42db22b92efcf47000d0ff9ef4971629/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/AutoConfigurationImportSelector.java#L181-L190)

```java
	protected List<String> getCandidateConfigurations(AnnotationMetadata metadata, AnnotationAttributes attributes) {
		List<String> configurations = new ArrayList<>(
				SpringFactoriesLoader.loadFactoryNames(getSpringFactoriesLoaderFactoryClass(), getBeanClassLoader()));
		ImportCandidates.load(AutoConfiguration.class, getBeanClassLoader()).forEach(configurations::add);
		Assert.notEmpty(configurations,
				"No auto configuration classes found in META-INF/spring.factories nor in META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports. If you "
						+ "are using a custom packaging, make sure that file is correct.");
		return configurations;
	}

```

[真实源码 · AutoConfigurationImportSelector.java:195–205 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/AutoConfigurationImportSelector.java#L195-L205)

```java
	protected List<String> getCandidateConfigurations(AnnotationMetadata metadata, AnnotationAttributes attributes) {
		ImportCandidates importCandidates = ImportCandidates.load(this.autoConfigurationAnnotation,
				getBeanClassLoader());
		List<String> configurations = importCandidates.getCandidates();
		Assert.state(!CollectionUtils.isEmpty(configurations),
				"No auto configuration classes found in " + "META-INF/spring/"
						+ this.autoConfigurationAnnotation.getName() + ".imports. If you "
						+ "are using a custom packaging, make sure that file is correct.");
		return configurations;
	}

```

[真实源码 · WebApplicationType.java:48–49 · 2.7.18](https://github.com/spring-projects/spring-boot/blob/0c8b382d42db22b92efcf47000d0ff9ef4971629/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/WebApplicationType.java#L48-L49)

```java
	private static final String[] SERVLET_INDICATOR_CLASSES = { "javax.servlet.Servlet",
			"org.springframework.web.context.ConfigurableWebApplicationContext" };
```

[真实源码 · WebApplicationType.java:51–52 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/WebApplicationType.java#L51-L52)

```java
	private static final String[] SERVLET_INDICATOR_CLASSES = { "jakarta.servlet.Servlet",
			"org.springframework.web.context.ConfigurableWebApplicationContext" };
```

### 分支与失败边界

javax.sql.DataSource属于Java SE，不在Jakarta迁移中改包；盲目全局替换javax会破坏代码。2.7.18已经支持imports与ConfigData，循环引用默认关闭也不是3.x才发生。路径匹配、尾斜杠等MVC差异主要属Framework，需要用请求回归验证，不能从Boot候选类名推导具体路由语义。

### 两版对照的依据

证据表只对固定基线负责。Boot3.0官方迁移指南用于背景解释，具体3.5.16机制以本文固定源码为准，不能据此断言所有改动恰好在3.0一次加入。

### 可复现实验与观察点

先用同一小型业务样例在2.7.18跑测试，再升级parent到3.5.16并设Java17；逐个迁移javax.servlet/validation/persistence，检查mvn dependency:tree是否有旧API混入。自定义starter做双版本ApplicationContextRunner测试，确认imports在两版都能工作，再删除只服务旧EnableAutoConfiguration候选的factories登记。

<h2 id="chapter-25">25. DataSource退让：用一个完整案例串起条件</h2>

### 问题与设计动机

数据源自动配置是理解条件组合的好案例。JDBC类存在，应用又没有选择R2DBC连接工厂时才进入主配置；进入后还要区分嵌入式数据库与连接池分支、有没有用户DataSource以及驱动/连接参数是否有效。依赖可见与连接成功是两个完成点。

### 字段、状态与不变量

DataSourceAutoConfiguration带ConditionalOnClass(DataSource,EmbeddedDatabaseType)、ConditionalOnMissingBean(type="io.r2dbc.spi.ConnectionFactory")；内部EmbeddedDatabaseConfiguration与PooledDataSourceConfiguration均要求没有DataSource/XADataSource。DataSourceProperties负责参数，JdbcConnectionDetails提供可覆盖的连接信息。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-25"><title id="diagram-title-25">DataSource退让：用一个完整案例串起条件：关键状态推进</title><defs><marker id="arrow-25" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-25)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">JDBC类存在</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">无R2DBC ConnectionFactory</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">无用户DataSource：默认池</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">建池成功≠查询成功</text></svg><figcaption>图25 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

自动配置候选过滤→DataSource主条件→嵌入式/池化分支→具体Hikari等配置→JdbcConnectionDetails选择→DataSource实例创建→连接池在需要时建立连接。SqlInitializationAutoConfiguration排在该配置之后，但排序不等于任意SQL初始化都成功。

[真实源码 · DataSourceAutoConfiguration.java:59–85 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/jdbc/DataSourceAutoConfiguration.java#L59-L85)

```java
@AutoConfiguration(before = SqlInitializationAutoConfiguration.class)
@ConditionalOnClass({ DataSource.class, EmbeddedDatabaseType.class })
@ConditionalOnMissingBean(type = "io.r2dbc.spi.ConnectionFactory")
@EnableConfigurationProperties(DataSourceProperties.class)
@Import({ DataSourcePoolMetadataProvidersConfiguration.class, DataSourceCheckpointRestoreConfiguration.class })
public class DataSourceAutoConfiguration {

	@Configuration(proxyBeanMethods = false)
	@Conditional(EmbeddedDatabaseCondition.class)
	@ConditionalOnMissingBean({ DataSource.class, XADataSource.class })
	@Import(EmbeddedDataSourceConfiguration.class)
	protected static class EmbeddedDatabaseConfiguration {

	}

	@Configuration(proxyBeanMethods = false)
	@Conditional(PooledDataSourceCondition.class)
	@ConditionalOnMissingBean({ DataSource.class, XADataSource.class })
	@Import({ DataSourceConfiguration.Hikari.class, DataSourceConfiguration.Tomcat.class,
			DataSourceConfiguration.Dbcp2.class, DataSourceConfiguration.OracleUcp.class,
			DataSourceConfiguration.Generic.class, DataSourceJmxConfiguration.class })
	protected static class PooledDataSourceConfiguration {

		@Bean
		@ConditionalOnMissingBean(JdbcConnectionDetails.class)
		PropertiesJdbcConnectionDetails jdbcConnectionDetails(DataSourceProperties properties) {
			return new PropertiesJdbcConnectionDetails(properties);
```

### 分支与失败边界

加R2DBC依赖本身不一定退让，需要对应ConnectionFactory Bean满足条件；自定义DataSource会让默认池配置退让。URL缺失且无嵌入式库可能在属性推导时报错，错误密码可能在连接池尝试连接时才暴露；某些池配置延迟建立连接，启动成功仍不能证明数据库可用。

### 可复现实验与观察点

新样例引入starter-jdbc与运行期H2。ApplicationContextRunner加载DataSourceAutoConfiguration，先断言有默认DataSource，再withUserConfiguration提供一个DataSource并确认自动配置退让。删除H2且不给URL观察启动失败诊断；无需连接生产数据库。

<h2 id="chapter-26">26. 关闭与优雅停机：把流量状态与资源回收串起来</h2>

### 问题与设计动机

关闭不能只System.exit。应先停止接收新请求，再给在途请求有限的完成机会，最后释放线程与连接。Boot把WebServer优雅关闭放进SmartLifecycle阶段，Framework负责按phase组织停止回调和关闭Bean。能否完成仍受超时与底层服务器能力约束。

### 字段、状态与不变量

WebServerGracefulShutdownLifecycle维护running标记，stop(callback)调用webServer.shutDownGracefully并将结果接到callback；Servlet上下文doClose在active时先发布ReadinessState.REFUSING_TRAFFIC，super.doClose后destroy webServer。WebServerStartStopLifecycle的phase低于优雅关闭phase，停机逆序先执行高phase。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-26"><title id="diagram-title-26">关闭与优雅停机：把流量状态与资源回收串起来：关键状态推进</title><defs><marker id="arrow-26" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-26)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">REFUSING_TRAFFIC：摘流量信号</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">优雅关闭：等待在途请求</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">超时或完成：继续停止</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">Bean销毁/服务器destroy</text></svg><figcaption>图26 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

关闭context→Servlet doClose发布REFUSING_TRAFFIC→Framework LifecycleProcessor停止高phase→WebServerGracefulShutdownLifecycle.shutDownGracefully→回调或超时→停止WebServer→销毁单例→webServer.destroy。部署平台摘流量与SIGTERM宽限时间必须与应用预算配合。

[真实源码 · WebServerGracefulShutdownLifecycle.java:60–63 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/web/context/WebServerGracefulShutdownLifecycle.java#L60-L63)

```java
	public void stop(Runnable callback) {
		this.running = false;
		this.webServer.shutDownGracefully((result) -> callback.run());
	}
```

[真实源码 · ServletWebServerApplicationContext.java:175–184 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/web/servlet/context/ServletWebServerApplicationContext.java#L175-L184)

```java
	protected void doClose() {
		if (isActive()) {
			AvailabilityChangeEvent.publish(this, ReadinessState.REFUSING_TRAFFIC);
		}
		super.doClose();
		WebServer webServer = this.webServer;
		if (webServer != null) {
			webServer.destroy();
		}
	}
```

[真实源码 · ServerProperties.java:116–116 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/web/ServerProperties.java#L116-L116)

```java
	private Shutdown shutdown = Shutdown.GRACEFUL;
```

[真实源码 · ServerProperties.java:108–108 · 2.7.18](https://github.com/spring-projects/spring-boot/blob/0c8b382d42db22b92efcf47000d0ff9ef4971629/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/web/ServerProperties.java#L108-L108)

```java
	private Shutdown shutdown = Shutdown.IMMEDIATE;
```

### 分支与失败边界

SIGKILL不会运行正常关闭回调；平台终止宽限比应用timeout短会截断优雅停机。Readiness事件不是网络层自动摘流量命令，外部控制器必须消费探针。固定基线的ServerProperties字段直接显示：2.7.18默认Shutdown.IMMEDIATE，3.5.16默认Shutdown.GRACEFUL。因此没有显式server.shutdown的应用也会改变停机路径；迁移时要重新检查超时与平台宽限时间。

### 可复现实验与观察点

样例增加一个耗时5秒的接口，设置server.shutdown=graceful与spring.lifecycle.timeout-per-shutdown-phase=10s；请求开始后发SIGTERM，预期在预算内完成已有请求并退出。改timeout为1s再观察差异。此实验须用临时本地端口，不能对生产进程执行信号。

<h2 id="chapter-27">27. 复现实验室：一个小应用验证多条主线</h2>

### 问题与设计动机

把阅读问题收敛到一个小工程：同一个/ping控制器、同一个DemoProperties、同一个Runner，可反复切换参数观察配置来源、绑定错误和就绪事件。另用ApplicationContextRunner做条件与Binder单测；它不依赖完整生产系统，也不需要真正访问数据库。

### 字段、状态与不变量

实验应用使用Java17语言级别、Spring Boot3.5.16 parent及starter-web/actuator/validation/test。源码目录在离线包的examples中；测试只使用临时上下文，不申请生产连接。DemoProperties是record，通过ConfigurationPropertiesScan注册，便于检查构造绑定。

<figure class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 815 215" role="img" aria-labelledby="diagram-title-27"><title id="diagram-title-27">复现实验室：一个小应用验证多条主线：关键状态推进</title><defs><marker id="arrow-27" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#648eb9"/></marker></defs><path d="M390 58H412 M603 91V114H207V130 M390 162H412" fill="none" stroke="#648eb9" stroke-width="2" marker-end="url(#arrow-27)"/><rect x="25" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="52" fill="#254c75" font-size="12">01 · 状态/交接</text><text x="41" y="74" fill="#20324d" font-size="15">单测：Binder/条件/失败</text><rect x="420" y="25" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="52" fill="#254c75" font-size="12">02 · 状态/交接</text><text x="436" y="74" fill="#20324d" font-size="15">打包：Boot可执行jar</text><rect x="25" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="41" y="157" fill="#254c75" font-size="12">03 · 状态/交接</text><text x="41" y="179" fill="#20324d" font-size="15">运行：Servlet/MVC/Actuator</text><rect x="420" y="130" width="365" height="66" rx="10" fill="#edf4ff" stroke="#b8cbe4"/><text x="436" y="157" fill="#254c75" font-size="12">04 · 状态/交接</text><text x="436" y="179" fill="#20324d" font-size="15">参数切换：验证不同状态</text></svg><figcaption>图27 · 关键交接点；完整调用及异常分支见正文</figcaption></figure>

### 沿真实调用链推演

mvn test运行绑定/条件/启动回归→mvn package生成可执行jar→java -jar启动完整Servlet路径→curl /ping→改变命令行、环境变量与profile观察行为→用本机信号验证关闭。Native实验另外要求GraalVM，不混入普通测试通过结论。

[真实源码 · SpringApplication.java:301–308 · 3.5.16](https://github.com/spring-projects/spring-boot/blob/0566f6933049aca6bc5ffc6d559fffade9cd2e0c/spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java#L301-L308)

```java
	public ConfigurableApplicationContext run(String... args) {
		Startup startup = Startup.create();
		if (this.properties.isRegisterShutdownHook()) {
			SpringApplication.shutdownHook.enableShutdownHookAddition();
		}
		DefaultBootstrapContext bootstrapContext = createBootstrapContext();
		ConfigurableApplicationContext context = null;
		configureHeadlessProperty();
```

### 分支与失败边界

测试通过只证明例子覆盖的行为，不是全量上游测试通过，也不能替代Native、真实网络、生产数据库、平台探针和迁移业务回归。某一实验结果不同，先记录实际依赖版本、参数、配置源顺序与根异常，再回到本文固定SHA核对，不能为了得到预期输出改掉关键前提。

### 可复现实验与观察点

从离线包进入examples，执行mvn test，然后mvn package。运行java -jar target/source-lab-1.0.0.jar --server.port=8088；另一个终端执行curl http://127.0.0.1:8088/ping与curl http://127.0.0.1:8088/actuator/health。绑定实验改变demo.timeout，来源实验改变demo.message。操作、预期与实测状态见VERIFICATION.md。

## 阅读自检：把机制说成因果链

1. 为什么ConfigData不能只扫一轮文件？先读取什么才能知道Profile，非活跃贡献为什么不能决定激活？
2. 为什么命令行常常覆盖文件？请描述PropertySources顺序以及读取第一个非null值的停止点。
3. 2.7已经有imports，为什么3.x仍需迁移自定义starter？指出两版getCandidateConfigurations的不同。
4. MissingBean在哪里检查？为何定义登记顺序会影响结果，为什么不应返回过于泛化的Object？
5. AutoConfigureAfter为什么不能保证业务实例先完成预热？说明定义、实例化、Runner三种时序。
6. Boot何处交给Framework？从refresh一路解释到Bean初始化后代理，再解释到DispatcherServlet。
7. 端口监听、Liveness与Readiness各证明什么？Runner失败发生时哪几个事实可能已成立？
8. 为什么Native不能随便在运行时改变Bean图？区分构建期结构与运行期属性值。
9. optional:能否吞掉所有配置错误？说明位置缺失、IO、语法失败的区别。
10. 为什么迁移不能全局把javax改成jakarta？用javax.sql.DataSource作为反例。

## 文件、归属与实验结果的边界

所有短源码片段来自Spring项目，Apache License2.0许可；源码版权归原作者。本页的图解和机制解释是独立导读，未改写片段中的语义。`source-notices.txt`列出完整文件、固定SHA和行号；`source-manifest.json`提供片段文本及SHA-256，方便复核。离线版不加载统计，不依赖CDN，只有点击上游外链才联网。实验依赖下载需要Maven仓库；这与手册离线阅读无关。

验证记录与局限见[VERIFICATION.md](./VERIFICATION.md)。没有执行的Native/平台探针/真实数据库实验只标预期，不宣称通过。遇到版本漂移先核对本文三组SHA，再做具体环境测试。
