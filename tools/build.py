"""Build the Korean SOTN Ultimate image.
python build.py <out.bin>
"""
import sys, os, struct, shutil, json
sys.path.insert(0, os.path.dirname(__file__))
from asm import Asm, jal_word
import imgpatch

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
import base
SRC_IMG = base.SRC_IMG                 # 원본롬 (base version: base.py / env SOTN_BASE)
K = os.path.join(ROOT, 'work', 'K')
U = base.U

# RAM layout
FONT_RAM = 0x801F0000
EXT_GLYPH = 1536               # glyph slots 1536..1599 are unused garbage in the Korean font
EXT_RAM = 0x801F0000 + EXT_GLYPH * 30   # table + blank glyph + code (stack reaches 0x801FF3xx, so not after the font)
EXT_SIZE = 64 * 30
TABLE_RAM = EXT_RAM
BLANK_RAM = EXT_RAM + 0x50
LOOKUP_RAM = EXT_RAM + 0x80
NARR_ENT_RAM = EXT_RAM - 0x10   # JP crawl narration XA entry (tail of the g7 area, see narration.py)
# EXE layout (file offset = va - 0x80010000 + 0x800), inside region cleared as BSS at boot
FONT_SRC = 0x80033BE8
STUB_VA = 0x80043000
COPY_LEN = 0xF000
ORIG_ENTRY = 0x80010DFC
CHEAT_SRC = 0x80044000          # test builds: cheat menu blob in the EXE (BSS, zero in the original file)

def exe_off(va): return va - 0x80010000 + 0x800

def lookup_code():
    a = Asm(LOOKUP_RAM)
    a.andi('a0', 'a0', 0xFFFF)
    a.ori('at', 'zero', 0x8140)
    a.beq('a0', 'at', 'blank'); a.nop()
    a.ori('at', 'zero', 0x8940)
    a.sltu('at', 'a0', 'at')
    a.beq('at', 'zero', 'form'); a.nop()
    a.li('t5', TABLE_RAM)
    a.ori('t6', 'zero', 19)
    a.label('loop')
    a.sll('at', 't6', 2); a.addu('t1', 't5', 'at')
    a.lbu('at', 0, 't1'); a.lbu('t2', 1, 't1'); a.sll('at', 'at', 8); a.addu('t2', 'at', 't2')
    a.sltu('at', 'a0', 't2')
    a.bne('at', 'zero', 'next'); a.nop()
    a.lbu('at', 2, 't1'); a.lbu('v0', 3, 't1'); a.sll('at', 'at', 8); a.addu('at', 'at', 'v0')
    a.addu('v0', 'a0', 'at'); a.subu('v0', 'v0', 't2')
    a.b('ptr'); a.nop()
    a.label('next')
    a.bne('t6', 'zero', 'loop'); a.addiu('t6', 't6', -1)
    a.label('form')
    a.srl('t1', 'a0', 8); a.andi('t1', 't1', 0xFF); a.andi('t2', 'a0', 0xFF)
    a.sltiu('at', 't2', 0x7F)
    a.bne('at', 'zero', 'f2'); a.nop()
    a.addiu('t2', 't2', -1)
    a.label('f2')
    a.addiu('t1', 't1', -137)
    a.sll('t5', 't1', 7); a.sll('t6', 't1', 6); a.sll('at', 't1', 2)
    a.subu('at', 't5', 'at'); a.addu('at', 'at', 't6'); a.addu('at', 'at', 't2')
    a.addiu('v0', 'at', 554)
    a.label('ptr')
    a.sltiu('at', 'v0', 2048)
    a.beq('at', 'zero', 'blank'); a.nop()
    a.addiu('at', 'v0', -EXT_GLYPH); a.sltiu('at', 'at', 64)
    a.bne('at', 'zero', 'blank'); a.nop()
    a.sll('at', 'v0', 5); a.subu('at', 'at', 'v0'); a.subu('v0', 'at', 'v0')
    a.lui('at', FONT_RAM >> 16); a.addu('v0', 'at', 'v0')
    a.jr('ra'); a.nop()
    a.label('blank')
    a.li('v0', BLANK_RAM)
    a.jr('ra'); a.nop()
    return a.assemble()

def stub_code():
    a = Asm(STUB_VA)
    a.li('t0', FONT_SRC); a.lui('t1', FONT_RAM >> 16); a.li('t2', FONT_SRC + COPY_LEN)
    a.label('l')
    a.lw('t3', 0, 't0'); a.addiu('t0', 't0', 4); a.sw('t3', 0, 't1')
    a.bne('t0', 't2', 'l'); a.addiu('t1', 't1', 4)
    if CHEATS:                                 # cheat menu blob: EXE BSS -> free RAM below DRA
        import cheatmenu
        a.li('t0', CHEAT_SRC); a.li('t1', cheatmenu.CHEAT_RAM); a.li('t2', CHEAT_SRC + cheatmenu.CHEAT_SIZE)
        a.label('c')
        a.lw('t3', 0, 't0'); a.addiu('t0', 't0', 4); a.sw('t3', 0, 't1')
        a.bne('t0', 't2', 'c'); a.addiu('t1', 't1', 4)
    a.j(ORIG_ENTRY); a.nop()
    return a.assemble()

