"""Load state, RAM-sync an overlay, hold a direction and snapshot. python run_walk.py <cue> <out> <overlay> <dir> <secs> [interval]"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra, ramsync
from PIL import Image
cue, out, ov, dr, secs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
iv = float(sys.argv[6]) if len(sys.argv) > 6 else 2.0
os.system('taskkill /im retroarch.exe /f >nul 2>&1'); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(15); ra.cmd('LOAD_STATE'); time.sleep(12)
ramsync.sync(ov if ov != '-' else None)
# dr: 'right' or a plan 'right:24,left:10,up+left:6'
plan = []
for part in dr.split(','):
    d, _, t = part.partition(':')
    m = 0
    for k in d.split('+'):
        m |= ra.BTN.get(k, 0)
    plan.append((m, float(t) if t else secs))
shots = []; t0 = time.time(); n = 0
ends = []; acc = 0
for m, t in plan:
    acc += t; ends.append((acc, m))
mask = plan[0][0]
ra.setpad(mask)
while time.time() - t0 < secs:
    el = time.time() - t0
    for e, m in ends:
        if el < e:
            if m != mask: mask = m; ra.setpad(mask)
            break
    ra.cmd('WRITE_CORE_RAM %x 46 00' % (0x80097BB4 & 0x1FFFFF))
    if os.environ.get('KILL'):
        import struct
        d = ra.mem(0x800733D8 + 64 * 0xBC, 0xBC * 64)
        for i in range(64):
            hp = struct.unpack_from('<h', d, i * 0xBC + 0x3E)[0]
            if 0 < hp < 32767:
                a = 0x800733D8 + (64 + i) * 0xBC + 0x3E
                ra.cmd('WRITE_CORE_RAM %x 00 00' % (a & 0x1FFFFF))
        ra.setpad(mask | ra.BTN['square']); time.sleep(0.1); ra.setpad(mask)
    time.sleep(iv); shots.append(ra.snap('%s_%03d.png' % (out, n))); n += 1
ra.setpad(0)
k = min(len(shots), 16); sel = shots[-k:]
s = Image.new('RGB', (320 * 4, 240 * ((k + 3) // 4)))
for i, f in enumerate(sel):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save(out + '_sheet.png'); print('done', n)
