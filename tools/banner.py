"""Korean (engine-A, `fin FF cv`) support for the name drawers that do not go through MenuDrawStr.

Our 8x8 strings store a syllable as <final cell> FF <initial+medial cell> (see draa.py): the FF xx pair
means "draw xx over the previous cell, 2 px up". MenuDrawStr was fixed in draa; these drawers were not:

1. BottomCornerText (item-pickup banner bottom-left, Faerie Scroll enemy name bottom-right), one copy in
   every stage/boss overlay (58 files, identical code; NO0 0x801C7398, args a0 = string, a1 = lower_left).
   US: collects the string into a 64-byte stack buffer dropping the FF (so FF xx became a separate cell),
   draws each cell 8 px apart and a 00 cell (our "no final") as a 4 px gap -> "ㅅ마ㅆ이ㄴ는 고기".
   K (JP base) has a different, longer pair-based routine; ours is rewritten in place, same size:
     collect (S+0x1C..S+0x7C): bytes copied as-is, FF xx -> FF marker + xx; width = 8 per cell,
       an FF group adds 0 (so a syllable is 8 px), buffer bounded at 63 bytes; no buffer clear needed
       (the draw loop stops when the charcount+4 prims run out, as before);
     draw (S+0x298..S+0x30C): 00 -> +8, FF -> x -= 8 and next cell at y 0xD2 (K: final 0xD4, CV 0xD2),
       other cells drawn at (x, y) and x += 8. A space (single 00) is now 8 px (as K) instead of 4.
2. DRA 0x8011D4B4 (DRA's own equipment-drop banner, called from 0x8011DBF8): the leftover JP pair
   routine; overlay cell drawn at y 0xCC (y-8) -> 0xD2 (0x8011D7CC), and its 12 px advance after a
   group whose 2nd cell is F0..FC (JP wide glyphs; none of our CV cells, safety only) disabled -> always
   8 (0x8011D7FC sltiu 13 -> 0).
3. LIB shop list drawer 0x801B19C4 (prim a0, x a1, y a2, string a3, clut [sp+16]; returns next prim) used
   for item names / menu8 labels in the librarian's shop: rewritten in place (79 words), keeps the US
   narrow-letter spacing for plain cells (i l f I ') and draws FF xx over the previous cell at
   (group x, y-2) with the group 8 px wide (K 0x801B4E44 does the same with y-2).

Build use:
    import banner
    for f in banner.FILES: data = banner.patch(f, data)   # f as in build ('DRA.BIN', 'ST/NO0/NO0.BIN', ...)
patch() asserts the original bytes and returns data unchanged for other paths.
`python banner.py` patches the US files in memory and prints what changed.
"""
import os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm import Asm

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
U = os.path.join(ROOT, 'work', 'U')
OVL = 0x80180000
DRA_BASE = 0x800A0000

