"""Probe: record callers (ra) and codes (a0) of the DRA glyph API 0x80104EDC."""
import sys, time, os, struct
sys.path.insert(0, os.path.dirname(__file__))
import ra
from asm import Asm

def wr(addr, data):
    for k in range(0, len(data), 32):
        ch = data[k:k + 32]
        ra.cmd('WRITE_CORE_RAM %x %s' % ((addr & 0x1FFFFF) + k, ' '.join('%02x' % b for b in ch)))

BUF = 0x801FB700   # count at BUF, entries (ra, a0) from BUF+8, 64 entries
a = Asm(0x801FB680)
a.li('t0', BUF)
a.lw('t1', 0, 't0'); a.nop()
a.andi('t2', 't1', 63); a.sll('t2', 't2', 3); a.addu('t2', 't2', 't0')
a.sw('ra', 8, 't2'); a.sw('a0', 12, 't2')
a.addiu('t1', 't1', 1); a.sw('t1', 0, 't0')
a.addiu('sp', 'sp', -32); a.sw('s2', 24, 'sp')
a.j(0x80104EE4); a.nop()
wr(0x801FB680, a.assemble())
wr(BUF, b'\0' * (8 + 64 * 8))
wr(0x80104EDC, struct.pack('<II', (2 << 26) | ((0x801FB680 >> 2) & 0x3FFFFFF), 0))
print('patched')

def dump():
    d = ra.mem(BUF, 8 + 64 * 8)
    n = struct.unpack('<I', d[:4])[0]
    ents = [struct.unpack('<II', d[8 + i * 8:16 + i * 8]) for i in range(min(n, 64))]
    from collections import Counter
    print('calls', n, Counter(hex(r) for r, _ in ents))
    print('codes', ' '.join('%04x' % (c & 0xFFFF) for _, c in ents[:40]))

if __name__ == '__main__' and len(sys.argv) > 1:
    time.sleep(float(sys.argv[1])); dump()
