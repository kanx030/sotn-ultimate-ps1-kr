"""Fresh boot -> new game as <char> for HUD plate checks (own emulator, test/hud_ra.pid).
python hud_newgame.py <cue> <alucard|richter|richter_sat|maria_sat|maria_psp> <out_prefix>"""
import sys, time
import hudtest
from hudtest import press, snap
cue, who, out = sys.argv[1:4]
hudtest.launch(cue)
time.sleep(18)
press('start:0.3 wait:5 cross:0.3 wait:4 cross:0.3 wait:4 start:0.3 wait:4')
pick = {'alucard': '', 'richter': 'left:0.2 wait:1', 'richter_sat': 'left:0.2 wait:1',
        'maria_sat': 'right:0.2 wait:1', 'maria_psp': 'right:0.2 wait:1'}[who]
if pick: press(pick)
press('cross:0.3 wait:2')
first = 'right:0.2 wait:0.5 ' if who in ('maria_psp', 'richter_sat') else ''
if who == 'alucard':
    press('cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1')
else:
    press(first + 'cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1')
time.sleep(int(sys.argv[4]) if len(sys.argv) > 4 else 18)
snap(out + '.png')
