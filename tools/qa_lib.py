"""QA helpers (interactive). python -c "import qa_lib as q; q.boot(); ..." from E:\\SOTNKR\\tools
boot(state_bak)  kill own RA, copy state -> testZ.state, launch testZ.cue, LOAD_STATE
w(addr, bytes|int, n=4), r(addr, n), r32/r16/r8, snap(name), sheet(names, out)"""
import os, sys, time, shutil, struct, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import ra
CUE = r'E:\SOTNKR\work\build\testZ.cue'
ST = r'E:\SOTNKR\test\states'
QA = r'E:\SOTNKR\test\qa'
os.makedirs(QA, exist_ok=True)
PIDF = os.path.join(QA, 'ra.pid')

def kill():
    if os.path.exists(PIDF):
        pid = open(PIDF).read().strip()
        os.system('taskkill /pid %s /f >nul 2>&1' % pid); time.sleep(1)
        os.remove(PIDF)

def launch():
    kill()
    p = subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, CUE])
    open(PIDF, 'w').write(str(p.pid))
    for _ in range(60):
        time.sleep(1)
        if ra.cmd('VERSION', reply=True, timeout=0.5): break
    time.sleep(8)

def boot(bak=os.path.join(ST, 'testZ_alucard.state.bak'), wait=8):
    shutil.copy(bak, os.path.join(ST, 'testZ.state'))
    if not (os.path.exists(PIDF) and ra.cmd('VERSION', reply=True, timeout=0.5)):
        launch()
    ra.cmd('LOAD_STATE'); time.sleep(wait)

def save(name):
    ra.cmd('SAVE_STATE'); time.sleep(3)
    shutil.copy(os.path.join(ST, 'testZ.state'), os.path.join(ST, 'qa_%s.state.bak' % name))

def w(addr, v, n=4):
    if isinstance(v, int): v = v.to_bytes(n, 'little', signed=v < 0)
    for k in range(0, len(v), 128):
        ra.cmd('WRITE_CORE_RAM %x %s' % ((addr & 0x1FFFFF) + k, ' '.join('%02x' % b for b in v[k:k + 128])))

def r(addr, n): return ra.mem(addr, n)
def r32(a): return struct.unpack('<i', r(a, 4))[0]
def r16(a): return struct.unpack('<h', r(a, 2))[0]
def r8(a): return r(a, 1)[0]

def snap(name):
    p = os.path.join(QA, name if name.endswith('.png') else name + '.png')
    return ra.snap(p)

def press(s): ra.press(s)
def pad(m): ra.setpad(m)
B = ra.BTN

def sheet(names, out, cols=4):
    from PIL import Image
    fs = [os.path.join(QA, n if n.endswith('.png') else n + '.png') for n in names]
    fs = [f for f in fs if os.path.exists(f)]
    rows = (len(fs) + cols - 1) // cols
    s = Image.new('RGB', (320 * cols, 240 * rows))
    for i, f in enumerate(fs):
        s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % cols) * 320, (i // cols) * 240))
    s.save(os.path.join(QA, out)); return out

def killall_enemies():
    d = r(0x800733D8 + 64 * 0xBC, 0xBC * 64)
    for i in range(64):
        hp = struct.unpack_from('<h', d, i * 0xBC + 0x3E)[0]
        if 0 < hp < 32767:
            w(0x800733D8 + (64 + i) * 0xBC + 0x3E, b'\0\0')