def patch_exe(exe):
    exe = bytearray(exe)
    kexe = open(os.path.join(K, 'SLPM_860.23'), 'rb').read()
    font = kexe[0x243E8:0x243E8 + 0xF000]
    table = kexe[0xE00:0xE50]
    ext = bytearray(EXT_SIZE)
    ext[0:0x50] = table
    lk = lookup_code(); assert len(lk) <= len(ext) - 0x80
    ext[0x80:0x80 + len(lk)] = lk
    assert 0x80 + len(lk) <= 0x1C0
    sh = st0help_code(); assert len(sh) <= 0x80
    ext[0x200:0x200 + len(sh)] = sh
    kc = kst0_code(); assert KST0_RAM + len(kc) <= NAMEH_RAM, len(kc)
    ext[0x280:0x280 + len(kc)] = kc
    kt = ktab(); o = KTAB_RAM - EXT_RAM; ext[o:o + len(kt)] = kt
    ks = kskip_code(); o = KSKIP_RAM - EXT_RAM; ext[o:o + len(ks)] = ks
    nh = nameh_code(); assert len(nh) == 8; o = NAMEH_RAM - EXT_RAM; ext[o:o + len(nh)] = nh
    nb, _ = name_pool(); o = NAME_POOL - EXT_RAM; ext[o:o + len(nb)] = nb
    hd = name_heads(); o = NHEAD_RAM - EXT_RAM; ext[o:o + len(hd)] = hd
    assert NFLAG_RAM + 4 <= EXT_RAM + EXT_SIZE
    if TEST:
        ph = padhook_code(); assert len(ph) <= 0x30
        ext[0x1C0:0x1C0 + len(ph)] = ph
    font = bytearray(font); font[EXT_GLYPH * 30:EXT_GLYPH * 30 + len(ext)] = ext
    import fontext
    font = fontext.apply(font)              # extra Hangul glyphs (generated) in the unused kanji slots
    blob, _ = bank().blob()                 # Galmuri cutscene glyph bank (slots 1600+), skipping the hole
    assert len(blob) <= BANK_END - BANK_RAM
    o = BANK_RAM - FONT_RAM; font[o:o + len(blob)] = blob
    import g7                               # Galmuri7 8x8 syllable bank + glyph cache code (font slots 1290..1535)
    va, gb, gn = g7.blob(); o = va - FONT_RAM
    assert va + len(gb) <= EXT_RAM
    font[o:o + len(gb)] = gb
    print('g7: %d syllables, %d bytes free' % (gn, EXT_RAM - va - len(gb)))
    import narration                        # JP crawl narration XA entry (16 bytes just below the ext area)
    if narration.ENABLED:
        assert va + len(gb) <= NARR_ENT_RAM
        o = NARR_ENT_RAM - FONT_RAM; font[o:o + 16] = narration.entry(narration.LBA0)
    o = exe_off(FONT_SRC); exe[o:o + 0xF000] = font
    st = stub_code(); o = exe_off(STUB_VA); exe[o:o + len(st)] = st
    assert STUB_VA + len(st) <= CHEAT_SRC
    if CHEATS:
        import cheatmenu
        _, cb = cheatmenu.blob(); o = exe_off(CHEAT_SRC)
        assert not any(exe[o:o + cheatmenu.CHEAT_SIZE]); exe[o:o + len(cb)] = cb
    exe[0x10:0x14] = struct.pack('<I', STUB_VA)          # pc0
    # InitHeap(0x801F0000) writes a header over glyph 0 (U+3000 space); lookup maps 0x8140 to a blank glyph.
    return bytes(exe)

PADHOOK_RAM = EXT_RAM + 0x1C0   # test builds only
MAILBOX_RAM = EXT_RAM + 0x1F0

def padhook_code():
    a = Asm(PADHOOK_RAM)
    a.addiu('sp', 'sp', -24); a.sw('ra', 16, 'sp')
    a.jal(0x80015288); a.nop()                 # PadRead
    a.li('at', MAILBOX_RAM); a.lw('t0', 0, 'at')
    a.lw('ra', 16, 'sp')          # (load-delay slot below)
    a.or_('v0', 'v0', 't0')
    a.jr('ra'); a.addiu('sp', 'sp', 24)
    return a.assemble()

