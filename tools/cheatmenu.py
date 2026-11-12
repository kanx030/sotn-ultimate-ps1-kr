"""Cheat window for --test builds: pause menu > 설정 (System) > '치트' (the row above 추가 설정).
It opens as a submenu box exactly like Ultimate's 추가 설정 window: it borrows the same DRA menu-context slot
(0x80137766, the one ARC_F2 uses for 추가 설정) with its own width CW, menu step 0x10F and the open/close
animation byte (+0x1C). Up/Down select, Cross apply/toggle, Triangle/Circle close (or '닫기').

Hooks (code/data at CHEAT_RAM, copied there by the EXE boot stub, build.stub_code):
  * DRA ReadPads 0x800E6960 'jal 800E67F4' -> entry: per-frame toggles (HP/MP/hearts refill, invincibility)
  * ARC_F2 (extraopt._cheat_entry, through guard thunks): System cursor call -> sysnav (row 6 + Cross opens),
    '추가 설정' label draw -> sysdraw ('치트' label + window input/close), context content draw -> ctxdraw."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
from asm import Asm, _i, _r, R

CHEAT_RAM = 0x8009C000
CHEAT_SIZE = 0x1000
HOOK_VA = 0x800E6960                # jal 800E67F4 inside ReadPads
PADREP = 0x800E67F4
NAV = 0x800F7E44                    # menu cursor up/down (cursor*, count, 0) with sound
CURSORDRAW = 0x800F3AD0             # menu cursor bar (ctx, idx, x, y, w, h, gap, 1)
CTXDRAW_ORIG = 0x800F4E50           # the borrowed context slot's original content routine
ARC_RESTORE = 0x8016DD24            # ARC_F2: restore the slot's rect (after the close animation)
SYS_ITEM = 6                        # System menu: '치트' row (추가 설정 moves to 7)
ENABLED = False                     # set by build.py --test (ARC_F2 System-menu entry is test-only)
PADS = 0x80097490                   # held, prev, tapped, repeat (u16 each)
MENUSTEP = 0x800978F8
SLOT = 0x80137766                   # menu context: x, y, w, h (s16) ... +0x1C anim state (3 open.., 0 idle, 1 close.., 2 closed)
SND = 0x8003C7DC                    # PlaySfx pointer
COLORFLAG = 0x8013784C
MENUDRAWSTR = 0x800F4494
EXPTAB = 0x800E0B7C                 # next-level EXP = EXPTAB[level]
ST = 0x80097964                     # relics
GODSPEED = 0x8003C0DC               # relic #30 Godspeed Shoes (Ultimate: own byte; 1 owned, 2 on)
SPELLS = 0x80097982
HAND = 0x8009798A
BODY = 0x80097A3A                   # body counts follow Ultimate's 176 hand counts
HANDDEF = 0x800A499C                # DRA hand-item table, 0x34 bytes each, +0x0E category
HP = 0x80097BB4                     # HP, HPmax, hearts, heartsmax, MP, MPmax
STATS = 0x80097BCC
LEVEL = 0x80097BFC
EXP = 0x80097C00
GOLD = 0x80097C04

B_CROSS, B_CANCEL = 0x40, 0x30
# Richter / Maria pause screen toggles (nothing else reads pads there): both held, one of them newly tapped.
# They use their own FLAGS bits so Alucard's cheat window (bits 0/1) is untouched.
HK_HP, HK_HEART = 0x0C, 0x03        # L1+R1 -> HP refill, L2+R2 -> hearts refill
RM_HP, RM_HEART = 0x10, 0x20        # FLAGS bits (refilled only while PLAYCHAR != 0)

# pause hint (Richter / Maria): DRA step 0x70 (paused) calls the HUD update 0x801002AC from 0x800F1680
PAUSE_HOOK_VA = 0x800F1680
PAUSE_HUD = 0x801002AC
PLAYCHAR = 0x8003C9A0               # 0 = Alucard (pause opens the menu), else Richter / Maria
HINT1 = 'L1+R1: HP 무한 %s'
HINT2 = 'L2+R2: 하트 무한 %s'
HINT_Y = (50, 62)                   # screen rows under the HUD '일시정지' plate (plate ends ~ y 36)
HINT_OT = 0x1E2                     # below the HUD (0x1F0..): MenuDrawStr's tpage DR_MODE must not share a HUD slot
                                    # (at 0x1FF it re-textured the '일시정지' plate with the font sheet)
SCREEN_W = 256

ITEMS = ['HP/MP/하트 무한', '무적', '골드 999999', '마도기 전부', '마법 전부', '아이템 전부 9개', '장비 전부 9개',
         '능력치 99', '레벨 업', '닫기']
N = len(ITEMS)
CX, CY, CW = 0xAC, 0x30, 0x98       # window rect (menu screen coords); CW != 0xA8 (추가 설정)
ROW = 12                            # row pitch (cursor bar 12 px, no gap)
CH = ROW * N + 8
VX = 0x70                           # value column (ON/OFF/OK), relative to the label x (추가 설정 uses 112)

# vars (offsets from VARS)
MODE, CURSOR, FLAGS, PEND, PREV, SAVEDP, OKT, OKIDX = range(0, 32, 4)


class A(Asm):
    def xori(self, rt, rs, imm): self.w(_i(14, rs, rt, imm))
    def nor(self, rd, rs, rt): self.w(_r(39, rs, rt, rd))
    def slt(self, rd, rs, rt): self.w(_r(42, rs, rt, rd))
    def li32(self, rt, v):
        v &= 0xFFFFFFFF; self.lui(rt, v >> 16); self.ori(rt, rt, v & 0xFFFF)
    def la(self, rt, lab):          # label address (2 words always)
        self.li32(rt, self.L.get(lab, 0))


def _enc(s):
    import draa
    return draa.encode_a(s) + b'\xff\x00'


def _gen(L):
    a = A(CHEAT_RAM); a.L = L
    # ---------------------------------------------------------------- entry (per frame, after pad read)
    a.addiu('sp', 'sp', -32); a.sw('ra', 24, 'sp'); a.sw('s0', 16, 'sp')
    a.jal(PADREP); a.nop()
    a.la('s0', 'vars')
    a.lw('t0', FLAGS, 's0'); a.nop()
    a.andi('t1', 't0', 1)
    a.beq('t1', 'zero', 'c1'); a.nop()
    a.li32('t9', HP)
    for cur in (0, 8, 16):
        a.lw('t2', cur + 4, 't9'); a.nop(); a.sw('t2', cur, 't9')
    a.label('c1')
    a.andi('t1', 't0', 2)
    a.beq('t1', 'zero', 'c2'); a.nop()
    a.jal('invuln'); a.nop()
    a.label('c2')
    # Richter / Maria toggles (set on their pause screen): HP and hearts refilled separately
    a.li32('at', PLAYCHAR); a.lw('t1', 0, 'at'); a.nop()
    a.beq('t1', 'zero', 'c4'); a.nop()
    a.lw('t0', FLAGS, 's0'); a.li32('t9', HP)
    a.andi('t1', 't0', RM_HP)
    a.beq('t1', 'zero', 'c3'); a.nop()
    a.lw('t2', 4, 't9'); a.nop(); a.sw('t2', 0, 't9')
    a.label('c3')
    a.andi('t1', 't0', RM_HEART)
    a.beq('t1', 'zero', 'c4'); a.nop()
    a.lw('t2', 12, 't9'); a.nop(); a.sw('t2', 8, 't9')
    a.label('c4')
    a.lw('s0', 16, 'sp'); a.lw('ra', 24, 'sp'); a.nop()
    a.jr('ra'); a.addiu('sp', 'sp', 32)

    # ---------------------------------------------------------------- sysnav (System cursor routine)
    a.label('sysnav')
    a.addiu('sp', 'sp', -24); a.sw('ra', 16, 'sp'); a.sw('a0', 20, 'sp')
    a.jal(NAV); a.nop()
    a.lw('a0', 20, 'sp'); a.nop(); a.lw('t0', 0, 'a0'); a.ori('at', 'zero', SYS_ITEM)
    a.bne('t0', 'at', 'sn_x'); a.nop()
    a.li32('t9', PADS); a.lhu('t1', 4, 't9'); a.nop(); a.andi('t1', 't1', B_CROSS)
    a.beq('t1', 'zero', 'sn_x'); a.nop()
    a.sh('zero', 4, 't9'); a.sh('zero', 6, 't9')  # consumed (as ARC does for 추가 설정)
    a.li32('t0', SLOT)                            # open the window (same sequence as 추가 설정)
    a.ori('t1', 'zero', CX); a.sh('t1', 0, 't0'); a.ori('t1', 'zero', CY); a.sh('t1', 2, 't0')
    a.ori('t1', 'zero', CW); a.sh('t1', 4, 't0'); a.ori('t1', 'zero', CH); a.sh('t1', 6, 't0')
    a.ori('t1', 'zero', 3); a.sb('t1', 0x1C, 't0'); a.sb('zero', 0x1D, 't0')
    a.ori('t1', 'zero', 0x10F); a.li32('at', MENUSTEP); a.sw('t1', 0, 'at')
    a.la('t8', 'vars'); a.sw('zero', OKT, 't8')
    a.li32('at', SND); a.lw('t1', 0, 'at'); a.nop()
    a.jalr('t1'); a.ori('a0', 'zero', 0x633)
    a.label('sn_x')
    a.lw('ra', 16, 'sp'); a.nop()
    a.jr('ra'); a.addiu('sp', 'sp', 24)

    # ---------------------------------------------------------------- sysdraw (every frame on the System screen)
    # replaces MenuDrawStr('추가 설정', x, y, ctx): '치트' one row above, then the window's input / close logic
    a.label('sysdraw')
    a.addiu('sp', 'sp', -48)
    a.sw('ra', 32, 'sp'); a.sw('s0', 36, 'sp')
    a.sw('a0', 16, 'sp'); a.sw('a1', 20, 'sp'); a.sw('a2', 24, 'sp'); a.sw('a3', 28, 'sp')
    a.la('a0', 's_sys'); a.jal(MENUDRAWSTR); a.addiu('a2', 'a2', -16)
    a.lw('a0', 16, 'sp'); a.lw('a1', 20, 'sp'); a.lw('a2', 24, 'sp'); a.lw('a3', 28, 'sp')
    a.jal(MENUDRAWSTR); a.nop()
    a.la('s0', 'vars')
    a.li32('at', MENUSTEP); a.lw('t0', 0, 'at'); a.ori('at', 'zero', 0x10F)
    a.bne('t0', 'at', 'sd_x'); a.nop()
    a.li32('t9', SLOT); a.lh('t0', 4, 't9'); a.ori('at', 'zero', CW)
    a.bne('t0', 'at', 'sd_x'); a.nop()
    a.lbu('t0', 0x1C, 't9'); a.ori('at', 'zero', 2)
    a.bne('t0', 'at', 'sd_in'); a.nop()
    a.jal(ARC_RESTORE); a.addu('a0', 't9', 'zero')     # closed: give the slot back, return to the System list
    a.ori('t0', 'zero', 0x101); a.li32('at', MENUSTEP); a.sw('t0', 0, 'at')
    a.b('sd_x'); a.nop()
    a.label('sd_in')
    a.bne('t0', 'zero', 'sd_x'); a.nop()               # still animating
    a.la('a0', 'vars'); a.addiu('a0', 'a0', CURSOR); a.ori('a1', 'zero', N)
    a.jal(NAV); a.addu('a2', 'zero', 'zero')
    a.li32('t9', PADS); a.lhu('t1', 4, 't9'); a.nop()
    a.andi('t2', 't1', B_CANCEL)
    a.bne('t2', 'zero', 'sd_close'); a.nop()
    a.andi('t2', 't1', B_CROSS)
    a.beq('t2', 'zero', 'sd_x'); a.nop()
    a.lw('a0', CURSOR, 's0')
    a.jal('apply'); a.nop()
    a.lw('t0', CURSOR, 's0'); a.ori('at', 'zero', N - 1)
    a.bne('t0', 'at', 'sd_snd'); a.nop()
    a.b('sd_x'); a.nop()                         # '닫기' already started the close
    a.label('sd_close')
    a.jal('close'); a.nop()
    a.b('sd_x'); a.nop()
    a.label('sd_snd')
    a.li32('at', SND); a.lw('t1', 0, 'at'); a.nop()
    a.jalr('t1'); a.ori('a0', 'zero', 0x633)
    a.label('sd_x')
    a.lw('s0', 36, 'sp'); a.lw('ra', 32, 'sp'); a.nop()
    a.jr('ra'); a.addiu('sp', 'sp', 48)

    a.label('close')                              # start the close animation (like 추가 설정's cancel)
    a.addiu('sp', 'sp', -24); a.sw('ra', 16, 'sp')
    a.li32('t9', SLOT); a.ori('t1', 'zero', 1); a.sb('t1', 0x1C, 't9'); a.sb('zero', 0x1D, 't9')
    a.li32('at', SND); a.lw('t1', 0, 'at'); a.nop()
    a.jalr('t1'); a.ori('a0', 'zero', 0x633)
    a.lw('ra', 16, 'sp'); a.nop()
    a.jr('ra'); a.addiu('sp', 'sp', 24)

    # ---------------------------------------------------------------- ctxdraw(a0 = context): window content
    a.label('ctxdraw')
    a.lh('t0', 4, 'a0'); a.ori('at', 'zero', CW)
    a.beq('t0', 'at', 'cd'); a.nop()
    a.j(CTXDRAW_ORIG); a.nop()
    a.label('cd')
    a.addiu('sp', 'sp', -64); a.sw('ra', 56, 'sp')
    for k, r in enumerate(('s0', 's1', 's2', 's3', 's4', 's5')):
        a.sw(r, 32 + 4 * k, 'sp')
    a.addu('s2', 'a0', 'zero'); a.la('s0', 'vars')
    a.lh('s5', 0, 's2'); a.lh('s3', 2, 's2'); a.addiu('s5', 's5', 4); a.addiu('s3', 's3', 4)
    a.addu('s1', 'zero', 'zero')
    a.label('cd_lp')
    a.sll('t1', 's1', 2); a.la('t2', 'itab'); a.addu('t1', 't1', 't2'); a.lw('a0', 0, 't1')
    a.sll('s4', 's1', 3); a.sll('t3', 's1', 2); a.addu('s4', 's4', 't3'); a.addu('s4', 's4', 's3')   # 12*i
    a.addu('a1', 's5', 'zero'); a.addu('a2', 's4', 'zero')
    a.jal(MENUDRAWSTR); a.addu('a3', 's2', 'zero')
    a.lw('t0', FLAGS, 's0')
    a.ori('at', 'zero', 0); a.beq('s1', 'at', 'cd_t'); a.andi('t1', 't0', 1)
    a.ori('at', 'zero', 1); a.beq('s1', 'at', 'cd_t'); a.andi('t1', 't0', 2)
    a.lw('t0', OKT, 's0'); a.nop()
    a.beq('t0', 'zero', 'cd_e'); a.nop()
    a.lw('t0', OKIDX, 's0'); a.nop()
    a.bne('t0', 's1', 'cd_e'); a.nop()
    a.la('a0', 's_ok'); a.b('cd_p'); a.nop()
    a.label('cd_t')
    a.la('a0', 's_off')
    a.beq('t1', 'zero', 'cd_p'); a.nop()
    a.la('a0', 's_on')
    a.label('cd_p')
    a.addiu('a1', 's5', VX); a.addu('a2', 's4', 'zero')
    a.jal(MENUDRAWSTR); a.addu('a3', 's2', 'zero')
    a.label('cd_e')
    a.addiu('s1', 's1', 1)
    a.sltiu('at', 's1', N); a.bne('at', 'zero', 'cd_lp'); a.nop()
    a.lw('t0', OKT, 's0'); a.nop()
    a.beq('t0', 'zero', 'cd_c'); a.addiu('t0', 't0', -1)
    a.sw('t0', OKT, 's0')
    a.label('cd_c')                               # cursor bar, as 추가 설정 draws it
    a.li32('at', COLORFLAG); a.sw('zero', 0, 'at')
    a.ori('t0', 'zero', CW - 4); a.sw('t0', 16, 'sp')
    a.ori('t0', 'zero', 0xC); a.sw('t0', 20, 'sp')
    a.ori('t0', 'zero', ROW - 12); a.sw('t0', 24, 'sp')
    a.ori('t0', 'zero', 1); a.sw('t0', 28, 'sp')
    a.addu('a0', 's2', 'zero'); a.lw('a1', CURSOR, 's0')
    a.addiu('a2', 's5', -2)
    a.jal(CURSORDRAW); a.addiu('a3', 's3', -2)
    for k, r in enumerate(('s0', 's1', 's2', 's3', 's4', 's5')):
        a.lw(r, 32 + 4 * k, 'sp')
    a.lw('ra', 56, 'sp'); a.nop()
    a.jr('ra'); a.addiu('sp', 'sp', 64)

    # ---------------------------------------------------------------- pause (replaces jal PAUSE_HUD in step 0x70)
    a.label('pause')
    a.addiu('sp', 'sp', -24); a.sw('ra', 16, 'sp')
    a.jal(PAUSE_HUD); a.nop()
    a.li32('at', PLAYCHAR); a.lw('t0', 0, 'at'); a.nop()
    a.beq('t0', 'zero', 'pz_x'); a.nop()                 # Alucard: menu screen, no hint
    # L1+R1 / L2+R2 (both held, one of them just pressed): toggle HP / hearts refill. Richter / Maria have
    # no pause menu, so this is their way to the cheats; only here (paused), never while playing.
    for k, (combo, bit) in enumerate(((HK_HP, RM_HP), (HK_HEART, RM_HEART))):
        a.li32('t9', PADS); a.lhu('t1', 0, 't9'); a.lhu('t2', 4, 't9'); a.nop()
        a.andi('t1', 't1', combo); a.ori('at', 'zero', combo)
        a.bne('t1', 'at', 'pz_n%d' % k); a.andi('t2', 't2', combo)
        a.beq('t2', 'zero', 'pz_n%d' % k); a.nop()
        a.la('t9', 'vars'); a.lw('t0', FLAGS, 't9'); a.nop(); a.xori('t0', 't0', bit)
        a.sw('t0', FLAGS, 't9')
        a.li32('at', SND); a.lw('t1', 0, 'at'); a.nop()
        a.jalr('t1'); a.ori('a0', 'zero', 0x633)
        a.label('pz_n%d' % k)
    for k, (bit, hint) in enumerate(((RM_HP, HINT1), (RM_HEART, HINT2))):
        a.li32('at', COLORFLAG); a.sw('zero', 0, 'at')
        a.la('t0', 'vars'); a.lw('t0', FLAGS, 't0'); a.nop(); a.andi('t0', 't0', bit)
        a.la('a0', 's_h%doff' % (k + 1))
        a.beq('t0', 'zero', 'pz_d%d' % k); a.nop()
        a.la('a0', 's_h%don' % (k + 1))
        a.label('pz_d%d' % k)
        a.ori('a1', 'zero', _hx(hint % '켬')); a.ori('a2', 'zero', HINT_Y[k])
        a.la('a3', 'hctx'); a.jal(MENUDRAWSTR); a.nop()
    a.label('pz_x')
    a.lw('ra', 16, 'sp'); a.nop()
    a.jr('ra'); a.addiu('sp', 'sp', 24)

    # ---------------------------------------------------------------- invincibility (filled by INVULN list)
    a.label('invuln')                            # keep the player's invincibility timer topped up
    a.la('t0', 'invtab')
    a.label('iv_lp')
    a.lw('t1', 0, 't0'); a.lw('t2', 4, 't0')
    a.beq('t1', 'zero', 'iv_x'); a.nop()
    a.sh('t2', 0, 't1')
    a.b('iv_lp'); a.addiu('t0', 't0', 8)
    a.label('iv_x')
    a.jr('ra'); a.nop()

    # ---------------------------------------------------------------- apply(a0 = item)
    a.label('apply')
    a.addiu('sp', 'sp', -24); a.sw('ra', 16, 'sp')
    a.sw('a0', OKIDX, 's0'); a.ori('t0', 'zero', 45); a.sw('t0', OKT, 's0')
    cases = ['a_inf', 'a_inv', 'a_gold', 'a_relic', 'a_spell', 'a_item', 'a_equip', 'a_stat', 'a_lvl', 'a_close']
    assert len(cases) == N
    for k, c in enumerate(cases):
        a.ori('at', 'zero', k)
        a.beq('a0', 'at', c); a.nop()
    a.b('a_ret'); a.nop()
    a.label('a_inf')
    a.lw('t0', FLAGS, 's0'); a.nop(); a.xori('t0', 't0', 1); a.sw('t0', FLAGS, 's0')
    a.b('a_ret'); a.nop()
    a.label('a_inv')
    a.lw('t0', FLAGS, 's0'); a.nop(); a.xori('t0', 't0', 2); a.sw('t0', FLAGS, 's0')
    a.b('a_ret'); a.nop()
    a.label('a_gold')
    a.li32('t0', 999999); a.li32('at', GOLD); a.sw('t0', 0, 'at')
    a.b('a_ret'); a.nop()
    a.label('a_relic')                           # abilities on (3); familiar cards 18..24 owned (1), keep 'on'
    a.li32('t1', ST); a.addu('t2', 'zero', 'zero')
    a.label('r_lp')
    a.ori('t0', 'zero', 3)
    a.sltiu('at', 't2', 18); a.bne('at', 'zero', 'r_w'); a.nop()
    a.sltiu('at', 't2', 25); a.beq('at', 'zero', 'r_w'); a.nop()
    a.lbu('t0', 0, 't1'); a.nop(); a.ori('t0', 't0', 1)
    a.label('r_w')
    a.sb('t0', 0, 't1'); a.addiu('t1', 't1', 1); a.addiu('t2', 't2', 1)
    a.sltiu('at', 't2', 30); a.bne('at', 'zero', 'r_lp'); a.nop()
    a.li32('t1', GODSPEED); a.ori('t0', 'zero', 3); a.sb('t0', 0, 't1')   # relic #30 (Ultimate keeps it apart)
    a.b('a_ret'); a.nop()
    a.label('a_spell')
    a.li32('t1', SPELLS); a.ori('t0', 'zero', 0x80)
    a.label('s_lp')
    a.sb('t0', 0, 't1'); a.addiu('t1', 't1', 1); a.addiu('t0', 't0', 1)
    a.sltiu('at', 't0', 0x88); a.bne('at', 'zero', 's_lp'); a.nop()
    a.b('a_ret'); a.nop()
    a.label('a_item')                            # consumables only: categories 6 food, 7 special, 8 thrown, 10 medicine
    a.ori('t5', 'zero', 1)
    a.b('hand'); a.nop()
    a.label('a_equip')                           # every body item + hand items that are not consumables
    a.li32('t1', BODY + 1); a.ori('t2', 'zero', 88); a.ori('t0', 'zero', 9)
    a.label('f_lp')
    a.sb('t0', 0, 't1'); a.addiu('t2', 't2', -1)
    a.bne('t2', 'zero', 'f_lp'); a.addiu('t1', 't1', 1)
    a.ori('t5', 'zero', 0)
    a.label('hand')
    a.li32('t1', HAND + 1); a.li32('t3', HANDDEF + 0x34 + 0x0E); a.ori('t2', 'zero', 175)
    a.label('h_lp')
    a.lbu('t4', 0, 't3'); a.nop()
    a.addiu('t6', 't4', -6); a.sltiu('t6', 't6', 3)
    a.xori('t7', 't4', 10); a.sltiu('t7', 't7', 1); a.or_('t6', 't6', 't7')
    a.bne('t6', 't5', 'h_skip'); a.nop()
    a.ori('t0', 'zero', 9); a.sb('t0', 0, 't1')
    a.label('h_skip')
    a.addiu('t1', 't1', 1); a.addiu('t3', 't3', 0x34); a.addiu('t2', 't2', -1)
    a.bne('t2', 'zero', 'h_lp'); a.nop()
    a.b('a_ret'); a.nop()
    a.label('a_stat')
    a.li32('t1', STATS); a.ori('t0', 'zero', 99)
    for k in range(4):
        a.sw('t0', 4 * k, 't1')
    a.b('a_ret'); a.nop()
    a.label('a_lvl')
    a.li32('t1', LEVEL); a.lw('t0', 0, 't1'); a.nop()
    a.sltiu('at', 't0', 99); a.beq('at', 'zero', 'a_ret'); a.nop()
    a.sll('t0', 't0', 2); a.li32('t2', EXPTAB); a.addu('t2', 't2', 't0')
    a.lw('t3', 0, 't2'); a.lw('t4', EXP - LEVEL, 't1'); a.nop()
    a.sltu('at', 't4', 't3'); a.beq('at', 'zero', 'a_ret'); a.nop()
    a.sw('t3', EXP - LEVEL, 't1')
    a.b('a_ret'); a.nop()
    a.label('a_close')
    a.jal('close'); a.nop()
    a.label('a_ret')
    a.lw('ra', 16, 'sp'); a.nop()
    a.jr('ra'); a.addiu('sp', 'sp', 24)

    # ---------------------------------------------------------------- data
    a.label('vars'); a.data(bytes(32))
    a.label('invtab')                            # (address, u16 value) pairs, 0-terminated
    for addr, val in INVULN + [(0, 0)] * (4 - len(INVULN)):
        a.data(struct.pack('<II', addr, val))
    def S(lab, txt):
        a.label(lab); a.data(_enc(txt))
    S('s_h1on', HINT1 % '켬'); S('s_h1off', HINT1 % '끔'); S('s_h2on', HINT2 % '켬'); S('s_h2off', HINT2 % '끔')
    a.label('hctx')                              # menu context for the hint: clip rect = whole screen, ot HINT_OT
    a.data(struct.pack('<4h4h4h2h', 0, 0, 0, 0, 0, 0, 0x200, 0x100, 0, 0, 0, 0, HINT_OT - 2, 0) + bytes(4))
    S('s_sys', '치트'); S('s_on', '켬'); S('s_off', '끔'); S('s_ok', '완료')
    for k, t in enumerate(ITEMS): S('i%d' % k, t)
    a.label('itab')
    for k in range(N): a.data(struct.pack('<I', L.get('i%d' % k, 0)))
    return a

def _hx(t):
    return (SCREEN_W - 8 * len(t)) // 2


INVULN = [(0x80072F1C, 4)]   # g_Player.timers[PL_T_INVINCIBLE], kept topped up while 무적 is on (warg walk-through test)


def labels():
    a = _gen({}); a.assemble(); return a.labels


def blob():
    a = _gen({})
    a.assemble()
    L = dict(a.labels)
    a = _gen(L)
    b = a.assemble()
    assert a.labels == L
    assert len(b) <= CHEAT_SIZE, hex(len(b))
    return CHEAT_RAM, b


if __name__ == '__main__':
    va, b = blob(); print(hex(va), hex(len(b)))
