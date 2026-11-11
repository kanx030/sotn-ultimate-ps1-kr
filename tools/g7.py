"""Galmuri7 (OFL) whole-syllable glyphs for every 8x8 menu-sheet text drawer (font unification, stage 1).

Strings keep the engine-A encoding (draa.encode_a: syllable = <final cell> FF <initial+medial cell>), so all
existing tools/limits stay valid. Instead of drawing the two K pieces, every drawer now reads its bytes
through one RAM routine, G7 CORE:

    in  v1 = string pointer
    out v0 = sheet cell to draw as a plain 8x8 cell, v1 = pointer past it
    (all other registers preserved; non-syllable bytes come back unchanged with v1+1)

A syllable group `fin FF cv` is decoded (CVTAB/FINTAB -> Unicode offset), looked up in the sorted bank SYL
(binary search) and mapped to a *cache cell* of the 8x8 sheet itself (VRAM 896,256, tpage 0x1E): the K
initial+medial cells (and unused final cells) are no longer drawn by anything, so they serve as a 2nd-chance
glyph cache: on a miss the Galmuri7 glyph (7x7 1bpp, bank GLY) is expanded to 4bpp (ink index 6, like the
sheet) and LoadImage'd into the victim cell (4 staging buffers, DrawSync(0) before reuse). Because the cache
is the sheet, drawers need no tpage/uv changes and a syllable is simply 8 px wide at the normal y.
If no 8x8 text was drawn for GAP vblanks (VSync counter 0x8002D374), the cache is dropped (the sheet may have
been reloaded from F_GAME meanwhile).

Stage 2 (MenuDrawStr) is hooked here as well (it must be: the sheet cells it used become cache cells).
Glue entries (return the cell in the drawer's own registers):
    G7A0: v1 = cell, a0 advanced      (BottomCornerText collect, DRA drop banner collect)
    G7A3: v1 = cell, a3 advanced      (LIB shop/boss list drawer)
    G7S0: a0 = cell, s0 advanced      (MenuDrawStr loop)
    NAMEH: cutscene speaker-name loop (j NAMEH; ori t9,zero,fid), uses build.NHEAD
RAM: font slots 1290..1535 (Korean-font kanji area; fontext keeps 1210..1289).
"""
import os, sys, struct, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm import Asm

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
BDF = os.path.join(ROOT, 'work', 'dl', 'galmuri', 'Galmuri7.bdf')
FONT_RAM = 0x801F0000
G7_RAM = FONT_RAM + 1290 * 30            # 0x801F9724
G7_END = FONT_RAM + 1536 * 30            # EXT_RAM (build) starts here
LOADIMAGE = 0x80012B24
DRAWSYNC = 0x8001290C
VCOUNT = 0x8002D374
GAP = 12                                 # vblanks without any 8x8 text -> drop the cache
INK = 6
NB = 4                                   # staging buffers
SHEET_X, SHEET_Y = 896, 256

CODE_MAX = 0x520
# data offsets (from G7_RAM + CODE_MAX)
D_SAVE = 0x00        # 26 words
D_LASTV = 0x68
D_CLOCK = 0x6C
D_RING = 0x70
D_NRA = 0x74
D_PEND = 0x78
D_GRA = 0x7C
D_BUF = 0x80         # NB x (rect 8 + 32)
D_SLOTS = D_BUF + NB * 40
SMAX = 168


def _slots():
    import draa
    bad = {0x46, 0x49, 0x4C} | set(draa.PLAIN_DEC) | set(draa.FIN)   # shop narrow letters, plain cells
    cells = sorted(c for c in draa.CV if c not in bad)
    cells += [c for c in (0x0C, 0x61, 0x62, 0x63, 0x64, 0xFC)]      # final pieces with no ASCII meaning
    # NB: 0x61..0x64/0xFC are final cells but nothing draws pieces any more
    assert len(cells) <= SMAX
    return cells