TEST = False
CHEATS = True                                  # cheat window + Richter/Maria pause cheats (release too, user 11-12)

ST0HELP_RAM = EXT_RAM + 0x200

def st0help_code():
    a = Asm(ST0HELP_RAM)
    a.sltiu('v0', 'a1', 0x80)
    a.bne('v0', 'zero', 'asc'); a.nop()
    a.lui('t0', 0x801C); a.lw('t1', 0x2AF8, 't0'); a.nop()
    a.lbu('t2', 0, 't1'); a.addiu('t1', 't1', 1); a.sw('t1', 0x2AF8, 't0')
    a.sll('a0', 'a1', 8); a.or_('a0', 'a0', 't2')
    a.lui('v0', 0x8004); a.lw('v0', -14336, 'v0'); a.nop()
    a.jr('v0'); a.addu('a1', 'zero', 'zero')
    a.label('asc')
    a.j(0x801B1800); a.addiu('sp', 'sp', -24)
    return a.assemble()

# Cutscene text engine (ST0 type; also NO3, NO4, DAI, TOP, CEN, bosses ... see cutscene.py): bytes >= 0x15
# are drawn by copying an 8x8 cell from a VRAM font sheet. Bytes >= 0x80 are taken as 2-byte Korean codes:
# the 16x15 glyph is expanded to 4bpp and uploaded with LoadImage at the text cursor.
# One shared hook in the font ext area; each overlay jumps to it with its id in t9 (delay slot) and the
# hook reads that overlay's (return, exit, cursor) addresses from KTAB.
KST0_RAM = EXT_RAM + 0x280
KBUF_RAM = EXT_RAM + 0x500      # 72-byte 12x12 4bpp image, RECT +0x80, saved ra +0x88, entry +0x8C, width +0x90
KTAB_RAM = EXT_RAM + 0x5A0      # 16-byte entries: ret, exit, cursor (line counter = cursor + 4), text VRAM y base
KCOLOR = 6              # palette index of the English body text (206,203,206)
LOADIMAGE = 0x80012B24
import cutscene
CUTSCENE_FILES = ['ST/ST0/ST0.BIN', 'ST/NO3/NO3.BIN', 'ST/NO4/NO4.BIN', 'ST/DAI/DAI.BIN', 'ST/TOP/TOP.BIN',
                  'ST/CEN/CEN.BIN', 'ST/RCEN/RCEN.BIN', 'ST/LIB/LIB.BIN', 'ST/NZ0/NZ0.BIN', 'ST/DRE/DRE.BIN',
                  'BOSS/BO2/BO2.BIN', 'BOSS/BO5/BO5.BIN', 'BOSS/BO6/BO6.BIN', 'BOSS/RBO2/RBO2.BIN',
                  'BOSS/RBO6/RBO6.BIN', 'BIN/BO6RIC2.BIN', 'BIN/CENP.BIN', 'BOSS/MAR/MAR.BIN',
                  'ST/SEL/SEL.BIN']
assert KTAB_RAM + 16 * len(CUTSCENE_FILES) <= EXT_RAM + EXT_SIZE

