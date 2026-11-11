import sys,os,json,re
sys.path.insert(0,'.')
from pscript import VOICE
TR='E:/SOTNKR/work/trans'; U='E:/SOTNKR/work/U'
NAMES='ST0 NO3 NO4 DAI TOP CEN CENP RCEN LIB NZ0 DRE BO2 BO5 BO6 BO6RIC2 RBO2 RBO6 SEL MAR'.split()
V2=re.compile(rb'\x0b\x09(..)',re.S)
def groups(name):
    d=json.load(open(f'{TR}/{name}.jp.json',encoding='utf8'))
    data=open(os.path.join(U,*d['file'].split('/')),'rb').read()
    vs=[(m.start(),m.group(1).hex()) for m in V2.finditer(data)]
    out=[]
    for k,it in enumerate(d['items']):
        v=None
        for o,vid in vs:
            if o<it['off']: v=vid
            else: break
        if not out or out[-1]['voice']!=v: out.append(dict(voice=v,items=[]))
        out[-1]['items'].append(k)
    return d,out
def vid(h): hi,lo=int(h[:2],16),int(h[2:],16); return (hi>>4)<<8|lo
def vhex(i): return '%02x%02x'%(((i>>8)<<4)|((i&0xff)>>4),i&0xff)
def pick(P,v,name,shift=2):
    if v is None: return None
    c=P.get(vhex(vid(v)-shift))
    if not c: return None
    for b in c:
        if b['file']==name.lower(): return b
    return max(c,key=lambda b:len(b['lines']))
if __name__=='__main__':
    psp=json.load(open('psp_script.json',encoding='utf8'))
    P={}
    for b in psp: P.setdefault(b['voice'],[]).append(b)
    for name in sys.argv[1:] or NAMES:
        d,gs=groups(name)
        print('=====',name,d['file'],len(d['items']))
        for g in gs:
            lines=[];cur=''
            for k in g['items']:
                it=d['items'][k]; cur+=it['en']+'·'
                if it.get('newline_after'): lines.append(cur); cur=''
            if cur: lines.append(cur)
            p=pick(P,g['voice'],name)
            print(' ',g['voice'],len(lines),'|'.join(lines)[:150])
            print('    PSP',len(p['lines']) if p else '-', ' / '.join(p['lines']) if p else '')
