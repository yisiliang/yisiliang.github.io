#!/usr/bin/env python3
"""Audit/fix handbook excerpts using syntax boundaries from bundled pinned sources.
Requires: tree-sitter, tree-sitter-java, tree-sitter-c, tree-sitter-cpp.
Run without arguments to audit; --apply updates Markdown, HTML and offline ZIPs.
"""
import argparse, html, json, re, subprocess, textwrap, zipfile
from pathlib import Path
from tree_sitter import Language, Parser
import tree_sitter_java, tree_sitter_c, tree_sitter_cpp
ROOT = Path(__file__).resolve().parents[1]
PARSERS = {k: Parser(Language(m.language())) for k,m in [('java',tree_sitter_java),('c',tree_sitter_c),('cpp',tree_sitter_cpp)]}
URL = re.compile(r'https://github.com/[^/]+/[^/]+/blob/([^/]+)/([^\s"<>)]*?)#L(\d+)-L(\d+)')
METHODS = {'method_declaration','constructor_declaration','function_definition'}
def walk(n):
    yield n
    for child in n.children: yield from walk(child)
def body(lines,a,b): return textwrap.dedent('\n'.join(lines[a-1:b]))
def bounds(lines,tree,a,b):
    nodes=list(walk(tree.root_node)); methods=[n for n in nodes if n.type in METHODS]
    comments=[n for n in nodes if 'comment' in n.type]
    old=(a,b); reasons=[]
    # A function window ends at that function, including when it begins with
    # the function's own documentation. Class/field windows stay as windows.
    active=[n for n in methods if n.start_point.row+1<=a<=n.end_point.row+1]
    first=min(active,key=lambda n:n.end_byte-n.start_byte) if active else None
    if first is None:
        following=sorted((n for n in methods if a<=n.start_point.row+1<=b),key=lambda n:n.start_byte)
        if following:
            candidate=following[0]
            leading='\n'.join(lines[a-1:candidate.start_point.row])
            leading=re.sub(r'/\*.*?\*/|//[^\n]*','',leading,flags=re.S)
            if not leading.strip(): first=candidate
    if first:
        end=first.end_point.row+1
        if end<b:
            # This existing excerpt explicitly explains the rehash/resize/full
            # stale sweep trio together, so keep its intended multi-method view.
            name=first.child_by_field_name('name')
            multi=name is not None and name.text==b'rehash' and any('expungeStaleEntries();' in x for x in lines[first.start_point.row:first.end_point.row+1])
            if not multi:
                b=end; reasons.append('trim following declaration/comment')
        annotation_prefix='\n'.join(lines[first.start_point.row:a-1])
        if a==first.start_point.row+1 or (annotation_prefix.lstrip().startswith('@') and not re.sub(r'@\w+(?:\([^\n]*\))?|/\*.*?\*/|//[^\n]*', '', annotation_prefix, flags=re.S).strip()):
            if a!=first.start_point.row+1:
                a=first.start_point.row+1; reasons.append('include function annotations')
            p=a-2
            while p>=0 and (not lines[p].strip() or lines[p].lstrip().startswith('@')): p-=1
            cs=[n for n in comments if n.end_point.row==p]
            if cs:
                c=max(cs,key=lambda n:n.start_byte)
                a=c.start_point.row+1
                # Consecutive C/Java line comments form one documentation block.
                while a>1 and lines[a-2].lstrip().startswith('//'): a-=1
                reasons.append('include current documentation')
    # Windows starting inside a comment must include its opening delimiter.
    for c in comments:
        ca,ce=c.start_point.row+1,c.end_point.row+1
        if ca<a<=ce: a=ca; reasons.append('complete leading comment')
        if ca<=b<ce:
            # Internal explanatory comments remain with their function.
            internal=any(n.start_byte<=c.start_byte and c.end_byte<=n.end_byte and n.start_point.row+1<=old[0] for n in methods)
            if internal: b=ce; reasons.append('complete internal comment')
            else: b=ca-1; reasons.append('remove dangling next comment')
    while b>=a and not lines[b-1].strip(): b-=1
    return a,b,reasons

