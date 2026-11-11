"""Leftover English fixes (2026-11-11). Called from build.write_file for every file in FILES.
Every edit asserts the US bytes first and is skipped when already applied (idempotent).

- DRA spell list (Special moves): combo tail "□or○" — MenuDrawChar 0x800F4434 draws 'o' (0x4F) and 'r' (0x52)
  one by one at 0x800F59FC..0x800F5A2C. Rewritten as one MenuDrawStr (0x800F4494, g7 CORE) call of "또는"
  (2 Galmuri7 syllables = the same 16 px); the encoded string lives inside the freed instructions.
- SEL / SELRIC2 file-box tags "Maria" "Richter" "Clear" "Replay" (SEL 0x27EC0.., drawn by 0x801BB504 ->
  glyph API, 2-byte K codes allowed): 마리아 / 리히터 / 클리어 / 리플레이. 'Clear' and 'Replay' share their
  16 bytes so 리플레이 fits; the Replay pointer (addiu at 0x801B2F5C) moves to the new start.
- BIN/F_GO.BIN game-over picture: the quote "Let us go out this evening for pleasure. / The night is still
  young." is painted into the 256x256 8bpp background (file 0x8000-0x17FFF, CLUT at 0x1A000). The English
  ink (+3 px halo) is inpainted from the surrounding sand (diffusion + seeded noise, quantised to the CLUT),
  then GO_TEXT is drawn in Galmuri11 (cream fill, 1 px dark outline), centred on the same two rows.
  The blackletter GAME OVER sprites (file 0x0000-0x3FFF) are redrawn as GO_TITLE (see gameover_title).
- DRA status screen name (g_MenuStr[0] "ALUCARD" / [42] "ALUCART" when the Alucart set is worn), drawn by
  MenuDrawStr(str, 0x80, 0x28) at 0x800F521C: 알카드 / 알카트 in Galmuri11 (11 px, as large as the English
  word looks) instead of 7 px Galmuri7. The word is cut into 8x7 tiles; each tile is a g7 "carrier"
  syllable (a Hangul syllable no text uses, given an EXT_CV code and a custom g7 glyph), so the normal 8x8
  path draws it. A thunk (in DRA_A's leftover free pool) draws the top tile row at y-2 and the bottom row
  7 px lower; v0 at the call is the game's "Alucart set worn" flag. DRA_A keeps 알카드/알카트 as fallback.
"""
import struct

FILES = ('DRA.BIN', 'ST/SEL/SEL.BIN', 'BIN/SELRIC2.BIN', 'BIN/F_GO.BIN')
LOG = []

DRA = 0x800A0000
SPELL_OR = 0x800F59FC              # 13 words: o / r MenuDrawChar calls
MENU_DRAW_STR = 0x800F4494


def _w(*ws):
    return b''.join(struct.pack('<I', w) for w in ws)


def _spell_or(d):
    import draa
    from asm import jal_word
    o = SPELL_OR - DRA
    us = bytes.fromhex('4f000434c02810002128a502213040020dd1030c213860020100102652000434'
                       'c02810002128a502213040020dd1030c21386002')
    s = draa.encode_a('또는') + b'\xff\x00'
    assert len(s) <= 16, s.hex()
    s = s + bytes(16 - len(s))
    stra = SPELL_OR + 0x24
    new = (_w(0x3C040000 | (stra >> 16),                       # lui a0,hi
              0x24840000 | (stra & 0xFFFF),                    # addiu a0,a0,lo (lo < 0x8000)
              0x001028C0, 0x02A52821, 0x02403021)              # sll a1,s0,3 ; addu a1,s5,a1 ; addu a2,s2,zero
           + jal_word(MENU_DRAW_STR) + _w(0x02603821)          # jal MenuDrawStr ; addu a3,s3,zero
           + _w(0x08000000 | ((SPELL_OR + 0x34) >> 2 & 0x3FFFFFF),   # j past the string
                0x26100001)                                    # addiu s0,s0,1 (delay slot)
           + s)
    assert stra & 0x8000 == 0 and len(new) == len(us) == 0x34
    cur = bytes(d[o:o + len(us)])
    if cur == new:
        return 'spell 또는: already'
    assert cur == us, cur.hex()
    d[o:o + len(us)] = new
    return 'spell □또는○'