# BottomCornerText start address per overlay (found by signature, all byte-identical except j targets)
BCT = {
    'ST/ARE/ARE.BIN': 0x801c34e8, 'ST/CAT/CAT.BIN': 0x801cecac, 'ST/CEN/CEN.BIN': 0x801bf65c,
    'ST/CHI/CHI.BIN': 0x801a7e34, 'ST/DAI/DAI.BIN': 0x801d116c, 'ST/DRE/DRE.BIN': 0x801a2b3c,
    'ST/LIB/LIB.BIN': 0x801cc994, 'ST/NO0/NO0.BIN': 0x801c7398, 'ST/NO1/NO1.BIN': 0x801cd364,
    'ST/NO2/NO2.BIN': 0x801c7f10, 'ST/NO3/NO3.BIN': 0x801d4de8, 'ST/NO4/NO4.BIN': 0x801d59d4,
    'ST/NP3/NP3.BIN': 0x801cae2c, 'ST/NZ0/NZ0.BIN': 0x801c3914, 'ST/NZ1/NZ1.BIN': 0x801b75f4,
    'ST/RARE/RARE.BIN': 0x801b1954, 'ST/RCAT/RCAT.BIN': 0x801bed64, 'ST/RCEN/RCEN.BIN': 0x801abcc8,
    'ST/RCHI/RCHI.BIN': 0x801a5a08, 'ST/RDAI/RDAI.BIN': 0x801bf440, 'ST/RLIB/RLIB.BIN': 0x801ad974,
    'ST/RNO0/RNO0.BIN': 0x801c6a10, 'ST/RNO1/RNO1.BIN': 0x801b3e00, 'ST/RNO2/RNO2.BIN': 0x801c1b20,
    'ST/RNO3/RNO3.BIN': 0x801c67e4, 'ST/RNO4/RNO4.BIN': 0x801d2fe0, 'ST/RNZ0/RNZ0.BIN': 0x801b7a18,
    'ST/RNZ1/RNZ1.BIN': 0x801b9f00, 'ST/RTOP/RTOP.BIN': 0x801ad308, 'ST/RWRP/RWRP.BIN': 0x801993f0,
    'ST/ST0/ST0.BIN': 0x801bae04, 'ST/TE1/TE1.BIN': 0x801dc624, 'ST/TE2/TE2.BIN': 0x801a837c,
    'ST/TE3/TE3.BIN': 0x801caf10, 'ST/TE4/TE4.BIN': 0x801b0100, 'ST/TOP/TOP.BIN': 0x801b9418,
    'ST/WRP/WRP.BIN': 0x80197470,
    'BOSS/BO0/BO0.BIN': 0x801ccc40, 'BOSS/BO1/BO1.BIN': 0x801b03a8, 'BOSS/BO2/BO2.BIN': 0x801b2858,
    'BOSS/BO3/BO3.BIN': 0x801b15b4, 'BOSS/BO4/BO4.BIN': 0x801c17c4, 'BOSS/BO5/BO5.BIN': 0x801b1e74,
    'BOSS/BO6/BO6.BIN': 0x801b523c, 'BOSS/BO7/BO7.BIN': 0x801a1450, 'BOSS/MAR/MAR.BIN': 0x80198148,
    'BOSS/RBO0/RBO0.BIN': 0x801a4e6c, 'BOSS/RBO1/RBO1.BIN': 0x8019ff4c, 'BOSS/RBO2/RBO2.BIN': 0x801acb68,
    'BOSS/RBO3/RBO3.BIN': 0x8019dfa0, 'BOSS/RBO4/RBO4.BIN': 0x801a3c14, 'BOSS/RBO5/RBO5.BIN': 0x801c06f8,
    'BOSS/RBO6/RBO6.BIN': 0x801b0e3c, 'BOSS/RBO7/RBO7.BIN': 0x801a0cdc, 'BOSS/RBO8/RBO8.BIN': 0x801a4ba0,
}
BCT_LEN = 0x330
# NO0 copy (0x801C7398..0x801C76C8); j/jal words are compared on the opcode only
BCT_ORIG = bytes.fromhex(
    'a0ffbd27 5400b1af 2188a000 1000a527 5000b0af 21800000 21680000 3f000234'
    '5800bfaf 0000a0a0 ffff4224 fdff4104 0100a524 1000a527 ff000234 00008390'
    '00000000 05006214 01008424 00008390 00000000 09006010 01008424 0000a3a0'
    '04006010 0100a524 0100ad25 00000008 08001026 00000008 04001026'.replace(' ', ''))