def kst0_code():
    """Galmuri bank glyph: hi byte 0x90..0x9E -> wide glyph ((hi-0x90)<<8|lo), 0x9F -> narrow glyph NW+lo.
    11x11 1bpp -> 4bpp buffer (12 rows, w halfwords), LoadImage at (cursor, ybase + 12*line), cursor += w."""
    nw = bank_nw()
    a = Asm(KST0_RAM)
    a.sll('t8', 't9', 4)
    a.li('t9', KTAB_RAM); a.addu('t8', 't8', 't9')        # t8 = entry
    a.lhu('at', 14, 't8')                                  # variant: 0 = char a2/ptr s1, 1 = a1/s0, 2 = a1/s1
    a.addu('t3', 's1', 'zero')
    a.beq('at', 'zero', 'v0k'); a.nop()
    a.addu('a2', 'a1', 'zero')
    a.ori('v0', 'zero', 1)
    a.bne('at', 'v0', 'v0k'); a.nop()
    a.addu('t3', 's0', 'zero')
    a.label('v0k')
    a.sltiu('at', 'a2', 0x80)
    a.beq('at', 'zero', 'kr'); a.nop()
    a.lw('t9', 0, 't8')                                    # ASCII: original two instructions, then return
    a.andi('v0', 'a2', 0xF)
    a.jr('t9'); a.sll('v0', 'v0', 1)
    a.label('kr')
    a.li('t9', KBUF_RAM)
    a.sw('ra', 0x88, 't9'); a.sw('t8', 0x8C, 't9')
    a.lw('t0', 0, 't3'); a.nop()
    a.lbu('t1', 0, 't0'); a.addiu('t0', 't0', 1); a.sw('t0', 0, 't3')
    a.ori('at', 'zero', 0x9F)
    a.bne('a2', 'at', 'wide'); a.ori('t6', 'zero', 3)
    a.ori('t6', 'zero', 2)
    a.b('got'); a.addiu('t1', 't1', nw)
    a.label('wide')
    a.addiu('t2', 'a2', -0x90); a.sll('t2', 't2', 8); a.or_('t1', 't2', 't1')
    a.label('got')
    a.sw('t6', 0x90, 't9')
    a.li('t0', BANK_RAM); a.sll('t1', 't1', 4); a.addu('t0', 't0', 't1')   # src glyph
    a.sll('t7', 't6', 1)                                   # buffer stride (bytes per row)
    a.addu('t3', 't9', 'zero'); a.ori('t4', 'zero', 72)
    a.label('clr')
    a.sb('zero', 0, 't3'); a.addiu('t4', 't4', -1)
    a.bne('t4', 'zero', 'clr'); a.addiu('t3', 't3', 1)
    a.addu('t5', 'zero', 'zero')                           # bit counter
    a.addu('a3', 't9', 'zero')                             # row base
    a.sll('a1', 't6', 2)                                   # visible width in px
    a.addu('t2', 'zero', 'zero')
    a.label('rowl')
    a.addu('t3', 'zero', 'zero')
    a.label('coll')
    a.srl('t4', 't5', 3); a.addu('t4', 't0', 't4'); a.lbu('t4', 0, 't4')
    a.andi('at', 't5', 7); a.ori('v0', 'zero', 7); a.subu('at', 'v0', 'at')
    a.srlv('t4', 't4', 'at'); a.andi('t4', 't4', 1)
    a.beq('t4', 'zero', 'skip'); a.addiu('t5', 't5', 1)
    a.sltu('v0', 't3', 'a1')
    a.beq('v0', 'zero', 'skip'); a.nop()
    a.srl('v0', 't3', 1); a.addu('v0', 'a3', 'v0'); a.lbu('v1', 0, 'v0')
    a.andi('at', 't3', 1); a.sll('at', 'at', 2)
    a.ori('a0', 'zero', KCOLOR); a.sllv('a0', 'a0', 'at')
    a.or_('v1', 'v1', 'a0'); a.sb('v1', 0, 'v0')
    a.label('skip')
    a.addiu('t3', 't3', 1); a.slti('at', 't3', 11)
    a.bne('at', 'zero', 'coll'); a.nop()
    a.addu('a3', 'a3', 't7')
    a.addiu('t2', 't2', 1); a.slti('at', 't2', 11)
    a.bne('at', 'zero', 'rowl'); a.nop()
    # RECT at KBUF+0x80: x = cursor, y = ybase + 12*line, w, h = 12
    a.lw('t8', 0x8C, 't9'); a.nop()
    a.lw('t0', 8, 't8'); a.nop()
    a.lhu('t1', 0, 't0'); a.lhu('t2', 4, 't0'); a.nop()
    a.sh('t1', 0x80, 't9')
    a.lh('t4', 12, 't8')
    a.sll('t3', 't2', 3); a.sll('t2', 't2', 2); a.addu('t3', 't3', 't2'); a.addu('t3', 't3', 't4')
    a.sh('t3', 0x82, 't9')
    a.sh('t6', 0x84, 't9')
    a.ori('t3', 'zero', 12); a.sh('t3', 0x86, 't9')
    a.addiu('a0', 't9', 0x80)
    a.jal(LOADIMAGE); a.addu('a1', 't9', 'zero')
    a.li('t9', KBUF_RAM)
    a.lw('t8', 0x8C, 't9'); a.lw('t6', 0x90, 't9')
    a.lw('t0', 8, 't8'); a.nop()
    a.lhu('t1', 0, 't0'); a.nop()
    a.addu('t1', 't1', 't6'); a.sh('t1', 0, 't0')
    a.lw('t1', 4, 't8')
    a.lw('ra', 0x88, 't9')
    a.jr('t1'); a.nop()
    return a.assemble()

# engine variants without the ST0 char signature: (char routine va, exit va, cursor va, variant)
VARIANTS = {'ST/SEL/SEL.BIN': (0x801C0440, 0x801C07D4, 0x801C54AE, 1),
            'BOSS/MAR/MAR.BIN': (0x8018C6A8, 0x8018CCB4, 0x8019B30A, 2)}

def ktab():
    out = b''
    for f in CUTSCENE_FILES:
        if f in VARIANTS:
            c, ex, cur, var = VARIANTS[f]
            out += struct.pack('<IIIhH', c + 8, ex, cur, 384, var); continue
        p = cutscene.params(read(os.path.join(U, *f.split('/'))))
        out += struct.pack('<IIIhH', p['ret'], p['exit'], p['cursor'], p['ybase'] or 384, 0)
    return out

