"""离线构建 HTML：pip install markdown beautifulsoup4；部署只需生成产物。"""
from pathlib import Path
import json,re,html,sys,hashlib
import markdown
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent
sources=json.loads((ROOT/'sources.json').read_text())
notes=json.loads((ROOT/'source-notes.json').read_text())
anchors=json.loads((ROOT/'anchors.json').read_text())
refs={1:['aqs','lock','pool'],2:['hashmap','chm'],3:['cms','g1'],4:['bits','xstream'],5:['beans','tx','boot'],6:['mvcc','pg','oracle'],7:['commitlog','mqsend','mqtx'],8:['redis','redislock'],9:['tx','mqtx'],10:['netty','reactor','gateway']}
meta={
'aqsqueue':('OpenJDK 8u462-b08','AbstractQueuedSynchronizer.acquireQueued','java'),
'chmput':('OpenJDK 8u462-b08','ConcurrentHashMap.putVal','java'),
'xstream':('XStream 1.4.4 / c4c7122','Sun14ReflectionProvider.getMungedConstructor','java'),
'aqs':('OpenJDK 8u462-b08','AbstractQueuedSynchronizer.acquire','java'),
'lock':('OpenJDK 8u462-b08','ReentrantLock.Sync.nonfairTryAcquire','java'),
'pool':('OpenJDK 8u462-b08','ThreadPoolExecutor.execute','java'),
'hashmap':('OpenJDK 8u462-b08','HashMap.hash','java'),
'chm':('OpenJDK 8u462-b08','ConcurrentHashMap.transfer','java'),
'bits':('OpenJDK 8u462-b08','Bits.tryReserveMemory','java'),
'cms':('HotSpot 8u462-b08','CMSCollector::collect_in_background','cpp'),
'g1':('HotSpot 8u462-b08','G1CollectedHeap::do_collection_pause_at_safepoint','cpp'),
'beans':('Spring Framework 5.3.31','DefaultSingletonBeanRegistry.getSingleton','java'),
'tx':('Spring Framework 5.3.31','TransactionAspectSupport.invokeWithinTransaction','java'),
'boot':('Spring Boot 2.7.18','AutoConfigurationImportSelector.getCandidateConfigurations','java'),
'mvcc':('MySQL 8.0.36','ReadView::changes_visible','cpp'),
'commitlog':('RocketMQ 4.9.8','CommitLog.asyncPutMessage','java'),
'mqtx':('RocketMQ 4.9.8','TransactionalMessageServiceImpl.check','java'),
'mqsend':('RocketMQ 4.9.8','DefaultMQProducerImpl.sendMessageInTransaction','java'),
'redis':('Redis 7.2.4','dbDelete','c'),
'redislock':('Redis 7.2.4','setGenericCommand','c'),
'netty':('Netty 4.1.108.Final','NioEventLoop.run','java'),
'reactor':('Reactor 3.4.34','FluxPublishOn.onNext','java'),
'gateway':('Spring Cloud Gateway 3.1.8','FilteringWebHandler.handle','java')}
extra_refs={3:[('Oracle JDK8 GC Tuning Guide','https://docs.oracle.com/javase/8/docs/technotes/guides/vm/gctuning/')],4:[('Netty 引用计数指南','https://netty.io/wiki/reference-counted-objects.html')],6:[('MySQL 一致性读','https://dev.mysql.com/doc/refman/8.0/en/innodb-consistent-read.html'),('OceanBase 官方文档（须选择实际租户版本）','https://en.oceanbase.com/docs')],7:[('RocketMQ 5.x 事务消息与版本边界','https://rocketmq.apache.org/docs/featureBehavior/04transactionmessage/'),('RocketMQ 5.3.4 源码对照','https://github.com/apache/rocketmq/tree/rocketmq-all-5.3.4')],8:[('Redis 分布式锁边界','https://redis.io/docs/latest/develop/use/patterns/distributed-locks/'),('Redisson 锁与 Watchdog','https://redisson.pro/docs/data-and-services/locks-and-synchronizers/')],9:[('CAP 原论文 Gilbert/Lynch','https://groups.csail.mit.edu/tds/papers/Gilbert/Brewer2.pdf')],10:[('Reactor 3.4.34 Reference','https://projectreactor.io/docs/core/3.4.34/reference/')]}
points=[
['volatile 让相关写入可见，但 count++ 仍可能被两个线程交错执行。','AQS 获取失败后排队，被唤醒后还要再次尝试拿锁。','公平 ReentrantLock 的无参数 tryLock 仍可能插队。','LongAdder 适合统计，不适合检查余额后扣款。','线程池先 core，再队列，队列满才试 max；无界队列会积压。'],
['扩容翻倍后，元素留在原桶，或移到原下标加旧容量。','容量不足 64 时优先扩容，不能只用链长 8 判断树化。','JDK 8 HashMap 仍可能并发覆盖，fail-fast 不保护写入。','CHM 空桶用 CAS，非空桶锁桶，旧桶用 ForwardingNode 指向新表。','size 不是并发快照，computeIfAbsent 避免慢 IO。'],
['TLAB 在堆里，只优化分配，对象仍能交给其他线程。','CMS 初标和重标暂停，正常周期清扫不整理，要留分配余量。','G1 RSet 找外部引用，SATB 记录被覆盖的旧引用。','Mixed 回收 Young 与部分 Old；暂停目标不是每次保证。','JDK 8 G1 Full GC 单线程，大对象和搬迁空间要单独检查。'],
['先按完整 OOM 报错区分堆、类元数据、Direct、线程与容器限额。','用 GC 后占用、MAT 持有链和代码解释为什么对象仍活着。','Cleaner 与 ByteBuf 引用计数是不同释放机制。','NMT reserved、committed 与 RSS 不是同一个数字。','修复后重放相同条件，还要测拒绝、异常和取消。'],
['Bean 实例化与注入之后，初始化和后处理器参与代理。','三级缓存只解决部分单例循环，Boot 2.7 默认禁止循环引用。','事务入口在代理，this 自调用和异步线程不会自动经过它。','REQUIRES_NEW 再借一条连接，NESTED 常用同事务保存点。','Boot 2.7 同时读取两类自动配置候选，排查先看条件报告。'],
['Read View 判断版本可见性，不可见沿 Undo 找旧版本。','RC 通常逐语句快照，RR 通常第一次一致性读后复用。','普通快照读与 UPDATE/FOR UPDATE 的当前读不同。','实际索引扫描决定成本和锁范围，不只是最终返回行数。','跨库要核对数据与隔离含义，迁移保证快照、CDC 与对账。'],
['CommitLog 存主体，ConsumeQueue 存队列索引，IndexFile 帮 key 查询。','发送超时可能已写入，刷盘与复制确认是不同保障。','业务提交后未保存消费位置可能重收，消费去重与业务同事务。','同 key 队列加顺序消费，还要防异步处理和版本乱序。','Half 后的结果要可持久回查，清积压靠完成率真正超过到达率。'],
['主命令线程串行，IO 多线程不表示命令全部并行。','RDB、AOF 与异步复制各有恢复和丢失窗口。','写库后删缓存仍可能被慢读回填，双删不是绝对保证。','token 和 Lua 防误删，租期过后旧 owner 仍可能写业务。','热点合并与总回源限额一起做，缓存宕机也要保护数据库。'],
['先说明支付、订单和保单有哪些结果必须成立。','2PC 需协议；TCC 预留可确认撤销；Saga 补偿是新业务动作。','Outbox 同事务保存待发事件，发送后标记前死机会重复。','消费唯一事件与业务同事务，外部调用用稳定幂等键。','超时是未知，保留查询、重试、对账和人工恢复办法。'],
['一个 EventLoop 处理多个连接，阻塞 JDBC 会影响其他连接。','subscribeOn 影响源执行，publishOn 影响后续信号。','背压仍需有界队列，timeout 不保证底层 SQL 已停。','重试会放大工作量，限制总次数、等待和依赖并发。','容量按实际耗时验证，灰度保证标签传播和数据可回退。']]