def layout(n):
    s = len(_slots())
    d = G7_RAM + CODE_MAX
    L = {'SAVE': d + D_SAVE, 'LASTV': d + D_LASTV, 'CLOCK': d + D_CLOCK, 'RING': d + D_RING,
         'NRA': d + D_NRA, 'PEND': d + D_PEND, 'GRA': d + D_GRA, 'BUF': d + D_BUF, 'SLOTS': d + D_SLOTS}
    o = d + D_SLOTS + SMAX
    L['REF'] = o; o += SMAX
    L['GLYOF'] = o; o += 2 * SMAX
    L['CVTAB'] = o; o += 2 * 0xD0          # cells 0x30..0xFF
    L['FINTAB'] = o; o += 0x100
    L['SYL'] = o; o += 2 * n
    L['SLOTOF'] = o; o += n
    L['GLY'] = o; o += 7 * n
    L['END'] = o
    L['S'] = s
    assert o <= G7_END, ('G7 bank too big', n, hex(o), hex(G7_END))
    return L


# ------------------------------------------------------------------ glyphs
_G = None
def _glyphs():
    global _G
    if _G is None:
        _G = {}
        cur = None
        for line in open(BDF, encoding='utf-8', errors='replace'):
            if line.startswith('ENCODING'):
                cur = {'enc': int(line.split()[1])}
            elif line.startswith('BBX') and cur is not None:
                cur['bbx'] = tuple(map(int, line.split()[1:5]))
            elif line.startswith('BITMAP') and cur is not None:
                cur['rows'] = []
            elif line.startswith('ENDCHAR') and cur is not None:
                _G[cur['enc']] = cur; cur = None
            elif cur is not None and 'rows' in cur:
                cur['rows'].append(int(line.strip() or '0', 16))
    return _G


CUSTOM = {}           # carrier syllable -> 7-byte tile (engfix: big status-screen name drawn as 8x7 tiles)

def glyph(ch):
    """7 bytes: rows 0..6 of the 8x8 cell, bit 7 = column 0. Baseline = bottom of row 6 (like the sheet's A-Z)."""
    if ch in CUSTOM:
        return CUSTOM[ch]
    g = _glyphs()[ord(ch)]
    w, h, xo, yo = g['bbx']
    nb = (w + 7) // 8
    out = [0] * 7
    top = 7 - (yo + h)
    for r, v in enumerate(g['rows']):
        y = top + r
        if 0 <= y < 7:
            bits = v >> (nb * 8 - w)
            for c in range(w):
                if bits & (1 << (w - 1 - c)) and 0 <= xo + c < 8:
                    out[y] |= 0x80 >> (xo + c)
    return bytes(out)


# ------------------------------------------------------------------ syllable set
USED = set()           # filled by draa.encode_a (every engine-A string of the build)

def _ok(ch):
    import draa
    sp = draa._split(ch)
    return bool(sp) and sp[0] in draa._CV_ENC and sp[1] in draa._FIN_ENC

def syllables():
    import draa, build
    s = set(ch for ch in USED if _ok(ch))
    for e in json.load(open(os.path.join(ROOT, 'work', 'trans', 'DRA_A.json'), encoding='utf-8')):
        s.update(ch for ch in (e.get('ko') or '') if _ok(ch))
    for fn in glob.glob(os.path.join(ROOT, 'work', 'trans', 'extra_*.json')):
        for e in json.load(open(fn, encoding='utf-8'))['items']:
            if e.get('path') in ('menu8', 'ascii8'):
                s.update(ch for ch in (e.get('ko') or '') if _ok(ch))
    for _, ko in build.NAMES:
        s.update(ch for ch in ko if _ok(ch))
    return sorted(s)


