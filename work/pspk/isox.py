import struct,sys,os
f=open(sys.argv[1],'rb')
def rd(l,n): f.seek(l*2048); return f.read(n)
pvd=rd(16,2048); root=pvd[156:190]
out=[]
def rec(lba,size,path):
    buf=rd(lba,size); p=0
    while p<len(buf):
        ln=buf[p]
        if ln==0: p=(p//2048+1)*2048; continue
        r=buf[p:p+ln]; l=struct.unpack('<I',r[2:6])[0]; s=struct.unpack('<I',r[10:14])[0]; fl=r[25]; nl=r[32]; nm=r[33:33+nl]
        if nm not in (b'\0',b'\1'):
            nm=nm.decode('latin1').split(';')[0]
            if fl&2: rec(l,s,path+nm+'/')
            else: out.append((path+nm,l,s))
        p+=ln
rec(struct.unpack('<I',root[2:6])[0],struct.unpack('<I',root[10:14])[0],'')
for p,l,s in out: print('%08x %10d %s'%(l*2048,s,p))
