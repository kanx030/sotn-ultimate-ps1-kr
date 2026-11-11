"""Long Library (ST/LIB/LIB.BIN): the Korean that does not fit in place.

    data = libfix.patch(path, data)     # only 'ST/LIB/LIB.BIN' changes; call it last for LIB
                                        # (after extraapply.apply, libnames.patch and banner.patch)

0. the PSP-dub copy of the librarian cutscene (0x801ADD38, English) is unreferenced once build.patch_cutscene
   points the PSP remap at the PS1 script: cleared and used as free space (the JP-dub script at 0x801ADEF8 is
   translated by LIB.jp.json).
0. the PSP-dub copy of the librarian cutscene (0x801ADD38, English) is unreferenced once build.patch_cutscene
   points the PSP remap at the PS1 script: cleared and used as free space (the JP-dub script at 0x801ADEF8 is
   translated by LIB.jp.json).
1. menu8 strings too long for their slot (tactics boss names, 3 sound-test titles): extragen marks them
   with 'want' (Korean) and extraapply leaves upper-case English in the slot. They are written into free
   space of LIB and their (single) pointer word is moved. Free space = the zero tails behind the Korean
   api descriptions / menu8 strings written in place, the slots of the moved strings and the 6 old
   main-menu strings (0x801AD3B8..0x801AD400). Every fragment is checked to have no data/code reference
   inside it.
2. raw-ASCII 8x8 routine 0x801B191C (main menu: table 0x80181310, ATT/DEF: table 0x80181528). It copies
   font cells VRAM->VRAM (MoveImage) into the menu texture at (x units, y), so it can not overlay the
   final + CV cells of a syllable. Replaced (same size) by a bitmap blit:
       a0 = record [w units (even)] [1bpp rows, w/2 bytes each, 10 rows], a1 = x, a2 = y
       -> expand to 4bpp (ink index 6, as the sheet) on the stack, LoadImage {a1, a2-2, w, 10},
          DrawSync(0) (the stack buffer must survive the transfer).
   The bitmaps are pre-rendered here from the Korean 8x8 sheet exactly as the shop drawer composes a
   syllable (CV cell 2 px above the final cell). Main-menu records are [col][w][bits] (the caller reads
   the column byte and passes ptr+1); ATT/DEF ('공격'/'방어') get a new 2-word table, the lui/addiu at
   0x801B5554 is repointed (the old table stays: fallback paths also read 'ATT' from it).
   Korean text comes from the sheet's ascii8 'ko' (extragen LIB_ASCII8); columns are re-centred on the
   84 px menu texture (US labels are centred at x 42).
Asserts the expected bytes (banner's shop drawer must already be in place). Running twice is a no-op.
"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm import Asm

LIB = 'ST/LIB/LIB.BIN'
B = 0x80180000
ROUT = 0x801B191C
ROUT_LEN = 42 * 4
ROUT_US = bytes.fromhex(
    'd8ffbd271c00b1af218880001800b0af2180a0002000b2af2190c0002400bfaf0000239200000000ff006430170080100100312620'
    '000234030082140f0062304fc6060801001026f0006330421803004010020080034224f00063241000a2a7020002341400a2a70800'
    '02341000a427ffff0532ffff46321200a3a7fb4a000c1600a2a74fc60608020010262400bf8f2000b28f1c00b18f1800b08f2800bd'
    '270800e00300000000')
LOADIMAGE = 0x80012B24
DRAWSYNC = 0x8001290C
H = 10                                   # bitmap rows: CV cell at y-2 .. final cell bottom at y+7
INK = 6                                  # the 8x8 sheet's only ink index
MENU_TAB = 0x1310                        # 6 pointers -> [col] ASCII 00
MENU_US = [0x2d3f0, 0x2d3e4, 0x2d3d8, 0x2d3cc, 0x2d3c4, 0x2d3b8]
MENU_SLOTS = (0x2d3b8, 0x2d400)          # the 6 strings + padding (0x2d400 is the next table)
MENU_CENTRE = 42                         # px, texture is 84 px wide (prim u 0..0x54)
AD_TAB = 0x1528                          # ATT, DEF (still read by fallback paths: left alone)
AD_US = [0x2d4f0, 0x2d4ec]
AD_CODE = 0x801B5554 - B                 # lui s0,0x8018; addiu s0,s0,0x1528 (loop drawing ATT/DEF)
AD_CODE_US = bytes.fromhex('1880103c28151026')
DESC_RANGE = (0x2bb94, 0x2d370)          # enemy descriptions (api; 0x801AD370 is a code-referenced table)
SHOPD_RANGE = (0x2d560, 0x2d660)         # shop item descriptions (api)
PS1_SCRIPT = 0x3f68                      # LIB cutscene script (translated by transapply)
PSP_REMAP = 0x2def0                      # remap table (from, to) for the PSP dub
PSP_SCRIPT = (0x2dd38, 0x2def0)          # PSP-dub script (English), unreferenced once remapped
LOG = []


def _base(path):
    return path.replace('\\', '/').split(';')[0].lstrip('/').upper()


def _sheet_items():
    import extraapply
    return json.load(open(extraapply.sheet_path(LIB), encoding='utf-8'))['items']


# ------------------------------------------------------------------ references
def _refs(d):
    """target file offset -> [('w', loc)] data words / [('c', loc)] lui + addiu/ori/load/store pairs."""
    n = len(d) // 4
    W = struct.unpack_from('<%dI' % n, d)
    out = {}
    for i, w in enumerate(W):
        if B <= w < B + len(d):
            out.setdefault(w - B, []).append(('w', i * 4))
    for i, w in enumerate(W):
        if w >> 26 != 15:
            continue
        rt, hi = (w >> 16) & 31, w & 0xFFFF
        for j in range(i + 1, min(i + 12, n)):
            v = W[j]; op = v >> 26
            if op in (9, 13, 32, 33, 35, 36, 37, 40, 41, 43) and (v >> 21) & 31 == rt:
                lo = v & 0xFFFF
                if op != 13 and lo & 0x8000:
                    lo -= 0x10000
                a = (hi << 16) + lo - B
                if 0 <= a < len(d):
                    out.setdefault(a, []).append(('c', j * 4))
            if (v >> 16) & 31 == rt and op in (9, 13, 15, 32, 33, 35, 36, 37):
                break
    return out


def _refs_in(refs, a, b):
    return [(o, r) for o, rs in refs.items() if a <= o < b for r in rs]


# ------------------------------------------------------------------ bitmaps
def _cells():
    import draa, gfx
    sheet = gfx.blk_get(draa._rd(draa.K_FGAME), 0x30000)
    return lambda c: sheet[(c >> 4) * 8:(c >> 4) * 8 + 8, (c & 15) * 8:(c & 15) * 8 + 8]


def render(ko, cell=None):
    """Korean text -> (10-row ink mask, width px), composed like the shop drawer 0x801B19C4."""
    import numpy as np, draa
    cell = cell or _cells()
    b = draa.encode_a(ko)
    img = np.zeros((H, 8 * len(b) + 8), bool)
    x = gx = 0
    i = 0
    def put(c, px, row):
        cc = cell(c)
        assert set(np.unique(cc)) <= {0, INK}, (ko, hex(c))
        img[row:row + 8, px:px + 8] |= cc != 0
    import g7
    while i < len(b):
        c = b[i]; i += 1
        if c != 0xFF and i + 1 < len(b) and b[i] == 0xFF and b[i + 1] in draa.CV:   # whole Galmuri7 syllable
            cv, fin = draa.CV[b[i + 1]], draa.FIN.get(c, draa._FIN_ALT.get(c, ''))
            o = ord(cv) - 0xAC00 + (draa.JONG.index(fin) + 1 if fin else 0)
            rows = g7.glyph(chr(0xAC00 + o))
            for r, v in enumerate(rows):
                for k in range(8):
                    if v & (0x80 >> k):
                        img[2 + r, x + k] = True
            i += 2
            gx = x; x += 8
        elif c == 0xFF:
            put(b[i], gx, 0); i += 1
            x = gx + 8
        elif c == 0:
            gx = x; x += 4
        else:
            gx = x; put(c, x, 2); x += 8
    return img[:, :x], x


def bitmap(ko, cell=None):
    """-> (w units, even), 1bpp bytes (row-major, bit k = pixel k of the byte's 8)."""
    img, px = render(ko, cell)
    w = -(-px // 4)
    w += w & 1
    assert w <= 14, (ko, px)                 # stack buffer of the blit routine
    out = bytearray()
    for r in range(H):
        for j in range(w // 2):
            v = 0
            for k in range(8):
                x = j * 8 + k
                if x < px and img[r, x]:
                    v |= 1 << k
            out.append(v)
    return w, bytes(out), px


def _rout_code():
    a = Asm(ROUT)
    F = 320
    a.addiu('sp', 'sp', -F)
    a.sw('ra', F - 8, 'sp')
    a.lbu('t0', 0, 'a0')                 # w (units)
    a.sh('a1', 16, 'sp')                 # RECT x
    a.addiu('a2', 'a2', -2)
    a.sh('a2', 18, 'sp')                 # y - 2
    a.sh('t0', 20, 'sp')
    a.ori('v0', 'zero', H)
    a.sh('v0', 22, 'sp')
    a.sll('t3', 't0', 2)
    a.addu('t3', 't3', 't0')             # 5w source bytes (one per 8 px)
    a.addiu('t1', 'a0', 1)
    a.addiu('t2', 'sp', 24)              # 4bpp buffer (<= 14 units * 2 * 10 = 280 bytes)
    a.label('L')
    a.lbu('v0', 0, 't1')
    a.addiu('t1', 't1', 1)
    a.addu('v1', 'zero', 'zero')
    a.ori('t5', 'zero', INK)
    a.label('B')
    a.beq('v0', 'zero', 'S')
    a.andi('t6', 'v0', 1)
    a.beq('t6', 'zero', 'N')
    a.srl('v0', 'v0', 1)
    a.or_('v1', 'v1', 't5')
    a.label('N')
    a.b('B')
    a.sll('t5', 't5', 4)
    a.label('S')
    a.sw('v1', 0, 't2')
    a.addiu('t3', 't3', -1)
    a.bne('t3', 'zero', 'L')
    a.addiu('t2', 't2', 4)
    a.addiu('a0', 'sp', 16)
    a.jal(LOADIMAGE)
    a.addiu('a1', 'sp', 24)
    a.jal(DRAWSYNC)
    a.addu('a0', 'zero', 'zero')
    a.lw('ra', F - 8, 'sp')
    a.nop()                              # load delay: jr would use the stale ra (DrawSync's return) -> stack walk/RAM wipe
    a.jr('ra')
    a.addiu('sp', 'sp', F)
    code = a.assemble()
    assert len(code) <= ROUT_LEN, len(code)
    return code + bytes(ROUT_LEN - len(code))


# ------------------------------------------------------------------ free space
class Pool:
    def __init__(self):
        self.free = []                   # [a, b)

    def add(self, a, b):
        if b > a:
            self.free.append([a, b])

    def merge(self):
        m = []
        for a, b in sorted(self.free):
            if m and a <= m[-1][1]:
                m[-1][1] = max(m[-1][1], b)
            else:
                m.append([a, b])
        self.free = m

    def alloc(self, n, align=1):
        best = None
        for f in self.free:
            s = (f[0] + align - 1) // align * align
            if s + n <= f[1] and (best is None or f[1] - f[0] < best[1] - best[0]):
                best = f
        assert best, ('LIB free space exhausted', n)
        s = (best[0] + align - 1) // align * align
        if s > best[0]:
            self.free.append([best[0], s])
        best[0] = s + n
        return s

    def total(self):
        return sum(b - a for a, b in self.free)


def patch(path, data):
    if _base(path) != LIB:
        return data
    import extraapply, banner
    d = bytearray(data)
    r = ROUT - B
    if bytes(d[r:r + ROUT_LEN]) == _rout_code():
        return bytes(data)                                   # already applied
    assert bytes(d[r:r + ROUT_LEN]) == ROUT_US, 'LIB 0x801B191C changed'
    so = banner.SHOP - B
    assert bytes(d[so:so + banner.SHOP_LEN]) == banner._shop_code(), 'banner.patch (LIB shop drawer) must run first'
    refs = _refs(d)
    items = _sheet_items()
    pool = Pool()

    def check_free(a, b, allow=()):
        bad = [(hex(o), k, hex(l)) for o, (k, l) in _refs_in(refs, a, b) if (o, l) not in allow]
        assert not bad, ('LIB free fragment referenced', hex(a), hex(b), bad)
        pool.add(a, b)

    # enemy descriptions (api, in place by extraapply): repacked 4-aligned in their own order so that the
    # space the shorter Korean leaves becomes one block at the end; every pointer (data word or lui/addiu
    # pair) to a description start is moved
    descs = [it for it in items if it['path'] == 'api' and DESC_RANGE[0] <= it['off'] < DESC_RANGE[1]]
    descs.sort(key=lambda it: it['off'])
    allow = {(it['off'], l) for it in descs for _, l in refs.get(it['off'], [])}
    bad = [(hex(o), k, hex(l)) for o, (k, l) in _refs_in(refs, *DESC_RANGE) if (o, l) not in allow]
    assert not bad, ('LIB description area referenced inside a string', bad)
    packed, moved = bytearray(), []
    for it in descs:
        o, cap = it['off'], it['cap']
        enc = extraapply.encode(it)
        assert bytes(d[o:o + cap]) == enc + bytes(cap - len(enc)), ('api not as extraapply wrote it', hex(o))
        assert d[o + cap] == 0 and refs.get(o), hex(o)
        moved.append((o, DESC_RANGE[0] + len(packed)))
        packed += enc + b'\0'
        packed += bytes(-len(packed) % 4)
    assert DESC_RANGE[0] + len(packed) <= DESC_RANGE[1]
    d[DESC_RANGE[0]:DESC_RANGE[1]] = packed + bytes(DESC_RANGE[1] - DESC_RANGE[0] - len(packed))
    for o, n in moved:
        for k, l in refs[o]:
            if k == 'w':
                assert struct.unpack_from('<I', d, l)[0] == B + o
                struct.pack_into('<I', d, l, B + n)
            else:
                w = struct.unpack_from('<I', d, l)[0]
                assert w >> 26 == 9 and ((w & 0xFFFF) ^ 0x8000) - 0x8000 == ((B + o) & 0xFFFF ^ 0x8000) - 0x8000
                rt = (w >> 21) & 31
                lui = [x for x in range(l - 4, l - 48, -4)
                       if struct.unpack_from('<I', d, x)[0] >> 16 == (0x3C00 | rt)][0]
                assert struct.unpack_from('<I', d, lui)[0] & 0xFFFF == (B + n + 0x8000) >> 16 == (B + o + 0x8000) >> 16
                struct.pack_into('<I', d, l, (w & 0xFFFF0000) | ((B + n) & 0xFFFF))
    pool.add(DESC_RANGE[0] + len(packed), DESC_RANGE[1])
    # shop descriptions (api): zero tails behind the Korean
    for it in items:
        if it['path'] == 'api' and SHOPD_RANGE[0] <= it['off'] < SHOPD_RANGE[1] and it.get('ko'):
            o, cap = it['off'], it['cap']
            enc = extraapply.encode(it)
            assert bytes(d[o:o + cap]) == enc + bytes(cap - len(enc)), ('api not as extraapply wrote it', hex(o))
            assert d[o + cap] == 0, hex(o)
            check_free(o + len(enc) + 1, o + cap)
    # menu8: tails of the in-place ones, whole slot of the ones to move
    moves = []
    for it in items:
        if it['path'] != 'menu8' or it.get('noterm'):
            continue
        o, cap = it['off'], it['cap']
        enc = extraapply.encode(it)
        assert bytes(d[o:o + cap]) == enc + bytes(cap - len(enc)), ('menu8 not as extraapply wrote it', hex(o))
        if 'want' in it:
            rs = refs.get(o, [])
            assert len(rs) == 1 and rs[0][0] == 'w', ('menu8 to move must have one pointer word', hex(o), rs)
            loc = rs[0][1]
            assert struct.unpack_from('<I', d, loc)[0] == B + o
            new = extraapply.enc_menu8(it['want'])
            moves.append((o, cap, loc, new, it['want']))
            check_free(o, o + cap, allow={(o, loc)})
        else:
            check_free(o + len(enc), o + cap)
    # main menu strings (only the table points there)
    tab = list(struct.unpack_from('<6I', d, MENU_TAB))
    assert tab == [B + o for o in MENU_US], ('LIB main menu table changed', [hex(t) for t in tab])
    ascii8 = {it['off']: it for it in items if it['path'] == 'ascii8'}
    for o in MENU_US + AD_US:
        it = ascii8[o + 1 if o in MENU_US else o]
        e = extraapply.encode(it)
        assert bytes(d[it['off']:it['off'] + it['cap']]) == e, ('ascii8 not as extraapply wrote it', hex(o))
    check_free(*MENU_SLOTS, allow={(o, MENU_TAB + 4 * i) for i, o in enumerate(MENU_US)})
    assert struct.unpack_from('<2I', d, AD_TAB) == tuple(B + o for o in AD_US), 'LIB ATT/DEF table changed'
    assert bytes(d[AD_CODE:AD_CODE + 8]) == AD_CODE_US, 'LIB ATT/DEF loop changed'
    # PSP-dub script: free space only while the PSP remap points at the PS1 script (old builds, PSP_TO_PS1=1).
    # Since 11-11 the PSP dub has its own Korean script (LIB.psp.json), so it stays in use.
    a, b = PSP_SCRIPT
    if struct.unpack_from('<2I', d, PSP_REMAP) == (B + PS1_SCRIPT, B + PS1_SCRIPT):
        check_free(a, b)

    # zero what is now free, then allocate (bitmaps first, then strings, largest first)
    pool.merge()
    for a, b in pool.free:
        d[a:b] = bytes(b - a)
    cell = _cells()
    recs = []
    for i, o in enumerate(MENU_US):
        ko = ascii8[o + 1]['ko']
        w, bits, px = bitmap(ko, cell)
        col = max(0, int((MENU_CENTRE - px / 2) / 4 + 0.5))
        recs.append(('menu', i, bytes([col, w]) + bits, ko))
    for i, o in enumerate(AD_US):
        ko = ascii8[o]['ko']
        w, bits, px = bitmap(ko, cell)
        recs.append(('ad', i, bytes([w]) + bits, ko))
    total0 = pool.total()
    ad_tab = pool.alloc(8, 4)
    ad_ptr = [0, 0]
    for kind, i, rec, ko in sorted(recs, key=lambda r: -len(r[2])):
        a = pool.alloc(len(rec))
        d[a:a + len(rec)] = rec
        if kind == 'menu':
            struct.pack_into('<I', d, MENU_TAB + 4 * i, B + a)
        else:
            ad_ptr[i] = B + a
    struct.pack_into('<2I', d, ad_tab, *ad_ptr)
    va = B + ad_tab
    hi, lo = (va + 0x8000) >> 16, va & 0xFFFF
    struct.pack_into('<II', d, AD_CODE, 0x3C100000 | hi, 0x26100000 | lo)
    for o, cap, loc, new, ko in sorted(moves, key=lambda m: -len(m[3])):
        a = pool.alloc(len(new))
        d[a:a + len(new)] = new
        struct.pack_into('<I', d, loc, B + a)
    d[r:r + ROUT_LEN] = _rout_code()
    LOG.append((LIB, 'main menu/ATT-DEF bitmaps: %s; moved %d menu8 strings; free %d -> %d bytes'
                % (' / '.join(k for _, _, _, k in recs), len(moves), total0, pool.total())))
    return bytes(d)


# ------------------------------------------------------------------ test / preview
def pipeline_lib():
    """LIB as build.main writes it (cutscene, transapply, names, extraapply, libnames, banner), then libfix."""
    import build, transapply, extraapply, libnames, banner
    f = LIB
    fid = build.CUTSCENE_FILES.index(f)
    d = build.patch_cutscene(build.read(os.path.join(build.U, *f.split('/'))), fid, f)
    if f not in build.CUTSCENE_SKIPPED:
        d, _ = transapply.apply(f, d)
    d, _ = build.patch_names(d, fid)
    d, _ = extraapply.apply(f, d, skip_cutscene=f in build.CUTSCENE_SKIPPED)
    d = libnames.patch(f, d)
    d = banner.patch(f, d)
    return d, patch(f, d)


def _decode_record(d, p, menu):
    import numpy as np
    o = p - B + (1 if menu else 0)
    w = d[o]
    bits = d[o + 1:o + 1 + 5 * w]
    img = np.zeros((H, 4 * w), np.uint8)
    for r in range(H):
        for j in range(w // 2):
            v = bits[r * (w // 2) + j]
            for k in range(8):
                if v >> k & 1:
                    img[r, j * 8 + k] = 255
    return (d[o - 1] if menu else 0x1A), img


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import draa, numpy as np
    before, after = pipeline_lib()
    assert patch(LIB, after) == after
    # string moves: every pointer that changed must still decode to the wanted Korean
    for it in _sheet_items():
        if 'want' in it:
            loc = [l for k, l in _refs(before)[it['off']] if k == 'w'][0]
            p = struct.unpack_from('<I', after, loc)[0] - B
            e = after.index(b'\xff\x00', p)
            assert draa.decode_a(after[p:e]) == it['want'], (hex(it['off']), draa.decode_a(after[p:e]))
            print('%05x -> %05x  %s' % (it['off'], p, it['want']))
    # bitmap preview
    from PIL import Image
    rows = []
    for i in range(6):
        col, img = _decode_record(after, struct.unpack_from('<I', after, MENU_TAB + 4 * i)[0], True)
        canvas = np.zeros((H + 2, 84), np.uint8)
        canvas[1:1 + H, col * 4:col * 4 + img.shape[1]] = img[:, :84 - col * 4]
        rows.append(canvas)
    va = (struct.unpack_from('<I', after, AD_CODE)[0] & 0xFFFF) << 16
    va += struct.unpack_from('<h', after, AD_CODE + 4)[0]
    for i in range(2):
        _, img = _decode_record(after, struct.unpack_from('<I', after, va - B + 4 * i)[0], False)
        canvas = np.zeros((H + 2, 84), np.uint8)
        canvas[1:1 + H, :img.shape[1]] = img
        rows.append(canvas)
    import gfx
    os.makedirs(gfx.PREVIEW, exist_ok=True)
    out = os.path.join(gfx.PREVIEW, 'lib_menu_bitmaps.png')
    Image.fromarray(np.vstack(rows)).resize((84 * 4, len(rows) * (H + 2) * 4), Image.NEAREST).save(out)
    print('preview', out)
    diff = sum(1 for i in range(len(before)) if before[i] != after[i])
    print(diff, 'bytes changed')
    for l in LOG:
        print(*l)
