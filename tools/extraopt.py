"""Ultimate's 'Extra settings' (System menu 7th item + submenu) in Korean.

Ultimate keeps this code and its strings in BIN/ARC_F2.BIN, loaded whole at 0x8013C000:
  * 0x8016E4F8 "Extra settings"  MenuDrawStr (engine A, 8x8 sheet) from 0x8016E1DC (lui/addiu)
  * 0x8016E498 label table -> "Boss Richter" / "Boss Maria" / "Balance" / "Dub" (engine A, loop at 0x8016E2A8)
  * 0x8016E478 value strings, 8-byte stride: "PS1" "Saturn" "PSP" "JP" (engine A, 0x8016E300)
  * 0x8016DC00 help line "Boss versions, game balance and voices" (engine B / glyph API, 2-byte codes),
    pointed to by DRA's system-help table entries 7..10 (0x800A2B20..2C); code follows at 0x8016DC28.
Space: labels are repacked into 0x8016E4A8..D7 (48 B) + the tail of the 'Extra settings' slot
0x8016E4F8..0F (24 B; 0x8016E510/14 are variables). Nothing in DRA is used.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draa, drab, fontext

FILES = ('BIN/ARC_F2.BIN',)
BASE = 0x8013C000
HELP_KO = '보스 버전, 게임 밸런스, 음성 설정'
CHEAT_HELP_KO = '무적, 무한, 아이템 등 테스트용 치트'   # --test builds: help line of the 치트 row
CHEAT_HELP_VA = 0x8016FE00                          # ARC_F2 zero tail (thunks start at 0x8016FF00)
fontext.ensure(''.join(c for c in HELP_KO + CHEAT_HELP_KO if fontext.is_hangul(c)))   # extension glyphs (밸) before the font is written

def _a(t): return draa.encode_a(t) + b'\xff\x00'

def patch(path, data):
    if path.replace('\\', '/').lstrip('/') not in FILES:
        return data
    d = bytearray(data)
    o = lambda va: va - BASE
    def chk(va, s): assert d[o(va):o(va) + len(s)] == s, (hex(va), d[o(va):o(va) + len(s)])
    chk(0x8016DC00, b'Boss versions\x81\x43 game balance and voices\0')
    chk(0x8016E480, bytes(ord(c) - 0x20 for c in 'Saturn') + b'\xff\0')
    chk(0x8016E4F8, bytes(ord(c) - 0x20 if c != ' ' else 0 for c in 'Extra settings') + b'\xff')
    assert d[o(0x8016E507):o(0x8016E510)] == bytes(9)
    tbl = o(0x8016E498)
    assert struct.unpack_from('<4I', d, tbl) == (0x8016E4C8, 0x8016E4BC, 0x8016E4B0, 0x8016E4A8)
    # help (engine B), 40 bytes before code
    h, bad, _ = drab.encode(HELP_KO)
    assert not bad, bad
    h += b'\0'; assert len(h) <= 40, len(h)
    d[o(0x8016DC00):o(0x8016DC28)] = h.ljust(40, b'\0')
    # value 'Saturn' -> 새턴 (8-byte slot)
    v = _a('새턴'); assert len(v) <= 8
    d[o(0x8016E480):o(0x8016E488)] = v.ljust(8, b'\0')
    # menu item + labels
    seg1 = [(o(0x8016E4A8), o(0x8016E4D8))]
    seg2 = [(o(0x8016E4F8), o(0x8016E510))]
    for a, b in seg1 + seg2:
        d[a:b] = bytes(b - a)
    def put(seg, s):
        b = _a(s); a = seg[0][0]
        assert a + len(b) <= seg[0][1], ('no room', s)
        d[a:a + len(b)] = b; seg[0] = (a + len(b), seg[0][1]); return BASE + a
    item = put(seg2, '추가 설정'); assert item == 0x8016E4F8
    labels = [put(seg1, '보스 리히터'), put(seg1, '보스 마리아'), put(seg1, '밸런스'), put(seg2, '음성')]
    struct.pack_into('<4I', d, tbl, *labels)
    import cheatmenu
    if cheatmenu.ENABLED:
        _cheat_entry(d, o)
    return bytes(d)

def _cheat_entry(d, o):
    """--test builds: System menu row 6 '치트' opens the cheat window (cheatmenu.py), 추가 설정 moves to row 7."""
    import cheatmenu
    from asm import jal_word
    L = cheatmenu.labels()
    def rep(va, old, new):
        assert d[o(va):o(va) + 4] == old, (hex(va), d[o(va):o(va) + 4].hex())
        d[o(va):o(va) + 4] = new
    w = lambda x: struct.pack('<I', x)
    h, bad, _ = drab.encode(CHEAT_HELP_KO); assert not bad, bad
    h += b'\0'; assert len(h) <= 0x100, len(h)
    assert not any(d[o(CHEAT_HELP_VA):o(CHEAT_HELP_VA) + 0x100])
    d[o(CHEAT_HELP_VA):o(CHEAT_HELP_VA) + len(h)] = h     # DRA's help entry 7 is pointed here by build.py
    rep(0x8016E3B4, w(0x28420007), w(0x28420008))          # slti v0,v0,7 -> 8 (cursor clamp)
    rep(0x8016E3C0, w(0x34020006), w(0x34020007))          # clamp value 6 -> 7
    # thunks in ARC_F2's zero tail: use the cheat blob only if it is in RAM (save states from older builds
    # have no blob at CHEAT_RAM -> fall back to the original routines instead of jumping into zeros)
    from asm import Asm
    TH = 0x8016FF00
    assert not any(d[o(TH):o(TH) + 0x100])
    a = Asm(TH)
    first = struct.unpack('<I', cheatmenu.blob()[1][:4])[0]
    for name, orig in (('sysnav', cheatmenu.NAV), ('sysdraw', cheatmenu.MENUDRAWSTR),
                       ('ctxdraw', cheatmenu.CTXDRAW_ORIG)):
        a.label(name)
        a.li('t0', cheatmenu.CHEAT_RAM); a.lw('t0', 0, 't0'); a.li('t1', first)
        a.bne('t0', 't1', name + '_o'); a.nop()
        a.j(L[name]); a.nop()
        a.label(name + '_o')
        a.j(orig); a.nop()
    tb = a.assemble(); d[o(TH):o(TH) + len(tb)] = tb
    T = a.labels
    rep(0x8016E3C8, jal_word(cheatmenu.NAV), jal_word(T['sysnav']))
    rep(0x8016E3CC, w(0x34050007), w(0x34050008))          # 7 -> 8 rows
    rep(0x8016E3D4, w(0x34020006), w(0x34020007))          # 추가 설정 row 6 -> 7
    rep(0x8016E1E4, w(0x34060090), w(0x340600A0))          # 추가 설정 y 0x90 -> 0xA0
    rep(0x8016E1E8, jal_word(cheatmenu.MENUDRAWSTR), jal_word(T['sysdraw']))
    rep(0x8016E268, jal_word(cheatmenu.CTXDRAW_ORIG), jal_word(T['ctxdraw']))   # slot content: cheat window
    rep(0x8016E140, w(0x14620006), w(0x1462001C))          # step 0x10F with a non-추가 설정 width: keep it open

if __name__ == '__main__':
    p = os.path.join(draa.WORK, 'U', 'BIN', 'ARC_F2.BIN')
    out = patch('BIN/ARC_F2.BIN', open(p, 'rb').read())
    print('ok', sum(a != b for a, b in zip(out, open(p, 'rb').read())), 'bytes changed')
