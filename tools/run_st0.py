"""Boot build, go through menus, wait for Richter stage, walk to Dracula, snapshot dialogue.
python run_st0.py <cue> <outprefix>"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra
from PIL import Image
cue, pre = sys.argv[1], sys.argv[2]
__import__('ra').kill_own(); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(22)
ra.press('start:0.3 wait:5 start:0.3 wait:4 cross:0.3 wait:3 cross:0.3 wait:3 start:0.3 wait:3 cross:0.3 wait:3')
ra.press('cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1')
time.sleep(62)
ra.cmd('SAVE_STATE')
ra.setpad(ra.BTN['left'] | ra.BTN['up'])
shots = []
time.sleep(14)
for i in range(4):
    time.sleep(2.5); shots.append(ra.snap('%s_%02d.png' % (pre, i)))
ra.setpad(0)
for i in range(8):
    time.sleep(2.5); shots.append(ra.snap('%s_%02d.png' % (pre, 4 + i)))
s = Image.new('RGB', (320 * 4, 240 * 3))
for i, f in enumerate(shots):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save(pre + '_sheet.png')
