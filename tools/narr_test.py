"""Opening-crawl narration test: load the ST0-start state with a new build, RAM-sync the narration patch
(DRA XA lookup + entry; the state holds old DRA/font RAM), set the dub, auto-win Dracula (beat_st0 logic),
then log the XA player state through the crawl and snapshot until Alucard.
python narr_test.py <cue> <outprefix> <jp|ps1> [state.bak]
Takes the shared RetroArch lock (work/ra.lock) and kills only the RetroArch it started."""
import sys, os, time, struct, shutil, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import ra, iso, narration, build

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
cue, out, dub = sys.argv[1], sys.argv[2], sys.argv[3]
state = sys.argv[4] if len(sys.argv) > 4 else os.path.join(ROOT, 'test', 'states', 'testC4_st0start.state.bak')
LOCK = os.path.join(ROOT, 'work', 'ra.lock')

def w(addr, data):
    for k in range(0, len(data), 64):
        ra.cmd('WRITE_CORE_RAM %x %s' % ((addr & 0x1FFFFF) + k, ' '.join('%02x' % b for b in data[k:k + 64])))

def patch_bytes():
    im = iso.Img(os.path.splitext(cue)[0] + '.bin')
    ents = {e['path'].upper(): e for e in im.walk()}
    e = ents['/DRA.BIN;1']; dra = im.read_file(e['lba'], e['size'])
    o = narration.LOOK - 0x800A0000; look = dra[o:o + 52]
    e = ents['/SLUS_000.67;1']; exe = im.read_file(e['lba'], e['size'])
    o = build.exe_off(build.FONT_SRC) + build.NARR_ENT_RAM - build.FONT_RAM; ent = exe[o:o + 16]
    return look, ent

def xa_state():
    m = ra.mem(0x80138440, 0x40)       # 0x80138458 requested index
    f = ra.mem(0x80138F20, 8)          # base LBA, filter file/chan
    loc = ra.mem(0x8013B640, 4)        # setloc MSF
    ln = ra.mem(0x8013AE90, 4)
    cur = ra.mem(0x8013901C, 2)
    return dict(idx=struct.unpack_from('<h', m, 0x18)[0], cur=struct.unpack('<h', cur)[0],
                base=struct.unpack_from('<I', f, 0)[0], file=f[4], chan=f[5], msf=loc[:3].hex(),
                len=struct.unpack('<I', ln)[0])

def beat(secs, log):
    BASE, STRIDE = 0x800733D8, 0xBC
    def w16(a, v): ra.cmd('WRITE_CORE_RAM %x %02x %02x' % (a & 0x1FFFFF, v & 0xFF, (v >> 8) & 0xFF))
    t0 = time.time(); k = 0
    while time.time() - t0 < secs:
        d = ra.mem(BASE + 64 * STRIDE, STRIDE * 32)
        px = struct.unpack_from('<h', ra.mem(BASE, 4), 2)[0]
        tx = None
        for i in range(32):
            hp = struct.unpack_from('<h', d, i * STRIDE + 0x3E)[0]
            if 1 < hp < 32767: w16(BASE + (64 + i) * STRIDE + 0x3E, 1)
            if 0 < hp < 32767: tx = struct.unpack_from('<h', d, i * STRIDE + 2)[0]
        w16(0x80097BB4, 30)
        s = xa_state()
        if k % 10 == 0: log.write('%6.1f fight %s\n' % (time.time() - T0, s)); log.flush()
        if s['idx'] == 0x40: return True
        if tx is not None:
            dx = tx - px; face = ra.BTN['right'] if dx > 0 else ra.BTN['left']
            if abs(dx) > 70: ra.setpad(face)
            else:
                ra.setpad(face); time.sleep(0.05); ra.setpad(0); time.sleep(0.03)
                ra.setpad(ra.BTN['cross']); time.sleep(0.25)
                ra.setpad(ra.BTN['cross'] | ra.BTN['square']); time.sleep(0.08)
                ra.setpad(0); time.sleep(0.35)
        else:
            ra.setpad(0)
        k += 1; time.sleep(0.15)
    return False

def main():
    while True:
        try: os.mkdir(LOCK); break
        except FileExistsError: print('waiting for ra.lock'); time.sleep(20)
    proc = None
    try:
        look, ent = patch_bytes()
        shutil.copyfile(state, os.path.join(ROOT, 'test', 'states', os.path.splitext(os.path.basename(cue))[0] + '.state'))
        proc = subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
        time.sleep(15); ra.cmd('LOAD_STATE'); time.sleep(3)
        w(narration.LOOK, look); w(build.NARR_ENT_RAM, ent)
        fl = ra.mem(0x80097BAF, 1)[0]
        nf = (fl & ~0x28) | (0x20 if dub == 'jp' else 0x08)
        w(0x80097BAF, bytes([nf]))
        log = open(out + '_log.txt', 'w')
        log.write('dub byte %02x -> %02x, look ok %s, entry %s\n' % (fl, nf, ra.mem(narration.LOOK, 52) == look,
                                                                   ra.mem(build.NARR_ENT_RAM, 16).hex()))
        ra.setpad(ra.BTN['left'] | ra.BTN['up']); time.sleep(16)
        ra.setpad(ra.BTN['left']); time.sleep(50); ra.setpad(0)
        global T0; T0 = time.time()
        got = beat(240, log); ra.setpad(0)
        log.write('crawl request seen: %s\n' % got)
        t1 = time.time(); k = 0; snaps = []
        while time.time() - t1 < 200:
            s = xa_state()
            log.write('%6.1f crawl %s\n' % (time.time() - T0, s)); log.flush()
            if k % 6 == 0: snaps.append(ra.snap('%s_%02d.png' % (out, len(snaps))))
            k += 1; time.sleep(5)
        ra.setpad(ra.BTN['right']); time.sleep(3); ra.setpad(0); time.sleep(1)
        snaps.append(ra.snap(out + '_end.png'))
        from PIL import Image
        sh = Image.new('RGB', (320 * 4, 240 * ((len(snaps) + 3) // 4)))
        for i, f in enumerate(snaps):
            sh.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
        sh.save(out + '_sheet.png'); log.close()
    finally:
        if proc: proc.kill()
        os.rmdir(LOCK)

T0 = time.time()
if __name__ == '__main__':
    main()
