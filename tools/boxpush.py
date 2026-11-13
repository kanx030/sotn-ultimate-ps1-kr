"""Pushable crates (Underground Caverns NO4 / reverse RNO4) move only while PLAYER.step == 1 (walk). With the
Godspeed Shoes always-dash (godspeed.py) every walk is a dash (step 0x13), so the crates could not be pushed.

Each crate check (pad right/left held, then the step test):
    andi v0,v0,0x2000|0x8000 ; beq v0,zero,skip ; ori v0,zero,1
    lui v1,0x8007 ; lhu v1,0x3404(v1) ; nop ; bne v1,v0,skip ; nop
becomes
    lui v1,0x8007 ; lhu v1,0x3404(v1) ; nop ; andi v1,v1,0xFFED ; bne v1,v0,skip
(steps 1, 3, 0x11, 0x13 pass). The instruction after (lh v0,0x7C(s0)) becomes the branch delay slot: on the push
path it ran next anyway; on the skip path v0 is not used (entity update, no return value / overwritten).
"""
import struct

FILES = ('ST/NO4/NO4.BIN', 'ST/RNO4/RNO4.BIN')
LOG = []
OLD = (0x3C038007, 0x94633404, 0x00000000)


def patch(rel, data):
    if rel not in FILES:
        return data
    d = bytearray(data); n = 0
    w = lambda o: struct.unpack_from('<I', d, o)[0]
    for o in range(12, len(d) - 20, 4):
        if (w(o - 12) & 0xFFFF0000) != 0x30420000 or (w(o - 12) & 0xFFFF) not in (0x2000, 0x8000):
            continue
        if w(o - 8) >> 16 != 0x1040 or w(o - 4) != 0x34020001:
            continue
        if (w(o), w(o + 4), w(o + 8)) != OLD:
            continue
        br, nop = w(o + 12), w(o + 16)
        if br >> 16 == 0x1462 and nop == 0:
            off = ((br & 0xFFFF) ^ 0x8000) - 0x8000          # target = o + 16 + 4*off
            tgt = o + 16 + 4 * off
            nb = 0x14620000 | (((tgt - (o + 20)) // 4) & 0xFFFF)
            struct.pack_into('<II', d, o + 12, 0x3063FFED, nb)
            n += 1
        elif br == 0x3063FFED:
            n += 1                                           # already patched
    assert n >= 2, (rel, n)
    LOG.append('boxpush %s: %d crate checks' % (rel, n))
    return bytes(d)


if __name__ == '__main__':
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import base, mips
    for f in FILES:
        a = open(base.upath(f), 'rb').read()
        b = patch(f, a)
        assert patch(f, b) == b
        for o in range(0, len(a), 4):
            if a[o:o + 4] != b[o:o + 4]:
                print(f, mips.listing(b, o - 4, 0x80180000 + o - 4, 3))
    print('\n'.join(LOG))
