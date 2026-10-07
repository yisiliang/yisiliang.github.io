#!/usr/bin/env python3
"""Render the fixed-source Nacos guide. Pass both source checkouts explicitly."""
import argparse, hashlib, html, json, re, shutil, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHA3 = '2c587c04891d532df1544ae95b906b677ac8eeff'
SHA2 = '55a99b1c186f81a53976e1a323ae29feb47d3aaf'

def method_end(lines, start):
    # Lex braces without counting quoted strings or comments.
    text = '\n'.join(lines[start-1:])
    state='code'; depth=0; begun=False; line=start; i=0
    while i < len(text):
        c=text[i]; n=text[i+1] if i+1<len(text) else ''
        if c=='\n': line+=1
        if state=='line':
            if c=='\n': state='code'
        elif state=='comment':
            if c=='*' and n=='/': state='code'; i+=1
        elif state in ('string','char'):
            if c=='\\': i+=1
            elif c==('"' if state=='string' else "'"): state='code'
        elif c=='/' and n=='/': state='line'; i+=1
        elif c=='/' and n=='*': state='comment'; i+=1
        elif c=='"': state='string'
        elif c=="'": state='char'
        elif c=='{': depth+=1; begun=True
        elif c=='}':
            depth-=1
            if begun and depth==0: return line
        i+=1
    raise ValueError('unterminated method')

def locate(root, name):
    if name=='pom.xml': return root/name
    paths=[p for p in root.rglob(name) if '/test/' not in str(p) and '/test-' not in str(p)]
    if name=='Service.java': paths=[p for p in paths if '/core/v2/' in str(p)]
    assert len(paths)==1,(name, paths)
    return paths[0]

def highlighted(source):
    pattern=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\b(?:public|private|protected|class|return|if|else|for|while|try|catch|throw|throws|new|true|false|null|void|boolean|int|long|final|static|switch|case|break|synchronized|this|extends|implements)\b|\b\d+(?:L)?\b')
    chunks=[]; last=0
    for m in pattern.finditer(source):
        chunks.append(html.escape(source[last:m.start()])); token=m.group()
        cls='comment' if token.startswith('/') else 'string' if token.startswith('"') else 'number' if token[0].isdigit() else 'keyword'
        chunks.append(f'<span class="{cls}">{html.escape(token)}</span>'); last=m.end()
    chunks.append(html.escape(source[last:])); return ''.join(chunks)

def diagram(ch):
    names=ch['diagram']; sid=ch['id']; title=ch['title'][3:]; desc=ch['diagramNote']; width=960
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 190" role="img" aria-labelledby="{sid}-title {sid}-desc"><title id="{sid}-title">{html.escape(title)}</title><desc id="{sid}-desc">{html.escape(desc)}</desc><defs><marker id="{sid}-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#75ccb9"/></marker></defs>']
    for i,name in enumerate(names):
        x=16+i*237
        if i: parts.append(f'<path d="M{x-23},78 H{x-3}" stroke="#75ccb9" stroke-width="2" marker-end="url(#{sid}-arrow)"/>')
        parts.append(f'<rect x="{x}" y="28" width="210" height="98" rx="12" fill="#132b31" stroke="#427d79"/><text x="{x+16}" y="52" fill="#75ccb9" font-family="monospace" font-size="12">0{i+1}</text><text x="{x+105}" y="87" text-anchor="middle" fill="#e0eeec" font-family="sans-serif" font-size="15">{html.escape(name)}</text>')
    parts.append(f'<text x="16" y="161" fill="#9bb6b5" font-family="sans-serif" font-size="14">{html.escape(desc)}</text></svg>')
    return ''.join(parts)

