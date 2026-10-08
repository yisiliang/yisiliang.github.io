# XStream1.4.4与每请求new XStream()：周期性Full GC分析

> 修订与核验：2026年10月8日。本文讨论JDK8、普通POJO、XStream1.4.4实际选中`Sun14ReflectionProvider`的场景。
> 实验使用Amazon Corretto8u462／macOS arm64。为触发旧版provider选择分支，实验程序在XStream初始化前将`java.vm.vendor`改为`Oracle Corporation`；这不等于在Oracle JDK上完成了性能测试。
> 文中的源码结论、历史实测、本次复测和待验证推断分别标明。性能数字只描述对应实验，不是生产环境的承诺。

## 0. 先看结论：对象能回收，为什么仍反复Full GC？

问题的起点不是POJO对象泄漏，而是**短命XStream实例不断生成短命反射类**。

XStream1.4.4的`Sun14ReflectionProvider`用实例字段`constructorCache`缓存序列化构造器。每个新provider第一次处理一个业务类型时，都会调用JDK8的`ReflectionFactory.newConstructorForSerialization(type, Object.<init>)`。在本文POJO场景中，该调用立即生成一个`GeneratedSerializationConstructorAccessorN`类，并交给新的`DelegatingClassLoader`定义。

复用同一个XStream时，同一类型随后命中缓存；每请求重新创建XStream时，下一请求又从空缓存开始。请求结束后，这些类通常可以卸载，但生成速率没有降低。在本文启用类卸载的ParallelGC配置下，元空间分配压力反复触发`Full GC (Metadata GC Threshold)`，于是监控表现为“元空间锯齿＋类反复卸载＋周期性停顿”。

```text
每请求新建XStream／provider
  → 每个实例第一次处理某种POJO时，构造器缓存未命中
  → ReflectionFactory生成新的序列化构造器accessor类
  → 类元数据累积，元空间扩展受到当前GC高水位约束
  → 元数据分配失败进入GC及分配重试路径
  → ParallelGC执行Full GC，卸载不可达类及其加载器
  → 请求继续，再次累积
```

核心修复是**停止重复生成类**：复用完成配置的XStream，或升级到移除了这条实例化路径的版本。元空间参数影响回收时机和内存预算，不能代替代码修复。

## 1. 适用边界：先确认实际provider

### 1.1 实验环境

|项目|配置|
|---|---|
|运行时|Amazon Corretto8u462，`1.8.0_462`，macOS arm64|
|旧版依赖|`com.thoughtworks.xstream:xstream:1.4.4`|
|XML解析依赖|`xpp3:xpp3_min:1.1.4c`、`xmlpull:xmlpull:1.1.3.1`|
|对象图|一个`Order`，含String与int字段；固定可信XML|
|GC复测|显式`-XX:+UseParallelGC`，`-Xms1g -Xmx1g`|
|元空间|主对照未设置`MetaspaceSize`或`MaxMetaspaceSize`|
|引用保留|`new`不累积XStream；`static`复用一个实例；`new-retain`另作反例|

### 1.2 厂商判断是选择分支，不是跨JVM行为保证

1.4.4根据初始化时读取的`java.vm.vendor`等条件选择provider。`Sun`、`Oracle`会命中对应分支；其他判断还包括`Apple`、`IBM`、`Hewlett-Packard Company`、`Blackdown`、`Hitachi`、`SAP AG`、`FreeBSD Foundation`，BEA另有VM版本判断。还必须满足Java版本及内部类可用性等条件，provider实例化也可能失败并回退。

因此，不能将“厂商名称出现在白名单里”直接写成“该JVM一定产生本文的GC行为”。特别是IBM或JRockit，其内部实现不等于本文核验的HotSpot实现。

本次在同一Corretto上确认了两条分支：

|条件|实际provider|1,000请求新增目标accessor类|
|---|---|---:|
|保留真实`Amazon.com Inc.`|`PureJavaReflectionProvider`|0|
|初始化前改为`Oracle Corporation`|`Sun14ReflectionProvider`|1,000|

生产诊断应直接输出`xstream.getReflectionProvider().getClass().getName()`，同时记录依赖版本、JDK版本和厂商。**仅凭`new XStream()`或某个版本号，不能确认命中本案例。**

## 2. 源码调用链：缓存在哪一层失效？

