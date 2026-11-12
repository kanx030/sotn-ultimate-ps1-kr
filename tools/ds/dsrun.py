"""DuckStation (scratch portable copy) boot test: python dsrun.py <name> <image> <fastboot 0/1> [secs] [bios]
Writes settings.ini into the copy, starts it windowed, screenshots the window every 10 s, closes our PID only."""
import sys, os, time, subprocess, ctypes, ctypes.wintypes as W, shutil
from PIL import ImageGrab
DS = r'E:\SOTNKR\test\duckstation_copy'
OUT = r'E:\SOTNKR\test\ds\out'
name, img, fb = sys.argv[1], sys.argv[2], sys.argv[3] == '1'
secs = int(sys.argv[4]) if len(sys.argv) > 4 else 75
bios = sys.argv[5] if len(sys.argv) > 5 else 'scph1001.bin'
extra = sys.argv[6] if len(sys.argv) > 6 else ''
os.makedirs(OUT, exist_ok=True)
ini = f"""[Main]
SettingsVersion = 3
SetupWizardIncomplete = false
StartFullscreen = false
ConfirmPowerOff = false
PauseOnFocusLoss = false
SaveStateOnExit = false
Language = en
[UI]
SetupWizardIncomplete = false
[Logging]
LogLevel = Dev
LogTimestamps = true
LogToFile = true
LogToConsole = false
LogFilter = 
[BIOS]
SearchDirectory = {DS}/bios
PathNTSCU = {bios}
PathNTSCJ = {bios}
PathPAL = {bios}
PatchFastBoot = {'true' if fb else 'false'}
FastForwardBoot = false
[Console]
Region = Auto
Enable8MBRAM = false
[CDROM]
ReadSpeedup = 1
SeekSpeedup = 1
LoadImageToRAM = false
RegionCheck = false
[MemoryCards]
Card1Type = None
Card2Type = None
[Audio]
Backend = Null
{extra.replace('|', chr(10))}
"""
open(os.path.join(DS, 'settings.ini'), 'w').write(ini)
log = os.path.join(DS, 'duckstation.log')
if os.path.exists(log): os.remove(log)
p = subprocess.Popen([os.path.join(DS, 'duckstation-qt-x64-ReleaseLTCG.exe')] + ([] if os.environ.get('DS_GUI') else ['-nogui']) + [
                      '-fastboot' if fb else '-slowboot', img], cwd=DS)
print('pid', p.pid, flush=True)
u = ctypes.windll.user32
def wins():
    r = []
    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, l):
        pid = W.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value == p.pid and u.IsWindowVisible(h):
            rc = W.RECT(); u.GetWindowRect(h, ctypes.byref(rc))
            b = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, b, 256)
            r.append((h, (rc.left, rc.top, rc.right, rc.bottom), b.value))
        return True
    u.EnumWindows(cb, 0); return r
t0 = time.time(); k = 0
try:
    while time.time() - t0 < secs:
        time.sleep(int(os.environ.get('DS_STEP','10')))
        if p.poll() is not None:
            print('EXITED code', p.returncode, 'at', int(time.time() - t0)); break
        ws = wins()
        for h, rc, title in ws:
            if rc[2] - rc[0] < 200: continue
            u.SetForegroundWindow(h); time.sleep(0.3)
            ImageGrab.grab(rc, all_screens=True).save(os.path.join(OUT, f'{name}_{k:02d}.png'))
            print(int(time.time() - t0), 's', title, rc, flush=True)
            break
        k += 1
finally:
    if p.poll() is None:
        subprocess.run(['taskkill', '/pid', str(p.pid), '/f'], capture_output=True)
    time.sleep(1)
    if os.path.exists(log): shutil.copy(log, os.path.join(OUT, name + '.log'))