route=[('0–8 分钟',1,'JMM、AQS 与线程池准入'),('8–15 分钟',2,'CHM 迁移协议与原子 API'),('15–24 分钟',3,'CMS/G1 正常、失败与恢复'),('24–32 分钟',4,'OOM 分类与证据链'),('32–40 分钟',5,'代理、事务与连接预算'),('40–49 分钟',6,'MVCC、锁与执行计划'),('49–64 分钟',7,'RocketMQ 五类失败边界'),('64–72 分钟',8,'缓存一致性与锁租约'),('72–81 分钟',9,'Outbox、幂等与补偿'),('81–90 分钟',10,'EventLoop、重试与容量')]
nav=[];articles=[];names=[];expanded_texts=[]; stats={'chapters':10,'questions':0,'diagrams':0,'code_blocks':0}
for n,file in enumerate(sorted((ROOT/'chapters').glob('*.md')),1):
 text=file.read_text();name=text.splitlines()[0][2:];names.append(name)
 def insert_source(m):
  key=m.group(1);s=sources[key];version,method,lang=meta[key]
  url=s['url'].replace('raw.githubusercontent.com/','github.com/',1)
  seg=url.split('/'); url='/'.join(seg[:5]+['blob']+seg[5:]) if 'github.com' in url else url
  url+=f"#L{s['line']}-L{s['end_line']}"
  return f'\n<div class="source-caption"><code>{method}</code><span>{version} · L{s["line"]}–L{s["end_line"]} · <a href="{url}">完整源码</a></span></div>\n\n```{lang}\n{s["excerpt"]}\n```\n\n{notes[key]}\n'
 text=re.sub(r'<!-- source:(\w+) -->',insert_source,text)
 text+='\n\n## 官方资料与版本来源\n\n本文按上述版本阅读官方源码，节选可能省略方法的其他分支。版权见 [source-notices.txt](./source-notices.txt)，下载记录见 [sources.json](./sources.json)。\n\n'
 for key in refs[n]:
  s=sources[key];label=meta[key][1]+' · '+meta[key][0] if key in meta else ('PostgreSQL16 隔离级别' if key=='pg' else 'Oracle19c 并发与一致性')
  text+=f'- [{label}]({s["url"]})\n'
 for label,url in extra_refs.get(n,[]):text+=f'- [{label}]({url})\n'
 expanded_texts.append(text)
 body=BeautifulSoup(markdown.markdown(text,extensions=['fenced_code','tables','md_in_html']), 'html.parser')
 body.h1.decompose();heads=body.find_all(['h2','h3']);sub=[]
 for i,h in enumerate(heads,1):
  registry=anchors.setdefault(f'c{n}',{})
  if h.get_text() not in registry:
   last=max([int(v.rsplit('-s',1)[1]) for v in registry.values()] or [0])
   registry[h.get_text()]=f'c{n}-s{last+1}'
  h['id']=registry[h.get_text()];h['tabindex']='-1'
  if h.name=='h2':sub.append(f'<a href="#{h["id"]}">{html.escape(h.get_text())}</a>')
 for code in body.select('code.language-shell'):code['class']=['language-bash']
 for code in body.select('code.language-mermaid'):
  stats['diagrams']+=1;pre=code.parent;diagram=body.new_tag('figure',attrs={'class':'diagram','data-diagram':str(stats['diagrams'])});
  pre['class']=['mermaid']; pre.string=code.get_text();pre.replace_with(diagram);diagram.append(pre)
  cap=body.new_tag('figcaption');cap.string=f'图 {stats["diagrams"]} · 对照上文阅读流程';diagram.append(cap)
 stats['code_blocks']+=len(body.select('pre:not(.mermaid)'));stats['questions']+=len(body.select('details'))
 # 让问题本身成为展开按钮，省去题目下重复的“查看答案”行。
 for d in body.select('details'):
  h=d.find_previous_sibling('h3')
  if not h: continue
  d['class']=['question']
  summary=d.summary;summary.clear();summary.append(h.extract())
  answer=body.new_tag('div',attrs={'class':'answer'})
  for child in list(d.children):
   if child is not summary:answer.append(child.extract())
  d.append(answer)
 # 速查保留重点问题与短回答。
 questions=body.select('details')[:(5 if n==7 else 4)];qa=''
 for d in questions:
  clone=BeautifulSoup(str(d),'html.parser')
  title=clone.summary.h3
  if title:title.name='span';title.attrs={'class':'question-title'}
  for el in clone.select('[id]'):del el['id']
  qa+=str(clone)
 def paragraph_after(title):
  h=next(x for x in body.find_all('h3') if x.get_text()==title)
  result=[]
  for el in h.next_siblings:
   if getattr(el,'name',None) in ['h2','h3']:break
   if getattr(el,'name',None) in ['p','ul','ol']:result.append(str(el))
  return ''.join(result)
 quick=f'<section class="quick" aria-label="面试速查"><h2 id="c{n}-quick-core">先记住这几件事</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in points[n-1])+f'</ul><h2 id="c{n}-quick-qa">{"五" if n==7 else "四"}个重点问题</h2>'+qa+f'<h2 id="c{n}-quick-answer">一分钟回答</h2>'+paragraph_after('60 秒快速回答')+f'<h2 id="c{n}-quick-errors">容易答错的地方与源码</h2>'+paragraph_after('高频追问、常见错误与速记')+'</section>'
 nav.append(f'<details class="chapter-nav" data-chapter="c{n}"><summary><a href="#c{n}"><span>{n:02}</span>{html.escape(name)}</a></summary><div>'+''.join(sub)+'</div></details>')
 articles.append(f'<article class="chapter" id="c{n}" data-title="{html.escape(name)}"><div class="chapter-title"><p class="eyebrow">专题 {n:02} / 完整阅读</p><h1>{html.escape(name)}</h1></div><div class="study">{body}</div>{quick}</article>')