以下XStream节选取自1.4.4源码包，与上游发布提交`c4c71226515fa42809a48d9ae702756e2831f379`对应；JDK反射节选取自本机Corretto8u462的`src.zip`。完整文件链接见附录C。

### 2.1 每次构造XStream，默认provider跟着实例创建

`XStream`的构造器创建一个`JVM`辅助对象；未显式传入provider时，由这个辅助对象选择并缓存provider。这里缓存的是**当前辅助对象所用的provider**，不是整个应用共用的全局provider。

`XStream.java:435–439`，构造器开头节选（不是完整方法）：

```java
        ConverterRegistry converterRegistry) {
        jvm = new JVM();
        if (reflectionProvider == null) {
            reflectionProvider = jvm.bestReflectionProvider();
        }
```

`JVM.java:241–267`，完整方法：

```java
    public synchronized ReflectionProvider bestReflectionProvider() {
        if (reflectionProvider == null) {
            try {
                String className = null;
                if (canUseSun14ReflectionProvider()) {
                    className = "com.thoughtworks.xstream.converters.reflection.Sun14ReflectionProvider";
                }
                if (className != null) {
                    Class cls = loadClass(className);
                    if (cls != null) {
                        reflectionProvider = (ReflectionProvider) cls.newInstance();
                    }
                }
                if (reflectionProvider == null) {
                    reflectionProvider = new PureJavaReflectionProvider();
                }
            } catch (InstantiationException e) {
                reflectionProvider = new PureJavaReflectionProvider();
            } catch (IllegalAccessException e) {
                reflectionProvider = new PureJavaReflectionProvider();
            } catch (AccessControlException e) {
                // thrown when trying to access sun.misc package in Applet context.
                reflectionProvider = new PureJavaReflectionProvider();
            }
        }
        return reflectionProvider;
    }
```

### 2.2 普通POJO的反序列化进入reflectionProvider

本文`Order`走反射转换器，而不是所有XML节点都无条件走这条路径。String、集合、自定义converter等可能走其他转换逻辑；已有对象或对象引用也可能避免创建新实例。

`AbstractReflectionConverter.java:419–430`，完整方法：

```java
    protected Object instantiateNewInstance(HierarchicalStreamReader reader, UnmarshallingContext context) {
        String attributeName = mapper.aliasForSystemAttribute("resolves-to");
        String readResolveValue = attributeName == null ? null : reader.getAttribute(attributeName);
        Object currentObject = context.currentObject();
        if (currentObject != null) {
            return currentObject;
        } else if (readResolveValue != null) {
            return reflectionProvider.newInstance(mapper.realClass(readResolveValue));
        } else {
            return reflectionProvider.newInstance(context.getRequiredType());
        }
    }
```

### 2.3 真正的重复点：provider实例上的构造器缓存

`Sun14ReflectionProvider.java:61–99`，字段与完整方法节选：

```java
    private transient ReflectionFactory reflectionFactory = ReflectionFactory.getReflectionFactory();
    private transient Map constructorCache =new HashMap();

    public Sun14ReflectionProvider() {
    	super();
	}

    public Sun14ReflectionProvider(FieldDictionary dic) {
    	super(dic);
	}

    public Object newInstance(Class type) {
        try {
            Constructor customConstructor = getMungedConstructor(type);
            return customConstructor.newInstance(new Object[0]);
        } catch (NoSuchMethodException e) {
            throw new ObjectAccessException("Cannot construct " + type.getName(), e);
        } catch (SecurityException e) {
            throw new ObjectAccessException("Cannot construct " + type.getName(), e);
        } catch (InstantiationException e) {
            throw new ObjectAccessException("Cannot construct " + type.getName(), e);
        } catch (IllegalAccessException e) {
            throw new ObjectAccessException("Cannot construct " + type.getName(), e);
        } catch (IllegalArgumentException e) {
            throw new ObjectAccessException("Cannot construct " + type.getName(), e);
        } catch (InvocationTargetException e) {
            throw new ObjectAccessException("Cannot construct " + type.getName(), e);
        }
    }

    private Constructor getMungedConstructor(Class type) throws NoSuchMethodException {
        synchronized (constructorCache) {
            Constructor ctor = (Constructor)constructorCache.get(type);
            if (ctor == null) {
                ctor = reflectionFactory.newConstructorForSerialization(type, Object.class.getDeclaredConstructor(new Class[0]));
                constructorCache.put(type, ctor);
            }
            return ctor;
        }
```

要读准这段代码，有三个关键点：

