"""Opening-crawl narration (JP) check: is the Japanese narrated crawl track on the Ultimate disc?

JP ST0 0x801B05B0 plays XA id 0x33D at the crawl start; Ultimate/US ST0 0x801B0F44 plays 0x340 (music only).
XA id -> 16-byte entry (index = id - 0x300): Ultimate DRA 0x800BD224, JP DRA 0x800BD390
  {u32 sector offset in SD/XA_STR1, u32 length, u8 file, u8 channel, u8 volume, ...};
first sector of the stream = XA_STR1 LBA + offset + channel, then every 8th sector.
Hashes every sector of the JP stream (bytes 24..2072: audio part, no subheader) and looks them up in the
Ultimate image. Analysis only, reads the local images; nothing is written.
python xa_narration.py [K image] [Ultimate image]"""
import sys, os, struct, hashlib
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
K_IMG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'SOTN_K.bin')
U_IMG = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, '원본롬', 'SOTN Ultimate (PS1 Version) v1.2.bin')
K_XA, U_XA = 47643, 51894            # SD/XA_STR1 LBAs (work/list_K.txt, list_U.txt)

def entry(dra, base, xid):
    o = base - 0x800A0000 + (xid - 0x300) * 16
    off, ln = struct.unpack_from('<II', dra, o)
    return off, ln, dra[o + 8], dra[o + 9], dra[o + 10]

def main():
    kd = open(os.path.join(ROOT, 'work', 'K', 'DRA.BIN'), 'rb').read()
    ud = open(os.path.join(ROOT, 'work', 'U', 'DRA.BIN'), 'rb').read()
    ks = open(os.path.join(ROOT, 'work', 'K', 'ST', 'ST0', 'ST0.BIN'), 'rb').read()
    us = open(os.path.join(ROOT, 'work', 'U', 'ST', 'ST0', 'ST0.BIN'), 'rb').read()
    kid = struct.unpack_from('<I', ks, 0x305B0)[0] & 0xFFFF
    uid = struct.unpack_from('<I', us, 0x30F44)[0] & 0xFFFF
    print('crawl XA id: JP %#x  Ultimate %#x' % (kid, uid))
    k = entry(kd, 0x800BD390, kid); u = entry(ud, 0x800BD224, uid)
    print('JP entry', k, ' Ultimate entry', u)
    uh = {}
    with open(U_IMG, 'rb') as f:
        f.seek(U_XA * 2352); l = U_XA
        while True:
            s = f.read(2352)
            if len(s) < 2352: break
            uh.setdefault(hashlib.md5(s[24:2072]).digest(), l); l += 1
    first = K_XA + k[0] + k[3]
    hit = n = 0
    with open(K_IMG, 'rb') as f:
        for i in range(2000):
            f.seek((first + i * 8) * 2352); s = f.read(2352)
            n += 1; hit += hashlib.md5(s[24:2072]).digest() in uh
    print('JP narrated crawl stream: %d sectors checked, %d found on the Ultimate disc' % (n, hit))

if __name__ == '__main__':
    main()
