import numpy as np
D=open('E:/SOTNKR/work/pspk/x/PS.ELF','rb').read(); B=0x41dc8
def idx(c):
    hi,lo=c>>8,c&0xff; l2=lo-0x40-(1 if lo>=0x7f else 0); return 188*(hi-0x89)+l2+618
def glyph(c):
    i=idx(c); a=np.frombuffer(D[B+i*30:B+i*30+30],np.uint8).reshape(15,2); v=(a[:,0].astype(int)<<8)|a[:,1]
    return ((v[:,None]>>np.arange(15,-1,-1))&1).astype(np.uint8)