1. `constructorCache`是实例字段，每个新provider都从空缓存开始。
2. 同一个provider按`Class`缓存。即使一个请求里出现100个同类型对象，也不需要生成100个accessor；第一次未命中后，后续对象复用构造器。
3. `newInstance()`没有优先调用业务类已有的无参构造器。因此，本案例不要求POJO缺少无参构造器，也不要求POJO实现`Serializable`。

这不是“缓存永不命中”，而是**缓存只能在当前实例内命中，跨请求创建新实例就无法复用它**。

### 2.4 JDK8的这次调用立即生成类

`ReflectionFactory.java:353–362`，完整方法：

```java
    public Constructor<?> newConstructorForSerialization
        (Class<?> classToInstantiate, Constructor<?> constructorToCall)
    {
        // Fast path
        if (constructorToCall.getDeclaringClass() == classToInstantiate) {
            return constructorToCall;
        }
        return generateConstructor(classToInstantiate, constructorToCall);
    }

```

业务类`Order`与传入构造器所属的`Object`不同，因此走`generateConstructor()`。该方法没有跨调用缓存，而是创建新的`MethodAccessorGenerator`。这是序列化构造器的生成路径，**不是普通Method.invoke达到反射inflation阈值后才生成accessor的路径**，不能套用“调用15次以后才生成”的解释。

`ReflectionFactory.java:393–418`，完整方法：

```java
    private final Constructor<?> generateConstructor(Class<?> classToInstantiate,
                                                     Constructor<?> constructorToCall) {


        ConstructorAccessor acc = new MethodAccessorGenerator().
            generateSerializationConstructor(classToInstantiate,
                                             constructorToCall.getParameterTypes(),
                                             constructorToCall.getExceptionTypes(),
                                             constructorToCall.getModifiers(),
                                             constructorToCall.getDeclaringClass());
        Constructor<?> c = newConstructor(constructorToCall.getDeclaringClass(),
                                          constructorToCall.getParameterTypes(),
                                          constructorToCall.getExceptionTypes(),
                                          constructorToCall.getModifiers(),
                                          langReflectAccess().
                                          getConstructorSlot(constructorToCall),
                                          langReflectAccess().
                                          getConstructorSignature(constructorToCall),
                                          langReflectAccess().
                                          getConstructorAnnotations(constructorToCall),
                                          langReflectAccess().
                                          getConstructorParameterAnnotations(constructorToCall));
        setConstructorAccessor(c, acc);
        c.setAccessible(true);
        return c;
    }
```

`ClassDefiner.java:54–64`，完整方法：

```java
    static Class<?> defineClass(String name, byte[] bytes, int off, int len,
                                final ClassLoader parentClassLoader)
    {
        ClassLoader newLoader = AccessController.doPrivileged(
            new PrivilegedAction<ClassLoader>() {
                public ClassLoader run() {
                        return new DelegatingClassLoader(parentClassLoader);
                    }
                });
        return unsafe.defineClass(name, bytes, off, len, newLoader, null);
    }
```

每次生成的accessor类由新的`DelegatingClassLoader`定义，使其可以独立于长期存活的业务类加载器被卸载。

这里要分清内存位置：**ClassLoader实例、Constructor对象、accessor实例及Class镜像在Java堆；生成类的元数据在Metaspace。**不能说“新类加载器实例进入Metaspace”。

## 3. 类增长规律：按实例与不同类型计数

在本文路径中，可把目标accessor数量近似写成：

```text
新增序列化accessor类数
  = 各provider实例实际遇到的、构造器缓存首次未命中的类型数之和
```

假设每请求创建一个新的XStream，且每个请求都反序列化N种走此provider的业务类，则目标accessor增长约为`请求数×N`。同一请求中同类型对象重复出现，不额外增加这一类型的accessor。

如果复用一个XStream，每个相关Class通常只生成一次，范围是**这个provider实例的生命周期**。重建配置实例、使用多个实例、应用重部署或同名类来自不同加载器，都会改变这个范围，不能概括成“每个类终生只生成一次”。

2026年10月8日本次复测：

|模式|请求／调用数|TraceClassLoading中的目标accessor数|
|---|---:|---:|
|1.4.4，`new`，选择Sun14 provider|1,000|1,000|
|1.4.4，`static`，选择Sun14 provider|1,000|1|
|直接调用JDK8 ReflectionFactory|500|500|
|1.4.5，`new`，同样的POJO|1,000|0|