def load_sources(d):
    z=zipfile.ZipFile(next(p for p in d.glob('*source.zip') if 'offline' not in p.name))
    result={}
    for name in z.namelist():
        if name.endswith(('.java','.c','.h','.cpp','.hpp','.java.template')):
            data=z.read(name);lang='java' if '.java' in name else ('cpp' if name.endswith(('.cpp','.hpp')) else 'c')
            result[name]=(data.decode().splitlines(),PARSERS[lang].parse(data))
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--baseline',action='store_true',help='rebuild from committed handbooks');ap.add_argument('--baseline-ref',default='HEAD');args=ap.parse_args();report=[]
    for book in ['jdk-source','rocketmq','redis']:
        d=ROOT/'docs'/book;src=load_sources(d);md=(d/'handbook.md').read_text();ht=(d/'index.html').read_text();changes={};cards=[]
        if args.baseline:
            md=subprocess.check_output(['git','show',f'{args.baseline_ref}:docs/{book}/handbook.md'],cwd=ROOT,text=True)
            ht=subprocess.check_output(['git','show',f'{args.baseline_ref}:docs/{book}/index.html'],cwd=ROOT,text=True)
        for m in re.finditer(r'<section class="source-card">.*?</section>',ht,re.S):
            links=list(URL.finditer(ht[:m.start()])); assert links,(book,m.start())
            u=links[-1];sha,f,a,b=u.groups();a,b=int(a),int(b)
            key=f if f in src else next((n for n in src if n.endswith('/'+f) and ((sha.startswith('ae6a') and n.startswith('7.2.6/')) or (sha.startswith('9186') and n.startswith('6.2.14/')) or (sha.startswith('63d2') and n.startswith('5.3.4/')) or (sha.startswith('2bdd') and n.startswith('4.9.8/')))),None)
            assert key,(book,f,sha)
            lines,tree=src[key];raw=re.search(r'<code\b[^>]*>(.*?)</code>',m[0],re.S)[1];plain=html.unescape(re.sub(r'<[^>]+>','',raw));assert plain.rstrip()==body(lines,a,b).rstrip(),(book,f,a,b,'source mismatch')
            na,nb,reasons=bounds(lines,tree,a,b);assert na<=nb,(f,a,b,na,nb)
            cards.append((m,u,raw,lines,a,b,na,nb))
            if (na,nb)!=(a,b):
                changes[(f,a,b)]=(na,nb,lines);report.append(dict(book=book,file=f,old=[a,b],new=[na,nb],reasons=reasons))
        highlighted = None
        if args.apply:
            payload=[dict(language=re.search(r'class="language-([^"]+)"',m[0])[1],code=body(lines,na,nb)) for m,u,raw,lines,a,b,na,nb in cards]
            highlighted=json.loads(subprocess.run(['node',str(ROOT/'tools'/'highlight_source.cjs')],input=json.dumps(payload),text=True,capture_output=True,check=True).stdout)
        # Work backwards so offsets remain stable. Only source cards and their
        # immediately preceding citation change; prose/diagrams remain intact.
        for idx in reversed(range(len(cards))):
            m,u,raw,lines,a,b,na,nb=cards[idx]
            if (na,nb)==(a,b) and not args.apply:continue
            newbody=body(lines,na,nb)
            section=m[0];section=re.sub(r'L\d+–L\d+',f'L{na}–L{nb}',section)
            section=re.sub(r'(<pre class="gutter"[^>]*>).*?(</pre>)',lambda x:x[1]+'\n'.join(map(str,range(na,nb+1)))+x[2],section,flags=re.S)
            section=re.sub(r'(<code\b[^>]*>).*?(</code>)',lambda x:x[1]+(highlighted[idx] if highlighted is not None else html.escape(newbody))+x[2],section,flags=re.S)
            assert html.unescape(re.sub(r'<[^>]+>','',re.search(r'<code\b[^>]*>(.*?)</code>',section,re.S)[1])).rstrip()==newbody.rstrip(),(book,f,a,b,na,nb)
            prefix=ht[u.start():m.start()];prefix=prefix.replace(f'#L{a}-L{b}',f'#L{na}-L{nb}').replace(f'L{a}–L{b}',f'L{na}–L{nb}')
            ht=ht[:u.start()]+prefix+section+ht[m.end():]
        # Match each fenced excerpt to its nearest fixed-source citation.
        matches=list(re.finditer(r'```(?:java|c|cpp)\n(.*?)\n```',md,re.S))
        updated=0
        for m in reversed(matches):
            us=list(URL.finditer(md[:m.start()]));
            if not us:continue
            u=us[-1];sha,f,a,b=u.groups();a,b=int(a),int(b)
            if (f,a,b) not in changes:continue
            na,nb,lines=changes[(f,a,b)]
            if m[1].rstrip()!=body(lines,a,b).rstrip(): continue
            prefix=md[u.start():m.start()].replace(f'#L{a}-L{b}',f'#L{na}-L{nb}')
            # Link labels occur before the URL.
            start=md.rfind('[',0,u.start());label=md[start:u.start()].replace(f'L{a}–L{b}',f'L{na}–L{nb}')
            md=md[:start]+label+prefix+m[0].replace(m[1],body(lines,na,nb))+md[m.end():];updated+=1
        assert updated==sum((a,b)!=(na,nb) for _,_,_,_,a,b,na,nb in cards),(book,updated)
        print(book,'audited',len(cards),'changed',updated)
        if args.apply:
            (d/'handbook.md').write_text(md);(d/'index.html').write_text(ht)
            zp=next(d.glob('*offline.zip'))
            with zipfile.ZipFile(zp) as z: entries=[(i,z.read(i.filename)) for i in z.infolist()]
            offline=re.sub(r'<script\b[^>]*src="https://cloud.umami.is/script.js"[^>]*></script>','',ht)
            with zipfile.ZipFile(zp,'w') as z:
                for i,data in entries:z.writestr(i,offline.encode() if i.filename=='index.html' else md.encode() if i.filename=='handbook.md' else data)
            with zipfile.ZipFile(zp) as z:assert z.testzip() is None;assert z.read('handbook.md')==md.encode();assert z.read('index.html')==offline.encode()
    if args.apply and report:(ROOT/'tools'/'source-excerpt-repair-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    else: print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
