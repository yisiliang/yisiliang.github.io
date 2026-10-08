"""离线构建 HTML：pip install markdown beautifulsoup4；部署只需生成产物。"""
from pathlib import Path
import json,re,html,sys
import markdown
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent
sources=json.loads((ROOT/'sources.json').read_text())
# 修正为 JDBC 标准拦截分支的连续源码。
sources['tx'].update(line=378,end_line=407,excerpt='\n'.join(Path('/workspace/research/tx.txt').read_text().splitlines()[377:407]) if Path('/workspace/research/tx.txt').exists() else sources['tx']['excerpt'])
(ROOT/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2))
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
['happens-before 约束可观察结果；volatile 不保证复合原子性','AQS state + owner + 同步队列；唤醒后重新竞争','公平 lock 与无参数 tryLock 的行为不同','LongAdder 用于统计，不用于额度条件扣减','线程池 core→queue→max；有界队列和拒绝构成准入'],
['2 的幂与高低位扰动；扩容留 j 或去 j+n','树化受链长和容量 64 约束','HashMap JDK8 仍不安全；fail-fast 不提供互斥','CHM 空桶 CAS、锁桶、ForwardingNode 协作迁移','size 是并发估计；computeIfAbsent 禁止慢 IO/递归修改'],
['TLAB 属于堆；晋升受存活率/空间与策略影响','CMS 标记清扫：初标/重标停顿，碎片和浮动垃圾','G1 RSet 是外部入引用信息，SATB 记录旧引用','Mixed 只带部分 Old；暂停目标是软目标','JDK8 G1 Full GC 单线程；预留 evacuation 目的空间'],
['先区分 heap、Metaspace、Direct、thread 与容器限额','GC 后存活趋势 + dominator + GC Roots 证明持有','DirectByteBuffer Cleaner 与 ByteBuf 引用计数不同','NMT 不等于 RSS；保留、提交和实际驻留分开','修复须同负载对照，并覆盖取消/拒绝/异常路径'],
['doCreateBean：实例化→早期暴露→注入→初始化→代理','三级缓存仅处理部分单例循环；Boot2.7 默认禁止','事务必须经过代理；自调用和异步是主要边界','REQUIRED rollback-only；REQUIRES_NEW 额外占连接','Boot2.7 两类候选资源；MVC 按 handler/adapter 流程'],
['Read View 判定版本可见性；不可见沿 Undo','RC 逐语句快照；RR 一般首次一致读复用','快照读与当前读不同；范围锁依赖实际访问路径','索引收益需实际扫描/回表/写成本证据','PG/Oracle/OceanBase 各有版本、锁与恢复实现'],
['CommitLog 主体、ConsumeQueue 队列索引、IndexFile key 索引','同步刷盘/复制有条件与超时边界；超时结果未知','业务成功/offset 持久化裂缝会重复，消费本地事务幂等','局部顺序 key + 队列 + listener + 业务 version','Half→本地提交→确认；回查状态持久，积压 μ 必须大于 λ'],
['事件循环主路径命令串行；IO 多线程不是全面并行','RDB/COW、AOF fsync、异步复制各有窗口','Cache Aside 仍有慢读回写；双删不保证强一致','token+Lua 防误删；租期/切换仍会出现旧 owner','热点合并、大 key 拆分、回源准入与容量故障压测'],
['先定义支付/订单/保单不变量与恢复 SLA','2PC 资源持有；TCC 预留/空回滚/悬挂；Saga 业务补偿','Outbox 同 DB 事务，发送与标记间重复是预期','消费去重+业务同事务；外部调用稳定幂等键','超时 UNKNOWN 查询恢复；版本状态机+对账保证收敛'],
['一个 EventLoop 服务多 channel；阻塞污染其他连接','subscribeOn 源执行，publishOn 后续信号，背压有限边界','有界隔离+依赖超时；取消不保证阻塞操作立即停','重试相乘，单层预算、退避抖动、熔断与舱壁','L≈λW 与吞吐拐点；灰度染色、schema 兼容和回退演练']]
route=[('0–8 分钟',1,'JMM、AQS 与线程池准入'),('8–15 分钟',2,'CHM 迁移协议与原子 API'),('15–24 分钟',3,'CMS/G1 正常、失败与恢复'),('24–32 分钟',4,'OOM 分类与证据链'),('32–40 分钟',5,'代理、事务与连接预算'),('40–49 分钟',6,'MVCC、锁与执行计划'),('49–64 分钟',7,'RocketMQ 五类失败边界'),('64–72 分钟',8,'缓存一致性与锁租约'),('72–81 分钟',9,'Outbox、幂等与补偿'),('81–90 分钟',10,'EventLoop、重试与容量')]
nav=[];articles=[];names=[];expanded_texts=[]; stats={'chapters':10,'questions':0,'diagrams':0,'code_blocks':0}
for n,file in enumerate(sorted((ROOT/'chapters').glob('*.md')),1):
 text=file.read_text();name=text.splitlines()[0][2:];names.append(name)
 def insert_source(m):
  key=m.group(1);s=sources[key];version,method,lang=meta[key]
  url=s['url'].replace('raw.githubusercontent.com/','github.com/',1)
  seg=url.split('/'); url='/'.join(seg[:5]+['blob']+seg[5:]) if 'github.com' in url else url
  url+=f"#L{s['line']}-L{s['end_line']}"
  return f'\n**源码原文连续节选：{method} · {version} · L{s["line"]}–L{s["end_line"]}**（保留逻辑，仅规范显示缩进，可能止于方法中间；[完整上下文]({url})）。\n\n```{lang}\n{s["excerpt"]}\n```\n'
 text=re.sub(r'<!-- source:(\w+) -->',insert_source,text)
 text+='\n\n## 官方资料与版本来源\n\n联网核对日期：2026-10-08。固定版本用于解释实现，不代表最新生产推荐版本。源码摘录版权见 [source-notices.txt](./source-notices.txt)，下载记录与摘要见 [sources.json](./sources.json)。\n\n'
 for key in refs[n]:
  s=sources[key];label=meta[key][1]+' · '+meta[key][0] if key in meta else ('PostgreSQL16 隔离级别' if key=='pg' else 'Oracle19c 并发与一致性')
  text+=f'- [{label}]({s["url"]})\n'
 for label,url in extra_refs.get(n,[]):text+=f'- [{label}]({url})\n'
 expanded_texts.append(text)
 body=BeautifulSoup(markdown.markdown(text,extensions=['fenced_code','tables','md_in_html']), 'html.parser')
 body.h1.decompose();heads=body.find_all(['h2','h3']);sub=[]
 for i,h in enumerate(heads,1):
  h['id']=f'c{n}-s{i}';h['tabindex']='-1'
  if h.name=='h2':sub.append(f'<a href="#{h["id"]}">{html.escape(h.get_text())}</a>')
 for code in body.select('code.language-shell'):code['class']=['language-bash']
 for code in body.select('code.language-mermaid'):
  stats['diagrams']+=1;pre=code.parent;diagram=body.new_tag('figure',attrs={'class':'diagram','data-diagram':str(stats['diagrams'])});
  pre['class']=['mermaid']; pre.string=code.get_text();pre.replace_with(diagram);diagram.append(pre)
  cap=body.new_tag('figcaption');cap.string=f'原理图 {stats["diagrams"]} · 示意关键流程，异常边界见正文';diagram.append(cap)
 stats['code_blocks']+=len(body.select('pre:not(.mermaid)'));stats['questions']+=len(body.select('details'))
 # 速查只保留核心、四个重点问题、60 秒和易错点/源码入口。
 questions=body.select('details')[:(5 if n==7 else 4)];qa=''
 for d in questions:
  h=d.find_previous('h3');clone=BeautifulSoup(str(d),'html.parser');clone.summary.string=h.get_text();qa+=str(clone)
 def paragraph_after(title):
  h=next(x for x in body.find_all('h3') if x.get_text()==title);return ''.join(str(x) for x in h.find_next_siblings() if x.name=='p') if False else str(h.find_next_sibling('p'))
 quick=f'<section class="quick" aria-label="面试速查"><h2 id="c{n}-quick-core">核心知识点</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in points[n-1])+f'</ul><h2 id="c{n}-quick-qa">{"五" if n==7 else "四"}个重点问题</h2>'+qa+f'<h2 id="c{n}-quick-answer">60 秒标准答案</h2>'+paragraph_after('60 秒快速回答')+f'<h2 id="c{n}-quick-errors">易错点与高频源码</h2>'+paragraph_after('高频追问、常见错误与速记')+'</section>'
 nav.append(f'<details class="chapter-nav" data-chapter="c{n}"><summary><a href="#c{n}"><span>{n:02}</span>{html.escape(name)}</a></summary><div>'+''.join(sub)+'</div></details>')
 articles.append(f'<article class="chapter" id="c{n}" data-title="{html.escape(name)}"><div class="chapter-title"><p class="eyebrow">专题 {n:02} / 深度学习</p><h1>{html.escape(name)}</h1></div><div class="study">{body}</div>{quick}</article>')
