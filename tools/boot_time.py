"""Measure boot-to-title time. python boot_time.py <cue> <outprefix> [seconds]
Launches RetroArch, polls game state (0x8003C734), engine step (0x8003C9A4), movie flag (0x8003C728)
every ~50 ms, logs every transition with the time since launch, and snaps a screenshot once per second
(<outprefix>_tNN.png) so the frame where the title logo appears can be checked. Prints the RetroArch PID;
the caller kills it (python ra.py is not used, so other agents' RetroArch is never touched)."""
import sys, time, os, struct, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import ra

cue, pre = sys.argv[1], sys.argv[2]
dur = float(sys.argv[3]) if len(sys.argv) > 3 else 40
p = subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
print('pid', p.pid, flush=True)
t0 = time.time()

def rd():
    r = ra.cmd('READ_CORE_RAM %x %d' % (0x3C728, 0x3C734 - 0x3C728 + 4), reply=True, timeout=0.3)
    if not r or len(r.split()) < 3 or r.split()[2] == '-1':
        return None
    b = bytes(int(x, 16) for x in r.split()[2:])
    r2 = ra.cmd('READ_CORE_RAM %x 4' % 0x3C9A4, reply=True, timeout=0.3)
    step = struct.unpack('<i', bytes(int(x, 16) for x in r2.split()[2:6]))[0] if r2 else None
    r3 = ra.cmd('READ_CORE_RAM %x 4' % 0x73060, reply=True, timeout=0.3)   # DRA title-handler step (g_GameStep)
    gstep = struct.unpack('<i', bytes(int(x, 16) for x in r3.split()[2:6]))[0] if r3 else None
    return struct.unpack('<i', b[12:16])[0], step, struct.unpack('<i', b[0:4])[0], gstep

last = None; nextshot = 1.0; log = []
while time.time() - t0 < dur:
    t = time.time() - t0
    try:
        s = rd()
    except Exception:
        s = None
    if s is not None and s != last:
        line = '%6.2f state=%s step=%s movie=%s gstep=%s' % (t, s[0], s[1], s[2], s[3])
        print(line, flush=True); log.append(line); last = s
    if s is not None and t >= nextshot:
        try:
            ra.snap('%s_t%02d.png' % (pre, int(t)))
        except SystemExit:
            pass
        nextshot = int(t) + 1.0
    time.sleep(0.05)
open(pre + '_log.txt', 'w').write('\n'.join(log) + '\n')
print('pid', p.pid)
