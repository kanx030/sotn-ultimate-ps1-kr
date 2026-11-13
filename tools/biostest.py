"""BIOS compatibility run: one fresh RetroArch boot with a chosen core + BIOS file.
python biostest.py <tag> <core> <bios|HLE|none> <cue> [seconds] [opt=val ...] [--press "<seq>@<t>" ...]
  core: pcsx_rearmed | mednafen_psx | swanstation
  bios: path to a BIOS file (copied into the scratch system dir under the names the core looks for,
        deleted afterwards), HLE (pcsx_rearmed built-in BIOS), none (empty system dir)
Scratch dir E:\\SOTNKR\\test\\bios_test\\<tag>\\ gets its own cfg (copy of test/ra3.cfg, port 55367), core options,
empty memory-card dir, screenshots and the RetroArch log. Polls g_GameState (0x8003C734; 1 = title) and the
engine step, snaps every 10 s and on each state change. --press needs a --test image (RAM pad hook).
Kills only its own PID (saved to test/bios_ra.pid)."""
import sys, os, time, struct, shutil, subprocess, glob
os.environ['SOTN_RA_PORT'] = '55367'
sys.path.insert(0, os.path.dirname(__file__))
import ra

ROOT = r'E:\SOTNKR\test\bios_test'
PIDF = r'E:\SOTNKR\test\bios_ra.pid'
CORES = r'I:\AttractMode\emulators\RetroArch\cores'
NAMES = {   # names the core looks for (all regions, so the disc region never picks another file)
    'pcsx_rearmed': ['scph1001.bin'],
    'mednafen_psx': ['scph5501.bin', 'scph5500.bin', 'scph5502.bin'],
    'swanstation': ['scph5501.bin', 'scph5500.bin', 'scph5502.bin'],
}

def kill_own():
    if os.path.exists(PIDF):
        pid = open(PIDF).read().strip()
        if pid:
            subprocess.run(['taskkill', '/pid', pid, '/f'], capture_output=True)
            time.sleep(1.5)
        os.remove(PIDF)

def rd():
    r = ra.cmd('READ_CORE_RAM %x %d' % (0x3C728, 0x3C734 - 0x3C728 + 4), reply=True, timeout=0.3)
    if not r or len(r.split()) < 3 or r.split()[2] == '-1':
        return None
    b = bytes(int(x, 16) for x in r.split()[2:])
    r2 = ra.cmd('READ_CORE_RAM %x 4' % 0x3C9A4, reply=True, timeout=0.3)
    step = struct.unpack('<i', bytes(int(x, 16) for x in r2.split()[2:6]))[0] if r2 and len(r2.split()) >= 6 else None
    return struct.unpack('<i', b[12:16])[0], step

def snap(d, name):
    before = set(glob.glob(d + r'\*.png'))
    ra.cmd('SCREENSHOT')
    for _ in range(40):
        time.sleep(0.1)
        new = set(glob.glob(d + r'\*.png')) - before
        if new:
            f = new.pop(); time.sleep(0.3)
            out = os.path.join(d, name + '.png')
            for _ in range(20):
                try:
                    os.replace(f, out); return out
                except PermissionError:
                    time.sleep(0.2)
    return None

def wait_for(cond, timeout):
    t1 = time.time(); s = None
    while time.time() - t1 < timeout:
        try: s = rd()
        except Exception: s = None
        if s and cond(s): return s
        time.sleep(0.2)
    return None

def new_game(shots, lines, t0):
    """title -> main menu -> file select -> new game -> name (blank) -> Alucard defaults -> crawl/movie
    (fast forward) -> prologue (g_GameState 2) -> walk to Dracula -> first dialogue pages. Each step waits
    for the game state/step of the next screen (title 1/2, menu 8/2, file 8/51, name 8/17, player 8/19,
    crawl 5). Needs a --test image (RAM pad hook)."""
    def step(seq, cond, name, timeout=20):
        for _ in range(3):
            ra.press(seq)
            s = wait_for(cond, timeout)
            if s: break
        lines.append('%6.1f %s -> %s' % (time.time() - t0, name, s)); time.sleep(1.0); snap(shots, name)
        return s
    step('start', lambda s: s == (8, 2), 'ng_menu')
    step('cross', lambda s: s == (8, 51), 'ng_file')
    step('cross', lambda s: s == (8, 17), 'ng_name')
    step('start', lambda s: s == (8, 19), 'ng_char')
    ra.press('cross wait:2'); snap(shots, 'ng_opts')
    step('start', lambda s: s[0] == 5, 'ng_crawl')
    ra.cmd('FAST_FORWARD')
    s = wait_for(lambda s: s[0] == 2, 150)
    ra.cmd('FAST_FORWARD'); time.sleep(3)
    lines.append('%6.1f after movie state=%s' % (time.time() - t0, s))
    snap(shots, 'ng_st0')
    ra.press('left+up:22 left:0.2 wait:4'); snap(shots, 'ng_dialog')
    ra.press('wait:6'); snap(shots, 'ng_dialog2')
    lines.append('%6.1f dialogue state=%s' % (time.time() - t0, rd()))

