"""Load ST0 state, sit through dialogue, then auto-win the Dracula fight (enemy HP -> 1, player HP kept),
and keep running until the prologue ends; snapshots + SAVE_STATE at the end. python beat_st0.py <cue> <out> [secs]"""
import sys, time, os, struct
sys.path.insert(0, os.path.dirname(__file__))
import ra
cue, out = sys.argv[1], sys.argv[2]; secs = float(sys.argv[3]) if len(sys.argv) > 3 else 150
__import__('ra').kill_own(); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(15); ra.cmd('LOAD_STATE'); time.sleep(12)
ra.setpad(ra.BTN['left'] | ra.BTN['up']); time.sleep(16)
ra.setpad(ra.BTN['left']); time.sleep(50); ra.setpad(0)
BASE, STRIDE = 0x800733D8, 0xBC
HPV = int(os.environ.get("HPV", "1"))
def w16(a, v): ra.cmd('WRITE_CORE_RAM %x %02x %02x' % (a & 0x1FFFFF, v & 0xFF, (v >> 8) & 0xFF))
t0 = time.time(); k = 0
log = open(out + '_log.txt', 'w')
while time.time() - t0 < secs:
    d = ra.mem(BASE + 64 * STRIDE, STRIDE * 32)
    px = struct.unpack_from('<h', ra.mem(BASE, 4), 2)[0]
    tx = None
    for i in range(32):
        hp = struct.unpack_from('<h', d, i * STRIDE + 0x3E)[0]
        if HPV < hp < 32767:
            w16(BASE + (64 + i) * STRIDE + 0x3E, HPV)
        if 0 < hp < 32767:
            tx = struct.unpack_from('<h', d, i * STRIDE + 2)[0]
    if k % 5 == 0:
        ents = [(64 + i, struct.unpack_from('<h', d, i * STRIDE + 0x3E)[0], struct.unpack_from('<h', d, i * STRIDE + 2)[0]) for i in range(32)]
        log.write('%5.1f px=%d %s\n' % (time.time() - t0, px, ' '.join('%d:%d@%d' % e for e in ents if e[1] not in (0, 32767))))
        log.flush()
    w16(0x80097BB4, 30)
    mv = 0; act = 0
    if tx is not None:
        dx = tx - px
        face = ra.BTN['right'] if dx > 0 else ra.BTN['left']
        if abs(dx) > 70:
            mv = face
        else:
            # head is the weak point: face him, jump, whip near the top of the jump
            ra.setpad(face); time.sleep(0.05); ra.setpad(0); time.sleep(0.03)
            ra.setpad(ra.BTN['cross']); time.sleep(0.25)
            ra.setpad(ra.BTN['cross'] | ra.BTN['square']); time.sleep(0.08)
            ra.setpad(0); time.sleep(0.35)
            mv = -1
    if mv >= 0:
        ra.setpad(mv)
    k += 1
    if k % 40 == 0: ra.snap('%s_%03d.png' % (out, k // 40))
    time.sleep(0.15)
ra.setpad(0)
ra.snap(out + '_end.png')