COMPARE=[
 ('服务端基线','2.5.4根POM：Java8','3.2.4根POM：Java17；客户端仍单独Java8','服务端JDK与业务SDK运行时分别检查'),
 ('gRPC','2.x已使用RpcClient/gRPC长连接','继续使用并扩展，不是首次引入','防火墙/负载均衡仍要覆盖SDK与节点间通道'),
 ('控制台','2.x传统console模块/服务集成路径','DeploymentType支持独立Console，默认console.port=8080','浏览器连通不等于SDK服务端可达'),
 ('临时注册','ConnectionBasedClient与Distro已存在','延续Client主记录与异步副本同步','不应以3.x标签宣称全局线性一致'),
 ('持久注册','PersistentClientOperationService与CP已存在','继续通过WriteRequest与状态机应用','多数派与异步推送的保证分开'),
 ('配置存储','外部与嵌入式实现分别存在','继续分开；3.2.4收紧嵌入式结果类型','不能说所有配置都由Raft存储'),
 ('AI资源','2.5.4没有对应ai模块及Prompt/Skill资源模型','MCP/A2A与Prompt/Skill有不同存储和发布链','业务发现兼容不等于新AI API兼容'),
 ('管理客户端','对照版本无maintainer-client模块','新增maintainer-client，与业务client职责分开','管理操作与SDK发现接口分别迁移'),
 ('JRaft认证','2.5.4没有该升级协调器','3.2.4引入能力检测和不可逆enforced锁存','核对每节点身份配置；不要假设混合旧版可滚动降级'),
 ('API兼容开关','没有3.2.4对应AI弃用接口开关','部分旧AI接口默认410；临时兼容开关有明确范围','不能把兼容开关视作所有2.x API的通用开关')]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source3',type=Path,required=True);ap.add_argument('--source2',type=Path,required=True);a=ap.parse_args()
    roots={'3.2.4':a.source3,'2.5.4':a.source2}; shas={'3.2.4':SHA3,'2.5.4':SHA2}
    chapters=json.loads((HERE/'chapters.json').read_text()); manifest=[]
    def excerpt(spec,version='3.2.4',eid=None):
        root=roots[version];p=locate(root,spec['file']);lines=p.read_text().splitlines(); start=spec['start'];end=method_end(lines,start) if spec.get('method') else spec['end'];code='\n'.join(lines[start-1:end])+'\n';eid=eid or spec['id'];filename=f'excerpts/{eid}.txt';(HERE/filename).write_text(code)
        path=str(p.relative_to(root));url=f'https://github.com/alibaba/nacos/blob/{shas[version]}/{path}#L{start}-L{end}'
        item={'id':eid,'version':version,'sha':shas[version],'path':path,'start':start,'end':end,'file':filename,'sha256':hashlib.sha256(code.encode()).hexdigest(),'url':url};manifest.append(item)
        return item,code
    supplemental=[
      {'id':'identity-equals','title':'身份比较：ephemeral不在equals中','file':'Service.java','start':107,'method':True},
      {'id':'distro-filter','title':'Distro过滤持久Client与非责任节点','file':'DistroClientDataProcessor.java','start':130,'method':True},
      {'id':'a2a-register','title':'A2A分别发布索引与正文','file':'A2aServerOperationService.java','start':97,'method':True},
      {'id':'skill-query','title':'Skill从manifest定位版本与文件','file':'SkillOperationServiceImpl.java','start':1108,'method':True},
      {'id':'rpc-auth','title':'gRPC业务鉴权与节点身份分支','file':'RemoteRequestAuthFilter.java','start':68,'method':True},
      {'id':'config-notifier','title':'配置事件转连接推送','file':'RpcConfigChangeNotifier.java','start':87,'method':True},
      {'id':'config-reconnect','title':'配置断连标脏与重连唤醒','file':'ClientWorker.java','start':825,'method':True},
      {'id':'config-pull','title':'拉取正文并检查Listener MD5','file':'ClientWorker.java','start':1064,'method':True},
      {'id':'config-defaults','title':'控制台默认端口','file':'application.properties','start':230,'end':252},
      {'id':'raft-commit','title':'JRaft提交时的leader路由','file':'JRaftServer.java','start':342,'method':True},
      {'id':'config-query-inner','title':'查询保存快照与删除快照分支','file':'ClientWorker.java','start':1316,'method':True},
      {'id':'raft-restore','title':'强制状态重启恢复','file':'JRaftAuthUpgradeCoordinator.java','start':136,'method':True}
    ]
    # distribution has the authoritative default properties, not a test fixture.
    oldlocate=locate
    def loc(root,name):
        return root/'distribution/conf/application.properties' if name=='application.properties' else oldlocate(root,name)
    globals()['locate']=loc
    md=['# Nacos源码学习手册：连接、状态与一致性边界','',f'主线Nacos3.2.4 · 固定提交`{SHA3}` · 对照2.5.4`{SHA2}`。核验日期：2026年10月7日。','', '这是一条从SDK长连接到服务实例、配置正文和AI资源的状态推导路径。所有源码窗口逐字取自固定官方提交。机制图是教学抽象，不承诺运行时同步发生。本文没有执行完整服务端构建、Java集成测试或真实升级实验；源码与静态交付检查已执行。','', '[网页阅读](index.html) · [离线包](nacos-offline.zip) · [核验记录](VERIFICATION.md) · [源码许可](apache-license.txt)','', '## 阅读顺序','']
    toc=[]; sections=[]
    for ch in chapters:
        sid=ch['id'];title=ch['title'];toc.append(f'<a href="#{sid}"><span>{title[:2]}</span>{html.escape(title[3:])}</a>');md.append(f'- [{title}](#{sid})')
    md+=['','## 版本对照：保留的机制与真正变化','', '|维度|2.5.4|3.2.4|迁移含义|','|---|---|---|---|']+['|'+'|'.join(r)+'|' for r in COMPARE]+['']
    compare='<section id="comparison"><h2>版本对照</h2><p>2.x已使用gRPC；变化应按模块、数据面与部署方式分别判断。</p><div class="table-wrap"><table><thead><tr>'+''.join(f'<th>{x}</th>' for x in ['维度','2.5.4','3.2.4','迁移含义'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>' for row in COMPARE)+'</tbody></table></div></section>'
    def code_html(item,code):
        return f'<details class="source" open><summary>源码正文 · Nacos{item["version"]} · L{item["start"]}–L{item["end"]}</summary><div class="source-meta"><a href="{item["url"]}" target="_blank" rel="noopener">{html.escape(item["path"])}</a><span>固定提交 {item["sha"][:12]}</span></div><pre><code class="language-java">{highlighted(code)}</code></pre></details>'
    for ch in chapters:
        item,code=excerpt(ch); ch['source']=item
        md+=['',f'<a id="{ch["id"]}"></a>',f'## {ch["title"]}','']
        ps=''.join('<p>'+html.escape(p)+'</p>' for p in ch['body']);md+=sum(([p,''] for p in ch['body']),[])
        rows=''.join('<tr><td><code>'+html.escape(f)+'</code></td><td>'+html.escape(d)+'</td></tr>' for f,d in ch['fields'])
        md+=['|字段/对象|状态含义|','|---|---|']+['|`'+f+'`|'+d+'|' for f,d in ch['fields']]+['']
        fig=''
        if ch.get('diagram'):
            svg=diagram(ch);f=f'diagrams/{ch["id"]}.svg';(HERE/f).write_text(svg);fig='<figure class="mechanism">'+svg+'<figcaption>'+html.escape(ch['diagramNote'])+'</figcaption></figure>';md+=['![机制图]('+f+')',ch['diagramNote'],'']
        md+=['### 固定源码正文','',f'[{item["path"]}，L{item["start"]}–L{item["end"]}]({item["url"]})','','```java',code.rstrip(),'```','', '### 失败边界','',ch['failure'],'','### 验证与观察','',ch['experiment'],'']
        sections.append(f'<section id="{ch["id"]}" class="chapter"><div class="eyebrow">SOURCE READING / {ch["title"][:2]}</div><h2>{html.escape(ch["title"][3:])}</h2>{ps}<div class="table-wrap"><table><thead><tr><th>字段/对象</th><th>状态含义</th></tr></thead><tbody>{rows}</tbody></table></div>{fig}{code_html(item,code)}<aside class="boundary"><strong>失败边界</strong><p>{html.escape(ch["failure"])}</p></aside><div class="experiment"><h3>验证与观察</h3><p>{html.escape(ch["experiment"])}</p></div></section>')
    extra=[];md+=['','## 附录A：补充源码证据','']
    for spec in supplemental:
        item,code=excerpt(spec);extra.append('<h3>'+html.escape(spec['title'])+'</h3>'+code_html(item,code));md += ['### '+spec['title'],'',f'[{item["path"]}]({item["url"]})','','```java',code.rstrip(),'```','']
    for spec in [{'id':'v2-pom','file':'pom.xml','start':90,'end':146}, {'id':'v2-register','file':'InstanceRequestHandler.java','start':73,'method':True}, {'id':'v2-distro','file':'DistroClientDataProcessor.java','start':115,'method':True}]:
        item,code=excerpt(spec,'2.5.4');extra.append('<h3>2.5.4对照 · '+html.escape(spec['file'])+'</h3>'+code_html(item,code));md+=['### 2.5.4对照：'+spec['file'],'',f'[{item["path"]}]({item["url"]})','','```java',code.rstrip(),'```','']
    (HERE/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    diagram_count=sum(bool(c.get('diagram')) for c in chapters)
    metadata={'title':'Nacos源码学习手册','version':'3.2.4','comparisonVersion':'2.5.4','category':'分布式与平台基础','sourceCommit':SHA3,'comparisonCommit':SHA2,'chapterCount':len(chapters),'diagramCount':diagram_count,'excerptCount':len(manifest),'verifiedDate':'2026-10-07','runtimeExperiments':'not-executed','source':'https://github.com/alibaba/nacos','sha':SHA3,'chapters':len(chapters),'diagrams':diagram_count,'excerpts':len(manifest),'summary':'固定3.2.4对照2.5.4，追踪注册发现、配置监听、gRPC状态、Distro/JRaft、部署鉴权与AI资源版本的真实调用链和失败边界。','tags':['注册发现','配置中心','gRPC','Distro','JRaft','AI Registry']}
    (HERE/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    md+=['## 附录B：升级前的检查顺序','','1. 固定当前与目标版本，区分Server、Console、Client和Maintainer Client。','2. 核对JDK、端口映射、namespace ID、DB模式与schema；备份DB和复制状态。','3. 验证每节点server identity一致，读取JRaft认证锁存状态，制定同版本完整恢复方案。','4. 使用隔离服务/配置验证注册、订阅、CAS发布、断链redo、快照与权限拒绝。','5. 将旧AI接口与MCP私网导入按3.2.4范围单独迁移；不以业务SDK连接成功推断全部兼容。','6. 对比Server主状态、节点缓存、SDK缓存和业务实际生效，不把ACK当最终效果。','','## 参考与许可','','[3.2.4官方发布说明](https://github.com/alibaba/nacos/releases/tag/3.2.4) · [2.5.4官方发布说明](https://github.com/alibaba/nacos/releases/tag/2.5.4)。具体技术推导以以上固定源码链接为依据。','源码节选原样保留，版权属于Alibaba及原贡献者，适用Apache License 2.0；本包附完整LICENSE与原NOTICE。机制图、解释与页面是教学编排，不是官方产品文档。']
    (HERE/'handbook.md').write_text('\n'.join(md)+'\n')
    css='''*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:28px}p,li,a,code,mark{overflow-wrap:anywhere}pre code{overflow-wrap:normal}button,.links a{white-space:nowrap}body{margin:0;background:#0b171d;color:#d9e6e7;font:16px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}a{color:#83d8c0;text-decoration:none}a:hover{text-decoration:underline}header{padding:64px max(24px,calc((100vw - 1280px)/2));border-bottom:1px solid #284149;background:linear-gradient(130deg,#142c32,#0b171d)}header .eyebrow{letter-spacing:.15em}h1{font-size:clamp(32px,5vw,62px);line-height:1.2;margin:18px 0 20px;max-width:950px}header p{max-width:820px;color:#acc2c5}.subtitle{font-size:21px;color:#81d3bf}.stats{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}.stats span,.links a{padding:6px 13px;border:1px solid #36515b;border-radius:7px}.links{display:flex;gap:14px;flex-wrap:wrap}.layout{display:grid;grid-template-columns:245px minmax(0,1fr);max-width:1280px;margin:auto;gap:48px;padding:36px 24px}nav{align-self:start;position:sticky;top:20px;max-height:calc(100vh - 40px);overflow:auto;font-size:13px;padding-right:8px}nav a{display:flex;gap:10px;padding:7px 0;color:#a9c3c7}nav a span{font:11px/2.4 monospace;color:#65bfa8}main{min-width:0}section{margin-bottom:60px;padding-bottom:38px;border-bottom:1px solid #29414a}.eyebrow{font:12px/1.6 monospace;color:#79cbb7}h2{font-size:28px;line-height:1.45;margin:10px 0 22px}h3{font-size:18px;margin:30px 0 12px}p{margin:18px 0}.table-wrap{overflow:auto;margin:26px 0}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:13px 14px;text-align:left;border:1px solid #2b464f;vertical-align:top}th{background:#17303a;color:#a5e2d0}td{min-width:150px}code{font:13px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace}.source{border:1px solid #315059;border-radius:10px;overflow:hidden;margin:26px 0;background:#091319}.source summary{cursor:pointer;padding:14px 18px;background:#152b33;color:#a5dfd0;font-size:14px}.source-meta{padding:14px 18px;border-bottom:1px solid #243a42;font-size:12px;overflow-wrap:anywhere}.source-meta span{display:block;color:#859fa6}pre{overflow:auto;padding:20px;margin:0;tab-size:4;line-height:1.55}pre code{white-space:pre}.keyword{color:#d59feb}.comment{color:#86a594}.string{color:#c0da8b}.number{color:#e0b06c}.mechanism{margin:28px 0;padding:14px;border:1px solid #2e4c54;border-radius:10px;background:#0a151b;overflow:auto}.mechanism svg{display:block;min-width:730px;width:100%;height:auto}.mechanism figcaption{font-size:13px;color:#99b9ba;margin:8px}.boundary{border-left:3px solid #dfa96f;background:#24291f;padding:16px 20px;margin:24px 0}.boundary p{margin:6px 0}.boundary strong{color:#e7b57d}.experiment{border-left:3px solid #619cb8;padding-left:20px}.experiment h3{margin:0}.note{border:1px solid #385663;padding:18px;background:#11232c;color:#afc7ce}footer{padding:35px 24px;max-width:1280px;margin:auto;color:#849fa6;font-size:13px}button{color:#a5dfd0;background:#17303a;border:1px solid #36515b;padding:8px 12px;border-radius:6px;cursor:pointer}@media(max-width:800px){header{padding:36px 20px}.layout{display:block;padding:24px 18px}nav{position:static;max-height:250px;border:1px solid #2b464f;padding:15px;margin-bottom:32px}h2{font-size:24px}body{font-size:15px}pre{padding:15px}section{margin-bottom:38px}.mechanism{margin:22px 0}header .subtitle{font-size:18px}}@media print{nav,.links,button{display:none}.layout{display:block}body{background:white;color:black}.source{background:#f8f8f8}pre{white-space:pre-wrap}a{color:#24584c}section{break-inside:auto}}'''
    page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nacos源码学习 · 源码之下，系统之上</title><meta name="description" content="固定Nacos3.2.4，对照2.5.4：连接、注册、配置、Distro、JRaft与AI Registry源码状态推导。"><style>{css}</style>{{TRACKER}}</head><body><header><div class="eyebrow">SOURCE NOTES / DISTRIBUTED SYSTEMS</div><h1>Nacos：从连接到一致性边界</h1><div class="subtitle">源码之下，系统之上。</div><p>沿着连接、实例、配置与AI资源四条状态链，追到真正的字段、写入与失败分支。主线3.2.4，对照2.5.4，固定源码而非浮动分支。</p><div class="stats"><span>{len(chapters)}章深入阅读</span><span>{diagram_count}幅机制图</span><span>{len(manifest)}个固定源码窗口</span><span>2026.10.07核验</span></div><div class="links"><a href="/">首页</a><a href="handbook.md" download>Markdown手册</a><a href="nacos-offline.zip" download>离线阅读包</a><a href="VERIFICATION.md">核验记录</a></div></header><div class="layout"><nav aria-label="章节目录"><strong>阅读目录</strong><a href="#comparison">版本对照</a>{''.join(toc)}<a href="#source-evidence">补充源码证据</a><a href="#migration">升级与实验</a></nav><main><p class="note">固定提交：3.2.4 <code>{SHA3}</code>；2.5.4 <code>{SHA2}</code>。源码/文件静态检查已执行。完整构建、服务集群、Java集成测试和升级实验均未执行，各章实验是可验证的观察方案。图中的箭头表达逻辑关系，不承诺同步原子发生。</p>{compare}{''.join(sections)}<section id="source-evidence"><h2>补充源码证据</h2><p>主章节之外的关键分支与2.5.4对照窗口。每个窗口均来自固定提交，全文未修改。</p>{''.join(extra)}</section><section id="migration"><h2>升级与实验：按边界验证</h2><p>先核对JDK、Server/Console端口、namespace ID、数据库模式与schema；再核对节点身份、JRaft认证锁存状态和完整恢复方案。注册发现兼容、配置监听兼容、管理API兼容与新AI资源兼容须分别验收。</p><p>本包提供<a href="examples/md5-cas-model.py">MD5/CAS边界模型</a>和<a href="examples/README.md">真实SDK实验步骤</a>。模型只说明状态语义，不模拟实际Nacos的并发或网络；静态源码与模型可以复核，真实集群实验尚未执行。</p><p>3.2.4部分弃用AI API默认返回410，私网MCP工具导入需允许列表，JRaft全员认证强制后不要依赖混合旧版本滚动降级。范围以<a href="https://github.com/alibaba/nacos/releases/tag/3.2.4">官方3.2.4发布说明</a>及固定源码为依据。</p></section></main></div><footer>源码节选版权属于Alibaba及贡献者，Apache License 2.0。<a href="apache-license.txt">完整许可</a> · <a href="nacos-notice.txt">原NOTICE</a> · <a href="source-notices.txt">节选说明</a>。解释和机制图为教学编排。</footer><script>document.querySelectorAll('.source pre').forEach(p=>{{const b=document.createElement('button');b.textContent='复制源码';b.addEventListener('click',()=>navigator.clipboard.writeText(p.innerText).then(()=>{{b.textContent='已复制';setTimeout(()=>b.textContent='复制源码',1500)}}));p.before(b)}});</script></body></html>'''
    tracker='<script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script>'
    (HERE/'index.html').write_text(page.replace('{TRACKER}',tracker))
    # Offline home is a local guide link, never a filesystem path.
    offline=page.replace('{TRACKER}','').replace('href="/"','href="index.html"').replace('<a href="nacos-offline.zip" download>离线阅读包</a>','<a href="source-manifest.json">固定源码清单</a>')
    (HERE/'offline.html').write_text(offline)
    shutil.copyfile(a.source3/'LICENSE',HERE/'apache-license.txt');shutil.copyfile(a.source3/'NOTICE',HERE/'nacos-notice.txt')
    (HERE/'source-notices.txt').write_text('Nacos源文件节选来自alibaba/nacos，主线3.2.4及对照2.5.4。\nCopyright Alibaba Group Holding Ltd. and contributors.\n适用Apache License 2.0，完整原文见apache-license.txt，原NOTICE见nacos-notice.txt。\n源码窗口逐字原样，窗口外的原文件许可头未重复附于每个方法；版权与完整许可在此统一保留。\n原创解释、机制图及HTML为学习编排；未修改上游源码或发布完整Nacos源码包。\n源文件路径、固定提交和行号见source-manifest.json。\nJava高亮为本包自有正则着色，不依赖第三方高亮库。\n')
    files=[p for p in HERE.rglob('*') if p.is_file() and p.suffix!='.zip' and '__pycache__' not in str(p)]
    with zipfile.ZipFile(HERE/'nacos-offline.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in files:
            if p.name=='index.html':continue
            z.write(p,str(p.relative_to(HERE)))
        z.writestr('index.html',offline)
    print(json.dumps(metadata,ensure_ascii=False))

if __name__=='__main__':main()
