"""Korean cutscene speaker tags in the Long Library (ST/LIB/LIB.BIN).

    data = libnames.patch(path, data)     # only 'ST/LIB/LIB.BIN' is changed; other paths are returned as is

LIB draws its speaker tag with 0x801BA4CC: name index -> pointer table 0x80181A60 (2 entries: 0 "Alucard",
1 "Master Librarian"), one byte = one 8x8 cell of the menu sheet (tpage 0x1E, clut 0x196), 0 = 4 px space,
FF 00 = end. It is the same ST0-type name routine build.patch_names hooks (NAME_SIG matches at 0x801BA5C8), but
build.NAMES only has 'Librarian', and the table points at "Master Librarian", so tag 1 stayed English (tag 0 is
redirected to the shared pool when patch_names ran). K (JP base) is no help here: its LIB tags are the JP
routine with 16-bit cells (flags 0xF000 = dakuten sprite at the same x, 2 px up) and still read ALUCARD /
LIBRARIAN.

What this does (self-contained in LIB, works on the US file or after build.patch_names):
  * writes the Korean names in place over the English strings (build.name_enc: syllable = [FF final] CV),
    "Alucard" -> 알카드 (0x801AE0D4), "Master Librarian" -> 사서 (0x801AE0C0; Saturn menu_ko: '사서와 만남');
  * points both table entries at those strings (undoes patch_names' redirect of entry 0, same text);
  * makes sure the loop head 0x801BA5C8 jumps to build's NAMEH hook (j NAMEH_RAM; ori t9,zero,7), which draws
    the final cell at the next CV's x, 2 px lower. The count loop at 0x801BA500 already counts FF xx as one
    cell, so the primitive count matches. (NAMEH + NHEAD live in the EXE font-ext area; build always writes
    them and NHEAD[7] = 0x801BA5C8.)
Original bytes are asserted; running twice is a no-op.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = 0x80180000
TABLE = 0x1A60
import addrmap
HEAD = addrmap.ovl('ST/LIB/LIB.BIN', 0x801BA5C8) - BASE      # v1.2 0x801BA5C8
HEAD_US = bytes.fromhex('0000c39000000000')              # lbu v1,0(a2); nop
FID = 7                                                   # build.CUTSCENE_FILES index of ST/LIB/LIB.BIN
# (pointer-table slot, US string address, US bytes incl. FF 00 and padding up to the next field, Korean)
TAGS = [
    (0, 0x801AE0D4, bytes.fromhex('214c5543415244ff00000000'), '알카드'),
    (1, 0x801AE0C0, bytes.fromhex('2d4153544552002c494252415249414eff000000'), '사서'),
]
LOG = []


def _base(path):
    return path.replace('\\', '/').split(';')[0].lstrip('/').upper()


def _hook():
    import build
    assert build.CUTSCENE_FILES[FID] == 'ST/LIB/LIB.BIN'
    return struct.pack('<II', (2 << 26) | ((build.NAMEH_RAM >> 2) & 0x3FFFFFF), 0x34190000 | FID)


def _enc(ko):
    import build
    return build.name_enc(ko)


def patch(path, data):
    if _base(path) != 'ST/LIB/LIB.BIN':
        return data
    import build
    d = bytearray(data)
    _, pool = build.name_pool()
    hook = _hook()
    # loop head: US or already hooked by build.patch_names
    h = bytes(d[HEAD:HEAD + 8])
    assert h in (HEAD_US, hook), ('LIB name loop head changed', h.hex())
    assert d[HEAD + 8:HEAD + 16] == bytes.fromhex('0300601401 00c624'.replace(' ', '')), 'LIB name loop changed'
    d[HEAD:HEAD + 8] = hook
    for slot, va, us, ko in TAGS:
        o = va - BASE
        new = _enc(ko)
        assert len(new) <= len(us), (ko, len(new), len(us))
        new = new + bytes(len(us) - len(new))
        cur = bytes(d[o:o + len(us)])
        assert cur in (us, new), ('LIB name string changed', hex(va), cur.hex())
        d[o:o + len(us)] = new
        t = TABLE + 4 * slot
        p = struct.unpack_from('<I', d, t)[0]
        en = 'Alucard' if slot == 0 else None
        assert p == va or (en and p == pool[en]), ('LIB name table changed', slot, hex(p))
        struct.pack_into('<I', d, t, va)
    if bytes(d) != bytes(data):
        LOG.append(('ST/LIB/LIB.BIN', 'speaker tags: ' + ', '.join(ko for _, _, _, ko in TAGS)))
    return bytes(d)


def _render(d, sheet):
    """preview of the two tags as NAMEH draws them (final cell at the next CV's x, 2 px lower)."""
    import numpy as np
    out = []
    for _, va, us, _ in TAGS:
        o = va - BASE
        img = np.zeros((12, 8 * 18), np.uint8)
        x, i, pend = 0, o, False
        while True:
            c = d[i]; i += 1
            dy = 0
            if c == 0xFF:
                c = d[i]; i += 1
                if c == 0:
                    break
                dy = 2
            if c == 0:
                x += 4
                continue
            cell = sheet[(c >> 4) * 8:(c >> 4) * 8 + 8, (c & 15) * 8:(c & 15) * 8 + 8]
            region = img[dy:dy + 8, x:x + 8]
            region[cell != 0] = cell[cell != 0]
            if not dy:
                x += 8
        out.append(img)
    return np.vstack(out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import gfx, draa
    U = gfx._u('ST/LIB/LIB.BIN')
    a = patch('ST/LIB/LIB.BIN', U)
    assert patch('ST/LIB/LIB.BIN', a) == a
    import build
    b, _ = build.patch_names(build.patch_cutscene(U, FID, 'ST/LIB/LIB.BIN'), FID)
    b2 = patch('ST/LIB/LIB.BIN', b)
    assert patch('ST/LIB/LIB.BIN', b2) == b2
    fg = draa.patch_fgame('BIN/F_GAME.BIN', gfx._u('BIN/F_GAME.BIN'))
    sheet = gfx.blk_get(fg, 0x30000)
    os.makedirs(gfx.PREVIEW, exist_ok=True)
    gfx._pair(_render(U, gfx.blk_get(gfx._u('BIN/F_GAME.BIN'), 0x30000)), _render(a, sheet),
              os.path.join(gfx.PREVIEW, 'lib_speaker_tags.png'), 4)
    for l in LOG:
        print(*l)
