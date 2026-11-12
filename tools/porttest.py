"""Emulator driver for the v1.4 port checks (own RetroArch on test/ra2.cfg, port 55366).
Only the PID saved in test/port_ra.pid is ever killed (shared PC: never kill RetroArch by name).

python porttest.py launch <cue>   |  kill  |  snap <out.png>  |  press "<seq>"  |  mem <hexaddr> <len>
"""
import os, sys, time, glob, subprocess
os.environ.setdefault('SOTN_RA_PORT', '55366')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ra

T = r'E:\SOTNKR\test'
CFG = os.path.join(T, 'ra2.cfg')
PIDF = os.path.join(T, 'port_ra.pid')
SHOTS = os.path.join(T, 'screenshots2')
LOG = os.path.join(T, 'ra2.log')

def kill():
    if os.path.exists(PIDF):
        pid = open(PIDF).read().strip()
        if pid:
            subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)
        os.remove(PIDF)
        time.sleep(1)

def launch(cue):
    kill()
    p = subprocess.Popen([ra.RA, '--config', CFG, '--verbose', '--log-file', LOG, '-L', ra.CORE, cue])
    open(PIDF, 'w').write(str(p.pid))
    for _ in range(60):
        time.sleep(0.5)
        if ra.cmd('VERSION', reply=True, timeout=0.5):
            return p.pid
    return p.pid

def snap(out):
    before = set(glob.glob(SHOTS + r'\*.png'))
    ra.cmd('SCREENSHOT')
    for _ in range(60):
        time.sleep(0.1)
        new = set(glob.glob(SHOTS + r'\*.png')) - before
        if new:
            f = new.pop(); time.sleep(0.3)
            if os.path.exists(out): os.remove(out)
            for _ in range(30):
                try:
                    os.replace(f, out); return out
                except PermissionError:
                    time.sleep(0.2)
    raise SystemExit('screenshot failed')

press = ra.press
setpad = ra.setpad
mem = ra.mem
cmd = ra.cmd

def w16(addr):
    return int.from_bytes(mem(addr, 2), 'little')

def w32(addr):
    return int.from_bytes(mem(addr, 4), 'little')

if __name__ == '__main__':
    a = sys.argv[1]
    if a == 'launch': print(launch(sys.argv[2]))
    elif a == 'kill': kill()
    elif a == 'snap': snap(sys.argv[2])
    elif a == 'press': press(sys.argv[2])
    elif a == 'mem': print(mem(int(sys.argv[2], 16), int(sys.argv[3])).hex(' '))

def watch(prefix, n, every, cols=4):
    """n snapshots every `every` s -> <prefix>_sheet.png contact sheet (320x240 cells)."""
    from PIL import Image
    fs = []
    for i in range(n):
        time.sleep(every)
        f = '%s_%02d.png' % (prefix, i); snap(f); fs.append(f)
    ims = [Image.open(f).resize((320, 240)) for f in fs]
    rows = (len(ims) + cols - 1) // cols
    W = Image.new('RGB', (320 * cols, 240 * rows))
    for i, im in enumerate(ims):
        W.paste(im, ((i % cols) * 320, (i // cols) * 240))
    W.save(prefix + '_sheet.png')
    return prefix + '_sheet.png'