# Galmuri glyph bank for all cutscene text (font slots 1600..2047)
import gfont
# Bank lives in the Korean font's unused Japanese kana/greek/cyrillic/box slots 209..523 (codes 0x829F-0x84BE are
# never used by our text). The font area above 0x801FC000 is NOT safe: the game writes buffers there at runtime.
BANK_RAM = (FONT_RAM + 209 * 30 + 3) & ~3
BANK_END = FONT_RAM + 524 * 30
BANK_MAX = (BANK_END - BANK_RAM) // 16
HOLE = (BANK_END, BANK_END)          # no hole inside this segment
BANK_SPLIT = BANK_MAX
_BANK = None
def bank():
    global _BANK
    if _BANK is None:
        import st0text, transapply
        _BANK = gfont.Bank()
        for s in st0text.cutscene_strings() + transapply.all_strings():
            _BANK.add(s)
        assert len(_BANK.wide) + len(_BANK.narrow) <= BANK_MAX, (len(_BANK.wide), BANK_MAX)
    return _BANK
def bank_nw():
    return len(bank().wide)

CUTSCENE_SKIPPED = []

# Cutscene skip (Start): the engine re-runs the script with g_SkipCutscene set, and its char path then just
# drops ONE byte per char (`lw v0,skip; nop; bne v0,zero,loop; nop` 0x48 before the char code). A Korean char is
# two bytes, so the low byte was run as an opcode (e.g. 0x0F jump -> random address -> freeze). The 5 words become
# `jal KSKIP; nop; .word skipvar; .word loop; nop`; KSKIP skips the extra byte of a >= 0x80 char.
KSKIP_RAM = EXT_RAM + 0x6D0
assert KTAB_RAM + 16 * len(CUTSCENE_FILES) <= KSKIP_RAM

def kskip_code():
    a = Asm(KSKIP_RAM)
    a.lw('t8', 0, 'ra'); a.lw('t9', 4, 'ra')            # skip flag address, loop head
    a.lw('v0', 0, 't8'); a.nop()
    a.bne('v0', 'zero', 'skip'); a.sltiu('at', 'a2', 0x80)
    a.addiu('ra', 'ra', 12); a.jr('ra'); a.nop()          # not skipping: back to the original char path
    a.label('skip')
    a.bne('at', 'zero', 'go'); a.nop()
    a.lw('t8', 0, 's1'); a.nop(); a.addiu('t8', 't8', 1); a.sw('t8', 0, 's1')   # 2-byte char: drop its low byte
    a.label('go')
    a.jr('t9'); a.nop()
    code = a.assemble()
    assert KSKIP_RAM + len(code) <= NHEAD_RAM
    return code

def patch_skip(data, c):
    o = c - 0x48
    w = lambda k: struct.unpack_from('<I', data, o + 4 * k)[0]
    a, b, n1, br, n2 = (w(k) for k in range(5))
    assert (a >> 16 == 0x3C02 and b >> 16 == 0x8C42 and n1 == 0 and br >> 16 == 0x1440 and n2 == 0), 'skip sig'
    var = ((a & 0xFFFF) << 16) + (b & 0xFFFF) - (0x10000 if b & 0x8000 else 0)
    loop = 0x80180000 + o + 16 + (((br & 0xFFFF) ^ 0x8000) - 0x8000) * 4
    data[o:o + 20] = jal_word(KSKIP_RAM) + struct.pack('<IIII', 0, var, loop, 0)

def patch_cutscene(data, fid, name=''):
    data = bytearray(data)
    loc = cutscene.locate(bytes(data))
    if name in VARIANTS:
        c = VARIANTS[name][0] - 0x80180000
        assert data[c:c + 8] == bytes.fromhex('0f00a23040100200'), name
    elif len(loc['char']) != 1:
        CUTSCENE_SKIPPED.append(name)
        return bytes(data)
    else:
        c = loc['char'][0]
    data[c:c + 8] = struct.pack('<II', (2 << 26) | ((KST0_RAM >> 2) & 0x3FFFFFF), 0x34190000 | fid)   # j hook; ori t9,zero,id
    if name not in VARIANTS:
        patch_skip(data, c)
    o = loc['chary'][0] + 12 if len(loc['chary']) == 1 else None   # 8x8 glyphs 2px lower: closer to the Galmuri baseline
    if o is not None:
        struct.pack_into('<h', data, o, struct.unpack_from('<h', data, o)[0] + 2)
    # dub scripts: each dub keeps its own script (PS1 -> <NAME>.json, JP -> .jp.json, PSP -> .psp.json).
    # (Until 11-11 the PSP dub was remapped to the PS1 script: ri['psp_to_off'] <- ri['ps1_b'].)
    if os.environ.get('PSP_TO_PS1') and cutscene.remap_info(bytes(data)):
        ri = cutscene.remap_info(bytes(data))
        struct.pack_into('<I', data, ri['psp_to_off'], ri['ps1_b'])
    return bytes(data)