COLLECT = (0x1C, 0x7C)          # S+0x1C .. S+0x7C (24 words, ends at "andi a1,t5,0xffff")
DRAW = (0x298, 0x30C)           # S+0x298 .. S+0x30C (29 words, ends at "ori v0,zero,0x130")
DRAW_ORIG = bytes.fromhex(
    '1e000934 96010834 08000434 f0010734 d4000634 0000a390 00000000 12006010'
    '0100a524 08008da5 0f006230 c0100200 0c0082a1 f0006230 42100200 1a0089a5'
    '0e0088a5 0d0082a1 190084a1 180084a1 260087a5 320080a5 0a0086a5 00008c8d'
    '00000008 0800ad25 0400ad25 e9ff8015 00000000'.replace(' ', ''))

DRA_Y = (0x8011D7CC, 0x340200CC, 0x340200D2)       # ori v0,zero,0xcc -> 0xd2  (overlay cell y)
DRA_W = (0x8011D7FC, 0x2C42000D, 0x2C420000)       # sltiu v0,v0,13 -> 0       (no 12 px cells)

LIB = 'ST/LIB/LIB.BIN'
SHOP = 0x801B19C4
SHOP_LEN = 79 * 4
SHOP_ORIG_HEAD = bytes.fromhex('c0ffbd27 5000ad97 2148a003 21500000 3f000234'.replace(' ', ''))
SHOP_ORIG_TAIL = bytes.fromhex('21108000 4000bd27 0800e003 00000000'.replace(' ', ''))

FILES = ['DRA.BIN'] + sorted(BCT)


def _mask(b):
    out = []
    for i in range(0, len(b), 4):
        w = struct.unpack_from('<I', b, i)[0]
        out.append(w >> 26 if (w >> 26) in (2, 3) else w)
    return out


def _collect_code(s):
    import g7
    a = Asm(s + COLLECT[0])
    end = s + COLLECT[1]
    a.sw('ra', 88, 'sp')                    # displaced from the old clear loop
    a.addiu('a1', 'sp', 16)                 # buffer
    a.ori('a2', 'zero', 0xFF)
    a.addiu('t0', 'sp', 16 + 62)            # stop before writing past buf[62] (FF path writes 2 bytes)
    a.label('L')
    a.sltu('v0', 'a1', 't0')
    a.beq('v0', 'zero', end)
    a.nop()
    a.jal(g7.entries()['G7A0'])             # v1 = cell (a Korean syllable -> one Galmuri7 cache cell), a0 advanced
    a.nop()
    a.bne('v1', 'a2', 'P')
    a.nop()
    a.lbu('v1', 0, 'a0')                    # FF xx (only FF 00 = end in practice)
    a.addiu('a0', 'a0', 1)
    a.beq('v1', 'zero', end)
    a.sb('a2', 0, 'a1')                     # FF marker (harmless at the end)
    a.addiu('a1', 'a1', 1)
    a.addiu('s0', 's0', -8)                 # overlay: group stays 8 px
    a.label('P')
    a.sb('v1', 0, 'a1')
    a.addiu('a1', 'a1', 1)
    a.beq('v1', 'zero', 'L')
    a.addiu('s0', 's0', 8)                  # width += 8 per cell
    a.b('L')
    a.addiu('t5', 't5', 1)                  # charcount (prims)
    code = a.assemble()
    n = COLLECT[1] - COLLECT[0]
    assert len(code) <= n, len(code)
    return code + b'\0' * (n - len(code))


DRA_COLLECT = (0x8011D4E8, 0x8011D564)


def _dra_collect_code():
    """DRA drop banner: (cell, overlay) pairs -> (cell, 0) with syllables as one g7 cache cell."""
    import g7
    a = Asm(DRA_COLLECT[0])
    end = DRA_COLLECT[1]
    a.label('L')
    a.jal(g7.entries()['G7A0'])
    a.nop()
    a.bne('v1', 'a3', 'P')
    a.nop()
    a.lbu('v1', 0, 'a0')
    a.addiu('a0', 'a0', 1)
    a.beq('v1', 'zero', end)
    a.nop()
    a.label('P')
    a.sb('v1', 0, 'a1')
    a.addiu('a1', 'a1', 2)
    a.beq('v1', 'zero', 'L')
    a.addiu('s0', 's0', 1)
    a.b('L')
    a.addiu('t5', 't5', 1)
    code = a.assemble()
    n = end - DRA_COLLECT[0]
    assert len(code) <= n
    return code + b'\0' * (n - len(code))


