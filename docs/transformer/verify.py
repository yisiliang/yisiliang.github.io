#!/usr/bin/env python3
"""Recompute the article's teaching examples using the standard library only."""
from pathlib import Path
from html.parser import HTMLParser
from math import exp, sqrt, sin, cos, log, inf, isclose
import json
ROOT=Path(__file__).resolve().parent

def mm(a,b):
    assert len(a[0])==len(b)
    return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]
def softmax(row):
    m=max(row)
    assert m != -inf, 'All-masked rows require explicit handling'
    e=[exp(x-m) for x in row]
    return [x/sum(e) for x in e]
def attention(q,k,v,causal=False):
    s=mm(q,list(map(list,zip(*k))))
    a=[softmax([x/sqrt(len(k[0])) if not causal or j<=i else -inf for j,x in enumerate(row)]) for i,row in enumerate(s)]
    return a,mm(a,v)
def near(a,b):
    assert isclose(a,b,abs_tol=5.1e-7), (a,b)
x=[[1,0],[0,1],[1,1]]
v=mm(x,[[2,0],[0,1]])
a,o=attention(x,x,v)
expected_a=[[.401112,.197776,.401112],[.197776,.401112,.401112],[.248255,.248255,.503490]]
expected_o=[[1.604448,.598888],[1.197776,.802224],[1.503490,.751745]]
for actual,expected in [(a,expected_a),(o,expected_o)]:
    for row,erow in zip(actual,expected):
        for z,e in zip(row,erow):near(z,e)
for row in a:near(sum(row),1)
am,om=attention(x,x,v,True)
near(am[0][0],1);near(am[1][0],.330238)
for i,row in enumerate(am):
    for j,z in enumerate(row):
        if j>i:near(z,0)
# Two one-dimensional heads and a two-dimensional output projection.
z1=mm(x,[[1],[0]]);z2=mm(x,[[0],[1]])
_,h1=attention(z1,z1,z1);_,h2=attention(z2,z2,z2)
joined=[aa+bb for aa,bb in zip(h1,h2)]
heads=mm(joined,[[1,1],[0,1]])
near(h1[0][0],.844638);near(h2[0][0],2/3);near(heads[0][1],1.511304)
pe=[[fn(pos/10000**(2*i/4)) for i in range(2) for fn in (sin,cos)] for pos in range(3)]
near(pe[1][0],.841471);near(pe[1][3],.999950);near(pe[2][2],.019999)
ff=mm([[max(0,z) for z in mm([[1,-2]],[[1,0,1],[0,1,1]])[0]]],[[1,0],[0,1],[1,1]])
assert ff==[[1,0]]
y=[2,-2];mean=sum(y)/2;var=sum((z-mean)**2 for z in y)/2
ln=[(z-mean)/sqrt(var+1e-6) for z in y];near(ln[0],1)
near(softmax([2,1,0])[0],.665241)
near(-(log(.8)+log(.5))/2,.458145)
for row in ([.707107,0,.707107],[2,1,0]):
    for aa,bb in zip(softmax(row),softmax([s+100 for s in row])):near(aa,bb)
# Independent checks for the new parameter, complexity and memory examples.
assert 8*512*64 == 512*512 == 262144
assert 128**2*512 == 8388608 and 128*512**2 == 33554432
assert 8192**2*512 == 34359738368
assert 8192**2*2/1024**2 == 128 and 8*8192**2*2/1024**3 == 1
# Finite-difference check of d cross-entropy / d logits = p - one_hot.
z=[log(.6),log(.3),log(.1)];eps=1e-5
for j in range(3):
    plus=z.copy();minus=z.copy();plus[j]+=eps;minus[j]-=eps
    derivative=(-log(softmax(plus)[1])+log(softmax(minus)[1]))/(2*eps)
    assert isclose(derivative,[.6,-.7,.1][j],abs_tol=1e-8)
# Verify page topology and every local asset; don't rely on visual counts.
class Page(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.links=[];self.sections=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='article' and attrs.get('class')=='chapter':self.sections+=1
        for k in ('href','src'):
            if k in attrs:self.links.append(attrs[k])
p=Page();p.feed((ROOT/'index.html').read_text())
assert len(p.ids)==len(set(p.ids))
assert p.sections==16
for link in p.links:
    if link.startswith('#'):assert link[1:] in p.ids,link
    elif link.startswith('./'):assert (ROOT/link[2:]).exists(),link
result={'attention_weights':a,'attention_output':o,'causal_weights':am,'causal_output':om,'two_heads':heads,'position_encoding':pe,'ffn':ff,'layer_norm':ln,'loss':-(log(.8)+log(.5))/2}
print(json.dumps(result,ensure_ascii=False,indent=2))
print('PASS: numerical examples, softmax invariance, causal zeros, 16 sections, unique ids, internal anchors and assets')