# Speaker names in cutscene boxes: an overlay routine draws each byte as one 8x8 cell of the menu sheet (0 = 4px
# space, FF 00 = end). The Korean build's sheet has CV cells and separate final-consonant cells, so names use a
# custom encoding (syllable = [FF final] CV) and a small hook draws the final cell at the same x as the next CV,
# 2 px lower. Shared name strings + per-overlay loop addresses live in the font ext area.
NAMES = [('Richter', '리히터'), ('Dracula', '드라큘라'), ('Alucard', '알카드'), ('Death', '데스'), ('Maria', '마리아'),
         ('Shaft', '샤프트'), ('Librarian', '사서'), ('Lisa', '리사'), ('Succubus', '서큐버스'), ('Olrox', '올록스'),
         ('Ferryman', '뱃사공')]
NAME_POOL = EXT_RAM + 0x440 + 0xC0 - 0xC0 + 0x0   # placeholder, set below
NAMEH_RAM = EXT_RAM + 0x460
NHEAD_RAM = EXT_RAM + 0x724          # 4 bytes per cutscene file: name-loop head address
NFLAG_RAM = NHEAD_RAM + 4 * 20       # pending final-cell sprite (y fix on next cell)
NAME_POOL = NAMEH_RAM + 8             # up to KBUF_RAM (NAMEH is now an 8-byte trampoline to g7)
NAME_SIG = bytes.fromhex('0000c390000000000300601401' '00c624')

def name_enc(ko):
    import draa
    return draa.encode_a(ko) + b'\xff\x00'       # whole Galmuri7 syllables via g7 (NAMEH -> g7.NAMEH)

def name_pool():
    out = b''; addr = {}
    for en, ko in NAMES:
        addr[en] = NAME_POOL + len(out)
        out += name_enc(ko)
        out += b'\x00' * (-len(out) % 4)
    assert NAME_POOL + len(out) <= KBUF_RAM, len(out)
    return out, addr

def name_heads():
    out = b''
    for f in CUTSCENE_FILES:
        x = read(os.path.join(U, *f.split('/')))
        h = [i for i in range(0, len(x) - 24, 4) if x[i:i + 16] == NAME_SIG and x[i + 20:i + 24] == bytes.fromhex('0400e724')]
        out += struct.pack('<I', 0x80180000 + h[0] if len(h) == 1 else 0)
    return out

def nameh_code():
    import g7
    a = Asm(NAMEH_RAM)
    a.j(g7.entries()['NAMEH']); a.nop()
    return a.assemble()

def patch_names(data, fid=None):
    if os.environ.get('NO_NAMES'): return data, 0
    orig = data; data = bytearray(data); _, addr = name_pool(); n = 0
    for en, ko in NAMES:
        pat = bytes(ord(c) - 0x20 for c in en) + b'\xff\x00'
        i = data.find(pat)
        while i >= 0:
            va = 0x80180000 + i
            for o in range(0, len(data) - 3, 4):
                if fid == 7 and not (0x1A60 <= o < 0x1A80):   # LIB: only the speaker table (boss list uses its own encoding)
                    continue
                if struct.unpack_from('<I', data, o)[0] == va:
                    struct.pack_into('<I', data, o, addr[en]); n += 1
            i = data.find(pat, i + 1)
    h = [i for i in range(0, len(data) - 24, 4) if data[i:i + 16] == NAME_SIG and data[i + 20:i + 24] == bytes.fromhex('0400e724')]
    if len(h) != 1 or fid is None:
        return bytes(orig), 0                 # no hookable name routine here: keep English names
    if n:
        if True:
            data[h[0]:h[0] + 8] = struct.pack('<II', (2 << 26) | ((NAMEH_RAM >> 2) & 0x3FFFFFF), 0x34190000 | fid)
    return bytes(data), n

def patch_st0(st0):
    st0 = bytearray(patch_cutscene(st0, 0, 'ST0'))
    # opening crawl: GetGlyph wrapper reads 2-byte Korean (second byte via the script pointer 0x801C2AF8)
    o = 0x801B17F8 - 0x80180000
    assert st0[o:o + 8] == bytes.fromhex('e8ffbd27ff008530')
    st0[o:o + 4] = struct.pack('<I', (2 << 26) | ((ST0HELP_RAM >> 2) & 0x3FFFFFF))
    return bytes(st0)