计数只匹配`[Loaded sun.reflect.GeneratedSerializationConstructorAccessor数字 …]`。`ClassLoadingMXBean.getTotalLoadedClassCount()`还包含初始化、监控和普通反射产生的其他类，只能作为辅助指标，不能与目标accessor数直接画等号。

## 4. 为什么对象能回收，元空间仍会锯齿上涨？

### 4.1 请求结束只意味着引用可能不再存活

引用关系可简化为：

```text
XStream实例
  → Sun14ReflectionProvider
    → constructorCache
      → 合成Constructor
        → ConstructorAccessor实例
          → accessor的Class及定义它的DelegatingClassLoader
            → 该加载器所属的类元数据
```

请求结束、这些对象失去强可达路径后，相关类通常具备卸载条件。但“变得不可达”与“已经卸载”是两件事。业务POJO对象可被堆GC回收，并不代表本轮GC已经做了类卸载。

此外，`DelegatingClassLoader`指向它的父加载器，并不意味着父加载器反向持有所有子加载器；业务类加载器长期存活不会自动阻止这些临时加载器卸载。仍需检查线程上下文加载器、静态字段、缓存等实际引用链。

### 4.2 类卸载是否需要Full GC，取决于收集器

本文主实验使用ParallelGC，启用类卸载时，相关回收发生在Full GC中；普通Young GC不执行这类卸载。

但这不能推广成所有JDK8收集器的规则：CMS可在启用`CMSClassUnloadingEnabled`的CMS周期中处理类卸载；G1可在启用`ClassUnloadingWithConcurrentMark`的并发标记周期中处理类卸载。相关周期仍有停顿阶段，但不必对应一条日志中的`Full GC`。关闭类卸载后，本来不可达的临时类也可能长期占用元空间。

来源：[JDK8u462 CMS实现](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/gc_implementation/concurrentMarkSweep/concurrentMarkSweepGeneration.cpp)、[G1实现](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/gc_implementation/g1/g1CollectedHeap.cpp)。

因此，诊断要同时看**生成速度、引用存活、类卸载配置与GC日志**。“unloaded持续增长”证明清理发生过，不能单独证明整个应用没有其他泄漏。

## 5. 元空间高水位：分配受限后触发GC，不是先越界提交

### 5.1 三个容易混淆的量

|量|含义|不能据此推导什么|
|---|---|---|
|used／MU|元数据已用量|不能把它当成GC高水位或进程RSS|
|committed／MC|JVM已提交的元空间容量|不等于所有容量都放了存活元数据，也不等于RSS|
|GC高水位|当前允许扩展元空间的阈值|不保证等于每次采样的used或committed|

`MetaspaceSize`影响初始GC高水位，并在JDK8高水位调整逻辑中作为下界；它不是预先分配固定大小的元空间，也不是其最大容量。`MaxMetaspaceSize`限制元空间提交容量。默认值应在实际JVM上查，本文机器约为21MiB，不能把这个数字写成所有JDK的恒定值。

### 5.2 从分配失败到GC与重试

JDK8u462的`MetaspaceGC::allowed_expansion()`根据当前committed、GC高水位和最大容量，计算允许扩展的余量。需要扩展时，如果这一余量不足，分配可以返回失败；并不需要先成功提交一块已经超过高水位的内存。

初始化完成后，`Metaspace::allocate()`在分配失败时进入`CollectorPolicy::satisfy_failed_metadata_allocation()`，通过`VM_CollectForMetadataAllocation`请求GC及分配重试。该流程有重新分配、扩展、回收和进一步重试等分支，最终仍失败才报告元数据OOM。

```text
尝试分配元数据
  → 当前空间与扩展额度不足，或原生内存提交失败
  → 进入元数据分配失败处理
  → 按收集器策略执行GC／尝试扩展／重新分配
  → 成功：继续运行；仍失败：报告OOM
```

**即使没有显式设置MaxMetaspaceSize，这条失败处理路径仍然存在。**原文“没有设置上限就缺少先GC再重试的兜底”不成立。

源码：[metaspace.cpp](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/memory/metaspace.cpp)、[collectorPolicy.cpp](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/memory/collectorPolicy.cpp)、[vmGCOperations.cpp](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/gc_implementation/shared/vmGCOperations.cpp)。这里用OpenJDK8u462源码交叉核对HotSpot机制，不把它当成对所有厂商二进制实现的逐字证明。

