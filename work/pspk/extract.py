"""Extract PSP Korean (V1.3) cutscene script -> psp_script.json"""
import sys,glob,os,json,re; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from pscript import tokens, blocks
from table import TAB, FW
def dec(seg):
    pages=[['']]; spk=None
    for t in tokens(seg):
        if t[0]=='end': break
        if t[0]=='c':
            ch=TAB.get(t[1]) or FW.get(t[1])
            if ch is None or not ('가'<=ch<='힣' or ch in ' .,!?~…-()\'"1234567890'): break
            pages[-1][-1]+=ch
        elif t[0]=='a':
            if t[1] in ' .,!?~-()\'"' or t[1].isdigit(): pages[-1][-1]+=t[1]
        elif t[0]=='nl': pages[-1].append('')
        elif t[0]=='op':
            if t[1]==0x06: pages.append([''])
            elif t[1]==0x0b: break
    out=[]
    for p in pages:
        ls=[re.sub(r'\s+',' ',l).strip() for l in p]
        ls=[l for l in ls if l and re.search('[가-힣]',l) or l in ('!!','!?','…')]
        if ls: out.append(ls)
    return out
def fix(s):
    s=s.replace('슴니','습니').replace('드라귤라','드라큘라')
    return s
res=[]
for fn in ['x/PS.ELF']+sorted(glob.glob('x/PSPBIN/*.bin')):
    d=open(fn,'rb').read(); name=os.path.basename(fn).split('.')[0]
    if name=='PS': name='st0'
    for off,v,seg in blocks(d):
        cs=[]
        for t in tokens(seg):
            if t[0]=='end' or t==('op',0x0b): break
            if t[0]=='c': cs.append(t[1])
        cs=cs[:20]
        if not cs or sum(c in TAB for c in cs)<0.7*len(cs): continue
        pages=[[fix(l) for l in p] for p in dec(seg)]
        if not pages: continue
        res.append(dict(file=name,off=off,voice=v,pages=pages,lines=[l for p in pages for l in p]))
json.dump(res,open('psp_script.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(len(res))