def main():
    args = sys.argv[1:]
    presses = []
    ng = '--ng' in args
    if ng: args.remove('--ng')
    while '--press' in args:
        i = args.index('--press'); presses.append(args[i + 1]); del args[i:i + 2]
    tag, core, bios, cue = args[:4]
    dur = float(args[4]) if len(args) > 4 and '=' not in args[4] else 90
    opts = dict(a.split('=', 1) for a in args[4:] if '=' in a)
    d = os.path.join(ROOT, tag)
    if os.path.exists(d): shutil.rmtree(d)
    sysd, saves, shots = (os.path.join(d, x) for x in ('system', 'saves', 'shots'))
    for x in (sysd, saves, shots): os.makedirs(x)
    copied = []
    if bios not in ('HLE', 'none'):
        for n in NAMES[core]:
            shutil.copy(bios, os.path.join(sysd, n)); copied.append(os.path.join(sysd, n))
    co = {}
    if core == 'pcsx_rearmed':
        co = {'pcsx_rearmed_bios': 'HLE' if bios == 'HLE' else 'auto', 'pcsx_rearmed_show_bios_bootlogo': 'enabled'}
    elif core == 'mednafen_psx':
        co = {'beetle_psx_skip_bios': 'disabled', 'beetle_psx_override_bios': 'disabled'}
    elif core == 'swanstation':
        reg = 'Auto'
        if bios not in ('HLE', 'none'):   # console region of the BIOS (last char of 'System ROM Version x.x mm/dd/yy R')
            v = open(bios, 'rb').read()[0x7FF32:0x7FF60].split(b'\0')[0].strip()
            reg = {b'J': 'NTSC-J', b'E': 'PAL', b'A': 'Auto'}.get(v[-1:], 'Auto')
        if 'swanstation_Console_Region' in opts: reg = opts['swanstation_Console_Region']
        co = {'swanstation_Console_Region': reg, 'swanstation_BIOS_PathNTSCU': 'scph5501.bin', 'swanstation_BIOS_PathNTSCJ': 'scph5500.bin',
              'swanstation_BIOS_PathPAL': 'scph5502.bin', 'swanstation_BIOS_PatchFastBoot': 'false',
              'swanstation_CDROM_RegionCheck': 'false'}
    co.update(opts)
    base = open(r'E:\SOTNKR\test\core-options.cfg', encoding='utf-8').read().splitlines()
    keep = [l for l in base if l.split(' = ')[0] not in co]
    open(os.path.join(d, 'core-options.cfg'), 'w', encoding='utf-8').write(
        '\n'.join(keep + ['%s = "%s"' % kv for kv in co.items()]) + '\n')
    cfg = open(r'E:\SOTNKR\test\ra3.cfg', encoding='utf-8').read().splitlines()
    rep = {'system_directory': sysd, 'savefile_directory': saves, 'screenshot_directory': shots,
           'core_options_path': os.path.join(d, 'core-options.cfg'), 'savestate_directory': d,
           'network_cmd_port': '55367',
           # never pick up the user's per-core/per-game overrides (they set system_directory for PSX cores)
           'auto_overrides_enable': 'false', 'auto_remaps_enable': 'false', 'game_specific_options': 'false',
           'rgui_config_directory': d, 'input_remapping_directory': d}
    cfg = [l for l in cfg if l.split(' = ')[0] not in rep] + ['%s = "%s"' % kv for kv in rep.items()]
    cfg.append('sort_savefiles_enable = "false"'); cfg.append('sort_savestates_enable = "false"')
    open(os.path.join(d, 'ra.cfg'), 'w', encoding='utf-8').write('\n'.join(cfg) + '\n')
    kill_own()
    log = os.path.join(d, 'ra.log')
    p = subprocess.Popen([ra.RA, '--config', os.path.join(d, 'ra.cfg'), '--verbose', '--log-file', log,
                          '-L', os.path.join(CORES, core + '_libretro.dll'), cue])
    open(PIDF, 'w').write(str(p.pid))
    t0 = time.time(); last = None; nexts = 2; lines = []; dumped = False
    pend = []
    for pr in presses:
        seq, _, t = pr.rpartition('@'); pend.append((float(t), seq))
    pend.sort()
    try:
        while time.time() - t0 < dur:
            t = time.time() - t0
            if p.poll() is not None:
                lines.append('%6.1f retroarch exited code %s' % (t, p.returncode)); break
            try: s = rd()
            except Exception: s = None
            if s != last:
                lines.append('%6.1f state=%s step=%s' % (t, *(s if s else (None, None))))
                print(lines[-1], flush=True)
                if s is not None and last is not None and s[0] != last[0]:
                    snap(shots, 'st%d_t%03d' % (s[0], int(t)))
                last = s
            if s == (1, 2) and not dumped:      # title: keep the kernel area (BIOS identification)
                dumped = True
                try: open(os.path.join(d, 'kernel.bin'), 'wb').write(ra.mem(0x80000000, 0x10000))
                except SystemExit: pass
            if t >= nexts:
                snap(shots, 't%03d' % int(t)); nexts += 2 if t < 20 else 10
            if ng and t > 150:
                lines.append('%6.1f no title by 150 s' % t); break
            if ng and s == (1, 2) and t > 5:
                ng = False
                time.sleep(3); lines.append('%6.1f new game' % (time.time() - t0))
                new_game(shots, lines, t0); dur = time.time() - t0 + 5; nexts = dur + 99
            while pend and t >= pend[0][0]:
                seq = pend.pop(0)[1]
                lines.append('%6.1f press %s' % (t, seq)); ra.press(seq)
            time.sleep(0.25)
        snap(shots, 'final')
    finally:
        if p.poll() is None:
            subprocess.run(['taskkill', '/pid', str(p.pid), '/f'], capture_output=True)
        if os.path.exists(PIDF): os.remove(PIDF)
        time.sleep(1)
        for f in copied:
            try: os.remove(f)
            except OSError: pass
    open(os.path.join(d, 'states.txt'), 'w').write('\n'.join(lines) + '\n')
    print('RESULT %s last=%s' % (tag, last))

if __name__ == '__main__':
    main()