### 5.3 GC之后，高水位会重新调整

`compute_new_size()`考虑GC后的committed、`MinMetaspaceFreeRatio`、`MaxMetaspaceFreeRatio`以及收缩策略，决定是否调整高水位。许多小加载器还会带来chunk开销和碎片，所以GC日志中的used、提交容量与阈值并不一一相等。

在本案例里，Full GC反复卸载大量临时类，之后又继续生成，因此容易出现相似的触发区间。但不能据此推导“高水位永远固定”“峰值严格等于MetaspaceSize”或“Full GC次数恒定”。

## 6. 数据核验：机制稳定，频率与耗时需要看实验口径

### 6.1 历史主对照：各自对应一批运行

已核对原始`app.log`与`gc.log`，两批运行均为4线程，`-Xms1g -Xmx1g`，不累积XStream引用。

|指标|1.4.4，每请求new|1.4.4，static复用|
|---|---:|---:|
|完成请求|200,000|800,000|
|loadedDelta|200,660|172|
|Full GC|66，全部Metadata GC Threshold|0|
|Young GC|66次Metadata GC Threshold＋3次Allocation Failure|85次Allocation Failure|
|应用线程累计停止时间|1.0747254秒|0.0278989秒|
|实验程序DONE elapsed|8.5秒|1.0秒|

这两列负载不同，能够支持“共享实例大幅减少类增长，本次运行消除了该Full GC现象”，不能直接当成严格的同负载吞吐比。累计停止时间来自`PrintGCApplicationStoppedTime`，包含所有记录的应用线程停顿，并不只统计Full GC。

原文的`320,677`来自另一批320,000请求，不能放进200,000请求这一行；原文static的`185`也来自其他运行。本表统一使用同批日志。

### 6.2 本次同请求量复测

重新编译实验源码后，以相同4线程、200,000请求复测。主机上曾有其他实验同时运行，因此耗时只用于记录，不做严格性能排名；两批日志均确认provider、完成次数和checksum正确。

|指标|new|static|
|---|---:|---:|
|请求数|200,000|200,000|
|loadedDelta|200,660|171|
|Full GC|66，全部Metadata GC Threshold|0|
|Young GC|66次Metadata GC Threshold＋3次Allocation Failure|22次Allocation Failure|
|累计应用线程停止时间|1.1359755秒|0.0623071秒|
|DONE elapsed|11.7秒|0.7秒|

`new`主结果与历史运行吻合；static仍有Young GC，所以修复目标不是“所有GC都变成0”，而是这条类生成路径及对应的元数据GC压力消失。

### 6.3 历史参数矩阵：采样最大值不等于全过程峰值

以下取自每批`jstat`采样文件。YGC／FGC是**最后一次成功采样时的累计值**，不是由完整GC日志重新统计的最终次数；内存列也是采样命中的最大值，可能漏掉峰值。MB数值实际按MiB（1024²字节）换算。

|场景|Xmx|元空间参数|采样末次YGC／FGC|采样最大MU／MC（MiB）|
|---|---|---|---|---|
|M1|256m|默认|278／46|20.7／29.4|
|M2|1g|默认|94／47|18.4／26.4|
|M3|4g|默认|48／48|6.8／18.0|
|M4|4g|MetaspaceSize=512m|19／2|322.4／512.0|
|M5|256m|MetaspaceSize=512m|259／2|321.1／510.3|
|M6|1g|MetaspaceSize=512m|68／2|322.4／512.0|
|M7|4g|MetaspaceSize=192m，MaxMetaspaceSize=192m|20／6|107.9／168.8|

M3的DONE日志反而记录MU=17.45MiB、MC=25.25MiB，均大于采样表里的“最大值”。这直接说明原文把低频采样最大值称作真实峰值不准确。M1～M3最后采样的卸载数也不是DONE时的最终卸载数，修订版不再混用。

这些数据支持有限的结论：默认阈值下，改变堆大小没有消除元数据GC压力；调大MetaspaceSize后，采样中的GC次数减少，但元空间积累量明显增大。**不能据此规定生产参数，也不能证明高水位越大单次停顿必然越长。**停顿还需完整日志、负载与存活量对照。

原文给出的T1“9次GC原始序列”目前只有`app.log`与`samples.csv`可核对，未找到声称的`T1_hwm128/gc.log`，因此删除那段看似精确的原始GC引用，保留可核查的采样记录。