def patch_dra(dra):
    import drabapply
    dra, n, _ = drabapply.apply(dra)          # engine-B Korean strings (descriptions, relic/spell names, save msgs)
    import draa
    dra = draa.patch_dra_a(dra)                # engine A (8x8 names/labels) + engine C (12x16 labels)
    dra = bytearray(dra)
    import g7
    o = 0x800F44D4 - 0x800A0000                # MenuDrawStr: lbu a0,0(s0); addiu s0,s0,1 -> jal G7S0; nop
    assert dra[o:o + 8] == bytes.fromhex('0000049201001026'), dra[o:o + 8].hex()
    dra[o:o + 8] = jal_word(g7.entries()['G7S0']) + bytes(4)
    o = 0x64EF8
    assert dra[o:o + 4] == jal_word(0x80015218)
    dra[o:o + 4] = jal_word(LOOKUP_RAM)
    if TEST:
        o = 0x800E6914 - 0x800A0000
        assert dra[o:o + 4] == jal_word(0x80015288)
        dra[o:o + 4] = jal_word(PADHOOK_RAM)
    if CHEATS:
        import cheatmenu                       # cheat window (per-frame toggles hook)
        o = cheatmenu.HOOK_VA - 0x800A0000
        assert dra[o:o + 4] == jal_word(cheatmenu.PADREP)
        dra[o:o + 4] = jal_word(cheatmenu.CHEAT_RAM)
        o = cheatmenu.PAUSE_HOOK_VA - 0x800A0000     # paused (step 0x70): Richter / Maria cheat hint lines
        assert dra[o:o + 4] == jal_word(cheatmenu.PAUSE_HUD), dra[o:o + 4].hex()
        dra[o:o + 4] = jal_word(cheatmenu.labels()['pause'])
        import extraopt                        # System help entry 7 = row 6 (치트 in test builds): own help line
        o = 0x800A2B20 - 0x800A0000
        assert dra[o:o + 4] == struct.pack('<I', 0x8016DC00), dra[o:o + 4].hex()
        dra[o:o + 4] = struct.pack('<I', extraopt.CHEAT_HELP_VA)
        cheatmenu.blob()                       # registers its syllables with g7 before the EXE is built
    import narration                           # JP dub: crawl XA 0x340 -> JP narrated stream (appended by main)
    if narration.ENABLED:
        dra = bytearray(narration.patch_dra(dra, NARR_ENT_RAM))
    return bytes(dra)

def read(p): return open(p, 'rb').read()