def _draw_code(s):
    a = Asm(s + DRAW[0])
    end = s + DRAW[1]
    a.lui('a0', 0x001E)                     # w=8, h=8, tpage 0x1E as one word at +24
    a.ori('a0', 'a0', 0x0808)
    a.ori('t0', 'zero', 0x196)              # clut
    a.ori('a3', 'zero', 0x1F0)              # priority
    a.ori('a2', 'zero', 0xD4)               # y
    a.ori('t2', 'zero', 0xFF)
    a.label('L')
    a.lbu('v1', 0, 'a1')
    a.addiu('a1', 'a1', 1)
    a.beq('v1', 't2', 'F')
    a.sh('t5', 8, 't4')                     # x (rewritten when the prim is really used)
    a.beq('v1', 'zero', 'Z')
    a.andi('v0', 'v1', 0xF)
    a.sll('v0', 'v0', 3)
    a.sb('v0', 12, 't4')
    a.andi('v0', 'v1', 0xF0)
    a.srl('v0', 'v0', 1)
    a.sb('v0', 13, 't4')
    a.sh('t0', 14, 't4')
    a.sw('a0', 24, 't4')
    a.sh('a3', 38, 't4')
    a.sh('zero', 50, 't4')
    a.sh('a2', 10, 't4')
    a.lw('t4', 0, 't4')
    a.b('Z')
    a.ori('a2', 'zero', 0xD4)
    a.label('F')                            # FF: next cell over the previous one, 2 px up
    a.addiu('t5', 't5', -16)
    a.ori('a2', 'zero', 0xD2)
    a.label('Z')
    a.bne('t4', 'zero', 'L')
    a.addiu('t5', 't5', 8)
    assert a.pc == end, hex(a.pc)
    return a.assemble()


def _shop_code():
    import g7
    a = Asm(SHOP)
    a.sw('ra', 0, 'sp')                     # arg home area: ra survives the g7 call
    a.lhu('t5', 16, 'sp')                   # clut (5th arg)
    a.ori('t3', 'zero', 0xFF)
    a.ori('t4', 'zero', 0x49)
    a.addu('t6', 'a1', 'zero')              # x of the last cell group
    a.label('L')
    a.jal(g7.entries()['G7A3'])             # v1 = cell (syllable -> g7 cache cell), a3 advanced
    a.nop()
    a.bne('v1', 't3', 'C')
    a.nop()
    a.lbu('v1', 0, 'a3')                    # FF xx
    a.addiu('a3', 'a3', 1)
    a.beq('v1', 'zero', 'END')              # FF 00 = end
    a.addiu('a1', 't6', 8)                  # the group is 8 px wide
    a.andi('v0', 'v1', 0xF)
    a.sll('v0', 'v0', 3)
    a.sb('v0', 12, 'a0')
    a.andi('v0', 'v1', 0xF0)
    a.srl('v0', 'v0', 1)
    a.sb('v0', 13, 'a0')
    a.sh('t5', 14, 'a0')
    a.sh('zero', 50, 'a0')
    a.sh('t6', 8, 'a0')
    a.addiu('v0', 'a2', -2)
    a.sh('v0', 10, 'a0')
    a.b('L')
    a.lw('a0', 0, 'a0')
    a.label('C')
    a.beq('v1', 'zero', 'Z')
    a.addu('t6', 'a1', 'zero')
    a.ori('t7', 'zero', 8)                  # US spacing: i l: -1/+7, f I: -1/+8, ': -2/+6
    a.beq('v1', 't4', 'A')
    a.ori('v0', 'zero', 0x4C)
    a.bne('v1', 'v0', 'B')
    a.ori('v0', 'zero', 0x46)
    a.label('A')
    a.b('P1')
    a.ori('t7', 'zero', 7)
    a.label('B')
    a.beq('v1', 'v0', 'P1')
    a.ori('v0', 'zero', 0x29)
    a.beq('v1', 'v0', 'P1')
    a.ori('v0', 'zero', 0x07)
    a.bne('v1', 'v0', 'D')
    a.nop()
    a.addiu('a1', 'a1', -1)
    a.ori('t7', 'zero', 6)
    a.label('P1')
    a.addiu('a1', 'a1', -1)
    a.label('D')
    a.andi('v0', 'v1', 0xF)
    a.sll('v0', 'v0', 3)
    a.sb('v0', 12, 'a0')
    a.andi('v0', 'v1', 0xF0)
    a.srl('v0', 'v0', 1)
    a.sb('v0', 13, 'a0')
    a.sh('t5', 14, 'a0')
    a.sh('zero', 50, 'a0')
    a.sh('a1', 8, 'a0')
    a.sh('a2', 10, 'a0')
    a.lw('a0', 0, 'a0')
    a.b('L')
    a.addu('a1', 'a1', 't7')
    a.label('Z')
    a.b('L')
    a.addiu('a1', 'a1', 4)                  # single 00 = US 4 px gap
    a.label('END')
    a.lw('ra', 0, 'sp')
    a.nop()
    a.jr('ra')
    a.addu('v0', 'a0', 'zero')
    code = a.assemble()
    assert len(code) <= SHOP_LEN, len(code)
    return code + b'\0' * (SHOP_LEN - len(code))


