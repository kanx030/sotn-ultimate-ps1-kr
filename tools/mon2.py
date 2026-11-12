"""Keep this project's emulator windows on monitor 2 (user rule, 11-13).
python mon2.py [--watch]  : moves visible top-level windows of RetroArch/DuckStation processes whose command
line mentions SOTNKR to monitor 2 (left monitor, X=-1920..0). --watch keeps doing it every second.
RetroArch ignores window_position_x/y on this setup, so windows are moved after they appear."""
import ctypes, subprocess, sys, time, json
from ctypes import wintypes
u = ctypes.WinDLL('user32', use_last_error=True)
MON2 = (-1920, -52, 1920, 1080)

def own_pids():
    ps = ("Get-CimInstance Win32_Process | ? { $_.Name -match 'retroarch|duckstation' -and $_.CommandLine -match 'SOTNKR' }"
          " | % { $_.ProcessId }")
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True).stdout
    return {int(x) for x in out.split() if x.strip().isdigit()}

def move_all(pids):
    moved = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        pid = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(h) and not u.GetWindow(h, 4):   # top-level, unowned
            r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
            if r.left >= 0:                                     # on monitor 1 -> move, keep size
                w, hgt = r.right - r.left, r.bottom - r.top
                x = MON2[0] + 40 + (pid.value % 4) * 40; y = MON2[1] + 40 + (pid.value % 4) * 40
                u.SetWindowPos(h, 0, x, y, w, hgt, 0x0014)      # SWP_NOZORDER | SWP_NOACTIVATE
                moved.append((pid.value, x, y))
        return True
    u.EnumWindows(EnumProc(cb), 0)
    return moved

if __name__ == '__main__':
    if '--watch' in sys.argv:
        p, t = set(), 0
        while True:
            if time.time() - t > 4:                 # process list via PowerShell is slow: refresh every ~4 s
                p, t = own_pids(), time.time()
            if p: move_all(p)
            time.sleep(0.3)
    else:
        print(move_all(own_pids()))
