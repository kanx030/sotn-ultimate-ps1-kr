"""Load state, walk to Dracula, wait for fight, dump entity HP fields. Usage: python ent_dump.py <cue> <wait>"""
import sys, time, os, struct
sys.path.insert(0, os.path.dirname(__file__))
import ra
cue = sys.argv[1]; wait = float(sys.argv[2])
os.system('taskkill /im retroarch.exe /f >nul 2>&1'); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(15); ra.cmd('LOAD_STATE'); time.sleep(12)
ra.setpad(ra.BTN['left'] | ra.BTN['up']); time.sleep(16); ra.setpad(0)
time.sleep(wait)
BASE, STRIDE, N = 0x800733D8, 0xBC, 256
def dump():
    d = ra.mem(BASE, STRIDE * N)
    rows = []
    for i in range(N):
        e = d[i * STRIDE:(i + 1) * STRIDE]
        x, y = struct.unpack_from('<hh', e, 2)[0], struct.unpack_from('<hh', e, 6)[0]
        hp = struct.unpack_from('<h', e, 0x3E)[0]
        oid = struct.unpack_from('<H', e, 0x22)[0] if len(e) > 0x24 else 0
        if any(e): rows.append((i, x, y, hp, oid, e[0x20:0x48].hex()))
    return rows
for r in dump(): print(r)
ra.cmd('SAVE_STATE_SLOT 1') if False else None
ra.snap(r'E:\SOTNKR\test\shots\fight.png')
