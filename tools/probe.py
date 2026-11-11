"""Probe: redirect ST0 GetGlyph to a counter stub to see if it runs. Assumes the state is loaded."""
import sys, time, os, struct
sys.path.insert(0, os.path.dirname(__file__))
import ra
from asm import Asm

def wr(addr, data):
    for k in range(0, len(data), 32):
        ch = data[k:k + 32]
        ra.cmd('WRITE_CORE_RAM %x %s' % ((addr & 0x1FFFFF) + k, ' '.join('%02x' % b for b in ch)))

a = Asm(0x801FB680)
a.li('t0', 0x801FB900)
a.sw('a1', 0, 't0')
a.lw('t1', 4, 't0'); a.nop(); a.addiu('t1', 't1', 1); a.sw('t1', 4, 't0')
a.j(0x801FB600); a.nop()
wr(0x801FB680, a.assemble())
wr(0x801FB900, b'\0' * 8)
wr(0x801B17F8, struct.pack('<I', (2 << 26) | ((0x801FB680 >> 2) & 0x3FFFFFF)))
print('patched; waiting')
if __name__ == '__main__':
    time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 10)
    print('last a1 / count:', ra.mem(0x801FB900, 8).hex(' '))
