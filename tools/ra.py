"""RetroArch test driver (paths via E:\\SOTNKR junction).
python ra.py launch <cue>      start emulator
python ra.py cmd <COMMAND>     send network command (SAVE_STATE, LOAD_STATE, SCREENSHOT, PAUSE_TOGGLE, FAST_FORWARD...)
python ra.py mem <hexaddr> <len> [out]
python ra.py keys <seq>        e.g. "enter:0.1 wait:2 x x down x"   (tap keys via SendInput)
python ra.py shot <out.png>    capture emulator window
python ra.py kill
"""
import socket, subprocess, sys, os, time, ctypes
from ctypes import wintypes
RA = r'I:\AttractMode\emulators\RetroArch\retroarch.exe'
CORE = r'I:\AttractMode\emulators\RetroArch\cores\swanstation_libretro.dll'
CFG = r'E:\SOTNKR\test\ra.cfg'
LOG = r'E:\SOTNKR\test\ra.log'
# own ports (SGKR sessions use 55355-55357): ra.cfg 55365, ra2.cfg 55366; override with SOTN_RA_PORT
PORT = int(os.environ.get('SOTN_RA_PORT', '55365'))

def kill_own():
    """Kill only RetroArch processes started for this project (command line mentions SOTNKR).
    Other sessions (e.g. the SGKR project) run their own RetroArch on this shared PC: never kill by name."""
    ps = ("Get-CimInstance Win32_Process -Filter \"name='retroarch.exe'\" | "
          "Where-Object { $_.CommandLine -match 'SOTNKR' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True)

def cmd(c, reply=False, timeout=2.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    s.sendto(c.encode(), ('127.0.0.1', PORT))
    if reply:
        try:
            return s.recvfrom(65536)[0].decode(errors='replace')
        except (socket.timeout, ConnectionResetError):
            return None

def mem(addr, n):
    out = b''
    while n > 0:
        k = min(n, 1024)
        r = cmd('READ_CORE_RAM %x %d' % (addr & 0x1FFFFF, k), reply=True)
        if r is None:
            raise SystemExit('no reply')
        parts = r.split()
        if len(parts) > 2 and parts[2] == '-1':
            raise SystemExit(r)
        out += bytes(int(x, 16) for x in parts[2:])
        addr += k; n -= k
    return out

user32 = ctypes.WinDLL('user32', use_last_error=True)
VK = {'enter': 0x0D, 'x': 0x58, 'z': 0x5A, 's': 0x53, 'a': 0x41, 'up': 0x26, 'down': 0x28, 'left': 0x25,
      'right': 0x27, 'rshift': 0xA1, 'f2': 0x71, 'f4': 0x73, 'f8': 0x77, 'space': 0x20, 'q': 0x51, 'w': 0x57}
EXT = {'up', 'down', 'left', 'right'}

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('i',)
    _fields_ = [('type', wintypes.DWORD), ('i', _I)]

def _send(vk, up, ext):
    scan = user32.MapVirtualKeyW(vk, 0)
    fl = 0x0008 | (0x0002 if up else 0) | (0x0001 if ext else 0)  # SCANCODE
    inp = INPUT(type=1); inp.ki = KEYBDINPUT(0, scan, fl, 0, 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

def find_window():
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if buf.value.startswith('RetroArch') and user32.IsWindowVisible(h):
            res.append(h)
        return True
    user32.EnumWindows(cb, 0)
    return res[0] if res else None

def focus():
    h = find_window()
    if h:
        user32.ShowWindow(h, 9)
        # trick to allow foreground switching
        user32.keybd_event(0x12, 0, 0, 0); user32.SetForegroundWindow(h); user32.keybd_event(0x12, 0, 2, 0)
        time.sleep(0.2)
    return h

def keys(seq):
    focus()
    for tok in seq.split():
        if tok.startswith('wait:'):
            time.sleep(float(tok[5:])); continue
        name, _, hold = tok.partition(':')
        hold = float(hold) if hold else 0.08
        vk = VK[name]
        _send(vk, False, name in EXT); time.sleep(hold); _send(vk, True, name in EXT); time.sleep(0.12)

def shot(out):
    from PIL import ImageGrab
    h = find_window()
    r = wintypes.RECT(); user32.GetClientRect(h, ctypes.byref(r))
    pt = wintypes.POINT(0, 0); user32.ClientToScreen(h, ctypes.byref(pt))
    ctypes.windll.user32.SetProcessDPIAware()
    img = ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + r.right, pt.y + r.bottom), all_screens=True)
    img.save(out)


BTN = {'l2': 0x1, 'r2': 0x2, 'l1': 0x4, 'r1': 0x8, 'tri': 0x10, 'circle': 0x20, 'cross': 0x40, 'square': 0x80,
       'select': 0x100, 'start': 0x800, 'up': 0x1000, 'right': 0x2000, 'down': 0x4000, 'left': 0x8000}
MAILBOX = 0x1FB5F0   # build.MAILBOX_RAM & 0x1FFFFF

def setpad(mask):
    cmd('WRITE_CORE_RAM %x %s' % (MAILBOX, ' '.join('%02x' % b for b in mask.to_bytes(4, 'little'))))

def press(seq):
    """e.g. 'cross start wait:2 down:0.5 up+cross'"""
    for tok in seq.split():
        if tok.startswith('wait:'):
            time.sleep(float(tok[5:])); continue
        name, _, hold = tok.partition(':')
        hold = float(hold) if hold else 0.1
        m = 0
        for n in name.split('+'): m |= BTN[n]
        setpad(m); time.sleep(hold); setpad(0); time.sleep(0.15)

def snap(out):
    import glob
    d = r'E:\SOTNKR\test\screenshots'
    before = set(glob.glob(d + r'\*.png'))
    cmd('SCREENSHOT')
    for _ in range(50):
        time.sleep(0.1)
        new = set(glob.glob(d + r'\*.png')) - before
        if new:
            f = new.pop(); time.sleep(0.2)
            if os.path.exists(out): os.remove(out)
            for _ in range(30):
                try:
                    os.replace(f, out); return out
                except PermissionError:
                    time.sleep(0.2)
    raise SystemExit('screenshot failed')

if __name__ == '__main__':
    ctypes.windll.user32.SetProcessDPIAware()
    a = sys.argv[1]
    if a == 'launch':
        subprocess.Popen([RA, '--config', CFG, '--verbose', '--log-file', LOG, '-L', CORE, sys.argv[2]])
    elif a == 'cmd':
        c = ' '.join(sys.argv[2:])
        print(cmd(c, reply=c.startswith(('GET', 'READ', 'VERSION'))))
    elif a == 'mem':
        d = mem(int(sys.argv[2], 16), int(sys.argv[3]))
        if len(sys.argv) > 4:
            open(sys.argv[4], 'wb').write(d)
        else:
            print(d.hex(' '))
    elif a == 'keys':
        keys(' '.join(sys.argv[2:]))
    elif a == 'shot':
        shot(sys.argv[2])
    elif a == 'press':
        press(' '.join(sys.argv[2:]))
    elif a == 'snap':
        snap(sys.argv[2])
    elif a == 'kill':
        kill_own()


