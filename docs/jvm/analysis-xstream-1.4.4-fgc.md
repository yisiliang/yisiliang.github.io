# 每个请求都new XStream()，为什么会增加CMS回收压力？

一段XML反序列化代码，每次调用都创建一个XStream。XML很小，解析出来的对象也没有被缓存。请求结束后，对象就可以回收，看起来不会留下多少内存负担。

```java
public Order parse(String xml) {
    XStream xstream = new XStream();
    xstream.alias("order", Order.class);
    return (Order) xstream.fromXML(xml);
}
```

运行环境是Oracle JDK8、XStream1.4.4，使用CMS。XStream选择`Sun14ReflectionProvider`创建对象，每请求新建实例会持续生成反射类，增加元空间的回收压力。

问题出在XStream为对象准备构造器的方式上。1.4.4的`Sun14ReflectionProvider`会生成一个反射类，并将构造器缓存在自己的实例字段中。每个请求重新创建XStream，也就重新创建了这份缓存。同一种业务对象在上一个请求里生成过的反射类，到了下一个请求又要生成一遍。

这些类可以在CMS周期中卸载。持续的请求会让元空间反复积累，促使CMS启动回收；如果等待并发回收期间仍无法满足元数据分配，还可能进入停顿式Full GC。

## 1. 解析一个对象，为什么会加载新类？

实验只解析一个`Order`，包含String类型的`id`和int类型的`amount`：

```xml
<order><id>10001</id><amount>128</amount></order>
```

Oracle JDK8的`java.vm.vendor`为`Oracle Corporation`，XStream1.4.4会据此选择`Sun14ReflectionProvider`。

一组已有JDK8参考实验执行了20万次请求，总加载类数增量为200,660。每个请求只解析一种POJO，类加载量却几乎与请求数相同。后文用这组记录说明反射类的生成规律；CMS是否发生Full GC、发生多少次，需要看业务进程的CMS日志。

## 2. XStream把构造器缓存在哪里？

### 每个XStream都有自己的provider

XStream的构造器会创建一个`JVM`辅助对象，再通过它选择反射provider。1.4.4的`XStream.java`构造器开头如下：

```java
    public XStream(
        ReflectionProvider reflectionProvider, HierarchicalStreamDriver driver,
        ClassLoader classLoader, Mapper mapper, ConverterLookup converterLookup,
        ConverterRegistry converterRegistry) {
        jvm = new JVM();
        if (reflectionProvider == null) {
            reflectionProvider = jvm.bestReflectionProvider();
        }
        this.reflectionProvider = reflectionProvider;
```

`bestReflectionProvider()`检查厂商、Java版本以及内部类是否可用。条件满足时，它创建`Sun14ReflectionProvider`；否则回退到`PureJavaReflectionProvider`。这个provider保存在当前`JVM`辅助对象上，随XStream实例一起使用。

因此，每次`new XStream()`都会得到一套新的provider及其缓存。

要确认线上是否走这条路径，可以直接打印：

```java
System.out.println(xstream.getReflectionProvider().getClass().getName());
```

Oracle JDK8下，这里应输出`com.thoughtworks.xstream.converters.reflection.Sun14ReflectionProvider`。

### 第一次遇到一种业务类，就生成一个构造器

普通POJO由反射转换器处理。它在创建对象时调用`reflectionProvider.newInstance(type)`，进入`Sun14ReflectionProvider.newInstance()`，后者再调用`getMungedConstructor(type)`。

缓存字段定义在`Sun14ReflectionProvider`实例上：

```java
    private transient ReflectionFactory reflectionFactory = ReflectionFactory.getReflectionFactory();
    private transient Map constructorCache =new HashMap();
```

`getMungedConstructor()`的代码是问题所在：

```java
    private Constructor getMungedConstructor(Class type) throws NoSuchMethodException {
        synchronized (constructorCache) {
            Constructor ctor = (Constructor)constructorCache.get(type);
            if (ctor == null) {
                ctor = reflectionFactory.newConstructorForSerialization(type, Object.class.getDeclaredConstructor(new Class[0]));
                constructorCache.put(type, ctor);
            }
            return ctor;
        }
    }
```

第一次解析`Order`时，缓存里没有这个Class，于是调用`newConstructorForSerialization()`，生成构造器并放进缓存。同一个XStream再次解析`Order`，就会命中缓存。

如果下一个请求创建了新的XStream，这份缓存又是空的。虽然处理的仍是同一个`Order.class`，却需要再生成一次构造器。

缓存按Class计数。一个请求中有100个Order对象，当前provider也只需要为Order生成一次构造器；如果对象图中有Order和Customer两种走此路径的业务类，则各生成一次。重复生成的数量，取决于创建了多少个provider，以及每个provider实际遇到了多少种业务类。

