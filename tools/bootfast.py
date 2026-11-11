"""Skip the Konami logo movie (LOGO15XA.STR) at boot and go straight to the title.

SEL overlay entry +0xC (0x801BCFD4) is the boot logo handler, driven by the engine step 0x8003C9A4:
  step 0: wait CD idle, set movie-playing flags (0x8003BDE0, 0x8003C728), movie index 0x8003C100 = 0 (logo), step=1
  step 1: play movie (0x801C2D80) until 0x8003C728 clears, then clear flags, clear the display (0x801BA7F0),
          g_GameState (0x8003C734) = 1 (title), step = 0
Patch: in step 0, after the CD-idle check, jump straight to the step-1 epilogue with s0 = 1, so the flags are
cleared, the display is cleared and the game state becomes Title without starting the stream.
The opening movie (OPN_WS, played from the title when idle) uses another path (0x801BF17C) and is untouched.
SELRIC2.BIN carries the same code at the same offset and gets the same patch."""
import struct, os

FILES = ('ST/SEL/SEL.BIN', 'BIN/SELRIC2.BIN')
BASE = 0x80180000
VA = 0x801BD018
ORIG = struct.pack('<II', 0x3C018004, 0xAC22BDE0)      # lui at,0x8004 ; sw v0,-0x4220(at)
NEW = struct.pack('<II', 0x08000000 | ((0x801BD05C >> 2) & 0x3FFFFFF),   # j 0x801BD05C (epilogue -> title)
                  0x34100001)                          # ori s0,zero,1  (delay slot: new game state = 1)

def patch(rel, data):
    if os.environ.get('BOOTFAST') == '0':                # baseline builds for timing comparisons
        return data
    off = VA - BASE
    cur = bytes(data[off:off + 8])
    if cur == NEW:
        return data
    assert cur == ORIG, '%s: boot logo code differs at %x: %s' % (rel, off, cur.hex())
    d = bytearray(data); d[off:off + 8] = NEW
    return bytes(d)