def tables(syls):
    import draa
    cvtab = bytearray(b'\xff' * (2 * 0xD0))
    for c, ch in list(draa.CV.items()) + list(draa.EXT_CV.items()):
        if c >= 0x30:
            struct.pack_into('<H', cvtab, 2 * (c - 0x30), ord(ch) - 0xAC00)
    fintab = bytearray(0x100)
    for c, f in list(draa.FIN.items()) + list(draa._FIN_ALT.items()):
        fintab[c] = (draa.JONG.index(f) + 1 if f else 0) + 1
    return bytes(cvtab), bytes(fintab)


# ------------------------------------------------------------------ code
SAVED = ['at', 'a0', 'a1', 'a2', 'a3', 't0', 't1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9',
         's0', 's1', 's2', 's3', 'ra']

def code(n):
    L = layout(n)
    S = L['S']
    a = Asm(G7_RAM)
    # ---- glue
    def glue(name, ptr, dst):
        a.label(name)
        a.lui('v0', _hi(L['GRA']))
        a.sw('ra', _lo(L['GRA']), 'v0')
        a.jal('CORE')
        a.addu('v1', ptr, 'zero')
        a.addu(ptr, 'v1', 'zero')
        a.addu(dst, 'v0', 'zero')
        a.lui('v0', _hi(L['GRA']))
        a.lw('ra', _lo(L['GRA']), 'v0')
        a.nop()
        a.jr('ra')
        a.nop()
    glue('G7A0', 'a0', 'v1')
    glue('G7A3', 'a3', 'v1')
    glue('G7S0', 's0', 'a0')
    # ---- NAMEH (cutscene speaker names): t9 = fid, a2 = ptr, a3 = x; head+0x10 = space, head+0x18 = draw v1
    a.label('NAMEH')
    import build
    a.sll('t8', 't9', 2); a.li('v0', build.NHEAD_RAM); a.addu('t8', 't8', 'v0'); a.lw('t8', 0, 't8')
    a.lui('v0', _hi(L['PEND'])); a.lw('v1', _lo(L['PEND']), 'v0'); a.nop()
    a.beq('v1', 'zero', 'n1'); a.nop()
    a.sw('zero', _lo(L['PEND']), 'v0')               # 2nd primitive of a syllable with a final: same cell again
    a.andi('v1', 'v1', 0xFF)
    a.addiu('a3', 'a3', -8)
    a.addiu('v0', 't8', 0x18); a.jr('v0'); a.nop()
    a.label('n1')
    a.sw('ra', _lo(L['NRA']), 'v0')
    a.sw('a2', _lo(L['SAVE'] + 0x58), 'v0')          # original pointer
    a.jal('CORE'); a.addu('v1', 'a2', 'zero')
    a.lui('t7', _hi(L['NRA'])); a.lw('ra', _lo(L['NRA']), 't7'); a.lw('t6', _lo(L['SAVE'] + 0x58), 't7')
    a.addu('a2', 'v1', 'zero')
    a.subu('t5', 'v1', 't6'); a.ori('t9', 'zero', 3)   # (t0..t4 are live in the name loop)
    a.bne('t5', 't9', 'n2'); a.nop()                 # syllable: the count loop counted 2 cells if fin != 0
    a.lbu('t5', 0, 't6'); a.nop()
    a.beq('t5', 'zero', 'n2'); a.ori('t5', 'zero', 0x100)
    a.or_('t5', 't5', 'v0')
    a.sw('t5', _lo(L['PEND']), 't7')
    a.label('n2')
    a.ori('t5', 'zero', 0xFF)
    a.bne('v0', 't5', 'n3'); a.addu('v1', 'v0', 'zero')
    a.lbu('v1', 0, 'a2'); a.nop()                    # FF xx: xx (FF 00 -> space; pointer stays on the 00)
    a.beq('v1', 'zero', 'n3'); a.nop()
    a.addiu('a2', 'a2', 1)
    a.label('n3')
    a.bne('v1', 'zero', 'n4'); a.nop()
    a.addiu('v0', 't8', 0x10); a.jr('v0'); a.nop()
    a.label('n4')
    a.addiu('v0', 't8', 0x18); a.jr('v0'); a.nop()
    # ---- CORE
    a.label('CORE')
    a.lui('v0', _hi(L['SAVE'])); a.addiu('v0', 'v0', _lo(L['SAVE']))
    for i, r in enumerate(SAVED):
        a.sw(r, 4 * i, 'v0')
    a.addu('s3', 'v0', 'zero')                       # s3 = data base (SAVE)
    B = L['SAVE']
    def o(k): return L[k] - B
    a.addu('s2', 'v1', 'zero')                       # s2 = ptr
    # gap check
    a.lui('t0', _hi(VCOUNT)); a.lw('t0', _lo(VCOUNT), 't0')
    a.lw('t1', o('LASTV'), 's3'); a.nop()
    a.sw('t0', o('LASTV'), 's3')
    a.subu('t1', 't0', 't1'); a.sltiu('t1', 't1', GAP)
    a.bne('t1', 'zero', 'nogap'); a.nop()
    a.ori('t0', 'zero', n); a.addiu('t1', 's3', o('SLOTOF')); a.ori('t2', 'zero', 0xFF)
    a.label('inv1')
    a.sb('t2', 0, 't1'); a.addiu('t0', 't0', -1)
    a.bgtz('t0', 'inv1'); a.addiu('t1', 't1', 1)
    a.ori('t0', 'zero', S); a.addiu('t1', 's3', o('REF')); a.addiu('t3', 's3', o('GLYOF')); a.ori('t4', 'zero', 0xFFFF)
    a.label('inv2')
    a.sb('zero', 0, 't1'); a.sh('t4', 0, 't3'); a.addiu('t0', 't0', -1); a.addiu('t3', 't3', 2)
    a.bgtz('t0', 'inv2'); a.addiu('t1', 't1', 1)
    a.label('nogap')
    a.lbu('a0', 0, 's2'); a.addiu('s1', 's2', 1)    # s1 = new ptr (default)
    a.addu('v0', 'a0', 'zero')                       # v0 = cell (default)
    a.ori('at', 'zero', 0xFF)
    a.beq('a0', 'at', 'ret')
    a.lbu('a1', 1, 's2'); a.nop()
    a.bne('a1', 'at', 'ret')
    a.lbu('a2', 2, 's2'); a.nop()
    a.beq('a2', 'zero', 'ret'); a.nop()
    a.beq('a2', 'at', 'ret')
    a.sltiu('t0', 'a2', 0x30)
    a.bne('t0', 'zero', 'ret')
    a.addiu('t0', 'a2', -0x30)
    a.sll('t0', 't0', 1); a.addu('t0', 't0', 's3'); a.lhu('t2', o('CVTAB'), 't0')
    a.ori('t3', 'zero', 0xFFFF)
    a.beq('t2', 't3', 'ret')
    a.addu('t0', 's3', 'a0'); a.lbu('t3', o('FINTAB'), 't0'); a.nop()
    a.beq('t3', 'zero', 'ret'); a.addiu('t3', 't3', -1)
    a.addu('t2', 't2', 't3')                          # t2 = syllable - 0xAC00
    a.addu('t4', 'zero', 'zero'); a.ori('t5', 'zero', n)
    a.label('bs')
    a.beq('t4', 't5', 'ret')
    a.addu('t6', 't4', 't5'); a.srl('t6', 't6', 1)
    a.sll('t0', 't6', 1); a.addu('t0', 't0', 's3'); a.lhu('t7', o('SYL'), 't0'); a.nop()
    a.beq('t7', 't2', 'found')
    a.sltu('t8', 't7', 't2')
    a.bne('t8', 'zero', 'bsr'); a.nop()
    a.b('bs'); a.addu('t5', 't6', 'zero')
    a.label('bsr')
    a.b('bs'); a.addiu('t4', 't6', 1)
    a.label('found')
    a.addiu('s1', 's2', 3)
    a.addu('s0', 't6', 'zero')                        # s0 = glyph index
    a.addu('t0', 's3', 's0'); a.lbu('t1', o('SLOTOF'), 't0'); a.ori('t2', 'zero', 0xFF)
    a.bne('t1', 't2', 'hit'); a.nop()
    # allocate (second chance)
    a.lw('t1', o('CLOCK'), 's3'); a.ori('t3', 'zero', 1)
    a.label('clk')
    a.addu('t0', 's3', 't1'); a.lbu('t2', o('REF'), 't0'); a.nop()
    a.beq('t2', 'zero', 'vic'); a.nop()
    a.sb('zero', o('REF'), 't0')
    a.addiu('t1', 't1', 1); a.sltiu('t2', 't1', S)
    a.bne('t2', 'zero', 'clk'); a.nop()
    a.b('clk'); a.addu('t1', 'zero', 'zero')
    a.label('vic')
    a.addiu('t2', 't1', 1); a.sltiu('t4', 't2', S)
    a.bne('t4', 'zero', 'vv'); a.nop()
    a.addu('t2', 'zero', 'zero')
    a.label('vv')
    a.sw('t2', o('CLOCK'), 's3')
    a.sll('t4', 't1', 1); a.addu('t4', 't4', 's3'); a.lhu('t5', o('GLYOF'), 't4'); a.ori('t6', 'zero', 0xFFFF)
    a.beq('t5', 't6', 'v2'); a.addu('t7', 's3', 't5')
    a.ori('t6', 'zero', 0xFF); a.sb('t6', o('SLOTOF'), 't7')
    a.label('v2')
    a.sh('s0', o('GLYOF'), 't4')
    a.addu('t0', 's3', 's0'); a.sb('t1', o('SLOTOF'), 't0')
    a.ori('t3', 'zero', 1); a.addu('t0', 's3', 't1'); a.sb('t3', o('REF'), 't0')
    # staging buffer
    a.sw('t1', 0x60, 's3')                            # spare SAVE word: slot
    a.lw('t2', o('RING'), 's3'); a.ori('t3', 'zero', NB)
    a.bne('t2', 't3', 'nb'); a.nop()
    a.jal(DRAWSYNC); a.addu('a0', 'zero', 'zero')
    a.sw('zero', o('RING'), 's3')
    a.addu('t2', 'zero', 'zero')
    a.label('nb')
    a.addiu('t3', 't2', 1); a.sw('t3', o('RING'), 's3')
    a.sll('t3', 't2', 5); a.sll('t2', 't2', 3); a.addu('t2', 't2', 't3')   # *40
    a.addu('s2', 's3', 't2'); a.addiu('s2', 's2', o('BUF'))               # s2 = rect, s2+8 = pixels
    a.lw('t1', 0x60, 's3'); a.nop()
    a.addu('t0', 's3', 't1'); a.lbu('t1', o('SLOTS'), 't0'); a.nop()     # t1 = cell
    a.andi('t3', 't1', 15); a.sll('t3', 't3', 1); a.addiu('t3', 't3', SHEET_X); a.sh('t3', 0, 's2')
    a.srl('t3', 't1', 4); a.sll('t3', 't3', 3); a.addiu('t3', 't3', SHEET_Y); a.sh('t3', 2, 's2')
    a.ori('t3', 'zero', 2); a.sh('t3', 4, 's2'); a.ori('t3', 'zero', 8); a.sh('t3', 6, 's2')
    a.sw('t1', 0x64, 's3')                            # cell (returned)
    # expand glyph s0 -> 4bpp
    a.sll('t0', 's0', 3); a.subu('t0', 't0', 's0'); a.addu('t0', 't0', 's3'); a.addiu('t0', 't0', o('GLY'))
    a.addiu('t1', 's2', 8); a.ori('t2', 'zero', 8)
    a.label('cl')
    a.sw('zero', 0, 't1'); a.addiu('t2', 't2', -1)
    a.bgtz('t2', 'cl'); a.addiu('t1', 't1', 4)
    a.addiu('t1', 's2', 8); a.ori('t2', 'zero', 7)
    a.label('row')
    a.lbu('t3', 0, 't0'); a.addiu('t0', 't0', 1)
    a.addu('t4', 'zero', 'zero')                      # column
    a.addu('t6', 'zero', 'zero')                      # row word
    a.label('col')
    a.ori('t5', 'zero', 0x80); a.srlv('t5', 't5', 't4'); a.and_('t5', 't5', 't3')
    a.beq('t5', 'zero', 'c0'); a.sll('t7', 't4', 2)
    a.ori('t5', 'zero', INK); a.sllv('t5', 't5', 't7'); a.or_('t6', 't6', 't5')
    a.label('c0')
    a.addiu('t4', 't4', 1); a.sltiu('t5', 't4', 8)
    a.bne('t5', 'zero', 'col'); a.nop()
    a.sw('t6', 0, 't1'); a.addiu('t1', 't1', 4)
    a.addiu('t2', 't2', -1)
    a.bgtz('t2', 'row'); a.nop()
    a.addu('a0', 's2', 'zero')
    a.jal(LOADIMAGE); a.addiu('a1', 's2', 8)
    a.lw('v0', 0x64, 's3')
    a.b('ret2'); a.nop()
    a.label('hit')
    a.ori('t2', 'zero', 1); a.addu('t0', 's3', 't1'); a.sb('t2', o('REF'), 't0')
    a.lbu('v0', o('SLOTS'), 't0')
    a.b('ret2'); a.nop()
    a.label('ret')
    a.label('ret2')
    a.addu('v1', 's1', 'zero')
    a.addu('at', 's3', 'zero')
    for i, r in enumerate(SAVED):
        if r != 'at':
            a.lw(r, 4 * i, 'at')
    a.lw('at', 0, 'at')
    a.jr('ra'); a.nop()
    b = a.assemble()
    assert len(b) <= CODE_MAX, hex(len(b))
    return b, {k: a.labels[k] for k in ('G7A0', 'G7A3', 'G7S0', 'NAMEH', 'CORE')}