另外，1.4.4的这条实例化路径直接取得合成构造器，并不会先尝试业务类自己的无参构造器。实验中的Order本来就有无参构造器，仍然会触发类生成。

## 3. 一个构造器，为什么会变成一个新类？

`newConstructorForSerialization()`是JDK内部为序列化准备构造器的方法。XStream传入两个参数：要创建的业务类，以及`Object`的无参构造器。

JDK8的实现如下：

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

只有“要创建的类”与“构造器所属的类”相同时，才直接返回已有构造器。这里分别是Order和Object，因而会调用`generateConstructor()`。

`generateConstructor()`首先通过`MethodAccessorGenerator`生成一个`ConstructorAccessor`，再将它装入新构造器。下面是方法开头的节选：

```java
    private final Constructor<?> generateConstructor(Class<?> classToInstantiate,
                                                     Constructor<?> constructorToCall) {


        ConstructorAccessor acc = new MethodAccessorGenerator().
            generateSerializationConstructor(classToInstantiate,
                                             constructorToCall.getParameterTypes(),
                                             constructorToCall.getExceptionTypes(),
                                             constructorToCall.getModifiers(),
                                             constructorToCall.getDeclaringClass());
```

生成类的名称是`sun.reflect.GeneratedSerializationConstructorAccessorN`，末尾的数字递增。生成好的字节码交给`ClassDefiner`定义：

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

每次定义类时，都会创建一个新的`DelegatingClassLoader`。JDK这样做，是为了让生成类能够单独卸载，而不必等业务类的加载器一起回收。

这次类生成发生在调用`newConstructorForSerialization()`时。它没有跨调用缓存，也不需要等到反射调用达到某个次数。普通`Method.invoke()`的inflation机制解释不了这里的现象。

打开`-XX:+TraceClassLoading`后，可以直接看到这些类。下面这组类生成参考实验记录于2026年10月8日：

|运行方式|请求或调用数|生成的序列化accessor类|
|---|---:|---:|
|1.4.4，每请求新建XStream|1,000|1,000|
|1.4.4，复用一个XStream|1,000|1|
|1.4.5，每请求新建XStream|1,000|0|

实验只处理一种POJO，因此每请求新建实例时，恰好每个请求生成一个accessor。复用实例后，只有第一次解析需要生成。

总类加载数会稍大一些，因为初始化XStream、执行监控以及其他反射操作也会加载类。判断这条路径的生成量，应计数`GeneratedSerializationConstructorAccessor`的加载记录。

## 4. 请求结束以后，这些类去哪了？

构造器缓存在XStream实例内，引用关系可以简化为：

```text
XStream
  └─ Sun14ReflectionProvider
       └─ constructorCache
            └─ Constructor
                 └─ ConstructorAccessor实例
                      └─ 生成类及其DelegatingClassLoader
```

这些Java对象位于堆中；生成类的元数据由Metaspace保存。请求结束后，如果没有其他引用留下，XStream、构造器和临时加载器都可以变成垃圾。

临时加载器虽然指向长期存活的业务类加载器，但父加载器不会因为这个关系就反向持有它。业务类仍在使用，临时accessor类依然可以卸载。

CMS通过`CMSClassUnloadingEnabled`控制是否在收集周期中卸载类。开启后，不可达的临时加载器及其类元数据可以在CMS周期中被清理，普通Young GC不会完成这项工作。

随着请求继续执行，未卸载的类越来越多，元空间需要扩展。元数据分配压力可以促使CMS启动收集，回收后用量下降；后续请求又生成新的类，于是用量再次上涨。关闭类卸载，或临时加载器仍然被引用，都会影响这轮回收能释放多少空间。

CMS周期包含初始标记和重新标记等停顿阶段，其余工作主要并发进行。监控里的FGC计数需要结合CMS日志解读，不能只凭计数增长就认定发生了一次全程停顿式Full GC。

## 5. MetaspaceSize在CMS下怎样起作用？

### 高水位控制扩展额度

元空间有两个常见指标：`used`是已经存放元数据的空间，`committed`是JVM已经提交的容量。GC高水位控制的是扩展额度，与某次日志里的used不是同一个量。

JDK8的`MetaspaceGC::allowed_expansion()`计算还能扩展多少：

```cpp
size_t MetaspaceGC::allowed_expansion() {
  size_t committed_bytes = MetaspaceAux::committed_bytes();
  size_t capacity_until_gc = capacity_until_GC();

  assert(capacity_until_gc >= committed_bytes,
        err_msg("capacity_until_gc: " SIZE_FORMAT " < committed_bytes: " SIZE_FORMAT,
                capacity_until_gc, committed_bytes));

  size_t left_until_max  = MaxMetaspaceSize - committed_bytes;
  size_t left_until_GC = capacity_until_gc - committed_bytes;
  size_t left_to_commit = MIN2(left_until_GC, left_until_max);

  return left_to_commit / BytesPerWord;
}
```

