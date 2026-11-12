"""HUD plate checks on a fresh boot (own RetroArch on test/ra2.cfg, port 55366).
Only the PID in test/hud_ra.pid is ever killed.
python hudtest.py launch <cue> | kill | snap <out.png> | press "<seq>" | mem <hex> <n> | vram <out.png> [x_hw y w_hw h]
"""
import os, sys, time
os.environ['SOTN_RA_PORT'] = '55366'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import porttest
porttest.PIDF = os.path.join(porttest.T, 'hud_ra.pid')
from porttest import launch, kill, snap, press, mem, cmd

def vram_now():
    """VRAM (512 rows x 2048 bytes) via a throw-away save state in slot 9 (state is only read, never loaded)."""
    import glob, vram
    cmd('STATE_SLOT 9') if False else None
    d = r'E:\SOTNKR\test\states'
    before = {f: os.path.getmtime(f) for f in glob.glob(d + r'\*')}
    cmd('SAVE_STATE')
    for _ in range(100):
        time.sleep(0.1)
        for f in glob.glob(d + r'\*'):
            if f.endswith(('.png',)): continue
            if before.get(f) != os.path.getmtime(f):
                time.sleep(0.5)
                return vram.vram(f)
    raise SystemExit('state failed')

if __name__ == '__main__':
    a = sys.argv[1]
    if a == 'launch': print(launch(sys.argv[2]))
    elif a == 'kill': kill()
    elif a == 'snap': snap(sys.argv[2])
    elif a == 'press': press(sys.argv[2])
    elif a == 'mem': print(mem(int(sys.argv[2], 16), int(sys.argv[3])).hex(' '))
    elif a == 'vram':
        import numpy as np, vram
        from PIL import Image
        v = vram_now()
        np.save(sys.argv[2] + '.npy', v)
        Image.fromarray(vram.view4(v, 0, 0, 1024, 512) * 17).save(sys.argv[2])
