"""Win the prologue Dracula fight (enemy HP -> 1, Richter HP kept) on the running porttest emulator.
python porttest_beat.py <outprefix> [secs]   (adapted from beat_st0.py)"""
import sys, time, struct
import porttest as P
ra = P.ra
out = sys.argv[1]; secs = float(sys.argv[2]) if len(sys.argv) > 2 else 150
BASE, STRIDE = 0x800733D8, 0xBC
def w16(a, v): P.cmd('WRITE_CORE_RAM %x %02x %02x' % (a & 0x1FFFFF, v & 0xFF, (v >> 8) & 0xFF))
t0 = time.time(); k = 0
while time.time() - t0 < secs:
    d = P.mem(BASE + 64 * STRIDE, STRIDE * 32)
    px = struct.unpack_from('<h', P.mem(BASE, 4), 2)[0]
    tx = None
    for i in range(32):
        hp = struct.unpack_from('<h', d, i * STRIDE + 0x3E)[0]
        if 1 < hp < 32767:
            w16(BASE + (64 + i) * STRIDE + 0x3E, 1)
        if 0 < hp < 32767:
            tx = struct.unpack_from('<h', d, i * STRIDE + 2)[0]
    w16(0x80097BB4, 50)
    if tx is not None:
        dx = tx - px
        face = ra.BTN['right'] if dx > 0 else ra.BTN['left']
        if abs(dx) > 70:
            P.setpad(face)
        else:
            P.setpad(face); time.sleep(0.05); P.setpad(0); time.sleep(0.03)
            P.setpad(ra.BTN['cross']); time.sleep(0.25)
            P.setpad(ra.BTN['cross'] | ra.BTN['square']); time.sleep(0.08)
            P.setpad(0); time.sleep(0.35)
    else:
        P.setpad(0)
    k += 1
    if k % 40 == 0: P.snap('%s_%03d.png' % (out, k // 40))
    time.sleep(0.15)
P.setpad(0)
