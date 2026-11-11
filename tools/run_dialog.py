"""Boot build, reach ST0, walk to Dracula, snap dialogue frames. python run_dialog.py <cue> <outprefix>"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra
from PIL import Image
cue, pre = sys.argv[1], sys.argv[2]
os.system('taskkill /im retroarch.exe /f >nul 2>&1'); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(25)
for b in ['start', 'start', 'cross', 'cross', 'start', 'cross', 'cross', 'cross', 'cross', 'cross', 'cross']:
    ra.press('%s:0.3 wait:4' % b)
time.sleep(float(os.environ.get('IW', '60')))
ra.cmd('SAVE_STATE')
ra.setpad(ra.BTN['left'] | ra.BTN['up']); time.sleep(20)
ra.setpad(ra.BTN['left']); time.sleep(0.1); ra.setpad(0)
shots = []
for i in range(12):
    time.sleep(1.0); shots.append(ra.snap('%s_%02d.png' % (pre, i)))
s = Image.new('RGB', (320 * 4, 240 * 3))
for i, f in enumerate(shots):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save(pre + '_sheet.png'); print('done')
