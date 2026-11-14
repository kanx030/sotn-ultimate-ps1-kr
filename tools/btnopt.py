"""Selectable menu button layout: pause menu > 설정 > 추가 설정 > new 5th row '버튼' = '○ 결정' / '× 결정'.

'○ 결정' (default, = the 11-15 release) is the player-contributed Circle-confirm / Cross-cancel layout that
oxswap.py writes into the files at build time. '× 결정' puts the original US bytes back at run time.

Storage: bit 0x80 of 0x80097BAF, Ultimate's Extra-settings byte (bits 0x01 Richter, 0x04 Maria, 0x40 balance,
0x28 dub; kept in the save with the rest of the player status). 0x80 is masked out by every reader of that byte
in all overlays (checked: andi / srl+andi users only). Bit clear = ○ 결정, so old saves and fresh games stay ○.

Runtime (code + tables at BTN_RAM, copied there from EXE BSS BTN_SRC by the boot stub, build.stub_code):
  * per frame: DRA ReadPads 'jal 800E67F4' (already pointed at the cheat blob when build.CHEATS) -> entry ->
    tail jump to the previous target. entry picks the wanted layout:
        g_GameState (0x8003C734) 1 (title) / 8 (file select, name entry): SHADOW (last in-game choice;
        0 = ○ after power-on: the blob is copied at boot only, a soft reset keeps it)
        any other state: bit 0x80 of the byte, and SHADOW = that bit
    then, per group (DRA, cheat blob, ARC_F2, SEL/SELRIC2, LIB), checks that EVERY site word is either the
    ○ or the × form (= that overlay is in RAM; a different overlay at the same address never matches all words),
    rewrites the words that differ and, if any changed, calls BIOS FlushCache (A0:44) for the I-cache.
    Overlays load with the ○ bytes from disc, so in ○ mode nothing is ever written (identical to the release).
  * × mode on the title/file-select screens (SEL group present, state 1/8): the two help-icon rects that
    oxswap redraws in F_SEL (VRAM 552,99 and 808,99, 4x9 hw: blocks 0x2000 / 0x22000 of F_SEL, loaded by DRA's
    tile loader table 0x800AC8EC at y 0) are LoadImage'd (0x80012B24) back to the original pixels every frame.
  * new game: SEL clears the byte at name entry (0x801B83A0) and rebuilds it from Ultimate's new-game options;
    SEL 0x801B5A34 'jal 801B54D0' (reached on every path after those writes) -> newgame: byte |= SHADOW, so a new
    game starts with the layout that was in use.
The title/file-select screens use SHADOW: there is no 버튼 row there, the layout follows the last game played
(○ after power-on). Loading a save switches to that save's choice once the game starts.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm import Asm, jal_word
import draa, oxswap

BTN_RAM = 0x8009E000          # free RAM between the EXE image end and DRA (songsub 0x80099000, cheats 0x8009C000)
BTN_SIZE = 0x800
BTN_SRC = 0x80048000          # EXE BSS copy source (after songsub.SONG_SRC + SONG_SIZE)
FLAG = 0x80097BAF
BIT = 0x80
GAMESTATE = 0x8003C734
LOADIMAGE = 0x80012B24
SEL_HOOK = 0x801B5A34         # SEL/SELRIC2: jal 801B54D0 after the new-game option writes
SEL_HOOK_T = 0x801B54D0
CODE_MAX = 0x200
D = BTN_RAM + CODE_MAX        # data
SHADOW, RECT1, RECT2, PIX1, PIX2, GROUPS = D, D + 0x08, D + 0x10, D + 0x18, D + 0x60, D + 0xB0
ENTRIES = D + 0x100

# where each oxswap file's sites live at run time: (load va - file offset), group flag (1 = SEL: icons)
CODE_FILES = {'DRA.BIN': (0x800A0000, 0), 'BIN/ARC_F2.BIN': (0x8013C000, 0), 'ST/SEL/SEL.BIN': (0x80180000, 1),
              'BIN/SELRIC2.BIN': (0x80180000, 1), 'ST/LIB/LIB.BIN': (0x80180000, 0)}
FSEL = 'ST/SEL/F_SEL.BIN'
FILES = tuple(CODE_FILES) + (FSEL,)
TILE_X = [0x200, 0x220, 0x200, 0x220, 0x240, 0x260, 0x240, 0x260, 0x280, 0x2A0, 0x280, 0x2A0,
          0x2C0, 0x2E0, 0x2C0, 0x2E0, 0x300, 0x320, 0x300, 0x320, 0x340, 0x360, 0x340, 0x360]   # DRA 0x800AC8EC

REC = {}                      # rel -> [(va, circle word, cross word)] / F_SEL -> [(rect, pixels)]
NEXT = None                   # previous target of the ReadPads call (set by hook_dra)
LOG = []

# ------------------------------------------------------------------ ARC_F2: the 5th row
ARC = 0x8013C000
LBL, ENT, VAL, LBLSTR = 0x8016F000, 0x8016F018, 0x8016F040, 0x8016F0A0   # ARC_F2 zero tail (BSS uses E510/E514)
ROW_LABEL = '버튼'
VALUES = ((0xE8, '결정'), (0xE9, '결정'))     # engine-A icon cells E8 = ○, E9 = × (sheet F_GAME 0x30000)

def _a(t): return draa.encode_a(t) + b'\xff\x00'

def _arc(d):
    o = lambda va: va - ARC
    def rep(va, old, new):
        assert struct.unpack_from('<I', d, o(va))[0] == old, (hex(va), d[o(va):o(va) + 4].hex())
        struct.pack_into('<I', d, o(va), new)
    assert not any(d[o(LBL):o(0x8016F100)])
    labels = list(struct.unpack_from('<4I', d, o(0x8016E498)))
    lb = _a(ROW_LABEL); d[o(LBLSTR):o(LBLSTR) + len(lb)] = lb
    struct.pack_into('<5I', d, o(LBL), *(labels + [LBLSTR]))
    d[o(ENT):o(ENT) + 32] = d[o(0x8016E4D8):o(0x8016E4F8)]
    d[o(ENT) + 32:o(ENT) + 40] = bytes([BIT, 2, 0x00, BIT, 0, 4, 5, 0])     # mask, count, values, -, string ids
    for i in range(4):                                                        # value strings: 8 -> 16-byte slots
        d[o(VAL) + 16 * i:o(VAL) + 16 * i + 8] = d[o(0x8016E478) + 8 * i:o(0x8016E478) + 8 * i + 8]
    for i, (icon, t) in enumerate(VALUES):
        v = bytes([icon, 0x00]) + _a(t); assert len(v) <= 16
        d[o(VAL) + 16 * (4 + i):o(VAL) + 16 * (4 + i) + len(v)] = v
    rep(0x8016DEF8, 0x34050004, 0x34050005)                   # submenu cursor: 4 -> 5 rows
    rep(0x8016DF10, 0x2484E4D8, 0x24840000 | (ENT & 0xFFFF))   # entry table (input)
    rep(0x8016E2AC, 0x2610E4D8, 0x26100000 | (ENT & 0xFFFF))   # entry table (draw)
    rep(0x8016E2B4, 0x2694E498, 0x26940000 | (LBL & 0xFFFF))   # label table
    rep(0x8016E30C, 0x2484E478, 0x24840000 | (VAL & 0xFFFF))   # value strings
    rep(0x8016E310, 0x000210C0, 0x00021100)                   # sll v0,v0,3 -> 4 (16-byte value slots)
    rep(0x8016E31C, 0x2A220004, 0x2A220005)                   # draw loop: 4 -> 5 rows
    rep(0x8016E40C, 0x3402007C, 0x3402006C)                   # window y 0x7C -> 0x6C (same bottom)
    rep(0x8016E424, 0x34020040, 0x34020050)                   # window h 0x40 -> 0x50
    for va in (0x8016DF10, 0x8016E2AC, 0x8016E2B4, 0x8016E30C):
        assert struct.unpack_from('<I', d, o(va) - 4)[0] >> 16 in (0x3C04, 0x3C10, 0x3C14)   # lui rX,0x8017
        assert struct.unpack_from('<I', d, o(va) - 4)[0] & 0xFFFF == 0x8017

def _sel(d):
    o = SEL_HOOK - 0x80180000
    assert bytes(d[o:o + 4]) == jal_word(SEL_HOOK_T), d[o:o + 4].hex()
    d[o:o + 4] = jal_word(labels()['newgame'])

# ------------------------------------------------------------------ build-time: static edits + site records
def patch(rel, data):
    """Call right before oxswap.patch (data = our built bytes with the original US button masks)."""
    if rel not in FILES:
        return data
    d = bytearray(data)
    if rel == FSEL:
        REC[rel] = _fsel_rects(d)
        return bytes(d)
    if rel == 'BIN/ARC_F2.BIN':
        _arc(d)
    if rel in ('ST/SEL/SEL.BIN', 'BIN/SELRIC2.BIN'):
        _sel(d)
    va0, _ = CODE_FILES[rel]
    REC[rel] = _sites(d, oxswap.FILES[rel], va0)
    LOG.append('btnopt %s: %d sites' % (rel, len(REC[rel])))
    return bytes(d)

def _sites(d, edits, va0, foff=0):
    words = {}
    for off, old, new in edits:
        assert d[off] == old, (hex(off), d[off], old)
        words.setdefault(off & ~3, []).append((off & 3, new))
    out = []
    for w, ch in sorted(words.items()):
        cross = bytes(d[w:w + 4]); circ = bytearray(cross)
        for k, new in ch: circ[k] = new
        out.append((va0 + w - foff, struct.unpack('<I', bytes(circ))[0], struct.unpack('<I', cross)[0]))
    return out

def _fsel_rects(d):
    edits = oxswap.FILES[FSEL]
    out = []
    for half in (0x00000, 0x20000):
        es = [e for e in edits if half <= e[0] < half + 0x20000]
        assert es
        blk = {(e[0] // 0x2000) for e in es}; assert len(blk) == 1, blk
        b = blk.pop(); bo = b * 0x2000
        rows = [(e[0] - bo) // 64 for e in es]; cols = [(e[0] - bo) % 64 for e in es]
        for off, old, _ in es: assert d[off] == old, hex(off)
        c0 = min(cols) // 4 * 4; c1 = (max(cols) // 4 + 1) * 4          # whole halfwords, even count
        r0, r1 = min(rows), max(rows) + 1
        px = b''.join(bytes(d[bo + r * 64 + c0:bo + r * 64 + c1]) for r in range(r0, r1))
        x = TILE_X[b] + c0 // 2; y = ((b & 2) << 6) + r0
        out.append((struct.pack('<4h', x, y, (c1 - c0) // 2, r1 - r0), px))
    assert [struct.unpack('<2h', r[:4]) for r, _ in out] == [(552, 99), (808, 99)], out
    return out

# ------------------------------------------------------------------ runtime blob
def labels():
    return _code(None, ())[1]

def hook_dra(dra, hook_va):
    """DRA: the ReadPads call -> entry (chains to whatever it called before: PADREP or the cheat blob)."""
    global NEXT
    o = hook_va - 0x800A0000
    w = struct.unpack_from('<I', dra, o)[0]; assert w >> 26 == 3, hex(w)
    NEXT = 0x80000000 | ((w & 0x3FFFFFF) << 2)
    dra[o:o + 4] = jal_word(BTN_RAM)

def _code(nxt, groups):
    a = Asm(BTN_RAM)
    a.label('entry')
    a.addiu('sp', 'sp', -48); a.sw('ra', 16, 'sp')
    a.sw('a0', 20, 'sp'); a.sw('a1', 24, 'sp'); a.sw('a2', 28, 'sp'); a.sw('a3', 32, 'sp')
    a.lui('t0', 0x8004); a.lw('t0', GAMESTATE - 0x80040000, 't0')
    a.li('t3', SHADOW)
    a.ori('t1', 'zero', 1); a.beq('t0', 't1', 'title'); a.ori('t1', 'zero', 8)
    a.beq('t0', 't1', 'title'); a.nop()
    a.lui('t1', FLAG >> 16); a.lbu('t2', FLAG & 0xFFFF, 't1'); a.nop()
    a.andi('t2', 't2', BIT); a.b('have'); a.sw('t2', 0, 't3')
    a.label('title')
    a.lw('t2', 0, 't3'); a.nop()
    a.label('have')                                   # t2 = wanted: 0 circle, BIT cross
    a.sw('t2', 36, 'sp'); a.sw('zero', 40, 'sp'); a.sw('zero', 44, 'sp')
    a.li('t4', GROUPS)
    a.label('gloop')
    a.lw('t5', 0, 't4'); a.lw('t6', 4, 't4'); a.nop()
    a.beq('t5', 'zero', 'gdone'); a.nop()
    a.addu('t7', 't6', 'zero'); a.addu('t8', 't5', 'zero')
    a.label('vloop')                                  # every word must be one of the two forms
    a.lw('t9', 0, 't7'); a.lw('a0', 4, 't7'); a.lw('a2', 8, 't7'); a.lw('a1', 0, 't9'); a.nop()
    a.beq('a1', 'a0', 'vok'); a.nop()
    a.bne('a1', 'a2', 'gnext'); a.nop()
    a.label('vok')
    a.addiu('t8', 't8', -1)
    a.bgtz('t8', 'vloop'); a.addiu('t7', 't7', 12)
    a.lw('a3', 8, 't4'); a.nop()
    a.beq('a3', 'zero', 'ap'); a.nop()
    a.sw('a3', 44, 'sp')                              # SEL present
    a.label('ap')
    a.addu('t7', 't6', 'zero'); a.addu('t8', 't5', 'zero')
    a.label('aloop')
    a.lw('t9', 0, 't7'); a.lw('a0', 4, 't7'); a.lw('a2', 8, 't7')
    a.beq('t2', 'zero', 'usec'); a.nop()
    a.addu('a0', 'a2', 'zero')
    a.label('usec')
    a.lw('a1', 0, 't9'); a.nop()
    a.beq('a1', 'a0', 'askip'); a.nop()
    a.sw('a0', 0, 't9')
    a.ori('a3', 'zero', 1); a.sw('a3', 40, 'sp')
    a.label('askip')
    a.addiu('t8', 't8', -1)
    a.bgtz('t8', 'aloop'); a.addiu('t7', 't7', 12)
    a.label('gnext')
    a.b('gloop'); a.addiu('t4', 't4', 12)
    a.label('gdone')
    a.lw('t0', 40, 'sp'); a.nop()
    a.beq('t0', 'zero', 'noflush'); a.nop()
    a.ori('t2', 'zero', 0xA0); a.jalr('t2'); a.ori('t1', 'zero', 0x44)    # BIOS FlushCache
    a.label('noflush')
    a.lw('t0', 36, 'sp'); a.lw('t1', 44, 'sp'); a.nop()
    a.beq('t0', 'zero', 'out'); a.nop()
    a.beq('t1', 'zero', 'out'); a.nop()
    a.lui('t0', 0x8004); a.lw('t0', GAMESTATE - 0x80040000, 't0'); a.ori('t1', 'zero', 1)
    a.beq('t0', 't1', 'icons'); a.ori('t1', 'zero', 8)
    a.bne('t0', 't1', 'out'); a.nop()
    a.label('icons')
    a.li('a0', RECT1); a.li('a1', PIX1); a.jal(LOADIMAGE); a.nop()
    a.li('a0', RECT2); a.li('a1', PIX2); a.jal(LOADIMAGE); a.nop()
    a.label('out')
    a.lw('ra', 16, 'sp'); a.lw('a0', 20, 'sp'); a.lw('a1', 24, 'sp'); a.lw('a2', 28, 'sp'); a.lw('a3', 32, 'sp')
    a.j(nxt or 0x80000000); a.addiu('sp', 'sp', 48)
    a.label('newgame')                                # SEL: after the new-game option writes
    a.li('t0', SHADOW); a.lw('t0', 0, 't0'); a.lui('t1', FLAG >> 16); a.lbu('t2', FLAG & 0xFFFF, 't1')
    a.andi('t0', 't0', BIT); a.or_('t2', 't2', 't0'); a.sb('t2', FLAG & 0xFFFF, 't1')
    a.j(SEL_HOOK_T); a.nop()
    code = a.assemble()
    assert len(code) <= CODE_MAX, hex(len(code))
    return code, a.labels

def blob(exe, exe_off, cheat_src, cheat_ram, cheat_size):
    """-> bytes for BTN_RAM. exe = the EXE being built (cheat blob already in place, before oxswap)."""
    assert NEXT is not None, 'hook_dra not called'
    need = list(CODE_FILES) + [FSEL]
    miss = [f for f in need if f not in REC]; assert not miss, ('btnopt: files not seen', miss)
    assert REC['ST/SEL/SEL.BIN'] == REC['BIN/SELRIC2.BIN']
    groups = []
    for rel in ('DRA.BIN', 'BIN/ARC_F2.BIN', 'ST/SEL/SEL.BIN', 'ST/LIB/LIB.BIN'):
        groups.append((REC[rel], CODE_FILES[rel][1]))
    ex = oxswap.FILES.get('SLUS_000.67')
    if ex:                                            # cheat window (bytes of the cheat blob in EXE BSS)
        lo = exe_off(cheat_src)
        assert all(lo <= o < lo + cheat_size for o, _, _ in ex)
        groups.append((_sites(exe, ex, cheat_ram, lo), 0))
    code, _ = _code(NEXT, groups)
    b = bytearray(BTN_SIZE); b[:len(code)] = code
    o = lambda va: va - BTN_RAM
    (r1, p1), (r2, p2) = REC[FSEL]
    assert len(p1) <= 0x48 and len(p2) <= 0x48
    b[o(RECT1):o(RECT1) + 8] = r1; b[o(RECT2):o(RECT2) + 8] = r2
    b[o(PIX1):o(PIX1) + len(p1)] = p1; b[o(PIX2):o(PIX2) + len(p2)] = p2
    e = ENTRIES; gt = bytearray()
    for sites, flag in groups:
        gt += struct.pack('<3I', len(sites), e, flag)
        for va, circ, cross in sites:
            assert circ != cross
            struct.pack_into('<3I', b, o(e), va, circ, cross); e += 12
    gt += bytes(12)
    assert GROUPS + len(gt) <= ENTRIES and e <= BTN_RAM + BTN_SIZE, hex(e)
    b[o(GROUPS):o(GROUPS) + len(gt)] = gt
    LOG.append('btnopt blob: %d groups, %d sites, %d bytes' % (len(groups), sum(len(s) for s, _ in groups), e - BTN_RAM))
    return bytes(b)