def _sel_tags(d, name):
    from st0text import enc
    T = 0x27EC0
    us = b'Maria\0\0\0Richter\0Clear\0\0\0Replay\0\0'
    new = bytearray(32)
    m, r, c, rp = enc('마리아'), enc('리히터'), enc('클리어'), enc('리플레이')
    new[0:len(m)] = m; new[8:8 + len(r)] = r
    new[16:16 + len(c)] = c
    rp_off = 16 + len(c) + 1
    new[rp_off:rp_off + len(rp)] = rp
    assert rp_off + len(rp) < 32 and len(m) < 8 and len(r) < 8
    ins = 0x32F5C                                   # addiu a0,a0,0x7ED8 (Replay)
    ins_us = struct.pack('<I', 0x24847ED8)
    ins_new = struct.pack('<I', 0x24840000 | (0x7EC0 + rp_off))
    cur = bytes(d[T:T + 32])
    if cur == bytes(new) and d[ins:ins + 4] == ins_new:
        return name + ' tags: already'
    assert cur == us and d[ins:ins + 4] == ins_us, (name, cur)
    d[T:T + 32] = new
    d[ins:ins + 4] = ins_new
    return name + ' tags 마리아/리히터/클리어/리플레이'


GO_TEXT = ('오늘 저녁은 즐기러 나가 보자꾸나.', '밤은 아직 길다.')
GO_BG, GO_CLUT = 0x8000, 0x1A000
GO_BOX = (192, 220, 34, 220)          # rows / cols holding the English quote (+ halo)


def _inpaint(img, rgb, box, hi=420, lo=60, grow=3, seed=1):
    import numpy as np, gfx
    Y0, Y1, X0, X1 = box
    L = rgb[img].sum(2)
    m = np.zeros(img.shape, np.uint8)
    sub = L[Y0:Y1, X0:X1]
    m[Y0:Y1, X0:X1] = (sub >= hi) | (sub < lo)          # cream ink / dark outline
    for _ in range(grow):
        m = gfx.dilate(m)
    m = m.astype(bool)
    m[:Y0] = False; m[Y1:] = False; m[:, :X0] = False; m[:, X1:] = False
    acc = rgb[img].astype(float); acc[m] = 0
    w = (~m).astype(float)
    for _ in range(300):
        s = np.zeros_like(acc); n = np.zeros_like(w)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s += np.roll(np.roll(acc * w[..., None], dy, 0), dx, 1); n += np.roll(np.roll(w, dy, 0), dx, 1)
        upd = m & (n > 0)
        acc[upd] = s[upd] / n[upd][:, None]
        w = np.where(m, (n > 0) * 1.0, 1.0)
    acc[m] += np.random.default_rng(seed).normal(0, 7, (int(m.sum()), 1))
    pal = rgb[1:].astype(float)
    idx = ((acc[m][:, None, :] - pal[None]) ** 2).sum(2).argmin(1) + 1
    out = img.copy(); out[m] = idx
    return out


