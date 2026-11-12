"""Boot a cue and snapshot each menu step to tune the boot sequence. python boot_probe.py <cue> <outprefix>"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra
from PIL import Image
cue, pre = sys.argv[1], sys.argv[2]
__import__('ra').kill_own(); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(25)
steps = ['start', 'start', 'cross', 'cross', 'start', 'cross', 'cross', 'cross', 'cross', 'cross', 'cross', 'cross']
shots = []
for i, b in enumerate(steps):
    shots.append(ra.snap('%s_%02d.png' % (pre, i)))
    ra.press('%s:0.3 wait:4' % b)
shots.append(ra.snap('%s_%02d.png' % (pre, len(steps))))
s = Image.new('RGB', (320 * 4, 240 * 4))
for i, f in enumerate(shots[:16]):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save(pre + '_sheet.png'); print('done')
