"""Godspeed Shoes (relic #30, Ultimate addition) behave like the Saturn version (2026-11-12); relic menu toggle kept.
Called from build.write_file for DRA.BIN. Every edit asserts the Ultimate bytes first; idempotent.

Ultimate's implementation (DRA):
- relic #30's byte is not in g_Status.relics[30] (that would be spells[0] at 0x80097982) but at 0x8003C0DC;
  every relic routine special-cases index 0x1E (menu 0x800FA7xx-0x800FAAxx, give 0x800FC00C,
  IsRelicActive 0x800FC408, relic orb in ST/TOP = Castle Keep).
- Start-walk routine 0x8010D214 (velocity 0x18000, step 1): if the double-tap timer 0x801362AC is still
  running (set to 12 at a walk start, 8 at walk->stand, counted down each frame) and 0x80072F9A == 0 and
  IsRelicActive(30) -> dash routine 0x8010D19C (step 0x13, anim 0xD, velocity 0x2D000, dust).
  Landing (0x8010EC4C / 0x8010ED44) keeps the dash when the player jumped out of one.

Changes:
1. 0x8010D214: the timer test is replaced by a test of g_Player.demo_timer (0x80072EFC, cutscene auto-pad):
   every walk start dashes while the relic is on, except during scripted movement (keeps 0x80072F9A test).
The relic menu on/off toggle is left as is (user's choice): switched off = normal walk.
"""
import struct

FILES = ('DRA.BIN',)
LOG = []
DRA = 0x800A0000


def _w(*ws):
    return b''.join(struct.pack('<I', w) for w in ws)


EDITS = [
    # (va, US words, new words, label)
    (0x8010D214,
     _w(0x3C028013, 0x8C4262AC),            # lui v0,0x8013 ; lw v0,0x62AC(v0)   (double-tap timer)
     _w(0x3C028007, 0x8C422EFC),            # lui v0,0x8007 ; lw v0,0x2EFC(v0)   (demo_timer)
     'walk start: timer -> demo_timer'),
    (0x8010D22C,
     _w(0x1040000E),                        # beqz v0,0x8010D268 (no timer -> plain walk)
     _w(0x1440000E),                        # bnez v0,0x8010D268 (cutscene pad -> plain walk)
     'walk start: dash unless demo'),
]


def patch(rel, data):
    d = bytearray(data)
    if rel != 'DRA.BIN':
        return bytes(d)
    for va, us, new, label in EDITS:
        o = va - DRA
        cur = bytes(d[o:o + len(us)])
        if cur == new:
            LOG.append('godspeed %s: already' % label); continue
        assert cur == us, (hex(va), cur.hex())
        d[o:o + len(us)] = new
        LOG.append('godspeed ' + label)
    return bytes(d)


if __name__ == '__main__':
    import os, sys
    sys.stdout.reconfigure(encoding='utf-8')
    U = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'U')
    a = patch('DRA.BIN', open(os.path.join(U, 'DRA.BIN'), 'rb').read())
    assert patch('DRA.BIN', a) == a
    print('\n'.join(LOG))