def _hi(v): return ((v + 0x8000) >> 16) & 0xFFFF
def _lo(v): return ((v & 0xFFFF) ^ 0x8000) - 0x8000


_E = None
def entries():
    """glue addresses (independent of n)."""
    global _E
    if _E is None:
        _E = code(400)[1]
    return _E


def blob():
    """-> (start va, bytes) to place in the font RAM image (names pool written by build)."""
    syls = syllables()
    n = len(syls)
    L = layout(n)
    c, e = code(n)
    assert e == entries()
    out = bytearray(L['END'] - G7_RAM)
    out[:len(c)] = c
    def put(k, b): o = L[k] - G7_RAM; out[o:o + len(b)] = b
    sl = _slots()
    put('SLOTS', bytes(sl))
    put('GLYOF', b'\xff' * (2 * SMAX))
    cv, fin = tables(syls)
    put('CVTAB', cv); put('FINTAB', fin)
    put('SYL', b''.join(struct.pack('<H', ord(ch) - 0xAC00) for ch in syls))
    put('SLOTOF', b'\xff' * n)
    put('GLY', b''.join(glyph(ch) for ch in syls))
    return G7_RAM, bytes(out), n


if __name__ == '__main__':
    s = syllables()
    L = layout(len(s))
    c, e = code(len(s))
    print(len(s), 'syllables, code', hex(len(c)), 'end', hex(L['END']), 'limit', hex(G7_END), 'slots', L['S'])
    print({k: hex(v) for k, v in e.items()})