def gameover_image(us):
    import numpy as np, gfx
    img = np.frombuffer(bytes(us[GO_BG:GO_BG + 0x10000]), np.uint8).reshape(256, 256).copy()
    c = np.frombuffer(bytes(us[GO_CLUT:GO_CLUT + 0x200]), np.uint16)
    rgb = np.dstack([(c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3]).reshape(256, 3).astype(int)
    img = _inpaint(img, rgb, GO_BOX)
    near = lambda col: int(((rgb[1:] - np.array(col)) ** 2).sum(1).argmin()) + 1
    FILL, OUT = near((248, 240, 224)), near((8, 8, 8))
    y = 194
    for line in GO_TEXT:
        m = gfx.galmuri(line, 11, space_w=4)
        H, W = m.shape
        x = 128 - W // 2
        assert 1 <= x and x + W < 255
        big = np.zeros((H + 2, W + 2), np.uint8); big[1:-1, 1:-1] = m
        reg = img[y - 1:y + H + 1, x - 1:x + W + 1]
        reg[gfx.dilate(big).astype(bool)] = OUT
        reg[big.astype(bool)] = FILL
        y += H + 2
    return img.tobytes(), rgb


GO_TITLE = '다시 관 속으로'           # replaces the blackletter GAME OVER (8 sprites of 32x32, 4bpp, side by side)
GO_TITLE_H = 24                        # glyph body height; rings add 5 px on each side (32 px row)
GO_TITLE_WEIGHT = 500
GO_TITLE_STRETCH = 1.15


def gameover_title():
    """F_GO 0x0000-0x3FFF: 256x128 4bpp, 8 letter cells x 4 rows. The 8 sprites sit side by side, 32 px
    apart, and stay still, so the row is one 256x32 canvas: the text is drawn across all 8 cells. The 4 rows
    are glow steps. Original encoding: D = 1 on the letter body, 2..6 on 1-px rings outward; row k shows
    D + (3 - k), cut off above 6."""
    import numpy as np, gfx
    from PIL import Image
    h = GO_TITLE_H
    def syl(ch):
        c = gfx.noto(ch, 40, GO_TITLE_WEIGHT, serif=True)
        return c, int(c.shape[1] * h / c.shape[0] * GO_TITLE_STRETCH)
    parts = [None if ch == ' ' else syl(ch) for ch in GO_TITLE]
    gap, sp = 6, 8
    tot = sum(sp if p is None else p[1] for p in parts) + gap * (len(parts) - 1)
    assert tot <= 256 - 12, tot
    cur = np.zeros((32, 256), bool); x = (256 - tot) // 2; y = (32 - h) // 2
    for p in parts:
        if p is None: x += sp + gap; continue
        c, w = p
        cur[y:y + h, x:x + w] = np.asarray(Image.fromarray((c * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)) > 110
        x += w + gap
    D = np.zeros((32, 256), np.uint8); D[cur] = 1
    for v in range(2, 7):
        n = gfx.dilate(cur); D[n & ~cur] = v; cur = n
    sheet = np.zeros((128, 256), np.uint8)
    for k in range(4):
        val = D.astype(int) + (3 - k); val[(D == 0) | (val > 6)] = 0
        sheet[k * 32:(k + 1) * 32] = val
    return bytes((sheet[:, 0::2] | (sheet[:, 1::2] << 4)).astype(np.uint8).ravel())


def _gameover(d):
    import hashlib, os
    us = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'U', 'BIN', 'F_GO.BIN'), 'rb').read()
    new, _ = gameover_image(us)
    title = gameover_title()
    out = []
    cur = bytes(d[GO_BG:GO_BG + 0x10000])
    if cur == new:
        out.append('quote: already')
    else:
        assert cur == us[GO_BG:GO_BG + 0x10000], 'F_GO background is not US'
        d[GO_BG:GO_BG + 0x10000] = new
        out.append('quote -> ' + ' / '.join(GO_TEXT))
    cur = bytes(d[0:0x4000])
    if cur == title:
        out.append('title: already')
    else:
        assert cur == us[0:0x4000], 'F_GO title letters are not US'
        d[0:0x4000] = title
        out.append('title -> ' + GO_TITLE)
    return 'F_GO ' + ', '.join(out)


NAME_CALL = 0x800F521C                 # jal MenuDrawStr (status name)
NAME_X, NAME_Y, NAME_W_US = 0x80, 0x28, 56
CARRIERS = '꺠꼐떄뗴뛔뺴뼤쀄쨰쪠쮀뙈컈턔퍠뽸'
CARRIER_CV = list(range(0xE3, 0xEC)) + list(range(0xF0, 0xFC))
_NAME = None


