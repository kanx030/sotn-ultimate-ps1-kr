"""Interactive DuckStation scratch-copy control.
python ctl.py start <image> <fastboot 0/1> [bios] | key <name> [hold_ms] ... | shot <name> | stop"""
import sys, os, time, subprocess, ctypes, ctypes.wintypes as W, shutil, json
DS = r'E:\SOTNKR\test\duckstation_copy'; OUT = r'E:\SOTNKR\test\ds\out'; PIDF = os.path.join(OUT, 'pid.json')
u = ctypes.windll.user32
def wins(pid):
    r = []
    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, l):
        p = W.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h):
            rc = W.RECT(); u.GetWindowRect(h, ctypes.byref(rc))
            if rc.right - rc.left > 200: r.append((h, (rc.left, rc.top, rc.right, rc.bottom)))
        return True
    u.EnumWindows(cb, 0); return r
VK = {'start': 0x0D, 'x': 0x58, 'o': 0x5A, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27, 'tri': 0x53, 'sq': 0x41}
# scan codes
SC = {0x0D: 0x1C, 0x58: 0x2D, 0x5A: 0x2C, 0x26: 0x48, 0x28: 0x50, 0x25: 0x4B, 0x27: 0x4D, 0x53: 0x1F, 0x41: 0x1E}
EXT = {0x26, 0x28, 0x25, 0x27}
def press(vk, ms):
    f = 1 if vk in EXT else 0
    u.keybd_event(vk, SC[vk], f, 0); time.sleep(ms / 1000); u.keybd_event(vk, SC[vk], f | 2, 0)
cmd = sys.argv[1]
if cmd == 'start':
    img, fb = sys.argv[2], sys.argv[3] == '1'; bios = sys.argv[4] if len(sys.argv) > 4 else 'scph1001.bin'
    ini = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'base.ini')).read().format(DS=DS, bios=bios, fb='true' if fb else 'false')
    open(os.path.join(DS, 'settings.ini'), 'w').write(ini)
    log = os.path.join(DS, 'duckstation.log')
    if os.path.exists(log): os.remove(log)
    p = subprocess.Popen([os.path.join(DS, 'duckstation-qt-x64-ReleaseLTCG.exe'), '-nogui',
                          '-fastboot' if fb else '-slowboot', img], cwd=DS)
    json.dump({'pid': p.pid}, open(PIDF, 'w')); print('pid', p.pid)
else:
    pid = json.load(open(PIDF))['pid']
    if cmd == 'stop':
        subprocess.run(['taskkill', '/pid', str(pid), '/f'], capture_output=True); time.sleep(1)
        shutil.copy(os.path.join(DS, 'duckstation.log'), os.path.join(OUT, sys.argv[2] + '.log'))
    else:
        w = wins(pid)
        if not w: print('no window (exited?)'); sys.exit(1)
        h, rc = w[0]
        for _ in range(3):
            u.keybd_event(0x12, 0x38, 0, 0); u.keybd_event(0x12, 0x38, 2, 0)   # Alt tap lifts the foreground lock
            u.ShowWindow(h, 5); u.SetForegroundWindow(h); time.sleep(0.3)
            if u.GetForegroundWindow() == h: break
        print('foreground ok' if u.GetForegroundWindow() == h else 'NOT foreground')
        if cmd == 'key':
            for k in sys.argv[2:]:
                if k.startswith('w'): time.sleep(float(k[1:])); continue
                press(VK[k], 250); time.sleep(0.35)
        elif cmd == 'shot':
            from PIL import ImageGrab
            ImageGrab.grab(rc, all_screens=True).save(os.path.join(OUT, sys.argv[2] + '.png')); print('saved')