它分别计算距离最大容量和GC高水位还有多少余量，取较小值。当现有空间不够、扩展额度也不足时，元数据分配可以失败，随后进入GC及分配重试流程。

`Metaspace::allocate()`在分配失败后调用`CollectorPolicy::satisfy_failed_metadata_allocation()`，由`VM_CollectForMetadataAllocation`处理。启用CMS并且开启类卸载时，源码会设置请求并发收集的标志：

```cpp
  if (UseConcMarkSweepGC && CMSClassUnloadingEnabled) {
    MetaspaceGC::set_should_concurrent_collect(true);
    return true;
  }
```

接着，JVM尝试扩展元空间并满足当前分配，为CMS并发回收留出时间。如果扩展成功，请求可以继续；如果仍然无法分配，就进入`collect_as_vm_thread(Metadata GC Threshold)`的回收路径，并在回收后重试。继续失败时，还会尝试扩展及最后一次回收，最终无法满足分配才报告OOM。

因此，`MetaspaceSize`影响的是**因元数据压力启动回收的初始高水位**。它并不规定“到这个值就必须发生一次停顿式Full GC”。在CMS下，先请求并发回收、扩展是否成功，以及类能否卸载，都影响后续走哪条路径。

`MetaspaceSize`还作为JDK8高水位调整的下界。GC后，高水位会根据committed及空闲比例调整；`MaxMetaspaceSize`则限制元空间的最大提交容量。设置128m，不意味着used必须涨到128MiB才启动回收，因为used和committed本来就不是同一个量。

### 调大堆和调大高水位，效果不同

`Xmx`控制Java堆，调大它不会减少反射类的生成，也不会直接抬高元空间的GC高水位。

调大`MetaspaceSize`可以推迟元数据压力触发的CMS收集，但也会让更多临时元数据积累。是否能减少停顿，需要同时看CMS周期、元空间扩展情况和业务延迟。每请求生成新类的代码没有改变，调参只是改变了回收时机。

## 6. 改成复用实例以后

一组已有JDK8参考实验比较了新建和复用实例的类加载量：

|指标|每请求新建XStream|复用一个XStream|
|---|---:|---:|
|完成请求|200,000|200,000|
|总加载类数增量|200,660|171|

复用以后，Order的构造器已经缓存，后续请求不再持续生成序列化accessor。剩余类加载主要来自初始化和其他运行开销。

在CMS环境中，这项改动减少了元空间中的临时类，以及相关的加载、卸载和回收工作。是否消除了业务系统中的Full GC，还要核对CMS日志中的触发原因和改造前后的结果。

实现上，只需把XStream的创建和配置移出请求方法：

```java
private static final XStream XSTREAM = createXStream();

private static XStream createXStream() {
    XStream xstream = new XStream();
    xstream.alias("order", Order.class);
    return xstream;
}

public Order parse(String xml) {
    return (Order) XSTREAM.fromXML(xml);
}
```

也可以交给依赖注入容器管理一个长期实例。关键是让构造器缓存得以复用。