def _tiles(word):
    import gfx, numpy as np
    m = gfx.galmuri(word, 11, spacing=1)
    H, W = m.shape
    pad = np.zeros((14, (W + 7) // 8 * 8), np.uint8)
    pad[0:H, 0:W] = m
    rows = []
    for r0 in (0, 7):
        rows.append([bytes(int(''.join(str(b) for b in pad[r0 + y, c:c + 8]), 2) for y in range(7))
                     for c in range(0, pad.shape[1], 8)])
    return rows, W


def name_setup():
    """Registers the carrier glyphs (call before any engine-A encoding of them). -> {word: (top, bot, W)}"""
    global _NAME
    if _NAME is None:
        import draa, g7
        tiles = {}
        out = {}
        for word in ('알카드', '알카트'):
            rows, W = _tiles(word)
            enc = []
            for row in rows:
                b = bytearray()
                for t in row:
                    if t not in tiles:
                        k = len(tiles)
                        ch, cv = CARRIERS[k], CARRIER_CV[k]
                        assert cv not in draa.CV and cv not in draa.EXT_CV and ch not in draa._CV_ENC
                        draa.EXT_CV[cv] = ch; draa._CV_ENC[ch] = cv
                        g7.CUSTOM[ch] = t
                        tiles[t] = ch
                    b += draa.encode_a(tiles[t])
                enc.append(bytes(b) + b'\xff\x00')
            out[word] = (enc[0], enc[1], W)
        _NAME = out
    return _NAME


def _status_name(d):
    import draa
    from asm import Asm, jal_word
    names = name_setup()                   # registers the carrier glyphs in any case
    cur = bytes(d[NAME_CALL - DRA:NAME_CALL - DRA + 4])
    if cur != jal_word(0x800F4494):
        return 'status name: already'
    blob = b''
    offs = {}
    for word in ('알카드', '알카트'):
        top, bot, W = names[word]
        offs[word] = (len(blob), len(blob) + len(top), W)
        blob += top + bot
    def alloc(n):
        for sp in draa.LAST_FREE:
            a = (sp[0] + 3) & ~3
            if a + n <= sp[1]:
                sp[0] = a + n
                assert bytes(d[a - DRA:a + n - DRA]) == bytes(n), hex(a)
                return a
        raise SystemExit('engfix: no DRA room for the status name (%d bytes)' % n)
    data_va = alloc(len(blob))
    d[data_va - DRA:data_va - DRA + len(blob)] = blob
    code_va = alloc(4 * 40)
    a = Asm(code_va)
    a.addiu('sp', 'sp', -32); a.sw('ra', 16, 'sp'); a.sw('s0', 20, 'sp'); a.sw('s1', 24, 'sp'); a.sw('s2', 28, 'sp')
    a.addu('s1', 'a3', 'zero')
    def la(r, va):
        a.lui(r, (va + 0x8000) >> 16); a.addiu(r, r, va & 0xFFFF)
    o, ob, W = offs['알카드']
    la('s0', data_va + o); a.ori('s2', 'zero', ob - o)
    a.beq('v0', 'zero', 'draw'); a.nop()
    o2, ob2, W2 = offs['알카트']
    la('s0', data_va + o2); a.ori('s2', 'zero', ob2 - o2)
    a.label('draw')
    x = NAME_X + (NAME_W_US - W) // 2
    a.addu('a0', 's0', 'zero'); a.ori('a1', 'zero', x); a.ori('a2', 'zero', NAME_Y - 2)
    a.jal(0x800F4494); a.addu('a3', 's1', 'zero')
    a.addu('a0', 's0', 's2'); a.ori('a1', 'zero', x); a.ori('a2', 'zero', NAME_Y + 5)
    a.jal(0x800F4494); a.addu('a3', 's1', 'zero')
    a.lw('ra', 16, 'sp'); a.lw('s0', 20, 'sp'); a.lw('s1', 24, 'sp'); a.lw('s2', 28, 'sp')
    a.jr('ra'); a.addiu('sp', 'sp', 32)
    code = a.assemble()
    assert len(code) <= 4 * 40 and W == W2
    d[code_va - DRA:code_va - DRA + len(code)] = code
    d[NAME_CALL - DRA:NAME_CALL - DRA + 4] = jal_word(code_va)
    return 'status name 알카드/알카트 big (code %08X, %d tiles)' % (code_va, len(set(CARRIERS) & set(__import__('g7').CUSTOM)))


def patch(rel, data):
    d = bytearray(data)
    if rel == 'DRA.BIN':
        LOG.append(_spell_or(d))
        if getattr(__import__('draa'), 'LAST_FREE', None) is not None:
            LOG.append(_status_name(d))
    elif rel in ('ST/SEL/SEL.BIN', 'BIN/SELRIC2.BIN'):
        LOG.append(_sel_tags(d, rel))
    elif rel == 'BIN/F_GO.BIN':
        LOG.append(_gameover(d))
    return bytes(d)


if __name__ == '__main__':
    import os, sys
    sys.stdout.reconfigure(encoding='utf-8')
    U = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'U')
    for f in FILES:
        a = patch(f, open(os.path.join(U, *f.split('/')), 'rb').read())
        b = patch(f, a)
        assert a == b
    print('\n'.join(LOG))
    import numpy as np
    from PIL import Image
    img, rgb = gameover_image(open(os.path.join(U, 'BIN', 'F_GO.BIN'), 'rb').read())
    a = np.frombuffer(img, np.uint8).reshape(256, 256)
    Image.fromarray(rgb[a].astype(np.uint8)).resize((768, 768), Image.NEAREST).save(
        os.path.join(U, '..', 'gfx_preview', 'f_go_quote.png'))
