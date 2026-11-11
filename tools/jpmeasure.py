"""Within-page subtitle timing of the prologue Dracula talk with the JP dub (flag 0x80097BAF = 0x20).
Loads <cue>'s state, sets the JP flag, walks Richter to Dracula and logs the ST0 script pointer (0x801C2AF8)
vs time. Per page (voice op 0b 09 xx xx) prints: when each text line starts / when typing ends, relative to the
page start (= pointer passing the voice op). python jpmeasure.py <cue> <out.json> [delay_after_load]
"""
import sys, time, os, struct, re, json
sys.path.insert(0, os.path.dirname(__file__))
import ra

LO, HI = 0x27c00, 0x28000
PTR = 0x801C2AF8


def run(cue, delay):
    os.system('taskkill /im retroarch.exe /f >nul 2>&1'); time.sleep(1)
    ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
    time.sleep(15); ra.cmd('LOAD_STATE'); time.sleep(delay)
    ra.cmd('WRITE_CORE_RAM %x 20' % 0x97BAF)
    seg = b''.join(ra.mem(0x80180000 + o, 1024) for o in range(LO, HI, 1024))
    ra.setpad(ra.BTN['left'] | ra.BTN['up']); time.sleep(16); ra.setpad(ra.BTN['left']); time.sleep(0.2); ra.setpad(0)
    t0 = time.time(); last = None; log = []
    while time.time() - t0 < 75:
        p = struct.unpack('<I', ra.mem(PTR, 4))[0]
        if p != last: log.append((round(time.time() - t0, 3), p)); last = p
        time.sleep(0.02)
    return seg, log


def analyse(seg, log):
    """pages: voice op offsets; lines: offsets right after 01 (newline) / first text byte after voice op."""
    pages = []
    for m in re.finditer(rb'\x0b\x09\x35.\x0a', seg):
        pages.append(dict(voice=m.group()[2:4].hex(), off=LO + m.start()))
    for i, p in enumerate(pages):
        end = pages[i + 1]['off'] if i + 1 < len(pages) else HI
        body = seg[p['off'] - LO:end - LO]
        # page text ends at the last text byte before the final wait (03 xx ... 06)
        j6 = body.find(b'\x06', 5)
        p['end_off'] = p['off'] + (j6 if j6 > 0 else len(body))
        nl = [p['off'] + 5] + [p['off'] + k + 1 for k in range(5, j6 if j6 > 0 else len(body)) if body[k] == 1]
        p['lines'] = nl

    def reach(a):
        t = [x for x, v in log if v - 0x80180000 >= a]
        return t[0] if t else None
    for p in pages:
        t0 = reach(p['off'] + 5)
        p['t'] = t0
        p['line_t'] = [None if t0 is None or reach(a) is None else round(reach(a) - t0, 2) for a in p['lines']]
        te = reach(p['end_off'] - 4)            # ~ typing finished (before final wait + voice wait)
        p['type_end'] = None if t0 is None or te is None else round(te - t0, 2)
    return pages


if __name__ == '__main__':
    cue, out = sys.argv[1], sys.argv[2]
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 12
    seg, log = run(cue, delay)
    pages = analyse(seg, log)
    json.dump(dict(log=log, seg=seg.hex(), pages=pages), open(out, 'w'))
    for p in pages:
        print(p['voice'], p['t'] and round(p['t'], 2), 'type_end', p['type_end'], 'lines', p['line_t'])
