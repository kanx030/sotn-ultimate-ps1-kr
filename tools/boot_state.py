"""Boot <cue> (memory card with one save in slot 1), start a new game, and save a state a few seconds after
the prologue caption ('Final Stage') appears = Richter at the start of ST0. python boot_state.py <cue>"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra
import numpy as np
from PIL import Image
cue = sys.argv[1]
os.system('taskkill /im retroarch.exe /f >nul 2>&1'); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(25)
ra.press('start:0.3 wait:4 start:0.3 wait:4 cross:0.3 wait:3 right:0.2 wait:1 cross:0.3 wait:3')
ra.press('cross:0.2 wait:1 start:0.3 wait:3 cross:0.3 wait:3')
ra.press('cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1')
shot = r'E:\SOTNKR\test\cap\_boot.png'
t = time.time()
while time.time() - t < 200:
    a = np.asarray(Image.open(ra.snap(shot)).convert('RGB')).astype(int)
    if ((a[:, :, 2] > 150) & (a[:, :, 0] < 60) & (a[:, :, 1] < 60)).sum() > 500:
        break
    time.sleep(0.1)
else:
    raise SystemExit('caption not seen')
time.sleep(5); ra.cmd('SAVE_STATE'); time.sleep(3); print('saved after', round(time.time() - t))