def main(out):
    import script_txt                          # 대사집.txt is the source of truth for dialogue: re-apply it first
    if os.path.exists(script_txt.OUT):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            script_txt.do_import()
    p = imgpatch.Patcher(SRC_IMG, out)
    import narration                            # JP narrated crawl stream from the JP disc -> image end
    narration.add_to_image(p.img.f, TEST)
    import banner
    import extraopt                             # import early: ensures its extension glyphs before the font is written
    written = set(); _wf = p.write_file
    def write_file(iso_path, data):             # every file passes through the name-banner fix
        rel = iso_path.lstrip('/').split(';')[0]
        if rel in banner.FILES: data = banner.patch(rel, data)
        if rel == 'ST/LIB/LIB.BIN':
            import libfix; data = libfix.patch(rel, data)
        import areacap                          # Korean area-name caption pictures (after per-file patches)
        if rel in areacap.FILES: data = areacap.patch(rel, data)
        if rel in extraopt.FILES: data = extraopt.patch(rel, data)   # Ultimate 'Extra settings' menu (ARC_F2)
        import engfix                           # leftover English (spell combo 'or', SEL file tags, game over)
        if rel in engfix.FILES: data = engfix.patch(rel, data)
        import godspeed                         # Godspeed Shoes (relic #30): always dash (no double tap), toggle kept
        if rel in godspeed.FILES: data = godspeed.patch(rel, data)
        import bootfast                        # skip the Konami logo movie at boot (SEL/SELRIC2)
        if rel in bootfast.FILES: data = bootfast.patch(rel, data)
        written.add(rel); _wf(iso_path, data)
    p.write_file = write_file
    import popup
    import gfx
    p.write_file('/DRA.BIN;1', gfx.patch_file('DRA.BIN', popup.patch_dra_popup(patch_dra(read(os.path.join(U, 'DRA.BIN'))))))
    import draa
    for fg in ('BIN/F_GAME.BIN', 'BIN/F_GAME2.BIN'):
        p.write_file('/' + fg + ';1', gfx.patch_file(fg, popup.patch_fgame_popup(fg, draa.patch_fgame(fg, read(os.path.join(U, *fg.split('/')))))))
    import st0text, seltext
    done_extra = set()
    for fid, f in enumerate(CUTSCENE_FILES):
        d = patch_cutscene(read(os.path.join(U, *f.split('/'))), fid, f)
        if f == 'ST/ST0/ST0.BIN':
            d = st0text.patch(patch_st0(read(os.path.join(U, 'ST', 'ST0', 'ST0.BIN'))))
            import transapply
            d, _ = transapply._apply(f, d, '.jp.json')
            d, _ = transapply._apply(f, d, '.psp.json')
        elif f not in CUTSCENE_SKIPPED:          # no Korean hook in skipped variants -> keep English
            import transapply
            d, n = transapply.apply(f, d)
            if n: print('  %s: %d lines translated' % (f, n))
        d, nn = patch_names(d, fid)
        import extraapply
        d, ne = extraapply.apply(f, d, skip_cutscene=f in CUTSCENE_SKIPPED)
        if f == 'ST/LIB/LIB.BIN':
            import libnames; d = libnames.patch(f, d)
        if f == 'ST/SEL/SEL.BIN':
            d = gfx.patch_file(f, draa.patch_sel(f, seltext.patch(d)))
            sel_done = d                        # SELRIC2 = this + its own ending sprite bytes (see below)
        p.write_file('/' + f + ';1', d)
        done_extra.add(f)
    if CUTSCENE_SKIPPED:
        print('cutscene engine variants not patched:', CUTSCENE_SKIPPED)
    import transapply
    if transapply.TRIMMED:
        print('trimmed to fit:', transapply.TRIMMED)
    # BIN/SELRIC2.BIN (ending file when the Boss-Richter option / RIC2 name is set) is SEL.BIN byte for byte except
    # sprite/palette data at 0xC71A-0xCD54 and 0xD5EC-0xD5F4 -> take the fully patched SEL (ending lines, PSP/JP
    # scripts, sound mode, credits, graphics) and put those bytes back.
    r2u = read(os.path.join(U, 'BIN', 'SELRIC2.BIN')); su = read(os.path.join(U, 'ST', 'SEL', 'SEL.BIN'))
    rdiff = [i for i in range(len(su)) if su[i] != r2u[i]] if len(su) == len(r2u) else None
    if rdiff is not None and len(rdiff) < 0x1000 and len(sel_done) == len(su) and all(sel_done[i] == su[i] for i in rdiff):
        r2 = bytearray(sel_done)
        for i in rdiff: r2[i] = r2u[i]
        p.write_file('/BIN/SELRIC2.BIN;1', bytes(r2))
        print('SELRIC2: SEL patches + %d own bytes' % len(rdiff))
    else:
      print('SELRIC2: layout differs from SEL, old partial patch')
      try:
        r2 = read(os.path.join(U, 'BIN', 'SELRIC2.BIN'))
        try:
            r2 = seltext.patch(r2)              # same messages if the file matches SEL's layout
        except AssertionError:
            pass
        import selui
        p.write_file('/BIN/SELRIC2.BIN;1', selui.patch('BIN/SELRIC2.BIN', draa.patch_sel('BIN/SELRIC2.BIN', r2)))
      except KeyError as e:
        print('SEL text skipped (missing glyph):', e)
    for gf in gfx.GFX_FILES:                    # graphics-only files (title, select screen ...)
        if gf in ('DRA.BIN', 'BIN/F_GAME.BIN', 'BIN/F_GAME2.BIN', 'ST/SEL/SEL.BIN'): continue
        p.write_file('/' + gf + ';1', gfx.patch_file(gf, read(os.path.join(U, *gf.split('/')))))
    # other overlays with extra sheets (message boxes, relic pop-ups, library...)
    import extraapply, glob as _g
    for fn in sorted(_g.glob(os.path.join(ROOT, 'work', 'trans', 'extra_*.json'))):
        f = json.load(open(fn, encoding='utf-8'))['file']
        if f in done_extra or f.endswith('SEL.BIN') or f.endswith('SELRIC2.BIN'): continue
        d, n = extraapply.apply(f, read(os.path.join(U, *f.split('/'))), skip_cutscene=True)
        if n: p.write_file('/' + f + ';1', d)
    import areacap
    import engfix
    for rel in list(banner.FILES) + [f for f in list(areacap.FILES) + list(extraopt.FILES) + list(engfix.FILES) if f not in banner.FILES]:  # overlays not otherwise touched
        if rel not in written:
            p.write_file('/' + rel + ';1', read(os.path.join(U, *rel.split('/'))))
    p.write_file('/SLUS_000.67;1', patch_exe(read(os.path.join(U, 'SLUS_000.67'))))   # last: g7 bank needs every string
    p.close()
    cue = os.path.splitext(out)[0] + '.cue'
    open(cue, 'w').write('FILE "%s" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n' % os.path.basename(out))
    print('built', out)

if __name__ == '__main__':
    if '--test' in sys.argv:
        TEST = True; sys.argv.remove('--test')
    if CHEATS:
        import cheatmenu; cheatmenu.ENABLED = True
    main(sys.argv[1])