route_html='<section id="review-route" class="route"><h2>90 分钟复习路线</h2><p>按下面顺序复习，先用 60 秒回答口述，再展开重点追问；RocketMQ 留 15 分钟。</p><ol>'+''.join(f'<li><time>{t}</time><a href="#c{n}">{title}</a></li>' for t,n,title in route)+'</ol></section>'
head='''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="Java 高级开发与架构师面试深度学习手册：JDK8 源码、RocketMQ、JVM 故障排查及分布式一致性，十个专题和三层问答。"><title>Java 架构师面试 · 深度学习手册</title><link rel="stylesheet" href="./style.css"><script src="./theme.js"></script><script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script><script defer src="./vendor/prism.js" data-manual></script><script defer src="./vendor/prism-c.js"></script><script defer src="./vendor/prism-cpp.js"></script><script defer src="./vendor/prism-java.js"></script><script defer src="./vendor/prism-sql.js"></script><script defer src="./vendor/prism-bash.js"></script><script defer src="./vendor/prism-yaml.js"></script><script defer src="./app.js"></script></head><body>
<a class="skip" href="#main">跳到正文</a>
<header class="topbar"><button id="menu" class="mobile" aria-label="打开章节导航" aria-expanded="false" aria-controls="left-nav">目录</button><div class="brand">Java 面试手册<span>Java 8 · Spring 5 · RocketMQ</span></div><div class="tools"><button id="search-open" aria-label="打开全文搜索">搜索 <kbd>/</kbd></button><button id="mode" aria-pressed="false">面试速查</button><button id="theme" aria-label="切换主题">主题：系统</button></div></header>
<div class="progress-track" aria-hidden="true"><div id="progress-bar"></div></div><div id="drawer-backdrop" hidden></div>
<div class="layout"><nav id="left-nav" aria-label="技术专题"><p class="nav-label">学习目录 / 10 个专题</p>'''
intro='''<main id="main" tabindex="-1"><section class="intro"><h1>Java 高级开发与架构师面试</h1><p>从具体问题读原理，再对照源码。十个专题都附有追问、故障排查和可直接口述的回答。面试前可切到速查模式。</p><noscript><p>JavaScript 已关闭，正文、问答与图表仍可阅读；搜索、复制和模式切换需要启用它。</p></noscript></section>'''
end='''</main><aside id="right-toc" aria-label="当前专题目录"><div class="reading"><span id="progress-text">阅读进度 0%</span><span id="current-label"></span></div><p class="nav-label">本篇目录</p><nav id="toc"></nav></aside></div>
<dialog id="search-dialog" aria-labelledby="search-title"><div class="search-head"><h2 id="search-title">全文搜索</h2><button id="search-close" aria-label="关闭搜索">关闭</button></div><label for="search-input">搜索关键词、源码方法或面试问题</label><input id="search-input" type="search" placeholder="例如：sizeCtl、事务回查、Direct buffer" autocomplete="off"><p id="search-status" role="status" aria-live="polite">输入关键词，搜索十个专题的完整正文与答案。</p><div id="search-results"></div></dialog><div id="toast" role="status" aria-live="polite"></div>
<footer>按章标注源码版本 · 故障案例为模拟情境 · <a href="./handbook.md">下载 Markdown 正文</a> · <a href="./VERIFICATION.md">验证范围</a></footer></body></html>'''
for asset in ['style.css','app.js','theme.js']:
 token=hashlib.sha256((ROOT/asset).read_bytes()).hexdigest()[:10]
 head=head.replace('./'+asset+'"','./'+asset+'?v='+token+'"')
(ROOT/'index.html').write_text(head+''.join(nav)+'<a class="route-link" href="#review-route">90 分钟复习路线</a></nav>'+intro+route_html+''.join(articles)+end)
(ROOT/'handbook.md').write_text('# Java 架构师面试深度学习手册\n\n'+ '\n\n---\n\n'.join(expanded_texts))
(ROOT/'anchors.json').write_text(json.dumps(anchors,ensure_ascii=False,indent=2))
(ROOT/'content-stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2));print(stats)