route_html='<section id="review-route" class="route"><h2>90 分钟复习路线</h2><p>按下面顺序复习，先用 60 秒回答口述，再展开重点追问；RocketMQ 留 15 分钟。</p><ol>'+''.join(f'<li><time>{t}</time><a href="#c{n}">{title}</a></li>' for t,n,title in route)+'</ol></section>'
head='''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="Java 高级开发与架构师面试深度学习手册：JDK8 源码、RocketMQ、JVM 故障排查及分布式一致性，十个专题和三层问答。"><title>Java 架构师面试 · 深度学习手册</title><link rel="stylesheet" href="./style.css"><script src="./theme.js"></script><script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script><script defer src="./vendor/prism.js" data-manual></script><script defer src="./vendor/prism-c.js"></script><script defer src="./vendor/prism-cpp.js"></script><script defer src="./vendor/prism-java.js"></script><script defer src="./vendor/prism-sql.js"></script><script defer src="./vendor/prism-bash.js"></script><script defer src="./vendor/prism-yaml.js"></script><script defer src="./app.js"></script></head><body>
<a class="skip" href="#main">跳到正文</a>
<header class="topbar"><button id="menu" class="mobile" aria-label="打开章节导航" aria-expanded="false" aria-controls="left-nav">目录</button><div class="brand">Java 架构师面试<span>深入原理 · 推演故障 · 口述答案</span></div><div class="tools"><button id="search-open" aria-label="打开全文搜索">搜索 <kbd>/</kbd></button><button id="mode" aria-pressed="false">面试速查</button><button id="theme" aria-label="切换主题">主题：系统</button></div></header>
<div class="progress-track" aria-hidden="true"><div id="progress-bar"></div></div><div id="drawer-backdrop" hidden></div>
<div class="layout"><nav id="left-nav" aria-label="技术专题"><p class="nav-label">学习目录 / 10 个专题</p>'''
intro='''<main id="main" tabindex="-1"><section class="intro"><p class="eyebrow">JAVA / ARCHITECTURE / INTERVIEW</p><h1>从源码机制，到架构决策</h1><p>一份可以反复阅读的面试技术手册。每章连接原理、源码、三层追问与模拟故障，先回答机制，再说明边界和恢复证据。</p><div class="meta"><span>10 个专题</span><span>60 道三层问答</span><span>JDK 8 / Spring 5.3 / RocketMQ</span></div><p class="note">案例均明确标为模拟；不将未执行的故障实验冒充真实事故。页面无站内导航入口，通过完整 URL 公开访问。</p><noscript><p>JavaScript 已关闭：完整正文、源码、问答和预渲染图仍可阅读；搜索、复制和模式切换需要启用 JavaScript。</p></noscript></section>'''
end='''</main><aside id="right-toc" aria-label="当前专题目录"><div class="reading"><span id="progress-text">阅读进度 0%</span><span id="current-label"></span></div><p class="nav-label">本篇目录</p><nav id="toc"></nav></aside></div>
<dialog id="search-dialog" aria-labelledby="search-title"><div class="search-head"><h2 id="search-title">全文搜索</h2><button id="search-close" aria-label="关闭搜索">关闭</button></div><label for="search-input">搜索关键词、源码方法或面试问题</label><input id="search-input" type="search" placeholder="例如：sizeCtl、事务回查、Direct buffer" autocomplete="off"><p id="search-status" role="status" aria-live="polite">输入关键词，搜索十个专题的完整正文与答案。</p><div id="search-results"></div></dialog><div id="toast" role="status" aria-live="polite"></div>
<footer>学习基线与官方资料已标明版本 · 内容核对 2026-10-08 · <a href="./handbook.md">下载 Markdown 正文</a> · <a href="./VERIFICATION.md">验证范围</a></footer></body></html>'''
(ROOT/'index.html').write_text(head+''.join(nav)+'<a class="route-link" href="#review-route">90 分钟复习路线</a></nav>'+intro+route_html+''.join(articles)+end)
(ROOT/'handbook.md').write_text('# Java 架构师面试深度学习手册\n\n'+ '\n\n---\n\n'.join(expanded_texts))
(ROOT/'content-stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2));print(stats)
