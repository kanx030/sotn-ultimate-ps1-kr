"""Load state (prologue start) and walk to Dracula; snapshot dialogue. python walk_st0.py <outprefix>"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra
from PIL import Image
pre = sys.argv[1]
ra.cmd('LOAD_STATE'); time.sleep(5)
ra.setpad(ra.BTN['left'] | ra.BTN['up'])
time.sleep(24)
ra.setpad(0)
shots = []
for i in range(12):
    time.sleep(2); shots.append(ra.snap('%s_%02d.png' % (pre, i)))
s = Image.new('RGB', (320 * 4, 240 * 3))
for i, f in enumerate(shots):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save(pre + '_sheet.png')
