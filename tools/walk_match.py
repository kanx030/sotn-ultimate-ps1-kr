"""Hold right until the screen matches a reference image, then run a follow-up plan. Snapshots along the way.
python walk_match.py <cue> <out> <ref.png> <plan 'left+down:3,right:15'> [maxsecs]"""
import sys, time, os, struct
sys.path.insert(0, os.path.dirname(__file__))
import ra, ramsync
from PIL import Image, ImageChops
cue, out, ref, plan = sys.argv[1:5]; mx = float(sys.argv[5]) if len(sys.argv) > 5 else 90
R = Image.open(ref).convert('L').resize((80, 60))
def diff(p):
    a = Image.open(p).convert('L').resize((80, 60))
    return sum(ImageChops.difference(a, R).getdata()) / 4800
def kill():
    d = ra.mem(0x800733D8 + 64 * 0xBC, 0xBC * 64)
    for i in range(64):
        hp = struct.unpack_from('<h', d, i * 0xBC + 0x3E)[0]
        if 0 < hp < 32767:
            ra.cmd('WRITE_CORE_RAM %x 00 00' % ((0x800733D8 + (64 + i) * 0xBC + 0x3E) & 0x1FFFFF))
    ra.cmd('WRITE_CORE_RAM %x 46 00' % (0x80097BB4 & 0x1FFFFF))
__import__('ra').kill_own(); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(15); ra.cmd('LOAD_STATE'); time.sleep(12)
ramsync.sync('ST/NO3/NO3.BIN')
ra.setpad(ra.BTN['right']); t0 = time.time(); n = 0; best = 999
while time.time() - t0 < mx:
    kill(); time.sleep(0.4)
    p = ra.snap('%s_tmp.png' % out); dv = diff(p); best = min(best, dv)
    if dv < 18: print('matched at %.1fs diff %.1f' % (time.time() - t0, dv)); break
else:
    print('no match, best', best)
shots = []
for part in plan.split(','):
    d, _, t = part.partition(':'); m = 0
    for k in d.split('+'): m |= ra.BTN.get(k, 0)
    ra.setpad(m); t1 = time.time()
    while time.time() - t1 < float(t):
        kill(); time.sleep(1.0); shots.append(ra.snap('%s_%03d.png' % (out, n))); n += 1
ra.setpad(0)
for i in range(4):
    time.sleep(1.5); shots.append(ra.snap('%s_%03d.png' % (out, n))); n += 1
sel = shots[-16:]
s = Image.new('RGB', (320 * 4, 240 * ((len(sel) + 3) // 4)))
for i, f in enumerate(sel):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save(out + '_sheet.png')
