"""Boot a build and drive it to the prologue (Richter vs Dracula), saving snapshots.
python run_prologue.py <cue> <outprefix> [seconds]"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra
cue, pre = sys.argv[1], sys.argv[2]
secs = int(sys.argv[3]) if len(sys.argv) > 3 else 120
ra.cmd('QUIT'); time.sleep(1); __import__('ra').kill_own(); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '--verbose', '--log-file', ra.LOG, '-L', ra.CORE, cue])
time.sleep(22)
ra.press('start:0.3 wait:5 start:0.3 wait:4 cross:0.3 wait:3 cross:0.3 wait:3 start:0.3 wait:3 cross:0.3 wait:3')
ra.press('cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1 cross:0.3 wait:1')
t0 = time.time(); n = 0
while time.time() - t0 < secs:
    time.sleep(4)
    ra.snap('%s_%02d.png' % (pre, n)); n += 1