## 7. 什么时候只是反复回收，什么时候会OOM？

### 7.1 短命实例：有生成压力，不一定有持续泄漏

`new`且不累积引用时，Full GC能够卸载大部分生成类。历史20万请求运行最终记录`unloadedTotal=198,351`，本次记录198,368。类加载数持续增加、卸载数也持续增加，是“生成—清理循环”的证据。

只要卸载及内存预算足够，程序可以持续运行，不必然OOM。但这并不保证每个生产系统都会频繁Full GC：请求量、观察时长、收集器、阈值和类卸载设置都会改变表现。

### 7.2 长期保留每请求实例：回收条件被破坏

如果应用在长期存活的集合里持续保留每请求创建的XStream，其构造器缓存及accessor也跟着存活。此时既增加元空间负担，也保留大量XStream内部堆对象。

M8使用`-Xmx256m -XX:MaxMetaspaceSize=128m`并保留每请求实例，原始异常是：

```text
java.lang.OutOfMemoryError: GC overhead limit exceeded
```

最后采样MU约26.1MiB、MC约38.0MiB，远未达到128MiB元空间上限。**该实验说明保留策略会导致内存问题，但本次先失败的是堆／GC开销保护，不能充当Metaspace OOM的直接实测证据。**也不能仅凭这个结果承诺换某个参数就一定先报Metaspace OOM。

同样，`static`复用一个实例与`static Map`无限累积每请求实例是两种完全不同的保留策略。固定大小的ThreadLocal或实例池，也不能只凭名称就判定为持续类增长。

### 7.3 上限与原生内存预算

达到MaxMetaspaceSize不等于立刻OOM：JVM可能通过GC卸载无用类，再让分配成功；若存活类、碎片或预算使分配持续失败，才会报告元数据OOM。

不设置该参数也不等于无限物理内存。提交失败、其他原生分配失败或容器／操作系统终止都可能出现，具体失败形式不能一律写成`OutOfMemoryError: Metaspace`。本文没有完成这些原生内存耗尽场景的独立复测。

## 8. 修复：先降低生成量，再安排内存预算

### 8.1 复用完成配置的实例

```java
private static final XStream XSTREAM = createXStream();

private static XStream createXStream() {
    XStream x = new XStream();
    x.alias("order", Order.class);
    // alias、converter、注解等配置在发布实例前完成。
    return x;
}

public Order parse(String xml) {
    return (Order) XSTREAM.fromXML(xml);
}
```

这段代码说明复用方式，不代表1.4.4已经具有现代版本的类型白名单安全框架。