def _norm(path):
    p = path.replace('\\', '/').lstrip('/')
    return p.split(';')[0]


def patch(path, data):
    p = _norm(path)
    if p == 'DRA.BIN':
        d = bytearray(data)
        for va, old, new in (DRA_Y, DRA_W):
            o = va - DRA_BASE
            assert struct.unpack_from('<I', d, o)[0] == old, (hex(va), d[o:o + 4].hex())
            struct.pack_into('<I', d, o, new)
        o = DRA_COLLECT[0] - DRA_BASE
        assert d[o:o + 8] == bytes.fromhex('0000839000000000'), 'DRA banner collect'
        d[o:DRA_COLLECT[1] - DRA_BASE] = _dra_collect_code()
        return bytes(d)
    if p not in BCT:
        return data
    d = bytearray(data)
    s = BCT[p]
    o = s - OVL
    assert _mask(bytes(d[o:o + len(BCT_ORIG)])) == _mask(BCT_ORIG), (p, 'BottomCornerText head')
    assert _mask(bytes(d[o + DRAW[0]:o + DRAW[1]])) == _mask(DRAW_ORIG), (p, 'BottomCornerText draw loop')
    d[o + COLLECT[0]:o + COLLECT[1]] = _collect_code(s)
    d[o + DRAW[0]:o + DRAW[1]] = _draw_code(s)
    if p == LIB:
        so = SHOP - OVL
        assert bytes(d[so:so + len(SHOP_ORIG_HEAD)]) == SHOP_ORIG_HEAD, 'LIB shop drawer head'
        assert bytes(d[so + SHOP_LEN - len(SHOP_ORIG_TAIL):so + SHOP_LEN]) == SHOP_ORIG_TAIL, 'LIB shop drawer tail'
        d[so:so + SHOP_LEN] = _shop_code()
    return bytes(d)


if __name__ == '__main__':
    n = 0
    for f in FILES:
        src = open(os.path.join(U, *f.split('/')), 'rb').read()
        out = patch(f, src)
        diff = sum(1 for i in range(0, len(src), 4) if src[i:i + 4] != out[i:i + 4])
        print('%-22s %3d words changed' % (f, diff))
        n += 1
    print(n, 'files')
