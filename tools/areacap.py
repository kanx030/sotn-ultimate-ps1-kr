"""Korean area-name captions (the italic card shown when entering a new area).

Each stage overlay keeps its caption as a compressed 128x128 4bpp picture (DecompressData format,
gfx.decompress) listed in the stage's gfxBanks (header +0x24, kind 4 entries) at rect (0x100,0x40),
i.e. VRAM (64hw,256). The card is one 256-px line split into two 128-px strips: left half = rows
0..63 cols 0..119, right half = rows 64..127 cols 8..127 (US ink rows 4..36 / 68..99), i.e. a 240-px
line (line x = col, or col + 112 for the lower strip) centred on x=120. Coverage 0..15 = white.
Reverse-castle stages have no caption picture; the remaining (0x100,0x40) pictures 'Golem Maker' /
'蔵書庫 Long Library' are unused JP leftovers (the second LIB one is still replaced, harmless).

Called from build.main's write_file wrapper: data = areacap.patch(rel, data). The compressed picture
is rewritten in place (must fit the original stream size; the original bytes are checked first).
Names follow selui.AREA_KO (save-file area names, Saturn title_ko.AREA).
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx

B = 0x80180000
# file -> [(va of compressed picture, kind, text)]
#   kind 'line'  : normal card (one line over both strips)
#   kind 'one'   : single strip text (rows y0..y1 in the left strip only)
#   kind 'st0'   : two lines in the left strip
CAPS = {
    'ST/ARE/ARE.BIN': [(0x8018521c, 'line', '콜로세움')],
    'ST/CAT/CAT.BIN': [(0x801880d0, 'line', '지하 묘지')],
    'ST/CHI/CHI.BIN': [(0x80189b38, 'line', '버려진 광산')],
    'ST/DAI/DAI.BIN': [(0x80196554, 'line', '왕실 예배당')],
    'ST/DRE/DRE.BIN': [(0x8018a88c, 'line', '악몽')],
    'ST/LIB/LIB.BIN': [(0x80195388, 'line', '장서관'), (0x80184fc8, 'line', '장서관')],
    'ST/NO0/NO0.BIN': [(0x801848a0, 'line', '대리석 회랑')],
    'ST/NO1/NO1.BIN': [(0x8019519c, 'line', '외벽'), (0x80194e14, 'one', '엘리베이터 작동')],
    'ST/NO2/NO2.BIN': [(0x80194014, 'line', '올록스의 거처')],
    'ST/NO4/NO4.BIN': [(0x80185400, 'line', '지하 동굴')],
    'ST/NZ0/NZ0.BIN': [(0x801956a4, 'line', '연금술 연구소')],
    'ST/NZ1/NZ1.BIN': [(0x80186530, 'line', '시계탑')],
    'ST/TE1/TE1.BIN': [(0x80195404, 'line', '지하 정원')],
    'ST/TE2/TE2.BIN': [(0x8018adf8, 'line', '저주받은 감옥')],
    'ST/TOP/TOP.BIN': [(0x80190714, 'line', '성 본관')],
    'ST/ST0/ST0.BIN': [(0x8019a40c, 'st0', ('최종 스테이지 :', '「피의 윤회」'))],
}
FILES = list(CAPS)
LOG = []
SHEAR = 0.15


def _cov(text, max_w, max_h, weight=600):
    return gfx.fit_noto(text, max_w, max_h, weight=weight, serif=True, shear=SHEAR)


def _q(cov, levels=15):
    v = np.clip(np.round(cov * 15), 0, 15).astype(np.uint8)
    if levels < 15:                               # fewer AA steps -> smaller stream
        step = 15 / levels
        v = np.clip(np.round(np.round(v / step) * step), 0, 15).astype(np.uint8)
    return v


def render(kind, text, size=22, levels=15):
    img = np.zeros((128, 128), np.uint8)
    if kind == 'line':
        c = _q(_cov(text, 228, size), levels)
        line = np.zeros((40, 240), np.uint8)
        x = 120 - c.shape[1] // 2
        y = 30 - c.shape[0]                       # bottom of the Hangul at the US baseline (row ~29)
        y = max(5, y)
        line[y:y + c.shape[0], x:x + c.shape[1]] = c
        img[0:40, 0:120] = line[:, :120]
        img[64:104, 8:128] = line[:, 120:]
    elif kind == 'one':
        c = _q(_cov(text, 124, min(size, 19)), levels)
        x = 64 - c.shape[1] // 2
        y = 1 + (20 - c.shape[0]) // 2
        img[y:y + c.shape[0], x:x + c.shape[1]] = c
    elif kind == 'st0':
        a = _q(_cov(text[0], 92, 12, weight=500), levels)
        b = _q(_cov(text[1], 96, 15), levels)
        img[1:1 + a.shape[0], 64 - a.shape[1] // 2:64 - a.shape[1] // 2 + a.shape[1]] = a
        y = 16 + (15 - b.shape[0]) // 2
        img[y:y + b.shape[0], 64 - b.shape[1] // 2:64 - b.shape[1] // 2 + b.shape[1]] = b
    return img


def build_stream(kind, text, limit):
    for size, levels in ((22, 15), (22, 7), (21, 5), (20, 4), (19, 3), (18, 3)):
        if kind != 'line' and size < 22 and levels == 15:
            continue
        img = render(kind, text, size, levels)
        s = gfx.compress(img)
        if len(s) <= limit:
            return img, s, (size, levels)
    raise ValueError('caption does not fit: %r (%d bytes)' % (text, limit))


def patch(rel, data):
    if rel not in CAPS:
        return data
    U = gfx._u(rel)
    d = bytearray(data)
    for va, kind, text in CAPS[rel]:
        o = va - B
        _, n = gfx.decompress(U, o)
        if bytes(d[o:o + n]) != U[o:o + n]:
            LOG.append((rel, text, 'SKIPPED (not US original)'))
            continue
        img, s, cfg = build_stream(kind, text, n)
        out, _ = gfx.decompress(s)
        assert np.array_equal(np.array(out[:16384], np.uint8).reshape(128, 128), img)
        d[o:o + len(s)] = s
        d[o + len(s):o + n] = bytes(n - len(s))     # rest of the old stream (never read)
        LOG.append((rel, text, 'patched %d/%d bytes size %d levels %d' % (len(s), n, cfg[0], cfg[1])))
    return bytes(d)


def preview(out):
    from PIL import Image
    rows = []
    for rel, caps in CAPS.items():
        U = gfx._u(rel)
        for va, kind, text in caps:
            a = np.array(gfx.decompress(U, va - B)[0][:16384], np.uint8).reshape(128, 128)
            img, s, cfg = build_stream(kind, text, gfx.decompress(U, va - B)[1])
            def disp(m):
                return np.hstack([m[0:40, :120], m[64:104, 8:]]) if kind == 'line' else np.hstack([m[0:40, :120], m[64:104, 8:] * 0])
            rows.append(np.hstack([disp(a), np.full((40, 4), 8, np.uint8), disp(img)]))
    Image.fromarray((np.vstack(rows) * 17).astype(np.uint8)).save(out)


if __name__ == '__main__':
    preview(sys.argv[1] if len(sys.argv) > 1 else os.path.join(gfx.PREVIEW, 'areacap.png'))
    for rel in FILES:
        patch(rel, gfx._u(rel))
    for l in LOG:
        print(*l)
