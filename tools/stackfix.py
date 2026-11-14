"""AllocPrimitives without recursion (2026-11-14 freeze fix).

DRA 0x800EBB04 AllocPrimitives(type, count) and 0x800EBC20 (the same, searching the pool from the top) call
themselves once per primitive: an enemy asking for hundreds of primitives (Frozen Half in the Floating Catacombs)
pushes 40 bytes of stack per call, ~20 KB, down to 0x801FAEFC. In the US game that RAM is free; in ours it holds
the Korean font, the Galmuri7 glyph cache (0x801F9724..) and the ext code (0x801FB400..), so menus, banners and
saving froze from then on. Both are rewritten in place as loops with the same results:
  0x800EBB04: lowest free prims chained upward, last next = NULL, D_800A21A4 = max(D_800A21A4, last index),
              returns the first index; none left -> every prim it took gets type 0 again, returns -1.
  0x800EBC20: same from the top of the pool down; as the original, when the pool runs out after some prims the
              last one links to prim[-1] and the first index is returned (no prim at all -> -1).
Prim pool g_PrimBuf 0x80086FEC, 1280 x 0x34 bytes (type byte at +7, next pointer at +0); clear = 0x800EB8F4."""
import struct
from asm import Asm, R

FILES = ('DRA.BIN',)
DRA = 0x800A0000
BUF = 0x80086FEC
CLEAR = 0x800EB8F4
MAXV_HI, MAXV_LO = 0x800A, 0x21A4
F1, F1_END = 0x800EBB04, 0x800EBC20
F2, F2_END = 0x800EBC20, 0x800EBCFC
F1_SIG = bytes.fromhex('d8ffbd272000b4af21a0a0001c00b3af21988000')
F2_SIG = bytes.fromhex('d8ffbd272000b4af21a0a0001c00b3af21988000')
LOG = []


def _prologue(a, first=True):
    a.addiu('sp', 'sp', -48)
    a.sw('ra', 36, 'sp'); a.sw('s4', 32, 'sp'); a.sw('s3', 28, 'sp')
    a.sw('s2', 24, 'sp'); a.sw('s1', 20, 'sp'); a.sw('s0', 16, 'sp')
    a.andi('s3', 'a0', 0xFF); a.addu('s4', 'a1', 'zero')
    a.sw('zero', 40, 'sp')                       # prev prim (0 = none yet)
    if first: a.sw('zero', 44, 'sp')             # first prim pointer


def _take(a, first=True):
    """s1 = free prim: clear it, set type, link after prev (or remember as first). Falls through."""
    a.jal(CLEAR); a.addu('a0', 's1', 'zero')
    a.sb('s3', 7, 's1')
    a.lw('v1', 40, 'sp'); a.nop()
    a.bne('v1', 'zero', 'link'); a.nop()
    if first: a.sw('s1', 44, 'sp')
    a.b('linked'); a.addu('s0', 's2', 'zero')    # first index
    a.label('link')
    a.sw('s1', 0, 'v1')                          # prev->next = this
    a.label('linked')
    a.sw('s1', 40, 'sp')
    a.addiu('s4', 's4', -1)


def _epilogue(a):
    a.label('exit')
    a.lw('ra', 36, 'sp'); a.lw('s4', 32, 'sp'); a.lw('s3', 28, 'sp')
    a.lw('s2', 24, 'sp'); a.lw('s1', 20, 'sp'); a.lw('s0', 16, 'sp')
    a.jr('ra'); a.addiu('sp', 'sp', 48)


def code_f1():
    a = Asm(F1)
    _prologue(a)
    a.li('s1', BUF); a.addu('s2', 'zero', 'zero')
    a.label('loop')
    a.slti('v0', 's2', 1024)
    a.beq('v0', 'zero', 'fail'); a.nop()
    a.lbu('v0', 7, 's1'); a.nop()
    a.bne('v0', 'zero', 'next'); a.nop()
    _take(a)
    a.bne('s4', 'zero', 'next'); a.nop()
    a.lui('v1', MAXV_HI); a.lw('v0', MAXV_LO, 'v1'); a.nop()          # last prim: max index
    a.w((R['v0'] << 21) | (R['s2'] << 16) | (R['v0'] << 11) | 42)   # slt v0,v0,s2 (signed, as the original)
    a.beq('v0', 'zero', 'ret'); a.nop()
    a.sw('s2', MAXV_LO, 'v1')
    a.label('ret')
    a.b('exit'); a.addu('v0', 's0', 'zero')
    a.label('next')
    a.addiu('s2', 's2', 1)
    a.b('loop'); a.addiu('s1', 's1', 0x34)
    a.label('fail')                              # give back what was taken
    a.lw('v1', 44, 'sp'); a.nop()
    a.label('undo')
    a.beq('v1', 'zero', 'm1'); a.nop()
    a.sb('zero', 7, 'v1')
    a.lw('v1', 0, 'v1')
    a.b('undo'); a.nop()
    a.label('m1')
    a.addiu('v0', 'zero', -1)
    _epilogue(a)
    b = a.assemble()
    assert F1 + len(b) <= F1_END, hex(len(b))
    return b


def code_f2():
    a = Asm(F2)
    _prologue(a, False)
    a.li('s1', BUF + 0x4FF * 0x34); a.ori('s2', 'zero', 0x4FF)
    a.label('loop')
    a.slti('v0', 's2', 0)
    a.bne('v0', 'zero', 'fail'); a.nop()
    a.lbu('v0', 7, 's1'); a.nop()
    a.bne('v0', 'zero', 'next'); a.nop()
    _take(a, False)
    a.bne('s4', 'zero', 'next'); a.nop()
    a.b('exit'); a.addu('v0', 's0', 'zero')
    a.label('next')
    a.addiu('s2', 's2', -1)
    a.b('loop'); a.addiu('s1', 's1', -0x34)
    a.label('fail')
    a.lw('v1', 40, 'sp'); a.nop()
    a.beq('v1', 'zero', 'exit'); a.addiu('v0', 'zero', -1)
    a.sw('s1', 0, 'v1')                          # s1 = prim[-1] here; as the original, last link -> prim[-1]
    a.b('exit'); a.addu('v0', 's0', 'zero')
    _epilogue(a)
    b = a.assemble()
    assert F2 + len(b) <= F2_END, hex(len(b))
    return b


def patch(rel, data):
    if rel != 'DRA.BIN':
        return data
    d = bytearray(data)
    for va, end, sig, fn, name in ((F1, F1_END, F1_SIG, code_f1, 'AllocPrimitives'),
                                   (F2, F2_END, F2_SIG, code_f2, 'AllocPrimitivesReverse')):
        o = va - DRA
        new = fn()
        if bytes(d[o:o + len(new)]) == new:
            LOG.append('stackfix %s: already' % name); continue
        assert bytes(d[o:o + len(sig)]) == sig, (name, d[o:o + 20].hex())
        d[o:end - DRA] = new + b'\0' * (end - va - len(new))
        LOG.append('stackfix %s: %d words (was %d, recursive)' % (name, len(new) // 4, (end - va) // 4))
    return bytes(d)


if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import base, mips
    a = open(base.upath('DRA.BIN'), 'rb').read()
    b = patch('DRA.BIN', a)
    assert patch('DRA.BIN', b) == b
    for va in (F1, F2):
        print('\n'.join(mips.listing(b, va - DRA, va, 8)))
    print('\n'.join(LOG))