XStream允许多个线程共享已经完成配置的实例。alias、converter和注解配置应在使用前完成，请求过程中不要继续修改；开启动态注解自动发现时，以及使用自定义converter时，还需要检查相应的并发行为。具体约束见[官方FAQ](https://x-stream.github.io/faq.html)。

## 7. 升级为什么能解决问题？

XStream1.4.4创建Order对象时，会先准备一个特殊构造器。JDK为这个构造器生成一个反射类，XStream再把构造器放进当前实例的缓存。下一个请求重新创建XStream，缓存又是空的，同样的反射类就要再生成一个。

从1.4.5开始，`Sun14ReflectionProvider`改用`Unsafe.allocateInstance(type)`创建对象。它可以直接分配Order实例，跳过构造方法，不再需要为此生成序列化构造器的反射类。

|版本|创建Order对象的方式|每请求新建XStream的结果|
|---|---|---|
|1.4.4|生成反射类，通过合成构造器创建对象|每个请求都为Order生成一个新的反射类|
|1.4.5|通过Unsafe直接分配对象|创建Order时不再生成这类反射类|

因此，即使仍然每请求新建XStream，升级也能消除这条路径上的重复类生成，减少CMS需要卸载的临时类。参考实验中，1,000次请求生成的序列化accessor类从1,000个降到了0个。

不过，每次创建和配置XStream本身也有开销。升级后仍然建议复用完成配置的实例。

这里提到1.4.5，是为了说明创建方式从哪个版本开始改变。实际升级应选择符合业务兼容性和安全要求的版本，参阅[版本历史](https://x-stream.github.io/changes.html)及[安全说明](https://x-stream.github.io/security.html)。

## 8. 在业务系统里怎样确认

先记录实际XStream版本、JDK版本和provider类名，并确认CMS的类卸载配置。日志中要同时看元数据触发原因、CMS周期、回收后的元空间用量，以及是否出现停顿式Full GC。

```bash
jstat -gc <pid> 2000
jstat -class <pid> 2000
jcmd <pid> VM.classloader_stats
jcmd <pid> VM.flags -all
```

检查`UseConcMarkSweepGC`和`CMSClassUnloadingEnabled`的实际值。MU、MC上升后回落，卸载类数随之增长，说明类在反复生成和清理。如果卸载很少、GC后的用量也持续升高，就应进一步检查加载器的引用、存活类数量和类卸载选项。

要确认生成的究竟是什么类，可以在测试环境短时开启`-XX:+TraceClassLoading`，匹配加载记录：

```bash
awk '/^\[Loaded sun\.reflect\.GeneratedSerializationConstructorAccessor[0-9]+ / {n++}
     END {print n+0}' trace.log
```

以下命令只统计日志中明确标为Full GC的事件；CMS并发周期的初始标记、重新标记和并发阶段应另外查看：

```bash
awk '/Full GC \(/ {
    s=$0
    sub(/^.*Full GC \(/,"",s)
    sub(/\).*$/,"",s)
    n[s]++
}
END {for (s in n) print n[s], s}' gc.log
```

`TraceClassLoading`记录的是类的加载。看到`DelegatingClassLoader`这个类只加载一次，并不表示只创建了一个加载器实例；实例数量要看`VM.classloader_stats`等工具。多个采集命令执行的时刻不同，比较数据时也要保留时间戳。

改造后，用同样的请求量再跑一次。应看到序列化accessor不再随请求数持续增加，元空间用量趋于稳定，相应的元数据GC压力下降。

## 附录：源码索引

JDK反射和HotSpot实现参考OpenJDK8u462源码。

|源码|建议阅读位置|
|---|---|
|[XStream1.4.4：XStream.java](https://github.com/x-stream/xstream/blob/c4c71226515fa42809a48d9ae702756e2831f379/xstream/src/java/com/thoughtworks/xstream/XStream.java#L432)|构造器创建JVM辅助对象并选择provider；272行起为线程安全说明|
|[1.4.4：JVM.java](https://github.com/x-stream/xstream/blob/c4c71226515fa42809a48d9ae702756e2831f379/xstream/src/java/com/thoughtworks/xstream/core/JVM.java#L241)|bestReflectionProvider与厂商判断|
|[1.4.4：AbstractReflectionConverter.java](https://github.com/x-stream/xstream/blob/c4c71226515fa42809a48d9ae702756e2831f379/xstream/src/java/com/thoughtworks/xstream/converters/reflection/AbstractReflectionConverter.java#L419)|instantiateNewInstance|
|[1.4.4：Sun14ReflectionProvider.java](https://github.com/x-stream/xstream/blob/c4c71226515fa42809a48d9ae702756e2831f379/xstream/src/java/com/thoughtworks/xstream/converters/reflection/Sun14ReflectionProvider.java#L61)|实例缓存及getMungedConstructor|
|[1.4.5：Sun14ReflectionProvider.java](https://github.com/x-stream/xstream/blob/6263a53e8b8c4d1b092a32fa1abcadb6acfce45b/xstream/src/java/com/thoughtworks/xstream/converters/reflection/Sun14ReflectionProvider.java#L62)|newInstance改用Unsafe.allocateInstance|
|[JDK8u462：ReflectionFactory.java](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/jdk/src/share/classes/sun/reflect/ReflectionFactory.java#L353)|序列化构造器fast path与生成路径|
|[JDK8u462：MethodAccessorGenerator.java](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/jdk/src/share/classes/sun/reflect/MethodAccessorGenerator.java#L763)|类名自增与字节码生成|
|[JDK8u462：ClassDefiner.java](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/jdk/src/share/classes/sun/reflect/ClassDefiner.java#L54)|每个生成类的新DelegatingClassLoader|
|[JDK8u462：metaspace.cpp](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/memory/metaspace.cpp#L1488)|can_expand、allowed_expansion、compute_new_size及分配失败处理|
|[JDK8u462：CMS实现](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/gc_implementation/concurrentMarkSweep/concurrentMarkSweepGeneration.cpp)|CMS周期与类卸载|
|[JDK8u462：vmGCOperations.cpp](https://github.com/openjdk/jdk8u/blob/jdk8u462-b08/hotspot/src/share/vm/gc_implementation/shared/vmGCOperations.cpp)|VM_CollectForMetadataAllocation的回收与重试分支|
