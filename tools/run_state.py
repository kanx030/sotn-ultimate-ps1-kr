"""Launch <cue>, load its state, optionally write RAM patches, walk to Dracula, snap. python run_state.py <cue> <outprefix> [addr=hexbytes ...]"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra
from PIL import Image
cue, pre = sys.argv[1], sys.argv[2]
os.system('taskkill /im retroarch.exe /f >nul 2>&1'); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(15); ra.cmd("LOAD_STATE"); time.sleep(12)
for p in sys.argv[3:]:
    a, h = p.split('='); a = int(a, 16) & 0x1FFFFF
    ra.cmd('WRITE_CORE_RAM %x %s' % (a, ' '.join(h[i:i + 2] for i in range(0, len(h), 2))))
if os.environ.get('RAMSYNC') is not None:
    import ramsync; ramsync.sync(os.environ['RAMSYNC'])
time.sleep(1); print('verify', [ra.mem(int(p.split('=')[0],16),8).hex() for p in sys.argv[3:]])
ra.setpad(ra.BTN['left'] | ra.BTN['up']); time.sleep(float(os.environ.get('UW','24')))
ra.setpad(ra.BTN['left']); time.sleep(float(os.environ.get('LW','8'))); ra.setpad(0)
shots = []
for i in range(12):
    time.sleep(float(os.environ.get('SI','3'))); shots.append(ra.snap('%s_%02d.png' % (pre, i)))
s = Image.new('RGB', (320 * 4, 240 * 3))
for i, f in enumerate(shots):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save(pre + '_sheet.png'); print('done')