XStream1.4.4的类文档与[官方FAQ](https://x-stream.github.io/faq.html)说明：创建并配置完成后，可以跨线程共享，但动态注解自动发现是例外。还应确保自定义converter、共享对象与其他扩展本身满足并发要求；不要在请求过程中修改共享实例的配置。

本次1,000请求trace显示，复用后目标accessor由1,000个降为1个。这个收益来自缓存生命周期改变，不是`static`关键字本身的特殊GC能力；依赖注入容器管理的长期实例同样可以实现复用。

### 8.2 升级并验证provider的实际行为

核对XStream1.4.5源码后，`Sun14ReflectionProvider.newInstance()`已经改为`unsafe.allocateInstance(type)`；本次在同一JDK与POJO下，1,000次新建XStream未观察到目标序列化accessor。

这里的1.4.5是**源码变更的历史边界，不是当前生产推荐版本**。升级目标应结合当前受支持版本、安全公告、XML兼容性与业务回归选择，参阅[官方版本历史](https://x-stream.github.io/changes.html)及[安全说明](https://x-stream.github.io/security.html)。升级消除的是本文路径，不能保证所有动态代理、其他反射机制或自定义converter从此不再生成类。

### 8.3 参数只能影响回收时机和资源边界

|参数／措施|合理用途|边界|
|---|---|---|
|MetaspaceSize|调整初始元数据GC触发时机|调大可减少启动期或短窗口内GC，但也可能积累更多临时元数据；不能一概规定保持默认或一律禁止调大|
|MaxMetaspaceSize|在整体内存预算内限制元空间容量|上限过小可能增加GC或导致OOM；256m不是通用安全值|
|Xmx|安排堆预算|不能停止本文的反射类生成；预算要考虑堆实际提交、元空间、线程栈、CodeCache、直接内存和其他原生开销|
|GC与类卸载设置|改变回收策略与停顿形态|必须以目标收集器日志核验；不能只比较FGC计数|

没有适用于所有应用的“总限额60%～70%”固定公式。扩容是否改善单实例负载，也取决于总请求量是否固定、流量如何分摊，不能简单写成“加机器无效”。

## 9. 诊断与回归：按证据逐步缩小范围

1. **确认配置与选择分支。**记录XStream版本、JDK版本、实际provider及GC参数，排除其他converter路径。
2. **核对GC原因。**在本文ParallelGC场景中，统计`Full GC (Metadata GC Threshold)`；CMS／G1还需结合各自周期日志。
3. **确认生成类。**短时开启类加载跟踪，计数目标accessor，而不是只看总类加载数。
4. **观察生成与卸载是否循环。**联合查看类计数、MU／MC、加载器统计，并保留采样时间。不同命令不是同一个原子快照。
5. **在相同负载下验证修复。**对比目标accessor数、GC原因、停顿分布、成功请求数与checksum。其他原因的GC仍可能发生。

```bash
# JDK8；启用类加载跟踪时应控制采集窗口和日志大小
jstat -class <pid> 2000
jstat -gc <pid> 2000
jcmd <pid> VM.classloader_stats

# 精确匹配目标类的加载记录
awk '/^\[Loaded sun\.reflect\.GeneratedSerializationConstructorAccessor[0-9]+ / {n++}
     END {print n+0}' trace.log

# 完整GC日志中的Full GC原因分布
# grep没有匹配时返回1，不表示Java运行失败
awk '/Full GC \(/ {s=$0; sub(/^.*Full GC \(/,"",s); sub(/\).*$/,"",s); n[s]++}
     END {for (s in n) print n[s], s}' gc.log
```

`VM.classloader_stats`可以观察加载器实例；`TraceClassLoading`里看到`DelegatingClassLoader`这个类加载一次，不意味着只创建了一个加载器实例。额外的`CompositeClassLoader`来自XStream自身，不能把它的实例计数直接当成JDK反射生成类数。

## 附录A：可复现实验

下载本页提供的实验与证据包。`lab/`保留LegacyProviderBench、Metrics、VersionProbe三份实验源码，`evidence/`保存历史主对照、本次复测与矩阵采样，`SHA256SUMS`记录校验值。仅使用包内固定可信XML。

请使用**JDK8的java、javac和Maven环境**。1.4.4是历史故障复现版本，不应用于处理不可信输入。

```bash
cd lab
# 如系统有多个JDK，应先让JAVA_HOME与PATH指向JDK8
java -version
mvn -q clean package
mvn -q dependency:build-classpath -Dmdep.outputFile=classpath.txt
CP="target/classes:$(cat classpath.txt)"

# 1）不同缓存生命周期；本程序会在初始化前设置测试vendor
java -XX:+TraceClassLoading -cp "$CP" -Dlegacy.bench.vendor="Oracle Corporation"   lab.LegacyProviderBench new 1 1000 > new-trace.log 2>&1
java -XX:+TraceClassLoading -cp "$CP" -Dlegacy.bench.vendor="Oracle Corporation"   lab.LegacyProviderBench static 1 1000 > static-trace.log 2>&1

# 2）同负载GC对照。分别单独运行，适合做性能比较
java -Xms1g -Xmx1g -XX:+UseParallelGC -XX:+PrintGCDetails   -XX:+PrintGCApplicationStoppedTime -Xloggc:new-gc.log   -cp "$CP" -Dlegacy.bench.vendor="Oracle Corporation"   lab.LegacyProviderBench new 4 50000 > new-app.log 2>&1
java -Xms1g -Xmx1g -XX:+UseParallelGC -XX:+PrintGCDetails   -XX:+PrintGCApplicationStoppedTime -Xloggc:static-gc.log   -cp "$CP" -Dlegacy.bench.vendor="Oracle Corporation"   lab.LegacyProviderBench static 4 50000 > static-app.log 2>&1

# 3）独立验证JDK8的序列化构造器生成行为
java -XX:+TraceClassLoading -cp "$CP" lab.VersionProbe rf 500 > rf.log 2>&1

# 4）保留真实vendor，检查默认provider；本机Corretto为PureJava
java -XX:+TraceClassLoading -Dlegacy.bench.keep.vendor=true   -cp "$CP" lab.LegacyProviderBench new 1 1000 > native-vendor.log 2>&1

# 5）历史变更对照：切换依赖并重新生成classpath；1.4.5不是生产推荐版本
mvn -q clean package dependency:build-classpath   -Dxstream.version=1.4.5 -Dmdep.outputFile=classpath.txt
CP="target/classes:$(cat classpath.txt)"
java -XX:+TraceClassLoading -cp "$CP" -Dlegacy.bench.vendor="Oracle Corporation"   lab.LegacyProviderBench new 1 1000 > upgrade-trace.log 2>&1
```

预期分别观察到1,000／1／500／0／0个目标accessor（native-vendor结果只适用于本文Corretto环境）。Full GC具体次数和耗时不要求复现为本文数值。`VersionProbe.rf`不进入其其他对象图模式。

## 附录B：证据与修订边界

|证据|内容|
|---|---|
|`evidence/history/A_144_new_200k/`|20万请求的app.log与完整gc.log|
|`evidence/history/B_144_static_800k/`|80万请求的app.log与完整gc.log|
|`evidence/history/M1…M8/`|各参数场景的app.log与samples.csv；目录保留原始名称|
|`evidence/history/T1_hwm128/`|仅存app.log、samples.csv；没有可核验的原始gc.log|
|`evidence/rerun/`|本次7组复测日志及rerun-results.json中的执行命令与结果|
|`review.md`|原文问题清单、修正依据及未完成验证|

本次没有重新运行全部历史参数矩阵、长时间高水位实验或独立Metaspace OOM实验；矩阵作为已有日志的再核查材料。也没有将单机耗时外推为生产吞吐率。

## 附录C：源码索引与阅读顺序

|源码|建议阅读位置|
|---|---|
|[XStream1.4.4：XStream.java](https://github.com/x-stream/xstream/blob/c4c71226515fa42809a48d9ae702756e2831f379/xstream/src/java/com/thoughtworks/xstream/XStream.java#L435)|构造器创建JVM辅助对象并选择provider；272行起为线程安全说明|
|[1.4.4：JVM.java](https://github.com/x-stream/xstream/blob/c4c71226515fa42809a48d9ae702756e2831f379/xstream/src/java/com/thoughtworks/xstream/core/JVM.java#L241)|bestReflectionProvider与厂商判断|
|[1.4.4：AbstractReflectionConverter.java](https://github.com/x-stream/xstream/blob/c4c71226515fa42809a48d9ae702756e2831f379/xstream/src/java/com/thoughtworks/xstream/converters/reflection/AbstractReflectionConverter.java#L419)|instantiateNewInstance|
|[1.4.4：Sun14ReflectionProvider.java](https://github.com/x-stream/xstream/blob/c4c71226515fa42809a48d9ae702756e2831f379/xstream/src/java/com/thoughtworks/xstream/converters/reflection/Sun14ReflectionProvider.java#L61)|实例缓存及getMungedConstructor|
|[1.4.5：Sun14ReflectionProvider.java](https://github.com/x-stream/xstream/blob/6263a53e8b8c4d1b092a32fa1abcadb6acfce45b/xstream/src/java/com/thoughtworks/xstream/converters/reflection/Sun14ReflectionProvider.java#L62)|newInstance改用Unsafe.allocateInstance|
|[JDK8u462：ReflectionFactory.java](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/jdk/src/share/classes/sun/reflect/ReflectionFactory.java#L353)|序列化构造器fast path与生成路径；与本机src.zip交叉核对|
|[JDK8u462：MethodAccessorGenerator.java](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/jdk/src/share/classes/sun/reflect/MethodAccessorGenerator.java#L763)|类名自增与字节码生成|
|[JDK8u462：ClassDefiner.java](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/jdk/src/share/classes/sun/reflect/ClassDefiner.java#L54)|每个生成类的新DelegatingClassLoader|
|[JDK8u462：metaspace.cpp](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/memory/metaspace.cpp#L1488)|can_expand、allowed_expansion、compute_new_size及分配失败处理|
|[JDK8u462：vmGCOperations.cpp](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/gc_implementation/shared/vmGCOperations.cpp)|VM_CollectForMetadataAllocation的回收与重试分支|

阅读时先看“实例缓存→每次生成”的Java路径，再看“扩展受限→GC重试”的HotSpot路径。两条链衔接起来，才能解释为什么对象可以回收，系统仍不断付出类加载和GC的代价。
