"""Load state, RAM-sync, open the menu and walk through a few screens. python menu_test.py <cue> <out> <seq>"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra, ramsync
from PIL import Image
cue, out, seq = sys.argv[1], sys.argv[2], sys.argv[3]
os.system('taskkill /im retroarch.exe /f >nul 2>&1'); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(15); ra.cmd('LOAD_STATE'); time.sleep(12)
ramsync.sync('ST/NO3/NO3.BIN')
shots = []
for i, b in enumerate(seq.split(',')):
    ra.press('%s:0.15 wait:1.2' % b)
    shots.append(ra.snap('%s_%02d.png' % (out, i)))
k = len(shots)
s = Image.new('RGB', (320 * 4, 240 * ((k + 3) // 4)))
for i, f in enumerate(shots):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save(out + '_sheet.png'); print('done')
